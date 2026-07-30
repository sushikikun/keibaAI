import json
import sys
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import train_noodds_v320_racer_branch_identity_set_ranker_on_v312 as v320


def config():
    return json.loads(
        v320.PREREGISTRATION.read_text(encoding="utf-8")
    )


def test_preregistration_fixes_branch_only_addition():
    cfg = config()
    assert cfg["identity_features"]["runner_columns"] == {
        "racer_code": 0,
        "branch_code": 1,
    }
    assert cfg["identity_features"]["embedding_widths"] == {
        "racer_code": 16,
        "branch_code": 4,
    }
    assert cfg["identity_features"]["arithmetic_on_ids"] is False
    assert cfg["architecture"]["dropout"] == 0.1
    assert cfg["training"]["seed"] == 32001
    assert cfg["policy"]["active_parent"].startswith("v312_")


def test_branch_vocabulary_is_fold_training_only():
    original_columns = v320.v311.IDENTITY_COLUMNS
    original_names = v320.v311.IDENTITY_NAMES
    v320.v311.IDENTITY_COLUMNS = (0, 1)
    v320.v311.IDENTITY_NAMES = ("racer_code", "branch_code")
    raw = np.asarray(
        [
            [[10, 1]] * 6,
            [[20, 2]] * 6,
            [[30, 99]] * 6,
        ],
        dtype=np.float64,
    )
    try:
        vocabulary = v320.v311.fit_identity_vocabulary(
            raw, np.asarray([0, 1])
        )
        encoded, audit = v320.v311.encode_identity(
            raw, np.asarray([2]), vocabulary
        )
    finally:
        v320.v311.IDENTITY_COLUMNS = original_columns
        v320.v311.IDENTITY_NAMES = original_names
    assert np.all(encoded[:, :, 0] == 0)
    assert np.all(encoded[:, :, 1] == 0)
    assert audit["branch_code"]["unknown_rate"] == 1.0


def test_train_predict_saves_two_vocabularies_and_normalizes(tmp_path):
    cfg = config()
    cfg["architecture"] = {
        "runner_projection_width": 12,
        "attention_heads": 3,
        "feedforward_width": 24,
        "dropout": 0.0,
        "self_attention_layers": 1,
    }
    cfg["identity_features"]["embedding_widths"] = {
        "racer_code": 4,
        "branch_code": 2,
    }
    cfg["training"].update(
        {
            "epochs_screen": 1,
            "epochs_full": 1,
            "threads": 1,
            "batch_races": 4,
        }
    )
    rng = np.random.default_rng(320)
    runner = rng.normal(size=(12, 6, 4)).astype(np.float32)
    race = rng.normal(size=(12, 3)).astype(np.float32)
    identity = np.asarray(
        [
            [
                [100 + lane, 1 + lane % 3]
                for lane in range(6)
            ]
        ] * 12,
        dtype=np.float64,
    )
    targets = np.asarray(
        [[0, 1, 2], [1, 2, 3], [2, 3, 4], [3, 4, 5]] * 3,
        dtype=np.int64,
    )
    probability, diagnostics = v320.train_and_predict(
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
    assert len(saved["vocabulary"]) == 2
    assert set(diagnostics["train_identity"]) == {
        "racer_code",
        "branch_code",
    }
