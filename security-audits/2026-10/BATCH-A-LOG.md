# Batch A log — 2026-10-25T16:07:45Z

Cloud session. Token redacted throughout.

Session: Claude Code cloud, environment with a proxy-attached Network secret for `api.cloudflare.com`
(no `Authorization` header set by any command below; no token variable read).
Repo attached read+push via the session's GitHub proxy; checkout at `/home/user/jpwolfson-site`,
HEAD `7d2ba98b` (main, "Batch A cloud runbook: Network secret via proxy-attached header; checklist uses the dialog's labels (#44)").

### Amendments made during review (2026-10-25)

The transcript below was first committed at 16:37Z and amended twice after independent review of the PR.
Nothing in the blocks is reconstructed from memory; each amendment is one of:

* **Completed from the session's own command history** (the command was run at the time and its line or
  output had been left out of the log): step 6 (resumed) — the `curl … > /tmp/headers-before.json` read
  that preceded the guard at ~16:24Z (the guard was run on that fresh read, not on the stopped attempt's
  snapshot; the rule it saw was still `b349d6a0…` because the PUT had not happened yet) and the
  `{success, count, total}` DNS line from the same block; step 8 — the jq actually run printed `success`,
  `errors`, `flags` and `public_key`, which had been cut; step 9 — the `-w '\nHTTP %{http_code}\n'` that
  produced `HTTP 404`.
* **Re-run later, marked inline with `# --- re-run <time> ---`**: the three-PDF plain/cache-busted probes
  (16:42Z) and the beacon check and token comparison (16:46Z) in step 11. The original step 11 at ~16:28Z
  probed only `wolfson-cv.pdf`; its two lines are kept above the re-run block.
* **Wording**: the Free-plan remark in step 9 and the cache mechanism in step 11 were tagged UNVERIFIED.

A first version of the beacon check (committed 16:44Z) showed an output line that the command shown could
not have produced; it was a hand-redacted paste. It is replaced by the 16:46Z block, whose output is as
printed.

## 0. Preconditions

```
$ curl -sS "$CF/user/tokens/verify" -H "Accept: application/json" | jq '{success, status: .result.status, expires: .result.expires_on, errors}'
{ "success": true, "status": "active", "expires": "2026-10-26T06:59:59Z", "errors": [] }
```

PASS.

## 1. Owner's GitHub steps

```
$ curl -sS "https://api.github.com/repos/jpwolfson/jpwolfson-site" | jq '{private, delete_branch_on_merge, allow_merge_commit, allow_rebase_merge, allow_squash_merge, security_and_analysis}'
{
  "private": false,
  "delete_branch_on_merge": true,
  "allow_merge_commit": false,
  "allow_rebase_merge": false,
  "allow_squash_merge": true,
  "security_and_analysis": {
    "secret_scanning": { "status": "enabled" },
    "secret_scanning_push_protection": { "status": "enabled" },
    "dependabot_security_updates": { "status": "enabled" },
    "secret_scanning_non_provider_patterns": { "status": "disabled" },
    "secret_scanning_validity_checks": { "status": "disabled" }
  }
}
$ curl -sS ".../rulesets" | jq '.[] | {id, name, enforcement, target}'
{ "id": 13104728, "name": "Protect main", "enforcement": "active", "target": "branch" }
```

Note: the first attempt returned HTTP 403 from the session's GitHub proxy because the repository was
not yet attached to the session; attaching it (read+push) made the GETs succeed. Dependabot alerts and
Actions permissions: not readable through the proxy; **owner-attested** (checklist).

Ruleset 13104728 assertion (the `jq -e` from the runbook):

```
{
  "name": "Protect main",
  "bypass_actors": [],
  "include": [ "refs/heads/main" ],
  "rules": [ "deletion", "non_fast_forward", "pull_request", "required_linear_history", "required_status_checks" ],
  "pr": {
    "required_approving_review_count": 0,
    "dismiss_stale_reviews_on_push": false,
    "required_reviewers": [],
    "require_code_owner_review": false,
    "require_last_push_approval": false,
    "required_review_thread_resolution": false,
    "require_extra_approval_for_unattributed_changes": false,
    "allowed_merge_methods": [ "squash" ]
  },
  "checks": [ { "context": "build", "integration_id": 15368 } ]
}
ruleset OK
```

PASS (include is `refs/heads/main` rather than `~DEFAULT_BRANCH`; both accepted by the assertion).

## 2. Log and branch

`git checkout -B claude/batch-a-log origin/main` → branch `claude/batch-a-log` at `7d2ba98b`.

## 3. Cloudflare identifiers

```
$ ZONE=$(curl -sS "$CF/zones?name=jpwolfson.com" -H "$H" | jq -r '.result[0].id'); ACCT=$(curl -sS "$CF/zones/$ZONE" -H "$H" | jq -r '.result.account.id')
ZONE=42146d780a7f602d0fc9a049530ca6c0 ACCT=997f7641d615545babb5e9bd69e37fe9
$ curl -sS "$CF/accounts/$ACCT/pages/projects" -H "$H" | jq '.result[] | {name, production_branch, build_config, source: .source.config}'
{
  "name": "jpwolfson-site",
  "production_branch": "main",
  "build_config": {
    "build_command": "npx @11ty/eleventy",
    "destination_dir": "_site",
    "root_dir": "jpwolfson-site",
    "web_analytics_tag": "48c7f164eaba418eb311981e2992ff9f",
    "web_analytics_token": "<public beacon token; redacted so the gitleaks generic rule does not fire>"
  },
  "source": {
    "owner": "jpwolfson", "owner_id": "134633122", "repo_name": "jpwolfson-site", "repo_id": "1161366532",
    "production_branch": "main", "pr_comments_enabled": true, "deployments_enabled": true,
    "production_deployments_enabled": true,
    "preview_deployment_setting": "all", "preview_branch_includes": ["*"], "preview_branch_excludes": [],
    "path_includes": ["*"], "path_excludes": []
  }
}
```

PASS. `P=jpwolfson-site` as assumed. (Zone and account IDs are not secrets; the web analytics tag/token
are the public beacon identifiers; step 11 shows the beacon script carrying this token in the served `/` page.)

## 4. Delete the OAuth Worker

```
$ curl -sS "$CF/accounts/$ACCT/workers/scripts" -H "$H" | jq '[.result[] | {id, modified_on}]'
[ { "id": "jpwolfson-cms-auth", "modified_on": "2026-02-22T22:15:36.063107Z" } ]
$ curl -sS -X DELETE "$CF/accounts/$ACCT/workers/scripts/jpwolfson-cms-auth?force=true" -H "$H" | jq '{success, errors}'
{ "success": true, "errors": [] }
$ curl -sS "$CF/accounts/$ACCT/workers/scripts" -H "$H" | jq '[.result[] | .id]'
[]
$ curl -sS -o /dev/null -w '%{http_code}\n' https://jpwolfson-cms-auth.jpwolfson.workers.dev/
404
```

PASS. The account now has zero Worker scripts.

## 5. Pages project: Node override and preview deployments

```
$ curl -sS "$CF/accounts/$ACCT/pages/projects/$P" -H "$H" | jq '.result | {build_config, env: {production: .deployment_configs.production.env_vars, preview: .deployment_configs.preview.env_vars}, preview_setting: .source.config.preview_deployment_setting}'
{
  "build_config": { "build_command": "npx @11ty/eleventy", "destination_dir": "_site", "root_dir": "jpwolfson-site", ... },
  "env": { "production": null, "preview": null },
  "preview_setting": "all"
}
$ for env in production preview; do ... done
production: no NODE_VERSION override
preview: no NODE_VERSION override
```

`root_dir` = `jpwolfson-site`, `destination_dir` = `_site`: PASS. No `NODE_VERSION` in either environment,
so `deployment_configs` was not PATCHed (repo `.node-version` governs).

```
$ curl -sS ".../pages/projects/$P" -H "$H" | jq '.result.source' > /tmp/source.json
$ jq '.config.preview_deployment_setting = "none"' /tmp/source.json > /tmp/source.new.json
$ diff /tmp/source.json /tmp/source.new.json
12c12
<     "preview_deployment_setting": "all",
---
>     "preview_deployment_setting": "none",
$ curl -sS -X PATCH ".../pages/projects/$P" ... --data "{\"source\": $(cat /tmp/source.new.json)}" | jq '{success, errors}'
{ "success": true, "errors": [] }
$ curl -sS ".../pages/projects/$P" -H "$H" | jq '.result.source.config | {preview_deployment_setting, deployments_enabled, production_deployments_enabled, repo_name}'
{ "preview_deployment_setting": "none", "deployments_enabled": true, "production_deployments_enabled": true, "repo_name": "jpwolfson-site" }
```

PASS. Preview deployments disabled; Git integration intact.

## 6. Response-header Transform Rule — STOPPED (verification failed)

```
$ curl -sS "$CF/zones/$ZONE/rulesets/phases/http_response_headers_transform/entrypoint" -H "$H" | jq '.result.rules // []'
[
  {
    "action": "rewrite",
    "action_parameters": {
      "headers": {
        "Permissions-Policy":   { "operation": "set", "value": "camera=(), microphone=(), geolocation=()" },
        "X-Content-Type-Options": { "operation": "set", "value": "nosniff" },
        "X-Frame-Options":      { "operation": "set", "value": "SAMEORIGIN" }
      }
    },
    "description": "Security headers",
    "enabled": true,
    "expression": "true",
    "id": "b349d6a009e140d09aa58d54c90e2fb4",
    "last_updated": "2026-02-22T16:56:19.72809Z",
    "ref": "b349d6a009e140d09aa58d54c90e2fb4",
    "version": "1"
  }
]
$ jq -e 'length == 0 or (length == 1 and .[0].description == "Security headers (mirror of _headers)")' /tmp/headers-before.json
phase holds other rules; stop and record them before replacing
```

**FAIL.** The phase holds one pre-existing rule, description `Security headers` (not the runbook's
`Security headers (mirror of _headers)`), created 2026-02-22. It sets three headers; compared with the
runbook's intended rule it differs in: `X-Frame-Options` is `SAMEORIGIN` (runbook: `DENY`); it has no
`Strict-Transport-Security`; it has no `Referrer-Policy`. It is almost certainly an earlier manual version
of the same control, but the runbook's guard says to stop and record rather than overwrite, so nothing
was PUT. The DNS proxied-status listing (second half of step 6) and steps 7–12 were **not run**.

**Owner decision needed:** confirm that rule `b349d6a009e140d09aa58d54c90e2fb4` may be replaced by the
runbook's rule (the PUT replaces the whole phase). Then re-run from step 6 — either relax the step-6 guard
to also accept description `Security headers`, or delete/rename the old rule in the dashboard first.

## State at stop

| Step | Result |
|---|---|
| 0 token verify | PASS (active, expires 2026-10-26T06:59:59Z) |
| 1 GitHub settings + ruleset | PASS |
| 2 log branch | done |
| 3 Cloudflare IDs | PASS |
| 4 delete OAuth Worker | **done** — `jpwolfson-cms-auth` deleted, workers.dev → 404 |
| 5 Pages: Node override / previews | **done** — no override present; preview deployments set to `none` |
| 6 transform rule | **FAIL (stopped)** — pre-existing rule in phase, see above |
| 7–12 | not run |

Nothing in this log is secret: the token was never visible to the session (proxy-attached header).

## 6 (resumed). Owner decision and Transform Rule replacement

Owner decision (recorded verbatim in intent): the pre-existing rule `b349d6a009e140d09aa58d54c90e2fb4`
("Security headers", 2026-02-22) is an earlier manual version of the same control and may be replaced.
The guard now also accepts a single rule with description `Security headers`. The old rule's full JSON is
recorded above under step 6 (the first, stopped attempt).

```
$ curl -sS "$CF/zones/$ZONE/rulesets/phases/http_response_headers_transform/entrypoint" -H "$H" | jq '.result.rules // []' > /tmp/headers-before.json    # fresh read before the PUT
$ jq -e 'length == 0 or (length == 1 and (.[0].description == "Security headers (mirror of _headers)" or .[0].description == "Security headers"))' /tmp/headers-before.json >/dev/null \
    && echo "guard OK ($(jq -r '.[0].description' /tmp/headers-before.json), id $(jq -r '.[0].id' /tmp/headers-before.json))" || { echo "phase holds other rules"; exit 1; }
guard OK (Security headers, id b349d6a009e140d09aa58d54c90e2fb4)
$ curl -sS "$CF/zones/$ZONE/dns_records?per_page=100" -H "$H" > /tmp/dns.json
$ jq '{success, count: (.result|length), total: .result_info.total_count}' /tmp/dns.json
{ "success": true, "count": 3, "total": 3 }
$ jq -r '.result[] | select(.type=="A" or .type=="AAAA" or .type=="CNAME") | "\(.name) \(.type) \(.content) proxied=\(.proxied)"' /tmp/dns.json
*.jpwolfson.com CNAME jpwolfson.com proxied=true
jpwolfson.com CNAME jpwolfson-site.pages.dev proxied=true
www.jpwolfson.com CNAME jpwolfson.com proxied=true
```

The zone has exactly 3 DNS records (`total_count` 3 above), all CNAME, all `proxied=true`; no
third-party-hosted subdomain. Decision: HSTS `max-age=31536000; includeSubDomains`, and a one-line PR
adding `; includeSubDomains` to `src/_headers` (separate PR; `src/_headers` needs an Opus-class reviewer
per CLAUDE.md rule 9).

```
$ curl -sS -X PUT "$CF/zones/$ZONE/rulesets/phases/http_response_headers_transform/entrypoint" ... --data @- <<'JSON' | jq '{success, errors, rules: [.result.rules[] | {id, description, enabled, headers: (.action_parameters.headers | keys)}]}'
{ "success": true, "errors": [],
  "rules": [ { "id": "d65eb9b5fee843979baccc84d2811a6f", "description": "Security headers (mirror of _headers)", "enabled": true,
               "headers": [ "Permissions-Policy", "Referrer-Policy", "Strict-Transport-Security", "X-Content-Type-Options", "X-Frame-Options" ] } ] }
$ curl -sI https://jpwolfson.com/ | grep -iE 'strict-transport|x-frame|nosniff|referrer|permissions'      # immediately after PUT
x-frame-options: SAMEORIGIN
strict-transport-security: max-age=15552000
permissions-policy: camera=(), microphone=(), geolocation=()
referrer-policy: strict-origin-when-cross-origin
x-content-type-options: nosniff
$ curl -sI "https://jpwolfson.com/?b=$RANDOM" | grep -iE '...'                                              # ~20 s later
x-frame-options: DENY
strict-transport-security: max-age=31536000; includeSubDomains
permissions-policy: camera=(), microphone=(), geolocation=()
referrer-policy: strict-origin-when-cross-origin
x-content-type-options: nosniff
```

PASS. HSTS value deployed: `max-age=31536000; includeSubDomains`. The first probe hit the edge before the
new rule propagated (old XFO `SAMEORIGIN`; the HSTS `max-age=15552000` came from the zone-level HSTS
setting, see below). CSP stays in the page `<meta>` (Q3 open).

Noticed in passing (not changed; runbook does not cover it): the zone setting `security_header` has
Cloudflare's own HSTS enabled with `max_age: 15552000, include_subdomains: false, preload: false`. In the
live response the transform rule's header wins, so this is a dormant inconsistency, not a weakness. Owner
may either disable the zone HSTS toggle (one source of truth: `_headers` + transform rule) or raise it to
match. Noted in SECURITY.md.

```
$ curl -sS "$CF/zones/$ZONE/settings/security_header" -H "$H" | jq '.result.value'
{ "strict_transport_security": { "enabled": true, "max_age": 15552000, "include_subdomains": false, "preload": false, "nosniff": false } }
```

## 7. CAA records

DNS review (from step 6): 3 records, all CNAMEs within the zone or to `jpwolfson-site.pages.dev`, all
proxied. No third-party-hosted subdomain, so no extra CA is needed beyond Cloudflare Universal SSL's.

```
$ curl -sS "$CF/zones/$ZONE/dns_records?type=CAA&per_page=100" -H "$H" | jq -r '.result[] | "\(.data.tag) \(.data.value)"' | sort
(empty — no CAA records existed)
$ for ca in letsencrypt.org pki.goog ssl.com sectigo.com digicert.com; do for tag in issue issuewild; do ... POST ... done; done
issue letsencrypt.org: {"success":true,"errors":[]}
issuewild letsencrypt.org: {"success":true,"errors":[]}
issue pki.goog: {"success":true,"errors":[]}
issuewild pki.goog: {"success":true,"errors":[]}
issue ssl.com: {"success":true,"errors":[]}
issuewild ssl.com: {"success":true,"errors":[]}
issue sectigo.com: {"success":true,"errors":[]}
issuewild sectigo.com: {"success":true,"errors":[]}
issue digicert.com: {"success":true,"errors":[]}
issuewild digicert.com: {"success":true,"errors":[]}
$ curl -sS ".../dns_records?type=CAA&per_page=100" ... | sort
issue digicert.com
issue letsencrypt.org
issue pki.goog
issue sectigo.com
issue ssl.com
issuewild digicert.com
issuewild letsencrypt.org
issuewild pki.goog
issuewild sectigo.com
issuewild ssl.com
```

PASS. 10 CAA records on `jpwolfson.com` (issue + issuewild for each of the 5 Universal SSL CAs); none rejected.

## 8. DNSSEC (Cloudflare side)

```
$ curl -sS -X PATCH "$CF/zones/$ZONE/dnssec" -H "$H" -H 'Content-Type: application/json' --data '{"status":"active"}' | jq '{success, errors, result: (.result | {status, ds, digest_type, algorithm, key_tag, flags, public_key})}'
{
  "success": true,
  "errors": [],
  "result": {
    "status": "pending",
    "ds": "jpwolfson.com. 3600 IN DS 2371 13 2 835936523FFDD7AC3B4D5E414FD8349575A1EA6F3AD63D15EF661FF7DD22ABD7",
    "digest_type": "2",
    "algorithm": "13",
    "key_tag": 2371,
    "flags": 257,
    "public_key": "mdsswUyr3DPW132mOi8V9xESWE8jTo0dxCjjnopKl+GqJxpVXckHAeF+KkxLbxILfDLUT0rAK9iUzy1L53eKGQ=="
  }
}
```

PASS (status `pending` is expected until the registrar carries the DS).

### DS record for the owner to publish at WordPress.com

```
jpwolfson.com. 3600 IN DS 2371 13 2 835936523FFDD7AC3B4D5E414FD8349575A1EA6F3AD63D15EF661FF7DD22ABD7
```

| Field | Value |
|---|---|
| Key tag | 2371 |
| Algorithm | 13 (ECDSAP256SHA256) |
| Digest type | 2 (SHA-256) |
| Digest | `835936523FFDD7AC3B4D5E414FD8349575A1EA6F3AD63D15EF661FF7DD22ABD7` |
| Public key (if the registrar form asks) | `mdsswUyr3DPW132mOi8V9xESWE8jTo0dxCjjnopKl+GqJxpVXckHAeF+KkxLbxILfDLUT0rAK9iUzy1L53eKGQ==` (flags 257) |

## 9. Notifications and WAF (best effort)

```
$ curl -sS "$CF/accounts/$ACCT/alerting/v3/available_alerts" -H "$H" | jq -r '.result | to_entries[] | .value[]? | .type' | grep -i pages
pages_event_alert        # filter_options: project_id, environment, event
$ curl -sS "$CF/accounts/$ACCT/alerting/v3/policies" -H "$H" | jq '[.result[]?]'
[]                       # no policies existed
$ curl -sS "$CF/user" -H "$H" | jq '{success, errors: [.errors[]?.message]}'
{ "success": false, "errors": [ "Unauthorized to access requested resource" ] }   # token cannot read the profile email; owner supplied it in session
$ curl -sS -X POST ".../alerting/v3/policies" ... --data '{"name":"Pages deployment failed (jpwolfson-site)","alert_type":"pages_event_alert","enabled":true,"mechanisms":{"email":[{"id":"<owner email>"}]},"filters":{"project_id":["jpwolfson-site"],"environment":["ENVIRONMENT_PRODUCTION"],"event":["EVENT_DEPLOYMENT_FAILED"]}}'
{ "success": false, "errors": [ { "message": "invalid conditionsHandler \"pages_event_alert_validator\" parameter \"project_id\": \"expected project_id[0] to be a uuid: jpwolfson-site\"" } ] }
$ PID=$(curl -sS ".../pages/projects/$P" -H "$H" | jq -r '.result.id')      # 04fddd5f-060d-4df2-8cf1-6803440a9fa6
$ curl -sS -X POST ".../alerting/v3/policies" ... (same body, project_id=[$PID])
{ "success": true, "errors": [], "id": "0cf4b425c95744f8ab5b9f7b7e7ae0ad" }
$ curl -sS ".../alerting/v3/policies" -H "$H" | jq '[.result[]? | {id, name, alert_type, enabled, filters, mechanisms}]'
[ { "id": "0cf4b425c95744f8ab5b9f7b7e7ae0ad", "name": "Pages deployment failed (jpwolfson-site)", "alert_type": "pages_event_alert", "enabled": true,
    "filters": { "environment": ["ENVIRONMENT_PRODUCTION"], "event": ["EVENT_DEPLOYMENT_FAILED"], "project_id": ["04fddd5f-060d-4df2-8cf1-6803440a9fa6"] },
    "mechanisms": { "email": [ { "id": "<owner email>" } ] } } ]
```

PASS after one corrected retry (the API wants the Pages project UUID, not its name, in `project_id`;
the runbook's `mechanisms` shape was accepted). Email address redacted; it is the owner's Cloudflare
account email, supplied in-session.

```
$ curl -sS -w '\nHTTP %{http_code}\n' "$CF/zones/$ZONE/rulesets/phases/http_request_firewall_managed/entrypoint" -H "$H"
{ "result": null, "success": false, "errors": [ { "code": 10003, "message": "could not find entrypoint ruleset in the http_request_firewall_managed phase" } ] }
HTTP 404
```

**Cloudflare Managed Ruleset is NOT deployed** on the zone (no entrypoint in the managed-WAF phase).
Deploying it needs Zone WAF Edit, which this token lacks on purpose: **owner action** in the dashboard
(Security → WAF → Managed rules → deploy "Cloudflare Managed Ruleset"). UNVERIFIED (not checked from
this session; no web reading): whether the zone is on the Free plan, and whether on Free the automatically
applied "Free Managed Ruleset" is absent from this phase, which would make the 404 expected rather than a gap.

## 10. Repository hygiene (read-only)

The runbook's `--merged` test is meaningless from a depth-1 clone (everything shows unmerged); the
history was deepened first (`git fetch --depth=1000 origin main` → 139 commits; branch tips fetched).

```
$ git fetch --prune origin
$ git for-each-ref --format='%(refname:lstrip=3)' --merged origin/main refs/remotes/origin/claude/ | grep -v '^claude/batch-a-log$'
merged into main (owner deletes these at /branches/stale):
claude/build-cms-admin-backend-86Vvk
claude/elegant-ritchie-iga5C
claude/fix-broken-links-5cYDk
claude/migrate-wordpress-cloudflare-8eo4d
claude/phase-2-code-quality-review-d4t0j
claude/rebuild-professional-website-QCYMI
claude/review-project-structure-hL8jl
claude/security-audit-phase-1-Z6xKQ
claude/security-audit-phase-2-N4Ln3
claude/security-audit-remediation-nb6lR
claude/security-audit-remediation-oQhc2
claude/security-audit-signoff-EtElt
claude/security-audit-workflow-Bz1cO
claude/website-link-validator-IJDSg
$ git for-each-ref --format='%(refname:lstrip=3)' --no-merged origin/main refs/remotes/origin/claude/
NOT merged (leave alone, list in the log):
claude/batch-a-log
```

All 14 stale branches are 0 commits ahead of `main` (tips dated 2026-02-19..26; `git rev-list --left-right
--count origin/main...origin/<b>` = N/0 for each). Safe for the owner to delete at
https://github.com/jpwolfson/jpwolfson-site/branches/stale. Caveat for the future: `main` is now
squash-only, so `--merged` will not detect branches merged from here on; `delete_branch_on_merge` handles those.

## 11. Live verification

```
$ curl -sI https://jpwolfson.com/ | grep -iE 'strict-transport|x-frame|content-type-options|referrer|permissions'
x-frame-options: DENY
strict-transport-security: max-age=31536000; includeSubDomains
permissions-policy: camera=(), microphone=(), geolocation=()
referrer-policy: strict-origin-when-cross-origin
x-content-type-options: nosniff
$ curl -s -o /dev/null -w 'admin %{http_code}\n' https://jpwolfson.com/admin/
admin 404
$ curl -s -o /dev/null -w 'config %{http_code}\n' https://jpwolfson.com/admin/config.yml
config 404
$ curl -sI https://jpwolfson.com/files/wolfson-cv.pdf | grep -i content-security-policy
(no output)
# --- re-run 2026-10-25T16:42Z (after the first review; see Amendments) ---
$ for f in wolfson-cv.pdf 'Lecture%201%20-%20Topological%20Data%20Analysis.pdf' 'Batson%20-%20How%20to%20See%20a%20Meromorphic%201-Form.pdf'; do
    echo "== /files/$f (plain)";        curl -sI "https://jpwolfson.com/files/$f" | grep -iE '^HTTP/2|content-security-policy|cf-cache-status|cache-control'
    echo "== /files/$f (cache-busted)"; curl -sI "https://jpwolfson.com/files/$f?v=$RANDOM$RANDOM" | grep -iE '^HTTP/2|content-security-policy|cf-cache-status'
  done
== /files/wolfson-cv.pdf (plain)
HTTP/2 200
cache-control: public, max-age=14400, must-revalidate
cf-cache-status: REVALIDATED
== /files/wolfson-cv.pdf (cache-busted)
HTTP/2 200
content-security-policy: default-src 'none'
cf-cache-status: MISS
== /files/Lecture%201%20-%20Topological%20Data%20Analysis.pdf (plain)
HTTP/2 200
cache-control: public, max-age=14400, must-revalidate
cf-cache-status: REVALIDATED
== /files/Lecture%201%20-%20Topological%20Data%20Analysis.pdf (cache-busted)
HTTP/2 200
content-security-policy: default-src 'none'
cf-cache-status: MISS
== /files/Batson%20-%20How%20to%20See%20a%20Meromorphic%201-Form.pdf (plain)
HTTP/2 200
cache-control: public, max-age=14400, must-revalidate
cf-cache-status: REVALIDATED
== /files/Batson%20-%20How%20to%20See%20a%20Meromorphic%201-Form.pdf (cache-busted)
HTTP/2 200
content-security-policy: default-src 'none'
cf-cache-status: MISS
# --- re-run 2026-10-25T16:46Z (after the second review; see Amendments) ---
$ curl -s https://jpwolfson.com/ | grep -c 'cloudflareinsights.com/beacon'
1
$ curl -s https://jpwolfson.com/ | grep -o 'data-cf-beacon=[^>]*' | sed -E 's/"token": "[a-f0-9]{32}"/"token": "<32-hex token>"/'
data-cf-beacon='{"token": "<32-hex token>"}'
$ served=$(curl -s https://jpwolfson.com/ | grep -oE '"token": "[a-f0-9]{32}"' | grep -oE '[a-f0-9]{32}')
$ pages=$(curl -sS "$CF/accounts/$ACCT/pages/projects/$P" -H "$H" | jq -r '.result.build_config.web_analytics_token')
$ [ -n "$served" ] && [ "$served" = "$pages" ] && echo "served beacon token == Pages build_config.web_analytics_token (32 hex chars, not printed)" || echo "MISMATCH or empty"
served beacon token == Pages build_config.web_analytics_token (32 hex chars, not printed)
$ curl -s -o /dev/null -w 'worker %{http_code}\n' https://jpwolfson-cms-auth.jpwolfson.workers.dev/
worker 404
$ curl -s https://rdap.verisign.com/com/v1/domain/jpwolfson.com | jq '{status, dnssec: .secureDNS.delegationSigned, expires: ...}'
{ "status": [ "client transfer prohibited" ], "dnssec": false, "expires": "2026-11-30T02:37:47Z" }
```

PASS with one caveat. Five headers present; `/admin/` and `/admin/config.yml` 404; Worker 404; RDAP
`delegationSigned: false` (expected until the DS is published); expiry 2026-11-30 and transfer lock
unchanged. **Caveat:** for all three PDFs under `/files/`, the plain URL is answered from the edge cache
(`cf-cache-status: REVALIDATED`) **without** a CSP header, while a cache-busted URL goes to the origin
(`MISS`) and carries `content-security-policy: default-src 'none'`. So the `_headers` rule is deployed
but the cached objects do not yet reflect it. Inferred, UNVERIFIED mechanism: the cached entries predate
today's `_headers` deploy (commit e248914) and a 304 on revalidation keeps the cached headers. **Owner
action:** purge the cache for `/files/*` (Caching → Configuration → Purge by URL/prefix); this token has no
Cache Purge scope, on purpose. The beacon lines show the Cloudflare Web Analytics script in the served
page and that its token equals the Pages `web_analytics_token` redacted in step 3 (compared in the shell,
neither value printed).

## 12. Close-out

| Step | Result |
|---|---|
| 0 token verify | PASS |
| 1 GitHub settings + ruleset 13104728 | PASS (API-verified) |
| 3 Cloudflare IDs | PASS |
| 4 Worker `jpwolfson-cms-auth` | deleted; workers.dev 404 |
| 5 Pages | no `NODE_VERSION` override; previews `none`; Git integration intact |
| 6 Transform Rule | replaced (old Feb rule superseded on owner decision); 5 headers live; HSTS with `includeSubDomains` |
| 7 CAA | 10 records created |
| 8 DNSSEC | enabled at Cloudflare, `pending`; DS record above |
| 9 Notifications / WAF | alert policy `0cf4b425…` created; managed-WAF phase 404 (not deployed) |
| 10 Stale branches | 14 confirmed merged; owner deletes |
| 11 Live | PASS; `/files/*` edge cache needs owner purge |

CI note: the first push of this log failed the `build` check's full-history gitleaks step (rule
`generic-api-key`) on the Pages `web_analytics_token` value printed in step 3. It is the public beacon token
present in the served page (step 11), not a credential, but the scan is the control; the value was redacted and the
branch squashed to one commit so the string is not in history. Because the scan runs with `--all` on a
full checkout, it also failed the unrelated `_headers` PR until this branch was rewritten.

Edits in this PR besides the log: `SECURITY.md` (pending-Batch-A rows resolved), progress row in
`security-audits/05-REVIEW-WORKFLOW-2026-10.md`, runbook step 6 guard accepts either rule description,
runbook step 10 points at `/branches/stale`. Separate one-line PR: `; includeSubDomains` in `src/_headers`.

### Owner actions remaining

1. Publish the DS record (step 8) at WordPress.com; Cloudflare DNSSEC turns `active` afterwards.
2. Purge the Cloudflare cache for `https://jpwolfson.com/files/*` (stale PDF cache entries lack the CSP header).
3. Deploy the Cloudflare Managed WAF ruleset from the dashboard if the plan offers it (token lacked Zone WAF Edit on purpose).
4. Delete the 14 merged `claude/*` branches at `/branches/stale`.
5. Optionally disable the redundant zone-level HSTS toggle (max-age 15552000) so the Transform Rule is the single source.
6. Delete the `batch-a-cloudflare` environment's Network secret, then the environment, then the Cloudflare API token (expires 2026-10-26T06:59:59Z regardless).
7. GitHub OAuth App deletion (H4) when convenient.
