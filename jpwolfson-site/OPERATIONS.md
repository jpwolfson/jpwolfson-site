# Operations — jpwolfson.com

How the site is built, deployed, and edited. The 2026-02 setup guide
(GitHub → Cloudflare Pages → Decap CMS) is superseded; Decap CMS and its OAuth Worker
were removed in October 2026.

## Build and deploy

- **Source:** this repository, branch `main`.
- **Builder:** Cloudflare Pages, Git integration. Root directory `jpwolfson-site`,
  build output `_site`. Pages reads `.node-version` (Node pin) and `.npmrc`
  (`ignore-scripts=true`) from the root directory, installs from `package-lock.json`,
  then runs the build command (`npx @11ty/eleventy` or `npm run build`; either works).
- **Headers:** `src/_headers` is copied to `_site/_headers` and applied by Cloudflare
  Pages. A Transform Rule in the Cloudflare dashboard mirrors the same headers so that
  a bad merge cannot remove them.
- **Preview deployments:** disabled or Access-gated (Batch A decision Q2). Nothing on
  a branch should be publicly reachable before it is merged.

## Editing content

All edits are pull requests. The usual author is an agent session following
`CLAUDE.md`; the GitHub web editor works for one-line fixes.

1. Branch from `main` (`claude/<topic>` for agents).
2. Edit `jpwolfson-site/src/content/<page>.md`. Front matter:
   ```yaml
   ---
   layout: base.njk
   title: Talks
   permalink: /talks/
   description: optional one-sentence summary for search and link previews
   ---
   ```
   Markdown with raw HTML allowed. `<p class="section-label">` and
   `<div class="video-wrapper"><iframe …>` are the two HTML patterns in use; iframes
   must point at `player.vimeo.com` or `www.youtube.com` or CI fails.
3. New page: add a file with the front matter above; add it to the `navItems` list in
   `src/_includes/base.njk` if it belongs in the header.
4. PDFs and images: put the file in `jpwolfson-site/src/files/` (PDF, PNG, JPG only,
   under 25 MB, hyphenated lowercase name) and link it as `/files/<name>`.
5. Build and check locally:
   ```bash
   cd jpwolfson-site
   npm ci
   npm run build
   npm run lint:html
   bash scripts/ci/check-output.sh
   python3 scripts/ci/check-csp.py
   bash scripts/ci/check-files.sh
   ```
6. Open a PR. The `build` check runs everything above plus `npm audit`, SRI
   verification, and a secret scan. A separate reviewer session posts a review.
   Merge (squash) when the check is green and the review has no blocking finding.
7. Cloudflare Pages deploys `main` within a minute or two.

## Things that need a human

- Hardware-key 2FA on GitHub, Cloudflare, and WordPress.com.
- Anything in the WordPress.com account (domain registration, DS record for DNSSEC,
  the old site).
- Starting the one-time local settings session
  (`security-audits/2026-10/BATCH-A-LOCAL-RUNBOOK.md`).

## Local development

```bash
cd jpwolfson-site
npm ci
npm run start      # http://localhost:8080 with live reload
```

## Link audit

`.github/workflows/link-audit.yml` runs `scripts/crawl_links.py` weekly and on
content pushes to `main`. Broken links are tracked in a single issue titled
"Link audit: broken links", updated on each run and closed when clean. The crawler is
deterministic Python; its output is never fed to an agent as instructions.
