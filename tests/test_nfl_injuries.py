"""Offline tests for verified NFL injury listings; no live ESPN API dependency."""
import datetime as dt
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PATH=Path(__file__).resolve().parent.parent/"scripts/refresh_nfl_injuries.py"
spec=importlib.util.spec_from_file_location("gazette_nfl_injuries",PATH)
feed=importlib.util.module_from_spec(spec)
spec.loader.exec_module(feed)

def sample():
    return {
        "season":{"year":2026,"type":2},
        "injuries":[
            {"team":{"id":"1","displayName":"Atlanta Falcons","abbreviation":"ATL"},
             "injuries":[
                 {"athlete":{"id":"100","displayName":"Test Receiver","position":{"abbreviation":"WR"}},
                  "status":"Questionable","type":{"description":"Ankle"},"date":"2026-11-20T17:00:00Z"},
                 {"athlete":{"id":"101","fullName":"Test Quarterback","position":{"abbreviation":"QB"}},
                  "status":"Day-To-Day","type":{"name":"Shoulder"}}
             ]},
            {"team":{"id":"2","displayName":"Buffalo Bills","abbreviation":"BUF"},
             "injuries":[
                 {"athlete":{"displayName":"Test Cornerback","position":{"abbreviation":"CB"}},
                  "status":"Out","type":{"description":"Knee"},"practiceStatus":"Did Not Participate"},
             ]}
        ]
    }

class NFLInjuryFeedTests(unittest.TestCase):
    def setUp(self):
        self.now=dt.datetime(2026,11,20,21,0,tzinfo=dt.timezone.utc)

    def test_normalizes_multiple_teams_and_statuses(self):
        result=feed.normalize(sample(),now=self.now,week=12)
        self.assertEqual(result["season"],2026)
        self.assertEqual(result["week"],12)
        self.assertEqual(result["teamCount"],2)
        self.assertEqual(result["playerCount"],3)
        a=result["teams"][0]["players"]
        self.assertEqual(a[0]["name"],"Test Receiver")
        self.assertEqual(a[0]["reportedStatus"],"Questionable")
        self.assertIsNone(a[0]["gameStatus"]) # An ESPN label is NOT an official game report
        self.assertEqual(a[0]["injury"],"Ankle")
        self.assertEqual(a[1]["reportedStatus"],"Day-To-Day")
        self.assertIsNone(a[1]["practiceStatus"])
        self.assertEqual(result["teams"][1]["players"][0]["practiceStatus"],"Did Not Participate")

    def test_live_espn_groups_with_direct_team_id_and_displayname(self):
        raw=sample()
        raw["injuries"]=[
            {"id":"1","displayName":"Atlanta Falcons","injuries":raw["injuries"][0]["injuries"]},
            {"id":"2","displayName":"Buffalo Bills","injuries":raw["injuries"][1]["injuries"]},
        ]
        result=feed.normalize(raw,now=self.now,week=12)
        self.assertEqual(result["teamCount"],2)
        self.assertEqual(result["playerCount"],3)
        self.assertEqual(result["teams"][0]["name"],"Atlanta Falcons")

    def test_ordinary_active_roster_records_are_not_labeled_injured(self):
        raw=sample()
        raw["injuries"][0]["injuries"].append(
            {"athlete":{"displayName":"Healthy Roster Player"},
             "status":"Active","type":{"name":"Unknown"}})
        result=feed.normalize(raw,now=self.now)
        self.assertEqual(result["playerCount"],3)
        self.assertEqual(result["excludedActiveCount"],1)
        self.assertEqual(result["sourceEntryCount"],4)
        self.assertNotIn("Healthy Roster Player",
            [p["name"] for t in result["teams"] for p in t["players"]])

    def test_rejects_incomplete_or_wrong_season(self):
        with self.assertRaises(ValueError):
            feed.normalize({"injuries":[]},now=self.now)
        broken=sample(); broken["season"]["year"]=2025
        with self.assertRaises(ValueError):
            feed.normalize(broken,now=self.now)
        missing=sample(); missing["injuries"]=[{"team":{"id":"1","displayName":"Test"},"injuries":[{}]}]
        with self.assertRaises(ValueError):
            feed.normalize(missing,now=self.now)

    def test_deduplicates_identical_injuries(self):
        raw=sample()
        raw["injuries"][0]["injuries"].append(raw["injuries"][0]["injuries"][0].copy())
        self.assertEqual(feed.normalize(raw,now=self.now)["playerCount"],3)

    def test_retains_previous_verification_on_api_failure(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/"data/nfl-injuries.json"
            out.parent.mkdir()
            out.write_text(json.dumps({"fetchedAt":"2026-11-19T01:00:00Z","teams":[{"name":"Verified original"}]}))
            with patch.object(feed,"OUT",out),patch.object(feed,"fetch",side_effect=OSError("provider offline")):
                feed.main()
            self.assertEqual(json.loads(out.read_text())["teams"][0]["name"],"Verified original")

    def test_unavailable_file_is_explicit(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/"data/nfl-injuries.json"
            with patch.object(feed,"OUT",out),patch.object(feed,"fetch",side_effect=OSError("blocked")):
                feed.main()
            self.assertEqual(json.loads(out.read_text())["status"],"unavailable")

if __name__=="__main__":
    unittest.main()
