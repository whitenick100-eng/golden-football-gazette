# Golden Football Gazette — NASCAR.com-only top ticker source

## Source isolation

The top sports ticker keeps its existing graphics, colors, moving animation, sport tabs, speed, caching, and live-NFL override. **Only NASCAR has changed its data source.**

- NFL, NBA, WNBA, PGA, NCAA Football, NCAA Men's Basketball, NCAA Women's Basketball and MLB: **unchanged ESPN news + scoreboard endpoints**.
- NASCAR: **NASCAR.com only**. The scheduled GitHub Pages publisher fetches dated news permalinks from `https://www.nascar.com/` and `https://www.nascar.com/news-media/` and creates a small, sanitized `data/nascar-ticker.json` on the same website. No ESPN racing feed is contacted or used for NASCAR, even when other ESPN news feeds cross-list a NASCAR article.
- Both **All Sports** and **NASCAR** tabs read exactly the same NASCAR.com JSON source. The NASCAR articles link directly to their original NASCAR.com stories.

### Official results and honesty

The official NASCAR.com homepage provides verifiable dated NASCAR.com news links. The ticker does not infer live positions, race leaders or winners from a headline. **NASCAR headlines are published; racing score rows remain empty until a separately verifiable NASCAR.com race-result feed can be integrated.** An official story describing a race finish can appear as news, but will not be relabeled as a live race score. No ESPN racing fallback is allowed.

For each story, the calendar date is parsed from the date embedded in its official NASCAR.com article URL (not an invented hour of publication). Items older than 30 days are suppressed. The news fetch is refreshed by the site's existing 4-hour and early-morning GitHub Actions workflows. When NASCAR.com is temporarily unavailable, an older NASCAR.com-only verified snapshot may be retained with its original `fetchedAt` timestamp. If no verifiable NASCAR.com headlines remain, the NASCAR tab shows the existing unavailable/empty ticker state rather than fake stories or ESPN racing content.

### Activating

Review and merge the pull request after checks pass. The existing website build then publishes the new NASCAR JSON file, and the mobile/desktop sports ticker uses it automatically. Site visuals and all eight other sports are unaffected. GitHub Actions logs say how many NASCAR.com headlines were verified; upstream availability can cause partial results.
