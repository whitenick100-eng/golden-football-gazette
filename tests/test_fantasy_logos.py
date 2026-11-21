"""Offline ESPN fantasy-logo cache checks: no network or credentials."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PATH = Path(__file__).resolve().parent.parent / "scripts/cache_fantasy_logos.py"
spec=importlib.util.spec_from_file_location("gazette_fantasy_logos",PATH)
logos=importlib.util.module_from_spec(spec)
spec.loader.exec_module(logos)

class LogoCacheTests(unittest.TestCase):
    def test_espan_hosts_only(self):
        self.assertTrue(logos.allowed("https://g.espncdn.com/lm-static/logo.svg"))
        self.assertTrue(logos.allowed("https://mystique-api.fantasy.espn.com/apis/v1/domains/lm/images/x"))
        self.assertFalse(logos.allowed("http://g.espncdn.com/unsafe"))
        self.assertFalse(logos.allowed("https://g.espncdn.com.evil.com/x"))
        self.assertFalse(logos.allowed("https://other-site.example/logo.png"))

    def test_svg_scripts_and_external_images_removed(self):
        xml=b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script><image href="https://elsewhere.com/img"/><circle cx="5" cy="5" r="2" onload="bad()" /></svg>'
        kind, safe=logos.detect(xml,"image/svg+xml")
        self.assertEqual(kind,"svg")
        self.assertNotIn(b"<script",safe)
        self.assertNotIn(b"onload",safe)
        self.assertNotIn(b"https://elsewhere",safe)
        self.assertIn(b"circle",safe)

    def test_mime_and_signatures(self):
        self.assertEqual(logos.detect(b"\x89PNG\r\n\x1a\n" + b"abc","image/png")[0],"png")
        self.assertEqual(logos.detect(b"\xff\xd8\xff" + b"abc","image/jpeg")[0],"jpg")
        with self.assertRaises(ValueError):
            logos.detect(b"<html>Denied</html>","text/html")

    def test_cache_manifest_preserves_team_identity_and_failed_images(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            inp=root/"assets/espn-team-logos.json"
            inp.parent.mkdir(parents=True)
            source=json.loads((PATH.parent.parent/"assets/espn-team-logos.json").read_text())
            inp.write_text(json.dumps(source))
            with (patch.object(logos,"ROOT",root),
                  patch.object(logos,"INPUT",inp),
                  patch.object(logos,"OUTPUT",root/"assets/fantasy-logos"),
                  patch.object(logos,"download",side_effect=lambda u:("png",b"\x89PNG\r\n\x1a\n") if "mystique-api" in u else (_ for _ in ()).throw(ValueError("blocked")))):
                manifest=logos.build()
                self.assertEqual(len(manifest["teams"]),10)
                self.assertTrue(manifest["teams"]["1"]["cached"])
                self.assertFalse(manifest["teams"]["2"]["cached"])
                self.assertIsNone(manifest["teams"]["2"]["localUrl"])
                self.assertEqual(manifest["teams"]["2"]["name"],source["teams"][1]["name"])
                self.assertTrue((root/"assets/fantasy-logos/manifest.json").exists())


    def test_owner_provided_original_can_be_cached(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            folder=root/"assets/espn-logo-overrides"
            folder.mkdir(parents=True)
            (folder/"team-1.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"data")
            inp=root/"assets/espn-team-logos.json"
            inp.write_text((PATH.parent.parent/"assets/espn-team-logos.json").read_text())
            with (patch.object(logos,"ROOT",root),
                  patch.object(logos,"INPUT",inp),
                  patch.object(logos,"OUTPUT",root/"assets/fantasy-logos"),
                  patch.object(logos,"download",side_effect=ValueError("access denied")) as fetch):
                manifest=logos.build()
            self.assertTrue(manifest["teams"]["1"]["cached"])
            self.assertEqual(manifest["teams"]["1"]["localUrl"],"assets/fantasy-logos/team-1.png")
            self.assertEqual(fetch.call_count,9)

if __name__=="__main__":
    unittest.main()
