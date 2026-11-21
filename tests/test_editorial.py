"""Offline tests for the daily writer. No credentials or network requests."""
import datetime as dt
import importlib.util
import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

MODULE = Path(__file__).resolve().parent.parent / "scripts/draft_article.py"
spec = importlib.util.spec_from_file_location("gazette_editor", MODULE)
editor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(editor)


class DailyEditorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.original_root = editor.ROOT
        editor.ROOT = Path(self.tmp.name)
        self.addCleanup(setattr, editor, "ROOT", self.original_root)
        (editor.ROOT / "data").mkdir()
        self.now = dt.datetime.now(dt.timezone.utc)
        self.teams = [
            {"teamId": i, "name": f"ESPN Team {i}", "wins": 5,
             "losses": 5, "ties": 0, "pointsFor": 1000} for i in range(1, 11)
        ]

    def write_snapshots(self, age=0):
        stamp = (self.now - dt.timedelta(hours=age)).isoformat()
        league = {"leagueId":"1413446022","season":2026,"fetchedAt":stamp,
                  "currentMatchupPeriod":11,"standings":self.teams,
                  "matchups":[{"week":11,"away":{"name":"ESPN Team 1"},
                               "home":{"name":"ESPN Team 2"},"winner":"UNDECIDED"}]}
        nfl = {"season":2026,"week":11,"fetchedAt":stamp,
               "games":[{"id":"football-game-1",
                        "date":(self.now+dt.timedelta(days=1)).isoformat(),
                        "home":{"name":"Home NFL Club"},"away":{"name":"Away NFL Club"},
                        "venue":"Verified Test Stadium","completed":False}]}
        for file, payload in (("league.json", league), ("nfl-week.json", nfl)):
            (editor.ROOT / "data" / file).write_text(json.dumps(payload), encoding="utf-8")

    def test_fresh_data_is_accepted(self):
        self.write_snapshots()
        sources = editor.verified_sources(self.now)
        self.assertEqual(set(sources), {"fantasy_league","nfl_week"})
        self.assertEqual(sources["fantasy_league"]["matchups"][0]["week"], 11)

    def test_stale_snapshots_are_rejected(self):
        self.write_snapshots(age=96)
        self.assertFalse(editor.verified_sources(self.now))

    def test_unsupported_league_is_rejected(self):
        self.write_snapshots()
        path = editor.ROOT / "data" / "league.json"
        data = json.loads(path.read_text())
        data["leagueId"] = "wrong"
        path.write_text(json.dumps(data))
        sources = editor.verified_sources(self.now)
        self.assertNotIn("fantasy_league",sources)
        self.assertIn("nfl_week",sources)

    def test_auto_article_types(self):
        # Tuesday recap, Sunday previews, Monday brief
        self.assertEqual(editor.choose_type("auto",dt.datetime(2026,11,24,tzinfo=editor.LOCAL)),"weekly-recap")
        self.assertEqual(editor.choose_type("auto",dt.datetime(2026,11,22,tzinfo=editor.LOCAL)),"week-preview")
        self.assertEqual(editor.choose_type("auto",dt.datetime(2026,11,23,tzinfo=editor.LOCAL)),"daily-brief")

    def test_fallback_contains_only_source_data_and_labels(self):
        self.write_snapshots()
        sources = editor.verified_sources(self.now)
        text = editor.verified_bulletin(sources,"week-preview",self.now.astimezone(editor.LOCAL))
        self.assertIn("ESPN Team 1", text)
        self.assertIn("Away NFL Club", text)
        self.assertIn("Verified Test Stadium",text)
        self.assertIn("not an AI-generated article",text)
        self.assertNotIn("top five performers",text.lower())

    def test_quota_error_falls_back_without_retries(self):
        err = urllib.error.HTTPError(
            "https://api.openai.com/v1/chat/completions",429,"Too Many",
            {},io.BytesIO(json.dumps({"error":{"code":"insufficient_quota","type":"insufficient_quota"}}).encode()))
        with patch.object(editor.urllib.request,"urlopen",side_effect=err) as req:
            with self.assertRaises(editor.APIUnavailable) as cm:
                editor.request_ai({"model":"test"}, "test-key",sleeper=lambda _: None)
        self.assertIn("quota",str(cm.exception).lower())
        self.assertEqual(req.call_count,1)

    def test_temporary_rate_limit_retries(self):
        err = urllib.error.HTTPError(
            "https://api.openai.com/v1/chat/completions",429,"Too Many",
            {"Retry-After":"1"},io.BytesIO(json.dumps({"error":{"code":"rate_limit_exceeded","type":"rate_limit_error"}}).encode()))
        article = "# Headline\n" + "Confirmed fact. " * 25
        ok = io.BytesIO(json.dumps({"choices":[{"finish_reason":"stop",
                           "message":{"content":article}}]}).encode())
        with patch.object(editor.urllib.request,"urlopen",side_effect=[err,ok]) as req:
            answer = editor.request_ai({"model":"test"},"test-key",sleeper=lambda _: None)
        self.assertEqual(answer,article.strip())
        self.assertEqual(req.call_count,2)

    def test_draft_is_review_only(self):
        self.write_snapshots()
        sources=editor.verified_sources(self.now)
        article=editor.verified_bulletin(sources,"daily-brief",self.now.astimezone(editor.LOCAL))
        editor.write_draft(article,sources,"verified-data-fallback-owner-review",
                           "daily-brief",self.now.astimezone(editor.LOCAL))
        d=json.loads((editor.ROOT/"editorial"/"latest.json").read_text())
        self.assertEqual(d["editorialStatus"],"owner-approved-on-merge")
        self.assertEqual(d["generationMethod"],"verified-data-fallback-owner-review")
        self.assertTrue(list((editor.ROOT/"editorial").glob("*-DRAFT.md")))


if __name__=="__main__":
    unittest.main()
