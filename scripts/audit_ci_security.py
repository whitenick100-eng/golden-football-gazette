#!/usr/bin/env python3
"""Offline GitHub Actions security audit, with explicit exceptions for approved workflows.

This is intentionally a restrictive text check; it is NOT a full GitHub Actions
parser or a substitute for CodeQL, branch protection, or security reviews.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"

# Approved, scoped uses of write tokens. All other workflows should be read-only.
ALLOWED_WRITE = {
    ("codeql.yml", "security-events"),
    ("draft-article.yml", "contents"),
    ("draft-article.yml", "pull-requests"),
    ("refresh-and-deploy.yml", "pages"),
    ("refresh-and-deploy.yml", "id-token"),
    ("restore-verified-snapshots.yml", "pages"),
    ("restore-verified-snapshots.yml", "id-token"),
}
WRITER = "draft-article.yml"  # Checkout credentials only for PR-creating git push.
USE_RE = re.compile(r"^\s*(?:-\s*)?uses:\s*([^\s#]+)", re.M)
PERMISSION_RE = re.compile(r"^(\s*)permissions:\s*(.*?)\s*$")


def audit_text(filename: str, source: str) -> list[str]:
    issues = []
    if not re.search(r"(?m)^permissions:\s*$", source):
        issues.append("missing explicit top-level GitHub token permissions")
    for trigger in ("pull_request_target", "workflow_run"):
        if re.search(r"(?m)^\s*"+trigger+r":", source):
            issues.append("unreviewed privileged trigger: "+trigger)
    if re.search(r"(?mi)^\s*permissions:\s*(write-all|read-all)\s*$", source):
        issues.append("global wildcard GitHub token permissions are forbidden")

    for item in USE_RE.findall(source):
        # Only the repo's pre-reviewed first-party actions may run automatically.
        # @vN refs are tracked by Dependabot; @SHA is also accepted.
        if not re.fullmatch(r"(?:actions/[A-Za-z0-9_.-]+|github/codeql-action/[A-Za-z0-9_.-]+)@(?:v[1-9]\d*|[a-f0-9]{40})", item):
            issues.append("unapproved or unversioned GitHub Action: " + item)

    lines = source.splitlines()
    for i, line in enumerate(lines):
        match = PERMISSION_RE.match(line)
        if not match:
            continue
        level = len(match.group(1))
        if match.group(2) not in ("",):
            issues.append("permissions must list individual scopes")
            continue
        checked = 0
        for sub in lines[i+1:]:
            if not sub.strip() or sub.lstrip().startswith("#"):
                continue
            indent = len(sub) - len(sub.lstrip())
            if indent <= level:
                break
            field = re.fullmatch(r"([a-z-]+):\s*(read|write|none)\s*(?:#.*)?", sub.strip())
            if not field:
                issues.append("non-explicit token permission declaration")
                continue
            checked += 1
            key, value = field.groups()
            if value == "write" and (filename, key) not in ALLOWED_WRITE:
                issues.append("unapproved write token permission: " + key)
        if not checked:
            issues.append("empty token permission declaration")

    for check in re.finditer(r"(?m)^\s*-\s*uses:\s*actions/checkout@[^\s#]+\s*$", source):
        if filename == WRITER:
            # Checkout's authentication allows this owner-reviewed workflow to
            # push *draft editorial branches* and open pull requests, not merge.
            continue
        snippet = source[check.end():].splitlines()[:4]
        if not any("persist-credentials: false" in line for line in snippet):
            issues.append("checkout must disable credential persistence")
    return issues


def audit(root: Path = ROOT) -> list[str]:
    folder = root / ".github" / "workflows"
    if not folder.is_dir():
        return ["missing workflows folder"]
    findings = []
    workflows = sorted(folder.glob("*.yml"))+sorted(folder.glob("*.yaml"))
    if not workflows:
        return ["no workflow files"]
    for path in workflows:
        if path.is_symlink():
            findings.append(path.name + ": workflow symlink is not permitted")
            continue
        for finding in audit_text(path.name,path.read_text("utf-8")):
            findings.append(path.name + ": " + finding)
    return findings


def main():
    findings = audit()
    if findings:
        for finding in findings:
            print("::error::"+finding)
        return 1
    print("GitHub Actions security policy passed: scoped tokens, versioned trusted actions, "
          "non-privileged triggers and safe read-only checkouts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
