//! Canonical connected memory stored in Relate: typed records, relationships, receipts and
//! native indexes. All writes are single engine transactions; any error rolls back.
//!
//! Relate owns: persistence, transactions, the single-writer lease, full-text and vector
//! indexes, scope/lifecycle filtering inside search, bounded traversal.
//! This module owns only what the engine cannot know: identity/revision/digest contracts,
//! replay-safe receipts, and the rule that imported or captured text never awards
//! verification, approval or outcomes.

use std::collections::BTreeSet;
use std::path::Path;

use anyhow::{anyhow, bail, Context, Result};
use relate::Value;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value as Json};

use crate::db::{floats, s, strings, Row, Store};
use crate::embed::{prepare, Encoder, DIMS};
use crate::params;
use crate::util::{canonical, check_id, check_project, check_utc, json_digest, now_utc, scope_tag, sha256_hex, text_digest};

pub const SHARED: &str = "_shared";
pub const STORE_CONTRACT: &str = "writ-relate-store/1";
pub const VECTOR_INDEX: &str = "writ_vec";

/// Exact reference to one immutable record version.
#[derive(Debug, Clone, Deserialize, Serialize, PartialEq)]
#[serde(deny_unknown_fields)]
pub struct Binding {
    pub key: String,
    pub revision: i64,
    pub content_digest: String,
}

impl Binding {
    pub fn to_json(&self) -> Json {
        json!({"key": self.key, "revision": self.revision, "content_digest": self.content_digest})
    }
}

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct SourceRef {
    pub uri: String,
    pub revision: String,
    pub path: String,
    pub start_line: i64,
    pub end_line: i64,
}

fn vkey(key: &str, rev: i64) -> String {
    format!("{key}@{rev}")
}

pub fn record_key(project: &str, label: &str, id: &str) -> String {
    format!("{project}|{label}|{id}")
}

pub fn parse_ref(r: &str) -> Result<(String, Option<i64>)> {
    match r.rsplit_once('@') {
        Some((k, v)) => Ok((k.to_string(), Some(v.parse().map_err(|_| anyhow!("bad revision in {r}"))?))),
        None => Ok((r.to_string(), None)),
    }
}

// ---------------------------------------------------------------------------------------
// Schema and scopes
// ---------------------------------------------------------------------------------------

pub fn init(st: &mut Store, encoder_identity: &str) -> Result<Json> {
    if !st.q0("MATCH (m:StoreMeta) RETURN m.contract AS c")?.is_empty() {
        bail!("store already initialized");
    }
    st.q0(&format!("CREATE VECTOR INDEX {VECTOR_INDEX} FOR (n:Searchable) ON n.embedding WITH [n.search_scope]"))?;
    st.q(
        "CREATE (:StoreMeta {contract:$c, created_at:$t, generation:0, encoder:$e})",
        params!("c" => s(STORE_CONTRACT), "t" => s(now_utc()), "e" => s(encoder_identity)),
    )?;
    st.checkpoint()?;
    Ok(json!({"initialized": true, "contract": STORE_CONTRACT}))
}

pub fn meta(st: &mut Store) -> Result<Row> {
    st.q0("MATCH (m:StoreMeta) RETURN m.contract AS contract, m.generation AS generation, m.encoder AS encoder, m.created_at AS created_at")?
        .into_iter()
        .next()
        .ok_or_else(|| anyhow!("not a writ-relate store (run init)"))
}

fn bump_generation(st: &mut Store) -> Result<i64> {
    let r = st.q0("MATCH (m:StoreMeta) SET m.generation = m.generation + 1 RETURN m.generation AS g")?;
    r.first().and_then(|r| r["g"].as_i64()).ok_or_else(|| anyhow!("store meta missing"))
}

pub fn scopes(st: &mut Store) -> Result<Vec<(String, String)>> {
    Ok(st
        .q0("MATCH (s:Scope) RETURN s.project AS p, s.tag AS t ORDER BY p")?
        .into_iter()
        .map(|r| (r["p"].as_str().unwrap().to_string(), r["t"].as_str().unwrap().to_string()))
        .collect())
}

/// A caller scope gets its own full-text index over exactly its permitted records
/// (its own plus `_shared`). Relate's full-text SEARCH rejects WHERE, so a per-scope index is
/// the native way to filter before limits and to keep hidden documents out of IDF.
pub fn ensure_scope(st: &mut Store, project: &str) -> Result<String> {
    let tag = scope_tag(project);
    if project == SHARED || st.q("MATCH (s:Scope {project:$p}) RETURN s.tag AS t", params!("p" => s(project)))?.len() == 1 {
        return Ok(tag);
    }
    st.q("CREATE (:Scope {project:$p, tag:$t})", params!("p" => s(project), "t" => s(tag.clone())))?;
    st.q(
        &format!("MATCH (n:Searchable) WHERE n.search_scope IN [$p, $sh] SET n:FT_{tag}"),
        params!("p" => s(project), "sh" => s(SHARED)),
    )?;
    st.q0(&format!("CREATE FULLTEXT INDEX ft_{tag} FOR (n:FT_{tag}) ON EACH [n.search_text]"))?;
    Ok(tag)
}

/// Lifecycle drives index membership natively: inactive records leave every full-text label
/// and get an inactive vector scope, so search filters them before limits.
fn set_searchable(st: &mut Store, vk: &str, project: &str, active: bool) -> Result<()> {
    let tags: Vec<String> = if project == SHARED {
        scopes(st)?.into_iter().map(|(_, t)| t).collect()
    } else {
        vec![scope_tag(project)]
    };
    let labels: String = tags.iter().map(|t| format!(":FT_{t}")).collect();
    if active {
        st.q(&format!("MATCH (n:Searchable {{vkey:$k}}) SET n.search_scope = n.project{}", if labels.is_empty() { String::new() } else { format!(", n{labels}") }), params!("k" => s(vk)))?;
    } else {
        st.q(&format!("MATCH (n:Searchable {{vkey:$k}}) SET n.search_scope = 'inactive:' + n.project{}", if labels.is_empty() { String::new() } else { format!(" REMOVE n{labels}") }), params!("k" => s(vk)))?;
    }
    Ok(())
}

// ---------------------------------------------------------------------------------------
// Receipts (replay safety)
// ---------------------------------------------------------------------------------------

/// Returns Some(receipt) when this exact request was already applied (replay is a no-op);
/// errors when the request id was used for different content.
fn receipt(st: &mut Store, request_id: &str, digest: &str) -> Result<Option<Json>> {
    check_id(request_id)?;
    let r = st.q("MATCH (r:Receipt {request_id:$id}) RETURN r.digest AS d, r.op AS op, r.at AS at, r.generation AS g", params!("id" => s(request_id)))?;
    match r.first() {
        None => Ok(None),
        Some(r) if r["d"] == digest => Ok(Some(json!({"replayed": true, "request_id": request_id, "op": r["op"], "applied_at": r["at"], "generation": r["g"]}))),
        Some(_) => bail!("request_id {request_id} was already used for different content; replay refused"),
    }
}

fn write_receipt(st: &mut Store, request_id: &str, op: &str, digest: &str, at: &str, generation: i64) -> Result<()> {
    st.q(
        "CREATE (:Receipt {request_id:$id, op:$op, digest:$d, at:$at, generation:$g})",
        params!("id" => s(request_id), "op" => s(op), "d" => s(digest), "at" => s(at), "g" => Value::Int(generation)),
    )?;
    Ok(())
}

// ---------------------------------------------------------------------------------------
// Public-source import (exact source references)
// ---------------------------------------------------------------------------------------

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct PassageFixture {
    pub contract_version: String,
    pub repository: String,
    pub revision: String,
    pub documents: Vec<Passage>,
    pub license: String,
    pub recorded_at: String,
}

/// Exactly the published passage fields. Any extra field (for example a verification or
/// approval claim) is rejected: imported text cannot award trust.
#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Passage {
    pub id: String,
    pub path: String,
    pub heading: String,
    pub text: String,
    pub start: i64,
    pub end: i64,
    pub start_line: i64,
    pub end_line: i64,
    pub revision: String,
    pub committed_at: String,
    pub source_digest: String,
    pub content_digest: String,
    pub uri: String,
    #[serde(default)]
    pub file_group: Option<i64>,
}

fn is_hex(s: &str, n: usize) -> bool {
    s.len() == n && s.bytes().all(|b| b.is_ascii_hexdigit() && !b.is_ascii_uppercase())
}

pub fn check_passages(fx: &PassageFixture) -> Result<()> {
    if fx.contract_version != "writ-passage-fixture/1" || !is_hex(&fx.revision, 40) {
        bail!("unsupported passage fixture or revision");
    }
    check_utc(&fx.recorded_at)?;
    for d in &fx.documents {
        let expected = &sha256_hex(format!("{}\0{}\0{}", d.path, d.start, d.text).as_bytes())[..24];
        let ok = d.id == expected
            && d.revision == fx.revision
            && d.committed_at == fx.recorded_at
            && d.content_digest == text_digest(&d.text)
            && is_hex(&d.source_digest, 64)
            && d.end - d.start == d.text.chars().count() as i64
            && d.start_line >= 1
            && d.end_line - d.start_line == d.text.matches('\n').count() as i64
            && d.uri == format!("{}/blob/{}/{}#L{}", fx.repository, fx.revision, d.path, d.start_line)
            && d.path.ends_with(".md")
            && !d.path.starts_with('/')
            && !d.path.split('/').any(|p| p == ".." || p.is_empty());
        if !ok {
            bail!("passage {} fails identity/digest/source-binding checks", d.id);
        }
    }
    Ok(())
}

/// Optional: compare every passage with the exact Git object (read-only `git cat-file`; no
/// checkout, fetch or hooks).
pub fn verify_git(repo: &Path, fx: &PassageFixture) -> Result<usize> {
    let mut files = std::collections::BTreeMap::<String, String>::new();
    for d in &fx.documents {
        let text = match files.get(&d.path) {
            Some(t) => t.clone(),
            None => {
                let out = std::process::Command::new("git")
                    .arg("-C").arg(repo).args(["-c", "core.hooksPath=/dev/null", "cat-file", "-p"])
                    .arg(format!("{}:{}", fx.revision, d.path))
                    .env("GIT_NO_LAZY_FETCH", "1")
                    .output()
                    .context("run git cat-file")?;
                if !out.status.success() {
                    bail!("git object {}:{} unavailable", fx.revision, d.path);
                }
                let t = String::from_utf8(out.stdout)?;
                files.insert(d.path.clone(), t.clone());
                t
            }
        };
        let slice: String = text.chars().skip(d.start as usize).take((d.end - d.start) as usize).collect();
        if sha256_hex(text.as_bytes()) != d.source_digest || slice != d.text {
            bail!("passage {} differs from git object {}:{}", d.id, fx.revision, d.path);
        }
    }
    Ok(files.len())
}

pub fn import_passages(st: &mut Store, enc: &Encoder, fx: &PassageFixture, project: &str) -> Result<Json> {
    check_project(project)?;
    check_passages(fx)?;
    let request = json!({"op": "import", "project": project, "fixture_revision": fx.revision,
        "passages": fx.documents.iter().map(|d| json!([d.id, d.content_digest])).collect::<Vec<_>>()});
    let digest = json_digest(&request);
    let request_id = format!("import:{project}:{}", &digest[7..31]);
    if let Some(r) = receipt(st, &request_id, &digest)? {
        return Ok(r);
    }
    // Embedding inference happens before the transaction; the write is all-or-nothing.
    let vectors: Vec<Vec<f32>> = fx.documents.iter().map(|d| enc.embed(&prepare(&d.heading, &d.text))).collect::<Result<_>>()?;
    let at = now_utc();
    let (mut created, mut unchanged) = (0, 0);
    st.tx(|t| {
        ensure_scope(t, project)?;
        for (d, v) in fx.documents.iter().zip(&vectors) {
            let id = format!("{}:{}", fx.revision, d.id);
            let key = record_key(project, "Guidance", &id);
            let found = t.q("MATCH (n:Guidance {vkey:$k}) RETURN n.content_digest AS d", params!("k" => s(vkey(&key, 1))))?;
            if let Some(f) = found.first() {
                if f["d"] != d.content_digest.as_str() {
                    bail!("immutable guidance {key} changed meaning");
                }
                unchanged += 1;
                continue;
            }
            t.q(
                "CREATE (n:Guidance:Searchable {key:$key, vkey:$vk, label:'Guidance', project:$p, id:$id, rev:1, title:$title, text:$text, \
                 search_text:$st, content_digest:$cd, recorded_at:$rec, imported_at:$at, lifecycle:'current', origin:'repository_assertion', \
                 verification:'unverified', approval:'unknown', outcome:'unknown', source_uri:$uri, source_revision:$rev, source_path:$path, \
                 start_line:$sl, end_line:$el, committed_at:$ca, file_digest:$fd, repository:$repo, license:$lic, search_scope:'pending', embedding:$emb})",
                params!("key" => s(key.clone()), "vk" => s(vkey(&key, 1)), "p" => s(project), "id" => s(id), "title" => s(d.heading.clone()),
                    "text" => s(d.text.clone()), "st" => s(prepare(&d.heading, &d.text)), "cd" => s(d.content_digest.clone()),
                    "rec" => s(fx.recorded_at.clone()), "at" => s(at.clone()), "uri" => s(d.uri.clone()), "rev" => s(fx.revision.clone()),
                    "path" => s(d.path.clone()), "sl" => Value::Int(d.start_line), "el" => Value::Int(d.end_line), "ca" => s(d.committed_at.clone()),
                    "fd" => s(d.source_digest.clone()), "repo" => s(fx.repository.clone()), "lic" => s(fx.license.clone()), "emb" => floats(v)),
            )?;
            set_searchable(t, &vkey(&key, 1), project, true)?;
            created += 1;
        }
        let g = bump_generation(t)?;
        write_receipt(t, &request_id, "import", &digest, &at, g)?;
        Ok(())
    })?;
    st.checkpoint()?;
    Ok(json!({"imported": created, "unchanged": unchanged, "project": project, "revision": fx.revision, "request_id": request_id}))
}

// ---------------------------------------------------------------------------------------
// Owner capture: decisions, evidence, supersession, conflicts, retraction
// ---------------------------------------------------------------------------------------

#[derive(Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Capture {
    pub contract_version: String,
    pub request_id: String,
    pub project: String,
    pub recorded_at: String,
    pub operations: Vec<Op>,
}

#[derive(Debug, Deserialize, Serialize)]
#[serde(tag = "op", rename_all = "snake_case", deny_unknown_fields)]
pub enum Op {
    Decision {
        id: String,
        title: String,
        text: String,
        #[serde(default)]
        rationale: Option<String>,
        #[serde(default)]
        source: Option<SourceRef>,
        #[serde(default)]
        governed_by: Vec<Binding>,
        #[serde(default)]
        affects: Vec<String>,
        #[serde(default)]
        valid_to: Option<String>,
    },
    Evidence {
        id: String,
        kind: String,
        text: String,
        #[serde(default)]
        source: Option<SourceRef>,
        #[serde(default)]
        supports: Vec<Binding>,
        #[serde(default)]
        contradicts: Vec<Binding>,
        #[serde(default)]
        valid_to: Option<String>,
    },
    Supersede {
        decision: Binding,
        title: String,
        text: String,
        reason: String,
        #[serde(default)]
        rationale: Option<String>,
        #[serde(default)]
        source: Option<SourceRef>,
        #[serde(default)]
        governed_by: Vec<Binding>,
        #[serde(default)]
        affects: Vec<String>,
    },
    Conflict {
        a: Binding,
        b: Binding,
        reason: String,
    },
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Retraction {
    pub contract_version: String,
    pub request_id: String,
    pub recorded_at: String,
    pub evidence: String,
    pub decision: Binding,
    pub reason: String,
}

fn current_version(st: &mut Store, b: &Binding, label: &str) -> Result<Row> {
    let rows = st.q(
        &format!("MATCH (n:{label} {{vkey:$vk}}) RETURN n.vkey AS vkey, n.project AS project, n.rev AS rev, n.content_digest AS digest, n.lifecycle AS lifecycle, n.key AS key"),
        params!("vk" => s(vkey(&b.key, b.revision))),
    )?;
    let r = rows.into_iter().next().ok_or_else(|| anyhow!("{label} {}@{} not found", b.key, b.revision))?;
    if r["digest"] != b.content_digest.as_str() {
        bail!("binding digest mismatch for {}@{}", b.key, b.revision);
    }
    Ok(r)
}

fn visible(project: &str, owner: &str) -> bool {
    owner == project || owner == SHARED
}

fn source_params(src: &Option<SourceRef>) -> Result<Vec<(&'static str, Value)>> {
    Ok(match src {
        None => vec![("source_uri", Value::Null), ("source_revision", Value::Null), ("source_path", Value::Null), ("start_line", Value::Null), ("end_line", Value::Null)],
        Some(r) => {
            if !(is_hex(&r.revision, 40) && r.start_line >= 1 && r.end_line >= r.start_line && r.uri.starts_with("https://")) {
                bail!("source must be an https URI with an exact 40-hex revision and a line interval");
            }
            vec![("source_uri", s(r.uri.clone())), ("source_revision", s(r.revision.clone())), ("source_path", s(r.path.clone())),
                 ("start_line", Value::Int(r.start_line)), ("end_line", Value::Int(r.end_line))]
        }
    })
}

#[allow(clippy::too_many_arguments)]
fn create_decision(t: &mut Store, enc_vec: &[f32], project: &str, id: &str, rev: i64, title: &str, text: &str, rationale: &Option<String>,
                   source: &Option<SourceRef>, valid_to: &Option<String>, recorded_at: &str, request_id: &str) -> Result<String> {
    let key = record_key(project, "Decision", id);
    let vk = vkey(&key, rev);
    let mut p = params!("key" => s(key.clone()), "vk" => s(vk.clone()), "p" => s(project), "id" => s(id), "rev" => Value::Int(rev),
        "title" => s(title), "text" => s(text), "st" => s(prepare(title, text)), "cd" => s(text_digest(text)), "rec" => s(recorded_at),
        "rat" => rationale.clone().map(s).unwrap_or(Value::Null), "vt" => valid_to.clone().map(s).unwrap_or(Value::Null),
        "req" => s(request_id), "emb" => floats(enc_vec));
    for (k, v) in source_params(source)? {
        p.insert(k.to_string(), v);
    }
    t.q(
        "CREATE (n:Decision:Searchable {key:$key, vkey:$vk, label:'Decision', project:$p, id:$id, rev:$rev, title:$title, text:$text, search_text:$st, \
         content_digest:$cd, recorded_at:$rec, rationale:$rat, valid_to:$vt, lifecycle:'current', origin:'local_owner_capture', \
         verification:'unverified', approval:'unknown', outcome:'unknown', request_id:$req, source_uri:$source_uri, source_revision:$source_revision, \
         source_path:$source_path, start_line:$start_line, end_line:$end_line, search_scope:'pending', embedding:$emb})",
        p,
    )?;
    set_searchable(t, &vk, project, true)?;
    Ok(vk)
}

fn link_decision(t: &mut Store, project: &str, vk: &str, governed_by: &[Binding], affects: &[String]) -> Result<()> {
    for g in governed_by {
        let r = current_version(t, g, "Guidance")?;
        if !visible(project, r["project"].as_str().unwrap()) {
            bail!("guidance {} is not visible to project {project}", g.key);
        }
        if r["lifecycle"] != "current" {
            bail!("guidance {} is not current", g.key);
        }
        t.q(
            "MATCH (d:Decision {vkey:$d}), (g:Guidance {vkey:$g}) CREATE (d)-[:GOVERNED_BY {guidance_rev:$rev, guidance_digest:$dg}]->(g)",
            params!("d" => s(vk), "g" => s(vkey(&g.key, g.revision)), "rev" => Value::Int(g.revision), "dg" => s(g.content_digest.clone())),
        )?;
    }
    for path in affects {
        if path.is_empty() || path.starts_with('/') || path.split('/').any(|x| x == "..") {
            bail!("artifact path must be repository-relative: {path}");
        }
        let akey = record_key(project, "Artifact", path);
        t.q("MERGE (a:Artifact {key:$k}) ON CREATE SET a.project = $p, a.path = $path, a.label = 'Artifact'", params!("k" => s(akey.clone()), "p" => s(project), "path" => s(path.clone())))?;
        t.q("MATCH (d:Decision {vkey:$d}), (a:Artifact {key:$k}) CREATE (d)-[:AFFECTS]->(a)", params!("d" => s(vk), "k" => s(akey)))?;
    }
    Ok(())
}

pub fn capture(st: &mut Store, enc: &Encoder, c: &Capture) -> Result<Json> {
    if c.contract_version != "writ-relate-capture/1" {
        bail!("unsupported capture contract");
    }
    check_project(&c.project)?;
    if c.project == SHARED {
        bail!("local captures belong to a project, not _shared");
    }
    check_utc(&c.recorded_at)?;
    if c.recorded_at > now_utc() {
        bail!("recorded_at is in the future");
    }
    let digest = json_digest(&serde_json::to_value(c)?);
    if let Some(r) = receipt(st, &c.request_id, &digest)? {
        return Ok(r);
    }
    // Inference first (outside the transaction).
    let mut vectors = Vec::new();
    for op in &c.operations {
        match op {
            Op::Decision { title, text, .. } | Op::Supersede { title, text, .. } => vectors.push(enc.embed(&prepare(title, text))?),
            _ => vectors.push(Vec::new()),
        }
    }
    let mut applied = Vec::new();
    st.tx(|t| {
        ensure_scope(t, &c.project)?;
        for (op, vec) in c.operations.iter().zip(&vectors) {
            match op {
                Op::Decision { id, title, text, rationale, source, governed_by, affects, valid_to } => {
                    check_id(id)?;
                    if let Some(v) = valid_to { check_utc(v)?; }
                    let key = record_key(&c.project, "Decision", id);
                    if !t.q("MATCH (n:Decision {key:$k}) RETURN n.rev AS r", params!("k" => s(key.clone())))?.is_empty() {
                        bail!("decision {key} exists; revise it with a supersede operation");
                    }
                    let vk = create_decision(t, vec, &c.project, id, 1, title, text, rationale, source, valid_to, &c.recorded_at, &c.request_id)?;
                    link_decision(t, &c.project, &vk, governed_by, affects)?;
                    applied.push(json!({"op": "decision", "created": vk}));
                }
                Op::Supersede { decision, title, text, reason, rationale, source, governed_by, affects } => {
                    let old = current_version(t, decision, "Decision")?;
                    if old["project"] != c.project.as_str() {
                        bail!("cannot supersede another project's decision");
                    }
                    if old["lifecycle"] != "current" {
                        bail!("{}@{} is not the current revision; supersede the current one", decision.key, decision.revision);
                    }
                    let newest = t.q("MATCH (n:Decision {key:$k}) RETURN max(n.rev) AS r", params!("k" => s(decision.key.clone())))?;
                    let rev = newest[0]["r"].as_i64().unwrap_or(0) + 1;
                    let id = decision.key.splitn(3, '|').nth(2).unwrap().to_string();
                    let old_vk = vkey(&decision.key, decision.revision);
                    t.q("MATCH (n:Decision {vkey:$vk}) SET n.lifecycle = 'superseded', n.superseded_at = $at", params!("vk" => s(old_vk.clone()), "at" => s(c.recorded_at.clone())))?;
                    set_searchable(t, &old_vk, &c.project, false)?;
                    let vk = create_decision(t, vec, &c.project, &id, rev, title, text, rationale, source, &None, &c.recorded_at, &c.request_id)?;
                    t.q(
                        "MATCH (new:Decision {vkey:$n}), (old:Decision {vkey:$o}) CREATE (new)-[:SUPERSEDES {reason:$r, at:$at, from_rev:$fr, from_digest:$fd}]->(old)",
                        params!("n" => s(vk.clone()), "o" => s(old_vk.clone()), "r" => s(reason.clone()), "at" => s(c.recorded_at.clone()),
                            "fr" => Value::Int(decision.revision), "fd" => s(decision.content_digest.clone())),
                    )?;
                    link_decision(t, &c.project, &vk, governed_by, affects)?;
                    applied.push(json!({"op": "supersede", "superseded": old_vk, "current": vk}));
                }
                Op::Evidence { id, kind, text, source, supports, contradicts, valid_to } => {
                    check_id(id)?;
                    if !["repository_document", "local_owner_report", "tool_output"].contains(&kind.as_str()) {
                        bail!("evidence kind must be repository_document, local_owner_report or tool_output");
                    }
                    if let Some(v) = valid_to { check_utc(v)?; }
                    let key = record_key(&c.project, "Evidence", id);
                    let existing = t.q("MATCH (e:Evidence {key:$k}) RETURN e.content_digest AS d", params!("k" => s(key.clone())))?;
                    match existing.first() {
                        Some(e) if e["d"] != text_digest(text).as_str() => bail!("evidence {key} is immutable; new evidence needs a new id"),
                        Some(_) => {}
                        None => {
                            let mut p = params!("key" => s(key.clone()), "vk" => s(vkey(&key, 1)), "p" => s(c.project.clone()), "id" => s(id.clone()),
                                "kind" => s(kind.clone()), "text" => s(text.clone()), "cd" => s(text_digest(text)), "rec" => s(c.recorded_at.clone()),
                                "vt" => valid_to.clone().map(s).unwrap_or(Value::Null), "req" => s(c.request_id.clone()));
                            for (k, v) in source_params(source)? { p.insert(k.to_string(), v); }
                            t.q("CREATE (e:Evidence {key:$key, vkey:$vk, label:'Evidence', project:$p, id:$id, rev:1, kind:$kind, text:$text, content_digest:$cd, \
                                 recorded_at:$rec, valid_to:$vt, request_id:$req, lifecycle:'current', verification:'unverified', approval:'unknown', outcome:'unknown', \
                                 source_uri:$source_uri, source_revision:$source_revision, source_path:$source_path, start_line:$start_line, end_line:$end_line})", p)?;
                        }
                    }
                    for (rel, targets) in [("SUPPORTS", supports), ("CONTRADICTS", contradicts)] {
                        for b in targets {
                            let d = current_version(t, b, "Decision")?;
                            if d["project"] != c.project.as_str() || d["lifecycle"] != "current" {
                                bail!("evidence can bind only the current revision of a decision in this project");
                            }
                            let prior = t.q("MATCH (:Evidence {key:$e})-[r]->(:Decision {vkey:$d}) RETURN r.state AS state", params!("e" => s(key.clone()), "d" => s(vkey(&b.key, b.revision))))?;
                            if !prior.is_empty() {
                                bail!("evidence {key} is already associated with {}@{} (state {}); a retracted association is never reactivated", b.key, b.revision, prior[0]["state"]);
                            }
                            t.q(&format!("MATCH (e:Evidence {{key:$e}}), (d:Decision {{vkey:$d}}) CREATE (e)-[:{rel} {{state:'active', decision_rev:$r, decision_digest:$dg, request_id:$req, at:$at}}]->(d)"),
                                params!("e" => s(key.clone()), "d" => s(vkey(&b.key, b.revision)), "r" => Value::Int(b.revision), "dg" => s(b.content_digest.clone()),
                                    "req" => s(c.request_id.clone()), "at" => s(c.recorded_at.clone())))?;
                        }
                    }
                    applied.push(json!({"op": "evidence", "evidence": key}));
                }
                Op::Conflict { a, b, reason } => {
                    let (x, y) = (current_version(t, a, "Decision")?, current_version(t, b, "Decision")?);
                    if x["project"] != c.project.as_str() || y["project"] != c.project.as_str() || a.key == b.key {
                        bail!("conflicts link two different decisions in this project");
                    }
                    t.q("MATCH (a:Decision {vkey:$a}), (b:Decision {vkey:$b}) CREATE (a)-[:CONFLICTS_WITH {reason:$r, at:$at, a_rev:$ar, b_rev:$br}]->(b)",
                        params!("a" => s(vkey(&a.key, a.revision)), "b" => s(vkey(&b.key, b.revision)), "r" => s(reason.clone()), "at" => s(c.recorded_at.clone()),
                            "ar" => Value::Int(a.revision), "br" => Value::Int(b.revision)))?;
                    applied.push(json!({"op": "conflict", "between": [a.key, b.key]}));
                }
            }
        }
        if std::env::var("WRIT_RELATE_FAIL_BEFORE_COMMIT").is_ok() {
            bail!("injected failure before commit (WRIT_RELATE_FAIL_BEFORE_COMMIT)");
        }
        let g = bump_generation(t)?;
        write_receipt(t, &c.request_id, "capture", &digest, &c.recorded_at, g)?;
        Ok(())
    })?;
    st.checkpoint()?;
    Ok(json!({"replayed": false, "request_id": c.request_id, "applied": applied}))
}

/// Retraction preserves the evidence record and the association; it flips the association
/// to `retracted` permanently. Replaying the original capture cannot undo it.
pub fn retract(st: &mut Store, r: &Retraction) -> Result<Json> {
    if r.contract_version != "writ-relate-retract/1" {
        bail!("unsupported retraction contract");
    }
    check_utc(&r.recorded_at)?;
    let digest = json_digest(&json!({"evidence": r.evidence, "decision": r.decision.to_json(), "reason": r.reason}));
    if let Some(x) = receipt(st, &r.request_id, &digest)? {
        return Ok(x);
    }
    st.tx(|t| {
        current_version(t, &r.decision, "Decision")?;
        let rows = t.q(
            "MATCH (e:Evidence {key:$e})-[a]->(d:Decision {vkey:$d}) WHERE a.decision_digest = $dg RETURN a.state AS state",
            params!("e" => s(r.evidence.clone()), "d" => s(vkey(&r.decision.key, r.decision.revision)), "dg" => s(r.decision.content_digest.clone())),
        )?;
        match rows.first().map(|x| x["state"].as_str().unwrap_or("")) {
            None => bail!("no association between {} and {}@{}", r.evidence, r.decision.key, r.decision.revision),
            Some("retracted") => bail!("association already retracted"),
            _ => {}
        }
        t.q(
            "MATCH (e:Evidence {key:$e})-[a]->(d:Decision {vkey:$d}) SET a.state = 'retracted', a.retracted_at = $at, a.retraction_reason = $why, a.retraction_request = $req",
            params!("e" => s(r.evidence.clone()), "d" => s(vkey(&r.decision.key, r.decision.revision)), "at" => s(r.recorded_at.clone()),
                "why" => s(r.reason.clone()), "req" => s(r.request_id.clone())),
        )?;
        let g = bump_generation(t)?;
        write_receipt(t, &r.request_id, "retract", &digest, &r.recorded_at, g)
    })?;
    st.checkpoint()?;
    Ok(json!({"retracted": true, "evidence": r.evidence, "decision": r.decision.to_json(), "request_id": r.request_id}))
}

// ---------------------------------------------------------------------------------------
// Inspection and integrity verification (read-only)
// ---------------------------------------------------------------------------------------

const RECORD_FIELDS: &str = "n.key AS key, n.vkey AS vkey, n.label AS label, n.project AS project, n.id AS id, n.rev AS revision, n.title AS title, \
    n.text AS text, n.content_digest AS content_digest, n.recorded_at AS recorded_at, n.valid_to AS valid_to, n.lifecycle AS lifecycle, \
    n.origin AS origin, n.kind AS kind, n.verification AS verification, n.approval AS approval, n.outcome AS outcome, n.rationale AS rationale, \
    n.source_uri AS source_uri, n.source_revision AS source_revision, n.source_path AS source_path, n.start_line AS start_line, \
    n.end_line AS end_line, n.committed_at AS committed_at, n.superseded_at AS superseded_at, n.path AS path";

pub fn record_fields() -> &'static str {
    RECORD_FIELDS
}

pub fn inspect(st: &mut Store, reference: &str) -> Result<Json> {
    let (key, rev) = parse_ref(reference)?;
    let versions = st.q(&format!("MATCH (n {{key:$k}}) RETURN {RECORD_FIELDS} ORDER BY revision"), params!("k" => s(key.clone())))?;
    if versions.is_empty() {
        bail!("no record {key}");
    }
    let chosen: Vec<&Row> = versions.iter().filter(|v| rev.is_none_or(|r| v["revision"].as_i64() == Some(r))).collect();
    if chosen.is_empty() {
        bail!("no revision {reference}");
    }
    let target = chosen.last().unwrap()["vkey"].as_str().unwrap_or("").to_string();
    let out = st.q(
        "MATCH (n {vkey:$v})-[r]->(m) RETURN type(r) AS rel, m.vkey AS target, m.key AS key, properties(r) AS props ORDER BY rel, target",
        params!("v" => s(target.clone())),
    )?;
    let inc = st.q(
        "MATCH (n {vkey:$v})<-[r]-(m) RETURN type(r) AS rel, m.vkey AS source, m.key AS key, properties(r) AS props ORDER BY rel, source",
        params!("v" => s(target.clone())),
    )?;
    let receipts = st.q("MATCH (r:Receipt) WHERE r.request_id IN $ids RETURN r.request_id AS request_id, r.op AS op, r.at AS at, r.generation AS generation",
        params!("ids" => strings(versions.iter().filter_map(|v| v.get("request_id").and_then(|x| x.as_str()).map(String::from)))))?;
    let integrity: Vec<Json> = chosen.iter().map(|v| {
        let text = v["text"].as_str().unwrap_or("");
        json!({"vkey": v["vkey"], "text_digest_matches": text_digest(text) == v["content_digest"].as_str().unwrap_or("")})
    }).collect();
    Ok(json!({"contract_version": "writ-relate-inspect/1", "key": key, "requested": reference, "record": chosen.last(),
        "versions": versions.iter().map(|v| json!({"vkey": v["vkey"], "revision": v["revision"], "lifecycle": v["lifecycle"], "content_digest": v["content_digest"], "recorded_at": v["recorded_at"], "superseded_at": v["superseded_at"]})).collect::<Vec<_>>(),
        "outgoing": out, "incoming": inc, "receipts": receipts, "integrity": integrity,
        "note": "Exact stored version. Verification and approval are never set by import or capture; approval is not an agent operation."}))
}

pub fn verify(st: &mut Store) -> Result<Json> {
    let m = meta(st)?;
    let mut problems = Vec::new();
    let rows = st.q0("MATCH (n) WHERE n.content_digest IS NOT NULL RETURN n.vkey AS vkey, n.text AS text, n.content_digest AS cd, n.lifecycle AS lc, \
                      n.project AS project, n.search_scope AS scope, labels(n) AS labels, size(coalesce(n.embedding, [])) AS dims")?;
    let tags: BTreeSet<String> = scopes(st)?.into_iter().map(|(_, t)| t).collect();
    for r in &rows {
        let vk = r["vkey"].as_str().unwrap_or("?");
        if text_digest(r["text"].as_str().unwrap_or("")) != r["cd"].as_str().unwrap_or("") {
            problems.push(format!("{vk}: stored text does not match content_digest"));
        }
        let labels: Vec<&str> = r["labels"].as_array().map(|a| a.iter().filter_map(|x| x.as_str()).collect()).unwrap_or_default();
        if labels.contains(&"Searchable") {
            if r["dims"].as_i64() != Some(DIMS as i64) {
                problems.push(format!("{vk}: embedding dimension mismatch"));
            }
            let active = r["lc"] == "current";
            let project = r["project"].as_str().unwrap_or("");
            let expect_scope = if active { project.to_string() } else { format!("inactive:{project}") };
            if r["scope"].as_str() != Some(&expect_scope) {
                problems.push(format!("{vk}: vector scope {} disagrees with lifecycle", r["scope"]));
            }
            for t in &tags {
                let want = active && (project == SHARED || scope_tag(project) == *t);
                if labels.contains(&format!("FT_{t}").as_str()) != want {
                    problems.push(format!("{vk}: full-text membership FT_{t} disagrees with lifecycle/scope"));
                }
            }
        }
    }
    let dangling = st.q0("MATCH (e:Evidence)-[a]->(d:Decision) WHERE a.decision_digest <> d.content_digest OR a.decision_rev <> d.rev RETURN e.key AS e, d.vkey AS d")?;
    for d in dangling {
        problems.push(format!("association {} -> {} binds a different version", d["e"], d["d"]));
    }
    Ok(json!({"contract_version": "writ-relate-verify/1", "generation": m["generation"], "records": rows.len(), "problems": problems, "ok": problems.is_empty()}))
}

pub fn canonical_request_digest(v: &Json) -> String {
    text_digest(&canonical(v))
}
