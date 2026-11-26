"""Offline reliability tests for two-day verified facts and daily fictional copy."""
import datetime as dt
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

MODULE=Path(__file__).resolve().parent.parent/"scripts/build_newspaper_pages.py"
spec=importlib.util.spec_from_file_location("gazette_newspaper_pages",MODULE)
pages=importlib.util.module_from_spec(spec)
spec.loader.exec_module(pages)

class NewspaperPagesTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        (self.root/"data").mkdir()
        self.now=dt.datetime(2026,11,24,14,17,tzinfo=dt.timezone.utc)
        self.teams=[{"teamId":i,"name":f"Verified ESPN Club {i}",
           "wins":12-i,"losses":i,"ties":0,"pointsFor":1400+i*21}
           for i in range(1,11)]
        self.league={
            "leagueId":"1413446022","season":2026,
            "fetchedAt":self.now.isoformat(),"currentMatchupPeriod":12,
            "standings":self.teams,
            "matchups":[
                {"week":11,"winner":"HOME",
                 "home":{"teamId":1,"points":131.25},
                 "away":{"teamId":2,"points":104.5}},
                {"week":11,"winner":"AWAY",
                 "home":{"teamId":3,"points":101.25},
                 "away":{"teamId":4,"points":125.0}},
                {"week":12,"winner":"UNDECIDED",
                 "home":{"teamId":1,"points":0},
                 "away":{"teamId":4,"points":0}},
                {"week":12,"winner":"UNDECIDED",
                 "home":{"teamId":6,"points":0},
                 "away":{"teamId":7,"points":0}},
                {"week":11,"winner":"HOME",
                 "home":{"teamId":5,"points":88.0},
                 "away":{"teamId":8,"points":99.5}}, # contradiction -> excluded
                {"week":10,"winner":"UNDECIDED",
                 "home":{"teamId":9,"points":25.0},
                 "away":{"teamId":10,"points":27.0}}
            ],
            "recentRosterActivity":{
              "status":"verified",
              "teams":[{"week":12,"name":"Verified ESPN Club 2","acquisitions":2},
                       {"week":11,"name":"Verified ESPN Club 6","acquisitions":1}]
            }
        }
        self.save(self.league)

    def save(self,payload):
        (self.root/"data/league.json").write_text(json.dumps(payload),encoding="utf-8")

    def generate(self,now=None,previous=None):
        return pages.generate(now or self.now,root=self.root,previous=previous)

    def test_page_one_only_source_backed_stats_and_consistent_finals(self):
        report=self.generate()
        one=report["pageOne"]
        self.assertEqual(one["status"],"verified")
        self.assertEqual(len(one["standings"]),10)
        self.assertEqual(one["standings"][0]["name"],"Verified ESPN Club 1")
        self.assertEqual(one["standings"][0]["pointsFor"],1421.0)
        self.assertEqual(one["leader"]["wins"],11)
        self.assertEqual(one["latestFinalWeek"],11)
        self.assertEqual(len(one["finals"]),2)
        self.assertEqual(one["finals"][0]["winner"],"Verified ESPN Club 1")
        self.assertEqual(one["finals"][1]["winner"],"Verified ESPN Club 4")
        self.assertFalse(any("Club 5" in json.dumps(x) for x in one["finals"]))
        self.assertNotIn("interviews",one)
        self.assertNotIn("fictional",json.dumps(one).lower())

    def test_refresh_page_one_after_48_hours_not_before(self):
        first=self.generate()
        within=self.now+dt.timedelta(hours=47,minutes=59)
        updated=json.loads(json.dumps(self.league))
        updated["fetchedAt"]=within.isoformat()
        updated["standings"][0]["wins"]=13
        self.save(updated)
        second=self.generate(within,previous=first)
        self.assertEqual(second["pageOne"],first["pageOne"])
        self.assertNotEqual(second["pageTwo"]["editionDateEastern"],
                            first["pageTwo"]["editionDateEastern"])
        self.assertNotEqual(second["pageTwo"]["banter"],first["pageTwo"]["banter"])
        due=self.now+dt.timedelta(hours=48)
        updated["fetchedAt"]=due.isoformat()
        self.save(updated)
        third=self.generate(due,previous=second)
        self.assertEqual(third["pageOne"]["standings"][0]["wins"],13)
        self.assertNotEqual(third["pageOne"]["publishedAt"],first["pageOne"]["publishedAt"])

    def test_failed_espn_refresh_preserves_old_facts_not_guessed_news(self):
        saved=self.generate()
        (self.root/"data/league.json").unlink()
        now=self.now+dt.timedelta(days=3)
        stale=self.generate(now,previous=saved)
        self.assertEqual(stale["pageOne"],saved["pageOne"])
        self.assertIsNone(stale["pageTwo"]["sourceAt"])
        self.assertEqual(len(stale["pageTwo"]["interviews"]),10)
        self.assertEqual(stale["pageTwo"]["fixtures"],[])
        self.assertEqual(stale["pageTwo"]["waivers"],[])
        self.assertIn("unavailable",stale["pageTwo"]["waiverNote"])
        self.assertFalse(stale["pageTwo"]["teamNamesFromVerifiedSource"])

    def test_unknown_league_is_never_treated_as_verified(self):
        wrong={**self.league,"leagueId":"9999999"}
        self.save(wrong)
        d=self.generate()
        self.assertEqual(d["pageOne"]["status"],"unavailable")
        self.assertFalse(d["pageTwo"]["interviews"])
        self.assertFalse(d["pageTwo"]["fixtures"])

    def test_daily_fictional_fan_interviews_cover_all_ten_teams(self):
        one=self.generate()
        two=one["pageTwo"]
        self.assertEqual(two["status"],"available")
        self.assertIn("Adrian Mercer",two["writer"])
        self.assertEqual(len(two["interviews"]),10)
        self.assertEqual({t["name"] for t in self.teams},
                         {i["team"] for i in two["interviews"]})
        self.assertTrue(all(i["fictional"] is True for i in two["interviews"]))
        self.assertIn("invented",two["fictionNotice"])
        self.assertEqual(two["fixtureWeek"],12)
        self.assertEqual(len(two["fixtures"]),2)
        self.assertIn("verified",two["waiverNote"].lower())
        self.assertEqual(two["waivers"][0]["team"],"Verified ESPN Club 2")
        self.assertEqual(two["waivers"][0]["acquisitions"],2)
        self.assertIn("official playoff seedings",two["championship"].lower())
        self.assertIn("Golden Toilet",two["consolation"])

    def test_chatgpt_fan_insights_require_today_and_all_verified_teams(self):
        baseline=self.generate()
        folder=self.root/"editorial"
        folder.mkdir()
        doc={"date":baseline["pageTwo"]["editionDateEastern"],
             "editorialStatus":"owner-approved-on-merge",
             "generationMethod":"chatgpt-draft-owner-review",
             "fanInsights":[{"team":t["name"],"quote":"A fresh fictional comment for "+t["name"],"fictional":True} for t in self.teams]}
        path=folder/"latest.json"
        path.write_text(json.dumps(doc),encoding="utf-8")
        result=self.generate()
        self.assertEqual(result["pageOne"],baseline["pageOne"])
        self.assertEqual(result["pageTwo"]["interviews"][0]["quote"],doc["fanInsights"][0]["quote"])
        self.assertEqual(result["pageTwo"]["interviews"][0]["fan"],baseline["pageTwo"]["interviews"][0]["fan"])
        for change in ({"date":"2026-01-01"},{"editorialStatus":"draft"},{"fanInsights":doc["fanInsights"][:-1]}):
            path.write_text(json.dumps({**doc,**change}),encoding="utf-8")
            self.assertEqual(self.generate()["pageTwo"]["interviews"],baseline["pageTwo"]["interviews"])
        doc["fanInsights"][0]["fictional"]=False
        path.write_text(json.dumps(doc),encoding="utf-8")
        self.assertEqual(self.generate()["pageTwo"]["interviews"],baseline["pageTwo"]["interviews"])

    def test_disclosure_and_factual_only_page_one_survive_serialization(self):
        data=self.generate()
        raw=json.dumps(data,allow_nan=False)
        self.assertIn("fictional",raw)
        self.assertNotIn("a real fan",raw.lower())
        self.assertEqual(json.loads(raw)["pageOne"]["sourceAt"],self.league["fetchedAt"])
        self.assertTrue(pages.valid_prior(data["pageOne"],self.now))
        tamper=json.loads(raw)["pageOne"]
        tamper["leagueId"]="not-this-league"
        self.assertFalse(pages.valid_prior(tamper,self.now))

    def test_prior_page_one_is_retained_on_day_one_even_after_data_refresh(self):
        first=self.generate()
        update=json.loads(json.dumps(self.league))
        update["standings"][0]["wins"]=99
        update["fetchedAt"]=(self.now+dt.timedelta(days=1)).isoformat()
        self.save(update)
        result=self.generate(self.now+dt.timedelta(days=1),previous=first)
        self.assertEqual(result["pageOne"],first["pageOne"])
        self.assertNotEqual(result["pageTwo"]["editionDateEastern"],
                            first["pageTwo"]["editionDateEastern"])


class ESPNRosterAcquisitionTests(unittest.TestCase):
    def test_only_completed_real_adds_count_as_waivers(self):
        path=Path(__file__).resolve().parent.parent/"scripts/refresh_espn.py"
        spec=importlib.util.spec_from_file_location("gazette_fantasy_refresh_for_newspaper",path)
        refresh=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(refresh)
        names={1:"Team One",2:"Team Two"}
        completed={"id":1001,"type":"WAIVER","status":"EXECUTED",
           "scoringPeriodId":12,
           "items":[{"type":"ADD","playerId":123,"toTeamId":1},
                    {"type":"DROP","playerId":456,"toTeamId":1}]}
        pending={"id":1002,"type":"WAIVER","status":"PENDING",
           "scoringPeriodId":12,
           "items":[{"type":"ADD","playerId":456,"toTeamId":1}]}
        free={"id":1003,"type":"FREEAGENT","status":"EXECUTED",
           "scoringPeriodId":12,
           "items":[{"type":"ADD","playerId":789,"toTeamId":2}]}
        def reply(url):
            if "scoringPeriodId=12" in url:
                return {"id":1413446022,"seasonId":2026,
                        "transactions":[completed,completed,pending,free]}
            return {"id":1413446022,"seasonId":2026,"transactions":[]}
        with patch.object(refresh,"get_json",side_effect=reply) as call:
            result=refresh.verified_roster_acquisitions(12,names)
        self.assertEqual(call.call_count,2)
        self.assertEqual(result["status"],"verified")
        self.assertEqual(len(result["teams"]),2)
        self.assertEqual([t["acquisitions"] for t in result["teams"]],[1,1])
        self.assertEqual({t["name"] for t in result["teams"]},{"Team One","Team Two"})
        self.assertNotIn("playerName",json.dumps(result))

if __name__=="__main__":
    unittest.main()
