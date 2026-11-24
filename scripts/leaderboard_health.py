#!/usr/bin/env python3
"""Explain whether the published Top Five has caught up with ESPN final games.

Read-only, fail-safe diagnostics for GitHub Actions job logs and summaries.
Never label an old leaderboard as current, alter its source timestamp, invent
scores, or block publication of otherwise verified league/NFL data.
"""
from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path

from refresh_player_leaders import (
    LEAGUE_FILE, OUT, completed_week, tuesday_window_started, verified_leaders,
)


def read_json(path):
    try:
        content = Path(path).read_text(encoding="utf-8")
        data = json.loads(content)
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def assess(league=None, leaders=None, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    if league is None:
        league = read_json(LEAGUE_FILE)
    if leaders is None:
        leaders = read_json(OUT)
    valid_league = (
        isinstance(league, dict)
        and str(league.get("leagueId")) == "1413446022"
        and league.get("season") == 2026
        and len(league.get("standings") or []) == 10
        and isinstance(league.get("currentMatchupPeriod"), int)
    )
    current_week = league.get("currentMatchupPeriod") if valid_league else None
    confirmed_week = completed_week(league) if valid_league else None
    published_week = leaders["week"] if verified_leaders(leaders) else None

    if published_week is None:
        state = "NO_VERIFIED_TOP_FIVE"
        explanation = "No valid five-player ESPN league boxscore is available for publication."
    elif confirmed_week is not None and published_week < confirmed_week:
        state = "RETRY_NEEDED"
        explanation = "ESPN has confirmed a newer completed week, but the published player ranking is still older."
    elif (confirmed_week is not None and published_week == confirmed_week
          and current_week is not None and current_week > published_week + 1):
        state = "WAITING_FOR_ESPN_FINALS"
        explanation = ("The published ranking matches ESPN's last fully final week, "
                       "but a later fantasy scoring period is still not marked complete.")
    elif confirmed_week is not None and published_week == confirmed_week:
        state = "VERIFIED_CURRENT_COMPLETED_WEEK"
        explanation = "The published Top Five matches the latest fully final ESPN scoring period."
    elif confirmed_week is None or (current_week is not None and current_week > published_week):
        state = "WAITING_FOR_ESPN_FINALS"
        explanation = "The ranking is preserved while ESPN has not confirmed a newer fully completed matchup period."
    else:
        state = "VERIFIED_PREVIOUS_RANKING"
        explanation = "This leaderboard is still the most recently verified ranking available."
    return {
        "state": state,
        "explanation": explanation,
        "currentLeagueWeek": current_week,
        "fullyFinalESPNWeek": confirmed_week,
        "publishedTopFiveWeek": published_week,
        "leaderboardSourceAt": leaders.get("fetchedAt") if published_week else None,
        "afterTuesdayCutoff": tuesday_window_started(now),
    }


def format_report(info):
    date = info.get("leaderboardSourceAt") or "unavailable"
    return "\n".join([
        "## Golden Football Gazette — Five Leading Fantasy Performers",
        "",
        f"- **Status:** `{info['state']}`",
        f"- **ESPN league matchup period:** {info['currentLeagueWeek'] or 'unavailable'}",
        f"- **Latest fully final ESPN fantasy week:** {info['fullyFinalESPNWeek'] or 'not yet confirmed'}",
        f"- **Published Top Five fantasy week:** {info['publishedTopFiveWeek'] or 'unavailable'}",
        f"- **Original ESPN ranking verification:** {date}",
        f"- **Tuesday 8:00 a.m. ET cutoff passed:** {'yes' if info['afterTuesdayCutoff'] else 'no'}",
        "",
        info["explanation"],
        "",
        "An Actions job passing does **not** certify that ESPN has supplied a newer completed-week ranking. "
        "Older rankings preserve their original source timestamp and never receive invented scores.",
        "",
    ])


def main():
    info = assess()
    print(format_report(info))
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        try:
            with open(summary, "a", encoding="utf-8") as output:
                output.write(format_report(info) + "\n")
        except OSError as exc:
            print("Top Five job summary not writable:", type(exc).__name__)
    if info["state"] == "RETRY_NEEDED" and info["afterTuesdayCutoff"]:
        print("::warning::ESPN finalized a newer fantasy scoring period, "
              "but the published Top Five has not caught up; verify the mBoxscore feed.")
    if info["state"] == "NO_VERIFIED_TOP_FIVE" and info["afterTuesdayCutoff"]:
        print("::warning::Top Five not yet verified; inspect ESPN boxscore "
              "and the previous published snapshot.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
