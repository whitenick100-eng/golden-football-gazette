#!/usr/bin/env python3
"""Gazette QA: block malformed data and ensure live page can render it."""
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def read_json(path):
    p = ROOT / path
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))

def valid_time(value):
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except (ValueError, AttributeError, TypeError):
        return False

def validate():
    page = (ROOT / "index.html").read_text(encoding="utf-8")
    for marker in ['id="nfl-games"', 'id="fantasy-team-grid"', 'id="championship-bracket"',
                   'id="espn-games"', 'id="nfl-status"']:
        assert marker in page, f"Website missing required section: {marker}"
    assert "data/nfl-week.json" in page and "data/league.json" in page
    assert "40 — 50 — 40" not in page, "Old yard-number strip returned"
    league = read_json("data/league.json")
    if league:
        if league.get("status") == "unavailable":
            print("WARNING: ESPN league unavailable; not asserting live league data")
        else:
            assert league.get("leagueId") == "1413446022"
            assert league.get("season") == 2026
            assert valid_time(league.get("fetchedAt"))
            teams = league.get("standings", [])
            assert len(teams) == 10 and len({t["teamId"] for t in teams}) == 10
            assert isinstance(league.get("matchups"), list)
            for g in league["matchups"]:
                assert isinstance(g.get("week"), int)
                for side in ("home", "away"):
                    assert isinstance(g[side].get("name"), str)
                    for key in ("points", "projectedPoints"):
                        v = g[side].get(key)
                        assert v is None or (isinstance(v, (int, float)) and not isinstance(v, bool) and 0 <= v < 1000)
    nfl = read_json("data/nfl-week.json")
    if nfl:
        if nfl.get("status") == "unavailable":
            print("WARNING: NFL schedule unavailable; not asserting live NFL data")
        else:
            assert valid_time(nfl.get("fetchedAt"))
            assert 1 <= nfl.get("week", 0) <= 22
            games = nfl.get("games")
            assert isinstance(games, list) and len(games) > 0
            for g in games:
                assert valid_time(g.get("date"))
                assert g.get("home", {}).get("name") and g.get("away", {}).get("name")
                if not (g.get("venue") or g.get("city")):
                    print("WARNING: NFL venue unavailable for game", g.get("id"))
                weather = g.get("weather")
                if weather:
                    assert weather.get("source") == "Open-Meteo" and weather.get("forecast") is True
                    assert -100 <= weather["temperatureF"] <= 150
                    assert 0 <= weather["precipitationChance"] <= 100
    injuries = read_json("data/nfl-injuries.json")
    if injuries:
        if injuries.get("status") == "unavailable":
            print("WARNING: NFL league injury feed unavailable; official report links remain visible")
        else:
            assert valid_time(injuries.get("fetchedAt")), "Injury report missing timestamp"
            assert injuries.get("season") == datetime.now(timezone.utc).year, "Injury season mismatch"
            assert injuries.get("source") == "ESPN NFL injury listing"
            assert isinstance(injuries.get("teams"), list) and injuries["teams"]
            assert injuries.get("teamCount") == len(injuries["teams"])
            assert injuries.get("playerCount") == sum(len(t["players"]) for t in injuries["teams"])
            for team in injuries["teams"]:
                assert team.get("teamId") and team.get("name")
                assert isinstance(team.get("players"), list) and team["players"]
                for player in team["players"]:
                    assert isinstance(player.get("name"), str) and player["name"]
                    assert "reportedStatus" in player and "practiceStatus" in player
    assert 'id="nfl-injury-report"' in page and 'id="injury-teams"' in page
    assert "data/nfl-injuries.json" in page
    for marker in ('id="auto-coverage"', 'id="auto-coverage-stories"',
                   'id="player-stars"', 'id="player-star-meta"',
                   'id="championship-pairings"', 'id="consolation-pairings"'):
        assert marker in page, f"Missing automated newsroom element: {marker}"
    assert "data/weekly-features.json" in page and "data/top-performers.json" in page
    leaders=read_json("data/top-performers.json")
    if leaders:
        if leaders.get("status") == "unavailable":
            print("WARNING: ESPN completed-week player leaderboard unavailable")
        else:
            assert leaders.get("leagueId")==1413446022 and leaders.get("season")==2026
            assert valid_time(leaders.get("fetchedAt"))
            assert isinstance(leaders.get("week"),int) and 1<=leaders["week"]<=22
            players=leaders.get("players")
            assert isinstance(players,list) and len(players)==5
            assert len({p["playerId"] for p in players})==5
            for p in players:
                assert p.get("name") and isinstance(p.get("playerId"),int)
                assert isinstance(p.get("points"),(int,float)) and 0<=p["points"]<250
                assert p.get("headshotUrl","").startswith("https://a.espncdn.com/i/headshots/nfl/players/full/")
    weekly=read_json("data/weekly-features.json")
    if weekly:
        assert valid_time(weekly.get("generatedAt"))
        assert weekly.get("status") in ("available","unavailable")
        assert isinstance(weekly.get("coverage"),list)
        for story in weekly["coverage"]:
            assert all(isinstance(story.get(k),str) and story[k] for k in ("headline","body","source","tag"))
        bracket=weekly.get("playoffs")
        assert isinstance(bracket,dict)
        if bracket.get("status")=="available":
            assert bracket.get("type") in ("provisional","espn-listed")
            assert len(bracket.get("contenders",[]))+len(bracket.get("outsideCurrentField",[]))==10
            assert bracket.get("playoffTeamCount")==len(bracket["contenders"])
    # Daily source-backed NFL trade/release/waiver desk.
    for marker in ('id="nfl-transactions-desk"','id="transaction-items"',
                   'id="transaction-filter"','id="transaction-freshness"'):
        assert marker in page, f"Missing daily NFL transactions view: {marker}"
    assert "data/nfl-transactions.json" in page
    transactions=read_json("data/nfl-transactions.json")
    if transactions:
        if transactions.get("status")=="unavailable":
            print("WARNING: ESPN NFL transaction records unavailable")
        else:
            assert transactions.get("status")=="available"
            assert transactions.get("source")=="ESPN NFL transactions"
            assert valid_time(transactions.get("fetchedAt"))
            assert transactions.get("windowStart") and transactions.get("windowEnd")
            assert isinstance(transactions.get("moves"),list)
            assert transactions.get("total")>=len(transactions["moves"])
            for move in transactions["moves"]:
                assert move.get("type") in ("Trade","Released","Waived")
                assert move.get("team") and move.get("description")
                assert transactions["windowStart"]<=move.get("date","")<=transactions["windowEnd"]
    print("Gazette structure and available data validation passed")

if __name__ == "__main__":
    validate()
