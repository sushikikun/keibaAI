import json
import sys
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import train_noodds_v329_venue_balanced_loss_racer_identity_on_v312 as v329


def config():
    return json.loads(v329.PREREGISTRATION.read_text(encoding="utf-8"))


def test_preregistration_fixes_fold_local_venue_weighting():
    cfg = config()
    assert cfg["training"]["batch_races"] == 256
    assert cfg["training"]["learning_rate"] == 0.0003
    assert cfg["training"]["weight_decay"] == 0.001
    assert cfg["training"]["seed"] == 31201
    assert cfg["sample_weighting"]["source"] == "race_features venue_code_cat index0"
    assert cfg["sample_weighting"]["clipping"] == "none"
    assert cfg["sample_weighting"]["weight_search"] is False


def test_fold_venue_weights_are_inverse_sqrt_and_mean_one():
    race = np.asarray([0.0, 0.0, 0.0, 0.0, 1.0, 2.0, np.nan])
    weight, audit = v329.build_fold_venue_weights(race, np.arange(7))
    assert np.isclose(weight.mean(), 1.0, atol=1e-7)
    assert weight[0] < weight[4]
    assert np.isclose(weight[4], weight[5])
    assert audit["known_venues"] == 3
    assert audit["count_min"] == 1
    assert audit["count_max"] == 4
    assert audit["valid_rate"] == 6 / 7


def test_validation_venues_do_not_change_training_weights():
    race = np.asarray([1.0, 1.0, 2.0, 2.0, 9.0, 9.0])
    train = np.arange(4)
    first, _ = v329.build_fold_venue_weights(race, train)
    race[4:] = [100.0, 200.0]
    second, _ = v329.build_fold_venue_weights(race, train)
    assert np.array_equal(first, second)


def test_per_race_loss_mean_matches_parent_loss():
    generator = torch.Generator().manual_seed(329)
    rows = 4
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
    targets = torch.tensor([[0, 1, 2], [1, 2, 3], [2, 3, 4], [3, 4, 5]])
    per_race = v329.stagewise_nll_per_race((stage1, stage2, stage3), targets)
    parent = v329.v310.stagewise_nll((stage1, stage2, stage3), targets)
    assert torch.allclose(per_race.mean(), parent, atol=1e-7)


def test_train_predict_normalizes_and_records_venue_audit(tmp_path):
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
    rng = np.random.default_rng(329)
    runner = rng.normal(size=(12, 6, 4)).astype(np.float32)
    race = rng.normal(size=(12, 3)).astype(np.float32)
    race[:, 0] = np.asarray([1] * 6 + [2] * 6)
    identity = np.asarray(
        [[[100 + lane] for lane in range(6)]] * 12, dtype=np.float64
    )
    targets = np.asarray(
        [[0, 1, 2], [1, 2, 3], [2, 3, 4], [3, 4, 5]] * 3,
        dtype=np.int64,
    )
    original_venues = v329.RAW_VENUE_CODES
    v329.RAW_VENUE_CODES = race[:, 0].copy()
    try:
        probability, diagnostics = v329.train_and_predict(
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
    finally:
        v329.RAW_VENUE_CODES = original_venues
    assert probability.shape == (4, 120)
    assert np.allclose(probability.sum(axis=1), 1.0, atol=1e-6)
    assert diagnostics["sample_weighting"]["method"] == "inverse_sqrt_venue_frequency"
    assert diagnostics["sample_weighting"]["known_venues"] == 2
    assert np.isclose(diagnostics["sample_weighting"]["weight_mean"], 1.0)
    assert diagnostics["sample_weighting"]["other_training_changes"] == 0
