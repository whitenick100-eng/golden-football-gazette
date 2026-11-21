#!/usr/bin/env python3
"""Generate fact-based daily newspaper briefs and the weekly playoff picture.

This publisher contains NO generative AI and requires no API key. Only
timestamped ESPN/NFL facts are described; owner-approved AI editorials remain
a separate GitHub pull-request workflow.
"""
import datetime as dt
import json
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/"data/weekly-features.json"
LOCAL=ZoneInfo("America/New_York")
FRESH_HOURS=48
WINNERS={"HOME","AWAY","TIE"}
PLAYOFF={"WINNERS_BRACKET"}
CONSOLATION={"LOSERS_BRACKET","CONSOLATION","TOILET_BOWL"}

def source(path, now, league=False):
    p=ROOT/"data"/path
    if not p.is_file():
        return None
    try:
        data=json.loads(p.read_text(encoding="utf-8"))
        if data.get("status")=="unavailable":return None
        time=dt.datetime.fromisoformat(data["fetchedAt"].replace("Z","+00:00"))
        if time.tzinfo is None:return None
        elapsed=(now-time.astimezone(dt.timezone.utc)).total_seconds()/3600
        if not -0.05<=elapsed<=FRESH_HOURS:return None
        if league and (str(data.get("leagueId"))!="1413446022" or data.get("season")!=2026
                       or len(data.get("standings") or [])!=10):
            return None
        return data
    except (ValueError,TypeError,KeyError,AttributeError,OSError):
        return None

def record(team):
    return f"{team.get('wins','?')}-{team.get('losses','?')}"

def playoff_picture(league):
    if not league:return {"status":"unavailable","message":"ESPN standings unavailable"}
    standings=league["standings"]
    settings=league.get("playoffSettings") or {}
    count=settings.get("playoffTeamCount")
    verified=isinstance(count,int) and 2<=count<=len(standings)
    # The owner supplied a four-team playoff format for this league.
    # If the ESPN settings endpoint fails, show it as owner-reported only.
    if not verified:count=4
    current=league.get("currentMatchupPeriod")
    regular=settings.get("regularSeasonMatchupPeriods")
    seed_rule=settings.get("playoffSeedingRule")
    # ESPN settings may seed by cumulative fantasy points rather than wins.
    # Respect that configured rule; do NOT reuse the wins-sorted standings
    # for a TOTAL_POINTS_SCORED playoff field.
    sorted_teams=list(standings)
    seeding_verified=True
    if seed_rule=="TOTAL_POINTS_SCORED":
        if all(isinstance(t.get("pointsFor"),(int,float)) for t in standings):
            sorted_teams.sort(key=lambda t:(-t["pointsFor"],-(t.get("wins") or 0),t["name"]))
        else:
            seeding_verified=False
    elif seed_rule=="WINNING_PCT":
        sorted_teams.sort(key=lambda t:(
            -(t.get("wins",0)/max(1,(t.get("wins",0)+t.get("losses",0)+t.get("ties",0)))),
            -(t.get("pointsFor") or 0),t["name"]))
    elif seed_rule=="H2H_RECORD":
        sorted_teams.sort(key=lambda t:(-(t.get("wins") or 0),t.get("losses") or 0,
                                       -(t.get("pointsFor") or 0),t["name"]))
    else:
        # Official ESPN seeding rule absent or unhandled. Sorting is purely
        # a standings snapshot, not verified playoff seeding.
        seeding_verified=False
    ordered=[{
        "seed":i+1,"teamId":t["teamId"],"name":t["name"],
        "record":record(t),"logo":t.get("logo"),
        "pointsFor":t.get("pointsFor"),
    } for i,t in enumerate(sorted_teams)]
    known=[x for x in league.get("matchups",[]) if
           isinstance(x.get("week"),int) and
           (current is None or x["week"]==current) and
           x.get("home",{}).get("teamId") and x.get("away",{}).get("teamId")]
    official_champ=[{
        "week":g["week"],"home":g["home"].get("name"),
        "away":g["away"].get("name"),"winner":g.get("winner"),
    } for g in known if g.get("playoffTierType") in PLAYOFF]
    official_cons=[{
        "week":g["week"],"home":g["home"].get("name"),
        "away":g["away"].get("name"),"winner":g.get("winner"),
    } for g in known if g.get("playoffTierType") in CONSOLATION]
    if official_champ:
        pairing_kind="espn-listed"
        championship=official_champ
        consolation=official_cons
        title="ESPN-listed postseason matchup pairings"
    else:
        pairing_kind="provisional"
        # Only 4-team semi-final pairing is a common bracket approximation,
        # not a claim about the league's official ESPN playoff matchups.
        championship=[]
        if count==4:
            championship=[
                {"home":ordered[0]["name"],"away":ordered[3]["name"],
                 "homeSeed":1,"awaySeed":4},
                {"home":ordered[1]["name"],"away":ordered[2]["name"],
                 "homeSeed":2,"awaySeed":3},
            ]
        consolation=[]
        title="Projected playoff field based on current standings"
    return {
        "status":"available","type":pairing_kind,"title":title,
        "source":"ESPN fantasy league standings and playoff settings",
        "fetchedAt":league["fetchedAt"],
        "currentWeek":current,"regularSeasonWeeks":regular,
        "playoffTeamCount":count,
        "formatVerifiedByESPN":verified,"seedingRule":seed_rule,
        "seedingOrderFromSettings":seeding_verified and verified,
        "contenders":ordered[:count],
        "outsideCurrentField":ordered[count:],
        "championshipPairings":championship,"consolationPairings":consolation,
        "caveat":(
            "ESPN-reported postseason pairings, not a mathematical clinch or elimination analysis."
            if pairing_kind=="espn-listed" else
            "These seedings are provisional standings positions; bracket pairings are an "
            "illustration only, not the official ESPN schedule. ESPN tiebreakers may change exact seed order. Teams outside the current "
            "field are NOT necessarily eliminated. Check ESPN for clinches and tiebreakers."
        ),
    }

def story(tag, headline, body, source_name):
    return {"tag":tag,"headline":headline,"body":body,"source":source_name}

def report(league,nfl,injuries,leaders,now):
    items=[]
    if league:
        ordered=league["standings"]
        first=ordered[0]
        items.append(story("Fantasy League","League leader sets the pace",
            f"{first['name']} leads the latest ESPN league standings at {record(first)}. "
            "Playoff positions remain provisional until the official bracket is established.",
            "ESPN fantasy league standings"))
        games=league.get("matchups") or []
        decided={}
        upcoming={}
        for g in games:
            w=g.get("week")
            if not isinstance(w,int) or not g.get("home",{}).get("name") or not g.get("away",{}).get("name"):continue
            if g.get("winner") in WINNERS:
                decided.setdefault(w,[]).append(g)
            elif w==league.get("currentMatchupPeriod"):
                upcoming.setdefault(w,[]).append(g)
        if decided:
            week=max(decided)
            rows=decided[week]
            completed=[]
            for g in rows:
                home,away=g["home"],g["away"]
                a,h=away.get("points"),home.get("points")
                if isinstance(a,(int,float)) and isinstance(h,(int,float)):
                    completed.append(f"{away['name']} {a:.2f} – {home['name']} {h:.2f}")
            if completed and len(rows)>=len(ordered)//2:
                items.append(story("Fantasy Recap",f"Week {week} completed matchups",
                    "; ".join(completed[:5])+". These are ESPN-reported final fantasy team totals.",
                    "ESPN fantasy matchups"))
        if upcoming:
            w=max(upcoming)
            pairs=[f"{g['away']['name']} vs. {g['home']['name']}" for g in upcoming[w][:5]]
            items.append(story("Fantasy Preview",f"Week {w} matchup slate",
                "The reported upcoming contests include: "+"; ".join(pairs)+
                ". No winner is predicted by this factual bulletin.",
                "ESPN fantasy matchups"))
    if nfl:
        week=nfl.get("week")
        final=[g for g in nfl.get("games",[]) if g.get("completed")]
        future=[g for g in nfl.get("games",[]) if not g.get("completed")]
        if final:
            games=[]
            for g in final[:5]:
                a,h=g.get("away") or {},g.get("home") or {}
                if a.get("score") is None or h.get("score") is None:continue
                games.append(f"{a.get('name')} {a['score']} – {h.get('name')} {h['score']}")
            if games:
                items.append(story("NFL Results",f"NFL Week {week} final scores",
                    "ESPN reports these completed games: "+"; ".join(games)+".",
                    "ESPN NFL scoreboard"))
        if future:
            summaries=[]
            for g in future[:5]:
                a,h=g.get("away") or {},g.get("home") or {}
                try:
                    t=dt.datetime.fromisoformat(g["date"].replace("Z","+00:00")).astimezone(LOCAL)
                    when=t.strftime("%a %b %d, %I:%M %p ET").replace(" 0"," ")
                except (ValueError,KeyError,TypeError):
                    when="kickoff not verified"
                summaries.append(f"{a.get('name')} at {h.get('name')} ({when})")
            items.append(story("NFL Preview",f"Week {week} kickoff guide",
                "Upcoming ESPN-listed fixtures include: "+"; ".join(summaries)+
                ". Dates and times are subject to league changes.","ESPN NFL scoreboard"))
    if leaders:
        p=leaders["players"]
        if p:
            top=p[0]
            items.append(story("Player Performance",f"Week {leaders['week']} fantasy scoring leader",
                f"{top['name']} scored {top['points']:.2f} ESPN fantasy points "
                f"while on the {top['fantasyTeam'] or 'a league'} roster. "
                "The leaderboard includes rostered players only, including benches.",
                "ESPN fantasy mBoxscore"))
    if injuries:
        status={}
        for t in injuries.get("teams",[]):
            for p in t.get("players",[]):
                name=(p.get("gameStatus") or p.get("reportedStatus") or "").strip()
                status[name]=status.get(name,0)+1
        lines=[f"{n}: {status[n]}" for n in ("Out","Doubtful","Questionable") if n in status]
        if lines:
            items.append(story("Injury Desk","Latest ESPN-reported injury statuses",
                "; ".join(lines)+". These are ESPN injury-listing designations, not "
                "necessarily official NFL practice/game statuses. Consult the NFL injury report.",
                "ESPN NFL injury listing"))
    return items[:8]

def generate(now=None):
    now=now or dt.datetime.now(dt.timezone.utc)
    league=source("league.json",now,league=True)
    nfl=source("nfl-week.json",now)
    injuries=source("nfl-injuries.json",now)
    leaders=source("top-performers.json",now)
    if leaders and not (isinstance(leaders.get("players"),list) and len(leaders["players"])==5):
        leaders=None
    if league and leaders and leaders.get("season")!=league.get("season"):
        leaders=None
    stories=report(league,nfl,injuries,leaders,now)
    return {
        "status":"available" if stories else "unavailable",
        "generatedAt":now.isoformat(),
        "editionDateEastern":now.astimezone(LOCAL).date().isoformat(),
        "editorialType":"automated verified-data brief; not AI-generated opinion",
        "coverage":stories,
        "playoffs":playoff_picture(league),
        "sources":{
            "espnLeague":league.get("fetchedAt") if league else None,
            "espnNFL":nfl.get("fetchedAt") if nfl else None,
            "espnInjuries":injuries.get("fetchedAt") if injuries else None,
            "espnPlayerBoxscore":leaders.get("fetchedAt") if leaders else None,
        },
    }

if __name__=="__main__":
    OUT.parent.mkdir(parents=True,exist_ok=True)
    data=generate()
    OUT.write_text(json.dumps(data,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print("Published daily factual briefs:",len(data["coverage"]),
          "playoff picture:",data["playoffs"]["status"])
