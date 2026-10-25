# Batch A — owner checklist (Option A: browser clicks + cloud session)

The cloud sandbox cannot write GitHub repository settings (Anthropic's proxy blocks
those API paths regardless of credential, verified 2026-10-25), so the GitHub half of
Batch A is a short click list for the owner. The Cloudflare half runs in a cloud
session (`BATCH-A-CLOUD-RUNBOOK.md`). Nothing here is a terminal command.

## GitHub — https://github.com/jpwolfson/jpwolfson-site/settings — in this order

| # | Where | Do | Why |
|---|---|---|---|
| 1 | General → Danger Zone → Change repository visibility | **Make public**; type the repo name to confirm | Unlocks rulesets and free secret scanning (A0). History scanned clean three times incl. PR refs. |
| 2 | General → Pull Requests | Untick *Allow merge commits* and *Allow rebase merging*; keep *Allow squash merging*; tick *Automatically delete head branches* | Linear history; no stale branches |
| 3 | Code security (and analysis) | Turn on *Dependabot alerts*, *Dependabot security updates*, *Secret scanning* / *Secret Protection*, *Push protection* | A5 |
| 4 | Actions → General | *Actions permissions*: "Allow jpwolfson, and select non-jpwolfson, actions and reusable workflows" + tick *Allow actions created by GitHub* and *Allow actions by Marketplace verified creators*. *Workflow permissions*: "Read repository contents and packages permissions"; untick *Allow GitHub Actions to create and approve pull requests*. Save. | R2 |
| 5 | Rules → Rulesets → New ruleset ▾ → **Import a ruleset** | Upload `security-audits/2026-10/main-ruleset.json` from this repo (Raw → save file). Confirm it shows: target default branch, Active, bypass list empty, rules: restrict deletions, block force pushes, require linear history, require pull request (0 approvals, squash only), require status check `build` (GitHub Actions). Create. | R1. Do this **after** 1 (needs public). |
| 6 | https://github.com/settings/installations → Claude → Configure | *Only select repositories* → `jpwolfson-site` only | R7 |
| 7 | https://github.com/settings/developers → OAuth Apps | Delete the Decap CMS OAuth App | A4 (inert once the Worker is gone) |

After step 5, a push that is not a PR, a force-push, or a merge without a green `build`
is refused for everyone, including the owner. Content edits go through PRs (agents open
and merge them).

## Claude cloud environment — environment menu in the session title bar → Edit

| Setting | Value |
|---|---|
| Network access → Allowed domains (keep *Allow package managers* ticked) | `api.cloudflare.com`, `jpwolfson.com`, `jpwolfson-cms-auth.jpwolfson.workers.dev`, `rdap.verisign.com` |
| Network secrets | `CLOUDFLARE_API_TOKEN` = the 24-hour token (scopes in `BATCH-A-CLOUD-RUNBOOK.md` §0) |

Then start a **new** cloud session on this repository (new sessions pick up the settings)
and give it:

```
Execute security-audits/2026-10/BATCH-A-CLOUD-RUNBOOK.md from main, in order, stopping at any failed verification. Do not browse the web.
```

## Afterwards (owner, any time)

- Publish the DS record the cloud session reports at WordPress.com → Domains → jpwolfson.com → DNSSEC (if the panel offers it; otherwise it waits for the registrar transfer, A8).
- Delete the Cloudflare API token (My Profile → API Tokens → ⋯ → Delete) and remove the Network secret from the environment.
- Hardware-key 2FA on GitHub, Cloudflare, WordPress.com: done 2026-10-25.
