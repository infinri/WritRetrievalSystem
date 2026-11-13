"""Integration checks against the real embedded Relate engine."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from writ_retrieval.cli import DEMO_PATH, context_for_path, seed_demo


class RelateIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Path(self.temp.name) / "graph"

    def test_context_survives_a_separate_process(self):
        subprocess.run(
            [sys.executable, "-m", "writ_retrieval.cli", "init-demo", "--store", str(self.store)],
            check=True, capture_output=True, text=True,
        )
        output = subprocess.run(
            [sys.executable, "-m", "writ_retrieval.cli", "context", DEMO_PATH, "--store", str(self.store)],
            check=True, capture_output=True, text=True,
        )
        rows = json.loads(output.stdout)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["decision_id"], "DEC-001")
        self.assertEqual(rows[0]["rule_id"], "PARAM-001")
        self.assertEqual(rows[0]["commit_id"], "COMMIT-001")
        self.assertIn("Parameterize", rows[0]["rationale"])

    def test_seed_can_be_repeated_without_duplicate_context(self):
        seed_demo(self.store)
        seed_demo(self.store)
        self.assertEqual(len(context_for_path(self.store, DEMO_PATH)), 1)

    def test_unknown_path_and_other_project_return_no_context(self):
        seed_demo(self.store)
        self.assertEqual(context_for_path(self.store, "src/unknown.py"), [])
        self.assertEqual(context_for_path(self.store, DEMO_PATH, "other-project"), [])

    def test_missing_store_is_not_silently_created_by_query(self):
        with self.assertRaises(FileNotFoundError):
            context_for_path(self.store, DEMO_PATH)
        self.assertFalse(self.store.exists())


if __name__ == "__main__":
    unittest.main()
