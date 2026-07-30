from __future__ import annotations

import csv
import json
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from nankan_ai.today_triple_exacta import (
    _build_holdout_validation,
    _prediction_report,
    _validate_model_manifest,
    _write_json,
    _write_selected_ticket_output,
    main,
    parse_race_card_html,
)
from nankan_ai.today_triple_exacta_model import (
    FEATURE_COLUMNS,
    blend_exacta,
    build_training_examples,
    build_triple_combinations,
    fit_model_a,
    horse_key,
    model_class_name,
    model_engine_name,
    model_b_scores,
    plackett_luce_exacta,
    select_blend_weight,
    select_tickets,
    walk_forward_race_splits,
)
from nankan_ai.today_triple_exacta_safety import (
    assert_no_forbidden_features,
    create_stable_snapshot,
    sha256_file,
)
import nankan_ai.today_triple_exacta_safety as safety


def test_forbidden_market_features_fail_fast() -> None:
    with pytest.raises(ValueError):
        assert_no_forbidden_features(["recent_speed", "win_odds_final"])
    assert_no_forbidden_features(FEATURE_COLUMNS)


def test_training_features_do_not_use_same_race_results() -> None:
    rows = [
        _row("20260101_kawasaki_1", "2026-01-01", "A", 1),
        _row("20260101_kawasaki_1", "2026-01-01", "B", 2),
        _row("20260102_kawasaki_1", "2026-01-02", "A", 2),
        _row("20260102_kawasaki_1", "2026-01-02", "B", 1),
    ]
    examples = build_training_examples(rows, max_examples=20)
    first_race = [row for row in examples if row["race_id"] == "20260101_kawasaki_1"]
    assert first_race
    assert all(row["history_count"] == 0 for row in first_race)


def test_horse_id_is_primary_and_fallback_is_explicit() -> None:
    assert horse_key({"horse_id": "H-1", "horse_name": "same"}) == ("horse_id", "H-1")
    assert horse_key({"horse_name": "same", "birth_date": "2020-01-01", "sex": "牝"}) == (
        "fallback",
        "same|2020-01-01|牝",
    )


def test_cancelled_horse_is_not_active() -> None:
    html = """
    <table><tr><th>枠</th><th>馬番</th><th>馬名</th></tr>
    <tr><td>1</td><td>1</td><td>アオイ</td></tr>
    <tr><td>2</td><td>取消</td><td>モジモジ</td></tr></table>
    """
    parsed = parse_race_card_html(html, "2026-07-10", "kawasaki", 10)
    assert {horse["status"] for horse in parsed["horses"]} == {"ACTIVE", "SCR"}


def test_exacta_probability_is_normalized_and_has_no_self_pair() -> None:
    probabilities = plackett_luce_exacta([2.0, 1.0, 0.5])
    assert sum(probabilities.values()) == pytest.approx(1.0)
    assert all(first != second for first, second in probabilities)


def test_triple_probability_is_normalized() -> None:
    triples = build_triple_combinations(
        {
            10: {(1, 2): 0.6, (2, 1): 0.4},
            11: {(1, 2): 1.0},
            12: {(1, 2): 1.0},
        }
    )
    assert sum(float(row["posterior_probability"]) for row in triples) == pytest.approx(1.0)


def test_budget_and_duplicate_ticket_constraints() -> None:
    triples = build_triple_combinations(
        {race: {(1, 2): 0.5, (2, 1): 0.5} for race in (10, 11, 12)}
    )
    selected = select_tickets(triples, budget_yen=250)
    keys = {
        tuple(row[column] for column in ("race10_first", "race10_second", "race11_first", "race11_second", "race12_first", "race12_second"))
        for row in selected
    }
    assert len(selected) == 5
    assert len(keys) == len(selected)
    assert len(selected) * 50 <= 250


def test_same_seed_model_b_is_reproducible() -> None:
    rows = [_feature_row(0), _feature_row(1), _feature_row(2)]
    first = model_b_scores(rows, distance=1400, seed=20260710, draws=100)[1]
    second = model_b_scores(rows, distance=1400, seed=20260710, draws=100)[1]
    assert first == second


def test_model_b_can_be_rejected_when_not_improving() -> None:
    pairs = [{(0, 1): 1.0}, {(0, 1): 1.0}]
    selection = select_blend_weight([(0, 1), (0, 1)], pairs, pairs)
    assert selection["weight"] == 1.0
    assert selection["model_b_improved"] is False
    assert blend_exacta(pairs[0], pairs[1], 1.0) == pairs[0]


def test_fallback_model_fits_without_optional_dependencies() -> None:
    examples = [_feature_row(0) | {"label": 1}, _feature_row(1) | {"label": 0}]
    model = fit_model_a(examples, seed=1)
    assert model.backend in {"fallback", "sklearn", "catboost"}
    assert len(model.scores(examples)) == 2


def test_loaded_sklearn_model_is_not_reported_as_fallback() -> None:
    examples = [_feature_row(0) | {"label": 1}, _feature_row(1) | {"label": 0}]
    model = fit_model_a(examples, seed=1)
    if model_engine_name(model) == "sklearn":
        manifest = {"model_engine": "sklearn", "model_class": model_class_name(model), "blend_weights": {"900": 1.0, "1400": 1.0}}
        report = _prediction_report(
            SimpleNamespace(date="2026-07-10", track="kawasaki", budget_yen=100),
            Path("."),
            manifest,
            {"ready": False, "evaluated_races": 0},
            {"status": "fetched"},
            [],
            [],
            {},
        )
        assert "model_engine: sklearn" in report
        assert "model_engine: fallback" not in report


def test_model_manifest_loaded_engine_mismatch_is_rejected(tmp_path: Path) -> None:
    examples = [_feature_row(0) | {"label": 1}, _feature_row(1) | {"label": 0}]
    model = fit_model_a(examples, seed=1)
    model_path = tmp_path / "model.bin"
    model_path.write_bytes(b"model")
    manifest = {"model_engine": "sklearn" if model_engine_name(model) == "fallback" else "fallback", "model_class": model_class_name(model), "model_file_sha256": "wrong", "feature_names": list(FEATURE_COLUMNS)}
    with pytest.raises(ValueError, match="engine mismatch"):
        _validate_model_manifest(manifest, model, model_path)


def test_validation_json_contains_required_holdout_fields() -> None:
    examples = []
    start = date(2020, 1, 1)
    for index in range(150):
        current = (start + timedelta(days=index)).isoformat()
        for horse, position in ((1, 1), (2, 2)):
            examples.append(
                _feature_row(horse + index) | {
                    "race_id": f"race-{index}",
                    "date": current,
                    "horse_no": horse,
                    "label": int(position == 1),
                    "actual_position": position,
                }
            )
    validation = _build_holdout_validation(examples, seed=1)
    for key in (
        "evaluated_races", "holdout_date_min", "holdout_date_max", "exacta_log_loss",
        "exacta_brier_score", "top_1_coverage", "top_3_coverage", "top_5_coverage",
        "top_10_coverage", "top_20_coverage", "mean_reciprocal_rank", "median_actual_pair_rank",
        "uniform_baseline", "recent_form_baseline", "model_improves_uniform",
        "model_improves_recent_form", "ready",
    ):
        assert key in validation


def test_predict_rejects_missing_validation(tmp_path: Path) -> None:
    result = main([
        "--root", str(tmp_path), "predict", "--date", "2026-07-10", "--track", "kawasaki",
        "--races", "10", "11", "12", "--budget-yen", "100",
    ])
    assert result == 1


def test_ready_gate_writes_only_approved_output(tmp_path: Path) -> None:
    selected = [{
        "rank": 1,
        "race10_first": 1, "race10_second": 2,
        "race11_first": 1, "race11_second": 2,
        "race12_first": 1, "race12_second": 2,
        "posterior_probability": 1.0,
        "cumulative_probability": 1.0,
        "model_disagreement": 0.0,
        "supporting_reasons": "test",
    }]
    unapproved = _write_selected_ticket_output(tmp_path, selected, ready=False)
    assert unapproved.name == "selected_tickets_unapproved.csv"
    assert not (tmp_path / "selected_tickets.csv").exists()
    approved = _write_selected_ticket_output(tmp_path, selected, ready=True)
    assert approved.name == "selected_tickets.csv"
    assert not (tmp_path / "selected_tickets_unapproved.csv").exists()


def test_json_round_trip_preserves_japanese_path(tmp_path: Path) -> None:
    path = tmp_path / "日本語" / "validation.json"
    payload = {"path": "C:<USER_HOME>/ドキュメント/keibaAI", "ready": False}
    _write_json(path, payload)
    assert json.loads(path.read_text(encoding="utf-8")) == payload


def test_report_probability_fields_match_selected_last_row() -> None:
    selected = [{"cumulative_probability": 0.25}]
    report = _prediction_report(
        SimpleNamespace(date="2026-07-10", track="kawasaki", budget_yen=50),
        Path("."),
        {"model_engine": "sklearn", "model_class": "sklearn.Test", "sklearn_version": "1.9", "seed": 1, "blend_weights": {"900": 1.0, "1400": 1.0}, "forbidden_feature_check": "passed"},
        {"ready": True, "evaluated_races": 100, "exacta_log_loss": 1.0, "model_improves_uniform": True, "model_improves_recent_form": True},
        {"status": "fetched"},
        selected,
        [{"posterior_probability": 1.0}],
        {},
    )
    assert "selected_cumulative_probability: 0.25" in report
    assert "uniform_selection_probability: 1.0" in report


def test_walk_forward_split_uses_race_id_without_overlap() -> None:
    examples = [
        {"race_id": "r1", "date": "2026-01-01"},
        {"race_id": "r2", "date": "2026-01-02"},
        {"race_id": "r3", "date": "2026-01-03"},
        {"race_id": "r4", "date": "2026-01-04"},
        {"race_id": "r5", "date": "2026-01-05"},
    ]
    fold = walk_forward_race_splits(examples)[0]
    layers = [set(fold[key]) for key in ("train_race_ids", "calibration_race_ids", "final_holdout_race_ids")]
    assert not (layers[0] & layers[1] or layers[0] & layers[2] or layers[1] & layers[2])
    assert fold["random_split"] is False


def test_snapshot_sha_is_unchanged(tmp_path: Path) -> None:
    raw = tmp_path / "raw.csv"
    db = tmp_path / "nankan.duckdb"
    training = tmp_path / "training_rows.csv"
    raw.write_text("race_id,track\nr1,kawasaki\n", encoding="utf-8")
    db.write_bytes(b"duck")
    training.write_text("race_id\nr1\n", encoding="utf-8")
    result = create_stable_snapshot(
        raw_csv_path=raw,
        db_path=db,
        training_rows_path=training,
        snapshot_dir=tmp_path / "snapshot",
        reports_dir=tmp_path / "reports",
        wait_seconds=0,
    )
    assert sha256_file(raw) == result.fingerprints["raw_csv"].sha256
    assert sha256_file(db) == result.fingerprints["duckdb"].sha256
    assert sha256_file(training) == result.fingerprints["training_rows"].sha256


def test_snapshot_rejects_source_that_changes_between_checks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    raw = tmp_path / "raw.csv"
    db = tmp_path / "nankan.duckdb"
    training = tmp_path / "training_rows.csv"
    raw.write_text("race_id,track\nr1,kawasaki\n", encoding="utf-8")
    db.write_bytes(b"duck")
    training.write_text("race_id\nr1\n", encoding="utf-8")
    original = safety.sha256_file
    calls = {raw: 0}

    def changing_sha(path):
        path = Path(path)
        if path == raw:
            calls[raw] += 1
            if calls[raw] == 2:
                return "changed-during-check"
        return original(path)

    monkeypatch.setattr(safety, "sha256_file", changing_sha)
    with pytest.raises(RuntimeError, match="being written"):
        create_stable_snapshot(
            raw_csv_path=raw,
            db_path=db,
            training_rows_path=training,
            snapshot_dir=tmp_path / "snapshot",
            reports_dir=tmp_path / "reports",
            wait_seconds=0,
        )


def _row(race_id: str, date: str, horse: str, finish: int) -> dict[str, object]:
    return {
        "race_id": race_id,
        "date": date,
        "track": "kawasaki",
        "distance": "1400",
        "surface": "dirt",
        "track_condition": "good",
        "class_name": "C3",
        "horse_id": horse,
        "horse_name": horse,
        "horse_no": "1" if horse == "A" else "2",
        "gate_no": "1" if horse == "A" else "2",
        "sex": "牝",
        "age": "4",
        "carried_weight": "54.0",
        "jockey_name": "J",
        "trainer_name": "T",
        "finish_position": str(finish),
        "finish_time": "1:30.0",
        "last_3f": "38.0",
        "passing_order": "1-1-1-1",
    }


def _feature_row(index: int) -> dict[str, object]:
    row = {column: float(index + 1) for column in FEATURE_COLUMNS}
    row.update({"horse_no": index + 1, "start_power": 0.5 + index * 0.1, "early_position": 2.0, "mid_hold": 0.8, "late_strength": 0.7, "fade_rate": 0.1})
    return row
