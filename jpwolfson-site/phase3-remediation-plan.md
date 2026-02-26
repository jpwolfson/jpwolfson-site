# Phase 2: Prioritized Remediation Plan

**Date:** 2026-02-26
**Input:** Phase 1 structural & architectural review (18 findings in `phase2-report.md`)
**Purpose:** Concrete, prioritized proposals grouped into implementation batches (one PR each)

---

## Executive Summary

Phase 1 identified 18 findings across structure, accessibility, DX, content, and security. After verifying each finding against the source code, this plan organizes them into five implementation batches, ordered so that each batch is independently shippable and low-risk.

**Key takeaways:**

- **14 findings** should be implemented across Batches 1–4 — all are straightforward changes with clear specifications.
- **3 findings** are deferred or skipped (Decap CMS lifecycle monitoring, JSON.stringify edge case, X-DNS-Prefetch-Control).
- **1 finding is incorrect** — Phase 1 claims the working-group page "appears current" with "no obviously stale content detected," but the site owner has indicated an error regarding an undergraduate member listing. See [§ Incorrect Phase 1 Finding](#incorrect-phase-1-finding) below.
- **Batch 5** (repo layout flattening) is the only high-complexity change. This plan recommends **deferring** it in favor of a root-level README as a stopgap. See [§ Repo Layout Decision](#repo-layout-decision) for the full assessment.

---

## Finding Disposition Table

| # | Phase 1 Ref | Finding | Severity | Recommendation | Batch |
|---|-------------|---------|----------|----------------|-------|
| 1 | 2c | No 404 page | Medium | **Implement** | 1 |
| 2 | 2c | `aria-current="page"` nav bug | Medium | **Implement** | 1 |
| 3 | 2f | Missing HSTS header | Low | **Implement** | 1 |
| 4 | 2e | Duplicate `2.` numbering in talks.md | Cosmetic | **Implement** | 1 |
| 5 | 2d | No `:focus-visible` styles | Medium | **Implement** | 1 |
| 6 | 2d | No skip-to-content link | Medium | **Implement** | 1 |
| 7 | 2i | No build CI workflow | High | **Implement** | 2 |
| 8 | 2b | No `clean`/`test` scripts in package.json | Low | **Implement** | 2 |
| 9 | 2c | No `<meta name="description">` | Low | **Implement** | 3 |
| 10 | 2c | No Open Graph tags | Low | **Implement** | 3 |
| 11 | 2j | Utility scripts cluttering project root | Low | **Implement** | 4 |
| 12 | 2j | `link_audit.json` tracked in git | Low | **Implement** | 4 |
| 13 | 2k | No `README.md` at repo root | Low | **Implement** | 4 |
| 14 | 2k | `SETUP.md` stale placeholder language | Cosmetic | **Implement** | 4 |
| 15 | 2e | Legacy WP URL in mathematics-and-dance.md | Medium | **Implement** | 4 |
| 16 | 2a | Nested repo layout | Medium | **Defer** | (5) |
| 17 | 2g | `JSON.stringify` edge case in OAuth worker | Low | **Skip** | — |
| 18 | 2f | Missing `X-DNS-Prefetch-Control` header | Cosmetic | **Skip** | — |
| — | 2h | REU pages missing from CMS config | Low | **Defer** | — |
| — | 2h | Decap CMS lifecycle / Sveltia consideration | Cosmetic | **Defer** | — |

**Skip rationale:**
- **#17 (JSON.stringify):** GitHub OAuth tokens are alphanumeric. The `</script>` injection scenario is impossible in practice. Adding sanitization introduces complexity for zero real-world benefit.
- **#18 (X-DNS-Prefetch-Control):** Marginal privacy benefit for an academic site with public links. Not worth the maintenance surface of yet another header to document.

**Defer rationale:**
- **#16 (Repo layout):** High complexity, requires Cloudflare dashboard changes. A root README (Batch 4) provides adequate orientation as a stopgap. See [§ Repo Layout Decision](#repo-layout-decision).
- **REU pages in CMS:** These are rarely-edited archival pages. Adding them to the CMS config can be done anytime if the site owner requests it. Not worth a PR on its own.
- **Decap CMS lifecycle:** No action needed now. Revisit if Decap CMS stops receiving security patches.

---

## Batch 1 — Quick Wins

**Goal:** Ship the highest-value, lowest-risk changes in a single PR.
**Risk:** Very low — all changes are additive or cosmetic. No build config changes.
**Judgment required:** Minimal — all changes are deterministic except for the 404 page copy (propose a default, site owner can adjust later).

### 1.1 Create a 404 page

- **File:** Create `jpwolfson-site/src/content/404.md`
- **Change:**

```markdown
---
layout: base.njk
title: Page Not Found
permalink: /404.html
---

Sorry, this page doesn't exist. You can return to the [home page](/) or use the navigation above.
```

- **How it works:** Cloudflare Pages automatically serves `_site/404.html` for unknown routes. Eleventy will compile this markdown file to `_site/404.html` via the `base.njk` layout.
- **Type:** Deterministic (create file with exact content above).

### 1.2 Fix `aria-current="page"` on nav links

- **File:** `jpwolfson-site/src/_includes/base.njk` (lines 50–58)
- **Change:** Replace the hardcoded nav links with conditional `aria-current` attributes. Each nav `<a>` should include the attribute when `page.url` matches that link's path.
- **Current code (lines 50–58):**

```html
<nav>
  <a href="/working-group/">Working Group</a>
  <a href="/papers/">Papers</a>
  <a href="/talks/">Talks</a>
  <a href="/mathematics-and-dance/">Mathematics and Dance</a>
  <a href="/teaching/">Teaching</a>
  <a href="/workshops/">Workshops</a>
  <a href="/roosevelt-institute/">Roosevelt Institute</a>
  <a href="/cv/">CV</a>
</nav>
```

- **New code:**

```html
<nav>
  <a href="/working-group/"{% if page.url == "/working-group/" %} aria-current="page"{% endif %}>Working Group</a>
  <a href="/papers/"{% if page.url == "/papers/" %} aria-current="page"{% endif %}>Papers</a>
  <a href="/talks/"{% if page.url == "/talks/" %} aria-current="page"{% endif %}>Talks</a>
  <a href="/mathematics-and-dance/"{% if page.url == "/mathematics-and-dance/" %} aria-current="page"{% endif %}>Mathematics and Dance</a>
  <a href="/teaching/"{% if page.url == "/teaching/" %} aria-current="page"{% endif %}>Teaching</a>
  <a href="/workshops/"{% if page.url == "/workshops/" %} aria-current="page"{% endif %}>Workshops</a>
  <a href="/roosevelt-institute/"{% if page.url == "/roosevelt-institute/" %} aria-current="page"{% endif %}>Roosevelt Institute</a>
  <a href="/cv/"{% if page.url == "/cv/" %} aria-current="page"{% endif %}>CV</a>
</nav>
```

- **Why not a loop:** The nav has only 8 static entries. A Nunjucks `for` loop over a frontmatter or data array would be more "DRY" but adds indirection for a non-developer maintainer. The explicit approach is readable and matches the site's simplicity.
- **Type:** Deterministic (exact code above).
- **CSS:** No CSS changes needed — `style.css:71–75` already styles `nav a[aria-current="page"]`.

### 1.3 Add HSTS header

- **File:** `jpwolfson-site/src/_headers` (line 5, append after the last header)
- **Change:** Add one line:

```
  Strict-Transport-Security: max-age=31536000; includeSubDomains
```

- **Full file after change:**

```
/*
  X-Content-Type-Options: nosniff
  X-Frame-Options: DENY
  Referrer-Policy: strict-origin-when-cross-origin
  Permissions-Policy: camera=(), microphone=(), geolocation=()
  Strict-Transport-Security: max-age=31536000; includeSubDomains
```

- **Risk:** None. Cloudflare already enforces HTTPS. HSTS just tells browsers to skip the HTTP→HTTPS redirect on future visits. The `includeSubDomains` directive is safe since the site uses no HTTP-only subdomains.
- **Type:** Deterministic (exact content above).

### 1.4 Fix talks.md duplicate numbering

- **File:** `jpwolfson-site/src/content/talks.md` (lines 14–15)
- **Current (lines 14–15):**

```markdown
2. [Correctness, Artificial Intelligence and the Epistemic Value of Proof](...) – APMP 2026, Chapman University, Jan. 12, 2026.
2. Fractals and Africanist Music – Tropical mathematics and ML seminar, Yonsei University, South Korea, Dec. 8, 2025.
```

- **Change:** Renumber the second `2.` to `3.` and renumber all subsequent items in the "Research Talks" list (items 3→4, 4→5, ... through the end of the list). The current list goes from 1 to 107 in the Research Talks section. After fix, the maximum number should be 108.
- **Note:** Markdown ordered lists auto-number in rendered output regardless of source numbering, so the rendered site is already correct. This fix is purely for source readability and CMS editing clarity.
- **Type:** Deterministic but tedious — every line from the second `2.` through `107.` needs its number incremented by 1.

### 1.5 Add `:focus-visible` styles

- **File:** `jpwolfson-site/src/css/style.css`
- **Change:** Add focus-visible styles after the existing `a:hover` rule (after line 110). Insert:

```css
/* ── Focus indicators (keyboard accessibility) ── */
a:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

nav a:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
  border-bottom-color: var(--accent);
  color: var(--accent);
}
```

- **Rationale:** `:focus-visible` only triggers on keyboard navigation, not mouse clicks. The `2px solid` outline with `2px` offset is a clean, accessible pattern that doesn't disrupt the visual design. The nav-specific rule ensures the bottom border also activates, matching the hover/aria-current behavior.
- **Type:** Deterministic (exact CSS above).

### 1.6 Add skip-to-content link

- **Files:** `jpwolfson-site/src/_includes/base.njk` and `jpwolfson-site/src/css/style.css`
- **Template change (`base.njk`):** Add a skip link as the first child of `<body>` (after line 47), and add `id="main"` to the `<main>` element:

```html
<body>
  <a href="#main" class="skip-link">Skip to content</a>
  <header>
    ...
  </header>

  <main id="main">
```

- **CSS change (`style.css`):** Add visually-hidden styles that become visible on focus. Insert before the `/* ── Header */` section (before line 32):

```css
/* ── Skip-to-content (accessibility) ─── */
.skip-link {
  position: absolute;
  left: -9999px;
  top: 0;
  padding: 0.5rem 1rem;
  background: var(--accent);
  color: #fff;
  font-size: 0.88rem;
  z-index: 100;
  text-decoration: none;
}

.skip-link:focus {
  left: 1rem;
  top: 0.5rem;
}
```

- **How it works:** The link is invisible until a keyboard user presses Tab. It then appears at the top-left of the page. Pressing Enter jumps focus to `<main id="main">`, bypassing the 8 nav links.
- **Type:** Deterministic (exact code above).

---

## Batch 2 — Build CI

**Goal:** Add a build workflow so that broken builds are caught before deployment.
**Risk:** Low — additive only (new workflow file, minor package.json changes). Does not affect existing link-audit workflow.
**Judgment required:** None — all changes are deterministic.

### 2.1 Add build workflow

- **File:** Create `.github/workflows/build.yml`
- **Content:**

```yaml
name: Build

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    permissions:
      contents: read
    defaults:
      run:
        working-directory: jpwolfson-site

    steps:
      - uses: actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5  # v4

      - name: Set up Node.js
        uses: actions/setup-node@1d0ff469b7ec7b3cb9d8673fde0c81c44821de2a  # v4
        with:
          node-version: '22'
          cache: 'npm'
          cache-dependency-path: jpwolfson-site/package-lock.json

      - name: Install dependencies
        run: npm ci

      - name: Build site
        run: npx @11ty/eleventy

      - name: Verify 404 page exists
        run: test -f _site/404.html
```

- **Notes:**
  - Action SHAs are pinned to the same version tags used in `link-audit.yml` (`actions/checkout` v4) plus `actions/setup-node` v4. The exact SHA for `actions/setup-node` v4 should be verified at implementation time via `gh api repos/actions/setup-node/git/refs/tags/v4 --jq '.object.sha'`.
  - `working-directory: jpwolfson-site` matches the nested repo layout. If Batch 5 (flattening) is ever done, this must be removed.
  - `npm ci` (not `npm install`) ensures reproducible builds from the lockfile.
  - The "Verify 404 page exists" step is a lightweight smoke test that also validates Batch 1's 404 page.
- **Type:** Deterministic (create file with content above; verify action SHA at implementation time).

### 2.2 Add `clean` and `test` scripts to package.json

- **File:** `jpwolfson-site/package.json`
- **Change:** Add `clean` and `test` scripts:

```json
{
  "name": "jpwolfson-site",
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "build": "eleventy",
    "start": "eleventy --serve",
    "clean": "rm -rf _site",
    "test": "eleventy --dryrun"
  },
  "dependencies": {
    "@11ty/eleventy": "^3.0.0"
  }
}
```

- **Note:** Moving `@11ty/eleventy` to `devDependencies` (as suggested in Phase 1) is technically correct but has zero practical impact for a static site and could confuse a non-developer owner. **Skip this change.**
- **Note:** Tightening the version range from `^3.0.0` to `~3.1.2` is a minor defensive measure, but the lockfile already pins the exact version. **Skip this change** — it adds maintenance burden (must update on every Eleventy patch) for no real protection.
- **Type:** Deterministic (exact JSON above).

---

## Batch 3 — Template & SEO

**Goal:** Add meta description and Open Graph tags to improve search results and social sharing.
**Risk:** Very low — additive changes to the `<head>` section of `base.njk`.
**Judgment required:** Yes — description text for the home page and default descriptions require site owner input. Propose defaults below; site owner should review.

### 3.1 Add meta description

- **File:** `jpwolfson-site/src/_includes/base.njk` (in `<head>`, after the `<title>` tag on line 27)
- **Change:** Add a description meta tag that uses a frontmatter `description` field with a fallback default:

```html
<meta name="description" content="{{ description | default('Jesse Wolfson – mathematician at the University of California, Irvine. Research in algebraic topology, algebraic geometry, and number theory.') }}">
```

- **Frontmatter integration:** Each content `.md` file *may* optionally add a `description:` field to its frontmatter for page-specific descriptions. If not provided, the default above is used. This is a progressive enhancement — no existing files need to change immediately.
- **Type:** Deterministic for the template change. Description text requires site owner approval (propose the default above and let them adjust).

### 3.2 Add Open Graph tags

- **File:** `jpwolfson-site/src/_includes/base.njk` (in `<head>`, after the description tag)
- **Change:** Add minimal Open Graph tags:

```html
<meta property="og:title" content="{% if title %}{{ title }} – {% endif %}Jesse Wolfson" />
<meta property="og:description" content="{{ description | default('Jesse Wolfson – mathematician at the University of California, Irvine. Research in algebraic topology, algebraic geometry, and number theory.') }}" />
<meta property="og:type" content="website" />
<meta property="og:url" content="https://jpwolfson.com{{ page.url }}" />
```

- **Note:** No `og:image` tag is included because the site has no logo or hero image. Adding one would require creating or sourcing an image. This can be done later if the site owner wants social sharing previews with an image.
- **CSP impact:** None — these are `<meta>` tags, not external resources.
- **Type:** Deterministic for the template. Description text is shared with §3.1 and requires site owner approval.

---

## Batch 4 — Repo Cleanup & Documentation

**Goal:** Clean up script locations, remove generated files from git, add a root README, fix the legacy WordPress URL, and update SETUP.md.
**Risk:** Low-to-moderate — moving `crawl_links.py` requires updating the CI workflow path. All other changes are self-contained.
**Judgment required:** Whether to delete the archive scripts or keep them. Propose keeping them in `scripts/archive/` for now.

### 4.1 Relocate utility scripts

- **Files affected:**
  - Move `jpwolfson-site/crawl_links.py` → `jpwolfson-site/scripts/crawl_links.py`
  - Move `jpwolfson-site/apply_phase2.py` → `jpwolfson-site/scripts/archive/apply_phase2.py`
  - Move `jpwolfson-site/apply_phase3.py` → `jpwolfson-site/scripts/archive/apply_phase3.py`
  - Move `export-wp-stats.py` (repo root) → `scripts/archive/export-wp-stats.py` (repo root)
- **CI workflow update:** `.github/workflows/link-audit.yml` line 38 — change `run: python crawl_links.py` to `run: python scripts/crawl_links.py`
- **CI workflow update:** `.github/workflows/link-audit.yml` line 13 — change path trigger from `'jpwolfson-site/crawl_links.py'` to `'jpwolfson-site/scripts/crawl_links.py'`
- **Type:** Deterministic (file moves + two line changes in the workflow).
- **Risk:** If the path update in the CI workflow is missed, the link audit will fail. Test by running the workflow manually after merge.

### 4.2 Add `link_audit.json` to `.gitignore`

- **File:** `.gitignore` (repo root)
- **Change:** Add `link_audit.json` to the gitignore:

```
link_audit.json
```

- **Then:** Remove the tracked file: `git rm --cached jpwolfson-site/link_audit.json` (keeps the local file but removes it from git).
- **Type:** Deterministic.

### 4.3 Add root README

- **File:** Create `README.md` at the repo root
- **Proposed content:**

```markdown
# jpwolfson.com

Personal academic website for Jesse Wolfson, hosted on [Cloudflare Pages](https://pages.cloudflare.com/).

## Project Layout

```
├── jpwolfson-site/          # Eleventy project (Cloudflare Pages root directory)
│   ├── src/                 # Source files (templates, content, CSS, admin)
│   ├── oauth-worker/        # Cloudflare Worker for Decap CMS OAuth
│   ├── .eleventy.js         # Eleventy configuration
│   ├── package.json         # Node.js dependencies
│   └── SETUP.md             # Full setup guide (GitHub → Cloudflare → CMS)
├── .github/workflows/       # CI workflows (link audit, build)
├── security-audits/         # Security audit reports
└── SECURITY.md              # Security controls & maintenance procedures
```

## Local Development

```bash
cd jpwolfson-site
npm install
npm run start        # http://localhost:8080
```

## Editing Content

Go to [jpwolfson.com/admin/](https://jpwolfson.com/admin/) and log in with GitHub.
See [SETUP.md](jpwolfson-site/SETUP.md) for the full setup guide.
```

- **Type:** Deterministic (exact content above; site owner may adjust).

### 4.4 Update SETUP.md stale placeholder language

- **File:** `jpwolfson-site/SETUP.md` (lines 104–108, step 3e)
- **Current text:**

```
### 3e. Update the CMS config
In your GitHub repository, edit `src/admin/config.yml`:
- Replace `YOUR_GITHUB_USERNAME` with your GitHub username.
- Replace `YOUR_REPO_NAME` with `jpwolfson-site` (or whatever you named it).
- Change `base_url` to your Worker URL: `https://jpwolfson-cms-auth.YOUR_SUBDOMAIN.workers.dev`
```

- **New text:**

```
### 3e. Verify the CMS config
The CMS configuration in `src/admin/config.yml` is already set up with the correct values:
- `repo: jpwolfson/jpwolfson-site`
- `base_url: https://jpwolfson-cms-auth.jpwolfson.workers.dev`

No changes needed unless you've renamed the repository or Worker.
```

- **Type:** Deterministic (exact replacement above).

### 4.5 Fix legacy WordPress URL

- **File:** `jpwolfson-site/src/content/mathematics-and-dance.md` (line 35)
- **Current:**

```markdown
- The [2013 newsletter of the Northwestern Department of Mathematics](https://jpwolfson.com/wp-content/uploads/2013/11/math_newsletter-spring-2013.pdf) (p. 8)
```

- **Remediation approach — two options (site owner chooses):**

**Option A (recommended): Host the PDF locally.**
  1. Download the PDF from the WordPress URL (while the WordPress site is still live, or from archive).
  2. Place it at `jpwolfson-site/src/files/math_newsletter-spring-2013.pdf`.
  3. Update the link in `mathematics-and-dance.md` to `/files/math_newsletter-spring-2013.pdf`.
  4. Eleventy's passthrough copy (`src/files` in `.eleventy.js:4`) will deploy it to `_site/files/`.

**Option B: Add a Cloudflare redirect rule.**
  - In the Cloudflare dashboard, add a redirect rule from `/wp-content/uploads/2013/11/math_newsletter-spring-2013.pdf` to the new hosted location.
  - This preserves any existing external links to the old URL.

- **Type:** Requires judgment (site owner must decide between options and provide the PDF file if Option A). The link-audit CI will flag this as broken once WordPress hosting ends.

---

## Batch 5 — Repo Layout Flattening (Deferred)

See [§ Repo Layout Decision](#repo-layout-decision) below for the full assessment.

This batch is **not recommended for implementation at this time.** The root README added in Batch 4 provides adequate orientation. If the site owner or a future maintainer wants to flatten the layout, this section provides the complete change list.

---

## Repo Layout Decision

### Current structure

```
jpwolfson-site/                     ← git root
├── .github/workflows/
├── security-audits/
├── SECURITY.md
├── export-wp-stats.py
├── .gitignore
└── jpwolfson-site/                 ← Eleventy project root (Cloudflare Pages root directory)
    ├── src/
    ├── oauth-worker/
    ├── .eleventy.js
    ├── package.json
    ├── package-lock.json
    ├── SETUP.md
    ├── crawl_links.py
    └── ...
```

### What would need to change

If promoting the inner `jpwolfson-site/` contents to the repo root:

| # | File / Config | Change Required |
|---|---------------|-----------------|
| 1 | `jpwolfson-site/package.json` | Move to repo root |
| 2 | `jpwolfson-site/package-lock.json` | Move to repo root |
| 3 | `jpwolfson-site/.eleventy.js` | Move to repo root |
| 4 | `jpwolfson-site/src/` | Move to repo root |
| 5 | `jpwolfson-site/oauth-worker/` | Move to repo root |
| 6 | `jpwolfson-site/SETUP.md` | Move to repo root |
| 7 | `jpwolfson-site/scripts/` | Move to repo root (after Batch 4) |
| 8 | `jpwolfson-site/_site/` | Already gitignored; will now generate at repo root |
| 9 | `.github/workflows/link-audit.yml` | Remove `working-directory: jpwolfson-site`; update `paths` triggers (remove `jpwolfson-site/` prefix); update artifact `path` |
| 10 | `.github/workflows/build.yml` | Remove `working-directory: jpwolfson-site`; update `cache-dependency-path` (after Batch 2) |
| 11 | `src/admin/config.yml` | Change `media_folder` from `jpwolfson-site/src/files` to `src/files`; change all `file:` paths from `jpwolfson-site/src/content/...` to `src/content/...` |
| 12 | `SECURITY.md` | Update path references (e.g., `jpwolfson-site/src/_headers` → `src/_headers`) |
| 13 | `SETUP.md` | Update any path references |
| 14 | `.gitignore` | Verify patterns still match (they should — `_site/` and `node_modules/` are relative) |
| 15 | **Cloudflare Pages build settings** | **Must be updated manually in the Cloudflare dashboard:** root directory from `jpwolfson-site` to `/` (or empty), build output from `jpwolfson-site/_site` to `_site` |

### Risks

1. **Cloudflare Pages config (item 15) is the critical risk.** This cannot be done via code — it requires logging into the Cloudflare dashboard and updating the build settings. If the code change is merged before the dashboard is updated, **the next build will fail** and the site will not update (the previous version remains live, so no downtime, but new changes won't deploy).
2. **CMS config (item 11) must be updated in the same commit.** If the CMS `file:` paths point to the old `jpwolfson-site/src/content/...` locations after flattening, Decap CMS will fail to load content for editing.
3. **CI workflows (items 9, 10) must be updated in the same commit.** Otherwise CI runs will fail because `working-directory: jpwolfson-site` will point to a nonexistent directory.

### Assessment

**Benefits:**
- Simpler, more conventional project structure.
- Shorter paths in all configs.
- New contributors (or the site owner) can immediately see `package.json`, `src/`, etc. at the root without navigating into a subdirectory.

**Costs:**
- 15 files/configs need coordinated changes.
- Cloudflare Pages dashboard update must happen in the same deploy window.
- A single-maintainer academic site gains little from a "conventional" layout — the site owner edits via CMS, not by navigating the repo.
- If anything is missed, the site build breaks (though the old version stays live).

### Recommendation

**Defer.** The root README added in Batch 4 provides adequate orientation. The nested layout is unusual but functional, and the site owner interacts through the CMS, not the filesystem. The complexity and coordination cost of flattening outweigh the benefits for a single-maintainer site.

If the site owner later decides to flatten, this section provides the complete checklist. The critical step is coordinating the Cloudflare dashboard update with the code merge.

---

## Incorrect Phase 1 Finding

Phase 1 finding **2e** (Content Quality) states:

> *"The working-group page has current PhD expected dates extending to 2030 — appears current."*
> *"No obviously stale content detected."*

**The site owner has indicated this is incorrect**, specifically regarding an undergraduate member listing on the working-group page. The "Current Undergraduate Members" section of `working-group.md` (line 29) currently lists one member:

```
* Ryder Mendelson
```

The site owner should be consulted directly to determine what correction is needed (e.g., whether this person should be moved to "Past Undergraduate Members" with dates, removed, or updated with different information). **Do not modify this content without the site owner's input** — this is a factual claim about research group membership that only the site owner can verify.

This correction is **not included in any batch** because it requires the site owner's direct input on the correct content. It should be addressed as a standalone content update via the CMS or a targeted PR once the site owner provides the correct information.

---

## Implementation Notes for Phase 3

- **Batch ordering:** Batches 1–4 can be implemented in sequence, each as its own PR. Batches 1 and 2 are fully independent and could theoretically be implemented in parallel if desired.
- **Testing:** After each batch, run `cd jpwolfson-site && npm install && npx @11ty/eleventy` locally to verify the build succeeds. After Batch 2, the build CI will catch regressions automatically.
- **Site owner review:** Batches 3 and 4 contain text that the site owner should review (meta description text, README content, SETUP.md changes, WordPress URL fix approach). Flag these for review in the PR descriptions.
- **Batch 5 coordination:** If Batch 5 is ever greenlit, it must be done as a single atomic commit with the Cloudflare dashboard update happening immediately after merge. Consider doing it during a low-traffic window and verifying the build succeeds in Cloudflare's dashboard before considering it done.
