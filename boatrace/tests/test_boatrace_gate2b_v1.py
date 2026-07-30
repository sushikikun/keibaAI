from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Gate2BBaselineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        script = ROOT / "scripts" / "boatrace_gate2b_validate_v1.py"
        p = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, check=True)
        cls.result = json.loads(p.stdout)

    def test_validation_passed(self):
        self.assertTrue(self.result["passed"], self.result)

    def test_evaluation_count_and_contract(self):
        self.assertEqual(self.result["evaluation_count"], 12822)
        self.assertTrue(self.result["probability_contract_passed"])

    def test_isolation_and_anchor(self):
        self.assertTrue(self.result["confirmation_access_zero"])
        self.assertTrue(self.result["final_lock_access_zero"])
        self.assertTrue(self.result["protected_anchor_difference_zero"])


if __name__ == "__main__":
    unittest.main()
