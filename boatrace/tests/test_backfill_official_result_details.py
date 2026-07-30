import sqlite3

from scripts.backfill_official_result_details import (
    ensure_schema,
    import_payload,
    load_db_index,
)


def make_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE races (race_key TEXT PRIMARY KEY, race_date TEXT, venue_code TEXT, race_no INTEGER);
        CREATE TABLE race_entries (race_key TEXT, lane INTEGER, racer_id TEXT);
        CREATE TABLE entry_results (race_key TEXT, lane INTEGER, finish_position INTEGER);
        """
    )
    conn.execute("INSERT INTO races VALUES ('2025011_01_01', '2025-1-1', '1', 1)")
    for lane in range(1, 7):
        conn.execute("INSERT INTO race_entries VALUES (?, ?, ?)", ('2025011_01_01', lane, str(4000 + lane)))
        conn.execute("INSERT INTO entry_results VALUES (?, ?, ?)", ('2025011_01_01', lane, lane))
    ensure_schema(conn)
    conn.commit()
    return conn


def payload(racer_override: tuple[int, int] | None = None) -> dict:
    boats = []
    for lane in range(1, 7):
        racer = 4000 + lane
        if racer_override and racer_override[0] == lane:
            racer = racer_override[1]
        boats.append(
            {
                "racer_boat_number": lane,
                "racer_course_number": 7 - lane,
                "racer_start_timing": lane / 100,
                "racer_place_number": lane,
                "racer_number": racer,
            }
        )
    return {
        "results": [
            {
                "date": "2025-01-01",
                "stadium_number": 1,
                "number": 1,
                "technique_number": 3,
                "boats": boats,
            }
        ]
    }


def test_import_requires_natural_key_and_all_racer_ids() -> None:
    conn = make_db()
    index = load_db_index(conn)
    stats, rejects = import_payload(conn, index, payload((4, 9999)), "sample", True)
    assert stats["updated"] == 0
    assert stats["rejected"] == 1
    assert "racer_id_mismatch_lane_4" == rejects[0]["reason"]
    assert conn.execute("SELECT COUNT(*) FROM entry_results WHERE actual_course IS NOT NULL").fetchone()[0] == 0


def test_import_updates_complete_identity_matched_race() -> None:
    conn = make_db()
    index = load_db_index(conn)
    stats, rejects = import_payload(conn, index, payload(), "sample", True)
    assert rejects == []
    assert stats["updated"] == 1
    assert conn.execute("SELECT technique_number FROM races").fetchone()[0] == 3
    assert conn.execute("SELECT actual_course, actual_start_timing FROM entry_results WHERE lane=1").fetchone() == (6, 0.01)
    assert conn.execute("SELECT identity_match_count FROM official_result_detail_imports").fetchone()[0] == 6
