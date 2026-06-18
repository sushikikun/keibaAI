from __future__ import annotations

from pathlib import Path

TRACKS = frozenset({"kawasaki", "oi", "funabashi", "urawa"})

REQUIRED_COLUMNS = (
    "race_id",
    "date",
    "track",
    "race_no",
    "race_name",
    "distance",
    "surface",
    "weather",
    "track_condition",
    "class_name",
    "field_size",
    "horse_no",
    "gate_no",
    "horse_name",
    "sex",
    "age",
    "carried_weight",
    "jockey_name",
    "trainer_name",
    "body_weight",
    "body_weight_diff",
    "finish_position",
    "finish_time",
    "margin",
    "passing_order",
    "last_3f",
    "popularity",
    "win_odds_final",
)

INTEGER_COLUMNS = frozenset(
    {
        "race_no",
        "distance",
        "field_size",
        "horse_no",
        "gate_no",
        "age",
        "body_weight",
        "body_weight_diff",
        "popularity",
    }
)

DECIMAL_COLUMNS = frozenset({"carried_weight", "last_3f", "win_odds_final"})

FINISH_STATUS_VALUES = frozenset({"SCR", "EXC", "DNF"})

BASIC_FEATURE_COLUMNS = (
    "win_flag",
    "second_flag",
    "top3_flag",
    "is_scratched",
    "is_dnf",
    "distance_bucket",
    "body_weight_available",
    "odds_available",
)

DEFAULT_RAW_CSV_PATH = Path("data/raw/nankan_past_races.csv")
DEFAULT_DB_PATH = Path("data/nankan.duckdb")
DEFAULT_TRAINING_ROWS_PATH = Path("data/processed/training_rows.csv")
PAST_RACE_ROWS_TABLE = "past_race_rows"

FIELD_SIZE_MISMATCH_TOLERANCE = 1
