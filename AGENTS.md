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

## Daily AI writer — automatic draft, owner approval required
The workflow is `.github/workflows/draft-article.yml`, displayed in GitHub Actions as **Daily Gazette Writer (approval required)**.

- **Daily:** GitHub schedules a new draft at **8:17 AM America/New_York** (adjusts for daylight saving time). GitHub may start scheduled work late.
- **Manual:** Open the workflow in Actions → **Run workflow**, choose `auto`, `daily-brief`, `week-preview`, or `weekly-recap`.
- **Edition selection:** `auto` selects a Tuesday recap, Thursday–Sunday previews, and daily briefs on other days.
- **Sources:** Each run retrieves its own fresh ESPN fantasy league and NFL schedule/weather snapshots. The writer refuses to invent data if neither source passes checks. Private ESPN leagues may be inaccessible.
- **AI:** Uses the `OPENAI_API_KEY` repository Actions secret and the configured API model (currently `gpt-4.1-mini`). Billing and rate limits apply **separately from ChatGPT**.
- **API unavailable:** Temporary 429 rate limits retry at most three times. Billing/credit/quota exhaustion, API errors, or a missing key produce a clearly labeled deterministic **verified-data bulletin** instead of an AI story, provided fresh source data exists. This fallback costs no OpenAI API tokens.
- **Approval:** Creates an `EDITOR REVIEW: Golden Football Gazette — YYYY-MM-DD` pull request containing an editorial Markdown draft and candidate `editorial/latest.json`. **Never automatically merges or publishes an article.** Only the owner's merge makes the approved article visible on the site.
- **Repository permission:** In Settings → Actions → General → Workflow permissions, enable **Allow GitHub Actions to create and approve pull requests**. The workflow will fail at the PR step if this is disallowed. It does not actually approve or merge PRs.
- **Data integrity:** Check every final score, matchup, statistical award, injury, forecast, and playoff statement before approval. There is no automatic player top-five ranking without verified player-level data.

Editor test suite: `python -m unittest discover -s tests -p "test_editorial.py" -v`.
On editorial pull requests, `.github/workflows/verify-editorial.yml` runs these tests without secrets or paid API calls.

## Design agent — owner-approved only
For design work, create a feature branch and pull request; inspect a preview or screenshots, then merge manually. There is intentionally no workflow that lets AI change `index.html` unattended.

## Troubleshooting
- Run `python -m py_compile scripts/*.py` and `python scripts/qa_gazette.py` locally.
- Check the **Data freshness summary** in GitHub Actions. A successful deployment does not prove ESPN responded.
- If `OPENAI_API_KEY` is absent or returns 429 due to exhausted credits, the writer produces a clearly labeled data-only review draft when at least one fresh feed exists.
- If a feed is stale, inspect the refresh step; do not change `fetchedAt` just to make it look fresh.
- GitHub scheduled workflows can run late. Refresh times are approximate.
