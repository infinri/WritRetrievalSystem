"""Real Relate + Tantivy + HNSW checks, with controlled vectors for mechanics."""
import asyncio
import json
from pathlib import Path

import pytest
import relate

from writ_retrieval.graph.adapter import RelateGraph
from writ_retrieval.graph.importer import import_corpus
from writ_retrieval.retrieval.pipeline import assemble_pipeline, load_pipeline_inputs, pipeline_fingerprint
from writ_retrieval.session.recall import compile_recall, write_decision_context
from tests.fixtures.controlled import ControlledEncoder, EDGES, NODES, QUERIES

FIXTURES = Path(__file__).parent / "fixtures"


def seed_nodes(store, nodes=NODES, edges=EDGES):
    db = relate.connect(str(store))
    try:
        for label, props in nodes:
            db.execute(f"CREATE (n:{label}) SET n += $props", {"props": props})
        for source, kind, target in edges:
            db.execute(f"MATCH (a), (b) WHERE coalesce(a.rule_id, a.skill_id, a.forbidden_id, a.category_id, a.abstraction_id) = $source AND coalesce(b.rule_id, b.skill_id, b.forbidden_id, b.category_id, b.abstraction_id) = $target CREATE (a)-[:{kind}]->(b)", {"source": source, "target": target})
    finally:
        db.close()


@pytest.fixture
async def controlled(tmp_path, monkeypatch):
    monkeypatch.setenv("WRIT_RETRIEVAL_CACHE", str(tmp_path / "indexes"))
    store = tmp_path / "graph"
    seed_nodes(store)
    with RelateGraph(store) as db:
        inputs = await load_pipeline_inputs(db)
    return inputs


async def test_real_index_pipeline_matches_pinned_upstream_controlled_results(controlled):
    p = assemble_pipeline(controlled, embedding_model=ControlledEncoder(), abstention_threshold=0.3)
    actual = [{k: v for k, v in p.query(**q).items() if k != "latency_ms"} for q in QUERIES]
    expected = json.loads((FIXTURES / "v1-controlled-results.json").read_text())
    assert actual == expected["results"]


async def test_collectors_filter_ranked_pool_and_keep_provenance(controlled):
    ids = [n["rule_id"] for n in controlled.candidates]
    assert ids == ["ASYNC-001", "PLAN-001", "SQL-001", "SKL-001", "FRB-001"]
    assert controlled.rule_metadata["SQL-001"]["provenance"] == "hand-authored"
    assert controlled.rule_metadata["SQL-001"]["source_origin"] == "ingest"
    assert controlled.rule_metadata["FRB-001"]["body"] == "cat unrelated plan"
    assert controlled.node_routes is None  # incomplete routing retains V1 fallback
    sql = controlled.adjacency_cache.get_neighbors("SQL-001")
    assert any(n["rule_id"] == "ASYNC-001" and n["direction"] == "outgoing" for n in sql)
    assert not any(n["edge_type"] == "BELONGS_TO" for n in sql)
    assert controlled.abstractions[0]["member_ids"] == ["SQL-001"]


async def test_warm_indexes_reload_without_reencoding_and_fingerprint_is_stable(controlled):
    first = ControlledEncoder()
    p = assemble_pipeline(controlled, embedding_model=first)
    assert first.batches == 1
    second = ControlledEncoder()
    warm = assemble_pipeline(controlled, embedding_model=second)
    assert second.batches == 0
    a, b = p.query("sql"), warm.query("sql")
    a.pop("latency_ms"); b.pop("latency_ms")
    assert a == b
    assert pipeline_fingerprint(controlled) == pipeline_fingerprint(controlled)


async def test_full_pinned_corpus_loads_from_reopened_store(tmp_path):
    store = tmp_path / "corpus"
    result = import_corpus(FIXTURES / "writ-corpus.cypher", store)
    assert (result["nodes"], result["edges"]) == (468, 1268)
    with RelateGraph(store) as db:
        inputs = await load_pipeline_inputs(db)
        counts = await db.read("MATCH (r:Rule) RETURN count(r) AS count")
    assert counts[0]["count"] == 288
    ids = {n["rule_id"] for n in inputs.candidates}
    assert "DB-SQL-002" in ids
    assert "SEC-INJ-SQL-001" not in ids  # gold target is mandatory at this baseline
    assert not any(n.get("mandatory") or n.get("superseded") for n in inputs.candidates if n["node_type"] == "Rule")
    # Gold data retains IDs, including intentional non-ranked/mandatory targets.
    gold = json.loads((FIXTURES / "ground_truth_queries.json").read_text())["queries"]
    assert len(gold) == 193
    with pytest.raises(FileExistsError):
        import_corpus(FIXTURES / "writ-corpus.cypher", store)


async def test_recall_project_scope_provenance_and_commit_join(tmp_path):
    store = tmp_path / "records"
    db = relate.connect(str(store))
    try:
        for project, text in [("app", "Use parameterized sql."), ("foreign", "SECRET FOREIGN")]:
            db.execute("CREATE (:Decision {project: $project, decision_id: 'DEC-001', rationale: $text, title: 'stored', ts: '2026-01-01', governing_rule_ids: ['SQL-001'], planned_files: $planned})", {"project": project, "text": text, "planned": json.dumps([{"path": "src/db.py", "reason": "sql parameters"}])})
            db.execute("CREATE (:Commit {project: $project, commit_hash: 'abc12345', subject: $subject})", {"project": project, "subject": text})
            db.execute("CREATE (:FileChange {project: $project, path: 'src/db.py', change_id: 'CHANGE-001', ts: '2026-01-02', reason: $text, commit_hash: 'abc12345'})", {"project": project, "text": text})
            db.execute("MATCH (f:FileChange {project: $project}), (d:Decision {project: $project}) CREATE (f)-[:MOTIVATED_BY]->(d)", {"project": project})
        # A hostile cross-project edge must not admit a foreign decision.
        db.execute("MATCH (f:FileChange {project:'app'}), (d:Decision {project:'foreign'}) CREATE (f)-[:MOTIVATED_BY]->(d)")
        db.execute("CREATE (:Memory {project: 'app', name:'gone', status:'deleted', description:'SECRET DELETED'})")
        db.execute("CREATE (:Rule {rule_id:'SQL-001', statement:'Use parameters'})")
    finally:
        db.close()
    with RelateGraph(store) as graph:
        result = await compile_recall(graph, "app", prompt="src/db.py", project_root="/repo", full=True)
        assert len(result["decisions"]) == 1
        d = result["decisions"][0]
        assert (d["decision_id"], d["match"], d["rule_statements"]) == ("DEC-001", "path", {"SQL-001": "Use parameters"})
        assert "SECRET" not in json.dumps(result)
        line, key = await write_decision_context(graph, "app", ["src/db.py"], set())
        assert "abc12345" in line and "Use parameterized sql" in line
        assert key == "src/db.py#DEC-001"
        assert (await compile_recall(graph, "unknown"))["decisions"] == []
        inputs = await load_pipeline_inputs(graph)
        assert {n["node_type"] for n in inputs.candidates} == {"Rule"}


async def test_path_recall_limits_changes_before_deduplication(tmp_path):
    store = tmp_path / "path-limits"
    db = relate.connect(str(store))
    try:
        db.execute("CREATE (:Decision {project:'app', decision_id:'D1', planned_files:'[]'}), (:Decision {project:'app', decision_id:'D2', planned_files:'[]'})")
        for ident, decision, ts in [("C3", "D1", "3"), ("C2", "D1", "2"), ("C1", "D2", "1")]:
            db.execute("MATCH (d:Decision {decision_id:$decision}) CREATE (:FileChange {project:'app', path:'file.py', change_id:$ident, ts:$ts})-[:MOTIVATED_BY]->(d)", {"ident": ident, "decision": decision, "ts": ts})
        # No edge, and a foreign commit with a matching hash, must not hide/leak.
        db.execute("CREATE (:FileChange {project:'app', path:'file.py', change_id:'C4', ts:'4'}), (:Commit {project:'foreign', commit_hash:'abc', subject:'SECRET'})")
    finally:
        db.close()
    with RelateGraph(store) as graph:
        first_two = await graph.get_decisions_for_paths("app", ["file.py"], per_path=2)
        first_three = await graph.get_decisions_for_paths("app", ["file.py"], per_path=3)
    assert [r["decision_id"] for r in first_two["file.py"]] == ["D1"]
    assert [r["decision_id"] for r in first_three["file.py"]] == ["D1", "D2"]


async def test_documents_stay_record_scoped_through_real_collectors_and_indexes(tmp_path, monkeypatch):
    from writ_retrieval.retrieval.documents import assemble_document_pipeline, fit_documents_block
    monkeypatch.setenv("WRIT_RETRIEVAL_CACHE", str(tmp_path / "indexes"))
    store = tmp_path / "docs"
    db = relate.connect(str(store))
    try:
        for project, ident, text in [("app", "a", "sql database"), ("foreign", "b", "SECRET sql database"), ("_shared", "s", "sql")]:
            db.execute("CREATE (d:Document {doc_id:$id, project:$project, title:$title, path:'docs/db.md', kind:'docs'})-[:CONTAINS]->(c:Chunk {chunk_id:$id, doc_id:$id, project:$project, ordinal:0, text:$text, breadcrumb:'database'})", {"id": ident, "project": project, "title": text, "text": text})
    finally:
        db.close()
    with RelateGraph(store) as graph:
        inputs = await load_pipeline_inputs(graph, with_documents=True)
    assert inputs.candidates == []
    assert len(inputs.chunks) == 3
    docs = assemble_document_pipeline(inputs.chunks, embedding_model=ControlledEncoder())
    result = docs.query("sql database", project="app", exclude_ids=[])
    assert {c["id"] for c in result["chunks"]} == {"a", "s"}
    block, cards = fit_documents_block(result, 2000)
    assert "SECRET" not in block
    assert {c["id"] for c in cards} == {"a", "s"}
    assert {c["id"] for c in docs.query("sql", project=None, exclude_ids=[])["chunks"]} == {"s"}


async def test_unknown_or_missing_project_never_uses_foreign_record_bridge(controlled):
    from writ_retrieval.retrieval.pipeline import compute_graph_proximity
    cache = controlled.adjacency_cache
    cache._neighbors = {
        "SQL-001": [{"rule_id": "PRIVATE", "node_type": "Decision", "project": "foreign"}],
        "PRIVATE": [{"rule_id": "ASYNC-001", "node_type": "Rule", "project": "writ"}],
    }
    for caller in (None, "", "app"):
        assert compute_graph_proximity(["ASYNC-001"], ["SQL-001"], cache, caller_project=caller) == {"ASYNC-001": 0.0}
    assert compute_graph_proximity(["ASYNC-001"], ["SQL-001"], cache, caller_project="foreign") == {"ASYNC-001": 0.5}
    p = assemble_pipeline(controlled, embedding_model=ControlledEncoder(), abstention_threshold=0.3)
    visible = p.query("sql", project="app", budget_tokens=2000)
    assert "PRIVATE" not in json.dumps(visible)
    # Excluded top vector hit cannot hold the abstention gate open.
    assert p.query("sql", exclude_rule_ids=["SQL-001"])["mode"] == "abstained"
