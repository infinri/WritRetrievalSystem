"""Informed local-owner promotion, not an agent-unforgeable remote approval service.

The owner must read a stored snapshot and type its digest in an interactive terminal.
There is no --yes flag or HTTP approval endpoint. A process controlling the same OS
account/TTY/database can defeat this boundary; deploy isolation separately if needed.
"""
import getpass
import json
import os
import sys

from writ_retrieval.graph.identity import Key
from writ_retrieval.retrieval.keyword import KeywordIndex
from .store import canonical, fingerprint, claim_hash


def _state(store, key):
    node = store.get(key, active=True)
    if not node: raise ValueError("missing review candidate")
    observations = [r["props"] for r in store.rows("MATCH (o:FeedbackObservation) WHERE o.rule_ref = $ref AND o.claim_hash = $hash RETURN properties(o) AS props ORDER BY o.observation_id", ref=canonical(key.as_dict()), hash=claim_hash(node))]
    for observation in observations:
        observation["source_outcome"] = store.get(Key.parse(json.loads(observation["outcome_ref"])))
    return {"ref": key.as_dict(), "rule": node, "confidence": store.feedback_states([key])[0], "observations": observations}


def prepare_review(store, ref):
    key = Key.parse(ref)
    if key.label != "Rule": raise ValueError("only Rule proposals can be reviewed")
    with store.transaction():
        state = _state(store, key)
        if state["rule"].get("provenance") != "graduation_pending": raise ValueError("not a statistical review candidate")
        rules = [dict(r["props"]) for r in store.rows("MATCH (r:Rule) RETURN properties(r) AS props")]
        keyword = KeywordIndex()
        searchable = [{**r, "rule_id": Key.of("Rule", r).token} for r in rules if Key.of("Rule", r) != key]
        keyword.build(searchable)
        by_token = {Key.of("Rule", r).token: r for r in rules}
        nearest = [{"ref": Key.of("Rule", by_token[h["rule_id"]]).as_dict(), "statement": by_token[h["rule_id"]].get("statement"), "bm25": h["score"]} for h in keyword.search(state["rule"]["statement"], limit=5)]
        conflicts = store.rows("MATCH (a:Rule {project:$project, rule_id:$id})-[r:CONFLICTS_WITH]-(b:Rule) RETURN properties(b) AS rule", project=key.project, id=key.id)
        artifact = {**state, "nearest_lexical": nearest, "explicit_conflicts": [r["rule"] for r in conflicts],
                    "boundary": "Correlation is not proof. Review text, source references, both signal signs, similar rules and explicit conflicts. Local owner assertion; no external identity attestation."}
        review_id = fingerprint(artifact)
        artifact["review_id"] = review_id
        store._set(Key(key.project, "ReviewSnapshot", review_id), {"project": key.project, "review_id": review_id,
                   "state_hash": fingerprint(state), "artifact": canonical(artifact), "provenance": "record"})
    return artifact


def apply_review(store, artifact, *, action):
    """Only interactive local-owner confirmation can change approval state."""
    if action not in {"approve", "reject"}: raise ValueError("invalid review action")
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise PermissionError("review requires an interactive owner terminal; no noninteractive approval")
    ref = Key.parse(artifact["ref"])
    snapshot_key = Key(ref.project, "ReviewSnapshot", artifact["review_id"])
    stored = store.get(snapshot_key)
    if not stored or canonical(artifact) != stored["artifact"]: raise ValueError("unrecognized/edited review artifact")
    # Render the stored artifact, not untrusted text from a supplied path.
    print(json.dumps(json.loads(stored["artifact"]), indent=2), flush=True)
    phrase = f"{action} {artifact['review_id']}"
    if input(f"After reviewing the evidence, type exactly '{phrase}': ") != phrase: raise PermissionError("confirmation did not match")
    with store.transaction():
        current = _state(store, ref)
        if fingerprint(current) != stored["state_hash"] or current["rule"].get("provenance") != "graduation_pending": raise ValueError("review is stale; prepare a new snapshot")
        rule = current["rule"]
        if action == "approve":
            if not rule.get("violation") or not rule.get("pass_example"): raise ValueError("approval requires violation and pass examples")
            others = store.rows("MATCH (r:Rule) RETURN properties(r) AS props")
            from .store import normalized
            if any(Key.of("Rule", r["props"]) != ref and normalized(r["props"].get("statement")) == normalized(rule["statement"]) for r in others):
                raise ValueError("duplicate statement; review and consolidate instead")
            props = {"authority": "ai-promoted", "provenance": "graduated", "graduated_via": "human-approve-asis"}
        else:
            props = {"status": "rejected", "superseded": True}
        store._archive(ref, rule, action)
        store._set(ref, props)
        event = Key(ref.project, "TrustEvent", fingerprint([artifact["review_id"], action]))
        store._set(event, {"project": ref.project, "event_id": event.id, "kind": action, "rule_ref": canonical(ref.as_dict()),
                          "review_id": artifact["review_id"], "os_uid": os.getuid() if hasattr(os, "getuid") else -1,
                          "os_login": getpass.getuser(), "provenance": "record", "claim_hash": claim_hash(rule)})
    return {"action": action, "ref": ref.as_dict(), "trust_event": event.as_dict()}
