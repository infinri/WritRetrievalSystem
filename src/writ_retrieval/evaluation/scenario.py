"""Replay the synthetic connected workflow through supported CLI operations.

50 synthetic outcomes exercise the unchanged confidence threshold. They do not
establish real-world reliability or statistically independent causal evidence.
"""
import argparse
import asyncio
from dataclasses import asdict
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time

from writ_retrieval.graph.identity import Key
from writ_retrieval.memory.store import LocalStore, claim_hash
from writ_retrieval.memory.service import ConnectedSession
from writ_retrieval.retrieval.embeddings import OnnxEmbeddingModel
from writ_retrieval.retrieval.pipeline import load_pipeline_inputs, RetrievalPipeline
from writ_retrieval.retrieval.ranking import RankingWeights
from writ_retrieval.retrieval.traversal import AdjacencyCache
from .full_corpus import EmptyKeyword, EmptyVector, digest


def cli(store, command, *arguments, stdin=None):
    result = subprocess.run([sys.executable, "-m", "writ_retrieval.cli", command, *map(str, arguments), "--store", str(store)], input=stdin, text=True, capture_output=True)
    if result.returncode: raise RuntimeError(result.stderr)
    return json.loads(result.stdout)


async def measure(args, phase):
    os.environ["WRIT_RETRIEVAL_CACHE"] = str(args.cache)
    model = OnnxEmbeddingModel(args.model_dir)
    with LocalStore(args.store) as db:
        session = ConnectedSession(db, model); await session.refresh()
        p = session.pipeline
        arms = {
            "lexical": (RankingWeights(1,0,0,0,0), p._keyword, EmptyVector(), AdjacencyCache(), 0),
            "vector": (RankingWeights(0,1,0,0,0), EmptyKeyword(), p._vector, AdjacencyCache(), .3),
            "hybrid_no_graph": (RankingWeights(*RankingWeights().first_pass_weights(), w_graph=0), p._keyword, p._vector, AdjacencyCache(), .3),
            "hybrid_graph": (RankingWeights(), p._keyword, p._vector, p._cache, .3),
        }
        rows = []
        for query in json.loads((args.examples / "queries.json").read_text()):
            for arm, (weights, keyword, vector, cache, threshold) in arms.items():
                pp = RetrievalPipeline(keyword, vector, cache, p.encoder, p._metadata, weights=weights, abstention_threshold=threshold)
                start = time.perf_counter(); result = pp.query(query["query"], project=query["project"], budget_tokens=2000)
                rows.append({"phase": phase, "id": query["id"], "arm": arm, "project": query["project"], "latency_ms": (time.perf_counter()-start)*1000,
                             "expected_rule": query["expected_rule"], "primary_hit5": query["expected_rule"] in [r["rule_id"] for r in result["rules"]] if query["expected_rule"] else None,
                             "history_hit": False if query["expected_history"] else None, "result": result})
            start = time.perf_counter(); connected = await session.context(query["query"], project=query["project"], project_root="/repo")
            history = {d["decision_id"] for d in connected["recall"]["decisions"]} | {r["ref"]["id"] for r in connected["connected"]["records"] if r["ref"]["label"] == "Decision"}
            leak = [marker for marker in query["forbidden"] if marker in json.dumps(connected)]
            rows.append({"phase": phase, "id": query["id"], "arm": "connected", "project": query["project"], "latency_ms": (time.perf_counter()-start)*1000,
                         "expected_rule": query["expected_rule"], "primary_hit5": query["expected_rule"] in [r["rule_id"] for r in connected["guidance"]["rules"]] if query["expected_rule"] else None,
                         "history_hit": query["expected_history"] in history if query["expected_history"] else None,
                         "forbidden_markers": leak, "provenance_correct": all(r["ref"]["project"] in {query["project"], "_shared"} and r["provenance"] == "record" and r["source_refs"] for r in connected["connected"]["records"]),
                         "result": connected})
        return rows


def run(args):
    if args.store.exists(): raise ValueError("scenario needs a new store")
    args.output.mkdir(parents=True, exist_ok=True)
    # Pin the model exactly as in the corpus experiment.
    from .full_corpus import digest
    import importlib.util
    spec = importlib.util.spec_from_file_location("setup_model", args.examples.parents[1] / "scripts/prepare_model.py")
    setup = importlib.util.module_from_spec(spec); spec.loader.exec_module(setup)
    assert all(digest(args.model_dir / name) == setup.EXPECTED_SHA256[name] for name in ("model.onnx", "tokenizer.json"))
    proposal = cli(args.store, "propose", args.examples/"proposal.json", "--create")
    cli(args.store, "propose", args.examples/"async-proposal.json")
    # Guidance is available before history exists.
    before_capture = asyncio.run(measure(args, "guidance_only"))
    captured = cli(args.store, "capture", args.examples/"records.json")
    replay = cli(args.store, "capture", args.examples/"records.json")
    cli(args.store, "record-lifecycle", args.examples/"supersede.json")
    cli(args.store, "record-lifecycle", args.examples/"delete.json")
    # Every CLI operation above closed its connection; measure opens a fresh store.
    after_restart = asyncio.run(measure(args, "captured_restart"))
    outcomes = []
    for i in range(50):
        outcomes.append({"label": "Outcome", "data": {"project": "payments", "ts": f"2026-11-13T11:{i:02d}:00Z", "source_refs": [f"synthetic:parameter-case/{i}"], "outcome_id": f"E-{i:02d}",
                         "decision_ref": Key("payments", "Decision", "D-CURRENT").as_dict(), "result": "pass" if i < 40 else "fail", "summary": "Synthetic threshold exercise; not real user evidence"}})
    outcomes_file = args.output/"threshold-outcomes.json"; outcomes_file.write_text(json.dumps(outcomes, indent=2)+"\n")
    cli(args.store, "capture", outcomes_file)
    signals = [{"rule_ref": Key("writ", "Rule", "MEM-SQL-PARAM-001").as_dict(), "claim_hash": claim_hash(proposal),
                "outcome_ref": Key("payments", "Outcome", f"E-{i:02d}").as_dict(), "signal": "positive" if i < 40 else "negative", "source_ref": f"synthetic:parameter-case/{i}"} for i in range(50)]
    batch = {"project": "payments", "batch_id": "synthetic-threshold-50", "signals": signals}
    batch_file = args.output/"feedback.json"; batch_file.write_text(json.dumps(batch, indent=2)+"\n")
    # Verify served metadata refresh on a running session, then durable replay from CLI.
    async def feedback_running():
        os.environ["WRIT_RETRIEVAL_CACHE"] = str(args.cache)
        with LocalStore(args.store) as db:
            service = ConnectedSession(db, OnnxEmbeddingModel(args.model_dir)); await service.refresh()
            before = service.pipeline.query("SQL parameters payment")
            applied = service.apply_feedback(**batch)
            after = service.pipeline.query("SQL parameters payment")
            return {"receipt": applied, "before": before, "after": after}
    running = asyncio.run(feedback_running())
    replay_feedback = cli(args.store, "feedback", batch_file)
    after_feedback = asyncio.run(measure(args, "feedback_restart"))
    artifact = cli(args.store, "review-prepare", args.examples/"rule-ref.json")
    (args.output/"review.json").write_text(json.dumps(artifact, indent=2)+"\n")
    rows = before_capture + after_restart + after_feedback
    (args.output/"queries.jsonl").write_text("".join(json.dumps(row, sort_keys=True)+"\n" for row in rows))
    checks = {"capture_replay_idempotent": all(r["replayed"] for r in replay), "feedback_replay_idempotent": replay_feedback["replayed"],
              "no_forbidden_context": all(not r.get("forbidden_markers") for r in rows),
              "provenance_correct": all(r.get("provenance_correct", True) for r in rows),
              "candidate_not_approved": running["receipt"]["states"][0]["authority"] == "ai-provisional",
              "contradictory_history_retained": any(r["arm"] == "connected" and r["phase"] == "captured_restart" and r["id"] == "S1" and any(n["ref"]["id"] == "FAIL" and n["result"] == "fail" for n in r["result"]["connected"]["records"]) for r in rows)}
    summary = {"synthetic": True, "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
               "model_sha256": {name: digest(args.model_dir/name) for name in ("model.onnx", "tokenizer.json")},
               "fixture_sha256": {p.name: digest(p) for p in args.examples.glob('*.json')}, "checks": checks,
               "threshold_state": running["receipt"], "running_refresh": running,
               "audit": cli(args.store, "audit"), "peak_process_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
               "summary": {phase: {arm: {"primary_hit5": sum(r["primary_hit5"] is True for r in rows if r["phase"] == phase and r["arm"] == arm),
                                         "primary_judged": sum(r["primary_hit5"] is not None for r in rows if r["phase"] == phase and r["arm"] == arm),
                                         "history_hit": sum(r["history_hit"] is True for r in rows if r["phase"] == phase and r["arm"] == arm),
                                         "history_judged": sum(r["history_hit"] is not None for r in rows if r["phase"] == phase and r["arm"] == arm)} for arm in ("lexical", "vector", "hybrid_no_graph", "hybrid_graph", "connected")} for phase in ("guidance_only", "captured_restart", "feedback_restart")},
               "limitations": ["Six authored synthetic queries, not a general benchmark", "Guidance-only arms have no history channel by design", "50 synthetic correlated outcomes only exercise the confidence algorithm", "Connected request latency includes graph refresh, recall and rendering; ranked-only latency does not", "No causal outcome or general reliability claim"]}
    (args.output/"summary.json").write_text(json.dumps(summary, indent=2)+"\n")
    print(json.dumps(checks, indent=2))
    if not all(checks.values()): raise AssertionError("scenario controls failed")


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--store", type=Path, required=True); p.add_argument("--output", type=Path, required=True)
    p.add_argument("--model-dir", type=Path, default=Path("data/model")); p.add_argument("--cache", type=Path, default=Path("data/scenario-indexes"))
    p.add_argument("--examples", type=Path, default=Path("examples/phase2"))
    run(p.parse_args())
if __name__ == '__main__': main()
