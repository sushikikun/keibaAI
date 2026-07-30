import inspect
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import train_noodds_v307_native_multiclass_stagewise_on_v295 as v307


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


def test_preregistered_native_stage_classes_are_fixed():
    cfg = json.loads(
        (
            ROOT
            / "configs"
            / "noodds_v307_native_multiclass_stagewise_on_v295_preregistered.json"
        ).read_text()
    )
    assert [cfg["model"][f"stage{i}"]["num_class"] for i in (1, 2, 3)] == [
        6,
        5,
        4,
    ]
    assert cfg["anchoring"]["gamma_bounds"] == [0, 0.25]
    assert "factorization search" in cfg["forbidden"]


def test_remaining_candidates_and_local_positions_are_exact():
    first = np.asarray([0, 4], dtype=np.int8)
    second = np.asarray([2, 1], dtype=np.int8)
    remaining2 = v307.remaining_candidates(first)
    remaining3 = v307.remaining_candidates(first, second)
    assert remaining2.shape == (2, 5)
    assert remaining3.shape == (2, 4)
    assert np.array_equal(
        v307.local_positions(remaining2, np.asarray([3, 5])),
        np.asarray([2, 4]),
    )
    assert np.array_equal(
        v307.local_positions(remaining3, np.asarray([4, 3])),
        np.asarray([2, 2]),
    )


def test_local_positions_reject_missing_target():
    candidates = np.asarray([[0, 1, 2, 3, 4]], dtype=np.int8)
    try:
        v307.local_positions(candidates, np.asarray([5], dtype=np.int8))
    except ValueError as error:
        assert "not present exactly once" in str(error)
    else:
        raise AssertionError("missing target must be rejected")


def test_stage_matrices_have_frozen_context_widths():
    block = _block(rows=2, runner_width=2, race_width=1)
    first = np.asarray([0, 4], dtype=np.int8)
    second = np.asarray([2, 1], dtype=np.int8)
    stage1 = v307.build_stage_matrix(block, runner_width=2)
    stage2 = v307.build_stage_matrix(
        block, runner_width=2, first=first
    )
    stage3 = v307.build_stage_matrix(
        block, runner_width=2, first=first, second=second
    )
    assert stage1.shape == (2, 13)
    assert stage2.shape == (2, 21)
    assert stage3.shape == (2, 29)
    assert np.array_equal(stage2[:, 12:14], block[np.arange(2), first, :2])
    assert np.array_equal(stage2[:, 14:20], np.eye(6)[first])


class _UniformModel:
    def __init__(self, classes):
        self.classes_ = np.arange(classes)

    def predict_proba(self, matrix):
        return np.full((len(matrix), len(self.classes_)), 1.0 / len(self.classes_))


def test_uniform_native_heads_reconstruct_uniform_exact_top3():
    block = _block(rows=3, runner_width=2, race_width=1)
    probability = v307.predict_contextual(
        (_UniformModel(6), _UniformModel(5), _UniformModel(4)),
        block,
        np.arange(3),
        runner_width=2,
    )
    assert probability.shape == (3, 120)
    assert np.allclose(probability, 1.0 / 120.0)
    assert np.allclose(probability.sum(axis=1), 1.0)


def test_predict_multiclass_expands_missing_classes():
    class Partial:
        classes_ = np.asarray([0, 2])

        def predict_proba(self, matrix):
            return np.tile(np.asarray([[0.25, 0.75]]), (len(matrix), 1))

    expanded = v307.predict_multiclass(Partial(), np.zeros((3, 2)), 4)
    assert expanded.shape == (3, 4)
    assert np.allclose(expanded[:, 0], 0.25)
    assert np.allclose(expanded[:, 2], 0.75)
    assert np.allclose(expanded[:, [1, 3]], 0.0)


def test_gamma_zero_reproduces_parent_and_fit_uses_true_context():
    parent = _prob(5, 1)
    standalone = _prob(5, 2)
    result = v307.anchored_probability(parent, standalone, 0.0)
    assert np.allclose(result, parent, atol=1e-12)
    signature = inspect.signature(v307.fit_models)
    assert "parent" not in signature.parameters
    source = inspect.getsource(v307.fit_models)
    assert "first=target[:, 0]" in source
    assert "second=target[:, 1]" in source
    assert "local_positions(candidates2, target[:, 1])" in source
    assert "local_positions(candidates3, target[:, 2])" in source
