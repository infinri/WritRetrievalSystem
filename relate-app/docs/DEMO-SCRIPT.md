# Demo video storyboard (about 110 seconds)

Everything shown is real output from the committed binary and store. The evidence view
(`evidence/demo/evidence-view.md`) and transcript can stand in for screenshots. Do not
describe the scripted CLI steps as an agent experiment. The agent segment is a real Claude
Code session calling the MCP server.

| Time | Screen | Narration (spoken) |
|---|---|---|
| 0:00–0:12 | Repo README, the one-line pitch | "Before an agent edits a file, it should know which decision governs it, what evidence backs it, and whether that changed. writ-relate keeps that chain in an embedded Relate graph." |
| 0:12–0:25 | `relate-app/demo-store/` in a file browser; `writ-relate verify --store demo-store` | "This is a Relate directory store you can open yourself: 127 public Writ guidance passages plus one real decision chain from this repo's history. Verify checks every digest and index membership." |
| 0:25–0:45 | `writ-relate context … --path src/writ_retrieval/reliable/grounded_cli.py "Which retrieval implementation should we ship?"` scrolled to the items | "Asking about the Python entry point: Relate's vector and full-text indexes, fused in one Cypher query, plus typed links. The current decision is revision 2, explained as the successor of the decision that affected this file. Its guidance has an exact revision binding, and its evidence is listed." |
| 0:45–1:00 | Same output, the `history` block | "The old decision is history, not guidance. Its evidence association from a biased review was retracted, and the reason is kept. Nothing claims to be verified or approved." |
| 1:00–1:20 | `writ-relate demo --out /tmp/d`, then `evidence-view.md` tables for context 1 and context 3 | "From an empty store: capture the decision and three pieces of evidence, retract one, try to reactivate it (refused), replay the capture (no-op), supersede with the owner's direction. Every step is a new process, so each change is visible after a restart. 15 of 15 checks pass." |
| 1:20–1:40 | `evidence/mcp-trace/summary.json`: tool call and answer | "A real Claude Code session using the read-only MCP server: two tools, no write or approval tools, network sockets denied. It found the current decision and refused to treat the old one as current." |
| 1:40–1:50 | `docs/OWNERSHIP.md` table | "Relate owns storage, indexes, scoped search, fusion and traversal. Rust keeps only inference, contracts and rendering. Measured costs and limits are in RESULTS.md." |

Do not claim: graph superiority, task success, faster or more accurate than alternatives
in general, or contest outcomes.
