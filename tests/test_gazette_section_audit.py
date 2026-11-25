"""Offline daily Gazette section audit regression tests (no network)."""
import copy
import datetime as dt
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("gazette_section_audit",ROOT/"scripts/gazette_section_audit.py")
audit=importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)
NOW=dt.datetime(2026,11,25,11,0,tzinfo=dt.timezone.utc)
STAMP="2026-11-25T10:20:00+00:00"


def fixture():
    teams=[{"teamId":i,"name":f"Team {i}","wins":13-i,"losses":i} for i in range(1,11)]
    games=[{"week":12,"home":{"teamId":i+1,"name":f"Team {i+1}","points":110.0},
            "away":{"teamId":i+2,"name":f"Team {i+2}","points":105.0},
            "winner":"HOME"} for i in (0,2,4,6,8)]
    league={"leagueId":"1413446022","season":2026,"fetchedAt":STAMP,
        "currentMatchupPeriod":12,"standings":teams,"matchups":games}
    weekly={"status":"available","generatedAt":STAMP,
        "sources":{"espnLeague":STAMP},
        "coverage":[{"tag":"Fantasy League","headline":"Team 1 leads the league",
                     "body":"Team 1 leads verified standings.","source":"ESPN fantasy league standings"}],
        "playoffs":{"status":"available","type":"provisional",
                    "contenders":teams[:4],"outsideCurrentField":teams[4:],
                    "championshipPairings":[],"consolationPairings":[]}}
    nfl={"season":2026,"fetchedAt":STAMP,"week":12,"games":[
        {"id":"game-1","completed":False,"home":{"name":"Home"},"away":{"name":"Away"},"date":STAMP}]}
    injuries={"filter":"first-string-status-watch","fetchedAt":STAMP,
        "outCount":1,"questionableCount":0,"doubtfulCount":0,"reserveCount":0,
        "coverageComplete":True,"teams":[{"name":"NFL Team","players":[
            {"name":"QB 1","reportedStatus":"Out","outType":"out"}]}]}
    wire={"status":"available","filter":"verified-key-players-only",
        "fetchedAt":STAMP,"total":1,"trades":0,"releases":1,
        "moves":[{"playerName":"QB 1","type":"Waived","date":"2026-11-25"}]}
    pages={"pageOne":{"status":"verified","standings":teams,
        "publishedAt":STAMP,"sourceAt":STAMP,"leagueId":1413446022,"headline":"Verified"},
        "pageTwo":{"status":"available","publishedAt":STAMP,
            "editionDateEastern":"2026-11-25","fictionNotice":"All fan quotes are invented",
            "writer":"Adrian Mercer","interviews":[{"fan":"Imaginary","fictional":True}]}}
    return {"data/league.json":league,"data/weekly-features.json":weekly,
        "data/nfl-week.json":nfl,"data/nfl-injuries.json":injuries,
        "data/nfl-transactions.json":wire,"data/gazette-pages.json":pages}


class DailyGazetteAuditTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        (self.root/"data").mkdir()
        (self.root/"editorial").mkdir()
        for path,data in fixture().items():
            (self.root/path).write_text(json.dumps(data),encoding="utf-8")
        (self.root/"index.html").write_text("<section id='headlines'>Archived</section>")

    def test_all_requested_sections_have_a_specific_verification_state(self):
        report=audit.build(now=NOW,root=self.root)
        self.assertEqual(list(report["sections"]),list(audit.KEYS))
        self.assertEqual(len(report["sections"]),11)
        self.assertEqual(report["sections"]["lead_story"]["status"],"VERIFIED_BASELINE")
        self.assertEqual(report["sections"]["espn_matchups"]["status"],"VERIFIED_BASELINE")
        self.assertEqual(report["sections"]["page_one"]["status"],"VERIFIED_BASELINE")
        self.assertEqual(report["sections"]["page_two"]["status"],"VERIFIED_BASELINE")
        self.assertEqual(report["sections"]["from_editor"]["status"],"APPROVAL_REQUIRED")
        self.assertEqual(report["sections"]["key_starters_out"]["status"],"VERIFIED_BASELINE")
        self.assertEqual(report["sections"]["waivers"]["status"],"VERIFIED_BASELINE")
        self.assertIn("does not prove Pages deployment",report["notes"])

    def test_same_espn_content_is_not_mislabeled_as_a_new_update(self):
        previous=audit.build(now=NOW,root=self.root)
        after=audit.build(now=NOW+dt.timedelta(minutes=10),root=self.root,prior=previous)
        self.assertEqual(after["sections"]["espn_matchups"]["status"],"UNCHANGED_VERIFIED")
        self.assertEqual(after["sections"]["football_desk"]["status"],"UNCHANGED_VERIFIED")
        self.assertEqual(after["sections"]["page_one"]["status"],"UNCHANGED_VERIFIED")
        self.assertEqual(after["sections"]["page_two"]["status"],"UNCHANGED_VERIFIED")

    def test_changes_require_new_espn_source_timestamp(self):
        previous=audit.build(now=NOW,root=self.root)
        path=self.root/"data/nfl-week.json"
        nfl=json.loads(path.read_text())
        nfl["games"][0]["completed"]=True
        nfl["fetchedAt"]="2026-11-25T10:40:00+00:00"
        path.write_text(json.dumps(nfl))
        after=audit.build(now=NOW,root=self.root,prior=previous)
        self.assertEqual(after["sections"]["nfl_review_preview"]["status"],"UPDATED")
        self.assertEqual(after["sections"]["espn_matchups"]["status"],"UNCHANGED_VERIFIED")
        nfl["games"][0]["completed"]=False
        path.write_text(json.dumps(nfl))
        # A source timestamp that does not advance must never earn UPDATED.
        nfl["fetchedAt"]=STAMP
        path.write_text(json.dumps(nfl))
        changed=audit.build(now=NOW,root=self.root,prior=previous)
        self.assertEqual(changed["sections"]["nfl_review_preview"]["status"],"UNCHANGED_VERIFIED")
        nfl["games"][0]["completed"]=True
        path.write_text(json.dumps(nfl))
        changed=audit.build(now=NOW,root=self.root,prior=previous)
        self.assertEqual(changed["sections"]["nfl_review_preview"]["status"],"CHANGED_WITHOUT_NEW_SOURCE")

    def test_archives_and_editorial_require_approval(self):
        path=self.root/"data/weekly-features.json"
        weekly=json.loads(path.read_text())
        weekly["coverage"]=[]
        path.write_text(json.dumps(weekly))
        report=audit.build(now=NOW,root=self.root)
        self.assertEqual(report["sections"]["lead_story"]["status"],"ARCHIVE_FALLBACK")
        self.assertEqual(report["sections"]["from_editor"]["status"],"APPROVAL_REQUIRED")

    def test_stale_sources_are_reported_not_hidden(self):
        nfl=self.root/"data/nfl-week.json"
        content=json.loads(nfl.read_text())
        content["fetchedAt"]="2026-11-15T10:20:00+00:00"
        nfl.write_text(json.dumps(content))
        report=audit.build(now=NOW,root=self.root)
        self.assertEqual(report["sections"]["nfl_review_preview"]["status"],"STALE")

    def test_early_morning_schedule_and_unchanged_theme(self):
        workflow=(ROOT/".github/workflows/refresh-and-deploy.yml").read_text()
        self.assertIn("cron: '5 10 * * *'",workflow)
        self.assertIn("python scripts/gazette_section_audit.py",workflow)
        self.assertLess(workflow.index("python scripts/build_newspaper_pages.py"),
                        workflow.index("python scripts/gazette_section_audit.py"))
        html=(ROOT/"index.html").read_text()
        self.assertIn("Historical Week 11 archive",html)
        self.assertIn('src="assets/lead-story-live.js"',html)
        for image in ("assets/stadium-nfl-unbranded.webp",
                      "assets/turkey-left.webp","assets/turkey-right.webp"):
            self.assertIn(image,html)
        js=(ROOT/"assets/lead-story-live.js").read_text()
        self.assertIn("headline.textContent",js)
        self.assertIn("body.textContent",js)
        self.assertNotIn(".innerHTML",js)


if __name__=="__main__":
    unittest.main()
