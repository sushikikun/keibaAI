from __future__ import annotations

import csv
from pathlib import Path

from nankan_ai.import_manual_html_cache import import_manual_html_cache


def test_import_manual_html_cache_copies_new_files_and_logs(tmp_path: Path) -> None:
    manual_dir = tmp_path / "manual"
    cache_dir = tmp_path / "cache"
    log_path = tmp_path / "metadata" / "manual_import_log.csv"
    manual_dir.mkdir()
    source = manual_dir / "20250908_kawasaki_1.html"
    source.write_text("<html>fixture</html>", encoding="utf-8")

    results = import_manual_html_cache(
        manual_html_dir=manual_dir,
        cache_html_dir=cache_dir,
        log_path=log_path,
    )

    assert len(results) == 1
    assert results[0].status == "imported"
    assert (cache_dir / source.name).read_text(encoding="utf-8") == "<html>fixture</html>"
    log_rows = _read_log(log_path)
    assert len(log_rows) == 1
    assert log_rows[0]["race_id"] == "20250908_kawasaki_1"
    assert log_rows[0]["status"] == "imported"
    assert log_rows[0]["source_sha256"]


def test_import_manual_html_cache_does_not_overwrite_existing_cache(tmp_path: Path) -> None:
    manual_dir = tmp_path / "manual"
    cache_dir = tmp_path / "cache"
    log_path = tmp_path / "metadata" / "manual_import_log.csv"
    manual_dir.mkdir()
    cache_dir.mkdir()
    filename = "20250908_kawasaki_2.html"
    (manual_dir / filename).write_text("<html>new</html>", encoding="utf-8")
    (cache_dir / filename).write_text("<html>existing</html>", encoding="utf-8")

    results = import_manual_html_cache(
        manual_html_dir=manual_dir,
        cache_html_dir=cache_dir,
        log_path=log_path,
    )

    assert results[0].status == "skipped_exists"
    assert (cache_dir / filename).read_text(encoding="utf-8") == "<html>existing</html>"
    assert _read_log(log_path)[0]["status"] == "skipped_exists"


def test_import_manual_html_cache_skips_invalid_filename(tmp_path: Path) -> None:
    manual_dir = tmp_path / "manual"
    cache_dir = tmp_path / "cache"
    log_path = tmp_path / "metadata" / "manual_import_log.csv"
    manual_dir.mkdir()
    (manual_dir / "not_a_race_id.html").write_text("<html>bad</html>", encoding="utf-8")

    results = import_manual_html_cache(
        manual_html_dir=manual_dir,
        cache_html_dir=cache_dir,
        log_path=log_path,
    )

    assert results[0].status == "skipped_invalid_name"
    assert not (cache_dir / "not_a_race_id.html").exists()
    assert _read_log(log_path)[0]["status"] == "skipped_invalid_name"


def _read_log(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))

