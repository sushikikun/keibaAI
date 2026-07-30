from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from datetime import date
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
SCRIPT = ROOT / "scripts" / "train_noodds_v299_recency_weighted_exact_top3_on_v295.py"
spec = importlib.util.spec_from_file_location("v299", SCRIPT)
v299 = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(v299)


def test_preregistration_freezes_half_life_and_v295_parent():
    cfg = json.loads(
        (
            ROOT
            / "configs"
            / "noodds_v299_recency_weighted_exact_top3_on_v295_preregistered.json"
        ).read_text(encoding="utf-8")
    )
    assert cfg["frozen_before_run"] is True
    assert cfg["policy"]["active_parent"].startswith("v295_")
    assert cfg["recency_weighting"]["half_life_days"] == 180.0
    assert cfg["recency_weighting"]["weight_floor"] is None
    assert cfg["anchoring"]["D6"] == "v295 unchanged"


def test_recency_weights_have_fixed_half_life_mean_one_and_future_nan():
    dates = np.array(
        ["2025-01-01", "2025-06-30", "2025-12-27", "2026-06-25"]
    )
    weights, audit = v299.build_recency_weights(
        dates, np.array([0, 1, 2]), 180.0
    )
    np.testing.assert_allclose(weights[1] / weights[0], 2.0, rtol=1e-12)
    np.testing.assert_allclose(weights[2] / weights[1], 2.0, rtol=1e-12)
    np.testing.assert_allclose(weights[:3].mean(), 1.0, atol=1e-12)
    assert np.isnan(weights[3])
    assert audit["reference_date"] == "2025-12-27"
    assert audit["future_rows_nan"] == 1


def test_dataset_ordinal_dates_are_interpreted_as_calendar_days():
    ordinals = np.array([
        date(2025, 1, 1).toordinal(),
        date(2025, 6, 30).toordinal(),
        date(2025, 12, 27).toordinal(),
    ], dtype=np.int32)
    weights, audit = v299.build_recency_weights(
        ordinals, np.array([0, 1, 2]), 180.0
    )
    np.testing.assert_allclose(weights[1] / weights[0], 2.0, rtol=1e-12)
    assert audit["reference_date"] == "2025-12-27"


def test_same_day_training_rows_receive_same_weight():
    dates = np.array(["2026-01-01", "2026-01-01", "2026-01-02"])
    weights, _ = v299.build_recency_weights(
        dates, np.array([0, 1, 2]), 180.0
    )
    assert weights[0] == weights[1]


def test_stage_objectives_apply_race_weights_to_gradient_and_hessian():
    captured = []

    class FakeModel:
        def __init__(self, **params):
            self.params = params
            captured.append(self)

        def fit(self, features, target, callbacks=None):
            self.target = np.asarray(target)
            return self

    original = v299.lgb.LGBMRegressor
    v299.lgb.LGBMRegressor = FakeModel
    try:
        race_matrix = np.zeros((2, 6, 3), dtype=np.float32)
        targets = np.array([[0, 1, 2], [1, 2, 3]], dtype=np.int8)
        weights = np.array([0.5, 1.5], dtype=np.float64)
        cfg = {
            "n_estimators_full": 2,
            "n_estimators_screen": 1,
            "learning_rate": 0.03,
            "num_leaves": 3,
            "max_depth": 2,
            "min_child_samples": 1,
            "reg_alpha": 0,
            "reg_lambda": 0,
            "max_bin": 63,
            "feature_fraction": 1,
            "bagging_fraction": 1,
            "bagging_freq": 0,
            "seed": 29901,
            "threads": 1,
        }
        v299.fit_models(
            np.array([0, 1]),
            race_matrix,
            targets,
            runner_width=1,
            cfg=cfg,
            mode="screen",
            race_weights=weights,
        )
    finally:
        v299.lgb.LGBMRegressor = original
    assert len(captured) == 3
    for model, group_size in zip(captured, (6, 5, 4)):
        objective = model.params["objective"]
        gradient, hessian = objective(
            model.target, np.zeros(2 * group_size, dtype=float)
        )
        gradient = gradient.reshape(2, group_size)
        hessian = hessian.reshape(2, group_size)
        np.testing.assert_allclose(
            np.abs(gradient[1]).sum() / np.abs(gradient[0]).sum(),
            weights[1] / weights[0],
            rtol=1e-12,
        )
        np.testing.assert_allclose(
            hessian[1].mean() / hessian[0].mean(),
            weights[1] / weights[0],
            rtol=1e-12,
        )


def test_load_v295_oof_preserves_parent_and_old_references():
    with tempfile.TemporaryDirectory() as directory:
        paths = {}
        for offset, fold in enumerate(v299.FOLDS):
            path = Path(directory) / f"{fold}.npz"
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
        loaded = v299.load_v295_oof(paths)
    assert loaded["probability"].shape == (3, 120)
    assert loaded["position"] == {100: 0, 101: 1, 102: 2}


def test_gamma_zero_reproduces_v295_parent_exactly():
    parent = np.array([[0.7, 0.2, 0.1], [0.1, 0.3, 0.6]], dtype=float)
    standalone = np.array([[0.1, 0.2, 0.7], [0.8, 0.1, 0.1]], dtype=float)
    got = v299.anchored_probability(parent, standalone, 0.0)
    np.testing.assert_allclose(got, parent, atol=1e-12)


class ZeroModel:
    def predict(self, features):
        return np.zeros(len(features), dtype=float)


def test_zero_context_models_produce_normalized_trifecta():
    block = np.zeros((2, 6, 7), dtype=np.float32)
    got = v299.predict_contextual(
        [ZeroModel(), ZeroModel(), ZeroModel()],
        block,
        np.array([0, 1]),
        runner_width=3,
    )
    assert got.shape == (2, 120)
    np.testing.assert_allclose(got.sum(axis=1), 1.0, atol=1e-12)
