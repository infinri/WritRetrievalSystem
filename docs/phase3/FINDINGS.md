# Phase 3 findings

The inspectable context/retraction workflow works on pinned public Writ history.
**This evaluation does not demonstrate a graph retrieval advantage or improved
agent outcomes.** Connected selection loses one source target versus flat hybrid.
Source provenance checks pass; source relevance and abstention are much weaker.

## Evaluation and denominators

The primary, network-denied run is in
[evaluation-release](../../evidence/phase3/evaluation-release).
It uses the same pinned public MiniLM ONNX/tokenizer as Phase 2. Twelve public
first-parent commits produce 47 document-section versions plus commit/change/
evidence records. All four arms see the same 128 eligible units before project
filtering, lifecycle semantics, 8,000-byte / 6,000-character output budget and
common conflict renderer. Connected adds typed adjacency; flat arms do not.

All **13** frozen prompts are published in [evaluation.json](../../examples/phase3/evaluation.json).
Eight have relevance proxies covering ten exact source versions; four expect
abstention; H7 independently checks that commit messages do not establish human
approval or successful verification. These are **model-authored, unreviewed
source-section labels**, not independent semantic relevance judgments. The
history cutoff precedes the two task-motivation commits; their documents were
not ingested. No prompt/label or relevance weight was tuned after seeing results.

| Arm | Any target hit / 8 | All targets / 8 | Source versions / 10 | Mean reciprocal source rank / 8 | Expected abstentions / 4 | Median query ms | Mean context bytes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| BM25 | 4 | 4 | 4 | 0.4375 | 1 | 92.1 | 4,553 |
| Vector | 2 | 1 | 3 | 0.1875 | 2 | 119.2 | 4,356 |
| Hybrid RRF | 3 | 2 | 4 | 0.2917 | 1 | 126.6 | 4,616 |
| Connected RRF | 2 | 1 | 3 | 0.1875 | 1 | 151.3 | 4,951 |

Timings are medians of three warm repetitions, then median across the 13 queries,
in one shared process/host. Initial model load was 1.06 s and generation build
1.59 s. Peak process RSS was **601,656 KiB (~588 MiB)**, including runtime/model/
indexes; it is not per-query allocation, an isolated per-arm comparison or a
server capacity claim. The maximum delivered payload was 5,990 bytes/characters.
Exact generative-model token counts were not measured.

Every delivered citation resolves to a stored exact source revision and matching
record digest; every arm reports no approval/outcome assertions on H7. This
checks **binding correctness**, not correctness of the source's prose. All arms
abstain on foreign-project H13. Only vector abstains on irrelevant-topic H12.
None abstains on missing-evidence H3/H8: these are failures under the provisional
abstention labels. Returning contextual text is not a measured false generated
answer because no generative model was run.

## Improvements, regressions and unchanged results

Compared with flat hybrid, connected has **zero improved**, **one regressed** and
**seven unchanged** source-target prompts. H4 loses the retrieval/authorization
separation source after neighbor delivery consumes budget. H6 returns two of
three D-035 versions under vector/hybrid/connected; no arm returns all three.
H11 returns the labeled draft section under all arms. H1/H5/H9 miss all their
exact targets. BM25 additionally hits H2 and H10. All five controls are published alongside
these positives, not removed from the full denominator.

The poor results are useful diagnostics: duplicate claim/evidence text, truncated
heads and verbose provenance/conflict bundles compete for a small total budget;
lexical matching can select generic words on unknown-topic questions. Source-hit
proxies can overcount usefulness when the answer-bearing clause is truncated.
These are candidate explanations, not controlled causal attributions. The frozen
run was not tuned to hide them. Dataset review, representative tasks and a new
held-out set are prerequisites to making a quality claim or tuning ranking.

Engineering changes followed observations, with earlier runs retained:

* The initial bulk embedding run reached 961,540 KiB (~939 MiB) RSS. A batch cap
  of 16 reduced observed peak to 585,428 KiB in the first bounded run and 607,976
  KiB in the final network-denied run. This is a descriptive process measurement,
  not an isolated performance experiment or guaranteed memory reduction on other
  corpora. Source coverage and abstention metrics stayed unchanged in that batch-only comparison.
* Earlier fresh BM25 builds reordered equal-score records. Explicit score/qualified
  identity ties now fix that reliability defect; five fresh-index tests and the
  final evaluation's repeated-query checks pass. Two earlier delivered selections
  differed across runs (H5 lexical, H11 hybrid); they are not claimed equivalent.
  The final run retains all per-query data and has unchanged aggregate coverage.

[evaluation-unbatched](../../evidence/phase3/evaluation-unbatched) and
[evaluation-bounded-before-tie-fix](../../evidence/phase3/evaluation-bounded-before-tie-fix)
retain those earlier complete outputs. Two later attempts were blocked by
automatic approval review over an incidental Microsoft connection with unknown
payload, including after the ONNX opt-out. They produced no completed benchmark
and are excluded. A kernel network deny subsequently allowed local evaluation to
complete. CI/tests use the same deny with anonymous local socketpairs for asyncio.

A later provenance correction removes fabricated FileChange records for files
merely present in the initial snapshot: a change now requires an actual path in
that commit's Git diff, removing five spurious records. This also changes BM25
H10 from a miss to a hit (4/8 versus 3/8 any-source hits); vector/hybrid/connected
coverage and abstention counts stay unchanged. The table reports the corrected
release run; earlier runs remain diagnostics, not equivalent provenance. The old
citation-digest check alone did not detect that semantic relationship error.

## Demonstrated reliability, separate from relevance

The [agent-facing scripted demo](../../evidence/phase3/demo-release) uses public
history through `82971fd`, separate from the evaluation store. It retrieves D-035,
inspects exact source/evidence versions, withdraws one local evidence association,
restarts in separate processes, replays the old import, and retrieves the changed
context. All **nine** checks pass: generation/revision change, support becomes
inactive, retraction is rendered, old snapshot/source bytes survive, import replay
cannot restore evidence, and no approval is invented. This does not revoke an
upstream decision or establish that upstream evidence was false.

Real-Relate regression tests also exercise close/reopen, obsolete bindings, source
and time validation, expiry during index building, failed build/render/publication,
cache corruption, tombstones, duplicate IDs/types, foreign bridges, cycles,
irrelevant edges, required conflict bundles and UTF-8 budget failures. Controlled
feedback tests establish exactly 40+/10- -> 0.80 confidence and a positive
withdrawal -> 49 observations -> static 0.30; old receipts cannot reactivate it.
Owner approval remains a separate terminal judgment, and a later evidence
withdrawal changes confidence without erasing that historical approval. Simulated
terminal tests are not actual human review of this evaluation's labels.

Original Phase 1/2 evidence and gold fixtures are unchanged. Their 1,012 paired
outputs are historical Phase 2 results, **not a newly repeated Phase 3 corpus
claim**. Original weighted retrieval and separate decision recall remain runnable;
only ONNX telemetry opt-out changes that original model loader's configuration.
The new all-unit history policy is explicitly experimental and measured separately.

## Remaining gaps

Independent label/source relevance review; real agent task execution and outcomes;
stronger abstention; better selection under provenance/conflict overhead;
automatic semantic conflict detection and arbitrary removed/renamed-section
supersession; authenticated source/tenant/runner identities; protected owner
approval and clocks; concurrent writers; cache compaction and incremental index
reuse; Windows/other-architecture validation; exact target-tokenizer accounting;
and original Writ local-model export equivalence. No causal outcome, security
infrastructure equivalence or general graph superiority is claimed.
