import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import train_noodds_v303_categorical_identity_exact_top3_on_v295 as v303


def _prob(rows, seed):
    rng = np.random.default_rng(seed)
    values = rng.random((rows, 120))
    return values / values.sum(axis=1, keepdims=True)


def _blocks():
    numeric = np.arange(6 * 3, dtype=np.float32).reshape(1, 6, 3)
    runner_cat = np.asarray(
        [[[100 + lane, 10 + lane, 200 + lane, 300 + lane] for lane in range(6)]],
        dtype=np.int32,
    )
    race_cat = np.asarray([[7, 11]], dtype=np.int32)
    return numeric, runner_cat, race_cat


def test_preregistered_category_layout_is_fixed():
    cfg = json.loads(
        (ROOT / "configs" / "noodds_v303_categorical_identity_exact_top3_on_v295_preregistered.json").read_text()
    )
    assert cfg["features"]["runner_categorical_indices"] == [0, 1, 2, 3]
    assert cfg["features"]["race_categorical_indices"] == [0, 1]
    assert v303.RUNNER_CATEGORY_INDICES.tolist() == [0, 1, 2, 3]
    assert v303.RACE_CATEGORY_INDICES.tolist() == [0, 1]


def test_stage1_keeps_category_ids_unmodified():
    numeric, runner_cat, race_cat = _blocks()
    matrix, categorical = v303.build_stage1_matrix(numeric, runner_cat, race_cat)
    assert matrix.shape == (6, 9)
    assert categorical == list(range(3, 9))
    assert np.array_equal(matrix[:, 3:7], runner_cat.reshape(6, 4))
    assert np.array_equal(matrix[:, 7:9], np.repeat(race_cat, 6, axis=0))


def test_stage2_has_candidate_and_first_categories_without_arithmetic():
    numeric, runner_cat, race_cat = _blocks()
    matrix, candidates, categorical = v303.build_context_matrix(
        numeric, runner_cat, race_cat, np.asarray([2]), runner_width=2
    )
    assert candidates.tolist() == [[0, 1, 3, 4, 5]]
    assert matrix.shape == (5, 17)
    assert categorical == list(range(7, 17))
    assert np.array_equal(matrix[:, 7:11], runner_cat[0, candidates[0]])
    assert np.array_equal(matrix[:, 11:15], np.repeat(runner_cat[0, 2][None, :], 5, axis=0))
    assert np.array_equal(matrix[:, 15:17], np.repeat(race_cat, 5, axis=0))


def test_stage3_has_three_runner_category_blocks():
    numeric, runner_cat, race_cat = _blocks()
    matrix, candidates, categorical = v303.build_context_matrix(
        numeric,
        runner_cat,
        race_cat,
        np.asarray([2]),
        runner_width=2,
        second=np.asarray([4]),
    )
    assert candidates.tolist() == [[0, 1, 3, 5]]
    assert matrix.shape == (4, 25)
    assert categorical == list(range(11, 25))
    assert np.array_equal(matrix[:, 11:15], runner_cat[0, candidates[0]])
    assert np.array_equal(matrix[:, 15:19], np.repeat(runner_cat[0, 2][None, :], 4, axis=0))
    assert np.array_equal(matrix[:, 19:23], np.repeat(runner_cat[0, 4][None, :], 4, axis=0))


def test_model_params_keep_frozen_category_regularization():
    cfg = json.loads(
        (ROOT / "configs" / "noodds_v303_categorical_identity_exact_top3_on_v295_preregistered.json").read_text()
    )["model"]
    params = v303.model_params(cfg, "screen", 1)
    assert params["n_estimators"] == 82
    assert params["max_cat_to_onehot"] == 32
    assert params["cat_l2"] == 20
    assert params["cat_smooth"] == 50
    assert params["min_data_per_group"] == 100


def test_gamma_zero_reproduces_parent_and_normalizes():
    parent = _prob(5, 1)
    standalone = _prob(5, 2)
    result = v303.anchored_probability(parent, standalone, 0.0)
    assert np.allclose(result, parent, atol=1e-12)
    assert np.allclose(result.sum(axis=1), 1.0)


def test_training_passes_native_categorical_columns():
    text = (ROOT / "scripts" / "train_noodds_v303_categorical_identity_exact_top3_on_v295.py").read_text()
    assert text.count("categorical_feature=cat") == 3
    category_section = text[text.index("def build_context_matrix"):text.index("def softmax")]
    assert "categories" in category_section
    assert "category_pieces" in category_section
    assert "categories -" not in category_section
