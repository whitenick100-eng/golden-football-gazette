# Golden Football Gazette — backend reliability and recovery

This runbook applies to the existing 2026 ESPN Fantasy league **1413446022**.

## What runs automatically

The current "Refresh ESPN and publish Gazette" workflow now does the following:

1. Reads **only the six allowlisted JSON files** from the previous public GitHub Pages deployment via HTTPS. The data guard verifies league IDs, team/game counts, source timestamps, ESPN week direction and the published data structure before reusing anything.
2. Stores valid previously published data under the runner's **temporary** \`monitor/prior/\` and \`data/\` paths. These locations are NOT committed, and are NOT copied into GitHub Pages.
3. Runs the normal ESPN/NFL score, player, injury, transaction and daily feature refreshes. Existing source times remain intact.
4. Validates every resulting feed again. Invalid, missing or regressed files are recovered from the verified per-run prior snapshot when possible. The original \`fetchedAt\` or \`generatedAt\` stays the same. **Recovery is not a new live refresh.**
5. Fails the publishing build if the essential fantasy league or NFL schedule is missing, invalid or more than **48 hours** old. This prevents replacing the existing deployed site with a misleading new build. For other feeds, the report shows warnings instead of failing the entire newspaper for an isolated optional dataset.
6. On every run that reaches the health gate, saves a **checksummed copy of the valid data** plus a Markdown health report in a GitHub Actions artifact named:
   \`gazette-verified-snapshots-<run_id>\` (retained for **90 days**, subject to GitHub's repository/organization retention limits).
7. Writes data health findings to the workflow's **Actions job summary**. It does **not** publish operational logs, report files, back-up manifests, or new site elements.

The independent **Gazette Published Data Health (failure notifications)** action checks the live published JSON **once a day**, in addition to the main publisher's checks. It fails if essential public data is older than 48 hours or invalid.

The current weekly Top Five stays weekly; its monitoring limit is fourteen days, not 48 hours. Separate 72-hour warning thresholds apply to injury reports, roster transactions and verified news briefs.

## Private failure alerts: GitHub Actions notifications

The repository is **public**, so **GitHub Issues would be public**. This implementation deliberately does not post private-operational details to public Issues. Instead it uses normal failed-workflow notifications, delivered privately to your GitHub account/email when your notification preferences allow them.

Check **GitHub → Settings → Notifications → System → Actions**. Enable notifications for failed Actions workflows, including email notifications if you want an email. The exact interface labels may vary. If your notification settings suppress Actions failures, GitHub will still record failed check runs, but cannot force a private message to reach you.

Useful GitHub Actions workflows:
- **Refresh ESPN and publish Gazette**: automatic data refresh, recovery and deployment gate.
- **Gazette Published Data Health (failure notifications)**: daily independent health checks; a failure is an alert.
- **Restore verified Gazette snapshots (manual only)**: explicit operator-controlled recovery.
- **Verify Gazette Backend Recovery and Health Alerts**: offline integrity tests (never accesses ESPN).

## Restore a verified historical snapshot manually

Only use manual restoration if a recent deploy is broken or verified historical data must be reinstated. Note that restored historical scores remain historical; they do **not** become live just because they were redeployed.

1. Open **GitHub → Actions → Refresh ESPN and publish Gazette**, select the **last successful main-branch run with an archived backup**, and note the numeric run ID.
2. On that run's **Artifacts** section, confirm that \`gazette-verified-snapshots-<run_id>\` exists. This artifact contains an SHA-256 checksum manifest and the verified JSON documents.
3. Open **Actions → Restore verified Gazette snapshots (manual only) → Run workflow**, enter the **same numeric run ID**, and submit.
4. The restore action verifies that the backup run is a successful main-branch Gazette publishing run. It then validates each file against its manifest SHA-256 and the expected 2026 league and dataset schemas. Missing, edited, or mismatched backups are **rejected**.
5. The workflow builds and validates the **current approved HTML/CSS/JS unchanged**, using the operator-selected historical data, and deploys it through GitHub Pages. No content draft is merged, no data is fabricated, and TinyFish is not involved.
6. Review the deployment in GitHub Actions and the published page. A subsequent normal daily refresh may supersede the restored snapshot when the upstream feeds are healthy.

**Artifact caveats:** GitHub artifact retention varies by plan/repository settings. Historical archives may contain only the datasets that could be verified when the run occurred. Manual restore requires both the ESPN fantasy league and NFL schedule snapshots; otherwise it fails safely. This workflow is a **data rollback**, not a permanent deployment binary/site version archive or an automatic full-site rollback.

## Security boundaries and limitations

- Nothing in these workflows accesses private ESPN cookies or stores account tokens in the public site.
- The backup source is a **fixed, allowlisted public GitHub Pages HTTPS origin**; arbitrary user-supplied download URLs are not accepted.
- Data restored from public Pages is structural-validated but cannot prove ESPN's upstream correctness when ESPN itself is unavailable; source timestamps and original source names provide the provenance you can verify.
- The GitHub Actions artifact and job logs are repository resources, **not a secret-storage system**. Only already-public website datasets are archived. Do not add member emails, private credentials or personally identifiable information to these backups.
- The website's **visible design, styles, turkey masthead, matchups, logos, and buttons are not modified**.
- If the current GitHub Pages site is already unreachable and ESPN is also unreachable, there may be no safe automatic fallback; the publish gate fails and signals the issue rather than inventing content.
- A GitHub Actions schedule is best-effort and may run late. The independent monitor catches silent aging data after a skipped run.
- The guard currently validates only **the 2026 season**; before changing to 2027, update league/year assertions together with the existing ESPN agents and regression tests.
