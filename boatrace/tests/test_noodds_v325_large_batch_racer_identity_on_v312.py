import json
import sys
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import train_noodds_v325_large_batch_racer_identity_on_v312 as v325


def config():
    return json.loads(
        v325.PREREGISTRATION.read_text(encoding="utf-8")
    )


def test_preregistration_changes_only_batch_size():
    cfg = config()
    assert cfg["identity_features"]["embedding_width"] == 16
    assert cfg["identity_features"]["parent_embedding_width"] == 16
    assert cfg["architecture"]["dropout"] == 0.1
    assert cfg["architecture"]["runner_projection_width"] == 48
    assert cfg["training"]["seed"] == 31201
    assert cfg["training"]["batch_races"] == 512
    assert cfg["training"]["weight_decay"] == 0.001
    assert cfg["training"]["epochs_full"] == 6
    assert cfg["anchoring"]["gamma_bounds"] == [0.0, 0.25]


def test_runtime_contract_preserves_parent_width_and_batch():
    cfg = v325.runtime_preregistration(config())
    assert cfg["identity_features"]["embedding_widths"] == {
        "racer_code": 16
    }
    assert cfg["training"]["batch_races"] == 512
    assert cfg["training"]["weight_decay"] == 0.001
    assert cfg["training"]["seed"] == 31201


def test_train_predict_normalizes_and_records_batch_change(tmp_path):
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
        {
            "epochs_screen": 1,
            "epochs_full": 1,
            "threads": 1,
            "batch_races": 4,
        }
    )
    rng = np.random.default_rng(325)
    runner = rng.normal(size=(12, 6, 4)).astype(np.float32)
    race = rng.normal(size=(12, 3)).astype(np.float32)
    identity = np.asarray(
        [[[100 + lane] for lane in range(6)]] * 12,
        dtype=np.float64,
    )
    targets = np.asarray(
        [[0, 1, 2], [1, 2, 3], [2, 3, 4], [3, 4, 5]] * 3,
        dtype=np.int64,
    )
    probability, diagnostics = v325.train_and_predict(
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
    saved = torch.load(tmp_path / "model.pt", weights_only=False)
    assert probability.shape == (4, 120)
    assert np.allclose(probability.sum(axis=1), 1.0, atol=1e-6)
    assert len(saved["vocabulary"]) == 1
    assert diagnostics["batch_change"] == {
        "parent_batch_races": 256,
        "candidate_batch_races": 512,
        "parent_seed_reused": 31201,
        "other_training_changes": 0,
    }
