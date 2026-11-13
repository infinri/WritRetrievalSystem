# Phase 2 findings

The connected workflow now preserves cited reasoning across restart and changes served confidence from durable observations. Its demonstrated benefit is **recovering project history with inspectable provenance**. It has not established better real-world outcomes or higher corpus relevance.

## Corpus relevance and abstention

The same pinned public ONNX model, original corpus and unchanged fixtures were used before and after implementation. All **1,012 per-query outputs** (253 queries × four arms) are identical after excluding timings. Identity repairs and separate record enrichment introduced no measured corpus ranking changes.

| Arm | Coding hit@5, all 193 | Primary MRR@5 | Methodology hit@5, all 40 | Primary MRR@5 | Negative false injections / 20 |
| --- | --- | --- | --- | --- | --- |
| Lexical only | 137/193 (70.98%) | 0.5781 | 37/40 (92.50%) | 0.6467 | 20/20 |
| Vector only | 156/193 (80.83%) | 0.6868 | 31/40 (77.50%) | 0.5713 | 4/20 |
| Hybrid without graph | 158/193 (81.87%) | 0.6917 | 34/40 (85.00%) | 0.6154 | 4/20 |
| Hybrid with doctrine graph | 157/193 (81.35%) | 0.6923 | 34/40 (85.00%) | 0.6208 | 4/20 |

The graph arm has a tradeoff: versus hybrid without graph, coding hit@5 falls from 158 to 157 while primary MRR@5 rises from 0.6917 to 0.6923. Methodology hit@5 stays 34/40 and MRR@5 rises from 0.6154 to 0.6208. Eight positive-query reciprocal ranks improve, two regress (Q84 and P38), and 223 are unchanged. Q84 loses its top-five hit. All paired query IDs and differences are published in [comparison.json](../evidence/comparison.json). Lexical search leads methodology hit rate in this test, while its lack of the cosine gate admits all 20 negative prompts. These are descriptive results on fixed labels, not a general best-method claim.

For graph retrieval, the coding denominators are explicit:

| Cohort | Count | Hit@5 | MRR@5 | Abstentions |
| --- | --- | --- | --- | --- |
| Full original coding set | 193 | 81.35% | 0.6923 | 7 |
| Primary target in ranked pool | 172 | 91.28% | 0.7768 | 4 |
| Primary target eligible for default semantic route | 169 | 92.90% | 0.7906 | 4 |

All 21 coding queries excluded from ranked eligibility target **mandatory rules** at this pin. Their zero ranked hits remain in the full denominator; the separate mandatory/always-on selection contains those target IDs. This does not verify delivery by an agent host. Three further primary targets are outside the default semantic route. Methodology runs explicitly admit doctrine types so route policy does not masquerade as a missing node. All ANN-containing arms abstain on 7 coding and 5 methodology prompts; negative outcomes are reported separately.

Metrics include primary hit@5/MRR@5/MRR@10 and nDCG@10 in the JSON. The 2,000-token standard budget returns at most five units, so MRR@10 equals MRR@5 here. nDCG assigns gain 2 to the primary and 1 to other listed targets; unlisted context is **unjudged**, not proven irrelevant. The original gold files were not edited.

## Connected workflow and feedback

On six authored synthetic prompts, all arms retain 4/4 judged guidance hits. Before capture, history hits are 0/3. After capture and restart, the connected channel retrieves 3/3 expected history items; guidance-only channels remain 0/3 by design. After feedback and another restart, guidance and history hit counts remain unchanged. This demonstrates the extra history channel, not a fair claim of general relevance superiority over systems that have no history input.

All scenario checks pass: idempotent capture and feedback replay, project/provenance correctness, contradictory failed history retained, and foreign/deleted/superseded/irrelevant markers excluded on the specified control prompts. Real-Relate tests also exercise legal cycles, foreign bridges, duplicate IDs, stale revisions/reviews and rollback.

Fifty **synthetic correlated outcomes**, 40 positive and 10 negative, change the speculative confidence weight from 0.30 to 0.80 at the original 50-observation threshold. The target guidance score changes from 0.8598 to 0.9073 (+0.0475, exactly 0.095 × 0.50); its rank and hit count do not improve. The rule becomes a review candidate and remains `ai-provisional`. This is an algorithm exercise, not 50 independent observations from real users.

An owner-readable snapshot includes wording, sources, signals, outcomes, similar rules and conflicts. Noninteractive approval is denied. PTY tests on disposable fixtures verify explicit confirmation, promotion attribution and stale-snapshot rejection. The actual scenario stays unapproved. Changed wording resets counts; frozen decision snapshots preserve the old wording.

## Runtime observations

| Run, graph arm | Uncached median / p95 (ms) | Cached median / p95 (ms) | Process peak RSS (MiB) |
| --- | --- | --- | --- |
| Before | 12.25 / 28.93 | 1.10 / 2.41 | 753.8 |
| After | 11.83 / 28.45 | 1.09 / 2.39 | 310.7 |

These are single-host measurements. RSS is Linux process-lifetime high-water memory across model/index building and all arms, not idle daemon usage. Cold-build/cache conditions and scheduling are not controlled for a speed comparison. The common lexical harness still pays an unused encoding call. Connected request timings include refresh, recall and rendering; ranked-only arms do not. No performance improvement is claimed.

## Practical limits

- History and feedback validation are synthetic. A held-out real-project task/outcome study, complete context relevance judgments and independent label review remain necessary.
- Numerical equivalence to Writ’s unavailable original local ONNX export remains unverified. All within-project comparisons use identical public artifact bytes.
- Record connections enrich a bounded separate channel; record-based proximity/ranking changes were deliberately not enabled. Large-store incremental loading and a unified total context budget remain open.
- Capture is manifest/API based; automatic Git/hook harvesting, authenticated service deployment, evidence retraction and concurrent-writer orchestration are not implemented. Tombstones hide context without erasing historical feedback.
- Approval is a local-owner terminal assertion, not Writ’s agent-unforgeable hook/token gate. Processes with the same account/terminal/store access are trusted.

See [PHASE2.md](PHASE2.md) for commands and contracts; [RUN-PROVENANCE.json](../evidence/RUN-PROVENANCE.json) maps locally recorded commit IDs to published commits with identical source trees.
