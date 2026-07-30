from __future__ import annotations

import csv
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FINAL = ROOT / "research" / "hypothesis_addenda" / "boatrace_research_hypothesis_addendum_v1" / "canonical_adjudication_v1"
SOURCE = FINAL / "source_package" / "boatrace_research_hypothesis_adjudication_v1"
STAGING = ROOT / "imports" / "boatrace_research_hypothesis_adjudication_v1_staging_retry2" / "boatrace_research_hypothesis_adjudication_v1"
RUNNER = ROOT / "scripts" / "generate_boatrace_research_hypothesis_adjudication_import_v1_retry2.py"


def entries(root: Path) -> dict[str, tuple[int, str]]:
    values: dict[str, tuple[int, str]] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            values[path.relative_to(root).as_posix()] = (
                path.stat().st_size,
                hashlib.sha256(path.read_bytes()).hexdigest(),
            )
    return values


class CanonicalAdjudicationImportTest(unittest.TestCase):
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
        self.assertEqual(entries(SOURCE), entries(STAGING))
        self.assertEqual(len(entries(SOURCE)), 19)

    def test_canonical_counts_merges_and_programs(self) -> None:
        validation = json.loads((FINAL / "canonical_adjudication_local_validation_v1.json").read_text(encoding="utf-8"))
        self.assertTrue(validation["passed"])
        self.assertEqual(validation["counts"]["records"], 76)
        self.assertEqual(validation["counts"]["top_level_candidates"], 10)
        self.assertEqual(validation["counts"]["variants"], 60)
        self.assertEqual(validation["counts"]["merged_variants"], 6)
        self.assertEqual(validation["counts"]["merge_decisions"], 6)
        self.assertEqual(validation["counts"]["decision_programs"], 15)
        self.assertEqual(validation["counts"]["program_members"], 35)
        self.assertEqual(validation["counts"]["protected_anchor_difference_count"], 0)
        self.assertTrue(all(validation["checks"].values()))
        self.assertEqual(
            validation["merge_targets"],
            [
                {"source_hypothesis_id": "H061", "canonical_parent_id": "H049"},
                {"source_hypothesis_id": "H062", "canonical_parent_id": "H043"},
                {"source_hypothesis_id": "H078", "canonical_parent_id": "H040"},
                {"source_hypothesis_id": "H082", "canonical_parent_id": "H039"},
                {"source_hypothesis_id": "H099", "canonical_parent_id": "H019"},
                {"source_hypothesis_id": "H101", "canonical_parent_id": "H049"},
            ],
        )

    def test_program_map_assigns_each_core_proposal_once(self) -> None:
        with (SOURCE / "core_proposal_to_program_map_v1.csv").open("r", encoding="utf-8-sig", newline="") as handle:
            mapping = list(csv.DictReader(handle))
        with (SOURCE / "compressed_core_decision_programs_v1.csv").open("r", encoding="utf-8-sig", newline="") as handle:
            programs = list(csv.DictReader(handle))
        self.assertEqual(len(mapping), 35)
        self.assertEqual(len({row["hypothesis_id"] for row in mapping}), 35)
        self.assertEqual(len(programs), 15)
        self.assertEqual(sum(int(row["member_count"]) for row in programs), 35)
        self.assertTrue(all(row["formal_core_registry_action"] == "proposal_only_not_applied" for row in programs))

    def test_protected_anchors_and_source_csv_headers(self) -> None:
        with (FINAL / "protected_anchor_after_v1.csv").open("r", encoding="utf-8-sig", newline="") as handle:
            anchors = list(csv.DictReader(handle))
        self.assertGreater(len(anchors), 11)
        self.assertTrue(all(row["status"] == "unchanged" for row in anchors))
        for path in SOURCE.rglob("*.csv"):
            with self.subTest(path=path.name), path.open("r", encoding="utf-8-sig", newline="") as handle:
                header = next(csv.reader(handle))
                self.assertTrue(header)
                self.assertEqual(len(header), len(set(header)))

    def test_declared_source_artifact_tampering_is_rejected(self) -> None:
        sys.path.insert(0, str(ROOT / "scripts"))
        import generate_boatrace_research_hypothesis_adjudication_import_v1_retry2 as runner

        with tempfile.TemporaryDirectory() as directory:
            copied = Path(directory) / "boatrace_research_hypothesis_adjudication_v1"
            shutil.copytree(SOURCE, copied)
            changed = copied / "codex_import_prompt_canonical_addendum_adjudication_v1.txt"
            changed.write_bytes(changed.read_bytes() + b"\n")
            with self.assertRaisesRegex(ValueError, "artifact hash mismatch"):
                runner.base.validate_package(copied)


if __name__ == "__main__":
    unittest.main()
