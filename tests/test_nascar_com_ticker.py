"""Offline regression tests for official NASCAR.com-only ticker ingestion."""
import datetime as dt
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("nascar_official",ROOT/"scripts/refresh_nascar.py")
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
NOW=dt.datetime(2026,11,25,16,0,tzinfo=dt.timezone.utc)


class NascarTickerTests(unittest.TestCase):
    def test_only_exact_nascar_com_dated_news_links_are_allowed(self):
        good="https://www.nascar.com/news-media/2026/11/25/major-cup-series-story/"
        self.assertEqual(mod.official_article_url(good),good)
        for bad in (
            "http://www.nascar.com/news-media/2026/11/25/story/",
            "https://nascar.com/news-media/2026/11/25/story/",
            "https://www.nascar.com.evil.test/news-media/2026/11/25/story/",
            "https://www.espn.com/racing/nascar/story/_/id/1234",
            "https://www.nascar.com/wp-admin/admin.php",
            "javascript:alert(1)",
            "//www.espn.com/news-media/2026/11/25/story/",
            "https://www.nascar.com/news-media/2026/14/25/story/",
        ):
            self.assertIsNone(mod.official_article_url(bad),bad)

    def test_official_homepage_anchor_extracts_nested_text_without_other_domains(self):
        html="""<html><body>
            <a href="/news-media/2026/11/25/cup-series-test-story/"><strong>NASCAR</strong>
              confirms a major 2027 Cup Series change</a>
            <a href="https://www.espn.com/racing/nascar/story/1">ESPN NASCAR headline</a>
            <a href="https://www.nascar.com.evil.example/news-media/2026/11/25/phishing/">Fake NASCAR</a>
            <a href="/news-media/2026/11/25/image-only/"><img alt="a photo"></a>
            </body></html>"""
        reader=mod.ArticleLinks()
        reader.feed(html)
        self.assertEqual(len(reader.articles),1)
        self.assertIn("NASCAR confirms",reader.articles[0]["title"])

    def test_verified_story_date_from_official_permalink_not_guessed_result(self):
        link={"title":"NASCAR confirms 2027 Cup Series rules",
              "url":"https://www.nascar.com/news-media/2026/11/24/2027-cup-series-rules/"}
        result=mod.story_from_link(link,NOW)
        self.assertEqual(result["date"],"2026-11-24")
        self.assertEqual(result["dateBasis"],"official NASCAR.com dated article permalink")
        self.assertEqual(result["type"],"news")
        self.assertNotIn("winner",result)
        self.assertIsNone(mod.story_from_link({**link,
            "url":"https://www.nascar.com/news-media/2025/01/01/old-article/"},NOW))
        self.assertIsNone(mod.story_from_link({**link,
            "url":"https://www.nascar.com/news-media/2026/12/31/future-article/"},NOW))

    def test_verified_stories_are_selected_and_deduplicated(self):
        html="""<a href="/news-media/2026/11/24/verified-driver-transfer/">
                  NASCAR team announces an official driver transfer</a>
                  <a href="/news-media/2026/11/24/verified-driver-transfer/">
                  NASCAR team announces an official driver transfer</a>
                  <a href="/news-media/2026/11/23/second-league-headline/">
                  NASCAR announces another official 2027 update</a>"""
        result=mod.fetch_official_stories(NOW,downloader=lambda url: html)
        self.assertEqual(result["source"],"NASCAR.com")
        self.assertEqual(result["status"],"available")
        self.assertEqual(len(result["articles"]),2)
        self.assertEqual(result["results"],[],"No fabricated NASCAR results")
        self.assertTrue(all(x["url"].startswith("https://www.nascar.com/news-media/")
                            for x in result["articles"]))

    def test_unavailable_nascar_source_fails_closed_without_espn(self):
        with self.assertRaises(ValueError):
            mod.fetch_official_stories(NOW,downloader=lambda url:
                '<a href="https://www.espn.com/racing/nascar/">ESPN NASCAR news</a>')
        code=(ROOT/"scripts/refresh_nascar.py").read_text()
        self.assertNotIn("site.api.espn.com",code)
        self.assertNotIn("racing/nascar-premier",code)
        self.assertNotIn("nascar.com/feed",code)

    def test_fallback_does_not_forge_timestamp_or_inject_results(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/"nascar-ticker.json"
            previous={"schema":1,"source":"NASCAR.com","status":"available",
                "fetchedAt":"2026-11-24T17:00:00Z",
                "articles":[{"title":"NASCAR confirms major racing series changes",
                    "url":"https://www.nascar.com/news-media/2026/11/24/racing-series-changes/",
                    "date":"2026-11-24","dateBasis":"official NASCAR.com dated article permalink",
                    "type":"news"}],"results":[]}
            self.assertEqual(mod.story_from_link(previous["articles"][0],NOW)["date"],"2026-11-24")
            self.assertEqual(previous["fetchedAt"],"2026-11-24T17:00:00Z")
            self.assertEqual(previous["results"],[])


if __name__=="__main__":
    unittest.main()
