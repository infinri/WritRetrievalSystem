//! Contract tests on the real embedded Relate engine and real ONNX inference.
//! No engine capability is mocked; fault injection only aborts our own transaction or
//! damages store files on disk.

use std::path::PathBuf;
use std::process::Command;
use std::sync::OnceLock;

use serde_json::{json, Value as Json};
use writ_relate::context::{context, Request, Requirements, SourceSelector};
use writ_relate::db::{s, Store};
use writ_relate::embed::Encoder;
use writ_relate::memory::{self, Binding, Capture, Passage, PassageFixture, Retraction};
use writ_relate::params;
use writ_relate::util::{canonical, sha256_hex, text_digest};

const REV: &str = "1111111111111111111111111111111111111111";
const BIN: &str = env!("CARGO_BIN_EXE_writ-relate");

fn model_dir() -> PathBuf {
    PathBuf::from(std::env::var("WRIT_MODEL_DIR").unwrap_or_else(|_| "../data/model".into()))
}

fn enc() -> &'static Encoder {
    static E: OnceLock<Encoder> = OnceLock::new();
    E.get_or_init(|| Encoder::load(&model_dir()).expect("model (set WRIT_MODEL_DIR or run scripts/fetch-model.sh)"))
}

fn passage(path: &str, start: i64, heading: &str, text: &str) -> Passage {
    Passage {
        id: sha256_hex(format!("{path}\0{start}\0{text}").as_bytes())[..24].to_string(),
        path: path.into(), heading: heading.into(), text: text.into(), start, end: start + text.chars().count() as i64,
        start_line: 3, end_line: 3 + text.matches('\n').count() as i64, revision: REV.into(), committed_at: "2026-11-13T00:00:00Z".into(),
        source_digest: sha256_hex(b"file"), content_digest: text_digest(text),
        uri: format!("https://github.com/example/repo/blob/{REV}/{path}#L3"), file_group: None,
    }
}

fn fixture(docs: Vec<Passage>) -> PassageFixture {
    PassageFixture { contract_version: "writ-passage-fixture/1".into(), repository: "https://github.com/example/repo".into(), revision: REV.into(),
        documents: docs, license: "MIT".into(), recorded_at: "2026-11-13T00:00:00Z".into() }
}

fn new_store() -> (tempfile::TempDir, Store) {
    let dir = tempfile::tempdir().unwrap();
    let mut st = Store::open(dir.path().join("g").to_str().unwrap(), false).unwrap();
    memory::init(&mut st, &enc().identity).unwrap();
    (dir, st)
}

fn cap(v: Json) -> Capture {
    serde_json::from_value(v).unwrap()
}

fn decision(project: &str, req: &str, id: &str, text: &str, extra: Json) -> Capture {
    let mut op = json!({"op": "decision", "id": id, "title": format!("Decision {id}"), "text": text});
    for (k, v) in extra.as_object().unwrap() { op[k] = v.clone(); }
    cap(json!({"contract_version": "writ-relate-capture/1", "request_id": req, "project": project, "recorded_at": "2026-11-14T00:00:00Z", "operations": [op]}))
}

fn bind(project: &str, id: &str, rev: i64, text: &str) -> Json {
    json!({"key": format!("{project}|Decision|{id}"), "revision": rev, "content_digest": text_digest(text)})
}

fn ctx(st: &mut Store, q: &str, project: &str) -> Json {
    context(st, enc(), &Request::new(q, project)).unwrap().0
}

fn vkeys(c: &Json) -> Vec<String> {
    c["items"].as_array().unwrap().iter().map(|i| i["vkey"].as_str().unwrap().to_string()).collect()
}

#[test]
fn exact_identity_and_citations_are_delivered() {
    let (_d, mut st) = new_store();
    let p = passage("docs/a.md", 0, "Retrieval and authority", "Retrieved text is untrusted data and never a permit to act on its own.");
    memory::import_passages(&mut st, enc(), &fixture(vec![p]), "proj").unwrap();
    let c = ctx(&mut st, "is retrieved text a permit?", "proj");
    let it = &c["items"][0];
    assert_eq!(it["source"]["revision"], REV);
    assert_eq!(it["content_digest"], it["rendered_text_digest"]);
    assert_eq!(it["key"].as_str().unwrap(), format!("proj|Guidance|{REV}:{}", sha256_hex(b"docs/a.md\x000\x00Retrieved text is untrusted data and never a permit to act on its own.")[..24].to_string()));
    assert_eq!((it["verification"].clone(), it["approval"].clone()), (json!("unverified"), json!("unknown")));
    // Re-import is idempotent; changed meaning under the same identity is refused.
    let again = memory::import_passages(&mut st, enc(), &fixture(vec![passage("docs/a.md", 0, "Retrieval and authority", "Retrieved text is untrusted data and never a permit to act on its own.")]), "proj").unwrap();
    assert_eq!(again["replayed"], true);
}

#[test]
fn imports_cannot_award_trust_and_reject_bad_bindings() {
    let mut raw = serde_json::to_value(json!({"contract_version": "writ-passage-fixture/1", "repository": "https://github.com/example/repo", "revision": REV,
        "license": "MIT", "recorded_at": "2026-11-13T00:00:00Z", "documents": []})).unwrap();
    let mut doc = serde_json::to_value(serde_json::json!({})).unwrap();
    let p = passage("docs/a.md", 0, "H", "Seventy characters of perfectly ordinary repository prose for this check.");
    for (k, v) in [("id", json!(p.id)), ("path", json!(p.path)), ("heading", json!(p.heading)), ("text", json!(p.text)), ("start", json!(p.start)), ("end", json!(p.end)),
                   ("start_line", json!(3)), ("end_line", json!(3)), ("revision", json!(REV)), ("committed_at", json!(p.committed_at)), ("source_digest", json!(p.source_digest)),
                   ("content_digest", json!(p.content_digest)), ("uri", json!(p.uri)), ("verification", json!("owner_confirmed"))] {
        doc[k] = v;
    }
    raw["documents"] = json!([doc]);
    assert!(serde_json::from_value::<PassageFixture>(raw).is_err(), "an imported 'verification' field must be rejected");
    let mut bad = passage("docs/a.md", 0, "H", "Seventy characters of perfectly ordinary repository prose for this check.");
    bad.content_digest = text_digest("something else");
    let (_d, mut st) = new_store();
    assert!(memory::import_passages(&mut st, enc(), &fixture(vec![bad]), "proj").is_err());
    let c = serde_json::from_value::<Capture>(json!({"contract_version": "writ-relate-capture/1", "request_id": "r", "project": "p", "recorded_at": "2026-11-14T00:00:00Z",
        "operations": [{"op": "decision", "id": "d", "title": "t", "text": "x", "approval": "approved"}]}));
    assert!(c.is_err(), "capture cannot carry approval");
}

#[test]
fn scope_is_filtered_before_limits_and_hidden_bridges_do_not_leak() {
    let (_d, mut st) = new_store();
    // Twenty foreign records that match better than the single permitted one.
    let foreign: Vec<Passage> = (0..20).map(|i| passage(&format!("docs/f{i}.md"), 0, "Deployment rollback", &format!("Deployment rollback procedure step {i}: revert the release and restore the database snapshot."))).collect();
    memory::import_passages(&mut st, enc(), &fixture(foreign), "foreign").unwrap();
    memory::import_passages(&mut st, enc(), &fixture(vec![passage("docs/mine.md", 0, "Release notes", "Rollback of a deployment is documented in the release notes for this project only.")]), "mine").unwrap();
    let c = ctx(&mut st, "deployment rollback procedure", "mine");
    let keys = vkeys(&c);
    assert!(keys.iter().any(|k| k.starts_with("mine|")), "permitted record found despite 20 better foreign matches");
    assert!(keys.iter().all(|k| !k.starts_with("foreign|")), "no foreign record");
    // Bridge: shared guidance governs a foreign decision; 'mine' must not receive it.
    let g = passage("docs/shared.md", 0, "Shared rule", "Every schema migration needs a written rollback plan before it is merged.");
    let gb = json!({"key": format!("_shared|Guidance|{REV}:{}", g.id), "revision": 1, "content_digest": g.content_digest});
    memory::import_passages(&mut st, enc(), &fixture(vec![g]), "_shared").unwrap();
    memory::capture(&mut st, enc(), &decision("foreign", "f1", "secret", "Foreign team decision about schema migration rollback plans.", json!({"governed_by": [gb]}))).unwrap();
    let c = ctx(&mut st, "schema migration rollback plan", "mine");
    let keys = vkeys(&c);
    assert!(keys.iter().any(|k| k.starts_with("_shared|Guidance|")));
    assert!(keys.iter().all(|k| !k.contains("secret")), "foreign decision must not arrive through shared guidance");
    assert!(memory::capture(&mut st, enc(), &decision("mine", "m1", "x", "x", json!({"governed_by": [{"key": "foreign|Guidance|nope", "revision": 1, "content_digest": "sha256:00"}]}))).is_err());
}

#[test]
fn supersession_expiry_retraction_replay_and_no_rebinding() {
    let (_d, mut st) = new_store();
    let t1 = "Use the flat retrieval profile for the local workflow.";
    memory::capture(&mut st, enc(), &decision("p", "c1", "backend", t1, json!({"affects": ["src/a.rs"]}))).unwrap();
    let ev = |req: &str, id: &str, rev: i64, text: &str| cap(json!({"contract_version": "writ-relate-capture/1", "request_id": req, "project": "p", "recorded_at": "2026-11-14T00:00:01Z",
        "operations": [{"op": "evidence", "id": id, "kind": "local_owner_report", "text": format!("observation {id}"), "supports": [bind("p", "backend", rev, text)]}]}));
    memory::capture(&mut st, enc(), &ev("e1", "obs-1", 1, t1)).unwrap();
    // Replay of the same request is a no-op; reuse of the id for other content is refused.
    assert_eq!(memory::capture(&mut st, enc(), &ev("e1", "obs-1", 1, t1)).unwrap()["replayed"], true);
    assert!(memory::capture(&mut st, enc(), &ev("e1", "obs-2", 1, t1)).is_err());
    // Retract, then replay the original capture: the association stays retracted.
    let r: Retraction = serde_json::from_value(json!({"contract_version": "writ-relate-retract/1", "request_id": "x1", "recorded_at": "2026-11-14T00:00:02Z",
        "evidence": "p|Evidence|obs-1", "decision": bind("p", "backend", 1, t1), "reason": "measurement error"})).unwrap();
    memory::retract(&mut st, &r).unwrap();
    memory::capture(&mut st, enc(), &ev("e1", "obs-1", 1, t1)).unwrap();
    let mut req = Request::new("which retrieval profile for the local workflow", "p");
    req.path = Some("src/a.rs".into());
    let c = context(&mut st, enc(), &req).unwrap().0;
    let d = c["items"].as_array().unwrap().iter().find(|i| i["vkey"] == "p|Decision|backend@1").unwrap();
    assert_eq!(d["evidence"]["active_supporting"].as_array().unwrap().len(), 0);
    assert_eq!(d["evidence"]["retracted"][0]["reason"], "measurement error");
    // Supersede to new wording, then restore the original wording as revision 3.
    let t2 = "Use the native Relate profile for the local workflow.";
    let sup = |req: &str, from_rev: i64, from_text: &str, to: &str| cap(json!({"contract_version": "writ-relate-capture/1", "request_id": req, "project": "p", "recorded_at": "2026-11-14T00:00:03Z",
        "operations": [{"op": "supersede", "decision": bind("p", "backend", from_rev, from_text), "title": "Decision backend", "text": to, "reason": "revised", "affects": ["src/a.rs"]}]}));
    memory::capture(&mut st, enc(), &sup("s2", 1, t1, t2)).unwrap();
    assert!(memory::capture(&mut st, enc(), &sup("s2b", 1, t1, t2)).is_err(), "only the current revision can be superseded");
    memory::capture(&mut st, enc(), &sup("s3", 2, t2, t1)).unwrap();
    let c = context(&mut st, enc(), &req).unwrap().0;
    let d3 = c["items"].as_array().unwrap().iter().find(|i| i["vkey"] == "p|Decision|backend@3").expect("restored wording is the current revision");
    assert_eq!(d3["evidence"]["active_supporting"].as_array().unwrap().len(), 0, "old observations never rebind to restored wording");
    assert_eq!(d3["evidence"]["retracted"].as_array().unwrap().len(), 0);
    assert!(vkeys(&c).iter().all(|k| k != "p|Decision|backend@1" && k != "p|Decision|backend@2"), "superseded revisions are not current guidance");
    assert!(c["history"].as_array().unwrap().iter().any(|h| h["vkey"] == "p|Decision|backend@1"));
    // Evidence cannot attach to a superseded revision.
    assert!(memory::capture(&mut st, enc(), &ev("e9", "obs-9", 1, t1)).is_err());
    // Expiry: a decision valid until the past is not delivered as current.
    memory::capture(&mut st, enc(), &decision("p", "c9", "temporary", "Temporary freeze on the deployment pipeline.", json!({"valid_to": "2026-11-14T00:00:05Z", "affects": ["src/b.rs"]}))).unwrap();
    let mut r2 = Request::new("deployment pipeline freeze", "p");
    r2.path = Some("src/b.rs".into());
    r2.as_of = Some("2026-11-20T00:00:00Z".into());
    let c = context(&mut st, enc(), &r2).unwrap().0;
    assert!(vkeys(&c).iter().all(|k| !k.contains("temporary")));
    assert_eq!(c["history"][0]["lifecycle"], "expired");
    r2.as_of = Some("2026-11-14T00:00:04Z".into());
    assert!(vkeys(&context(&mut st, enc(), &r2).unwrap().0).iter().any(|k| k.contains("temporary")));
    assert_eq!(memory::verify(&mut st).unwrap()["ok"], true);
}

#[test]
fn conflict_bundles_required_records_and_hard_utf8_budget() {
    let (_d, mut st) = new_store();
    let long = "Ünïcödé façade — 日本語テキスト ".repeat(30);
    memory::capture(&mut st, enc(), &decision("p", "a", "alpha", &format!("Cache the index on disk. {long}"), json!({"affects": ["src/x.rs"]}))).unwrap();
    memory::capture(&mut st, enc(), &decision("p", "b", "beta", &format!("Never cache the index on disk. {long}"), json!({}))).unwrap();
    memory::capture(&mut st, enc(), &cap(json!({"contract_version": "writ-relate-capture/1", "request_id": "c", "project": "p", "recorded_at": "2026-11-14T00:00:00Z",
        "operations": [{"op": "conflict", "a": bind("p", "alpha", 1, &format!("Cache the index on disk. {long}")), "b": bind("p", "beta", 1, &format!("Never cache the index on disk. {long}")), "reason": "opposite caching policies"}]}))).unwrap();
    let mut req = Request::new("caching the index", "p");
    req.path = Some("src/x.rs".into());
    let c = context(&mut st, enc(), &req).unwrap().0;
    let ks = vkeys(&c);
    assert!(ks.contains(&"p|Decision|alpha@1".to_string()) && ks.contains(&"p|Decision|beta@1".to_string()), "conflict partner travels with the artifact decision: {ks:?}");
    let text = canonical(&c);
    assert!(text.len() <= 8000 && text.chars().count() <= 6000);
    assert_eq!(c["budget"]["bytes"].as_u64().unwrap() as usize, text.len());
    assert_eq!(c["budget"]["chars"].as_u64().unwrap() as usize, text.chars().count());
    // A bundle that cannot fit is omitted as a whole and counted.
    req.max_bytes = 4500;
    req.max_chars = 4000;
    let c = context(&mut st, enc(), &req).unwrap().0;
    assert!(!vkeys(&c).iter().any(|k| k.contains("alpha") || k.contains("beta")));
    assert!(c["omitted_records_total"].as_u64().unwrap() >= 2);
    // Required content that cannot fit is an explicit error, never silently clipped.
    req.required = vec!["p|Decision|alpha".into()];
    assert!(context(&mut st, enc(), &req).unwrap_err().to_string().contains("do not fit"));
}

#[test]
fn explicit_source_and_owner_confirmation_requirements() {
    let (_d, mut st) = new_store();
    let p = passage("docs/a.md", 0, "Capability packs", "Capability packs extend the kernel with typed, versioned contracts for tools.");
    let uri = p.uri.clone();
    memory::import_passages(&mut st, enc(), &fixture(vec![p]), "proj").unwrap();
    let mut req = Request::new("unrelated words entirely", "proj");
    req.requirements = Requirements { source: Some(SourceSelector { uri: uri.clone(), revision: REV.into() }), ..Default::default() };
    let c = context(&mut st, enc(), &req).unwrap().0;
    assert_eq!(c["evidence_assessment"]["status"], "requirements_satisfied");
    assert_eq!(c["items"][0]["channel"], "required");
    req.requirements.verification = Some("owner_confirmed".into());
    let c = context(&mut st, enc(), &req).unwrap().0;
    assert_eq!(c["evidence_assessment"]["status"], "insufficient", "imports never satisfy owner confirmation");
    let c = ctx(&mut st, "capability packs", "unrelated-project");
    assert_eq!(c["abstained"], true);
}

#[test]
fn tampered_records_are_detected_and_never_rendered() {
    let (_d, mut st) = new_store();
    memory::capture(&mut st, enc(), &decision("p", "a", "alpha", "Keep the single-writer boundary.", json!({"affects": ["src/x.rs"]}))).unwrap();
    st.q("MATCH (n:Decision {vkey:$v}) SET n.text = 'Allow multiple writers.'", params!("v" => s("p|Decision|alpha@1"))).unwrap();
    let v = memory::verify(&mut st).unwrap();
    assert_eq!(v["ok"], false);
    let mut req = Request::new("writer boundary", "p");
    req.path = Some("src/x.rs".into());
    assert!(context(&mut st, enc(), &req).unwrap_err().to_string().contains("does not match its content digest"));
}

fn run(args: &[&str], env: &[(&str, &str)]) -> (i32, Json, String) {
    let o = Command::new(BIN).args(args).env("WRIT_MODEL_DIR", model_dir()).envs(env.iter().cloned()).output().unwrap();
    (o.status.code().unwrap_or(-1), serde_json::from_slice(&o.stdout).unwrap_or(Json::Null), String::from_utf8_lossy(&o.stderr).into())
}

#[test]
fn failed_write_rolls_back_restart_and_corruption_fail_closed() {
    let dir = tempfile::tempdir().unwrap();
    let store = dir.path().join("g");
    let st = store.to_str().unwrap();
    assert_eq!(run(&["init", "--store", st], &[]).0, 0);
    let input = dir.path().join("c.json");
    std::fs::write(&input, canonical(&json!({"contract_version": "writ-relate-capture/1", "request_id": "r1", "project": "p", "recorded_at": "2026-11-14T00:00:00Z",
        "operations": [{"op": "decision", "id": "a", "title": "Writers", "text": "Keep the single-writer boundary.", "affects": ["src/x.rs"]}]}))).unwrap();
    let (code, _, err) = run(&["capture", "--store", st, "--input", input.to_str().unwrap()], &[("WRIT_RELATE_FAIL_BEFORE_COMMIT", "1")]);
    assert_eq!(code, 2, "{err}");
    let (_, v, _) = run(&["inspect", "--store", st, "p|Decision|a"], &[]);
    assert!(v.is_null(), "failed write left nothing behind");
    assert_eq!(run(&["capture", "--store", st, "--input", input.to_str().unwrap()], &[]).0, 0);
    // Fresh process (restart) sees the committed write.
    let (code, c, _) = run(&["context", "--store", st, "--project", "p", "--path", "src/x.rs", "writer boundary"], &[]);
    assert_eq!(code, 0);
    assert_eq!(c["items"][0]["vkey"], "p|Decision|a@1");
    assert_eq!(run(&["verify", "--store", st], &[]).0, 0);
    // Damage every store data file: opening must fail closed with no payload.
    for e in walk(&store) {
        let mut b = std::fs::read(&e).unwrap();
        if b.len() > 16 {
            for x in b.iter_mut().skip(8).step_by(7) { *x ^= 0x5a; }
            std::fs::write(&e, b).unwrap();
        }
    }
    let (code, out, err) = run(&["context", "--store", st, "--project", "p", "--path", "src/x.rs", "writer boundary"], &[]);
    assert_ne!(code, 0, "corrupt store must not serve context");
    assert!(out.is_null() && err.contains("error"));
    eprintln!("corruption error: {err}");
}

fn walk(p: &std::path::Path) -> Vec<PathBuf> {
    let mut v = vec![];
    for e in std::fs::read_dir(p).unwrap() {
        let e = e.unwrap().path();
        if e.is_dir() { v.extend(walk(&e)); } else if !e.file_name().unwrap().to_string_lossy().contains("lock") { v.push(e); }
    }
    v
}

#[test]
fn read_only_surfaces_deny_network() {
    let (code, v, err) = run(&["selftest-offline"], &[]);
    assert_eq!(code, 0, "{err}");
    assert!(v["tcp_error"].as_str().unwrap_or("").contains("denied") || v["tcp_error"].as_str().unwrap_or("").contains("ermission"), "{v}");
    assert!(v["udp_error"].is_string());
    assert_eq!(v["unix_socket_ok"], true);
}

#[test]
fn single_writer_lease_is_enforced_across_processes() {
    let dir = tempfile::tempdir().unwrap();
    let st = dir.path().join("g");
    let mut owner = Store::open(st.to_str().unwrap(), false).unwrap();
    memory::init(&mut owner, &enc().identity).unwrap();
    let input = dir.path().join("c.json");
    std::fs::write(&input, canonical(&json!({"contract_version": "writ-relate-capture/1", "request_id": "r1", "project": "p", "recorded_at": "2026-11-14T00:00:00Z",
        "operations": [{"op": "decision", "id": "a", "title": "t", "text": "x"}]}))).unwrap();
    let (code, _, err) = run(&["capture", "--store", st.to_str().unwrap(), "--input", input.to_str().unwrap()], &[]);
    assert_eq!(code, 2);
    assert!(err.to_lowercase().contains("lock"), "{err}");
    let (code, _, _) = run(&["verify", "--store", st.to_str().unwrap()], &[]);
    assert_eq!(code, 0, "read-only opens are allowed beside the writer");
    drop(owner);
    let _ = Binding { key: String::new(), revision: 0, content_digest: String::new() };
}
