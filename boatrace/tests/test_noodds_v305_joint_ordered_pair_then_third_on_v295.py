import inspect
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import train_noodds_v305_joint_ordered_pair_then_third_on_v295 as v305


def _prob(rows, seed):
    rng = np.random.default_rng(seed)
    values = rng.random((rows, 120))
    return values / values.sum(axis=1, keepdims=True)


def _block(rows=2, runner_width=2, race_width=1):
    runner = np.arange(rows * 6 * runner_width, dtype=np.float32).reshape(
        rows, 6, runner_width
    )
    race = np.arange(rows * race_width, dtype=np.float32).reshape(
        rows, 1, race_width
    )
    return np.concatenate(
        [runner, np.broadcast_to(race, (rows, 6, race_width))], axis=2
    )


def test_preregistered_joint_factorization_is_fixed():
    cfg = json.loads(
        (
            ROOT
            / "configs"
            / "noodds_v305_joint_ordered_pair_then_third_on_v295_preregistered.json"
        ).read_text()
    )
    assert cfg["training"]["pair_target"] == "30 ordered distinct first-second classes"
    assert cfg["model"]["pair"]["num_class"] == 30
    assert cfg["model"]["third"]["group_size"] == 4
    assert cfg["anchoring"]["gamma_bounds"] == [0, 0.25]


def test_ordered_pairs_cover_only_valid_distinct_lanes():
    assert v305.PAIRS.shape == (30, 2)
    assert len({tuple(pair) for pair in v305.PAIRS.tolist()}) == 30
    assert np.all(v305.PAIRS[:, 0] != v305.PAIRS[:, 1])
    assert np.all(np.diag(v305.PAIR_TO_INDEX) == -1)
    for pair_index, (first, second) in enumerate(v305.PAIRS):
        assert v305.PAIR_TO_INDEX[first, second] == pair_index


def test_remaining_candidates_exclude_selected_pair():
    first = np.asarray([0, 4, 5], dtype=np.int8)
    second = np.asarray([2, 1, 0], dtype=np.int8)
    remaining = v305.remaining_candidates(first, second)
    assert remaining.shape == (3, 4)
    for row, a, b in zip(remaining, first, second):
        assert len(set(row.tolist())) == 4
        assert a not in row
        assert b not in row


def test_pair_matrix_uses_canonical_lane_order_and_one_race_context():
    block = _block(rows=2, runner_width=2, race_width=1)
    matrix = v305.build_pair_matrix(block, runner_width=2)
    assert matrix.shape == (2, 13)
    assert np.array_equal(matrix[:, :12], block[:, :, :2].reshape(2, 12))
    assert np.array_equal(matrix[:, 12], block[:, 0, 2])


def test_third_matrix_uses_only_four_remaining_lanes():
    block = _block(rows=2, runner_width=2, race_width=1)
    first = np.asarray([0, 4], dtype=np.int8)
    second = np.asarray([2, 1], dtype=np.int8)
    matrix, candidates = v305.build_third_matrix(
        block, first, second, runner_width=2
    )
    assert matrix.shape == (8, 11)
    assert candidates.shape == (2, 4)
    for row, a, b in zip(candidates, first, second):
        assert a not in row
        assert b not in row


class _UniformPair:
    classes_ = np.arange(30)

    def predict_proba(self, matrix):
        return np.full((len(matrix), 30), 1.0 / 30.0)


class _UniformThird:
    def predict(self, matrix):
        return np.zeros(len(matrix), dtype=np.float64)


def test_uniform_joint_heads_reconstruct_uniform_exact_top3():
    block = _block(rows=3, runner_width=2, race_width=1)
    probability = v305.predict_contextual(
        (_UniformPair(), _UniformThird()),
        block,
        np.arange(3),
        runner_width=2,
    )
    assert probability.shape == (3, 120)
    assert np.allclose(probability, 1.0 / 120.0)
    assert np.allclose(probability.sum(axis=1), 1.0)


def test_gamma_zero_reproduces_parent_and_training_uses_true_pair_context():
    parent = _prob(5, 1)
    standalone = _prob(5, 2)
    result = v305.anchored_probability(parent, standalone, 0.0)
    assert np.allclose(result, parent, atol=1e-12)
    signature = inspect.signature(v305.fit_models)
    assert "parent" not in signature.parameters
    source = inspect.getsource(v305.fit_models)
    assert "target[:, 0], target[:, 1]" in source
    assert "target[:, 2" in source
