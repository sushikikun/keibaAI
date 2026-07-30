from __future__ import annotations

import sqlite3
import sys
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import promote_existing_boatrace_db_batch as promote  # noqa: E402
import reuse_boatrace_raw_assets as raw_reuse  # noqa: E402
import run_boatrace_data_expansion_pipeline_reuse as runner  # noqa: E402


def test_db_has_day_accepts_legacy_non_padded_dates(tmp_path: Path) -> None:
    db = tmp_path / "legacy.db"
    connection = sqlite3.connect(db)
    connection.execute("CREATE TABLE races (race_date TEXT)")
    connection.execute("INSERT INTO races VALUES ('2026-4-9')")
    connection.commit()
    connection.close()
    assert runner.db_has_day(db, promote.date(2026, 4, 9))
    assert not runner.db_has_day(db, promote.date(2026, 4, 10))


def test_complete_actual_requires_six_unique_places() -> None:
    rows = {
        lane: {
            "finish_position": lane,
            "actual_course": lane,
            "actual_start_timing": 0.10 + lane / 100,
        }
        for lane in range(1, 7)
    }
    assert promote.complete_actual(rows)
    rows[6]["finish_position"] = 5
    assert not promote.complete_actual(rows)


def test_raw_asset_pattern_is_exact() -> None:
    match = raw_reuse.PAGE_RE.match("20260718_01_12_beforeinfo.html")
    assert match is not None
    assert match.group("kind") == "beforeinfo"
    assert raw_reuse.PAGE_RE.match("20260718_01_12_raceresult.html") is None
