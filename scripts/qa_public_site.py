#!/usr/bin/env python3
"""Verify exactly what GitHub Pages will serve before starting deployment."""
import html
import re
from pathlib import Path

from build_public_site import OUT, ROOT, PUBLIC_DATA, hash_source, inline_content

def check(root=ROOT, output=OUT):
    if not (output/"index.html").is_file():
        raise ValueError("No secure Pages artifact; run build_public_site.py first")
    raw=(root/"index.html").read_text("utf-8")
    rendered=(output/"index.html").read_text("utf-8")
    assert rendered.count('http-equiv="Content-Security-Policy"')==1
    parsed = inline_content(rendered)
    policies = [m.get("content") for m in parsed.metadata
                if m.get("http-equiv", "").lower() == "content-security-policy"]
    assert len(policies) == 1, "Missing early enforcement policy"
    policy = html.unescape(policies[0])
    assert rendered.index('http-equiv="Content-Security-Policy"')<rendered.index("<style")
    assert "default-src 'none'" in policy
    assert "script-src-attr 'none'" in policy
    assert "object-src 'none'" in policy and "frame-src 'none'" in policy
    assert "form-action 'none'" in policy
    assert "'unsafe-eval'" not in policy
    script_part=policy.split("script-src 'self' ",1)[1].split("; ",1)[0]
    assert "'unsafe-inline'" not in script_part
    for tag, attrs, content in inline_content(raw).blocks:
        if tag == "script" and "src" not in attrs:
            assert hash_source(content) in script_part, "Inline JS would be blocked by CSP"
        if tag == "style":
            assert hash_source(content) in policy, "Inline CSS would be blocked by CSP"
    assert 'name="referrer" content="no-referrer"' in rendered
    assert rendered.count("<script")==raw.count("<script"), "Scripts were unexpectedly changed"

    public_files={str(p.relative_to(output)) for p in output.rglob("*") if p.is_file()}
    required={"index.html",".nojekyll",
              "assets/stadium-late-fall.webp",
              "assets/live-nfl-scores.js",
              "assets/espn-team-logos.json"}
    assert required.issubset(public_files), "Missing required web assets"
    allowed=required | {"editorial/latest.json"} | {"assets/fantasy-logos/manifest.json"}
    allowed.update("data/"+name for name in PUBLIC_DATA)
    for name in public_files:
        if re.fullmatch(r"assets/fantasy-logos/team-\d+\.(?:webp|png|jpg|jpeg|gif|svg)",name):
            continue
        if name not in allowed:
            raise ValueError("Unexpected file in public site: "+name)
    assert not any(x.startswith((".github/","scripts/","tests/")) or "DRAFT" in x
                   for x in public_files)
    print("Security QA passed:",len(public_files),"public-only files, strict script hashes, no repository internals")

if __name__=="__main__":
    check()
