# Security — jpwolfson.com

Last full review: 2026-10-25 (workflow: `security-audits/05-REVIEW-WORKFLOW-2026-10.md`).
Prior audit history: `security-audits/00`–`04` (February 2026). Several conclusions in
those reports were later found to be wrong; treat them as history, not as a description
of the current system.

## What this site is

Static HTML and PDFs, built by Eleventy, deployed by Cloudflare Pages from `main`,
served behind Cloudflare. There is no CMS, no OAuth flow, no Worker, no server-side
code, no database, no form, and no credential anywhere in the repository or its CI.
Decap CMS and its OAuth Worker were removed in October 2026.

```
 GitHub repo (public since 2026-10-25) ──push──▶  Cloudflare Pages build  ──▶  jpwolfson.com
   agents open PRs                        .node-version pins Node       _headers + CSP
   `build` check required                 .npmrc ignore-scripts         /files/* locked down
   ruleset: no force-push,                npm ci from lockfile
            no deletion, PR only
```

## Controls

| Control | Where | Status |
|---|---|---|
| No dynamic surface: no `/admin/`, no Worker, no OAuth App | repo (removed) + Cloudflare (Worker deleted) | done 2026-10-25: Worker `jpwolfson-cms-auth` deleted via API (script list empty; `workers.dev` URL 404; `/admin/` 404). GitHub OAuth App deletion remains owner step H4 (inert without the Worker) |
| Content Security Policy on every page: hash-allow-listed inline scripts only, `base-uri 'self'`, `form-action 'none'`, `object-src 'none'`, `frame-src` limited to Vimeo/YouTube | `src/_includes/base.njk`; verified by `scripts/ci/check-csp.py` | done |
| HTTP headers: `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy`, `Permissions-Policy`, HSTS | `src/_headers` + Cloudflare Transform Rule "Security headers (mirror of _headers)" | done 2026-10-25: Transform Rule deployed and live (`curl -sI https://jpwolfson.com/` shows all five; HSTS `max-age=31536000; includeSubDomains`, all DNS records proxied). Cloudflare's zone-level HSTS toggle is also on (`max_age 15552000`, no `includeSubDomains`); it was what the edge sent before the rule existed, so if the rule were ever removed it, not `_headers`, would decide HSTS. Owner may disable it |
| `/files/*` served with `Content-Security-Policy: default-src 'none'`; only PDF/PNG/JPG under 25 MB may be committed there, content-sniffed | `src/_headers`; `scripts/ci/check-files.sh` | deployed, **not yet served on the plain URLs**: 2026-10-25 cache-busted fetches of all three PDFs return the header (`cf-cache-status: MISS`), while the plain URLs are answered from edge cache entries that lack it (`REVALIDATED`, no CSP; presumed to predate the deploy). Owner purges `/files/*`; evidence in `BATCH-A-LOG.md` step 11 |
| Subresource Integrity + exact version pin on MathJax; CI re-downloads and compares | `base.njk`; `scripts/ci/check-sri.sh` | done |
| npm lifecycle scripts disabled everywhere (Pages, CI, local) | `jpwolfson-site/.npmrc` | done |
| Node pinned at or above the CVE-2026-111497 fix | `jpwolfson-site/.node-version` | done |
| Lockfile-only installs; `npm audit` fails CI on high/critical; registry signature check | `build.yml` | done |
| Dependabot with 7-day cooldown for npm, pip, GitHub Actions | `.github/dependabot.yml` | done (API 2026-10-25: `dependabot_security_updates.status: enabled`; the alerts toggle is not readable through the proxy, owner-attested) |
| Full-history secret scan with checksum-pinned gitleaks on every PR | `scripts/ci/gitleaks.sh` | done |
| HTML validation; file-level invariants (404 present, no `/admin/`, output limited to html/css/pdf/png/jpg); DOM invariants parsed with `html.parser` (one canonical CSP per page, exactly the two known inline hashes, only the MathJax scripts, iframes on allowed hosts, no `<base>`/`<object>`/`<embed>`/`<form>`/inline handlers) | `build.yml`, `scripts/ci/check-output.sh`, `scripts/ci/check-csp.py` | done |
| All GitHub Actions pinned to commit SHAs; least privilege (`build`: `contents: read`; link audit adds `issues: write` for the tracking issue); no repository secrets | `.github/workflows/*` | done |
| Ruleset on `main`: PR required, `build` required, no force-push, no deletion, linear history, **empty bypass list** | GitHub settings | done 2026-10-25: ruleset 13104728 "Protect main" API-verified against `security-audits/2026-10/main-ruleset.json` (empty bypass, five rules, squash-only, 0 approvals, required check `build`) |
| Actions: default token read-only; only GitHub-owned and verified actions | GitHub settings | owner-attested 2026-10-25 (checklist step; not readable through the proxy) |
| Secret scanning + push protection | GitHub settings (public repo) | done 2026-10-25 (API: both `enabled`) |
| DNSSEC, CAA records, Pages preview deployments disabled or gated | Cloudflare + registrar | CAA (issue + issuewild for the five Universal SSL CAs) and previews `none`: done 2026-10-25. DNSSEC enabled at Cloudflare, **pending** the owner publishing the DS record at WordPress.com (record in `BATCH-A-LOG.md` step 8) |
| Hardware-key 2FA on GitHub, Cloudflare, WordPress.com (registrar) | accounts | **owner** |
| External change monitor outside this repo's CI | owner-controlled service | **pending Batch C** |

Batch A was executed on 2026-10-25: the GitHub half by the owner
(`security-audits/2026-10/BATCH-A-OWNER-CHECKLIST.md`), the Cloudflare half by a one-purpose cloud
session (`BATCH-A-CLOUD-RUNBOOK.md`); every command and output is in `BATCH-A-LOG.md`. Done there beyond the table: Pages
deployment-failure email alert. Still open from it, all owner: publish the DS record at the registrar;
purge the edge cache for `/files/*`; deploy the Cloudflare Managed WAF ruleset if the plan offers it (the
managed-WAF phase returned 404; the token lacked Zone WAF Edit); delete the 14 merged `claude/*` branches;
optionally disable the zone-level HSTS toggle; delete the GitHub OAuth App (H4).

## Agent governance

Agents author, review, and merge without a human. The rules are in `CLAUDE.md`.
The safety argument: the worst a hijacked agent can do is deface the site or abuse
CI minutes, because (a) the ruleset forbids history rewriting, (b) CI holds no
credentials and its token is read-only, (c) no agent holds a Cloudflare write
credential, (d) the HTTP security headers are mirrored at Cloudflare where a merge cannot
touch them (done 2026-10-25; the CSP itself still lives in the page `<meta>` and is
not yet mirrored, decision Q3), and (e) sessions that read the open web do not hold merge rights.
Recovery from a bad merge is `git revert` plus a Pages redeploy.

## Maintenance

| Task | How |
|---|---|
| Update MathJax | Change the version in `base.njk`, run `bash scripts/ci/check-sri.sh`, paste the hash it prints. |
| Edit the inline MathJax config | Run `python3 scripts/ci/check-csp.py` after building; paste the new `sha256-…` into the CSP meta and the comment. |
| Cloudflare analytics beacon hash goes stale | Symptom: CSP error in DevTools naming `cloudflareinsights`. Replace the second hash in `script-src` with the one shown. |
| Bump Node | Edit `.node-version`; Pages and CI both read it. |
| Dependencies | Dependabot opens PRs after a 7-day cooldown; `build` must pass; an agent reviews and merges. |
| Add a file to `/files/` | PDF/PNG/JPG only, under 25 MB, hyphenated lowercase name. CI enforces. |

## Periodic checks

| Check | Cadence | Mechanism |
|---|---|---|
| Build, audit, CSP, SRI, files, secrets | every PR and push to `main` | `build.yml` |
| External links | weekly | `link-audit.yml` opens or updates an issue |
| Live headers, `/admin/` 404, Worker gone | after Batch A, then via external monitor | `curl -sI https://jpwolfson.com/` |
| Domain: expiry 2026-11-30 (auto-renew: owner-stated 2026-10-25, recorded in the review workflow progress log, not independently verified; A8), transfer lock, DNSSEC | quarterly | `curl -s https://rdap.verisign.com/com/v1/domain/jpwolfson.com` |
| Full review | 6 months, or on any Node/npm/Cloudflare advisory touching the build | this workflow |

## Accepted risks

| Risk | Why accepted |
|---|---|
| `'unsafe-inline'` in `style-src` | MathJax injects inline styles. Styles cannot execute script; `script-src` is hash-only. |
| `img-src https:` | Academic content may embed external images. Pages carry no tokens, so image-request exfiltration has nothing to carry. |
| Raw HTML enabled in Markdown (`html: true`) | Needed for video embeds and section labels. Compensated by `base-uri`, `form-action`, `object-src`, `frame-src`, and the `/files/*` allow-list. Only PR authors can write content, and merges are recoverable. |
| Cloudflare Web Analytics beacon without SRI | Injected at the edge by the hosting provider; the trust boundary is Cloudflare itself. |
| MathJax served from jsdelivr | Pinned version + SRI; CI detects drift. Self-hosting is an open option (review workflow Q4). |
| Claude GitHub App installed on more than this repository | Owner's choice (2026-10-25): the app is used on other repositories. A hijacked session here could reach them through the same installation. Compensating controls: the ruleset and no-secrets CI bound what a session can do *to this repo*; nothing here bounds the others. |
| Public repository (done 2026-10-25) | Required for free branch protection and secret scanning. Content is public anyway; history was secret-scanned clean (every PR; one mirror scan including PR refs). |
| `/files/*` CSP omits `sandbox` | Spec B4 proposed `default-src 'none'; sandbox`. `sandbox` breaks Chrome's built-in PDF viewer, so only `default-src 'none'` is set; the primary control is the CI allow-list that keeps non-PDF/image files out of `src/files/`. |

## Incident runbook

- **Bad merge (defacement, hostile file, broken build):** `git revert` the merge on a
  branch, open a PR, merge when `build` is green; Pages redeploys. If Pages is serving
  a bad build, roll back to the previous deployment in the Cloudflare dashboard.
- **Suspected agent compromise:** revoke the Claude GitHub App installation for the
  repo (GitHub → Settings → Applications), audit `git log main` since last known-good,
  revert as above, then re-install.
- **Lost GitHub account:** the Cloudflare Pages deployment keeps serving the last build
  indefinitely. Recover the account; the repo is public and clonable; a `git bundle`
  backup should exist outside GitHub (Batch C).
- **Lost Cloudflare account:** DNS and hosting go with it. Registrar access (WordPress.com)
  lets you repoint nameservers to a new host; the repo rebuilds anywhere Eleventy runs.
- **Lost registrar account:** everything depends on it. Hardware 2FA and the transfer
  lock are the controls; Automattic support is the recovery path.
- **Node/npm/Cloudflare advisory:** check `.node-version`, run `npm audit`, read
  Dependabot alerts; for a runtime CVE, bump `.node-version` and merge.

## Reporting

Security contact: the repository owner via GitHub issues (once the repository is public),
or the email address on the site.
