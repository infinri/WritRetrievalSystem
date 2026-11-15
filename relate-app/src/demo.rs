//! Reproducible end-to-end demonstration. Every step is a separate `writ-relate` process,
//! so each step closes and reopens the Relate store (restart is exercised throughout).
//! The transcript records exact commands, exit codes, outputs and checked expectations.

use std::path::{Path, PathBuf};
use std::process::Command;

use anyhow::{bail, Context, Result};
use serde_json::{json, Value as Json};

use crate::util::{canonical, now_utc};

const PROJECT: &str = "writ-retrieval-system";
const D: &str = "writ-retrieval-system|Decision|local-workflow-backend";
const QUERY: &str = "Which retrieval implementation should the local hackathon workflow ship, and what evidence supports it?";

struct Step {
    name: &'static str,
    args: Vec<String>,
    expect_ok: bool,
}

fn find_default(rel: &str) -> PathBuf {
    for base in [".", "..", "../.."] {
        let p = Path::new(base).join(rel);
        if p.exists() {
            return p;
        }
    }
    PathBuf::from(rel)
}

fn items(v: &Json) -> Vec<&Json> {
    v["items"]
        .as_array()
        .map(|a| a.iter().collect())
        .unwrap_or_default()
}

fn find<'a>(v: &'a Json, vkey: &str) -> Option<&'a Json> {
    items(v).into_iter().find(|i| i["vkey"] == vkey)
}

pub fn run(
    out: &Path,
    store: Option<PathBuf>,
    fixture: Option<PathBuf>,
    seed: Option<PathBuf>,
    model_dir: PathBuf,
) -> Result<Json> {
    std::fs::create_dir_all(out)?;
    let store = store.unwrap_or_else(|| out.join("store"));
    if store.exists() {
        bail!(
            "{} exists; the demo builds a fresh store (use a new --out or --store)",
            store.display()
        );
    }
    let fixture = fixture.unwrap_or_else(|| {
        find_default("experiments/reliable_memory/fixtures/history-a0e0e41.json")
    });
    let seed = seed.unwrap_or_else(|| find_default("relate-app/demo/seed"));
    let exe = std::env::current_exe()?;
    let st = store.to_string_lossy().to_string();
    let sd = |f: &str| seed.join(f).to_string_lossy().to_string();
    let a = |v: &[&str]| v.iter().map(|s| s.to_string()).collect::<Vec<_>>();
    let ctx = |path: &str| {
        a(&[
            "context",
            "--store",
            &st,
            "--project",
            PROJECT,
            "--path",
            path,
            "--max-bytes",
            "16000",
            "--max-chars",
            "12000",
            QUERY,
        ])
    };
    let steps = vec![
        Step {
            name: "init",
            args: a(&["init", "--store", &st]),
            expect_ok: true,
        },
        Step {
            name: "import-public-guidance",
            args: a(&[
                "import",
                "--store",
                &st,
                "--fixture",
                &fixture.to_string_lossy(),
                "--project",
                "_shared",
            ]),
            expect_ok: true,
        },
        Step {
            name: "capture-pr10-decision-and-evidence",
            args: a(&[
                "capture",
                "--store",
                &st,
                "--input",
                &sd("01-capture-pr10-decision.json"),
            ]),
            expect_ok: true,
        },
        Step {
            name: "context-1-before-corrections",
            args: ctx("src/writ_retrieval/reliable/grounded_cli.py"),
            expect_ok: true,
        },
        Step {
            name: "retract-biased-review-evidence",
            args: a(&[
                "retract",
                "--store",
                &st,
                "--input",
                &sd("02-retract-biased-evidence.json"),
            ]),
            expect_ok: true,
        },
        Step {
            name: "reactivation-attempt-is-refused",
            args: a(&[
                "capture",
                "--store",
                &st,
                "--input",
                &sd("04-reactivation-attempt.json"),
            ]),
            expect_ok: false,
        },
        Step {
            name: "replay-original-capture-is-no-op",
            args: a(&[
                "capture",
                "--store",
                &st,
                "--input",
                &sd("01-capture-pr10-decision.json"),
            ]),
            expect_ok: true,
        },
        Step {
            name: "context-2-after-retraction",
            args: ctx("src/writ_retrieval/reliable/grounded_cli.py"),
            expect_ok: true,
        },
        Step {
            name: "supersede-with-owner-direction",
            args: a(&[
                "capture",
                "--store",
                &st,
                "--input",
                &sd("03-supersede-owner-direction.json"),
            ]),
            expect_ok: true,
        },
        Step {
            name: "context-3-after-restart-old-artifact",
            args: ctx("src/writ_retrieval/reliable/grounded_cli.py"),
            expect_ok: true,
        },
        Step {
            name: "context-4-after-restart-new-artifact",
            args: ctx("relate-app/src/main.rs"),
            expect_ok: true,
        },
        Step {
            name: "inspect-superseded-decision",
            args: a(&["inspect", "--store", &st, &format!("{D}@1")]),
            expect_ok: true,
        },
        Step {
            name: "verify-store",
            args: a(&["verify", "--store", &st]),
            expect_ok: true,
        },
    ];
    let mut transcript = vec![];
    let mut outputs = std::collections::BTreeMap::new();
    for s in &steps {
        let t = std::time::Instant::now();
        let o = Command::new(&exe)
            .args(&s.args)
            .env("WRIT_MODEL_DIR", &model_dir)
            .output()
            .with_context(|| format!("spawn {}", s.name))?;
        let ms = t.elapsed().as_secs_f64() * 1e3;
        let stdout: Json = serde_json::from_slice(&o.stdout).unwrap_or(Json::Null);
        let stderr: Json = serde_json::from_slice(&o.stderr)
            .unwrap_or_else(|_| json!(String::from_utf8_lossy(&o.stderr)));
        let ok = o.status.success() == s.expect_ok;
        transcript.push(json!({"step": s.name, "command": std::iter::once("writ-relate".to_string()).chain(s.args.iter().cloned()).collect::<Vec<_>>(),
            "exit_code": o.status.code(), "expected_success": s.expect_ok, "as_expected": ok, "elapsed_ms": ms, "stdout": stdout, "stderr": stderr}));
        outputs.insert(s.name, (stdout, stderr));
        if !ok {
            break;
        }
    }
    // Checked expectations: the connected chain changes exactly as the corrections say.
    let out_of = |n: &str| outputs.get(n).map(|x| x.0.clone()).unwrap_or(Json::Null);
    let err_of = |n: &str| outputs.get(n).map(|x| x.1.to_string()).unwrap_or_default();
    let d1 = format!("{D}@1");
    let d2 = format!("{D}@2");
    let (c1, c2, c3, c4) = (
        out_of("context-1-before-corrections"),
        out_of("context-2-after-retraction"),
        out_of("context-3-after-restart-old-artifact"),
        out_of("context-4-after-restart-new-artifact"),
    );
    let ev = |c: &Json, slot: &str| {
        find(c, &d1)
            .map(|i| i["evidence"][slot].as_array().map(|a| a.len()).unwrap_or(0))
            .unwrap_or(99)
    };
    let inspect = out_of("inspect-superseded-decision");
    let checks = vec![
        (
            "decision affecting the artifact is delivered with a why",
            find(&c1, &d1)
                .map(|i| i["channel"] == "artifact" && !i["why"].as_array().unwrap().is_empty())
                .unwrap_or(false),
        ),
        (
            "governing public guidance is connected with an exact binding",
            items(&c1)
                .iter()
                .any(|i| i["label"] == "Guidance" && i["binding"] == "exact"),
        ),
        (
            "before correction: 2 supporting and 1 contradicting active evidence",
            ev(&c1, "active_supporting") == 2 && ev(&c1, "active_contradicting") == 1,
        ),
        (
            "rationale is reported unknown, not invented",
            find(&c1, &d1)
                .map(|i| i["rationale"].as_str().unwrap_or("").starts_with("unknown"))
                .unwrap_or(false),
        ),
        (
            "retracted association cannot be reactivated",
            err_of("reactivation-attempt-is-refused").contains("never reactivated"),
        ),
        (
            "replaying the original capture is a no-op",
            out_of("replay-original-capture-is-no-op")["replayed"] == true,
        ),
        (
            "after retraction: contradicting evidence is retracted with its reason, not active",
            ev(&c2, "active_contradicting") == 0 && ev(&c2, "retracted") == 1,
        ),
        (
            "after supersession and restart: old decision is not current guidance",
            find(&c3, &d1).is_none()
                && c3["history"]
                    .as_array()
                    .map(|h| h.iter().any(|x| x["vkey"] == d1.as_str()))
                    .unwrap_or(false),
        ),
        (
            "after restart: the superseding decision is delivered for the new artifact",
            find(&c4, &d2)
                .map(|i| i["lifecycle"] == "current")
                .unwrap_or(false),
        ),
        (
            "history stays inspectable: old revision superseded, retracted association kept",
            inspect["record"]["lifecycle"] == "superseded"
                && inspect["incoming"]
                    .as_array()
                    .map(|a| {
                        a.iter().any(|r| {
                            r["rel"] == "CONTRADICTS" && r["props"]["state"] == "retracted"
                        })
                    })
                    .unwrap_or(false),
        ),
        (
            "no record gained verification or approval",
            [&c1, &c2, &c3, &c4].iter().all(|c| {
                items(c)
                    .iter()
                    .all(|i| i["verification"] == "unverified" && i["approval"] == "unknown")
            }),
        ),
        (
            "every payload is within its hard budget",
            [&c1, &c2, &c3, &c4].iter().all(|c| {
                c["budget"]["bytes"].as_u64().unwrap_or(u64::MAX) <= 16000
                    && c["budget"]["chars"].as_u64().unwrap_or(u64::MAX) <= 12000
            }),
        ),
        (
            "store integrity verified",
            out_of("verify-store")["ok"] == true,
        ),
    ];
    let passed = checks.iter().filter(|c| c.1).count();
    let all_steps =
        transcript.iter().all(|t| t["as_expected"] == true) && transcript.len() == steps.len();
    let report = json!({"contract_version": "writ-relate-demo/1", "ran_at": now_utc(), "store": st, "model_dir": model_dir,
        "steps_as_expected": all_steps, "checks": checks.iter().map(|(n, ok)| json!({"check": n, "pass": ok})).collect::<Vec<_>>(),
        "checks_passed": passed, "checks_total": checks.len(),
        "note": "Scripted CLI demonstration (each step a separate process). Not an agent experiment; see the MCP trace for a real host invocation."});
    std::fs::write(
        out.join("transcript.json"),
        canonical(&json!({"report": report, "steps": transcript})) + "\n",
    )?;
    std::fs::write(
        out.join("evidence-view.md"),
        evidence_view(&transcript, &checks),
    )?;
    if !all_steps || passed != checks.len() {
        bail!(
            "demo expectations failed ({passed}/{} checks); see {}",
            checks.len(),
            out.join("transcript.json").display()
        );
    }
    Ok(report)
}

fn short(vkey: &str) -> String {
    match vkey.split('|').collect::<Vec<_>>().as_slice() {
        [p, l, id] if *l == "Guidance" => {
            format!("{p}|Guidance|…{}", &id[id.len().saturating_sub(26)..])
        }
        _ => vkey.to_string(),
    }
}

/// Human-readable view of the connected chain at each context step (generated, not edited).
fn evidence_view(steps: &[Json], checks: &[(&str, bool)]) -> String {
    let mut md = String::from("# Demo evidence view\n\nGenerated by `writ-relate demo` from `transcript.json`. Each step is a separate process (the store is closed and reopened every time).\n\n");
    md += "| # | Step | Exit | ms |\n|---:|---|---:|---:|\n";
    for (i, s) in steps.iter().enumerate() {
        md += &format!(
            "| {} | {} | {} | {:.0} |\n",
            i + 1,
            s["step"].as_str().unwrap_or(""),
            s["exit_code"],
            s["elapsed_ms"].as_f64().unwrap_or(0.0)
        );
    }
    for s in steps
        .iter()
        .filter(|s| s["step"].as_str().unwrap_or("").starts_with("context"))
    {
        let c = &s["stdout"];
        md += &format!("\n## {}\n\n`{}`\n\nPayload {} bytes / {} chars (limit {} / {}); generation {}; omitted records {}.\n\n| Channel | Record | Lifecycle | Why | Evidence (support / contradict / retracted) |\n|---|---|---|---|---|\n",
            s["step"].as_str().unwrap_or(""), s["command"].as_array().map(|a| a.iter().filter_map(|x| x.as_str()).collect::<Vec<_>>().join(" ")).unwrap_or_default(),
            c["budget"]["bytes"], c["budget"]["chars"], c["budget"]["max_bytes"], c["budget"]["max_chars"], c["store"]["generation"], c["omitted_records_total"]);
        for i in c["items"].as_array().cloned().unwrap_or_default() {
            let ev = if i["label"] == "Decision" {
                let n = |k: &str| i["evidence"][k].as_array().map(|a| a.len()).unwrap_or(0);
                format!(
                    "{} / {} / {}",
                    n("active_supporting"),
                    n("active_contradicting"),
                    n("retracted")
                )
            } else {
                String::new()
            };
            md += &format!(
                "| {} | `{}` | {} | {} | {} |\n",
                i["channel"].as_str().unwrap_or(""),
                short(i["vkey"].as_str().unwrap_or("")).replace('|', "\\|"),
                i["lifecycle"].as_str().unwrap_or(""),
                i["why"]
                    .as_array()
                    .and_then(|w| w.first())
                    .and_then(|w| w.as_str())
                    .unwrap_or("")
                    .replace('|', "\\|"),
                ev
            );
        }
        for h in c["history"].as_array().cloned().unwrap_or_default() {
            md += &format!(
                "| history | `{}` | {} | {} | |\n",
                h["vkey"].as_str().unwrap_or("").replace('|', "\\|"),
                h["lifecycle"].as_str().unwrap_or(""),
                h["why"].as_str().unwrap_or("").replace('|', "\\|")
            );
        }
        if let Some(d) = c["items"]
            .as_array()
            .and_then(|a| a.iter().find(|i| i["label"] == "Decision"))
        {
            for r in d["evidence"]["retracted"]
                .as_array()
                .cloned()
                .unwrap_or_default()
            {
                md += &format!(
                    "\nRetracted association: `{}`: {}\n",
                    r["evidence"].as_str().unwrap_or(""),
                    r["reason"].as_str().unwrap_or("")
                );
            }
        }
    }
    md += "\n## Checks\n\n";
    for (n, ok) in checks {
        md += &format!("- [{}] {}\n", if *ok { "x" } else { " " }, n);
    }
    md
}
