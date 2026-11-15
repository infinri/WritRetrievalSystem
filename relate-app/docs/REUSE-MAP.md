# Source-to-runtime reuse map and disclosures

## What runs (shipping runtime and judge workflow)

Only `relate-app/` (Rust) plus `scripts/fetch-model.sh` (POSIX shell, curl, sha256sum).
No Python is built, imported, spawned or required. CI checks that the binary does not link
libpython.

| Runtime piece | Origin | Reuse |
|---|---|---|
| `src/extract.rs` | Port of `src/writ_retrieval/reliable/passages.py::export_passages` (this repo, Python) | Same paragraph rules and identity formula; byte-identical output on both committed fixtures (test) |
| `src/memory.rs` contracts (bindings, receipts, retraction, supersession, no trust from imports) | Ideas from Phase 3 contracts (`docs/phase3/CONTRACTS.md`) and Writ V2 principles | Re-implemented in Rust over Relate records; Python code not copied |
| `src/context.rs` ranking policy (k=6, RRF 60, cosine 0.30, full-partition lists, 1,600-character heads) | `experiments/reliable_memory/protocol/settings.json` and `grounded.py` | Same policy; identical candidate rankings on 54/54 natural-track regression tasks |
| `src/context.rs` budgeting and rendering | New | Complete records; indivisible conflict bundles; hard byte and codepoint limits (similar to Phase 3 `budget.py`, new format `writ-relate-context/1`) |
| `src/embed.rs` | Same model and preparation as `retrieval/embeddings.py` | New Rust implementation (tract + tokenizers) |
| `src/offline.rs` | Replaces `reliable/offline.py::deny_network` | seccomp socket filter instead of Python socket patching |
| `src/mcp.rs` | New | Read-only, two tools |
| Data: `experiments/reliable_memory/fixtures/history-*.json` | Public Writ architecture docs (MIT, Lucio Saldivar / JolliAI) at exact revisions | Imported unchanged as `_shared` guidance |
| Data: `demo/seed/*.json` | Exact quotes of this repo's committed files at `0bdf503`, plus one clearly labeled local owner report | New |

Historical Python sources (`src/`, `scripts/`, `experiments/`) and their evidence remain
as reference material. They are not part of the Rust build or the judge workflow.

## Third-party components (all pinned in `Cargo.lock`)

| Component | License | Notes |
|---|---|---|
| `relate` 1.0.1 (Neo4j Labs; github.com/relatedb/relate, tag v1.0.1 / `ef436ce`) | Apache-2.0 | Embedded engine; not modified or vendored |
| `tract-onnx` 0.21.13 (Sonos) | MIT / Apache-2.0 | Pure-Rust ONNX inference |
| `tokenizers` 0.21.4 (Hugging Face), `fancy-regex` feature, no C regex | Apache-2.0 | |
| `seccompiler` 0.5.0 (rust-vmm) | Apache-2.0 / BSD-3-Clause | Linux offline boundary |
| serde, serde_json, sha2, hex, anyhow, flate2 (rust backend), libc | MIT / Apache-2.0 | |
| Model: sentence-transformers/all-MiniLM-L6-v2 @ `1110a243` | Apache-2.0 | Downloaded and hash-checked by `fetch-model.sh`; not committed |

The dependency tree has no C/C++ build dependencies (285 crates, all Rust). The binary
links only libc, libm and libgcc_s.

## Earlier work reused (contest rule: disclose)

The repository was started on 2026-11-13. Reused and disclosed:

- Writ V1 (`ebdafe5`) and the public Writ V2 architecture docs. Author's own MIT work;
  see root `NOTICE.md`.
- This repository's Python Phase 1–3 and experiments, as policy reference, fixtures and
  evidence.

## AI assistance (contest rule: describe significant AI use)

- **This Rust application, its tests, docs and evaluation:** written with Claude Code
  (Claude Opus 5.5) under owner direction. The owner remains responsible for review.
- **Earlier Python milestones:** OpenAI Codex assisted code, provisional labels and analysis,
  as disclosed in those milestones.
- **Model calls in evidence:** a few live Claude Code sessions (Claude Sonnet 5.5) were
  used for the MCP demonstration, through the owner's existing login. Earlier QA trials
  are documented in `experiments/laptop_decision/`.
- **Labels:** the regression labels are model-authored and not independently
  human-reviewed.
