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

## NCAA football and intermediate scroll speed (November 23, 2026)

- When ESPN confirms **no NFL games are in progress**, the same off-NFL ticker includes **NCAA FBS football** game scores and ESPN football headlines, in addition to the seven previously supported sports. College football uses ESPN's `football/college-football` feed and the FBS group (`groups=80`) for its scoreboard. It only displays current/recent verified live or final scores, never estimates.
- **Strict live NFL override remains:** ESPN's NFL scoreboard is consulted before requesting or displaying off-NFL content. Any verified in-progress NFL game keeps the ticker **NFL-player-stats-only**, including while college football is live.
- **Moderate scrolling speed:** The marquee scrolls at approximately 30 pixels per second (minimum 100-second loop), between the original fast 65-second loop and the slower previous 25 pixels per second (minimum 120 seconds). Animation still adjusts to the real content width, pauses on hover/focus and respects reduced-motion settings.
- Missing or stale college football data is omitted instead of being invented. Source failures are disclosed; the website's existing ESPN-only CSP and security workflows are unchanged.

## Accurate news sport labels and clearer stadium presentation (November 23, 2026)

- **Keep sport tags visible.** Each news card retains the adjacent sport badge. Do not remove the tag or replace it with a generic "NEWS" category.
- **Verify topic before labeling.** ESPN league news feeds can cross-list stories. Use the article's canonical ESPN sport-specific URL path first; where the link is generic, use explicit `league`/`sport` article categories. Use the feed's sport only as a last resort when the article provides no more specific classification. Cross-listed NFL/NHL/soccer stories are excluded from the non-NFL rotation rather than falsely presented as another sport. Duplicate articles linked by more than one feed are shown once.
- **NFL-only priority is unchanged.** During an ESPN-verified live NFL game, only NFL player stats appear. News and non-NFL sports continue to use the existing off-NFL mode.
- **Speed:** Increase from about 30 to **32 pixels per second**, reducing the minimum full marquee cycle from 100 to **95 seconds**. This stays appreciably slower than the original fixed 65-second animation. Real content width, pause on hover/focus, and reduced-motion settings remain respected.
- **Stadium photo:** Retain the existing `assets/stadium-late-fall.webp` image and original layout. Soften the dark desktop/mobile gradients and reduce desktop translucent-panel backdrop blur from 3px to 1px, revealing clearer details. The mobile photo-only backdrop gets a subtle contrast/saturation/brightness lift. These are reversible CSS visibility enhancements, **not a resolution increase or a regenerated photo**, and text readability panel colors are preserved.
- **Regression tests:** `tests/test_multisport_ticker.js` validates sport-specific news URL/category precedence, rejects unsupported cross-listings, and de-duplicates headlines. `tests/test_nfl_player_ticker.js` checks the adjusted speed and CSS photo treatment.

## 2026-11-23: Featured news, verified scores, high-definition stadium, league identity

- **Verified scores lead:** Outside live NFL games, the marquee leads with ESPN-verified live/final results for every supported league with games. Each league can contribute up to three of its most recent results and a single significant news story. No missing score or event is fabricated; PGA and NASCAR continue to show verified scores/leaders rather than unsupported invented head-to-head matchups.
- **Important, recent news only:** Instead of arbitrary headlines from the previous week, consider only articles published within the previous **48 hours** whose headlines report a material development (e.g. meaningful trades, injuries, suspensions, coaching changes, postseason/championship developments, milestones). Reject low-value predictions, gambling guides, podcasts, filler and outdated content. Use ESPN's own lead order as a small editorial signal; article significance and freshness determine the shortlist. A **BREAKING** label requires an ESPN breaking designation and an article published within **12 hours**; older consequential items are **MAJOR NEWS**.
- **Popularity limitations:** The ESPN public league news endpoints do not supply independently comparable readership figures for all sports. The tracker prioritizes ESPN editorial news and material events, **not a claim that measured popularity or actual social virality is known**. News sport labels still follow the original article's canonical ESPN URL or league metadata; cross-listed irrelevant stories are excluded.
- **NFL exclusivity:** The ESPN NFL scoreboard is still checked *first*, and any game reported `in` makes the marquee display NFL player game stats only. Other sports are omitted until the NFL scoreboard verifies no active games. The refresh interval and existing team roster, matchup, and injury components remain unchanged.
- **Crisp stadium backdrop:** The site uses a verified **high-resolution American football stadium night photo** from [Scott Greer / Unsplash](https://unsplash.com/photos/a-crowded-football-stadium-at-night-under-bright-lights-b_XhrmGQnyc), requested at 3200px on desktop and 1800px on mobile. The previous local asset is a fallback layer. Dark readable editorial panels and the Thanksgiving masthead retain their design; the main backdrop no longer relies on a low-detail source image alone. The external Unsplash URL is already within the project's CSP `img-src` allowlist; the Unsplash source can fail or be blocked, in which case the local background remains available.
- **League name:** User-facing records and ESPN matchup headings and aria labels now use the exact name **Gridiron Giggles Fantasy Football League**, with the family surnames removed. Retain the two-line typographic brand and subtitle arrangement.

## Clickable sport filters, NFL off-game news and scores, and bracket placement

- A horizontal row of **blue accessible buttons** sits immediately above the stat marquee: **All Sports, NFL, NBA, WNBA, PGA, NCAA Football, NCAA Men's BB, NCAA Women's BB, MLB, NASCAR**. Buttons update `aria-pressed` and show only verified scores and high-impact recent headlines from the selected sport. `All Sports` restores the combined rotation. Buttons are keyboard accessible, and the row scrolls horizontally on mobile.
- On selection, the browser first checks ESPN's live NFL scoreboard. Any event with `status.type.state === 'in'` forces **current live NFL game player stats only**, overriding the previous selection. Non-NFL buttons are temporarily disabled and the NFL button becomes selected; after all NFL games finish, the previous selected filter resumes.
- **NFL added to off-game coverage** with the same score and significant recent news depth as other sports: up to three ESPN-verified recent team scores and one significant ESPN article, with the correct NFL sport badge. **During live NFL games there is no news, no other-sport scores, and no completed-game stat rows.** If boxscores are pending, display a truthful NFL live stats pending message.
- ESPN feeds cache independently for up to five minutes while the browser is open; changing sports does not reload every other league's news. The NFL scoreboard is checked first at each refresh so the live-only override remains authoritative.
- **Playoff Picture & Consolation Ladder** remains a single functional section, now immediately beneath the **ESPN Fantasy Matchup Center**, retaining all bracket and status element IDs, data logic and notices.
- No stadium image, masthead, typography, league records, or fantasy-playoff data are modified.

## Smooth, readable ticker and original unbranded NFL-style background (November 23, 2026)

- **Scroll speed:** The top tracker uses a content-width-adjusted speed of approximately **44 CSS pixels/second**, with a minimum **72-second** full scroll. The previous setting was 32px/s with a 95-second minimum. Applies to both multi-sport scores/news and live NFL player stats.
- **No second click after choosing a sport:** Earlier CSS paused animation whenever any descendant of the sticky ticker had focus, including the blue sport selection buttons. Pause selectors now apply only to the scrolling-content window. Hover pause works for hover-capable pointers, while keyboard users retain pause when focus is visibly on a linked headline/stat card. Clicking a blue sport tab no longer freezes the animation.
- **Neutral professional NFL-style stadium:** The repo now contains original, locally hosted **assets/stadium-nfl-unbranded.webp**, a high-detail 1672×941 stadium scene with professional American-football field markings, stadium lights, packed seating and no franchise names, logos or sponsor marks. It depicts a generic professional football venue, not an assertion that it is a specific existing NFL stadium. Desktop and mobile CSS both load this asset in place of the old remote Unsplash photo.
- The previous local assets/stadium-late-fall.webp remains as a fallback. The new roughly **403 KB WebP** is included in the reviewed public-site allowlist and secure-build regression tests.
- The Thanksgiving masthead, editorial design, accessible reduced-motion preference, verified sports feeds, and the rule of *NFL in-progress game player stats only* remain unchanged.

## November 23, 2026 — Consistent scroll velocity and regular sports news

- **All sport tabs scroll at the same speed:** Keep the established 44 CSS pixels per second for both All Sports and each individual league. The former minimum 72-second animation made selected leagues with short lists crawl. Duration now follows the *actual rendered content width*, with an 8-second safety minimum only for extremely short content; shorter lists repeat their verified cards until the track spans the viewport, then duplicate that sequence for seamless scrolling. Decorative repeats are removed from keyboard focus, while the original cards remain clickable. Even a single item now scrolls.
- **More news in every league tab:** ESPN breaking and major news keep top placement when verified, but are not the only eligible content. Show up to four dated league-specific articles in a selected sport, including regular reporting; All Sports shows up to two per league so the combined feed remains manageable. Prioritize up to two significant stories and up to two regular stories when available. Filter out predictions, gambling links, podcasts and other low-value filler. Never generate fake headlines.
- **Off-season fallback:** Prefer ESPN articles from the previous 14 days; if a league has no such content, allow news from up to 30 days ago with an explicit `OLDER NEWS` label and publication date. Other categories are `BREAKING` only within 12 hours with ESPN breaking evidence, `MAJOR NEWS` within 48 hours, `LATEST NEWS` for recent reporting and `RECENT NEWS` for the remainder of the fortnight. If ESPN has no eligible articles, show an honest data-unavailable message rather than invented news.
- **Scores remain first:** ESPN-verified live and final scores/results appear ahead of news. Extend final-score freshness from 72 hours to eight days so weekly leagues (NFL, NCAA football, PGA and NASCAR) continue displaying the preceding weekend’s verified scores, with the actual result date attached. Unverified/scheduled scores never appear as finals.
- **NFL-only rule remains:** The active NFL scoreboard is always checked before off-game content, and any in-progress game overrides all tabs with NFL player statistics only. No news, regular scores, or non-NFL content can appear during a live NFL game.
- **No design changes:** The blue tabs, sharp unbranded stadium, Thanksgiving details, league heading and ESPN Fantasy Matchup Center remain as merged.

## 2026-11-24 — automatic Page One every two days and Page Two every day

The owner requested separate editorial standards and publishing cadences for the two traditional newspaper pages.

**Page One · League Report (verified fact only; at most one new edition per 48 hours)**

- The scheduled `Refresh ESPN and publish Gazette` workflow now runs `scripts/build_newspaper_pages.py` after ESPN refresh and data-health recovery. It reads the *sanitized* `data/league.json` and, when fresh and structurally verified, writes a factual report to `data/gazette-pages.json`. Page One contains ESPN standings, current scoring period, confirmed winner-and-score fantasy matchups, current standings leader/last-place teams, and an optional recently verified rostered-player performance.
- An HTTPS fetch of the previous public `data/gazette-pages.json` is used to **retain Page One byte-for-byte** until 48 hours have elapsed since publication. A GitHub push or another daily run within that window must not rewrite factual Page One with new scores. After 48 hours, regenerate only from verified ESPN data. If ESPN cannot be verified, keep the last fact-checked page explicitly timestamped rather than inventing results.
- The 'positions' numbers are ESPN's sanitized standings order and not necessarily official playoff seeds or mathematically clinched berths. Finals are shown only when ESPN explicitly reports `HOME`/`AWAY`/`TIE`, the two side scores exist, and points agree with the winner status.
- Both publication and source timestamps appear in the reader's view. When the edition JSON is unavailable, old static Week 10 copy remains marked as **an archive**, not a live report.

**Page Two · Fixtures and League Notes (daily; clean, professional fictional satire)**

- Daily editions use the fictional professional columnist **Adrian Mercer**, introduced as a fictional pen name. Each edition rotates professionally playful banter and **ten explicitly invented fan interviews**, one imaginary fan for each ESPN-verified fantasy league team. They are neither recordings nor actual statements or endorsements from real participants.
- Upcoming ESPN-listed fantasy fixtures, standings-based championship/Golden Toilet commentary, and optional executed ESPN weekly waiver/free-agent acquisition **counts** remain factual and clearly distinguished from invented quotes. The waiver reader accepts only `mTransactions2` entries explicitly executed with an `ADD` item assigned to a known fantasy team. We never invent player identities, actual fan identities, team owner statements, outcomes, roster transactions, or closeness to playoff clinching.
- The daily edition updates its banter by Eastern calendar day. It uses no external generative API, secret, subscription, external scraping vendor, or AI-written purported news. It is deterministic satire with user-approved automatic publishing, not the separately review-gated `editorial/latest.json` writer.
- Publication is still governed by the existing strict Pages allowlist, CSP hashes, and checks. A failed GitHub Actions run or unavailable ESPN data can delay an update; timestamps make that limitation visible.

**Presentation and security:** `assets/dynamic-newspaper.js` renders `data/gazette-pages.json` using DOM `textContent` (no `innerHTML`). It preserves the stadium artwork, typography, fantasy matchup center and playoff brackets, and keeps historical static page fallback if a verified edition cannot be retrieved. The updated workflow adds the generator to the existing daily scheduled site deployment, not an additional background process.

## 2026-11-24 — Tuesday Top Five publication fallback and transparent status

The Five Leading Fantasy Performers section is a **weekly**, not a continuously live, award. Its source is ESPN's league-specific completed-week mBoxscore, including players on the ten fantasy teams' rosters and their benches. Unfinished matchup periods never replace confirmed actual scores.

The site's scheduled deployment at 6:43 a.m. EST on November 24 explicitly retained the previous confirmed ranking: that was the correct result because the code's Tuesday verification window opens at **8 a.m. Eastern**. The original daily GitHub cron runs at 13:17 UTC, or **8:17 a.m. EST / 9:17 a.m. EDT**, but GitHub can delay or omit scheduled workflow executions.

To make the weekly refresh more reliable, the same reviewed publishing workflow now also schedules a **Tuesday-only second attempt at 15:47 UTC (10:47 a.m. EST / 11:47 a.m. EDT)**. All other days remain on the existing once-daily cadence. Both attempts contact ESPN from the same script, use the same verified snapshot backup/recovery and security gate, and publish Pages only when existing critical data requirements pass. No stale scores are relabeled as fresh. The second run may still retain the previous verified ranking when ESPN has not finalized all matchups or mBoxscore data remains unavailable.

A new read-only check, `scripts/leaderboard_health.py`, writes the latest league matchup period, latest fully final ESPN week, published Top Five week, original source timestamp, and one of four explicit publication states to GitHub Actions output and its Job Summary. `RETRY_NEEDED` warns when the leaderboard is actually behind a fully completed ESPN week. `WAITING_FOR_ESPN_FINALS` means ESPN has not yet marked a newer week fully final. This monitor does **not** block a valid deploy, guess fantasy scores, call external services, or change site styling. Offline tests cover both states and the Tuesday-only retry.
