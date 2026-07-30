import unittest

import numpy as np

from train_weather_dynamics_residual_v219 import (
    build_weather_dynamics,
    weather_feature_names,
)


class WeatherDynamicsResidualTests(unittest.TestCase):
    def make_meta(self):
        return [
            {"race_date": "2026-01-01", "venue_code": "1", "race_no": str(i)}
            for i in (1, 2, 3)
        ]

    def make_features(self):
        values = np.full((3, 21), np.nan, dtype=np.float32)
        values[:, 10] = [20.0, 22.0, 21.0]
        values[:, 11] = [2.0, 4.0, 3.0]
        values[:, 12] = [0.0, 1.0, 0.0]
        values[:, 13] = [1.0, 0.0, 1.0]
        values[:, 15] = [18.0, 19.0, 20.0]
        values[:, 16] = [1.0, 3.0, 2.0]
        return values

    def test_future_weather_cannot_change_past_features(self):
        raw_a = self.make_features()
        raw_b = raw_a.copy()
        raw_b[2, [10, 11, 12, 13, 15, 16]] = [
            35.0,
            9.0,
            -1.0,
            0.0,
            30.0,
            15.0,
        ]

        dynamics_a = build_weather_dynamics(raw_a, self.make_meta())
        dynamics_b = build_weather_dynamics(raw_b, self.make_meta())

        np.testing.assert_allclose(dynamics_a[:2], dynamics_b[:2])
        self.assertGreater(
            float(np.abs(dynamics_a[2] - dynamics_b[2]).sum()),
            0.0,
        )

    def test_fixed_scalar_and_direction_deltas(self):
        dynamics = build_weather_dynamics(
            self.make_features(), self.make_meta()
        )
        names = weather_feature_names()
        index = {name: i for i, name in enumerate(names)}

        self.assertAlmostEqual(
            float(dynamics[1, index["temperature_c_current_minus_previous"]]),
            2.0,
        )
        self.assertAlmostEqual(
            float(dynamics[1, index["temperature_c_current_minus_prior_mean"]]),
            2.0,
        )
        self.assertAlmostEqual(
            float(dynamics[1, index["wind_previous_chord_distance"]]),
            np.sqrt(2.0),
            places=6,
        )
        self.assertAlmostEqual(
            float(dynamics[2, index["temperature_c_prior_standard_deviation"]]),
            1.0,
        )
        self.assertTrue(np.isfinite(dynamics).all())


if __name__ == "__main__":
    unittest.main()
