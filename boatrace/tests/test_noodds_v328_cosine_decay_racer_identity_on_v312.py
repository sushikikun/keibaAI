import json
import sys
from pathlib import Path

import numpy as np
import pytest
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import train_noodds_v328_cosine_decay_racer_identity_on_v312 as v328


def config():
    return json.loads(v328.PREREGISTRATION.read_text(encoding="utf-8"))


def test_preregistration_changes_only_fixed_learning_rate_schedule():
    cfg = config()
    assert cfg["identity_features"]["embedding_width"] == 16
    assert cfg["architecture"]["dropout"] == 0.1
    assert cfg["training"]["batch_races"] == 256
    assert cfg["training"]["learning_rate"] == 0.0003
    assert cfg["training"]["weight_decay"] == 0.001
    assert cfg["training"]["seed"] == 31201
    assert cfg["learning_rate_schedule"]["method"] == "CosineAnnealingLR"
    assert cfg["learning_rate_schedule"]["minimum_learning_rate"] == 0.00003
    assert cfg["learning_rate_schedule"]["warmup_epochs"] == 0
    assert cfg["learning_rate_schedule"]["schedule_search"] is False
    assert cfg["anchoring"]["gamma_bounds"] == [0.0, 0.25]


def test_runtime_contract_preserves_racer_only_identity():
    cfg = v328.runtime_preregistration(config())
    assert cfg["identity_features"]["embedding_widths"] == {
        "racer_code": 16
    }


def test_train_predict_uses_saved_cosine_epoch_rates(tmp_path):
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
    rng = np.random.default_rng(328)
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
    probability, diagnostics = v328.train_and_predict(
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
    expected_rates = [0.0003, 0.0002325, 0.0000975]
    assert probability.shape == (4, 120)
    assert np.allclose(probability.sum(axis=1), 1.0, atol=1e-6)
    assert saved["learning_rate_schedule"]["method"] == "CosineAnnealingLR"
    assert saved["learning_rate_schedule"]["epoch_rates"] == pytest.approx(
        expected_rates
    )
    assert diagnostics["learning_rate_schedule"]["epoch_rates"] == pytest.approx(
        expected_rates
    )
    assert diagnostics["learning_rate_schedule"]["other_training_changes"] == 0


def test_invalid_minimum_learning_rate_is_rejected(tmp_path):
    cfg = config()
    cfg["learning_rate_schedule"]["minimum_learning_rate"] = 0.0003
    runner = np.zeros((2, 6, 1), dtype=np.float32)
    race = np.zeros((2, 1), dtype=np.float32)
    identity = np.ones((2, 6, 1), dtype=np.float64)
    targets = np.asarray([[0, 1, 2], [1, 2, 3]], dtype=np.int64)
    with pytest.raises(ValueError, match="below initial"):
        v328.train_and_predict(
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
