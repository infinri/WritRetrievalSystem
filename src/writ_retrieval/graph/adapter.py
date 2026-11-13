"""Relate reads for the extracted V1 pipeline and project-scoped decision recall.

No Bolt driver, session emulation, APOC, or Neo4j server is required. Async methods
match the extracted startup API; embedded reads are synchronous and belong at
startup/CLI boundaries, not on an async web server's request loop.
"""
from __future__ import annotations

from pathlib import Path

import relate

from .schema import NODE_ID_FIELDS

# Preserve V1's projection, including its omission of record-only ID fields.
# Record recall uses explicit Decision/FileChange/Commit fields separately.
GRAPH_ID_COALESCE = "coalesce(" + ", ".join(f"{{v}}.{f}" for f in sorted(set(NODE_ID_FIELDS.values()))) + ")"


class RelateGraph:
    def __init__(self, store: str | Path):
        store = Path(store)
        if not store.exists():
            raise FileNotFoundError(f"Store does not exist: {store}")
        self._db = relate.connect(str(store))

    def close(self):
        self._db.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    async def read(self, query: str, **parameters) -> list[dict]:
        return [dict(row) for row in self._db.execute(query, parameters)]

    async def get_all_abstractions(self) -> list[dict]:
        from .snapshot import GraphSnapshot
        snapshot = await GraphSnapshot.load(self)
        aliases = snapshot.index_keys()
        result = []
        for key in sorted(snapshot.nodes):
            if key.label != "Abstraction": continue
            data = dict(snapshot.nodes[key])
            data["abstraction_id"] = aliases[key]
            data["member_ids"] = [aliases[b] for a, kind, b in snapshot.edges if a == key and kind == "ABSTRACTS" and b.label == "Rule"]
            result.append(data)
        return result

    async def get_category_routes_by_node(self) -> dict[str, list[str]]:
        from .snapshot import GraphSnapshot
        return (await GraphSnapshot.load(self)).routes()

    async def adjacency_rows(self):
        from .snapshot import GraphSnapshot
        return (await GraphSnapshot.load(self)).doctrine_rows()

    async def get_recent_decisions(self, project: str, limit: int = 20) -> list[dict]:
        rows = await self.read(
            "MATCH (d:Decision {project: $project}) WHERE coalesce(d.status, 'live') = 'live' RETURN d ORDER BY d.ts DESC LIMIT $limit",
            project=project, limit=limit,
        )
        return [self._decision(dict(row["d"])) for row in rows]

    async def list_memories(self, project: str, include_deleted: bool = False) -> list[dict]:
        rows = await self.read("""
            MATCH (m:Memory {project: $project})
            WHERE $include_deleted OR coalesce(m.status, 'live') = 'live'
            RETURN m ORDER BY m.updated_at DESC
        """, project=project, include_deleted=include_deleted)
        memories = [dict(row["m"]) for row in rows]
        for memory in memories:
            memory["links"] = memory.get("links") or []
        return memories

    @staticmethod
    def _parse_planned_files(raw) -> list[dict]:
        """Parse the planned_files property into a list[dict].

        An empty list is stored natively (the _coerce_neo4j_value `and v` guard
        means [] never becomes the string '[]'), so handle both the JSON-string
        and the native-list forms.
        """
        import json
        if isinstance(raw, str):
            try:
                parsed = json.loads(raw)
            except (ValueError, TypeError):
                return []
        elif isinstance(raw, list):
            parsed = raw
        else:
            return []
        return [c for c in parsed if isinstance(c, dict)]

    @staticmethod
    def _decision(row: dict) -> dict:
        row["planned_files"] = RelateGraph._parse_planned_files(row.get("planned_files"))
        row["governing_rule_ids"] = row.get("governing_rule_ids") or []
        return row

    async def get_decisions_for_paths(self, project: str, paths: list[str], per_path: int = 1) -> dict[str, list[dict]]:
        if not paths or per_path <= 0:
            return {}
        # V1's USING INDEX hint and collect/slice/UNWIND are replaced with an
        # ordered embedded read and Python grouping. Slice CHANGES before decision
        # deduplication, matching V1 even when two changes cite the same decision.
        rows = await self.read("""
            MATCH (n:FileChange)-[:MOTIVATED_BY]->(d:Decision)
            WHERE n.project = $project AND n.path IN $paths AND d.project = $project
              AND coalesce(n.status, 'live') = 'live' AND coalesce(d.status, 'live') = 'live'
            OPTIONAL MATCH (c:Commit {project: $project, commit_hash: n.commit_hash})
            RETURN n, d, c.subject AS commit_subject
            ORDER BY n.ts DESC, n.change_id DESC
        """, project=project, paths=paths)
        counts: dict[str, int] = {}
        out: dict[str, list[dict]] = {}
        for row in rows:
            change = dict(row["n"])
            path = change["path"]
            counts[path] = counts.get(path, 0) + 1
            if counts[path] > per_path:
                continue
            decision = self._decision(dict(row["d"]))
            hits = out.setdefault(path, [])
            if any(h["decision_id"] == decision["decision_id"] for h in hits):
                continue
            hits.append({**decision, "decision_ts": decision.get("ts"),
                         "reason": change.get("reason"), "change_ts": change.get("ts"),
                         "commit_hash": change.get("commit_hash"), "commit_subject": row["commit_subject"]})
        return out

    async def get_rule_statements(self, rule_ids: list[str]) -> dict[str, str]:
        if not rule_ids:
            return {}
        rows = await self.read("MATCH (r:Rule) WHERE r.rule_id IN $ids RETURN r.rule_id AS id, r.statement AS statement", ids=rule_ids)
        from collections import Counter
        counts = Counter(r["id"] for r in rows)
        return {r["id"]: r["statement"] or "" for r in rows if counts[r["id"]] == 1}

    async def get_rule_statements_by_ref(self, refs):
        from .identity import Key
        result = {}
        for ref in refs:
            key = Key.parse(ref)
            if key.label != "Rule": raise ValueError("not a rule reference")
            rows = await self.read("MATCH (r:Rule) WHERE coalesce(r.project,'writ')=$project AND r.rule_id=$id RETURN r.statement AS statement", project=key.project, id=key.id)
            if len(rows) == 1: result[key.token] = rows[0]["statement"] or ""
        return result
