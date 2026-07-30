import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pytest
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import train_noodds_v334_calendar_month_context_on_v312 as v334

v313 = v334.v313


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
    )
    original = [(module, name, getattr(module, name)) for module, name in shared_attributes]
    try:
        yield
    finally:
        for module, name, value in original:
            setattr(module, name, value)


def _config():
    return json.loads(v334.PREREGISTRATION.read_text(encoding="utf-8"))


def _architecture():
    return {
        "runner_projection_width": 12,
        "attention_heads": 3,
        "feedforward_width": 24,
        "dropout": 0.0,
        "self_attention_layers": 1,
    }


def _configure():
    v334.configure_core()


def test_preregistration_fixes_month_only_context_and_parent():
    cfg = _config()
    assert cfg["policy"]["active_parent"] == (
        "v312_large_history_racer_identity_set_ranker_on_v295"
    )
    assert cfg["race_context_features"]["categories"] == [
        "calendar_month_1_to_12"
    ]
    assert cfg["race_context_features"]["embedding_widths"] == {
        "calendar_month": 4
    }
    assert cfg["race_context_features"]["year_used"] is False
    assert cfg["training"]["seed"] == 31201
    assert cfg["final_protocol"].endswith("noodds_evaluation_protocol_v9.json")


def test_calendar_month_parses_integer_and_string_dates():
    dates = np.asarray([20260131, "2026-02-01", "2026/12/15"], dtype=object)
    months = v334.calendar_month_context(dates)
    assert months.shape == (3, 1)
    assert np.array_equal(months[:, 0], [1, 2, 12])


def test_calendar_month_parses_dataset_ordinal_dates():
    dates = np.asarray(
        [date(2025, 1, 1).toordinal(), date(2026, 7, 16).toordinal()],
        dtype=np.int32,
    )
    months = v334.calendar_month_context(dates)
    assert np.array_equal(months[:, 0], [1, 7])


def test_calendar_month_rejects_invalid_date():
    with pytest.raises(ValueError, match="invalid calendar month"):
        v334.calendar_month_context(np.asarray([20261301]))
    with pytest.raises(ValueError, match="invalid race date"):
        v334.calendar_month_context(np.asarray(["bad"]))


def test_context_vocabulary_is_training_only_and_unseen_maps_zero():
    _configure()
    raw = np.asarray([[1], [2], [12]], dtype=np.float64)
    vocabulary = v313.fit_context_vocabulary(raw, np.asarray([0, 1]))
    encoded, audit = v313.encode_context(raw, np.asarray([2]), vocabulary)
    assert 12 not in vocabulary[0]
    assert encoded[0, 0] == 0
    assert audit["calendar_month"]["unknown_rate"] == 1.0


def test_month_context_model_outputs_normalized_probabilities():
    _configure()
    torch.manual_seed(334)
    model = v313.RacerContextStagewiseSetRanker(
        5,
        3,
        [20],
        [12],
        {"embedding_widths": {"racer_code": 4}},
        {"embedding_widths": {"calendar_month": 2}},
        _architecture(),
    )
    model.eval()
    runner = torch.randn(3, 6, 5)
    race = torch.randn(3, 3)
    identity = torch.randint(0, 20, (3, 6, 1))
    context = torch.randint(0, 12, (3, 1))
    logits = model(runner, race, identity, context)
    probability = v313.v310.joint_probabilities(logits)
    assert probability.shape == (3, 120)
    assert torch.allclose(probability.sum(dim=1), torch.ones(3), atol=1e-6)


def test_train_predict_saves_single_month_vocabulary(tmp_path):
    _configure()
    rng = np.random.default_rng(334)
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
        "race_context_features": {"embedding_widths": {"calendar_month": 2}},
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
    assert diagnostics["train_context"]["calendar_month"]["vocabulary_size"] == 4


def test_v9_and_v4_remain_frozen_to_v312():
    v9 = json.loads((ROOT / "configs" / "noodds_evaluation_protocol_v9.json").read_text())
    v4 = json.loads((ROOT / "configs" / "noodds_candidate_acceleration_v4_matched_v312.json").read_text())
    assert v9["references"]["active_parent"]["model_id"] == (
        "v312_large_history_racer_identity_set_ranker_on_v295"
    )
    assert v4["policy"]["screen_never_promotes"] is True
