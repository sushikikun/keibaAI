import json
import sys
from pathlib import Path

import numpy as np
import pytest
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import train_noodds_v336_venue_wind_regime_context_on_v312 as v336

v313 = v336.v313


@pytest.fixture(autouse=True)
def _restore_shared_parent_state():
    shared_attributes = (
        (v313, "MODEL_ID"),
        (v313, "PREREGISTRATION"),
        (v313, "CONTEXT_COLUMNS"),
        (v313, "CONTEXT_NAMES"),
        (v313, "_CONTEXT_RAW"),
        (v313.v311, "MODEL_ID"),
        (v313.v311, "IDENTITY_COLUMNS"),
        (v313.v311, "IDENTITY_NAMES"),
        (v313.v311, "PARENT_PATHS"),
        (v313.v311, "validate_inputs"),
        (v313.v311, "train_and_predict"),
        (v313.v310, "load_matched_parents"),
        (v313.v310, "evaluate_matched_screen"),
        (v313.v310, "build_pairwise_history_features"),
    )
    original = [(module, name, getattr(module, name)) for module, name in shared_attributes]
    try:
        yield
    finally:
        for module, name, value in original:
            setattr(module, name, value)


def _config():
    return json.loads(v336.PREREGISTRATION.read_text(encoding="utf-8"))


def _architecture():
    return {
        "runner_projection_width": 12,
        "attention_heads": 3,
        "feedforward_width": 24,
        "dropout": 0.0,
        "self_attention_layers": 1,
    }


def _configure():
    v336.configure_core()


def _race(rows):
    array = np.zeros((len(rows), 15), dtype=np.float32)
    for index, (venue, wind_sin, wind_cos, missing) in enumerate(rows):
        array[index, 0] = venue
        array[index, 12] = wind_sin
        array[index, 13] = wind_cos
        array[index, 14] = missing
    return array


def test_preregistration_fixes_venue_wind_context_and_parent():
    cfg = _config()
    assert cfg["policy"]["active_parent"] == (
        "v312_large_history_racer_identity_set_ranker_on_v295"
    )
    assert cfg["race_context_features"]["venue_domain"] == [0, 23]
    assert cfg["race_context_features"]["wind_missing_sector"] == 16
    assert cfg["race_context_features"]["embedding_widths"] == {
        "venue_wind_regime": 12
    }
    assert cfg["training"]["seed"] == 31201
    assert cfg["final_protocol"].endswith("noodds_evaluation_protocol_v9.json")


def test_fixed_compass_sectors_and_venue_are_encoded_as_opaque_tokens():
    race = _race([(0, 0.0, 1.0, 0), (0, 1.0, 0.0, 0), (2, 0.0, 1.0, 0)])
    token = v336.venue_wind_regime_context(race)[:, 0]
    assert np.array_equal(token, [1, 5, 35])


def test_missing_wind_uses_dedicated_sector_without_imputation():
    race = _race([(3, np.nan, np.nan, 1), (3, 0.0, 1.0, 0)])
    token = v336.venue_wind_regime_context(race)[:, 0]
    assert token[0] == 1 + 17 * 3 + 16
    assert token[1] == 1 + 17 * 3


def test_invalid_venue_wind_or_missing_flag_is_rejected():
    with pytest.raises(ValueError, match="0..23"):
        v336.venue_wind_regime_context(_race([(24, 0.0, 1.0, 0)]))
    with pytest.raises(ValueError, match="observed wind"):
        v336.venue_wind_regime_context(_race([(1, np.nan, 1.0, 0)]))
    with pytest.raises(ValueError, match="binary"):
        v336.venue_wind_regime_context(_race([(1, 0.0, 1.0, 0.5)]))


def test_chunked_pairwise_runner_aggregation_preserves_fixed_eight_features():
    pairwise = np.zeros((2, 6, 6, 3), dtype=np.float32)
    for right, residual in enumerate([0.1, 0.2, 0.3, 0.4, 0.5], start=1):
        pairwise[:, 0, right] = (residual, float(right), 1.0)
        pairwise[:, right, 0] = (-residual, float(right), 1.0)
    course = np.zeros((2, 6, 5), dtype=np.float32)
    course[:, :, 0] = np.arange(1, 7)
    available = np.asarray([1, 0], dtype=np.uint8)
    runner = v336.aggregate_pairwise_runner(pairwise, course, available, chunk_size=1)
    assert runner.shape == (2, 6, 8)
    assert np.allclose(runner[0, 0, :6], [0.3, 0.1, 0.5, 3.0, 5.0, 1.0])
    expected_interaction = np.mean((1.0 - np.arange(2, 7)) * np.arange(0.1, 0.6, 0.1))
    assert np.isclose(runner[0, 0, 7], expected_interaction)
    assert runner[0, 0, 6] == 1.0
    assert np.all(runner[1, :, 6:] == 0.0)

def test_context_vocabulary_is_training_only_and_unseen_maps_zero():
    _configure()
    raw = np.asarray([[1], [5], [35]], dtype=np.float64)
    vocabulary = v313.fit_context_vocabulary(raw, np.asarray([0, 1]))
    encoded, audit = v313.encode_context(raw, np.asarray([2]), vocabulary)
    assert 35 not in vocabulary[0]
    assert encoded[0, 0] == 0
    assert audit["venue_wind_regime"]["unknown_rate"] == 1.0


def test_venue_wind_context_model_outputs_normalized_probabilities():
    _configure()
    torch.manual_seed(336)
    model = v313.RacerContextStagewiseSetRanker(
        5,
        3,
        [20],
        [220],
        {"embedding_widths": {"racer_code": 4}},
        {"embedding_widths": {"venue_wind_regime": 3}},
        _architecture(),
    )
    model.eval()
    runner = torch.randn(3, 6, 5)
    race = torch.randn(3, 3)
    identity = torch.randint(0, 20, (3, 6, 1))
    context = torch.randint(0, 220, (3, 1))
    logits = model(runner, race, identity, context)
    probability = v313.v310.joint_probabilities(logits)
    assert probability.shape == (3, 120)
    assert torch.allclose(probability.sum(dim=1), torch.ones(3), atol=1e-6)


def test_train_predict_saves_venue_wind_vocabulary(tmp_path):
    _configure()
    rng = np.random.default_rng(336)
    runner = rng.normal(size=(12, 6, 4)).astype(np.float32)
    race = rng.normal(size=(12, 3)).astype(np.float32)
    identity = np.asarray(
        [[[100 + race_index * 6 + lane] for lane in range(6)] for race_index in range(12)],
        dtype=np.float64,
    )
    v313._CONTEXT_RAW = np.asarray([[1 + i % 4] for i in range(12)], dtype=np.float64)
    targets = np.asarray([[0, 1, 2], [1, 2, 3], [2, 3, 4], [3, 4, 5]] * 3)
    prereg = {
        "identity_features": {"embedding_widths": {"racer_code": 4}},
        "race_context_features": {"embedding_widths": {"venue_wind_regime": 2}},
        "architecture": _architecture(),
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
    path = tmp_path / "model.pt"
    probability, diagnostics = v313.train_and_predict(
        runner,
        race,
        identity,
        targets,
        np.arange(8),
        np.arange(8, 12),
        prereg,
        "screen",
        "d6",
        path,
    )
    saved = torch.load(path, weights_only=False)
    assert probability.shape == (4, 120)
    assert np.allclose(probability.sum(axis=1), 1.0, atol=1e-6)
    assert len(saved["context_vocabulary"]) == 1
    assert diagnostics["train_context"]["venue_wind_regime"]["vocabulary_size"] == 4


def test_v9_and_v4_remain_frozen_to_v312():
    v9 = json.loads((ROOT / "configs" / "noodds_evaluation_protocol_v9.json").read_text())
    v4 = json.loads((ROOT / "configs" / "noodds_candidate_acceleration_v4_matched_v312.json").read_text())
    assert v9["references"]["active_parent"]["model_id"] == (
        "v312_large_history_racer_identity_set_ranker_on_v295"
    )
    assert v4["policy"]["screen_never_promotes"] is True
