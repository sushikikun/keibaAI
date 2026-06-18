from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from nankan_ai.fetch_plan import build_fetch_plan, write_fetch_plan
from nankan_ai.schema import REQUIRED_COLUMNS


def test_build_fetch_plan_excludes_existing_race_ids(tmp_path: Path) -> None:
    raw_path = tmp_path / "raw.csv"
    _write_raw(raw_path, existing_race_id="20260617_kawasaki_1")

    rows = build_fetch_plan(
        track="kawasaki",
        date_from="2026-06-17",
        date_to="2026-06-18",
        race_no_from=1,
        race_no_to=2,
        raw_csv_path=raw_path,
        cache_html_dir=tmp_path / "cache",
        exclude_existing=True,
        date_order="desc",
    )

    race_ids = [row.race_id for row in rows]
    assert race_ids == [
        "20260618_kawasaki_1",
        "20260618_kawasaki_2",
        "20260617_kawasaki_2",
    ]
    assert "k_babaCode=21" in rows[0].official_url
    assert "RaceMarkTable" in rows[0].official_url
    assert rows[0].cache_html_path.endswith("20260618_kawasaki_1.html")


def test_write_fetch_plan_creates_csv(tmp_path: Path) -> None:
    rows = build_fetch_plan(
        track="kawasaki",
        date_from="2026-06-18",
        date_to="2026-06-18",
        race_no_from=1,
        race_no_to=1,
        raw_csv_path=tmp_path / "missing_raw.csv",
        cache_html_dir=tmp_path / "cache",
    )

    output_path = write_fetch_plan(
        rows,
        reports_dir=tmp_path,
        now=datetime(2026, 6, 18, 12, 0, 0),
    )

    assert output_path == tmp_path / "fetch_plan_20260618_120000.csv"
    with output_path.open("r", encoding="utf-8", newline="") as handle:
        written = list(csv.DictReader(handle))
    assert len(written) == 1
    assert written[0]["race_id"] == "20260618_kawasaki_1"


def _write_raw(path: Path, *, existing_race_id: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {column: "" for column in REQUIRED_COLUMNS}
    row.update(
        {
            "race_id": existing_race_id,
            "date": "2026-06-17",
            "track": "kawasaki",
            "race_no": "1",
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

