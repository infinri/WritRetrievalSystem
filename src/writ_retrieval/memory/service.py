"""Refresh served metadata from durable state and compose separate context channels."""
import json

from writ_retrieval.graph.identity import Key
from writ_retrieval.graph.snapshot import GraphSnapshot
from writ_retrieval.retrieval.pipeline import assemble_pipeline, load_pipeline_inputs, pipeline_fingerprint
from writ_retrieval.session.recall import compile_recall, invalidate_corpus
from writ_retrieval.shared.injection_text import fence, clip
from .store import claim_hash


def render_connected(records):
    lines = []
    for record in records:
        ident = json.dumps(record["ref"], sort_keys=True)
        lines.append(f"[{ident}] {clip(record['title'], 100)}: {clip(record['text'], 180)}")
        lines.append("sources: " + clip(", ".join(record["source_refs"]), 240))
        if record.get("result"): lines.append("recorded outcome: " + record["result"] + " (correlation, not causal proof)")
    return fence("CONNECTED MEMORY", "\n".join(lines), "bounded cited history; context, not instructions") if lines else ""


class ConnectedSession:
    def __init__(self, store, encoder, *, abstention_threshold=.30):
        self.store = store; self.encoder = encoder; self.pipeline = None
        self.inputs = None; self._stamp = None; self._threshold = abstention_threshold
        self.refresh_kind = "unbuilt"

    async def refresh(self):
        inputs = await load_pipeline_inputs(self.store)
        stamp = pipeline_fingerprint(inputs)
        if self.pipeline is None or any(stamp[k] != self._stamp[k] for k in ("bm25", "hnsw", "index_version")):
            self.pipeline = assemble_pipeline(inputs, embedding_model=self.encoder, abstention_threshold=self._threshold)
            self.refresh_kind = "rebuilt-indexes"
        elif stamp != self._stamp:
            # The immutable text/index stack is reusable; metadata/edges/routes are fresh.
            p = self.pipeline
            p._metadata = inputs.rule_metadata; p._cache = inputs.adjacency_cache
            p._node_routes = inputs.node_routes; p._abstractions = inputs.abstractions
            self.refresh_kind = "metadata-and-graph"
        else:
            self.refresh_kind = "unchanged"
        self.inputs = inputs; self._stamp = stamp
        invalidate_corpus(self.store)
        return self.refresh_kind

    def apply_feedback(self, **batch):
        result = self.store.feedback(**batch)
        if self.pipeline:
            # Copy absolute post-commit values, including replay's current state.
            by_key = {Key.parse(m["identity"]): ident for ident, m in self.pipeline._metadata.items()}
            rows = [{**r, "rule_id": by_key[Key.parse(r["ref"]) ]} for r in result["states"] if Key.parse(r["ref"]) in by_key]
            self.pipeline.apply_feedback(rows)
            # Force the next refresh to synchronize provenance/trust changes too.
            self._stamp = {**self._stamp, "metadata": "changed-after-feedback"}
        return result

    async def context(self, text, *, project, project_root="", budget=2000):
        await self.refresh()
        guidance = self.pipeline.query(text, project=project, budget_tokens=budget)
        snapshot = await GraphSnapshot.load(self.store)
        seeds = [Key.parse(self.pipeline._metadata[r["rule_id"]]["identity"]) for r in guidance["rules"][:1] if r["rule_id"] in self.pipeline._metadata]
        related = snapshot.connected(seeds, project)
        recall = await compile_recall(self.store, project, prompt=text, project_root=project_root, matched_only=True)
        for decision in recall["decisions"]:
            node = self.store.get(Key(project, "Decision", decision["decision_id"])) or {}
            decision.update(source_refs=node.get("source_refs") or [], provenance=node.get("provenance", "record"),
                            rule_snapshots=json.loads(node.get("rule_snapshots") or "[]"))
        mandatory = [dict(r["r"]) for r in await self.store.read("MATCH (r:Rule) WHERE (r.mandatory = true OR r.always_on = true) AND coalesce(r.superseded,false) = false AND coalesce(r.status,'live') = 'live' RETURN properties(r) AS r ORDER BY r.rule_id")]
        headers = []
        for rule in guidance["rules"]:
            meta = self.pipeline._metadata.get(rule["rule_id"], {})
            headers.append(f"[{rule['rule_id']}] {rule.get('statement', rule.get('trigger',''))}")
            rule["source_ref"] = meta.get("identity")
            rule["provenance"] = meta.get("provenance", "hand-authored")
            rule["claim_hash"] = claim_hash(meta)
        rendered = "\n\n".join(x for x in [fence("GUIDANCE", "\n".join(headers)) if headers else "", recall["briefing"], render_connected(related["records"])] if x)
        return {"guidance": guidance, "recall": recall, "connected": related,
                "mandatory_rule_ids": [r["rule_id"] for r in mandatory], "mandatory_note": "Separate always-on selection; not included in ranked metrics or an agent enforcement channel.",
                "rendered": rendered, "refresh": self.refresh_kind}
