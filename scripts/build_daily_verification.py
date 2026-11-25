#!/usr/bin/env python3
"""Create a conservative, user-readable Gazette update verification snapshot.

This is a *build-time* report, not proof of successful GitHub Pages deployment.
The 7 a.m. ChatGPT verification separately checks the deployed site and Actions.
Never replace stale data with estimates, backdate ESPN source stamps, expose
unapproved editorials, or mark a routine refetch as editorial content change.
"""
from __future__ import annotations
import datetime as dt
import hashlib
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"data/daily-update-report.json"
BASE="https://whitenick100-eng.github.io/golden-football-gazette/data/daily-update-report.json"
EASTERN=ZoneInfo("America/New_York")
LEAGUE_ID="1413446022"
DATE_KEYS={"fetchedAt","generatedAt","publishedAt","builtAt","checkedAt",
           "lastCheckedAt","sourceAt","standingsAsOf"}
MAX_SIZE=250000

def utc(value):
    if not isinstance(value,str):
        return None
    try:
        value=dt.datetime.fromisoformat(value.replace("Z","+00:00"))
        return value.astimezone(dt.timezone.utc) if value.tzinfo else None
    except ValueError:
        return None

def load(path):
    try:
        p=Path(path)
        if p.stat().st_size>MAX_SIZE*5:
            return None
        obj=json.loads(p.read_text("utf-8"))
        return obj if isinstance(obj,dict) else None
    except (ValueError,OSError,TypeError):
        return None

def clean(value):
    if isinstance(value,dict):
        return {k:clean(v) for k,v in value.items() if k not in DATE_KEYS}
    if isinstance(value,list):
        return [clean(v) for v in value]
    return value

def signature(value):
    packed=json.dumps(clean(value),sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False)
    return hashlib.sha256(packed.encode("utf-8")).hexdigest()

def previous_published():
    """Read a fixed public URL; never fetch an arbitrary redirect or secret."""
    class SafeRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,req,fp,code,msg,headers,url):
            if not url.startswith("https://whitenick100-eng.github.io/golden-football-gazette/data/"):
                raise ValueError("Untrusted redirect")
            return super().redirect_request(req,fp,code,msg,headers,url)
    req=urllib.request.Request(BASE,headers={"Accept":"application/json",
        "User-Agent":"GoldenFootballGazette-PublicVerification/1.0"})
    with urllib.request.build_opener(SafeRedirect).open(req,timeout=12) as response:
        body=response.read(MAX_SIZE+1)
    if len(body)>MAX_SIZE:raise ValueError("Report too large")
    data=json.loads(body)
    if not isinstance(data,dict) or data.get("schema")!=1 or data.get("leagueId")!=LEAGUE_ID:
        raise ValueError("Previous report identity failed")
    return data

def lead_story(weekly):
    stories=weekly.get("coverage") if isinstance(weekly,dict) else None
    if not isinstance(stories,list):return None
    for tag in ("Fantasy Recap","Fantasy League","NFL Results","NFL Preview","Fantasy Preview"):
        for story in stories:
            if isinstance(story,dict) and story.get("tag")==tag and all(
                isinstance(story.get(x),str) and story[x].strip()
                for x in ("headline","body","source")
            ):
                return story
    return next((x for x in stories if isinstance(x,dict) and
                 all(isinstance(x.get(k),str) and x[k] for k in ("headline","body","source"))),None)

def source_ok(doc,expected=None):
    if not isinstance(doc,dict) or doc.get("status")=="unavailable":return False
    if expected=="league":
        return str(doc.get("leagueId"))==LEAGUE_ID and doc.get("season")==2026 and (
            isinstance(doc.get("standings"),list) and len(doc["standings"])==10)
    if expected=="weekly":
        return doc.get("status")=="available" and isinstance(doc.get("coverage"),list)
    if expected=="nfl":
        return isinstance(doc.get("games"),list)
    if expected=="injuries":
        return doc.get("filter") in ("first-string-status-watch","first-string-out-only") and isinstance(doc.get("teams"),list)
    if expected=="roster":
        return doc.get("status")=="available" and doc.get("keyOnly") is True and doc.get("filter")=="verified-key-players-only" and isinstance(doc.get("moves"),list)
    return True

def section_specs(d):
    league,weekly,nfl,injuries,roster,pages,approved=(
      d.get(x) for x in ("league","weekly","nfl","injuries","roster","pages","approved"))
    league_valid=source_ok(league,"league")
    weekly_valid=source_ok(weekly,"weekly")
    nfl_valid=source_ok(nfl,"nfl")
    injury_valid=source_ok(injuries,"injuries")
    roster_valid=source_ok(roster,"roster")
    bracket=weekly.get("playoffs") if weekly_valid else None
    bracket_valid=isinstance(bracket,dict) and bracket.get("status")=="available"
    paper_valid=isinstance(pages,dict) and str(pages.get("leagueId"))==LEAGUE_ID and pages.get("season")==2026
    one=pages.get("pageOne") if paper_valid else None
    two=pages.get("pageTwo") if paper_valid else None
    leader=league["standings"][0] if league_valid else {}
    games=league.get("matchups",[]) if league_valid else []
    current=league.get("currentMatchupPeriod") if league_valid else None
    current_games=[g for g in games if isinstance(g,dict) and g.get("week")==current]
    total_final=sum(g.get("winner") in ("HOME","AWAY","TIE") for g in current_games)
    nfl_games=nfl.get("games",[]) if nfl_valid else []
    final_nfl=sum(g.get("completed") is True for g in nfl_games if isinstance(g,dict))
    lead=lead_story(weekly) if weekly_valid else None
    st=weekly.get("generatedAt") if weekly_valid else None
    ls=league.get("fetchedAt") if league_valid else None
    ns=nfl.get("fetchedAt") if nfl_valid else None
    inj_stamp=injuries.get("fetchedAt") if injury_valid else None
    roster_stamp=roster.get("fetchedAt") if roster_valid else None
    one_ok=isinstance(one,dict) and one.get("status")=="verified" and len(one.get("standings") or [])==10
    two_ok=isinstance(two,dict) and two.get("status")=="available" and isinstance(two.get("interviews"),list)
    approved_ok=isinstance(approved,dict) and approved.get("editorialStatus")=="owner-approved-on-merge" and bool(approved.get("body","").strip())
    daily_editor={"facts":(weekly["coverage"][:2] if weekly_valid else []),
                  "source":"automated verified daily desk; NOT an owner-approved editorial"}
    standings=league["standings"] if league_valid else []
    def team_name(team):
        return (team.get("name") or "Unnamed ESPN team") if isinstance(team,dict) else "Unknown"
    result=[
      ("lead_story","Lead Story",lead,st,72,
       (lead.get("headline","") if lead else "No verified lead story"),bool(lead),"ESPN verified daily features"),
      ("espn_matchups","ESPN Fantasy Matchup Center",
       {"week":current,"games":games,"standings":standings} if league_valid else None,ls,48,
       f"Fantasy week {current}; {len(current_games)} matchups; {total_final} ESPN-final in the current week" if league_valid else "ESPN league snapshot unavailable",league_valid,"ESPN public fantasy league"),
      ("playoff_picture","Playoff Picture",
       {"type":bracket.get("type"),"contenders":bracket.get("contenders"),"pairings":bracket.get("championshipPairings"),"settings":bracket.get("playoffTeamCount")} if bracket_valid else None,st,72,
       f"{bracket.get('type')} bracket; {len(bracket.get('contenders') or [])} current contenders (provisional unless ESPN confirmed)" if bracket_valid else "No verified championship bracket",bracket_valid,"ESPN playoff settings and standings"),
      ("consolation_ladder","Consolation Ladder",
       {"type":bracket.get("type"),"outside":bracket.get("outsideCurrentField"),"pairings":bracket.get("consolationPairings")} if bracket_valid else None,st,72,
       f"{len(bracket.get('outsideCurrentField') or [])} teams outside the current ESPN playoff field; final elimination not implied" if bracket_valid else "No verified consolation ladder",bracket_valid,"ESPN playoff settings and standings"),
      ("todays_football_desk","Today's Football Desk",
       weekly.get("coverage") if weekly_valid else None,st,72,
       f"{len(weekly.get('coverage') or [])} dated ESPN-sourced briefings" if weekly_valid else "No verified daily coverage",weekly_valid and bool(weekly.get("coverage")),"ESPN NFL and fantasy feeds"),
      ("from_the_editor","From the Editor",
       {"daily":daily_editor,"approved":approved if approved_ok else None} if weekly_valid or approved_ok else None,
       st if weekly_valid else (approved.get("date") if approved_ok else None),72,
       ("Automated source-backed daily notes; "+("owner-approved editorial also available" if approved_ok else "no new owner-approved article")) if weekly_valid else
       ("Owner-approved article retained; no verified daily note" if approved_ok else "Editorial not available"),weekly_valid or approved_ok,
       "Verified Daily Desk; separate owner-approved editorial"),
      ("nfl_week_review_preview","NFL Week in Review and Preview",
       {"week":nfl.get("week"),"games":nfl_games} if nfl_valid else None,ns,48,
       f"NFL week {nfl.get('week')}; {len(nfl_games)} fixtures; {final_nfl} ESPN-final" if nfl_valid else "Verified NFL schedule unavailable",nfl_valid,"ESPN NFL scoreboard"),
      ("page_one_league_report","Page One · League Report",
       one if one_ok else None,one.get("sourceAt") if one_ok else None,336,
       f"Verified league report published {one.get('publishedAt')}; fantasy week {one.get('currentWeek')}; updates every 48h" if one_ok else "Factual league report unavailable",one_ok,"ESPN standings and confirmed final matchups"),
      ("page_two_fixtures_notes","Page Two · Fixtures and League Notes",
       two if two_ok else None,two.get("sourceAt") if two_ok else None,48,
       f"Daily fictional column dated {two.get('editionDateEastern')}; {len(two.get('fixtures') or [])} verified fantasy fixtures; {len(two.get('interviews') or [])} invented fan voices" if two_ok else "Daily column unavailable",two_ok,"ESPN data for facts; fictional banter explicitly labeled"),
      ("key_starters_out","NFL Key Starters OUT/Questionable/IR",
       injuries.get("teams") if injury_valid else None,inj_stamp,72,
       f"{len(injuries.get('teams') or [])} ESPN NFL clubs checked; complete coverage: {injuries.get('coverageComplete') is True}" if injury_valid else "ESPN starter-status report unavailable",injury_valid,"ESPN depth charts and dated injury statuses"),
      ("nfl_waivers_roster_wire","NFL Waivers and Roster Wire",
       roster.get("moves") if roster_valid else None,roster_stamp,72,
       f"{len(roster.get('moves') or [])} curated, ESPN-verified key-player moves" if roster_valid else "Verified important NFL roster moves unavailable",roster_valid,"ESPN NFL transactions; starter/league-rostered filter"),
    ]
    return result

def generate(root=ROOT,now=None,previous=None):
    now=(now or dt.datetime.now(dt.timezone.utc)).astimezone(dt.timezone.utc)
    root=Path(root)
    d={
        "league":load(root/"data/league.json"),
        "weekly":load(root/"data/weekly-features.json"),
        "nfl":load(root/"data/nfl-week.json"),
        "injuries":load(root/"data/nfl-injuries.json"),
        "roster":load(root/"data/nfl-transactions.json"),
        "pages":load(root/"data/gazette-pages.json"),
        "approved":load(root/"editorial/latest.json"),
    }
    earlier=(previous or {}).get("sections") if isinstance(previous,dict) else {}
    if not isinstance(earlier,dict):earlier={}
    sections={}
    for section_id,label,payload,stamp,max_hours,desc,valid,source in section_specs(d):
        timestamp=utc(stamp)
        age=(now-timestamp).total_seconds()/3600 if timestamp else None
        recent=age is not None and -0.1<=age<=max_hours
        old=earlier.get(section_id) if isinstance(earlier.get(section_id),dict) else {}
        fp=signature(payload) if valid and payload is not None else None
        if not valid:
            status="unavailable"
            details="No current verified source data; the website may retain a timestamped previous edition."
        elif section_id=="from_the_editor" and not d["weekly"]:
            status="approved_archive_only"
            details="Owner-approved editorial is historical; no current verified automated daily note."
        elif not recent:
            status="stale_or_undated"
            details="Published source date is absent or outside the verification window."
        elif fp and old.get("fingerprint") and old["fingerprint"]!=fp:
            status="content_changed"
            details=f"Previous: {old.get('summary','not available')} | Latest: {desc}"
        elif fp and old.get("fingerprint")==fp:
            status="verified_unchanged"
            details="New check ran; underlying content is identical to the previous published edition."
        else:
            status="baseline_unavailable"
            details="First verified audit or previous public audit could not be retrieved; cannot prove content changed."
        if section_id=="page_one_league_report" and valid and recent and status=="verified_unchanged":
            status="held_48_hour_schedule"
            details="Factual Page One preserved on its 48-hour cadence; source and publication times are unchanged."
        if section_id=="page_two_fixtures_notes" and valid and timestamp is None:
            status="fiction_only_source_unavailable"
            details="Fictional column was generated, but ESPN facts are not newly verified."
        sections[section_id]={
            "label":label,"status":status,"summary":desc,
            "details":details,"source":source,"sourceVerifiedAt":stamp,
            "fingerprint":fp,
            "comparedToPreviousPublishedAudit":bool(old.get("fingerprint")),
        }
    return {
      "schema":1,"leagueId":LEAGUE_ID,"season":2026,
      "generatedAt":now.isoformat(),"reportDateEastern":now.astimezone(EASTERN).date().isoformat(),
      "scope":"Build-time candidate. Verify successful GitHub Pages deployment and live feed separately.",
      "previousPublishedAuditAt":previous.get("generatedAt") if isinstance(previous,dict) else None,
      "sections":sections,
      "summary":{
        "changed":[v["label"] for v in sections.values() if v["status"]=="content_changed"],
        "unchanged":[v["label"] for v in sections.values() if v["status"] in ("verified_unchanged","held_48_hour_schedule")],
        "needsAttention":[v["label"] for v in sections.values() if v["status"] in ("unavailable","stale_or_undated","fiction_only_source_unavailable","approved_archive_only")],
        "comparisonAvailable":bool(earlier),
      },
    }

def markdown(data):
    out=[
      "## Golden Football Gazette — Daily Update Audit (candidate)",
      "",
      f"Generated: {data['generatedAt']} · Eastern date: {data['reportDateEastern']}",
      "",
      "**Not proof of live Pages deployment.** Check the deploy job and published JSON after it succeeds.",
      "",
      "| Section | Status | Verified/source summary |",
      "|---|---|---|"
    ]
    for v in data["sections"].values():
        desc=v["summary"].replace("|","/").replace("\n"," ")[:170]
        out.append(f"| {v['label']} | {v['status']} | {desc} |")
    out+=["",f"Content changed: {len(data['summary']['changed'])}",
          f"Unchanged verified: {len(data['summary']['unchanged'])}",
          f"Needs attention: {len(data['summary']['needsAttention'])}",
          ""]
    return "\n".join(out)

def main():
    now=dt.datetime.now(dt.timezone.utc)
    try:
        prior=previous_published()
    except (OSError,ValueError,urllib.error.URLError,json.JSONDecodeError) as exc:
        print("Previous published audit unavailable:",type(exc).__name__)
        prior=None
    result=generate(root=ROOT,now=now,previous=prior)
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    report=markdown(result)
    print(report)
    filename=os.environ.get("GITHUB_STEP_SUMMARY")
    if filename:
        try:
            with open(filename,"a",encoding="utf-8") as f:f.write(report+"\n")
        except OSError as exc:print("Summary unavailable:",type(exc).__name__)
    return 0

if __name__=="__main__":
    raise SystemExit(main())
