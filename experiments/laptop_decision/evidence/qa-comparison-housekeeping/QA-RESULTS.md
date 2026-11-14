# Fixed-context QA: original and corrected model-assisted review

Model-assisted review by claude-opus-5-5, **not independent human review**. Labels are model-authored and unreviewed. Primary score: positives 1 / .5 / 0 for correct / partial / incorrect; unknown controls 1 if the answer warrantedly declines. Paired differences average the three repetitions within each task, then bootstrap over tasks (descriptive 95%).

## original_registered

| Class | Arm | Answers | Mean score | Correct / partial / incorrect / n.a. | Warranted unknown | Answers with unsupported claims | Citation correct / incorrect / none |
|---|---|---:|---:|---|---:|---:|---|
| natural-language | none | 60 | 0.0 | 0 / 0 / 56 / 4 | 0 | 0 | 0 / 0 / 60 |
| natural-language | legacy-hybrid | 60 | 0.85 | 48 / 6 / 5 / 1 | 0 | 4 | 60 / 0 / 0 |
| natural-language | grounded-flat | 60 | 0.875 | 51 / 3 / 6 / 0 | 0 | 1 | 60 / 0 / 0 |
| natural-language | grounded-relate | 60 | 0.875 | 51 / 3 / 4 / 2 | 0 | 2 | 60 / 0 / 0 |
| historical | none | 12 | 0.0 | 0 / 0 / 12 / 0 | 0 | 0 | 0 / 0 / 12 |
| historical | legacy-hybrid | 12 | 0.875 | 9 / 3 / 0 / 0 | 0 | 2 | 12 / 0 / 0 |
| historical | grounded-flat | 12 | 0.8333 | 8 / 4 / 0 / 0 | 0 | 3 | 12 / 0 / 0 |
| historical | grounded-relate | 12 | 0.875 | 9 / 3 / 0 / 0 | 0 | 0 | 12 / 0 / 0 |
| explicit-source | none | 18 | 0.0 | 0 / 0 / 18 / 0 | 0 | 0 | 0 / 0 / 18 |
| explicit-source | legacy-hybrid | 18 | 0.6667 | 9 / 6 / 3 / 0 | 0 | 0 | 17 / 1 / 0 |
| explicit-source | grounded-flat | 18 | 1.0 | 18 / 0 / 0 / 0 | 0 | 0 | 18 / 0 / 0 |
| explicit-source | grounded-relate | 18 | 1.0 | 18 / 0 / 0 / 0 | 0 | 0 | 18 / 0 / 0 |
| unknown-control | none | 18 | 1.0 | 0 / 0 / 0 / 18 | 18 | 0 | 0 / 0 / 18 |
| unknown-control | legacy-hybrid | 18 | 1.0 | 0 / 0 / 0 / 18 | 18 | 6 | 11 / 6 / 1 |
| unknown-control | grounded-flat | 18 | 1.0 | 0 / 0 / 0 / 18 | 18 | 17 | 8 / 8 / 2 |
| unknown-control | grounded-relate | 18 | 1.0 | 0 / 0 / 0 / 18 | 18 | 18 | 7 / 10 / 1 |
| all-positive | none | 90 | 0.0 | 0 / 0 / 86 / 4 | 0 | 0 | 0 / 0 / 90 |
| all-positive | legacy-hybrid | 90 | 0.8167 | 66 / 15 / 8 / 1 | 0 | 6 | 89 / 1 / 0 |
| all-positive | grounded-flat | 90 | 0.8944 | 77 / 7 / 6 / 0 | 0 | 4 | 90 / 0 / 0 |
| all-positive | grounded-relate | 90 | 0.9 | 78 / 6 / 4 / 2 | 0 | 2 | 90 / 0 / 0 |
| all | none | 108 | 0.1667 | 0 / 0 / 86 / 22 | 18 | 0 | 0 / 0 / 108 |
| all | legacy-hybrid | 108 | 0.8472 | 66 / 15 / 8 / 19 | 18 | 12 | 100 / 7 / 1 |
| all | grounded-flat | 108 | 0.912 | 77 / 7 / 6 / 18 | 18 | 21 | 98 / 8 / 2 |
| all | grounded-relate | 108 | 0.9167 | 78 / 6 / 4 / 20 | 18 | 20 | 97 / 10 / 1 |

| Class | Arm vs grounded-flat | Tasks | Mean task diff | 95% task bootstrap | Better / worse tasks |
|---|---|---:|---:|---|---|
| natural-language | none | 20 | -0.875 | [-1.0, -0.725] | 0 / 18 |
| natural-language | legacy-hybrid | 20 | -0.025 | [-0.075, 0.0] | 0 / 1 |
| natural-language | grounded-relate | 20 | 0.0 | [0.0, 0.0] | 0 / 0 |
| historical | none | 4 | -0.8333 | [-1.0, -0.625] | 0 / 4 |
| historical | legacy-hybrid | 4 | 0.0417 | [0.0, 0.125] | 1 / 0 |
| historical | grounded-relate | 4 | 0.0417 | [0.0, 0.125] | 1 / 0 |
| explicit-source | none | 6 | -1.0 | [-1.0, -1.0] | 0 / 6 |
| explicit-source | legacy-hybrid | 6 | -0.3333 | [-0.6667, -0.0833] | 0 / 3 |
| explicit-source | grounded-relate | 6 | 0.0 | [0.0, 0.0] | 0 / 0 |
| unknown-control | none | 6 | 0.0 | [0.0, 0.0] | 0 / 0 |
| unknown-control | legacy-hybrid | 6 | 0.0 | [0.0, 0.0] | 0 / 0 |
| unknown-control | grounded-relate | 6 | 0.0 | [0.0, 0.0] | 0 / 0 |
| all-positive | none | 30 | -0.8944 | [-0.9833, -0.7889] | 0 / 28 |
| all-positive | legacy-hybrid | 30 | -0.0778 | [-0.1778, -0.0056] | 1 / 4 |
| all-positive | grounded-relate | 30 | 0.0056 | [0.0, 0.0167] | 1 / 0 |

## corrected_amendment_2

| Class | Arm | Answers | Mean score | Correct / partial / incorrect / n.a. | Warranted unknown | Answers with unsupported claims | Citation correct / incorrect / none |
|---|---|---:|---:|---|---:|---:|---|
| natural-language | none | 60 | 0.0 | 0 / 0 / 58 / 2 | 0 | 0 | 0 / 0 / 60 |
| natural-language | legacy-hybrid | 60 | 0.85 | 48 / 6 / 5 / 1 | 0 | 2 | 60 / 0 / 0 |
| natural-language | grounded-flat | 60 | 0.875 | 51 / 3 / 5 / 1 | 0 | 2 | 60 / 0 / 0 |
| natural-language | grounded-relate | 60 | 0.8833 | 51 / 4 / 5 / 0 | 0 | 1 | 59 / 1 / 0 |
| historical | none | 12 | 0.0 | 0 / 0 / 11 / 1 | 0 | 0 | 0 / 0 / 12 |
| historical | legacy-hybrid | 12 | 0.875 | 9 / 3 / 0 / 0 | 0 | 1 | 12 / 0 / 0 |
| historical | grounded-flat | 12 | 0.875 | 9 / 3 / 0 / 0 | 0 | 1 | 12 / 0 / 0 |
| historical | grounded-relate | 12 | 0.875 | 9 / 3 / 0 / 0 | 0 | 0 | 12 / 0 / 0 |
| explicit-source | none | 18 | 0.0 | 0 / 0 / 18 / 0 | 0 | 0 | 0 / 0 / 18 |
| explicit-source | legacy-hybrid | 18 | 0.6667 | 9 / 6 / 2 / 1 | 0 | 0 | 17 / 1 / 0 |
| explicit-source | grounded-flat | 18 | 1.0 | 18 / 0 / 0 / 0 | 0 | 0 | 18 / 0 / 0 |
| explicit-source | grounded-relate | 18 | 1.0 | 18 / 0 / 0 / 0 | 0 | 0 | 18 / 0 / 0 |
| unknown-control | none | 18 | 1.0 | 0 / 0 / 0 / 18 | 18 | 0 | 0 / 0 / 18 |
| unknown-control | legacy-hybrid | 18 | 1.0 | 0 / 0 / 0 / 18 | 18 | 0 | 16 / 0 / 2 |
| unknown-control | grounded-flat | 18 | 1.0 | 0 / 0 / 0 / 18 | 18 | 0 | 15 / 0 / 3 |
| unknown-control | grounded-relate | 18 | 1.0 | 0 / 0 / 0 / 18 | 18 | 0 | 14 / 0 / 4 |
| all-positive | none | 90 | 0.0 | 0 / 0 / 87 / 3 | 0 | 0 | 0 / 0 / 90 |
| all-positive | legacy-hybrid | 90 | 0.8167 | 66 / 15 / 7 / 2 | 0 | 3 | 89 / 1 / 0 |
| all-positive | grounded-flat | 90 | 0.9 | 78 / 6 / 5 / 1 | 0 | 3 | 90 / 0 / 0 |
| all-positive | grounded-relate | 90 | 0.9056 | 78 / 7 / 5 / 0 | 0 | 1 | 89 / 1 / 0 |
| all | none | 108 | 0.1667 | 0 / 0 / 87 / 21 | 18 | 0 | 0 / 0 / 108 |
| all | legacy-hybrid | 108 | 0.8472 | 66 / 15 / 7 / 20 | 18 | 3 | 105 / 1 / 2 |
| all | grounded-flat | 108 | 0.9167 | 78 / 6 / 5 / 19 | 18 | 3 | 105 / 0 / 3 |
| all | grounded-relate | 108 | 0.9213 | 78 / 7 / 5 / 18 | 18 | 1 | 103 / 1 / 4 |

| Class | Arm vs grounded-flat | Tasks | Mean task diff | 95% task bootstrap | Better / worse tasks |
|---|---|---:|---:|---|---|
| natural-language | none | 20 | -0.875 | [-1.0, -0.725] | 0 / 18 |
| natural-language | legacy-hybrid | 20 | -0.025 | [-0.075, 0.0] | 0 / 1 |
| natural-language | grounded-relate | 20 | 0.0083 | [0.0, 0.025] | 1 / 0 |
| historical | none | 4 | -0.875 | [-1.0, -0.625] | 0 / 4 |
| historical | legacy-hybrid | 4 | 0.0 | [0.0, 0.0] | 0 / 0 |
| historical | grounded-relate | 4 | 0.0 | [0.0, 0.0] | 0 / 0 |
| explicit-source | none | 6 | -1.0 | [-1.0, -1.0] | 0 / 6 |
| explicit-source | legacy-hybrid | 6 | -0.3333 | [-0.6667, -0.0833] | 0 / 3 |
| explicit-source | grounded-relate | 6 | 0.0 | [0.0, 0.0] | 0 / 0 |
| unknown-control | none | 6 | 0.0 | [0.0, 0.0] | 0 / 0 |
| unknown-control | legacy-hybrid | 6 | 0.0 | [0.0, 0.0] | 0 / 0 |
| unknown-control | grounded-relate | 6 | 0.0 | [0.0, 0.0] | 0 / 0 |
| all-positive | none | 30 | -0.9 | [-0.9833, -0.8] | 0 / 28 |
| all-positive | legacy-hybrid | 30 | -0.0833 | [-0.1833, -0.0167] | 0 / 4 |
| all-positive | grounded-relate | 30 | 0.0056 | [0.0, 0.0167] | 1 / 0 |

## Usage and reported cost

```json
{
 "answerer": {
  "calls": 432,
  "errors": 0,
  "resolved_models": [
   "claude-sonnet-5-5"
  ],
  "input_tokens": 1972,
  "cache_read_input_tokens": 1477098,
  "cache_creation_input_tokens": 692762,
  "output_tokens": 279026,
  "reported_list_cost_usd": 5.713,
  "cost_basis": [
   "list"
  ],
  "elapsed_p50_ms": 8110.409593999975,
  "elapsed_p95_ms": 13195.892968249836,
  "note": "Reported list-price estimates from the CLI result event; not an invoice. Actual subscription billing is unknown."
 },
 "grader_original": {
  "calls": 432,
  "errors": 0,
  "resolved_models": [
   "claude-opus-5-5"
  ],
  "input_tokens": 874,
  "cache_read_input_tokens": 484036,
  "cache_creation_input_tokens": 1438444,
  "output_tokens": 161558,
  "reported_list_cost_usd": 14.839,
  "cost_basis": [
   "list"
  ],
  "elapsed_p50_ms": 4947.324578999542,
  "elapsed_p95_ms": 6971.419544050696,
  "note": "Reported list-price estimates from the CLI result event; not an invoice. Actual subscription billing is unknown."
 },
 "grader_corrected": {
  "calls": 433,
  "errors": 1,
  "resolved_models": [
   "claude-opus-5-5"
  ],
  "input_tokens": 882,
  "cache_read_input_tokens": 506135,
  "cache_creation_input_tokens": 1498350,
  "output_tokens": 157055,
  "reported_list_cost_usd": 15.2327,
  "cost_basis": [
   "list"
  ],
  "elapsed_p50_ms": 4903.297640998062,
  "elapsed_p95_ms": 6959.229231799686,
  "note": "Reported list-price estimates from the CLI result event; not an invoice. Actual subscription billing is unknown."
 }
}
```

