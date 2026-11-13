# Phase 3 contract and frozen evaluation plan

Starting point: merged Phase 2 `cc8e32d1064805c8eb517e5d97cf37d4e49fe94b`.
Recovery found a clean local `codex/context-reliability-phase3` branch at
`26694a3`, with no uncommitted files, extra worktrees or remote Phase 3 PR.
Fast-forwarded to merged main. Phase 1/2 fixtures and evidence remain immutable.

## V2 applicability map (before implementation)

Reference: Writ `82971fdbfd0a8650db247e832cf8df89948e2cd6`,
`docs/architecture/{retrieval-and-memory,data-model}.md`, D-035/D-036 in
`docs/implementation/DECISION-LOG.md`. Remote checked 2026-11-13; no subsequent
decisions at that head. These are design inputs, not imported broker guarantees.

| Principle | Initial state | Phase 3 scope |
| --- | --- | --- |
| Context never grants execution permission | Already implemented | Preserve local-owner boundary |
| Qualified identity, typed bounded graph expansion, per-node visibility | Already implemented | Reuse; extend to history search |
| Immutable cited claim, revision invalidation, durable replay receipts | Already implemented | Reuse; add irreversible evidence withdrawal |
| One coherent guidance/recall/graph/render generation | Partial | Stage refresh inside a local read transaction; publish only complete output; explicit unavailable/stale result on failure |
| Source digest, observation classes, temporal validity | New | Closed evidence envelopes; imports unverified; owner confirmations through interactive local terminal |
| Retraction with preserved history | New | Mark observations inactive; recompute matching current-claim contributions; preserve receipts |
| One model-facing context ceiling | New | Exact UTF-8 byte ceiling includes citations/fences; deterministic whole-card omissions; no exact token claim |
| Frozen real-history evaluation with fair flat baselines | New | Public pinned Git records and explicit documentary reasoning; same visibility, records, renderer and byte budget |
| Atomic generation publication/rollback | Partial | Local immutable pipeline metadata copies; old generation retained internally on failure, never silently served as fresh |
| Authenticated tenants, broker permits, HMAC acceptance, trusted clock, enterprise | Deferred | Remain in Writ V2; no authority transferred into this application |

## Frozen before implementation

`examples/phase3/queries.json` freezes questions and provisional labels before
Phase 3 search code. Labels are AI-authored, **PENDING HUMAN REVIEW**. They measure
source recovery, not correct agent behavior or improved outcomes. Real history
sources are MIT-licensed Writ Retrieval System at `26694a3` and Writ at the V2
reference above. Read Git objects at exact revisions, never execute hooks, run
source scripts or invent rationale, approvals or outcomes. Documentary claims
are attributed assertions; Git object hashing establishes byte identity only.

Compare flat BM25, flat vector, flat reciprocal-rank fusion and connected RRF.
All arms receive exactly the same visible live records, record text, source
identities and 8,000-byte model-context limit. RRF k=60; connected expansion two
hops with one seed, max six neighbors and 64 visits; no tuning on these labels.
Report every query, source hit, abstention, omitted cards, timings and regressions.
Explicit negative questions target unknown approvals/outcomes and absent history;
no source match is not a verified answer. Preserve complete returned contexts.
