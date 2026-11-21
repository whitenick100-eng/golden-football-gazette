#!/usr/bin/env python3
"""Daily verified NFL trades, releases and waivers from ESPN's NFL transactions API.

Only explicit action phrases in ESPN's transaction descriptions qualify;
practice-squad deletions, signings, rumors, waivers claimed by other teams,
and roster 'inactive' notices are not misreported as releases.
"""
import datetime as dt
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/"data/nfl-transactions.json"
URL="https://site.api.espn.com/apis/site/v2/sports/football/nfl/transactions"
SOURCE_PAGE="https://www.espn.com/nfl/transactions"
HEADERS={"User-Agent":"Mozilla/5.0 (compatible; GoldenFootballGazette/1.0)","Accept":"application/json"}
TRADE=re.compile(r"\btraded\b|\bacquired\b[^.]{0,80}\b(?:via|in)\s+(?:a\s+)?trade\b",re.I)
RELEASE=re.compile(r"\b(?:released?|releases?|cut|cuts|contract terminated)\b",re.I)
WAIVED=re.compile(r"\b(?:waived?)\b",re.I)

def category(description):
    """Only positive literal actions; avoid inferred releases from transactions."""
    text=description.strip()
    if not text:return None
    if TRADE.search(text):return "Trade"
    if RELEASE.search(text):return "Released"
    if WAIVED.search(text):return "Waived"
    return None

def actions(description):
    """ESPN often combines separate player actions into one description."""
    if not isinstance(description,str):return []
    # Safe split on sentence boundaries; preserve word-for-word short ESPN summary.
    chunks=re.split(r"(?<=[.!?])\s+(?=[A-Z])",description.strip())
    out=[]
    for chunk in chunks:
        move=category(chunk)
        if move:
            # Keep the source's full detail and original named players.
            out.append((move, " ".join(chunk.split())[:350]))
    return out

def normalize(response, cutoff, today):
    if not isinstance(response,dict) or not isinstance(response.get("transactions"),list):
        raise ValueError("No ESPN transaction list in response")
    result=[]
    oldest=None
    for group in response["transactions"]:
        if not isinstance(group,dict):continue
        raw_date=group.get("date")
        if not isinstance(raw_date,str):continue
        try:
            date=dt.date.fromisoformat(raw_date[:10])
        except ValueError:
            continue
        oldest=min(date,oldest) if oldest else date
        if not (cutoff<=date<=today):continue
        team=group.get("team") or {}
        if not isinstance(team,dict):continue
        team_name=team.get("displayName")
        if not isinstance(team_name,str) or not team_name.strip():continue
        team_abbr=team.get("abbreviation") if isinstance(team.get("abbreviation"),str) else ""
        logo=None
        for icon in team.get("logos") or []:
            if isinstance(icon,dict) and isinstance(icon.get("href"),str) and icon["href"].startswith("https://a.espncdn.com/"):
                logo=icon["href"];break
        for kind,desc in actions(group.get("description")):
            result.append({"date":date.isoformat(),"team":team_name[:110],
                           "teamAbbr":team_abbr[:10], "teamLogo":logo,
                           "type":kind,"description":desc})
    return result,oldest

def fetch(page=1, limit=100):
    query=urllib.parse.urlencode({"limit":limit,"page":page})
    request=urllib.request.Request(URL+"?"+query,headers=HEADERS)
    with urllib.request.urlopen(request,timeout=25) as resp:
        payload=resp.read(4_000_000+1)
    if len(payload)>4_000_000:raise ValueError("ESPN NFL transactions response exceeds size limit")
    return json.loads(payload)

def build(now=None,fetcher=fetch):
    now=now or dt.datetime.now(dt.timezone.utc)
    today=now.astimezone(ZoneInfo('America/New_York')).date()
    cutoff=today-dt.timedelta(days=7)
    moves=[]
    seen=set()
    oldest_reached=False
    covered_dates=[]
    pages=0
    for p in range(1,13):
        response=fetcher(page=p,limit=100)
        if not isinstance(response,dict):
            raise ValueError("Invalid ESPN transaction page")
        page_records=response.get("transactions") or []
        if not page_records and p==1:
            raise ValueError("ESPN returned no transactions")
        page_moves,oldest=normalize(response,cutoff,today)
        for record in page_moves:
            key=(record["date"],record["teamAbbr"],record["type"],record["description"])
            if key not in seen:
                seen.add(key);moves.append(record)
        pages=p
        if oldest:covered_dates.append(oldest)
        if oldest and oldest<cutoff:
            oldest_reached=True;break
        page_count=response.get("pageCount")
        if isinstance(page_count,int) and page_count<=p:break
        if not page_records:break
    moves.sort(key=lambda t:(t["date"],t["team"],t["description"]),reverse=True)
    if not covered_dates:
        raise ValueError("ESPN returned no parseable transaction dates")
    return {
        "status":"available",
        "fetchedAt":now.isoformat(),"source":"ESPN NFL transactions",
        "sourceUrl":SOURCE_PAGE,
        "windowStart":cutoff.isoformat(),"windowEnd":today.isoformat(),
        "coverageComplete":oldest_reached,
        "pagesChecked":pages,"lastSourceDate":min(covered_dates).isoformat(),
        "total":len(moves),"trades":sum(m["type"]=="Trade" for m in moves),
        "releases":sum(m["type"] in ("Released","Waived") for m in moves),
        "moves":moves[:150],
        "note":"ESPN transaction descriptions; Waived and Released are separate move types. Records are sourced from ESPN, not rumors. Some trades may appear for both clubs; absence of a move does not prove no move occurred.",
    }

def main():
    OUT.parent.mkdir(parents=True,exist_ok=True)
    try:
        data=build()
        OUT.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print("NFL transaction desk:",data["total"],"verified movements",
              data["trades"],"trade entries",data["releases"],"release/waiver entries",
              "pages",data["pagesChecked"],"complete window",data["coverageComplete"])
    except (ValueError,OSError,TypeError,json.JSONDecodeError,urllib.error.URLError) as exc:
        print("ESPN NFL transactions temporarily unavailable:",type(exc).__name__,str(exc)[:160])
        if OUT.exists():
            print("Keeping previously fetched transactions with original timestamp")
        else:
            OUT.write_text(json.dumps({
                "status":"unavailable","source":"ESPN NFL transactions","sourceUrl":SOURCE_PAGE,
                "message":"No verified trade and release transactions available from ESPN."
            },indent=2)+"\n",encoding="utf-8")

if __name__=="__main__":
    main()
