from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
SCRIPT = ROOT / "scripts" / "train_noodds_v296_large_history_exact_top3_with_form_trend_on_v295.py"
spec = importlib.util.spec_from_file_location("v296", SCRIPT)
v296 = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(v296)


def test_preregistration_is_frozen_and_uses_v295_parent():
    cfg = json.loads(
        (
            ROOT
            / "configs"
            / "noodds_v296_large_history_exact_top3_with_form_trend_on_v295_preregistered.json"
        ).read_text(encoding="utf-8")
    )
    assert cfg["frozen_before_run"] is True
    assert cfg["policy"]["active_parent"].startswith("v295_")
    assert cfg["policy"]["odds_used"] is False
    assert cfg["policy"]["future_information_used"] is False
    assert cfg["anchoring"]["D6"] == "v295 unchanged"
    assert cfg["form_trend"]["missing"] == "retain NaN for LightGBM native handling"


def test_fixed_form_contrasts_have_raw_and_field_relative_columns():
    raw = np.zeros((2, 6, 68), dtype=np.float32)
    for lane in range(6):
        raw[:, lane, 24] = lane + 2.0
        raw[:, lane, 32] = 1.0
    raw[1, 3, 24] = np.nan
    form = v296.build_form_features(raw)
    assert form.shape == (2, 6, 20)
    np.testing.assert_allclose(form[0, :, 0], np.arange(6) + 1.0)
    np.testing.assert_allclose(form[0, :, 1], np.arange(6) - 2.5)
    assert np.isnan(form[1, 3, 0])
    assert np.isnan(form[1, 3, 1])
    finite = np.array([1.0, 2.0, 3.0, 5.0, 6.0])
    np.testing.assert_allclose(
        form[1, [0, 1, 2, 4, 5], 1], finite - finite.mean(), atol=1e-6
    )


def test_form_features_are_built_before_row_selection():
    raw = np.zeros((5, 6, 68), dtype=np.float32)
    raw[:, :, 24] = np.arange(30, dtype=np.float32).reshape(5, 6)
    raw[:, :, 32] = 2.0
    full = v296.build_form_features(raw)
    selected = np.array([4, 1], dtype=np.int64)
    np.testing.assert_allclose(
        full[selected],
        v296.build_form_features(raw)[selected],
        equal_nan=True,
    )


def test_load_v295_oof_preserves_parent_and_old_references(tmp_path):
    paths = {}
    for offset, fold in enumerate(v296.FOLDS):
        path = tmp_path / f"{fold}.npz"
        parent = np.full((1, 120), 1.0 / 120.0, dtype=np.float32)
        np.savez_compressed(
            path,
            standalone=parent,
            v283=parent,
            v280=parent,
            v270=parent,
            v269=parent,
            v242=parent,
            v251=parent,
            race_indices=np.array([100 + offset]),
            race_dates=np.array([f"2026-01-0{offset + 1}"]),
            true_combo=np.array([offset]),
        )
        paths[fold] = path
    loaded = v296.load_v295_oof(paths)
    assert loaded["probability"].shape == (3, 120)
    assert loaded["v283"].shape == (3, 120)
    assert loaded["position"] == {100: 0, 101: 1, 102: 2}


def test_remaining_candidates_respects_order_context():
    first = np.array([1, 4])
    second = np.array([3, 0])
    stage2 = v296.remaining_candidates(first)
    stage3 = v296.remaining_candidates(first, second)
    assert stage2.shape == (2, 5)
    assert stage3.shape == (2, 4)
    assert 1 not in stage2[0] and 4 not in stage2[1]
    assert 1 not in stage3[0] and 3 not in stage3[0]


def test_grouped_objective_has_zero_group_gradient_sum():
    objective = v296.grouped_softmax_objective(4)
    labels = np.array([1, 0, 0, 0, 0, 1, 0, 0], dtype=float)
    grad, hess = objective(labels, np.zeros(8))
    np.testing.assert_allclose(
        grad.reshape(-1, 4).sum(axis=1), 0.0, atol=1e-12
    )
    assert np.all(hess > 0)


def test_context_matrix_uses_selected_runner_and_differences():
    block = np.zeros((1, 6, 5), dtype=np.float32)
    for lane in range(6):
        block[0, lane, :2] = [lane, lane + 10]
        block[0, lane, 2:] = [100, 200, 300]
    matrix, candidates = v296.build_context_matrix(
        block, np.array([2]), runner_width=2
    )
    slot = int(np.where(candidates[0] == 4)[0][0])
    np.testing.assert_allclose(matrix[slot, :5], block[0, 4])
    np.testing.assert_allclose(matrix[slot, 5:7], block[0, 2, :2])
    np.testing.assert_allclose(matrix[slot, 7:9], [2, 2])


def test_gamma_zero_reproduces_v295_parent_exactly():
    parent = np.array([[0.7, 0.2, 0.1], [0.1, 0.3, 0.6]], dtype=float)
    standalone = np.array([[0.1, 0.2, 0.7], [0.8, 0.1, 0.1]], dtype=float)
    got = v296.anchored_probability(parent, standalone, 0.0)
    np.testing.assert_allclose(got, parent, atol=1e-12)


class ZeroModel:
    def predict(self, features):
        return np.zeros(len(features), dtype=float)


def test_zero_context_models_produce_normalized_trifecta():
    block = np.zeros((2, 6, 7), dtype=np.float32)
    got = v296.predict_contextual(
        [ZeroModel(), ZeroModel(), ZeroModel()],
        block,
        np.array([0, 1]),
        runner_width=3,
    )
    assert got.shape == (2, 120)
    np.testing.assert_allclose(got.sum(axis=1), 1.0, atol=1e-12)
    np.testing.assert_allclose(got, 1.0 / 120.0, atol=1e-12)
