# Phase 3 versioned local contracts

These Python/Relate contracts implement selected [V2 principles](V2-SCOPE-MAP.md).
They are not Writ V2 acceptance records, authenticated permits or broker authority.
The original V1/Phase 2 commands and their historical evidence remain available.
Use the **reliable** APIs together on a supported Linux, single-process,
single-thread owner connection. Do not mix legacy/raw writers into an open
reliable session. Relate connections are thread-affine; an unsupported thread
returns an unavailable result, never a partial context.

## Identity, source and evidence

Public shapes are in [contracts/phase3](../../contracts/phase3); runtime checks in
`reliable/contracts.py` additionally enforce calendar times, digest equality,
source URI/revision/path binding, exact qualified identity and current revisions.
JSON ingestion rejects duplicate keys, nonfinite numbers and extra managed fields.

| Contract | Meaning |
| --- | --- |
| `writ-source/1` | URI, exact source revision, optional path, committed time and source line interval. Source identity does not authenticate its author. |
| Binding | `{ref:{project,label,id},revision,content_digest}`. Revision is a strict positive integer (booleans rejected); digest is canonical semantic properties, excluding lifecycle/derived confidence/approval metadata. |
| `writ-claim/1` | Immutable ID, project/topic/title/text, exact UTF-8 text digest, source, assertion kind, recorded time, optional validity interval/rationale. Only `model_assertion` and `repository_assertion` may be imported. |
| `writ-evidence/1` | Immutable material/digest/source and exact subject binding, recorded time and optional validity. Imported text cannot supply verification, owner judgment or tool-observed status. |
| `writ-relation/1` | Stored source/target bindings, recorded time, source references and unverified status. Traversal checks both endpoints and visibility at every hop. Invalid/obsolete bindings cannot become graph bridges. |
| `writ-feedback-observation/1` | Correlated positive/negative observation, exact Rule binding, exact Evidence binding, recorded time and provenance. The Evidence binds an immutable captured Outcome; its Decision must cite this rule wording. |
| `writ-context/1` | Complete model-facing JSON, snapshot revision/generation/source digest/as-of, separate item channels, citations, claim versions, lifecycle, verification, approval, omission count and budget policy. |
| `writ-generation-pointer/1` | Atomically published current/previous generation and source revision; complete immutable snapshot/vector files have checked manifests. |
| `writ-bound-review/1` | Stored owner-review snapshot of claim binding, both signal signs, active counts, actual evidence/outcomes and other doctrine statements. It cannot itself approve anything. |

All new envelope times are actual UTC whole seconds `YYYY-MM-DDTHH:MM:SSZ`.
Offsets, date-only strings, impossible dates and leap seconds are rejected.
Recorded times cannot be in the future at ingestion; source committed time
cannot follow observation time. Validity is half-open `[valid_from,valid_to)`;
`valid_from < valid_to` when both exist. Retroactive validity is allowed but
never makes a record available before it was recorded. The trusted local OS
clock is the boundary, not a protected clock or a rollback-resistant service.
Legacy records without validity remain explicitly unknown, not verified.

Git ingestion mechanically checks available immutable objects against the frozen
export. It assigns `tool_observed / git_object_identity_only` to commit-object
observations. Repository prose stays unverified, including prose claiming that
something was approved or tested. A provided public URL is provenance attribution;
there is no authenticated remote-source attestation. Commit rationale, application
outcome and human approval remain unknown. Source URI section fragments are
stable internal heading identities; use the stored path/revision/line interval
for exact source inspection rather than assuming those hashes are GitHub anchors.

## Updates, history and retraction

Immutable Claim/Evidence IDs reject changed meaning. Claim supersession creates
a new claim, retains the old source text as historical, and binds the operation
to the exact old revision/digest. A Claim tombstone hides it from fresh context;
old snapshots remain explicitly inspectable. Captured Decision/Commit/FileChange/
Outcome remain immutable; Memory retains Phase 2's optimistic revision update.
Lifecycle operations archive old payloads. Retraction preserves the Evidence's
material, increments its revision, records a reason/time and permanent request
receipt, and prevents active contributions. Replaying that request or a prior
import/feedback batch cannot undo it. New evidence requires a new ID; restoring
an old observation is not an implicit consequence of import replay.

Source document replacement is **document-version history**, not authenticated
policy supersession. D-number headings keep their identity when their wording
changes. Arbitrary renamed/removed sections are not automatically adjudicated;
source validity and explicit local corrections remain necessary. Superseded
claims are searchable as history and are marked `current_guidance=false`.

Contradictions are explicit, revision-bound **potential conflicts**. The renderer
carries both texts in one indivisible bundle, with unresolved status and source
references. Optional bundles may be wholly omitted with diagnostics. Requiring
either endpoint requires the complete conflict bundle to fit or produces a budget
error. This is not semantic contradiction detection or truth adjudication. The
real-history status tension is an unreviewed benchmark annotation and may concern
different scopes of implementation; only synthetic tests assert a true conflict.

## Active confidence and human approval

Phase 3's stricter path retains the upstream numerical function but has an explicit
admission policy `active-bound-evidence/1`: count one observation per Rule meaning /
Evidence identity only when Rule and Evidence bindings remain current, the rule
and linked Outcome/Decision remain live, evidence is within its validity interval,
and the local owner confirmed that bound evidence. Imports alone contribute zero.
Git object identity verification is never verification of an application's outcome.
Duplicate batches and new batch IDs for the same fact do not increase counts.
Retraction, claim revision, expiry, deleted Decision/Outcome or supersession makes
the contribution inactive. Old observations/receipts survive. Reads recompute
active counts as well as writes; expiry needs no new write to change context.
Legacy static/Phase 2 counters are retained separately when a Rule first enters
this policy and are not silently treated as verified evidence for this policy.

For `n = positive + negative < 50`, confidence uses the static tier (speculative
0.30). For `n >= 50` and positive ratio `>= 0.75`, confidence is that ratio.
At/above 50 with a lower ratio it is flagged for review and keeps its static
confidence. Thus 40 positive / 10 negative gives 0.80; withdrawing one positive
leaves 49 observations and returns speculative confidence to 0.30. Tests verify
these values and absolute served metadata. The new flat/RRF history policy
**reports** confidence separately; it does not add this value to RRF. Original
V1/Phase 2 ranking retains its existing confidence score component.

Statistical crossing can mark a proposal pending; `review_eligible` is recomputed
from active evidence. Neither crossing nor owner confirmation of an outcome grants
rule approval. Preparing a review snapshots current evidence; applying it requires
the local-owner terminal to inspect the stored artifact and type its digest.
Changed evidence/wording/eligibility makes it stale. Approval is a distinct
`TrustEvent` and authority change. Retraction does not erase historical approval
or silently revoke a prior human judgment; its active confidence evidence changes.

The read-only agent module has no mutation/confirmation/promotion commands.
This is a local-owner tooling boundary: an agent with unrestricted same-account
shell, database or terminal control can defeat it. There are no tenant identities,
capability permits, HMAC attestations or protected administrator credentials here.
Analysis outcomes remain correlated reports, not causal proof about any rule.

## Complete generations and budgets

One synchronous Relate read transaction captures every node and edge. Guidance,
decision recall, history, graph paths, cited versions and rendering derive from
that copy; no later live channel read is stitched into it. Exact vectors are built
in batches of at most 16 over at most 5,000 units. Policy/model/text/snapshot
identities bind the generation. Immutable files and their digests are checked
before atomic pointer publication. Source revision and temporal classification
are checked again before publication. A failed build/render/refresh returns no
fresh payload and retains the previous complete generation. A commit exception
poisons the writer handle: close/reopen and inspect durable state rather than
assuming rollback proved the outcome. Publication/I/O failures report unavailable;
a crash after atomic rename may have completed a new pointer, so inspect `CURRENT`.

`CURRENT.json` retains `previous`; old snapshots/vectors are not overwritten or
automatically garbage-collected. `inspect --generation` verifies and reads that
immutable snapshot. Repair a corrupt active cache by closing the process and
moving the corrupt generation directory aside, then rebuild from the current
store. Never restore a previous snapshot as fresh after deletion/retraction.
No distributed writers, online compaction or automated historical serving exists.

Only **payload** (or default CLI stdout) goes to a model. `--inspect` is an owner
wrapper; its diagnostics are outside the payload budget. Defaults are 8,000
UTF-8 bytes **and** 6,000 Unicode codepoints, covering the entire JSON including
metadata, trust marker, guidance, recall, graph paths, citations and truncation
counts. Optional `--estimated-tokens` enforces `ceil(chars/4)` as a heuristic;
no exact target tokenizer is pinned. The MiniLM embedding tokenizer is not a
model prompt tokenizer. Required header/content failures return `BudgetError`
and exit 2, not an incomplete required bundle.

Ranking uses at most 1,600 text characters and MiniLM's first 128 tokens per unit;
display uses a 640-character head with exact omitted-character count and full
content/source digests. Full text is available via version-bound inspection.
Whole-card omissions list exact IDs/reasons in diagnostics; the model sees the
omission count. Selection has explicit score/identity ties and bounded traversal
(two hops / 64 visits, meaningful typed edges only). Mandatory-rule delivery is
required separately and excluded from ranked-rule candidates. Historical and
retracted records can be returned as explicitly marked history, never current
guidance or active support. Legacy rule retrieval remains in the original CLI.
