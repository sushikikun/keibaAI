import json
import sys
from pathlib import Path

import numpy as np
import pytest
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import train_noodds_v332_racer_course_identity_on_v312 as v332


def _config():
    return json.loads(v332.PREREGISTRATION.read_text(encoding="utf-8"))


def _small_config():
    return {
        "identity_features": {
            "embedding_widths": {"racer_code": 4, "racer_course_code": 3}
        },
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
            "seed": 33201,
            "threads": 1,
            "learning_rate": 0.0003,
            "weight_decay": 0.001,
            "batch_races": 4,
            "gradient_clip": 1.0,
        },
    }


def test_preregistration_fixes_parent_course_feature_and_protocols():
    cfg = _config()
    assert cfg["policy"]["active_parent"] == (
        "v312_large_history_racer_identity_set_ranker_on_v295"
    )
    assert cfg["identity_features"]["embedding_widths"] == {
        "racer_code": 16,
        "racer_course_code": 8,
    }
    assert cfg["identity_features"]["course_missing_races"] == 865
    assert cfg["training"]["seed"] == 33201
    assert cfg["screen_protocol"].endswith(
        "noodds_candidate_acceleration_v4_matched_v312.json"
    )
    assert cfg["final_protocol"].endswith("noodds_evaluation_protocol_v9.json")


def test_racer_course_tuple_encoding_is_exact_and_collision_free():
    racer = np.asarray(
        [
            [[100], [101], [102], [103], [104], [105]],
            [[100], [101], [102], [103], [104], [105]],
        ],
        dtype=np.float64,
    )
    course = np.asarray([[1, 2, 3, 4, 5, 6], [6, 5, 4, 3, 2, 1]])
    combined = v332.build_racer_course_identity(racer, course, [1, 1])
    assert np.array_equal(combined[:, :, 0], racer[:, :, 0])
    assert combined[0, 0, 1] == 100 * v332.PAIR_RADIX + 1
    assert combined[1, 0, 1] == 100 * v332.PAIR_RADIX + 6
    assert len(np.unique(combined[:, :, 1])) == 12


def test_unavailable_course_maps_tuple_to_unknown_without_lane_substitution():
    racer = np.asarray([[[100], [101], [102], [103], [104], [105]]])
    course = np.asarray([[1, 2, 3, 4, 5, 6]], dtype=np.float64)
    combined = v332.build_racer_course_identity(racer, course, [0])
    assert np.all(combined[0, :, 0] > 0)
    assert np.all(combined[0, :, 1] == 0)


def test_invalid_racer_and_available_course_are_handled_strictly():
    racer = np.asarray([[[np.nan], [0], [100], [101], [102], [103]]])
    course = np.asarray([[1, 2, 3, 4, 5, 6]], dtype=np.float64)
    combined = v332.build_racer_course_identity(racer, course, [1])
    assert np.array_equal(combined[0, :2], np.zeros((2, 2)))
    assert np.all(combined[0, 2:, 1] > 0)
    with pytest.raises(ValueError, match="1..6"):
        v332.build_racer_course_identity(
            np.ones((1, 6, 1)), np.asarray([[7, 2, 3, 4, 5, 6]]), [1]
        )


def test_train_predict_saves_two_fold_training_vocabularies(tmp_path):
    rng = np.random.default_rng(332)
    runner = rng.normal(size=(12, 6, 4)).astype(np.float32)
    race = rng.normal(size=(12, 3)).astype(np.float32)
    racer = np.asarray(
        [
            [[100 + race_index * 6 + lane] for lane in range(6)]
            for race_index in range(12)
        ],
        dtype=np.float64,
    )
    v332._COURSE_RAW = np.tile(np.arange(1, 7), (12, 1)).astype(np.float64)
    v332._COURSE_AVAILABLE = np.ones(12, dtype=np.uint8)
    targets = np.asarray(
        [[0, 1, 2], [1, 2, 3], [2, 3, 4], [3, 4, 5]] * 3,
        dtype=np.int64,
    )
    path = tmp_path / "model.pt"
    probability, diagnostics = v332.train_and_predict(
        runner,
        race,
        racer,
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
    assert len(saved["vocabulary"]) == 2
    assert set(diagnostics["train_identity"]) == {
        "racer_code",
        "racer_course_code",
    }


def test_fold_vocabulary_maps_unseen_racer_course_tuple_to_zero():
    racer = np.asarray(
        [
            [[100], [101], [102], [103], [104], [105]],
            [[100], [101], [102], [103], [104], [105]],
        ],
        dtype=np.float64,
    )
    course = np.asarray([[1, 2, 3, 4, 5, 6], [6, 5, 4, 3, 2, 1]])
    combined = v332.build_racer_course_identity(racer, course, [1, 1])
    original_columns = v332.v311.IDENTITY_COLUMNS
    original_names = v332.v311.IDENTITY_NAMES
    v332.v311.IDENTITY_COLUMNS = (0, 1)
    v332.v311.IDENTITY_NAMES = ("racer_code", "racer_course_code")
    try:
        vocabulary = v332.v311.fit_identity_vocabulary(combined, np.asarray([0]))
        encoded, audit = v332.v311.encode_identity(
            combined, np.asarray([1]), vocabulary
        )
    finally:
        v332.v311.IDENTITY_COLUMNS = original_columns
        v332.v311.IDENTITY_NAMES = original_names
    assert np.all(encoded[:, :, 0] > 0)
    assert np.all(encoded[:, :, 1] == 0)
    assert audit["racer_course_code"]["unknown_rate"] == 1.0
