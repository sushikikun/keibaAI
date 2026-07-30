import inspect
import json
import sys
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import train_noodds_v310_large_history_permutation_equivariant_stagewise_on_v295 as v310


def _config():
    return json.loads(
        (
            ROOT
            / "configs"
            / "noodds_v310_large_history_permutation_equivariant_stagewise_on_v295_preregistered.json"
        ).read_text(encoding="utf-8")
    )


def _model(runner_width=10, race_width=6):
    cfg = {
        "runner_projection_width": 12,
        "attention_heads": 3,
        "feedforward_width": 24,
        "dropout": 0.0,
        "self_attention_layers": 1,
    }
    torch.manual_seed(310)
    model = v310.StagewiseSetRanker(runner_width, race_width, cfg)
    model.eval()
    return model


def test_preregistered_architecture_and_history_are_fixed():
    cfg = _config()
    assert cfg["training_data"]["full_train_races"] == {
        "d6": 50788,
        "d7": 55225,
        "d8": 59840,
    }
    assert cfg["features"]["pairwise_tau"] == 20
    assert cfg["features"]["current_meet_window_calendar_days"] == 7
    assert cfg["architecture"]["permutation_equivariance"] is True
    assert cfg["training"]["seed"] == 31001
    assert cfg["training"]["search"] is False
    assert cfg["anchoring"]["gamma_bounds"] == [0.0, 0.25]


def test_normalization_uses_only_supplied_training_indices():
    runner = np.zeros((3, 6, 2), dtype=np.float32)
    race = np.zeros((3, 2), dtype=np.float32)
    runner[0] = 1.0
    runner[1] = 3.0
    runner[2] = 1000.0
    race[0] = 2.0
    race[1] = 4.0
    race[2] = 2000.0
    stats = v310.fit_normalization(
        runner, race, np.asarray([0, 1], dtype=np.int64)
    )
    assert np.allclose(stats["runner_mean"], [2.0, 2.0])
    assert np.allclose(stats["race_mean"], [3.0, 3.0])


def test_stage_masks_exclude_used_runners():
    model = _model()
    runner = torch.randn(2, 6, 10)
    race = torch.randn(2, 6)
    _, stage2, stage3 = model(runner, race)
    for lane in range(6):
        assert torch.all(stage2[:, lane, lane] < -1e8)
    for first in range(6):
        for second in range(6):
            if first == second:
                continue
            assert torch.all(stage3[:, first, second, first] < -1e8)
            assert torch.all(stage3[:, first, second, second] < -1e8)


def test_joint_probability_has_120_normalized_outcomes():
    model = _model()
    runner = torch.randn(4, 6, 10)
    race = torch.randn(4, 6)
    probability = v310.joint_probabilities(model(runner, race))
    assert probability.shape == (4, 120)
    assert torch.all(probability > 0)
    assert torch.allclose(probability.sum(dim=1), torch.ones(4), atol=1e-6)


def test_model_is_equivariant_when_runner_and_lane_ids_move_together():
    model = _model()
    runner = torch.randn(2, 6, 10)
    race = torch.randn(2, 6)
    permutation = torch.tensor([2, 5, 1, 0, 4, 3])
    original = model(runner, race)
    moved = model(
        runner[:, permutation],
        race,
        lane_ids=torch.arange(6)[permutation],
    )
    assert torch.allclose(moved[0], original[0][:, permutation], atol=1e-6)
    expected2 = original[1][:, permutation][:, :, permutation]
    assert torch.allclose(moved[1], expected2, atol=1e-5)
    expected3 = original[2][:, permutation][:, :, permutation][
        :, :, :, permutation
    ]
    assert torch.allclose(moved[2], expected3, atol=1e-5)


def test_stagewise_nll_uses_only_observed_top_three():
    model = _model()
    runner = torch.randn(3, 6, 10)
    race = torch.randn(3, 6)
    target = torch.tensor([[0, 1, 2], [5, 3, 0], [2, 4, 1]])
    loss = v310.stagewise_nll(model(runner, race), target)
    assert loss.ndim == 0
    assert torch.isfinite(loss)


def test_zero_gamma_reproduces_parent_exactly():
    rng = np.random.default_rng(310)
    parent = rng.random((5, 120))
    parent /= parent.sum(axis=1, keepdims=True)
    standalone = rng.random((5, 120))
    standalone /= standalone.sum(axis=1, keepdims=True)
    actual = v310.anchored_probability(parent, standalone, 0.0)
    assert np.allclose(actual, parent, atol=1e-12)




def test_train_predict_saves_after_releasing_training_arrays(tmp_path):
    rng = np.random.default_rng(311)
    runner = rng.normal(size=(12, 6, 3)).astype(np.float32)
    race = rng.normal(size=(12, 2)).astype(np.float32)
    targets = np.asarray(
        [[0, 1, 2], [1, 2, 3], [2, 3, 4], [3, 4, 5]] * 3,
        dtype=np.int64,
    )
    prereg = {
        "architecture": {
            "runner_projection_width": 12,
            "attention_heads": 3,
            "feedforward_width": 24,
            "dropout": 0.0,
            "self_attention_layers": 1,
        },
        "training": {
            "epochs_screen": 1,
            "epochs_full": 1,
            "seed": 31001,
            "threads": 1,
            "learning_rate": 0.0003,
            "weight_decay": 0.001,
            "batch_races": 4,
            "gradient_clip": 1.0,
        },
    }
    path = tmp_path / "model.pt"
    probability, diagnostics = v310.train_and_predict(
        runner,
        race,
        targets,
        np.arange(8),
        np.arange(8, 12),
        prereg,
        "screen",
        "d6",
        path,
    )
    assert path.exists()
    assert probability.shape == (4, 120)
    assert np.allclose(probability.sum(axis=1), 1.0, atol=1e-6)
    assert diagnostics["train_races"] == 8

def test_fold_training_and_gamma_are_strictly_prior():
    source = inspect.getsource(v310.main)
    assert 'for fold, prior in (("d7", ["d6"]), ("d8", ["d6", "d7"]))' in source
    assert 'gamma = {"d6": 0.0}' in source
    assert 'folds[fold]["train_indices"]' in source
    cfg = _config()
    assert cfg["policy"]["same_day_validation_result_used"] is False
    assert cfg["policy"]["future_information_used"] is False
    assert "post-result changes" in cfg["forbidden"]
