"""Offline ESPN fantasy source integrity tests; no network access."""
import copy
import importlib.util
import math
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("refresh_espn",ROOT/"scripts"/"refresh_espn.py")
espn=importlib.util.module_from_spec(spec)
spec.loader.exec_module(espn)


def game(gid=11,week=12,home=1,away=2,winner="UNDECIDED"):
    return {"id":gid,"matchupPeriodId":week,"winner":winner,
        "home":{"teamId":home,"totalPointsLive":17,"totalProjectedPointsLive":117},
        "away":{"teamId":away,"totalPointsLive":15,"totalProjectedPointsLive":115}}


class EspnRefreshIntegrityTests(unittest.TestCase):
    def test_only_scoped_week_and_exact_opponents_can_update(self):
        base=[game(11,12),game(12,11,3,4)]
        alternate=game(11,12,2,1)
        alternate["home"]["totalPointsLive"]=900
        out=espn.merge_schedule(base,[alternate,game(12,11,3,4)],12)
        self.assertEqual(out,base)
        self.assertIsNot(out,base)

    def test_final_result_cannot_downgrade_to_undecided(self):
        base=[game(11,12,winner="HOME")]
        fresh=game(11,12,winner="UNDECIDED")
        fresh["home"]["totalPointsLive"]=39.3
        out=espn.merge_schedule(base,[fresh],12)
        self.assertEqual(out[0]["winner"],"HOME")
        self.assertEqual(out[0]["home"]["totalPointsLive"],39.3)
        self.assertEqual(base[0]["home"]["totalPointsLive"],17)

    def test_espn_point_validation_rejects_negative_nonnumeric_and_nonfinite(self):
        for value in (float("inf"),float("nan"),"150",True,-20,1000,None):
            self.assertIsNone(espn.point(value))
        self.assertEqual(espn.point(0),0)
        self.assertEqual(espn.point(156.44),156.44)

    def test_invalid_score_values_cannot_replace_previous_scores(self):
        base=[game()]
        bad=game()
        bad["home"]["totalPointsLive"]="120"
        bad["away"]["totalPointsLive"]=math.nan
        out=espn.merge_schedule(base,[bad],12)
        self.assertEqual(out[0]["home"]["totalPointsLive"],17)
        self.assertEqual(out[0]["away"]["totalPointsLive"],15)

    def test_wrong_game_id_does_not_add_unverified_matchups(self):
        base=[game()]
        extra=game(gid=999,home=8,away=9)
        out=espn.merge_schedule(base,[extra],12)
        self.assertEqual(out,base)
        self.assertEqual(len(out),1)


if __name__=="__main__":
    unittest.main()
