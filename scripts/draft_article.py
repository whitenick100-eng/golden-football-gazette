#!/usr/bin/env python3
"""Manually draft a source-grounded Gazette article. Never publish directly."""
import argparse
import datetime as dt
import json
import os
import re
import urllib.request
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--type", choices=["weekly-recap","week-preview","daily-brief"], required=True)
args = parser.parse_args()
key = os.environ.get("OPENAI_API_KEY")
if not key:
    raise SystemExit("OPENAI_API_KEY is not configured; no article generated")

sources = {}
for name, file in [("fantasy_league", "data/league.json"), ("nfl_week", "data/nfl-week.json")]:
    path = Path(file)
    if path.exists():
        obj = json.loads(path.read_text(encoding="utf-8"))
        if obj.get("fetchedAt") and obj.get("status") != "unavailable":
            stamp = dt.datetime.fromisoformat(obj["fetchedAt"].replace("Z", "+00:00"))
            age = dt.datetime.now(dt.timezone.utc) - stamp
            if dt.timedelta(0) <= age <= dt.timedelta(hours=48):
                sources[name] = obj
            else:
                print(f"Skipping stale source: {name}")
if not sources:
    raise SystemExit("No verified data snapshots; refusing to draft unsupported article")

today = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
instructions = (
    "You are the professional sports editor of The Golden Football Gazette, "
    "an independent fantasy football newspaper. Draft in an authoritative newspaper "
    "voice with lively but respectful writing. Use ONLY facts explicitly present in "
    "the supplied structured data. Cite the source feed and its fetchedAt timestamp "
    "in an editorial verification note. Never invent player stats, quotes, injuries, "
    "ESPN fantasy ownership, projections, playoff eliminations, awards, final results, "
    "or team logos. If data is unavailable, say so briefly and omit the claim. "
    "Separate editorial forecasts from actual outcomes and label all forecasts. "
    "Do not claim games are final unless the supplied data establishes it. "
    "Write Markdown with headline, dateline, and 3-5 compact paragraphs. "
    "End with a section 'Editor's verification checklist' listing facts requiring "
    "human confirmation before publication. The article is a DRAFT."
)
body = {
    "model": os.environ.get("GAZETTE_OPENAI_MODEL", "gpt-4.1-mini"),
    "messages": [
        {"role":"system","content":instructions},
        {"role":"user","content":json.dumps({"date_utc":today,"article_type":args.type,
                                             "source_data":sources},ensure_ascii=False)}
    ],
    "temperature":0.2,
    "max_tokens":1800
}
request = urllib.request.Request("https://api.openai.com/v1/chat/completions",
    data=json.dumps(body).encode("utf-8"),
    headers={"Authorization":"Bearer "+key,"Content-Type":"application/json"},
    method="POST")
with urllib.request.urlopen(request, timeout=90) as response:
    payload = json.load(response)
draft = payload["choices"][0]["message"]["content"]
if not isinstance(draft,str) or len(draft.strip()) < 250:
    raise SystemExit("Draft was empty or incomplete; no file written")
Path("editorial").mkdir(exist_ok=True)
path = Path("editorial") / f"{today}-{args.type}-DRAFT.md"
path.write_text("<!-- UNPUBLISHED DRAFT: OWNER APPROVAL REQUIRED -->\n\n"+draft.strip()+"\n",encoding="utf-8")
Path("editorial/latest.json").write_text(json.dumps({"date":today,"articleType":args.type,"body":draft.strip(),"sourceTimes":{name:obj.get("fetchedAt") for name,obj in sources.items()},"editorialStatus":"owner-approved-on-merge"},indent=2)+"\\n",encoding="utf-8")
print(f"Created review-only draft: {path}; owner approval via merge is required before homepage displays it")
