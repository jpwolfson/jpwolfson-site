# Security Audit — jpwolfson.com

**Date:** 2026-02-22
**Scope:** Static site (Eleventy → Cloudflare Pages), Decap CMS, Cloudflare Worker OAuth proxy
**Branch:** `claude/security-audit-workflow-Bz1cO`

---

## Summary

| Severity | Count |
|---|---|
| Critical | 2 |
| High | 3 |
| Medium | 5 |
| Low / Info | 3 |

The most urgent issues are both in `oauth-worker/worker.js`: a wildcard `postMessage` fallback that can broadcast the GitHub OAuth token to any listening window, and the absence of Subresource Integrity (SRI) on the Decap CMS CDN script that handles those same tokens. These two findings create a realistic path to full GitHub account takeover from a CDN supply-chain compromise.

---

## Critical

### C1 — Wildcard postMessage fallback broadcasts GitHub token to all origins

**File:** `oauth-worker/worker.js:101–104`

```js
// Fallback: send token directly after 5s if no handshake reply
setTimeout(function() {
  window.opener.postMessage(tokenMsg, '*');   // ← '*' = any origin
  window.close();
}, 5000);
```

**Attack scenario:** The OAuth popup posts the GitHub access token to `'*'` — every window/frame that can receive messages — after a 5-second timeout. This fires whenever the handshake doesn't complete within 5 seconds (slow network, CMS tab backgrounded, browser throttling timers in background tabs). Any page the user has open that listens for `window.message` events can silently capture the token. The token carries `repo,user` scope (see H1), so the attacker gains full read/write access to all of the user's GitHub repositories.

There is also a subtler version of this issue on line 95:

```js
window.opener.postMessage(tokenMsg, e.origin || '*');
```

The message handler accepts `'authorizing:github'` from **any** origin with no validation. An attacker script that sends that string first causes the token to be sent to the attacker's origin — without waiting 5 seconds, and without the user noticing.

**Fix — restrict target origin to the known CMS origin:**

Define the allowed CMS origin as a constant (it is already known — it's the Cloudflare Pages URL) and use it as the `targetOrigin` argument in every `postMessage` call. Add an origin check before accepting the handshake reply.

```js
// At the top of the callback HTML script, replace the current logic with:
const CMS_ORIGIN = 'https://jpwolfson.com';   // or the *.pages.dev preview URL

window.opener.postMessage('authorizing:' + provider, CMS_ORIGIN);

window.addEventListener('message', function handler(e) {
  if (e.origin !== CMS_ORIGIN) return;          // reject unexpected senders
  if (e.data === 'authorizing:' + provider) {
    window.removeEventListener('message', handler);
    window.opener.postMessage(tokenMsg, CMS_ORIGIN);
    setTimeout(function() { window.close(); }, 500);
  }
});

// Remove the 5-second fallback entirely — it provides no safety benefit
// and creates the primary vulnerability.
```

The fallback was added to handle the case where Decap CMS doesn't reply to the handshake. With a pinned target origin on the initial announcement, Decap CMS will receive it and reply correctly in all normal circumstances. If the CMS genuinely fails to reply, closing without sending the token is the correct behaviour — not broadcasting it to `'*'`.

---

### C2 — No Subresource Integrity on Decap CMS CDN script

**File:** `src/admin/index.html:10`

```html
<script src="https://unpkg.com/decap-cms@^3.0.0/dist/decap-cms.js"></script>
```

**Attack scenario:** The admin page loads Decap CMS from `unpkg.com` with no `integrity` attribute and a floating version constraint (`^3.0.0`). If unpkg is compromised, serves a malicious build, or a cache-poisoning attack substitutes malicious content, the injected script runs inside the admin origin with full access to `window.opener` postMessage communications, the GitHub OAuth flow, and the ability to exfiltrate tokens silently. This is a CDN supply-chain attack that converts a CDN compromise into a full GitHub token theft without any user interaction beyond logging in.

The `^3.0.0` constraint makes this worse: it automatically fetches newer 3.x releases, so a malicious version published to npm and mirrored on unpkg would be served immediately.

**Fix — pin an exact version and add an SRI hash:**

1. Pick the current stable release (e.g., `3.3.3` — verify on npmjs.com).
2. Download the bundle, compute the hash:
   ```sh
   curl -s https://unpkg.com/decap-cms@3.3.3/dist/decap-cms.js \
     | openssl dgst -sha384 -binary | openssl base64 -A
   ```
3. Add the exact version URL and `integrity` attribute:
   ```html
   <script
     src="https://unpkg.com/decap-cms@3.3.3/dist/decap-cms.js"
     integrity="sha384-<hash-from-step-2>"
     crossorigin="anonymous">
   </script>
   ```

Re-pin (and audit the release notes) whenever you intentionally upgrade.

---

## High

### H1 — OAuth scope `repo,user` is excessively broad

**File:** `oauth-worker/worker.js:29`

```js
scope: "repo,user",
```

**Description:** The `repo` scope grants read/write access to **all** repositories (public and private) owned by the authenticating user, plus collaborator management and commit status writes. The `user` scope grants read/write access to the user's profile data. This CMS only needs to commit Markdown files to one public repository.

**Attack scenario:** A stolen or leaked token (via C1, C2, or any other vector) does not just compromise the website — it compromises the user's entire GitHub account: all private repositories, any organisation repositories they belong to, and the ability to add SSH keys or OAuth apps.

**Fix:** Change the scope to `public_repo`, which limits access to public repositories only and permits commits to this site's repo without exposing private repos or profile data:

```js
scope: "public_repo",
```

If `user:email` is needed for any reason (Decap CMS typically does not need it), add only that granular scope rather than the full `user` scope.

---

### H2 — OAuth state parameter not validated server-side

**File:** `oauth-worker/worker.js:31, 37–68`

```js
// In /oauth/authorize — state is proxied through but not stored
state: url.searchParams.get("state") || "",

// In /oauth/callback — state is never read or validated
if (url.pathname === "/oauth/callback") {
  const code = url.searchParams.get("code");
  // No: const state = url.searchParams.get("state");
  // No: if (state !== expectedState) return error;
```

**Description:** The CSRF protection in OAuth 2.0 relies on the state parameter being generated by the client, stored (in session or localStorage), and compared against what GitHub returns in the callback. The worker proxies the state to GitHub correctly but never validates the returned state in the callback. It relies entirely on Decap CMS performing this check client-side.

**Attack scenario:** If Decap CMS has a bug or is compromised (C2), the state check disappears and the worker becomes vulnerable to CSRF: an attacker tricks the user's browser into completing an OAuth flow with an attacker-controlled `code`, exchanging it for a token issued to the attacker's OAuth App.

**Fix:** Because this is a stateless Cloudflare Worker (no session storage), full server-side CSRF validation requires either signed state (HMAC with a worker secret) or passing state validation responsibility explicitly to the CMS. At minimum, validate that state is non-empty:

```js
const state = url.searchParams.get("state");
const code = url.searchParams.get("code");

if (!code) return new Response("Missing code parameter", { status: 400 });
if (!state) return new Response("Missing state parameter", { status: 400 });
```

For full CSRF protection, sign the state with HMAC-SHA256 in `/oauth/authorize`, store the signature in the URL, and verify it in `/oauth/callback`. This is stateless and works within Worker constraints.

---

### H3 — No ALLOWED_DOMAINS enforcement in the Worker

**File:** `oauth-worker/worker.js` (entire file), `oauth-worker/wrangler.toml`

**Description:** The previous audit noted an `ALLOWED_DOMAINS` env var set to `jpwolfson.com`. This variable does not appear in `wrangler.toml` and is not referenced anywhere in `worker.js`. The worker accepts OAuth initiation requests from **any** origin. Any website can link to `https://jpwolfson-cms-auth.jpwolfson.workers.dev/oauth/authorize` and initiate an OAuth flow using your Client ID, potentially confusing users or burning your GitHub OAuth App's rate limits.

**Fix:** Check the `Referer` or `Origin` header in `/oauth/authorize` and reject requests that don't originate from the known CMS origin:

```js
if (url.pathname === "/oauth/authorize") {
  const origin = request.headers.get("Origin") || request.headers.get("Referer") || "";
  const allowed = env.ALLOWED_ORIGINS || "https://jpwolfson.com";
  const isAllowed = allowed.split(",").some(o => origin.startsWith(o.trim()));
  if (!isAllowed) {
    return new Response("Forbidden", { status: 403 });
  }
  // ... rest of the handler
}
```

Add `ALLOWED_ORIGINS = "https://jpwolfson.com"` to `wrangler.toml` under `[vars]`, or set it as a Worker secret.

---

## Medium

### M1 — No SRI on MathJax CDN script (affects all site visitors)

**File:** `src/_includes/base.njk:14`

```html
<script async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml.js"></script>
```

**Description:** MathJax is loaded on every page of the public site from jsDelivr without SRI. A jsDelivr compromise or cache-poisoning attack would inject malicious JS into every page for every visitor — not just the admin. Unlike C2 (which targets the admin), this targets all readers of the site.

**Fix:** Pin to an exact MathJax version and add an SRI hash:
```sh
curl -s https://cdn.jsdelivr.net/npm/mathjax@3.2.2/es5/tex-chtml.js \
  | openssl dgst -sha384 -binary | openssl base64 -A
```
```html
<script
  async
  src="https://cdn.jsdelivr.net/npm/mathjax@3.2.2/es5/tex-chtml.js"
  integrity="sha384-<hash>"
  crossorigin="anonymous">
</script>
```

---

### M2 — No Content-Security-Policy on the admin page

**File:** `src/admin/index.html`

**Description:** The admin page has no CSP header (which Cloudflare Pages would need to inject via `_headers`) and no CSP meta tag. There is also no `X-Frame-Options` or `frame-ancestors` directive, leaving the admin page vulnerable to clickjacking. An attacker who frames `/admin/` inside a transparent overlay can trick a logged-in user into initiating actions without realising it.

**Fix:** Add a Cloudflare Pages `_headers` file to the `src/` (or output) directory:

```
/admin/*
  Content-Security-Policy: default-src 'none'; script-src 'self' https://unpkg.com; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self' https://api.github.com https://jpwolfson-cms-auth.jpwolfson.workers.dev; frame-ancestors 'none'
  X-Frame-Options: DENY
  X-Content-Type-Options: nosniff
```

Adjust `script-src` and `connect-src` based on what Decap CMS actually needs at runtime (check the browser console after login for any CSP violations).

---

### M3 — `publish_mode: simple` removes the last line of defence against a compromised token

**File:** `src/admin/config.yml:12`

```yaml
publish_mode: simple
```

**Description:** With `simple` mode, every save in the CMS editor commits directly to `main` and deploys to production immediately. Combined with the `repo` scope (H1), a stolen token gives an attacker one click from injecting content into the live site. An `editorial_workflow` publish mode (if supported for this Decap version/backend) would require a PR review, adding a human checkpoint after a token compromise.

**Note:** Decap CMS's `editorial_workflow` requires GitHub's branch protection and PR mechanics. For a solo-author site, this is a usability trade-off. At minimum, consider enabling GitHub branch protection on `main` that requires a human review before merge, even if that reviewer is yourself via a separate session.

---

### M4 — Missing security headers on main site (requires Cloudflare Pages `_headers`)

**Phase 3 note:** The live site was not reachable from the audit environment (network access blocked). The following headers should be verified and added via a `_headers` file if not already present:

| Header | Recommended value |
|---|---|
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains; preload` |
| `X-Content-Type-Options` | `nosniff` |
| `X-Frame-Options` | `SAMEORIGIN` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |
| `Permissions-Policy` | `geolocation=(), microphone=(), camera=()` |
| `Content-Security-Policy` | See M2 above; public pages are simpler than admin |

Cloudflare Pages respects a `_headers` file at the root of the published output. Create `src/_headers` (or `_headers` at the project root, depending on Eleventy output config) with these directives.

---

### M5 — Floating Decap CMS version with no integrity check enables silent upgrades

**File:** `src/admin/index.html:10`

```html
src="https://unpkg.com/decap-cms@^3.0.0/dist/decap-cms.js"
```

**Description:** The `^3.0.0` constraint resolves to whatever the latest compatible release is at the time unpkg serves the file. This is different from npm where `package-lock.json` pins the resolved version — the CDN URL with `^` is re-resolved on every request. A version bump that introduces a breaking change or regression in the OAuth flow would silently take effect.

This is partially addressed by C2 (pin + SRI), but worth noting independently: the version constraint is the root cause; SRI is the detection mechanism.

---

## Low / Informational

### L1 — `{{ content | safe }}` is appropriate but ties site security to token security

**File:** `src/_includes/base.njk:33`

```nunjucks
{{ content | safe }}
```

**Description:** This is the correct pattern for an Eleventy CMS site — without `| safe`, Markdown-rendered HTML would be double-escaped. However, it means that anyone who can commit to the `main` branch can inject arbitrary HTML (including `<script>` tags) into any page on the public site. This is not a bug; it is an intentional design consequence. The implication is that the security of the public site is exactly as strong as the security of the GitHub token used by the CMS editor. All the token-security findings above (C1, C2, H1, H2) cascade here.

No code change needed. The fix is to resolve C1, C2, H1, and H2 to reduce token exposure risk.

---

### L2 — GitHub Actions workflow lacks explicit permissions declaration

**File:** `.github/workflows/link-audit.yml`

**Description:** The `audit` job has no `permissions:` block. For a public repository, the default GITHUB_TOKEN permissions include `contents: read`, which is sufficient for a checkout-and-run workflow. However, explicit permissions are a best practice that makes the intent clear and protects against changes to the repository's default permission settings.

**Fix:**
```yaml
jobs:
  audit:
    runs-on: ubuntu-latest
    permissions:
      contents: read
```

---

### L3 — GitHub Actions: action versions pinned to tags, not commit SHAs

**File:** `.github/workflows/link-audit.yml`

```yaml
- uses: actions/checkout@v4
- uses: actions/setup-python@v5
- uses: actions/upload-artifact@v4
```

**Description:** Tags like `v4` are mutable — the action maintainer can push a new commit to the `v4` tag at any time. For a workflow that runs on every push to content files, a supply-chain compromise of `actions/checkout` would give an attacker code execution with the GITHUB_TOKEN. SHA-pinning prevents this.

**Fix:** Replace tag references with the full commit SHA (find them on each action's GitHub releases page):
```yaml
- uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683  # v4.2.2
- uses: actions/setup-python@0b93645e9fea7318ecaed2b359559ac225c90a2b  # v5.3.0
- uses: actions/upload-artifact@65462800fd760344b1a7b4272f337f957bba11f8  # v4.4.3
```

---

## Remediation Priority Order

1. **C1** — Remove the 5-second `postMessage('*')` fallback; restrict all `postMessage` calls to the known CMS origin.
2. **C2** — Pin Decap CMS to an exact version and add SRI hash.
3. **H1** — Change OAuth scope from `repo,user` to `public_repo`.
4. **H2** — Add state parameter validation in the callback.
5. **H3** — Implement ALLOWED_ORIGINS check in `/oauth/authorize`.
6. **M1** — Add SRI to MathJax CDN script.
7. **M2** — Add CSP and `X-Frame-Options` to admin page.
8. **M4** — Add security headers `_headers` file for Cloudflare Pages.
9. **M3** — Consider `editorial_workflow` or GitHub branch protection.
10. **M5** — Resolved by C2.
11. **L2, L3** — Harden GitHub Actions permissions and SHA-pin actions.

---

## Notes on Phase 1 / Phase 3 (Live Site Checks)

The audit environment did not have outbound HTTP access to `jpwolfson.com` or `jpwolfson-cms-auth.jpwolfson.workers.dev` (all requests returned 403 `host_not_allowed` from the sandboxed network). The following checks should be run from a machine with normal internet access:

- `curl -sI https://jpwolfson.com/` — verify security headers (see M4)
- `curl -sI https://jpwolfson.com/admin/` — verify admin-specific headers
- `curl -sI https://jpwolfson-cms-auth.jpwolfson.workers.dev/` — verify worker CORS and security headers
- SSL Labs API or `testssl.sh` against `jpwolfson.com` — verify TLS config, cipher strength, certificate chain
- Manual OAuth flow trace — open DevTools Network tab, step through login, verify no token in URL params or unintended origins in postMessage events
- Directory enumeration: check `/.git/`, `/src/`, `/.env` — Cloudflare Pages should block these, but worth confirming
- Check Cloudflare dashboard: WAF rules, Bot Fight Mode, DDoS protection tier

No `ALLOWED_DOMAINS` environment variable was found in `wrangler.toml` or referenced in `worker.js`. If it exists as a Cloudflare Worker secret, it is currently dead configuration — the worker code doesn't read it.

---

## Git History

A surface-level scan of the git history found no committed secrets. All references to `GITHUB_CLIENT_SECRET` and `GITHUB_CLIENT_ID` in `worker.js` are `env.*` lookups, confirming these are correctly stored as Cloudflare Worker Secrets rather than hardcoded values.
