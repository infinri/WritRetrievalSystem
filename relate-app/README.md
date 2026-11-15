# writ-relate

Connected project memory for coding agents: decisions, the evidence for and against
them, the guidance they cite and the files they affect, stored and searched in an
embedded Relate graph. Written in Rust, with no Python at runtime.

## Use case

Before an agent edits a file, it should know which decision currently governs that file,
which exact source versions support or contradict the decision, and whether anything was
later corrected. Flat document search returns text. It does not say that a decision was
superseded, that an evidence association was retracted, or which revision a citation
pointed at.

writ-relate keeps that chain as typed records and relationships, and returns it as one
bounded, cited context packet:

- `Decision -[:GOVERNED_BY {exact revision, digest}]-> Guidance`
- `Evidence -[:SUPPORTS | CONTRADICTS {active | retracted}]-> Decision@revision`
- `Decision -[:AFFECTS]-> Artifact`, and `Decision@2 -[:SUPERSEDES]-> Decision@1`

Each delivered record says why it is there. Old decisions appear only as history.
Imported or captured text can never mark itself verified or approved.

## How it uses Relate

- **Mode: directory store** (`demo-store/`: WAL plus Parquet). It persists across
  processes and judges can open it read-only. The engine allows only one writer at a time.
  A directory store also lets the read-only CLI and MCP server open it beside a writer;
  this repository's tests verify that.
- **What Relate does:** canonical records and relationships, transactions, the
  single-writer lease, a native vector index searched with a scope filter applied before the
  limit, per-scope native full-text indexes, Reciprocal Rank Fusion in one Cypher statement,
  and typed, bounded traversal with visibility predicates.
- **What Rust does:** embedding inference (pinned MiniLM ONNX through tract), request
  contracts, exact revision/digest checks, evidence interpretation, the "why" text,
  complete-payload budgeting, and the read-only MCP surface.
  See [docs/OWNERSHIP.md](docs/OWNERSHIP.md).

Relate does not know our evidence policy. Retraction, supersession and replay safety are
our rules, enforced in our queries and checked by tests against the real engine.

## Setup and run (Linux x86_64; no Python)

Prerequisites: [rustup](https://rustup.rs) (it installs Rust 1.88.0 from
`rust-toolchain.toml`), git, curl and sha256sum.

```bash
git clone https://github.com/infinri/WritRetrievalSystem && cd WritRetrievalSystem/relate-app
scripts/fetch-model.sh model          # pinned all-MiniLM-L6-v2 ONNX + tokenizer, hash-checked (87 MB)
cargo build --release --locked        # about 2-3 minutes the first time

# First useful result: what governs this file, with its evidence and corrections.
./target/release/writ-relate context --store demo-store --project writ-retrieval-system \
  --path src/writ_retrieval/reliable/grounded_cli.py --include-history \
  "Which retrieval implementation should the local hackathon workflow ship, and what evidence supports it?"
```

The answer is JSON:

- **Current decision:** `…|Decision|local-workflow-backend@2` (ship the Rust app), with
  its governing guidance (exact binding) and its supporting evidence.
- **History:** `@1` (the Python profile) is marked superseded, with the reason. Its
  retracted evidence association is kept with the retraction reason.

Inspect any version exactly:

```bash
./target/release/writ-relate inspect --store demo-store "writ-retrieval-system|Decision|local-workflow-backend@1"
./target/release/writ-relate verify  --store demo-store     # digests, index membership, bindings
```

Rebuild the whole story from an empty store. This takes 13 steps, each in a separate process, so
the store is closed and reopened every time, and 13 checked expectations:

```bash
./target/release/writ-relate demo --out /tmp/writ-demo
# writes /tmp/writ-demo/transcript.json and /tmp/writ-demo/evidence-view.md
```

Run the tests (real Relate engine, real ONNX inference, no mocks):

```bash
WRIT_MODEL_DIR=$PWD/model cargo test --release --locked
```

## Use it from an agent (read-only MCP)

```bash
claude mcp add writ -- "$PWD/target/release/writ-relate" mcp --store "$PWD/demo-store" --model-dir "$PWD/model"
```

There are exactly two tools, `writ_context` and `writ_inspect`. There are no write,
approval or execution tools, and the server runs with IPv4/IPv6 sockets denied (seccomp).
A real Claude Code session calling this server is recorded in
[evidence/mcp-trace/](evidence/mcp-trace/).

## Owner workflow (writes)

| Command | What it does |
|---|---|
| `writ-relate extract --repo GIT --revision SHA --path doc.md …` | Read-only paragraph export from exact Git objects. Refuses non-MIT LICENSE by default. |
| `writ-relate import --store S --fixture F --project P [--verify-git GIT]` | Imports guidance with exact source URI, revision and digests. Idempotent. |
| `writ-relate capture --store S --input F` | Decision, evidence, supersede and conflict operations, in one transaction with a replay-safe request id. |
| `writ-relate retract --store S --input F` | Permanently retracts an evidence association. The record and its history stay. |

Input formats are in [demo/seed/](demo/seed/). Writes need the writer lease; agents
never get these commands.

## Where the data lives

- `demo-store/`: the persistent Relate directory store judges can inspect. It holds 127
  public Writ architecture passages (MIT) as `_shared` guidance, plus one real decision
  chain from this repository's own history.
- `demo/seed/`: the exact capture, retraction and supersession inputs. Quotes are exact
  lines of committed files at `0bdf503`, with URIs.
- `evidence/`: the demo transcript and evidence view, regression evaluation, cold-process
  benchmark and MCP trace. See [docs/RESULTS.md](docs/RESULTS.md).

## More

[Results and limitations](docs/RESULTS.md) · [Ownership](docs/OWNERSHIP.md) ·
[ADR-0002](docs/ADR-0002-rust-relate.md) · [Demo script](docs/DEMO-SCRIPT.md) ·
[Reuse map and disclosures](docs/REUSE-MAP.md) · [Contest audit](docs/CONTEST.md)

MIT licensed. The project builds on the author's earlier Writ work and was developed with
AI assistance; see [docs/REUSE-MAP.md](docs/REUSE-MAP.md) and the root
[NOTICE.md](../NOTICE.md).
