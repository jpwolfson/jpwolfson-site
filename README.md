# jpwolfson.com

Source for the personal academic site of Jesse Wolfson (UC Irvine). Static HTML
built with [Eleventy](https://www.11ty.dev/) and deployed by Cloudflare Pages from
the `main` branch. No CMS, no server-side code, no secrets.

```
.
├── jpwolfson-site/           Eleventy project — Cloudflare Pages root directory
│   ├── src/content/          one Markdown file per page
│   ├── src/_includes/        base.njk layout (carries the CSP)
│   ├── src/_headers          HTTP security headers
│   ├── src/files/            PDFs and images served at /files/
│   ├── scripts/ci/           deterministic checks run by CI
│   ├── scripts/crawl_links.py  weekly external-link audit
│   ├── .node-version         Node pin (Cloudflare Pages and CI both read it)
│   └── .npmrc                ignore-scripts=true
├── .github/workflows/        build (required check) and link-audit
├── security-audits/          audit history and the current review workflow
├── CLAUDE.md                 rules for agents working here
└── SECURITY.md               controls, accepted risks, maintenance
```

## Local build

```bash
cd jpwolfson-site
npm ci
npm run build          # output in _site/
npm run start          # live-reload dev server
npm run lint:html
bash scripts/ci/check-output.sh && python3 scripts/ci/check-csp.py && bash scripts/ci/check-files.sh
```

## Editing

Content is edited through pull requests, usually by agent sessions following
`CLAUDE.md`. See `jpwolfson-site/OPERATIONS.md` for the editing runbook and
`SECURITY.md` for the security model.
