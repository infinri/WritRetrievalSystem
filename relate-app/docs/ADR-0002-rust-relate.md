# ADR-0002: Ship a Rust-native, Relate-centered connected-memory application

**Status: implemented and merged in PR #11 (`00505e9`).** The merge records that the owner accepted the code change. It does not confirm any stored assertion, label or evidence record; those remain unverified unless a later owner-confirmation step says otherwise.

## Context

PR #10's ADR (`experiments/laptop_decision/ADR.md`) recommended the Python grounded-flat
profile for the local hackathon workflow. That recommendation was based on measurements
of Python profiles. On 2026-11-14 the owner set a product requirement instead: the
shipping application must be Python-free and centered on Relate. The earlier ADR stays as
historical evidence. It does not dictate this implementation.

This is an **owner-directed product requirement, not a measured performance win.**
Measurements below are reported as found, including regressions.

## Decision

1. Ship `writ-relate`, one Rust binary built on the public `relate` 1.0.1 crate (embedded,
   directory store). No Neo4j server, PostgreSQL, Writ kernel/broker or M4 code.
2. Relate owns records, relationships, receipts, transactions, the writer lease, native
   full-text and vector indexes, scope and lifecycle filtering inside search, RRF fusion in
   Cypher, and bounded typed traversal. Rust owns only extraction, inference, contracts,
   binding checks, evidence interpretation, explanations, budgeting/rendering and the
   read-only agent interface. See [OWNERSHIP.md](OWNERSHIP.md).
3. Embeddings use the same pinned MiniLM ONNX model through tract. The output matches the
   Python reference within cosine ≥ 0.99999 (observed worst case 0.9999995).
4. The agent surface is a read-only MCP server with two tools. Owner writes are separate CLI
   commands. Approval is not implemented as any command.
5. Selective enrichment: governing guidance, active evidence, conflict partners and
   current successors are added only for decisions that are ranked, required or linked to
   the requested artifact. Focus enrichment (decisions on the requested file) comes before
   other ranked candidates. Ordinary enrichment comes after them, so unconditional
   expansion cannot crowd out ranked targets.
6. Python sources and evidence stay in the repository as clearly labeled historical
   reference. They are not part of the build, runtime, demo or CI path for `relate-app/`.

## Consequences

- **Quality on opened regression tasks** (72; labels model-authored and unreviewed):
  - Natural-language delivery: Rust 40/48 vs Python grounded 35/48 and legacy 36/48.
  - Candidate rankings are identical to Python grounded-relate on all 54 natural-track
    tasks.
  - The gain comes from rendering. Leaner item metadata fits about 2.7 vs 1.5 records in the
    same 8,000-byte budget. It is not a retrieval improvement, and these are not unseen tasks.
- **Cost** (paired fresh processes, same laptop):
  - Rust CLI p50 is about 345 ms, vs about 917 ms for Python grounded-relate.
  - Peak RSS is about 198 MiB, vs 235 MiB.
  - Whole-CLI differences mix language, runtime imports and implementation. They are
    not a language-only claim.
- **Regressions and new costs:**
  - The demo and default budget rose to 16,000/12,000 so connected chains fit.
  - Per-scope full-text indexes add DDL and relabeling when scopes appear.
  - Vector search is an exact scan of the permitted partition.
  - The binary is 57 MB.
  - Importing 127 passages takes about 7 s, dominated by inference.
- Unsupported: multi-writer, remote server, power-loss/device-fault guarantees,
  authenticated tenancy, owner confirmation/approval, confidence thresholds, and
  non-Linux offline enforcement.

## Rollback

`relate-app/` is additive. Removing it, or not merging the PR, leaves every Python CLI,
fixture and evidence file unchanged. The demo store is reproducible from committed seeds.

## Reconsider when

- Relate gains full-text `WHERE` filtering (drop the per-scope labels) or ANN at larger
  corpus sizes (revisit exact scans).
- An independent review of the labels changes the regression conclusions.
- Multi-process writers or a shared server become requirements.
