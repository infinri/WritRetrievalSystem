# Connected memory and feedback

Phase 2 builds on the reviewed extraction baseline. All commands below run from
the repository root. Fixtures and outcomes under `examples/phase2` are synthetic.

## Run the complete workflow

```bash
python -m pip install -c requirements-validated.txt -e '.[dev]'
python scripts/prepare_model.py --output data/model
python -m writ_retrieval.evaluation.scenario --store data/my-phase2-run --output data/my-phase2-evidence
writ-retrieval connected 'SQL parameters src/payments.py' --store data/my-phase2-run --model-dir data/model --project payments --project-root .
writ-retrieval inspect --store data/my-phase2-run --project payments
writ-retrieval audit --store data/my-phase2-run
```

The scenario refuses an existing store. It retrieves guidance, captures a decision,
file change, commit, memory and outcomes through the supported CLI, closes and
reopens stores, recalls history, applies replay-safe feedback, and inspects fresh
context. It compares lexical, vector, hybrid without graph, hybrid with graph and
connected context on the same six prompts before capture, after restart, and after
feedback/restart. Controls cover unrelated, contradictory, superseded, deleted
and foreign-project content. The scenario writes the review artifact but does
not grant approval.

## Supported local APIs and CLI

```bash
writ-retrieval propose examples/phase2/proposal.json --store data/manual --create
writ-retrieval propose examples/phase2/async-proposal.json --store data/manual
writ-retrieval capture examples/phase2/records.json --store data/manual
writ-retrieval capture examples/phase2/records.json --store data/manual
writ-retrieval record-lifecycle examples/phase2/supersede.json --store data/manual
writ-retrieval record-lifecycle examples/phase2/delete.json --store data/manual
writ-retrieval recall src/payments.py --store data/manual --project payments --project-root . --full
```

`capture` accepts a JSON list of `{label, data, expected_revision?}`. Supported
labels are Decision, FileChange, Commit, Memory and Outcome. Every record requires
an explicit project, timestamp and nonempty source-reference list; no project is
inferred from a path. See the example manifests for all fields. Governing rule
references use `{project, label: "Rule", id}`; legacy governing IDs resolve only
against the `writ` doctrine project. Explicit references disambiguate duplicate
IDs. Referenced records must be live and in the same project or `_shared`;
Rule citations may name shared doctrine. All imported records and links commit
or roll back together.

Python APIs live in `memory.store.LocalStore`, `memory.service.ConnectedSession`
and `memory.review`. Use `LocalStore(path, create=True)` then `capture(records)`;
`ConnectedSession(store, encoder)` supports `await context(...)` and
`apply_feedback(...)`. Transactions use real Relate commit/rollback. One local
writer owns a store; concurrent host-service operation is not implemented.

| Item | Update and lifecycle semantics |
| --- | --- |
| Decisions, changes, commits, outcomes | Immutable facts. Identical imports are no-ops. A changed payload under the same identity is rejected; capture a new fact and explicitly supersede the old one. |
| Memory | Identical replay is a no-op. An update requires the current `expected_revision`; it replaces ABOUT links and archives the preceding revision. |
| Delete | Soft tombstone with expected revision. Excluded from active recall/enrichment, retained for audit. Reimport never resurrects it. |
| Supersede | Replacement must already be live, same project and type. A `replacement -SUPERSEDES-> old` edge and tombstone preserve history. |
| Rule proposal revision | `revise-proposal` accepts `{ref, fields, expected_claim_hash}`. Provisional rules only. Changed normalized statement **or trigger** resets both observation counts and returns provenance to `proposed`. Old observations remain bound to the old hash. Case/whitespace-only changes preserve the claim. |
| Existing feedback after record deletion | Observations remain historical correlated evidence; tombstoning context does not silently subtract counts. Source status is included in a promotion review. There is no evidence-retraction API in this phase. |

`RecordRevision` nodes preserve prior payloads and lifecycle actions. They are
audit records, excluded from recall, rule candidates and rendered enrichment.
Captured decisions freeze the cited rule's identity, hash, statement, trigger
and provenance. Full recall distinguishes captured text from the current rule's
text, so revising a claim does not rewrite history.

## Identity, visibility and rendering

`graph.identity.Key` identifies a node by **project + label + local ID**. Its
unambiguous encoded token is independent of the doctrine candidate registry.
Graph snapshots reject duplicate physical nodes with the same qualified identity;
unknown/multilabel nodes are omitted and counted by the audit. Duplicate bare
IDs across projects or types remain distinct. Ranked index IDs stay unchanged
when unambiguous, preserving the corpus baseline; collisions use qualified IDs.
Chunk IDs and PRECEDES links are also qualified and document/project checked.

Doctrine adjacency retains the original category exclusion and visibility rules.
Record edges do **not** become ranking-proximity bridges. The connected channel
follows only meaningful typed contracts: Decision→Rule GOVERNED_BY,
FileChange→Decision MOTIVATED_BY, Commit→FileChange INCLUDES,
Commit→Decision REALIZES, Memory→Rule/Decision ABOUT and Outcome→Decision
EVALUATES. Links may be followed in either direction for context. Traversal stops
at invisible/tombstoned nodes, including foreign bridges, and avoids cycles.
Defaults are one guidance seed, two hops, six records and 64 visited nodes.
An unrelated relationship type cannot authorize expansion.

`connected` returns separate `guidance`, `recall`, `connected`, and mandatory-rule
selection fields, plus sanitized fenced text. Guidance retains its original token
budget; recall uses its separate 500-token budget; record enrichment has its own
node/hop limits and clipped display fields. There is no unified total prompt
budget or agent hook-delivery/enforcement service. Mandatory/always-on IDs are a
separate selection and never count as ranked hits.

## Durable feedback and served metadata

The scenario writes a complete supported feedback manifest. Replay it safely:

```bash
writ-retrieval feedback data/my-phase2-evidence/feedback.json --store data/my-phase2-run
```

A batch is `{project, batch_id, signals}`. Each signal requires `rule_ref`, the
captured `claim_hash`, `outcome_ref`, `positive|negative` signal and a `source_ref`
listed by that outcome. The project's live outcome must cite a live decision
that captured this rule claim. Unknown outcomes and inconsistent pass/negative
or fail/positive signals are rejected; mixed outcomes may support either sign.
Signals are **correlated outcome observations**, not proof a rule caused success.
No automatic causal attribution or domain heuristic is applied.

The batch receipt, observations, counters and review-candidate crossing share one
transaction. Reusing a batch ID with a different ordered payload is rejected.
Exact replay returns the receipt and **current** absolute metadata. The same
rule/claim/outcome is deduplicated even under another batch ID; contradicting an
existing observation is rejected. Receipts are retained without a replay expiry.

The upstream confidence computation is unchanged:

- Fewer than 50 observations: use the rule's static confidence weight.
- At least 50 and positive fraction at least 0.75: use that empirical fraction.
- At least 50 with a lower fraction: use the static weight and flag the evidence.
- A proposed rule crossing the passing threshold becomes `graduation_pending`,
  while authority remains `ai-provisional`. This transition is one-way; later
  negative evidence is visible to the reviewer and does not silently approve it.

A running session copies post-commit absolute counts into served metadata. Its
next refresh synchronizes metadata/edges/routes without rebuilding unchanged
text indexes. Text or candidate-set changes trigger cache validation/rebuild.
Restart rebuilds metadata from the persistent graph. Replaying old feedback after
a wording revision cannot restore the previous claim's counts.

## Review and promotion

```bash
writ-retrieval review-prepare examples/phase2/rule-ref.json --store data/my-phase2-run > data/my-review.json
writ-retrieval review-apply data/my-review.json --store data/my-phase2-run --action approve
```

The second command is for the local owner in an interactive terminal. The owner
reads the stored artifact and types `approve <full review digest>`; there is no
`--yes` option. `--action reject` uses the same confirmation boundary. The
artifact contains wording/examples, source references, both signal signs and
outcomes, current confidence, nearest lexical rules and explicit conflicts.
Changed evidence or wording invalidates the snapshot. Approval requires examples
and rejects an exact normalized duplicate statement. It stamps `graduated` /
`ai-promoted` and a TrustEvent containing the claim/review digest and OS identity.

This adapts Writ's distinction between statistical crossing and human promotion,
but does not port its hook/token approval gate, structural linter, source export
or authenticated identity service. It is a **local-owner terminal assertion**.
A process controlling that OS account, terminal or database can forge it. The
scenario never simulates owner approval; isolated automated tests use a PTY only
to verify confirmation and stale-snapshot behavior on disposable synthetic data.

## Reproduce corpus evidence

```bash
python -m writ_retrieval.evaluation.full_corpus --store data/fresh-eval --output data/fresh-evidence --model-dir data/model
python -m writ_retrieval.evaluation.compare evidence/baseline data/fresh-evidence --output data/my-comparison.json
python -m pytest -q
```

CI builds hnswlib from source with `HNSWLIB_NO_NATIVE=1` and bypasses cached
wheels, avoiding reuse of CPU-specific `-march=native` binaries on another
runner. See the [upstream build flag](https://github.com/nmslib/hnswlib/blob/v0.8.0/setup.py).

Use a new store for every corpus evaluation. The harness imports the verified
original dump, checks the model's actual bytes, and records settings, hashes,
per-query identity/score/similarity/relationship outputs, eligibility, abstention,
uncached and cached timings, and process peak RSS. Timing includes the common
pipeline harness, not optimized single-index implementations. See
[FINDINGS.md](FINDINGS.md), the frozen [baseline](../evidence/baseline/summary.json),
[Phase 2 results](../evidence/phase2/summary.json), [paired comparison](../evidence/comparison.json)
and [scenario](../evidence/scenario/summary.json).
