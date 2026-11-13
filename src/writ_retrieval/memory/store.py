"""Transactional Relate capture and durable feedback, adapted from Writ V1 stores.

One local writer at a time. Receipts, counters and lifecycle changes commit or roll
back together. No authentication is provided against a process with store access.
"""
from __future__ import annotations
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import threading

import relate
from writ_retrieval.graph.adapter import RelateGraph
from writ_retrieval.graph.identity import GRAPH_ID_FIELDS, Key
from writ_retrieval.graph.schema import NODE_ID_FIELDS
from writ_retrieval.frequency import evaluate_graduation
from writ_retrieval.retrieval.ranking import compute_confidence_weight
from writ_retrieval.session.recall import invalidate_corpus
from .models import RECORD_MODELS


def canonical(value): return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
def fingerprint(value): return hashlib.sha256(canonical(value).encode()).hexdigest()
def normalized(text): return " ".join((text or "").lower().split())
def claim_hash(rule):
    return fingerprint({k: normalized(rule.get(k)) for k in ("statement", "trigger")})


class LocalStore(RelateGraph):
    def __init__(self, store, *, create=False):
        path = Path(store)
        if create and not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            relate.connect(str(path)).close()
        super().__init__(path)
        self._lock = threading.RLock()
        self._in_transaction = False

    def rows(self, query, **params): return [dict(row) for row in self._db.execute(query, params)]

    @contextmanager
    def transaction(self):
        with self._lock:
            if self._in_transaction:
                raise RuntimeError("nested transaction")
            self._in_transaction = True
            self._db.autocommit = False
            try:
                yield
                self._db.commit()
            except BaseException:
                self._db.rollback()
                raise
            finally:
                self._db.autocommit = True
                self._in_transaction = False
                invalidate_corpus(self)

    def get(self, ref, *, active=False):
        key = ref if isinstance(ref, Key) else Key.parse(ref)
        field = GRAPH_ID_FIELDS[key.label]
        rows = self.rows(f"MATCH (n:{key.label}) WHERE coalesce(n.project, $default) = $project AND n.{field} = $id RETURN properties(n) AS props", project=key.project, id=key.id, default="writ" if key.label in NODE_ID_FIELDS else "")
        if len(rows) > 1: raise ValueError(f"ambiguous physical identity: {key}")
        node = rows[0]["props"] if rows else None
        if node and active and node.get("status", "live") != "live": return None
        return node

    def _set(self, key, props):
        self.rows(f"MERGE (n:{key.label} {{project:$project, {GRAPH_ID_FIELDS[key.label]}:$id}}) SET n += $props", project=key.project, id=key.id, props=props)

    def _edge(self, source, kind, target):
        # Every interpolation comes from a fixed registry or a code constant.
        self.rows(f"MATCH (a:{source.label} {{project:$sp, {GRAPH_ID_FIELDS[source.label]}:$sid}}), (b:{target.label} {{project:$tp, {GRAPH_ID_FIELDS[target.label]}:$tid}}) MERGE (a)-[:{kind}]->(b)", sp=source.project, sid=source.id, tp=target.project, tid=target.id)

    def _archive(self, key, node, action):
        event = fingerprint([key.token, node.get("revision", 1), action, node])
        self._set(Key(key.project, "RecordRevision", event), {"revision_id": event, "project": key.project,
                  "subject": key.token, "action": action, "payload": canonical(node), "provenance": "record"})

    def capture(self, records):
        """Atomic import; immutable facts reject overwrites; Memory needs expected_revision."""
        with self.transaction():
            prepared = []
            for item in records:
                if set(item) - {"label", "data", "expected_revision"}: raise ValueError("unknown import field")
                model = RECORD_MODELS.get(item["label"])
                if not model: raise ValueError("not a supported record label")
                data = model(**item["data"]).model_dump()
                if item["label"] == "Decision" and data["rule_refs"] and not data["governing_rule_ids"]:
                    data["governing_rule_ids"] = [ref["id"] for ref in data["rule_refs"]]
                if item["label"] == "Memory" and not data["updated_at"]:
                    data["updated_at"] = data["ts"]
                key = Key.of(item["label"], data)
                Key.parse(key.as_dict())
                prepared.append((key, data, item.get("expected_revision")))
            if len({key for key, _, _ in prepared}) != len(prepared): raise ValueError("duplicate identity in import")
            # Records are validated first, written second, then wired atomically.
            result = []
            for key, data, expected in prepared:
                previous = self.get(key)
                if previous is None and expected is not None: raise ValueError("update target does not exist")
                content_hash = fingerprint(data)
                if previous:
                    if previous.get("content_hash") == content_hash:
                        result.append({"ref": key.as_dict(), "replayed": True, "revision": previous["revision"]}); continue
                    if key.label != "Memory" or previous.get("status") != "live" or expected != previous.get("revision"):
                        raise ValueError("immutable/stale record: create a new fact and supersede, or update Memory with expected_revision")
                    self._archive(key, previous, "update")
                props = {**data, "revision": previous["revision"] + 1 if previous else 1,
                         "content_hash": content_hash, "status": "live", "provenance": "record", "source_origin": "graph-authored"}
                # Nested maps are explicit JSON, matching upstream record storage.
                for name, value in list(props.items()):
                    if isinstance(value, dict) or (isinstance(value, list) and any(isinstance(v, dict) for v in value)):
                        props[name] = canonical(value)
                self._set(key, props)
                self._archive(key, props, "capture")
                result.append({"ref": key.as_dict(), "replayed": False, "revision": props["revision"]})
            for (key, data, _), item_result in zip(prepared, result):
                if not item_result["replayed"]: self._wire(key, data)
            return result

    def _target(self, source, ref, label=None):
        key = Key.parse(ref)
        if label and key.label not in label: raise ValueError("invalid relationship endpoint type")
        if key.label != "Rule" and key.project not in {source.project, "_shared"}: raise ValueError("foreign-project reference")
        target = self.get(key, active=True)
        if target is None: raise ValueError(f"missing/inactive relationship target: {key}")
        return key, target

    def _wire(self, key, data):
        references = []
        if key.label == "Decision":
            refs = data["rule_refs"] or [Key("writ", "Rule", i).as_dict() for i in data["governing_rule_ids"]]
            if data["rule_refs"] and set(data["governing_rule_ids"]) != {ref["id"] for ref in refs}: raise ValueError("rule IDs and references disagree")
            snapshots = []
            for ref in refs:
                target, rule = self._target(key, ref, {"Rule"})
                snapshots.append({"ref": target.as_dict(), "claim_hash": claim_hash(rule), "statement": rule.get("statement", ""), "trigger": rule.get("trigger", ""), "provenance": rule.get("provenance", "hand-authored")})
                references.append(("GOVERNED_BY", target))
            # Freeze claim identity on first import, never silently update on replay.
            if not self.get(key).get("rule_snapshots"):
                self._set(key, {"rule_snapshots": canonical(snapshots)})
        elif key.label == "FileChange":
            for ref in data["decision_refs"]:
                target, _ = self._target(key, ref, {"Decision"}); references.append(("MOTIVATED_BY", target))
        elif key.label == "Commit":
            for ref in data["change_refs"]:
                target, change = self._target(key, ref, {"FileChange"})
                if change.get("commit_hash") != key.id: raise ValueError("change belongs to a different commit")
                references.append(("INCLUDES", target))
            for ref in data["decision_refs"]:
                target, _ = self._target(key, ref, {"Decision"}); references.append(("REALIZES", target))
        elif key.label == "Memory":
            # An explicit Memory update replaces ABOUT edges; historical payload is archived.
            self.rows("MATCH (m:Memory {project:$project, name:$id})-[r:ABOUT]->() DELETE r", project=key.project, id=key.id)
            for ref in data["about_refs"]:
                target, _ = self._target(key, ref, {"Decision", "Rule"}); references.append(("ABOUT", target))
        elif key.label == "Outcome":
            target, _ = self._target(key, data["decision_ref"], {"Decision"}); references.append(("EVALUATES", target))
        for kind, target in references: self._edge(key, kind, target)

    def lifecycle(self, ref, *, expected_revision, action, replacement=None):
        key = Key.parse(ref)
        if key.label not in RECORD_MODELS: raise ValueError("record lifecycle only")
        if action not in {"delete", "supersede"}: raise ValueError("unknown lifecycle action")
        with self.transaction():
            node = self.get(key)
            if not node or node.get("revision") != expected_revision or node.get("status") != "live": raise ValueError("stale/inactive record")
            if action == "supersede":
                other, _ = self._target(key, replacement, {key.label})
                if other == key or other.project != key.project: raise ValueError("invalid supersession")
                self._edge(other, "SUPERSEDES", key)
            self._archive(key, node, action)
            self._set(key, {"status": "deleted" if action == "delete" else "superseded", "revision": expected_revision + 1,
                            "superseded_by": canonical(replacement) if replacement else ""})
        return self.get(key)

    def propose(self, data):
        allowed = {"rule_id", "project", "statement", "trigger", "domain", "severity", "confidence", "violation", "pass_example", "rationale", "source_refs"}
        if set(data) - allowed: raise ValueError("proposal contains managed fields")
        if any(not isinstance(data.get(k), str) or not data[k].strip() for k in ("rule_id", "project", "statement", "trigger", "domain")): raise ValueError("proposal requires id/project/statement/trigger/domain")
        if not isinstance(data.get("source_refs"), list) or not data["source_refs"] or any(not isinstance(s, str) or not s.strip() for s in data["source_refs"]): raise ValueError("proposal requires source references")
        from writ_retrieval.retrieval.ranking import SEVERITY_WEIGHTS, CONFIDENCE_WEIGHTS
        if data.get("confidence", "speculative") not in CONFIDENCE_WEIGHTS or data.get("severity", "medium") not in SEVERITY_WEIGHTS: raise ValueError("unknown severity/confidence")
        key = Key.of("Rule", data)
        Key.parse(key.as_dict())
        with self.transaction():
            previous = self.get(key)
            if previous:
                if previous.get("proposal_hash") == fingerprint(data): return previous
                raise ValueError("proposal exists; revise explicitly")
            props = {**data, "authority": "ai-provisional", "provenance": "proposed", "source_origin": "graph-authored",
                     "confidence": data.get("confidence", "speculative"), "severity": data.get("severity", "medium"),
                     "mandatory": False, "times_seen_positive": 0, "times_seen_negative": 0,
                     "revision": 1, "status": "live", "proposal_hash": fingerprint(data)}
            props["claim_hash"] = claim_hash(props)
            self._set(key, props)
        return self.get(key)

    def revise_proposal(self, ref, fields, *, expected_claim_hash):
        key = Key.parse(ref)
        if key.label != "Rule" or set(fields) - {"statement", "trigger", "violation", "pass_example", "rationale"}: raise ValueError("invalid proposal edit")
        if any(not isinstance(v, str) or not v.strip() for v in fields.values()): raise ValueError("empty proposal text")
        with self.transaction():
            node = self.get(key, active=True)
            if not node or node.get("authority") != "ai-provisional" or claim_hash(node) != expected_claim_hash: raise ValueError("stale or non-provisional rule")
            edited = {**node, **fields}
            if claim_hash(edited) != claim_hash(node):
                edited.update(times_seen_positive=0, times_seen_negative=0, provenance="proposed", claim_hash=claim_hash(edited))
            edited["revision"] = node.get("revision", 1) + 1
            self._archive(key, node, "revise-proposal")
            self._set(key, edited)
        return self.get(key)

    def feedback(self, *, project, batch_id, signals):
        """Atomic replay-safe observations, one rule/claim/outcome fact across batches.

        Signals are explicitly correlated outcomes, never causal proof. Out-of-date
        claim hashes are rejected; old observations remain inspectable but inactive.
        """
        receipt = Key(project, "FeedbackBatch", batch_id)
        Key.parse(receipt.as_dict())
        request_hash = fingerprint(signals)
        with self.transaction():
            prior = self.get(receipt)
            if prior:
                if prior["request_hash"] != request_hash: raise ValueError("batch ID reused for different feedback")
                return {**json.loads(prior["result"]), "replayed": True, "states": self.feedback_states([Key.parse(s["rule_ref"]) for s in signals])}
            touched = set(); duplicates = 0
            for signal in signals:
                if set(signal) != {"rule_ref", "claim_hash", "outcome_ref", "signal", "source_ref"}: raise ValueError("invalid signal shape")
                rule_key = Key.parse(signal["rule_ref"])
                if rule_key.label != "Rule" or signal["signal"] not in {"positive", "negative"} or not isinstance(signal["source_ref"], str) or not signal["source_ref"].strip(): raise ValueError("invalid feedback")
                rule = self.get(rule_key, active=True)
                if not rule or rule.get("superseded") or claim_hash(rule) != signal["claim_hash"]: raise ValueError("missing/inactive/revised rule")
                outcome_key, outcome = self._target(Key(project, "Outcome", "request"), signal["outcome_ref"], {"Outcome"})
                if outcome_key.project != project: raise ValueError("feedback requires own-project outcome")
                if signal["source_ref"] not in outcome.get("source_refs", []): raise ValueError("signal source is not an outcome source reference")
                if outcome.get("result") == "unknown": raise ValueError("unknown outcome is not feedback evidence")
                if (outcome.get("result"), signal["signal"]) in {("pass", "negative"), ("fail", "positive")}: raise ValueError("signal contradicts recorded outcome")
                decision_key, decision = self._target(outcome_key, json.loads(outcome["decision_ref"]), {"Decision"})
                snapshots = json.loads(decision.get("rule_snapshots") or "[]")
                if not any(s.get("ref") == rule_key.as_dict() and s.get("claim_hash") == signal["claim_hash"] for s in snapshots): raise ValueError("outcome decision did not cite this claim")
                observation = Key(project, "FeedbackObservation", fingerprint([rule_key.token, signal["claim_hash"], outcome_key.token]))
                prior_signal = self.get(observation)
                if prior_signal:
                    if prior_signal["signal"] != signal["signal"]: raise ValueError("contradictory replay for the same rule/outcome")
                    duplicates += 1; touched.add(rule_key); continue
                props = {"project": project, "observation_id": observation.id, "rule_ref": canonical(rule_key.as_dict()),
                         "outcome_ref": canonical(outcome_key.as_dict()), "claim_hash": signal["claim_hash"],
                         "signal": signal["signal"], "source_ref": signal["source_ref"], "kind": "correlated-outcome", "provenance": "record"}
                self._set(observation, props)
                self._edge(observation, "ABOUT", rule_key)
                pos = int(rule.get("times_seen_positive") or 0) + (signal["signal"] == "positive")
                neg = int(rule.get("times_seen_negative") or 0) + (signal["signal"] == "negative")
                provenance = rule.get("provenance", "hand-authored")
                if provenance == "proposed" and evaluate_graduation(pos, neg).graduated: provenance = "graduation_pending"
                self._set(rule_key, {"times_seen_positive": pos, "times_seen_negative": neg, "provenance": provenance})
                touched.add(rule_key)
            states = self.feedback_states(sorted(touched))
            answer = {"batch_id": batch_id, "project": project, "applied": len(signals) - duplicates, "duplicate_observations": duplicates,
                      "states": states, "replayed": False}
            self._set(receipt, {"project": project, "batch_id": batch_id, "request_hash": request_hash, "result": canonical(answer), "provenance": "record"})
        return answer

    def feedback_states(self, keys):
        result = []
        for key in sorted(set(keys)):
            node = self.get(key)
            if not node: continue
            pos, neg = int(node.get("times_seen_positive") or 0), int(node.get("times_seen_negative") or 0)
            result.append({"ref": key.as_dict(), "rule_id": key.id, "project": key.project, "times_seen_positive": pos,
                           "times_seen_negative": neg, "provenance": node.get("provenance", "hand-authored"), "authority": node.get("authority", "human"),
                           "claim_hash": claim_hash(node), "confidence_weight": compute_confidence_weight(node.get("confidence", "production-validated"), pos, neg),
                           "review_candidate": node.get("provenance") == "graduation_pending", "flagged": evaluate_graduation(pos, neg).flagged})
        return result
