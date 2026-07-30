import unittest

import numpy as np

from train_noodds_raw_v200 import A, B, C
from train_noodds_v276_course_adjusted_exhibition_on_v270 import (
    RAW_FEATURE_INDICES,
    RUNNER_FEATURE_NAMES,
    build_course_adjusted_runner,
    candidate_features,
)


class CourseAdjustedExhibitionTests(unittest.TestCase):
    def test_fixed_interactions_and_missing_course_flag(self):
        course = np.zeros((2, 6, 5), dtype=np.float32)
        raw = np.zeros((2, 6, 143), dtype=np.float32)
        available = np.asarray([1, 0], dtype=np.uint8)
        course[0, :, 0] = np.arange(1, 7)
        course[0, :, 1] = np.asarray([0, 1, -1, 2, -2, 0])
        raw[0, :, 110] = 0.1
        raw[0, :, 111] = 0.2
        raw[0, :, 104] = -0.3
        raw[0, :, 105] = -0.4

        combined = build_course_adjusted_runner(course, raw, available)

        self.assertEqual(combined.shape, (2, 6, len(RUNNER_FEATURE_NAMES)))
        self.assertEqual(len(RAW_FEATURE_INDICES), 9)
        delta = course[0, :, 1]
        np.testing.assert_allclose(combined[0, :, 14], delta * 0.1)
        np.testing.assert_allclose(combined[0, :, 15], delta * 0.2)
        np.testing.assert_allclose(combined[0, :, 16], delta * -0.3)
        np.testing.assert_allclose(combined[0, :, 17], delta * -0.4)
        np.testing.assert_allclose(combined[0, :, 18], 1.0)
        np.testing.assert_allclose(combined[1, :, 18], 0.0)

    def test_candidate_projection_follows_trifecta_runner_order(self):
        course = np.zeros((1, 6, 5), dtype=np.float32)
        raw = np.zeros((1, 6, 143), dtype=np.float32)
        available = np.ones(1, dtype=np.uint8)
        course[0, :, 0] = np.arange(1, 7)
        combined = build_course_adjusted_runner(course, raw, available)
        race = np.asarray([[1, 2, 3, 2]], dtype=np.float32)

        projected = candidate_features(combined, race, np.asarray([0]))
        width = len(RUNNER_FEATURE_NAMES)

        np.testing.assert_allclose(projected[0, 0, :width], combined[0, A[0]])
        np.testing.assert_allclose(projected[0, 0, width:2 * width], combined[0, B[0]])
        np.testing.assert_allclose(projected[0, 0, 2 * width:3 * width], combined[0, C[0]])


if __name__ == "__main__":
    unittest.main()
