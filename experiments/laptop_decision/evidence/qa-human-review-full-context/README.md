# Blinded response review (pending)

No human has reviewed these responses. `human-review.csv` lists every completed trial in a shuffled order (seed 20261116) without arm or repetition. Fill each rubric column from RUBRIC below, plus your real name/date. Context copies in `human-review-packets.jsonl.gz` are the complete packets each answering model received, with only projection.backend masked (housekeeping fix; matches Amendment 2); an empty context still reveals the no-history condition, and format may hint at legacy vs grounded. Keep `blind-key.json` closed until all rows are complete. Labels are model-authored and unreviewed: record label disagreements in notes.

## Rubric

- **gold_content_conveyed**: Positive task only: does the answer convey the substance of the labelled passage? yes / partial / no; not_applicable for expected-unknown tasks.
- **answer_correctness**: Relative to the labelled passage and supplied context: correct / partially_correct / incorrect / not_applicable (expected-unknown tasks).
- **appropriate_uncertainty**: yes if the answer states unknowns where the supplied context does not warrant an answer (and does not abstain when it does); otherwise no.
- **warranted_unknown**: Expected-unknown task only: does the answer decline to assert the requested content / missing confirmation, or correctly say it is unavailable? yes / no; not_applicable for positive tasks.
- **unsupported_assertions**: Integer: substantive factual claims about the project that are supported neither by the supplied context nor by the label.
- **citation_correctness**: correct (cited source/revision matches supplied evidence for the claims), incorrect, or none (no citation).
