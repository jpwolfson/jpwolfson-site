/**
 * Cloudflare Worker – GitHub OAuth proxy for Decap CMS
 *
 * Deploy this as a Cloudflare Worker (free tier).
 * Set these environment variables (Secrets) in the Worker settings:
 *
 *   GITHUB_CLIENT_ID      – from your GitHub OAuth App
 *   GITHUB_CLIENT_SECRET  – from your GitHub OAuth App
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

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    // Step 1: Redirect to GitHub for authorization
    if (url.pathname === "/oauth/authorize") {
      const params = new URLSearchParams({
        client_id: env.GITHUB_CLIENT_ID,
        scope: "repo,user",
        redirect_uri: `${url.origin}/oauth/callback`,
        state: url.searchParams.get("state") || "",
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
        return new Response(
          `GitHub OAuth error: ${tokenData.error_description || tokenData.error}`,
          { status: 400 }
        );
      }

      const token = tokenData.access_token;

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
  var tokenMsg = 'authorization:' + provider + ':success:' + JSON.stringify({ token: token, provider: provider });

  if (!window.opener) {
    window.close();
    return;
  }

  // Step 1: announce we are authorizing
  window.opener.postMessage('authorizing:' + provider, '*');

  // Step 2: wait for CMS to respond, then send token
  window.addEventListener('message', function handler(e) {
    if (e.data === 'authorizing:' + provider) {
      window.removeEventListener('message', handler);
      window.opener.postMessage(tokenMsg, e.origin || '*');
      setTimeout(function() { window.close(); }, 500);
    }
  });

  // Fallback: send token directly after 5s if no handshake reply
  setTimeout(function() {
    window.opener.postMessage(tokenMsg, '*');
    window.close();
  }, 5000);
})();
</script>
</body>
</html>`;

      return new Response(html, {
        headers: { "Content-Type": "text/html" },
      });
    }

    return new Response("Not found", { status: 404 });
  },
};
