#!/usr/bin/env python3
"""Publish a timestamped, sanitized league-wide NFL injury listing from ESPN.

This is an ESPN injury listing, NOT necessarily the NFL's official weekly
practice/game-status report. Never turn 'day-to-day' or DNP into 'out'.
A failed/empty fetch cannot replace the last verified snapshot with fake data.
"""
import datetime as dt
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/nfl-injuries.json"
SOURCE = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/injuries"
SOURCE_PAGE = "https://www.espn.com/nfl/injuries"
OFFICIAL_REPORT = "https://www.nfl.com/injuries/"
HEADERS = {"User-Agent": "Mozilla/5.0 GoldenFootballGazette/1.0",
           "Accept": "application/json"}

def label(value):
    """Take only a concise literal ESPN field, never guess a designation."""
    if isinstance(value, dict):
        for key in ("displayName", "description", "name", "abbreviation", "shortName"):
            if isinstance(value.get(key), str) and value[key].strip():
                return value[key].strip()[:100]
    if isinstance(value, str):
        return " ".join(value.strip().split())[:100]
    return ""

def status_rank(status):
    s = (status or "").lower()
    order = ("out", "injured reserve", "ir", "doubtful", "questionable",
             "day-to-day", "limited", "did not participate", "full")
    return next((i for i, flag in enumerate(order) if s == flag), len(order))

def normalize(payload, now=None, week=None):
    if not isinstance(payload, dict):
        raise ValueError("ESPN did not return an injury object")
    raw = payload.get("injuries")
    if not isinstance(raw, list) or not raw:
        raise ValueError("ESPN injury response missing team groups")
    now = now or dt.datetime.now(dt.timezone.utc)
    year = (payload.get("season") or {}).get("year")
    if year is not None and int(year) != now.year:
        raise ValueError("ESPN returned a different NFL season")
    groups = {}
    for group in raw:
        if not isinstance(group, dict):
            continue
        # ESPN's live NFL feed puts id/displayName directly on each group;
        # some documented examples instead nest these fields in "team".
        nested_team = group.get("team")
        team = nested_team if isinstance(nested_team, dict) and nested_team else group
        team_id = str(team.get("id") or "").strip()
        team_name = label(team.get("displayName") or team.get("name"))
        if not team_id or not team_name:
            continue
        abbrev = label(team.get("abbreviation"))
        raw_players = group.get("injuries")
        if not isinstance(raw_players, list):
            continue
        dest = groups.setdefault(team_id, {
            "teamId": team_id, "name":team_name, "abbreviation":abbrev,
            "players":[],
        })
        for entry in raw_players:
            if not isinstance(entry, dict):
                continue
            athlete = entry.get("athlete") or {}
            if not isinstance(athlete, dict):
                athlete = {}
            name = label(athlete.get("displayName") or athlete.get("fullName") or entry.get("name"))
            if not name:
                continue
            position = label(athlete.get("position"))
            injury = label(entry.get("type") or entry.get("injury"))
            reported = label(entry.get("status"))
            game_status = label(entry.get("gameStatus"))
            practice = label(entry.get("practiceStatus") or entry.get("practice"))
            date = entry.get("date")
            if not isinstance(date, str) or len(date) > 40:
                date = None
            person = {
                "name":name, "position":position or None,
                "injury":injury or None, "reportedStatus":reported or None,
                "gameStatus":game_status or None, "practiceStatus":practice or None,
                "reportDate":date,
            }
            # Duplicate entries can appear across overlapping team groups.
            if person not in dest["players"]:
                dest["players"].append(person)

    teams = [team for team in groups.values() if team["players"]]
    teams.sort(key=lambda t:(t["name"].lower(), t["teamId"]))
    for team in teams:
        team["players"].sort(key=lambda p:(status_rank(p["gameStatus"] or p["reportedStatus"]),
                                          p["name"].lower()))
    if not teams:
        # Schema-only diagnostics; never log player names or private fields.
        print("ESPN injury response keys:", sorted(payload.keys())[:25])
        print("ESPN injury group count:",len(raw))
        for index, group in enumerate(raw[:3]):
            if not isinstance(group, dict):
                print("Group",index,"type:",type(group).__name__)
                continue
            print("Group",index,"keys:",sorted(group.keys())[:20],
                  "team kind:",type(group.get("team")).__name__,
                  "injuries kind:",type(group.get("injuries")).__name__,
                  "injuries length:",len(group.get("injuries")) if isinstance(group.get("injuries"),list) else "n/a")
            first=(group.get("injuries") or [None])[0] if isinstance(group.get("injuries"),list) else None
            if isinstance(first,dict):
                print("Group",index,"first entry keys:",sorted(first.keys())[:25])
        raise ValueError("No attributable NFL injury entries in ESPN response")
    total = sum(len(team["players"]) for team in teams)
    return {
        "season":year or now.year, "week":week,
        "fetchedAt":now.isoformat(),
        "source":"ESPN NFL injury listing",
        "sourceUrl":SOURCE_PAGE, "officialNflReportUrl":OFFICIAL_REPORT,
        "coverageNote":"ESPN injury listings are not necessarily the official NFL practice/game-status reports. Only teams and players actually returned are shown. Teams not listed are not necessarily injury-free.",
        "teamCount":len(teams), "playerCount":total,
        "teams":teams,
    }

def fetch():
    request = urllib.request.Request(SOURCE, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=35) as response:
        raw = response.read(15_000_000 + 1)
    if len(raw) > 15_000_000:
        raise ValueError("ESPN injury report too large")
    return json.loads(raw)

def current_week():
    path = ROOT / "data/nfl-week.json"
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
        if d.get("status") != "unavailable" and d.get("season") == dt.datetime.now(dt.timezone.utc).year:
            number = d.get("week")
            if isinstance(number, int) and 1 <= number <= 22:
                return number
    except (OSError, ValueError, TypeError):
        pass
    return None

def main():
    OUT.parent.mkdir(parents=True,exist_ok=True)
    try:
        data = normalize(fetch(), week=current_week())
        OUT.write_text(json.dumps(data,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
        print(f"ESPN NFL injury listing updated: {data['playerCount']} players across {data['teamCount']} teams")
    except Exception as exc:
        print(f"ESPN NFL injury listing unavailable ({type(exc).__name__}): {exc}")
        if OUT.is_file():
            print("Retaining the previous injury listing with its original timestamp")
        else:
            OUT.write_text(json.dumps({
                "status":"unavailable", "source":"ESPN NFL injury listing",
                "message":"No verified league-wide injury listing is available.",
                "sourceUrl":SOURCE_PAGE,"officialNflReportUrl":OFFICIAL_REPORT,
            },indent=2)+"\n",encoding="utf-8")

if __name__ == "__main__":
    main()
