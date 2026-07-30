from __future__ import annotations

import pytest

from nankan_ai.today_triple_exacta_identity import (
    assess_inference_readiness,
    history_index_for_current_runners,
    normalize_horse_name,
    runner_key,
)
from nankan_ai.today_triple_exacta_model import FEATURE_COLUMNS, ModelAWrapper, plackett_luce_exacta


def test_normalize_horse_name_handles_width_and_spaces() -> None:
    assert normalize_horse_name(" ﾌﾞﾗｯｸ ﾄﾙﾏﾘﾝ ") == normalize_horse_name("ブラックトルマリン")


def test_history_join_matches_normalized_name_sex_and_birth_year() -> None:
    runner = {
        "race_id": "20260710_kawasaki_10",
        "race_no": 10,
        "date": "2026-07-10",
        "horse_no": 4,
        "horse_name": "アオイ ハナミチ",
        "sex": "牝",
        "age": 4,
    }
    raw = [
        {
            "race_id": "20260601_kawasaki_1",
            "date": "2026-06-01",
            "horse_name": "アオイハナミチ",
            "sex": "牝",
            "age": 4,
            "track": "kawasaki",
            "distance": 1400,
            "finish_position": 1,
            "finish_time": "1:31.1",
        },
        {
            "race_id": "20250601_kawasaki_1",
            "date": "2025-06-01",
            "horse_name": "アオイハナミチ",
            "sex": "牝",
            "age": 3,
            "track": "kawasaki",
            "distance": 1400,
            "finish_position": 2,
            "finish_time": "1:32.0",
        },
    ]
    histories, audit = history_index_for_current_runners(raw, before_date="2026-07-10", runners=[runner])
    assert len(histories[runner_key(runner)]) == 2
    assert audit[0]["join_method"] == "normalized_name_sex_birth_year"
    assert audit[0]["status"] == "matched"


def test_history_join_refuses_ambiguous_same_name() -> None:
    runner = {
        "race_id": "20260710_kawasaki_10",
        "date": "2026-07-10",
        "horse_no": 1,
        "horse_name": "同名馬",
        "sex": "牡",
        "age": 0,
    }
    raw = [
        {"date": "2025-01-01", "horse_name": "同名馬", "sex": "牡", "age": 3, "finish_position": 1},
        {"date": "2015-01-01", "horse_name": "同名馬", "sex": "牡", "age": 3, "finish_position": 1},
    ]
    histories, audit = history_index_for_current_runners(raw, before_date="2026-07-10", runners=[runner])
    assert histories[runner_key(runner)] == []
    assert audit[0]["status"] == "collision"
    assert audit[0]["collision_count"] >= 2


def test_inference_readiness_rejects_zero_history_and_constant_features() -> None:
    feature_rows = {
        10: [
            {column: 0.0 for column in FEATURE_COLUMNS} | {"history_count": 0},
            {column: 0.0 for column in FEATURE_COLUMNS} | {"history_count": 0},
        ]
    }
    audit = [
        {"matched_history_rows": 0, "collision_count": 0},
        {"matched_history_rows": 0, "collision_count": 0},
    ]
    result = assess_inference_readiness(
        feature_rows,
        audit,
        history_feature_columns=("recent1_speed", "recent3_speed_mean", "same_track_win_rate"),
        minimum_variable_features_per_race=1,
    )
    assert result["inference_ready"] is False
    assert result["zero_history_runner_count"] == 2


def test_model_scores_convert_probability_to_logit() -> None:
    np = pytest.importorskip("numpy")

    class DummyEstimator:
        def predict_proba(self, matrix):
            del matrix
            return np.asarray([[0.1, 0.9], [0.9, 0.1]])

    model = ModelAWrapper("sklearn", ("distance",), DummyEstimator())
    scores = model.scores([{"distance": 900}, {"distance": 900}])
    assert scores[0] > 2.0
    assert scores[1] < -2.0
    exacta = plackett_luce_exacta(scores)
    assert exacta[(0, 1)] > 0.95
