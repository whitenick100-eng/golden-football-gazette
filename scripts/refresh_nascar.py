#!/usr/bin/env python3
"""Publish NASCAR-only ticker news from NASCAR.com (no ESPN racing data).

Fetch publicly linked NASCAR.com news articles from the official NASCAR.com
homepage. Each article's date comes from its official dated permalink, not
an inferred race score or a fabricated publication time. Preserve an earlier
verified NASCAR.com-only snapshot on an upstream outage.
"""
from __future__ import annotations

import datetime as dt
import html
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/nascar-ticker.json"
SOURCE_URLS = ("https://www.nascar.com/", "https://www.nascar.com/news-media/")
PREVIOUS_URL = "https://whitenick100-eng.github.io/golden-football-gazette/data/nascar-ticker.json"
ARTICLE_PATH = re.compile(r"^/news-media/(20\d{2})/(0[1-9]|1[0-2])/([0-2]\d|3[01])/[a-z0-9-]+/?$", re.I)
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; GoldenFootballGazette/1.0; NASCAR.com source attribution)",
           "Accept": "text/html,application/json;q=0.9,*/*;q=0.5"}
MAX_BYTES = 3_000_000
MAX_STORIES = 12


def official_article_url(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = urllib.parse.urlsplit(urllib.parse.urljoin("https://www.nascar.com/", value))
    except ValueError:
        return None
    if (parsed.scheme != "https" or parsed.netloc.lower() != "www.nascar.com"
            or parsed.username or parsed.password or parsed.port):
        return None
    if not ARTICLE_PATH.fullmatch(parsed.path):
        return None
    return "https://www.nascar.com" + parsed.path


class ArticleLinks(HTMLParser):
    """Extract link text from official HTML; no JavaScript, network, or HTML reuse."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.current = None
        self.depth = 0
        self.articles = []

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        attrs = dict(attrs)
        if self.current is None:
            href = official_article_url(attrs.get("href"))
            if href:
                self.current = {"url": href, "words": []}
                self.depth = 1
        else:
            self.depth += 1

    def handle_data(self, data):
        if self.current is not None:
            self.current["words"].append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.current is not None:
            self.depth -= 1
            if self.depth:
                return
            value = self.current
            self.current = None
            title = " ".join("".join(value["words"]).split())
            # Skip empty linked images, navigation, incomplete teaser snippets.
            if 14 <= len(title) <= 180 and not title.lower().startswith(("read more", "watch more")):
                self.articles.append({"title": title, "url": value["url"]})


def story_from_link(item, now):
    url = official_article_url(item.get("url"))
    if not url:
        return None
    path = urllib.parse.urlsplit(url).path
    match = ARTICLE_PATH.fullmatch(path)
    if not match:
        return None
    try:
        date = dt.date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return None
    # NASCAR.com embeds this calendar date in the article's canonical URL.
    # It is NOT assumed to be a confirmed hour/minute of publication.
    age = now.date() - date
    if not 0 <= age.days <= 30:
        return None
    title = " ".join(html.unescape(item.get("title", "")).split())
    if not 14 <= len(title) <= 160:
        return None
    return {"title": title, "url": url, "date": date.isoformat(),
            "dateBasis": "official NASCAR.com dated article permalink",
            "type": "news"}


def _download(url, limit=MAX_BYTES):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as response:
        final = urllib.parse.urlsplit(response.geturl())
        if final.scheme != "https" or final.netloc.lower() != "www.nascar.com":
            raise ValueError("Official NASCAR.com source redirected to an unapproved site")
        raw = response.read(limit + 1)
    if len(raw) > limit:
        raise ValueError("NASCAR.com response exceeded size limit")
    return raw.decode("utf-8", errors="replace")


def fetch_official_stories(now=None, downloader=_download):
    now = now or dt.datetime.now(dt.timezone.utc)
    articles = []
    failures = []
    for url in SOURCE_URLS:
        try:
            reader = ArticleLinks()
            reader.feed(downloader(url))
            articles.extend(reader.articles)
        except (OSError, ValueError, TypeError, urllib.error.URLError) as exc:
            failures.append(f"{url}: {type(exc).__name__}")
    seen = set()
    selected = []
    for raw in articles:
        entry = story_from_link(raw, now)
        if entry is None or entry["url"] in seen:
            continue
        seen.add(entry["url"])
        selected.append(entry)
    selected.sort(key=lambda item: item["date"], reverse=True)
    if not selected:
        raise ValueError("NASCAR.com provided no independently verifiable dated news links"
                         + ("; " + "; ".join(failures) if failures else ""))
    return {
        "schema": 1, "source": "NASCAR.com", "sourceUrl": "https://www.nascar.com/",
        "status": "available", "fetchedAt": now.isoformat(),
        "articles": selected[:MAX_STORIES],
        # Race positions/scores are intentionally NOT fabricated from headlines.
        "results": [], "resultsNote": "No official NASCAR.com race-position feed has been verified for this edition.",
        "dateNote": "Story dates are derived from NASCAR.com's dated article links, not a confirmed publication hour.",
    }


def earlier_snapshot():
    req = urllib.request.Request(PREVIOUS_URL, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=8) as response:
        data = response.read(200_001)
    if len(data) > 200_000:
        raise ValueError("Previous NASCAR feed exceeds size limit")
    snapshot = json.loads(data)
    if (not isinstance(snapshot, dict) or snapshot.get("schema") != 1
            or snapshot.get("source") != "NASCAR.com" or snapshot.get("status") != "available"
            or not isinstance(snapshot.get("articles"), list)):
        return None
    rows = []
    for item in snapshot["articles"][:MAX_STORIES]:
        entry = story_from_link(item, dt.datetime.now(dt.timezone.utc))
        if entry:
            rows.append(entry)
    if not rows:
        return None
    snapshot["articles"] = rows
    snapshot["results"] = []
    return snapshot


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    try:
        result = fetch_official_stories()
        OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print("NASCAR.com-only ticker:", len(result["articles"]),
              "official dated news links; no ESPN NASCAR feed requested")
    except (OSError, ValueError, TypeError, urllib.error.URLError) as exc:
        print("NASCAR.com retrieval unavailable:", type(exc).__name__, str(exc)[:160])
        prior = None
        try:
            prior = earlier_snapshot()
        except (OSError, ValueError, TypeError, urllib.error.URLError):
            pass
        if prior:
            # Original verification timestamp preserved; never call older news new.
            OUT.write_text(json.dumps(prior, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            print("Retained last official NASCAR.com headlines and their original source timestamp")
        else:
            OUT.write_text(json.dumps({"schema": 1, "source": "NASCAR.com",
                "status": "unavailable", "sourceUrl": "https://www.nascar.com/",
                "articles": [], "results": [],
                "message": "Official NASCAR.com headlines could not be verified; no ESPN fallback is permitted."
            }, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
