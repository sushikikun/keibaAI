from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Gate2BCompletionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        p = subprocess.run([sys.executable, str(ROOT / "scripts" / "boatrace_gate2b_completion_validate_v1.py")], capture_output=True, text=True, check=True)
        cls.result = json.loads(p.stdout)

    def test_completion_passed(self):
        self.assertTrue(self.result["passed"], self.result)

    def test_four_fold_counts(self):
        self.assertEqual(self.result["evaluation_count"], 51232)
        self.assertEqual(sum(self.result["fold_evaluation_counts"].values()), 51232)

    def test_access_and_pilot_protection(self):
        self.assertTrue(self.result["fold1_pilot_status"]["original_artifacts_mutated"] is False)
        self.assertTrue(self.result["fold1_pilot_status"]["valid_as_fold1_pilot"])


if __name__ == "__main__": unittest.main()
