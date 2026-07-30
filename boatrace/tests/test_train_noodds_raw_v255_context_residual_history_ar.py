from __future__ import annotations

import numpy as np

from train_noodds_raw_v255_context_residual_history_ar import auxiliary_targets


def synthetic_data():
    runner_names = ["start_st", "start_st_missing", "exhibition_time"]
    race_names = ["venue_code_cat", "race_no"]
    runner = np.zeros((2, 6, 3), dtype=np.float32)
    runner[:, :, 0] = np.asarray([[0.10, 0.12, 0.14, 0.16, 0.18, 0.20]] * 2)
    runner[:, :, 2] = np.asarray([[6.70, 6.72, 6.74, 6.76, 6.78, 6.80]] * 2)
    return {
        "manifest": {"runner_feature_names": runner_names, "race_feature_names": race_names},
        "runner": runner,
        "race": np.asarray([[0, 1], [0, 1]], dtype=np.float32),
        "targets": np.asarray([[0, 1, 2], [0, 1, 2]], dtype=np.int64),
    }


def test_context_residual_uses_fold_training_rows():
    finish, finish_ok, start, start_ok, exhibition, exhibition_ok = auxiliary_targets(
        synthetic_data(), np.asarray([0, 1], dtype=np.int64)
    )
    assert finish_ok.all()
    assert np.allclose(finish.mean(axis=0), 0.0, atol=1e-6)
    assert start_ok.all() and exhibition_ok.all()
    assert np.allclose(start.mean(axis=1), 0.0, atol=1e-7)
    assert np.allclose(exhibition.mean(axis=1), 0.0, atol=1e-7)


def test_validation_outcome_cannot_change_training_context():
    data = synthetic_data()
    first = auxiliary_targets(data, np.asarray([0], dtype=np.int64))[0][0].copy()
    data["targets"][1] = np.asarray([5, 4, 3])
    second = auxiliary_targets(data, np.asarray([0], dtype=np.int64))[0][0]
    assert np.array_equal(first, second)


if __name__ == "__main__":
    test_context_residual_uses_fold_training_rows()
    test_validation_outcome_cannot_change_training_context()
    print("ok")
