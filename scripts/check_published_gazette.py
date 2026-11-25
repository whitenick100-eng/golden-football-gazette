#!/usr/bin/env python3
"""Independently audit what is actually LIVE on GitHub Pages.

This read-only check runs before the 7 AM Eastern ChatGPT report. It does not
claim that a GitHub Actions job has deployed unless an independent deploy job
confirms it; it does not publish files or change the desktop/mobile website.
"""
from __future__ import annotations
import datetime as dt
import json
import os
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

from build_daily_verification import (
    generate,markdown,signature,lead_story,utc,LEAGUE_ID,MAX_SIZE
)
ROOT=Path(__file__).resolve().parents[1]
BASE="https://whitenick100-eng.github.io/golden-football-gazette/"
EASTERN=ZoneInfo("America/New_York")
DOCS={
    "data/league.json":"league",
    "data/nfl-week.json":"nfl",
    "data/nfl-injuries.json":"injuries",
    "data/nfl-transactions.json":"roster",
    "data/weekly-features.json":"weekly",
    "data/gazette-pages.json":"pages",
    "editorial/latest.json":"approved",
}

def public_file(url):
    if not url.startswith(BASE) or "?" in url or ".." in url:
        raise ValueError("Untrusted Gazette source")
    class RestrictRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,req,fp,code,msg,headers,new):
            if not new.startswith(BASE):
                raise ValueError("External redirect refused")
            return super().redirect_request(req,fp,code,msg,headers,new)
    req=urllib.request.Request(url,headers={
       "Accept":"application/json,text/html","User-Agent":"Gazette-MorningSiteAudit/1.0"})
    with urllib.request.build_opener(RestrictRedirect).open(req,timeout=10) as r:
        content=r.read(MAX_SIZE*5+1)
    if len(content)>MAX_SIZE*5:raise ValueError("Public source exceeds audit size limit")
    return content

def read_json_public(url):
    try:
        data=json.loads(public_file(url))
        return data if isinstance(data,dict) else None
    except (OSError,ValueError,TypeError,urllib.error.URLError):
        return None

def live_source_snapshot(destination):
    root=Path(destination)
    results={}
    for public_path,key in DOCS.items():
        data=read_json_public(BASE+public_path)
        results[key]=data is not None
        if data is None:continue
        path=root/public_path
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(data,ensure_ascii=False,allow_nan=False)+"\n",encoding="utf-8")
    try:
        html=public_file(BASE+"index.html").decode("utf-8","replace")
    except (OSError,ValueError,UnicodeError,urllib.error.URLError):
        html=""
    return results,html

def annotate(report,html,availability):
    report["siteCheck"]="live-Pages-read-only"
    report["sourceAvailability"]=availability
    report["deploymentConfirmedByThisReport"]=False
    # The currently published site has a dated, hard-coded Week 11 lead story.
    # Don't falsely describe refreshed weekly-features JSON as a refreshed
    # visible Lead Story until the page actually binds verified data to it.
    lead=report["sections"]["lead_story"]
    if not html:
        lead.update(status="site_unreachable",details="Could not verify the live HTML page.")
    elif "lead.dataset.sourceVerifiedAt" not in html:
        lead.update(status="archived_static",
            details="Live Lead Story is still a historical static headline; refreshed Today’s Football Desk JSON does not automatically replace it.")
    # Likewise, an approved historical editorial is not a freshly authored
    # daily column. Do not imply user review/approval that never occurred.
    editor=report["sections"]["from_the_editor"]
    if not html:
        editor.update(status="site_unreachable",details="Live From the Editor section could not be inspected.")
    elif "daily-verified-editor-notes" not in html:
        editor.update(status="approval_gated",
            details="The separately approved editorial retains its owner-approved date; no automatic daily From the Editor article is published.")
    report["summary"]["changed"]=[x["label"] for x in report["sections"].values() if x["status"]=="content_changed"]
    report["summary"]["unchanged"]=[x["label"] for x in report["sections"].values() if x["status"] in ("verified_unchanged","held_48_hour_schedule")]
    report["summary"]["needsAttention"]=[x["label"] for x in report["sections"].values() if x["status"] in (
        "unavailable","stale_or_undated","site_unreachable","archived_static","approval_gated",
        "fiction_only_source_unavailable","approved_archive_only")]
    return report

def run(now=None,fetcher=live_source_snapshot):
    now=now or dt.datetime.now(dt.timezone.utc)
    with tempfile.TemporaryDirectory() as tmp:
        available,html=fetcher(tmp)
        result=generate(root=Path(tmp),now=now,previous=None)
    result=annotate(result,html,available)
    result["auditTarget"]=BASE
    return result

def main():
    report=run()
    output=ROOT/"data/daily-update-report.json"
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    message=markdown(report)+"\n"
    message+="\nLIVE SITE AUDIT: This report checks public Pages feeds, not just repository files.\n"
    message+="It does NOT certify that a fresh website deployment completed before 7 a.m.; compare GitHub Actions deploy timestamps separately.\n"
    message+="\n"+ "\n".join(
        f"- {s['label']}: {s['status']} — {s['details']}"
        for s in report["sections"].values())+"\n"
    print(message)
    summary=os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary,"a",encoding="utf-8") as stream:
            stream.write(message)
    # Audits are informational, not approval to invent results. No exception
    # should prevent the report from disclosing a source outage.
    return 0

if __name__=="__main__":
    raise SystemExit(main())
