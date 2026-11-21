# Original ESPN custom fantasy emblems (optional owner copies)

ESPN's **private custom-logo endpoint returns HTTP 401** to GitHub's unauthenticated image downloader for the following five teams in league `1413446022`:

| Team ID | ESPN fantasy team | Upload original emblem as |
|---|---|---|
| 1 | Cam, Bam Thank you Ma'am. | `team-1.png` |
| 4 | The Automatons | `team-4.png` |
| 5 | 4th and 10 | `team-5.png` |
| 7 | Fumbly In My Tumbly | `team-7.png` |
| 9 | HVAC guru | `team-9.png` |

If you can save the actual logo from your signed-in ESPN fantasy team page, put the image at the corresponding path in this folder. Supported formats: PNG, JPEG (`.jpg` or `.jpeg`), WebP, GIF and SVG. File size maximum is 2 MB. For example: `assets/espn-logo-overrides/team-5.png`.

The Gazette's `scripts/cache_fantasy_logos.py` will automatically validate and use each owner-supplied image during deployment. Only one file per team ID should be present, and the file must be the team's actual ESPN logo (no fabricated replacements).

The other five teams' regular ESPN CDN emblems can be downloaded automatically. **Do not upload ESPN passwords, cookies, authentication tokens or private league member data.** The site is public, so any logo placed here will be publicly viewable after merging and deployment.
