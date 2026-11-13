"""Paired per-query comparisons; publish wins, losses and unchanged results."""
import argparse
import json
from pathlib import Path


def read(path): return [json.loads(line) for line in path.read_text().splitlines()]


def paired(left, right):
    a = {r["id"]: r for r in left}; b = {r["id"]: r for r in right}
    if a.keys() != b.keys(): raise ValueError("different query sets")
    result = {"improved_rr5": [], "regressed_rr5": [], "unchanged_rr5": [], "changed_outputs": []}
    timing = {"uncached_ms", "cached_ms"}
    for ident in a:
        before, after = a[ident], b[ident]
        delta = after.get("rr5", 0) - before.get("rr5", 0)
        group = "improved_rr5" if delta > 1e-12 else "regressed_rr5" if delta < -1e-12 else "unchanged_rr5"
        result[group].append({"id": ident, "cohort": before["cohort"], "delta": delta})
        if {k:v for k,v in before.items() if k not in timing} != {k:v for k,v in after.items() if k not in timing}:
            result["changed_outputs"].append(ident)
    return result


def compare(baseline, candidate):
    old = json.loads((baseline/"summary.json").read_text()); new = json.loads((candidate/"summary.json").read_text())
    for key in ("model", "corpus_sha256", "fixture_sha256", "settings"):
        if old[key] != new[key]: raise ValueError(f"comparison changed {key}")
    return {"same_artifacts_and_settings": True,
            "phase2_vs_baseline": {arm: paired(read(baseline/f"{arm}.jsonl"), read(candidate/f"{arm}.jsonl")) for arm in old["arms"]},
            "graph_vs_no_graph": paired(read(candidate/"hybrid_no_graph.jsonl"), read(candidate/"hybrid_graph.jsonl")),
            "limits": "Paired descriptive differences on fixed judgments, not statistical or causal evidence. Changed outputs include scores and relationships."}


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('baseline', type=Path);p.add_argument('candidate', type=Path);p.add_argument('--output', type=Path, required=True)
    args=p.parse_args();args.output.write_text(json.dumps(compare(args.baseline,args.candidate),indent=2)+'\n')
