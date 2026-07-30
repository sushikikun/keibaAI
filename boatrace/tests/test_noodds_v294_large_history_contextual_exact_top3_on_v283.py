from __future__ import annotations
import importlib.util
import json
import sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
SCRIPT = ROOT / "scripts" / "train_noodds_v294_large_history_contextual_exact_top3_on_v283.py"
spec = importlib.util.spec_from_file_location("v294", SCRIPT)
v294 = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(v294)

def test_preregistration_is_frozen_and_time_safe():
    cfg = json.loads((ROOT / "configs" / "noodds_v294_large_history_contextual_exact_top3_on_v283_preregistered.json").read_text(encoding="utf-8"))
    assert cfg["frozen_before_run"] is True
    assert cfg["policy"]["odds_used"] is False
    assert cfg["policy"]["future_information_used"] is False
    assert cfg["anchoring"]["D6"] == "v283 unchanged"

def test_remaining_candidates_respects_order_context():
    first = np.array([1, 4])
    second = np.array([3, 0])
    stage2 = v294.remaining_candidates(first)
    stage3 = v294.remaining_candidates(first, second)
    assert stage2.shape == (2, 5)
    assert stage3.shape == (2, 4)
    assert 1 not in stage2[0] and 4 not in stage2[1]
    assert 1 not in stage3[0] and 3 not in stage3[0]

def test_grouped_objective_has_zero_group_gradient_sum():
    objective = v294.grouped_softmax_objective(4)
    y = np.array([1,0,0,0, 0,1,0,0], dtype=float)
    grad, hess = objective(y, np.zeros(8))
    assert grad.shape == hess.shape == (8,)
    np.testing.assert_allclose(grad.reshape(-1,4).sum(axis=1), 0.0, atol=1e-12)
    assert np.all(hess > 0)

def test_context_matrix_uses_selected_runner_and_differences():
    block = np.zeros((1,6,5), dtype=np.float32)
    for lane in range(6):
        block[0,lane,:2] = [lane, lane+10]
        block[0,lane,2:] = [100,200,300]
    x, candidates = v294.build_context_matrix(block, np.array([2]), runner_width=2)
    assert x.shape == (5, 9)
    slot = int(np.where(candidates[0] == 4)[0][0])
    np.testing.assert_allclose(x[slot,:5], block[0,4])
    np.testing.assert_allclose(x[slot,5:7], block[0,2,:2])
    np.testing.assert_allclose(x[slot,7:9], [2,2])

def test_gamma_zero_reproduces_parent_exactly():
    parent = np.array([[0.7,0.2,0.1],[0.1,0.3,0.6]], dtype=float)
    standalone = np.array([[0.1,0.2,0.7],[0.8,0.1,0.1]], dtype=float)
    got = v294.anchored_probability(parent, standalone, 0.0)
    np.testing.assert_allclose(got, parent, atol=1e-12)

def test_fit_gamma_is_bounded_and_uses_given_oof_only():
    parent = np.array([[0.8,0.1,0.1],[0.1,0.8,0.1],[0.1,0.1,0.8]], dtype=float)
    standalone = np.full((3,3), 1/3, dtype=float)
    gamma, loss = v294.fit_gamma(parent, standalone, np.array([0,1,2]), [0.0,0.25])
    assert 0.0 <= gamma <= 0.25
    assert np.isfinite(loss)
    assert gamma < 1e-3

class ZeroModel:
    def predict(self, x):
        return np.zeros(len(x), dtype=float)

def test_zero_context_models_produce_normalized_uniform_trifecta():
    block = np.zeros((2,6,7), dtype=np.float32)
    got = v294.predict_contextual([ZeroModel(),ZeroModel(),ZeroModel()], block, np.array([0,1]), runner_width=3)
    assert got.shape == (2,120)
    np.testing.assert_allclose(got.sum(axis=1), 1.0, atol=1e-12)
    np.testing.assert_allclose(got, 1/120, atol=1e-12)
