from __future__ import annotations

from collections.abc import Mapping

from .schema import BASIC_FEATURE_COLUMNS, FINISH_STATUS_VALUES


def add_basic_features(row: Mapping[str, object]) -> dict[str, object]:
    """Return a copy of a race row with the MVP training flags appended."""
    output = dict(row)
    finish_position = _clean(row.get("finish_position")).upper()
    finish_number = _positive_int_or_none(finish_position)

    output.update(
        {
            "win_flag": 1 if finish_number == 1 else 0,
            "second_flag": 1 if finish_number == 2 else 0,
            "top3_flag": 1 if finish_number in {1, 2, 3} else 0,
            "is_scratched": 1 if finish_position in {"SCR", "EXC"} else 0,
            "is_dnf": 1 if finish_position == "DNF" else 0,
            "distance_bucket": bucket_distance(row.get("distance")),
            "body_weight_available": 1 if _has_value(row.get("body_weight")) else 0,
            "odds_available": 1 if _has_value(row.get("win_odds_final")) else 0,
        }
    )
    return output


def bucket_distance(distance: object) -> str:
    value = _positive_int_or_none(_clean(distance))
    if value is None:
        return ""
    if value <= 1400:
        return "short"
    if value <= 1700:
        return "mile"
    if value <= 2200:
        return "middle"
    return "long"


def feature_columns() -> tuple[str, ...]:
    return BASIC_FEATURE_COLUMNS


def _has_value(value: object) -> bool:
    return _clean(value) != ""


def _clean(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _positive_int_or_none(value: str) -> int | None:
    if not value.isdigit():
        return None
    number = int(value)
    if number <= 0:
        return None
    return number


__all__ = [
    "FINISH_STATUS_VALUES",
    "add_basic_features",
    "bucket_distance",
    "feature_columns",
]
