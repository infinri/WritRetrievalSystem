# Capability status map

Baseline: PR #11 merged as `00505e9`. Updated with each increment.

The "Product Scope and Agreement Register" and the "Self-Improvement Research note" referenced
by the 2026-11-14 handoff are **not in this repository and were not supplied in the session**.
This map is built from the capability list in that handoff (the current-to-target map and the
assignment text). When the register is added, reconcile it here. Nothing below silently drops
an agreed capability.

Legend: **existing** = at PR #11 · **partial** = usable subset · **now** = implemented in
the increment named · **deferred** = recorded gap with reason.

| Area | Capability | Status | Where / gap |
|---|---|---|---|
| Retrieval | Rust + native Relate search, per-scope full-text, scoped vector, Cypher RRF | existing | `context::search` |
| Retrieval | Temporal (valid-time) semantics across all channels; point-in-time `--as-of` | **now (A)** | `context::live`, all-version index `fth_<scope>`; older stores report unsupported |
| Retrieval | Bounded, complete-or-flagged conflict components; required incomplete bundle is an error | **now (A)** | `MAX_CONFLICT_HOPS`=4, `MAX_CONFLICT_MEMBERS`=12 |
| Integrity | Calendar validation; interval ordering of supersede/association/conflict/retraction | **now (A)** | `util::check_utc`, `memory::capture`/`retract` |
| Integrity | Transaction time (`ingested_at`) recorded beside valid time (`recorded_at`) | **now (A)** | stored, not used for filtering (documented) |
| Records | Decisions, evidence, supersede, conflict, retraction, guidance import, Git extraction | existing | `memory.rs`, `extract.rs` |
| Records | General contracts: source, claim, observation, memory/lesson, question, investigation, goal, recommendation | specified (A) → B | `docs/CONTRACTS.md` |
| Records | Ingestion of local Markdown/plain text/structured records, outcomes, tool results, logs | partial | Markdown at exact Git revisions exists; local files and outcomes planned for B |
| Records | Deletion/tombstone semantics | deferred → B | retraction/supersession exist; tombstone planned |
| Relationships | GOVERNED_BY, AFFECTS, SUPPORTS, CONTRADICTS, SUPERSEDES, CONFLICTS_WITH | existing | |
| Relationships | Writ V1 registry audit (DEPENDS_ON … REALIZES) with endpoint semantics or deferral reasons | → B | |
| Feedback | Durable feedback, named confidence policy, active-contribution recomputation | → B | Python path exists (`reliable/store.py`); absent in Rust |
| Review | Local-owner confirmation/proposal review outside agent tools | → B | |
| Patterns | Experience-backed recurring patterns with cases, counterexamples and support policy | → C | |
| Investigation | Bounded epistemic controller and ledger (question → assumptions → action → observation → counterexample → conclusion/next) | → C | |
| Planning | Goal/constraint-based recommendations with alternatives and conditions | → C | |
| Model boundary | Thin adapter for hypothesis/question proposals via existing Claude Code; replay contract | → C | live trials marked NOT RUN when unavailable |
| Receipts | Versioned run/context receipts (scope, generation, candidates, scores, paths, omissions, payload, timings) | partial | context returns candidates/timings; persisted receipts → D |
| Diagnosis | Cause localization (missing knowledge, retrieval miss, ordering, stale, budget loss, …) | → D | |
| Improvement | Allowlisted config proposals tested by bounded replay; rejected proposals kept | → D | |
| Recovery | Derived-index verify/rebuild with atomic publication; retraction invalidates dependents | partial | `verify`, fail-closed open exist; rebuild/invalidation → D |
| Interface | Read-only MCP (context, inspect) | existing | |
| Interface | Read-only investigation/impact/pattern/plan views | → C/D | |
| Contest | Required topic `relate`; video | owner action | `docs/CONTEST.md` |

Not in scope by instruction: Python in the shipping path, a language bake-off, a broker or
kernel, M4 authentication, multi-writer or distributed services, enterprise tenancy,
neural training, autonomous source-code repair.
