# ⚾ Home Run Pool

Automated MLB home run pool tracker. Standings are pulled live from the MLB Stats API and published to GitHub Pages every 2 hours during the season.

---

## Setup (one-time, ~30 minutes)

### 1. Create the GitHub repository

1. Go to [github.com](https://github.com) and sign in
2. Click **+** → **New repository**
3. Name it `hr-pool` (or anything you like)
4. Set it to **Public** *(required for free GitHub Pages)*
5. Click **Create repository**

### 2. Upload these files

You can do this entirely in the browser — no coding tools needed.

In your new repo, click **Add file → Upload files** and upload everything in this folder:
- `config.json`
- `fetch_stats.py`
- `requirements.txt`
- `README.md`

Then for the workflow file, you need to create the folder path manually:
1. Click **Add file → Create new file**
2. In the filename box, type: `.github/workflows/update.yml`
3. Paste in the contents of `update.yml` from this folder
4. Click **Commit new file**

### 3. Enable GitHub Pages

1. In your repo, go to **Settings → Pages**
2. Under **Source**, select **Deploy from a branch**
3. Set branch to `main`, folder to `/ (root)`
4. Click **Save**

Your site will be live at: `https://YOUR-USERNAME.github.io/hr-pool`

### 4. Fill in the draft picks

After your draft, edit `config.json` directly on GitHub (click the file → pencil icon) and replace the placeholder names with your actual participants and their drafted players.

> **Tip:** Use full names as they appear on MLB.com (e.g. `"Rafael Devers"` not `"Devers"`). The script will find them automatically.

### 5. Run it for the first time

Go to **Actions → Update HR Pool Standings → Run workflow** to kick off the first run manually. After that, it runs automatically every 2 hours.

---

## Troubleshooting a player not found

If a player shows as "Not found", it usually means the name didn't match exactly. To fix it:

1. Look up the player's MLB ID at `https://statsapi.mlb.com/api/v1/people/search?names=FIRSTNAME+LASTNAME`
2. Add them directly to `player_id_cache.json` in this format:
   ```json
   "Nickname Name": {"id": 123456, "full_name": "Official Full Name"}
   ```

---

## Manual refresh for friends

Anyone can trigger a standings refresh by going to:
`https://github.com/YOUR-USERNAME/hr-pool/actions` → **Update HR Pool Standings** → **Run workflow**

No account needed to *view* the standings page — just share the GitHub Pages link.
