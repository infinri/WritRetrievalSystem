"""A minimal, persistent Relate decision-context demonstration.

The synthetic fixture demonstrates Writ's decision-memory relationship model.
This is not the extracted hybrid retrieval pipeline or an authorization system.
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
    ("Rule", {"id": "PARAM-001", "statement": "Use parameterized SQL queries."}),
    ("Decision", {"id": "DEC-001", "rationale": "Parameterize the payment lookup to keep user input out of SQL syntax."}),
    ("FileChange", {"id": "CHANGE-001", "path": DEMO_PATH}),
    ("Commit", {"id": "COMMIT-001", "subject": "Parameterize payment lookup"}),
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    init = subparsers.add_parser("init-demo", help="Create the persistent synthetic graph")
    init.add_argument("--store", type=Path, default=Path("data/demo"))
    context = subparsers.add_parser("context", help="Retrieve the connected context for a path")
    context.add_argument("path")
    context.add_argument("--store", type=Path, default=Path("data/demo"))
    context.add_argument("--project", default=DEMO_PROJECT)
    args = parser.parse_args()
    try:
        result = seed_demo(args.store) if args.command == "init-demo" else context_for_path(args.store, args.path, args.project)
    except FileNotFoundError as exc:
        parser.exit(2, f"{exc}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
