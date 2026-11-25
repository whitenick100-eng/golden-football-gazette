#!/usr/bin/env python3
"""Build an honest, read-only per-section Gazette publication audit.

A successful GitHub Actions build != a successful Pages deployment or proof that
every section changed. Compare approved, source-backed semantic content with the
last published section audit. Never invent scores or approve an editorial.
"""
import datetime as dt
import hashlib
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/daily-update-report.json"
PREVIOUS_URL = "https://whitenick100-eng.github.io/golden-football-gazette/data/daily-update-report.json"
EASTERN = ZoneInfo("America/New_York")
KEYS = (
    "lead_story", "espn_matchups", "playoffs", "consolation",
    "football_desk", "from_editor", "nfl_review_preview",
    "page_one", "page_two", "key_starters_out", "waivers",
)
LABELS = {
    "lead_story":"Lead Story", "espn_matchups":"ESPN Fantasy Matchup Center",
    "playoffs":"Playoff Picture", "consolation":"Consolation Ladder",
    "football_desk":"Today's Football Desk", "from_editor":"From the Editor",
    "nfl_review_preview":"NFL Week in Review and Preview",
    "page_one":"Page One — League Report",
    "page_two":"Page Two — Fixtures and League Notes",
    "key_starters_out":"NFL Key Starters OUT / Questionable / Doubtful / IR",
    "waivers":"NFL Waivers and Roster Wire",
}
UA = {"User-Agent":"Gazette-Daily-Section-Audit/1.0", "Accept":"application/json"}


def read_json(path, root=ROOT):
    try:
        file = root / path
        if file.stat().st_size > 1_000_000:
            return None
        data = json.loads(file.read_text("utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, ValueError, TypeError):
        return None


def when(value):
    try:
        date = dt.datetime.fromisoformat(value.replace("Z","+00:00"))
        return date.astimezone(dt.timezone.utc) if date.tzinfo else None
    except (ValueError, TypeError, AttributeError, OverflowError):
        return None


def digest(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=True,
        separators=(",",":"), default=str).encode()).hexdigest()


def previous_report():
    # Prior public snapshot is optional, never trusted as a data authority.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, url):
            raise ValueError("Prior audit redirect prohibited")
    req = urllib.request.Request(PREVIOUS_URL, headers=UA)
    with urllib.request.build_opener(NoRedirect).open(req, timeout=8) as response:
        content = response.read(1_000_001)
    if len(content) > 1_000_000:
        raise ValueError("Prior audit oversize")
    doc = json.loads(content)
    if not isinstance(doc, dict) or doc.get("schema")!=1 or doc.get("leagueId")!="1413446022":
        return None
    return doc


def status_for(name, payload, stamp, description, now, prior,
               max_age_hours=48, override=None):
    previous = ((prior or {}).get("sections") or {}).get(name) or {}
    signature = digest(payload) if payload is not None else None
    time = when(stamp)
    old_time = when(previous.get("sourceAt"))
    if override:
        state = override
    elif payload is None or time is None:
        state = "UNVERIFIED"
    elif time > now + dt.timedelta(minutes=10) or now-time > dt.timedelta(hours=max_age_hours):
        state = "STALE"
    elif not previous.get("fingerprint"):
        state = "VERIFIED_BASELINE"
    elif signature == previous.get("fingerprint"):
        state = "UNCHANGED_VERIFIED"
    elif old_time and time <= old_time:
        state = "CHANGED_WITHOUT_NEW_SOURCE"
    else:
        state = "UPDATED"
    return {"label":LABELS[name],"status":state,"sourceAt":stamp if time else None,
            "fingerprint":signature, "details":description}


def build(now=None, root=ROOT, prior=None):
    now=(now or dt.datetime.now(dt.timezone.utc)).astimezone(dt.timezone.utc)
    league=read_json("data/league.json",root)
    nfl=read_json("data/nfl-week.json",root)
    stories=read_json("data/weekly-features.json",root)
    pages=read_json("data/gazette-pages.json",root)
    injuries=read_json("data/nfl-injuries.json",root)
    wire=read_json("data/nfl-transactions.json",root)
    editorial=read_json("editorial/latest.json",root)
    try:
        html=(root/"index.html").read_text("utf-8")
    except OSError:
        html=""
    valid_league=bool(league and league.get("season")==2026
         and str(league.get("leagueId"))=="1413446022"
         and league.get("status")!="unavailable"
         and len(league.get("standings") or [])==10
         and when(league.get("fetchedAt")))
    valid_nfl=bool(nfl and nfl.get("season")==2026 and isinstance(nfl.get("games"),list)
         and when(nfl.get("fetchedAt")))
    valid_stories=bool(stories and stories.get("status")=="available"
         and isinstance(stories.get("coverage"),list)
         and when(stories.get("generatedAt")))
    valid_inj=bool(injuries and isinstance(injuries.get("teams"),list)
         and injuries.get("filter") in ("first-string-status-watch","first-string-out-only")
         and when(injuries.get("fetchedAt")))
    valid_wire=bool(wire and wire.get("status")=="available"
         and wire.get("filter")=="verified-key-players-only"
         and isinstance(wire.get("moves"),list) and when(wire.get("fetchedAt")))
    section={}
    def put(name, payload,stamp,desc,**extra):
        section[name]=status_for(name,payload,stamp,desc,now,prior,**extra)

    # Lead story must be supported by the verified fantasy desk feed.
    lead=next((x for x in (stories or {}).get("coverage",[])
        if isinstance(x,dict) and x.get("tag")=="Fantasy League"
        and x.get("headline") and x.get("body")), None) if valid_stories and valid_league else None
    put("lead_story",lead,league.get("fetchedAt") if lead else None,
        ("Verified ESPN league lead: "+lead["headline"]) if lead else
        "No fresh, verified league headline; original Week 11 article is marked an archive.",
        override=None if lead else "ARCHIVE_FALLBACK")
    matches=[g for g in league.get("matchups",[]) if isinstance(g,dict) and
             g.get("week")==league.get("currentMatchupPeriod")] if valid_league else []
    finals=sum(g.get("winner") in ("HOME","AWAY","TIE") for g in matches)
    put("espn_matchups",matches if valid_league else None,league.get("fetchedAt") if valid_league else None,
        "ESPN fantasy week "+str(league.get("currentMatchupPeriod"))+
        ": "+str(len(matches))+" matchups, "+str(finals)+" ESPN-final results." if valid_league else
        "Fantasy matchup snapshot unavailable.")
    bracket=(stories or {}).get("playoffs") or {}
    bracket_ok=bool(valid_stories and bracket.get("status")=="available"
        and isinstance(bracket.get("contenders"),list)
        and isinstance(bracket.get("outsideCurrentField"),list))
    stamp=league.get("fetchedAt") if bracket_ok and valid_league else None
    put("playoffs",{"type":bracket.get("type"),
        "teams":bracket.get("contenders"),"pairings":bracket.get("championshipPairings")} if bracket_ok else None,
        stamp,"ESPN "+str(bracket.get("type"))+" field; "
        +str(len(bracket.get("contenders") or []))+" possible contenders. Not confirmed clinches."
        if bracket_ok else "Playoff field not verified.")
    put("consolation",{"type":bracket.get("type"),
        "teams":bracket.get("outsideCurrentField"),"pairings":bracket.get("consolationPairings")} if bracket_ok else None,
        stamp,str(len(bracket.get("outsideCurrentField") or []))+
        " teams outside the current playoff field. Final Golden Toilet not determined."
        if bracket_ok else "Consolation field not verified.")
    coverage=stories.get("coverage") if valid_stories else None
    put("football_desk",coverage,stories.get("generatedAt") if valid_stories else None,
        (str(len(coverage))+" verified-source briefs: "+
         "; ".join(x.get("headline","") for x in coverage[:3])) if valid_stories else
        "Daily verified sports briefs unavailable.")
    approved=bool(editorial and editorial.get("editorialStatus")=="owner-approved-on-merge"
        and isinstance(editorial.get("body"),str) and editorial["body"].strip())
    put("from_editor",{"date":editorial.get("date"),
        "body":editorial.get("body")} if approved else None,
        editorial.get("approvedAt") or editorial.get("publishedAt") if approved else None,
        "Owner-approved article only; historical fallback is not an automatic daily editorial.",
        override="OWNER_APPROVED_ARCHIVE" if approved else "APPROVAL_REQUIRED")
    nfl_games=nfl.get("games") if valid_nfl else None
    put("nfl_review_preview",nfl_games,nfl.get("fetchedAt") if valid_nfl else None,
        ("NFL Week "+str(nfl.get("week"))+": "+str(len(nfl_games))+" verified games, "+
         str(sum(bool(g.get("completed")) for g in nfl_games))+" finals; weather if verified.")
        if valid_nfl else "NFL schedule/results unavailable.")
    one=(pages or {}).get("pageOne") or {}
    one_ok=one.get("status")=="verified" and len(one.get("standings") or [])==10
    put("page_one",{k:v for k,v in one.items() if k!="sourceAt"} if one_ok else None,
        one.get("sourceAt") if one_ok else None,
        ("48-hour verified edition published "+str(one.get("publishedAt"))+
         "; ESPN source "+str(one.get("sourceAt"))+".") if one_ok else
        "Page One unverified; archived fallback may display.",max_age_hours=72)
    two=(pages or {}).get("pageTwo") or {}
    two_ok=(two.get("status")=="available" and
        two.get("editionDateEastern")==now.astimezone(EASTERN).date().isoformat()
        and isinstance(two.get("fictionNotice"),str) and "invented" in two.get("fictionNotice",""))
    put("page_two",{k:v for k,v in two.items() if k!="publishedAt"} if two_ok else None,
        two.get("publishedAt") if two_ok else None,
        ("Daily edition "+str(two.get("editionDateEastern"))+", "+
         str(len(two.get("interviews") or []))+" explicitly fictional fan interviews.")
        if two_ok else "Today's fictional column not verified.",max_age_hours=28)
    roster=[{"team":t.get("name"),"players":[{"name":p.get("name"),
            "status":p.get("reportedStatus"),"type":p.get("outType")} for p in
            t.get("players",[]) if isinstance(p,dict)]} for t in injuries.get("teams",[])
            if isinstance(t,dict)] if valid_inj else None
    put("key_starters_out",roster,injuries.get("fetchedAt") if valid_inj else None,
        ("ESPN starters: "+str(injuries.get("outCount",0))+" OUT; "+
        str(injuries.get("questionableCount",0))+" questionable; "+
        str(injuries.get("doubtfulCount",0))+" doubtful; "+
        str(injuries.get("reserveCount",0))+" IR/PUP."+
        (" Coverage incomplete." if not injuries.get("coverageComplete") else ""))
        if valid_inj else "Starter OUT injury watch unavailable.",max_age_hours=72)
    moves=wire.get("moves") if valid_wire else None
    put("waivers",moves,wire.get("fetchedAt") if valid_wire else None,
        ("ESPN key roster wire: "+str(wire.get("total",len(moves)))+" featured moves, "+
         str(wire.get("trades",0))+" trades and "+
         str(wire.get("releases",0))+" releases/waivers.")
        if valid_wire else "Key-player waivers/transactions not verified.",max_age_hours=72)
    result={"schema":1,"leagueId":"1413446022","season":2026,
        "generatedAt":now.isoformat(),
        "editionDateEastern":now.astimezone(EASTERN).date().isoformat(),
        "site":"https://whitenick100-eng.github.io/golden-football-gazette/",
        "sections":{key:section[key] for key in KEYS},
        "notes":"This audit verifies source timestamps and content changes; a successful build does not prove Pages deployment. Page One remains on its 48h factual schedule and independent editorial still requires owner approval."}
    return result


def summary(report):
    lines=["## Golden Football Gazette — Daily Section Verification",
        "Generated (UTC): "+report["generatedAt"],""]
    for name, entry in report["sections"].items():
        lines.append("- "+entry["label"]+": "+entry["status"]+" — "+entry["details"])
    lines.extend(["",report["notes"],""])
    return "\n".join(lines)


def main():
    try:
        prior=previous_report()
    except (OSError, ValueError, TypeError, urllib.error.URLError):
        prior=None
        print("No compatible previous published report; establishing new comparison baseline")
    result=build(prior=prior)
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    report=summary(result)
    print(report)
    if os.getenv("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"],"a",encoding="utf-8") as fp:
            fp.write(report+"\n")
    for name,item in result["sections"].items():
        if item["status"] in ("UNVERIFIED","STALE","CHANGED_WITHOUT_NEW_SOURCE","ARCHIVE_FALLBACK"):
            print("::warning::"+item["label"]+" status: "+item["status"])
    return 0


if __name__=="__main__":
    raise SystemExit(main())
