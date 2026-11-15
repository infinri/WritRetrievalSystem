# Evidence index

| Path | What it is | Produced by |
|---|---|---|
| `demo/transcript.json`, `demo/evidence-view.md` | 13-step end-to-end run from an empty store, each step a separate process; 15 checked expectations | `writ-relate demo` |
| `eval/` | Final regression run on the 72 opened tasks, both fusion owners, compared per task with committed Python results | `writ-relate eval` |
| `eval-initial-per-list-k6/` | Preserved pre-correction run (per-list cut to k before fusion); see `docs/RESULTS.md` | `writ-relate eval` (earlier policy) |
| `bench-cold-spec.json`, `bench-cold/` | Paired fresh-process timing of the Rust CLI and the Python reference CLIs | `writ-relate bench-cold` |
| `mcp-trace/` | One real Claude Code session using the read-only MCP server (sanitized) | `claude -p` with `--mcp-config` (see its README) |

The Python reference CLIs appear only as measured comparison commands in
`bench-cold-spec.json`. They are not needed to build, run, test or demonstrate the Rust
application.
