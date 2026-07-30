import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from evaluate_noodds_v339_v338_final_internal_vs_v312 import daily_means, normalize_saved_dates, paired_wilcoxon_less


def test_daily_means_cluster_multiple_races():
    values = np.asarray([1.0, 3.0, 2.0])
    dates = np.asarray(["2026-01-01", "2026-01-01", "2026-01-02"], dtype="datetime64[D]")
    np.testing.assert_allclose(daily_means(values, dates), [2.0, 2.0])


def test_paired_wilcoxon_prefers_consistently_lower_candidate_loss():
    parent = np.asarray([2.0, 2.1, 2.2, 2.3, 2.4, 2.5])
    candidate = parent - 0.1
    dates = np.asarray(["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04", "2026-01-05", "2026-01-06"], dtype="datetime64[D]")
    assert paired_wilcoxon_less(candidate, parent, dates) < 0.05

def test_saved_python_ordinals_are_normalized_to_calendar_days():
    normalized = normalize_saved_dates(np.asarray(["739640", "739641"]))
    np.testing.assert_array_equal(normalized, np.asarray(["2026-01-24", "2026-01-25"], dtype="datetime64[D]"))
