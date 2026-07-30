from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
SCRIPT = ROOT / "scripts" / "train_noodds_v298_large_history_exact_top3_seed_ensemble_on_v295.py"
spec = importlib.util.spec_from_file_location("v298", SCRIPT)
v298 = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(v298)


def test_preregistration_freezes_three_distinct_seeds_and_equal_weights():
    cfg = json.loads(
        (
            ROOT
            / "configs"
            / "noodds_v298_large_history_exact_top3_seed_ensemble_on_v295_preregistered.json"
        ).read_text(encoding="utf-8")
    )
    assert cfg["frozen_before_run"] is True
    assert cfg["policy"]["active_parent"].startswith("v295_")
    assert cfg["ensemble"]["seeds"] == [29801, 29802, 29803]
    assert cfg["ensemble"]["members"] == 3
    assert cfg["ensemble"]["member_weight"] == 1 / 3
    assert cfg["anchoring"]["D6"] == "v295 unchanged"


def test_geometric_mean_is_normalized_and_member_order_invariant():
    first = np.array([[0.7, 0.2, 0.1], [0.2, 0.3, 0.5]])
    second = np.array([[0.4, 0.4, 0.2], [0.3, 0.3, 0.4]])
    third = np.array([[0.6, 0.1, 0.3], [0.1, 0.2, 0.7]])
    forward = v298.geometric_probability_mean([first, second, third])
    reverse = v298.geometric_probability_mean([third, second, first])
    np.testing.assert_allclose(forward, reverse, atol=1e-12)
    np.testing.assert_allclose(forward.sum(axis=1), 1.0, atol=1e-12)


def test_identical_members_are_reproduced_exactly():
    member = np.array([[0.7, 0.2, 0.1], [0.2, 0.3, 0.5]])
    got = v298.geometric_probability_mean([member, member, member])
    np.testing.assert_allclose(got, member, atol=1e-12)


def test_model_params_use_member_seed_without_changing_capacity():
    cfg = {
        "n_estimators_full": 240,
        "n_estimators_screen": 82,
        "learning_rate": 0.03,
        "num_leaves": 15,
        "max_depth": 4,
        "min_child_samples": 1000,
        "reg_alpha": 2.0,
        "reg_lambda": 20.0,
        "max_bin": 63,
        "feature_fraction": 0.8,
        "bagging_fraction": 0.8,
        "bagging_freq": 1,
        "threads": 4,
    }
    first = v298.model_params(cfg, "screen", 1, 29801)
    second = v298.model_params(cfg, "screen", 1, 29802)
    assert first["random_state"] == 29802
    assert second["random_state"] == 29803
    assert first["n_estimators"] == second["n_estimators"] == 82


def test_load_v295_oof_preserves_parent_and_old_references():
    with tempfile.TemporaryDirectory() as directory:
        paths = {}
        for offset, fold in enumerate(v298.FOLDS):
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
        loaded = v298.load_v295_oof(paths)
    assert loaded["probability"].shape == (3, 120)
    assert loaded["v283"].shape == (3, 120)
    assert loaded["position"] == {100: 0, 101: 1, 102: 2}


def test_gamma_zero_reproduces_v295_parent_exactly():
    parent = np.array([[0.7, 0.2, 0.1], [0.1, 0.3, 0.6]], dtype=float)
    standalone = np.array([[0.1, 0.2, 0.7], [0.8, 0.1, 0.1]], dtype=float)
    got = v298.anchored_probability(parent, standalone, 0.0)
    np.testing.assert_allclose(got, parent, atol=1e-12)


class ZeroModel:
    def predict(self, features):
        return np.zeros(len(features), dtype=float)


def test_zero_context_models_produce_normalized_trifecta():
    block = np.zeros((2, 6, 7), dtype=np.float32)
    got = v298.predict_contextual(
        [ZeroModel(), ZeroModel(), ZeroModel()],
        block,
        np.array([0, 1]),
        runner_width=3,
    )
    assert got.shape == (2, 120)
    np.testing.assert_allclose(got.sum(axis=1), 1.0, atol=1e-12)
