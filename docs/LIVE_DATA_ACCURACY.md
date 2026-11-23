# Live ESPN / NFL data accuracy — November 2026

The Golden Football Gazette is published on GitHub Pages (static hosting). It
does not own ESPN's scoring data or operate a real-time server.

## Fantasy matchup accuracy

- Browser requests use the 2026 **ESPN fantasy league 1413446022** and its
  current matchup/scoring period with the \`mTeam\`, \`mMatchupScore\`,
  \`mScoreboard\` and \`mLiveScoring\` views.
- A response is only accepted after **league, season, matchup period, ESPN game
  identifier, home team ID and away team ID** are checked.
- Missing games and partial scores **do not erase verified published results**.
  The matchup scoreboard reports how many matching games were verified.
- A final ESPN winner cannot silently revert to \`UNDECIDED\` due to an incomplete
  refresh. Corrected completed results are accepted when ESPN explicitly reports
  a valid final.
- Numeric 0.00 is preserved where ESPN explicitly reports it; unavailable or
  malformed scores are not fabricated or converted to zero.
- Browser polling is **best-effort**: approximately every 30 seconds during
  reported scoring, every 3 minutes otherwise. ESPN can block browser CORS,
  throttle requests or publish delayed values. The Gazette shows the last
  verified source time and its published daily snapshot as fallback.
- A GitHub Pages-only website **cannot guarantee second-by-second ESPN
  updates** without an independently operated, authorized backend feed.

## NFL games and player statistics

- A direct NFL scoreboard result must match the **ESPN event ID and both
  published opponent team abbreviations** before it can update the page.
- Missing or malformed team scores cannot overwrite verified scores. Earlier
  pregame/quarter states cannot overwrite a confirmed final result.
- Partially returned scoreboards keep previously verified games and identify
  the partial feed in the status message.
- Player yards and touchdowns come from ESPN's individual **game summary
  boxscore**, not guessed season values. The ticker verifies its event ID
  when the response provides that identifier.
- Final-game box scores are rechecked after a 15-minute cache period to pick
  up post-game statistical corrections.
- ESPN's generic scoreboard leader widget is labeled **ESPN SCOREBOARD
  LEADERS**, not automatically **season totals**, because the metric's scope
  cannot be safely inferred from that field alone.
- ESPN can revise official statistics. A legitimate correction may decrease
  fantasy points or yardage. The Gazette must not discard an authentic
  correction just because the new value is lower.

## Validation and boundaries

- \`tests/test_espn_matchups.js\` verifies team identity and atomic fantasy
  score overlays.
- \`tests/test_espn_refresh_integrity.py\` checks the server-side ESPN
  snapshot overlay.
- \`tests/test_live_nfl_scores.js\` verifies correct event opponents and state.
- \`tests/test_nfl_player_ticker.js\` guards against game/season mix-ups and
  wrong-game summary statistics.
- Existing **Gazette security gate**, data-backup, published-data monitoring
  and normal PR owner approval are preserved.
- No private ESPN cookies, credentials, paid agents or TinyFish integration
  are introduced. There are **no layout redesigns**.

## Top ticker: NFL-exclusive mode and seven-sport scores/news (November 23, 2026)

- **NFL is live:** At each visible-page check, the ticker first requests ESPN's NFL scoreboard. A game with ESPN `status.type.state === "in"` activates **NFL-only game statistics**. The original ESPN per-game box-score verification, timed final-stat rechecks, formatting, and marquee remain in place. Previous multi-sport cards are cleared before NFL game stats load.
- **NFL is not live:** If the scoreboard successfully confirms no in-progress NFL event, the same top ticker displays ESPN-reported NBA, WNBA, PGA, NCAA men's basketball, NCAA women's basketball, MLB, and NASCAR results plus their most recent ESPN headlines. This is not a redesign or an additional section.
- **Switching:** The page rechecks the NFL scoreboard about once a minute outside NFL games; during active games it uses the existing ~90-second player-stat refresh. Switching is automatic without a GitHub deployment.
- **Sources:** All seven scoreboard and league-specific news feeds use `https://site.api.espn.com/apis/site/v2/sports/`. Team scores must have both competitors and explicit ESPN numeric scores with an `in` or `post` event status. Golf/NASCAR leaders must have an explicit ESPN position of 1; PGA also requires a published score. Results older than 72 hours and headlines older than seven days are excluded.
- **Headlines:** Display verbatim (truncated) ESPN headlines as links to ESPN, marked **LATEST NEWS** unless ESPN labels the article as breaking or uses a breaking headline. Do not fabricate headlines or mislabel every recent article as breaking.
- **Data limits:** Unofficial ESPN endpoints can change, rate-limit or deny CORS. Feeds are best effort, checked only when the webpage is open, and reused for up to five minutes. Unavailable sports are skipped and partial feed coverage is disclosed. If NFL live status cannot be verified, do not assume there is no active NFL game.
- **Security:** Existing CSP still limits fetch destinations to ESPN and self, external article links are restricted to `https://www.espn.com/`, and the new script is in the security-reviewed public-site allowlist. No keys, cookies, new server, third-party scraping service, automatic design updates, or TinyFish.
- **Tests:** `node tests/test_multisport_ticker.js` and `node tests/test_nfl_player_ticker.js`, plus the existing required GitHub security gate and public-site tests.
