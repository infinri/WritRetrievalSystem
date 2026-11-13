"""Doctrine 1-2 hop traversal from candidate rule_ids.

Two backends:
1. Live Neo4j queries (used during ingest/validate, offline operations)
2. Pre-computed adjacency cache (used in hot path, built at startup)

Latency budget: < 3ms. Neo4j live queries exceed this (Phase 2 benchmarks).
The adjacency cache is the mitigation: traversal becomes a dict lookup (< 0.1ms).

Per ARCH-DI-001: receives db connection via constructor injection.
Per PERF-IO-001: hot-path traversal uses in-memory cache, no I/O.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from writ_retrieval.graph.adapter import RelateGraph


class AdjacencyCache:
    """In-memory adjacency list for hot-path traversal.

    Built from Relate at startup. Lookup is O(1) per rule_id.
    """

    def __init__(self) -> None:
        self._neighbors: dict[str, list[dict]] = {}
        self._build_time_ms: float = 0.0

    async def build_from_db(self, db: RelateGraph) -> int:
        """Load doctrine edges from Relate into memory.

        Phase 1 expansion: matches any labeled node (Rule, Skill, Playbook,
        AntiPattern, etc.) so methodology edges surface during Stage 4
        enrichment. Cache key is the node's primary id field value.

        DELIBERATELY UNFILTERED, AND EACH ENTRY CARRIES ITS NEIGHBOR'S LABEL AND
        PROJECT TAG. One cache is shared by every caller in the daemon, so adding a
        project filter here would either make the cache caller-specific (wrong: it is
        built once at startup) or drop record adjacency outright (which loses future
        record edges instead of scoping them). The scope decision therefore belongs to
        the ATTACH site, RetrievalPipeline._scope_enrichment, and that site cannot make
        it from the pipeline's metadata dict: `_load_candidates` loads only Rule plus
        the five retrievable methodology labels, so a record-typed neighbor is absent
        from it, its node_type would default to "Rule", and every foreign record would
        be admitted. Carrying node_type + project on the entry is what makes the filter
        decidable at all.

        Returns the number of nodes with at least one neighbor.
        """
        start = time.perf_counter()
        # Qualified doctrine adjacency preserves V1 ranking semantics. Record-aware
        # enrichment is handled separately by GraphSnapshot.connected.
        records = await db.adjacency_rows()

        self._neighbors.clear()
        for rec in records:
            src = rec["source"]
            tgt = rec["target"]
            edge_type = rec["edge_type"]
            # Store both directions for undirected lookup. node_type/project always
            # describe the NEIGHBOR named by rule_id, never the node the entry is filed
            # under, so the attach-time filter can ask about the node it is about to
            # hand out without a second lookup.
            self._neighbors.setdefault(src, []).append({
                "rule_id": tgt,
                "edge_type": edge_type,
                "direction": "outgoing",
                "node_type": rec.get("target_type"),
                "project": rec.get("target_project"),
            })
            self._neighbors.setdefault(tgt, []).append({
                "rule_id": src,
                "edge_type": edge_type,
                "direction": "incoming",
                "node_type": rec.get("source_type"),
                "project": rec.get("source_project"),
            })

        self._build_time_ms = (time.perf_counter() - start) * 1000
        return len(self._neighbors)

    def get_neighbors(self, rule_id: str) -> list[dict]:
        """Return cached neighbors for a rule_id. O(1) lookup."""
        return self._neighbors.get(rule_id, [])

    def get_enrichment(self, rule_ids: list[str]) -> dict[str, list[dict]]:
        """For each candidate rule_id, return its neighbors from cache."""
        return {rid: self.get_neighbors(rid) for rid in rule_ids}

    def snapshot(self) -> dict[str, list[dict]]:
        """The canonical edge map, for hashing (program item 2, C1). Read-only: callers
        must not mutate it. Deterministic, because the build query is ORDER BY
        source, target, edge_type."""
        return self._neighbors

    @property
    def build_time_ms(self) -> float:
        return self._build_time_ms

    @property
    def size(self) -> int:
        return len(self._neighbors)
