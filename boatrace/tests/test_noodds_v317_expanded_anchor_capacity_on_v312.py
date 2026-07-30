import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import train_noodds_v317_expanded_anchor_capacity_on_v312 as v317


def _prob(seed):
    rng = np.random.default_rng(seed)
    value = rng.random((8, 120))
    return value / value.sum(axis=1, keepdims=True)


def _fold(seed):
    anchor = _prob(seed)
    raw = _prob(seed + 10)
    parent = v317.anchored_probability(anchor, raw, 0.25)
    return {
        "v295": anchor,
        "v311_raw": raw,
        "standalone": parent,
        "true_combo": np.arange(8) % 120,
    }


def test_preregistration_fixes_parent_and_expanded_bound():
    cfg = json.loads(v317.parse_args.__globals__["ROOT"].joinpath(
        "configs", "noodds_v317_expanded_anchor_capacity_on_v312_preregistered.json"
    ).read_text(encoding="utf-8"))
    assert cfg["policy"]["active_parent"] == (
        "v312_large_history_racer_identity_set_ranker_on_v295"
    )
    assert cfg["anchoring"]["gamma_bounds"] == [0.0, 0.5]
    assert cfg["base_definition"]["training"] == "no retraining"
    assert cfg["final_protocol"].endswith("noodds_evaluation_protocol_v9.json")


def test_d6_is_v312_parent_exactly():
    folds = {
        name: _fold(index)
        for index, name in enumerate(("d6", "d7", "d8"), start=1)
    }
    pred = v317.candidate_predictions(
        folds, {"d6": 0.0, "d7": 0.4, "d8": 0.45}
    )
    assert np.array_equal(pred["d6"], folds["d6"]["standalone"])


def test_chronological_fit_ignores_current_and_future_targets():
    folds = {
        name: _fold(index)
        for index, name in enumerate(("d6", "d7", "d8"), start=1)
    }
    before, _ = v317.fit_chronological_gammas(folds, [0.0, 0.5])
    folds["d8"]["true_combo"] = (
        folds["d8"]["true_combo"] + 17
    ) % 120
    after_d8, _ = v317.fit_chronological_gammas(folds, [0.0, 0.5])
    assert before == after_d8
    original_d7 = before["d7"]
    folds["d7"]["true_combo"] = (
        folds["d7"]["true_combo"] + 23
    ) % 120
    after_d7, _ = v317.fit_chronological_gammas(folds, [0.0, 0.5])
    assert after_d7["d7"] == original_d7


def test_candidate_probabilities_are_normalized():
    folds = {
        name: _fold(index)
        for index, name in enumerate(("d6", "d7", "d8"), start=1)
    }
    pred = v317.candidate_predictions(
        folds, {"d6": 0.0, "d7": 0.4, "d8": 0.45}
    )
    for value in pred.values():
        assert np.all(value >= 0)
        assert np.allclose(value.sum(axis=1), 1.0)
