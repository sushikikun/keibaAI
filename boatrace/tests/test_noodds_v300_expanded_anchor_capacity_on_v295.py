import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from train_noodds_v300_expanded_anchor_capacity_on_v295 import (
    candidate_predictions,
    fit_chronological_gammas,
)


def _prob(seed):
    rng = np.random.default_rng(seed)
    value = rng.random((8, 120))
    return value / value.sum(axis=1, keepdims=True)


def _fold(seed):
    parent = _prob(seed)
    raw = _prob(seed + 10)
    return {
        "v283": parent,
        "v295_raw": raw,
        "standalone": parent.copy(),
        "true_combo": np.arange(8) % 120,
    }


def test_d6_is_parent_exactly():
    folds = {name: _fold(i) for i, name in enumerate(("d6", "d7", "d8"), start=1)}
    pred = candidate_predictions(folds, {"d6": 0.0, "d7": 0.4, "d8": 0.6})
    assert np.array_equal(pred["d6"], folds["d6"]["standalone"])


def test_chronological_fit_ignores_future_fold_targets():
    folds = {name: _fold(i) for i, name in enumerate(("d6", "d7", "d8"), start=1)}
    before, _ = fit_chronological_gammas(folds, [0.0, 1.0])
    folds["d8"]["true_combo"] = (folds["d8"]["true_combo"] + 17) % 120
    after, _ = fit_chronological_gammas(folds, [0.0, 1.0])
    assert before == after


def test_probabilities_are_normalized():
    folds = {name: _fold(i) for i, name in enumerate(("d6", "d7", "d8"), start=1)}
    pred = candidate_predictions(folds, {"d6": 0.0, "d7": 0.4, "d8": 0.6})
    for value in pred.values():
        assert np.all(value >= 0)
        assert np.allclose(value.sum(axis=1), 1.0)
