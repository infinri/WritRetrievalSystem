# Contracts

## Time semantics (implemented in increment A)

- **Valid time:** `recorded_at` is the owner-declared time a record or association took
  effect. `valid_to` closes its applicability (half-open interval). `superseded_at` is set by
  a supersession, and `retracted_at` by a retraction.
- **Transaction time:** `ingested_at` is the wall-clock time the store accepted a write.
  It is stored for audit and is not used for filtering.
- **Ordering rules enforced on write:**
  - A supersession is not earlier than the revision it replaces.
  - An evidence association is not earlier than its decision or its evidence record.
  - A conflict is not earlier than either decision.
  - A retraction is not earlier than its association.
  - A decision is not earlier than the guidance it cites.
- **Request time:** `context` without `--as-of` is a current request (now), served from the
  current-only native partitions. `--as-of T` is a point-in-time request: every version in
  scope is searched, and a record is in effect if
  `recorded_at <= T < valid_to` and it was not superseded at or before T. Associations count
  only if created at or before T. Retractions count only if made at or before T. Items carry
  `lifecycle` (at T) and `stored_lifecycle` (now).
- Point-in-time search needs the all-version index (`fth_<scope>`), which this version
  creates. Stores created by PR #11 (including the committed baseline `demo-store/`) report
  point-in-time search as **unsupported** instead of returning a wrong answer.
- This is a reconstruction of recorded valid time. It is not a snapshot of what the store
  physically contained at T, so backdated captures appear in point-in-time views.

## Conflict bundles

Recorded `CONFLICTS_WITH` links form components. Components are traversed up to 4 hops
and 12 members, and every node must be visible and in effect. Each payload lists
`conflict_bundles` with `complete` and, if incomplete, the reason. A required record whose
component cannot be established completely is an error. Membership means pairwise recorded
conflicts; it does not assert that every pair contradicts.

## Existing record contracts (PR #11)

`writ-passage-fixture/1`, `writ-relate-capture/1` (decision, evidence, supersede, conflict),
`writ-relate-retract/1`, `writ-relate-context/1`, `writ-relate-inspect/1`,
`writ-relate-verify/1`. See `src/memory.rs` and `demo/seed/` for exact shapes.

## General knowledge contracts (specified in A; implementation in B)

One record family, `writ-relate-record/1`, with an explicit `kind`. Identity is
`scope|Kind|id@revision`. All kinds carry: `source` (URI, exact revision, path and lines, or
an explicit `null` meaning a local owner record), `content_digest`, `recorded_at`, optional
`valid_to`, `rationale` (text or `null` meaning unknown) and `judgment` (see below). Import
and capture never set verification or approval.

| Kind | Purpose | Distinguishes |
|---|---|---|
| `source` | A document or artifact at an exact revision | identity only, not truth |
| `claim` | A descriptive assertion found in a source | `judgment: descriptive` |
| `guidance` | Normative guidance (existing `Guidance`) | `judgment: normative`; imported guidance is not approved |
| `decision` | A historical choice (existing) | `judgment: decision` |
| `observation` | Something recorded as happening: tool result, log line, outcome, attempt | `observation_kind: tool_output, log, outcome_success, outcome_failure, outcome_unknown, attempt, exception` |
| `lesson` | A proposed generalization from cases | `judgment: proposed_explanation`; a model may propose it but cannot certify it |
| `question` | An open question that could change an answer | |
| `investigation` | A ledger entry: question, assumptions, actions, observations, counterexamples, conclusion, stop reason | |
| `goal` | An explicit goal with constraints | |
| `recommendation` | A proposed next action tied to goals, prerequisites, alternatives and change conditions | never execution permission |
