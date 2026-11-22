#!/usr/bin/env python3
"""Gazette backend resilience: validate public snapshots, recover and archive.

Never update an original ESPN verification time, invent scores, or publish
unverified private/source data. This writes ONLY data/ and monitor/ (never HTML).
The published Pages site is a fixed, HTTPS, read-only recovery source.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
MONITOR = ROOT / "monitor"
PRIOR = MONITOR / "prior"
BACKUP = MONITOR / "backup-artifact"
REPORT = BACKUP / "health-report.md"
BASE = "https://whitenick100-eng.github.io/golden-football-gazette/data/"
MAX_BYTES = 1_000_000
YEAR = 2026
LEAGUE = "1413446022"

# Critical feeds block an unsafe deployment only after verification/recovery
# is exhausted. Other feeds are monitored but do not block football scores.
FEEDS = {
    "league.json": {"label": "ESPN fantasy league", "max_hours": 48, "critical": True, "time": "fetchedAt"},
    "nfl-week.json": {"label": "NFL schedule and scores", "max_hours": 48, "critical": True, "time": "fetchedAt"},
    "nfl-injuries.json": {"label": "NFL starter injury report", "max_hours": 72, "critical": False, "time": "fetchedAt"},
    "nfl-transactions.json": {"label": "NFL roster wire", "max_hours": 72, "critical": False, "time": "fetchedAt"},
    "top-performers.json": {"label": "Weekly fantasy top five", "max_hours": 336, "critical": False, "time": "fetchedAt"},
    "weekly-features.json": {"label": "Verified football briefs", "max_hours": 72, "critical": False, "time": "generatedAt"},
}
UA = {"User-Agent": "GoldenFootballGazette-DataGuard/1.0", "Accept": "application/json"}


def time_from(value):
    if not isinstance(value, str):
        raise ValueError("Source timestamp absent")
    stamp = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        raise ValueError("Source timestamp has no timezone")
    return stamp.astimezone(dt.timezone.utc)


def age_hours(name, data, now):
    timestamp = time_from(data[FEEDS[name]["time"]])
    return (now - timestamp).total_seconds() / 3600


def valid(name, data, now=None):
    """Strict, deterministic structural validation. Does NOT claim ESPN was contacted."""
    now = now or dt.datetime.now(dt.timezone.utc)
    if name not in FEEDS or not isinstance(data, dict) or data.get("status") == "unavailable":
        return False, "missing/unavailable or wrong document type"
    try:
        age = age_hours(name, data, now)
        if age < -1:
            raise ValueError("future-dated verification")
        if name == "league.json":
            teams = data["standings"]
            games = data["matchups"]
            if str(data.get("leagueId")) != LEAGUE or data.get("season") != YEAR:
                raise ValueError("league identity mismatch")
            if not isinstance(teams, list) or len(teams) != 10:
                raise ValueError("not all 10 league teams are present")
            ids = [t.get("teamId") for t in teams if isinstance(t, dict)]
            if len(ids) != 10 or len(set(ids)) != 10:
                raise ValueError("missing/duplicate fantasy team ids")
            if not isinstance(games, list) or len(games) < 5:
                raise ValueError("incomplete season matchup coverage")
            for game in games:
                if not isinstance(game, dict) or not isinstance(game.get("home"), dict) or not isinstance(game.get("away"), dict):
                    raise ValueError("malformed fantasy game")
                if game["home"].get("teamId") is None or game["away"].get("teamId") is None:
                    raise ValueError("unidentified fantasy opponents")
                if game.get("winner") not in ("HOME", "AWAY", "TIE", "UNDECIDED", None):
                    raise ValueError("invalid matchup winner")
            if not isinstance(data.get("currentMatchupPeriod"), int) or not 1 <= data["currentMatchupPeriod"] <= 22:
                raise ValueError("invalid fantasy week")
        elif name == "nfl-week.json":
            games = data["games"]
            if data.get("season") != YEAR or not isinstance(data.get("week"), int) or not 1 <= data["week"] <= 22:
                raise ValueError("invalid NFL season/week")
            if not isinstance(games, list) or not games:
                raise ValueError("NFL schedule contains no games")
            ids = []
            for game in games:
                if not isinstance(game, dict) or not game.get("id"):
                    raise ValueError("unidentified NFL game")
                if not isinstance(game.get("home"), dict) or not isinstance(game.get("away"), dict):
                    raise ValueError("incomplete NFL opponents")
                if not game["home"].get("abbr") or not game["away"].get("abbr"):
                    raise ValueError("missing NFL team abbreviation")
                ids.append(str(game["id"]))
            if len(ids) != len(set(ids)):
                raise ValueError("duplicate NFL game ids")
        elif name == "nfl-injuries.json":
            teams = data["teams"]
            if data.get("season") != YEAR or not isinstance(teams, list):
                raise ValueError("invalid injury feed season/teams")
            if data.get("filter") not in ("first-string-status-watch", "first-string-out-only"):
                raise ValueError("unknown injury starter filter")
            if data.get("teamCount") != len(teams):
                raise ValueError("injury team count mismatch")
            if not all(isinstance(t, dict) and isinstance(t.get("players"), list) for t in teams):
                raise ValueError("malformed starter injury groups")
            if data.get("playerCount") != sum(len(t["players"]) for t in teams):
                raise ValueError("injury player count mismatch")
        elif name == "nfl-transactions.json":
            if data.get("status") != "available" or data.get("filter") != "verified-key-players-only":
                raise ValueError("unverified transactions source")
            if not isinstance(data.get("moves"), list):
                raise ValueError("missing roster transactions list")
        elif name == "top-performers.json":
            if str(data.get("leagueId")) != LEAGUE or data.get("season") != YEAR:
                raise ValueError("incorrect top-five league")
            if not isinstance(data.get("week"), int) or not 1 <= data["week"] <= 22:
                raise ValueError("invalid top-five scoring week")
            players = data.get("players")
            if not isinstance(players, list) or len(players) != 5:
                raise ValueError("top five must contain exactly five players")
            ids = [p.get("playerId") for p in players if isinstance(p, dict)]
            if len(ids) != 5 or len(set(ids)) != 5:
                raise ValueError("top five player IDs are invalid or duplicated")
            if not all(isinstance(p.get("points"), (int, float)) and
                       not isinstance(p.get("points"), bool) and 0 <= p["points"] < 250
                       for p in players):
                raise ValueError("invalid actual fantasy points")
        elif name == "weekly-features.json":
            if data.get("status") != "available" or not isinstance(data.get("coverage"), list):
                raise ValueError("weekly features are unavailable or incomplete")
        return True, f"verified structure; {age:.1f}h since source"
    except (ValueError, KeyError, TypeError, OverflowError) as exc:
        return False, str(exc)[:170]


def read_json(file):
    try:
        if not file.is_file() or file.stat().st_size > MAX_BYTES:
            return None
        data = json.loads(file.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, ValueError, json.JSONDecodeError):
        return None


class FixedHostRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, url):
        # The source must remain on the official public GitHub Pages host.
        if not url.startswith(BASE):
            raise ValueError("Unexpected backup redirect destination")
        return super().redirect_request(req, fp, code, msg, headers, url)


def fetch_previous(name):
    if name not in FEEDS:
        raise ValueError("Unapproved data filename")
    req = urllib.request.Request(BASE + name, headers=UA)
    opener = urllib.request.build_opener(FixedHostRedirect)
    with opener.open(req, timeout=12) as response:
        raw = response.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("Published backup exceeds data size cap")
    return json.loads(raw)


def store_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def preload(now=None, fetcher=fetch_previous):
    """Load last verified public snapshots before any refresh script can fail.

    Also retain an immutable per-run baseline in monitor/prior for comparisons.
    Unknown/invalid source documents are ignored, not treated as verified.
    """
    now = now or dt.datetime.now(dt.timezone.utc)
    DATA.mkdir(exist_ok=True, parents=True)
    PRIOR.mkdir(exist_ok=True, parents=True)
    for name in FEEDS:
        prior = read_json(DATA / name)
        valid_prior = valid(name, prior, now)[0]
        try:
            incoming = fetcher(name)
            good, detail = valid(name, incoming, now)
            if good:
                if not valid_prior or time_from(incoming[FEEDS[name]["time"]]) >= time_from(prior[FEEDS[name]["time"]]):
                    prior, valid_prior = incoming, True
            else:
                print(f"BACKUP IGNORED {name}: {detail}")
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError, urllib.error.URLError) as exc:
            print(f"BACKUP UNREACHABLE {name}: {type(exc).__name__}")
        if valid_prior:
            store_json(PRIOR / name, prior)
            # Leave the authentic source timestamp in place.
            store_json(DATA / name, prior)
            print("BACKUP STAGED", name)
        else:
            print("NO VERIFIED BACKUP", name)


def progress_key(name, value):
    if name == "league.json":
        return value["currentMatchupPeriod"]
    if name in ("nfl-week.json", "top-performers.json"):
        return value["week"]
    return None


def choose(name, candidate, prior, now):
    """Compare a new feed against the last verified backup; never regress."""
    good, reason = valid(name, candidate, now)
    prior_ok = valid(name, prior, now)[0]
    if good and prior_ok:
        if age_hours(name, candidate, now) > age_hours(name, prior, now) + .25:
            good, reason = False, "source verification time moved backwards"
        else:
            current_key, old_key = progress_key(name, candidate), progress_key(name, prior)
            if current_key is not None and old_key is not None and current_key < old_key:
                good, reason = False, "ESPN week/scoring period regressed"
    if good:
        return candidate, "VERIFIED", reason
    if prior_ok:
        return prior, "RECOVERED", reason
    return None, "UNAVAILABLE", reason


def archive(snapshots, now, report):
    if BACKUP.exists():
        shutil.rmtree(BACKUP)
    data_dir = BACKUP / "data"
    data_dir.mkdir(parents=True)
    manifest = {"schema": 1, "createdAt": now.isoformat(), "leagueId": LEAGUE,
                "season": YEAR, "files": {}}
    for name, doc in snapshots.items():
        if not valid(name, doc, now)[0]:
            continue
        file = data_dir / name
        store_json(file, doc)
        manifest["files"][name] = {
            "sha256": hashlib.sha256(file.read_bytes()).hexdigest(),
            "sourceVerifiedAt": doc[FEEDS[name]["time"]],
        }
    store_json(BACKUP / "manifest.json", manifest)
    REPORT.write_text(report, encoding="utf-8")


def finalize(now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    lines = ["# Golden Football Gazette — backend data health", "",
             "Data checks operate on verified public JSON only; source timestamps are not altered.",
             ""]
    rows = []
    backup_data = {}
    critical = []
    warnings = []
    for name, cfg in FEEDS.items():
        current = read_json(DATA / name)
        previous = read_json(PRIOR / name)
        chosen, mode, reason = choose(name, current, previous, now)
        age = age_hours(name, chosen, now) if chosen is not None else None
        stale = chosen is None or age > cfg["max_hours"]
        if chosen is not None:
            store_json(DATA / name, chosen)
            backup_data[name] = chosen
        elif (DATA / name).exists():
            # Do not publish a known-malformed or unlabeled document.
            (DATA / name).unlink()
        if mode == "RECOVERED":
            warnings.append(f"{cfg['label']}: restored last verified snapshot ({reason})")
        if stale:
            note = f"{cfg['label']}: {'missing/unverified' if age is None else f'{age:.1f}h old'}"
            (critical if cfg["critical"] else warnings).append(note)
        label = "STALE" if stale and chosen is not None else ("UNAVAILABLE" if chosen is None else mode)
        rows.append((cfg["label"], label, "—" if age is None else f"{age:.1f}h", reason))
    lines.extend(["| Feed | Assessment | Source age | Notes |",
                  "|---|---|---:|---|"])
    for name, mode, age, reason in rows:
        lines.append(f"| {name} | {mode} | {age} | {reason.replace('|','/')} |")
    lines.extend(["", "## Required follow-up", ""])
    if warnings:
        lines.extend("- WARNING: " + s for s in warnings)
    if critical:
        lines.extend("- CRITICAL: " + s for s in critical)
    if not critical and not warnings:
        lines.append("- All feeds structurally verified; no backup recovery required.")
    lines.extend(["", f"**Deployment gate:** {'FAILED' if critical else 'PASSED'}",
                  "", "Historical snapshots are never presented as freshly fetched data.", ""])
    report = "\n".join(lines)
    archive(backup_data, now, report)
    print(report)
    return 1 if critical else 0


def restore_artifact(folder, now=None):
    """Manually recover a prior Actions artifact, rejecting edited/wrong files."""
    now = now or dt.datetime.now(dt.timezone.utc)
    root = Path(folder).resolve()
    manifest = read_json(root / "manifest.json")
    if not manifest or manifest.get("schema") != 1 or str(manifest.get("leagueId")) != LEAGUE or manifest.get("season") != YEAR:
        raise ValueError("Unrecognized backup manifest / wrong league")
    files = manifest.get("files")
    if not isinstance(files, dict):
        raise ValueError("Backup file index missing")
    snapshots = {}
    for name, entry in files.items():
        if name not in FEEDS or not isinstance(entry, dict):
            raise ValueError("Unknown backup dataset")
        source = root / "data" / name
        if not source.is_file() or not source.resolve().is_relative_to(root):
            raise ValueError("Backup dataset absent")
        if hashlib.sha256(source.read_bytes()).hexdigest() != entry.get("sha256"):
            raise ValueError("Backup checksum mismatch: " + name)
        doc = read_json(source)
        if not valid(name, doc, now)[0]:
            raise ValueError("Backup validation failed: " + name)
        if doc[FEEDS[name]["time"]] != entry.get("sourceVerifiedAt"):
            raise ValueError("Backup source timestamp mismatch: " + name)
        snapshots[name] = doc
    for required in ("league.json", "nfl-week.json"):
        if required not in snapshots:
            raise ValueError("Recovery artifact lacks essential "+required)
    DATA.mkdir(parents=True, exist_ok=True)
    for name, doc in snapshots.items():
        store_json(DATA / name, doc)
    print("Manual recovery verified:", len(snapshots),
          "data files; original source timestamps preserved.")
    print("WARNING: This is a historical rollback, not a claim of live scores.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["preload", "check", "restore-artifact"])
    parser.add_argument("--source", help="Directory extracted from a known successful Actions artifact")
    opts = parser.parse_args(argv)
    if opts.action == "preload":
        preload()
        return 0
    if opts.action == "check":
        return finalize()
    if not opts.source:
        parser.error("--source is mandatory for restore-artifact")
    restore_artifact(opts.source)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, TypeError) as exc:
        print("Data guard error:", str(exc), file=sys.stderr)
        sys.exit(1)
