# Batch A — cloud session runbook (Cloudflare half + repo hygiene)

Run this in **one fresh Claude Code cloud session in the dedicated `batch-a-cloudflare`
environment** (never the shared environment; spec R3) after the owner has completed
`BATCH-A-OWNER-CHECKLIST.md` (GitHub clicks) and created that environment with
`CLOUDFLARE_API_TOKEN` as a Network secret and allowed domains `api.cloudflare.com`,
`jpwolfson.com`, `jpwolfson-cms-auth.jpwolfson.workers.dev`, `rdap.verisign.com`.
The environment and the token are deleted by the owner when this session reports done. It is a one-purpose session: do not browse the web, do not read
pages other than the API responses below.

Rules: idempotent steps, in order; each ends with a verification; stop on a failed
verification and report. **Never print, echo, or commit the token.** Shell state does
not persist between Bash calls: every block re-reads `$CLOUDFLARE_API_TOKEN` from the
environment and sources `~/.batch-a.env` for the non-secret values written in step 3.
Record every command and output (token redacted) in
`security-audits/2026-10/BATCH-A-LOG.md` on branch `claude/batch-a-log`, and finish
with a PR per `CLAUDE.md`.

## 0. Preconditions

```bash
[ -n "$CLOUDFLARE_API_TOKEN" ] || { echo "CLOUDFLARE_API_TOKEN not set in this environment"; exit 1; }
CF=https://api.cloudflare.com/client/v4
curl -sS "$CF/user/tokens/verify" -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" | jq '{success, status: .result.status, expires: .result.expires_on}'
```

Expect `success: true`, `status: "active"`. A proxy 403 or DNS failure means the
domain allow-list was not applied: stop and tell the owner which host was refused.

Token scopes the owner was asked to grant (verify failures later map to these):
Account → Cloudflare Pages Edit, Workers Scripts Edit, Notifications Edit;
Zone (jpwolfson.com only) → DNS Edit, Zone Settings Edit, Transform Rules Edit,
Zone WAF Read, Zone Read.

## 1. Confirm the owner's GitHub steps (read-only; the proxy allows GETs)

```bash
R=jpwolfson/jpwolfson-site
curl -sS "https://api.github.com/repos/$R" | jq '{private, delete_branch_on_merge, allow_merge_commit, allow_rebase_merge, allow_squash_merge, security_and_analysis}'
curl -sS "https://api.github.com/repos/$R/rulesets" | jq '.[] | {id, name, enforcement, target}'
```

Required before continuing: `private: false`; `allow_merge_commit: false`;
`allow_rebase_merge: false`; `delete_branch_on_merge: true`;
`security_and_analysis.secret_scanning.status` and
`secret_scanning_push_protection.status` both `enabled` (these two **are** readable
through the proxy; verify them, do not take them on attestation). If `private` is still
`true`, stop: the owner must finish checklist step 1 first. What the proxy refuses even
for GET: `vulnerability-alerts`, `automated-security-fixes`, `actions/permissions*`;
record Dependabot alerts and Actions permissions as "owner-attested" in the log.

Exactly **one active ruleset** must target the default branch: the owner edits the
pre-existing "Protect main" (created 2026-02-22, enforced only since the repo went
public) to the state in `main-ruleset.json`. Select it by its conditions, not by list
position, and assert the rules:

```bash
RS=$(curl -sS "https://api.github.com/repos/jpwolfson/jpwolfson-site/rulesets" | jq -r '[.[] | select(.enforcement=="active" and .target=="branch")] | if length==1 then .[0].id else error("expected exactly 1 active branch ruleset, found \(length)") end')
curl -sS "https://api.github.com/repos/jpwolfson/jpwolfson-site/rulesets/$RS" | jq '{name, bypass_actors, include: .conditions.ref_name.include, rules: [.rules[] | .type], pr: (.rules[] | select(.type=="pull_request") | .parameters | {required_approving_review_count, allowed_merge_methods, require_extra_approval_for_unattributed_changes}), checks: [.rules[] | select(.type=="required_status_checks") | .parameters.required_status_checks[]]}'
```

Required: `bypass_actors: []`; include covers `main` (`refs/heads/main` or
`~DEFAULT_BRANCH`); rules contain `deletion`, `non_fast_forward`,
`required_linear_history`, `pull_request`, `required_status_checks`;
`allowed_merge_methods: ["squash"]`; `require_extra_approval_for_unattributed_changes`
false or absent; checks `[{"context":"build","integration_id":15368}]`. Anything else:
stop and tell the owner which field differs (they fix it in the ruleset editor).

## 2. Start the log and branch

```bash
cd /home/user/jpwolfson-site && git fetch -q origin main && git checkout -q -B claude/batch-a-log origin/main
printf '# Batch A log — %s\n\nCloud session. Token redacted throughout.\n\n' "$(date -u +%FT%TZ)" > security-audits/2026-10/BATCH-A-LOG.md
```

Append to this file after every step (`cat >> …`). Commit at the end.

## 3. Resolve Cloudflare identifiers (non-secret values only go in the env file)

```bash
CF=https://api.cloudflare.com/client/v4; H="Authorization: Bearer $CLOUDFLARE_API_TOKEN"
ZONE=$(curl -sS "$CF/zones?name=jpwolfson.com" -H "$H" | jq -r '.result[0].id')
ACCT=$(curl -sS "$CF/zones/$ZONE" -H "$H" | jq -r '.result.account.id')
[ -n "$ZONE" ] && [ "$ZONE" != null ] && [ -n "$ACCT" ] && [ "$ACCT" != null ] || { echo "zone/account lookup failed (token scope?)"; exit 1; }
printf 'export CF=%q\nexport ZONE=%q\nexport ACCT=%q\nexport P=jpwolfson-site\n' "$CF" "$ZONE" "$ACCT" > ~/.batch-a.env
curl -sS "$CF/accounts/$ACCT/pages/projects" -H "$H" | jq '.result[] | {name, production_branch, build_config, source: .source.config}'
```

`P` is the Pages project name; correct it in `~/.batch-a.env` if the listing differs.
Every block below starts with `source ~/.batch-a.env; H="Authorization: Bearer $CLOUDFLARE_API_TOKEN"`.

## 4. Delete the OAuth Worker

```bash
source ~/.batch-a.env; H="Authorization: Bearer $CLOUDFLARE_API_TOKEN"
curl -sS "$CF/accounts/$ACCT/workers/scripts" -H "$H" | jq '[.result[] | {id, modified_on}]'          # snapshot for the log
curl -sS -X DELETE "$CF/accounts/$ACCT/workers/scripts/jpwolfson-cms-auth?force=true" -H "$H" | jq '{success, errors}'
curl -sS "$CF/accounts/$ACCT/workers/scripts" -H "$H" | jq '[.result[] | .id]'                       # must not list jpwolfson-cms-auth
curl -sS -o /dev/null -w '%{http_code}\n' https://jpwolfson-cms-auth.jpwolfson.workers.dev/         # not 200 (expect 404/530)
```

If the script was already absent, the DELETE returns a "not found" error: that is
success for this step; record it.

## 5. Pages project: Node override check and preview deployments off

```bash
source ~/.batch-a.env; H="Authorization: Bearer $CLOUDFLARE_API_TOKEN"
curl -sS "$CF/accounts/$ACCT/pages/projects/$P" -H "$H" | jq '.result | {build_config, env: {production: .deployment_configs.production.env_vars, preview: .deployment_configs.preview.env_vars}, preview_setting: .source.config.preview_deployment_setting}'
```

`build_config.root_dir` must be `jpwolfson-site` and `destination_dir` `_site`. **Only
if** the GET above shows a `NODE_VERSION` key in an environment's `env_vars`, remove it
from that environment (it would override the repo's `.node-version`); do not PATCH
`deployment_configs` otherwise:

```bash
source ~/.batch-a.env; H="Authorization: Bearer $CLOUDFLARE_API_TOKEN"
for env in production preview; do
  has=$(curl -sS "$CF/accounts/$ACCT/pages/projects/$P" -H "$H" | jq -r ".result.deployment_configs.$env.env_vars.NODE_VERSION // empty")
  [ -z "$has" ] && { echo "$env: no NODE_VERSION override"; continue; }
  curl -sS -X PATCH "$CF/accounts/$ACCT/pages/projects/$P" -H "$H" -H 'Content-Type: application/json' \
    --data "{\"deployment_configs\":{\"$env\":{\"env_vars\":{\"NODE_VERSION\":null}}}}" | jq -c '{success, errors}'
done
```

Disable preview deployments by PATCHing the **whole** `source` object (a partial one can
disconnect the Git integration):

```bash
source ~/.batch-a.env; H="Authorization: Bearer $CLOUDFLARE_API_TOKEN"
curl -sS "$CF/accounts/$ACCT/pages/projects/$P" -H "$H" | jq '.result.source' > /tmp/source.json
jq '.config.preview_deployment_setting = "none"' /tmp/source.json > /tmp/source.new.json
diff /tmp/source.json /tmp/source.new.json || true      # exactly one changed line expected
curl -sS -X PATCH "$CF/accounts/$ACCT/pages/projects/$P" -H "$H" -H 'Content-Type: application/json' \
  --data "{\"source\": $(cat /tmp/source.new.json)}" | jq '{success, errors}'
curl -sS "$CF/accounts/$ACCT/pages/projects/$P" -H "$H" | jq '.result.source.config.preview_deployment_setting'   # "none"
```

## 6. Response-header Transform Rule (mirror of `_headers`, out of reach of a merge)

```bash
source ~/.batch-a.env; H="Authorization: Bearer $CLOUDFLARE_API_TOKEN"
curl -sS "$CF/zones/$ZONE/rulesets/phases/http_response_headers_transform/entrypoint" -H "$H" | jq '.result.rules // []' | tee /tmp/headers-before.json
jq -e 'length == 0 or (length == 1 and .[0].description == "Security headers (mirror of _headers)")' /tmp/headers-before.json >/dev/null \
  || { echo "phase holds other rules; stop and record them before replacing"; exit 1; }
# includeSubDomains is safe only if every A/AAAA/CNAME is Cloudflare-proxied:
curl -sS "$CF/zones/$ZONE/dns_records?per_page=100" -H "$H" | jq -r '.result[] | select(.type=="A" or .type=="AAAA" or .type=="CNAME") | "\(.name) \(.type) proxied=\(.proxied)"'
```

If every listed record shows `proxied=true`, use `max-age=31536000; includeSubDomains`
below and open a one-line PR adding `; includeSubDomains` to `src/_headers`; otherwise
keep `max-age=31536000` and record why.

```bash
source ~/.batch-a.env; H="Authorization: Bearer $CLOUDFLARE_API_TOKEN"
curl -sS -X PUT "$CF/zones/$ZONE/rulesets/phases/http_response_headers_transform/entrypoint" -H "$H" -H 'Content-Type: application/json' --data @- <<'JSON' | jq '{success, errors}'
{"rules":[{"description":"Security headers (mirror of _headers)","expression":"true","action":"rewrite","action_parameters":{"headers":{
  "Strict-Transport-Security":{"operation":"set","value":"max-age=31536000"},
  "X-Frame-Options":{"operation":"set","value":"DENY"},
  "X-Content-Type-Options":{"operation":"set","value":"nosniff"},
  "Referrer-Policy":{"operation":"set","value":"strict-origin-when-cross-origin"},
  "Permissions-Policy":{"operation":"set","value":"camera=(), microphone=(), geolocation=()"}}}}]}
JSON
curl -sI https://jpwolfson.com/ | grep -iE 'strict-transport|x-frame|nosniff|referrer|permissions'
```

CSP stays in the page `<meta>` (decision Q3 open).

## 7. CAA records (idempotent)

CAA restricts which CAs may issue for the whole name. Before adding, review the DNS
listing from step 6: any subdomain hosted by a third party (a CNAME to another provider)
may need that provider's CA added, or the record will block its renewals. Record the
listing and the decision in the log.

```bash
source ~/.batch-a.env; H="Authorization: Bearer $CLOUDFLARE_API_TOKEN"
curl -sS "$CF/zones/$ZONE/dns_records?type=CAA&per_page=100" -H "$H" | jq -r '.result[] | "\(.data.tag) \(.data.value)"' | sort > /tmp/caa-have.txt
for ca in letsencrypt.org pki.goog ssl.com sectigo.com digicert.com; do for tag in issue issuewild; do
  grep -qx "$tag $ca" /tmp/caa-have.txt && continue
  curl -sS -X POST "$CF/zones/$ZONE/dns_records" -H "$H" -H 'Content-Type: application/json' \
    --data "{\"type\":\"CAA\",\"name\":\"jpwolfson.com\",\"data\":{\"flags\":0,\"tag\":\"$tag\",\"value\":\"$ca\"}}" | jq -c '{success, errors: [.errors[]?.message]}'
done; done
curl -sS "$CF/zones/$ZONE/dns_records?type=CAA&per_page=100" -H "$H" | jq -r '.result[] | "\(.data.tag) \(.data.value)"' | sort
```

The issuer list is Cloudflare Universal SSL's CAs; if the API rejects one, record it
and continue.

## 8. DNSSEC (Cloudflare side)

```bash
source ~/.batch-a.env; H="Authorization: Bearer $CLOUDFLARE_API_TOKEN"
curl -sS -X PATCH "$CF/zones/$ZONE/dnssec" -H "$H" -H 'Content-Type: application/json' --data '{"status":"active"}' | jq '.result | {status, ds, digest_type, algorithm, key_tag}'
```

Write the `ds` record into the log under a heading **"DS record for the owner to publish
at WordPress.com"**. Cloudflare will show DNSSEC as pending until the registrar carries
the DS; that is expected.

## 9. Notifications and WAF (best effort)

```bash
source ~/.batch-a.env; H="Authorization: Bearer $CLOUDFLARE_API_TOKEN"
curl -sS "$CF/accounts/$ACCT/alerting/v3/available_alerts" -H "$H" | jq -r '.result | to_entries[] | .value[]? | .type' | grep -i pages
```

Create a policy of the Pages deployment-failure alert type found above, delivering to
the owner's account email (`mechanisms: {"email":[{"id":"<owner email>"}]}`; the email
is on the Cloudflare profile, not in this repo; ask the owner for it if the API needs
it). If the shape is rejected, record the response and leave notifications for the
owner's dashboard; do not loop. **Redact the email address in the log**: the log is
committed to a public repository.

```bash
source ~/.batch-a.env; H="Authorization: Bearer $CLOUDFLARE_API_TOKEN"
curl -sS "$CF/zones/$ZONE/rulesets/phases/http_request_firewall_managed/entrypoint" -H "$H" | jq '{success, rules: [.result.rules[]? | {description, enabled}], errors}'
```

Record whether the Cloudflare Managed Ruleset is deployed; if the GET is a 404, note it
for the owner (deploying it needs Zone WAF Edit, which this token lacks on purpose).

## 10. Repository hygiene (git works through the proxy)

```bash
cd /home/user/jpwolfson-site && git fetch --prune origin
for b in $(git for-each-ref --format='%(refname:lstrip=3)' --merged origin/main refs/remotes/origin/claude/); do
  [ "$b" = "claude/batch-a-log" ] && continue
  git push origin --delete "$b"
done
git for-each-ref --format='%(refname:lstrip=3)' --no-merged origin/main refs/remotes/origin/claude/    # unmerged: leave, list in log
```

## 11. Live verification

```bash
curl -sI https://jpwolfson.com/ | grep -iE 'strict-transport|x-frame|content-type-options|referrer|permissions'
curl -s -o /dev/null -w 'admin %{http_code}\n' https://jpwolfson.com/admin/
curl -s -o /dev/null -w 'config %{http_code}\n' https://jpwolfson.com/admin/config.yml
curl -sI https://jpwolfson.com/files/wolfson-cv.pdf | grep -i content-security-policy
curl -s -o /dev/null -w 'worker %{http_code}\n' https://jpwolfson-cms-auth.jpwolfson.workers.dev/
curl -s https://rdap.verisign.com/com/v1/domain/jpwolfson.com | jq '{status, dnssec: .secureDNS.delegationSigned, expires: [.events[] | select(.eventAction=="expiration") | .eventDate][0]}'
```

Expect: five headers present; `admin 404`; `config 404`; a CSP header on the PDF;
worker not 200; RDAP `delegationSigned` still false until the owner publishes the DS.

## 12. Close out

1. Update `SECURITY.md`: every row marked **pending Batch A** becomes done with the
   evidence (command output summary), or stays pending with the reason (e.g. DS record
   awaiting registrar; notifications left for dashboard).
2. Append a progress-log row to `security-audits/05-REVIEW-WORKFLOW-2026-10.md`.
3. Commit `BATCH-A-LOG.md` + those edits on `claude/batch-a-log`, push, open a PR,
   have a reviewer session that did not author it review the final head, merge when
   `build` is green and the review has no BLOCKING finding (`CLAUDE.md` rule 2; the
   ruleset now enforces the check).
4. Report to the owner: the DS record, anything UNVERIFIED or left for the dashboard,
   and a reminder to **delete the `batch-a-cloudflare` environment and the Cloudflare
   API token** now that the one-session exception to R3 is over.
