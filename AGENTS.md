# Golden Football Gazette — Hybrid Agent Operations

## Publishing policy (Option C)
- **Automatically publish only verified structured data:** ESPN league standings, matchup totals and projections **when supplied by ESPN**, NFL schedule/venues/team records, and weather forecasts with source and timestamp.
- **Never automatically publish AI-written articles or redesigns.** Drafts and design changes must be reviewed and merged by the repository owner via a pull request.
- Missing data is marked unavailable or left at its last verified timestamp; **do not fabricate** scores, weather, fantasy logos, brackets, player rankings, or quotes.
- The static website is hosted with GitHub Pages. The workflow requires no paid AI API for data refreshes.
- ESPN fantasy API access may be limited by league privacy. Never add ESPN cookies, API keys, or personally identifying member data to the public site.

## Existing automatic agents
1. **ESPN Data Agent**: `scripts/refresh_espn.py` — scheduled daily; writes sanitized `data/league.json` only if the response passes basic validation.
2. **NFL Schedule & Weather Agent**: `scripts/refresh_nfl.py` — scheduled daily; writes `data/nfl-week.json`. Open-Meteo weather is a forecast, not a verified game-day observation.
3. **Website QA Agent**: `scripts/qa_gazette.py` — checks required website sections and validates available data. `scripts/data_status.py` reports whether each feed is fresh, stale, unavailable, or invalid.
4. **Publisher**: `.github/workflows/refresh-and-deploy.yml` — runs the agents, QA, and then publishes to Pages. No editorial or design files are modified by the data agents.

## Daily ChatGPT newsroom agent — owner approval required

ChatGPT is the editorial writer, using the connected GitHub repository and standard web search. No separately billed API, TinyFish, or new paid service is authorized. The existing GitHub writer is a manually dispatched, data-only fallback with an empty API key.

Target: prepare a review PR before 7 AM Eastern; verified structured data continues on the existing Pages workflow. Publication of AI copy depends on the owner's merge and successful deployment. GitHub schedules are best effort.

For each daily ChatGPT run:
1. Read this file and the current main-branch editorial/latest.json. Inspect the live site's timestamped sanitized data/league.json, data/nfl-week.json, data/top-performers.json and other available verified feeds. Cross-check important claims against ESPN/NFL sources. If a feed is absent, stale, inconsistent or inaccessible, omit its claims; do not invent timestamps or statistics.
2. Write a new article as Adrian Mercer (fictional columnist), with headline, dateline, concise competitive commentary, source timestamps and an explicit distinction between facts, opinions and predictions. Never present invented quotes as real interviews.
3. Prepare editorial/latest.json with the existing date, articleType, body, sourceTimes and editorialStatus fields. Set generationMethod to chatgpt-draft-owner-review and editorialStatus to owner-approved-on-merge. Add fanInsights as an array of exactly ten objects, each containing team (exact current verified ESPN team name), quote (20–500 characters, single line), fictional (true). Use fresh, distinct, clearly fictional satire; omit the entire array if all ten current team names cannot be verified. Preserve the existing stable fictional supporter names.
4. On a separate date-specific branch, update only editorial/latest.json and create the matching editorial/YYYY-MM-DD-ARTICLE-TYPE-DRAFT.md with an unpublished approval notice. Check for an existing same-day review PR first; do not create duplicates or overwrite owner edits. Open a PR to main and send the owner its link. Never merge it automatically.
5. After owner merge, the existing Pages build incorporates today's valid fanInsights into the existing supporters' corner. Invalid, missing or stale drafts retain the deterministic fictional fallback. No HTML, CSS, JavaScript or security settings need to change.
6. Report what was verified, drafted, submitted and actually deployed separately. Never claim a draft was published merely because a PR exists. Structural changes require separate owner approval.

## Design agent — owner-approved only
For design work, create a feature branch and pull request; inspect a preview or screenshots, then merge manually. There is intentionally no workflow that lets AI change `index.html` unattended.

## Troubleshooting
- Run `python -m py_compile scripts/*.py` and `python scripts/qa_gazette.py` locally.
- Check the **Data freshness summary** in GitHub Actions. A successful deployment does not prove ESPN responded.
- The manual fallback produces a clearly labeled data-only review draft when at least one fresh feed exists.
- If a feed is stale, inspect the refresh step; do not change `fetchedAt` just to make it look fresh.
- GitHub scheduled workflows can run late. Refresh times are approximate.
