# Hosted replication findings

This is a new execution of already frozen policies after workspace loss. It is not a new unseen evaluation, tuning, or reconstruction of lost raw measurements. All labels remain provisional.

Complete target delivery means all 120-character frozen source proxies with exact version/digest are actually present. It is not independent proof of full answer sufficiency. There are 20 positive tasks / ten families, 12 warranted-unknown controls / six families, 24 target instances and only five distinct source versions.

## matched

| Arm | Targets complete /20 | Clauses /24 | MRR | Empty abstentions /12 | E2E p95 ms | Errors |
|---|---:|---:|---:|---:|---:|---:|
| A-connected | 8 | 9 | 0.221 | 4 | 21.8 | 0 |
| A-hybrid | 14 | 17 | 0.300 | 4 | 21.1 | 0 |
| A-lexical | 13 | 15 | 0.410 | 4 | 21.0 | 0 |
| A-vector | 8 | 9 | 0.232 | 4 | 21.1 | 0 |
| B-connected | 8 | 9 | 0.221 | 4 | 26.3 | 0 |
| B-flat | 13 | 15 | 0.292 | 4 | 25.7 | 0 |
| C-connected | 8 | 9 | 0.221 | 4 | 26.9 | 0 |
| C-flat | 13 | 15 | 0.292 | 4 | 25.9 | 0 |
| D-connected | 8 | 9 | 0.221 | 4 | 48.2 | 0 |
| D-flat | 12 | 14 | 0.285 | 4 | 39.5 | 0 |
## best

| Arm | Targets complete /20 | Clauses /24 | MRR | Empty abstentions /12 | E2E p95 ms | Errors |
|---|---:|---:|---:|---:|---:|---:|
| A-connected | 9 | 11 | 0.260 | 4 | 26.9 | 0 |
| A-hybrid | 14 | 17 | 0.300 | 4 | 23.9 | 0 |
| A-lexical | 13 | 15 | 0.410 | 4 | 24.0 | 0 |
| A-vector | 8 | 9 | 0.232 | 4 | 23.7 | 0 |
| B-connected | 9 | 11 | 0.262 | 4 | 32.0 | 0 |
| B-flat | 13 | 15 | 0.292 | 4 | 32.2 | 0 |
| C-connected | 8 | 9 | 0.221 | 4 | 32.3 | 0 |
| C-flat | 13 | 15 | 0.292 | 4 | 31.7 | 0 |
| D-connected | 9 | 11 | 0.262 | 4 | 53.5 | 0 |
| D-flat | 12 | 14 | 0.285 | 4 | 47.5 | 0 |

## All registered resource profiles

| Profile | Status | n | p50/p95/p99 ms | Peak RSS MiB | Import ms | Disk MiB | CPU s |
|---|---|---:|---|---:|---:|---:|---:|
| C-10-1 | COMPLETE | 1000 | 70.0/80.7/87.9 | 580.3 | 1322.5 | 13.8 | 129.6 |
| B-10-1 | COMPLETE | 1000 | 70.6/79.1/86.3 | 585.4 | 1307.2 | 13.8 | 129.7 |
| D-100-4 | COMPLETE | 1000 | 78.6/100.3/118.0 | 1892.9 | 21472.5 | 308.4 | 167.5 |
| A-10-4 | COMPLETE | 1000 | 139.8/201.1/229.7 | 435.8 | 58.3 | 0.0 | 569.3 |
| D-1-4 | COMPLETE | 1000 | 67.6/75.0/103.1 | 1331.8 | 1967.6 | 5.3 | 95.7 |
| D-1-1 | COMPLETE | 1000 | 29.2/36.6/40.7 | 1169.5 | 1368.1 | 5.3 | 103.4 |
| B-100-1 | FAILED | 313 | - | 1682.3 | 20483.5 | 152.9 | 241.4 |
| A-100-4 | COMPLETE | 1000 | 600.8/778.8/953.8 | 628.0 | 510.4 | 0.0 | 1159.8 |
| D-10-4 | COMPLETE | 1000 | 69.3/85.8/96.1 | 1392.9 | 3586.5 | 32.9 | 104.6 |
| C-100-1 | FAILED | 312 | - | 1486.2 | 19609.4 | 152.9 | 239.2 |
| A-10-1 | COMPLETE | 1000 | 38.8/74.8/92.6 | 437.7 | 66.1 | 0.0 | 656.3 |
| B-10-4 | COMPLETE | 1000 | 91.6/115.9/132.4 | 1258.8 | 1504.5 | 13.8 | 132.2 |
| C-1-4 | COMPLETE | 1000 | 65.9/76.4/83.5 | 687.7 | 140.4 | 1.5 | 56.8 |
| D-100-1 | COMPLETE | 1000 | 60.1/73.2/95.5 | 1890.8 | 21087.9 | 308.4 | 180.8 |
| B-1-1 | COMPLETE | 1000 | 25.1/29.8/32.6 | 437.5 | 178.4 | 1.5 | 62.4 |
| B-100-4 | FAILED | 1 | - | 4809.9 | 21078.9 | 138.3 | 60.3 |
| A-100-1 | COMPLETE | 1000 | 157.6/222.1/308.9 | 586.8 | 483.9 | 0.0 | 1149.8 |
| C-1-1 | COMPLETE | 1000 | 24.2/28.0/29.8 | 435.7 | 146.6 | 1.5 | 59.9 |
| C-10-4 | COMPLETE | 1000 | 90.1/105.8/121.9 | 1252.9 | 1313.0 | 13.8 | 126.9 |
| C-100-4 | FAILED | 1 | - | 4803.8 | 19941.3 | 138.3 | 58.8 |
| D-10-1 | COMPLETE | 1000 | 32.6/52.1/62.7 | 1213.1 | 3898.3 | 32.9 | 135.1 |
| A-1-4 | COMPLETE | 1000 | 63.5/69.4/73.2 | 385.1 | 18.5 | 0.0 | 44.9 |
| A-1-1 | COMPLETE | 1000 | 17.4/19.6/21.1 | 389.9 | 18.5 | 0.0 | 45.3 |
| B-1-4 | COMPLETE | 1000 | 65.6/73.5/84.5 | 691.3 | 143.3 | 1.5 | 57.6 |

## Limits and proposed split

No production modules or dependencies are removed. Keep Relate persistence and application source/binding/visibility/replay/confidence/approval/budget semantics. Native partitions are not built-in authorization. Automatic conflict discovery, trusted shared publication, full canonical-memory projection, native evidence replay/retraction, device faults, remote server and full cold CLI recovery remain unsupported adoption gates.

A source digest establishes identity, not truth. Human labels and actual generative outcomes remain unreviewed/NOT RUN. The 64 formulations represent only 32 families and a small public-document corpus. No claim generalizes to untested database versions, configurations or project populations.

Performance uses fresh processes and static prepared generations, one serialized offline model and separate reader connections. It includes inference, DB/transport, validation and complete rendering, excluding live canonical refresh. Cooperative 2 GiB RSS checks run after setup and during queries, not an OS hard limit. 180 s query and 300 s outer limits are retained. RSS samples can miss peaks, CPU counts may omit unwaited descendants. Working disk excludes shared runtimes/model/distribution; environment metadata records those separately. Failed profiles have no adoption percentiles. One hosted run/profile is not an independent multi-host replication.

The original offline CLI and all baselines are unchanged. Any adoption needs completed correctness integrations, actual independent review, the registered noninferiority/speed/RSS thresholds and new held-out data before further tuning. Rollback is simply the unchanged production path.
