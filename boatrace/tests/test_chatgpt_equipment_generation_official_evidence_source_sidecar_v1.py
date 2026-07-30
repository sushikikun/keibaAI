from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "imports" / "equipment_generation_official_evidence_v1_staging" / "equipment_generation_official_evidence_v1"
SIDECAR = ROOT / "research" / "equipment_generation_official_evidence_v1"
IMPORT_MANIFEST = ROOT / "research" / "equipment_generation_official_evidence_import_v1" / "equipment_generation_import_manifest_v1.json"


def entries(root: Path) -> dict[str, tuple[int, str]]:
    result: dict[str, tuple[int, str]] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            result[path.relative_to(root).as_posix()] = (
                path.stat().st_size,
                hashlib.sha256(path.read_bytes()).hexdigest(),
            )
    return result


class SourceSidecarTest(unittest.TestCase):
    def test_source_sidecar_is_byte_identical_to_verified_staging(self) -> None:
        self.assertTrue(STAGING.is_dir())
        self.assertTrue(SIDECAR.is_dir())
        self.assertEqual(entries(STAGING), entries(SIDECAR))

    def test_import_manifest_records_the_immutable_source_sidecar(self) -> None:
        manifest = json.loads(IMPORT_MANIFEST.read_text(encoding="utf-8"))
        record = manifest["source_sidecar"]
        self.assertEqual(record["path"], "research/equipment_generation_official_evidence_v1")
        self.assertEqual(record["file_count"], len(entries(SIDECAR)))
        self.assertEqual(record["internal_manifest_sha256"], "420ea33afa6a67ccf2386f89251b610809f183dcf49cb46c7d7e53940bf63554")


if __name__ == "__main__":
    unittest.main()
