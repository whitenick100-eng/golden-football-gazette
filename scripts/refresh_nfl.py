#!/usr/bin/env python3
"""Fetch NFL weekly schedule, team records, logos, venues, and optional weather.
Weather is forecast only, never invented; published games are ordered by kickoff.
"""
import datetime as dt
import json
import urllib.parse
import urllib.request
from pathlib import Path

OUT = Path("data/nfl-week.json")
OUT.parent.mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "GoldenFootballGazette/1.0", "Accept": "application/json"}

def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
        return json.load(r)

def build():
    now = dt.datetime.now(dt.timezone.utc)
    current = get("https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?limit=100")
    season = current.get("season", {}).get("year", now.year)
    week = current.get("week", {}).get("number")
    if not isinstance(week, int) or not 1 <= week <= 22:
        raise ValueError("NFL week not available")
    url = f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates={season}&seasontype=2&week={week}&limit=100"
    data = get(url)
    events = data.get("events") or []
    if not events:
        raise ValueError("No NFL schedule returned")
    games = []
    for e in events:
        comp = (e.get("competitions") or [{}])[0]
        status = e.get("status") or {}
        status_type = status.get("type") or {}
        state = status_type.get("state") if status_type.get("state") in ("pre","in","post") else "pre"
        if status_type.get("completed"):
            state = "post"
        sides = {}
        for c in comp.get("competitors", []):
            team = c.get("team", {})
            record = next((r.get("summary") for r in c.get("records", []) if r.get("type") == "total"), None)
            sides[c.get("homeAway")] = {
                "name": team.get("displayName"), "abbr": team.get("abbreviation"),
                "record": record, "logo": team.get("logo"),
                "score": c.get("score") if state in ("in","post") else None
            }
        if not sides.get("home") or not sides.get("away"): continue
        venue = comp.get("venue") or {}
        address = venue.get("address") or {}
        games.append({
            "id": str(e.get("id")), "date": e.get("date"),
            "status": status_type.get("description"),
            "statusType": state,
            "period": status.get("period") if isinstance(status.get("period"), int) else 0,
            "displayClock": status.get("displayClock") if isinstance(status.get("displayClock"), str) else "",
            "shortDetail": status_type.get("shortDetail") if isinstance(status_type.get("shortDetail"), str) else "",
            "completed": bool(status_type.get("completed")),
            "home": sides["home"], "away": sides["away"],
            "venue": venue.get("fullName"), "city": address.get("city"),
            "state": address.get("state"), "indoor": bool(venue.get("indoor")),
            "weather": None
        })
    games.sort(key=lambda g: (g["date"] or "", g["id"]))
    # Open-Meteo weather is only shown when a city can be geocoded and the
    # kickoff is within the supported forecast window.
    cache = {}
    for g in games:
        try:
            if g["completed"] or g["indoor"] or not g["city"]: continue
            kickoff = dt.datetime.fromisoformat(g["date"].replace("Z", "+00:00"))
            if not dt.timedelta(0) <= kickoff - now <= dt.timedelta(days=14): continue
            key = (g["city"], g["state"])
            if key not in cache:
                q = urllib.parse.urlencode({"name": g["city"], "count": 5, "language": "en", "format": "json"})
                results = get("https://geocoding-api.open-meteo.com/v1/search?" + q).get("results") or []
                cache[key] = next((p for p in results if p.get("country_code") == "US" and (not g["state"] or p.get("admin1", "").lower() == g["state"].lower())), None)
                if cache[key] is None: cache[key] = next((p for p in results if p.get("country_code") == "US"), None)
            loc = cache[key]
            if not loc: continue
            params = urllib.parse.urlencode({"latitude":loc["latitude"],"longitude":loc["longitude"],
                "hourly":"temperature_2m,precipitation_probability,weather_code",
                "temperature_unit":"fahrenheit","timezone":"UTC","forecast_days":15})
            forecast = get("https://api.open-meteo.com/v1/forecast?" + params).get("hourly") or {}
            times = forecast.get("time") or []
            target = kickoff.strftime("%Y-%m-%dT%H:00")
            if target not in times: continue
            i = times.index(target)
            g["weather"] = {"temperatureF":forecast["temperature_2m"][i],
                "precipitationChance":forecast["precipitation_probability"][i],
                "code":forecast["weather_code"][i], "source":"Open-Meteo", "forecast":True}
        except Exception as ex:
            print("Weather unavailable for", g["id"], type(ex).__name__)
    if not games: raise ValueError("No valid games returned")
    return {"season":season,"week":week,"fetchedAt":now.isoformat(),"games":games}

try:
    OUT.write_text(json.dumps(build(),indent=2)+"\n",encoding="utf-8")
    print("NFL weekly schedule published")
except Exception as exc:
    print("NFL weekly refresh unavailable:",type(exc).__name__,str(exc))
    if not OUT.exists():
        OUT.write_text(json.dumps({"status":"unavailable","message":"NFL schedule not verified"})+"\n")
