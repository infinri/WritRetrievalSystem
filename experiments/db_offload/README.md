# Database offloading bake-off

**Final proposal: keep Relate persistence and the application baseline; adopt no
architecture replacement from these experiments.**

- [Findings and decision](FINAL-FINDINGS.md)
- [Executable commands, pins, scope and trust boundaries](RECOVERY-REPLICATION.md)
- [Responsibility matrix](protocol/OWNERSHIP.md) and [zero-removal/rollback audit](REMOVAL-AND-ADOPTION.md)
- [All matched/best quality and 24-profile tables](evidence/recovered-ci/43540148638/FINDINGS.md)
- [Machine-readable results](evidence/recovered-ci/43540148638/summary.json), [supporting checks/oracle/client results](evidence/recovered-ci/43540148638/supporting-summary.json), [comparison curves](evidence/recovered-ci/43540148638/comparison.svg)
- [Pending independent review](evidence/recovered-ci/43540148638/review/README.md) and [attribution](ATTRIBUTION.md)

Primary hosted run 43540148638 finished all 24 registered profiles: eighteen
completed within limits, six failed. Raw per-query/per-profile data, timings,
resources, failures and compression hashes are committed. The restored local
checkpoint is separately archived and remains secondary; its interrupted suite
finished sixteen profiles. Neither source is cherry-picked by speed.

Labels are model-authored and unreviewed. Agent trials are NOT RUN without an
authorized executable generative host/model identity; the actual tool-calling
harness and blind review materials are supplied. Unsupported native integration
gates block adoption. Production CLI/offline controls and Phases 1–3 stay intact.

## Original capability entry point

Experimental namespace; preserves Phases 1–3 and original offline command.
Read `protocol/PROTOCOL.md`, `protocol/OWNERSHIP.md`, `protocol/settings.json`.
Labels are provisional, NOT HUMAN REVIEWED. No winner chosen before testing.

```bash
pip install -e '.[dev]' -r experiments/db_offload/requirements.txt
python -m experiments.db_offload.capability --output data/capability.json \
  --neo4j-home /path/to/neo4j-community-5.26.0
```

The harness owns its Neo4j child process and uses only the literal loopback
endpoint. Use a downloaded/extracted Community distribution; no Docker or paid
credentials required. Original `scripts/offline_run.py` and agent stay intact.
