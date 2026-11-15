//! Verifies the Relate 1.0.1 capabilities this application relies on, against the real
//! embedded engine (no mocks). If one of these fails after an upgrade, the ownership table
//! in docs/OWNERSHIP.md must be revisited.
use writ_relate::db::{floats, s, Store};
use writ_relate::params;

fn store() -> (tempfile::TempDir, Store) {
    let dir = tempfile::tempdir().unwrap();
    let st = Store::open(dir.path().join("g").to_str().unwrap(), false).unwrap();
    (dir, st)
}

#[test]
fn vector_search_filters_scope_before_limit() {
    let (_d, mut st) = store();
    for i in 0..30 {
        st.q(
            "CREATE (:C {uid:$u, scope:'foreign', embedding:$e})",
            params!("u" => s(format!("f{i}")), "e" => floats(&[1.0, 0.0])),
        )
        .unwrap();
    }
    st.q(
        "CREATE (:C {uid:'allowed', scope:'app', embedding:$e})",
        params!("e" => floats(&[0.6, 0.8])),
    )
    .unwrap();
    st.q0("CREATE VECTOR INDEX cv FOR (n:C) ON n.embedding WITH [n.scope]")
        .unwrap();
    let global = st.q("CALL db.index.vector.queryNodes('cv', 5, $v) YIELD node, score WHERE node.scope = 'app' RETURN node.uid AS uid", params!("v" => floats(&[1.0, 0.0]))).unwrap();
    assert!(
        global.is_empty(),
        "global top-k then filter starves the permitted node"
    );
    let scoped = st.q("MATCH (n:C) SEARCH n IN (VECTOR INDEX cv FOR $v WHERE n.scope IN $scopes LIMIT 5) SCORE AS sc RETURN n.uid AS uid, sc", params!("v" => floats(&[1.0, 0.0]), "scopes" => writ_relate::db::strings(vec!["app".to_string()]))).unwrap();
    assert_eq!(scoped.len(), 1);
    assert_eq!(scoped[0]["uid"], "allowed");
    let sc = scoped[0]["sc"].as_f64().unwrap();
    assert!(
        (2.0 * sc - 1.0 - 0.6).abs() < 1e-6,
        "score is (cosine+1)/2: {sc}"
    );
}

#[test]
fn fulltext_rejects_where_but_per_label_index_isolates_idf() {
    let (_d, mut st) = store();
    // Hidden project: many documents containing 'needle' would lower its IDF in a shared index.
    for i in 0..20 {
        st.q(
            "CREATE (:Doc:SearchHidden {uid:$u, text:'needle common words'})",
            params!("u" => s(format!("h{i}"))),
        )
        .unwrap();
    }
    st.q0("CREATE (:Doc:SearchApp {uid:'a1', text:'needle rare'})")
        .unwrap();
    st.q0("CREATE (:Doc:SearchApp {uid:'a2', text:'other common words'})")
        .unwrap();
    st.q0("CREATE FULLTEXT INDEX ft_all FOR (n:Doc) ON EACH [n.text]")
        .unwrap();
    st.q0("CREATE FULLTEXT INDEX ft_app FOR (n:SearchApp) ON EACH [n.text]")
        .unwrap();
    let err = st.q0("MATCH (n:Doc) SEARCH n IN (FULLTEXT INDEX ft_all FOR 'needle' WHERE n.uid = 'a1' LIMIT 5) SCORE AS s RETURN n.uid");
    assert!(
        err.is_err(),
        "fulltext SEARCH with WHERE is rejected by 1.0.1"
    );
    let shared = st.q0("CALL db.index.fulltext.queryNodes('ft_all', 'needle') YIELD node, score WHERE node.uid = 'a1' RETURN score").unwrap();
    let isolated = st.q0("CALL db.index.fulltext.queryNodes('ft_app', 'needle') YIELD node, score RETURN node.uid AS uid, score").unwrap();
    assert_eq!(isolated.len(), 1);
    let (a, b) = (
        shared[0]["score"].as_f64().unwrap(),
        isolated[0]["score"].as_f64().unwrap(),
    );
    assert!(
        b > a,
        "hidden documents change shared-index scores ({a}) but not the per-label index ({b})"
    );
}

#[test]
fn cypher_rrf_and_bounded_typed_traversal() {
    let (_d, mut st) = store();
    st.q0("CREATE (a:N {uid:'a', p:'x'})-[:R]->(b:N {uid:'b', p:'x'})-[:R]->(c:N {uid:'c', p:'hidden'})-[:R]->(d:N {uid:'d', p:'x'})").unwrap();
    let rows = st.q0("CALL { MATCH (n:N) WHERE n.p = 'x' RETURN n.uid AS uid, 1.0/61 AS r UNION ALL MATCH (n:N) WHERE n.uid IN ['a','b'] RETURN n.uid AS uid, 1.0/62 AS r } RETURN uid, sum(r) AS fused ORDER BY fused DESC, uid ASC").unwrap();
    assert_eq!(rows[0]["uid"], "a");
    // Invisible bridge: d is reachable from a only through hidden c, so it must not appear.
    let reach = st.q0("MATCH p = (a:N {uid:'a'})-[:R*1..3]->(m:N) WHERE all(x IN nodes(p) WHERE x.p = 'x') RETURN m.uid AS uid ORDER BY uid").unwrap();
    let got: Vec<_> = reach
        .iter()
        .map(|r| r["uid"].as_str().unwrap().to_string())
        .collect();
    assert_eq!(got, vec!["b"]);
}

#[test]
fn transaction_rollback_restart_and_single_writer() {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("g");
    let p = path.to_str().unwrap();
    {
        let mut st = Store::open(p, false).unwrap();
        st.q0("CREATE (:K {uid:'kept'})").unwrap();
        let r: anyhow::Result<()> = st.tx(|t| {
            t.q0("CREATE (:K {uid:'rolled-back'})")?;
            anyhow::bail!("injected failure")
        });
        assert!(r.is_err());
        assert!(
            Store::open(p, false).is_err(),
            "second writable open is refused while the writer lives"
        );
        let mut ro = Store::open(p, true).unwrap();
        assert!(
            ro.q0("CREATE (:K {uid:'x'})").is_err(),
            "read-only open refuses writes"
        );
        st.checkpoint().unwrap();
    }
    let mut st = Store::open(p, false).unwrap();
    let rows = st
        .q0("MATCH (k:K) RETURN k.uid AS uid ORDER BY uid")
        .unwrap();
    assert_eq!(rows.len(), 1);
    assert_eq!(rows[0]["uid"], "kept");
}
