#!/usr/bin/env python3
"""Publish NASCAR.com-only Cup race data and optional official headlines.

Official race-list/weekend-results feeds from cf.nascar.com supply race
winners and upcoming schedule. If www.nascar.com blocks the GitHub runner,
headlines are simply omitted; there is NEVER an ESPN NASCAR fallback.
"""
from __future__ import annotations

import datetime as dt
import html
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo
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
EASTERN = ZoneInfo("America/New_York")
CDN = "https://cf.nascar.com/"
OFFICIAL_SCHEDULE = "https://www.nascar.com/nascar-cup-series/{year}/schedule/"
RACE_FEED_PATTERN = re.compile(r"^/cacher/20\d{2}/1/(?:race_list_basic\.json|\d{3,6}/weekend-feed\.json)$")


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


def _get_official_json(url):
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme != "https" or parsed.netloc.lower() != "cf.nascar.com"
            or not RACE_FEED_PATTERN.fullmatch(parsed.path)):
        raise ValueError("Non-NASCAR official data URL prohibited")
    request = urllib.request.Request(url, headers={
        "User-Agent": "GoldenFootballGazette-NASCAR-Cup/1.0",
        "Accept": "application/json",
    })
    with urllib.request.urlopen(request, timeout=15) as response:
        final = urllib.parse.urlsplit(response.geturl())
        if final.scheme != "https" or final.netloc.lower() != "cf.nascar.com":
            raise ValueError("NASCAR CDN redirected away from official source")
        raw = response.read(5_000_001)
    if len(raw) > 5_000_000:
        raise ValueError("Official NASCAR feed too large")
    return json.loads(raw)


def race_day(value):
    """NASCAR Cup race_list_basic dates are track-local display dates."""
    if not isinstance(value, str):
        return None
    try:
        # Do not convert a race date through UTC and accidentally change its day.
        day = dt.date.fromisoformat(value[:10])
    except ValueError:
        return None
    return day if 2020 <= day.year <= 2100 else None


def official_cup_results(now=None, get_json=_get_official_json):
    """Trust only NASCAR's race list + explicit first-place official finish."""
    now = now or dt.datetime.now(dt.timezone.utc)
    today = now.astimezone(EASTERN).date()
    lists = []
    failures = []
    for year in (today.year, today.year + 1):
        url = CDN + f"cacher/{year}/1/race_list_basic.json"
        try:
            feed = get_json(url)
            if not isinstance(feed, list):
                raise ValueError("NASCAR Cup race list is not an array")
            rows = [r for r in feed if isinstance(r, dict) and
                    r.get("series_id") == 1 and r.get("race_season") == year
                    and isinstance(r.get("race_id"), int) and
                    isinstance(r.get("race_name"), str) and
                    len(r.get("race_name", "")) > 5]
            lists.extend(rows)
        except (OSError, ValueError, TypeError, urllib.error.URLError) as exc:
            failures.append(f"{year} Cup schedule: {type(exc).__name__}")
    if not lists:
        raise ValueError("Official NASCAR.com Cup schedules unavailable: " + "; ".join(failures))

    scheduled = []
    for race in lists:
        day = race_day(race.get("race_date")) or race_day(race.get("date_scheduled"))
        if day and day >= today and day <= today + dt.timedelta(days=400):
            scheduled.append({"race": race["race_name"].strip()[:110],
                              "track": str(race.get("track_name") or "").strip()[:80],
                              "date": day.isoformat(), "status": "scheduled",
                              "url": OFFICIAL_SCHEDULE.format(year=race["race_season"]),
                              "verification": "NASCAR.com official Cup race schedule"})
    scheduled.sort(key=lambda r: r["date"])
    # At most three of the most recent 45-day completed races. Never infer
    # a winner from the event title, article text, or an unconfirmed field.
    past = [r for r in lists if (race_day(r.get("race_date")) and
            dt.timedelta(0) <= today - race_day(r["race_date"]) <= dt.timedelta(days=45)
            and r.get("inspection_complete") is True
            and isinstance(r.get("winner_driver_id"), int)
            and r["winner_driver_id"] > 0)]
    past.sort(key=lambda r: race_day(r["race_date"]), reverse=True)
    results = []
    for race in past[:4]:
        year, rid = race["race_season"], race["race_id"]
        try:
            data = get_json(CDN + f"cacher/{year}/1/{rid}/weekend-feed.json")
            if not isinstance(data, dict) or not isinstance(data.get("weekend_race"), list):
                continue
            matching = [item for item in data["weekend_race"]
                        if isinstance(item, dict) and item.get("race_id") == rid
                        and item.get("series_id") == 1 and
                        isinstance(item.get("results"), list)]
            if not matching:
                continue
            winners = [item for item in matching[0]["results"]
                       if isinstance(item, dict) and item.get("finishing_position") == 1
                       and item.get("driver_id") == race["winner_driver_id"]
                       and item.get("disqualified") is not True
                       and isinstance(item.get("driver_fullname"), str)
                       and item["driver_fullname"].strip()]
            if len(winners) != 1:
                continue
            results.append({
                "race": race["race_name"].strip()[:110],
                "track": str(race.get("track_name") or "").strip()[:80],
                "winner": winners[0]["driver_fullname"].strip()[:75],
                "date": race_day(race["race_date"]).isoformat(),
                "status": "final",
                "url": OFFICIAL_SCHEDULE.format(year=year),
                "verification": "NASCAR.com official Cup weekend race results",
            })
        except (OSError, ValueError, TypeError, urllib.error.URLError):
            # A failed weekend feed cannot create an inferred winner.
            continue
    return {"results": results[:3], "upcoming": scheduled[:3],
            "officialFeedUrl": CDN + f"cacher/{today.year}/1/race_list_basic.json",
            "series": "NASCAR Cup Series",
            "raceDataNote": "Race winners verified by official NASCAR.com finishing-position and driver-ID matches; upcoming race dates from NASCAR Cup schedule only."}


def assemble(now=None, stories=None, cup=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    stories = stories if isinstance(stories, dict) else {}
    cup = cup if isinstance(cup, dict) else {}
    articles = stories.get("articles") or []
    results = cup.get("results") or []
    upcoming = cup.get("upcoming") or []
    if not (articles or results or upcoming):
        raise ValueError("No official NASCAR.com news, race results or schedule were verified")
    return {
        "schema": 1, "source": "NASCAR.com", "sourceUrl": "https://www.nascar.com/",
        "officialFeedUrl": cup.get("officialFeedUrl"),
        "status": "available", "fetchedAt": now.isoformat(),
        "articles": articles[:MAX_STORIES], "results": results[:3], "upcoming": upcoming[:3],
        "resultsNote": cup.get("raceDataNote") or
          "No verified official Cup race winners or schedule in this edition.",
        "dateNote": "News article dates come from official NASCAR.com dated permalinks. Cup race dates and winners come from NASCAR-owned schedule and results JSON.",
    }


def earlier_snapshot():
    req = urllib.request.Request(PREVIOUS_URL, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=8) as response:
        data = response.read(200_001)
    if len(data) > 200_000:
        raise ValueError("Previous NASCAR feed exceeds size limit")
    snapshot = json.loads(data)
    if (not isinstance(snapshot, dict) or snapshot.get("schema") != 1
            or snapshot.get("source") != "NASCAR.com" or snapshot.get("status") != "available"):
        return None
    if not isinstance(snapshot.get("articles"), list) or not isinstance(snapshot.get("results"), list):
        return None
    now = dt.datetime.now(dt.timezone.utc)
    articles = [story_from_link(row, now) for row in snapshot["articles"][:MAX_STORIES]]
    snapshot["articles"] = [row for row in articles if row]
    schedule_link = re.compile(r"^https://www\.nascar\.com/nascar-cup-series/20\d{2}/schedule/$")
    old_results = []
    for row in snapshot["results"][:3]:
        if (isinstance(row, dict) and row.get("status") == "final"
                and isinstance(row.get("race"), str)
                and isinstance(row.get("winner"), str)
                and row.get("verification") == "NASCAR.com official Cup weekend race results"
                and isinstance(row.get("url"), str)
                and schedule_link.fullmatch(row["url"])
                and race_day(row.get("date"))):
            old_results.append(row)
    snapshot["results"] = old_results
    upcoming=[]
    for row in snapshot.get("upcoming") or []:
        if (isinstance(row,dict) and row.get("status")=="scheduled"
                and isinstance(row.get("race"),str)
                and row.get("verification")=="NASCAR.com official Cup race schedule"
                and isinstance(row.get("url"),str)
                and schedule_link.fullmatch(row["url"])
                and race_day(row.get("date"))):
            upcoming.append(row)
    snapshot["upcoming"]=upcoming[:3]
    return snapshot if any((snapshot["articles"],old_results,upcoming)) else None

def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    try:
        now = dt.datetime.now(dt.timezone.utc)
        try:
            news = fetch_official_stories(now)
        except (OSError, ValueError, TypeError, urllib.error.URLError) as exc:
            news = None
            print("NASCAR.com news pages unavailable (not replaced by ESPN):",type(exc).__name__)
        try:
            cup = official_cup_results(now)
        except (OSError, ValueError, TypeError, urllib.error.URLError) as exc:
            cup = None
            print("NASCAR-owned Cup racing feeds unavailable:",type(exc).__name__)
        result = assemble(now, news, cup)
        OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print("NASCAR.com-only ticker:", len(result["articles"]), "headlines,",
              len(result["results"]), "verified Cup finishes,",
              len(result["upcoming"]), "upcoming Cup races; no ESPN NASCAR feed")
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
                "articles": [], "results": [], "upcoming": [],
                "message": "NASCAR.com official news, Cup races and schedule unavailable; no ESPN fallback is permitted."
            }, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
