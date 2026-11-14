# Database ownership protocol (pre-implementation freeze)

No architecture winner is selected. This branch is an experiment, not replacement
code. Main `892e139` and V2 `a0e0e4` match the requested pins. M3 acceptance is
scoped development acceptance (17 exact / 64 adapted / 21 differences / 25 deferred),
not production enforcement. D-035..D-040 were inspected; only immutable identity,
current binding, provenance, replay/freshness and report-input verification
principles apply. No broker, execution permission or M4 authentication is ported.

## Data and labels

64 new tasks, 32 development / 32 held-out, eight categories with four distinct
topic families each and two formulations per family. Whole families are split;
16 independent families per partition, not 32 independent judgments. Existing
Phase 1–3 prompts are historical regression data only. The discarded 7/10 result
is not used. Public MIT Writ source at the exact V2 revision and the unchanged
Phase 3 historical export supplies 305 overlapping 900-character passages and
288 source-adjacency/reference edges. Source files, revisions, text digests and
answer-clause offsets are frozen. Each label requires the actual clause plus
correct source revision/digest in delivered text; a URI hit alone is insufficient.

Labels are MODEL-AUTHORED / NOT HUMAN REVIEWED, not truth adjudication. Negative
labels are warranted unknowns under the registered available sources; human
review may find alternatives. Local retraction/expiry are explicitly test controls
on an evidence association, not claims that upstream facts were revoked or false.
Historical tasks use a 17:32:20Z cutoff; later 23:00:13Z documents cannot enter.
Conflicts remain explicitly unresolved; text never grants permission. Human
review sheets and blind agent-review packets are deliverables, not completed
human review. No unreviewed quality outcome authorizes architecture replacement.

## Tracks and tuning

Matched: identical permitted passages, vectors, scalar cosine, candidate cap 20,
RRF k=60, score/qualified-ID ties, 2 hops / 64 visits and full 16,000-byte /
12,000-codepoint model-facing JSON. Entire passage cards are selected or omitted;
answer labels never count a truncated-away clause. Native analyzer/ANN differences
are measured, not called equivalent. Vector gates use raw cosine .30: native
rebounded cosine is mapped with `2*s-1`. Approximate recall is scored separately
against an exact normalized-dot-product oracle.

Best-configured: exactly two registered configs per comparable backend (20/.30
and 40/.40), development only. Select by complete answer-clause sufficiency, then
correct abstention, then E2E p95. Equal effort cap: two configs, no handwritten
query rules. Commit selected configs before executing held-out queries. Do not
change configs after opening held-out; any later tuning needs a new held-out set.
Embedding model/tokenizer bytes and 128-token preparation stay fixed. Optional
learned reranking is a separate, equal-access ablation, never confused with RRF.

A includes original weighted retrieval and Phase 3 paths as historical controls,
plus a strong warm Tantivy/exact-vector/RRF control on the identical passage set.
B offloads candidate searches. C adds Cypher fusion/filtering/expansion. D uses
Neo4j native search/Cypher with loopback-only server transport. E follows measured
promising splits; equivalent data/queries must separate client language from DB
ownership. Do not port an unsuccessful split without a recorded reason.

## Correctness and resources

Zero tolerance: foreign results/bridges, stale revision/digest citations, evidence
resurrection, imported verification/approval, incomplete required conflict bundles,
non-deterministic selection, budget overflow, or silently mixed index generations.
Unsupported native semantics are unsupported, never a passing fallback. Test
global-top-k starvation, hidden/shared IDF influence and index partition costs.
A partition materialized by our code is not native DB authorization. Application
contracts, approval boundary, confidence policy and uncertain-write handling
remain explicit even when evaluated in queries. Original offline agent code is
untouched. Neo4j's dedicated harness validates its literal 127.0.0.1 endpoint;
no external server, credentials, paid services or privileged host changes.

Record startup, import/index/update, restart, retraction visibility, query-only
and E2E latencies (including model inference), throughput, client/model/server
CPU/RSS/disk. Neo4j gets heap 512 MiB, page cache 128 MiB; count actual process
memory too. No remote numbers are inferred from loopback. Warmup 10, randomized
counterbalanced seed 20261113, target 1,000 warm samples/profile for p99; report
percentiles only with their sample sizes, failures and timeouts. Cold CLI and
persistent service are distinct. Register 1x/10x/100x synthetic load and 1/4
readers; single-writer remains the supported mutation boundary. Synthetic load
is not relevance evidence. Budget 2 GiB combined measured RSS, 180 s/profile;
stop/record timeout/OOM/resource-limit rather than silently omitting it. Do not
flush caches, alter clocks or suspend the host. Host is shared, no isolation claim.

## Decision rule before held-out

All correctness gates must pass. Provisional noninferiority requires a grouped,
paired, one-sided 95% bootstrap lower bound > -0.03 for both complete-answer
sufficiency and MRR. Families, not duplicated formulations, are bootstrap units;
2,000 draws with fixed seed. Adoption additionally requires >=1.20x E2E p95
speedup at equivalent quality and <=1.10x combined RSS, or a separately reviewed
explicit Pareto tradeoff. Review provisional labels before any adoption. Publish
per-query wins/losses and uncertainty; no composite score hides regressions.
Distinguish local/server winners; unsupported concurrency/remote profiles are
NOT RUN. Preserve production baselines until owner decision is reviewed.

## Execution milestones

1. Protocol/capability PR: freeze data/config and actual engine probes.
2. B/C working Relate PR: native queries, compatibility gates and development data.
3. D/E PR: real local Neo4j, language-isolated thin Rust after ownership evidence.
4. Decision PR: frozen held-out results, resource curves, review materials,
   agent trials or precise NOT RUN prerequisites, removal/rollback audit.

Scripts/configs, raw results and exact hashes live only under this namespace.
