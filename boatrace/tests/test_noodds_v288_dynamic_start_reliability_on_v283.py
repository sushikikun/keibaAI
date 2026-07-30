import unittest

import numpy as np

from train_noodds_raw_v200 import A
from noodds_v288_dynamic_start_reliability_features import (
    RUNNER_FEATURE_NAMES,
    build_dynamic_start_reliability_features,
    candidate_features,
)


def fixture(races):
    raw=np.zeros((races,6,143),dtype=np.float32)
    raw[:,:,0]=np.arange(10,16,dtype=np.float32)
    raw[:,:,17]=0.20
    raw[:,:,67]=0.15
    course=np.zeros((races,6,5),dtype=np.float32)
    course[:,:,0]=np.arange(1,7,dtype=np.float32)
    available=np.ones(races,dtype=np.uint8)
    return raw,course,available


def build(raw,course,available,dates):
    return build_dynamic_start_reliability_features(
        raw,course,available,np.asarray(dates),
        overall_prior_count=30.0,
        overall_prior_std=0.04,
        course_shrinkage=15.0,
        variance_floor=0.0001,
    )


class DynamicStartReliabilityTests(unittest.TestCase):
    def test_same_day_updates_are_deferred(self):
        raw,course,available=fixture(3)
        raw[0,:,67]=0.10
        raw[1,:,67]=0.30
        features,_=build(
            raw,course,available,
            ["2026-01-01","2026-01-01","2026-01-02"],
        )
        np.testing.assert_allclose(features[0,:,:6],features[1,:,:6])
        np.testing.assert_allclose(features[2,:,0],np.log1p(2.0))

    def test_f_l_and_missing_rows_do_not_update_moments(self):
        raw,course,available=fixture(2)
        raw[0,0,68]=1
        raw[0,1,69]=1
        raw[0,2,70]=1
        features,_=build(raw,course,available,["2026-01-01","2026-01-02"])
        np.testing.assert_allclose(features[1,:3,0],0.0)
        np.testing.assert_allclose(features[1,3:,0],np.log1p(1.0))

    def test_overall_prior_mean_and_variance_are_fixed(self):
        raw,course,available=fixture(2)
        raw[0,0,67]=0.10
        features,_=build(raw,course,available,["2026-01-01","2026-01-02"])
        expected_mean=(0.10+30.0*0.20)/31.0
        expected_second=(0.10**2+30.0*(0.20**2+0.04**2))/31.0
        expected_std=np.sqrt(max(expected_second-expected_mean**2,0.0001))
        np.testing.assert_allclose(features[1,0,1],expected_mean-0.20,rtol=1e-5)
        np.testing.assert_allclose(features[1,0,2],expected_std,rtol=1e-5)

    def test_course_moments_shrink_to_overall(self):
        raw,course,available=fixture(2)
        raw[0,0,67]=0.10
        features,_=build(raw,course,available,["2026-01-01","2026-01-02"])
        overall_mean=(0.10+30.0*0.20)/31.0
        course_mean=(0.10+15.0*overall_mean)/16.0
        np.testing.assert_allclose(
            features[1,0,3],course_mean-overall_mean,rtol=1e-5
        )
        np.testing.assert_allclose(features[1,0,5],np.log1p(1.0))

    def test_changed_course_has_no_course_history_but_overall_history(self):
        raw,course,available=fixture(2)
        course[1,:,0]=[2,1,3,4,5,6]
        features,_=build(raw,course,available,["2026-01-01","2026-01-02"])
        self.assertGreater(features[1,0,0],0.0)
        self.assertEqual(features[1,0,5],0.0)

    def test_missing_course_zeroes_course_specific_features(self):
        raw,course,available=fixture(2)
        available[1]=0
        course[1,:,0]=0
        features,_=build(raw,course,available,["2026-01-01","2026-01-02"])
        self.assertGreater(features[1,0,0],0.0)
        np.testing.assert_allclose(features[1,:,3:8],0.0)
        np.testing.assert_allclose(features[1,:,9],0.0)
        np.testing.assert_allclose(features[1,:,8],1.0)

    def test_invalid_current_start_zeroes_current_interactions(self):
        raw,course,available=fixture(2)
        raw[1,0,70]=1
        features,_=build(raw,course,available,["2026-01-01","2026-01-02"])
        np.testing.assert_allclose(features[1,0,6:9],0.0)

    def test_audit_reports_dense_prior_history(self):
        raw,course,available=fixture(2)
        _,audit=build(raw,course,available,["2026-01-01","2026-01-02"])
        self.assertEqual(audit["normal_start_slots"],12)
        self.assertEqual(audit["overall_history_known_slots"],6)
        self.assertEqual(audit["course_history_known_slots"],6)

    def test_missing_term_prior_uses_fixed_point15(self):
        raw,course,available=fixture(1)
        raw[0,0,17]=np.nan
        features,audit=build(raw,course,available,["2026-01-01"])
        np.testing.assert_allclose(features[0,0,1],0.0)
        self.assertEqual(audit["term_avg_st_prior_missing_slots"],1)

    def test_candidate_projection_order(self):
        runner=np.zeros((1,6,len(RUNNER_FEATURE_NAMES)),dtype=np.float32)
        runner[0,:,0]=np.arange(10,16)
        projected=candidate_features(runner,np.asarray([0]))
        width=len(RUNNER_FEATURE_NAMES)
        np.testing.assert_allclose(projected[0,0,:width],runner[0,A[0]])


if __name__=="__main__":
    unittest.main()
