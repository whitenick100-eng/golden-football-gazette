#!/usr/bin/env python3
"""Summarize the two data agents; never mislabel missing data as success."""
import json
from datetime import datetime, timezone
from pathlib import Path

def status(path):
    p = Path(path)
    if not p.exists(): return "MISSING"
    try:
        d = json.loads(p.read_text())
        if d.get("status") == "unavailable": return "UNAVAILABLE"
        stamp = datetime.fromisoformat(d["fetchedAt"].replace("Z", "+00:00"))
        age = (datetime.now(timezone.utc) - stamp).total_seconds()/3600
        if age < -1: return "INVALID FUTURE TIMESTAMP"
        return f"{'FRESH' if age <= 36 else 'STALE'} ({age:.1f}h old)"
    except (ValueError, KeyError, TypeError, json.JSONDecodeError): return "INVALID"

for name, path in [("ESPN fantasy league", "data/league.json"), ("NFL schedule/weather", "data/nfl-week.json")]:
    print(f"{name}: {status(path)}")
