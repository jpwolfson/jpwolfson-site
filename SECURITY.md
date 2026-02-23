# Security — jpwolfson.com

Last audited: 2026-02-23 | Audit reports: [`security-audits/`](security-audits/)

## Current Security Controls

- **OAuth token protection:** postMessage restricted to `jpwolfson.com` origin only; 5-second fallback also restricted; fails safely (CMS login breaks rather than leaking) if `ALLOWED_DOMAINS` is unset (`oauth-worker/worker.js`)
- **CDN script integrity:** SRI hashes on Decap CMS (`sha384-Yw42/...`) and MathJax (`sha384-AHAnt9...`); both pinned to exact versions (`@3.10.0`, `@3.2.2`); `crossorigin="anonymous"` present on both
- **Content Security Policy:** Hash-based `script-src` on all public pages (no `unsafe-inline`; only the known MathJax config block and the Cloudflare analytics beacon are allowed as inline scripts); separate, more permissive CSP on the admin page (required by Decap CMS)
- **HTTP security headers:** `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy: camera=(), microphone=(), geolocation=()` via `jpwolfson-site/src/_headers` (applied to all pages)
- **CI hardening:** GitHub Actions pinned to full commit SHAs; pip dependencies version-pinned; `permissions: contents: read` on the workflow job
- **Branch protection:** Enabled on `main` — prevents direct pushes from a compromised token
- **OAuth token response:** `Cache-Control: no-store`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer` on the OAuth callback page
- **OAuth scope:** `repo` only (no `user` scope); GitHub's minimum for CMS write access

---

## Maintenance Procedures

### Updating Decap CMS

When a new Decap CMS version is released:

1. Compute the new SRI hash:
   ```bash
   # Replace 3.10.0 with the new version number
   curl -sL https://unpkg.com/decap-cms@NEW_VERSION/dist/decap-cms.js \
     | openssl dgst -sha384 -binary | openssl base64 -A | sed 's/^/sha384-/'
   ```

2. Update `jpwolfson-site/src/admin/index.html`:
   - Change the version in the `src` URL
   - Replace the `integrity` attribute value with the new hash

3. Test: run `cd jpwolfson-site && npx @11ty/eleventy`, then verify the CMS loads at `/admin/`

---

### Updating MathJax

When a new MathJax version is released:

1. Compute the new SRI hash:
   ```bash
   # Replace 3.2.2 with the new version number
   curl -sL https://cdn.jsdelivr.net/npm/mathjax@NEW_VERSION/es5/tex-chtml.js \
     | openssl dgst -sha384 -binary | openssl base64 -A | sed 's/^/sha384-/'
   ```

2. Update `jpwolfson-site/src/_includes/base.njk`:
   - Change the version in the `src` URL
   - Replace the `integrity` attribute value with the new hash

3. Test: build and verify math renders correctly on any page with LaTeX

---

### Updating the MathJax CSP hash

If you change the MathJax inline config block (`MathJax = { ... }`) in `base.njk`, you must also recompute its CSP hash or the browser will block the script:

1. Recompute the hash (run from the repo root, inside the `jpwolfson-site/` directory):
   ```bash
   python3 -c "
   import hashlib, base64
   with open('src/_includes/base.njk') as f:
       html = f.read()
   import re
   match = re.search(r'<script>(.*?)</script>', html, re.DOTALL)
   digest = hashlib.sha256(match.group(1).encode('utf-8')).digest()
   print('sha256-' + base64.b64encode(digest).decode())
   "
   ```

2. Replace the old `sha256-...` value for the MathJax hash in the `script-src` of the CSP meta tag in `base.njk` (line 21)

3. Update the comment block above the CSP tag (lines 6–18) that documents the hash

---

### If Cloudflare updates their analytics beacon

Cloudflare Web Analytics injects a beacon script at the edge. The CSP includes a hash for this script (`sha256-ieoeWczDHkReVBsRBqaal5AFMlBtNjMzgwKvLqi/tSU=`). If Cloudflare updates the beacon:

1. **Symptom:** CSP error in browser DevTools console mentioning `cloudflareinsights` with a different `sha256-...` value
2. **Fix:** Replace the old beacon hash in the `script-src` CSP meta tag in `base.njk` with the new hash shown in the CSP error
3. **If you can't immediately determine the new hash:** Add `'unsafe-inline'` back alongside the existing hashes in `script-src`. In modern browsers (CSP Level 2+), `'unsafe-inline'` is ignored when hashes are present, so the MathJax hash protection still applies.

---

### Updating GitHub Actions

When updating a pinned action to a new version:

1. Find the commit SHA for the new version tag:
   ```bash
   # Example for actions/checkout v4.3.1
   gh api repos/actions/checkout/git/refs/tags/v4.3.1 --jq '.object.sha'
   ```

2. Replace the SHA in `.github/workflows/link-audit.yml`

3. Update the `# vX.Y.Z` comment after the SHA for readability

---

## Periodic Checks

| Check | Frequency | Command |
|-------|-----------|---------|
| npm audit | Before any npm update | `cd jpwolfson-site && npm audit` |
| Live security headers | After any deploy touching `_headers` | `curl -sI https://jpwolfson.com \| grep -iE '(x-frame\|x-content\|referrer-policy\|permissions-policy)'` |
| SRI hash validity | After any CDN dependency update | Run the `curl \| openssl` command for the updated package (see above) |
| Decap CMS releases | Quarterly | https://github.com/decaporg/decap-cms/releases |
| MathJax releases | Annually | https://github.com/mathjax/MathJax/releases |
| GitHub Actions versions | Quarterly | Check for new releases of `actions/checkout`, `actions/setup-python`, `actions/upload-artifact` |

---

## Accepted Risks

These are known findings that were deliberately not fixed, with reasons:

| Finding | Why Accepted |
|---------|-------------|
| `unsafe-eval` in admin page CSP | Required by Decap CMS internally. Cannot remove without replacing the CMS. Single-user admin page. |
| `unsafe-inline` in admin page `script-src` | Required by Decap CMS. Only affects the admin page, not public pages. |
| npm audit: minimatch ReDoS (4 HIGH) | Build-time dependency only; never deployed. Exploiting it requires repository write access. Monitor for upstream fix in `@11ty/recursive-copy`. |
| `img-src https:` on public pages | Public pages have no tokens or sensitive data. Academic content may legitimately embed external images. |
| OAuth `repo` scope | GitHub's only option for CMS write access. Mitigated by branch protection on `main`. |
| Cloudflare analytics without SRI | Edge-injected by Cloudflare at the CDN layer. Cannot add SRI. Trust boundary is the hosting provider. |
| OAuth token in `localStorage` | Decap CMS built-in behavior. Protected by CSP + SRI on the admin page. |
| Referer check bypassable | Secondary defense only. The primary defense (postMessage `targetOrigin` restriction) cannot be bypassed without controlling a page on `jpwolfson.com`. |

---

## Architecture Reference

```
                  ┌──────────────────┐
                  │  GitHub (repo)   │
                  │  jpwolfson-site  │
                  └────────┬─────────┘
                           │ push to main
                  ┌────────▼─────────┐
                  │ Cloudflare Pages │── _headers (security headers)
                  │  jpwolfson.com   │── _site/ (static HTML)
                  └────────┬─────────┘
                           │
          ┌────────────────┼────────────────────┐
          │                │                    │
    Public pages       /admin/           OAuth Worker
    (base.njk)     (index.html)    (jpwolfson-cms-auth.
    CSP: hash-based  CSP: unsafe-eval   workers.dev)
    MathJax (SRI)    Decap CMS (SRI)  postMessage: restricted
                          │                    │
                          └──── GitHub OAuth ──┘
```

Detailed reports from the 2026-02-22/23 audit are in [`security-audits/`](security-audits/).
