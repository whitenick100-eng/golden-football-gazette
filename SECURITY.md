# Security policy — The Golden Football Gazette

## What this site is

The Golden Football Gazette is a **public, read-only GitHub Pages** website. Visitors do not create accounts, upload files, or run server-side code through the site. The data refreshes and optional editorial AI writer execute only in GitHub Actions, not on visitors' devices.

No public website can guarantee protection against all malware, phishing, compromised accounts, browser exploits, or data leaks.

## Protections provided by this repository

- **Allowlisted Pages publishing:** `scripts/build_public_site.py` copies only `index.html`, necessary local JavaScript/images, selected sanitized `data/*.json`, and the previously owner-approved `editorial/latest.json` into `public/`. The deploy workflow uploads `public/`, **not** the repository root. Python scripts, tests, workflows, private notes, `.env` files and `editorial/*DRAFT.md` are never included in the Pages artifact.
- **Browser Content Security Policy:** the generated public HTML includes a meta CSP with exact SHA-256 hashes for the current inline scripts/styles, local JavaScript only, an explicit allowlist for ESPN and Unsplash images, and ESPN scoreboard network access. Third-party scripts, `eval`, iframes, forms, and object/plugin content are blocked by policy in supporting browsers. A referrer meta tag limits URL leakage.
- **Automatic prevention checks:** the publishing workflow and the separate weekly `Security Audit - Public Gazette` workflow check obvious leaked credentials, verify the exact upload manifest, validate the CSP, run offline security regressions, and use GitHub CodeQL to inspect Python and JavaScript source for common security defects.
- **Update review:** Dependabot proposes GitHub Actions updates as pull requests instead of silently replacing deployment dependencies.
- **Editorial approval:** AI-written newspaper articles continue to require a separate pull request and an owner's merge. Source data from ESPN remains untrusted and is rendered by text-safe DOM APIs, not `innerHTML`.

## Limits of GitHub Pages security

GitHub Pages does **not provide application-layer authentication, custom server request filtering, firewall rules, or configurable response security headers** for this repository. A CSP delivered as a `<meta>` tag **cannot set `frame-ancestors`**, cannot prevent all clickjacking, and does not substitute for response headers. A CDN or hosting provider that controls HTTP response headers can offer stronger controls, WAF/rate limiting, bot protections and monitoring.

**The GitHub repository itself is public.** Scripts, workflows, editorial draft files committed to GitHub, images, and previous Git history can still be browsed through github.com even though they are not in the Pages artifact. The packaging change does not remove previously exposed information from Git history. If any credential has ever been committed, revoke/rotate it immediately and remove it from the repository/history using GitHub's secret exposure guidance.

### Settings the owner must enable in GitHub

1. In your GitHub account's **Password and authentication** settings, turn on two-factor authentication; consider a passkey or hardware security key.
2. Under the repository's **Settings → Rules → Rulesets**, require pull requests before merging into `main`, require successful security/build tests, and prevent force pushes. Set bypass permissions narrowly. **Not configured by the code in this PR.**
3. Under **Settings → Security & analysis** (labels may change), enable secret scanning/push protection, Dependabot security alerts, and code scanning where available. GitHub may offer some of these by default for public repos. **Not verified or enabled by this PR.**
4. Store `OPENAI_API_KEY` only in the repository Actions secrets; never in HTML, JavaScript, fantasy URLs, screenshots, notes or code. Limit API key scope and spending. Never add ESPN login cookies, passwords or session tokens.
5. Review any third-party GitHub Actions and proposed Dependabot updates. Revoke unused tokens, users, deploy keys and connected apps. No antivirus solution is able to inspect or secure every visitor's device.

### Operational verification

- Scheduled allowlist/token audit: **every Monday** and on proposed code changes. CodeQL source analysis: **every Tuesday** and on proposed code changes (results depend on GitHub Code Scanning being enabled/available).
- Pages deploy: `python scripts/build_public_site.py && python scripts/qa_public_site.py` must pass before upload.
- Browser: after deploying, check Console in developer tools for CSP violations or broken images/scoreboard requests.
- If the audit reports a possible secret, do **not** paste the secret into a public issue; rotate it and use a private reporting channel with the repository owner.

## Reporting a problem

Do not disclose passwords or API keys in a public GitHub issue. Contact the repository owner privately and provide steps to reproduce, affected file or URL, and the observed security issue without including sensitive tokens.
