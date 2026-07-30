import inspect
import json
import sys
from pathlib import Path

import numpy as np
import pytest
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import train_noodds_v310_large_history_permutation_equivariant_stagewise_on_v295 as v310
import train_noodds_v311_large_history_identity_set_ranker_on_v295 as v311


def _config():
    return json.loads(
        (
            ROOT
            / "configs"
            / "noodds_v311_large_history_identity_set_ranker_on_v295_preregistered.json"
        ).read_text(encoding="utf-8")
    )


def _architecture():
    return {
        "runner_projection_width": 12,
        "attention_heads": 3,
        "feedforward_width": 24,
        "dropout": 0.0,
        "self_attention_layers": 1,
    }


def _identity_config():
    return {
        "embedding_widths": {
            "racer_code": 4,
            "branch_code": 2,
            "venue_motor_code": 3,
            "venue_boat_code": 3,
        }
    }


def _model(runner_width=5, race_width=3):
    torch.manual_seed(311)
    model = v311.IdentityStagewiseSetRanker(
        runner_width,
        race_width,
        [20, 8, 20, 20],
        _identity_config(),
        _architecture(),
    )
    model.eval()
    return model


def test_preregistered_identity_definition_is_fixed():
    cfg = _config()
    assert cfg["base_definition"]["full_train_races"] == {
        "d6": 50788,
        "d7": 55225,
        "d8": 59840,
    }
    assert cfg["identity_features"]["runner_columns"] == {
        "racer_code": 0,
        "branch_code": 1,
        "venue_motor_code": 2,
        "venue_boat_code": 3,
    }
    assert cfg["identity_features"]["vocabulary"] == (
        "built from each fold training indices only"
    )
    assert cfg["identity_features"]["embedding_widths"] == {
        "racer_code": 16,
        "branch_code": 4,
        "venue_motor_code": 8,
        "venue_boat_code": 8,
    }
    assert cfg["training"]["search"] is False
    assert cfg["anchoring"]["gamma_bounds"] == [0.0, 0.25]


def test_vocabulary_is_training_only_and_unseen_maps_to_zero():
    raw = np.asarray(
        [
            [[10, 1, 100, 200]] * 6,
            [[20, 2, 101, 201]] * 6,
            [[999, 9, 999, 999]] * 6,
        ],
        dtype=np.float64,
    )
    vocab = v311.fit_identity_vocabulary(raw, np.asarray([0, 1]))
    assert 999 not in vocab[0]
    encoded, audit = v311.encode_identity(raw, np.asarray([2]), vocab)
    assert np.all(encoded == 0)
    assert audit["racer_code"]["unknown_rate"] == 1.0


def test_nonpositive_and_nonfinite_identity_map_to_zero():
    raw = np.asarray([[[1, 2, 3, 4]] * 6], dtype=np.float64)
    vocab = v311.fit_identity_vocabulary(raw, np.asarray([0]))
    probe = raw.copy()
    probe[0, 0] = [0, -1, np.nan, np.inf]
    encoded, _ = v311.encode_identity(probe, np.asarray([0]), vocab)
    assert np.all(encoded[0, 0] == 0)


def test_fractional_identity_is_rejected():
    raw = np.asarray([[[1, 2, 3, 4]] * 6], dtype=np.float64)
    raw[0, 2, 0] = 1.5
    with pytest.raises(ValueError, match="not integer encoded"):
        v311.fit_identity_vocabulary(raw, np.asarray([0]))


def test_stage_masks_and_joint_probability_are_valid():
    model = _model()
    runner = torch.randn(3, 6, 5)
    race = torch.randn(3, 3)
    identity = torch.randint(0, 8, (3, 6, 4))
    stage1, stage2, stage3 = model(runner, race, identity)
    assert stage1.shape == (3, 6)
    for lane in range(6):
        assert torch.all(stage2[:, lane, lane] < -1e8)
    for first in range(6):
        for second in range(6):
            if first == second:
                continue
            assert torch.all(stage3[:, first, second, first] < -1e8)
            assert torch.all(stage3[:, first, second, second] < -1e8)
    probability = v310.joint_probabilities((stage1, stage2, stage3))
    assert probability.shape == (3, 120)
    assert torch.all(probability > 0)
    assert torch.allclose(probability.sum(dim=1), torch.ones(3), atol=1e-6)


def test_identity_model_is_equivariant_when_all_runner_inputs_move_together():
    model = _model()
    runner = torch.randn(2, 6, 5)
    race = torch.randn(2, 3)
    identity = torch.randint(0, 8, (2, 6, 4))
    permutation = torch.tensor([2, 5, 1, 0, 4, 3])
    original = model(runner, race, identity)
    moved = model(
        runner[:, permutation],
        race,
        identity[:, permutation],
        lane_ids=torch.arange(6)[permutation],
    )
    assert torch.allclose(moved[0], original[0][:, permutation], atol=1e-6)
    expected2 = original[1][:, permutation][:, :, permutation]
    assert torch.allclose(moved[1], expected2, atol=1e-5)
    expected3 = original[2][:, permutation][:, :, permutation][
        :, :, :, permutation
    ]
    assert torch.allclose(moved[2], expected3, atol=1e-5)


def test_train_predict_saves_vocabulary_and_probabilities(tmp_path):
    rng = np.random.default_rng(311)
    runner = rng.normal(size=(12, 6, 4)).astype(np.float32)
    race = rng.normal(size=(12, 3)).astype(np.float32)
    identity = np.empty((12, 6, 4), dtype=np.float64)
    for race_index in range(12):
        for lane in range(6):
            identity[race_index, lane] = [
                100 + race_index * 6 + lane,
                1 + lane % 3,
                200 + lane,
                300 + lane,
            ]
    targets = np.asarray(
        [[0, 1, 2], [1, 2, 3], [2, 3, 4], [3, 4, 5]] * 3,
        dtype=np.int64,
    )
    prereg = {
        "identity_features": _identity_config(),
        "architecture": _architecture(),
        "training": {
            "epochs_screen": 1,
            "epochs_full": 1,
            "seed": 31101,
            "threads": 1,
            "learning_rate": 0.0003,
            "weight_decay": 0.001,
            "batch_races": 4,
            "gradient_clip": 1.0,
        },
    }
    path = tmp_path / "model.pt"
    probability, diagnostics = v311.train_and_predict(
        runner,
        race,
        identity,
        targets,
        np.arange(8),
        np.arange(8, 12),
        prereg,
        "screen",
        "d6",
        path,
    )
    saved = torch.load(path, weights_only=False)
    assert probability.shape == (4, 120)
    assert np.allclose(probability.sum(axis=1), 1.0, atol=1e-6)
    assert len(saved["vocabulary"]) == 4
    assert diagnostics["train_races"] == 8
    assert diagnostics["validation_identity"]["racer_code"][
        "unknown_rate"
    ] == 1.0


def test_fold_training_and_gamma_are_strictly_prior():
    source = inspect.getsource(v311.main)
    assert 'for fold, prior in (("d7", ["d6"]), ("d8", ["d6", "d7"]))' in source
    assert 'gamma = {"d6": 0.0}' in source
    assert 'folds[fold]["train_indices"]' in source
    cfg = _config()
    assert cfg["policy"]["same_day_validation_result_used"] is False
    assert cfg["policy"]["future_information_used"] is False
    assert "global vocabulary built from validation or future races" in cfg["forbidden"]
