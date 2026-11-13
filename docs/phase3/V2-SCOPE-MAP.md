# Selected V2 principles and Phase 3 scope

Design input: `infinri/Writ` `v2/architecture-rebuild` at
`82971fdbfd0a8650db247e832cf8df89948e2cd6`, specifically
`docs/architecture/retrieval-and-memory.md`, `data-model.md`, D-035/D-036 in
`docs/implementation/DECISION-LOG.md` and the immutable-binding/freshness section
of `M3-ACCEPTANCE-CONTRACTS.md`. These are design references, not claims that
this Python/Relate application implements the V2 broker or its target schema.

| Principle | Phase 2 status | Phase 3 work | Deferred boundary/reason |
| --- | --- | --- | --- |
| Retrieved text is data, not authority | Implemented: separate record context; no policy permits | Preserve separate integrity, verification and approval fields; imports cannot self-verify | Broker/capability enforcement and enterprise identities are outside local retrieval scope |
| Typed/project-qualified identity; per-hop visibility | Implemented, including duplicate IDs and scoped chunks | Extend to Evidence/Claim and revision-bound relations; reuse visibility predicate | Tenant/principal authentication and explicitly published shared doctrine require a different deployment boundary; legacy doctrine remains type-shared |
| Immutable evidence binding (D-036) | Partial: decision captures rule wording/hash, records mostly immutable | Bind evidence to exact subject revision and content digest; validate at use time; retain old versions | No HMAC acceptance authority, runner attestation service or Rust kernel port; digest integrity alone does not authenticate a source |
| Freshness and semantic time (D-035/D-036) | Partial: timestamps are strings, lifecycle hides stale records | Versioned contracts; actual UTC calendar validation; validity windows; future/obsolete bindings rejected or explicitly excluded | Trusted OS clock is the local boundary, not V2's protected clock/rollback-resistant time service |
| One coherent context generation | Partial: separate reads and in-place metadata refresh | Capture one read transaction, build replacement snapshots/indexes, atomic pointer publication; retain prior generation; failures refuse fresh context | Distributed/concurrent-writer snapshots and background serving infrastructure deferred; one supported writer |
| Replay never changes immutable meaning (D-035/D-036) | Implemented receipts and cross-batch observation dedup; wording invalidates counts | Evidence retraction; recompute active contributions; old receipt replay cannot reactivate retracted/obsolete evidence | External-effect recovery/uncertain dispatch are unrelated to this retrieval-only application |
| Contradictions retained and surfaced | Partial: raw contradictory text can be recalled | Explicit bound contradiction relations and contested markers; distinguish current document revision from historical text | Automatic semantic truth adjudication and independent human label review are deferred |
| Deterministic total budget | Partial: per-channel budgets only | One UTF-8 byte and character cap over the entire model-facing JSON payload; deterministic omissions; explicit required-content error | Exact generative-model token counts require a separately pinned target tokenizer; embedding tokenizer is not a prompt tokenizer |
| Outcomes distinguish evidence classes | Partial: all outcomes treated as correlated input | Unverified/model/repository assertion versus mechanically observed tool facts versus local-owner confirmation; retraction history | Production evidence provenance authentication and causal attribution deferred |
| Relevance and usefulness evaluation | Synthetic workflow and fixed V1 gold results implemented | Frozen time-separated public Writ history; all arms get identical documents, records, visibility and budget; publish losses/unknown labels | Live-agent effectiveness and real task success are not inferred from scripted retrieval; no live agent is required |

The map is published before retrieval changes. The implementation/test coverage
and remaining gaps will be recorded in PHASE3.md and the findings report.
