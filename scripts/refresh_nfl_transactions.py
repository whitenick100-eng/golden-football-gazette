#!/usr/bin/env python3
"""Publish only significant NFL trades/releases/waivers involving verified key players.

"Key" has a transparent, evidence-backed definition:
  * ESPN first-string NFL offensive/defensive starter or starting kicker; OR
  * QB/RB/WR/TE/K on a team in this Gazette's verified ESPN fantasy league.

Both source feeds are checked daily. Descriptions are always sourced to ESPN
transactions; we never infer a completed trade from rumors or render
unmatched backup/practice-squad moves as major news.
"""
import concurrent.futures
import datetime as dt
import json
import re
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/"data/nfl-transactions.json"
URL="https://site.api.espn.com/apis/site/v2/sports/football/nfl/transactions"
NFL_TEAMS="https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams?limit=40"
DEPTH="https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{team}/depthcharts"
FANTASY="https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/2026/segments/0/leagues/1413446022?view=mRoster"
SOURCE_PAGE="https://www.espn.com/nfl/transactions"
HEADERS={"User-Agent":"Mozilla/5.0 (compatible; GoldenFootballGazette/1.0)",
         "Accept":"application/json"}
TRADE=re.compile(r"\btraded\b|\bacquired\b[^.]{0,80}\b(?:via|in)\s+(?:a\s+)?trade\b",re.I)
RELEASE=re.compile(r"\b(?:released?|releases?|cut|cuts|contract terminated)\b",re.I)
WAIVED=re.compile(r"\bwaived\b",re.I)
SKILL_POS={1:"QB",2:"RB",3:"WR",4:"TE",5:"K"}
OFFENSE_KEYS={"qb","rb","hb","fb","te"}
DEFENSE_KEYS={"cb","ss","fs","s","de","dt","nt","lb","mlb","olb","ilb","wlb","slb","lcb","rcb"}

def category(description):
    text=description.strip()
    if not text:return None
    if TRADE.search(text):return "Trade"
    if RELEASE.search(text):return "Released"
    if WAIVED.search(text):return "Waived"
    return None

def actions(description):
    if not isinstance(description,str):return []
    chunks=re.split(r"(?<=[.!?])\s+(?=[A-Z])",description.strip())
    return [(kind," ".join(chunk.split())[:350]) for chunk in chunks
            if (kind:=category(chunk))]

def fetch_json(url):
    req=urllib.request.Request(url,headers=HEADERS)
    with urllib.request.urlopen(req,timeout=22) as res:
        raw=res.read(8_000_001)
    if len(raw)>8_000_000:raise ValueError("ESPN response too large")
    return json.loads(raw)

def normalized(text):
    if not isinstance(text,str):return ""
    # Compare whole names, not substrings/surnames: two Smiths are not the same player.
    plain=unicodedata.normalize("NFKD",text)
    plain="".join(c for c in plain if not unicodedata.combining(c))
    return " ".join(re.findall(r"[a-z0-9]+",plain.casefold()))

def slot_position(value):
    slot=str(value).strip().casefold()
    if slot in ("pk","k"):return "K"
    if slot in ("qb","rb","hb","fb","te"):return {"hb":"RB","fb":"RB"}.get(slot,slot.upper())
    if re.fullmatch(r"wr[1-5]?",slot):return "WR"
    if slot.startswith("cb"):return "CB"
    if slot in ("fs","ss","s"):return "S"
    if slot.endswith("lb") or slot in ("lb","mlb","olb","ilb"):return "LB"
    if slot in ("de","dt","nt","lcb","rcb"):return {"nt":"DT","lcb":"CB","rcb":"CB"}.get(slot,slot.upper())
    return None

def depth_starters(payload):
    if not isinstance(payload,dict) or not isinstance(payload.get("depthchart"),list):
        raise ValueError("Unexpected ESPN NFL depth-chart format")
    offensive=[]; defensive=[]; kickers=[]
    for section in payload["depthchart"]:
        slots=section.get("positions") if isinstance(section,dict) else None
        if not isinstance(slots,dict):continue
        labels={str(k).casefold() for k in slots}
        if "qb" in labels and ({"rb","wr1","te"} & labels):offensive.append(section)
        elif {"cb","cb1","fs","ss","mlb","de","dt","olb"} & labels:defensive.append(section)
        if "pk" in labels or "k" in labels:kickers.append(section)
    # One current starting formation for offense and defense, plus the kicker;
    # do not treat return specialists or second-string backups as starters.
    selected=offensive[:1]+defensive[:1]+kickers[:1]
    if not selected:raise ValueError("No NFL first-string players in depth chart")
    result={}
    for section in selected:
        for slot,info in section["positions"].items():
            position=slot_position(slot)
            if not position or not isinstance(info,dict):continue
            entries=info.get("athletes") or []
            if not isinstance(entries,list) or not entries:continue
            athlete=entries[0]
            if not isinstance(athlete,dict):continue
            name=athlete.get("displayName") or athlete.get("fullName")
            key=normalized(name)
            if len(key)<5 or " " not in key:continue
            result[key]={"name":name[:100],"position":position,
                         "importanceBasis":"ESPN NFL first-string depth chart"}
    return result

def espn_nfl_team_ids(payload):
    sports=payload.get("sports") or []
    if not sports:raise ValueError("No NFL team list")
    leagues=(sports[0] or {}).get("leagues") or []
    if not leagues:raise ValueError("Missing ESPN NFL league roster")
    teams=leagues[0].get("teams") or []
    ids=[]
    for row in teams:
        team=row.get("team") if isinstance(row,dict) else {}
        number=team.get("id") if isinstance(team,dict) else None
        if str(number).isdigit() and str(number) not in ids:ids.append(str(number))
    if len(ids)<28:raise ValueError("ESPN NFL list did not include enough teams")
    return ids

def fantasy_rostered(payload):
    """Supplement depth charts for well-known players no longer on a team's chart."""
    if str(payload.get("id"))!="1413446022" or payload.get("seasonId")!=2026:
        raise ValueError("Fantasy team ownership snapshot is from another league or season")
    teams=payload.get("teams") or []
    if len(teams)!=10:raise ValueError("Incomplete fantasy team roster snapshot")
    owned={}
    for team in teams:
        for item in (team.get("roster") or {}).get("entries") or []:
            player=(item.get("playerPoolEntry") or {}).get("player") or {}
            name=player.get("fullName")
            pos=SKILL_POS.get(player.get("defaultPositionId"))
            key=normalized(name)
            if pos and len(key)>=5 and " " in key:
                owned[key]={"name":name[:100],"position":pos,
                            "importanceBasis":"Rostered in Gridiron Giggles ESPN fantasy league"}
    if not owned:raise ValueError("ESPN did not return any fantasy-owned players")
    return owned

def key_player_index():
    ids=espn_nfl_team_ids(fetch_json(NFL_TEAMS))
    names={}
    checked=0
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        tasks={pool.submit(fetch_json,DEPTH.format(team=tid)):tid for tid in ids}
        for future in concurrent.futures.as_completed(tasks):
            try:
                starters=depth_starters(future.result())
            except (ValueError,TypeError,KeyError,OSError,urllib.error.URLError):
                continue
            names.update(starters);checked+=1
    fantasy_count=0
    try:
        fantasy=fantasy_rostered(fetch_json(FANTASY))
        fantasy_count=len(fantasy)
        # A verified first-string starter is the stronger primary reason.
        for name,details in fantasy.items():
            names.setdefault(name,details)
    except (ValueError,TypeError,KeyError,OSError,urllib.error.URLError) as error:
        print("ESPN fantasy roster supplement unavailable:",type(error).__name__)
    # If most NFL charts are missing, do not silently claim complete coverage.
    if checked<26 and not fantasy_count:
        raise ValueError("Too few ESPN player-importance sources available")
    return names,{"nflDepthChartsVerified":checked,"nflDepthChartsExpected":len(ids),
                  "leagueOwnedPlayersVerified":fantasy_count,
                  "coverageComplete":checked==len(ids)}

def normalize(response,cutoff,today):
    if not isinstance(response,dict) or not isinstance(response.get("transactions"),list):
        raise ValueError("No ESPN transaction list in response")
    result=[];oldest=None
    for group in response["transactions"]:
        if not isinstance(group,dict):continue
        raw_date=group.get("date")
        if not isinstance(raw_date,str):continue
        try:date=dt.date.fromisoformat(raw_date[:10])
        except ValueError:continue
        oldest=min(date,oldest) if oldest else date
        if not (cutoff<=date<=today):continue
        team=group.get("team") or {}
        if not isinstance(team,dict):continue
        team_name=team.get("displayName")
        if not isinstance(team_name,str) or not team_name.strip():continue
        abbr=team.get("abbreviation") if isinstance(team.get("abbreviation"),str) else ""
        logo=None
        for icon in team.get("logos") or []:
            if isinstance(icon,dict) and isinstance(icon.get("href"),str) and icon["href"].startswith("https://a.espncdn.com/"):
                logo=icon["href"];break
        for kind,desc in actions(group.get("description")):
            result.append({"date":date.isoformat(),"team":team_name[:110],
                           "teamAbbr":abbr[:10],"teamLogo":logo,
                           "type":kind,"description":desc})
    return result,oldest

def named_key_moves(moves,key_index):
    """Prefer strict full-name matches; unknown and routine players are excluded."""
    index=[(name,info) for name,info in key_index.items() if len(name)>=5 and " " in name]
    index.sort(key=lambda pair:len(pair[0]),reverse=True)
    hits=[];seen={}
    for move in moves:
        description=" "+normalized(move.get("description"))+" "
        found=[]
        for name,details in index:
            if " "+name+" " in description and name not in found:
                found.append(name)
                # An ESPN trade is often reported by both involved teams.
                # Display it once per named player and transaction day.
                key=(move["date"],move["type"],name) if move["type"]=="Trade" else (
                    move["date"],move["teamAbbr"],move["type"],name)
                if key in seen:
                    prior=hits[seen[key]]
                    if move["team"] not in prior["mentionedTeams"]:
                        prior["mentionedTeams"].append(move["team"])
                    continue
                item={**move,"playerName":details["name"],
                      "position":details["position"],
                      "importanceBasis":details["importanceBasis"],
                      "mentionedTeams":[move["team"]]}
                seen[key]=len(hits);hits.append(item)
        # A sentence mentioning only unknown/nonstarter players is not major news.
    hits.sort(key=lambda m:(m["date"],m["type"]=="Trade",m["team"],m["playerName"]),reverse=True)
    return hits

def fetch(page=1,limit=100):
    query=urllib.parse.urlencode({"limit":limit,"page":page})
    return fetch_json(URL+"?"+query)

def build(now=None,fetcher=fetch,key_provider=key_player_index):
    now=now or dt.datetime.now(dt.timezone.utc)
    today=now.astimezone(ZoneInfo("America/New_York")).date()
    cutoff=today-dt.timedelta(days=7)
    raw=[];seen=set();oldest_reached=False;covered_dates=[];pages=0
    for page in range(1,13):
        response=fetcher(page=page,limit=100)
        if not isinstance(response,dict):raise ValueError("Invalid ESPN transaction page")
        groups=response.get("transactions") or []
        if not groups and page==1:raise ValueError("ESPN returned no transactions")
        matches,oldest=normalize(response,cutoff,today)
        for item in matches:
            key=(item["date"],item["teamAbbr"],item["type"],item["description"])
            if key not in seen:
                seen.add(key);raw.append(item)
        pages=page
        if oldest:covered_dates.append(oldest)
        if oldest and oldest<cutoff:oldest_reached=True;break
        if isinstance(response.get("pageCount"),int) and response["pageCount"]<=page:break
        if not groups:break
    if not covered_dates:raise ValueError("ESPN returned no parseable transaction dates")
    index,coverage=key_provider()
    if not isinstance(index,dict) or not index:
        raise ValueError("Could not verify key NFL players from ESPN")
    featured=named_key_moves(raw,index)
    return {
        "status":"available","keyOnly":True,"filter":"verified-key-players-only",
        "fetchedAt":now.isoformat(),"source":"ESPN NFL transactions",
        "sourceUrl":SOURCE_PAGE,
        "windowStart":cutoff.isoformat(),"windowEnd":today.isoformat(),
        "coverageComplete":oldest_reached,"playerCoverage":coverage,
        "pagesChecked":pages,"lastSourceDate":min(covered_dates).isoformat(),
        "allESPNMovesChecked":len(raw),
        "total":len(featured),
        "trades":sum(m["type"]=="Trade" for m in featured),
        "releases":sum(m["type"] in ("Released","Waived") for m in featured),
        "moves":featured[:30],
        "note":"This is a selective wire of ESPN-confirmed trade/release/waiver actions involving ESPN first-string NFL depth-chart players or players rostered in Gridiron Giggles. Routine backup and practice-squad moves are omitted. Historical starters no longer on a depth chart can be missed. Verify transactions directly at ESPN.",
    }

def main():
    OUT.parent.mkdir(parents=True,exist_ok=True)
    try:
        data=build()
        OUT.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print("KEY NFL ROSTER WIRE:",data["total"],"featured moves from",data["allESPNMovesChecked"],
              "ESPN actions; depth charts",data["playerCoverage"]["nflDepthChartsVerified"],
              "league-owned",data["playerCoverage"]["leagueOwnedPlayersVerified"])
        for m in data["moves"][:8]:
            print(m["date"],m["type"],m["playerName"],m["team"],m["importanceBasis"])
    except (ValueError,OSError,TypeError,json.JSONDecodeError,urllib.error.URLError) as exc:
        print("Key NFL transaction verification unavailable:",type(exc).__name__,str(exc)[:140])
        if OUT.is_file():
            print("Retaining previously verified snapshot; site suppresses unfiltered historical data")
        else:
            OUT.write_text(json.dumps({
                "status":"unavailable","keyOnly":False,"source":"ESPN NFL transactions",
                "sourceUrl":SOURCE_PAGE,
                "message":"Verified key-player transactions unavailable from ESPN.",
            },indent=2)+"\n",encoding="utf-8")

if __name__=="__main__":
    main()
