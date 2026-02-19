# Jesse Wolfson – jpwolfson.com
## Setup Guide: GitHub → Cloudflare Pages → Decap CMS

This guide walks you through getting the site live, from zero.
Estimated time: 45–60 minutes, mostly waiting for things to process.
No coding required beyond copy-pasting.

---

## Part 1: GitHub (the file store)

GitHub is where your site's files live. Think of it as Google Drive for code.

### 1a. Create a GitHub account
1. Go to https://github.com and sign up for a free account.
2. **Important – secure it properly:** After signing up, go to Settings → Password and authentication → enable Two-factor authentication. Use an authenticator app (Google Authenticator, Authy, 1Password) — **not** SMS. This account is now the master key to your site, so treat it accordingly.

### 1b. Create a repository (a folder for your site)
1. Click the **+** in the top-right corner → "New repository."
2. Name it `jpwolfson-site` (or anything you like).
3. Set it to **Private** (nobody needs to see the source files).
4. Leave everything else as default. Click **Create repository.**

### 1c. Upload the site files
1. On your new repository page, click "uploading an existing file" (or drag files in).
2. Upload everything inside the `jpwolfson-site` folder you received — maintain the folder structure.
   Alternatively, if you have Git installed: `git clone` the repo, copy files in, `git add . && git commit -m "initial" && git push`.
3. After upload, you should see all the folders (`src/`, `oauth-worker/`, etc.) in the repository.

---

## Part 2: Cloudflare Pages (the host)

### 2a. Create a Cloudflare account
1. Go to https://cloudflare.com and sign up for a free account.
2. Enable Two-factor authentication here too (Settings → My Profile → Authentication).

### 2b. Connect to GitHub and deploy
1. In the Cloudflare dashboard, click **Pages** in the left sidebar.
2. Click **Create a project** → **Connect to Git.**
3. Click **Connect GitHub** and authorize Cloudflare to access your GitHub account. Select your `jpwolfson-site` repo.
4. On the "Set up builds and deployments" screen, set:
   - **Framework preset:** None (leave as is, or select "Eleventy" if available)
   - **Build command:** `npx @11ty/eleventy`
   - **Build output directory:** `_site`
5. Click **Save and Deploy.** Cloudflare will build and publish your site. Takes 1–2 minutes.
6. You'll get a temporary URL like `jpwolfson-site.pages.dev` — open it and verify the site looks correct.

### 2c. Point your domain at Cloudflare Pages
1. Still in Cloudflare Pages → your project → **Custom domains.**
2. Click **Set up a custom domain** → enter `jpwolfson.com` → Continue.
3. Cloudflare will show you DNS records to add. **Copy these.**
4. Log into WordPress.com → your domain settings.
5. Find the DNS or Name Server settings. You have two options:
   - **Option A (simpler):** Change the nameservers to Cloudflare's (Cloudflare will prompt you with the exact values). This moves all DNS management to Cloudflare.
   - **Option B:** Keep WordPress.com nameservers but add a CNAME record pointing `jpwolfson.com` to your `jpwolfson-site.pages.dev` address.
   
   Option A is easier long-term. Option B requires less change to WordPress.com.
6. DNS changes take 10 minutes to 48 hours to propagate. Your site should be live at `jpwolfson.com` after that.

### 2d. Enable Cloudflare Web Analytics
1. In your Cloudflare dashboard, click **Analytics & Logs** → **Web Analytics.**
2. Add your site → follow the prompt to add a small script tag to your site.
   (I can add this for you — just paste the script snippet they give you in a message here and I'll insert it into the template.)

---

## Part 3: Cloudflare Worker (the authentication bridge)

This small piece of code lets Decap CMS securely log into GitHub on your behalf. You deploy it once and never touch it again.

### 3a. Create a GitHub OAuth App
1. Go to GitHub → Settings → Developer settings → OAuth Apps → **New OAuth App.**
2. Fill in:
   - **Application name:** `jpwolfson CMS`
   - **Homepage URL:** `https://jpwolfson.com`
   - **Authorization callback URL:** `https://jpwolfson-cms-auth.YOUR_SUBDOMAIN.workers.dev/oauth/callback`
     (You'll get the actual Worker URL in step 3c; come back and update this.)
3. Click **Register application.**
4. Click **Generate a new client secret.** Save both the **Client ID** and **Client Secret** somewhere safe (like a password manager). You won't see the secret again.

### 3b. Create the Cloudflare Worker
1. In Cloudflare dashboard → **Workers & Pages** → **Create** → **Create Worker.**
2. Name it something like `jpwolfson-cms-auth.`
3. In the editor, delete all the placeholder code and paste in the contents of `oauth-worker/worker.js` (from the files you uploaded).
4. Click **Deploy.**
5. Note the Worker's URL — it will look like `jpwolfson-cms-auth.YOUR_SUBDOMAIN.workers.dev.`

### 3c. Add your secrets to the Worker
1. Go to your Worker → **Settings** → **Variables.**
2. Under **Environment Variables**, add three **Secret** variables (use "Add variable" → type → "Encrypt"):
   - `GITHUB_CLIENT_ID` → paste your GitHub OAuth App Client ID
   - `GITHUB_CLIENT_SECRET` → paste your GitHub OAuth App Client Secret
   - `ALLOWED_DOMAINS` → `jpwolfson.com`
3. Click **Save.**

### 3d. Go back and finish the GitHub OAuth App
1. Return to GitHub → Settings → Developer settings → OAuth Apps → your app.
2. Update the **Authorization callback URL** to your actual Worker URL:
   `https://jpwolfson-cms-auth.YOUR_SUBDOMAIN.workers.dev/oauth/callback`
3. Save.

### 3e. Update the CMS config
In your GitHub repository, edit `src/admin/config.yml`:
- Replace `YOUR_GITHUB_USERNAME` with your GitHub username.
- Replace `YOUR_REPO_NAME` with `jpwolfson-site` (or whatever you named it).
- Change `base_url` to your Worker URL: `https://jpwolfson-cms-auth.YOUR_SUBDOMAIN.workers.dev`

Save → Cloudflare will automatically rebuild and deploy.

---

## Part 4: Using the CMS

1. Go to `https://jpwolfson.com/admin/` in your browser.
2. Click **Login with GitHub.**
3. You'll be redirected to GitHub to authorize → then back to the CMS editor.
4. Click any page on the left sidebar to edit it. The editor looks like a basic word processor.
5. When done, click **Publish.** Cloudflare automatically rebuilds the site within ~1 minute.

That's it. From this point on, editing the site is: go to `/admin/`, make changes, publish.

---

## Canceling WordPress.com hosting

Once your site is live and confirmed working at `jpwolfson.com`:

1. Log into WordPress.com → Plans.
2. Cancel your hosting plan. **Do not** cancel the domain registration — that stays active as long as you pay the annual domain fee (~$18/year).
3. If WordPress.com requires you to keep a plan to retain the domain, you can transfer the domain registration to Cloudflare Registrar (same price, no markup). That's a separate ~15-minute process I can walk you through.

---

## Getting help / making updates

For any content changes — new paper, updated talk list, anything on any page — just message me here and describe what you want changed. I'll send you back the updated file and tell you exactly where to put it, or walk you through the CMS if you prefer to do it yourself.
