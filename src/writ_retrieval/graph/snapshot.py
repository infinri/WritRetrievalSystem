"""Qualified identities and meaning-checked bounded record enrichment.

Record edges enrich context separately; they never become proximity bridges in
ranked retrieval. Doctrine adjacency keeps V1's eligible labels and exclusions.
"""
from collections import Counter, deque
from dataclasses import dataclass, field
import json

from .identity import Key
from .schema import NODE_ID_FIELDS
from writ_retrieval.retrieval.node_scope import is_visible

# Directed edge contracts; traversal may follow either direction for context.
RECORD_EDGES = {
    ("Decision", "GOVERNED_BY", "Rule"), ("FileChange", "MOTIVATED_BY", "Decision"),
    ("Commit", "INCLUDES", "FileChange"), ("Commit", "REALIZES", "Decision"),
    ("Memory", "ABOUT", "Rule"), ("Memory", "ABOUT", "Decision"),
    ("Outcome", "EVALUATES", "Decision"),
}


@dataclass
class GraphSnapshot:
    nodes: dict = field(default_factory=dict)
    edges: list = field(default_factory=list)
    omitted_nodes: list = field(default_factory=list)
    unresolved_edges: int = 0

    @classmethod
    async def load(cls, db):
        result = cls(); physical = {}
        for row in await db.read("MATCH (n) RETURN elementId(n) AS physical, labels(n) AS labels, properties(n) AS props"):
            try:
                if len(row["labels"]) != 1: raise ValueError("multi-label node")
                key = Key.of(row["labels"][0], row["props"])
            except ValueError:
                result.omitted_nodes.append(row["physical"]); continue
            if key in result.nodes: raise ValueError(f"duplicate physical graph identity: {key}")
            result.nodes[key] = row["props"]; physical[row["physical"]] = key
        for row in await db.read("MATCH (a)-[r]->(b) RETURN elementId(a) AS a, type(r) AS kind, elementId(b) AS b"):
            if row["a"] in physical and row["b"] in physical:
                result.edges.append((physical[row["a"]], row["kind"], physical[row["b"]]))
            else:
                result.unresolved_edges += 1
        result.edges.sort()
        return result

    def index_keys(self):
        counts = Counter(k.id for k in self.nodes if k.label in NODE_ID_FIELDS)
        return {k: k.id if counts[k.id] == 1 else k.token for k in self.nodes if k.label in NODE_ID_FIELDS}

    def doctrine_rows(self):
        aliases = self.index_keys(); rows = []
        for a, kind, b in self.edges:
            if a not in aliases or b not in aliases or kind == "BELONGS_TO": continue
            if self.nodes[a].get("status", "live") != "live" or self.nodes[b].get("status", "live") != "live": continue
            rows.append(dict(source=aliases[a], target=aliases[b], edge_type=kind,
                             source_type=a.label, source_project=self.nodes[a].get("project"),
                             target_type=b.label, target_project=self.nodes[b].get("project")))
        return sorted(rows, key=lambda r: (r["source"], r["target"], r["edge_type"]))

    def routes(self):
        aliases = self.index_keys(); result = {}
        for a, kind, b in self.edges:
            if kind == "BELONGS_TO" and a in aliases and b.label == "Category" and self.nodes[b].get("routes"):
                result[aliases[a]] = self.nodes[b]["routes"]
        return result

    def connected(self, seeds, project, *, max_hops=2, max_records=6, max_visited=64):
        if not 0 <= max_hops <= 2 or not 0 <= max_records <= 20 or not 1 <= max_visited <= 128:
            raise ValueError("invalid traversal budget")
        adjacency = {}
        for a, kind, b in self.edges:
            if (a.label, kind, b.label) not in RECORD_EDGES: continue
            adjacency.setdefault(a, []).append((b, kind, "outgoing"))
            adjacency.setdefault(b, []).append((a, kind, "incoming"))
        seen = set(); queue = deque((seed, 0, []) for seed in seeds); found = []
        while queue and len(seen) < max_visited and len(found) < max_records:
            key, depth, path = queue.popleft()
            if key in seen: continue
            seen.add(key)
            node = self.nodes.get(key)
            if node is None or node.get("status", "live") != "live": continue
            if not is_visible(key.label, key.project, project): continue
            if depth and key.label not in NODE_ID_FIELDS:
                found.append({"ref": key.as_dict(), "path": path,
                              "provenance": node.get("provenance", "record"), "source_origin": node.get("source_origin", "unknown"),
                              "source_refs": node.get("source_refs") or [], "revision": node.get("revision"),
                              "title": node.get("title") or node.get("name") or node.get("subject") or node.get("path") or key.id,
                              "text": node.get("rationale") or node.get("description") or node.get("summary") or node.get("reason") or "",
                              "result": node.get("result"), "governing_rule_ids": node.get("governing_rule_ids") or [],
                              "rule_snapshots": json.loads(node.get("rule_snapshots") or "[]")})
            if depth >= max_hops: continue
            # Only traverse a visible node. A private bridge cannot carry traversal.
            for target, kind, direction in sorted(adjacency.get(key, [])):
                if target.label == "Rule" and target not in seeds: continue
                queue.append((target, depth + 1, [*path, {"ref": target.as_dict(), "edge": kind, "direction": direction}]))
        return {"records": found, "visited": len(seen), "remaining_frontier": len(queue), "max_hops": max_hops,
                "max_records": max_records, "max_visited": max_visited, "truncated": bool(queue)}

    def audit(self):
        adjacency = self.doctrine_rows()
        attached = {k for a, _, b in self.edges for k in (a, b)}
        record_edges = [(a, kind, b) for a, kind, b in self.edges if a.label not in NODE_ID_FIELDS or b.label not in NODE_ID_FIELDS]
        invalid = [(a, kind, b) for a, kind, b in record_edges if (a.label, kind, b.label) not in RECORD_EDGES]
        return {"nodes": len(self.nodes), "edges": len(self.edges), "omitted_nodes": len(self.omitted_nodes), "unresolved_edges": self.unresolved_edges,
                "colliding_bare_ids": {ident: [k.as_dict() for k in sorted(self.nodes) if k.id == ident] for ident, n in Counter(k.id for k in self.nodes).items() if n > 1},
                "edge_types": dict(Counter(kind for _, kind, _ in self.edges)),
                "doctrine_adjacency_edges": len(adjacency), "record_edges": len(record_edges),
                "context_eligible_record_edges": len(record_edges)-len(invalid),
                "intentionally_unrendered_record_edges": len(invalid),
                "isolated": [k.as_dict() for k in sorted(set(self.nodes)-attached)],
                "note": "Isolated or unrendered does not imply defective; revisions, receipts and supersession edges are audit-only."}
