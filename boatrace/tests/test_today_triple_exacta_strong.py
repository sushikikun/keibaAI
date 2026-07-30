from __future__ import annotations

import math

import pytest

from nankan_ai.today_triple_exacta import parse_race_card_html
from nankan_ai.today_triple_exacta_model import (
    ModelAWrapper,
    build_feature_row,
    build_training_examples,
    history_record_from_row,
    new_participant_stats,
    participant_context_for_row,
    plackett_luce_exacta,
    update_participant_stats,
)


def _row(race_id: str, race_date: str, horse: str, finish: int, *, passing: str = "1-1-1-1") -> dict[str, object]:
    return {
        "race_id": race_id,
        "date": race_date,
        "track": "kawasaki",
        "race_no": 1,
        "distance": 1400,
        "surface": "dirt",
        "track_condition": "good",
        "class_name": "C1",
        "horse_id": horse,
        "horse_name": horse,
        "horse_no": 1 if horse == "A" else 2,
        "gate_no": 1 if horse == "A" else 2,
        "sex": "牝",
        "age": 4,
        "carried_weight": 54.0,
        "jockey_name": f"J-{horse}",
        "trainer_name": f"T-{horse}",
        "finish_position": finish,
        "finish_time": "1:30.0",
        "last_3f": "38.0",
        "passing_order": passing,
    }


def test_training_examples_sort_unsorted_input_before_lag_features() -> None:
    rows = [
        _row("20260102_kawasaki_1", "2026-01-02", "A", 2),
        _row("20260102_kawasaki_1", "2026-01-02", "B", 1),
        _row("20260101_kawasaki_1", "2026-01-01", "A", 1),
        _row("20260101_kawasaki_1", "2026-01-01", "B", 2),
    ]
    examples = build_training_examples(rows, max_examples=20)
    past = [row for row in examples if row["race_id"] == "20260101_kawasaki_1"]
    future = [row for row in examples if row["race_id"] == "20260102_kawasaki_1"]
    assert all(row["history_count"] == 0 for row in past)
    assert all(row["history_count"] == 1 for row in future)


def test_passing_order_parser_accepts_full_width_and_slashes() -> None:
    record = history_record_from_row(_row("r", "2026-01-01", "A", 1, passing="２／３／４／５"))
    assert record.turn1 == 2.0
    assert record.turn2 == 3.0


def test_class_matching_handles_combined_b1_b2_condition() -> None:
    history = [
        history_record_from_row(_row("r", "2026-01-01", "A", 1) | {"class_name": "B2"}),
        history_record_from_row(_row("r2", "2026-02-01", "A", 5) | {"class_name": "C1"}),
    ]
    feature = build_feature_row(_row("today", "2026-07-10", "A", 0) | {"class_name": "B1B2"}, history)
    assert feature["same_class_win_rate"] == 1.0


def test_invalid_last3f_is_dropped_instead_of_becoming_outlier() -> None:
    record = history_record_from_row(_row("r", "2026-01-01", "A", 1) | {"last_3f": "99.9"})
    assert record.last3f is None


def test_participant_rates_use_global_history_and_smoothing() -> None:
    stats = new_participant_stats()
    runner = _row("today", "2026-07-10", "A", 0)
    before = participant_context_for_row(runner, stats)
    prior_rows = [
        _row(f"r{i}", f"2026-01-{i:02d}", "A", 1 if i <= 3 else 4)
        for i in range(1, 11)
    ]
    update_participant_stats(stats, prior_rows)
    after = participant_context_for_row(runner, stats)
    assert after["jockey_starts"] == 10
    assert 0.0 < after["jockey_win_rate"] < 1.0
    assert after["jockey_win_rate"] > before["jockey_win_rate"]


def test_log_probability_transform_is_less_sharp_than_logit() -> None:
    np = pytest.importorskip("numpy")

    class Dummy:
        def predict_proba(self, matrix):
            del matrix
            return np.asarray([[0.0, 0.60], [0.0, 0.40]])

    rows = [{"distance": 900}, {"distance": 900}]
    logit = ModelAWrapper("sklearn", ("distance",), Dummy(), score_transform="logit")
    logprob = ModelAWrapper("sklearn", ("distance",), Dummy(), score_transform="log_probability")
    p_logit = plackett_luce_exacta(logit.scores(rows))[(0, 1)]
    p_logprob = plackett_luce_exacta(logprob.scores(rows))[(0, 1)]
    assert p_logit > p_logprob
    assert math.isclose(p_logprob, 0.60, rel_tol=1e-6)


def test_race_card_parser_extracts_full_width_class_code() -> None:
    html = """
    <h1>10R 2026年7月10日 Ｃ１（四）（五） 詳細</h1>
    <table><tr><th>枠</th><th>馬番</th><th>馬名</th></tr>
    <tr><td>1</td><td>1</td><td>テストホース</td></tr></table>
    """
    parsed = parse_race_card_html(html, "2026-07-10", "kawasaki", 10)
    assert parsed["class_name"] == "C1"
    assert parsed["horses"][0]["class_name"] == "C1"


def test_training_example_cap_keeps_complete_races() -> None:
    rows: list[dict[str, object]] = []
    for day in range(1, 7):
        race_id = f"202601{day:02d}_kawasaki_1"
        for horse_no in range(1, 5):
            rows.append(
                _row(
                    race_id,
                    f"2026-01-{day:02d}",
                    f"H{horse_no}",
                    horse_no,
                )
                | {
                    "horse_no": horse_no,
                    "gate_no": horse_no,
                    "horse_id": f"H{horse_no}",
                }
            )
    examples = build_training_examples(rows, max_examples=10)
    counts: dict[str, int] = {}
    for row in examples:
        counts[str(row["race_id"])] = counts.get(str(row["race_id"]), 0) + 1
        assert int(row["race_runner_count"]) == 4
    assert len(examples) == 8
    assert set(counts.values()) == {4}
    assert sorted(counts) == ["20260105_kawasaki_1", "20260106_kawasaki_1"]
