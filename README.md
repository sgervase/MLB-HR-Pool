# MLB Home Run Pool Tracker

A lightweight, fully automated standings tracker for MLB home run pools. Each participant drafts 6 players at the start of the season, and their top 4 home run totals count toward their score. Standings update automatically twice a day throughout the season.

## How It Works

A Python script queries the [MLB Stats API](https://statsapi.mlb.com) to fetch current home run totals for every drafted player. It calculates each participant's score (sum of their top 4 players), sorts the standings, and generates a static HTML page published via GitHub Pages. The whole process runs on a schedule using GitHub Actions — no server required.

## Features

- Live standings updated twice daily from the MLB Stats API
- Per-participant cards showing all 6 players with bench players dimmed
- Mobile-friendly layout
- Manual refresh trigger available via GitHub Actions
- Entirely free to host and run

## Tech Stack

- **Python** — data fetching and HTML generation
- **MLB Stats API** — free, public, no authentication required
- **GitHub Actions** — scheduled automation (runs at 4am and 11am UTC daily)
- **GitHub Pages** — static site hosting

## Project Structure

```
├── config.json              # Pool settings and participant draft picks
├── fetch_stats.py           # Main script: fetches stats and builds the page
├── requirements.txt         # Python dependencies
├── index.html               # Auto-generated standings page (do not edit manually)
├── player_id_cache.json     # Cached MLB player IDs to speed up API lookups
└── .github/
    └── workflows/
        └── update.yml       # GitHub Actions workflow definition
```

## Configuration

All pool settings live in `config.json`:

```json
{
  "pool_name": "2026 Home Run Pool",
  "season": 2026,
  "players_per_team": 6,
  "top_n_count": 4,
  "participants": [
    {
      "name": "Alice",
      "players": ["Aaron Judge", "Shohei Ohtani", "..."]
    }
  ]
}
```

To update draft picks, edit `config.json` directly on GitHub and commit. The next scheduled run will pick up the changes automatically.

## Live Site

Standings are published at: https://sgervase.github.io/MLB-HR-Pool
