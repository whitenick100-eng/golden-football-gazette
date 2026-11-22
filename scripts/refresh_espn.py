#!/usr/bin/env python3
"""Publish only sanitized ESPN fantasy league standings/matchups.

Refresh follows ESPN's *current* scoring period; never fix the feed to Week 11.
ESPN public league access may be unavailable for private leagues.
"""
import datetime as dt
import json
import urllib.request
from pathlib import Path

LEAGUE = "1413446022"
YEAR = 2026
BASE_URL = (
    f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/"
    f"seasons/{YEAR}/segments/0/leagues/{LEAGUE}"
)
OUT = Path("data/league.json")
OUT.parent.mkdir(exist_ok=True, parents=True)
HEADERS = {"User-Agent":"Mozilla/5.0 GoldenFootballGazette/1.0","Accept":"application/json"}

def get_json(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=25) as response:
        return json.load(response)

def point(value):
    """Only finite, league-plausible ESPN fantasy points."""
    import math
    return value if type(value) in (int, float) and math.isfinite(value) and 0 <= value < 1000 else None


def merge_schedule(base, current, week=None):
    """Apply a verified current-week patch; never replace other fantasy weeks.

    ESPN responses can be partial. Verify both team IDs and matchup week BEFORE
    applying the update, and never regress ESPN's confirmed final to undecided.
    """
    import copy
    games = copy.deepcopy(base)
    if not isinstance(current, list):
        return games
    by_id = {str(g["id"]):g for g in games
             if isinstance(g, dict) and g.get("id") is not None}
    for game in current:
        if not isinstance(game, dict):
            continue
        old = by_id.get(str(game.get("id")))
        if not old or (week is not None and game.get("matchupPeriodId") != week):
            continue
        if old.get("matchupPeriodId") != game.get("matchupPeriodId"):
            continue
        sides_match = all(
            isinstance(game.get(side), dict) and
            isinstance(old.get(side), dict) and
            game[side].get("teamId") is not None and
            game[side].get("teamId") == old[side].get("teamId")
            for side in ("home", "away"))
        if not sides_match:
            continue
        for side in ("home", "away"):
            for key in ("totalPointsLive", "totalPoints", "totalProjectedPointsLive"):
                validated = point(game[side].get(key))
                if validated is not None:
                    old[side][key] = validated
        winner = game.get("winner")
        if winner in {"HOME","AWAY","TIE"}:
            old["winner"] = winner
        elif winner == "UNDECIDED" and old.get("winner") not in {"HOME","AWAY","TIE"}:
            old["winner"] = winner
    return games

def refresh():
    first = get_json(BASE_URL + "?view=mTeam&view=mMatchup&view=mMatchupScore")
    if str(first.get("id")) != LEAGUE or int(first.get("seasonId",0)) != YEAR:
        raise ValueError("ESPN returned unexpected league or season")
    teams = first.get("teams") or []
    schedule = first.get("schedule") or []
    if len(teams) != 10 or not schedule:
        raise ValueError("ESPN returned incomplete teams or schedule")
    status = first.get("status") or {}
    week = status.get("currentMatchupPeriod") or first.get("scoringPeriodId")
    try:
        week = int(week)
    except (TypeError, ValueError):
        week = None
    if week is not None and 1 <= week <= 22:
        url = (BASE_URL + "?view=mScoreboard&view=mMatchupScore"
               + f"&matchupPeriodId={week}&scoringPeriodId={week}")
        try:
            scoped = get_json(url)
            if str(scoped.get("id")) == LEAGUE and scoped.get("seasonId") == YEAR:
                schedule = merge_schedule(schedule, scoped.get("schedule") or [], week)
        except Exception as exc:
            # The original mMatchupScore schedule remains intact.
            print("Week-specific ESPN projection lookup unavailable:",
                  type(exc).__name__)

    # Playoff configuration comes from ESPN league settings, not a guessed
    # four-team bracket. Keep only public competition configuration.
    playoff_settings = {}
    try:
        config = get_json(BASE_URL + "?view=mSettings")
        rule = ((config.get("settings") or {}).get("scheduleSettings") or {})
        spots = rule.get("playoffTeamCount")
        regular_weeks = rule.get("matchupPeriodCount")
        if isinstance(spots, int) and 2 <= spots <= len(teams):
            playoff_settings["playoffTeamCount"] = spots
        if isinstance(regular_weeks, int) and 1 <= regular_weeks <= 18:
            playoff_settings["regularSeasonMatchupPeriods"] = regular_weeks
        if isinstance(rule.get("playoffSeedingRule"), str):
            playoff_settings["playoffSeedingRule"] = rule["playoffSeedingRule"][:60]
        playoff_settings["source"] = "ESPN league mSettings"
    except Exception as exc:
        print("ESPN playoff settings unavailable:", type(exc).__name__)
    names = {int(t["id"]): t.get("name") or f"Team {t['id']}" for t in teams}
    standings = []
    for t in teams:
        record = (t.get("record") or {}).get("overall") or {}
        standings.append({
            "teamId": t["id"],"name": names[int(t["id"])],"logo":t.get("logo"),
            "wins":record.get("wins"),"losses":record.get("losses"),
            "ties":record.get("ties"),"pointsFor":record.get("pointsFor"),
        })
    standings.sort(key=lambda t: (
        -(t["wins"] or 0),t["losses"] or 0,-(t["pointsFor"] or 0)
    ))
    if week is None or week < 1 or week > 22:
        raise ValueError("ESPN current matchup week is not verified")
    games = []
    for game in schedule:
        if not isinstance(game.get("home"), dict) or not isinstance(game.get("away"), dict):
            continue
        home, away = game["home"], game["away"]
        def side(item):
            projected = point(item.get("totalProjectedPointsLive"))
            actual = point(item.get("totalPointsLive"))
            if actual is None:
                actual = point(item.get("totalPoints"))
            return {
                "teamId":item.get("teamId"),
                "name":names.get(item.get("teamId")),
                "points":actual,
                "projectedPoints":projected if projected is not None and projected > 0 else None,
            }
        games.append({
            "id": game.get("id"),
            "week":game.get("matchupPeriodId"),
            "playoffTierType":game.get("playoffTierType") or "NONE",
            "winner":game.get("winner","UNDECIDED"),
            "home":side(home),"away":side(away),
        })
    return {
        "leagueId":LEAGUE,"season":YEAR,
        "source":"ESPN public fantasy API",
        "fetchedAt":dt.datetime.now(dt.timezone.utc).isoformat(),
        "standingsAsOf":status.get("standingsUpdateDate"),
        "currentMatchupPeriod":week,
        "requestedWeek":week,
        "standings":standings,
        "playoffSettings": playoff_settings,
        "matchups":games,
    }

if __name__ == "__main__":
    try:
        OUT.write_text(json.dumps(refresh(),indent=2)+"\n",encoding="utf-8")
        print("ESPN fantasy league refresh succeeded")
    except Exception as exc:
        print(f"ESPN fantasy refresh unavailable: {type(exc).__name__}: {exc}")
        if OUT.exists():
            print("Retaining last verified league snapshot and timestamp")
        else:
            OUT.write_text(json.dumps({
                "leagueId":LEAGUE,"season":YEAR,"status":"unavailable",
                "message":"No verified live ESPN fantasy data available"
            },indent=2)+"\n")
