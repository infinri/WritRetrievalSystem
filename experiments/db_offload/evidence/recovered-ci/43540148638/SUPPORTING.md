# Supporting measurements

All results are from the registered hosted replication, not restored local files.

| Backend | Python p95 ms | Rust p95 ms | Paired queries |
|---|---:|---:|---:|
| relate | 9.59 | 9.27 | 200 |
| neo4j | 17.33 | 14.62 | 200 |

Thin client stacks, same backend queries/data and Python outer validation. Model/rendering excluded; Relate PyO3/C ABI and HTTP client differences remain.

| Vector backend / k | Exact recall | Tie-aware recall | Raw p95 ms |
|---|---:|---:|---:|
| HNSW-ef100:5 | 1.0000 | 1.0000 | 0.060 |
| HNSW-ef100:10 | 1.0000 | 1.0000 | 0.055 |
| HNSW-ef100:20 | 1.0000 | 1.0000 | 0.061 |
| HNSW-ef100:50 | 0.9994 | 1.0000 | 0.067 |
| HNSW-ef20:5 | 1.0000 | 1.0000 | 0.098 |
| HNSW-ef20:10 | 0.9875 | 0.9875 | 0.095 |
| HNSW-ef20:20 | 0.9719 | 0.9719 | 0.109 |
| HNSW-ef20:50 | 0.9969 | 0.9975 | 0.121 |
| HNSW-ef50:5 | 1.0000 | 1.0000 | 0.046 |
| HNSW-ef50:10 | 1.0000 | 1.0000 | 0.055 |
| HNSW-ef50:20 | 0.9984 | 0.9984 | 0.057 |
| HNSW-ef50:50 | 0.9969 | 0.9975 | 0.060 |
| Neo4j-ANN:5 | 0.8563 | 0.8563 | 7.049 |
| Neo4j-ANN:10 | 0.9250 | 0.9250 | 7.011 |
| Neo4j-ANN:20 | 0.9734 | 0.9734 | 7.596 |
| Neo4j-ANN:50 | 0.9962 | 0.9969 | 9.074 |
| Relate-exact:5 | 1.0000 | 1.0000 | 1.311 |
| Relate-exact:10 | 1.0000 | 1.0000 | 1.279 |
| Relate-exact:20 | 1.0000 | 1.0000 | 1.330 |
| Relate-exact:50 | 0.9994 | 1.0000 | 1.658 |

Original weighted outputs: 1012; exact changed outputs excluding timing: 52. Numerical differences across runtime/hardware, if present, remain changes, not hidden.

Production restart/retraction checks: 9/9. This is scripted deterministic evidence, not actual agent success.
