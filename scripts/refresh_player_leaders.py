#!/usr/bin/env python3
"""Top five ESPN fantasy performers *on this league's team rosters*.

Scores are ESPN's league-specific actual applied fantasy points from completed
matchup-period box scores. No estimated player points or fabricated portraits.
Bench players can qualify; free agents outside this league are not in this pool.
"""
import datetime as dt
import json
import math
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
LEAGUE_FILE = ROOT / "data/league.json"
OUT = ROOT / "data/top-performers.json"
BASE = "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/2026/segments/0/leagues/1413446022"
UA = {"User-Agent":"Mozilla/5.0 GoldenFootballGazette/1.0", "Accept":"application/json"}
POS = {1:"QB",2:"RB",3:"WR",4:"TE",5:"K",16:"D/ST"}

def completed_week(snapshot):
    """Only rank a period with every league matchup decided by ESPN."""
    current = snapshot.get("currentMatchupPeriod")
    if not isinstance(current,int):
        return None
    scheduled = {}
    for match in snapshot.get("matchups",[]):
        if not isinstance(match,dict):
            continue
        week = match.get("week")
        if isinstance(week,int) and 1 <= week <= current:
            scheduled.setdefault(week,[]).append(match)
    expected = len(snapshot.get("standings",[]))//2
    for week in sorted(scheduled,reverse=True):
        rows = scheduled[week]
        if (len(rows) == expected and all(
            g.get("winner") in ("HOME","AWAY","TIE") and
            g.get("home",{}).get("teamId") is not None and
            g.get("away",{}).get("teamId") is not None for g in rows
        )):
            return week
    return None

def score(entry,week):
    """Only actual weekly fantasy points, never ESPN projections."""
    pool=entry.get("playerPoolEntry") or {}
    player=pool.get("player") or {}
    # Prefer the explicit actual stat entry for this exact scoring period.
    stats=pool.get("stats") or player.get("stats") or []
    for stat in stats:
        if not isinstance(stat,dict):
            continue
        if (stat.get("scoringPeriodId") == week and
            stat.get("statSourceId",stat.get("statTypeId")) == 0 and
            stat.get("seasonId",2026) == 2026):
            points=stat.get("appliedTotal")
            if isinstance(points,(int,float)) and math.isfinite(points) and 0 <= points < 250:
                return float(points)
    # Boxscore's playerPoolEntry.appliedStatTotal represents the requested
    # scoringPeriodId; only trust it when this was explicitly scoped to week.
    points=pool.get("appliedStatTotal")
    if isinstance(points,(int,float)) and math.isfinite(points) and 0 <= points < 250:
        return float(points)
    return None

def parse_boxscore(box, snapshot, week):
    if str(box.get("id")) != "1413446022" or box.get("seasonId") != 2026:
        raise ValueError("Boxscore league/season mismatch")
    games=[x for x in box.get("schedule",[]) if x.get("matchupPeriodId")==week]
    if len(games)<len(snapshot["standings"])//2:
        raise ValueError("ESPN boxscore returned incomplete matchup coverage")
    team_names={int(t["teamId"]):t["name"] for t in snapshot["standings"]}
    athletes={}
    entries_seen=0
    for game in games:
        for side in ("home","away"):
            row=game.get(side) or {}
            roster=row.get("rosterForCurrentScoringPeriod") or row.get("rosterForMatchupPeriod") or {}
            entries=roster.get("entries") if isinstance(roster,dict) else None
            if not isinstance(entries,list):
                continue
            for entry in entries:
                pool=entry.get("playerPoolEntry") or {}
                player=pool.get("player") or {}
                athlete_id=entry.get("playerId") or player.get("id")
                name=player.get("fullName")
                if not isinstance(athlete_id,int) or not isinstance(name,str) or not name.strip():
                    continue
                pos=player.get("defaultPositionId")
                if pos==16 or "D/ST" in name.upper():
                    continue # Defense is not a person with a headshot.
                points=score(entry,week)
                if points is None:
                    continue
                entries_seen+=1
                team_id=row.get("teamId")
                item={
                    "playerId":athlete_id,
                    "name":name.strip()[:100],
                    "position":POS.get(pos,"NFL"),
                    "fantasyTeam":team_names.get(team_id),
                    "fantasyTeamId":team_id,
                    "points":round(points,2),
                    # ESPN NFL athlete ID points to an actual portrait image.
                    # Browser onerror will hide 404s, not display synthetic art.
                    "headshotUrl":f"https://a.espncdn.com/i/headshots/nfl/players/full/{athlete_id}.png",
                    "headshotSource":"ESPN NFL athlete portrait",
                }
                if athlete_id not in athletes or item["points"] > athletes[athlete_id]["points"]:
                    athletes[athlete_id]=item
    top=sorted(athletes.values(),key=lambda p:(-p["points"],p["name"]))[:5]
    if len(top)<5:
        raise ValueError(f"Only {len(top)} player scores in completed ESPN boxscore")
    # Position standings must be actual scores, not projections.
    return {
        "leagueId":1413446022,
        "season":2026,
        "week":week,
        "fetchedAt":dt.datetime.now(dt.timezone.utc).isoformat(),
        "source":"ESPN fantasy mBoxscore (actual league scoring)",
        "scope":"Players on the 10 ESPN fantasy team rosters, including bench; not every NFL free agent",
        "eligiblePlayersWithScores":len(athletes),
        "players":top,
    }

def refresh():
    snapshot=json.loads(LEAGUE_FILE.read_text(encoding="utf-8"))
    if str(snapshot.get("leagueId"))!="1413446022" or snapshot.get("season")!=2026 or snapshot.get("status")=="unavailable":
        raise ValueError("Verified ESPN league snapshot not available")
    week=completed_week(snapshot)
    if week is None:
        raise ValueError("No fully completed matchup period confirmed by ESPN yet")
    query=urllib.parse.urlencode([
        ("view","mBoxscore"),("view","mMatchupScore"),
        ("matchupPeriodId",week),("scoringPeriodId",week),
    ])
    request=urllib.request.Request(BASE+"?"+query,headers=UA)
    with urllib.request.urlopen(request,timeout=35) as response:
        payload=json.load(response)
    return parse_boxscore(payload,snapshot,week)

# GitHub Pages publishes a fresh, temporary artifact each day rather than
# committing generated data to the main branch. Reuse the previously published
# verified leaderboard until ESPN confirms a NEW completed scoring week.
PUBLISHED = "https://whitenick100-eng.github.io/golden-football-gazette/data/top-performers.json"
EASTERN = ZoneInfo("America/New_York")


def verified_leaders(data):
    """Reject stale-format, incomplete or misidentified previous leaderboards."""
    if not isinstance(data, dict):
        return False
    if str(data.get("leagueId")) != "1413446022" or data.get("season") != 2026:
        return False
    if not isinstance(data.get("week"), int) or not 1 <= data["week"] <= 22:
        return False
    try:
        stamp = dt.datetime.fromisoformat(str(data["fetchedAt"]).replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            return False
    except (KeyError, ValueError, TypeError):
        return False
    players = data.get("players")
    if not isinstance(players, list) or len(players) != 5:
        return False
    identities = set()
    for player in players:
        if not isinstance(player, dict):
            return False
        pid = player.get("playerId")
        if not isinstance(pid, int) or pid <= 0 or pid in identities:
            return False
        identities.add(pid)
        if not isinstance(player.get("name"), str) or not player["name"].strip():
            return False
        points = player.get("points")
        if not isinstance(points, (int, float)) or isinstance(points, bool) or not math.isfinite(points) or not 0 <= points < 250:
            return False
    return True


def load_previous():
    options = []
    if OUT.is_file():
        try:
            current = json.loads(OUT.read_text("utf-8"))
            if verified_leaders(current):
                options.append(current)
        except (OSError, json.JSONDecodeError):
            pass
    try:
        request = urllib.request.Request(
            PUBLISHED, headers={"User-Agent": UA["User-Agent"], "Accept": "application/json"}
        )
        with urllib.request.urlopen(request, timeout=12) as response:
            content = response.read(200_001)
        if len(content) <= 200_000:
            published = json.loads(content)
            if verified_leaders(published):
                options.append(published)
    except (OSError, ValueError, json.JSONDecodeError, urllib.error.URLError):
        print("Published weekly top-five backup unavailable; not assuming old data is current")
    if not options:
        return None
    return max(options, key=lambda d: (
        d["week"], dt.datetime.fromisoformat(d["fetchedAt"].replace("Z", "+00:00"))
    ))


def tuesday_window_started(now):
    """No new week before Tuesday 8:00 a.m. Eastern after Monday's games."""
    local = now.astimezone(EASTERN)
    return local.weekday() not in (0,) and not (local.weekday() == 1 and local.hour < 8)


def save(data):
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    prior = load_previous()
    if prior:
        # Preserve the ORIGINAL ESPN verification timestamp when using this
        # week's confirmed leaderboard on subsequent daily page deployments.
        save(prior)

    # Tuesday morning is the scheduled weekly refresh. If ESPN has not
    # confirmed final matchups by then, daily checks may retry later in the
    # week, but never replace the prior leaderboard with an older/same week.
    if prior and not tuesday_window_started(now):
        print("Keeping the previous verified top five until Tuesday morning ET")
        return
    try:
        result = refresh()
        if prior and result["week"] <= prior["week"]:
            print("Current verified fantasy top five retained: ESPN has not confirmed a newer completed week")
            return
        if prior is None and not tuesday_window_started(now):
            print("First-run top five is available but weekly rollover begins Tuesday morning")
            # Bootstrap so the site's initial leaderboard is not blank.
        result["refreshCadence"] = "Weekly Tuesday morning Eastern, after ESPN confirms completed matchups"
        save(result)
        print("Published new verified weekly top five: week", result["week"],
              "rostered player pool", result["eligiblePlayersWithScores"])
        for i, player in enumerate(result["players"], 1):
            print(i, player["name"], player["points"], player["fantasyTeam"])
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError, urllib.error.URLError) as exc:
        print("Weekly top-five refresh unavailable:", type(exc).__name__, str(exc)[:180])
        if prior:
            print("Keeping last confirmed weekly ESPN leaderboard with original timestamp")
        elif OUT.is_file():
            print("Retaining last output in this job")
        else:
            save({
                "status": "unavailable",
                "message": "Five verified ESPN rostered player scores could not be retrieved",
                "source": "ESPN fantasy mBoxscore",
            })


if __name__ == "__main__":
    main()
