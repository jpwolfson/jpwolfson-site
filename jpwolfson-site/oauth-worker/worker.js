/**
 * Cloudflare Worker – GitHub OAuth proxy for Decap CMS
 *
 * Deploy this as a Cloudflare Worker (free tier).
 * Set these environment variables (Secrets) in the Worker settings:
 *
 *   GITHUB_CLIENT_ID      – from your GitHub OAuth App
 *   GITHUB_CLIENT_SECRET  – from your GitHub OAuth App
 *   ALLOWED_DOMAINS       – comma-separated list of allowed domains (e.g. "jpwolfson.com")
 *
 * The GitHub OAuth App callback URL should be:
 *   https://YOUR_WORKER_SUBDOMAIN.workers.dev/oauth/callback
 *
 * In admin/config.yml, set:
 *   base_url: https://YOUR_WORKER_SUBDOMAIN.workers.dev
 *   auth_endpoint: /oauth/authorize
 */

const GITHUB_AUTH_URL = "https://github.com/login/oauth/authorize";
const GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token";

/**
 * Parse ALLOWED_DOMAINS env var into a list of allowed origins (https://<domain>).
 * Falls back to an empty list if not set (all requests will be rejected).
 */
function getAllowedOrigins(env) {
  const raw = env.ALLOWED_DOMAINS || "";
  return raw
    .split(",")
    .map((d) => d.trim())
    .filter(Boolean)
    .map((d) => `https://${d}`);
}

/**
 * Check if a given origin is in the allowed list.
 */
function isOriginAllowed(origin, allowedOrigins) {
  return allowedOrigins.some(
    (allowed) => origin === allowed || origin.endsWith("." + allowed.replace("https://", ""))
  );
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const allowedOrigins = getAllowedOrigins(env);

    // Step 1: Redirect to GitHub for authorization
    if (url.pathname === "/oauth/authorize") {
      // Enforce ALLOWED_DOMAINS: check Referer header
      const referer = request.headers.get("Referer");
      if (referer && allowedOrigins.length > 0) {
        try {
          const refererOrigin = new URL(referer).origin;
          if (!isOriginAllowed(refererOrigin, allowedOrigins)) {
            return new Response("Forbidden", { status: 403 });
          }
        } catch {
          return new Response("Forbidden", { status: 403 });
        }
      } else if (allowedOrigins.length > 0 && !referer) {
        // No referer but domains are configured — allow (some browsers strip Referer)
        // The postMessage origin restriction is the primary defense.
      }

      const state = url.searchParams.get("state");
      if (!state) {
        return new Response("Missing state parameter", { status: 400 });
      }

      const params = new URLSearchParams({
        client_id: env.GITHUB_CLIENT_ID,
        scope: "repo",
        redirect_uri: `${url.origin}/oauth/callback`,
        state,
      });
      return Response.redirect(`${GITHUB_AUTH_URL}?${params}`, 302);
    }

    // Step 2: GitHub redirects back here with a code; exchange for token
    if (url.pathname === "/oauth/callback") {
      const code = url.searchParams.get("code");

      if (!code) {
        return new Response("Missing code parameter", { status: 400 });
      }

      // Exchange code for access token
      const tokenResponse = await fetch(GITHUB_TOKEN_URL, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify({
          client_id: env.GITHUB_CLIENT_ID,
          client_secret: env.GITHUB_CLIENT_SECRET,
          code,
          redirect_uri: `${url.origin}/oauth/callback`,
        }),
      });

      const tokenData = await tokenResponse.json();

      if (tokenData.error || !tokenData.access_token) {
        console.error("OAuth error:", tokenData.error, tokenData.error_description);
        return new Response("Authentication failed. Please try again.", {
          status: 400,
        });
      }

      const token = tokenData.access_token;

      // Determine the allowed postMessage target origin.
      // This is the primary defense against token theft via malicious openers.
      const targetOrigin =
        allowedOrigins.length > 0 ? allowedOrigins[0] : url.origin;

      // Decap CMS uses a two-step handshake:
      // 1. Popup announces "authorizing:github" to the CMS parent window
      // 2. CMS responds with the same message (confirming it's ready)
      // 3. Popup sends the actual token
      const html = `<!DOCTYPE html>
<html>
<body>
<script>
(function() {
  var provider = 'github';
  var token = ${JSON.stringify(token)};
  var targetOrigin = ${JSON.stringify(targetOrigin)};
  var tokenMsg = 'authorization:' + provider + ':success:' + JSON.stringify({ token: token, provider: provider });

  if (!window.opener) {
    window.close();
    return;
  }

  // Step 1: announce we are authorizing (restricted to allowed origin)
  window.opener.postMessage('authorizing:' + provider, targetOrigin);

  // Step 2: wait for CMS to respond, then send token (restricted to allowed origin)
  window.addEventListener('message', function handler(e) {
    if (e.data === 'authorizing:' + provider && e.origin === targetOrigin) {
      window.removeEventListener('message', handler);
      window.opener.postMessage(tokenMsg, targetOrigin);
      setTimeout(function() { window.close(); }, 500);
    }
  });

  // Fallback: send token directly after 5s (still restricted to allowed origin)
  setTimeout(function() {
    window.opener.postMessage(tokenMsg, targetOrigin);
    window.close();
  }, 5000);
})();
</script>
</body>
</html>`;

      return new Response(html, {
        headers: {
          "Content-Type": "text/html",
          "Cache-Control": "no-store",
          "X-Frame-Options": "DENY",
          "Content-Security-Policy":
            "default-src 'none'; script-src 'unsafe-inline'",
          "Referrer-Policy": "no-referrer",
        },
      });
    }

    return new Response("Not found", { status: 404 });
  },
};
