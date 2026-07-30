import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from evaluate_noodds_v337_rolling_origins import date_cluster_bootstrap_interval, evaluate_origin, losses_for


def test_losses_follow_true_exact_top3_probability():
    probability = np.full((2, 120), 1.0 / 120.0)
    probability[0, 7] = 0.5
    probability[0] /= probability[0].sum()
    loss = losses_for(probability, np.asarray([7, 8]))
    assert loss[0] < loss[1]


def test_date_cluster_interval_is_seed_reproducible():
    values = np.asarray([-0.2, -0.1, 0.1, 0.2])
    dates = np.asarray(["2025-01-01", "2025-01-01", "2025-01-02", "2025-01-02"], dtype="datetime64[D]")
    assert date_cluster_bootstrap_interval(values, dates, 33701, draws=100) == date_cluster_bootstrap_interval(values, dates, 33701, draws=100)


def test_evaluate_origin_reports_uniform_improvement():
    probability = np.full((2, 120), 1.0 / 120.0)
    probability[:, 0] = 0.5
    probability /= probability.sum(axis=1, keepdims=True)
    dates = np.asarray(["2025-01-01", "2025-01-02"], dtype="datetime64[D]")
    report = evaluate_origin(probability, np.asarray([0, 0]), dates, 33701,)
    assert report["vs_uniform_logloss_delta"] < 0.0
    assert report["races"] == 2
