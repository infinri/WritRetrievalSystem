"""Report fixture target eligibility, not retrieval quality or query execution."""
import argparse
import asyncio
import json
from pathlib import Path

from writ_retrieval.graph.adapter import GRAPH_ID_COALESCE, RelateGraph
from writ_retrieval.retrieval.pipeline import load_pipeline_inputs


async def audit(store, fixtures):
    with RelateGraph(store) as graph:
        inputs = await load_pipeline_inputs(graph)
        ids = {r["id"] for r in await graph.read("MATCH (n) RETURN " + GRAPH_ID_COALESCE.format(v="n") + " AS id")}
    ranked = {n["rule_id"] for n in inputs.candidates}
    report = {}
    for name in ("ground_truth_queries.json", "ground_truth_proc.json"):
        queries = json.loads((fixtures / name).read_text())["queries"]
        targets = [(q["id"], q.get("expected_rule_id") or q["expected_node_ids"][0]) for q in queries]
        report[name] = {
            "queries": len(targets),
            "missing_primary_targets": [q for q, target in targets if target not in ids],
            "primary_targets_excluded_from_ranked_pool": [q for q, target in targets if target in ids and target not in ranked],
        }
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", type=Path, default=Path("data/corpus"))
    parser.add_argument("--fixtures", type=Path, default=Path("tests/fixtures"))
    args = parser.parse_args()
    print(json.dumps(asyncio.run(audit(args.store, args.fixtures)), indent=2))
