# Evaluation housekeeping (deterministic; no model calls)

These three repairs were made in a later PR (the Rust/Relate application). They rerun only
deterministic code over committed trial and review outputs. No paid model trial or grading
call was repeated. Every original artifact stays byte-identical: `qa-human-review/`,
`qa-model-review*/`, `qa-comparison/` and `qa-summary-original/` are untouched, and
`grade.py materials --context stripped` still reproduces the original `human-review.csv`
byte-for-byte.

1. **Full-context human-review packets:** `evidence/qa-human-review-full-context/`
   (`grade.py materials --context full`). Reviewers see the complete packet each answering
   model received, with only `projection.backend` masked, matching Amendment 2.
2. **Explicit `not_applicable` counts:** `evidence/qa-comparison-housekeeping/` adds
   `answer_correctness_not_applicable`, `gold_content_conveyed_not_applicable`,
   `warranted_unknown_not_applicable` and `positive_answers_marked_not_applicable`. Correct,
   partial and incorrect counts no longer silently omit them. In the corrected review, 0–3
   positive answers per condition were marked not applicable (none 3, legacy 2, flat 1,
   Relate 0).
3. **Unregistered-revision citations:** `evidence/qa-summary-housekeeping/`. Mechanical
   scoring now flags whole-word, revision-like tokens (7–40 lowercase hex characters,
   containing a digit) that are neither a prefix of a registered revision nor present in the
   supplied packet or request. A first version also matched English letters such as
   "cceeded" in "succeeded". That false positive was fixed before publishing. Result: 0
   answers in any condition cite an unregistered revision. 0 cite a revision missing from
   their packet or request.
