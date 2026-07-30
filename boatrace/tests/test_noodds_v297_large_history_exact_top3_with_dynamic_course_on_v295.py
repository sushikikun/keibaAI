from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
SCRIPT = ROOT / "scripts" / "train_noodds_v297_large_history_exact_top3_with_dynamic_course_on_v295.py"
spec = importlib.util.spec_from_file_location("v297", SCRIPT)
v297 = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(v297)


def test_preregistration_is_frozen_and_uses_v295_parent():
    cfg = json.loads(
        (
            ROOT
            / "configs"
            / "noodds_v297_large_history_exact_top3_with_dynamic_course_on_v295_preregistered.json"
        ).read_text(encoding="utf-8")
    )
    assert cfg["frozen_before_run"] is True
    assert cfg["policy"]["active_parent"].startswith("v295_")
    assert cfg["anchoring"]["D6"] == "v295 unchanged"
    assert cfg["dynamic_racer_course"]["overall_shrinkage"] == 50.0
    assert cfg["dynamic_racer_course"]["racer_course_shrinkage"] == 20.0


def test_dynamic_course_history_is_same_day_safe_and_course_aware():
    raw = np.zeros((3, 6, 1), dtype=np.float32)
    raw[:, :, 0] = np.arange(1, 7, dtype=np.float32)
    course = np.zeros((3, 6, 5), dtype=np.float32)
    course[:, :, 0] = np.arange(1, 7, dtype=np.float32)
    available = np.ones(3, dtype=np.uint8)
    targets = np.array([[0, 1, 2], [0, 1, 2], [0, 1, 2]], dtype=np.int8)
    dates = np.array(["2026-01-01", "2026-01-01", "2026-01-02"])
    features = v297.build_dynamic_racer_course_features(
        raw,
        course,
        available,
        targets,
        dates,
        initial_global_rates=np.array([1 / 6, 1 / 3, 1 / 2]),
        overall_shrinkage=50.0,
        racer_course_shrinkage=20.0,
    )
    np.testing.assert_allclose(features[0], features[1])
    np.testing.assert_allclose(features[0, :, 0], 0.0)
    assert np.all(features[0, :, 4] == 1.0)
    np.testing.assert_allclose(features[2, :, 0], np.log1p(2.0))


def test_missing_official_course_is_zero_and_does_not_impute():
    raw = np.zeros((1, 6, 1), dtype=np.float32)
    raw[0, :, 0] = np.arange(1, 7, dtype=np.float32)
    course = np.zeros((1, 6, 5), dtype=np.float32)
    features = v297.build_dynamic_racer_course_features(
        raw,
        course,
        np.zeros(1, dtype=np.uint8),
        np.array([[0, 1, 2]], dtype=np.int8),
        np.array(["2026-01-01"]),
        initial_global_rates=np.array([1 / 6, 1 / 3, 1 / 2]),
        overall_shrinkage=50.0,
        racer_course_shrinkage=20.0,
    )
    np.testing.assert_allclose(features, 0.0)


def test_load_v295_oof_preserves_parent_and_old_references():
    with tempfile.TemporaryDirectory() as directory:
        paths = {}
        for offset, fold in enumerate(v297.FOLDS):
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
        loaded = v297.load_v295_oof(paths)
    assert loaded["probability"].shape == (3, 120)
    assert loaded["v283"].shape == (3, 120)
    assert loaded["position"] == {100: 0, 101: 1, 102: 2}


def test_context_matrix_uses_selected_runner_and_differences():
    block = np.zeros((1, 6, 5), dtype=np.float32)
    for lane in range(6):
        block[0, lane, :2] = [lane, lane + 10]
    matrix, candidates = v297.build_context_matrix(
        block, np.array([2]), runner_width=2
    )
    slot = int(np.where(candidates[0] == 4)[0][0])
    np.testing.assert_allclose(matrix[slot, :5], block[0, 4])
    np.testing.assert_allclose(matrix[slot, 7:9], [2, 2])


def test_gamma_zero_reproduces_v295_parent_exactly():
    parent = np.array([[0.7, 0.2, 0.1], [0.1, 0.3, 0.6]], dtype=float)
    standalone = np.array([[0.1, 0.2, 0.7], [0.8, 0.1, 0.1]], dtype=float)
    got = v297.anchored_probability(parent, standalone, 0.0)
    np.testing.assert_allclose(got, parent, atol=1e-12)


class ZeroModel:
    def predict(self, features):
        return np.zeros(len(features), dtype=float)


def test_zero_context_models_produce_normalized_trifecta():
    block = np.zeros((2, 6, 7), dtype=np.float32)
    got = v297.predict_contextual(
        [ZeroModel(), ZeroModel(), ZeroModel()],
        block,
        np.array([0, 1]),
        runner_width=3,
    )
    assert got.shape == (2, 120)
    np.testing.assert_allclose(got.sum(axis=1), 1.0, atol=1e-12)
