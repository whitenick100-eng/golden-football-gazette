# ESPN custom fantasy emblems — original owner-provided images

The five exact custom team emblems supplied as ESPN screenshots are stored here as transparent, cropped WebP images. These are the **actual pictured team emblems**, not substitutes.

| ESPN team ID | Team | Local image |
|---|---|---|
| 1 | Cam, Bam Thank you Ma'am. | `team-1.webp` |
| 4 | The Automatons | `team-4.webp` |
| 5 | 4th and 10 | `team-5.webp` |
| 7 | Fumbly In My Tumbly | `team-7.webp` |
| 9 | HVAC guru | `team-9.webp` |

During every GitHub Pages deployment, `scripts/cache_fantasy_logos.py` prioritizes these images and saves them under `assets/fantasy-logos/`. Other teams' standard ESPN CDN logos are retrieved and cached automatically.

These images are cropped from provided team-header screenshots, optimized for small website emblems. No private account credentials are stored here. **Images are public when the website is published.** If a team changes its logo in ESPN, replace that team's local image with the newer original file.
