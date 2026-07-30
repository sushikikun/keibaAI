from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_start_course_sidecar_v231 import build_arrays, course_map


def official_rows(race_key: str, courses: list[int]) -> list[dict]:
    return [
        {
            "race_key": race_key,
            "lane": str(lane),
            "start_display_course": str(course),
        }
        for lane, course in enumerate(courses, start=1)
    ]


class BuildStartCourseSidecarV231Tests(unittest.TestCase):
    def test_aligns_by_race_key_and_encodes_course_change(self):
        rows = official_rows("race_b", [1, 2, 3, 4, 6, 5])
        rows += official_rows("race_a", [1, 2, 3, 4, 5, 6])
        runner, race, available, missing = build_arrays(
            ["race_a", "race_b"], course_map(rows), allow_missing=False
        )
        np.testing.assert_array_equal(runner[0, :, 0], np.arange(1, 7))
        np.testing.assert_array_equal(
            runner[1, :, 1], np.array([0, 0, 0, 0, 1, -1])
        )
        np.testing.assert_array_equal(
            runner[1, :, 2], np.array([0, 0, 0, 0, 1, 1])
        )
        np.testing.assert_array_equal(race[1], np.array([1, 2, 2, 1]))
        np.testing.assert_array_equal(available, np.array([True, True]))
        self.assertEqual(missing, [])

    def test_missing_course_is_rejected_unless_explicitly_allowed(self):
        mapping = course_map(
            official_rows("race_a", [1, 2, 3, 4, 5, 6])
        )
        with self.assertRaisesRegex(ValueError, "missing for 1"):
            build_arrays(
                ["race_a", "race_b"], mapping, allow_missing=False
            )
        runner, race, available, missing = build_arrays(
            ["race_a", "race_b"], mapping, allow_missing=True
        )
        self.assertFalse(available[1])
        self.assertEqual(missing, ["race_b"])
        np.testing.assert_array_equal(runner[1], 0.0)
        np.testing.assert_array_equal(race[1], 0.0)

    def test_prefers_legacy_db_key_used_by_dataset(self):
        rows = official_rows(
            "20251207_18_03", [1, 2, 3, 4, 5, 6]
        )
        for row in rows:
            row["db_race_key"] = "2025127_18_03"
        mapping = course_map(rows)
        self.assertEqual(set(mapping), {"2025127_18_03"})
        _runner, race, available, missing = build_arrays(
            ["2025127_18_03"], mapping, allow_missing=False
        )
        self.assertEqual(race[0, 0], 1.0)
        self.assertTrue(available[0])
        self.assertEqual(missing, [])


    def test_invalid_permutation_is_rejected(self):
        rows = official_rows("race_a", [1, 2, 3, 4, 5, 5])
        with self.assertRaisesRegex(ValueError, "invalid course permutation"):
            course_map(rows)


if __name__ == "__main__":
    unittest.main()
