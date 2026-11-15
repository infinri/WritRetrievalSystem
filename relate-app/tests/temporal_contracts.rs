//! Desired contracts for the six defects reproduced in the PR #11 review (original probes and
//! their before/after outputs are preserved in evidence/review-repros-pr11/).
//! Real Relate engine and real ONNX inference.
use std::path::PathBuf;
use std::sync::OnceLock;

use serde_json::{json, Value as Json};
use writ_relate::context::{context, Request};
use writ_relate::db::Store;
use writ_relate::embed::Encoder;
use writ_relate::memory::{self, Capture, Retraction};

fn enc() -> &'static Encoder {
    static E: OnceLock<Encoder> = OnceLock::new();
    E.get_or_init(|| {
        Encoder::load(&PathBuf::from(
            std::env::var("WRIT_MODEL_DIR").unwrap_or_else(|_| "../data/model".into()),
        ))
        .unwrap()
    })
}
fn setup() -> (tempfile::TempDir, Store) {
    let d = tempfile::tempdir().unwrap();
    let mut st = Store::open(d.path().join("g").to_str().unwrap(), false).unwrap();
    memory::init(&mut st, &enc().identity).unwrap();
    (d, st)
}
fn binding(id: &str, rev: i64, text: &str) -> Json {
    json!({"key": format!("p|Decision|{id}"), "revision": rev, "content_digest": writ_relate::util::text_digest(text)})
}
fn capture(st: &mut Store, id: &str, at: &str, operations: Json) -> anyhow::Result<Json> {
    let c: Capture = serde_json::from_value(json!({"contract_version": "writ-relate-capture/1", "request_id": id, "project": "p", "recorded_at": at, "operations": operations})).unwrap();
    memory::capture(st, enc(), &c)
}
fn required(id: &str, at: Option<&str>) -> Request {
    let mut r = Request::new("zzzzzzzznoquerymatch", "p");
    r.required = vec![format!("p|Decision|{id}")];
    r.as_of = at.map(String::from);
    r.gate = 2.0; // no semantic padding: isolate enrichment from the exact required record
    r.max_bytes = 64000;
    r.max_chars = 64000;
    r
}
fn keys(c: &Json) -> Vec<String> {
    c["items"]
        .as_array()
        .unwrap()
        .iter()
        .map(|i| i["vkey"].as_str().unwrap().to_string())
        .collect()
}
fn item<'a>(c: &'a Json, vk: &str) -> &'a Json {
    c["items"]
        .as_array()
        .unwrap()
        .iter()
        .find(|i| i["vkey"] == vk)
        .unwrap_or_else(|| panic!("{vk} missing: {:?}", keys(c)))
}

#[test]
fn impossible_calendar_dates_are_rejected() {
    for bad in [
        "2026-02-31T12:00:00Z",
        "2026-02-29T00:00:00Z",
        "2026-04-31T00:00:00Z",
        "1900-02-29T00:00:00Z",
    ] {
        assert!(writ_relate::util::check_utc(bad).is_err(), "{bad}");
    }
    writ_relate::util::check_utc("2028-02-29T00:00:00Z").unwrap();
    writ_relate::util::check_utc("2000-02-29T00:00:00Z").unwrap();
}

#[test]
fn evidence_recorded_after_as_of_is_not_delivered_and_retraction_applies_from_its_time() {
    let (_d, mut st) = setup();
    capture(
        &mut st,
        "d",
        "2026-11-10T00:00:00Z",
        json!([{"op": "decision", "id": "a", "title": "A", "text": "Use indexed context."}]),
    )
    .unwrap();
    capture(&mut st, "e", "2026-11-12T00:00:00Z", json!([{"op": "evidence", "id": "later", "kind": "tool_output", "text": "Test measured later.", "supports": [binding("a", 1, "Use indexed context.")]}])).unwrap();
    let c = context(&mut st, enc(), &required("a", Some("2026-11-11T00:00:00Z")))
        .unwrap()
        .0;
    assert!(!keys(&c).contains(&"p|Evidence|later@1".to_string()));
    assert_eq!(
        item(&c, "p|Decision|a@1")["evidence"]["active_supporting"],
        json!([])
    );
    let c = context(&mut st, enc(), &required("a", Some("2026-11-13T00:00:00Z")))
        .unwrap()
        .0;
    assert!(keys(&c).contains(&"p|Evidence|later@1".to_string()));
    // Retraction recorded Nov 14: still active as of Nov 13, retracted as of Nov 15.
    let r: Retraction = serde_json::from_value(json!({"contract_version": "writ-relate-retract/1", "request_id": "x", "recorded_at": "2026-11-14T00:00:00Z",
        "evidence": "p|Evidence|later", "decision": binding("a", 1, "Use indexed context."), "reason": "bad run"})).unwrap();
    memory::retract(&mut st, &r).unwrap();
    let c = context(&mut st, enc(), &required("a", Some("2026-11-13T00:00:00Z")))
        .unwrap()
        .0;
    assert_eq!(
        item(&c, "p|Decision|a@1")["evidence"]["active_supporting"]
            .as_array()
            .unwrap()
            .len(),
        1
    );
    let c = context(&mut st, enc(), &required("a", Some("2026-11-15T00:00:00Z")))
        .unwrap()
        .0;
    assert_eq!(
        item(&c, "p|Decision|a@1")["evidence"]["retracted"][0]["reason"],
        "bad run"
    );
    // A retraction cannot be dated before the association it retracts.
    let early: Retraction = serde_json::from_value(json!({"contract_version": "writ-relate-retract/1", "request_id": "x2", "recorded_at": "2026-11-11T00:00:00Z",
        "evidence": "p|Evidence|later", "decision": binding("a", 1, "Use indexed context."), "reason": "too early"})).unwrap();
    assert!(memory::retract(&mut st, &early).is_err());
}

fn chain(st: &mut Store, n: usize) {
    let mut ops = vec![];
    for i in 0..n {
        ops.push(json!({"op": "decision", "id": format!("d{i}"), "title": format!("D{i}"), "text": format!("Position {i}.")}));
    }
    for i in 0..n - 1 {
        ops.push(json!({"op": "conflict", "a": binding(&format!("d{i}"), 1, &format!("Position {i}.")),
            "b": binding(&format!("d{}", i + 1), 1, &format!("Position {}.", i + 1)), "reason": format!("{i}-{}", i + 1)}));
    }
    capture(st, "chain", "2026-11-10T00:00:00Z", json!(ops)).unwrap();
}

#[test]
fn conflict_chains_are_delivered_whole_or_marked_incomplete() {
    let (_d, mut st) = setup();
    chain(&mut st, 3); // d0 - d1 - d2
    let c = context(&mut st, enc(), &required("d0", None)).unwrap().0;
    for k in ["p|Decision|d0@1", "p|Decision|d1@1", "p|Decision|d2@1"] {
        assert!(
            keys(&c).contains(&k.to_string()),
            "{k} missing from {:?}",
            keys(&c)
        );
    }
    assert_eq!(c["conflict_bundles"][0]["complete"], true);
    assert!(c["conflict_bundles"][0]["note"]
        .as_str()
        .unwrap()
        .contains("does not assert"));
    // Longer than the 4-hop cap from d0.
    let (_d2, mut st2) = setup();
    chain(&mut st2, 7);
    let err = context(&mut st2, enc(), &required("d0", None))
        .unwrap_err()
        .to_string();
    assert!(err.contains("cannot be established completely"), "{err}");
    let mut r = Request::new("Position", "p");
    r.gate = -1.0;
    r.max_bytes = 64000;
    r.max_chars = 64000;
    let c = context(&mut st2, enc(), &r).unwrap().0;
    assert!(
        c["conflict_bundles"]
            .as_array()
            .unwrap()
            .iter()
            .any(|b| b["complete"] == false
                && b["reason"].as_str().unwrap().contains("traversal cap")),
        "{}",
        c["conflict_bundles"]
    );
}

#[test]
fn expired_conflict_partner_is_history_with_its_interval_not_current() {
    let (_d, mut st) = setup();
    capture(&mut st, "d", "2026-11-10T00:00:00Z", json!([
        {"op": "decision", "id": "a", "title": "A", "text": "Alpha."},
        {"op": "decision", "id": "b", "title": "B", "text": "Beta.", "valid_to": "2026-11-11T00:00:00Z"},
        {"op": "conflict", "a": binding("a", 1, "Alpha."), "b": binding("b", 1, "Beta."), "reason": "conflict"}
    ])).unwrap();
    let c = context(&mut st, enc(), &required("a", Some("2026-11-12T00:00:00Z")))
        .unwrap()
        .0;
    assert!(!keys(&c).contains(&"p|Decision|b@1".to_string()));
    let h = c["history"]
        .as_array()
        .unwrap()
        .iter()
        .find(|h| h["vkey"] == "p|Decision|b@1")
        .expect("expired partner listed as history");
    assert_eq!(h["lifecycle"], "expired");
    assert_eq!(h["valid_to"], "2026-11-11T00:00:00Z");
    let c = context(&mut st, enc(), &required("a", Some("2026-11-10T12:00:00Z")))
        .unwrap()
        .0;
    let b = item(&c, "p|Decision|b@1");
    assert_eq!(
        (b["lifecycle"].clone(), b["valid_to"].clone()),
        (json!("current"), json!("2026-11-11T00:00:00Z"))
    );
}

#[test]
fn records_and_links_cannot_predate_what_they_depend_on() {
    let (_d, mut st) = setup();
    capture(
        &mut st,
        "d",
        "2026-11-12T00:00:00Z",
        json!([{"op": "decision", "id": "a", "title": "A", "text": "Alpha."}]),
    )
    .unwrap();
    assert!(capture(&mut st, "s", "2026-11-11T00:00:00Z", json!([{"op": "supersede", "decision": binding("a", 1, "Alpha."), "title": "A2", "text": "Beta.", "reason": "backdated"}])).is_err());
    assert!(capture(&mut st, "e", "2026-11-11T00:00:00Z", json!([{"op": "evidence", "id": "x", "kind": "tool_output", "text": "t", "supports": [binding("a", 1, "Alpha.")]}])).is_err());
    capture(
        &mut st,
        "d2",
        "2026-11-12T00:00:00Z",
        json!([{"op": "decision", "id": "b", "title": "B", "text": "Beta."}]),
    )
    .unwrap();
    assert!(capture(&mut st, "c", "2026-11-11T00:00:00Z", json!([{"op": "conflict", "a": binding("a", 1, "Alpha."), "b": binding("b", 1, "Beta."), "reason": "r"}])).is_err());
    capture(&mut st, "s2", "2026-11-12T00:00:00Z", json!([{"op": "supersede", "decision": binding("a", 1, "Alpha."), "title": "A2", "text": "Gamma.", "reason": "same instant is allowed"}])).unwrap();
}

#[test]
fn point_in_time_requests_recover_the_decision_then_in_effect() {
    let (_d, mut st) = setup();
    capture(&mut st, "d", "2026-11-10T00:00:00Z", json!([{"op": "decision", "id": "a", "title": "A", "text": "Alpha.", "affects": ["src/a.rs"]}])).unwrap();
    capture(&mut st, "s", "2026-11-12T00:00:00Z", json!([{"op": "supersede", "decision": binding("a", 1, "Alpha."), "title": "A2", "text": "Beta.", "reason": "revision", "affects": ["src/a.rs"]}])).unwrap();
    let mut r = Request::new("zzzzzzzznoquerymatch", "p");
    r.path = Some("src/a.rs".into());
    r.gate = 2.0;
    r.as_of = Some("2026-11-11T00:00:00Z".into());
    let c = context(&mut st, enc(), &r).unwrap().0;
    assert_eq!(keys(&c), vec!["p|Decision|a@1".to_string()]);
    assert_eq!(item(&c, "p|Decision|a@1")["lifecycle"], "current");
    assert_eq!(item(&c, "p|Decision|a@1")["stored_lifecycle"], "superseded");
    r.as_of = None;
    let c = context(&mut st, enc(), &r).unwrap().0;
    assert!(keys(&c).contains(&"p|Decision|a@2".to_string()));
    assert!(c["history"]
        .as_array()
        .unwrap()
        .iter()
        .any(|h| h["vkey"] == "p|Decision|a@1"));
    // Point-in-time search finds the then-current revision by query, not only by artifact.
    let mut q = Request::new("Alpha", "p");
    q.as_of = Some("2026-11-11T00:00:00Z".into());
    q.gate = -1.0;
    let c = context(&mut st, enc(), &q).unwrap().0;
    assert!(
        keys(&c).contains(&"p|Decision|a@1".to_string())
            && !keys(&c).contains(&"p|Decision|a@2".to_string()),
        "{:?}",
        keys(&c)
    );
    // Without the all-version index, point-in-time search is reported unsupported.
    let tag = writ_relate::util::scope_tag("p");
    st.q0(&format!("DROP INDEX fth_{tag}")).unwrap();
    let err = context(&mut st, enc(), &q).unwrap_err().to_string();
    assert!(err.contains("unsupported for this store"), "{err}");
}
