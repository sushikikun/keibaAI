import json
import sys
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import train_noodds_v330_racer_embedding_dropout_on_v312 as v330


def config():
    return json.loads(v330.PREREGISTRATION.read_text(encoding="utf-8"))


def small_model(dropout_probability):
    architecture = {
        "runner_projection_width": 12,
        "attention_heads": 3,
        "feedforward_width": 24,
        "dropout": 0.0,
        "self_attention_layers": 1,
    }
    identity = {
        "embedding_widths": {"racer_code": 4},
        "embedding_dropout_probability": dropout_probability,
    }
    original_columns = v330.v311.IDENTITY_COLUMNS
    original_names = v330.v311.IDENTITY_NAMES
    v330.v311.IDENTITY_COLUMNS = (0,)
    v330.v311.IDENTITY_NAMES = ("racer_code",)
    try:
        model = v330.RacerEmbeddingDropoutSetRanker(
            4, 3, [8], identity, architecture
        )
    finally:
        v330.v311.IDENTITY_COLUMNS = original_columns
        v330.v311.IDENTITY_NAMES = original_names
    return model


def model_inputs():
    runner = torch.randn(5, 6, 4)
    race = torch.randn(5, 3)
    identity = torch.arange(6)[None, :, None].expand(5, -1, -1) + 1
    return runner, race, identity


def test_preregistration_fixes_embedding_dropout_only():
    cfg = config()
    assert cfg["identity_features"]["embedding_width"] == 16
    assert cfg["architecture"]["dropout"] == 0.1
    assert cfg["training"]["batch_races"] == 256
    assert cfg["training"]["learning_rate"] == 0.0003
    assert cfg["training"]["weight_decay"] == 0.001
    assert cfg["training"]["seed"] == 31201
    assert cfg["identity_regularization"]["probability"] == 0.10
    assert cfg["identity_regularization"]["training_only"] is True
    assert cfg["identity_regularization"]["inference_disabled"] is True
    assert cfg["identity_regularization"]["dropout_search"] is False


def test_zero_embedding_dropout_matches_parent_model():
    torch.manual_seed(330)
    candidate = small_model(0.0)
    original_columns = v330.v311.IDENTITY_COLUMNS
    original_names = v330.v311.IDENTITY_NAMES
    v330.v311.IDENTITY_COLUMNS = (0,)
    v330.v311.IDENTITY_NAMES = ("racer_code",)
    try:
        parent = v330._BASE_MODEL(
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
        v330.v311.IDENTITY_COLUMNS = original_columns
        v330.v311.IDENTITY_NAMES = original_names
    parent.load_state_dict(candidate.state_dict())
    candidate.eval()
    parent.eval()
    inputs = model_inputs()
    for left, right in zip(candidate(*inputs), parent(*inputs)):
        assert torch.allclose(left, right, atol=1e-7)


def test_embedding_dropout_is_training_only():
    torch.manual_seed(331)
    model = small_model(0.10)
    inputs = model_inputs()
    model.train()
    first_train = model(*inputs)[0]
    second_train = model(*inputs)[0]
    assert not torch.equal(first_train, second_train)
    model.eval()
    first_eval = model(*inputs)[0]
    second_eval = model(*inputs)[0]
    assert torch.equal(first_eval, second_eval)


def test_train_predict_normalizes_records_and_restores_parent(tmp_path):
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
    rng = np.random.default_rng(330)
    runner = rng.normal(size=(12, 6, 4)).astype(np.float32)
    race = rng.normal(size=(12, 3)).astype(np.float32)
    identity = np.asarray(
        [[[100 + lane] for lane in range(6)]] * 12, dtype=np.float64
    )
    targets = np.asarray(
        [[0, 1, 2], [1, 2, 3], [2, 3, 4], [3, 4, 5]] * 3,
        dtype=np.int64,
    )
    original_model = v330.v311.IdentityStagewiseSetRanker
    original_columns = v330.v311.IDENTITY_COLUMNS
    probability, diagnostics = v330.train_and_predict(
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
    assert diagnostics["identity_regularization"] == {
        "method": "racer_embedding_dropout",
        "probability": 0.10,
        "training_only": True,
        "parent_seed_reused": 31201,
        "other_training_changes": 0,
    }
    assert v330.v311.IdentityStagewiseSetRanker is original_model
    assert v330.v311.IDENTITY_COLUMNS == original_columns
