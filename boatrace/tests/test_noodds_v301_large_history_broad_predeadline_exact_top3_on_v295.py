import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import train_noodds_v301_large_history_broad_predeadline_exact_top3_on_v295 as v301


def _prob(rows, seed):
    rng = np.random.default_rng(seed)
    value = rng.random((rows, 120))
    return value / value.sum(axis=1, keepdims=True)


def test_preregistered_feature_set_excludes_forbidden_and_constant_columns():
    cfg = json.loads(
        (ROOT / "configs" / "noodds_v301_large_history_broad_predeadline_exact_top3_on_v295_preregistered.json").read_text()
    )
    indices = cfg["features"]["runner_indices"]
    assert len(indices) == 79
    assert not set(range(72, 80)).intersection(indices)
    assert not {15, 16, 59, 60, 61, 62, 63, 64, 65, 66}.intersection(indices)
    assert indices == v301.RUNNER_INDICES.tolist()


def test_race_context_uses_fixed_one_hot_and_numeric_width():
    race = np.zeros((24, 21), dtype=np.float32)
    race[:, 0] = np.arange(24)
    race[:, 1] = (np.arange(24) % 12) + 1
    race[:, v301.RACE_NUMERIC_INDICES] = 2.5
    encoded = v301.encode_race_context(race)
    assert encoded.shape == (24, 54)
    assert np.allclose(encoded[:, :24].sum(axis=1), 1.0)
    assert np.allclose(encoded[:, 24:36].sum(axis=1), 1.0)
    assert np.allclose(encoded[:, 36:], 2.5)


def test_race_context_rejects_changed_categories():
    race = np.zeros((23, 21), dtype=np.float32)
    race[:, 0] = np.arange(23)
    race[:, 1] = (np.arange(23) % 12) + 1
    try:
        v301.encode_race_context(race)
    except ValueError as exc:
        assert "venue categories changed" in str(exc)
    else:
        raise AssertionError("changed venue categories were accepted")


def test_gamma_zero_reproduces_parent():
    parent = _prob(5, 1)
    standalone = _prob(5, 2)
    result = v301.anchored_probability(parent, standalone, 0.0)
    assert np.allclose(result, parent, atol=1e-12)


def test_stage_widths_match_preregistration():
    cfg = json.loads(
        (ROOT / "configs" / "noodds_v301_large_history_broad_predeadline_exact_top3_on_v295_preregistered.json").read_text()
    )
    runner = cfg["feature_audit"]["runner_width_after_course_history"]
    race = cfg["feature_audit"]["race_width_before_course"] + 4
    assert runner + race == cfg["feature_audit"]["stage_widths"]["stage1"]
    assert 3 * runner + race == cfg["feature_audit"]["stage_widths"]["stage2"]
    assert 5 * runner + race == cfg["feature_audit"]["stage_widths"]["stage3"]


def test_matched_screen_requires_exact_alignment(tmp_path):
    matched = tmp_path / "matched"
    matched.mkdir()
    out = tmp_path / "out"
    out.mkdir()
    folds = {}
    raw_pred = {}
    for number, fold in enumerate(v301.FOLDS):
        indices = np.array([number * 10, number * 10 + 1], dtype=np.int64)
        dates = np.array([f"2026-01-0{number + 1}", f"2026-01-0{number + 1}"])
        target = np.array([0, 1], dtype=np.int64)
        parent = _prob(2, number + 10)
        candidate = parent.copy()
        np.savez_compressed(
            matched / f"fold_{fold}_predictions.npz",
            v295_raw=parent,
            race_indices=indices,
            race_dates=dates,
            true_combo=target,
        )
        folds[fold] = {"indices": indices, "dates": dates, "target": target}
        raw_pred[fold] = candidate

    protocol = {
        "protocol_id": "test_matched",
        "comparison": {"bootstrap_seed": 1, "bootstrap_samples": 50},
    }
    protocol_path = tmp_path / "screen.json"
    protocol_path.write_text(json.dumps(protocol))
    args = SimpleNamespace(
        screen_protocol=protocol_path,
        matched_parent_dir=matched,
    )
    gate = v301.evaluate_matched_screen(args, folds, raw_pred, out)
    assert gate["status"] == "continue_full_evaluation"
    assert abs(gate["comparison_vs_matched_v295_raw"]["delta_mean"]) < 1e-12

    folds["d8"]["indices"] = folds["d8"]["indices"] + 1
    try:
        v301.evaluate_matched_screen(args, folds, raw_pred, out)
    except ValueError as exc:
        assert "race_indices mismatch" in str(exc)
    else:
        raise AssertionError("misaligned matched parent was accepted")
