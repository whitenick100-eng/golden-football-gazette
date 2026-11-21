#!/usr/bin/env python3
"""Cache each fantasy team's original ESPN image for the GitHub Pages build.

The live ESPN league is preferred when available; otherwise use the exact
source URLs in assets/espn-team-logos.json. Never manufacture or replace logos.
An image that cannot be retrieved remains explicitly unavailable.
"""
import io
import json
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INPUT = ROOT / "assets/espn-team-logos.json"
OUTPUT = ROOT / "assets/fantasy-logos"
MAX_BYTES = 2_000_000
UA = "Mozilla/5.0 (compatible; GoldenFootballGazette/1.0)"
ALLOWED = ("mystique-api.fantasy.espn.com", "g.espncdn.com", "a.espncdn.com")

def allowed(url):
    try:
        p = urllib.parse.urlparse(url)
        return p.scheme == "https" and p.hostname in ALLOWED and not p.username and not p.password
    except (ValueError, TypeError):
        return False

class ESPNRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not allowed(newurl):
            raise ValueError("Image redirected outside ESPN image hosts")
        return super().redirect_request(req, fp, code, msg, headers, newurl)

OPENER = urllib.request.build_opener(ESPNRedirects)

def sanitize_svg(data):
    root = ET.fromstring(data)
    if root.tag.split("}")[-1].lower() != "svg":
        raise ValueError("Unexpected SVG document root")
    blocked = {"script", "foreignObject", "iframe", "object", "embed", "image", "use"}
    def clean(parent):
        for child in list(parent):
            if child.tag.split("}")[-1].lower() in {x.lower() for x in blocked}:
                parent.remove(child)
                continue
            clean(child)
        for key, value in list(parent.attrib.items()):
            k = key.split("}")[-1].lower()
            if (k.startswith("on") or k in ("href", "src")
                or re.search(r"url\(\s*['\"]?\s*(https?:|//|javascript:)", value, re.I)):
                parent.attrib.pop(key, None)
    clean(root)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)

def detect(data, content_type):
    lower = content_type.lower().split(";")[0].strip()
    if data.startswith(b"\x89PNG\r\n\x1a\n"): return "png", data
    if data[:3] == b"\xff\xd8\xff": return "jpg", data
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP": return "webp", data
    if data[:6] in (b"GIF87a", b"GIF89a"): return "gif", data
    if lower in ("image/svg+xml", "application/svg+xml", "text/xml", "application/xml") or b"<svg" in data[:500]:
        return "svg", sanitize_svg(data)
    raise ValueError("ESPN response was not a supported image")

def download(url):
    if not allowed(url):
        raise ValueError("Logo URL not recognized as an ESPN image endpoint")
    headers = {
        "User-Agent": UA,
        "Accept": "image/avif,image/webp,image/png,image/jpeg,image/svg+xml,image/gif,*/*;q=0.8",
        "Referer": "https://fantasy.espn.com/",
    }
    req = urllib.request.Request(url, headers=headers)
    with OPENER.open(req, timeout=12) as resp:
        final = resp.geturl()
        if not allowed(final):
            raise ValueError("Untrusted final image host")
        data = resp.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ValueError("Logo exceeds maximum image size")
        return detect(data, resp.headers.get("Content-Type", ""))

def collect_teams():
    base = json.loads(INPUT.read_text(encoding="utf-8"))
    teams = {int(t["id"]): dict(t) for t in base["teams"]}
    if len(teams) != 10:
        raise ValueError("Expected exactly 10 ESPN fantasy teams")
    league = ROOT / "data/league.json"
    if league.is_file():
        try:
            snapshot = json.loads(league.read_text(encoding="utf-8"))
            if str(snapshot.get("leagueId")) == "1413446022" and snapshot.get("season") == 2026:
                for team in snapshot.get("standings", []):
                    id_ = int(team["teamId"])
                    if id_ in teams:
                        if team.get("name"):
                            teams[id_]["name"] = team["name"]
                        if allowed(team.get("logo")):
                            teams[id_]["logo"] = team["logo"]
        except (OSError, KeyError, ValueError, TypeError, json.JSONDecodeError):
            print("Unable to read the ESPN league's latest logo fields; using saved team URLs")
    return teams

def build():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    teams = collect_teams()
    result = {"leagueId": 1413446022, "season": 2026, "teams": {}}
    cached = 0
    for id_, t in sorted(teams.items()):
        url = t.get("logo") or ""
        row = {"teamId":id_, "name":t.get("name"), "sourceUrl":url, "localUrl":None, "cached":False}
        # Preserve source URL if download fails; never assign a different logo.
        if not allowed(url):
            print(f"ESPN team {id_}: source URL is missing or unrecognized")
        else:
            try:
                ext, data = download(url)
                path = OUTPUT / f"team-{id_}.{ext}"
                path.write_bytes(data)
                row["localUrl"] = f"assets/fantasy-logos/{path.name}"
                row["cached"] = True
                cached += 1
                print(f"ESPN team {id_}: cached {ext} image ({len(data)} bytes)")
            except (OSError, urllib.error.URLError, ValueError, ET.ParseError) as exc:
                print(f"ESPN team {id_}: logo unavailable ({type(exc).__name__}); original URL preserved")
        result["teams"][str(id_)] = row
    (OUTPUT / "manifest.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"ESPN logo coverage: {cached}/{len(teams)} cached; no substitutions")
    return result

if __name__ == "__main__":
    build()
