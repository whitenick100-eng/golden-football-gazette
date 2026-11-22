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

# Fantasy-relevant skill positions only. ESPN supplies either a position
# abbreviation or its full name, depending on the feed format.
WATCHED_POSITIONS = {"QB", "RB", "WR", "TE", "K"}
POSITION_NAMES = {
    "quarterback":"QB", "running back":"RB", "wide receiver":"WR",
    "tight end":"TE", "kicker":"K", "place kicker":"K",
    "placekicker":"K",
}
def position_label(value):
    if isinstance(value, dict):
        code=value.get("abbreviation") or value.get("shortName")
        if isinstance(code,str) and code.strip():
            normalized=code.strip().upper()
            if normalized=="PK": normalized="K"
            if normalized in WATCHED_POSITIONS:return normalized
        text=label(value.get("displayName") or value.get("name"))
    else:
        text=label(value)
    code=text.strip().upper()
    if code=="PK":code="K"
    if code in WATCHED_POSITIONS:return code
    return POSITION_NAMES.get(text.strip().casefold(),"")

# A "Day-To-Day" label, routine practice limitation or general roster status
# does not amount to a major designation. Do not infer injury severity.
def major_status(value):
    status=label(value).strip().casefold().replace("_"," ").replace("-"," ")
    status=" ".join(status.split())
    if status in {"out","doubtful","questionable","injured reserve","ir","ir r",
                  "reserve injured","reserve ir","physically unable to perform",
                  "pup","reserve pup"}:
        return True
    return False

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
    excluded_active = 0
    source_entries = 0
    group_sizes = []
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
        group_sizes.append(len(raw_players))
        source_entries += len(raw_players)
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
            position = position_label(athlete.get("position") or entry.get("position"))
            injury = label(entry.get("type") or entry.get("injury"))
            reported = label(entry.get("status"))
            # ESPN includes ordinary roster 'Active' statuses in its large
            # injuries endpoint. Never present these as injury designations.
            if reported.casefold() in {"active", "healthy", "available"}:
                excluded_active += 1
                continue
            game_status = label(entry.get("gameStatus"))
            practice = label(entry.get("practiceStatus") or entry.get("practice"))
            # Include only meaningful ESPN-listed injury availability updates
            # for the five fantasy-relevant offensive/kicking positions.
            # Practice participation alone is NOT an official game status.
            if position not in WATCHED_POSITIONS:
                continue
            if not (major_status(game_status) or major_status(reported)):
                continue
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
    # A genuine zero is valid: ESPN can have no significant QB/RB/WR/TE/K
    # listings. Do not misreport this as an API outage or invent injuries.
    if not teams and source_entries==0:
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
        "coverageNote":"Only QB, RB, WR, TE and K players with ESPN-listed Out, Doubtful, Questionable, Injured Reserve or PUP statuses are included. ESPN injury listings are not necessarily official NFL game designations. Day-to-day, practice-only and Active roster records are excluded. ESPN may limit results; missing players are not necessarily healthy. Consult NFL.com for official practice and game reports.",
        "positions":sorted(WATCHED_POSITIONS), "filter":"major-availability-only",
        "teamCount":len(teams), "playerCount":total,
        "sourceEntryCount":source_entries, "excludedActiveCount":excluded_active,
        "sourceTeamGroupCount":len(group_sizes),
        "possiblePerTeamLimit":25 if group_sizes and all(n == 25 for n in group_sizes) else None,
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
        print(f"ESPN key-position injury watch: {data['playerCount']} major reported statuses across {data['teamCount']} teams (QB/RB/WR/TE/K only; {data['excludedActiveCount']} Active records excluded)")
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
