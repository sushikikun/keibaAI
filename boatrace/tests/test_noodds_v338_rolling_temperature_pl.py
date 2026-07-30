import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from evaluate_noodds_v338_rolling_temperature_pl import exact_probabilities, exact_top3_losses, fit_beta


def test_zero_beta_is_uniform_exact_top3():
    scores = np.asarray([[10.0, -10.0, 1.0, 2.0, 3.0, 4.0]])
    probabilities = exact_probabilities(scores, 0.0)
    np.testing.assert_allclose(probabilities, 1.0 / 120.0)


def test_strictly_prior_likelihood_fits_positive_temperature_when_signal_exists():
    scores = np.tile(np.asarray([[8.0, 0.0, -1.0, -2.0, -3.0, -4.0]]), (20, 1))
    target = np.zeros(20, dtype=np.int64)
    beta, fitted_loss = fit_beta(scores, target, 0.0, 2.0, 32)
    assert beta > 0.0
    assert fitted_loss < exact_top3_losses(scores, target, 0.0).mean()


def test_exact_probabilities_match_loss_at_target():
    scores = np.asarray([[0.5, 0.0, -0.3, -0.4, -0.5, -0.6]])
    target = np.asarray([0], dtype=np.int64)
    probability = exact_probabilities(scores, 0.2)
    expected = -np.log(probability[0, 0])
    np.testing.assert_allclose(exact_top3_losses(scores, target, 0.2), [expected])
