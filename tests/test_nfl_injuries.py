"""Offline starter OUT watch tests, including ESPN's truncated 25-player feed."""
import datetime as dt
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

FILE=Path(__file__).resolve().parents[1]/"scripts/refresh_nfl_injuries.py"
spec=importlib.util.spec_from_file_location("injury_starters",FILE)
feed=importlib.util.module_from_spec(spec)
spec.loader.exec_module(feed)
NOW=dt.datetime(2026,11,22,18,0,tzinfo=dt.timezone.utc)

def athlete(id_,name,status=None,date="2026-11-22T16:00Z"):
    data={"id":str(id_),"displayName":name,
          "links":[{"href":f"https://www.espn.com/nfl/player/_/id/{id_}/{name.lower().replace(' ','-')}"}],
          "injuries":[]}
    if status:
        data["injuries"]=[{"date":date,"status":status,"details":{"bodyPart":"Shoulder"}}]
    return data

def depth():
    return {"season":{"year":2026},"depthchart":[
        {"name":"3WR 1TE","positions":{
            "qb":{"athletes":[athlete(101,"Starter QB","Out"),athlete(102,"Backup QB","Out")]},
            "rb":{"athletes":[athlete(103,"Starter RB","Questionable")]},
            "wr1":{"athletes":[athlete(104,"Starter WR One"),athlete(105,"Backup WR","Out")]},
            "wr2":{"athletes":[athlete(106,"Starter WR Two","Injured Reserve",date="2026-11-01T10:00Z")]},
            "te":{"athletes":[athlete(107,"Starter TE","Out",date="2026-11-01T10:00Z")]},
        }},
        {"name":"Special Teams","positions":{
            "pk":{"athletes":[athlete(108,"Starting Kicker","Out")]},
            "kr":{"athletes":[athlete(109,"Kick Returner","Out")]},
        }},
    ]}

def injury_entry(id_,name,status,date="2026-11-22T16:00Z"):
    # No athlete.id, as observed in ESPN's league-wide injury response.
    return {"athlete":{"displayName":name,"links":[
        {"href":f"https://www.espn.com/nfl/player/_/id/{id_}/official-player"}]},
        "status":status,"date":date,"type":{"description":"out"}}

def feed_data(entries=None):
    return {"season":{"year":2026},"injuries":[
        {"id":"1","displayName":"Atlanta Falcons","injuries":entries or [
            injury_entry(101,"Starter QB","Out"),
            injury_entry(102,"Backup QB","Out"),
            injury_entry(103,"Starter RB","Questionable"),
            injury_entry(106,"Starter WR Two","Injured Reserve",date="2026-11-01T10:00Z"),
            injury_entry(107,"Starter TE","Out",date="2026-11-01T10:00Z"),
            injury_entry(108,"Starting Kicker","Out"),
        ]},
    ]}

class StarterInjuryWatchTests(unittest.TestCase):
    def test_depthchart_picks_only_espn_first_string_and_kicker(self):
        starters=feed.first_string(depth())
        self.assertEqual(set(starters),{"101","103","104","106","107","108"})
        self.assertEqual(starters["101"]["starterSlot"],"QB")
        self.assertEqual(starters["106"]["position"],"WR")
        self.assertEqual(starters["108"]["position"],"K")
        self.assertNotIn("102",starters)
        self.assertNotIn("109",starters) # Returner is not the starting kicker.

    def test_report_includes_only_reported_out_and_ir_pup_starters(self):
        result=feed.normalize(feed_data(),{"1":depth()},now=NOW,week=12)
        self.assertEqual(result["filter"],"first-string-out-only")
        self.assertEqual(result["teamCount"],1)
        self.assertEqual(result["playerCount"],3)
        self.assertEqual(result["outCount"],2)
        self.assertEqual(result["reserveCount"],1)
        names={p["name"]:p for t in result["teams"] for p in t["players"]}
        self.assertEqual(set(names),{"Starter QB","Starter WR Two","Starting Kicker"})
        self.assertTrue(all(p["depthRank"]==1 for p in names.values()))
        self.assertEqual(names["Starter WR Two"]["outType"],"reserve")
        self.assertEqual(names["Starter QB"]["injury"],"Shoulder")
        self.assertEqual(names["Starter QB"]["athleteId"],"101")

    def test_injury_in_embedded_depthchart_not_in_25_entry_feed_is_included(self):
        # Injury feed includes no matching starter; depthchart still confirms
        # the currently OUT player directly.
        data=feed_data([injury_entry(998,"Other Cornerback","Out")])
        result=feed.normalize(data,{"1":depth()},now=NOW)
        self.assertIn("Starter QB",[p["name"] for t in result["teams"] for p in t["players"]])
        self.assertEqual(result["playerCount"],3)

    def test_latest_active_status_overrides_older_out(self):
        chart=depth()
        chart["depthchart"][0]["positions"]["qb"]["athletes"][0]["injuries"][0]["date"]="2026-11-19T12:00Z"
        current=injury_entry(101,"Starter QB","Active","2026-11-22T16:01Z")
        result=feed.normalize(feed_data([current]),{"1":chart},now=NOW)
        self.assertNotIn("Starter QB",[p["name"] for t in result["teams"] for p in t["players"]])

    def test_recent_out_not_infinite_across_weeks(self):
        self.assertFalse(feed.recent_out({"status":"Out","date":"2026-11-01T12:00Z"},NOW))
        self.assertTrue(feed.recent_out({"status":"Injured Reserve","date":"2026-10-02T12:00Z"},NOW))
        self.assertFalse(feed.recent_out({"status":"Doubtful","date":"2026-11-22T12:00Z"},NOW))
        self.assertFalse(feed.recent_out({"status":"Questionable","date":"2026-11-22T12:00Z"},NOW))
        self.assertFalse(feed.recent_out({"status":"Out"},NOW))

    def test_zero_absent_first_string_is_valid_no_fabrication(self):
        ch=depth()
        for group in ch["depthchart"]:
            for slot in group["positions"].values():
                for player in slot["athletes"]:player["injuries"]=[]
        result=feed.normalize(feed_data([injury_entry(102,"Backup QB","Out")]),{"1":ch},now=NOW)
        self.assertEqual(result["playerCount"],0)
        self.assertEqual(result["teams"],[])
        self.assertTrue(result["coverageComplete"])

    def test_duplicate_and_no_wrong_team_matches(self):
        data=feed_data([injury_entry(102,"Backup QB","Out"),
                        injury_entry(102,"Backup QB","Out")])
        result=feed.normalize(data,{"1":depth()},now=NOW)
        self.assertEqual(result["playerCount"],3)

    def test_team_depthchart_failure_is_explicit_incomplete_coverage(self):
        raw=feed_data()
        raw["injuries"].append({"id":"2","displayName":"Buffalo Bills","injuries":[]})
        result=feed.normalize(raw,{"1":depth()},now=NOW)
        self.assertFalse(result["coverageComplete"])
        self.assertEqual(result["depthChartTeamCount"],1)
        self.assertEqual(result["teamsNotVerified"],["2"])

    def test_rejects_malformed_data_and_other_seasons(self):
        with self.assertRaises(ValueError):
            feed.normalize({"injuries":[]},{"1":depth()},now=NOW)
        with self.assertRaises(ValueError):
            feed.normalize(feed_data(),{},now=NOW)
        other=depth();other["season"]["year"]=2025
        with self.assertRaises(ValueError):
            feed.normalize(feed_data(),{"1":other},now=NOW)

    def test_failure_preserves_previous_verification_timestamp(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/"nfl-injuries.json"
            out.write_text(json.dumps({"status":"available","fetchedAt":"2026-11-19T14:00:00Z"}))
            with patch.object(feed,"OUT",out),patch.object(feed,"get_json",side_effect=OSError("no provider")):
                feed.main()
            self.assertEqual(json.loads(out.read_text())["fetchedAt"],"2026-11-19T14:00:00Z")

    def test_unavailable_when_no_verified_source_exists(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/"nfl-injuries.json"
            with patch.object(feed,"OUT",out),patch.object(feed,"get_json",side_effect=OSError("no provider")):
                feed.main()
            self.assertEqual(json.loads(out.read_text())["status"],"unavailable")

if __name__=="__main__":
    unittest.main()
