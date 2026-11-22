"""Offline verification for the Gazette key offensive/kicker NFL injury desk."""
import datetime as dt
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PATH = Path(__file__).resolve().parent.parent / "scripts/refresh_nfl_injuries.py"
spec = importlib.util.spec_from_file_location("gazette_nfl_injuries", PATH)
feed = importlib.util.module_from_spec(spec)
spec.loader.exec_module(feed)

def sample():
    return {
        "season":{"year":2026,"type":2},
        "injuries":[
            {"team":{"id":"1","displayName":"Atlanta Falcons","abbreviation":"ATL"},
             "injuries":[
                 {"athlete":{"id":"100","displayName":"Test Receiver",
                             "position":{"displayName":"Wide Receiver","abbreviation":"WR"}},
                  "status":"Questionable","type":{"description":"Ankle"},"date":"2026-11-20T17:00:00Z"},
                 {"athlete":{"id":"101","fullName":"Test Quarterback",
                             "position":{"displayName":"Quarterback","abbreviation":"QB"}},
                  "status":"Day-To-Day","type":{"name":"Shoulder"}},
                 {"athlete":{"id":"102","displayName":"Test Running Back",
                             "position":{"displayName":"Running Back","abbreviation":"RB"}},
                  "status":"Doubtful","type":{"name":"Hamstring"}},
                 {"athlete":{"id":"103","displayName":"Test Tight End",
                             "position":{"displayName":"Tight End","abbreviation":"TE"}},
                  "status":"Injured Reserve","type":{"name":"Knee"}},
                 {"athlete":{"id":"104","displayName":"Test Kicker",
                             "position":{"displayName":"Place Kicker","abbreviation":"PK"}},
                  "status":"Out","type":{"name":"Groin"}},
             ]},
            {"team":{"id":"2","displayName":"Buffalo Bills","abbreviation":"BUF"},
             "injuries":[
                 {"athlete":{"id":"200","displayName":"Test Cornerback",
                             "position":{"abbreviation":"CB"}},
                  "status":"Out","type":{"description":"Knee"},
                  "practiceStatus":"Did Not Participate"},
                 {"athlete":{"id":"201","displayName":"Test Bills Quarterback",
                             "position":{"displayName":"Quarterback","abbreviation":"QB"}},
                  "status":"Questionable","type":{"description":"Calf"}},
                 {"athlete":{"id":"202","displayName":"Test Healthy Receiver",
                             "position":{"abbreviation":"WR"}},
                  "status":"Active","type":{"description":"Healthy"}},
             ]}
        ],
    }

class NFLInjuryFeedTests(unittest.TestCase):
    def setUp(self):
        self.now = dt.datetime(2026,11,20,21,0,tzinfo=dt.timezone.utc)

    def test_only_major_qb_rb_wr_te_k_included(self):
        result = feed.normalize(sample(), now=self.now, week=12)
        self.assertEqual(result["season"],2026)
        self.assertEqual(result["week"],12)
        self.assertEqual(result["teamCount"],2)
        self.assertEqual(result["playerCount"],5)
        self.assertEqual(result["filter"],"major-availability-only")
        self.assertEqual(set(result["positions"]),{"QB","RB","WR","TE","K"})
        by_name = {p["name"]:p for t in result["teams"] for p in t["players"]}
        self.assertEqual(set(by_name),{
            "Test Receiver","Test Running Back","Test Tight End",
            "Test Kicker","Test Bills Quarterback",
        })
        self.assertEqual(by_name["Test Receiver"]["injury"],"Ankle")
        self.assertEqual(by_name["Test Kicker"]["position"],"K")
        self.assertEqual(by_name["Test Tight End"]["reportedStatus"],"Injured Reserve")
        self.assertIsNone(by_name["Test Receiver"]["gameStatus"])  # Not inferred from ESPN status.
        self.assertEqual(result["excludedActiveCount"],1)
        self.assertEqual(result["sourceEntryCount"],8)

    def test_live_espn_groups_with_direct_team_name(self):
        raw=sample()
        raw["injuries"]=[
            {"id":"1","displayName":"Atlanta Falcons","injuries":raw["injuries"][0]["injuries"]},
            {"id":"2","displayName":"Buffalo Bills","injuries":raw["injuries"][1]["injuries"]},
        ]
        result=feed.normalize(raw,now=self.now,week=12)
        self.assertEqual(result["teamCount"],2)
        self.assertEqual(result["playerCount"],5)
        self.assertEqual(result["teams"][0]["name"],"Atlanta Falcons")

    def test_severity_is_explicit_and_not_inferred_from_practice(self):
        for status in ["Out","Doubtful","Questionable","Injured Reserve",
                       "IR","IR-R","Physically Unable to Perform","PUP"]:
            self.assertTrue(feed.major_status(status),status)
        for status in ["Day-To-Day","Active","Limited","Full","Suspended",
                       "Did Not Participate", "Probable", "Unknown"]:
            self.assertFalse(feed.major_status(status),status)
        raw=sample()
        raw["injuries"][0]["injuries"].append({
            "athlete":{"displayName":"Practice Only QB",
                       "position":{"abbreviation":"QB"}},
            "status":"Day-To-Day","practiceStatus":"Did Not Participate",
        })
        result=feed.normalize(raw,now=self.now)
        self.assertEqual(result["playerCount"],5)

    def test_game_status_can_qualify_without_overwriting_source_status(self):
        raw=sample()
        raw["injuries"][0]["injuries"].append({
            "athlete":{"displayName":"Game Out QB","position":{"abbreviation":"QB"}},
            "status":"Day-To-Day","gameStatus":"Out",
            "type":{"name":"Shoulder"},
        })
        result=feed.normalize(raw,now=self.now)
        p=next(p for t in result["teams"] for p in t["players"] if p["name"]=="Game Out QB")
        self.assertEqual(p["gameStatus"],"Out")
        self.assertEqual(p["reportedStatus"],"Day-To-Day")
        self.assertEqual(result["playerCount"],6)

    def test_only_minor_listings_is_valid_empty_not_fake_failure(self):
        raw={"season":{"year":2026},"injuries":[
            {"id":"1","displayName":"Atlanta Falcons","injuries":[
                {"athlete":{"displayName":"Healthy QB",
                            "position":{"abbreviation":"QB"}},"status":"Active"},
                {"athlete":{"displayName":"Day-to-day RB",
                            "position":{"abbreviation":"RB"}},"status":"Day-To-Day"},
            ]},
        ]}
        result=feed.normalize(raw,now=self.now)
        self.assertEqual(result["teamCount"],0)
        self.assertEqual(result["playerCount"],0)
        self.assertEqual(result["sourceEntryCount"],2)

    def test_rejects_incomplete_or_wrong_season(self):
        with self.assertRaises(ValueError):
            feed.normalize({"injuries":[]},now=self.now)
        wrong=sample();wrong["season"]["year"]=2025
        with self.assertRaises(ValueError):
            feed.normalize(wrong,now=self.now)
        empty=sample();empty["injuries"]=[{"team":{"id":"1","displayName":"Test"},"injuries":[{}]}]
        with self.assertRaises(ValueError):
            feed.normalize(empty,now=self.now)

    def test_duplicate_players_not_double_counted(self):
        raw=sample()
        raw["injuries"][0]["injuries"].append(raw["injuries"][0]["injuries"][0].copy())
        self.assertEqual(feed.normalize(raw,now=self.now)["playerCount"],5)

    def test_retains_previous_snapshot_on_api_failure(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/"data/nfl-injuries.json"
            out.parent.mkdir()
            out.write_text(json.dumps({"fetchedAt":"2026-11-19T01:00:00Z",
                                       "teams":[{"name":"Verified original"}]}))
            with patch.object(feed,"OUT",out),patch.object(feed,"fetch",side_effect=OSError("offline")):
                feed.main()
            self.assertEqual(json.loads(out.read_text())["teams"][0]["name"],"Verified original")

    def test_missing_feed_is_explicitly_unavailable(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/"data/nfl-injuries.json"
            with patch.object(feed,"OUT",out),patch.object(feed,"fetch",side_effect=OSError("blocked")):
                feed.main()
            self.assertEqual(json.loads(out.read_text())["status"],"unavailable")

if __name__=="__main__":
    unittest.main()
