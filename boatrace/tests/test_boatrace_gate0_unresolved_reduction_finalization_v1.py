from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "research" / "gate0_unresolved_reduction_v1"


class Gate0UnresolvedReductionFinalizationV1Test(unittest.TestCase):
    def test_persisted_validation_is_post_manifest_and_valid(self) -> None:
        validation = json.loads(
            (PACKAGE / "gate0_unresolved_reduction_validation_v1.json").read_text(encoding="utf-8")
        )
        self.assertTrue(validation["valid"])
        self.assertEqual(validation["errors"], [])
        self.assertFalse(validation["manifest_pending_at_validation_write"])
        self.assertEqual(validation["validation_phase"], "post_manifest_finalization")
        self.assertEqual(validation["artifact_hash_mismatch_count"], 0)
        self.assertEqual(validation["protected_anchor_mismatch_count"], 0)


if __name__ == "__main__":
    unittest.main()
