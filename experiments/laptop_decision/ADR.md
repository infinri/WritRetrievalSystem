# ADR: Retrieval responsibility split for the local hackathon workflow

**Status: PROPOSED. This has not been reviewed or approved by the owner.** It
is a recommendation for joint review. Nothing here is merged, deployed or
removed by this change.

Evidence: [FINDINGS.md](FINDINGS.md), [decision-summary.json](evidence/decision-summary.json),
[QA results](evidence/qa-comparison/QA-RESULTS.md) and the registered
[protocol](PROTOCOL.md), with Amendments 1 and 2. The labels are model-authored
and unreviewed. Answer grading is model-assisted (Claude Opus 5.5), not
independent human review.

## Decision

1. **Recommended local hackathon workflow: grounded flat.** "Default" means
   this exact entry point:

   ```bash
   python -m writ_retrieval.reliable.grounded_cli --store STORE --cache-dir CACHE \
     --model-dir MODEL --project PROJECT 'question'
   ```

   With `--backend` omitted the backend is `flat`, and with `--arm` omitted
   the arm is `hybrid`. That is the command's existing behavior. **No CLI
   behavior changes are made or proposed.** The legacy
   `writ_retrieval.reliable.agent context`, the weighted `writ-retrieval query`
   and the Phase 2 `connected` / `recall` commands keep their current defaults
   and remain supported controls. Pointing documentation or any wrapper at
   grounded flat would be a separate change for review. It is not done here.
2. **Relate remains the persistence layer.** The canonical ledger
   (`ReliableStore` on embedded Relate 1.0.1) owns captured records,
   revisions, receipts, retraction and lifecycle.
3. **Native Relate retrieval stays an opt-in profile** (`grounded_cli
   --backend relate`). It is a supported, tested canonical-memory → native-index
   workflow with identical labeled delivery. It is not the default because it
   is slower (warm p95 about 1.28x flat, cold p95 about 1.20x) and no speed
   gate is met. This keeps meaningful, working Relate integration for the
   hackathon without claiming it is faster.
4. **No Neo4j profile is adopted.** The bake-off D profile stays experimental.

## Responsibilities

| Responsibility | Owner now | Can move into the database now? |
|---|---|---|
| Canonical records, revisions, receipts, lifecycle | Writ `ReliableStore` on Relate | Already in Relate storage; meaning stays in Writ |
| Embedding inference (MiniLM ONNX) | Writ | No; identical vectors are supplied to every engine |
| Keyword and vector candidates | Flat: Tantivy plus exact/HNSW in Writ. Opt-in: Relate native FULLTEXT/VECTOR | Yes, as opt-in (grounded Relate). Not as the default (slower here) |
| Permitted-partition construction (scope before top-k) | Writ | No; a partition built by app code is not database authorization |
| Fusion (RRF), typed traversal, ties | Writ | Not adopted: Cypher RRF/expansion (C/D) failed the quality margin |
| Required/conflict bundles, budget, abstention, rendering | Writ | No native contract exists |
| Feedback, confidence, retraction/replay meaning, approval | Writ (by design) | Not required: the split intentionally keeps this policy in Writ |
| Generation publication, index validation, quarantine | Writ | No; the publication manifest binds both engines' artifacts |
| Offline boundary and owner approval | Writ CLIs | No |

## Removals

**None are justified.** Tantivy and HNSW are still required by the default
(grounded flat) and by the legacy and weighted baselines. The application
fusion and traversal code is used by every supported profile. The B/C/D
prototype code stays in `experiments/` and is not consulted by any production
command. NumPy, ONNX Runtime, tokenizers, Pydantic and Relate all remain
necessary.

## Tradeoffs recorded (laptop, loopback; not remote or cross-machine)

- **Grounded flat vs legacy hybrid:** grounded flat supports the explicit
  source and owner-confirmation request contract, which legacy does not
  (both pass 3/3 project isolation). Natural-language
  coverage is mixed: development 15/24 vs legacy 17/24, held-out 20/24 vs
  19/24, combined 35/48 vs 36/48. Legacy is faster at the median (warm p50
  41 ms vs 60 ms). Warm p95 is similar (141 ms vs 144 ms). Cold CLI p50 is
  919 ms vs 862 ms.
- **Grounded Relate vs flat:** target delivery is identical on all 60
  positives. Relate is slower (warm p95 180 ms vs 141 ms; cold p95 1294 ms vs
  1077 ms) but has **lower cold-process peak RSS (238 MiB vs 284 MiB)**.
- **Neo4j (bake-off D):** **strong large-load performance.** At 100x
  synthetic load D's p95 is 73 ms vs flat's 222 ms with one reader (3.0x), and
  100 ms vs 779 ms with four readers (7.8x). It also uses about 3x the memory
  (about 1.85 GiB vs 0.6 GiB). At 1x it is slower than flat (37 ms vs 20 ms)
  with about 1.1 GiB vs 0.4 GiB. Its quality lower bound is −0.20 against the
  registered −0.03 margin, and it has no canonical live-memory, feedback or
  recovery integration.
- **B/C Relate prototypes:** they fail the quality margin (−0.15) and fail at
  100x load (timeout or about 4.7 GiB RSS with four readers).
- **Fixed-context QA (model-assisted):** see the QA results. QA gates no
  architecture choice. It cannot show task completion or the causal benefit of
  a rule.

## Reconsider when

- Independent human review replaces or confirms the labels, or a new frozen
  held-out set with realistic multi-source and changed-decision tasks shows a
  different quality ranking.
- Corpus size or concurrent readers grow to where flat latency degrades, as at
  10x/100x with four readers. That favors re-testing Neo4j or native Relate
  ANN, provided a canonical-memory projection with refresh, retraction and
  recovery exists and quality is non-inferior.
- Relate releases native ANN or incremental index updates that close the
  latency gap, or a deployment where cold-process memory matters more than
  latency (then native Relate becomes the better opt-in default candidate).
- Remote or shared server operation becomes a requirement. Only loopback was
  measured.

## Rollback

Nothing is changed in production code, so no rollback is needed. If a later
change makes native Relate or another profile the default, roll back by
omitting `--backend` (flat) or by using the unchanged legacy
`reliable.agent context`. Canonical data is untouched by derived-index choices.
Corrupt derived indexes are quarantined with the owner CLI and rebuilt.

## Disclosure

Prepared with Claude Code (Claude Opus 5.5). Trials used Claude Sonnet 5.5
through the existing authorized Claude Code login. Earlier milestones disclose
OpenAI Codex assistance. Writ V1/V2 (MIT, Lucio Saldivar) and JolliAI
attribution in NOTICE.md are unchanged. Relate (Apache-2.0) and Neo4j
Community (GPL) are external runtimes and are not bundled.
