# Phase 2: Structural & Architectural Review

## Summary

The site is well-built for its purpose — a clean, static academic personal page with minimal attack surface and thoughtful security controls. The top priorities are: (1) adding a 404 page (currently missing entirely), (2) fixing the `aria-current="page"` nav indicator bug identified in Phase 1, (3) adding build CI to prevent regressions on merge, and (4) addressing the nested repo layout which complicates Cloudflare Pages build paths and developer orientation. No critical security issues were found; the findings below are primarily structure, DX, and accessibility improvements.

## Findings

### 2a. Repo Layout

- **Finding:** The repository has a nested structure: the git root is `jpwolfson-site/` but the Eleventy project lives at `jpwolfson-site/jpwolfson-site/`. This means Cloudflare Pages must be configured with `jpwolfson-site` as the root directory and `jpwolfson-site/_site` as the build output — a non-obvious two-level nesting. The outer root contains `SECURITY.md`, `export-wp-stats.py`, `.github/workflows/`, and `security-audits/`. The inner directory contains everything Eleventy needs plus utility scripts (`apply_phase2.py`, `apply_phase3.py`, `crawl_links.py`) and `link_audit.json`. There is no README at the repo root, so a new contributor (or the site owner returning after months) has no orientation. The `.gitignore` at the repo root contains `node_modules/`, `_site/`, `.DS_Store` — correct but only applies at the outer level; a matching `.gitignore` is not present in the inner directory (not currently needed since the outer one covers paths via prefix matching).
- **Severity:** medium
- **Category:** structure / DX
- **Remediation:** Promote the inner `jpwolfson-site/` contents to the repo root. Move `package.json`, `.eleventy.js`, `src/`, `oauth-worker/` etc. to the top level. Keep `security-audits/`, `SECURITY.md`, and `.github/` where they are. Update the Cloudflare Pages build config to use `/` as root directory and `_site` as output. Update `config.yml` media_folder from `jpwolfson-site/src/files` to `src/files` and all file paths from `jpwolfson-site/src/content/...` to `src/content/...`. Update the CI workflow `working-directory` and paths triggers. This is a one-time coordinated change that simplifies everything downstream. If promotion is too disruptive right now, at minimum add a root-level `README.md` explaining the layout.

### 2b. Build Config

- **Finding:**
  - `.eleventy.js` (16 lines) uses ESM `export default` correctly, matching `"type": "module"` in `package.json`. No issues with the ESM setup.
  - `package.json` has zero `devDependencies` — no linter, no formatter, no link checker. The only dependency is `@11ty/eleventy` under `dependencies` (should arguably be `devDependencies` since it's a build tool, not a runtime dependency, though this has no practical impact for a static site).
  - Build scripts are limited to `"build": "eleventy"` and `"start": "eleventy --serve"`. There is no `clean` script (to remove `_site/`), no `lint` script, no `test` script.
  - `package-lock.json` is present, lockfileVersion 3, correctly committed. Lockfile hygiene is good.
  - `npm audit` reports 1 high severity vulnerability (minimatch ReDoS in transitive build dep) — this was already documented in Phase 1 and accepted in `SECURITY.md`.
  - The `^3.0.0` semver range for Eleventy means `npm install` could pull a future Eleventy 3.x with breaking changes. The lockfile mitigates this, but pinning to `~3.1.2` would be more defensive.
- **Severity:** low
- **Category:** DX
- **Remediation:** (1) Add a `"clean"` script: `"clean": "rm -rf _site"`. (2) Consider adding `"test": "eleventy --dryrun"` as a basic smoke test. (3) Move `@11ty/eleventy` to `devDependencies` for correctness. (4) Consider tightening the version range to `~3.1.2`. These are all minor DX improvements with no urgency.

### 2c. Template Architecture

- **Finding:**
  - A single `base.njk` layout (71 lines) serves all 12 pages. For a site of this size and uniformity, one template is appropriate — all pages share the same header/nav/footer structure. No template proliferation needed.
  - **No 404 page exists.** After build, `_site/404.html` is absent. Cloudflare Pages will serve its generic 404 page for unknown routes. This is a functional gap — visitors hitting a broken link will see a Cloudflare-branded error, not a page consistent with the site.
  - **No `<meta name="description">` tag.** The `<head>` in `base.njk` has no description meta tag. This hurts SEO and produces blank previews when the site is shared on social media or in search results.
  - **No Open Graph / Twitter Card tags.** Sharing links on social media will produce a bare title with no description or image preview.
  - **`aria-current="page"` bug (from Phase 1):** CSS at `style.css:72` styles `nav a[aria-current="page"]` but `base.njk:50-58` never sets this attribute on any link. The nav highlight for the current page does not work.
- **Severity:** medium (404), low (meta/OG), medium (aria-current, Phase 1 carry-forward)
- **Category:** accessibility (aria-current), performance/SEO (meta), structure (404)
- **Remediation:** (1) Create `src/content/404.md` with frontmatter `permalink: /404.html` and a friendly "page not found" message. Cloudflare Pages automatically serves `_site/404.html` for 404 responses. (2) Add `<meta name="description" content="...">` to `base.njk`, using a frontmatter `description` field or a sensible default. (3) Add minimal Open Graph tags (`og:title`, `og:description`, `og:type`). (4) Fix `aria-current="page"` in `base.njk` by adding Nunjucks logic: `{% if page.url == "/papers/" %}aria-current="page"{% endif %}` on each nav link (or use a loop with a conditional).

### 2d. CSS Architecture

- **Finding:**
  - `style.css` is 192 lines, well-organized with clear section comments. Custom properties at `:root` (lines 6–14) are used consistently throughout.
  - **Single breakpoint at 600px** (`@media (max-width: 600px)`, line 188). This only adjusts padding and nav gap/font-size. There is no intermediate breakpoint for tablets (~768px–1024px). On a 1100px-max layout this is generally acceptable for a text-heavy academic site, but the nav with 8 links (`flex-wrap: wrap`) may wrap awkwardly on medium-width screens around 700–900px.
  - **Unused CSS rules:** `.section-label` (line 126) and `.member-section h2` (line 138) are used via inline HTML classes in the markdown files — these are legitimately used. `.video-wrapper` (line 169) is used in `mathematics-and-dance.md` and `roosevelt-institute.md`. No obviously dead CSS was found.
  - **Accessibility — contrast ratios:** `--muted: #555` on `--bg: #ffffff` yields a contrast ratio of ~5.9:1, passing WCAG AA (4.5:1) for normal text. `--accent: #1a4a7a` on white yields ~7.2:1, also passing AA. `--text: #1a1a1a` on white is ~16.6:1, excellent. All color combinations pass AA.
  - **Accessibility — focus states:** No explicit `:focus` or `:focus-visible` styles are defined. The browser's default focus ring applies, which is acceptable but may be invisible or inconsistent across browsers, especially since `text-decoration: none` is set on links and the nav links have `border-bottom: 2px solid transparent`.
  - **Accessibility — skip-to-content:** No skip-to-content link exists. Screen reader and keyboard users must tab through all 8 nav links before reaching main content on every page.
- **Severity:** low (breakpoint), medium (focus states), medium (skip-to-content)
- **Category:** accessibility
- **Remediation:** (1) Add a `a.skip-link` that targets `#main` (with `<main id="main">`), visually hidden until focused. This is a standard accessibility pattern. (2) Add `:focus-visible` styles for nav links and body links to ensure visible keyboard focus indicators. (3) Optionally add a breakpoint around 768px for slightly tighter nav spacing on tablets. These changes amount to ~15 lines of CSS and a small template change.

### 2e. Content Quality

- **Finding:**
  - All 11 markdown files have correct, consistent frontmatter (`layout`, `title`, `permalink`). No missing fields or typos.
  - **Talks numbering bug:** In `talks.md`, line 14 and line 15 are both numbered `2.` under "Research Talks" (entries for "Fractals and Africanist Music" and "Hodge Theory and Resolvent Problems"). Markdown will auto-number correctly in the rendered output since these are ordered lists, but the source is confusing and suggests a copy-paste error where item 2 should be item 3 (and all subsequent items are off by one).
  - **2015-reu.md and 2016-reu.md** are not in the nav (`base.njk:50-58`) and not in the CMS config (`config.yml`). They are linked from `teaching.md` as sub-pages. This is intentional — they are secondary pages. However, they are invisible to the CMS editor.
  - **Stale content check:** The "Upcoming" section in `talks.md` lists a talk at IAS for Mar. 24–26, 2026. As of today (Feb. 25, 2026), this is still upcoming. No obviously stale content detected. The working-group page has current PhD expected dates extending to 2030 — appears current.
  - **The about page** links to `https://jpwolfson.com/wp-content/uploads/2013/11/math_newsletter-spring-2013.pdf` (line 35 of `mathematics-and-dance.md`) which is a legacy WordPress URL. After migration to Cloudflare Pages, this URL will 404 unless a redirect is configured or the file is hosted locally.
- **Severity:** cosmetic (numbering), low (CMS coverage), medium (legacy WP URL)
- **Category:** content
- **Remediation:** (1) Fix the duplicate `2.` numbering in `talks.md` at lines 14–15. (2) Add the REU pages to the CMS config if the site owner may want to edit them through the CMS. (3) Either host the newsletter PDF locally in `src/files/` and update the link in `mathematics-and-dance.md:35`, or set up a Cloudflare redirect rule from `/wp-content/uploads/...` to the new location. The link audit CI should catch this as broken once the WordPress site is decommissioned.

### 2f. Security Headers

- **Finding:**
  - `src/_headers` (deployed as `_site/_headers`) applies to `/*` (all paths) and includes: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy: camera=(), microphone=(), geolocation=()`. These are good and appropriate.
  - **Missing: `Strict-Transport-Security` (HSTS).** Cloudflare enforces HTTPS at the CDN level, but HSTS tells the browser to never attempt HTTP in the first place. Adding `Strict-Transport-Security: max-age=31536000; includeSubDomains` is standard best practice. The absence is low-risk because Cloudflare already handles the redirect, but HSTS provides defense-in-depth against downgrade attacks.
  - **Missing: `X-DNS-Prefetch-Control`.** This header controls whether the browser prefetches DNS for links on the page. Setting `X-DNS-Prefetch-Control: off` is a minor privacy hardening — it prevents the browser from revealing which links the user might click by pre-resolving their DNS. For an academic site with many outbound links to arxiv, journals, etc., this is a reasonable privacy measure, though very low impact.
  - **CSP interaction model:** The site uses both a `<meta http-equiv="Content-Security-Policy">` tag in `base.njk:19-26` AND the `_headers` file. The `_headers` file does **not** include a CSP header — it only has the four headers listed above. The CSP is delivered exclusively via the `<meta>` tag. This means: (a) the CSP applies per-page and is controlled by the template, which is correct; (b) the `_headers`-based security headers complement, not conflict with, the meta CSP; (c) the admin page (`admin/index.html`) has its own, more permissive meta CSP (lines 6-12), which correctly allows `unsafe-eval` and `unsafe-inline` needed by Decap CMS. There is no conflict or override issue. This is a clean architecture.
  - The `_headers` file scoping uses `/*` (all paths). This applies to admin pages too, which is correct — all four headers are appropriate for admin pages.
- **Severity:** low (HSTS), cosmetic (X-DNS-Prefetch-Control)
- **Category:** security
- **Remediation:** (1) Add `Strict-Transport-Security: max-age=31536000; includeSubDomains` to `src/_headers`. (2) Optionally add `X-DNS-Prefetch-Control: off` for privacy hardening. Both are one-line additions.

### 2g. OAuth Worker

- **Finding:**
  - `worker.js` (175 lines) is well-structured with clear comments. The security model is sound:
    - `postMessage` is restricted to `targetOrigin` (line 140, 146) using the first entry in `ALLOWED_DOMAINS` — this is the primary defense against token theft.
    - Referer checking (lines 51–64) is a secondary defense with a documented acceptable bypass (browsers stripping Referer).
    - The callback response includes `Cache-Control: no-store`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, and a tight CSP (line 166–167).
  - **GitHub scope is `repo` (line 75).** This grants full read/write access to all repositories the user can access. GitHub does not offer a narrower scope for CMS write access (e.g., no `repo:contents:write` granular scope exists). This is documented as an accepted risk in `SECURITY.md`. Branch protection on `main` mitigates the blast radius.
  - **Edge case — token in HTML:** The token is embedded in an HTML page via `JSON.stringify(token)` (line 130). This is safe because `JSON.stringify` escapes `</script>` sequences and the CSP on the response page is `default-src 'none'; script-src 'unsafe-inline'` (no external resource loading). However, if the token contained a string like `</script>`, `JSON.stringify` would produce `"</script>"` which could break parsing. A safer approach would use `.replace(/</g, '\\u003c')` after stringification, but in practice GitHub OAuth tokens are alphanumeric so this is theoretical.
  - **Edge case — error message leakage:** Line 107 logs `tokenData.error` and `tokenData.error_description` to `console.error`, but only the generic "Authentication failed. Please try again." is returned to the user (line 108). This is correct — no sensitive info leaks.
  - **No token revocation or expiry handling.** Once a token is issued, it persists in the browser's localStorage (Decap CMS behavior) until manually cleared. There is no server-side session management. This is inherent to the Decap CMS architecture and documented in `SECURITY.md`.
  - **`wrangler.toml`** has `compatibility_date = "2026-02-19"` — current and correct.
- **Severity:** low (JSON.stringify edge case)
- **Category:** security
- **Remediation:** Optionally add `token.replace(/</g, '\\u003c')` sanitization on line 130 for defense-in-depth. This is a theoretical concern with near-zero practical risk for GitHub tokens.

### 2h. CMS Config

- **Finding:**
  - Decap CMS is pinned to `@3.10.0` in `admin/index.html:23` with SRI (`integrity="sha384-Yw42/..."`). Version 3.10.0 is the [latest release](https://github.com/decaporg/decap-cms/releases) as of January 2026. The project's maintenance has slowed significantly — Netlify has stopped supporting it and no new features are being added. For now, 3.10.0 is current.
  - `config.yml` defines 9 files in the `pages` collection: about, papers, talks, working-group, math-dance, teaching, workshops, roosevelt, cv. This covers 9 of the 11 content `.md` files.
  - **Missing from CMS config:** `2015-reu.md` and `2016-reu.md`. These are REU mini-course pages linked from the Teaching page. If the site owner ever needs to edit them, they would have to use GitHub directly rather than the CMS.
  - `publish_mode: simple` — appropriate; no editorial workflow needed for a single-author site.
  - `media_folder: jpwolfson-site/src/files` — this path is relative to the git repo root and accounts for the nested directory structure. If the repo layout is ever flattened (see 2a), this must be updated to `src/files`.
  - `backend.branch: main` — correct, matches the production branch.
  - The admin page has its own CSP (lines 6–12) that correctly allows the domains needed by Decap CMS (`unpkg.com`, `api.github.com`, the worker domain). `unsafe-eval` and `unsafe-inline` are required by Decap CMS and documented as accepted risks.
  - **Long-term concern:** Decap CMS is entering maintenance-mode. [Sveltia CMS](https://github.com/sveltia/sveltia-cms) is a drop-in replacement under active development. Migration is a future consideration, not urgent.
- **Severity:** low (missing REU pages), cosmetic (Decap CMS lifecycle)
- **Category:** DX / content
- **Remediation:** (1) Add CMS entries for `2015-reu.md` and `2016-reu.md` if the site owner should be able to edit them via the CMS. (2) Note in project documentation that Sveltia CMS is a viable future replacement for Decap CMS.

### 2i. CI/CD Gaps

- **Finding:**
  - **Only one CI workflow exists:** `link-audit.yml` (runs on push to `jpwolfson-site/src/**`, weekly cron, and manual dispatch). It runs `crawl_links.py` against the site's content — useful for catching broken external links.
  - **No build CI.** There is no workflow that runs `npm install && npx @11ty/eleventy` on PRs or pushes to `main`. The site could break on merge with zero warning. Given that the site owner edits via Decap CMS (which commits directly to `main`), a failing build would only be caught after Cloudflare Pages deployment fails — at which point the old version remains live but the owner may not notice.
  - **No Lighthouse CI.** No performance or accessibility regression testing.
  - **No HTML validation.** No check that the generated HTML is well-formed.
  - The existing workflow is well-hardened: actions pinned to full SHAs, pip deps version-pinned, `permissions: contents: read`, artifact upload with 90-day retention. Good security practices.
  - `working-directory: jpwolfson-site` in the workflow correctly accounts for the nested layout.
- **Severity:** high (no build CI)
- **Category:** DX
- **Remediation:** Add a `build.yml` workflow that: (1) triggers on `push` to `main` and on `pull_request`; (2) runs `npm ci && npx @11ty/eleventy`; (3) optionally runs `npx html-validate _site/**/*.html` for HTML validation; (4) sets `working-directory: jpwolfson-site` to match the nested layout. This is the single highest-impact DX improvement. Lighthouse CI is a nice-to-have but lower priority.

### 2j. Utility Scripts at Repo Root

- **Finding:**
  - **Outer repo root:**
    - `export-wp-stats.py` (278 lines) — WordPress.com stats exporter. This is a one-time migration tool used to archive analytics before decommissioning WordPress. It should not remain at the repo root indefinitely.
  - **Inner `jpwolfson-site/` directory:**
    - `apply_phase2.py` (4,447 bytes), `apply_phase3.py` (6,050 bytes) — audit remediation scripts from a previous security audit phase. These are one-time tools.
    - `crawl_links.py` (11,548 bytes) — link crawler used by the CI workflow. This is an **active** script referenced by `.github/workflows/link-audit.yml` and should be preserved.
    - `link_audit.json` (129,869 bytes / ~127 KB) — output artifact from `crawl_links.py`. This is a generated file that should not be in version control; it's also uploaded as a CI artifact.
  - These utility scripts clutter the project root alongside production files like `package.json` and `.eleventy.js`.
- **Severity:** low
- **Category:** DX / structure
- **Remediation:** (1) Move `export-wp-stats.py`, `apply_phase2.py`, and `apply_phase3.py` to a `scripts/archive/` directory (or delete them if the migration/audit work is complete and they're no longer needed). (2) Move `crawl_links.py` to `scripts/` and update the CI workflow path accordingly. (3) Add `link_audit.json` to `.gitignore` — it's a generated artifact, not source code. (4) If flattening the repo layout (2a), these paths simplify to `scripts/` at the repo root.

### 2k. Documentation

- **Finding:**
  - **`SECURITY.md`** (outer repo root, 161 lines) — comprehensive, accurate, and well-maintained. Covers current security controls, maintenance procedures for updating Decap CMS / MathJax / CSP hashes / GitHub Actions, periodic check schedule, accepted risks with justifications, and an architecture diagram. Last audited date is 2026-02-23. This is excellent documentation.
  - **`SETUP.md`** (inner `jpwolfson-site/`, 138 lines) — a thorough, non-technical setup guide walking through GitHub → Cloudflare Pages → Cloudflare Worker → Decap CMS. Written for a non-developer site owner. Includes WordPress migration instructions. One issue: step 3e references `YOUR_GITHUB_USERNAME` and `YOUR_REPO_NAME` as placeholders, but `config.yml` already has the correct values (`jpwolfson/jpwolfson-site`, `jpwolfson-cms-auth.jpwolfson.workers.dev`). This suggests SETUP.md was written before config was finalized and this section is now slightly misleading — a reader might think they still need to fill these in.
  - **No `README.md` at the repo root.** A developer (or the site owner) cloning the repo sees `SECURITY.md`, `export-wp-stats.py`, `jpwolfson-site/`, `.github/`, and `security-audits/` with no explanation of what this repo is or how to get started. GitHub will display `SECURITY.md` as a fallback, but its content is security-focused, not onboarding-focused.
- **Severity:** low (no README), cosmetic (SETUP.md staleness)
- **Category:** DX
- **Remediation:** (1) Add a brief `README.md` at the repo root explaining: what this repo is, the project layout, how to build locally (`cd jpwolfson-site && npm install && npm run start`), and pointers to `SETUP.md` and `SECURITY.md`. (2) Update `SETUP.md` step 3e to note that the values are already filled in, or remove the placeholder language.

---

## Prioritized Remediation Summary

Ordered by severity, with Phase 1 carry-forwards integrated:

| # | Severity | Category | Finding | Section |
|---|----------|----------|---------|---------|
| 1 | **High** | DX | No build CI — site can break on merge with no warning | 2i |
| 2 | **Medium** | Structure | No 404 page — visitors see generic Cloudflare error | 2c |
| 3 | **Medium** | Accessibility | `aria-current="page"` nav indicator bug (Phase 1) — CSS ready, template logic missing | 2c |
| 4 | **Medium** | Accessibility | No skip-to-content link for keyboard/screen reader users | 2d |
| 5 | **Medium** | Accessibility | No `:focus-visible` styles for keyboard navigation | 2d |
| 6 | **Medium** | Structure/DX | Nested repo layout complicates builds, CI, and orientation | 2a |
| 7 | **Medium** | Content | Legacy WordPress URL in `mathematics-and-dance.md:35` will 404 after migration | 2e |
| 8 | **Low** | Security | Missing `Strict-Transport-Security` header | 2f |
| 9 | **Low** | SEO | No `<meta name="description">` or Open Graph tags | 2c |
| 10 | **Low** | DX | No `clean`, `lint`, or `test` scripts in `package.json` | 2b |
| 11 | **Low** | DX / Structure | Utility scripts cluttering project root; `link_audit.json` in version control | 2j |
| 12 | **Low** | DX | No `README.md` at repo root | 2k |
| 13 | **Low** | Content/DX | 2 REU pages missing from CMS config | 2h |
| 14 | **Low** | Security | `JSON.stringify` edge case in OAuth worker (theoretical) | 2g |
| 15 | **Cosmetic** | Content | Duplicate numbering (`2.` twice) in `talks.md` lines 14–15 | 2e |
| 16 | **Cosmetic** | Security | Missing `X-DNS-Prefetch-Control` header | 2f |
| 17 | **Cosmetic** | DX | `SETUP.md` step 3e references placeholders already filled in | 2k |
| 18 | **Cosmetic** | DX | Decap CMS entering maintenance mode; consider Sveltia CMS long-term | 2h |
