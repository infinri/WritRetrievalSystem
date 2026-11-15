//! Regression evaluation and cost measurement (no Python required).
//!
//! * `eval`: runs the frozen, already-opened reliable-memory tasks (72) through the Rust
//!   pipeline with both fusion owners (Cypher vs Rust), scores exact labeled-passage delivery
//!   with the same rules as the historical evaluation, and compares per task with the
//!   committed Python-reference results. These are regression data, not unseen evaluation.
//! * `bench-cold`: interleaved fresh-process timing of arbitrary commands (wall time,
//!   peak RSS and CPU via wait4), used to compare the Rust CLI with reference commands.

use std::collections::BTreeMap;
use std::io::{BufRead, Write};
use std::path::{Path, PathBuf};

use anyhow::{bail, Context as _, Result};
use serde_json::{json, Value as Json};

use crate::context::{context, Fusion, Request, Requirements};
use crate::db::Store;
use crate::embed::Encoder;
use crate::memory::{import_passages, init, PassageFixture};
use crate::util::canonical;

pub struct Rng(u64);
impl Rng {
    pub fn new(seed: u64) -> Self {
        Rng(seed ^ 0x9E37_79B9_7F4A_7C15)
    }
    fn next(&mut self) -> u64 {
        self.0 ^= self.0 << 13;
        self.0 ^= self.0 >> 7;
        self.0 ^= self.0 << 17;
        self.0
    }
    pub fn shuffle<T>(&mut self, v: &mut [T]) {
        for i in (1..v.len()).rev() {
            let j = (self.next() % (i as u64 + 1)) as usize;
            v.swap(i, j);
        }
    }
}

fn pct(xs: &[f64], q: f64) -> Option<f64> {
    if xs.is_empty() {
        return None;
    }
    let mut v = xs.to_vec();
    v.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let k = (v.len() - 1) as f64 * q;
    let (lo, hi) = (
        k.floor() as usize,
        (k.floor() as usize + 1).min(v.len() - 1),
    );
    Some(v[lo] + (v[hi] - v[lo]) * (k - lo as f64))
}

fn passage_token(s: &str) -> Option<String> {
    // "<40-hex revision>:<24-hex passage id>" appears in both Rust and Python identities.
    let b = s.as_bytes();
    (0..b.len().saturating_sub(64)).find_map(|i| {
        let w = &s[i..i + 65];
        (w.as_bytes()[40] == b':'
            && w[..40].bytes().all(|c| c.is_ascii_hexdigit())
            && w[41..].bytes().all(|c| c.is_ascii_hexdigit()))
        .then(|| w.to_string())
    })
}

fn score(task: &Json, payload: &Json) -> Json {
    let items = payload["items"].as_array().cloned().unwrap_or_default();
    let gold = task["gold"].as_array().cloned().unwrap_or_default();
    let hits: Vec<Option<usize>> = gold
        .iter()
        .map(|g| {
            items.iter().position(|c| {
                c["source"]["uri"] == g["uri"]
                    && c["source"]["revision"] == g["revision"]
                    && c["content_digest"] == g["content_digest"]
                    && c["text"]
                        .as_str()
                        .unwrap_or("")
                        .contains(g["answer_text"].as_str().unwrap_or("\u{0}"))
            })
        })
        .collect();
    let n = hits.iter().filter(|h| h.is_some()).count();
    let structured = task["track"] == "structured";
    let unknown_ok = if structured {
        payload["evidence_assessment"]["status"] == "insufficient"
    } else {
        payload["abstained"] == true
    };
    json!({"gold": gold.len(), "delivered": n, "complete": !gold.is_empty() && n == gold.len(),
        "mrr": hits.iter().flatten().min().map(|r| 1.0 / (*r as f64 + 1.0)).unwrap_or(0.0),
        "abstained": payload["abstained"], "evidence_status": payload["evidence_assessment"]["status"],
        "correct_unknown": if task["expected_unknown"] == true { json!(unknown_ok) } else { Json::Null },
        "citation_correct": items.iter().all(|c| c["source"]["revision"] == task["corpus_revision"] && c["project"] == task["project"]),
        "bytes": payload["budget"]["bytes"], "chars": payload["budget"]["chars"],
        "delivered_tokens": items.iter().filter_map(|c| c["vkey"].as_str().and_then(passage_token)).collect::<Vec<_>>()})
}

fn read_gz_jsonl(p: &Path) -> Result<Vec<Json>> {
    let f = std::fs::File::open(p).with_context(|| format!("open {}", p.display()))?;
    let r = std::io::BufReader::new(flate2::read::GzDecoder::new(f));
    r.lines().map(|l| Ok(serde_json::from_str(&l?)?)).collect()
}

pub struct EvalArgs {
    pub tasks: PathBuf,
    pub fixtures: PathBuf,
    pub reference: Option<PathBuf>,
    pub work: PathBuf,
    pub out: PathBuf,
    pub repetitions: usize,
    pub model_dir: PathBuf,
}

pub fn eval(a: &EvalArgs) -> Result<Json> {
    if a.work.exists() || a.out.join("queries.jsonl").exists() {
        bail!("use a fresh --work directory and --out");
    }
    std::fs::create_dir_all(&a.out)?;
    let tasks: Vec<Json> = serde_json::from_str::<Json>(&std::fs::read_to_string(&a.tasks)?)?
        ["tasks"]
        .as_array()
        .cloned()
        .unwrap_or_default();
    let t = std::time::Instant::now();
    let enc = Encoder::load(&a.model_dir)?;
    let model_load_ms = t.elapsed().as_secs_f64() * 1e3;
    let mut stores = BTreeMap::new();
    let mut imports = BTreeMap::new();
    for rev in tasks
        .iter()
        .filter_map(|t| t["corpus_revision"].as_str())
        .collect::<std::collections::BTreeSet<_>>()
    {
        let fx: PassageFixture = serde_json::from_str(&std::fs::read_to_string(
            a.fixtures.join(format!("history-{}.json", &rev[..7])),
        )?)?;
        let path = a.work.join(format!("store-{}", &rev[..7]));
        let mut st = Store::open(path.to_str().unwrap(), false)?;
        init(&mut st, &enc.identity)?;
        let t = std::time::Instant::now();
        let r = import_passages(&mut st, &enc, &fx, "writ-public")?;
        imports.insert(rev.to_string(), json!({"passages": r["imported"], "import_ms_including_inference": t.elapsed().as_secs_f64() * 1e3}));
        stores.insert(rev.to_string(), st);
    }
    let fusions = [("cypher", Fusion::Cypher), ("app", Fusion::App)];
    let run_one = |stores: &mut BTreeMap<String, Store>,
                   task: &Json,
                   fusion: Fusion|
     -> Result<(Json, f64, Vec<String>)> {
        let mut req = Request::new(
            task["query"].as_str().unwrap(),
            task["project"].as_str().unwrap(),
        );
        req.requirements =
            serde_json::from_value::<Requirements>(task["request"].clone()).unwrap_or_default();
        req.fusion = fusion;
        let st = stores
            .get_mut(task["corpus_revision"].as_str().unwrap())
            .unwrap();
        let t = std::time::Instant::now();
        let r = context(st, &enc, &req);
        let ms = t.elapsed().as_secs_f64() * 1e3;
        Ok(match r {
            Ok((p, tm)) => (
                p,
                ms,
                tm.candidates
                    .iter()
                    .filter_map(|c| passage_token(c))
                    .collect(),
            ),
            Err(e) => (json!({"error": e.to_string()}), ms, vec![]),
        })
    };
    // Warm-up once per fusion owner (not recorded), then randomized, rotated repetitions.
    for (_, f) in fusions {
        for task in &tasks {
            run_one(&mut stores, task, f)?;
        }
    }
    let mut rng = Rng::new(20261114);
    let mut rows = vec![];
    for rep in 0..a.repetitions {
        let mut order: Vec<usize> = (0..tasks.len()).collect();
        rng.shuffle(&mut order);
        for (n, &ti) in order.iter().enumerate() {
            let owners = if (n + rep) % 2 == 0 {
                [fusions[0], fusions[1]]
            } else {
                [fusions[1], fusions[0]]
            };
            for (name, f) in owners {
                let (payload, ms, cands) = run_one(&mut stores, &tasks[ti], f)?;
                let sc = if payload.get("error").is_some() {
                    json!({"error": payload["error"]})
                } else {
                    score(&tasks[ti], &payload)
                };
                rows.push(json!({"task_id": tasks[ti]["id"], "split": tasks[ti]["split"], "track": tasks[ti]["track"], "category": tasks[ti]["category"],
                    "fusion": name, "repeat": rep, "elapsed_ms": ms, "score": sc, "candidates": cands, "items": payload["items"].as_array().map(|a| a.len()).unwrap_or(0), "payload_digest": crate::util::text_digest(&canonical(&payload))}));
            }
        }
    }
    let mut f = std::fs::File::create(a.out.join("queries.jsonl"))?;
    for r in &rows {
        writeln!(f, "{}", canonical(r))?;
    }
    // Reference: committed Python results (repeat 0), if provided.
    let mut reference: BTreeMap<(String, String), Json> = BTreeMap::new();
    if let Some(dir) = &a.reference {
        for split in ["development", "heldout"] {
            let p = dir.join(split).join("queries.jsonl.gz");
            if p.exists() {
                for r in read_gz_jsonl(&p)? {
                    if r["repeat"] == 0 {
                        reference.insert(
                            (
                                r["task_id"].as_str().unwrap().into(),
                                r["arm"].as_str().unwrap().into(),
                            ),
                            r,
                        );
                    }
                }
            }
        }
    }
    let first: Vec<&Json> = rows.iter().filter(|r| r["repeat"] == 0).collect();
    let mut summary = BTreeMap::new();
    for split in ["development", "heldout"] {
        for (fname, _) in fusions {
            let sel: Vec<&&Json> = first
                .iter()
                .filter(|r| r["split"] == split && r["fusion"] == fname)
                .collect();
            let nat: Vec<&&&Json> = sel
                .iter()
                .filter(|r| r["track"] == "natural" && r["score"]["gold"].as_u64().unwrap_or(0) > 0)
                .collect();
            let pos: Vec<&&&Json> = sel
                .iter()
                .filter(|r| r["score"]["gold"].as_u64().unwrap_or(0) > 0)
                .collect();
            let unk: Vec<&&&Json> = sel
                .iter()
                .filter(|r| !r["score"]["correct_unknown"].is_null())
                .collect();
            let times: Vec<f64> = rows
                .iter()
                .filter(|r| r["split"] == split && r["fusion"] == fname)
                .map(|r| r["elapsed_ms"].as_f64().unwrap())
                .collect();
            summary.insert(format!("{split}/{fname}"), json!({
                "natural_complete": nat.iter().filter(|r| r["score"]["complete"] == true).count(), "natural_positive": nat.len(),
                "all_complete": pos.iter().filter(|r| r["score"]["complete"] == true).count(), "all_positive": pos.len(),
                "natural_mrr": if nat.is_empty() { Json::Null } else { json!(nat.iter().map(|r| r["score"]["mrr"].as_f64().unwrap_or(0.0)).sum::<f64>() / nat.len() as f64) },
                "correct_unknown": unk.iter().filter(|r| r["score"]["correct_unknown"] == true).count(), "unknown": unk.len(),
                "errors": sel.iter().filter(|r| r["score"].get("error").is_some()).count(),
                "citation_failures": sel.iter().filter(|r| r["score"]["citation_correct"] == false).count(),
                "max_chars": sel.iter().filter_map(|r| r["score"]["chars"].as_u64()).max(),
                "warm_samples": times.len(), "warm_p50_ms": pct(&times, 0.5), "warm_p95_ms": pct(&times, 0.95)}));
        }
    }
    // Per-task comparison: fusion owner (Cypher vs Rust) and language/implementation (Rust vs Python reference).
    let mut cmp = vec![];
    for task in &tasks {
        let id = task["id"].as_str().unwrap();
        let get = |f: &str| {
            first
                .iter()
                .find(|r| r["task_id"] == id && r["fusion"] == f)
                .map(|r| r["score"].clone())
                .unwrap_or(Json::Null)
        };
        let rust_row = first
            .iter()
            .find(|r| r["task_id"] == id && r["fusion"] == "cypher")
            .cloned()
            .cloned()
            .unwrap_or(Json::Null);
        let py_cands: Option<Vec<String>> = reference
            .get(&(id.to_string(), "grounded-relate".to_string()))
            .map(|r| {
                r["result"]["diagnostics"]["candidate_ids"]
                    .as_array()
                    .cloned()
                    .unwrap_or_default()
                    .iter()
                    .filter_map(|x| x.as_str().and_then(passage_token))
                    .collect()
            });
        let rust_cands: Vec<String> = rust_row["candidates"]
            .as_array()
            .cloned()
            .unwrap_or_default()
            .iter()
            .filter_map(|x| x.as_str().map(String::from))
            .collect();
        let py_items = reference
            .get(&(id.to_string(), "grounded-relate".to_string()))
            .map(|r| {
                r["score"]["delivered_ids"]
                    .as_array()
                    .map(|a| a.len())
                    .unwrap_or(0)
            });
        let (c, ap) = (get("cypher"), get("app"));
        let py = |arm: &str| {
            reference
                .get(&(id.to_string(), arm.to_string()))
                .map(|r| r["score"].clone())
        };
        let py_tokens = |arm: &str| {
            reference.get(&(id.to_string(), arm.to_string())).map(|r| {
                r["score"]["delivered_ids"]
                    .as_array()
                    .cloned()
                    .unwrap_or_default()
                    .iter()
                    .filter_map(|x| x.as_str().and_then(passage_token))
                    .collect::<Vec<_>>()
            })
        };
        cmp.push(json!({"task": id, "split": task["split"], "category": task["category"],
            "rust_cypher_complete": c["complete"], "rust_app_complete": ap["complete"],
            "fusion_owner_identical_delivery": c["delivered_tokens"] == ap["delivered_tokens"],
            "python_grounded_relate_complete": py("grounded-relate").map(|s| s["complete_proxy"].clone()),
            "python_grounded_flat_complete": py("grounded-flat").map(|s| s["complete_proxy"].clone()),
            "python_legacy_hybrid_complete": py("legacy-hybrid").map(|s| s["complete_proxy"].clone()),
            "same_passages_as_python_grounded_relate": py_tokens("grounded-relate").map(|t| json!(t == c["delivered_tokens"].as_array().cloned().unwrap_or_default().iter().filter_map(|x| x.as_str().map(String::from)).collect::<Vec<_>>())),
            "python_unknown_correct": py("grounded-relate").map(|s| s["correct_unknown"].clone()),
            "candidates_identical_order": py_cands.as_ref().map(|p| *p == rust_cands),
            "candidates_identical_set": py_cands.as_ref().map(|p| { let mut a = p.clone(); let mut b = rust_cands.clone(); a.sort(); b.sort(); a == b }),
            "rust_items_delivered": rust_row["items"], "python_items_delivered": py_items}));
    }
    let count = |f: &dyn Fn(&Json) -> bool| cmp.iter().filter(|c| f(c)).count();
    let comparison = json!({
        "fusion_owner_identical_delivery": count(&|c| c["fusion_owner_identical_delivery"] == true), "tasks": cmp.len(),
        "candidates_identical_order_vs_python_grounded_relate": count(&|c| c["candidates_identical_order"] == true),
        "candidates_identical_set_vs_python_grounded_relate": count(&|c| c["candidates_identical_set"] == true),
        "mean_items_delivered": {"rust": cmp.iter().filter_map(|c| c["rust_items_delivered"].as_f64()).sum::<f64>() / cmp.len() as f64,
                                 "python_grounded_relate": cmp.iter().filter_map(|c| c["python_items_delivered"].as_f64()).sum::<f64>() / cmp.len() as f64},
        "rust_vs_python_grounded_relate": {
            "both_complete": count(&|c| c["rust_cypher_complete"] == true && c["python_grounded_relate_complete"] == true),
            "rust_only": cmp.iter().filter(|c| c["rust_cypher_complete"] == true && c["python_grounded_relate_complete"] == false).map(|c| c["task"].clone()).collect::<Vec<_>>(),
            "python_only": cmp.iter().filter(|c| c["rust_cypher_complete"] == false && c["python_grounded_relate_complete"] == true).map(|c| c["task"].clone()).collect::<Vec<_>>(),
            "identical_delivered_passages": count(&|c| c["same_passages_as_python_grounded_relate"] == true)},
        "rust_vs_python_legacy_hybrid": {
            "rust_only": cmp.iter().filter(|c| c["rust_cypher_complete"] == true && c["python_legacy_hybrid_complete"] == false).map(|c| c["task"].clone()).collect::<Vec<_>>(),
            "python_only": cmp.iter().filter(|c| c["rust_cypher_complete"] == false && c["python_legacy_hybrid_complete"] == true).map(|c| c["task"].clone()).collect::<Vec<_>>()}});
    std::fs::write(
        a.out.join("per-task.json"),
        serde_json::to_string_pretty(&cmp)? + "\n",
    )?;
    let mut ru: libc::rusage = unsafe { std::mem::zeroed() };
    unsafe { libc::getrusage(libc::RUSAGE_SELF, &mut ru) };
    let report = json!({"contract_version": "writ-relate-eval/1", "labels": "MODEL-AUTHORED, NOT HUMAN REVIEWED; opened sets used as regression data only",
        "settings": {"k": 6, "cosine_gate": 0.30, "rrf_k": 60, "max_bytes": 8000, "max_chars": 6000, "repetitions": a.repetitions, "seed": 20261114, "warmup_passes": 1},
        "model_load_ms": model_load_ms, "imports": imports, "summary": summary, "comparison": comparison,
        "process_peak_rss_kib": ru.ru_maxrss, "cpu_seconds": ru.ru_utime.tv_sec as f64 + ru.ru_stime.tv_sec as f64 + (ru.ru_utime.tv_usec + ru.ru_stime.tv_usec) as f64 / 1e6,
        "note": "Warm persistent Rust process; timings include query embedding, Relate search/fusion, enrichment queries, validation and complete rendering. One process for all arms; RSS is not per-arm."});
    std::fs::write(
        a.out.join("summary.json"),
        serde_json::to_string_pretty(&report)? + "\n",
    )?;
    Ok(report)
}

/// Interleaved fresh-process timing. Input: {"commands": {"name": ["argv", ...]}, "repetitions": N, "warmups": W}.
pub fn bench_cold(spec: &Path, out: &Path) -> Result<Json> {
    let s: Json = serde_json::from_str(&std::fs::read_to_string(spec)?)?;
    let cmds: BTreeMap<String, Vec<String>> = serde_json::from_value(s["commands"].clone())?;
    let reps = s["repetitions"].as_u64().unwrap_or(10) as usize;
    let warm = s["warmups"].as_u64().unwrap_or(2) as usize;
    let run = |argv: &[String]| -> Result<(i32, f64, i64, f64, String)> {
        let t = std::time::Instant::now();
        let child = std::process::Command::new(&argv[0])
            .args(&argv[1..])
            .stdout(std::process::Stdio::piped())
            .stderr(std::process::Stdio::null())
            .spawn()?;
        let pid = child.id() as i32;
        let mut stdout = child.stdout.unwrap();
        let mut buf = Vec::new();
        std::io::Read::read_to_end(&mut stdout, &mut buf)?;
        let mut status = 0;
        let mut ru: libc::rusage = unsafe { std::mem::zeroed() };
        unsafe { libc::wait4(pid, &mut status, 0, &mut ru) };
        let ms = t.elapsed().as_secs_f64() * 1e3;
        let code = if libc::WIFEXITED(status) {
            libc::WEXITSTATUS(status)
        } else {
            -1
        };
        let cpu = ru.ru_utime.tv_sec as f64
            + ru.ru_stime.tv_sec as f64
            + (ru.ru_utime.tv_usec + ru.ru_stime.tv_usec) as f64 / 1e6;
        Ok((code, ms, ru.ru_maxrss, cpu, crate::util::sha256_hex(&buf)))
    };
    for argv in cmds.values() {
        for _ in 0..warm {
            run(argv)?;
        }
    }
    let mut plan: Vec<(String, usize)> = cmds
        .keys()
        .flat_map(|k| (0..reps).map(move |r| (k.clone(), r)))
        .collect();
    Rng::new(20261114).shuffle(&mut plan);
    let mut rows = vec![];
    for (name, rep) in plan {
        let (code, ms, rss, cpu, digest) = run(&cmds[&name])?;
        rows.push(json!({"name": name, "repeat": rep, "exit": code, "elapsed_ms": ms, "peak_rss_kib": rss, "cpu_s": cpu, "stdout_sha256": digest}));
    }
    std::fs::create_dir_all(out)?;
    let mut f = std::fs::File::create(out.join("samples.jsonl"))?;
    for r in &rows {
        writeln!(f, "{}", canonical(r))?;
    }
    let mut summary = BTreeMap::new();
    for name in cmds.keys() {
        let ok: Vec<&Json> = rows
            .iter()
            .filter(|r| r["name"] == name.as_str() && r["exit"] == 0)
            .collect();
        let ms: Vec<f64> = ok
            .iter()
            .map(|r| r["elapsed_ms"].as_f64().unwrap())
            .collect();
        summary.insert(name.clone(), json!({"samples": ok.len(), "failures": rows.iter().filter(|r| r["name"] == name.as_str() && r["exit"] != 0).count(),
            "p50_ms": pct(&ms, 0.5), "p95_ms": pct(&ms, 0.95), "max_peak_rss_kib": ok.iter().filter_map(|r| r["peak_rss_kib"].as_i64()).max(),
            "mean_cpu_s": if ok.is_empty() { Json::Null } else { json!(ok.iter().map(|r| r["cpu_s"].as_f64().unwrap()).sum::<f64>() / ok.len() as f64) },
            "deterministic_stdout": ok.iter().map(|r| r["stdout_sha256"].as_str().unwrap_or("").to_string()).collect::<std::collections::BTreeSet<_>>().len() <= 1}));
    }
    let report = json!({"contract_version": "writ-relate-bench-cold/1", "repetitions": reps, "warmups": warm, "seed": 20261114, "commands": cmds, "summary": summary,
        "note": "Fresh process per sample, randomized interleaving, warm disk. Peak RSS/CPU per child via wait4. Loopback/local only."});
    std::fs::write(
        out.join("summary.json"),
        serde_json::to_string_pretty(&report)? + "\n",
    )?;
    Ok(report)
}
