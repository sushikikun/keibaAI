from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
IMPORTER = ROOT / "scripts" / "import_chatgpt_equipment_generation_official_evidence_v1.py"
FINAL = ROOT / "research" / "equipment_generation_official_evidence_import_v1"


class ChatGPTEquipmentGenerationOfficialEvidenceImportV1Test(unittest.TestCase):
    def test_final_sidecar_validates_and_is_proposal_only(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(IMPORTER), "--validate"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        result = json.loads(completed.stdout)
        self.assertTrue(result["valid"])
        self.assertEqual(result["artifact_hash_mismatch_count"], 0)
        self.assertEqual(result["protected_anchor_difference_count"], 0)
        self.assertEqual(result["generation_id_issued_count"], 0)

    def test_persisted_counts_and_non_materialization(self) -> None:
        validation = json.loads(
            (FINAL / "equipment_generation_import_validation_v1.json").read_text(encoding="utf-8")
        )
        self.assertTrue(validation["passed"])
        self.assertEqual(validation["counts"]["local_batch_count"], 48)
        self.assertEqual(validation["counts"]["local_equipment_key_count"], 3240)
        self.assertEqual(validation["counts"]["local_hypothesis_count"], 33)
        self.assertEqual(validation["counts"]["boundary_candidates"], 54)
        self.assertEqual(validation["counts"]["unresolved_batch_periods"], 46)
        self.assertEqual(validation["counts"]["generation_id_issued_count"], 0)
        self.assertTrue(validation["checks"]["no_C_or_D_boundary_candidates"])


if __name__ == "__main__":
    unittest.main()
