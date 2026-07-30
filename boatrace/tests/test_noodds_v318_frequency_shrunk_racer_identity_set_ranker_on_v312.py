import json
import sys
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import train_noodds_v318_frequency_shrunk_racer_identity_set_ranker_on_v312 as v318


def config():
    return json.loads(
        v318.PREREGISTRATION.read_text(encoding="utf-8")
    )


def small_config():
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
    return cfg


def test_preregistration_fixes_tau_parent_and_protocols():
    cfg = config()
    assert cfg["identity_features"]["count_shrinkage_tau"] == 20
    assert cfg["identity_features"]["scale_formula"] == (
        "sqrt(count / (count + 20))"
    )
    assert cfg["policy"]["active_parent"].startswith("v312_")
    assert cfg["screen_protocol"].endswith("matched_v312.json")
    assert cfg["final_protocol"].endswith("protocol_v9.json")


def test_frequency_scale_is_exact_and_reserves_unknown_zero():
    raw = np.asarray(
        [[[10], [10], [20], [30], [30], [30]]],
        dtype=np.float64,
    )
    vocabulary, counts, scale, audit = (
        v318.fit_frequency_scale(raw, np.asarray([0]), 20)
    )
    assert np.array_equal(vocabulary, [10, 20, 30])
    assert np.array_equal(counts, [2, 1, 3])
    assert scale[0] == 0.0
    expected = np.sqrt(
        np.asarray([2, 1, 3]) / np.asarray([22, 21, 23])
    )
    assert np.allclose(scale[1:], expected)
    assert audit["count_sum"] == 6


def test_validation_only_appearances_do_not_change_counts():
    raw = np.asarray(
        [[[10]] * 6, [[999]] * 6, [[999]] * 6],
        dtype=np.float64,
    )
    vocabulary, counts, scale, _ = v318.fit_frequency_scale(
        raw, np.asarray([0]), 20
    )
    assert np.array_equal(vocabulary, [10])
    assert np.array_equal(counts, [6])
    original_names = v318.v311.IDENTITY_NAMES
    v318.v311.IDENTITY_NAMES = ("racer_code",)
    try:
        encoded, audit = v318.v311.encode_identity(
            raw, np.asarray([1, 2]), [vocabulary]
        )
    finally:
        v318.v311.IDENTITY_NAMES = original_names
    assert np.all(encoded == 0)
    assert audit["racer_code"]["unknown_rate"] == 1.0
    assert scale[0] == 0.0


def test_zero_scale_removes_identity_effect():
    original_names = v318.v311.IDENTITY_NAMES
    v318.v311.IDENTITY_NAMES = ("racer_code",)
    v318._ACTIVE_IDENTITY_SCALE = np.zeros(4, dtype=np.float32)
    try:
        model = v318.FrequencyShrunkIdentityStagewiseSetRanker(
            3,
            2,
            [3],
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
        v318._ACTIVE_IDENTITY_SCALE = None
        v318.v311.IDENTITY_NAMES = original_names
    model.eval()
    runner = torch.randn(2, 6, 3)
    race = torch.randn(2, 2)
    first = torch.ones(2, 6, 1, dtype=torch.long)
    second = torch.full((2, 6, 1), 3, dtype=torch.long)
    with torch.no_grad():
        a = model(runner, race, first)
        b = model(runner, race, second)
    assert all(
        torch.allclose(left, right)
        for left, right in zip(a, b)
    )


def test_train_predict_saves_scale_and_normalized_probability(
    tmp_path,
):
    rng = np.random.default_rng(318)
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
    path = tmp_path / "model.pt"
    probability, diagnostics = v318.train_and_predict(
        runner,
        race,
        identity,
        targets,
        np.arange(8),
        np.arange(8, 12),
        small_config(),
        "screen",
        "d6",
        path,
    )
    saved = torch.load(path, weights_only=False)
    assert probability.shape == (4, 120)
    assert np.allclose(
        probability.sum(axis=1), 1.0, atol=1e-6
    )
    assert "identity_frequency_scale" in saved["state_dict"]
    assert diagnostics["frequency_shrinkage"]["count_sum"] == 48
    assert diagnostics["frequency_shrinkage"]["unknown_scale"] == 0.0
