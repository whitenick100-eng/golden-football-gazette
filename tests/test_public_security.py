"""Offline security regressions: no network, secrets or paid services."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("gazette_secure_build",ROOT/"scripts/build_public_site.py")
build=importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)

class PublicSiteSecurityTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        (self.root/"assets").mkdir()
        (self.root/"assets/stadium-late-fall.webp").write_bytes(b"RIFF----WEBP")
        (self.root/"assets/live-nfl-scores.js").write_text("console.log('ok')\n")
        (self.root/"assets/nfl-player-ticker.js").write_text("console.log('verified ticker')\n")
        (self.root/"assets/espn-matchups.js").write_text("console.log('scoreboard')\n")
        (self.root/"assets/espn-team-logos.json").write_text("{}")
        (self.root/".github/workflows").mkdir(parents=True)
        (self.root/".github/workflows/publish.yml").write_text("secrets: PRIVATE\n")
        (self.root/"scripts").mkdir()
        (self.root/"scripts/private-helper.py").write_text("print('private helper')\n")
        (self.root/"editorial").mkdir()
        (self.root/"editorial/2026-11-20-DRAFT.md").write_text("private unpublished editorial draft")
        (self.root/"editorial/latest.json").write_text(json.dumps({
            "editorialStatus":"owner-approved-on-merge","body":"publicly approved edition"}))
        (self.root/"data").mkdir()
        (self.root/"data/league.json").write_text(json.dumps({"standings":[],"source":"ESPN"}))
        (self.root/"private-notes.txt").write_text("Notes not for visitors")
        scripts="\n".join(f"<script>const item{i}={i};</script>" for i in range(6))
        page="<!doctype html>\n<html><head><style>body{color:white}</style></head><body>"+scripts+"</body></html>"
        (self.root/"index.html").write_text(page)

    def test_public_artifact_contains_only_allowlisted_files(self):
        published=build.build(self.root)
        self.assertIn("index.html",published)
        self.assertIn("data/league.json",published)
        self.assertIn("editorial/latest.json",published)
        for excluded in [".github/workflows/publish.yml","scripts/private-helper.py",
                         "editorial/2026-11-20-DRAFT.md","private-notes.txt"]:
            self.assertNotIn(excluded,published)
            self.assertFalse((self.root/"public"/excluded).exists())

    def test_inline_scripts_allowed_by_hash_but_no_unsafe_inline_js(self):
        original=(self.root/"index.html").read_text()
        secured=build.secure_html(original)
        policy=build.csp_for_html(original)
        self.assertIn("script-src 'self'",policy)
        self.assertIn("script-src-attr 'none'",policy)
        self.assertIn("default-src 'none'",policy)
        self.assertIn(build.hash_source("const item0=0;"),policy)
        self.assertNotIn("script-src 'self' 'unsafe-inline'",policy)
        self.assertLess(secured.index("Content-Security-Policy"),secured.index("<style"))
        self.assertIn("no-referrer",secured)

    def test_credentials_blocked_without_echoing_secret(self):
        # Feed a simulated token into the scanner entirely in memory;
        # never persist even a fake credential-shaped string to disk.
        simulated = "sk-" + ("a" * 45)
        original_reader = Path.read_text
        target = self.root / "data/league.json"

        def in_memory_reader(path, *args, **kwargs):
            if path == target:
                return simulated
            return original_reader(path, *args, **kwargs)

        with patch.object(Path, "read_text", in_memory_reader):
            with self.assertRaises(ValueError) as error:
                build.build(self.root)
        self.assertIn("OpenAI API key", str(error.exception))
        self.assertNotIn(simulated, str(error.exception))

    def test_html_parser_rejects_unclosed_script_element(self):
        # An unterminated script must not be hashed and allowed to execute.
        source = '<script>console.log(1)'
        with self.assertRaises(ValueError):
            build.inline_content(source)

    def test_forbidden_dotenv_blocked_even_if_not_in_public_allowlist(self):
        (self.root/".env").write_text("MOCK=value")
        with self.assertRaises(ValueError) as e:
            build.build(self.root)
        self.assertIn("Forbidden credential-like file",str(e.exception))

    def test_reject_unknown_generated_logo_paths_and_symlinks(self):
        cache=self.root/"assets/fantasy-logos"
        cache.mkdir()
        (cache/"manifest.json").write_text(json.dumps({
            "teams":{"1":{"localUrl":"../../private-notes.txt"}}
        }))
        with self.assertRaises(ValueError):
            build.build(self.root)

    def test_block_active_svg_payload(self):
        for payload in (b'<svg><script>alert(1)</script></svg>',
                        b'<svg onload="alert(1)"/>',
                        b'<!DOCTYPE svg><svg/>',
                        b'<svg><style>@import url(https://evil)</style></svg>'):
            with self.assertRaises(ValueError):
                build.validate_svg(payload)
        build.validate_svg(b'<svg xmlns="http://www.w3.org/2000/svg"><circle r="3"/></svg>')

    def test_unapproved_editorial_does_not_publish(self):
        (self.root/"editorial/latest.json").write_text(json.dumps({
            "editorialStatus":"draft","body":"unpublished"
        }))
        with self.assertRaises(ValueError):
            build.build(self.root)

if __name__=="__main__":
    unittest.main()
