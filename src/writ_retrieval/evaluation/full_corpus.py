"""Reproducible retrieval ablations with explicit eligibility and per-query evidence.

Pure lexical has no cosine abstention; all ANN-containing arms use the same 0.30
survivor gate. No-graph renormalizes the other V1 weights. Query latency includes
one uncached encode; repeated timings use the cached encoder, reported separately.
"""
from __future__ import annotations
import argparse
import asyncio
from dataclasses import asdict
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import resource
import statistics
import subprocess
import time

from writ_retrieval.graph.adapter import RelateGraph
from writ_retrieval.graph.importer import CORPUS_SHA256, import_corpus
from writ_retrieval.retrieval.embeddings import OnnxEmbeddingModel
from writ_retrieval.retrieval.pipeline import assemble_pipeline, load_pipeline_inputs, RetrievalPipeline
from writ_retrieval.retrieval.ranking import RankingWeights
from writ_retrieval.retrieval.traversal import AdjacencyCache


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def metrics(rows):
    if not rows:
        return {"n": 0}
    return {"n": len(rows), **{k: sum(r[k] for r in rows) / len(rows) for k in ("hit5", "rr5", "rr10", "ndcg10")},
            "abstentions": sum(r["mode"] == "abstained" for r in rows)}


def scores(ids, expected):
    import math
    rank = ids.index(expected[0]) + 1 if expected[0] in ids else 0
    gains = {ident: (2 if i == 0 else 1) for i, ident in enumerate(expected)}
    dcg = sum((2 ** gains.get(ident, 0) - 1) / math.log2(i + 2) for i, ident in enumerate(ids[:10]))
    ideal = sum((2 ** gain - 1) / math.log2(i + 2) for i, gain in enumerate(sorted(gains.values(), reverse=True)[:10]))
    return {"hit5": int(0 < rank <= 5), "rr5": 1 / rank if 0 < rank <= 5 else 0,
            "rr10": 1 / rank if 0 < rank <= 10 else 0, "ndcg10": dcg / ideal if ideal else 0}


class EmptyKeyword:
    def search(self, *args, **kwargs): return []

class EmptyVector:
    def search(self, *args, **kwargs): return []


async def evaluate(args):
    if args.repeats < 1: raise ValueError("repeats must be positive")
    args.output.mkdir(parents=True, exist_ok=True)
    if args.store.exists():
        raise FileExistsError("use a fresh evaluation store to guarantee pinned corpus contents")
    import_corpus(args.fixtures / "writ-corpus.cypher", args.store)
    if digest(args.fixtures / "writ-corpus.cypher") != CORPUS_SHA256:
        raise ValueError("wrong corpus")
    # Verify actual model bytes, not just a caller-supplied manifest.
    from importlib.util import spec_from_file_location, module_from_spec
    spec = spec_from_file_location("model_setup", args.fixtures.parents[1] / "scripts/prepare_model.py")
    setup = module_from_spec(spec); spec.loader.exec_module(setup)
    for name in ("model.onnx", "tokenizer.json"):
        if digest(args.model_dir / name) != setup.EXPECTED_SHA256[name]:
            raise ValueError(f"unpinned artifact: {name}")
    os.environ["WRIT_RETRIEVAL_CACHE"] = str(args.cache)
    began = time.perf_counter()
    with RelateGraph(args.store) as db:
        inputs = await load_pipeline_inputs(db)
        rules = [dict(r["r"]) for r in await db.read("MATCH (r:Rule) RETURN r")]
        # Verify the persistent graph really is the pinned dump: no feedback or records.
        actual = {k: v for k, v in (await db.read("MATCH (n) RETURN count(n) AS nodes"))[0].items()}
        if actual["nodes"] != 468 or len(rules) != 288:
            raise ValueError("evaluation requires an unmodified pinned corpus store")
        edges = (await db.read("MATCH ()-[r]->() RETURN count(r) AS edges"))[0]["edges"]
        if edges != 1268:
            raise ValueError("modified graph")
    model = OnnxEmbeddingModel(args.model_dir)
    pipeline = assemble_pipeline(inputs, embedding_model=model, abstention_threshold=0.30)
    build_seconds = time.perf_counter() - began
    mandatory = {r["rule_id"] for r in rules if (r.get("mandatory") or r.get("always_on")) and not r.get("superseded")}
    ranked = set(inputs.rule_metadata)
    semantic = {ident for ident in ranked if ("semantic" in pipeline._routes_for(ident) if inputs.node_routes else
                 inputs.rule_metadata[ident].get("node_type", "Rule") == "Rule" and inputs.rule_metadata[ident].get("domain", "").lower() not in {"process", "communication", "meta-authoring"})}
    all_queries = []
    for filename, cohort, key in [("ground_truth_queries.json", "coding", "queries"), ("ground_truth_proc.json", "methodology", "queries"), ("ground_truth_negatives.json", "negative", "negatives")]:
        for q in json.loads((args.fixtures / filename).read_text())[key]:
            expected = q.get("expected_node_ids") or ([q["expected_rule_id"]] if q.get("expected_rule_id") else [])
            all_queries.append({**q, "cohort": cohort, "expected": expected})
    base = RankingWeights()
    nog = RankingWeights(*base.first_pass_weights(), w_graph=0)
    arms = {
        "lexical": (RankingWeights(1, 0, 0, 0, 0), 0, EmptyVector(), pipeline._keyword, AdjacencyCache()),
        "vector": (RankingWeights(0, 1, 0, 0, 0), .30, pipeline._vector, EmptyKeyword(), AdjacencyCache()),
        "hybrid_no_graph": (nog, .30, pipeline._vector, pipeline._keyword, AdjacencyCache()),
        "hybrid_graph": (base, .30, pipeline._vector, pipeline._keyword, inputs.adjacency_cache),
    }
    output = {"schema": 1, "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
              "label": args.label, "corpus_sha256": CORPUS_SHA256, "model": {"revision": setup.REVISION, "sha256": {n: digest(args.model_dir / n) for n in ("model.onnx", "tokenizer.json")}},
              "fixture_sha256": {p.name: digest(p) for p in args.fixtures.glob("ground_truth_*.json")},
              "settings": {"budget_tokens": args.budget, "repeats": args.repeats, "candidate_limits": [50, 50], "project": "evaluation", "coding": "default semantic routes", "methodology": "explicit doctrine types, semantic weights", "ndcg": "primary gain 2, other listed targets gain 1; unlisted=0 for this incomplete judgment set", "hnsw": {"M": 16, "ef_construction": 200, "ef_search": 50, "insert_threads": 1}, "query_order": "fixture order", "onnx_threads": {"intra": model._session.get_session_options().intra_op_num_threads, "inter": model._session.get_session_options().inter_op_num_threads}},
              "environment": {"python": platform.python_version(), "platform": platform.platform(), "cpu_count": os.cpu_count(), "affinity_count": len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None, "packages": {n: importlib.metadata.version(n) for n in ("relate-db", "tantivy", "hnswlib", "numpy", "onnxruntime", "tokenizers")}},
              "build_seconds": build_seconds, "arms": {}}
    for name, (weights, threshold, vector, keyword, cache) in arms.items():
        p = RetrievalPipeline(keyword, vector, cache, pipeline.encoder, inputs.rule_metadata, weights=weights,
                              abstention_threshold=threshold, abstractions=inputs.abstractions, node_routes=inputs.node_routes)
        rows = []
        for q in all_queries:
            kwargs = dict(project="evaluation", budget_tokens=args.budget)
            if q["cohort"] == "methodology":
                kwargs["node_types"] = ["Rule", "Skill", "Playbook", "Technique", "AntiPattern", "ForbiddenResponse"]
            p.encoder.cache_clear()
            start = time.perf_counter(); result = p.query(q["query"], **kwargs); uncached_ms = (time.perf_counter() - start) * 1000
            cached_ms = []
            for _ in range(args.repeats):
                start = time.perf_counter(); p.query(q["query"], **kwargs); cached_ms.append((time.perf_counter() - start) * 1000)
            ids = [r["rule_id"] for r in result["rules"]]
            row = {"id": q["id"], "query": q["query"], "cohort": q["cohort"], "expected": q["expected"],
                   "ranked_eligible": bool(q["expected"] and q["expected"][0] in ranked),
                   "route_eligible": bool(q["expected"] and q["expected"][0] in (semantic if q["cohort"] == "coding" else ranked)),
                   "mandatory_delivery": bool(q["expected"] and q["expected"][0] in mandatory),
                   "mode": result["mode"], "abstain_signal": result.get("abstain_signal"), "total_candidates": result["total_candidates"],
                   "rules": [{k: r.get(k) for k in ("rule_id", "node_type", "score", "similarity", "relationships")} for r in result["rules"]],
                   "uncached_ms": uncached_ms, "cached_ms": cached_ms,
                   **(scores(ids, q["expected"]) if q["expected"] else {})}
            rows.append(row)
        with (args.output / f"{name}.jsonl").open("w") as f:
            for row in rows: f.write(json.dumps(row, sort_keys=True) + "\n")
        output["arms"][name] = {"weights": asdict(weights), "abstention_threshold": threshold,
            "cohorts": {cohort: {subset: metrics([r for r in rows if r["cohort"] == cohort and (subset == "full" or r[subset])]) for subset in ("full", "ranked_eligible", "route_eligible")} for cohort in ("coding", "methodology")},
            "negative": {"n": 20, "false_injections": sum(bool(r["rules"]) for r in rows if r["cohort"] == "negative")},
            "uncached_latency_ms": {"median": statistics.median(r["uncached_ms"] for r in rows), "p95": sorted(r["uncached_ms"] for r in rows)[int(.95 * (len(rows)-1))]},
            "cached_latency_ms": {"median": statistics.median(t for r in rows for t in r["cached_ms"]), "p95": sorted(t for r in rows for t in r["cached_ms"])[int(.95 * (len(rows)*args.repeats-1))]},
            "process_peak_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024}
    output["limitations"] = ["Local export equivalence unverified", "Incomplete relevance judgments; unlisted context is unjudged", "Lexical still pays unused encoder call for common harness; do not interpret as optimized lexical latency", "ru_maxrss is process lifetime high-water RSS, Linux KiB, cumulative across arms", "Corpus-only feedback/record effects require the separate scenario", "Single host, not a controlled performance claim"]
    (args.output / "summary.json").write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps({arm: val["cohorts"]["coding"]["full"] for arm, val in output["arms"].items()}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", type=Path, default=Path("data/evaluation-corpus"))
    parser.add_argument("--fixtures", type=Path, default=Path("tests/fixtures"))
    parser.add_argument("--model-dir", type=Path, default=Path("data/model"))
    parser.add_argument("--cache", type=Path, default=Path("data/evaluation-indexes"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--label", default="baseline-before-phase2")
    parser.add_argument("--budget", type=int, default=2000)
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    asyncio.run(evaluate(args))

if __name__ == "__main__": main()
