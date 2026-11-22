"""Curated ESPN NFL key-player roster wire: strict player verification tests."""
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
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

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

KEY_INDEX={
    "sample receiver":{"name":"Sample Receiver","position":"WR",
      "importanceBasis":"ESPN NFL first-string depth chart"},
    "sample passer":{"name":"Sample Passer","position":"QB",
      "importanceBasis":"Rostered in Gridiron Giggles ESPN fantasy league"},
}
COVERAGE={"nflDepthChartsVerified":32,"nflDepthChartsExpected":32,
          "leagueOwnedPlayersVerified":135,"coverageComplete":True}

def fixture_report(now,content):
    with tempfile.TemporaryDirectory() as path:
        root=Path(path)
        (root/"data").mkdir()
        (root/"data/nfl-transactions.json").write_text(json.dumps({
            "status":"available","fetchedAt":now.isoformat(), **content
        }),encoding="utf-8")
        with patch.object(writer,"ROOT",root):
            return writer.generate(now)

class TransactionTests(unittest.TestCase):
    def test_only_literal_actions_qualify(self):
        self.assertEqual(feed.category("Released QB Example."),"Released")
        self.assertEqual(feed.category("Waived OT Example."),"Waived")
        self.assertEqual(feed.category("Traded RB Example."),"Trade")
        self.assertEqual(feed.category("Acquired via trade RB Example."),"Trade")
        for description in ("Signed QB Example.","Claims Example off waivers.",
                            "Practice squad del QB Example.",
                            "May trade QB Example rumored"):
            self.assertIsNone(feed.category(description),description)

    def test_multiple_players_separated_and_verbatim(self):
        self.assertEqual(feed.actions("Released QB John Doe. Released LS Jane Doe."),
            [("Released","Released QB John Doe."),("Released","Released LS Jane Doe.")])
        self.assertEqual(len(feed.actions(sample()["transactions"][0]["description"])),3)

    def test_normalize_espn_actions_before_important_player_filter(self):
        got,oldest=feed.normalize(sample(),dt.date(2026,11,13),dt.date(2026,11,20))
        self.assertEqual(oldest,dt.date(2026,11,20))
        self.assertEqual(len(got),4)
        self.assertEqual({x["type"] for x in got},{"Trade","Released","Waived"})
        self.assertEqual(got[0]["team"],"Tennessee Titans")
        self.assertEqual(got[0]["date"],"2026-11-20")
        self.assertTrue(got[0]["description"].startswith("Traded WR"))

    def test_curated_feed_excludes_backup_and_deduplicates_two_team_trade(self):
        now=dt.datetime(2026,11,21,2,30,tzinfo=dt.timezone.utc)
        called=[]
        def fetch(page=1,limit=100):
            called.append(page)
            return sample("2026-11-20" if page==1 else "2026-11-10",previous=page==2)
        data=feed.build(now=now,fetcher=fetch,
                        key_provider=lambda:(KEY_INDEX,COVERAGE))
        self.assertEqual(called,[1,2])
        self.assertTrue(data["keyOnly"])
        self.assertEqual(data["filter"],"verified-key-players-only")
        self.assertEqual(data["total"],2)
        self.assertEqual(data["allESPNMovesChecked"],4)
        self.assertEqual(data["trades"],1)
        self.assertEqual(data["releases"],1)
        self.assertTrue(data["coverageComplete"])
        self.assertNotIn("Sample Defender",str(data["moves"]))
        receiver=next(x for x in data["moves"] if x["playerName"]=="Sample Receiver")
        self.assertEqual(len(receiver["mentionedTeams"]),2)
        self.assertEqual(receiver["position"],"WR")

    def test_matching_entire_player_name_never_surname_or_partial_match(self):
        moves=[{"date":"2026-11-20","teamAbbr":"TEN","team":"Tennessee Titans",
                "type":"Released","description":"Released QB Johnny Smith."}]
        key={"john smith":{"name":"John Smith","position":"QB",
                           "importanceBasis":"ESPN NFL first-string depth chart"}}
        self.assertEqual(feed.named_key_moves(moves,key),[])
        moves[0]["description"]="Released QB John Smith."
        self.assertEqual(len(feed.named_key_moves(moves,key)),1)

    def test_first_string_depth_chart_ignores_second_string_and_returners(self):
        people={
           "depthchart":[
             {"positions":{"qb":{"athletes":[{"displayName":"Star Quarterback"},
                                                {"displayName":"Reserve Quarterback"}]},
                           "rb":{"athletes":[{"displayName":"First Runningback"}]},
                           "wr1":{"athletes":[{"displayName":"Lead Receiver"}]},
                           "te":{"athletes":[{"displayName":"Starting Tightend"}]}}},
             {"positions":{"cb":{"athletes":[{"displayName":"Starting Cornerback"},
                                                {"displayName":"Backup Cornerback"}]},
                           "fs":{"athletes":[{"displayName":"Starting Safety"}]},
                           "de":{"athletes":[{"displayName":"Defensive End"}]}}},
             {"positions":{"pk":{"athletes":[{"displayName":"Starting Kicker"}]},
                           "kr":{"athletes":[{"displayName":"Return Specialist"}]}}},
           ]
        }
        result=feed.depth_starters(people)
        self.assertIn("star quarterback",result)
        self.assertIn("starting cornerback",result)
        self.assertIn("starting kicker",result)
        self.assertNotIn("reserve quarterback",result)
        self.assertNotIn("backup cornerback",result)
        self.assertNotIn("return specialist",result)

    def test_fantasy_roster_supplement_labels_ownership_not_starter_claim(self):
        payload={"id":1413446022,"seasonId":2026,"teams":[
            {"roster":{"entries":[{"playerPoolEntry":{"player":{
                "fullName":"Sample Passer","defaultPositionId":1}}},
                {"playerPoolEntry":{"player":{
                "fullName":"The Defense","defaultPositionId":16}}}]}}
            for _ in range(10)
        ]}
        result=feed.fantasy_rostered(payload)
        self.assertIn("sample passer",result)
        self.assertNotIn("the defense",result)
        self.assertEqual(result["sample passer"]["importanceBasis"],
                         "Rostered in Gridiron Giggles ESPN fantasy league")

    def test_newsroom_mentions_only_verified_important_players(self):
        now=dt.datetime.now(dt.timezone.utc)
        moves=[
            {"date":"2026-11-20","team":"Tennessee Titans",
             "type":"Trade","playerName":"Sample Receiver","position":"WR",
             "importanceBasis":"ESPN NFL first-string depth chart",
             "description":"Traded WR Sample Receiver."},
            {"date":"2026-11-20","team":"Atlanta Falcons",
             "type":"Released","playerName":"Sample Passer","position":"QB",
             "importanceBasis":"Rostered in Gridiron Giggles ESPN fantasy league",
             "description":"Released QB Sample Passer."},
        ]
        report=fixture_report(now,{"keyOnly":True,"filter":"verified-key-players-only","moves":moves})
        self.assertEqual(report["status"],"available")
        self.assertIn("NFL Trades",{x["tag"] for x in report["coverage"]})
        self.assertIn("NFL Releases",{x["tag"] for x in report["coverage"]})
        self.assertIn("Sample Receiver",str(report["coverage"]))

    def test_old_whole_nfl_snapshots_do_not_generate_major_news(self):
        now=dt.datetime.now(dt.timezone.utc)
        report=fixture_report(now,{"moves":[{"team":"Team","type":"Waived",
                                      "description":"Waived reserve LB Unknown Person."}]})
        self.assertFalse(any(x["tag"] in ("NFL Trades","NFL Releases")
                             for x in report["coverage"]))

    def test_no_significant_transactions_is_valid_empty(self):
        move=[{"date":"2026-11-20","team":"Tennessee Titans",
               "teamAbbr":"TEN","type":"Waived",
               "description":"Waived LB Reserve Defender."}]
        self.assertEqual(feed.named_key_moves(move,KEY_INDEX),[])

    def test_no_key_sources_means_no_unfiltered_fallback(self):
        with self.assertRaises(ValueError):
            feed.build(now=dt.datetime(2026,11,21,2,30,tzinfo=dt.timezone.utc),
                       fetcher=lambda page=1,limit=100:sample(),
                       key_provider=lambda: ({},COVERAGE))

    def test_old_feed_preserved_on_unavailable_espn(self):
        with tempfile.TemporaryDirectory() as path:
            file=Path(path)/"nfl-transactions.json"
            file.write_text(json.dumps({
                "fetchedAt":"2026-11-15T00:00:00Z","status":"available","keyOnly":True
            }))
            with patch.object(feed,"OUT",file),patch.object(feed,"build",side_effect=OSError("offline")):
                feed.main()
            self.assertEqual(json.loads(file.read_text())["fetchedAt"],"2026-11-15T00:00:00Z")

if __name__=="__main__":
    unittest.main()
