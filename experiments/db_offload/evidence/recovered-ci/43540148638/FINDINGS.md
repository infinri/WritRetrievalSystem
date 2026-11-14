# Hosted replication findings

This is a new execution of already frozen policies after workspace loss. It is not a new unseen evaluation, tuning, or reconstruction of lost raw measurements. All labels remain provisional.

Complete target delivery means all 120-character frozen source proxies with exact version/digest are actually present. It is not independent proof of full answer sufficiency. There are 20 positive tasks / ten families, 12 warranted-unknown controls / six families, 24 target instances and only five distinct source versions.

## matched

| Arm | Targets complete /20 | Clauses /24 | MRR | Empty abstentions /12 | E2E p95 ms | Errors |
|---|---:|---:|---:|---:|---:|---:|
| A-connected | 8 | 9 | 0.221 | 4 | 36.3 | 0 |
| A-hybrid | 14 | 17 | 0.300 | 4 | 30.6 | 0 |
| A-lexical | 13 | 15 | 0.410 | 4 | 30.4 | 0 |
| A-vector | 8 | 9 | 0.232 | 4 | 30.8 | 0 |
| B-connected | 8 | 9 | 0.221 | 4 | 42.4 | 0 |
| B-flat | 13 | 15 | 0.292 | 4 | 39.7 | 0 |
| C-connected | 8 | 9 | 0.221 | 4 | 39.2 | 0 |
| C-flat | 13 | 15 | 0.292 | 4 | 38.4 | 0 |
| D-connected | 8 | 9 | 0.221 | 4 | 74.6 | 0 |
| D-flat | 12 | 14 | 0.285 | 4 | 72.5 | 0 |
## best

| Arm | Targets complete /20 | Clauses /24 | MRR | Empty abstentions /12 | E2E p95 ms | Errors |
|---|---:|---:|---:|---:|---:|---:|
| A-connected | 9 | 11 | 0.260 | 4 | 34.6 | 0 |
| A-hybrid | 14 | 17 | 0.300 | 4 | 30.7 | 0 |
| A-lexical | 13 | 15 | 0.410 | 4 | 30.6 | 0 |
| A-vector | 8 | 9 | 0.232 | 4 | 30.0 | 0 |
| B-connected | 9 | 11 | 0.262 | 4 | 43.0 | 0 |
| B-flat | 13 | 15 | 0.292 | 4 | 38.5 | 0 |
| C-connected | 8 | 9 | 0.221 | 4 | 44.8 | 0 |
| C-flat | 13 | 15 | 0.292 | 4 | 38.3 | 0 |
| D-connected | 9 | 11 | 0.262 | 4 | 83.9 | 0 |
| D-flat | 12 | 14 | 0.285 | 4 | 66.3 | 0 |

## Learned reranking, separate from ownership

{
  "actual_calls": 128,
  "added_p50_ms": 827.8186069999833,
  "added_p95_ms": 956.9424108499959,
  "peak_worker_rss_kib": 461136,
  "composed_timings_only": true,
  "arms": {
    "A-hybrid": {
      "complete": 14,
      "mrr": 0.5808333333333333,
      "changes": [
        {
          "task": "multihop-4-1",
          "complete_delta": 0,
          "mrr_delta": 0.875
        },
        {
          "task": "exact-3-1",
          "complete_delta": 0,
          "mrr_delta": 0.0
        },
        {
          "task": "exact-4-2",
          "complete_delta": 0,
          "mrr_delta": 0.20833333333333331
        },
        {
          "task": "multihop-3-1",
          "complete_delta": 0,
          "mrr_delta": 0
        },
        {
          "task": "history-4-2",
          "complete_delta": 0,
          "mrr_delta": 0
        },
        {
          "task": "paraphrase-4-2",
          "complete_delta": 0,
          "mrr_delta": 0.5
        },
        {
          "task": "paraphrase-4-1",
          "complete_delta": 0,
          "mrr_delta": 0.5
        },
        {
          "task": "history-3-1",
          "complete_delta": 0,
          "mrr_delta": 0
        },
        {
          "task": "exact-4-1",
          "complete_delta": 0,
          "mrr_delta": 0.75
        },
        {
          "task": "history-4-1",
          "complete_delta": 0,
          "mrr_delta": 0.6666666666666667
        },
        {
          "task": "conflict-4-2",
          "complete_delta": -1,
          "mrr_delta": -0.25
        },
        {
          "task": "multihop-4-2",
          "complete_delta": 0,
          "mrr_delta": 0.20833333333333331
        },
        {
          "task": "paraphrase-3-1",
          "complete_delta": 0,
          "mrr_delta": 0.75
        },
        {
          "task": "conflict-3-2",
          "complete_delta": 1,
          "mrr_delta": 1.0
        },
        {
          "task": "multihop-3-2",
          "complete_delta": 0,
          "mrr_delta": 0.07500000000000001
        },
        {
          "task": "history-3-2",
          "complete_delta": 0,
          "mrr_delta": 0
        },
        {
          "task": "exact-3-2",
          "complete_delta": 0,
          "mrr_delta": 0.0
        },
        {
          "task": "paraphrase-3-2",
          "complete_delta": 0,
          "mrr_delta": 0.33333333333333337
        },
        {
          "task": "conflict-3-1",
          "complete_delta": 0,
          "mrr_delta": 0.0
        },
        {
          "task": "conflict-4-1",
          "complete_delta": 0,
          "mrr_delta": 0.0
        }
      ]
    },
    "B-flat": {
      "complete": 14,
      "mrr": 0.5808333333333333,
      "changes": [
        {
          "task": "exact-3-2",
          "complete_delta": 0,
          "mrr_delta": 0.0
        },
        {
          "task": "multihop-3-2",
          "complete_delta": 0,
          "mrr_delta": 0.05714285714285716
        },
        {
          "task": "conflict-4-1",
          "complete_delta": 0,
          "mrr_delta": 0.0
        },
        {
          "task": "multihop-4-2",
          "complete_delta": 1,
          "mrr_delta": 0.3333333333333333
        },
        {
          "task": "history-4-2",
          "complete_delta": 0,
          "mrr_delta": 0
        },
        {
          "task": "conflict-3-2",
          "complete_delta": 1,
          "mrr_delta": 1.0
        },
        {
          "task": "conflict-4-2",
          "complete_delta": -1,
          "mrr_delta": -0.25
        },
        {
          "task": "paraphrase-4-2",
          "complete_delta": 0,
          "mrr_delta": 0.5
        },
        {
          "task": "history-3-2",
          "complete_delta": 0,
          "mrr_delta": 0
        },
        {
          "task": "paraphrase-3-2",
          "complete_delta": 0,
          "mrr_delta": 0.33333333333333337
        },
        {
          "task": "conflict-3-1",
          "complete_delta": 0,
          "mrr_delta": 0.0
        },
        {
          "task": "history-3-1",
          "complete_delta": 0,
          "mrr_delta": 0
        },
        {
          "task": "exact-4-2",
          "complete_delta": 0,
          "mrr_delta": 0.16666666666666666
        },
        {
          "task": "multihop-4-1",
          "complete_delta": 0,
          "mrr_delta": 0.8571428571428572
        },
        {
          "task": "paraphrase-3-1",
          "complete_delta": 0,
          "mrr_delta": 0.75
        },
        {
          "task": "paraphrase-4-1",
          "complete_delta": 0,
          "mrr_delta": 0.5
        },
        {
          "task": "multihop-3-1",
          "complete_delta": 0,
          "mrr_delta": 0
        },
        {
          "task": "history-4-1",
          "complete_delta": 0,
          "mrr_delta": 0.6666666666666667
        },
        {
          "task": "exact-4-1",
          "complete_delta": 0,
          "mrr_delta": 0.8571428571428572
        },
        {
          "task": "exact-3-1",
          "complete_delta": 0,
          "mrr_delta": 0.0
        }
      ]
    },
    "C-flat": {
      "complete": 14,
      "mrr": 0.5808333333333333,
      "changes": [
        {
          "task": "history-3-2",
          "complete_delta": 0,
          "mrr_delta": 0
        },
        {
          "task": "multihop-3-2",
          "complete_delta": 0,
          "mrr_delta": 0.05714285714285716
        },
        {
          "task": "conflict-4-2",
          "complete_delta": -1,
          "mrr_delta": -0.25
        },
        {
          "task": "multihop-3-1",
          "complete_delta": 0,
          "mrr_delta": 0
        },
        {
          "task": "multihop-4-2",
          "complete_delta": 1,
          "mrr_delta": 0.3333333333333333
        },
        {
          "task": "exact-3-1",
          "complete_delta": 0,
          "mrr_delta": 0.0
        },
        {
          "task": "history-3-1",
          "complete_delta": 0,
          "mrr_delta": 0
        },
        {
          "task": "paraphrase-4-2",
          "complete_delta": 0,
          "mrr_delta": 0.5
        },
        {
          "task": "paraphrase-3-1",
          "complete_delta": 0,
          "mrr_delta": 0.75
        },
        {
          "task": "conflict-3-2",
          "complete_delta": 1,
          "mrr_delta": 1.0
        },
        {
          "task": "exact-3-2",
          "complete_delta": 0,
          "mrr_delta": 0.0
        },
        {
          "task": "conflict-3-1",
          "complete_delta": 0,
          "mrr_delta": 0.0
        },
        {
          "task": "multihop-4-1",
          "complete_delta": 0,
          "mrr_delta": 0.8571428571428572
        },
        {
          "task": "history-4-1",
          "complete_delta": 0,
          "mrr_delta": 0.6666666666666667
        },
        {
          "task": "exact-4-2",
          "complete_delta": 0,
          "mrr_delta": 0.16666666666666666
        },
        {
          "task": "history-4-2",
          "complete_delta": 0,
          "mrr_delta": 0
        },
        {
          "task": "paraphrase-3-2",
          "complete_delta": 0,
          "mrr_delta": 0.33333333333333337
        },
        {
          "task": "exact-4-1",
          "complete_delta": 0,
          "mrr_delta": 0.8571428571428572
        },
        {
          "task": "conflict-4-1",
          "complete_delta": 0,
          "mrr_delta": 0.0
        },
        {
          "task": "paraphrase-4-1",
          "complete_delta": 0,
          "mrr_delta": 0.5
        }
      ]
    },
    "D-flat": {
      "complete": 13,
      "mrr": 0.5308333333333334,
      "changes": [
        {
          "task": "exact-4-1",
          "complete_delta": 0,
          "mrr_delta": 0
        },
        {
          "task": "multihop-3-1",
          "complete_delta": 0,
          "mrr_delta": 0
        },
        {
          "task": "multihop-3-2",
          "complete_delta": 0,
          "mrr_delta": 0.05714285714285716
        },
        {
          "task": "multihop-4-2",
          "complete_delta": 1,
          "mrr_delta": 0.3333333333333333
        },
        {
          "task": "exact-3-1",
          "complete_delta": 0,
          "mrr_delta": 0.0
        },
        {
          "task": "multihop-4-1",
          "complete_delta": 0,
          "mrr_delta": 0.8571428571428572
        },
        {
          "task": "conflict-3-1",
          "complete_delta": 0,
          "mrr_delta": 0.0
        },
        {
          "task": "conflict-3-2",
          "complete_delta": 1,
          "mrr_delta": 1.0
        },
        {
          "task": "paraphrase-3-2",
          "complete_delta": 0,
          "mrr_delta": 0.33333333333333337
        },
        {
          "task": "conflict-4-2",
          "complete_delta": -1,
          "mrr_delta": -0.25
        },
        {
          "task": "exact-3-2",
          "complete_delta": 0,
          "mrr_delta": 0.0
        },
        {
          "task": "paraphrase-4-2",
          "complete_delta": 0,
          "mrr_delta": 0.5
        },
        {
          "task": "conflict-4-1",
          "complete_delta": 0,
          "mrr_delta": 0.0
        },
        {
          "task": "history-4-2",
          "complete_delta": 0,
          "mrr_delta": 0
        },
        {
          "task": "history-3-1",
          "complete_delta": 0,
          "mrr_delta": 0
        },
        {
          "task": "history-4-1",
          "complete_delta": 0,
          "mrr_delta": 0.6666666666666667
        },
        {
          "task": "exact-4-2",
          "complete_delta": 0,
          "mrr_delta": 0.16666666666666666
        },
        {
          "task": "history-3-2",
          "complete_delta": 0,
          "mrr_delta": 0
        },
        {
          "task": "paraphrase-4-1",
          "complete_delta": 0,
          "mrr_delta": 0.5
        },
        {
          "task": "paraphrase-3-1",
          "complete_delta": 0,
          "mrr_delta": 0.75
        }
      ]
    }
  }
}

Added processing and worker memory are measured independently; composed E2E is not a direct full-system reranking measurement. No threshold was tuned.

## Limits and proposed split

No production modules or dependencies are removed. Keep Relate persistence and application source/binding/visibility/replay/confidence/approval/budget semantics. Native partitions are not built-in authorization. Automatic conflict discovery, trusted shared publication, full canonical-memory projection, native evidence replay/retraction, device faults, remote server and full cold CLI recovery remain unsupported adoption gates.

A source digest establishes identity, not truth. Human labels and actual generative outcomes remain unreviewed/NOT RUN. The 64 formulations represent only 32 families and a small public-document corpus. No claim generalizes to untested database versions, configurations or project populations.

Performance uses fresh processes and static prepared generations, one serialized offline model and separate reader connections. It includes inference, DB/transport, validation and complete rendering, excluding live canonical refresh. Cooperative 2 GiB RSS checks run after setup and during queries, not an OS hard limit. 180 s query and 300 s outer limits are retained. RSS samples can miss peaks, CPU counts may omit unwaited descendants. Working disk excludes shared runtimes/model/distribution; environment metadata records those separately. Failed profiles have no adoption percentiles. One hosted run/profile is not an independent multi-host replication.

The original offline CLI and all baselines are unchanged. Any adoption needs completed correctness integrations, actual independent review, the registered noninferiority/speed/RSS thresholds and new held-out data before further tuning. Rollback is simply the unchanged production path.
