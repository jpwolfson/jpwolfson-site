# Batch A — local settings session runbook

**Run this once, from a Claude Code session on the owner's Mac**, in a fresh clone of
`jpwolfson/jpwolfson-site`. It changes GitHub repository settings and Cloudflare
account settings that the cloud sandbox cannot reach. It is a one-purpose session:
feed it this file and nothing else; it must not browse the web.

Everything here is idempotent. Run steps in order. Each step ends with a verification
command; do not continue past a failed verification.

**Shell state does not persist between an agent's Bash calls.** Every block below starts
with `source ~/.batch-a.env`; step 0 writes that file. Run each block as one Bash call. Record every command and its
output in `security-audits/2026-10/BATCH-A-LOG.md` and open a PR with that log and
the `SECURITY.md` status-table updates at the end.

## 0. Preconditions (owner, ~5 minutes, before starting the session)

```bash
node --version                      # must be >= 22.23.4 (CLAUDE.md rule 6); otherwise `nvm install 22` first
gh auth status                      # logged in as jpwolfson, scopes include repo, admin:repo_hook, workflow
cat > ~/.batch-a.env <<'ENV'
export R=jpwolfson/jpwolfson-site
export WRANGLER=wrangler@4.149.0            # pinned, published 2026-10-08; never `@latest` in a session holding your identity
export npm_config_ignore_scripts=true       # npx must not run install scripts either
export CF=https://api.cloudflare.com/client/v4
ENV
printf 'export REPO_ROOT=%q\n' "$(git rev-parse --show-toplevel)" >> ~/.batch-a.env   # resolved now, not at source time
chmod 600 ~/.batch-a.env
```

**Owner, before the next block:** open `~/.batch-a.env` in an editor and add one line,
`export CLOUDFLARE_API_TOKEN=<the token>` (24-hour expiry; never paste it into chat).
The agent then continues:

```bash
source ~/.batch-a.env
grep -q '^export CLOUDFLARE_API_TOKEN=.\{20,\}' ~/.batch-a.env || { echo "token not set in ~/.batch-a.env"; exit 1; }
(cd "$REPO_ROOT/jpwolfson-site" && npx --yes "$WRANGLER" whoami)   # run from jpwolfson-site/ (its .npmrc applies); logged in to the account that owns jpwolfson.com
```

Delete `~/.batch-a.env` in step 11.

Create the Cloudflare API token at **My Profile → API Tokens → Create Token → Custom**,
TTL 1 day, permissions:

| Scope | Permission |
|---|---|
| Account → Cloudflare Pages | Edit |
| Account → Workers Scripts | Edit |
| Account → Notifications | Edit |
| Zone → DNS | Edit |
| Zone → Zone Settings | Edit |
| Zone → Transform Rules | Edit |
| Zone → Zone WAF | Read |
| Zone → Zone | Read |
| Zone resources | Include → Specific zone → jpwolfson.com |

Delete the token when the session is finished.

Hardware-key 2FA on GitHub, Cloudflare, and WordPress.com is also the owner's; do it
in the same sitting.

## 1. Baseline snapshot (GitHub)

```bash
source ~/.batch-a.env
gh api repos/$R --jq '{private,default_branch,delete_branch_on_merge,allow_auto_merge,security_and_analysis}'
gh api repos/$R/branches --jq '.[].name'
```

**Owner, UI (R7):** open https://github.com/settings/installations, click the Claude
app, and confirm "Repository access" is *Only select repositories* with
`jpwolfson/jpwolfson-site` alone. (The `/user/installations` API needs a GitHub App
user token, so this cannot be scripted from `gh`.)

## 2. Pre-public gate

```bash
source ~/.batch-a.env
# Scan a mirror so refs/pull/* (which become public too) are included.
MIRROR=$(mktemp -d)/site-mirror.git
git clone --mirror https://github.com/jpwolfson/jpwolfson-site "$MIRROR"
( cd "$MIRROR" && bash "$REPO_ROOT/jpwolfson-site/scripts/ci/gitleaks.sh" )   # must print "no leaks found"
git grep -nIE '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[a-z]{2,}' -- . ':!jpwolfson-site/package-lock.json' | grep -v noreply
```

The second command should show nothing beyond addresses already published on the site.

## 3. Make the repository public and set merge behaviour

```bash
source ~/.batch-a.env
gh api -X PATCH repos/$R -F private=false -F delete_branch_on_merge=true -F allow_auto_merge=true \
  -F allow_squash_merge=true -F allow_merge_commit=false -F allow_rebase_merge=false
gh api repos/$R --jq '{private,delete_branch_on_merge,allow_auto_merge,allow_merge_commit}'
```

Expect `private: false`, merge commits off (linear history).

## 4. Secret scanning, push protection, Dependabot

```bash
source ~/.batch-a.env
gh api -X PATCH repos/$R --input - <<'JSON'
{"security_and_analysis":{"secret_scanning":{"status":"enabled"},"secret_scanning_push_protection":{"status":"enabled"}}}
JSON
gh api -X PUT repos/$R/vulnerability-alerts
gh api -X PUT repos/$R/automated-security-fixes
gh api repos/$R --jq '.security_and_analysis'
gh api repos/$R/vulnerability-alerts && echo "dependabot alerts: on"
```

## 5. Actions permissions (read-only token, trusted actions only)

```bash
source ~/.batch-a.env
gh api -X PUT repos/$R/actions/permissions --input - <<'JSON'
{"enabled":true,"allowed_actions":"selected"}
JSON
gh api -X PUT repos/$R/actions/permissions/selected-actions --input - <<'JSON'
{"github_owned_allowed":true,"verified_allowed":true,"patterns_allowed":[]}
JSON
gh api -X PUT repos/$R/actions/permissions/workflow --input - <<'JSON'
{"default_workflow_permissions":"read","can_approve_pull_request_reviews":false}
JSON
gh api repos/$R/actions/permissions/workflow
gh api repos/$R/actions/secrets --jq '.total_count'      # must be 0
```

## 6. Confirm the hardening PR is merged and deployed

PR #38 (branch `claude/happy-babbage-nioug8`) removed Decap, added the `build` check,
pinned Node, disabled npm scripts, and rewrote the docs. **It was merged on 2026-10-25
02:23 UTC via the GitHub UI**, before this runbook ran, so this step only verifies.
If you are re-running on a later hardening PR, replace the number.

```bash
source ~/.batch-a.env
gh pr view 38 --json state,mergedAt,mergeCommit --jq '{state, mergedAt, merge: .mergeCommit.oid}'   # state MERGED
gh api repos/$R/commits/main/check-runs --jq '.check_runs[] | "\(.name) \(.status) \(.conclusion)"'  # build success, Cloudflare Pages success
```

If a hardening PR is still open instead: `gh pr checks <n> --watch` must be all green and
`gh pr view <n> --json reviews` must show a review from a session other than the author
with no BLOCKING finding (`CLAUDE.md` rule 2); then
`gh pr merge <branch> --squash --delete-branch`.

Confirm production before continuing (Cloudflare Pages builds `main` within minutes):

```bash
curl -sI https://jpwolfson.com/ | grep -iE 'strict-transport|x-frame|content-type-options'
curl -s -o /dev/null -w '%{http_code}\n' https://jpwolfson.com/admin/            # 404
curl -s -o /dev/null -w '%{http_code}\n' https://jpwolfson.com/admin/config.yml  # 404
curl -sI https://jpwolfson.com/files/wolfson-cv.pdf | grep -i content-security-policy
```

If the Pages build failed, read the build log in the dashboard (likely cause: build
command or root directory). Do not change repo files from this session; open an issue.

## 7. Ruleset on `main` (empty bypass list)

```bash
source ~/.batch-a.env
gh api -X POST repos/$R/rulesets --input - <<'JSON'
{
  "name": "main: PR + build check, no history rewrite",
  "target": "branch",
  "enforcement": "active",
  "bypass_actors": [],
  "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
  "rules": [
    {"type": "deletion"},
    {"type": "non_fast_forward"},
    {"type": "required_linear_history"},
    {"type": "pull_request", "parameters": {
        "required_approving_review_count": 0,
        "dismiss_stale_reviews_on_push": false,
        "require_code_owner_review": false,
        "require_last_push_approval": false,
        "required_review_thread_resolution": false}},
    {"type": "required_status_checks", "parameters": {
        "strict_required_status_checks_policy": true,
        "required_status_checks": [{"context": "build", "integration_id": 15368}]}}
  ]
}
JSON
gh api repos/$R/rulesets --jq '.[] | {id,name,enforcement}'
```

`integration_id` 15368 is GitHub Actions (verify with `gh api apps/github-actions --jq .id`);
without it any commit status named `build` would satisfy the rule. The `build` context must have reported at least once (it did, on the PR) or the rule
will block every merge; verify with
`gh api repos/$R/commits/main/check-runs --jq '.check_runs[].name'`.

## 8. Branch hygiene

```bash
source ~/.batch-a.env
git fetch --prune
for b in $(git for-each-ref --format='%(refname:lstrip=3)' --merged origin/main refs/remotes/origin/claude/); do
  git push origin --delete "$b"
done
git for-each-ref --no-merged origin/main refs/remotes/origin/claude/    # anything left here is unmerged: leave it, list it in the log
gh api repos/$R/branches --jq '.[].name'      # main only
```

## 9. Cloudflare: Worker and OAuth remnants

```bash
source ~/.batch-a.env
cd "$REPO_ROOT/jpwolfson-site"
npx --yes "$WRANGLER" deployments list --name jpwolfson-cms-auth   # snapshot for the log (cwd is jpwolfson-site/, see the cd above)
npx --yes "$WRANGLER" delete --name jpwolfson-cms-auth --force
npx --yes "$WRANGLER" deployments list --name jpwolfson-cms-auth   # must error: not found
curl -s -o /dev/null -w '%{http_code}\n' https://jpwolfson-cms-auth.jpwolfson.workers.dev/   # not 200
```

Owner, UI, any time: delete the "Decap CMS" OAuth App at
https://github.com/settings/developers. It is inert once the Worker is gone.

## 10. Cloudflare: zone, Pages, headers, DNS

Resolve identifiers once:

```bash
source ~/.batch-a.env
H="Authorization: Bearer $CLOUDFLARE_API_TOKEN"
ZONE=$(curl -s "$CF/zones?name=jpwolfson.com" -H "$H" | jq -r '.result[0].id')
ACCT=$(curl -s "$CF/zones/$ZONE" -H "$H" | jq -r '.result.account.id')
[ -n "$ZONE" ] && [ "$ZONE" != null ] && [ -n "$ACCT" ] && [ "$ACCT" != null ] || { echo "zone/account lookup failed (token scope?)"; exit 1; }
sed -i.bak '/^export \(H\|ZONE\|ACCT\|P\)=/d' ~/.batch-a.env && rm -f ~/.batch-a.env.bak   # idempotent re-run
printf 'export H=%q\nexport ZONE=%q\nexport ACCT=%q\nexport P=jpwolfson-site\n' "$H" "$ZONE" "$ACCT" >> ~/.batch-a.env
curl -s "$CF/accounts/$ACCT/pages/projects" -H "$H" | jq '.result[] | {name, production_branch, build_config, source: .source.config}'
```

Every 10x block below begins with `source ~/.batch-a.env`; `P` is the Pages project name
(fix it in the env file if the listing shows a different name).

**10a. Pages project.** Record the project name as `P` (expected: `jpwolfson-site`).
Confirm `build_config.root_dir` is `jpwolfson-site` and `destination_dir` is `_site`.

Check for an env var that would override the repo's `.node-version`:

```bash
source ~/.batch-a.env
curl -s "$CF/accounts/$ACCT/pages/projects/$P" -H "$H" | jq '.result.deployment_configs | {production: .production.env_vars, preview: .preview.env_vars}'
```

If `NODE_VERSION` exists in either, it must be removed or set to `22.23.4`
(a PATCH of `deployment_configs.<env>.env_vars` with `{"NODE_VERSION": null}` removes it;
GET again to confirm). Never add new env vars here; Node and `ignore-scripts` are
repo-controlled.

Disable preview deployments (decision Q2). **Always PATCH the whole `source` object**,
never a partial one, or the Git integration can be disconnected:

```bash
source ~/.batch-a.env
curl -s "$CF/accounts/$ACCT/pages/projects/$P" -H "$H" | jq '.result.source' > /tmp/source.json
jq '.config.preview_deployment_setting = "none"' /tmp/source.json > /tmp/source.new.json
diff /tmp/source.json /tmp/source.new.json          # exactly one line should change
curl -s -X PATCH "$CF/accounts/$ACCT/pages/projects/$P" -H "$H" -H 'Content-Type: application/json' \
  --data "{\"source\": $(cat /tmp/source.new.json)}" | jq '.success, .errors'
curl -s "$CF/accounts/$ACCT/pages/projects/$P" -H "$H" | jq '.result.source.config.preview_deployment_setting'
```

**10b. Response-header Transform Rule** (mirrors `_headers` so a merge cannot remove them).

The PUT below **replaces every rule in the phase**. Snapshot first and abort if any
rule already exists that is not ours:

```bash
source ~/.batch-a.env
curl -s "$CF/zones/$ZONE/rulesets/phases/http_response_headers_transform/entrypoint" -H "$H" | jq '.result.rules // []' | tee /tmp/headers-phase-before.json
# Idempotent: the phase may be empty, or hold only our own rule from an earlier run.
jq -e 'length == 0 or (length == 1 and .[0].description == "Security headers (mirror of _headers)")' /tmp/headers-phase-before.json >/dev/null \
  || { echo "phase holds other rules; stop and record them in the log before replacing"; exit 1; }
```

HSTS `includeSubDomains` is only safe if no subdomain is served over plain HTTP.
List DNS records; if every A/AAAA/CNAME is Cloudflare-proxied (`proxied: true`),
you may add `; includeSubDomains` to the HSTS value below and in `src/_headers`
(via a PR); otherwise omit it and note why in the log:

```bash
source ~/.batch-a.env
curl -s "$CF/zones/$ZONE/dns_records?per_page=100" -H "$H" | jq -r '.result[] | select(.type=="A" or .type=="AAAA" or .type=="CNAME") | "\(.name) \(.type) proxied=\(.proxied)"'
```

```bash
source ~/.batch-a.env
curl -s -X PUT "$CF/zones/$ZONE/rulesets/phases/http_response_headers_transform/entrypoint" \
  -H "$H" -H 'Content-Type: application/json' --data @- <<'JSON' | jq '.success, .errors'
{"rules":[{"description":"Security headers (mirror of _headers)","expression":"true","action":"rewrite","action_parameters":{"headers":{
  "Strict-Transport-Security":{"operation":"set","value":"max-age=31536000"},
  "X-Frame-Options":{"operation":"set","value":"DENY"},
  "X-Content-Type-Options":{"operation":"set","value":"nosniff"},
  "Referrer-Policy":{"operation":"set","value":"strict-origin-when-cross-origin"},
  "Permissions-Policy":{"operation":"set","value":"camera=(), microphone=(), geolocation=()"}}}}]}
JSON
curl -sI https://jpwolfson.com/ | grep -iE 'strict-transport|x-frame|nosniff|referrer|permissions'
```

Content-Security-Policy stays in the page `<meta>` for now (decision Q3); adding it
here would need a second rule scoped with `not starts_with(http.request.uri.path, "/files/")`.

**10c. CAA records** (Cloudflare Universal SSL issuers; confirm the current list in
Cloudflare's docs before running):

```bash
source ~/.batch-a.env
for ca in letsencrypt.org pki.goog ssl.com sectigo.com digicert.com; do
  for tag in issue issuewild; do
    curl -s -X POST "$CF/zones/$ZONE/dns_records" -H "$H" -H 'Content-Type: application/json' \
      --data "{\"type\":\"CAA\",\"name\":\"jpwolfson.com\",\"data\":{\"flags\":0,\"tag\":\"$tag\",\"value\":\"$ca\"}}" | jq -c '.success, (.errors[]?.message)'
  done
done
dig +short CAA jpwolfson.com
```

**10d. DNSSEC** (Cloudflare side; the DS record then goes to the registrar):

```bash
source ~/.batch-a.env
curl -s -X PATCH "$CF/zones/$ZONE/dnssec" -H "$H" -H 'Content-Type: application/json' --data '{"status":"active"}' \
  | jq '.result | {status, ds, digest_type, algorithm, key_tag}'
```

Write the DS record into the log. **Owner:** publish it in the WordPress.com domain
panel if the panel supports DS records; if it does not, note that DNSSEC waits for the
registrar transfer (A8) and leave Cloudflare's DNSSEC in "pending" state.

**10e. Notifications:** create an account notification policy for Pages deployment
failures (`alert_type: pages_event_alert`) to the owner's email via
`POST $CF/accounts/$ACCT/alerting/v3/policies`; verify with a GET.

**10f. WAF:** `GET $CF/zones/$ZONE/rulesets/phases/http_request_firewall_managed/entrypoint`
and confirm the Cloudflare Managed Ruleset (free tier) is deployed; if the GET is 404,
deploy it per Cloudflare's documentation.

## 11. Close out

```bash
source ~/.batch-a.env
curl -sI https://jpwolfson.com/ ; curl -s -o /dev/null -w '%{http_code}\n' https://jpwolfson.com/admin/
curl -s https://rdap.verisign.com/com/v1/domain/jpwolfson.com | jq '.secureDNS, .status, [.events[] | select(.eventAction=="expiration") | .eventDate]'
```

Update the status column in `SECURITY.md` for every row marked **pending Batch A**,
add `BATCH-A-LOG.md`, open a PR, let `build` run, have a reviewer session review it,
merge. Then **delete the Cloudflare API token**, `rm ~/.batch-a.env`, and end the session.
