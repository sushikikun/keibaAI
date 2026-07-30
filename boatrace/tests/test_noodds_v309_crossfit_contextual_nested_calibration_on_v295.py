import inspect
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import train_noodds_v309_crossfit_contextual_nested_calibration_on_v295 as v309


def _config():
    return json.loads(
        (
            ROOT
            / "configs"
            / "noodds_v309_crossfit_contextual_nested_calibration_on_v295_preregistered.json"
        ).read_text(encoding="utf-8")
    )


def _probability(rows=5, seed=309):
    rng = np.random.default_rng(seed)
    values = rng.random((rows, 120))
    return values / values.sum(axis=1, keepdims=True)


def _identity_parameter():
    return {
        "global_alpha": 1.0,
        "venue_alpha": [0.0] * 24,
        "race_bucket_alpha": [0.0] * 3,
        "bias": [0.0] * 6,
    }


def test_preregistered_context_and_regularization_are_fixed():
    cfg = _config()
    assert cfg["context"]["venue_code"].endswith("integer 0..23 used directly")
    assert cfg["context"]["race_no_buckets"] == {
        "1-4": 0,
        "5-8": 1,
        "9-12": 2,
    }
    assert cfg["calibration"]["parameters"] == 102
    assert cfg["calibration"]["l2_venue_alpha_toward_zero"] == 0.1
    assert cfg["calibration"]["l2_race_bucket_alpha_toward_zero"] == 0.1
    assert cfg["calibration"]["search"] is False


def test_context_indices_map_venue_and_race_number_buckets():
    race_features = np.zeros((6, 2), dtype=np.float64)
    race_features[:, 0] = [0, 1, 7, 12, 22, 23]
    race_features[:, 1] = [1, 4, 5, 8, 9, 12]
    venue, bucket = v309.context_indices(race_features, np.arange(6))
    assert np.array_equal(venue, [0, 1, 7, 12, 22, 23])
    assert np.array_equal(bucket, [0, 0, 1, 1, 2, 2])


@pytest.mark.parametrize("venue,race_no", [(-1, 1), (24, 1), (0, 0), (0, 13)])
def test_context_indices_reject_invalid_values(venue, race_no):
    race_features = np.asarray([[venue, race_no]], dtype=np.float64)
    with pytest.raises(ValueError):
        v309.context_indices(race_features, np.asarray([0]))


def test_identity_contextual_calibration_reconstructs_parent():
    parent = _probability()
    parameters = [_identity_parameter() for _ in range(3)]
    venue = np.asarray([0, 1, 7, 12, 23])
    bucket = np.asarray([0, 1, 2, 0, 1])
    calibrated = v309.calibrate_contextual(parent, parameters, venue, bucket)
    assert np.allclose(calibrated, parent, atol=1e-12)
    assert np.allclose(calibrated.sum(axis=1), 1.0)


def test_context_deviation_changes_only_matching_rows():
    parent = np.repeat(_probability(1), 2, axis=0)
    parameter = _identity_parameter()
    parameter["venue_alpha"][5] = 0.5
    parameters = [parameter, _identity_parameter(), _identity_parameter()]
    calibrated = v309.calibrate_contextual(
        parent,
        parameters,
        np.asarray([4, 5]),
        np.asarray([0, 0]),
    )
    assert np.allclose(calibrated[0], parent[0], atol=1e-12)
    assert not np.allclose(calibrated[1], parent[1], atol=1e-8)
    assert np.allclose(calibrated.sum(axis=1), 1.0)


def test_frozen_inner_cache_is_complete_and_aligned():
    cfg = _config()
    targets = np.load(
        ROOT / "results/noodds_raw_v200/dataset/targets.npy", mmap_mode="r"
    )
    race_dates = np.load(
        ROOT / "results/noodds_raw_v200/dataset/race_dates.npy", mmap_mode="r"
    )
    probability, target, indices, audit = v309.load_inner_cache(
        cfg, v309.true_combo_indices(targets), race_dates
    )
    assert probability.shape == (35905, 120)
    assert target.shape == indices.shape == (35905,)
    assert len(np.unique(indices)) == 35905
    assert sum(row["races"] for row in audit) == 35905
    assert [row["id"] for row in audit] == ["i1", "i2", "i3", "i4", "i5"]
    assert np.allclose(probability.sum(axis=1), 1.0, atol=1e-5)


def test_outer_calibration_uses_only_completed_prior_folds():
    source = inspect.getsource(v309.main)
    assert 'prior_folds = {"d6": [], "d7": ["d6"], "d8": ["d6", "d7"]}' in source
    assert "training_base = [inner_base]" in source
    assert "mode_parent[name] for name in prior_folds[fold]" in source
    assert "training_target = [inner_target]" in source
    cfg = _config()
    assert cfg["outer_training"]["gamma"] == "none"
    assert cfg["outer_training"]["blend"] == "none"
    assert cfg["policy"]["odds_used"] is False
    assert cfg["policy"]["payout_used"] is False
