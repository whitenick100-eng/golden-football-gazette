#!/usr/bin/env python3
"""Read-only live-site smoke test using TinyFish's streaming Agent API."""
import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.request

URL = "https://whitenick100-eng.github.io/golden-football-gazette/"
REPORT = Path("qa-report.md")
GOAL = """
Read-only QA of the live Golden Football Gazette website. Do not log in,
submit any forms, change any settings, write content, or modify the website.

Inspect the rendered webpage after dynamic loading. Check all of the following:
1. Masthead title visible and both Thanksgiving turkey images are actually loaded.
2. Scrolling NFL player-stat ticker has populated player names and stats,
   or displays a clear, truthful data-unavailable message (not stuck loading).
3. ESPN Fantasy Matchup Center has populated matchups, or a clear error/empty
   state rather than misleading placeholder scores or indefinite loading.
4. Roster Wire says feed active and shows verified major moves OR a legitimate
   'no qualifying transactions' message; an empty wire is NOT a failure.
5. No broken images, obvious browser errors, or sections stuck loading.
6. If possible, check a narrow/mobile viewport. If unable, mark as not_checked
   rather than reporting a pass.

Return ONLY a JSON object with this exact structure:
{"passed":true,"summary":"concise factual result",
 "checks":[{"name":"masthead_and_turkeys","status":"pass","detail":"..."},
 {"name":"nfl_player_ticker","status":"pass","detail":"..."},
 {"name":"fantasy_matchups","status":"pass","detail":"..."},
 {"name":"roster_wire","status":"pass","detail":"..."},
 {"name":"visible_errors","status":"pass","detail":"..."},
 {"name":"mobile","status":"not_checked","detail":"..."}],
 "failures":[]}
Each check status is pass, fail, or not_checked. 'passed' must be false
if any core check (first five) fails or cannot be verified. Be evidence-based:
never claim ESPN source statistics are independently verified.
"""

def write_report(message, checks=None, failures=None):
    checks = checks or []
    failures = failures or []
    lines = ["# Golden Football Gazette — TinyFish website QA", "",
             "Website: " + URL, "", "## Summary", "", str(message), "",
             "## Checks", ""]
    for check in checks:
        if isinstance(check, dict):
            lines.append("- **{}:** {} — {}".format(
                str(check.get("name", "unknown"))[:90],
                str(check.get("status", "unknown"))[:25],
                str(check.get("detail", ""))[:600]))
    lines.extend(["", "## Failures", ""])
    lines.extend(["- " + str(item)[:700] for item in failures] or ["None reported."])
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(message)

def main():
    key = os.environ.get("TINYFISH_API_KEY", "").strip()
    if not key:
        write_report("TinyFish is not configured: add TINYFISH_API_KEY under GitHub repository Settings > Secrets and variables > Actions.",
                     failures=["Missing repository secret TINYFISH_API_KEY."])
        return 1

    request = urllib.request.Request(
        "https://agent.tinyfish.ai/v1/automation/run-sse",
        data=json.dumps({"url": URL, "goal": GOAL}).encode("utf-8"),
        headers={"X-API-Key": key, "Content-Type": "application/json",
                 "Accept": "text/event-stream"},
        method="POST",
    )

    try:
        complete = None
        with urllib.request.urlopen(request, timeout=360) as response:
            for raw in response:
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                try:
                    event = json.loads(line[5:].strip())
                except (ValueError, TypeError):
                    continue
                if not isinstance(event, dict):
                    continue
                if event.get("type") == "COMPLETE":
                    complete = event
                    break
                if event.get("type") in ("ERROR", "FAILED"):
                    raise RuntimeError("TinyFish reported an error during browser QA.")
        if complete is None:
            raise RuntimeError("TinyFish did not return a COMPLETE event.")
        if complete.get("status") != "COMPLETED":
            raise RuntimeError("TinyFish run finished with status: " + str(complete.get("status")))
        result = complete.get("result")
        if isinstance(result, str):
            result = json.loads(result)
        if isinstance(result, dict) and "passed" not in result and isinstance(result.get("result"), dict):
            result = result["result"]
        if not isinstance(result, dict) or not isinstance(result.get("passed"), bool):
            raise ValueError("TinyFish output was not valid structured QA JSON.")
        checks = result.get("checks", [])
        failures = result.get("failures", [])
        if not isinstance(checks, list) or not isinstance(failures, list):
            raise ValueError("TinyFish returned an invalid checks/failures structure.")
        core = {"masthead_and_turkeys", "nfl_player_ticker", "fantasy_matchups",
                "roster_wire", "visible_errors"}
        passed_names = {c.get("name") for c in checks if isinstance(c, dict) and c.get("status") == "pass"}
        passed = result["passed"] and core.issubset(passed_names) and not failures
        write_report(result.get("summary", "QA completed."), checks, failures)
        return 0 if passed else 1
    except (urllib.error.URLError, ValueError, RuntimeError, TimeoutError, OSError) as exc:
        write_report("TinyFish website QA could not complete.",
                     failures=[str(exc)[:500]])
        return 1

if __name__ == "__main__":
    sys.exit(main())
