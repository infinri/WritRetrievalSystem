"""Supported-interface end-to-end tests on real Relate, Tantivy and HNSW."""
import asyncio
import json
import os
from pathlib import Path
import pty
import select
import subprocess
import sys
import time

import pytest

from writ_retrieval.graph.identity import Key
from writ_retrieval.graph.snapshot import GraphSnapshot
from writ_retrieval.memory.store import LocalStore, claim_hash
from writ_retrieval.memory.service import ConnectedSession
from writ_retrieval.memory.review import prepare_review, apply_review
from writ_retrieval.retrieval.pipeline import load_pipeline_inputs, assemble_pipeline
from writ_retrieval.session.recall import compile_recall
from tests.fixtures.controlled import ControlledEncoder


def ref(label, ident, project="app"):
    return Key(project, label, ident).as_dict()


def proposal(ident="SQL-001", project="writ", statement="Use parameterized sql"):
    return dict(rule_id=ident, project=project, statement=statement, trigger="sql database", domain="database", confidence="speculative", severity="medium", violation="Interpolate input into SQL", pass_example="execute(sql, parameters)", source_refs=["synthetic:proposal"])


def decision(ident="D", project="app", rules=None, rationale="Use parameterized sql in src/db.py"):
    return dict(label="Decision", data=dict(project=project, ts="2026-01-01", source_refs=["synthetic:plan"], decision_id=ident, title="Parameterize lookup", rationale=rationale, rule_refs=rules if rules is not None else [ref("Rule", "SQL-001", "writ")], planned_files=[{"path": "src/db.py", "reason": "parameterized sql"}]))


def history(ident="D", project="app"):
    return [decision(ident, project),
            dict(label="FileChange", data=dict(project=project, ts="2026-01-02", source_refs=["synthetic:diff"], change_id="F", path="src/db.py", reason="Use SQL parameters", commit_hash="abc", decision_refs=[ref("Decision", ident, project)])),
            dict(label="Commit", data=dict(project=project, ts="2026-01-02", source_refs=["synthetic:commit"], commit_hash="abc", subject="Parameterize query", change_refs=[ref("FileChange", "F", project)], decision_refs=[ref("Decision", ident, project)])),
            dict(label="Memory", data=dict(project=project, ts="2026-01-02", source_refs=["synthetic:memory"], name="db", description="sql database project context", about_refs=[ref("Rule", "SQL-001", "writ")])),
            outcome("O", ident, project)]


def outcome(ident, decision_id="D", project="app", result="pass"):
    return dict(label="Outcome", data=dict(project=project, ts="2026-01-03", source_refs=["synthetic:test/"+ident], outcome_id=ident, decision_ref=ref("Decision", decision_id, project), result=result, summary="Synthetic test " + result))


def signals(rule, outcomes, *, project="app", positive=100):
    return [dict(rule_ref=ref("Rule", rule["rule_id"], rule["project"]), claim_hash=claim_hash(rule), outcome_ref=ref("Outcome", ident, project), signal="positive" if index < positive else "negative", source_ref="synthetic:test/"+ident) for index, ident in enumerate(outcomes)]


@pytest.fixture
def store(tmp_path):
    with LocalStore(tmp_path / "graph", create=True) as store:
        store.propose(proposal())
        yield store


async def test_cli_capture_restart_recall_preserves_provenance_and_is_idempotent(tmp_path):
    path = tmp_path / "graph"
    with LocalStore(path, create=True) as s: s.propose(proposal())
    capture = tmp_path / "records.json"; capture.write_text(json.dumps(history()))
    cmd = [sys.executable, "-m", "writ_retrieval.cli", "capture", str(capture), "--store", str(path)]
    a = json.loads(subprocess.check_output(cmd, text=True)); b = json.loads(subprocess.check_output(cmd, text=True))
    assert not any(r["replayed"] for r in a) and all(r["replayed"] for r in b)
    recall = json.loads(subprocess.check_output([sys.executable, "-m", "writ_retrieval.cli", "recall", "src/db.py", "--store", str(path), "--project", "app", "--project-root", "/repo", "--full"], text=True))
    d = recall["decisions"][0]
    assert (d["decision_id"], d["match"], d["governing_rule_ids"]) == ("D", "path", ["SQL-001"])
    assert d["source_refs"] == ["synthetic:plan"] and d["provenance"] == "record"
    assert d["rule_snapshots"][0]["ref"] == ref("Rule", "SQL-001", "writ")
    with LocalStore(path) as s:
        snapshot = await GraphSnapshot.load(s)
        assert {kind for _, kind, _ in snapshot.edges} >= {"GOVERNED_BY", "MOTIVATED_BY", "INCLUDES", "REALIZES", "ABOUT", "EVALUATES"}
        assert len([k for k in snapshot.nodes if k.label == "Decision"]) == 1


async def test_failed_import_rolls_back_all_records_and_links(store):
    broken = history(); broken[-1]["data"]["decision_ref"] = ref("Decision", "missing")
    with pytest.raises(ValueError): store.capture(broken)
    assert store.get(ref("Decision", "D")) is None
    assert store.rows("MATCH (r:RecordRevision) RETURN count(r) AS n")[0]["n"] == 0
    assert not (await GraphSnapshot.load(store)).edges


async def test_memory_update_tombstone_supersession_and_stale_optimism(store):
    store.capture(history())
    edited = history()[3]; edited["data"]["description"] = "Updated sql history"
    with pytest.raises(ValueError): store.capture([edited])
    edited["expected_revision"] = 1
    store.capture([edited]); assert store.get(ref("Memory", "db"))["revision"] == 2
    with pytest.raises(ValueError): store.capture([{**edited, "data": {**edited["data"], "description": "stale"}}])
    store.capture([decision("D2", rationale="Replacement sql decision")])
    store.lifecycle(ref("Decision", "D"), expected_revision=1, action="supersede", replacement=ref("Decision", "D2"))
    store.lifecycle(ref("Memory", "db"), expected_revision=2, action="delete")
    assert store.capture([history()[0]])[0]["replayed"]  # never resurrect old record
    recall = await compile_recall(store, "app", full=True)
    assert [d["decision_id"] for d in recall["decisions"]] == ["D2"]
    assert recall["memories"] == []
    assert store.rows("MATCH (r:RecordRevision) RETURN count(r) AS n")[0]["n"] >= 8


async def test_project_and_type_collisions_do_not_overwrite_candidates_or_records(store, tmp_path, monkeypatch):
    monkeypatch.setenv("WRIT_RETRIEVAL_CACHE", str(tmp_path / "indexes"))
    store.propose(proposal(project="other", statement="Use async python"))
    store.capture(history())
    store.capture([decision("D", "foreign", rationale="SECRET FOREIGN")])
    store.capture([dict(label="Memory", data=dict(project="app", ts="now", source_refs=["test"], name="D", description="Same local ID different type"))])
    inputs = await load_pipeline_inputs(store)
    assert len(inputs.candidates) == 2 and len(inputs.rule_metadata) == 2
    assert all(n["rule_id"].startswith("@") for n in inputs.candidates)
    p = assemble_pipeline(inputs, embedding_model=ControlledEncoder())
    assert len(p.query("sql async", budget_tokens=10000)["rules"]) == 2
    assert store.get(ref("Decision", "D"))["rationale"] != store.get(ref("Decision", "D", "foreign"))["rationale"]
    assert store.get(ref("Memory", "D"))["description"]
    context = (await GraphSnapshot.load(store)).connected([Key("writ", "Rule", "SQL-001")], "app")
    assert "SECRET" not in json.dumps(context)


async def test_record_bridges_cycles_irrelevant_neighbors_and_budgets(store):
    store.capture(history())
    store.capture([decision("secret", "foreign", rationale="SECRET BRIDGE")])
    # A meaning-valid triangle exercises a genuine cycle.
    store._edge(Key("app", "Memory", "db"), "ABOUT", Key("app", "Decision", "D"))
    # Deliberate hostile/cyclic data bypasses supported capture validation.
    store._edge(Key("foreign", "Decision", "secret"), "GOVERNED_BY", Key("writ", "Rule", "SQL-001"))
    store._edge(Key("app", "Decision", "D"), "MOTIVATED_BY", Key("app", "Decision", "D"))
    store._edge(Key("app", "Memory", "db"), "RELATED_TO", Key("writ", "Rule", "SQL-001"))
    snapshot = await GraphSnapshot.load(store)
    result = snapshot.connected([Key("writ", "Rule", "SQL-001")], "app", max_records=20)
    assert "SECRET" not in json.dumps(result)
    assert {r["ref"]["label"] for r in result["records"]} >= {"Decision", "Outcome", "Commit", "FileChange", "Memory"}
    assert len({json.dumps(r["ref"], sort_keys=True) for r in result["records"]}) == len(result["records"])
    assert snapshot.connected([Key("writ", "Rule", "SQL-001")], None)["records"] == []
    bounded = snapshot.connected([Key("writ", "Rule", "SQL-001")], "app", max_records=1)
    assert len(bounded["records"]) == 1 and bounded["truncated"]
    assert snapshot.audit()["intentionally_unrendered_record_edges"] >= 2


async def test_feedback_atomic_replay_cross_batch_dedup_and_persistence(store, tmp_path, monkeypatch):
    monkeypatch.setenv("WRIT_RETRIEVAL_CACHE", str(tmp_path / "indexes"))
    store.capture(history())
    session = ConnectedSession(store, ControlledEncoder()); await session.refresh()
    rule = store.get(ref("Rule", "SQL-001", "writ"))
    sig = signals(rule, ["O"])
    result = session.apply_feedback(project="app", batch_id="b", signals=sig)
    assert result["states"][0]["times_seen_positive"] == 1
    assert session.pipeline._metadata["SQL-001"]["times_seen_positive"] == 1
    assert session.apply_feedback(project="app", batch_id="b", signals=sig)["replayed"]
    assert session.apply_feedback(project="app", batch_id="b2", signals=sig)["applied"] == 0
    with pytest.raises(ValueError): store.feedback(project="app", batch_id="b", signals=[])
    store.capture([outcome("O2")])
    bad = [*signals(rule, ["O2"]), {**sig[0], "claim_hash": "wrong"}]
    with pytest.raises(ValueError): store.feedback(project="app", batch_id="rollback", signals=bad)
    assert store.get(ref("Rule", "SQL-001", "writ"))["times_seen_positive"] == 1
    assert store.get(ref("FeedbackBatch", "rollback")) is None
    assert (await session.context("sql", project="app"))["refresh"] == "metadata-and-graph"


async def test_experience_threshold_review_candidate_and_wording_invalidation(store, tmp_path, monkeypatch):
    monkeypatch.setenv("WRIT_RETRIEVAL_CACHE", str(tmp_path / "indexes"))
    store.capture([decision()])
    ids = [str(i) for i in range(50)]
    store.capture([outcome(i, result="pass" if int(i) < 40 else "fail") for i in ids])
    rule = store.get(ref("Rule", "SQL-001", "writ"))
    sig = signals(rule, ids, positive=40)
    store.feedback(project="app", batch_id="first49", signals=sig[:49])
    state = store.feedback_states([Key("writ", "Rule", "SQL-001")])[0]
    assert state["confidence_weight"] == .3 and not state["review_candidate"]
    result = store.feedback(project="app", batch_id="last", signals=sig[49:])
    state = result["states"][0]
    assert state["times_seen_positive"] == 40 and state["times_seen_negative"] == 10
    assert state["confidence_weight"] == .8 and state["review_candidate"] and state["authority"] == "ai-provisional"
    artifact = prepare_review(store, ref("Rule", "SQL-001", "writ"))
    assert len(artifact["observations"]) == 50
    with pytest.raises(PermissionError): apply_review(store, artifact, action="approve")
    revised = store.revise_proposal(ref("Rule", "SQL-001", "writ"), {"statement": "Use async database transactions"}, expected_claim_hash=claim_hash(rule))
    assert revised["times_seen_positive"] == 0 and revised["times_seen_negative"] == 0 and revised["provenance"] == "proposed"
    assert store.feedback(project="app", batch_id="last", signals=sig[49:])["states"][0]["times_seen_positive"] == 0
    with pytest.raises(ValueError): store.feedback(project="app", batch_id="old-claim", signals=sig[:1])


@pytest.mark.parametrize("positives,expected,flagged", [(50,1.0,False),(38,.76,False),(37,.3,True),(0,.3,True)])
def test_exact_upstream_confidence_boundaries(store, positives, expected, flagged):
    store.capture([decision()])
    ids = [str(i) for i in range(50)]
    store.capture([outcome(i, result="pass" if int(i) < positives else "fail") for i in ids])
    sig = signals(store.get(ref("Rule", "SQL-001", "writ")), ids, positive=positives)
    result = store.feedback(project="app", batch_id="boundary", signals=sig)["states"][0]
    assert result["confidence_weight"] == expected and result["flagged"] == flagged


def terminal_review(path, artifact_path, artifact, action="approve"):
    master, slave = pty.openpty()
    process = subprocess.Popen([sys.executable, "-m", "writ_retrieval.cli", "review-apply", str(artifact_path), "--store", str(path), "--action", action], stdin=slave, stdout=slave, stderr=slave, close_fds=True)
    os.close(slave); output = b""; sent = False
    try:
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            ready, _, _ = select.select([master], [], [], .1)
            if ready:
                try: output += os.read(master, 65536)
                except OSError: break
            if not sent and b"type exactly" in output:
                os.write(master, f"{action} {artifact['review_id']}\n".encode()); sent = True
            if process.poll() is not None: break
        process.wait(timeout=2)
    finally:
        if process.poll() is None: process.kill(); process.wait()
        os.close(master)
    return process.returncode, output.decode(errors="replace")


def test_local_interactive_review_cannot_be_replaced_by_feedback_and_rejects_stale_snapshot(tmp_path):
    path = tmp_path / "graph"; artifact_path = tmp_path / "review.json"
    with LocalStore(path, create=True) as s:
        s.propose(proposal()); s.capture([decision()])
        ids = [str(i) for i in range(50)]; s.capture([outcome(i) for i in ids])
        s.feedback(project="app", batch_id="threshold", signals=signals(s.get(ref("Rule", "SQL-001", "writ")), ids))
        artifact = prepare_review(s, ref("Rule", "SQL-001", "writ")); artifact_path.write_text(json.dumps(artifact))
    code, output = terminal_review(path, artifact_path, artifact)
    assert code == 0, output
    with LocalStore(path) as s:
        assert s.get(ref("Rule", "SQL-001", "writ"))["authority"] == "ai-promoted"
        assert s.rows("MATCH (e:TrustEvent) RETURN count(e) AS n")[0]["n"] == 1
    code, _ = terminal_review(path, artifact_path, artifact)
    assert code != 0  # same snapshot no longer authorizes a new promotion


async def test_duplicate_chunk_ids_are_scoped_and_foreign_precedes_cannot_alias(store, tmp_path, monkeypatch):
    from writ_retrieval.retrieval.documents import assemble_document_pipeline
    monkeypatch.setenv("WRIT_RETRIEVAL_CACHE", str(tmp_path/"docs-index"))
    for project, text in [("app", "sql database"), ("foreign", "SECRET sql database")]:
        store.rows("CREATE (d:Document {project:$project, doc_id:'d', path:'doc.md'})-[:CONTAINS]->(c:Chunk {project:$project, doc_id:'d', chunk_id:'same', text:$text, ordinal:0})", project=project, text=text)
    store.rows("MATCH (a:Chunk {project:'app'}), (b:Chunk {project:'foreign'}) CREATE (a)-[:PRECEDES]->(b)")
    inputs = await load_pipeline_inputs(store, with_documents=True)
    assert len({c["rule_id"] for c in inputs.chunks}) == 2
    assert all(c["next_id"] is None and c["prev_id"] is None for c in inputs.chunks)
    p = assemble_document_pipeline(inputs.chunks, embedding_model=ControlledEncoder())
    result = p.query("sql database", project="app", exclude_ids=[])
    assert len(result["chunks"]) == 1 and "SECRET" not in json.dumps(result)
    assert result["chunks"][0]["source_chunk_id"] == "same"


async def test_captured_claim_survives_wording_revision_and_typed_full_recall(store):
    store.capture([decision()])
    before = store.get(ref("Rule", "SQL-001", "writ"))
    store.propose(proposal(project="other", statement="Use async python"))
    store.revise_proposal(ref("Rule", "SQL-001", "writ"), {"statement": "Use async database transactions"}, expected_claim_hash=claim_hash(before))
    full = await compile_recall(store, "app", full=True)
    d = full["decisions"][0]; key = Key("writ", "Rule", "SQL-001").token
    assert d["captured_rule_statements_by_ref"][key] == "Use parameterized sql"
    assert d["current_rule_statements_by_ref"][key] == "Use async database transactions"
    assert d["rule_statements"]["SQL-001"] == "Use parameterized sql"


def test_review_snapshot_expires_when_new_observation_arrives(tmp_path):
    path = tmp_path / "graph"; artifact_path = tmp_path / "stale.json"
    with LocalStore(path, create=True) as s:
        s.propose(proposal()); s.capture([decision()])
        ids = [str(i) for i in range(50)]; s.capture([outcome(i) for i in ids])
        rule = s.get(ref("Rule", "SQL-001", "writ"))
        s.feedback(project="app", batch_id="threshold", signals=signals(rule, ids))
        artifact = prepare_review(s, ref("Rule", "SQL-001", "writ")); artifact_path.write_text(json.dumps(artifact))
        s.capture([outcome("contradiction", result="fail")])
        s.feedback(project="app", batch_id="new-evidence", signals=signals(rule, ["contradiction"], positive=0))
    code, output = terminal_review(path, artifact_path, artifact)
    assert code != 0 and "stale" in output
    with LocalStore(path) as s:
        assert s.get(ref("Rule", "SQL-001", "writ"))["authority"] == "ai-provisional"
