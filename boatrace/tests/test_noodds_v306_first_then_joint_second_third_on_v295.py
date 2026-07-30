import inspect
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import train_noodds_v306_first_then_joint_second_third_on_v295 as v306


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


def test_preregistered_reverse_factorization_is_fixed():
    cfg = json.loads(
        (
            ROOT
            / "configs"
            / "noodds_v306_first_then_joint_second_third_on_v295_preregistered.json"
        ).read_text()
    )
    assert cfg["training"]["pair_target"].startswith("20 ordered distinct")
    assert cfg["model"]["first"]["group_size"] == 6
    assert cfg["model"]["second_third"]["num_class"] == 20
    assert cfg["anchoring"]["gamma_bounds"] == [0, 0.25]


def test_local_pairs_cover_only_valid_remaining_positions():
    assert v306.LOCAL_PAIRS.shape == (20, 2)
    assert len({tuple(pair) for pair in v306.LOCAL_PAIRS.tolist()}) == 20
    assert np.all(v306.LOCAL_PAIRS[:, 0] != v306.LOCAL_PAIRS[:, 1])
    assert np.all(np.diag(v306.LOCAL_PAIR_TO_INDEX) == -1)
    for pair_index, (second, third) in enumerate(v306.LOCAL_PAIRS):
        assert v306.LOCAL_PAIR_TO_INDEX[second, third] == pair_index


def test_remaining_candidates_exclude_first():
    first = np.asarray([0, 4, 5], dtype=np.int8)
    remaining = v306.remaining_candidates(first)
    assert remaining.shape == (3, 5)
    for row, selected in zip(remaining, first):
        assert len(set(row.tolist())) == 5
        assert selected not in row


def test_first_matrix_has_six_candidate_rows_per_race():
    block = _block(rows=2, runner_width=2, race_width=1)
    matrix = v306.build_first_matrix(block)
    assert matrix.shape == (12, 3)
    assert np.array_equal(matrix, block.reshape(12, 3))


def test_second_third_matrix_includes_first_context():
    block = _block(rows=2, runner_width=2, race_width=1)
    first = np.asarray([0, 4], dtype=np.int8)
    matrix, candidates = v306.build_second_third_matrix(
        block, first, runner_width=2
    )
    assert matrix.shape == (2, 21)
    assert candidates.shape == (2, 5)
    assert np.array_equal(matrix[:, 12:14], block[np.arange(2), first, :2])
    assert np.array_equal(matrix[:, 14:20], np.eye(6, dtype=np.float32)[first])


class _UniformFirst:
    def predict(self, matrix):
        return np.zeros(len(matrix), dtype=np.float64)


class _UniformPair:
    classes_ = np.arange(20)

    def predict_proba(self, matrix):
        return np.full((len(matrix), 20), 1.0 / 20.0)


def test_uniform_heads_reconstruct_uniform_exact_top3():
    block = _block(rows=3, runner_width=2, race_width=1)
    probability = v306.predict_contextual(
        (_UniformFirst(), _UniformPair()),
        block,
        np.arange(3),
        runner_width=2,
    )
    assert probability.shape == (3, 120)
    assert np.allclose(probability, 1.0 / 120.0)
    assert np.allclose(probability.sum(axis=1), 1.0)


def test_gamma_zero_reproduces_parent_and_training_uses_true_first_context():
    parent = _prob(5, 1)
    standalone = _prob(5, 2)
    result = v306.anchored_probability(parent, standalone, 0.0)
    assert np.allclose(result, parent, atol=1e-12)
    signature = inspect.signature(v306.fit_models)
    assert "parent" not in signature.parameters
    source = inspect.getsource(v306.fit_models)
    assert "target[:, 0]" in source
    assert "target[:, 1, None]" in source
    assert "target[:, 2, None]" in source
