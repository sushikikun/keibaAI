import json
import sys
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import train_noodds_v333_pair_history_stage_bias_on_v312 as v333


def _config():
    return json.loads(v333.PREREGISTRATION.read_text(encoding="utf-8"))


def _small_config():
    return {
        "identity_features": {"embedding_widths": {"racer_code": 4}},
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
            "seed": 31201,
            "threads": 1,
            "learning_rate": 0.0003,
            "weight_decay": 0.001,
            "batch_races": 4,
            "gradient_clip": 1.0,
        },
    }


def _model():
    return v333.PairHistoryStageBiasRanker(
        4 + v333.PAIR_RUNNER_WIDTH,
        3,
        [20],
        _small_config()["identity_features"],
        _small_config()["architecture"],
    )


def test_preregistration_fixes_direct_pair_mechanism_and_parent():
    cfg = _config()
    assert cfg["policy"]["active_parent"] == (
        "v312_large_history_racer_identity_set_ranker_on_v295"
    )
    assert cfg["pair_history_features"]["beta_shrinkage_tau"] == 20
    assert cfg["pair_history_features"]["known_pair_rate"] == 0.47023190081582833
    assert cfg["training"]["seed"] == 31201
    assert cfg["architecture"]["pair_bias_heads"]["initialization"].startswith(
        "all pair-head weights exactly zero"
    )


def test_zero_pair_heads_preserve_shared_model_outputs():
    torch.manual_seed(7)
    original_names = v333.v311.IDENTITY_NAMES
    v333.v311.IDENTITY_NAMES = ("racer_code",)
    try:
        base = v333._BASE_MODEL(
            4,
            3,
            [20],
            _small_config()["identity_features"],
            _small_config()["architecture"],
        )
    finally:
        v333.v311.IDENTITY_NAMES = original_names
    torch.manual_seed(7)
    candidate = _model()
    base.eval()
    candidate.eval()
    runner = torch.randn(2, 6, 4)
    pair = torch.randn(2, 6, 6, 3)
    augmented = torch.cat([runner, pair.reshape(2, 6, -1)], dim=2)
    race = torch.randn(2, 3)
    identity = torch.randint(0, 20, (2, 6, 1))
    with torch.no_grad():
        expected = base(runner, race, identity)
        actual = candidate(augmented, race, identity)
    for left, right in zip(expected, actual):
        assert torch.allclose(left, right, atol=1e-7)


def test_stage2_pair_bias_uses_candidate_over_first_orientation():
    model = _model()
    for parameter in model.parameters():
        parameter.data.zero_()
    model.stage2_pair_bias.weight.data[0, 0] = 1.0
    pair = torch.zeros(1, 6, 6, 3)
    pair[0, 4, 1, 0] = 0.375
    runner = torch.cat([torch.zeros(1, 6, 4), pair.reshape(1, 6, -1)], dim=2)
    with torch.no_grad():
        _, stage2, _ = model(runner, torch.zeros(1, 3), torch.zeros(1, 6, 1, dtype=torch.long))
    assert torch.isclose(stage2[0, 1, 4], torch.tensor(0.375))
    assert torch.isclose(stage2[0, 4, 1], torch.tensor(0.0))


def test_stage3_pair_bias_uses_both_ordered_contexts():
    model = _model()
    for parameter in model.parameters():
        parameter.data.zero_()
    model.stage3_first_pair_bias.weight.data[0, 0] = 2.0
    model.stage3_second_pair_bias.weight.data[0, 0] = 3.0
    pair = torch.zeros(1, 6, 6, 3)
    pair[0, 5, 1, 0] = 0.2
    pair[0, 5, 3, 0] = -0.1
    runner = torch.cat([torch.zeros(1, 6, 4), pair.reshape(1, 6, -1)], dim=2)
    with torch.no_grad():
        _, _, stage3 = model(runner, torch.zeros(1, 3), torch.zeros(1, 6, 1, dtype=torch.long))
    assert torch.isclose(stage3[0, 1, 3, 5], torch.tensor(0.1), atol=1e-7)


def test_pair_history_is_not_updated_within_same_date():
    raw = np.zeros((3, 6, 1), dtype=np.float32)
    raw[:, :, 0] = np.arange(100, 106)
    course = np.zeros((3, 6, 5), dtype=np.float32)
    available = np.zeros(3, dtype=np.uint8)
    targets = np.tile(np.asarray([[0, 1, 2]]), (3, 1))
    dates = np.asarray([20260101, 20260101, 20260102])
    _, pair, _ = v333.v280.build_pairwise_history_features(
        raw, course, available, targets, dates, shrinkage=20.0
    )
    assert np.all(pair[0] == 0.0)
    assert np.all(pair[1] == 0.0)
    assert pair[2, 0, 3, 2] == 1.0


def test_bottom3_pair_is_never_updated():
    raw = np.zeros((2, 6, 1), dtype=np.float32)
    raw[:, :, 0] = np.arange(100, 106)
    course = np.zeros((2, 6, 5), dtype=np.float32)
    targets = np.tile(np.asarray([[0, 1, 2]]), (2, 1))
    _, pair, _ = v333.v280.build_pairwise_history_features(
        raw, course, np.zeros(2), targets, np.asarray([20260101, 20260102]), shrinkage=20.0
    )
    assert pair[1, 3, 4, 2] == 0.0
    assert pair[1, 0, 3, 2] == 1.0


def test_memmap_pair_builder_matches_reference(tmp_path):
    raw = np.zeros((3, 6, 1), dtype=np.float32)
    raw[:, :, 0] = np.arange(100, 106)
    targets = np.tile(np.asarray([[0, 1, 2]]), (3, 1))
    dates = np.asarray([20260101, 20260101, 20260102])
    course = np.zeros((3, 6, 5), dtype=np.float32)
    _, expected, expected_audit = v333.v280.build_pairwise_history_features(
        raw, course, np.zeros(3), targets, dates, shrinkage=20.0
    )
    actual, audit = v333.build_pairwise_history_memmap(
        raw, targets, dates, tmp_path / "cache"
    )
    assert isinstance(actual, np.memmap)
    assert np.array_equal(np.asarray(actual), expected)
    assert audit["known_pair_slots"] == expected_audit["known_pair_slots"]
    cached, cached_audit = v333.build_pairwise_history_memmap(
        raw, targets, dates, tmp_path / "cache"
    )
    assert np.array_equal(np.asarray(cached), expected)
    assert cached_audit == audit

def test_train_predict_outputs_normalized_probabilities(tmp_path):
    rng = np.random.default_rng(333)
    runner = rng.normal(size=(12, 6, 4)).astype(np.float32)
    race = rng.normal(size=(12, 3)).astype(np.float32)
    identity = np.asarray(
        [[[100 + lane] for lane in range(6)] for _ in range(12)], dtype=np.float64
    )
    targets = np.asarray([[0, 1, 2], [1, 2, 3], [2, 3, 4], [3, 4, 5]] * 3)
    v333._PAIRWISE_RAW = rng.normal(size=(12, 6, 6, 3)).astype(np.float32)
    v333._PAIR_AUDIT = {"races": 12, "known_pair_rate": 0.5}
    path = tmp_path / "model.pt"
    probability, diagnostics = v333.train_and_predict(
        runner,
        race,
        identity,
        targets,
        np.arange(8),
        np.arange(8, 12),
        _small_config(),
        "screen",
        "d6",
        path,
    )
    saved = torch.load(path, weights_only=False)
    assert probability.shape == (4, 120)
    assert np.allclose(probability.sum(axis=1), 1.0, atol=1e-6)
    assert "stage2_pair_bias.weight" in saved["state_dict"]
    assert diagnostics["pair_bias_heads"]["zero_initialized"] is True
