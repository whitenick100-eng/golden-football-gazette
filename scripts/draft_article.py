#!/usr/bin/env python3
"""Daily Gazette editor. All content is an UNPUBLISHED owner-review draft.

Retrieves compact facts from the data-refresh job's verified snapshots.
Uses the OpenAI API when available; otherwise writes a labeled, strictly
data-derived bulletin so API quota errors don't halt the daily workflow.
No article is published without the repository owner's PR merge.
"""
import argparse
import datetime as dt
import email.utils
import json
import os
import random
import time
import urllib.error
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

LOCAL = ZoneInfo("America/New_York")
ROOT = Path(__file__).resolve().parent.parent
VALID_TYPES = ("auto", "daily-brief", "week-preview", "weekly-recap")
MAX_AGE = dt.timedelta(hours=48)

class APIUnavailable(Exception):
    pass

def choose_type(choice, today):
    if choice != "auto":
        return choice
    if today.weekday() == 1:  # Tuesday: review the previous football week
        return "weekly-recap"
    if today.weekday() in (3, 4, 5, 6):  # Thursday-Sunday: fixtures ahead
        return "week-preview"
    return "daily-brief"

def verified_sources(now):
    sources = {}
    for name, filename in (("fantasy_league", "data/league.json"),
                           ("nfl_week", "data/nfl-week.json")):
        path = ROOT / filename
        if not path.is_file():
            print(f"Data check: {name} missing")
            continue
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if raw.get("status") == "unavailable":
                print(f"Data check: {name} unavailable")
                continue
            stamp = dt.datetime.fromisoformat(raw["fetchedAt"].replace("Z", "+00:00"))
            if stamp.tzinfo is None:
                raise ValueError("timestamp missing timezone")
            age = now - stamp.astimezone(dt.timezone.utc)
            if not dt.timedelta(0) <= age <= MAX_AGE:
                print(f"Data check: {name} outside 48-hour freshness window")
                continue
            if name == "fantasy_league":
                if (str(raw.get("leagueId")) != "1413446022" or
                    raw.get("season") != 2026 or
                    not isinstance(raw.get("standings"), list) or
                    len(raw["standings"]) != 10):
                    raise ValueError("unexpected league or incomplete standings")
                period = raw.get("currentMatchupPeriod")
                games = [g for g in raw.get("matchups", []) if g.get("week") in
                         (period, period - 1 if isinstance(period, int) else None)]
                sources[name] = {
                    "source": "ESPN fantasy league",
                    "fetchedAt": raw["fetchedAt"],
                    "season": raw["season"],
                    "matchupPeriod": period,
                    "standings": raw["standings"][:10],
                    "matchups": games[:12],
                }
            else:
                games = raw.get("games")
                if not isinstance(games, list) or not games or not (1 <= int(raw.get("week", 0)) <= 22):
                    raise ValueError("no verified NFL games")
                sources[name] = {
                    "source": "ESPN NFL schedule and optional Open-Meteo forecasts",
                    "fetchedAt": raw["fetchedAt"],
                    "season": raw.get("season"),
                    "week": raw["week"],
                    "games": games[:18],
                }
            print(f"Data check: verified {name}, timestamp {raw['fetchedAt']}")
        except (ValueError, TypeError, KeyError, AttributeError, json.JSONDecodeError) as exc:
            print(f"Data check: rejected invalid {name}: {type(exc).__name__}")
    # Verified daily items and completed-week fantasy stars may also inform
    # the AI editor's unpublished article, but never override source facts.
    extra = ROOT / "data/weekly-features.json"
    if extra.is_file():
        try:
            obj = json.loads(extra.read_text(encoding="utf-8"))
            stamp = dt.datetime.fromisoformat(obj["generatedAt"].replace("Z", "+00:00"))
            age = now - stamp.astimezone(dt.timezone.utc)
            if dt.timedelta(minutes=-3) <= age <= MAX_AGE and obj.get("status") == "available":
                sources["weekly_features"] = {
                    "source":"Gazette fact-based briefing from ESPN source snapshots",
                    "fetchedAt":obj["generatedAt"],
                    "coverage":obj.get("coverage",[])[:6],
                    "playoffs":obj.get("playoffs"),
                }
        except (OSError,ValueError,TypeError,KeyError,AttributeError):
            print("Unverified daily feature snapshot not included in editorial input")
    players_file = ROOT / "data/top-performers.json"
    if players_file.is_file():
        try:
            obj = json.loads(players_file.read_text(encoding="utf-8"))
            stamp=dt.datetime.fromisoformat(obj["fetchedAt"].replace("Z","+00:00"))
            age=now-stamp.astimezone(dt.timezone.utc)
            if (dt.timedelta(minutes=-3)<=age<=MAX_AGE and len(obj.get("players",[]))==5
                and obj.get("leagueId")==1413446022 and obj.get("season")==2026):
                sources["top_rostered_players"] = {
                    "source":"ESPN actual fantasy mBoxscore for rostered athletes",
                    "fetchedAt":obj["fetchedAt"], "week":obj["week"],
                    "scope":obj["scope"], "players":obj["players"],
                }
        except (OSError,ValueError,TypeError,KeyError,AttributeError):
            print("Unverified player awards not included in editorial input")
    return sources

def verified_bulletin(sources, article_type, local_now):
    """Deterministic verified-data fallback with no fabricated statistics."""
    date_label = local_now.strftime("%A, %B %d, %Y").replace(" 0", " ")
    lines = [
        f"# The Golden Football Gazette — {article_type.replace('-', ' ').title()}",
        f"*{date_label} · Independent fantasy football league newspaper*",
        "",
        "## Today's Verified Football Report",
        "",
    ]
    league = sources.get("fantasy_league")
    if league:
        standings = league["standings"]
        leader = standings[0]
        lines.append(
            f"ESPN league 1413446022 lists **{leader['name']}** at the top of its "
            f"latest supplied standings ({leader.get('wins', '?')}–{leader.get('losses', '?')}). "
            f"These standings were retrieved {league['fetchedAt']}. "
            "Standings position is not, by itself, proof of a clinched playoff berth."
        )
        period = league.get("matchupPeriod")
        current = [g for g in league.get("matchups", []) if g.get("week") == period]
        if current:
            descriptions = []
            for g in current[:5]:
                a, h = g.get("away") or {}, g.get("home") or {}
                descriptions.append(f"{a.get('name', 'Away team')} against {h.get('name', 'Home team')}")
            lines.append(
                f"ESPN lists these fantasy matchups for period {period}: "
                + "; ".join(descriptions) + ". "
                "No winner or final result is declared unless the supplied feed confirms it."
            )
    nfl = sources.get("nfl_week")
    if nfl:
        games = nfl["games"]
        pending = [g for g in games if not g.get("completed")]
        completed = [g for g in games if g.get("completed")]
        if pending:
            upcoming = []
            for game in pending[:5]:
                away = (game.get("away") or {}).get("name", "Away team")
                home = (game.get("home") or {}).get("name", "Home team")
                try:
                    start = dt.datetime.fromisoformat(game["date"].replace("Z", "+00:00")).astimezone(LOCAL)
                    kickoff = start.strftime("%a %b %d, %I:%M %p ET").replace(" 0", " ")
                except (ValueError, TypeError, KeyError):
                    kickoff = "kickoff unverified"
                venue = game.get("venue") or "venue not confirmed"
                upcoming.append(f"{away} at {home} ({kickoff}; {venue})")
            lines.append(
                f"The verified NFL Week {nfl['week']} schedule includes "
                + "; ".join(upcoming) + ". "
                "Outdoor weather forecasts are subject to change."
            )
        if completed:
            results = []
            for game in completed[:4]:
                away, home = game.get("away") or {}, game.get("home") or {}
                if away.get("score") is None or home.get("score") is None:
                    continue
                results.append(f"{away.get('name')} {away['score']}, {home.get('name')} {home['score']}")
            if results:
                lines.append("The supplied NFL feed marks these games final: " + "; ".join(results) + ".")
    leaders=sources.get("top_rostered_players")
    if leaders:
        top=leaders["players"]
        lines.append(
            f"ESPN reports the five highest-scoring rostered players for completed Week {leaders['week']}: "
            + "; ".join(f"{p['name']} ({p['points']:.2f})" for p in top)
            + ". This list includes bench players and excludes NFL free agents not rostered in this league."
        )
    bracket=(sources.get("weekly_features") or {}).get("playoffs") or {}
    if bracket.get("status")=="available":
        spots=bracket.get("playoffTeamCount")
        field=bracket.get("contenders") or []
        if spots and field:
            lines.append(
                "The current standings-based championship field contains "
                + ", ".join(t["name"] for t in field)
                + ". These are provisional positions, not confirmed clinches or eliminations."
            )
    lines += [
        "",
        "## Editor's Verification Checklist",
        "",
        "- Check each ESPN snapshot timestamp and confirm it is current.",
        "- Verify any projected scores, individual player awards and playoff claims separately.",
        "- Confirm team logos, injuries, and forecasts before publishing additional claims.",
        "",
        "### Sources and editorial status",
        "",
        "This is an **automated verified-data bulletin**, not an AI-generated article. "
        "It is a draft and requires the owner's review and GitHub merge before publication.",
    ]
    for name, source in sources.items():
        lines.append(f"- {source['source']}: retrieved {source['fetchedAt']} UTC timestamp.")
    return "\n\n".join(lines)

def request_ai(payload, api_key, sleeper=time.sleep):
    encoded = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=encoded,
        headers={"Authorization": "Bearer " + api_key,
                 "Content-Type": "application/json"},
        method="POST",
    )
    quota_codes = {
        "insufficient_quota", "credit_balance_exhausted",
        "organization_usage_limit_exceeded", "organization_spend_limit_exceeded",
        "project_spend_limit_exceeded",
    }
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                result = json.load(response)
            choice = result["choices"][0]
            if choice.get("finish_reason") == "length":
                raise APIUnavailable("AI response was truncated")
            draft = choice["message"]["content"]
            if not isinstance(draft, str) or len(draft.strip()) < 250:
                raise APIUnavailable("AI response was empty or incomplete")
            return draft.strip()
        except urllib.error.HTTPError as exc:
            try:
                info = json.loads(exc.read(4096).decode("utf-8", "replace")).get("error", {})
                code = str(info.get("code") or "")
                kind = str(info.get("type") or "")
            except (ValueError, TypeError, AttributeError):
                code, kind = "", ""
            if exc.code == 429:
                if code in quota_codes or kind == "insufficient_quota":
                    raise APIUnavailable("OpenAI API credits or spending quota exhausted (429)")
                if attempt < 2:
                    try:
                        delay = float(exc.headers.get("Retry-After"))
                    except (TypeError, ValueError):
                        delay = 3 * (2 ** attempt) + random.uniform(0, 1)
                    delay = min(30, max(1, delay))
                    print(f"Temporary API rate limit; retrying in {delay:.1f}s")
                    sleeper(delay)
                    continue
                raise APIUnavailable("OpenAI API rate limit persisted after 3 attempts (429)")
            raise APIUnavailable(f"OpenAI API returned HTTP {exc.code} ({code or kind or 'unclassified'})")
        except (urllib.error.URLError, TimeoutError) as exc:
            raise APIUnavailable(f"OpenAI API network unavailable ({type(exc).__name__})")
    raise APIUnavailable("OpenAI API unavailable")

def write_draft(draft, sources, mode, article_type, local_now):
    date_label = local_now.strftime("%Y-%m-%d")
    folder = ROOT / "editorial"
    folder.mkdir(exist_ok=True)
    name = f"{date_label}-{article_type}-DRAFT.md"
    (folder / name).write_text(
        "<!-- UNPUBLISHED: OWNER APPROVAL REQUIRED -->\n\n"
        + draft.strip() + "\n", encoding="utf-8")
    document = {
        "date": date_label,
        "articleType": article_type,
        "body": draft.strip(),
        "generationMethod": mode,
        "sourceTimes": {name: d["fetchedAt"] for name, d in sources.items()},
        "editorialStatus": "owner-approved-on-merge",
    }
    (folder / "latest.json").write_text(
        json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Created approval-only draft editorial/{name} ({mode})")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--type", choices=VALID_TYPES, default="auto")
    args = parser.parse_args()
    local_now = dt.datetime.now(LOCAL)
    sources = verified_sources(dt.datetime.now(dt.timezone.utc))
    if not sources:
        raise SystemExit("No fresh verified ESPN or NFL data. No article created; refusing to invent facts.")
    article_type = choose_type(args.type, local_now)
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if key:
        instructions = (
            "You are the professional editor of The Golden Football Gazette, an independent "
            "fantasy football newspaper. Write an engaging, professional, copyedited daily "
            "newspaper article with a headline, dateline, 3–5 concise paragraphs, and an "
            "Editor's Verification Checklist. Use ONLY facts expressly contained in the "
            "supplied structured data. Separate ESPN fantasy league facts from NFL games. "
            "Never invent final results, player points, rankings, playoff clinches, "
            "injuries, weather, quotes, trophies, or fantasy ownership. "
            "Use only ESPN-verified completed-week player scores and label provisional brackets. "
            "Label previews and "
            "forecasts as such; do not label games final unless explicitly verified. "
            "Avoid recycled or stale history. Include the exact source names and fetchedAt "
            "timestamps in a brief source note. No misleading claims. "
            "The entire article is an unpublished draft awaiting owner approval."
        )
        payload = {
            "model": os.environ.get("GAZETTE_OPENAI_MODEL", "gpt-4.1-mini"),
            "messages": [
                {"role": "system", "content": instructions},
                {"role": "user", "content": json.dumps({
                    "article_type": article_type,
                    "date_eastern": local_now.strftime("%Y-%m-%d"),
                    "verified_data": sources,
                }, ensure_ascii=False)},
            ],
            "temperature": 0.2,
            "max_tokens": 1400,
        }
        try:
            draft = request_ai(payload, key)
            mode = "ai-draft-owner-review"
        except APIUnavailable as exc:
            print(f"AI writing unavailable: {exc}; preparing verified-data fallback bulletin.")
            draft = verified_bulletin(sources, article_type, local_now)
            mode = "verified-data-fallback-owner-review"
    else:
        print("OPENAI_API_KEY not configured; using verified-data bulletin without AI.")
        draft = verified_bulletin(sources, article_type, local_now)
        mode = "verified-data-fallback-owner-review"
    write_draft(draft, sources, mode, article_type, local_now)

if __name__ == "__main__":
    main()
