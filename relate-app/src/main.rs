use std::path::PathBuf;
use std::process::ExitCode;

use anyhow::{anyhow, bail, Result};
use serde_json::{json, Value as Json};

use writ_relate::context::{context, Fusion, Request, Requirements};
use writ_relate::db::Store;
use writ_relate::embed::Encoder;
use writ_relate::memory::{self, Capture, PassageFixture, Retraction};
use writ_relate::util::canonical;
use writ_relate::{mcp, offline};

const USAGE: &str = "writ-relate: connected decision/evidence context in embedded Relate

USAGE (all output is JSON on stdout; errors are JSON on stderr, exit code 2)
  writ-relate init     --store DIR [--model-dir DIR]
  writ-relate extract  --repo GIT_DIR --revision SHA40 --path DOC.md [--path ...] [--repository-url URL] [--out FILE]
  writ-relate import   --store DIR --fixture FILE --project NAME [--verify-git REPO]
  writ-relate capture  --store DIR --input FILE          (owner write: decision/evidence/supersede/conflict)
  writ-relate retract  --store DIR --input FILE          (owner write: retract an evidence association)
  writ-relate context  --store DIR --project NAME [--path ARTIFACT] [--require KEY[@REV]]...
                       [--request FILE] [--include-history] [--max-bytes N (16000)] [--max-chars N (12000)]
                       [--as-of UTC] [--fusion cypher|app] [--timings] QUERY
  writ-relate inspect  --store DIR KEY[@REV]
  writ-relate verify   --store DIR
  writ-relate mcp      --store DIR                        (read-only MCP server on stdio)
  writ-relate demo     --out DIR [--store DIR] [--fixture FILE] [--seed DIR]
  writ-relate eval     --tasks FILE --fixtures DIR --work DIR --out DIR [--reference DIR] [--repetitions N]
  writ-relate bench-cold --spec FILE --out DIR

  --model-dir defaults to $WRIT_MODEL_DIR or ./model (pinned MiniLM; see scripts/fetch-model.sh).
  context/inspect/verify/mcp open the store read-only and run with IPv4/IPv6 sockets denied.";

struct Args {
    cmd: String,
    flags: Vec<(String, String)>,
    switches: Vec<String>,
    positional: Vec<String>,
}

impl Args {
    fn parse() -> Result<Self> {
        let mut it = std::env::args().skip(1);
        let cmd = it
            .next()
            .ok_or_else(|| anyhow!("missing command\n\n{USAGE}"))?;
        let (mut flags, mut switches, mut positional) = (vec![], vec![], vec![]);
        let boolean = ["--include-history", "--timings", "--help"];
        while let Some(a) = it.next() {
            if boolean.contains(&a.as_str()) {
                switches.push(a);
            } else if let Some(name) = a.strip_prefix("--") {
                flags.push((
                    name.to_string(),
                    it.next().ok_or_else(|| anyhow!("--{name} needs a value"))?,
                ));
            } else {
                positional.push(a);
            }
        }
        Ok(Self {
            cmd,
            flags,
            switches,
            positional,
        })
    }
    fn get(&self, k: &str) -> Option<&str> {
        self.flags
            .iter()
            .rev()
            .find(|(n, _)| n == k)
            .map(|(_, v)| v.as_str())
    }
    fn all(&self, k: &str) -> Vec<String> {
        self.flags
            .iter()
            .filter(|(n, _)| n == k)
            .map(|(_, v)| v.clone())
            .collect()
    }
    fn need(&self, k: &str) -> Result<&str> {
        self.get(k).ok_or_else(|| anyhow!("--{k} is required"))
    }
    fn has(&self, k: &str) -> bool {
        self.switches.iter().any(|s| s == k)
    }
    fn model_dir(&self) -> PathBuf {
        self.get("model-dir")
            .map(PathBuf::from)
            .or_else(|| std::env::var("WRIT_MODEL_DIR").ok().map(PathBuf::from))
            .unwrap_or_else(|| PathBuf::from("model"))
    }
}

fn read_json<T: serde::de::DeserializeOwned>(path: &str) -> Result<T> {
    let text = std::fs::read_to_string(path).map_err(|e| anyhow!("read {path}: {e}"))?;
    serde_json::from_str(&text).map_err(|e| anyhow!("{path}: {e}"))
}

fn run() -> Result<Json> {
    let a = Args::parse()?;
    if a.cmd == "--help" || a.cmd == "help" || a.has("--help") {
        println!("{USAGE}");
        std::process::exit(0);
    }
    if matches!(a.cmd.as_str(), "context" | "inspect" | "verify" | "mcp") {
        // Read-only agent surfaces: deny IPv4/IPv6 before any engine or inference threads start.
        offline::deny_network()?;
    }
    match a.cmd.as_str() {
        "init" => {
            let enc = Encoder::load(&a.model_dir())?;
            let mut st = Store::open(a.need("store")?, false)?;
            memory::init(&mut st, &enc.identity)
        }
        "import" => {
            let fx: PassageFixture = read_json(a.need("fixture")?)?;
            let mut verified = Json::Null;
            if let Some(repo) = a.get("verify-git") {
                verified = json!({"git_files_verified": memory::verify_git(std::path::Path::new(repo), &fx)?});
            }
            let enc = Encoder::load(&a.model_dir())?;
            let mut st = Store::open(a.need("store")?, false)?;
            let mut r = memory::import_passages(&mut st, &enc, &fx, a.need("project")?)?;
            r["git"] = verified;
            Ok(r)
        }
        "capture" => {
            let c: Capture = read_json(a.need("input")?)?;
            let enc = Encoder::load(&a.model_dir())?;
            let mut st = Store::open(a.need("store")?, false)?;
            memory::capture(&mut st, &enc, &c)
        }
        "retract" => {
            let r: Retraction = read_json(a.need("input")?)?;
            let mut st = Store::open(a.need("store")?, false)?;
            memory::retract(&mut st, &r)
        }
        "context" => {
            let started = std::time::Instant::now();
            let query = a.positional.join(" ");
            if query.trim().is_empty() {
                bail!("context needs a QUERY");
            }
            let mut req = Request::new(&query, a.need("project")?);
            // Interactive default budget; the regression evaluation keeps 8000/6000.
            req.max_bytes = 16000;
            req.max_chars = 12000;
            req.path = a.get("path").map(String::from);
            req.required = a.all("require");
            req.requirements = match a.get("request") {
                Some(f) => read_json(f)?,
                None => Requirements::default(),
            };
            if a.has("--include-history") {
                req.requirements.include_history = true;
            }
            if let Some(v) = a.get("max-bytes") {
                req.max_bytes = v.parse()?;
            }
            if let Some(v) = a.get("max-chars") {
                req.max_chars = v.parse()?;
            }
            req.as_of = a.get("as-of").map(String::from);
            req.fusion = match a.get("fusion").unwrap_or("cypher") {
                "cypher" => Fusion::Cypher,
                "app" => Fusion::App,
                f => bail!("unknown fusion {f}"),
            };
            let load = std::time::Instant::now();
            let enc = Encoder::load(&a.model_dir())?;
            let mut st = Store::open(a.need("store")?, true)?;
            let startup_ms = load.elapsed().as_secs_f64() * 1e3;
            let (payload, t) = context(&mut st, &enc, &req)?;
            if a.has("--timings") {
                eprintln!(
                    "{}",
                    json!({"startup_ms": startup_ms, "embed_ms": t.embed_ms, "search_ms": t.search_ms, "enrich_ms": t.enrich_ms,
                    "render_ms": t.render_ms, "total_ms": started.elapsed().as_secs_f64() * 1e3})
                );
            }
            Ok(payload)
        }
        "inspect" => {
            let mut st = Store::open(a.need("store")?, true)?;
            memory::inspect(
                &mut st,
                a.positional
                    .first()
                    .ok_or_else(|| anyhow!("inspect needs KEY[@REV]"))?,
            )
        }
        "verify" => {
            let mut st = Store::open(a.need("store")?, true)?;
            let r = memory::verify(&mut st)?;
            if r["ok"] != true {
                println!("{}", canonical(&r));
                std::process::exit(1);
            }
            Ok(r)
        }
        "mcp" => {
            mcp::serve(PathBuf::from(a.need("store")?), a.model_dir())?;
            std::process::exit(0);
        }
        "demo" => writ_relate::demo::run(
            &PathBuf::from(a.need("out")?),
            a.get("store").map(PathBuf::from),
            a.get("fixture").map(PathBuf::from),
            a.get("seed").map(PathBuf::from),
            a.model_dir(),
        ),
        "extract" => {
            let paths = a.all("path");
            let v = writ_relate::extract::extract(
                std::path::Path::new(a.need("repo")?),
                a.need("revision")?,
                &paths,
                a.get("repository-url")
                    .unwrap_or("https://github.com/infinri/Writ"),
                a.get("license-marker").unwrap_or("MIT License"),
            )?;
            if let Some(out) = a.get("out") {
                std::fs::write(out, serde_json::to_string_pretty(&v)? + "\n")?;
                return Ok(
                    json!({"written": out, "passages": v["documents"].as_array().map(|d| d.len())}),
                );
            }
            Ok(v)
        }
        "eval" => writ_relate::eval::eval(&writ_relate::eval::EvalArgs {
            tasks: a.need("tasks")?.into(),
            fixtures: a.need("fixtures")?.into(),
            reference: a.get("reference").map(PathBuf::from),
            work: a.need("work")?.into(),
            out: a.need("out")?.into(),
            repetitions: a.get("repetitions").unwrap_or("3").parse()?,
            model_dir: a.model_dir(),
        }),
        "bench-cold" => writ_relate::eval::bench_cold(
            std::path::Path::new(a.need("spec")?),
            std::path::Path::new(a.need("out")?),
        ),
        "selftest-offline" => {
            // Hidden diagnostic used by the test suite: proves the deny is active in this process.
            let installed = offline::deny_network()?;
            let tcp = std::net::TcpStream::connect_timeout(
                &"127.0.0.1:9".parse()?,
                std::time::Duration::from_millis(200),
            );
            let udp = std::net::UdpSocket::bind("127.0.0.1:0");
            let unix = std::os::unix::net::UnixDatagram::unbound();
            Ok(
                json!({"installed": installed, "tcp_error": tcp.err().map(|e| e.to_string()), "udp_error": udp.err().map(|e| e.to_string()), "unix_socket_ok": unix.is_ok()}),
            )
        }
        other => bail!("unknown command {other}\n\n{USAGE}"),
    }
}

fn main() -> ExitCode {
    match run() {
        Ok(v) => {
            println!("{}", canonical(&v));
            ExitCode::SUCCESS
        }
        Err(e) => {
            eprintln!("{}", canonical(&json!({"error": format!("{e:#}")})));
            ExitCode::from(2)
        }
    }
}
