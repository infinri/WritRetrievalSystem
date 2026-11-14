# Proposed responsibility split and removal audit

Status: no architecture replacement is adopted. All production modules and
dependencies remain. The new native candidate profiles are experimental;
unsupported integration gates disqualify adoption regardless of a fast run.

| Responsibility | Retain now | Candidate replacement | Removed |
|---|---|---|---:|
| Persistent memory/capture | Relate, memory APIs, reliable/store.py | Native projection over canonical receipts after complete integration tests | 0 |
| Embedding generation | retrieval/embeddings.py, ONNX/tokenizers | None measured; identical vectors are supplied to all engines | 0 |
| Keyword search | retrieval/keyword.py and Tantivy | Relate fulltext for a qualified profile only | 0 |
| Vector index/candidates | HNSW files / exact oracle controls | Relate exact search locally; Neo4j native ANN in a separately qualified server profile | 0 |
| Fusion/ranking | ranking.py and original weighted paths | Cypher RRF for a new profile; not equivalent to weighted doctrine scoring | 0 |
| Graph expansion | traversal.py and visibility verifier | Native typed two-hop expansion, retaining bound visibility and budgets | 0 |
| Scope/time/lifecycle | node_scope and reliable contracts | App-permitted partition plus native queries; not built-in DB authorization | 0 |
| Citations/snapshots | contracts.py and session.py | Native storage/index replacement; exact binding verification/publication stays | 0 |
| Confidence/replay/retraction | reliable/store.py, receipts and policy | Cypher aggregation is not a tested native evidence policy | 0 |
| Owner review/approval | reliable/review.py and owner CLI | None; outside agent tools | 0 |
| Abstention/conflicts/budget | reliable/budget.py, selection/required closure | None established; database scores cannot supply missing evidence or permission | 0 |
| Offline boundary | reliable/agent.py and offline_run.py | None; server comparison remains a separate scoped harness | 0 |

Potential profile-specific removals are Tantivy/HNSW sidecars and some candidate
fusion/BFS execution code. Neither dependency can be removed project-wide while
preserving the original weighted baseline and supported interfaces. NumPy,
ONNX Runtime, tokenizers, Pydantic and Relate remain needed. Neo4j/psutil and
Rust C ABI introduce optional operational/binding costs, not automatic simplicity.

Native candidate partitions do not yet implement canonical live-memory refresh,
trusted shared publication, automatic conflict construction, native confidence/
retraction/replay, storage-device faults or complete cold CLI recovery. Existing
production tests are not proof those native integrations exist. Imported text
remains unverified and cannot grant approval. Retrieval supplies context, not
execution authority; no kernel/broker/M4 authentication is ported.

Evaluate the registered grouped quality margins, 1.20x E2E p95 improvement and
1.10x total RSS limit against the strongest credible flat baseline, not merely
the weak connected arm. Report uncertainty, failures and provisional review.
Local/server winners can differ, but no untested remote profile is inferred from
loopback. A live-agent benefit requires actual authorized model execution.

Rollback is the unchanged production CLI/offline agent and prior indexes. The
experimental namespace is not consulted by it. Further tuning requires a new
held-out set and independent label review; no production replacement, website
deployment or superiority claim is authorized by these provisional experiments.
