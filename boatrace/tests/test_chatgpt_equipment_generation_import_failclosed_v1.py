from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import import_chatgpt_equipment_generation_official_evidence_v1 as base  # noqa: E402


class FailClosedImportTest(unittest.TestCase):
    @staticmethod
    def package() -> dict:
        return base.validate_package(base.STAGING)

    def copied_stage(self) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        temporary = tempfile.TemporaryDirectory()
        stage = Path(temporary.name)
        shutil.copytree(base.STAGING / base.PACKAGE_ROOT, stage / base.PACKAGE_ROOT)
        return temporary, stage

    def test_wrong_zip_hash_is_rejected_before_extraction(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bad_zip = root / base.ZIP_NAME
            bad_zip.write_bytes(b"not the expected ZIP")
            with (
                patch.object(base, "FINAL", root / "final"),
                patch.object(base, "STAGING", root / "staging"),
                patch.object(base, "BUILD", root / "build"),
                patch.object(base, "locate_zip", return_value=bad_zip),
            ):
                with self.assertRaisesRegex(ValueError, "ZIP SHA-256 mismatch"):
                    base.build()

    def test_internal_manifest_hash_mismatch_is_rejected(self) -> None:
        temporary, stage = self.copied_stage()
        try:
            manifest = stage / base.PACKAGE_ROOT / "equipment_generation_official_evidence_manifest_v1.json"
            manifest.write_bytes(manifest.read_bytes() + b"\n")
            with self.assertRaisesRegex(ValueError, "internal manifest SHA-256 mismatch"):
                base.validate_package(stage)
        finally:
            temporary.cleanup()

    def test_declared_package_file_hash_mismatch_is_rejected(self) -> None:
        temporary, stage = self.copied_stage()
        try:
            changed = stage / base.PACKAGE_ROOT / "manual_followup_queue_v1.csv"
            changed.write_bytes(changed.read_bytes() + b"\n")
            with self.assertRaisesRegex(ValueError, "package artifact hashes mismatch"):
                base.validate_package(stage)
        finally:
            temporary.cleanup()

    def test_local_input_hash_mismatch_is_rejected(self) -> None:
        package = self.package()
        with tempfile.TemporaryDirectory() as directory:
            changed_batch = Path(directory) / "equipment_evidence_batch_queue_v1.csv"
            local = base.local_paths()
            shutil.copyfile(local[changed_batch.name], changed_batch)
            changed_batch.write_bytes(changed_batch.read_bytes() + b"\n")
            altered = dict(local)
            altered[changed_batch.name] = changed_batch
            with patch.object(base, "local_paths", return_value=altered):
                with self.assertRaisesRegex(ValueError, "local input reconciliation mismatch"):
                    base.local_input_reconciliation(package)

    def test_missing_batch_equipment_key_and_hypothesis_id_are_rejected(self) -> None:
        package = self.package()
        local = base.local_paths()
        for filename in [
            "equipment_evidence_batch_queue_v1.csv",
            "equipment_generation_evidence_registry_v1.csv",
            "hypothesis_execution_readiness_v1.csv",
        ]:
            with self.subTest(filename=filename), tempfile.TemporaryDirectory() as directory:
                changed = Path(directory) / filename
                source_rows = base.read_csv(local[filename])
                base.write_csv(changed, list(source_rows[0]), source_rows[:-1])
                altered = dict(local)
                altered[filename] = changed
                with patch.object(base, "local_paths", return_value=altered):
                    with self.assertRaisesRegex(ValueError, "local input reconciliation mismatch"):
                        base.local_input_reconciliation(package)

    def test_c_or_d_candidate_cannot_be_formally_issued(self) -> None:
        package = self.package()
        candidates = package["candidates"]
        self.assertTrue(all(row["boundary_confidence"] in {"A", "B"} for row in candidates))
        self.assertTrue(all(row["generation_id_issued"] == "false" for row in candidates))

    def test_candidate_overlap_is_detected(self) -> None:
        rows = [
            {
                "venue_code": "01",
                "equipment_type": "motor",
                "generation_start_date": "2024-01-01",
                "generation_end_date_if_known": "2024-12-31",
                "candidate_id": "first",
            },
            {
                "venue_code": "01",
                "equipment_type": "motor",
                "generation_start_date": "2024-12-31",
                "generation_end_date_if_known": "",
                "candidate_id": "second",
            },
        ]
        self.assertEqual(base.candidate_overlap_errors(rows), ["('01', 'motor'):first:second"])

    def test_existing_final_folder_conflict_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            final = root / "conflicting_final"
            final.mkdir()
            with patch.object(base, "FINAL", final):
                with self.assertRaises(FileNotFoundError):
                    base.build()

    def test_identical_reimport_is_idempotent_and_protected(self) -> None:
        result = base.build()
        self.assertTrue(result["valid"])
        self.assertEqual(result["import_status"], "already_installed_identical")
        self.assertEqual(result["protected_anchor_difference_count"], 0)
        self.assertEqual(result["generation_id_issued_count"], 0)


if __name__ == "__main__":
    unittest.main()
