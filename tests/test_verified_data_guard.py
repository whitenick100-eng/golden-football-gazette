"""Offline tests for integrity, recovery, archives, and fail-closed health checks."""
import datetime as dt
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("verified_data_guard", ROOT/"scripts/verified_data_guard.py")
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)
UTC = dt.timezone.utc
NOW = dt.datetime(2026, 11, 22, 19, 0, tzinfo=UTC)


def stamp(now=NOW):
    return now.isoformat()


def league(now=NOW, week=11):
    teams = [{"teamId":i,"name":f"Fantasy {i}","wins":6,"losses":5} for i in range(1,11)]
    games = [{"id":week*100+i,"week":week,"winner":"UNDECIDED",
              "home":{"teamId":2*i+1},"away":{"teamId":2*i+2}} for i in range(5)]
    return {"leagueId":"1413446022","season":2026,"fetchedAt":stamp(now),
            "currentMatchupPeriod":week,"standings":teams,"matchups":games}


def nfl(now=NOW, week=11):
    return {"season":2026,"week":week,"fetchedAt":stamp(now),
            "games":[{"id":"401761001","home":{"abbr":"DET"},
                      "away":{"abbr":"CHI"},"statusType":"pre"}]}


class DataGuardTests(unittest.TestCase):
    def test_validation_requires_correct_league_and_ten_teams(self):
        self.assertTrue(guard.valid("league.json",league(),NOW)[0])
        wrong = dict(league(),leagueId="0000000000")
        self.assertFalse(guard.valid("league.json",wrong,NOW)[0])
        incomplete = dict(league(),standings=league()["standings"][:9])
        self.assertFalse(guard.valid("league.json",incomplete,NOW)[0])
        altered = dict(league(),fetchedAt=stamp(NOW+dt.timedelta(days=3)))
        self.assertFalse(guard.valid("league.json",altered,NOW)[0])

    def test_recovery_never_accepts_an_older_scoring_week(self):
        previous = league(NOW-dt.timedelta(hours=1),week=11)
        newer_time_but_old_week = league(NOW,week=10)
        chosen, state, reason = guard.choose("league.json",newer_time_but_old_week,previous,NOW)
        self.assertEqual(state,"RECOVERED")
        self.assertEqual(chosen["currentMatchupPeriod"],11)
        self.assertIn("regressed",reason)

    def test_invalid_scoreboard_recovers_original_timestamp(self):
        old = nfl(NOW-dt.timedelta(hours=2))
        chosen, state, reason = guard.choose("nfl-week.json",{"status":"unavailable"},old,NOW)
        self.assertEqual(state,"RECOVERED")
        self.assertEqual(chosen["fetchedAt"],old["fetchedAt"])
        self.assertIn("unavailable",reason)

    def test_preload_uses_validated_remote_backup_only(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            def mock_fetch(name):
                if name=="league.json": return league(NOW-dt.timedelta(hours=3))
                if name=="nfl-week.json": return {"season":2025,"games":[]}
                raise OSError("not published")
            with patch.object(guard,"DATA",root/"data"),patch.object(guard,"PRIOR",root/"prior"):
                guard.preload(NOW,mock_fetch)
                self.assertTrue((root/"data/league.json").exists())
                self.assertTrue((root/"prior/league.json").exists())
                self.assertFalse((root/"data/nfl-week.json").exists())

    def test_only_essential_feeds_block_deployment(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            with patch.object(guard,"DATA",root/"data"),\
                 patch.object(guard,"PRIOR",root/"prior"),\
                 patch.object(guard,"BACKUP",root/"backup"),\
                 patch.object(guard,"REPORT",root/"backup/health-report.md"):
                guard.store_json(guard.DATA/"league.json",league())
                guard.store_json(guard.DATA/"nfl-week.json",nfl())
                self.assertEqual(guard.finalize(NOW),0)
                self.assertTrue((root/"backup/health-report.md").is_file())
                self.assertIn("NFL starter injury report", (root/"backup/health-report.md").read_text())
                self.assertIn("league.json",json.loads((root/"backup/manifest.json").read_text())["files"])

    def test_stale_essential_feed_blocks_deployment_and_creates_report(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            with patch.object(guard,"DATA",root/"data"),\
                 patch.object(guard,"PRIOR",root/"prior"),\
                 patch.object(guard,"BACKUP",root/"backup"),\
                 patch.object(guard,"REPORT",root/"backup/health-report.md"):
                guard.store_json(guard.DATA/"league.json",league(NOW-dt.timedelta(hours=62)))
                guard.store_json(guard.DATA/"nfl-week.json",nfl())
                self.assertEqual(guard.finalize(NOW),1)
                text=(root/"backup/health-report.md").read_text()
                self.assertIn("CRITICAL",text)
                self.assertIn("FAILED",text)

    def test_artifact_recovery_validates_hash_and_league(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            bundle=root/"backup"
            data={"league.json":league(),"nfl-week.json":nfl()}
            with patch.object(guard,"BACKUP",bundle),patch.object(guard,"REPORT",bundle/"health-report.md"):
                guard.archive(data,NOW,"# Verified backup")
            target=root/"restored"
            with patch.object(guard,"DATA",target):
                guard.restore_artifact(bundle,NOW)
                self.assertEqual(json.loads((target/"league.json").read_text())["currentMatchupPeriod"],11)
                original=(bundle/"data/nfl-week.json").read_text()
                (bundle/"data/nfl-week.json").write_text(original.replace('"week": 11','"week": 7'))
                with self.assertRaisesRegex(ValueError,"checksum mismatch"):
                    guard.restore_artifact(bundle,NOW)

    def test_archive_omits_unverified_documents(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            with patch.object(guard,"BACKUP",root),patch.object(guard,"REPORT",root/"health-report.md"):
                guard.archive({"league.json":league(),"nfl-week.json":{"status":"unavailable"}},NOW,"QA")
            doc=json.loads((root/"manifest.json").read_text())
            self.assertIn("league.json",doc["files"])
            self.assertNotIn("nfl-week.json",doc["files"])


if __name__ == "__main__":
    unittest.main()
