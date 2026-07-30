import json
import sys
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import train_noodds_v322_expanded_racer_identity_set_ranker_on_v312 as v322


def config():
    return json.loads(
        v322.PREREGISTRATION.read_text(encoding="utf-8")
    )


def test_preregistration_fixes_expanded_identity_only():
    cfg = config()
    assert cfg["identity_features"]["embedding_width"] == 32
    assert cfg["identity_features"]["parent_embedding_width"] == 16
    assert cfg["architecture"]["dropout"] == 0.1
    assert cfg["architecture"]["runner_projection_width"] == 48
    assert cfg["training"]["epochs_full"] == 6
    assert cfg["training"]["seed"] == 32201
    assert cfg["anchoring"]["gamma_bounds"] == [0.0, 0.25]
    assert cfg["policy"]["active_parent"].startswith("v312_")


def test_runtime_contract_has_width32_racer_only():
    cfg = v322.runtime_preregistration(config())
    assert cfg["identity_features"]["embedding_widths"] == {
        "racer_code": 32
    }
    assert cfg["architecture"]["dropout"] == 0.1


def test_train_predict_normalizes_and_records_capacity(tmp_path):
    cfg = config()
    cfg["architecture"] = {
        "runner_projection_width": 12,
        "attention_heads": 3,
        "feedforward_width": 24,
        "dropout": 0.0,
        "self_attention_layers": 1,
    }
    cfg["identity_features"]["embedding_width"] = 5
    cfg["training"].update(
        {
            "epochs_screen": 1,
            "epochs_full": 1,
            "threads": 1,
            "batch_races": 4,
        }
    )
    rng = np.random.default_rng(322)
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
    probability, diagnostics = v322.train_and_predict(
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
    assert saved["state_dict"]["identity_embeddings.0.weight"].shape[1] == 5
    assert diagnostics["capacity_change"] == {
        "parent_embedding_width": 16,
        "candidate_embedding_width": 32,
        "other_architecture_changes": 0,
    }
