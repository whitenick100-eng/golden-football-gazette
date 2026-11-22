# Golden Football Gazette — repository security and merge protection

This is a **backend-only** security upgrade for
[whitenick100-eng/golden-football-gazette](https://github.com/whitenick100-eng/golden-football-gazette).
It does not change the newspaper's HTML, CSS, artwork, football data or reader-facing features.

## What is installed by the pull request

- **Gazette Required Security Gate**: a stable PR check named **Gazette security gate**.
  It runs on pull requests and pushes to \`main\`, validates workflow permissions,
  runs Python/JavaScript syntax checks, security unit tests and the actual
  GitHub Pages allowlist/CSP build checks. The gate fails on suspicious
  GitHub Actions triggers, overbroad token scopes, unapproved third-party
  Actions, unsafe checkout credentials or accidentally published files.
- **Actions checkout credential reduction**: all read-only workflows
  use \`persist-credentials: false\`. The editorial writer is the *sole*
  documented exception: it creates review-only editorial branches and PRs,
  using a scoped GitHub token. It does not auto-merge or auto-publish articles.
- **Dependabot**: the existing weekly GitHub Actions version updates are kept,
  and nonbreaking updates are grouped to reduce review noise. Dependabot
  submits PRs for your approval; it does **not** auto-merge.
- The existing CodeQL, publication allowlist, secret scans and backend
  verified-data recovery remain active.

## Action required in GitHub Settings after merging this PR

**Important:** A pull request CANNOT activate GitHub branch rules by itself.
The connected GitHub API currently cannot edit rulesets/branch protection.
You must do this once as the repository owner.

1. First merge the security PR **only after all existing CI checks pass**.
2. Go to [Settings → Rules → Rulesets](https://github.com/whitenick100-eng/golden-football-gazette/settings/rules)
   and select **New branch ruleset** (wording can vary).
3. Name it \`Protect Gazette main\`; set enforcement to **Active**.
   Target the branch named \`main\` only.
4. Select **Require a pull request before merging**.
   - If you are the only person reviewing and merging your own PRs,
     choose **0 required approvals** (no mandatory outside reviewer)
     so you do not lock yourself out. Every change still requires a PR and
     a green security check.
   - If you have a trusted collaborator, you can require **1 approving review**.
     GitHub does not count approval by the person who authored the PR.
   - Do not require Code Owner reviews unless an independent reviewer exists.
5. Select **Require status checks to pass before merging**.
   Add the check with the exact name:
   **\`Gazette security gate\`**
   This is the stable job name in \`.github/workflows/security-merge-gate.yml\`.
   You may also require \`scan-and-test\` (the existing public-site audit job)
   and the CodeQL analysis checks if they are available and consistently run.
   Select **Require branches to be up to date** if you prefer the strongest
   validation before each merge (it can add rebases/updates during active work).
6. Enable **Block force pushes** and **Restrict deletions** for \`main\`.
   Do **not** put yourself or the normal editor bot on a blanket bypass list
   unless you have an intentional emergency recovery procedure.
7. Save the ruleset. Open a harmless test PR to verify a failing required check
   blocks merging and a passing check permits the normal owner-reviewed merge.

The branch ruleset (not the CI file alone) is what **enforces** green checks
and PR-only changes. Until step 7 is completed, checks are advisory.

## Security settings to confirm

Under [Repository Settings → Security](https://github.com/whitenick100-eng/golden-football-gazette/settings/security_analysis),
check that **Dependabot alerts** and **Dependabot security updates**
are enabled if offered for your repository. Confirm secret scanning,
push protection, or code scanning features where your plan supports them.
The exact labels and feature availability can vary.

Under **Settings → Actions → General → Workflow permissions**, prefer the
**Read repository contents permission** default where compatible with
the editorial writer, whose workflow explicitly needs scoped
\`contents: write\` and \`pull-requests: write\` to open drafts. Keep
**Allow GitHub Actions to create and approve pull requests** enabled if
you want that existing editorial review workflow to create PRs.
No workflow in this upgrade merges its own changes.

## Checks and emergency handling

- For a red \`Gazette security gate\`, open the failed job's logs to find
  the token scope, unsafe action reference, bad file or failing website test.
- Do **not** disable the check or add a bypass just to get a merge through.
- CodeQL is a separate existing security scan; it is not replaced by the
  new gate.
- Backups and the manual verified-snapshot restore remain available under
  the previously installed workflows.
- The Pages artifact is still built from a fixed allowlist. It is not a
  backend capable of protecting a real web server or users' browser devices.
- No TinyFish automation or external security service was added.
