#!/usr/bin/env python3
"""Fetch ESPN public league data; publish only sanitized scores/standings.
Never publish members, player ownership, credentials or full ESPN responses.
"""
import json, os, urllib.request, datetime
from pathlib import Path

LEAGUE = "1413446022"
YEAR = 2026
URL = (f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{YEAR}/"
       f"segments/0/leagues/{LEAGUE}?view=mTeam&view=mMatchup&view=mMatchupScore&view=mScoreboard&view=mBoxscore&matchupPeriodId=11&scoringPeriodId=11")
OUT = Path("data/league.json")
OUT.parent.mkdir(exist_ok=True, parents=True)

def refresh():
    request = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0 GoldenFootballGazette/1.0", "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=25) as response:
        data = json.load(response)
    if str(data.get("id")) != LEAGUE or int(data.get("seasonId", 0)) != YEAR:
        raise ValueError("Unexpected ESPN league or season")
    teams = data.get("teams") or []
    schedule = data.get("schedule") or []
    if len(teams) != 10 or not schedule:
        raise ValueError("Incomplete ESPN league response")
    names = {int(t["id"]): t.get("name", "Team " + str(t["id"])) for t in teams}
    standings = []
    for t in teams:
        overall = t.get("record", {}).get("overall", {})
        standings.append({"teamId": t["id"], "name": names[int(t["id"])],
                          "logo": t.get("logo"), "wins": overall.get("wins"), "losses": overall.get("losses"),
                          "ties": overall.get("ties"), "pointsFor": overall.get("pointsFor")})
    standings.sort(key=lambda t: (-(t["wins"] or 0), t["losses"] or 0, -(t["pointsFor"] or 0)))
    games = []
    for g in schedule:
        if "home" not in g or "away" not in g: continue
        home, away = g["home"], g["away"]
        games.append({"week": g.get("matchupPeriodId"), "winner": g.get("winner", "UNDECIDED"),
                      "home": {"teamId":home.get("teamId"), "name": names.get(home.get("teamId")), "points": home.get("totalPointsLive",home.get("totalPoints")), "projectedPoints": home.get("totalProjectedPointsLive") if isinstance(home.get("totalProjectedPointsLive"),(int,float)) and home.get("totalProjectedPointsLive")>0 else None},
                      "away": {"teamId":away.get("teamId"), "name": names.get(away.get("teamId")), "points": away.get("totalPointsLive",away.get("totalPoints")), "projectedPoints": away.get("totalProjectedPointsLive") if isinstance(away.get("totalProjectedPointsLive"),(int,float)) and away.get("totalProjectedPointsLive")>0 else None}})
    return {"leagueId": LEAGUE, "season": YEAR, "source": "ESPN public API",
            "fetchedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "standingsAsOf": data.get("status", {}).get("standingsUpdateDate"),
            "currentMatchupPeriod": data.get("status", {}).get("currentMatchupPeriod"),\n            "requestedWeek": 11,
            "standings": standings, "matchups": games}

try:
    payload = refresh()
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print("ESPN refresh succeeded; sanitized league data written")
except Exception as exc:
    print(f"ESPN refresh unavailable: {type(exc).__name__}: {exc}")
    if OUT.exists():
        print("Retaining last verified league.json without changing its fetchedAt")
    else:
        OUT.write_text(json.dumps({"leagueId": LEAGUE, "season": YEAR,
            "status": "unavailable", "message": "No verified live ESPN data available"}, indent=2) + "\n")
