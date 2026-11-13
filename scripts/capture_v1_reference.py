"""Capture controlled query results using the UNMODIFIED pinned Writ V1 pipeline.

Usage: python scripts/capture_v1_reference.py --upstream /path/to/Writ

Only import-time database registries are supplied as a shim, avoiding installation
of the original Bolt/service stack. No upstream graph reads are invoked: inputs
come from the separately tested Relate collectors. Both pipelines build real
Tantivy/HNSW indexes from identical inputs and controlled vectors. This is query
mechanics parity, not Neo4j-vs-Relate end-to-end or embedding-model quality parity.
"""
import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tests.fixtures.controlled import ControlledEncoder, QUERIES
from tests.test_extracted_integration import seed_nodes
from writ_retrieval.graph.adapter import RelateGraph
from writ_retrieval.graph.schema import RECORD_LABELS
from writ_retrieval.retrieval.pipeline import load_pipeline_inputs

BASELINE = "ebdafe5450b201339f81e717ed104e6bcfd3fe3e"


async def capture(upstream):
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=upstream, text=True).strip() == BASELINE
    assert not subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=upstream, text=True).strip()
    sys.path.insert(0, str(upstream))
    shim = types.ModuleType("writ.graph.db")
    shim._common = types.SimpleNamespace(RECORD_LABELS=RECORD_LABELS)
    sys.modules["writ.graph.db"] = shim
    from writ.retrieval import pipeline as original

    with tempfile.TemporaryDirectory() as temp:
        os.environ["WRIT_FRICTION_LOG"] = str(Path(temp) / "diagnostics.jsonl")
        original.get_hnsw_cache_dir = lambda: str(Path(temp) / "indexes" / "hnsw")
        store = Path(temp) / "graph"
        seed_nodes(store)
        with RelateGraph(store) as graph:
            inputs = await load_pipeline_inputs(graph)
        p = original.assemble_pipeline(inputs, embedding_model=ControlledEncoder(), abstention_threshold=0.3)
        results = [{k: v for k, v in p.query(**q).items() if k != "latency_ms"} for q in QUERIES]
    modules = ["pipeline", "ranking", "keyword", "embeddings"]
    source_hashes = {m: hashlib.sha256((upstream / f"writ/retrieval/{m}.py").read_bytes()).hexdigest() for m in modules}
    return {"baseline": BASELINE, "source_sha256": source_hashes, "encoder": "controlled synthetic vectors (384d)", "results": results}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", type=Path, required=True)
    args = parser.parse_args()
    result = asyncio.run(capture(args.upstream.resolve()))
    target = ROOT / "tests/fixtures/v1-controlled-results.json"
    target.write_text(json.dumps(result, indent=2) + "\n")
    print(target)
