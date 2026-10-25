# Batch A — owner checklist (Option A: browser clicks + cloud session)

The cloud sandbox cannot write GitHub repository settings (Anthropic's proxy blocks
those API paths regardless of credential, verified 2026-10-25), so the GitHub half of
Batch A is a short click list for the owner. The Cloudflare half runs in a cloud
session (`BATCH-A-CLOUD-RUNBOOK.md`). Nothing here is a terminal command.

## GitHub — https://github.com/jpwolfson/jpwolfson-site/settings — in this order

| # | Where | Do | Why |
|---|---|---|---|
| 1 | General → Danger Zone → Change repository visibility | **Make public**; type the repo name to confirm | Unlocks rulesets and free secret scanning (A0). History scanned clean (gitleaks on every PR; one mirror scan including PR refs). **Done 2026-10-25.** |
| 2 | General → Pull Requests | Untick *Allow merge commits* and *Allow rebase merging*; keep *Allow squash merging*; tick *Automatically delete head branches* | Linear history; no stale branches. **Done 2026-10-25 (API-verified).** |
| 3 | https://github.com/jpwolfson/jpwolfson-site/settings/security_analysis | Turn on *Dependabot alerts*, *Dependabot security updates*, and under **Secret Protection**: *Secret scanning* then *Push protection* | A5. **Owner reports done 2026-10-25;** the cloud runbook verifies secret scanning/push protection from the API. |
| 4 | https://github.com/jpwolfson/jpwolfson-site/settings/actions | *Actions permissions*: "Allow jpwolfson, and select non-jpwolfson, actions and reusable workflows" + tick *Allow actions created by GitHub* and *Allow actions by Marketplace verified creators*. *Workflow permissions*: "Read repository contents and packages permissions"; untick *Allow GitHub Actions to create and approve pull requests*. Save. | R2 |
| 5 | https://github.com/jpwolfson/jpwolfson-site/settings/rules → **Protect main** | A ruleset named **"Protect main"** has existed since 2026-02-22 (unenforced while the repo was private; live now). **Edit it in place** rather than importing a second one: tick *Require linear history*; in *Require a pull request before merging* keep 0 approvals, **untick every checkbox in that block** (this clears `require_extra_approval_for_unattributed_changes`), allowed merge methods **Squash only**; tick *Require status checks to pass* → *Add checks* → `build` (GitHub Actions) → tick *Require branches to be up to date*; keep *Block force pushes* and *Restrict deletions*; bypass list empty; **Save changes**. `main-ruleset.json` in this folder is the expected end state for comparison. | R1. The cloud runbook asserts exactly one active ruleset on the default branch with these rules. |
| 6 | https://github.com/settings/installations → Claude → Configure | *Only select repositories* → `jpwolfson-site` only | R7. **Owner declined 2026-10-25** (the Claude app is used on other repositories). Accepted risk: a hijacked session on this repo can reach those repos through the same installation. Recorded in SECURITY.md. |
| 7 | https://github.com/settings/developers → OAuth Apps | Delete the Decap CMS OAuth App | A4. **Owner reports done 2026-10-25.** |

After step 5, a push that is not a PR, a force-push, or a merge without a green `build`
is refused for everyone, including the owner. Content edits go through PRs (agents open
and merge them).

## Claude cloud environment — a **dedicated, throw-away environment**, not the shared one

Spec R3 forbids a Cloudflare write credential anywhere an ordinary agent session can
reach, and the environment attached to this repo is shared by every session on it.
So the token goes into a **new environment used for exactly one session**, then deleted.
This is a time-boxed, recorded exception to R3 (24-hour token, one session, one purpose).

1. In Claude Code (web or app) open the environments list (the cloud environment menu
   in a session's title bar → *Manage environments*, or the Environments page of the
   Claude Code web app) → **Create environment**. Name it `batch-a-cloudflare`.
2. Repositories: `jpwolfson/jpwolfson-site`.
3. Network access → **Limited** → Allowed domains: `api.cloudflare.com`, `jpwolfson.com`,
   `jpwolfson-cms-auth.jpwolfson.workers.dev`, `rdap.verisign.com`; keep *Allow package
   managers* ticked.
4. Network secrets (or Environment variables if the app shows that instead): name
   `CLOUDFLARE_API_TOKEN`, value = the 24-hour token created under **My Profile → API
   Tokens** (scopes in `BATCH-A-CLOUD-RUNBOOK.md` §0).
5. Save. Start **one new session** in that environment on this repository and give it:

```
Execute security-audits/2026-10/BATCH-A-CLOUD-RUNBOOK.md from main, in order, stopping at any failed verification. Do not browse the web.
```

6. When that session reports done: **delete the `batch-a-cloudflare` environment** and
   **delete the Cloudflare API token** (My Profile → API Tokens → ⋯ → Delete).

## Afterwards (owner, any time)

- Publish the DS record the cloud session reports at WordPress.com → Domains → jpwolfson.com → DNSSEC (if the panel offers it; otherwise it waits for the registrar transfer, A8).
- Hardware-key 2FA on GitHub, Cloudflare, WordPress.com: owner-stated done 2026-10-25 (not independently verifiable).
