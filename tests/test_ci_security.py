"""Offline security policy regression tests; no credentials, GitHub API, or web calls."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "audit_ci_security", ROOT / "scripts" / "audit_ci_security.py"
)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class SecurityWorkflowAuditTests(unittest.TestCase):
    def test_current_repository_workflows_follow_security_policy(self):
        self.assertEqual(audit.audit(ROOT), [])

    def test_rejects_privileged_events_and_wildcard_tokens(self):
        source = """name: unsafe
on:
  pull_request_target:
permissions: write-all
jobs:
  unsafe:
    runs-on: ubuntu-latest
    steps:
      - uses: someone/unknown@main
"""
        text = " ".join(audit.audit_text("untrusted.yml", source))
        self.assertIn("privileged trigger", text)
        self.assertIn("global wildcard", text)
        self.assertIn("unapproved", text)

    def test_rejects_write_permission_in_unapproved_job(self):
        source = """name: danger
permissions:
  contents: read
jobs:
  audit:
    permissions:
      contents: write
"""
        text = " ".join(audit.audit_text("verify.yml", source))
        self.assertIn("unapproved write token permission", text)

    def test_trusted_codeql_and_deploy_write_scopes_are_allowed(self):
        codeql = """name: security
permissions:
  contents: read
  security-events: write
jobs:
  scan:
    steps:
      - uses: github/codeql-action/analyze@v4
"""
        self.assertEqual(audit.audit_text("codeql.yml", codeql), [])
        publisher = """name: deploy
permissions:
  contents: read
jobs:
  deployment:
    permissions:
      pages: write
      id-token: write
    steps:
      - uses: actions/deploy-pages@v4
"""
        self.assertEqual(audit.audit_text("refresh-and-deploy.yml", publisher), [])

    def test_read_only_checkout_must_not_keep_git_credentials(self):
        source = """name: tests
permissions:
  contents: read
jobs:
  tests:
    steps:
      - uses: actions/checkout@v4
      - run: python -m unittest
"""
        self.assertIn("checkout must disable", " ".join(audit.audit_text("checks.yml", source)))
        good = source.replace("      - run:", "        with:\n          persist-credentials: false\n      - run:")
        self.assertEqual(audit.audit_text("checks.yml",good),[])

    def test_only_editorial_workflow_can_retain_checkout_git_push_credentials(self):
        source = """name: editorial
permissions:
  contents: write
  pull-requests: write
jobs:
  writer:
    steps:
      - uses: actions/checkout@v4
"""
        self.assertEqual(audit.audit_text("draft-article.yml",source),[])
        self.assertIn("unapproved write", " ".join(audit.audit_text("verify.yml",source)))

    def test_no_workflow_symlinks(self):
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/".github"/"workflows"
            path.mkdir(parents=True)
            target=Path(t)/"foo"
            target.write_text("dummy")
            (path/"bad.yml").symlink_to(target)
            self.assertIn("workflow symlink", " ".join(audit.audit(Path(t))))


if __name__ == "__main__":
    unittest.main()
