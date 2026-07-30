import unittest

import numpy as np

from train_form_trend_residual_v220 import (
    CONTRASTS,
    build_form_features,
    form_feature_names,
)


class FormTrendResidualTests(unittest.TestCase):
    def test_fixed_contrasts_and_field_centering(self):
        source = np.full((1, 6, 143), np.nan, dtype=np.float32)
        for _name, short_index, long_index in CONTRASTS:
            source[0, :, short_index] = np.arange(6, dtype=np.float32)
            source[0, :, long_index] = 1.0

        result = build_form_features(source)

        expected = np.arange(6, dtype=np.float32) - 1.0
        expected_centered = expected - expected.mean()
        np.testing.assert_allclose(result[0, :, 0], expected)
        np.testing.assert_allclose(
            result[0, :, 1], expected_centered
        )
        self.assertEqual(result.shape, (1, 6, len(CONTRASTS) * 2))
        self.assertEqual(len(form_feature_names()), len(CONTRASTS) * 2)

    def test_missing_source_remains_missing(self):
        source = np.zeros((1, 6, 143), dtype=np.float32)
        _name, short_index, long_index = CONTRASTS[0]
        source[0, 2, short_index] = np.nan

        result = build_form_features(source)

        self.assertTrue(np.isnan(result[0, 2, 0]))
        self.assertTrue(np.isnan(result[0, 2, 1]))
        self.assertTrue(np.isfinite(result[0, [0, 1, 3, 4, 5], 1]).all())
        self.assertEqual(long_index, 32)


if __name__ == "__main__":
    unittest.main()
