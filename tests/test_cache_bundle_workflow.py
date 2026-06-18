from __future__ import annotations

import csv
import json
import zipfile
from datetime import datetime
from pathlib import Path

from nankan_ai.append_batch_log import file_sha256
from nankan_ai.build_cache_bundle import build_cache_bundle
from nankan_ai.export_fetch_job import export_fetch_job
from nankan_ai.import_cache_bundle import import_cache_bundle
from nankan_ai.schema import REQUIRED_COLUMNS


def test_export_fetch_job_excludes_existing_raw_race_ids(tmp_path: Path) -> None:
    raw_path = tmp_path / "raw.csv"
    jobs_dir = tmp_path / "jobs"
    _write_raw(raw_path, "20250908_kawasaki_1")

    result = export_fetch_job(
        track="kawasaki",
        date_from="2025-09-08",
        date_to="2025-09-08",
        race_no_from=1,
        race_no_to=2,
        raw_csv_path=raw_path,
        jobs_dir=jobs_dir,
        cache_html_dir=tmp_path / "cache_html",
        now=datetime(2026, 6, 18, 12, 0, 0),
    )

    assert result.job_id == "job_20260618_120000"
    assert result.race_count == 1
    assert result.raw_sha256_at_export == file_sha256(raw_path)
    rows = _read_csv(result.csv_path)
    assert [row["race_id"] for row in rows] == ["20250908_kawasaki_2"]
    payload = json.loads(result.json_path.read_text(encoding="utf-8"))
    assert payload["race_count"] == 1
    assert payload["race_ids"] == ["20250908_kawasaki_2"]
    assert payload["raw_sha256_at_export"] == file_sha256(raw_path)


def test_build_cache_bundle_includes_html_manifest_job_and_fetch_log(tmp_path: Path) -> None:
    raw_path = tmp_path / "raw.csv"
    _write_raw(raw_path, "20250908_kawasaki_9")
    job = export_fetch_job(
        track="kawasaki",
        date_from="2025-09-08",
        date_to="2025-09-08",
        race_no_from=1,
        race_no_to=1,
        raw_csv_path=raw_path,
        jobs_dir=tmp_path / "jobs",
        cache_html_dir=tmp_path / "cache" / "html",
        job_id="job_fixture",
    )
    html_path = tmp_path / "cache" / "html" / "20250908_kawasaki_1.html"
    html_path.parent.mkdir(parents=True)
    html_path.write_text("<html>race 1</html>", encoding="utf-8")
    fetch_log = tmp_path / "cache" / "metadata" / "fetch_log.csv"
    fetch_log.parent.mkdir(parents=True)
    fetch_log.write_text("race_id,status\n20250908_kawasaki_1,fetched\n", encoding="utf-8")

    result = build_cache_bundle(
        job_id=job.job_id,
        cache_html_dir=html_path.parent,
        bundles_dir=tmp_path / "bundles",
        job_csv_path=job.csv_path,
        job_json_path=job.json_path,
        fetch_log_path=fetch_log,
        now=datetime(2026, 6, 18, 12, 30, 0),
    )

    assert result.html_count == 1
    with zipfile.ZipFile(result.bundle_path) as bundle:
        names = set(bundle.namelist())
        assert "html/20250908_kawasaki_1.html" in names
        assert "manifest.json" in names
        assert "fetch_log.csv" in names
        assert f"jobs/{job.csv_path.name}" in names
        assert f"jobs/{job.json_path.name}" in names
        manifest = json.loads(bundle.read("manifest.json").decode("utf-8"))
    assert manifest["job_id"] == "job_fixture"
    assert manifest["html_files"][0]["race_id"] == "20250908_kawasaki_1"
    assert manifest["html_files"][0]["sha256"] == file_sha256(html_path)


def test_import_cache_bundle_imports_html_and_writes_report(tmp_path: Path) -> None:
    bundle_path = _make_bundle(tmp_path, {"20250908_kawasaki_1": b"<html>race 1</html>"})
    cache_dir = tmp_path / "main_cache"
    imports_dir = tmp_path / "imports"

    result = import_cache_bundle(
        bundle_path,
        cache_html_dir=cache_dir,
        imports_dir=imports_dir,
        now=datetime(2026, 6, 18, 13, 0, 0),
    )

    assert result.is_valid
    assert result.imported == ["20250908_kawasaki_1"]
    assert (cache_dir / "20250908_kawasaki_1.html").read_bytes() == b"<html>race 1</html>"
    assert result.report_path == imports_dir / "import_cache_bundle_20260618_130000.md"
    assert "raw_changed: no" in result.report_path.read_text(encoding="utf-8")


def test_import_cache_bundle_does_not_overwrite_existing_cache(tmp_path: Path) -> None:
    bundle_path = _make_bundle(tmp_path, {"20250908_kawasaki_1": b"<html>new</html>"})
    cache_dir = tmp_path / "main_cache"
    cache_dir.mkdir()
    (cache_dir / "20250908_kawasaki_1.html").write_text("<html>existing</html>", encoding="utf-8")

    result = import_cache_bundle(bundle_path, cache_html_dir=cache_dir, imports_dir=tmp_path / "imports")

    assert result.is_valid
    assert result.imported == []
    assert result.skipped_existing == ["20250908_kawasaki_1"]
    assert (cache_dir / "20250908_kawasaki_1.html").read_text(encoding="utf-8") == "<html>existing</html>"


def test_import_cache_bundle_detects_manifest_missing_html(tmp_path: Path) -> None:
    bundle_path = tmp_path / "missing_html.zip"
    manifest = {
        "html_files": [
            {
                "race_id": "20250908_kawasaki_1",
                "path": "html/20250908_kawasaki_1.html",
                "sha256": "",
            }
        ]
    }
    with zipfile.ZipFile(bundle_path, "w") as bundle:
        bundle.writestr("manifest.json", json.dumps(manifest))

    result = import_cache_bundle(bundle_path, cache_html_dir=tmp_path / "cache", imports_dir=tmp_path / "imports")

    assert not result.is_valid
    assert any("manifest references missing HTML" in error for error in result.errors)
    assert not (tmp_path / "cache").exists()


def test_import_cache_bundle_detects_extra_html_not_in_manifest(tmp_path: Path) -> None:
    bundle_path = tmp_path / "extra_html.zip"
    manifest = {"html_files": []}
    with zipfile.ZipFile(bundle_path, "w") as bundle:
        bundle.writestr("manifest.json", json.dumps(manifest))
        bundle.writestr("html/20250908_kawasaki_1.html", b"<html>extra</html>")

    result = import_cache_bundle(bundle_path, cache_html_dir=tmp_path / "cache", imports_dir=tmp_path / "imports")

    assert result.is_valid
    assert result.imported == []
    assert any("not listed in manifest" in warning for warning in result.warnings)


def test_import_cache_bundle_blocks_zip_slip(tmp_path: Path) -> None:
    bundle_path = tmp_path / "zip_slip.zip"
    with zipfile.ZipFile(bundle_path, "w") as bundle:
        bundle.writestr("manifest.json", json.dumps({"html_files": []}))
        bundle.writestr("../evil.html", b"evil")

    result = import_cache_bundle(bundle_path, cache_html_dir=tmp_path / "cache", imports_dir=tmp_path / "imports")

    assert not result.is_valid
    assert any("unsafe zip path" in error for error in result.errors)
    assert not (tmp_path / "evil.html").exists()


def test_import_cache_bundle_rejects_empty_html(tmp_path: Path) -> None:
    bundle_path = _make_bundle(tmp_path, {"20250908_kawasaki_1": b""})

    result = import_cache_bundle(bundle_path, cache_html_dir=tmp_path / "cache", imports_dir=tmp_path / "imports")

    assert not result.is_valid
    assert any("empty" in error for error in result.errors)
    assert not (tmp_path / "cache" / "20250908_kawasaki_1.html").exists()


def _make_bundle(tmp_path: Path, html_by_race_id: dict[str, bytes]) -> Path:
    bundle_path = tmp_path / "bundle.zip"
    html_files = []
    import hashlib

    for race_id, data in html_by_race_id.items():
        html_files.append(
            {
                "race_id": race_id,
                "path": f"html/{race_id}.html",
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
    manifest = {
        "manifest_version": 1,
        "job_id": "job_fixture",
        "html_files": html_files,
    }
    with zipfile.ZipFile(bundle_path, "w") as bundle:
        bundle.writestr("manifest.json", json.dumps(manifest))
        for race_id, data in html_by_race_id.items():
            bundle.writestr(f"html/{race_id}.html", data)
    return bundle_path


def _write_raw(path: Path, race_id: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {column: "" for column in REQUIRED_COLUMNS}
    row.update(
        {
            "race_id": race_id,
            "date": "2025-09-08",
            "track": "kawasaki",
            "race_no": race_id.rsplit("_", 1)[1],
            "race_name": "Existing Race",
            "distance": "1400",
            "surface": "dirt",
            "field_size": "1",
            "horse_no": "1",
            "gate_no": "1",
            "horse_name": "Existing Horse",
            "age": "4",
            "finish_position": "1",
        }
    )
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REQUIRED_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerow(row)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))

