"""Offline regression tests for weekly ESPN brackets, scores and daily factual coverage."""
import datetime as dt
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]

def module(filename,name):
    spec=importlib.util.spec_from_file_location(name,ROOT/"scripts"/filename)
    obj=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj

stars=module("refresh_player_leaders.py","stars")
features=module("build_weekly_features.py","features")

def league():
    teams=[
        {"teamId":i,"name":f"Fantasy Club {i}","wins":11-i,
         "losses":i-1,"pointsFor":1000+10*(11-i),"logo":None}
        for i in range(1,11)
    ]
    games=[]
    for week in (10,11):
        for k in range(5):
            home=teams[2*k];away=teams[2*k+1]
            games.append({
                "week":week,"id":week*10+k,
                "home":{"teamId":home["teamId"],"name":home["name"],"points":100.25},
                "away":{"teamId":away["teamId"],"name":away["name"],"points":99.0},
                "winner":"HOME" if week==10 else "UNDECIDED",
                "playoffTierType":"NONE",
            })
    return {"leagueId":"1413446022","season":2026,
        "fetchedAt":dt.datetime.now(dt.timezone.utc).isoformat(),
        "currentMatchupPeriod":11,
        "standings":teams,
        "playoffSettings":{"playoffTeamCount":4,"regularSeasonMatchupPeriods":14,
                           "playoffSeedingRule":"H2H_RECORD"},
        "matchups":games}

def box():
    games=[]
    for i in range(5):
        def side(team_id,score,athlete_id):
            return {"teamId":team_id,
                    "rosterForCurrentScoringPeriod":{"entries":[
                        {"playerId":athlete_id,
                         "playerPoolEntry":{
                             "appliedStatTotal":score,
                             "player":{"id":athlete_id,"fullName":f"NFL Athlete {athlete_id}",
                                       "defaultPositionId":1,"proTeamId":3}}},
                        {"playerId":9000+team_id,
                         "playerPoolEntry":{"appliedStatTotal":2,
                                            "player":{"id":9000+team_id,
                                                      "fullName":"Test Bench "+str(team_id),
                                                      "defaultPositionId":2}}},
                    ]}}
        games.append({"matchupPeriodId":10,"home":side(2*i+1,42-i,200+i),
                     "away":side(2*i+2,38-i,300+i)})
    return {"id":1413446022,"seasonId":2026,"schedule":games}

class PlayoffCoverageTests(unittest.TestCase):
    def test_completed_week_is_previous_week_not_in_progress_week(self):
        self.assertEqual(stars.completed_week(league()),10)

    def test_top_five_only_real_scored_rostered_players(self):
        data=stars.parse_boxscore(box(),league(),10)
        self.assertEqual(data["week"],10)
        self.assertEqual(len(data["players"]),5)
        self.assertEqual(data["players"][0]["name"],"NFL Athlete 200")
        self.assertEqual(data["players"][0]["points"],42)
        self.assertEqual(data["eligiblePlayersWithScores"],20)
        self.assertTrue(data["players"][0]["headshotUrl"].endswith("/200.png"))

    def test_projection_stats_not_used_as_actual(self):
        e={"playerPoolEntry":{"stats":[
            {"scoringPeriodId":10,"seasonId":2026,"statSourceId":1,"appliedTotal":50},
            {"scoringPeriodId":10,"seasonId":2026,"statSourceId":0,"appliedTotal":11.3}]}}
        self.assertEqual(stars.score(e,10),11.3)

    def test_no_finished_week_means_no_leaderboard(self):
        sample=league()
        for g in sample["matchups"]:g["winner"]="UNDECIDED"
        self.assertIsNone(stars.completed_week(sample))

    def test_provisional_bracket_has_separate_championship_consolation(self):
        b=features.playoff_picture(league())
        self.assertEqual(b["playoffTeamCount"],4)
        self.assertTrue(b["formatVerifiedByESPN"])
        self.assertEqual(len(b["contenders"]),4)
        self.assertEqual(len(b["outsideCurrentField"]),6)
        self.assertEqual(b["championshipPairings"][0]["homeSeed"],1)
        self.assertEqual(b["championshipPairings"][0]["awaySeed"],4)
        self.assertIn("NOT necessarily eliminated",b["caveat"])

    def test_actual_espn_winners_bracket_replaces_projections(self):
        d=league()
        g=d["matchups"][-1]
        g["playoffTierType"]="WINNERS_BRACKET"
        b=features.playoff_picture(d)
        self.assertEqual(b["type"],"espn-listed")
        self.assertEqual(b["championshipPairings"][0]["home"],g["home"]["name"])
        self.assertNotIn("homeSeed",b["championshipPairings"][0])

    def test_daily_coverage_only_from_recent_source_snapshots(self):
        now=dt.datetime.now(dt.timezone.utc)
        with tempfile.TemporaryDirectory() as path:
            root=Path(path)
            (root/"data").mkdir()
            data=league()
            (root/"data/league.json").write_text(json.dumps(data))
            with patch.object(features,"ROOT",root):
                result=features.generate(now)
                self.assertEqual(result["status"],"available")
                self.assertEqual(result["playoffs"]["status"],"available")
                self.assertTrue(all("source" in x and x["source"] for x in result["coverage"]))
                self.assertIn("provisional",result["playoffs"]["caveat"].lower())
                data["fetchedAt"]=(now-dt.timedelta(days=5)).isoformat()
                (root/"data/league.json").write_text(json.dumps(data))
                stale=features.generate(now)
                self.assertEqual(stale["status"],"unavailable")
                self.assertEqual(stale["playoffs"]["status"],"unavailable")

if __name__=="__main__":
    unittest.main()
