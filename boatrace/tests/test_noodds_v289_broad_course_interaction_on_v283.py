import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from train_noodds_raw_v200 import A, B, C
from noodds_v289_broad_course_interaction_features import (
    COURSE_RACE_NAMES,
    COURSE_RUNNER_NAMES,
    RACE_NAMES,
    RUNNER_INDICES,
    RUNNER_NAMES,
    candidate_features,
    feature_names,
)
from train_noodds_v289_broad_course_interaction_on_v283 import (
    load_or_build_feature_cache,
)


def fixture(races=1):
    raw=np.zeros((races,6,143),dtype=np.float32)
    for lane in range(6):
        raw[:,lane,:]=lane*1000+np.arange(143,dtype=np.float32)
    race=np.zeros((races,21),dtype=np.float32)
    race[:]=np.arange(21,dtype=np.float32)
    course=np.zeros((races,6,5),dtype=np.float32)
    for lane in range(6):
        course[:,lane,:]=lane*10+np.arange(5,dtype=np.float32)
    course_race=np.asarray([[1,2,3,4]],dtype=np.float32)
    return raw,race,course,course_race


class BroadCourseInteractionTests(unittest.TestCase):
    def test_fixed_feature_contract(self):
        self.assertEqual(len(RUNNER_INDICES),24)
        self.assertEqual(len(RUNNER_NAMES),24)
        self.assertEqual(len(COURSE_RUNNER_NAMES),5)
        self.assertEqual(len(RACE_NAMES),12)
        self.assertEqual(len(COURSE_RACE_NAMES),4)
        self.assertEqual(len(feature_names()),154)

    def test_projection_shape_and_first_second_third_order(self):
        raw,race,course,course_race=fixture()
        out=candidate_features(raw,race,course,course_race,np.asarray([0]))
        self.assertEqual(out.shape,(1,120,154))
        selected=np.concatenate(
            [raw[0][:,RUNNER_INDICES],course[0]],axis=1
        )
        width=29
        np.testing.assert_allclose(out[0,0,:width],selected[A[0]])
        np.testing.assert_allclose(out[0,0,width:2*width],selected[B[0]])
        np.testing.assert_allclose(out[0,0,2*width:3*width],selected[C[0]])

    def test_field_mean_and_std_use_all_six_runners(self):
        raw,race,course,course_race=fixture()
        out=candidate_features(raw,race,course,course_race,np.asarray([0]))
        offset=3*29
        values=raw[0][:,RUNNER_INDICES]
        np.testing.assert_allclose(out[0,0,offset:offset+24],values.mean(axis=0))
        np.testing.assert_allclose(out[0,0,offset+24:offset+48],values.std(axis=0))

    def test_race_and_course_race_context_order(self):
        raw,race,course,course_race=fixture()
        out=candidate_features(raw,race,course,course_race,np.asarray([0]))
        offset=3*29+48
        np.testing.assert_allclose(out[0,0,offset:offset+12],race[0,9:21])
        np.testing.assert_allclose(out[0,0,offset+12:offset+16],course_race[0])

    def test_all_missing_field_remains_nan(self):
        raw,race,course,course_race=fixture()
        raw[0,:,RUNNER_INDICES[0]]=np.nan
        out=candidate_features(raw,race,course,course_race,np.asarray([0]))
        offset=3*29
        self.assertTrue(np.isnan(out[0,0,offset]))
        self.assertTrue(np.isnan(out[0,0,offset+24]))

    def test_missing_course_zeros_are_not_imputed(self):
        raw,race,course,course_race=fixture()
        course[:]=0
        course_race[:]=0
        out=candidate_features(raw,race,course,course_race,np.asarray([0]))
        np.testing.assert_allclose(out[0,0,24:29],0)
        offset=3*29+48+12
        np.testing.assert_allclose(out[0,0,offset:offset+4],0)

    def test_feature_cache_round_trip_and_integrity(self):
        raw,race,course,course_race=fixture(races=2)
        course_race=np.repeat(course_race,2,axis=0)
        indices=np.asarray([0,1],dtype=np.int64)
        with TemporaryDirectory() as temp:
            first=load_or_build_feature_cache(
                Path(temp),"full","d6",indices,raw,race,course,course_race,
                "ABC",True,
            )
            self.assertIsInstance(first,np.memmap)
            expected=candidate_features(
                raw,race,course,course_race,indices
            )
            np.testing.assert_allclose(first,expected)
            second=load_or_build_feature_cache(
                Path(temp),"full","d6",indices,raw,race,course,course_race,
                "ABC",False,
            )
            self.assertIsInstance(second,np.memmap)
            with self.assertRaises(ValueError):
                load_or_build_feature_cache(
                    Path(temp),"full","d6",indices[::-1],raw,race,course,
                    course_race,"ABC",False,
                )
            del first
            del second


if __name__=="__main__":
    unittest.main()
