import json
import sys
from pathlib import Path

import numpy as np
import pytest
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import train_noodds_v331_identity_warmup_freeze_on_v312 as v331


def config():
    return json.loads(v331.PREREGISTRATION.read_text(encoding="utf-8"))


def small_model():
    original_columns = v331.v311.IDENTITY_COLUMNS
    original_names = v331.v311.IDENTITY_NAMES
    v331.v311.IDENTITY_COLUMNS = (0,)
    v331.v311.IDENTITY_NAMES = ("racer_code",)
    try:
        model = v331.v311.IdentityStagewiseSetRanker(
            4,
            3,
            [8],
            {"embedding_widths": {"racer_code": 4}},
            {
                "runner_projection_width": 12,
                "attention_heads": 3,
                "feedforward_width": 24,
                "dropout": 0.0,
                "self_attention_layers": 1,
            },
        )
    finally:
        v331.v311.IDENTITY_COLUMNS = original_columns
        v331.v311.IDENTITY_NAMES = original_names
    return model


def test_preregistration_fixes_two_phase_schedule():
    cfg = config()
    assert cfg["training"]["batch_races"] == 256
    assert cfg["training"]["learning_rate"] == 0.0003
    assert cfg["training"]["weight_decay"] == 0.001
    assert cfg["training"]["seed"] == 31201
    assert cfg["training_phases"]["screen_phase1_epochs"] == [1]
    assert cfg["training_phases"]["screen_phase2_epochs"] == [2, 3]
    assert cfg["training_phases"]["full_phase1_epochs"] == [1, 2]
    assert cfg["training_phases"]["full_phase2_epochs"] == [3, 4, 5, 6]
    assert cfg["training_phases"]["phase_search"] is False


def test_trainable_toggle_changes_only_identity_parameters():
    model = small_model()
    identity_ids = {id(parameter) for parameter in v331.identity_parameters(model)}
    assert identity_ids
    v331.set_identity_trainable(model, False)
    for parameter in model.parameters():
        assert parameter.requires_grad is (id(parameter) not in identity_ids)
    v331.set_identity_trainable(model, True)
    assert all(parameter.requires_grad for parameter in model.parameters())


def test_train_predict_records_screen_phases_and_restores_trainability(tmp_path):
    cfg = config()
    cfg["architecture"] = {
        "runner_projection_width": 12,
        "attention_heads": 3,
        "feedforward_width": 24,
        "dropout": 0.0,
        "self_attention_layers": 1,
    }
    cfg["identity_features"]["embedding_width"] = 4
    cfg["training"].update({"threads": 1, "batch_races": 4})
    rng = np.random.default_rng(331)
    runner = rng.normal(size=(12, 6, 4)).astype(np.float32)
    race = rng.normal(size=(12, 3)).astype(np.float32)
    identity = np.asarray(
        [[[100 + lane] for lane in range(6)]] * 12, dtype=np.float64
    )
    targets = np.asarray(
        [[0, 1, 2], [1, 2, 3], [2, 3, 4], [3, 4, 5]] * 3,
        dtype=np.int64,
    )
    model_path = tmp_path / "model.pt"
    probability, diagnostics = v331.train_and_predict(
        runner,
        race,
        identity,
        targets,
        np.arange(8),
        np.arange(8, 12),
        cfg,
        "screen",
        "d6",
        model_path,
    )
    saved = torch.load(model_path, weights_only=False)
    expected = [False, True, True]
    assert probability.shape == (4, 120)
    assert np.allclose(probability.sum(axis=1), 1.0, atol=1e-6)
    assert saved["training_phases"]["frozen_epochs"] == [1]
    assert saved["training_phases"]["identity_trainable_by_epoch"] == expected
    assert diagnostics["training_phases"]["identity_trainable_by_epoch"] == expected
    assert diagnostics["training_phases"]["single_optimizer"] is True
    assert diagnostics["training_phases"]["other_training_changes"] == 0


def test_invalid_freeze_epoch_is_rejected(tmp_path):
    cfg = config()
    cfg["training_phases"]["screen_phase1_epochs"] = [4]
    runner = np.zeros((2, 6, 1), dtype=np.float32)
    race = np.zeros((2, 1), dtype=np.float32)
    identity = np.ones((2, 6, 1), dtype=np.float64)
    targets = np.asarray([[0, 1, 2], [1, 2, 3]], dtype=np.int64)
    with pytest.raises(ValueError, match="outside training budget"):
        v331.train_and_predict(
            runner,
            race,
            identity,
            targets,
            np.asarray([0]),
            np.asarray([1]),
            cfg,
            "screen",
            "d6",
            tmp_path / "model.pt",
        )
