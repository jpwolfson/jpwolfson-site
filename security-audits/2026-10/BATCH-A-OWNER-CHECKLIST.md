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
| 5 | https://github.com/jpwolfson/jpwolfson-site/settings/rules → **Protect main** | A ruleset named **"Protect main"** has existed since 2026-02-22 (unenforced while the repo was private; live now). **Edit it in place** rather than importing a second one: tick *Require linear history*; in *Require a pull request before merging* keep 0 approvals, **untick every checkbox in that block** (this clears `require_extra_approval_for_unattributed_changes`), allowed merge methods **Squash only**; tick *Require status checks to pass* → *Add checks* → `build` (GitHub Actions) → tick *Require branches to be up to date*; keep *Block force pushes* and *Restrict deletions*; bypass list empty; **Save changes**. `main-ruleset.json` in this folder is the expected end state for comparison. **Fallback:** if the editor offers no way to clear the unattributed-changes option (the cloud runbook will report `require_extra_approval_for_unattributed_changes: true`), use *New ruleset ▾ → Import a ruleset* with `main-ruleset.json`, then delete "Protect main", so exactly one ruleset remains. | R1. The cloud runbook asserts exactly one active ruleset on the default branch with these rules. |
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
Labels below are the ones in the cloud-environments documentation.

1. At https://claude.ai/code, on the **new-session screen** (before typing a message),
   click the **first control in the row under the message box** (the environment
   selector). At the bottom of the menu click **New environment**.
2. In the **New environment** dialog: name `batch-a-cloudflare`. Click the **Network
   access** row → **Custom** → **Allowed domains**, one per line:
   `jpwolfson.com`, `jpwolfson-cms-auth.jpwolfson.workers.dev`, `rdap.verisign.com`;
   tick **Also include default list of common package managers**. Click **Add environment**.
3. Reopen it: selector → find `batch-a-cloudflare` under **Cloud** (or **More**) → hover
   → settings icon → **Edit cloud environment** dialog → **Network secrets** row →
   **Add secret**. **Secret type** Bearer; **Name** `Cloudflare Batch A`; **Allowed
   websites** `api.cloudflare.com`; **Custom headers** row left as `Authorization` /
   prefix `Bearer`, token pasted as **Value**. Click **Add** (saves immediately; the value
   cannot be viewed again). The token now lives outside the session VM; the proxy attaches
   it only to `api.cloudflare.com` requests.
4. With `batch-a-cloudflare` selected, send this as the session's first message:

```
Execute security-audits/2026-10/BATCH-A-CLOUD-RUNBOOK.md from main, in order, stopping at any failed verification. Do not browse the web.
```

5. When that session reports done: edit the environment, delete the Network secret,
   then archive the environment; delete the Cloudflare API token (My Profile → API
   Tokens → ⋯ → Delete).

## Afterwards (owner, any time)

- Publish the DS record the cloud session reports at WordPress.com → Domains → jpwolfson.com → DNSSEC (if the panel offers it; otherwise it waits for the registrar transfer, A8).
- Hardware-key 2FA on GitHub, Cloudflare, WordPress.com: owner-stated done 2026-10-25 (not independently verifiable).
