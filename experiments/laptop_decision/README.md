# Laptop architecture validation

**Proposed decision (not owner-approved):** recommend grounded flat
(`grounded_cli`, backend omitted) for the local hackathon workflow. Relate
remains the persistence layer, native Relate retrieval stays an opt-in profile,
and no Neo4j profile is adopted. No CLI behavior is changed and no production
code, dependency or baseline is removed.

- [ADR](ADR.md) with tradeoffs, the responsibility split, reconsideration
  triggers and rollback
- [Findings](FINDINGS.md) with all measured results and limitations
- [Registered protocol](PROTOCOL.md) with Amendment 1 (setup error) and
  Amendment 2 (grader correction)
- [Decision summary JSON](evidence/decision-summary.json) and the
  [bake-off report on laptop data](evidence/bakeoff-report/FINDINGS.md)
- [QA trial results, original and corrected](evidence/qa-comparison/QA-RESULTS.md),
  [raw trials](evidence/qa-trials/) and [blinded human-review materials](evidence/qa-human-review/README.md)
- Container: [docker/](docker/). The reproduction commands are in PROTOCOL.md.

Labels are model-authored and unreviewed. Answer review is model-assisted, not
human review. Fixed-context QA is not a tool-calling or repository-editing
agent experiment. Earlier experiments in `experiments/db_offload/` and
`experiments/reliable_memory/` are unchanged (403 preservation hashes verified).
