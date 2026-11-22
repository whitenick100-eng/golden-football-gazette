#!/usr/bin/env python3
"""ESPN NFL Key Injury Watch: verified first-string QB/RB/WR/TE/K who are out.

Join ESPN's current team depth charts to ESPN injury records by athlete ID,
not just injury position or assumed 'star' status. ESPN limits its league-wide
injury listing, so also inspect injury records attached to depth-chart starters.
Do not classify Questionable, Doubtful, DNP, or old OUT tags as ruled out today.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/nfl-injuries.json"
SOURCE = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/injuries"
DEPTH_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{team_id}/depthcharts"
SOURCE_PAGE = "https://www.espn.com/nfl/injuries"
OFFICIAL_REPORT = "https://www.nfl.com/injuries/"
HEADERS = {"User-Agent": "Mozilla/5.0 GoldenFootballGazette/1.0",
           "Accept": "application/json"}
WATCHED_POSITIONS = {"QB", "RB", "WR", "TE", "K"}
PRIMARY_SLOTS = {"qb":"QB", "rb":"RB", "hb":"RB", "te":"TE", "pk":"K", "k":"K"}
OUT_STATES = {"out", "ruled out"}
RESERVE_STATES = {"ir", "ir r", "injured reserve", "reserve injured",
                  "reserve ir", "pup", "reserve pup",
                  "physically unable to perform"}
MAX_OUT_AGE_DAYS = 8


def label(value):
    if isinstance(value, dict):
        for name in ("displayName","description","name","abbreviation","shortName"):
            if isinstance(value.get(name), str) and value[name].strip():
                return " ".join(value[name].split())[:110]
    return " ".join(value.split())[:110] if isinstance(value, str) else ""


def clean_name(value):
    return re.sub(r"[^a-z0-9]", "", label(value).casefold())


def state(value):
    norm=" ".join(label(value).casefold().replace("_"," ").replace("-"," ").split())
    if norm in OUT_STATES:return "out"
    if norm in RESERVE_STATES:return "reserve"
    return None


def parse_date(value):
    if not isinstance(value,str):return None
    try:
        parsed=dt.datetime.fromisoformat(value.replace("Z","+00:00"))
        if parsed.tzinfo is None:return None
        return parsed.astimezone(dt.timezone.utc)
    except ValueError:
        return None


def player_id(athlete):
    if not isinstance(athlete,dict):return None
    value=athlete.get("id")
    if isinstance(value,(int,str)) and str(value).isdigit():
        return str(value)
    # ESPN's league injuries endpoint sometimes omits athlete.id but includes
    # the exact ESPN athlete number in the canonical playercard link.
    for link in athlete.get("links") or []:
        if not isinstance(link,dict):continue
        url=link.get("href") or ""
        if not isinstance(url,str):continue
        parsed=urlparse(url)
        if parsed.scheme!="https" or parsed.hostname!="www.espn.com":continue
        parts=parsed.path.split("/")
        if "id" in parts:
            pos=parts.index("id")
            if pos+1<len(parts) and parts[pos+1].isdigit():
                return parts[pos+1]
    return None


def slot_position(slot):
    key=str(slot).casefold().strip()
    if key in PRIMARY_SLOTS:return PRIMARY_SLOTS[key]
    if re.fullmatch(r"wr[1-5]?",key):return "WR"
    return None


def first_string(chart):
    """Return current first-listed players for the starting offensive formation."""
    if not isinstance(chart,dict) or not isinstance(chart.get("depthchart"),list):
        raise ValueError("Unrecognized ESPN NFL depthchart response")
    season=chart.get("season") or {}
    if season.get("year") is not None and int(season["year"])!=dt.datetime.now(dt.timezone.utc).year:
        raise ValueError("Depthchart returned a different NFL season")
    sections=chart["depthchart"]
    offense=[]
    special=[]
    for section in sections:
        positions=section.get("positions")
        if not isinstance(positions,dict):continue
        keys={str(key).casefold() for key in positions}
        if {"qb","rb","wr1","te"} & keys:
            offense.append(section)
        if "pk" in keys or "k" in keys:
            special.append(section)
    # ESPN labels its base offensive formation e.g. "3WR 1TE". Prefer the
    # formation with the most offensive starting positions, not reserve charts.
    offense.sort(key=lambda sec:sum(bool(slot_position(k)) for k in sec["positions"]), reverse=True)
    selected=offense[:1]+special[:1]
    if not selected:
        raise ValueError("No first-string offensive or kicker positions in ESPN depthchart")
    starters={}
    for section in selected:
        for slot,pos in section["positions"].items():
            position=slot_position(slot)
            if position is None:continue
            entries=pos.get("athletes") if isinstance(pos,dict) else None
            if not isinstance(entries,list) or not entries:continue
            athlete=entries[0]  # first on ESPN's position-specific depth chart
            if not isinstance(athlete,dict):continue
            id_=player_id(athlete)
            name=label(athlete.get("displayName"))
            if not id_ or not name:continue
            if id_ not in starters:
                starters[id_]={"name":name,"position":position,"starterSlot":str(slot).upper(),
                               "depthRank":1,"athleteId":id_,
                               "embeddedInjuries":athlete.get("injuries") or []}
    return starters


def recent_out(record,now):
    category=state(record.get("status"))
    when=parse_date(record.get("date"))
    if category=="out":
        # Game-week OUT is not automatically true indefinitely. A historical
        # "Out" tag older than eight days needs fresh reconfirmation.
        if not when:return False
        age=(now-when).total_seconds()/86400
        return -1 <= age <= MAX_OUT_AGE_DAYS
    return category=="reserve"


def condition(record):
    details=record.get("details")
    if isinstance(details,dict):
        for key in ("injury","bodyPart","detail","description"):
            value=label(details.get(key))
            if value and value.casefold() not in ("out","injured reserve"):return value
    injury=label(record.get("injury"))
    return injury or None


def normalize(payload, depthcharts, now=None, week=None):
    """Join currently-listed first-string players with ESPN's direct injury statuses."""
    now=now or dt.datetime.now(dt.timezone.utc)
    if not isinstance(payload,dict) or not isinstance(payload.get("injuries"),list):
        raise ValueError("ESPN injury groups are missing")
    groups=payload["injuries"]
    if not groups:raise ValueError("ESPN returned no NFL team groups")
    year=(payload.get("season") or {}).get("year")
    if year is not None and int(year)!=now.year:
        raise ValueError("ESPN returned a different NFL season")
    if not isinstance(depthcharts,dict) or not depthcharts:
        raise ValueError("No verified ESPN first-string depthcharts")
    results=[]
    checked=0
    total_first_string=0
    groups_seen=set()
    for group in groups:
        if not isinstance(group,dict):continue
        team=group.get("team") if isinstance(group.get("team"),dict) else group
        team_id=str(team.get("id") or "").strip()
        team_name=label(team.get("displayName") or team.get("name"))
        if not team_id or not team_name:continue
        groups_seen.add(team_id)
        if team_id not in depthcharts:continue
        current=first_string(depthcharts[team_id])
        checked+=1
        total_first_string+=len(current)
        raw=group.get("injuries") if isinstance(group.get("injuries"),list) else []
        by_id={}
        by_name={}
        for entry in raw:
            if not isinstance(entry,dict):continue
            person=entry.get("athlete") or {}
            if not isinstance(person,dict):continue
            id_=player_id(person)
            if id_:by_id.setdefault(id_,[]).append(entry)
            named=clean_name(person.get("displayName") or person.get("fullName"))
            if named:by_name.setdefault(named,[]).append(entry)
        injured=[]
        for id_,start in current.items():
            # The 25-entry ESPN league endpoint can omit an injured starter.
            # Depthchart athlete injuries are an independent ESPN source.
            records=[]
            for item in start["embeddedInjuries"]:
                if isinstance(item,dict):
                    records.append((item,"ESPN starter depth chart"))
            for item in by_id.get(id_) or by_name.get(clean_name(start["name"]),[]) or []:
                records.append((item,"ESPN injury listing"))
            if not records:continue
            dated=sorted(records,key=lambda item:(
                parse_date(item[0].get("date")) or dt.datetime.min.replace(tzinfo=dt.timezone.utc),
                item[1]=="ESPN injury listing"),reverse=True)
            entry,source=dated[0]
            if not recent_out(entry,now):
                continue
            reported=label(entry.get("status"))
            out_type=state(reported)
            # ESPN's summary listing may omit the body-part detail while
            # the corresponding athlete's depthchart record still has it.
            # Preserve the source's reported detail without inferring one.
            injury_detail=condition(entry)
            if not injury_detail:
                for other,_source in records:
                    injury_detail=condition(other)
                    if injury_detail:break
            injured.append({
                "name":start["name"],"athleteId":id_,"position":start["position"],
                "depthRank":1,"starterSlot":start["starterSlot"],
                "injury":injury_detail,
                "reportedStatus":reported,"gameStatus":None,"practiceStatus":None,
                "outType":out_type,
                "reportDate":entry.get("date") if parse_date(entry.get("date")) else None,
                "verificationSource":source,
                "playerUrl":"https://www.espn.com/nfl/player/_/id/"+id_,
            })
        if injured:
            injured.sort(key=lambda p:(
                0 if p["outType"]=="out" else 1,
                {"QB":0,"RB":1,"WR":2,"TE":3,"K":4}.get(p["position"],9),p["name"].casefold()))
            results.append({"teamId":team_id,"name":team_name,
                            "abbreviation":label(team.get("abbreviation")),
                            "players":injured})
    if not checked:raise ValueError("No ESPN depthcharts matched any NFL injury team")
    results.sort(key=lambda r:r["name"].casefold())
    total=sum(len(t["players"]) for t in results)
    failed=sorted(set(groups_seen)-set(depthcharts),key=lambda x:int(x) if x.isdigit() else 999)
    return {
        "season":now.year,"week":week,"fetchedAt":now.isoformat(),
        "source":"ESPN NFL injury listing + ESPN starting depth charts",
        "sourceUrl":SOURCE_PAGE,"officialNflReportUrl":OFFICIAL_REPORT,
        "positions":sorted(WATCHED_POSITIONS),"filter":"first-string-out-only",
        "outCount":sum(p["outType"]=="out" for t in results for p in t["players"]),
        "reserveCount":sum(p["outType"]=="reserve" for t in results for p in t["players"]),
        "teamCount":len(results),"playerCount":total,
        "depthChartTeamCount":checked,"injuryTeamCount":len(groups_seen),
        "coverageComplete":checked==len(groups_seen),
        "teamsNotVerified":failed,
        "verifiedStarterCount":total_first_string,
        "coverageNote":"ESPN first-string QB, RB, WR (multiple slots), TE and K only. ESPN-listed Out must be reported within eight days; IR/PUP are listed separately as unavailable. Questionable/Doubtful/backup players are excluded. Some ESPN injury entries may be missing or delayed. Verify game-day inactives and final designations with NFL.com.",
        "teams":results,
    }


def get_json(url):
    req=urllib.request.Request(url,headers=HEADERS)
    with urllib.request.urlopen(req,timeout=18) as res:
        content=res.read(18_000_000+1)
    if len(content)>18_000_000:raise ValueError("ESPN feed exceeds maximum size")
    return json.loads(content)


def fetch_depthchart(team_id):
    if not str(team_id).isdigit() or not 1<=int(team_id)<=99:
        raise ValueError("Unexpected ESPN team ID")
    return get_json(DEPTH_URL.format(team_id=team_id))


def fetch_all_depthcharts(team_ids):
    depthcharts={}
    with ThreadPoolExecutor(max_workers=8) as executor:
        jobs={executor.submit(fetch_depthchart,id_):id_ for id_ in team_ids}
        for future in as_completed(jobs):
            team_id=jobs[future]
            try:
                chart=future.result()
                first_string(chart)  # Reject empty/unexpected responses.
                depthcharts[team_id]=chart
            except (ValueError,TypeError,OSError,urllib.error.URLError) as exc:
                print(f"Depthchart for NFL team {team_id} not verified: {type(exc).__name__}")
    return depthcharts


def current_week():
    p=ROOT/"data/nfl-week.json"
    try:
        data=json.loads(p.read_text(encoding="utf-8"))
        if data.get("season")==dt.datetime.now(dt.timezone.utc).year:
            number=data.get("week")
            if isinstance(number,int) and 1<=number<=22:return number
    except (OSError,ValueError,TypeError):pass
    return None


def main():
    OUT.parent.mkdir(parents=True,exist_ok=True)
    try:
        source=get_json(SOURCE)
        teams=source.get("injuries")
        if not isinstance(teams,list) or not teams:
            raise ValueError("ESPN injury feed was empty")
        ids=[]
        for row in teams:
            if not isinstance(row,dict):continue
            club=row.get("team") if isinstance(row.get("team"),dict) else row
            value=str(club.get("id") or "")
            if value.isdigit() and value not in ids:ids.append(value)
        chart=fetch_all_depthcharts(ids)
        report=normalize(source,chart,week=current_week())
        OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print("ESPN verified first-string OUT watch:",
              report["playerCount"],"players","("+str(report["outCount"])+" OUT,",
              str(report["reserveCount"])+" IR/PUP),",report["depthChartTeamCount"],
              "of",report["injuryTeamCount"],"NFL depth charts confirmed")
    except (OSError,ValueError,TypeError,urllib.error.URLError) as exc:
        print("ESPN first-string injury verification unavailable:",type(exc).__name__)
        if OUT.is_file():
            print("Retaining earlier ESPN snapshot with its original verification timestamp")
        else:
            OUT.write_text(json.dumps({
                "status":"unavailable","source":"ESPN NFL starter injury feed",
                "message":"First-string players and out statuses could not be verified",
                "sourceUrl":SOURCE_PAGE,"officialNflReportUrl":OFFICIAL_REPORT,
            },indent=2)+"\n",encoding="utf-8")


if __name__=="__main__":
    main()
