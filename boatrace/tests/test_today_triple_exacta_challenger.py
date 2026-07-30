from __future__ import annotations

import inspect

import pytest

from nankan_ai.today_triple_exacta_challenger import (
    HALF_LIVES,
    adoption_decision,
    choose_half_life,
    partition_by_distance,
    recency_sample_weights,
    select_ensemble_weights,
    split_complete_races,
)


def test_distance_expert_partitions_only_target_distance() -> None:
    rows = [
        {"distance": 900, "race_id": "r1"},
        {"distance": 1400, "race_id": "r2"},
        {"distance": 1500, "race_id": "r3"},
    ]
    partitions = partition_by_distance(rows)
    assert {_row["distance"] for _row in partitions[900]} == {900}
    assert {_row["distance"] for _row in partitions[1400]} == {1400}


def test_recency_weight_uses_only_rows_at_or_before_anchor() -> None:
    rows = [{"date": "2025-01-01"}, {"date": "2025-12-31"}]
    weights = recency_sample_weights(rows, anchor_date="2025-12-31", half_life_days=365)
    assert weights[0] < weights[1]
    with pytest.raises(ValueError, match="future"):
        recency_sample_weights([{"date": "2026-01-01"}], anchor_date="2025-12-31", half_life_days=365)


def test_half_life_is_selected_from_calibration_metrics_only() -> None:
    metrics = {
        365: {"exacta_log_loss": 4.2, "exacta_brier_score": 0.98},
        730: {"exacta_log_loss": 4.0, "exacta_brier_score": 0.97},
        1460: {"exacta_log_loss": 4.1, "exacta_brier_score": 0.96},
    }
    assert set(metrics) == set(HALF_LIVES)
    assert choose_half_life(metrics) == 730


def test_ensemble_weights_are_nonnegative_sum_one_and_grid_aligned() -> None:
    actual = [(1, 2)]
    global_p = [{(1, 2): 0.5, (2, 1): 0.5}]
    distance_p = [{(1, 2): 0.8, (2, 1): 0.2}]
    recency_p = [{(1, 2): 0.6, (2, 1): 0.4}]
    weights = select_ensemble_weights(actual, global_p, distance_p, recency_p)
    assert sum(weights.values()) == pytest.approx(1.0)
    assert all(value >= 0 for value in weights.values())
    assert all(value * 20 == pytest.approx(round(value * 20)) for value in weights.values())


def test_final_holdout_is_not_an_ensemble_selection_argument() -> None:
    assert "holdout" not in inspect.signature(select_ensemble_weights).parameters


def test_small_improvement_retains_baseline() -> None:
    baseline = {
        "exacta_log_loss": 4.027302404054624,
        "exacta_brier_score": 0.9709704994667626,
        "top_10_coverage": 0.42049335863377607,
        "top_20_coverage": 0.6015180265654649,
    }
    challenger = dict(baseline)
    challenger["exacta_log_loss"] -= 0.004
    decision = adoption_decision(baseline, {"distance_expert": challenger}, checks_passed=True, inference_ready=True)
    assert decision["adopted"] is False
    assert decision["model"] == "global_baseline"


def test_complete_race_split_never_splits_one_race_id() -> None:
    examples = []
    for day in range(1, 11):
        for horse_no in (1, 2, 3):
            examples.append({
                "race_id": f"r{day}",
                "date": f"2026-01-{day:02d}",
                "horse_no": horse_no,
                "race_runner_count": 3,
            })
    split = split_complete_races(examples)
    ids = {
        name: {row["race_id"] for row in split[name]}
        for name in ("validation_fit", "calibration", "final_holdout")
    }
    assert not (ids["validation_fit"] & ids["calibration"])
    assert not (ids["validation_fit"] & ids["final_holdout"])
    assert not (ids["calibration"] & ids["final_holdout"])
    assert all(len([row for row in split[name] if row["race_id"] == race_id]) == 3 for name in ids for race_id in ids[name])
