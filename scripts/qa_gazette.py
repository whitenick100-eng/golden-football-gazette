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
    print("Gazette structure and available data validation passed")

if __name__ == "__main__":
    validate()
