#!/usr/bin/env python3
"""Publish a verified 48-hour league report and a daily clearly fictional column.

Page One contains only facts explicitly present in recent sanitized ESPN data.
Page Two separates source-backed fixture/waiver/standings notes from fictional
professional fan interviews. No generative API, credentials or real quotations.
The previous public Page One is reused until >=48 hours have elapsed.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import urllib.error
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = "gazette-pages.json"
PUBLIC_URL = "https://whitenick100-eng.github.io/golden-football-gazette/data/" + OUTPUT
EASTERN = ZoneInfo("America/New_York")
LEAGUE_ID = "1413446022"
SEASON = 2026
RECORD_TTL = dt.timedelta(hours=48)
MAX_PUBLIC_BYTES = 350000
BYLINE = "Adrian Mercer · Gazette League Correspondent (fictional pen name)"
FAN_NAMES = ("Alex Rowan", "Cameron Vale", "Jordan Reed", "Taylor Brooks",
             "Riley Parker", "Morgan Ellis", "Casey Quinn", "Drew Collins",
             "Avery Finch", "Blake Sutton")
FAN_LINES = (
    "We respect the standings. We simply reserve the right to file a strongly worded appeal with the fantasy football gods.",
    "Our supporter group has examined the projections. The conclusion: numbers are helpful, but confidence remains our preferred statistic.",
    "I will not predict the outcome. I will, however, confirm that my refresh button is preparing for overtime.",
    "Every contender deserves respect. Some of them also deserve a reminder that the schedule still has games left.",
    "There's no panic in our section. We call it a coordinated display of competitive enthusiasm.",
    "The commissioner can keep the official rankings. We specialize in unsolicited tactical observations.",
    "I am optimistic about our chances, though I acknowledge optimism has yet to appear in the league scoring settings.",
    "Our fan club is ready for the next matchup. The pregame speech has been rehearsed and politely shortened.",
    "We study matchups with dedication, then spend Sunday discovering that fantasy football has its own editorial agenda.",
    "The trophy race is open to interpretation; the final scores, fortunately, are not."
)
LEAD_LINES = (
    "The standings have the final word on facts; the supporters have requested equal time for opinions.",
    "A fresh day in Gridiron Giggles brings new tactical theories and the familiar sound of someone checking the box score.",
    "The supporters' desk confirms widespread optimism, careful scoreboard watching and a healthy respect for upsets.",
    "Our fictional fan correspondents have filed their latest dispatches. The enthusiasm is verified; the interviews are deliberately imaginary.",
    "The league's next slate deserves serious attention. Our fan section has offered serious attention with occasional theatrical pauses.",
    "No championship is awarded in the group chat. That has not prevented several excellent imaginary acceptance speeches.",
)
SECOND_LINES = (
    "A lead in the standings is useful, but even the leader has to set a lineup.",
    "The consolation race comes with no shortcuts and a trophy nobody wants on the mantel.",
    "A fantasy manager's greatest opponent is often the temptation to check the score every thirty seconds.",
    "Predictions are editorial entertainment; ESPN results decide the actual standings.",
    "The competition remains professional on paper and impressively creative in the supporters' imagination.",
)

def utc_time(value):
    if not isinstance(value, str):
        raise ValueError("Timestamp absent")
    stamp = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        raise ValueError("Timestamp lacks timezone")
    return stamp.astimezone(dt.timezone.utc)

def as_points(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        return None
    return round(float(value), 2) if 0 <= value < 1000 else None

def as_int(value, minimum=0, maximum=100000):
    return value if type(value) is int and minimum <= value <= maximum else None

def read_source(root, name):
    path = Path(root) / "data" / name
    try:
        if not path.is_file() or path.stat().st_size > MAX_PUBLIC_BYTES:
            return None
        doc = json.loads(path.read_text(encoding="utf-8"))
        return doc if isinstance(doc, dict) else None
    except (OSError, ValueError, TypeError):
        return None

def validated_league(raw, now):
    if not isinstance(raw, dict) or str(raw.get("leagueId")) != LEAGUE_ID:
        return None
    if raw.get("season") != SEASON or len(raw.get("standings") or []) != 10:
        return None
    if not isinstance(raw.get("matchups"), list):
        return None
    try:
        time = utc_time(raw.get("fetchedAt"))
        if not dt.timedelta(minutes=-5) <= now - time <= RECORD_TTL:
            return None
        ids = [t.get("teamId") for t in raw["standings"]]
        if any(type(x) is not int for x in ids) or len(set(ids)) != 10:
            return None
        week = as_int(raw.get("currentMatchupPeriod"), 1, 22)
        if week is None:
            return None
        return raw
    except (ValueError, TypeError, AttributeError):
        return None

def safe_name(value):
    return value.strip()[:90] if isinstance(value, str) and value.strip() else "Unnamed ESPN team"

def snapshot_standings(league):
    result = []
    for i, team in enumerate(league["standings"]):
        result.append({
            "position":i+1, "teamId":team["teamId"],
            "name":safe_name(team.get("name")),
            "wins":as_int(team.get("wins"),0,30),
            "losses":as_int(team.get("losses"),0,30),
            "ties":as_int(team.get("ties"),0,30),
            "pointsFor":as_points(team.get("pointsFor")) if as_points(team.get("pointsFor")) is not None
                else (round(float(team["pointsFor"]),2) if type(team.get("pointsFor")) in (int,float)
                      and math.isfinite(team["pointsFor"]) and 0 <= team["pointsFor"] < 100000 else None)
        })
    return result

def verified_final_games(league):
    names = {t["teamId"]:safe_name(t.get("name")) for t in league["standings"]}
    finals = []
    for game in league["matchups"]:
        if not isinstance(game, dict) or game.get("winner") not in ("HOME","AWAY","TIE"):
            continue
        week = as_int(game.get("week"),1,22)
        if week is None or week > league["currentMatchupPeriod"]:
            continue
        home,away = game.get("home"),game.get("away")
        if not isinstance(home,dict) or not isinstance(away,dict):
            continue
        hid,aid=home.get("teamId"),away.get("teamId")
        if hid not in names or aid not in names or hid==aid:
            continue
        h,a=as_points(home.get("points")),as_points(away.get("points"))
        if h is None or a is None:
            continue
        if (game["winner"]=="HOME" and h<=a or
            game["winner"]=="AWAY" and a<=h or
            game["winner"]=="TIE" and h!=a):
            continue  # Contradiction between supplied points and winner flag.
        finals.append({"week":week,"home":names[hid],"away":names[aid],
                       "homePoints":h,"awayPoints":a,
                       "winner": names[hid] if game["winner"]=="HOME" else
                                 names[aid] if game["winner"]=="AWAY" else "TIE"})
    if not finals:
        return [], None
    latest_week=max(x["week"] for x in finals)
    subset=[x for x in finals if x["week"]==latest_week]
    return subset[:5], latest_week

def verified_preview(league):
    names={t["teamId"]:safe_name(t.get("name")) for t in league["standings"]}
    possibilities=[]
    for game in league["matchups"]:
        if not isinstance(game, dict) or game.get("winner") not in ("UNDECIDED",None):
            continue
        week=as_int(game.get("week"),1,22)
        home,away=game.get("home"),game.get("away")
        if week is None or week < league["currentMatchupPeriod"] or not isinstance(home,dict) or not isinstance(away,dict):
            continue
        hid,aid=home.get("teamId"),away.get("teamId")
        if hid not in names or aid not in names or hid==aid:
            continue
        possibilities.append({"week":week,"home":names[hid],"away":names[aid]})
    if not possibilities:
        return [], None
    week=min(x["week"] for x in possibilities)
    return [x for x in possibilities if x["week"]==week][:5], week

def safe_waivers(league):
    """Only records explicitly marked EXECUTED by ESPN are publishable."""
    source=league.get("recentRosterActivity")
    if not isinstance(source, dict) or source.get("status")!="verified":
        return [], "Recent fantasy waiver activity could not be independently verified from ESPN."
    rows=[]
    for move in source.get("teams",[]):
        if not isinstance(move,dict):
            continue
        week=as_int(move.get("week"),1,22)
        added=as_int(move.get("acquisitions"),0,100)
        name=move.get("name")
        if week is not None and added and isinstance(name,str) and name.strip():
            rows.append({"team":safe_name(name),"week":week,"acquisitions":added})
    return rows[:10], "Verified ESPN-executed free-agent/waiver additions; player identities are not inferred."

def build_page_one(league, now, root):
    records=snapshot_standings(league)
    finals,latest_week=verified_final_games(league)
    lead=records[0]
    top=None
    leaders=read_source(root,"top-performers.json")
    if isinstance(leaders,dict) and str(leaders.get("leagueId"))==LEAGUE_ID and leaders.get("season")==SEASON:
        try:
            as_of=utc_time(leaders.get("fetchedAt"))
            if dt.timedelta(minutes=-5)<=now-as_of<=dt.timedelta(days=14):
                players=leaders.get("players")
                if isinstance(players,list) and players:
                    p=players[0]
                    if (isinstance(p,dict) and as_points(p.get("points")) is not None and
                        isinstance(p.get("name"),str) and as_int(leaders.get("week"),1,22) is not None):
                        top={"week":leaders["week"],"name":p["name"][:90],
                             "points":as_points(p["points"]),"fantasyTeam":safe_name(p.get("fantasyTeam"))}
        except (ValueError,TypeError):
            pass
    return {
        "status":"verified","publishedAt":now.isoformat(),
        "sourceAt":league["fetchedAt"],"season":SEASON,"leagueId":LEAGUE_ID,
        "currentWeek":league["currentMatchupPeriod"],
        "headline":"The Verified League Report",
        "standings":records,"latestFinalWeek":latest_week,"finals":finals,
        "leader":{"name":lead["name"],"wins":lead["wins"],"losses":lead["losses"]},
        "lastPlace":{"name":records[-1]["name"],"wins":records[-1]["wins"],
                     "losses":records[-1]["losses"]},
        "topPerformer":top,
        "source":"ESPN fantasy league public standings, final matchups and rostered player box scores",
        "notice":"Positions reflect ESPN's supplied standings order, not confirmed playoff seeding. "
                 "Winner claims appear only for explicitly final ESPN matchups with consistent point totals."
    }

def valid_prior(page,now):
    if (not isinstance(page,dict) or page.get("status")!="verified" or
        str(page.get("leagueId"))!=LEAGUE_ID or page.get("season")!=SEASON or
        len(page.get("standings") or [])!=10 or not isinstance(page.get("finals"),list)):
        return False
    try:
        created=utc_time(page.get("publishedAt"))
        sourced=utc_time(page.get("sourceAt"))
        return created<=now+dt.timedelta(minutes=5) and sourced<=created+dt.timedelta(minutes=5)
    except ValueError:
        return False

def published_previous():
    """Read only the known Pages host; no arbitrary URLs, redirects or auth."""
    class SameSiteRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,req,fp,code,msg,headers,url):
            if not url.startswith("https://whitenick100-eng.github.io/golden-football-gazette/data/"):
                raise ValueError("Untrusted Gazette redirect")
            return super().redirect_request(req,fp,code,msg,headers,url)
    req=urllib.request.Request(PUBLIC_URL,headers={
        "User-Agent":"GoldenFootballGazette-BidailyEdition/1.0",
        "Accept":"application/json"})
    with urllib.request.build_opener(SameSiteRedirect).open(req,timeout=10) as response:
        raw=response.read(MAX_PUBLIC_BYTES+1)
    if len(raw)>MAX_PUBLIC_BYTES:
        raise ValueError("Published edition too large")
    value=json.loads(raw)
    return value if isinstance(value,dict) and value.get("schema")==1 else None

def page_two(league,prior_one,now):
    stamp=now.astimezone(EASTERN).date()
    day=stamp.toordinal()
    names=[safe_name(t.get("name")) for t in league["standings"]] if league else [
        safe_name(t.get("name")) for t in (prior_one.get("standings") or [])] if prior_one else []
    # Respect ESPN team identifiers/order; use a stable fan persona for each club.
    interview=[]
    for i,name in enumerate(names[:10]):
        interview.append({"team":name,
            "fan":FAN_NAMES[i], "quote":FAN_LINES[(day+i*3)%len(FAN_LINES)],
            "fictional":True})
    fixtures,fixture_week=verified_preview(league) if league else ([],None)
    waivers,waiver_note=safe_waivers(league) if league else (
        [],"Fantasy waiver activity unavailable without a recent verified ESPN league report.")
    records=snapshot_standings(league) if league else []
    championship=(
        "The latest ESPN standings list "+records[0]["name"]+" first at "+
        str(records[0]["wins"])+"-"+str(records[0]["losses"])+
        ". The official playoff seedings and clinches must be verified separately."
        if records else "The ESPN standings could not be verified for this edition. No standings claims are made.")
    consolation=(
        "The last listed team in the latest ESPN standings is "+records[-1]["name"]+
        " ("+str(records[-1]["wins"])+"-"+str(records[-1]["losses"])+
        "). This does not establish mathematical elimination or the final Golden Toilet recipient."
        if records else "The Golden Toilet race remains open; current standings verification is unavailable.")
    return {
        "status":"available","publishedAt":now.isoformat(),"editionDateEastern":stamp.isoformat(),
        "sourceAt":league["fetchedAt"] if league else None,
        "writer":BYLINE,"title":"The Daily Sideline · Fixtures & League Notes",
        "fictionNotice":"Professional fictional satire. All fan interviews and quotes are invented; "
                        "they are not interviews with real fans or team owners. "
                        "Fixtures, standings and waiver counts are drawn only from verified ESPN data.",
        "banter":LEAD_LINES[day%len(LEAD_LINES)],
        "closing":SECOND_LINES[(day*3)%len(SECOND_LINES)],
        "fixtureWeek":fixture_week,"fixtures":fixtures,
        "waivers":waivers,"waiverNote":waiver_note,
        "championship":championship,"consolation":consolation,
        "interviews":interview,"teamNamesFromVerifiedSource":bool(league),
        "source":"ESPN fantasy league data" if league else "Historical team names only; current ESPN data unavailable"
    }

def generate(now=None,root=ROOT,previous=None):
    now=(now or dt.datetime.now(dt.timezone.utc)).astimezone(dt.timezone.utc)
    league=validated_league(read_source(root,"league.json"),now)
    previous=previous if isinstance(previous,dict) else {}
    prior_one=previous.get("pageOne")
    if not valid_prior(prior_one,now):
        prior_one=None
    age=now-utc_time(prior_one["publishedAt"]) if prior_one else None
    if prior_one and age<RECORD_TTL and age>=dt.timedelta(0):
        one=prior_one  # Retain every factual word for the entire 48-hour interval.
    elif league:
        one=build_page_one(league,now,root)
    elif prior_one:
        one=prior_one  # Never replace historical facts with guesses.
    else:
        one={"status":"unavailable","notice":"ESPN league data not verified. Historical edition remains available."}
    two=page_two(league,prior_one if prior_one else one,now)
    return {"schema":1,"leagueId":LEAGUE_ID,"season":SEASON,
            "builtAt":now.isoformat(),"pageOne":one,"pageTwo":two}

def main():
    now=dt.datetime.now(dt.timezone.utc)
    try:
        previous=published_previous()
    except (OSError,ValueError,TypeError,urllib.error.URLError,json.JSONDecodeError) as exc:
        print("Prior Gazette edition unavailable:",type(exc).__name__)
        previous=read_source(ROOT,OUTPUT)
    output=generate(now=now,root=ROOT,previous=previous)
    target=ROOT/"data"/OUTPUT
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(output,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    one=output["pageOne"]
    print("Newspaper prepared: Page One",one["status"],"as of",one.get("publishedAt"),
          "; Page Two daily",output["pageTwo"]["editionDateEastern"],
          "; fictional interviews",len(output["pageTwo"]["interviews"]))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
