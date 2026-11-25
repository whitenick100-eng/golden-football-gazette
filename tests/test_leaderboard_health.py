"""Offline checks for Tuesday retry diagnostics, no ESPN API calls."""
import datetime as dt
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("leaderboard_health", ROOT / "scripts/leaderboard_health.py")
import sys
sys.path.insert(0, str(ROOT / "scripts"))
health = importlib.util.module_from_spec(spec)
spec.loader.exec_module(health)


def sample_league(week11_final=True):
    standings = [{"teamId":i, "name":f"Club {i}"} for i in range(1,11)]
    games = []
    for week in (10,11):
        for pair in range(5):
            games.append({
                "week":week,
                "winner":"HOME" if week==10 or week11_final else "UNDECIDED",
                "home":{"teamId":2*pair+1},
                "away":{"teamId":2*pair+2},
            })
    return {
        "leagueId":"1413446022","season":2026,"currentMatchupPeriod":12,
        "standings":standings,"matchups":games,
    }


def sample_leaders(week):
    return {
        "leagueId":1413446022,"season":2026,"week":week,
        "fetchedAt":"2026-11-22T20:00:00+00:00",
        "players":[{
            "playerId":1000+i,"name":f"Player {i}","points":60-i
        } for i in range(5)],
    }


NOW = dt.datetime(2026, 11, 24, 14, 20, tzinfo=dt.timezone.utc)


class LeaderboardHealthTests(unittest.TestCase):
    def test_report_waits_without_inventing_new_week_results(self):
        report = health.assess(sample_league(False), sample_leaders(10), NOW)
        self.assertEqual(report["fullyFinalESPNWeek"],10)
        self.assertEqual(report["state"],"WAITING_FOR_ESPN_FINALS")
        self.assertEqual(report["publishedTopFiveWeek"],10)
        self.assertTrue(report["afterTuesdayCutoff"])

    def test_warns_if_espn_final_week_is_newer_than_published(self):
        report = health.assess(sample_league(True), sample_leaders(10), NOW)
        self.assertEqual(report["fullyFinalESPNWeek"],11)
        self.assertEqual(report["state"],"RETRY_NEEDED")
        self.assertIn("still older",report["explanation"])

    def test_detects_successful_completed_week_rollover(self):
        report = health.assess(sample_league(True), sample_leaders(11), NOW)
        self.assertEqual(report["state"],"VERIFIED_CURRENT_COMPLETED_WEEK")
        self.assertEqual(report["publishedTopFiveWeek"],11)

    def test_missing_or_wrong_league_does_not_claim_current(self):
        report = health.assess({**sample_league(True),"leagueId":"wrong"},sample_leaders(11),NOW)
        self.assertEqual(report["fullyFinalESPNWeek"],None)
        self.assertEqual(report["currentLeagueWeek"],None)
        self.assertNotEqual(report["state"],"VERIFIED_CURRENT_COMPLETED_WEEK")
        bad={**sample_leaders(11),"players":[]}
        report=health.assess(sample_league(True),bad,NOW)
        self.assertEqual(report["state"],"NO_VERIFIED_TOP_FIVE")

    def test_report_preserves_original_source_timestamp(self):
        before=sample_leaders(10)
        original=json.dumps(before,sort_keys=True)
        report=health.assess(sample_league(False),before,NOW)
        self.assertEqual(json.dumps(before,sort_keys=True),original)
        self.assertIn(before["fetchedAt"],health.format_report(report))
        self.assertIn("does **not** certify",health.format_report(report))

    def test_four_hour_schedule_preserves_tuesday_fallback(self):
        content=(ROOT / ".github/workflows/refresh-and-deploy.yml").read_text("utf-8")
        self.assertIn("cron: '17 1,5,9,13,17,21 * * *'",content)
        self.assertIn("cron: '47 15 * * 2'",content)
        self.assertIn("cron: '0 12,13 * * 2'",content)
        self.assertIn("cron: '5 10 * * *'",content)
        self.assertEqual(content.count("cron:"),4)
        self.assertIn("python scripts/leaderboard_health.py",content)
        self.assertLess(content.index("python scripts/refresh_player_leaders.py"),
                        content.index("python scripts/leaderboard_health.py"))

    def test_status_diagnostics_dont_stop_website_deployment(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d)
            league=base/"league.json"
            tops=base/"top-performers.json"
            status=base/"summary.md"
            league.write_text(json.dumps(sample_league(True)))
            tops.write_text(json.dumps(sample_leaders(10)))
            with patch.object(health,"LEAGUE_FILE",league),patch.object(health,"OUT",tops),\
                 patch.dict("os.environ",{"GITHUB_STEP_SUMMARY":str(status)}):
                self.assertEqual(health.main(),0)
            summary=status.read_text("utf-8")
            self.assertIn("RETRY_NEEDED",summary)
            self.assertIn("fantasy week",summary)


if __name__ == "__main__":
    unittest.main()
