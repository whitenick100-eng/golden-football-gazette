#!/usr/bin/env python3
"""Gazette QA: block malformed data and ensure live page can render it."""
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def read_json(path):
    p = ROOT / path
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))

def valid_time(value):
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except (ValueError, AttributeError, TypeError):
        return False

def validate():
    page = (ROOT / "index.html").read_text(encoding="utf-8")
    for marker in ['id="nfl-games"', 'id="gazette-team-records"', 'id="championship-bracket"',
                   'id="espn-games"', 'id="nfl-status"']:
        assert marker in page, f"Website missing required section: {marker}"
    assert "data/nfl-week.json" in page and "data/league.json" in page
    # ESPN fantasy matchup center must be cards, not the old crowded text table.
    for marker in ('id="espn-live"', 'id="espn-games"', 'id="espn-week-select"',
                   'id="espn-week-prev"', 'id="espn-week-next"',
                   'id="espn-week-refresh"', 'id="espn-week-summary"',
                   'ESPN Fantasy Matchup Center'):
        assert marker in page, f"ESPN matchup center element missing: {marker}"
    assert '<script src="assets/espn-matchups.js"></script>' in page
    assert "<th>ESPN projected / actual points</th>" not in page
    cards = ROOT / "assets/espn-matchups.js"
    assert cards.is_file(), "Matchup renderer JavaScript missing"
    logic=cards.read_text(encoding="utf-8")
    assert "data/league.json" in logic and "winnerSide" in logic
    assert "actual fantasy points" in logic and "Projected final" in logic

    assert "40 — 50 — 40" not in page, "Old yard-number strip returned"
    assert 'id="gazette-current-datetime"' in page, "Live Gazette date/time missing from masthead"
    # Seasonal design is restricted to the masthead: the original turkeys,
    # accessible live clock and tournament branding must remain visible.
    assert '<header class="gazette-masthead thanksgiving-masthead">' in page
    assert page.count('class="dancing-turkey"') == 2
    assert 'src="assets/turkey-left.webp"' in page
    assert 'src="assets/turkey-right.webp"' in page
    assert 'The Golden Football Gazette</h1>' in page
    assert 'Thanksgiving Week · 2026 NFL Season' in page
    assert 'A Gridiron Thanksgiving Special' in page
    # The former flat illustrated pumpkins/bales are removed; the replacement
    # is a realistic fall harvest photo restricted to the title masthead.
    masthead=page.split('<header class="gazette-masthead thanksgiving-masthead">',1)[1].split('</header>',1)[0]
    assert 'thanksgiving-harvest-art' not in masthead
    assert 'id="harvest-pumpkin"' not in page and 'id="harvest-bale"' not in page
    assert 'images.unsplash.com/photo-1541480333465-b09786ad8ac6' in page
    assert "background-size:cover!important" in page
    assert 'content:none!important' in page
    assert 'background:linear-gradient(165deg,rgba(26,10,8,.96)' in page
    assert '.gazette-masthead.thanksgiving-masthead h1' in page
    assert 'color:#fff7e5!important' in page
    assert '.gazette-masthead.thanksgiving-masthead .masthead-live-date' in page
    assert 'animation:turkey-mascot-left' in page, "Dancing turkeys unexpectedly disabled"
    assert '@media(prefers-reduced-motion:reduce)' in page
    assert "new Intl.DateTimeFormat('en-US'" in page and "timeZone:'America/New_York'" in page
    assert "setInterval(refreshMastheadTime,60000)" in page, "Masthead clock must refresh every minute"
    # The owner chose a concise, consistent league identity across both the
    # records directory and the ESPN matchup center.
    full_name = "Gridiron Giggles Fantasy Football League"
    assert page.count(full_name) >= 2, "Full league name missing from accessible headings"
    assert "The White / Wilcox / Hulsey / Homan Fantasy Football League" not in page
    assert 'class="league-identity-heading"' in page
    assert 'class="league-identity-brand"' in page
    assert 'class="league-identity-family"' in page
    assert 'league-identity-kicker' in page
    assert "White/Wilcox Fantasy League" not in page, "Old league identity remains"
    assert "color:#ffdb9d" in page, "Gold team-name color was changed"
    assert "<h2>Our Fantasy League" not in page, "Former generic league header remains"
    assert "Thursday, November 19, 2026 · Week 11 Daily Brief</div>" not in page, "Old static masthead date remains"

    league = read_json("data/league.json")
    if league:
        if league.get("status") == "unavailable":
            print("WARNING: ESPN league unavailable; not asserting live league data")
        else:
            assert league.get("leagueId") == "1413446022"
            assert league.get("season") == 2026
            assert valid_time(league.get("fetchedAt"))
            teams = league.get("standings", [])
            assert len(teams) == 10 and len({t["teamId"] for t in teams}) == 10
            assert isinstance(league.get("matchups"), list)
            for g in league["matchups"]:
                assert isinstance(g.get("week"), int)
                for side in ("home", "away"):
                    assert isinstance(g[side].get("name"), str)
                    for key in ("points", "projectedPoints"):
                        v = g[side].get(key)
                        assert v is None or (isinstance(v, (int, float)) and not isinstance(v, bool) and 0 <= v < 1000)
    nfl = read_json("data/nfl-week.json")
    if nfl:
        if nfl.get("status") == "unavailable":
            print("WARNING: NFL schedule unavailable; not asserting live NFL data")
        else:
            assert valid_time(nfl.get("fetchedAt"))
            assert 1 <= nfl.get("week", 0) <= 22
            games = nfl.get("games")
            assert isinstance(games, list) and len(games) > 0
            for g in games:
                assert valid_time(g.get("date"))
                assert g.get("home", {}).get("name") and g.get("away", {}).get("name")
                if not (g.get("venue") or g.get("city")):
                    print("WARNING: NFL venue unavailable for game", g.get("id"))
                weather = g.get("weather")
                if weather:
                    assert weather.get("source") == "Open-Meteo" and weather.get("forecast") is True
                    assert -100 <= weather["temperatureF"] <= 150
                    assert 0 <= weather["precipitationChance"] <= 100
    injuries = read_json("data/nfl-injuries.json")
    if injuries:
        if injuries.get("status") == "unavailable":
            print("WARNING: First-string NFL out watch unavailable; official NFL injury link remains")
        elif injuries.get("filter") == "first-string-status-watch":
            assert valid_time(injuries.get("fetchedAt")), "Missing ESPN starter verification timestamp"
            assert injuries.get("season") == datetime.now(timezone.utc).year
            assert injuries.get("source") == "ESPN NFL injury listing + ESPN starting depth charts"
            assert set(injuries.get("positions",[])) == {"QB","RB","WR","TE","K"}
            assert isinstance(injuries.get("teams"), list)
            assert injuries.get("teamCount") == len(injuries["teams"])
            assert injuries.get("playerCount") == sum(len(t["players"]) for t in injuries["teams"])
            assert (injuries.get("outCount",0) + injuries.get("reserveCount",0) +
                    injuries.get("questionableCount",0) + injuries.get("doubtfulCount",0)) == injuries["playerCount"]
            assert isinstance(injuries.get("coverageComplete"),bool)
            assert 0 < injuries.get("depthChartTeamCount",0) <= injuries.get("injuryTeamCount",0)
            for team in injuries["teams"]:
                assert team.get("teamId") and team.get("name")
                assert isinstance(team.get("players"),list) and team["players"]
                for p in team["players"]:
                    assert p.get("name") and p.get("position") in {"QB","RB","WR","TE","K"}
                    assert p.get("depthRank") == 1 and p.get("starterSlot")
                    assert str(p.get("athleteId","")).isdigit()
                    assert p.get("outType") in {"out","reserve","questionable","doubtful"}
                    assert p.get("verificationSource") in {"ESPN injury listing","ESPN starter depth chart"}
                    assert p.get("reportedStatus") and "reportDate" in p
        else:
            print("WARNING: Existing injury snapshot predates first-string verification; refresh required")
    assert 'id="nfl-injury-report"' in page and 'id="injury-teams"' in page
    assert "data/nfl-injuries.json" in page
    # Only a chosen team is shown; OUT totals include all verified affected teams.
    assert 'id="injury-team-filter"' in page
    assert 'Select an NFL team' in page
    assert 'id="injury-count"' in page
    assert 'outTeams+' in page and 'totals.out+' in page
    assert 'All affected teams' not in page
    assert 'class="gazette-records-grid"' in page
    assert 'assets/espn-team-logos.json' in (ROOT/"assets/espn-matchups.js").read_text(encoding="utf-8")
    assert 'assets/fantasy-logos/manifest.json' in (ROOT/"assets/espn-matchups.js").read_text(encoding="utf-8")
    assert 'id="injury-position-filter"' in page
    assert 'NFL Key Starter OUT Watch' in page
    for marker in ('id="auto-coverage"', 'id="auto-coverage-stories"',
                   'id="player-stars"', 'id="player-star-meta"',
                   'id="championship-pairings"', 'id="consolation-pairings"'):
        assert marker in page, f"Missing automated newsroom element: {marker}"
    assert "data/weekly-features.json" in page and "data/top-performers.json" in page
    assert "Five Leading Fantasy Performers · Updated Tuesday Mornings" in page
    assert "age>48" not in page, "Weekly top five must not disappear after 48 hours"
    assert "tuesday_window_started" in (ROOT/"scripts/refresh_player_leaders.py").read_text(encoding="utf-8")
    leaders=read_json("data/top-performers.json")
    if leaders:
        if leaders.get("status") == "unavailable":
            print("WARNING: ESPN completed-week player leaderboard unavailable")
        else:
            assert leaders.get("leagueId")==1413446022 and leaders.get("season")==2026
            assert valid_time(leaders.get("fetchedAt"))
            assert isinstance(leaders.get("week"),int) and 1<=leaders["week"]<=22
            players=leaders.get("players")
            assert isinstance(players,list) and len(players)==5
            assert len({p["playerId"] for p in players})==5
            for p in players:
                assert p.get("name") and isinstance(p.get("playerId"),int)
                assert isinstance(p.get("points"),(int,float)) and 0<=p["points"]<250
                assert p.get("headshotUrl","").startswith("https://a.espncdn.com/i/headshots/nfl/players/full/")
    weekly=read_json("data/weekly-features.json")
    if weekly:
        assert valid_time(weekly.get("generatedAt"))
        assert weekly.get("status") in ("available","unavailable")
        assert isinstance(weekly.get("coverage"),list)
        for story in weekly["coverage"]:
            assert all(isinstance(story.get(k),str) and story[k] for k in ("headline","body","source","tag"))
        bracket=weekly.get("playoffs")
        assert isinstance(bracket,dict)
        if bracket.get("status")=="available":
            assert bracket.get("type") in ("provisional","espn-listed")
            assert len(bracket.get("contenders",[]))+len(bracket.get("outsideCurrentField",[]))==10
            assert bracket.get("playoffTeamCount")==len(bracket["contenders"])
    # Mobile-only reflow: no edits to desktop themes or ESPN sources.
    assert '<link rel="stylesheet" href="assets/mobile-gazette.css">' in page
    assert '<script src="assets/mobile-gazette.js"></script>' in page
    assert page.count('id="gazette-mobile-bottom-nav"')==1
    assert page.count('id="gazette-mobile-top-nav"')==1
    assert page.count('id="gazette-mobile-stories"')==1
    assert page.count('id="gazette-mobile-articlebar"')==1
    assert page.count('id="espn-games"')==1
    assert 'assets/stadium-nfl-unbranded.webp' in page
    assert 'assets/turkey-left.webp' in page and 'assets/turkey-right.webp' in page
    # The lead story is sourced by verified ESPN standings only; every covered
    # section gets an inspectable timestamp/semantic-change audit.
    assert '<script src="assets/lead-story-live.js"></script>' in page
    assert (ROOT/"scripts/gazette_section_audit.py").is_file()
    assert "The lead story · Historical Week 11 archive" in page
    # Automated newspaper: Page One is verified for 48h; Page Two refreshes
    # daily with explicitly fictional fan interviews (never attributed to real fans).
    assert '<script src="assets/dynamic-newspaper.js"></script>' in page
    assert 'data/gazette-pages.json' in (ROOT/"assets/dynamic-newspaper.js").read_text(encoding="utf-8")
    assert (ROOT/"scripts/build_newspaper_pages.py").is_file()
    assert 'Archived Week 10 edition' in page and 'Archived Week 11 fixture notes' in page
    publication=read_json("data/gazette-pages.json")
    if publication:
        assert publication.get("schema")==1 and str(publication.get("leagueId"))=="1413446022"
        assert publication.get("season")==2026
        assert valid_time(publication.get("builtAt"))
        one=publication.get("pageOne") or {}
        if one.get("status")=="verified":
            assert valid_time(one.get("publishedAt")) and valid_time(one.get("sourceAt"))
            assert len(one.get("standings") or [])==10
            names={t.get("name") for t in one["standings"]}
            assert all(x.get("winner") in names|{"TIE"} for x in one.get("finals",[]))
        else:
            assert one.get("status")=="unavailable"
        two=publication.get("pageTwo") or {}
        assert two.get("status")=="available" and valid_time(two.get("publishedAt"))
        assert two.get("fictionNotice") and "invented" in two["fictionNotice"]
        assert all(x.get("fictional") is True for x in two.get("interviews",[]))
    # Daily source-backed NFL trade/release/waiver desk.
    for marker in ('id="nfl-transactions-desk"','id="transaction-items"',
                   'id="transaction-filter"','id="transaction-freshness"'):
        assert marker in page, f"Missing daily NFL transactions view: {marker}"
    assert "data/nfl-transactions.json" in page
    assert 'Roster Wire · Key NFL Player Moves' in page
    assert "d.keyOnly!==true" in page, "Legacy all-NFL snapshot must be suppressed"
    assert "m.importanceBasis" in page, "Selected moves must show verified relevance"
    transactions=read_json("data/nfl-transactions.json")
    if transactions:
        if transactions.get("status")=="unavailable":
            print("WARNING: ESPN NFL transaction records unavailable")
        else:
            assert transactions.get("status")=="available"
            assert transactions.get("source")=="ESPN NFL transactions"
            assert valid_time(transactions.get("fetchedAt"))
            assert transactions.get("windowStart") and transactions.get("windowEnd")
            assert isinstance(transactions.get("moves"),list)
            if transactions.get("keyOnly") is not True:
                # Existing data from before upgrade must not be treated as
                # curated major transactions; browser will suppress it.
                print("WARNING: Legacy all-NFL transaction snapshot; key-player filter pending refresh")
            else:
                assert transactions.get("filter")=="verified-key-players-only"
                assert isinstance(transactions.get("playerCoverage"),dict)
                assert transactions.get("allESPNMovesChecked",0)>=transactions.get("total",0)
                assert transactions.get("total")>=len(transactions["moves"])
                for move in transactions["moves"]:
                    assert move.get("type") in ("Trade","Released","Waived")
                    assert move.get("team") and move.get("description")
                    assert isinstance(move.get("playerName"),str) and move["playerName"]
                    assert move.get("position")
                    assert move.get("importanceBasis") in (
                        "ESPN NFL first-string depth chart",
                        "Rostered in Gridiron Giggles ESPN fantasy league")
                    assert transactions["windowStart"]<=move.get("date","")<=transactions["windowEnd"]
                    assert isinstance(move.get("mentionedTeams"),list)
    # Verify public league identity and sharp stadium source remain reviewable.
    assert page.count("Gridiron Giggles Fantasy Football League") >= 2
    assert "The White / Wilcox / Hulsey / Homan Fantasy Football League" not in page
    assert 'league-identity-family">Fantasy Football League</span>' in page
    assert page.count("assets/stadium-nfl-unbranded.webp") >= 2, "Unbranded NFL-style stadium missing from desktop/mobile CSS"
    assert "photo-1781650104690-a5309d91a26b" not in page, "Old team-specific remote stadium must not remain"
    assert "assets/stadium-late-fall.webp" in page, "Local stadium fallback missing"
    # In-browser, auto-refreshed NFL scores supplement the daily static snapshot.
    for required in ('id="nfl-stat-ticker"', 'id="nfl-stat-track"',
                      'id="nfl-stat-ticker-mode"', 'id="nfl-stat-ticker-status"',
                      'id="nfl-stat-ticker-refresh"', 'id="roster-wire-health"',
                      'id="roster-wire-scan-details"', 'id="roster-wire-refresh"'):
        assert required in page, f"Ticker or roster health element missing: {required}"
    assert '<script src="assets/nfl-player-ticker.js"></script>' in page
    assert 'id="nfl-stat-ticker-title"' in page
    assert page.count('class="sports-ticker-tab"')==10
    assert ".nfl-stat-ticker:focus-within .ticker-animate" not in page, "Sport tab focus must never freeze the marquee"
    assert ".nfl-stat-ticker-window:focus-within .ticker-animate" not in page
    assert ".nfl-stat-ticker-window:has(a:focus-visible) .ticker-animate" in page
    assert "var(--gz-ticker-duration,72s)" in page
    assert 'id="sports-ticker-tabs"' in page
    for sport in ('ALL','NFL','NBA','WNBA','PGA','NCAA FB','NCAA MEN','NCAA WOMEN','MLB','NASCAR'):
        assert 'data-sport="'+sport+'"' in page
    assert page.index('id="espn-live"') < page.index('id="playoff-picture"') < page.index('id="auto-coverage"')
    assert page.count('id="playoff-picture"')==1 and page.count('id="consolation-bracket"')==1
    assert '<script src="assets/multisport-ticker.js"></script>' in page
    assert page.index('<script src="assets/multisport-ticker.js"></script>') < page.index('<script src="assets/nfl-player-ticker.js"></script>')
    multi=ROOT/"assets/multisport-ticker.js"
    official=multi.read_text(encoding="utf-8")
    assert "data/nascar-ticker.json" in official
    assert "https://www.nascar.com/" in official
    assert "racing/nascar-premier" not in official
    assert (ROOT/"scripts/refresh_nascar.py").is_file()
    assert "NASCAR.com" in (ROOT/"scripts/refresh_nascar.py").read_text(encoding="utf-8")
    assert multi.is_file() and "GazetteMultiSport" in multi.read_text(encoding="utf-8")
    assert "nflGameInProgress" in (ROOT/"assets/nfl-player-ticker.js").read_text(encoding="utf-8")
    # A short selected sport must move at the same px/sec as the long All Sports
    # rotation, even when the feed has only one item.
    ticker_src=(ROOT/"assets/nfl-player-ticker.js").read_text(encoding="utf-8")
    assert "const TICKER_PX_PER_SEC=44" in ticker_src
    assert "tickerRepeatCount(first.scrollWidth,tickerWindow?.clientWidth||bar.clientWidth)" in ticker_src
    assert "if(data.rows.length>1)" not in ticker_src, "Single-item sports must scroll"
    multi_src=multi.read_text(encoding="utf-8")
    assert "MAX_NEWS_AGE_MS=30*24*60*60*1000" in multi_src
    assert "MAX_SCORE_AGE_MS=8*24*60*60*1000" in multi_src
    assert "routine.slice(0,2)" in multi_src and "feed.news[3]" in multi_src
    assert "nflGameInProgress(nflBoard)" in ticker_src, "NFL live-only game statistics remain mandatory"
    ticker=ROOT/"assets/nfl-player-ticker.js"
    assert ticker.is_file(), "NFL ticker script not present"
    tick=ticker.read_text(encoding="utf-8")
    assert "summary?event=" in tick and "gameBoxStats" in tick
    assert "boardEvents(board).filter(g=>g.state==='in')" in tick
    assert "NFL LIVE GAME STATS · LOADING" in tick
    assert "const leaders=scoreboardLeaders(board)" not in tick, "Live NFL mode cannot show unverified season leaders"
    assert "FINAL_BOX_RECHECK_MS" in tick, "Final-game statistics must allow ESPN corrections"
    assert "verifiedGameUpdate" in (ROOT/"assets/live-nfl-scores.js").read_text(encoding="utf-8")
    assert "liveMatchupMerge" in (ROOT/"assets/espn-matchups.js").read_text(encoding="utf-8")
    assert "d.keyOnly!==true" in page and "FEED ACTIVE" in page
    assert 'id="live-score-status"' in page and 'id="refresh-nfl-scores"' in page
    assert 'data-nfl-game-id' in page or 'dataset.nflGameId' in page
    assert 'assets/live-nfl-scores.js' in page
    assert (ROOT/"assets/live-nfl-scores.js").is_file()
    script=(ROOT/"assets/live-nfl-scores.js").read_text(encoding="utf-8")
    assert "site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard" in script
    assert "setTimeout" in script and "ESPN Gamecast" in page
    print("Gazette structure and available data validation passed")

if __name__ == "__main__":
    validate()
