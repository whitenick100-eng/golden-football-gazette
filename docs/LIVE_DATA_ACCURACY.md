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
