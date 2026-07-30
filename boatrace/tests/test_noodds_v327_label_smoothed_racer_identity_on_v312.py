import json
import sys
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import train_noodds_v327_label_smoothed_racer_identity_on_v312 as v327


def config():
    return json.loads(v327.PREREGISTRATION.read_text(encoding="utf-8"))


def masked_logits(seed=327, rows=5):
    generator = torch.Generator().manual_seed(seed)
    stage1 = torch.randn(rows, 6, generator=generator)
    stage2 = torch.randn(rows, 6, 6, generator=generator)
    stage3 = torch.randn(rows, 6, 6, 6, generator=generator)
    eye = torch.eye(6, dtype=torch.bool)
    stage2 = stage2.masked_fill(eye[None], -1e9)
    lanes = torch.arange(6)
    used = (lanes[None, None, :] == lanes[:, None, None]) | (
        lanes[None, None, :] == lanes[None, :, None]
    )
    stage3 = stage3.masked_fill(used[None], -1e9)
    return stage1, stage2, stage3


def test_preregistration_fixes_conditional_smoothing_only():
    cfg = config()
    assert cfg["training"]["batch_races"] == 256
    assert cfg["training"]["weight_decay"] == 0.001
    assert cfg["training"]["seed"] == 31201
    assert cfg["loss_regularization"]["epsilon"] == 0.02
    assert cfg["loss_regularization"]["stage1_valid_classes"] == 6
    assert cfg["loss_regularization"]["stage2_valid_classes"] == 5
    assert cfg["loss_regularization"]["stage3_valid_classes"] == 4
    assert cfg["loss_regularization"]["epsilon_search"] is False


def test_zero_smoothing_matches_parent_stagewise_nll():
    logits = masked_logits()
    targets = torch.tensor(
        [[0, 1, 2], [1, 2, 3], [2, 3, 4], [3, 4, 5], [4, 5, 0]]
    )
    expected = v327.v310.stagewise_nll(logits, targets)
    actual = v327.conditional_smoothed_nll(logits, targets, epsilon=0.0)
    assert torch.allclose(actual, expected, atol=1e-7)


def test_smoothing_is_finite_and_ignores_already_used_lanes():
    logits = list(masked_logits(rows=2))
    targets = torch.tensor([[0, 1, 2], [2, 4, 5]])
    first = v327.conditional_smoothed_nll(tuple(logits), targets, 0.02)
    changed = [value.clone() for value in logits]
    changed[1][0, 0, 0] = -5e8
    changed[2][0, 0, 1, 0] = -5e8
    changed[2][0, 0, 1, 1] = -5e8
    second = v327.conditional_smoothed_nll(tuple(changed), targets, 0.02)
    assert torch.isfinite(first)
    assert torch.allclose(first, second, atol=1e-7)


def test_train_predict_normalizes_records_loss_and_restores_parent(tmp_path):
    cfg = config()
    cfg["architecture"] = {
        "runner_projection_width": 12,
        "attention_heads": 3,
        "feedforward_width": 24,
        "dropout": 0.0,
        "self_attention_layers": 1,
    }
    cfg["identity_features"]["embedding_width"] = 4
    cfg["training"].update(
        {"epochs_screen": 1, "epochs_full": 1, "threads": 1, "batch_races": 4}
    )
    rng = np.random.default_rng(327)
    runner = rng.normal(size=(12, 6, 4)).astype(np.float32)
    race = rng.normal(size=(12, 3)).astype(np.float32)
    identity = np.asarray(
        [[[100 + lane] for lane in range(6)]] * 12, dtype=np.float64
    )
    targets = np.asarray(
        [[0, 1, 2], [1, 2, 3], [2, 3, 4], [3, 4, 5]] * 3,
        dtype=np.int64,
    )
    original_loss = v327.v310.stagewise_nll
    original_columns = v327.v311.IDENTITY_COLUMNS
    probability, diagnostics = v327.train_and_predict(
        runner,
        race,
        identity,
        targets,
        np.arange(8),
        np.arange(8, 12),
        cfg,
        "screen",
        "d6",
        tmp_path / "model.pt",
    )
    assert probability.shape == (4, 120)
    assert np.allclose(probability.sum(axis=1), 1.0, atol=1e-6)
    assert diagnostics["loss_regularization"] == {
        "method": "conditional_label_smoothing",
        "epsilon": 0.02,
        "valid_classes": [6, 5, 4],
        "invalid_used_lanes_receive_mass": False,
        "parent_seed_reused": 31201,
        "other_training_changes": 0,
    }
    assert v327.v310.stagewise_nll is original_loss
    assert v327.v311.IDENTITY_COLUMNS == original_columns
