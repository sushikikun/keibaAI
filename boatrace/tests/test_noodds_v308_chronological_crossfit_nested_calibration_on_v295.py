import inspect
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import train_noodds_v308_chronological_crossfit_nested_calibration_on_v295 as v308


def _config():
    return json.loads(
        (
            ROOT
            / "configs"
            / "noodds_v308_chronological_crossfit_nested_calibration_on_v295_preregistered.json"
        ).read_text()
    )


def _prob(rows, seed=1):
    rng = np.random.default_rng(seed)
    values = rng.random((rows, 120))
    return values / values.sum(axis=1, keepdims=True)


def test_preregistered_inner_blocks_and_total_are_fixed():
    cfg = _config()
    blocks = cfg["inner_crossfit"]["blocks"]
    assert [block["id"] for block in blocks] == ["i1", "i2", "i3", "i4", "i5"]
    assert [block["validation_races"] for block in blocks] == [
        8859,
        9241,
        7399,
        6517,
        3889,
    ]
    assert sum(block["validation_races"] for block in blocks) == 35905
    assert cfg["inner_crossfit"]["total_pre_d6_oof_races"] == 35905


def test_inner_blocks_are_strictly_chronological_and_disjoint():
    cfg = _config()
    previous_end = None
    for block in cfg["inner_crossfit"]["blocks"]:
        start = date.fromisoformat(block["validation_start"])
        end = date.fromisoformat(block["validation_end_exclusive"])
        train_before = date.fromisoformat(block["train_before"])
        assert train_before == start
        assert start < end
        if previous_end is not None:
            assert previous_end <= start
        previous_end = end


def test_identity_nested_calibration_reconstructs_parent():
    parent = _prob(7)
    identity = [
        {"alpha": 1.0, "bias": [0.0] * 6},
        {"alpha": 1.0, "bias": [0.0] * 6},
        {"alpha": 1.0, "bias": [0.0] * 6},
    ]
    calibrated = v308.calibrate_probability(parent, identity)
    assert np.allclose(calibrated, parent, atol=1e-12)
    assert np.allclose(calibrated.sum(axis=1), 1.0)


def test_atomic_savez_replaces_complete_file(tmp_path):
    path = tmp_path / "cache.npz"
    v308.atomic_savez(path, values=np.asarray([1, 2, 3]))
    assert path.exists()
    assert not path.with_suffix(".tmp.npz").exists()
    with np.load(path) as source:
        assert np.array_equal(source["values"], [1, 2, 3])


def test_inner_crossfit_builds_then_reuses_validated_cache(tmp_path, monkeypatch):
    start = date(2025, 1, 2).toordinal()
    end = date(2025, 1, 4).toordinal()
    race_dates = np.asarray(
        [date(2025, 1, 1).toordinal()] * 2 + [start, start + 1],
        dtype=np.int32,
    )
    prereg = {
        "inner_crossfit": {
            "cache": str(tmp_path),
            "total_pre_d6_oof_races": 2,
            "blocks": [
                {
                    "id": "i1",
                    "validation_start": "2025-01-02",
                    "validation_end_exclusive": "2025-01-04",
                    "train_races": 2,
                    "validation_races": 2,
                }
            ],
        }
    }
    calls = {"fit": 0}

    def fake_fit(*args, **kwargs):
        calls["fit"] += 1
        return ("models",), {"train_races": 2}

    def fake_predict(models, matrix, indices, width):
        return np.full((len(indices), 120), 1.0 / 120.0)

    monkeypatch.setattr(v308, "fit_v295_models", fake_fit)
    monkeypatch.setattr(v308, "predict_v295_contextual", fake_predict)
    matrix = np.zeros((4, 6, 3), dtype=np.float32)
    target_lanes = np.zeros((4, 3), dtype=np.int8)
    target_combo = np.zeros(4, dtype=np.int64)

    pieces, audit = v308.build_inner_crossfit(
        prereg,
        "fixed-hash",
        matrix,
        target_lanes,
        target_combo,
        race_dates,
        2,
        {},
    )
    assert calls["fit"] == 1
    assert audit[0]["status"] == "cache_built"
    assert pieces[0]["base"].shape == (2, 120)

    _, audit2 = v308.build_inner_crossfit(
        prereg,
        "fixed-hash",
        matrix,
        target_lanes,
        target_combo,
        race_dates,
        2,
        {},
    )
    assert calls["fit"] == 1
    assert audit2[0]["status"] == "cache_hit"


def test_outer_calibration_uses_only_completed_prior_folds():
    source = inspect.getsource(v308.main)
    assert 'prior_folds = {"d6": [], "d7": ["d6"], "d8": ["d6", "d7"]}' in source
    assert "mode_parent[name] for name in prior_folds[fold]" in source
    assert 'folds[name]["target"] for name in prior_folds[fold]' in source
    assert "inner_base" in source
    assert "inner_target" in source


def test_policy_forbids_in_sample_parent_and_posthoc_search():
    cfg = _config()
    assert cfg["policy"]["odds_used"] is False
    assert cfg["policy"]["payout_used"] is False
    assert "in-sample parent predictions for calibration" in cfg["forbidden"]
    assert "post-result changes" in cfg["forbidden"]
    assert cfg["calibration"]["search"] is False
