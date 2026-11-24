# Golden Football Gazette — phone-only hybrid layout

The original desktop Gazette stays visually and functionally unchanged. New mobile-only HTML nodes are hidden at desktop widths, and two allowlisted assets provide phone navigation and responsive sizing.

## Activation
1. Review and merge the mobile layout pull request after the required tests pass.
2. GitHub Pages deploys the merged site through the existing Refresh ESPN and publish Gazette workflow.
3. On phones with widths of 700 CSS pixels or less, the hybrid layout appears after a page reload. Desktop and most tablets (701px and above) show the classic layout without changes.
4. The Page One and Page Two article deep links are #page-one and #page-two, respectively.

## Mobile navigation
- HOME: Original masthead, turkey decorations and trophies, then existing ESPN sports ticker at the top only, two newspaper article previews, a swipeable real ESPN fantasy matchup center and quick links to league standings and trophies.
- SCORES: Original ten-sport ticker, NFL scoreboard, top fantasy players and verified reports.
- LEAGUE: ESPN fantasy team records, real matchup center, championship and consolation brackets, all reformatted vertically.
- GAZETTE: Dedicated reading pages for the factual 48-hour Page One report and the daily fictional-fan Page Two article. No page content or quotes are duplicated.
- MORE: Original supplemental NFL news, team logos, roster notes, injury reports and newspaper archives.

Bottom navigation exists only on phones. The sports ticker scrolls away naturally; it is never sticky. Swipe left/right to navigate real existing ESPN fantasy matchup cards, or use accessible previous/next buttons.

## Desktop isolation
The first rule of assets/mobile-gazette.css only hides new mobile-only nodes. All other style rules are under mobile-only media queries. The script assets/mobile-gazette.js refuses to change body layout, replace nodes, or intercept clicks on desktop viewports. No changes were made to desktop colors, fonts, stadium artwork, logo graphics, seasonal decorations, score logic or existing ESPN APIs. The actual desktop section elements remain mounted in the DOM.

The HTML reads the same existing ESPN data and newspaper feed. Do not substitute the sample scores from the approved conceptual image: those were a visual wireframe, not live data.

## Safety and checks
- The existing GitHub Pages CSP and static asset allowlist cover both new mobile resources.
- Python and Node offline tests verify desktop-width isolation, mobile routes, ESPN matchup reflow, article deep links, preserved source links, and accessibility.
- Source outages retain existing verified/historical fallbacks; no fabricated league scores are rendered.
