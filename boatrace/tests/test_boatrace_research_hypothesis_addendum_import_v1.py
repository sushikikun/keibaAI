from __future__ import annotations

import csv
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
IMPORT_ROOT = ROOT / "research" / "hypothesis_addenda" / "boatrace_research_hypothesis_addendum_v1"
SOURCE_ROOT = IMPORT_ROOT / "source_package" / "boatrace_research_hypothesis_addendum_v1"
STAGING_ROOT = ROOT / "imports" / "boatrace_research_hypothesis_addendum_v1_staging_retry1" / "boatrace_research_hypothesis_addendum_v1"
RUNNER = ROOT / "scripts" / "generate_boatrace_research_hypothesis_addendum_import_v1.py"


def entries(root: Path) -> dict[str, tuple[int, str]]:
    result: dict[str, tuple[int, str]] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            result[path.relative_to(root).as_posix()] = (
                path.stat().st_size,
                hashlib.sha256(path.read_bytes()).hexdigest(),
            )
    return result


def rows(filename: str) -> list[dict[str, str]]:
    with (IMPORT_ROOT / filename).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


class HypothesisAddendumImportTest(unittest.TestCase):
    def test_installed_sidecar_validates_without_writes(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(RUNNER), "--validate"],
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

    def test_source_package_is_byte_identical_to_verified_retry_staging(self) -> None:
        self.assertEqual(entries(SOURCE_ROOT), entries(STAGING_ROOT))
        self.assertEqual(len(entries(SOURCE_ROOT)), 7)

    def test_required_counts_and_non_materialization(self) -> None:
        validation = json.loads((IMPORT_ROOT / "addendum_import_validation_v1.json").read_text(encoding="utf-8"))
        self.assertTrue(validation["passed"])
        self.assertEqual(validation["counts"]["addendum_hypotheses"], 76)
        self.assertEqual(validation["counts"]["formal_hypotheses"], 33)
        self.assertEqual(validation["counts"]["addendum_dag_cycle_count"], 0)
        self.assertEqual(validation["counts"]["orphan_candidate_count"], 0)
        self.assertEqual(validation["counts"]["core_experiment_proposal_count"], 35)
        self.assertEqual(validation["counts"]["protected_anchor_difference_count"], 0)
        self.assertTrue(validation["checks"]["formal_registry_merge_not_applied"])
        self.assertTrue(validation["checks"]["readiness_data_gap_feature_map_not_updated"])

    def test_overlap_classifications_cover_all_addendum_ids(self) -> None:
        review = rows("addendum_overlap_review_v1.csv")
        self.assertEqual(len(review), 76)
        counts = Counter(row["classification"] for row in review)
        self.assertEqual(counts, {
            "new_distinct_hypothesis": 10,
            "variant_of_existing": 60,
            "merge_candidate": 6,
        })
        self.assertTrue(all(row["formal_registry_action"] == "not_applied" for row in review))

    def test_generated_csv_headers_are_unique_and_row_counts_match(self) -> None:
        expected = {
            "addendum_local_reconciliation_v1.csv": 76,
            "addendum_dependency_review_v1.csv": 76,
            "addendum_overlap_review_v1.csv": 76,
            "addendum_core_experiment_proposal_v1.csv": 35,
            "addendum_data_gap_proposal_v1.csv": 76,
            "addendum_readiness_feature_map_proposal_v1.csv": 76,
        }
        for filename, expected_count in expected.items():
            with self.subTest(filename=filename), (IMPORT_ROOT / filename).open(
                "r", encoding="utf-8-sig", newline=""
            ) as handle:
                reader = csv.reader(handle)
                header = next(reader)
                self.assertEqual(len(header), len(set(header)))
                self.assertNotIn("", header)
            self.assertEqual(len(rows(filename)), expected_count)

    def test_declared_source_artifact_tampering_is_rejected(self) -> None:
        sys.path.insert(0, str(ROOT / "scripts"))
        import generate_boatrace_research_hypothesis_addendum_import_v1 as runner

        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            copied = temporary / "boatrace_research_hypothesis_addendum_v1"
            shutil.copytree(SOURCE_ROOT, copied)
            prompt = copied / "codex_import_prompt_boatrace_research_hypothesis_addendum_v1.txt"
            prompt.write_bytes(prompt.read_bytes() + b"\n")
            with self.assertRaisesRegex(ValueError, "artifact hash mismatch"):
                runner.base.validate_package(copied)


if __name__ == "__main__":
    unittest.main()
