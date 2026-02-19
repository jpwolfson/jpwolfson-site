/**
 * Cloudflare Worker – GitHub OAuth proxy for Decap CMS
 *
 * Deploy this as a Cloudflare Worker (free tier).
 * Set these environment variables (Secrets) in the Worker settings:
 *
 *   GITHUB_CLIENT_ID      – from your GitHub OAuth App
 *   GITHUB_CLIENT_SECRET  – from your GitHub OAuth App
 *   ALLOWED_DOMAINS       – your site domain, e.g. "jpwolfson.com"
 *
 * The GitHub OAuth App callback URL should be:
 *   https://YOUR_WORKER_SUBDOMAIN.workers.dev/oauth/callback
 *   (or your custom domain if you've set one on the Worker)
 *
 * In admin/config.yml, set:
 *   base_url: https://YOUR_WORKER_SUBDOMAIN.workers.dev
 *   auth_endpoint: /oauth/callback
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
      const state = url.searchParams.get("state") || "";

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

      // Return a small HTML page that posts the token back to the CMS opener
      const script = `
        <script>
          const token = ${JSON.stringify(tokenData.access_token)};
          const state = ${JSON.stringify(state)};
          // Decap CMS listens for this postMessage
          if (window.opener) {
            window.opener.postMessage(
              'authorization:github:success:' + JSON.stringify({ token, provider: 'github' }),
              '*'
            );
          }
          window.close();
        </script>
      `;
      return new Response(`<!DOCTYPE html><html><body>${script}</body></html>`, {
        headers: { "Content-Type": "text/html" },
      });
    }

    return new Response("Not found", { status: 404 });
  },
};
