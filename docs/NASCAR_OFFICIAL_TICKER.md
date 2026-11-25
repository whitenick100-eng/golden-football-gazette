# Golden Football Gazette — NASCAR.com-only top ticker source

The original top ticker, tabs, scroll speed, stadium background, desktop styling, phone layout and NFL live-game priority are unchanged. Only the NASCAR data source is different.

## Sources by sport

- **NASCAR**: NASCAR-owned `https://cf.nascar.com/cacher/{year}/1/race_list_basic.json` for Cup Series schedule, and verified `https://cf.nascar.com/cacher/{year}/1/{race_id}/weekend-feed.json` for official race winners. Optional current NASCAR.com article links are collected from `https://www.nascar.com/` and `https://www.nascar.com/news-media/` only when those sites permit GitHub Actions access. In November 2026, the public NASCAR.com article pages return 403 to the GitHub runner; the official CDN feeds respond successfully.
- **All eight other sports** (NFL, NBA, WNBA, PGA, NCAA Football, NCAA Men's and Women's Basketball, MLB): unchanged **ESPN scoreboard and news feeds**.
- An ESPN NASCAR racing query is **never used**, even as a fallback. ESPN cross-listed NASCAR headlines cannot slip into All Sports.

The publisher generates `data/nascar-ticker.json` from NASCAR.com-operated sources, which the ticker reads from the same website without cross-origin browser permissions. The NASCAR tab shows up to three recently completed, **officially confirmed Cup race winners** and up to three scheduled Cup races, with direct NASCAR.com links and dates; it also displays up to four dated NASCAR.com headlines when reachable. A winner is published only when NASCAR's own season race-list winner driver ID matches the sole first-place, non-disqualified driver in the official race weekend result feed. No race times or positions are inferred when NASCAR doesn't confirm them.

The next official Cup races can appear during the offseason when there are no live races. If NASCAR's feeds become unreachable, earlier officially confirmed NASCAR data can remain with its **original** source timestamp; stale or unverified entries are suppressed. An unavailable NASCAR.com source is never filled with ESPN racing data.

## Activation and checks

Review and merge the pull request after CI, including the live NASCAR-owned official-source smoke test, is green. The normal every-four-hour and pre-7 Eastern GitHub Pages builds automatically refresh the official NASCAR ticker JSON. No theme changes, external browser CORS allowances, API keys or paid services were added.
