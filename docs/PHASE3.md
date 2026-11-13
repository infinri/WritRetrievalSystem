# Phase 3: reliable local context and real-history evidence

PR #2 was merged at `cc8e32d1064805c8eb517e5d97cf37d4e49fe94b` when this
implementation resumed. This separate branch builds on that merged baseline.
The original gold corpus, Phase 1/2 results and original ranking paths remain.

Read the [V2 scope map](phase3/V2-SCOPE-MAP.md), [versioned contracts and trust
boundary](phase3/CONTRACTS.md), and [measured findings](phase3/FINDINGS.md).
This is Python/Relate retrieval and memory behavior, not a Rust kernel, broker,
authenticated permission system or completed Writ V2 data model.

## Reproduce the evidence

From this checkout, after the README installation steps:

```bash
python scripts/prepare_model.py --output data/model
git clone https://github.com/infinri/Writ ../Writ-public
git -C ../Writ-public fetch origin v2/architecture-rebuild
python -m pytest -q
python -m unittest discover -s tests -v
python -m writ_retrieval.evaluation.reliable_history \
  --repo ../Writ-public --model-dir data/model \
  --work-dir data/new-history-eval --output data/new-history-results
python -m writ_retrieval.evaluation.reliable_demo \
  --repo ../Writ-public --model-dir data/model \
  --work-dir data/new-agent-demo --output data/new-agent-results
```

Use new work/output paths each time. Git ingestion reads exact object revisions;
it does not check out files, fetch, run hooks or execute repository code. The
clone/fetch above is an explicit preparation step, separate from ingestion.
Model hashes and all frozen input hashes are checked. Runtime inference disables
ONNX telemetry and uses the local pinned weights/tokenizer.

The primary evaluation uses `examples/phase3/evaluation.json`: **13 prompts**, with
8 source-target prompts (10 exact source-version targets), 4 expected abstentions
and one unknown-verification control. History ends at `154be77` (November 13,
01:47:57 UTC); task motivation comes from `6be251c`/`82971fd` later that day.
Holdout documents never enter that store. Query wording, source proxies and
settings were frozen at local `87ed6d2` before implementing this retrieval path;
its exact tree is published as the freeze checkpoint in the PR. Labels are
model-authored and **unreviewed**, not human relevance or outcome gold. The older
`queries.json` is retained because the freeze manifest references it; it is an
exploratory source-recovery plan and contributes no primary denominators.

Flat lexical, exact vector and RRF hybrid receive the same underlying units,
scope and output budget as connected RRF. Conflict closure and lifecycle labels
are common output contracts. Connected alone adds meaningful, bound adjacency
from the top hybrid seed, with two hops/64 visits. Records remain separate from
legacy doctrine candidates; the experimental all-unit index reports explicit
`guidance`, `decision_recall` and `memory` channels. New history RRF is measured
separately from original V1 weighted ranking. It can crowd guidance out unless
required; mandatory rules are always a separate required delivery channel.

This is a small source-recovery experiment with truncated text and incomplete,
unreviewed judgments. It does not establish successful task completion, causal
outcomes or a graph advantage. Every returned payload, omission and timing is
published, including misses and negative-control failures.

## Capture public history and retrieve

```bash
python -m writ_retrieval.reliable.cli --store data/my-history history-import \
  examples/phase3/demo-history.json --verify-repo ../Writ-public --create
python -m writ_retrieval.reliable.agent --store data/my-history context \
  'Implement approver provenance and immutable grant binding. Inspect D-035.' \
  --project writ-history --model-dir data/model --cache-dir data/my-generations
```

The default stdout is the complete budgeted JSON payload. Add `--inspect` for an
owner wrapper with candidate IDs, omission reasons, bytes/chars and index path;
deliver **only its payload** to a model. Use `--arm lexical|vector|hybrid|connected`
for comparable selection, `--max-bytes`, `--max-chars` and optionally
`--estimated-tokens`. `--require` takes a qualified item ID returned in context.
An absent/unfittable required item returns an explicit error and exit 2.

For supported read-only ingestion of a different first-parent window at this
public source, use `reliable.cli ... git-ingest --repo PATH --end FULL40HEX
--limit 12 --project writ-history --create`. This does not infer semantic
supersession of arbitrary renamed sections, approval or successful verification.
The frozen fixtures are sufficient for unverified local imports when no source
checkout is available; `--verify-repo` additionally checks actual Git objects.

Inspect the exact generation cited in context (replace placeholders):

```bash
python -m writ_retrieval.reliable.agent --store data/my-history inspect \
  '{"project":"writ-history","label":"Claim","id":"CLAIM_ID"}' \
  --project writ-history --generation sha256:GENERATION_DIGEST \
  --cache-dir data/my-generations
```

Omit `--generation` to inspect the current store instead; its returned revision
makes that distinction explicit. The deterministic demo publishes real concrete
commands, refs, before/after contexts, full claim/evidence inspection, retraction
and historical inspection in its output directory. Each CLI call uses a new
process. The demo withdraws a **local evidence association**, not public Writ
policy or a source fact. It proves persisted change visibility, not better agent
reasoning. No generative agent/model was run; MiniLM is the embedding model.

## Owner mutations and review

The read-only agent module exposes only `context` and `inspect`. Owner mutation
commands are in `writ_retrieval.reliable.cli`; same-account unrestricted shell
access remains outside this tooling boundary. Capture Decision/FileChange/Commit/
Memory/Outcome through `capture INPUT.json` (Phase 2 shapes, but actual UTC whole
second timestamps). Use `propose` and `revise` for local rule proposals, and
`lifecycle` for optimistic record/Claim tombstones. All reliable writers share
the owner lock and transaction revision.

`claim INPUT.json` takes `{"claim":CLAIM_ENVELOPE,"supersedes":OPTIONAL_OLD_BINDING}`;
`evidence INPUT.json` takes a versioned Evidence envelope. Source/digest/time and
binding checks run before publication; imported envelopes cannot self-verify.
`inspect` returns the exact binding needed for later operations.

`retract INPUT.json` takes:

```json
{"ref":{"project":"app","label":"Evidence","id":"report-1"},"expected_revision":1,"request_id":"withdraw-1","reason":"The report was associated with the wrong claim."}
```

This correction is durable and replay-safe. Old Evidence and observations are
retained, while active support/confidence is recomputed. `conflict INPUT.json`
takes `left`/`right` bindings, `source_refs` and `note`; both claims remain visible
as unresolved when their bundle is delivered.

`feedback INPUT.json` takes `project`, stable `batch_id`, and `signals` containing
`rule` (exact Binding), `evidence_ref` and `signal` (`positive`/`negative`). Evidence
must bind a current Outcome whose Decision cited that rule wording. Contributions
require local-owner evidence confirmation under the stricter Phase 3 policy.

The owner alone runs `confirm` with `{"refs":[EVIDENCE_REF,...]}` from a terminal,
inspects the stored materials/subjects and types the binding digest. It records
an owner judgment, **not rule approval**. At the statistical threshold,
`review-prepare` takes `{"ref":RULE_REF}` and returns a stored review artifact;
`review-apply` takes `{"artifact":RETURNED_ARTIFACT,"action":"approve"}` or
`reject`. It requires a separate terminal confirmation after displaying the stored
review. Retraction/expiry/wording changes invalidate stale approval proposals.
There is no noninteractive approval flag or agent promotion endpoint.

## Limits

Linux single-thread/single-writer operation, local-owner-selected project labels,
bounded histories and local clocks only. No authenticated tenant boundary,
capability broker, Rust kernel, remote attestation or protected owner credentials.
No automatic contradiction detector, independent label review, live-agent trial,
causal outcome evidence or original local-model-export equivalence. Old immutable
generations need owner-managed disk retention; changes currently rebuild a
bounded replacement index even when texts largely overlap. Public-source digest
checks do not authenticate a remote origin. Failed/uncertain storage or cache
publication returns unavailable; recover by reopening/rebuilding from current
knowledge rather than serving a prior generation as fresh.
