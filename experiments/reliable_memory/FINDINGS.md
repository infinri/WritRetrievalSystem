# Reliable-memory follow-up findings

The canonical-memory → native-index → restart → retraction workflow now runs through supported local interfaces. This closes a persistence/refresh integration gap. The measurements do **not** justify replacing the existing retrieval architecture or claiming improved agent outcomes.

Protocol/inputs were published at `74fecfc0a056a1263693ec580f3d51d9168ae18a`; source times were corrected to UTC before that publication. Implementation and evaluation code were published at `f16a3502ff9ab4b262262d9eab07dae84cb77d71` before opening held-out results. Zero configurations were tuned. After scoring, missing-object Git reads were made explicitly fetch-free/failing and malformed-import guards were tightened for public URI/path/line bindings, normalized paths, source bounds and future times; ranking, rendering, request selection and native search remain the frozen implementation. Scores refer to that published evaluation code, not a newly unseen set. Frozen valid fixtures still pass source/import checks. Prior evidence is unchanged: 324 registered files pass byte-hash checks. The merged bake-off's primary findings remain authoritative; no discarded exploratory result is reused.

## What was measured

72 tasks: 60 distinct section families and 12 unknown controls, divided into 36 development / 36 held-out tasks with disjoint source files. Each split has 24 natural-language positives, six explicit source lookups, three missing-owner-confirmation requests and three project-isolation controls. Four positives per split use the older Git snapshot only. Twelve public Writ architecture files at two exact revisions yield 254 source-version passages but **127 distinct text passages**: their text is unchanged between these pins. This checks time/revision isolation, not successful discovery of changed public decisions. Local changed/retracted/conflicting records are covered separately by regression tests and the demo.

Labels are **model-authored and unreviewed**. Complete selected paragraphs replace the bake-off's 120-character proxies, but a section question can have other relevant answers. These are source-recovery tasks, not a representative independently reviewed coding benchmark. Historical recorded facts and unknown approvals/outcomes are preserved as such.

All arms ingest the same 127 passage Claims per snapshot. Flat/native profiles share visibility, request constraints, 1600-character embedding heads, pinned MiniLM ONNX/tokenizer, 128-token embedding truncation, exact cosine gate .30, k=6, RRF=60 and complete 8,000-byte / 6,000-character budgets. Source/projection validation, query inference and rendering are included in timings. Legacy retains its original parser, 640-character display heads and lack of explicit request constraints. Those differences are policy changes, not database improvements.

## Held-out results, separated by task type

| Profile | Natural full target passage / 24 | Natural MRR / 24 | Explicit source lookup / 6 | Project isolation / 3 | Missing owner confirmation / 3 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Legacy hybrid | 19 | 0.6875 | Unsupported contract (raw 3) | 3 | Unsupported |
| Legacy connected | 19 | 0.6875 | Unsupported contract (raw 3) | 3 | Unsupported |
| Grounded flat | 20 | 0.7292 | 6 | 3 | 3 |
| Grounded native Relate | 20 | 0.7292 | 6 | 3 | 3 |

Raw all-positive totals are 22/30 legacy and 26/30 grounded; three of four gains are explicit lookup support and **must not be presented as a semantic retrieval improvement**. The sole natural-language change is `hel-06`: candidate ordering changes after keyword preparation, and a different complete passage fits. Full display text, parser changes and metadata budgeting changed together; no causal attribution to one change is established. The other 23 natural tasks are unchanged (19 hits, four misses). The paired file-cluster bootstrap interval for grounded-minus-legacy natural coverage is [0, .1364], with only five file clusters; descriptive, provisional and compatible with no gain.

Native and grounded-flat deliver identical labeled targets on all 30 positives. Native candidate orders differ on `hel-07`, `hel-08`, `hel-16`, `hel-20`, without target-delivery changes. A zero-observed-regression binomial diagnostic on 24 natural positives still permits an 11.7% one-sided upper bound; this cannot establish population noninferiority at the registered 3-point margin. No native quality superiority is shown.

Development all-positive delivery is 21/30 for every profile, but its natural subset **regresses to 15/24 grounded versus 17/24 legacy**. Grounded gains `dev-02`, `dev-11` (natural) and `dev-27`, `dev-29` (structured); loses `dev-04`, `dev-05`, `dev-07`, `dev-22` (all natural); 22 positives are unchanged. The full-card/keyword policy is therefore mixed, not an overall quality win. Across both partitions, natural delivery is **35/48 grounded versus 36/48 legacy**. Complete development comparisons are published alongside held-out results; no tuning was performed to remove those regressions. All final repeated payloads in the held-out run are deterministic. No context errors, scope/citation-version failures or payload-budget violations were observed. Maximum complete payload is 6,000 bytes/characters. Binding/digest correctness does not establish truth or semantic answer sufficiency.

This corpus contains standalone Claims, without captured record relationships. Accordingly legacy connected equals legacy hybrid; this is **not a graph-advantage experiment**. The separate canonical workflow demo and actual-engine tests exercise record/evidence edges and lifecycle changes. Original Phase 3 connected 3/10 versus flat 4/10 evidence is preserved.

## Latency and resources

| Profile | Natural query p50 ms | Natural query p95 ms | Full 36-task p50 ms | Full p95 ms |
| --- | ---: | ---: | ---: | ---: |
| Legacy hybrid | 39.8 | 134.7 | 37.2 | 133.9 |
| Legacy connected | 35.8 | 135.3 | 35.1 | 134.5 |
| Grounded flat | 52.1 | 113.8 | 50.7 | 131.4 |
| Grounded native Relate | 53.2 | 142.6 | 51.8 | 141.8 |

Each full row has 108 measured calls (36 tasks × three repetitions), after initial builds; natural rows have 81 calls including isolation controls. Repetitions are timing samples, not additional relevance tasks. Latin rotations/randomized task order, seed 20261114, same local persistent Python process, two intra-op / one inter-op ONNX threads. These are descriptive local warm measurements, not throughput/concurrency, remote-server or fresh-CLI capacity results. Small timing differences and noisy tails do not select a winner.

Host: Linux x86_64, AMD EPYC 9V45, nine visible CPUs. Python 3.12; Relate 1.0.1, NumPy 2.5.4, Tantivy 0.27.0, ONNX Runtime 1.32.0, tokenizers 0.23.3, Pydantic 2.14.3. Held-out whole-process peak RSS is 701,448 KiB (~685 MiB), 57.08 CPU seconds, working stores/cache 5,449,826 bytes. This includes all profiles and the embedding model; it is not per-arm resource attribution. Source import, model startup and every first-context time are in the summary. Legacy hybrid/connected share their generation cache, making connected's first-context time warmed rather than an independent cold startup. No host caches were flushed and no privileged setup was used. The initial development run, with concurrent tests, is retained as an initial diagnostic rather than the final performance run.

The grounded flat/native profiles show no speed advantage over legacy median latency at this scale. Native adds permitted partitions, full artifact checks and index update work. Counts/feedback remain application semantics; the bridge currently rebuilds rather than incrementally updates embeddings. Larger-scale update costs and isolated per-arm resource curves have not been measured by this follow-up. The previous bake-off's scale/Neo4j/Rust evidence remains separate.

## Complete workflow evidence

`evidence/demo/demo.json`: **17 actual CLI/process invocations**, including pinned read-only public Git ingestion, real ONNX/native retrieval, a clearly labeled local scripted decision/outcome, revision-bound feedback, historical inspection, retraction, replay and fresh retrieval after process exit. The before/after generations differ; withdrawn evidence is absent from active recall; its old live snapshot remains inspectable. Imported script evidence stays unverified, active positive contributions stay zero and the proposed rule stays `ai-provisional`. The outcome reports only the mechanical retrieval operation, not implementation success or rule causality. No owner confirmation was automated.

Real-engine gates additionally verify native served confidence 40+/10− → .80, withdrawal → 39+/10− → static .30, plus replay safety; they cover owner-confirmed contribution withdrawal, restoring wording under a new revision, expiry, source/record requirement mismatch, full UTF-8 conflict bundles, exact budget errors, mandatory delivery with insufficient requested evidence, duplicate IDs across types, cycles, foreign bridges and hidden-project IDF/top-k influence. Fault injection exercises build, canonical read and atomic publication failures; corruption is detected with an open reader. Owner quarantine and process restart rebuild the disposable projection without changing canonical facts. These are bounded application/engine checks, not power-loss, adversarial filesystem or enterprise authentication guarantees.

The explicit localhost generative harness and fixed context packets are prepared, but actual model trials are **NOT RUN**: an authorized generative endpoint plus exact model identity/artifact revision are missing. Embedding inference and deterministic CLI scripts are not generative-agent evidence. Review worksheets and blinded context copies are prepared; no human reviewer or outcome review is claimed.

## Validation

149 local pytest checks and all five original unittest demo checks pass under
network denial. `pip check` passes. A wheel built with setuptools 84.2.1 was
installed into a separate target and its native Relate / real-ONNX grounded
command ran from `/tmp`, outside the source checkout. The reused venv lacked
setuptools for the initial no-isolation pip build; that failed log is retained,
and the direct build succeeds. Logs and hashes are in `evidence/validation`.
The historical 1,012 weighted-query comparison was not rerun or reasserted. All nine original Phase 3 scripted restart/retraction checks also pass with the original frozen source fixture. A first attempt failed against missing historical blobs in a partial reference clone; after explicit source-object preparation the full export matches. The failed attempt is recorded, and Git ingestion now prohibits implicit lazy fetch and refuses unavailable promised documents rather than omitting them.

## Proposed decision and remaining work

Keep the existing baseline, with grounded flat and native Relate as opt-in profiles. Adopt the canonical-to-derived-index contract as an experimental integration boundary; keep confidence/replay/lifecycle/approval semantics in the canonical application ledger. Native search has working persistence and parity on this sample, but equal provisional quality and slightly higher median latency give no reason to replace the baseline. **Zero production modules or dependencies are removed.** No architecture replacement is merged.

Next evidence needed: actual independent label review/replacement; realistic task formulations with changed public decisions and complete multi-source answers; a new frozen held-out set before any tuning; generic missing-evidence/near-miss abstention beyond explicit requirements; actual paired generative trials; incremental refresh/compaction and larger-scale fault/resource measurements. Exact target-tokenizer accounting, authenticated source/tenant identities, protected owner judgments/clocks and multi-writer support remain deferred under the local-owner boundary.
