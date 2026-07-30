import json
import sys
from pathlib import Path

import numpy as np
import pytest
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import train_noodds_v326_late_epoch_swa_racer_identity_on_v312 as v326


def config():
    return json.loads(v326.PREREGISTRATION.read_text(encoding="utf-8"))


def test_preregistration_fixes_parent_training_and_average_epochs():
    cfg = config()
    assert cfg["identity_features"]["embedding_width"] == 16
    assert cfg["architecture"]["dropout"] == 0.1
    assert cfg["training"]["batch_races"] == 256
    assert cfg["training"]["weight_decay"] == 0.001
    assert cfg["training"]["seed"] == 31201
    assert cfg["checkpoint_averaging"]["full_epochs"] == [4, 5, 6]
    assert cfg["checkpoint_averaging"]["screen_epochs"] == [2, 3]
    assert cfg["checkpoint_averaging"]["checkpoint_selection"] is False
    assert cfg["anchoring"]["gamma_bounds"] == [0.0, 0.25]


def test_average_state_dicts_means_float_and_keeps_final_integer():
    states = [
        {
            "weight": torch.tensor([1.0, 3.0]),
            "counter": torch.tensor(2, dtype=torch.int64),
        },
        {
            "weight": torch.tensor([3.0, 7.0]),
            "counter": torch.tensor(5, dtype=torch.int64),
        },
    ]
    averaged = v326.average_state_dicts(states)
    assert torch.allclose(averaged["weight"], torch.tensor([2.0, 5.0]))
    assert averaged["weight"].dtype == torch.float32
    assert averaged["counter"].item() == 5


def test_average_state_dicts_rejects_empty_or_mismatched_states():
    with pytest.raises(ValueError, match="at least one"):
        v326.average_state_dicts([])
    with pytest.raises(ValueError, match="keys differ"):
        v326.average_state_dicts(
            [{"a": torch.tensor(1.0)}, {"b": torch.tensor(1.0)}]
        )


def test_runtime_contract_preserves_racer_only_identity():
    cfg = v326.runtime_preregistration(config())
    assert cfg["identity_features"]["embedding_widths"] == {
        "racer_code": 16
    }
    assert cfg["training"]["seed"] == 31201


def test_train_predict_uses_and_saves_preregistered_screen_average(tmp_path):
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
            "threads": 1,
            "batch_races": 4,
        }
    )
    rng = np.random.default_rng(326)
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
    model_path = tmp_path / "model.pt"
    probability, diagnostics = v326.train_and_predict(
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
    assert probability.shape == (4, 120)
    assert np.allclose(probability.sum(axis=1), 1.0, atol=1e-6)
    assert saved["checkpoint_averaging"] == {
        "method": "uniform",
        "epochs": [2, 3],
        "count": 2,
    }
    assert diagnostics["checkpoint_averaging"] == {
        "method": "uniform",
        "epochs": [2, 3],
        "count": 2,
        "parent_seed_reused": 31201,
        "other_training_changes": 0,
    }
    assert tuple(saved["state_dict"]) != ()
