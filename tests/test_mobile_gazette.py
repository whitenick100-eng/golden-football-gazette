"""Offline assertions: mobile reflow must not alter desktop CSS or ESPN data."""
import re
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class GazetteMobileLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html=(ROOT/"index.html").read_text(encoding="utf-8")
        cls.css=(ROOT/"assets/mobile-gazette.css").read_text(encoding="utf-8")
        cls.js=(ROOT/"assets/mobile-gazette.js").read_text(encoding="utf-8")

    def test_mobile_stylesheet_has_no_desktop_visual_overrides(self):
        prefix,sep,rest=self.css.partition('@media screen and (max-width:700px){')
        self.assertTrue(sep,"Styles for the phone must be viewport-scoped")
        self.assertIn('.gazette-mobile-only{display:none!important}',prefix)
        self.assertNotIn('body{',prefix)
        self.assertNotIn('.gazette-masthead{',prefix)
        self.assertNotIn('#nfl-stat-ticker{',prefix)
        self.assertTrue(rest)
        self.assertIn('@media screen and (max-width:370px){',rest)
        self.assertNotIn('min-width:701px',rest)
        self.assertIn('body[data-gazette-mobile-view]',rest)
        self.assertIn('data-gazette-mobile-view="article-one"',rest)
        self.assertIn('data-gazette-mobile-view="article-two"',rest)

    def test_rivalry_header_stadium_and_trophies_remain(self):
        for marker in (
            'assets/stadium-nfl-unbranded.webp',
            'assets/rivalry-masthead.webp',
            'assets/golden-football-trophy.webp',
            'assets/golden-toilet-trophy.webp',
            'class="gazette-masthead rivalry-masthead"',
            'aria-label="Golden Football championship trophy"',
            'aria-label="Golden Toilet last-place trophy"',
            'class="paper"',
            'id="espn-games"',
            'id="nfl-stat-ticker"',
            'id="playoff-picture"',
            'id="championship-bracket"',
            'id="consolation-bracket"',
            'id="auto-coverage"',
        ):
            self.assertIn(marker,self.html,marker)
        self.assertEqual(self.html.count('id="espn-games"'),1)
        self.assertEqual(self.html.count('id="nfl-stat-ticker"'),1)
        self.assertEqual(self.html.count('id="playoff-picture"'),1)
        self.assertIn('<link rel="stylesheet" href="assets/mobile-gazette.css">',self.html)
        self.assertIn('<script src="assets/mobile-gazette.js"></script>',self.html)

    def test_phone_only_has_five_navigation_destinations(self):
        nav=re.search(r'<nav id="gazette-mobile-bottom-nav".*?</nav>',self.html,re.S)
        self.assertIsNotNone(nav)
        buttons=re.findall(r'<button\b[^>]*data-mobile-nav="([^"]+)"[^>]*>',nav.group(0))
        self.assertEqual(buttons,['home','scores','league','gazette','more'])
        for dest in buttons:
            self.assertIn('data-mobile-target="'+dest+'"',nav.group(0))
        self.assertIn('position:fixed!important',self.css)
        self.assertIn('safe-area-inset-bottom',self.css)

    def test_same_sport_ticker_is_ordered_below_mobile_masthead(self):
        self.assertIn('.wrap > .gazette-masthead{\n    display:grid!important;\n    order:1;',self.css)
        self.assertIn('.wrap > #nfl-stat-ticker{\n    order:3;',self.css)
        self.assertIn('body[data-gazette-mobile-view="home"] .wrap > #nfl-stat-ticker',self.css)
        self.assertIn('body[data-gazette-mobile-view="scores"] .wrap > #nfl-stat-ticker',self.css)
        self.assertIn('position:static!important',self.css)
        self.assertNotIn('tickerScrollSeconds',self.js)
        self.assertNotIn('fetch(',self.js) # Existing verified ESPN loaders are reused.
        self.assertIn('scroll-snap-type:x proximity',self.css)

    def test_phone_articles_use_original_article_elements(self):
        self.assertEqual(self.html.count('id="gazette-mobile-stories"'),1)
        self.assertEqual(self.html.count('data-mobile-target="article-one" aria-label="Read Page One'),1)
        self.assertEqual(self.html.count('data-mobile-target="article-two" aria-label="Read Page Two'),1)
        self.assertIn('.wrap > .paper{',self.css)
        self.assertIn('.paper > .page:first-child',self.css)
        self.assertIn('.paper > .page:nth-child(2)',self.css)
        self.assertIn('main.paper',self.js)
        self.assertIn('MutationObserver',self.js)
        self.assertIn('#page-one',self.js)
        self.assertIn('#page-two',self.js)

    def test_swipeable_existing_espn_matchups_and_fallback_links(self):
        self.assertIn('id="gazette-mobile-shortcuts"',self.html)
        self.assertIn('data-mobile-carousel="previous"',self.html)
        self.assertIn('data-mobile-carousel="next"',self.html)
        self.assertIn('#espn-games > *{',self.css)
        self.assertIn('scroll-snap-type:x mandatory',self.css)
        self.assertIn('scrollBy({left:width*direction,behavior:',self.js)
        self.assertIn('data-mobile-scroll-target="championship-bracket"',self.html)
        self.assertIn('data-mobile-scroll-target="consolation-bracket"',self.html)
        self.assertIn('data-mobile-scroll-target="standings"',self.html)
        self.assertIn('data-mobile-target="league" data-mobile-scroll-target="espn-live"',self.html)

    def test_mobile_links_are_buttons_and_readable_to_assistive_tech(self):
        self.assertIn('aria-label="Mobile primary navigation"',self.html)
        self.assertIn('aria-label="Mobile featured Gazette articles"',self.html)
        self.assertIn('aria-label="Mobile newspaper reading"',self.html)
        self.assertIn('aria-label="Navigate ESPN fantasy matchup cards"',self.html)
        self.assertIn(':focus-visible',self.css)
        self.assertIn("button.setAttribute('aria-current','page')",self.js)
        self.assertIn('role="navigation"',self.html)
        self.assertIn('Gridiron Giggles',self.html)

if __name__=="__main__":
    unittest.main()
