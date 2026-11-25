# Gazette early-morning publishing and section verification

This change is backend / content-freshness-only. It preserves every existing desktop and phone layout, image, Thanksgiving turkey, trophy, team logo, color and font. It does not write unreviewed editorial or alter ESPN scores.

## Daily publishing

The existing four-hour publisher, Tuesday fantasy leaderboard refresh and Tuesday fallback are preserved. An extra daily GitHub Actions attempt runs at **10:05 UTC**, or **5:05 a.m. EST / 6:05 a.m. EDT**. It executes the existing ESPΝ league/NFL verified data refreshes, validated backup recovery, official newspaper generator, security checks and GitHub Pages deployment. **GitHub scheduled Actions can start late or fail**; a 7:00 a.m. Eastern guarantee is not possible with GitHub's best-effort scheduler. The separate already-active ChatGPT automation, Gazette 7 AM Verification, checks for that condition and reports it rather than inventing successful updates.

The existing Pages deployment depends on its build passing and retains its security/content allowlists. Section audits do not override failures or let unverified scores into the site.

## Section audit

Each successful build now publishes a public, read-only JSON at:

https://whitenick100-eng.github.io/golden-football-gazette/data/daily-update-report.json

GitHub Actions also displays the report in its build summary.

The report covers these **eleven individually verified sections**:

1. Lead Story
2. ESPN Fantasy Matchup Center
3. Playoff Picture
4. Consolation Ladder
5. Today's Football Desk
6. From the Editor
7. NFL Week in Review and Preview
8. Page One League Report
9. Page Two Fixtures and League Notes
10. NFL Key Starters OUT / Questionable / Doubtful / IR
11. NFL Waivers and Key Roster Wire

It compares the newest verified section payload and original source time with the previous published audit, not just file modification time. Possible states include UPDATED, VERIFIED_BASELINE (initial report), UNCHANGED_VERIFIED, STALE, UNVERIFIED, CHANGED_WITHOUT_NEW_SOURCE, ARCHIVE_FALLBACK, APPROVAL_REQUIRED and OWNER_APPROVED_ARCHIVE. Sections that did not actually change are **not** marked updated.

The source-at timestamp is retained when ESPN's previous snapshot was used. A GitHub build success does not prove publication: the ChatGPT 7:00 a.m. verification automation must separately check the actual Pages deployment and live JSON.

The lead story now reads the existing verified, source-labeled Fantasy League newsroom item and only updates if the ESPN league source is within 48 hours. The original Week 11 story is explicitly labeled a **historical archive** until verified fresh content arrives. The original newspaper styling remains unchanged; fetched content is rendered with safe DOM textContent.

Page One remains on the agreed **48-hour factual cadence**, not an invented daily rewrite. Page Two remains a **daily, clearly fictional fan-interview column** with source-verified fixtures. New independently authored From the Editor articles remain subject to **owner approval and merge**. Existing approved editions retain their approval status; no scheduled job pretends to approve them.

## How to activate

Review the PR and merge after security/CI checks pass. The push-to-main publishing workflow will build and deploy the result. The existing daily 7 AM Eastern ChatGPT verification task is already active and can inspect the report after the next successful deployment. A scheduled GitHub trigger cannot be guaranteed to finish by 7 AM; the verification must flag any delays, failed runs or stale source feeds.

No new secrets, paid APIs, credentials or unreviewed posts were introduced.
