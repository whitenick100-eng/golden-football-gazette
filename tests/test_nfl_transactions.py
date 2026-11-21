"""Offline coverage for ESPN's verified NFL trade and release wire."""
import datetime as dt
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
def load(filename,name):
    spec=importlib.util.spec_from_file_location(name,ROOT/"scripts"/filename)
    obj=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj

feed=load("refresh_nfl_transactions.py","tradefeed")
writer=load("build_weekly_features.py","dailywriter")

def sample(date="2026-11-20",previous=False):
    return {
      "count":25,"pageIndex":2 if previous else 1,"pageCount":2,
      "transactions":[
        {"date":date+"T08:00Z",
         "team":{"id":"10","displayName":"Tennessee Titans","abbreviation":"TEN",
                 "logos":[{"href":"https://a.espncdn.com/i/teamlogos/nfl/500/ten.png"}]},
         "description":"Traded WR Sample Receiver to the Falcons. Released QB Sample Passer. Waived LB Sample Defender."},
        {"date":date+"T08:00Z",
         "team":{"id":"10","displayName":"Tennessee Titans","abbreviation":"TEN"},
         "description":"Signed WR New Addition. Added S Placeholder to practice squad."},
        {"date":date+"T08:00Z",
         "team":{"id":"15","displayName":"Atlanta Falcons","abbreviation":"ATL"},
         "description":"Acquired via trade WR Sample Receiver. Claimed S Placeholder off waivers."},
      ],
    }

class TransactionTests(unittest.TestCase):
    def test_only_literal_actions_qualify(self):
        self.assertEqual(feed.category("Released QB Example."),"Released")
        self.assertEqual(feed.category("Waived OT Example."),"Waived")
        self.assertEqual(feed.category("Traded RB Example."),"Trade")
        self.assertEqual(feed.category("Acquired via trade RB Example."),"Trade")
        for text in ("Signed QB Example.","Claims Example off waivers.",
                     "Practice squad del QB Example.","May trade QB Example rumored"):
            self.assertIsNone(feed.category(text),text)

    def test_multiple_named_players_separated_and_preserved(self):
        self.assertEqual(feed.actions("Released QB John Doe. Released LS Jane Doe."),
            [("Released","Released QB John Doe."),("Released","Released LS Jane Doe.")])
        self.assertEqual(len(feed.actions(sample()["transactions"][0]["description"])),3)

    def test_normalize_team_date_and_exact_action(self):
        got,oldest=feed.normalize(sample(),dt.date(2026,11,13),dt.date(2026,11,20))
        self.assertEqual(oldest,dt.date(2026,11,20))
        self.assertEqual(len(got),4)
        self.assertEqual({x["type"] for x in got},{"Trade","Released","Waived"})
        self.assertEqual(got[0]["team"],"Tennessee Titans")
        self.assertEqual(got[0]["date"],"2026-11-20")
        self.assertTrue(got[0]["description"].startswith("Traded WR"))

    def test_build_window_dedupe_and_source_completeness(self):
        now=dt.datetime(2026,11,21,2,30,tzinfo=dt.timezone.utc) # 9:30 PM EST Nov 20
        called=[]
        def f(page=1,limit=100):
            called.append((page,limit))
            return sample("2026-11-20" if page==1 else "2026-11-10",previous=(page==2))
        d=feed.build(now=now,fetcher=f)
        self.assertEqual(d["windowEnd"],"2026-11-20")
        self.assertTrue(d["coverageComplete"])
        self.assertEqual(d["trades"],2)
        self.assertEqual(d["releases"],2)
        self.assertEqual(d["total"],4)
        self.assertEqual(len(called),2)

    def test_daily_coverage_has_trade_and_release_cards_without_inference(self):
        now=dt.datetime.now(dt.timezone.utc)
        now_e=now.astimezone(feed.ZoneInfo("America/New_York")).date().isoformat()
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/"data").mkdir()
            moves=[{"date":now_e,"team":"Tennessee Titans","teamAbbr":"TEN",
                    "type":"Trade","description":"Traded WR Sample Receiver to Falcons."},
                   {"date":now_e,"team":"Atlanta Falcons","teamAbbr":"ATL",
                    "type":"Released","description":"Released LB Sample Tackler."}]
            (root/"data/nfl-transactions.json").write_text(json.dumps({
                "status":"available","fetchedAt":now.isoformat(),"moves":moves,
                "source":"ESPN NFL transactions"}))
            with patch.object(writer,"ROOT",root):
                result=writer.generate(now)
            self.assertEqual(result["status"],"available")
            cats={x["tag"] for x in result["coverage"]}
            self.assertIn("NFL Trades",cats)
            self.assertIn("NFL Releases",cats)
            self.assertIn("Sample Receiver",str(result["coverage"]))

    def test_old_feed_unavailable_retain_original_verification(self):
        with tempfile.TemporaryDirectory() as d:
            file=Path(d)/"nfl-transactions.json"
            file.write_text(json.dumps({"fetchedAt":"2026-11-15T00:00:00Z","status":"available"}))
            with patch.object(feed,"OUT",file),patch.object(feed,"build",side_effect=OSError("offline")):
                feed.main()
            self.assertEqual(json.loads(file.read_text())["fetchedAt"],"2026-11-15T00:00:00Z")

if __name__=="__main__":
    unittest.main()
