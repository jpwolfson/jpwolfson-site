# Security Audit — Phase 2: Focused Code Review

**Date:** 2026-02-22
**Auditor:** Claude Opus 4.6
**Scope:** Deep manual-style review of six files plus seven threat-model questions

---

## Summary of Findings

| # | Severity | File | Title |
|---|----------|------|-------|
| F-01 | **CRITICAL** | worker.js:89,101 | postMessage sends OAuth token to any opener via `'*'` |
| F-02 | **CRITICAL** | worker.js:101-104 | 5-second fallback guarantees token delivery to any origin |
| F-03 | **HIGH** | admin/index.html:10 | No SRI on Decap CMS script loaded from unpkg.com |
| F-04 | **HIGH** | base.njk:14 | No SRI on MathJax script loaded from jsdelivr.net |
| F-05 | **HIGH** | worker.js:29 | OAuth scope `repo,user` — `user` is unnecessary |
| F-06 | **MEDIUM** | worker.js (absent) | ALLOWED_DOMAINS env var set but never enforced |
| F-07 | **MEDIUM** | worker.js:74-108 | Token-bearing HTML response lacks Cache-Control and security headers |
| F-08 | **MEDIUM** | admin/index.html | No Content Security Policy on admin panel |
| F-09 | **MEDIUM** | base.njk | No Content Security Policy on public pages |
| F-10 | **MEDIUM** | config.yml:8 | CMS pushes directly to main; no branch protection |
| F-11 | **LOW** | worker.js:31 | State parameter passed through without server-side validation |
| F-12 | **LOW** | worker.js:63 | GitHub error descriptions echoed verbatim to user |
| F-13 | **LOW** | link-audit.yml:24,26,39 | GitHub Actions pinned to major version, not commit SHA |
| F-14 | **LOW** | link-audit.yml:32 | pip install without pinned versions or hash checking |
| F-15 | **INFO** | base.njk:33 | `{{ content \| safe }}` — acceptable given content pipeline |
| F-16 | **INFO** | wrangler.toml | Clean — no hardcoded secrets |

**Totals:** 2 Critical, 3 High, 5 Medium, 4 Low, 2 Informational

---

## Detailed Findings

### F-01 — CRITICAL: postMessage sends OAuth token to any opener via `'*'`

**File:** `oauth-worker/worker.js:89,95`

```js
// Line 89 — initial handshake, wildcard origin
window.opener.postMessage('authorizing:' + provider, '*');

// Line 95 — token delivery, origin derived from whoever replies
window.opener.postMessage(tokenMsg, e.origin || '*');
```

**Analysis:**

The Decap CMS OAuth handshake works as follows:

1. The admin panel opens a popup to `/oauth/authorize`.
2. After the GitHub code-for-token exchange, the worker returns an HTML page.
3. That page sends `'authorizing:github'` to `window.opener` with target origin `'*'`.
4. It then waits for the opener to reply with the same string, and sends the token to `window.opener` using `e.origin` as the target origin.

The critical flaw: **any site can open this popup.** An attacker at `evil.com` can:

1. Open `https://jpwolfson-cms-auth.jpwolfson.workers.dev/oauth/authorize` as a popup.
2. Receive the `'authorizing:github'` handshake (sent to `'*'`).
3. Reply with `'authorizing:github'`.
4. The popup sends the token to `window.opener` with target origin `'https://evil.com'` — which succeeds because `window.opener` *is* `evil.com`.

If the user has previously authorized the GitHub OAuth App, GitHub will silently redirect back with a code (no user prompt). The entire attack can execute with a single click.

**Remediation:**

Replace `'*'` with the specific allowed origin:

```js
var ALLOWED_ORIGIN = 'https://jpwolfson.com';

window.opener.postMessage('authorizing:' + provider, ALLOWED_ORIGIN);

// In the handler:
window.opener.postMessage(tokenMsg, ALLOWED_ORIGIN);
```

The allowed origin should be either hardcoded or read from a Worker environment variable, **never** derived from the incoming message's `e.origin`.

---

### F-02 — CRITICAL: 5-second fallback guarantees token delivery to any origin

**File:** `oauth-worker/worker.js:101-104`

```js
setTimeout(function() {
    window.opener.postMessage(tokenMsg, '*');
    window.close();
}, 5000);
```

**Analysis:**

Even if the handshake in F-01 were fixed, this fallback sends the token to `window.opener` with target origin `'*'` after 5 seconds. This is an unconditional, guaranteed delivery of the token to any opener, regardless of origin.

This fallback was presumably added to handle edge cases where the CMS parent doesn't respond to the handshake. But it completely nullifies any origin restriction in the handshake path.

**Remediation:**

Either remove the fallback entirely, or restrict it to the allowed origin:

```js
setTimeout(function() {
    window.opener.postMessage(tokenMsg, ALLOWED_ORIGIN);
    window.close();
}, 5000);
```

---

### F-03 — HIGH: No SRI on Decap CMS script (unpkg.com)

**File:** `src/admin/index.html:10`

```html
<script src="https://unpkg.com/decap-cms@^3.0.0/dist/decap-cms.js"></script>
```

**Analysis:**

- No `integrity` attribute (Subresource Integrity).
- Version range `^3.0.0` resolves to the latest 3.x release — the actual file served changes whenever a new version is published.
- unpkg.com serves npm packages directly. If unpkg is compromised, or if a malicious version of `decap-cms` is published to npm (e.g., via maintainer account takeover), arbitrary JavaScript would execute in the admin panel.
- The admin panel holds the GitHub OAuth token. A supply-chain compromise here means full `repo,user` token theft.

**Remediation:**

Pin to an exact version and add an SRI hash:

```html
<script src="https://unpkg.com/decap-cms@3.3.4/dist/decap-cms.js"
        integrity="sha384-<hash>"
        crossorigin="anonymous"></script>
```

Generate the hash with:
```
curl -s https://unpkg.com/decap-cms@3.3.4/dist/decap-cms.js | openssl dgst -sha384 -binary | openssl base64 -A
```

---

### F-04 — HIGH: No SRI on MathJax script (jsdelivr.net)

**File:** `src/_includes/base.njk:14`

```html
<script async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml.js"></script>
```

**Analysis:**

- No `integrity` attribute.
- Version `mathjax@3` resolves to latest 3.x — the file changes with each release.
- jsdelivr.net has had historical incidents (e.g., the 2021 compromise where jsdelivr served modified files).
- Unlike the admin panel, this script loads on **every public page** of the site.
- A compromised MathJax could inject crypto miners, redirect visitors, exfiltrate page content, or deface the site.

**Remediation:**

Pin to an exact version and add SRI:

```html
<script async
        src="https://cdn.jsdelivr.net/npm/mathjax@3.2.2/es5/tex-chtml.js"
        integrity="sha384-<hash>"
        crossorigin="anonymous"></script>
```

---

### F-05 — HIGH: OAuth scope includes unnecessary `user` permission

**File:** `oauth-worker/worker.js:29`

```js
scope: "repo,user",
```

**Analysis:**

- `repo` scope: full read/write access to **all** repositories the authenticated user can access — not just `jpwolfson-site`. This is unfortunately the minimum GitHub OAuth scope that allows pushing commits (GitHub does not support per-repo scoping via OAuth).
- `user` scope: read access to the user's profile data, email addresses (including private ones), and the ability to update profile information. **This is completely unnecessary for Decap CMS**, which only needs to read/write repository content.
- If the token is stolen (see F-01/F-02), the `user` scope increases the blast radius by exposing personal data.

**Remediation:**

Change to `repo` only:

```js
scope: "repo",
```

---

### F-06 — MEDIUM: ALLOWED_DOMAINS configured but never enforced

**File:** `oauth-worker/worker.js` (absent), `SETUP.md:94`

**Analysis:**

The SETUP.md instructs the user to set an `ALLOWED_DOMAINS` environment variable on the Cloudflare Worker:

> `ALLOWED_DOMAINS` → `jpwolfson.com`

But `worker.js` never references `env.ALLOWED_DOMAINS`. The variable is silently ignored. This creates a false sense of security — an operator believes origin restrictions are in place, but no enforcement exists.

**Remediation:**

Either implement domain checking in the worker (validate the `Referer` or `Origin` header on `/oauth/authorize`, and restrict `postMessage` targets), or remove the `ALLOWED_DOMAINS` instruction from SETUP.md to avoid confusion.

Implementing it:

```js
if (url.pathname === "/oauth/authorize") {
  const referer = request.headers.get("Referer") || "";
  const allowed = (env.ALLOWED_DOMAINS || "").split(",").map(d => d.trim());
  const refererHost = new URL(referer).hostname;
  if (!allowed.some(d => refererHost === d || refererHost.endsWith('.' + d))) {
    return new Response("Forbidden", { status: 403 });
  }
  // ... rest of authorize logic
}
```

---

### F-07 — MEDIUM: Token-bearing HTML response lacks security headers

**File:** `oauth-worker/worker.js:110-112`

```js
return new Response(html, {
    headers: { "Content-Type": "text/html" },
});
```

**Analysis:**

The HTML page containing the OAuth token is served with only a `Content-Type` header. Missing:

- `Cache-Control: no-store` — the token page could be cached by the browser, an intermediary proxy, or a browser extension, making the token retrievable after the session ends.
- `X-Frame-Options: DENY` — the page could be framed.
- `Content-Security-Policy: default-src 'none'; script-src 'unsafe-inline'` — the page should only allow its own inline script.
- `Referrer-Policy: no-referrer` — prevents the token URL from leaking via Referer header if the page somehow navigates.

**Remediation:**

```js
return new Response(html, {
    headers: {
        "Content-Type": "text/html",
        "Cache-Control": "no-store",
        "X-Frame-Options": "DENY",
        "Content-Security-Policy": "default-src 'none'; script-src 'unsafe-inline'",
        "Referrer-Policy": "no-referrer",
    },
});
```

---

### F-08 — MEDIUM: No Content Security Policy on admin panel

**File:** `src/admin/index.html`

**Analysis:**

The admin panel HTML has no CSP meta tag and relies solely on whatever headers Cloudflare Pages sends (or Cloudflare Transform Rules add). Without CSP, any injected script (via XSS, browser extension, or compromised CDN) can freely exfiltrate data, load additional scripts, or communicate with arbitrary servers.

A CSP for this page should at minimum restrict `script-src` to `unpkg.com` and `'self'`, and `connect-src` to `api.github.com` and the OAuth worker.

**Remediation:**

Add a CSP meta tag:

```html
<meta http-equiv="Content-Security-Policy"
      content="default-src 'self';
               script-src 'self' https://unpkg.com;
               style-src 'self' 'unsafe-inline' https://unpkg.com;
               connect-src 'self' https://api.github.com https://jpwolfson-cms-auth.jpwolfson.workers.dev;
               img-src 'self' data: https:;
               frame-src 'none';" />
```

Note: Decap CMS uses inline styles extensively, so `'unsafe-inline'` for `style-src` may be required. Test after adding.

---

### F-09 — MEDIUM: No Content Security Policy on public pages

**File:** `src/_includes/base.njk`

**Analysis:**

Public pages load MathJax from jsdelivr but have no CSP to restrict what other scripts could execute. This is lower severity than the admin panel (no OAuth tokens on public pages), but still represents a defense-in-depth gap.

**Remediation:**

Add via Cloudflare Transform Rule (preferred) or meta tag:

```
Content-Security-Policy: default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self' https://cdn.jsdelivr.net;
```

Note: MathJax requires `'unsafe-inline'` for script-src due to its inline script configuration block.

---

### F-10 — MEDIUM: CMS pushes directly to main with no branch protection

**File:** `src/admin/config.yml:8`

```yaml
branch: main
```

**Analysis:**

Decap CMS commits directly to `main`, which triggers immediate deployment via Cloudflare Pages. There is no mention of GitHub branch protection rules. Without them:

- A compromised OAuth token could push arbitrary content (or code) directly to production.
- Accidental CMS edits go live immediately with no review gate.
- There's no audit trail beyond the git log.

**Remediation:**

On GitHub, enable branch protection for `main`:
- Require pull request reviews (even if you approve your own).
- Or, at minimum, enable "Restrict who can push to matching branches" to limit direct pushes to specific accounts.

Alternatively, change the CMS to use `publish_mode: editorial_workflow` (creates PRs instead of direct commits), but note this requires the GitHub API backend and additional configuration.

---

### F-11 — LOW: State parameter passed through without server-side validation

**File:** `oauth-worker/worker.js:31`

```js
state: url.searchParams.get("state") || "",
```

**Analysis:**

The worker passes whatever `state` value the client provides directly to GitHub. It does not generate, store, or validate the state parameter. Decap CMS handles state validation on the client side, which is the standard pattern for a stateless OAuth proxy. However, this means CSRF protection depends entirely on the CMS JavaScript — if the CMS code has a bug in state validation, there's no server-side safety net.

The empty-string fallback (`|| ""`) also means the flow works with no state parameter at all, which GitHub permits but is contrary to OAuth 2.0 security best practices.

**Remediation:**

For a stateless proxy, this is acceptable but could be improved. A signed-state approach (generate HMAC-signed state on `/authorize`, validate on `/callback`) would add server-side CSRF protection without requiring persistent storage.

---

### F-12 — LOW: GitHub error descriptions echoed to user

**File:** `oauth-worker/worker.js:63`

```js
`GitHub OAuth error: ${tokenData.error_description || tokenData.error}`
```

**Analysis:**

GitHub's error messages are passed directly to the user. In practice, GitHub's OAuth error messages are generic and unlikely to leak sensitive information, but best practice is to log the detailed error server-side and show a generic message to the user.

**Remediation:**

```js
console.error("OAuth error:", tokenData.error, tokenData.error_description);
return new Response("Authentication failed. Please try again.", { status: 400 });
```

---

### F-13 — LOW: GitHub Actions pinned to major versions

**File:** `.github/workflows/link-audit.yml:24,26,39`

```yaml
- uses: actions/checkout@v4
- uses: actions/setup-python@v5
- uses: actions/upload-artifact@v4
```

**Analysis:**

Pinning to major versions (`@v4`) means any new minor/patch release is automatically adopted. A compromised GitHub Actions release could execute arbitrary code in the CI environment. Best practice for security-sensitive workflows is to pin to the full commit SHA.

**Remediation:**

```yaml
- uses: actions/checkout@b4ffde65f46336ab88eb53be808477a3936bae11  # v4.1.1
```

This is low priority for a link-audit workflow that has no access to secrets.

---

### F-14 — LOW: pip install without version pinning

**File:** `.github/workflows/link-audit.yml:32`

```yaml
run: pip install requests beautifulsoup4
```

**Analysis:**

Unpinned `pip install` fetches whatever version is current on PyPI. A supply-chain attack on either package would execute in the CI runner. The blast radius is limited — this workflow only runs the link auditor and has no access to deploy secrets.

**Remediation:**

Pin versions: `pip install requests==2.31.0 beautifulsoup4==4.12.3`

---

### F-15 — INFO: `{{ content | safe }}` is standard for this architecture

**File:** `src/_includes/base.njk:33`

```njk
{{ content | safe }}
```

**Analysis:**

The `safe` filter tells Nunjucks not to HTML-escape the content. This is standard and necessary in static site generators — the markdown-to-HTML pipeline produces trusted HTML that must be rendered as-is. The content originates from markdown files in the repository, authored by the site owner via Decap CMS or git. There is no public user-generated content.

The risk materializes only if an attacker gains write access to the repository, at which point they could inject arbitrary HTML/JS. But at that point, they already have full repo access and could modify templates, configuration, or deployment settings directly.

**Verdict:** No action needed. This is working as designed.

---

### F-16 — INFO: wrangler.toml is clean

**File:** `oauth-worker/wrangler.toml`

```toml
name = "jpwolfson-cms-auth"
main = "worker.js"
compatibility_date = "2026-02-19"
```

**Analysis:**

No secrets, no hardcoded values, no sensitive configuration. Secrets (`GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`) are correctly managed via the Cloudflare dashboard as encrypted environment variables.

**Verdict:** No issues.

---

## Threat Model Answers

### Q1: Can an attacker intercept the GitHub OAuth token via the postMessage wildcard `'*'`?

**Yes — this is the most critical finding.**

The attack requires a single user click on an attacker-controlled page. If the user has previously authorized the GitHub OAuth App, the entire flow completes silently (GitHub auto-redirects without prompting). The 5-second fallback (F-02) guarantees token delivery even if the handshake fails.

**Attack chain:**
1. Attacker page at `evil.com` opens popup to `/oauth/authorize`.
2. Popup redirects to GitHub → GitHub auto-redirects back with `code` (no user interaction if previously authorized).
3. Worker exchanges code for token, returns HTML.
4. HTML sends `'authorizing:github'` to `window.opener` (evil.com) via `'*'`.
5. Evil.com replies with `'authorizing:github'`.
6. Popup sends token to `window.opener` with `e.origin` (`evil.com`) as target — succeeds because `window.opener` *is* evil.com.
7. Even without step 5-6, the 5-second fallback sends the token via `'*'` unconditionally.

**Result:** Attacker obtains a GitHub token with `repo,user` scope.

### Q2: Is the OAuth state parameter validated to prevent CSRF?

**Partially.** The worker is a stateless proxy — it passes the `state` parameter through to GitHub and back, but never validates it. Decap CMS is responsible for generating and checking the state on the client side. This is the standard pattern for stateless OAuth proxies and is acceptable, though a signed-state approach would add a server-side safety net. The empty-string fallback (`|| ""`) is slightly concerning — it means the flow works with no state at all.

### Q3: Is the `repo,user` scope excessive?

**Yes.** The `user` scope is unnecessary — Decap CMS only needs `repo` scope. Even `repo` is broader than ideal (it grants access to all of the user's repos), but GitHub OAuth doesn't support per-repo scoping. Removing `user` reduces the blast radius of a token compromise by eliminating access to personal profile data and email addresses.

### Q4: What happens if the Decap CMS CDN (unpkg.com) is compromised?

**Full token theft.** The admin panel loads Decap CMS from `unpkg.com` without SRI, using a version range (`^3.0.0`) that auto-resolves. If unpkg is compromised or a malicious npm version is published, arbitrary JavaScript executes in the admin context. That JavaScript has access to the GitHub OAuth token (it's in the same page context), enabling silent exfiltration. The same applies to MathJax from jsdelivr on public pages (F-04), though public pages don't hold OAuth tokens.

### Q5: Can anyone with a GitHub account use the admin panel, or only repo collaborators?

**Anyone can authenticate, but only collaborators can write.** The OAuth flow does not restrict which GitHub users can obtain a token. However, the resulting token only grants write access to repositories where the user is a collaborator. A non-collaborator would successfully authenticate with Decap CMS but fail when trying to save changes (GitHub API would return 403). The `user` scope, however, would still grant access to the authenticating user's own profile data regardless of collaborator status.

### Q6: Does `{{ content | safe }}` create XSS risk?

**Negligible, given the content pipeline.** Content comes from trusted markdown files in the repository, not from public users. The markdown-to-HTML conversion is handled by Eleventy's markdown processor (markdown-it), which produces standard HTML. The `safe` filter is standard and necessary for static site generators. The risk only materializes if an attacker gains write access to the repo — but at that point, they already have full control and could modify templates or configuration directly.

### Q7: Are Cloudflare Worker secrets properly isolated?

**Yes.** `wrangler.toml` contains no secrets. `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`, and `ALLOWED_DOMAINS` are configured as encrypted environment variables via the Cloudflare dashboard, encrypted at rest and available only within the Worker's execution context. The one issue is that `ALLOWED_DOMAINS` is set but never read by the code (F-06), creating a false sense of security.

---

## Confirmed Open Findings from Phase 1

These findings were identified in Phase 1 and are confirmed still present:

1. **SRI hashes missing** on Decap CMS (unpkg) and MathJax (jsdelivr) — now documented as F-03 and F-04.
2. **ALLOWED_DOMAINS not enforced** in worker.js — now documented as F-06.
3. **npm audit: 4 HIGH** (build-time ReDoS in minimatch via `@11ty/eleventy@^3.0.0` dependency tree) — build-time only, does not affect the deployed site.

---

## Prioritized Remediation Roadmap

### Immediate (do now)

| Finding | Action | Effort |
|---------|--------|--------|
| F-01, F-02 | Hardcode allowed origin in postMessage; remove or restrict fallback | 15 min |
| F-05 | Change scope from `repo,user` to `repo` | 1 min |
| F-07 | Add Cache-Control, CSP, X-Frame-Options, Referrer-Policy to token response | 5 min |

### Short-term (this week)

| Finding | Action | Effort |
|---------|--------|--------|
| F-03 | Pin Decap CMS version and add SRI hash | 15 min |
| F-04 | Pin MathJax version and add SRI hash | 15 min |
| F-06 | Implement ALLOWED_DOMAINS enforcement or remove from docs | 30 min |
| F-10 | Enable branch protection on main | 10 min (GitHub UI) |

### Medium-term (when convenient)

| Finding | Action | Effort |
|---------|--------|--------|
| F-08 | Add CSP meta tag to admin/index.html | 30 min (needs testing) |
| F-09 | Add CSP header via Cloudflare for public pages | 30 min (needs testing) |
| F-12 | Replace verbose error with generic message | 5 min |
| F-13, F-14 | Pin Actions to SHA, pin pip versions | 15 min |

---

## Methodology

Each file was reviewed line by line with attention to:

- **Authentication & authorization:** OAuth flow correctness, token handling, scope
- **Input validation:** Parameter sanitization, origin checking
- **Output encoding:** XSS prevention, HTML escaping
- **Transport security:** HTTPS enforcement, header hygiene
- **Supply chain:** CDN integrity, dependency pinning
- **Secrets management:** Hardcoded credentials, environment isolation
- **Access control:** Who can authenticate, who can write, branch protection

The seven threat-model questions were evaluated against the actual code behavior, not documentation or intent.

---

## Remediation Status

All code-fixable findings have been remediated in this commit:

| # | Finding | Status | Notes |
|---|---------|--------|-------|
| F-01 | postMessage wildcard `'*'` | **FIXED** | postMessage now targets `ALLOWED_DOMAINS` origin only |
| F-02 | 5-second fallback to `'*'` | **FIXED** | Fallback now also uses restricted `targetOrigin` |
| F-03 | No SRI on Decap CMS | **PARTIAL** | Pinned to `3.10.0` + `crossorigin`; SRI hash must be computed locally (see comment in file) |
| F-04 | No SRI on MathJax | **PARTIAL** | Pinned to `3.2.2` + `crossorigin`; SRI hash must be computed locally (see comment in file) |
| F-05 | Scope `repo,user` | **FIXED** | Changed to `repo` only |
| F-06 | ALLOWED_DOMAINS unenforced | **FIXED** | Worker now reads and enforces `ALLOWED_DOMAINS` via Referer check and postMessage origin |
| F-07 | Missing security headers | **FIXED** | Added `Cache-Control: no-store`, `X-Frame-Options: DENY`, CSP, `Referrer-Policy: no-referrer` |
| F-08 | No CSP on admin panel | **FIXED** | Added CSP meta tag restricting scripts to `self` + `unpkg.com` |
| F-09 | No CSP on public pages | **FIXED** | Added CSP meta tag restricting scripts to `self` + `cdn.jsdelivr.net` |
| F-10 | No branch protection | **MANUAL** | Requires GitHub UI: Settings → Branches → Add rule for `main` |
| F-11 | State parameter passthrough | **FIXED** | Empty state now rejected with 400 (requires `state` parameter) |
| F-12 | Verbose error messages | **FIXED** | Errors logged to console; generic message returned to user |
| F-13 | Actions pinned to major version | **FIXED** | Pinned to full commit SHAs |
| F-14 | Unpinned pip install | **FIXED** | Pinned to `requests==2.32.5 beautifulsoup4==4.14.3` |
| F-15 | `{{ content \| safe }}` | N/A | No action needed (acceptable pattern) |
| F-16 | wrangler.toml | N/A | No issues found |

### Remaining manual steps

1. **Compute and add SRI hashes** (F-03, F-04): Run the commands in the HTML comments to generate `integrity` attributes, then add them to the `<script>` tags.

2. **Enable branch protection** (F-10): Go to GitHub → `jpwolfson/jpwolfson-site` → Settings → Branches → Add branch protection rule for `main`. Recommended settings:
   - Require a pull request before merging
   - Restrict who can push to matching branches

3. **Redeploy the Cloudflare Worker**: Copy the updated `oauth-worker/worker.js` to the Cloudflare Workers dashboard, or deploy via `wrangler deploy`. The `ALLOWED_DOMAINS` secret should already be set to `jpwolfson.com`.

4. **Test the CMS login flow** after deploying the worker changes. The postMessage origin restriction may require that the admin panel is accessed at `https://jpwolfson.com/admin/` (not the `.pages.dev` URL).
