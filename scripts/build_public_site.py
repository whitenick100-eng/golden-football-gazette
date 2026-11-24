#!/usr/bin/env python3
"""Build a minimal, reviewed GitHub Pages artifact with a browser CSP.

IMPORTANT: This protects the *published Pages artifact*, not GitHub repository
history or other copies of the public repository. Never commit credentials.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import html
import json
import re
import shutil
from pathlib import Path
from html.parser import HTMLParser

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "public"

# Only these JSON documents are appropriate for the public news website.
PUBLIC_DATA = (
    "league.json",
    "nfl-week.json",
    "nfl-injuries.json",
    "nfl-transactions.json",
    "top-performers.json",
    "weekly-features.json",
    "gazette-pages.json",
)
STATIC_ASSETS = (
    "assets/stadium-late-fall.webp",
    "assets/stadium-nfl-unbranded.webp",
    "assets/live-nfl-scores.js",
    "assets/nfl-player-ticker.js",
    "assets/multisport-ticker.js",
    "assets/dynamic-newspaper.js",
    "assets/mobile-gazette.css",
    "assets/mobile-gazette.js",
    "assets/espn-matchups.js",
    "assets/espn-team-logos.json",
    # Reviewed, owner-supplied Thanksgiving masthead artwork.
    "assets/turkey-left.webp",
    "assets/turkey-right.webp",
)
IMAGE_EXTENSIONS = {".webp", ".png", ".jpg", ".jpeg", ".gif", ".svg"}
MAX_IMAGE_BYTES = 2_000_000
class InlineContentParser(HTMLParser):
    """Extract exact inline JS/CSS using the HTML parser instead of a regex."""

    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.blocks = []
        self.metadata = []
        self.active_tag = None
        self.active_attrs = None
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag == "meta":
            self.metadata.append(dict(attrs))
        if tag in ("script", "style"):
            if self.active_tag is not None:
                raise ValueError("Malformed nested script/style content")
            self.active_tag = tag
            self.active_attrs = dict(attrs)
            self.parts = []

    def handle_endtag(self, tag):
        if self.active_tag == tag:
            self.blocks.append((tag, self.active_attrs, "".join(self.parts)))
            self.active_tag = None
            self.active_attrs = None
            self.parts = []

    def handle_data(self, data):
        if self.active_tag is not None:
            self.parts.append(data)

    def handle_entityref(self, name):
        if self.active_tag is not None:
            self.parts.append("&" + name + ";")

    def handle_charref(self, name):
        if self.active_tag is not None:
            self.parts.append("&#" + name + ";")

    def ensure_complete(self):
        if self.active_tag is not None:
            raise ValueError("Unterminated HTML script/style element")
        return self


def inline_content(source: str) -> InlineContentParser:
    parser = InlineContentParser()
    parser.feed(source)
    parser.close()
    return parser.ensure_complete()


# Keep checks conservative: reject genuine credential patterns, not harmless
# source-code references like os.getenv("OPENAI_API_KEY").
SECRET_PATTERNS = {
    "GitHub token": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{25,}|github_pat_[A-Za-z0-9_]{25,})\b"),
    "OpenAI API key": re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b"),
    "Cloud access key": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "Google API key": re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    "Private key block": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |ENCRYPTED )?PRIVATE KEY-----"),
    "ESPN session cookie": re.compile(r"(?i)\b(?:espn_s2|SWID)\s*=\s*[^;\s\"']+"),
}
TEXT_SCAN_EXTENSIONS = {".html", ".js", ".json", ".md", ".txt", ".yml",
                        ".yaml", ".py", ".toml", ".xml", ".env", ".cfg"}


def scan_for_secrets(root: Path) -> None:
    """Block obvious credentials before publication without echoing their values."""
    for p in root.rglob("*"):
        if not p.is_file() or p.is_symlink():
            continue
        if any(part in {".git", ".venv", "venv", "__pycache__", "public"} for part in p.relative_to(root).parts):
            continue
        if p.suffix.lower() in {".pem", ".p12", ".pfx", ".key"} or p.name.startswith(".env"):
            raise ValueError("Forbidden credential-like file in repository: " + str(p.relative_to(root)))
        if p.suffix.lower() not in TEXT_SCAN_EXTENSIONS:
            continue
        if p.stat().st_size > 2_000_000:
            continue
        content = p.read_text("utf-8", errors="replace")
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(content):
                raise ValueError(f"Potential {label} in {p.relative_to(root)}; remove and rotate it before publishing")


def checked_copy(root: Path, output: Path, relative: str, required: bool = False) -> bool:
    source = root / relative
    if not source.is_file():
        if required:
            raise ValueError(f"Missing required website asset: {relative}")
        return False
    if source.is_symlink() or not source.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"Refusing untrusted symlink: {relative}")
    destination = output / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    return True


def hash_source(source: str) -> str:
    encoded = hashlib.sha256(source.encode("utf-8")).digest()
    return "'sha256-" + base64.b64encode(encoded).decode("ascii") + "'"


def csp_for_html(source: str) -> str:
    parsed = inline_content(source)
    scripts = [hash_source(content) for tag, attrs, content in parsed.blocks
               if tag == "script" and "src" not in attrs]
    styles = [hash_source(content) for tag, attrs, content in parsed.blocks
              if tag == "style"]
    if len(scripts) < 5 or not styles:
        raise ValueError("Inline scripts or styles changed unexpectedly; audit CSP generation")
    # GitHub Pages does not allow project-defined response headers. A meta CSP
    # limits browsers after parsing <head>, but cannot provide frame-ancestors,
    # a true HTTP Referrer-Policy header, or report-only CSP.
    policy = [
        "default-src 'none'",
        "base-uri 'none'",
        "object-src 'none'",
        "frame-src 'none'",
        "form-action 'none'",
        "script-src 'self' " + " ".join(scripts),
        "script-src-attr 'none'",
        "style-src 'self' " + " ".join(styles),
        # Four existing, trusted inline style attributes in the static layout:
        "style-src-attr 'unsafe-inline'",
        "img-src 'self' data: https://a.espncdn.com https://g.espncdn.com https://mystique-api.fantasy.espn.com https://images.unsplash.com",
        "connect-src 'self' https://site.api.espn.com https://lm-api-reads.fantasy.espn.com",
        "font-src 'self'",
        "media-src 'none'",
        "worker-src 'none'",
        "manifest-src 'none'",
        "upgrade-insecure-requests",
    ]
    return "; ".join(policy)


def secure_html(source: str) -> str:
    if not source.startswith("<!doctype html>"):
        raise ValueError("Unexpected website HTML structure")
    parsed = inline_content(source)
    if any(meta.get("http-equiv", "").lower() == "content-security-policy"
           for meta in parsed.metadata):
        raise ValueError("Existing CSP must be audited before generating a new one")
    if "<head>" not in source:
        raise ValueError("No HTML head for CSP")
    csp = html.escape(csp_for_html(source), quote=True)
    return source.replace("<head>", "<head>\n"
                          '<meta http-equiv="Content-Security-Policy" content="' + csp + '">\n'
                          '<meta name="referrer" content="no-referrer">\n', 1)


def validate_svg(source: bytes) -> None:
    """A locally cached image must remain passive SVG, not active web content."""
    low = source.lower()
    for text in (b"<!doctype", b"<!entity", b"<script", b"<foreignobject",
                 b"<iframe", b"<object", b"<style", b"javascript:", b"<image",
                 b"onload=", b"onerror=", b"@import"):
        if text in low:
            raise ValueError("Cached SVG contains an active or external-content feature")


def build(root: Path = ROOT, output: Path | None = None) -> list[str]:
    output = output or root / "public"
    scan_for_secrets(root)
    if output.exists():
        if output.is_symlink() or not output.resolve().is_relative_to(root.resolve()):
            raise ValueError("Refusing unsafe output location")
        shutil.rmtree(output)
    output.mkdir(parents=True)
    raw = (root / "index.html").read_text(encoding="utf-8")
    (output / "index.html").write_text(secure_html(raw), encoding="utf-8")
    (output / ".nojekyll").write_text("", encoding="utf-8")

    for relative in STATIC_ASSETS:
        checked_copy(root, output, relative, required=True)

    for name in PUBLIC_DATA:
        relative = "data/" + name
        source = root / relative
        if source.is_file():
            value = json.loads(source.read_text(encoding="utf-8"))
            if not isinstance(value, dict):
                raise ValueError(f"Unexpected public JSON object: {relative}")
            checked_copy(root, output, relative)
            # Preserve the exact JSON data while omitting whitespace that
            # browsers otherwise download on every Pages data revalidation.
            (output / relative).write_text(
                json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n",
                encoding="utf-8",
            )
    editorial = root / "editorial/latest.json"
    if editorial.is_file():
        doc = json.loads(editorial.read_text("utf-8"))
        if doc.get("editorialStatus") != "owner-approved-on-merge":
            raise ValueError("Editorial JSON not marked for owner-approved merge")
        checked_copy(root, output, "editorial/latest.json")

    # Only the generated, sanitized ESPN logo cache is published, never the
    # original upload directory, drafts, scripts, workflows or repository data.
    manifest_path = root / "assets/fantasy-logos/manifest.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(manifest.get("teams"), dict):
            raise ValueError("Invalid ESPN logo cache manifest")
        for team_id, team in manifest["teams"].items():
            if not team_id.isdigit() or not isinstance(team, dict):
                raise ValueError("Invalid ESPN team logo entry")
            image = team.get("localUrl")
            if not image:
                continue
            if not re.fullmatch(r"assets/fantasy-logos/team-\d+\.(?:png|jpg|jpeg|webp|gif|svg)", image):
                raise ValueError("Unexpected generated team logo path")
            if f"team-{team_id}." not in image:
                raise ValueError("Logo identity does not match ESPN team ID")
            img = root / image
            if img.stat().st_size > MAX_IMAGE_BYTES:
                raise ValueError("Generated logo exceeds size limit")
            if img.suffix.lower() == ".svg":
                validate_svg(img.read_bytes())
            checked_copy(root, output, image, required=True)
        checked_copy(root, output, "assets/fantasy-logos/manifest.json")

    published = sorted(str(p.relative_to(output)) for p in output.rglob("*") if p.is_file())
    for relative in published:
        if (relative.startswith((".github/", "scripts/", "tests/", "assets/espn-logo-overrides/"))
            or relative.endswith((".py", ".md", ".yml", ".yaml", ".env", ".pem", ".key"))
            or "DRAFT" in relative):
            raise ValueError(f"Non-public file reached Pages artifact: {relative}")
    # Check the exact bytes that will be served, too.
    for relative in published:
        p = output / relative
        if p.suffix.lower() in TEXT_SCAN_EXTENSIONS and p.stat().st_size <= 2_000_000:
            data = p.read_text("utf-8", errors="replace")
            for label, pattern in SECRET_PATTERNS.items():
                if pattern.search(data):
                    raise ValueError(f"Potential {label} in Pages artifact: {relative}")
    return published


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    published = build(args.root)
    print("Secure GitHub Pages artifact: " + str(len(published)) + " allowlisted public files")
    for path in published:
        print("PUBLIC:", path)
