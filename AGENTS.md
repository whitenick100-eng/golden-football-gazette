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

## Editorial agent — manual, approval required
1. Add a repository Actions secret named `OPENAI_API_KEY` (Settings → Secrets and variables → Actions).
2. Go to Actions → **Draft Gazette Article (approval required)** → Run workflow.
3. Select the article type. The AI agent writes a Markdown draft using only the current checked-in structured data.
4. The workflow opens a pull request under `editorial/draft-...` for the owner to review. It does **not** merge or publish the draft.
5. GitHub repository settings may require enabling **Allow GitHub Actions to create and approve pull requests** (Settings → Actions → General), or the workflow's PR step will fail.
6. Review all statistics, league references, predictions and dates before merging. The draft is stored in `editorial/` and a candidate `editorial/latest.json` is included in the same PR. **Only after you merge** does the website display that approved edition in its "From the Editor" section.

## Design agent — owner-approved only
For design work, create a feature branch and pull request; inspect a preview or screenshots, then merge manually. There is intentionally no workflow that lets AI change `index.html` unattended.

## Troubleshooting
- Run `python -m py_compile scripts/*.py` and `python scripts/qa_gazette.py` locally.
- Check the **Data freshness summary** in GitHub Actions. A successful deployment does not prove ESPN responded.
- If `OPENAI_API_KEY` is absent, the editorial workflow will stop without changing the site.
- If a feed is stale, inspect the refresh step; do not change `fetchedAt` just to make it look fresh.
- GitHub scheduled workflows can run late. Refresh times are approximate.
