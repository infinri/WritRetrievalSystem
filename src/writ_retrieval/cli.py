"""Standalone Writ retrieval, decision recall, and persistent Relate demo.

The synthetic fixture demonstrates Writ's decision-memory relationship model.
Rule retrieval and decision recall are separate commands; neither authorizes actions.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import relate


DEMO_PROJECT = "writ-demo"
DEMO_PATH = "src/payments.py"

# Synthetic examples, not records harvested from a real project.
_NODES = (
    ("Rule", {
        "id": "PARAM-001", "rule_id": "PARAM-001",
        "statement": "Use parameterized SQL queries.",
        "trigger": "When building a SQL query", "domain": "database",
        "provenance": "hand-authored",
    }),
    ("Decision", {
        "id": "DEC-001", "decision_id": "DEC-001",
        "title": "Parameterize payment lookup", "ts": "2026-11-13T00:00:00Z",
        "governing_rule_ids": ["PARAM-001"],
        "planned_files": json.dumps([{"path": DEMO_PATH, "reason": "Use SQL parameters"}]),
        "rationale": "Parameterize the payment lookup to keep user input out of SQL syntax.",
    }),
    ("FileChange", {
        "id": "CHANGE-001", "change_id": "CHANGE-001", "path": DEMO_PATH,
        "commit_hash": "COMMIT-001", "ts": "2026-11-13T00:00:01Z",
        "reason": "Use SQL parameters",
    }),
    ("Commit", {
        "id": "COMMIT-001", "commit_hash": "COMMIT-001",
        "subject": "Parameterize payment lookup",
    }),
)
_EDGES = (
    ("FileChange", "CHANGE-001", "MOTIVATED_BY", "Decision", "DEC-001"),
    ("Decision", "DEC-001", "GOVERNED_BY", "Rule", "PARAM-001"),
    ("Commit", "COMMIT-001", "INCLUDES", "FileChange", "CHANGE-001"),
)


def seed_demo(store: Path) -> dict:
    """Create or reopen a persistent store and merge the synthetic fixture."""
    store.parent.mkdir(parents=True, exist_ok=True)
    db = relate.connect(str(store))
    try:
        for label, properties in _NODES:
            # Labels, property names and relationship types are code constants;
            # property values are always parameters.
            assignments = ", ".join(f"n.{key} = ${key}" for key in properties if key != "id")
            db.execute(
                f"MERGE (n:{label} {{project: $project, id: $id}}) SET {assignments}",
                {"project": DEMO_PROJECT, **properties},
            )
        for src_label, source, relationship, dst_label, target in _EDGES:
            db.execute(
                f"MATCH (a:{src_label} {{project: $project, id: $source}}), "
                f"(b:{dst_label} {{project: $project, id: $target}}) "
                f"MERGE (a)-[:{relationship}]->(b)",
                {"project": DEMO_PROJECT, "source": source, "target": target},
            )
        return {"store": str(store), "project": DEMO_PROJECT, "sample_path": DEMO_PATH}
    finally:
        db.close()


def context_for_path(store: Path, path: str, project: str = DEMO_PROJECT) -> list[dict]:
    """Follow a file change to its decision, rule and commit within one project."""
    if not store.exists():
        raise FileNotFoundError(f"Store does not exist: {store}. Run 'writ-retrieval init-demo' first.")
    db = relate.connect(str(store))
    try:
        return [dict(row) for row in db.execute(
            "MATCH (f:FileChange {project: $project, path: $path})"
            "-[:MOTIVATED_BY]->(d:Decision {project: $project})"
            "-[:GOVERNED_BY]->(r:Rule {project: $project}), "
            "(c:Commit {project: $project})-[:INCLUDES]->(f) "
            "RETURN f.path AS path, f.id AS change_id, d.id AS decision_id, "
            "d.rationale AS rationale, r.id AS rule_id, r.statement AS rule, "
            "c.id AS commit_id, c.subject AS commit_subject "
            "ORDER BY change_id, decision_id, rule_id, commit_id",
            {"path": path, "project": project},
        )]
    finally:
        db.close()


async def _retrieval_command(args):
    from .graph.adapter import RelateGraph

    with RelateGraph(args.store) as db:
        if args.command == "recall":
            from .session.recall import compile_recall
            return await compile_recall(db, args.project, prompt=args.text,
                                        project_root=args.project_root, budget=args.budget,
                                        full=args.full, matched_only=args.matched_only)
        import hashlib
        import os
        from .retrieval.embeddings import OnnxEmbeddingModel
        from .retrieval.pipeline import build_pipeline, RULE_INJECTION_ABSTENTION_THRESHOLD

        # Separate caches by actual artifact bytes: V1's text-only cache key alone
        # cannot distinguish two local exports or an injected test encoder.
        identity = hashlib.sha256()
        for name in ("model.onnx", "tokenizer.json"):
            with (args.model_dir / name).open("rb") as artifact:
                while chunk := artifact.read(1024 * 1024):
                    identity.update(chunk)
        os.environ["WRIT_RETRIEVAL_CACHE"] = str(args.cache / identity.hexdigest())
        model = OnnxEmbeddingModel(args.model_dir)
        pipeline = await build_pipeline(
            db, embedding_model=model,
            abstention_threshold=0.0 if args.ungated else RULE_INJECTION_ABSTENTION_THRESHOLD,
        )
        return pipeline.query(args.text, project=args.project, budget_tokens=args.budget,
                              retrieval_mode=args.mode)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    init = subparsers.add_parser("init-demo", help="Create the persistent synthetic graph")
    init.add_argument("--store", type=Path, default=Path("data/demo"))
    context = subparsers.add_parser("context", help="Retrieve the connected context for a path")
    context.add_argument("path")
    context.add_argument("--store", type=Path, default=Path("data/demo"))
    context.add_argument("--project", default=DEMO_PROJECT)
    corpus = subparsers.add_parser("import-corpus", help="Import the pinned V1 corpus into a new store")
    corpus.add_argument("source", type=Path)
    corpus.add_argument("--store", type=Path, default=Path("data/corpus"))
    query = subparsers.add_parser("query", help="Run the extracted hybrid rule retrieval pipeline")
    query.add_argument("text")
    query.add_argument("--store", type=Path, default=Path("data/corpus"))
    query.add_argument("--model-dir", type=Path, required=True)
    query.add_argument("--cache", type=Path, default=Path("data/indexes"))
    query.add_argument("--project", default=None)
    query.add_argument("--budget", type=int, default=2000)
    query.add_argument("--mode", choices=("semantic", "literal"), default="semantic")
    query.add_argument("--ungated", action="store_true", help="Disable injection abstention for offline diagnostics")
    recall = subparsers.add_parser("recall", help="Recall decisions and memories from one project")
    recall.add_argument("text", nargs="?", default="")
    recall.add_argument("--store", type=Path, default=Path("data/demo"))
    recall.add_argument("--project", required=True)
    recall.add_argument("--project-root", default="")
    recall.add_argument("--budget", type=int, default=500)
    recall.add_argument("--full", action="store_true")
    recall.add_argument("--matched-only", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "init-demo":
            result = seed_demo(args.store)
        elif args.command == "context":
            result = context_for_path(args.store, args.path, args.project)
        elif args.command == "import-corpus":
            from .graph.importer import import_corpus
            result = import_corpus(args.source, args.store)
        else:
            import asyncio
            result = asyncio.run(_retrieval_command(args))
    except (OSError, ValueError, RuntimeError) as exc:
        parser.exit(2, f"{exc}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
