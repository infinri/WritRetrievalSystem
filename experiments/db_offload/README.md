# Database offloading bake-off

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
