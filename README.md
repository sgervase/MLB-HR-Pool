# MLB Home Run Pool Tracker

This is a fully automated standings tracker for a personal MLB home run pool. Each participant drafts 6 players at the start of the season, and their top 4 home run totals count toward their score. Nothing more to it. At the end of the season, the participant with the highest home run total from their top 4 players wins.

## How It Works

A Python script pulls current home run totals from the MLB Stats API for every drafted player, calculates each participant's score, and generates a standings page that gets published automatically via GitHub Pages. It runs on a schedule twice a day using GitHub Actions, so there's nothing to manually update during the season.

## Tech Stack

- **Python** — data fetching and HTML generation
- **MLB Stats API** — free and public, no authentication required
- **GitHub Actions** — runs automatically at 4am and 11am UTC daily
- **GitHub Pages** — hosts the standings page

## Project Structure

```
├── config.json              # Pool settings and participant draft picks
├── fetch_stats.py           # Fetches stats from the MLB API and builds the page
├── requirements.txt         # Python dependencies
├── index.html               # Auto-generated standings page (do not edit manually)
├── player_id_cache.json     # Cached MLB player IDs to speed up API lookups
└── .github/
    └── workflows/
        └── update.yml       # GitHub Actions workflow
```

## Configuration

All pool settings and draft picks are managed in `config.json`. To update picks after the draft, just edit the file directly on GitHub and commit. The next scheduled run will pick up the changes.

```json
{
  "pool_name": "2026 Home Run Pool",
  "season": 2026,
  "players_per_team": 6,
  "top_n_count": 4,
  "participants": [
    {
      "name": "sgervase",
      "players": ["Aaron Judge", "Shohei Ohtani", "..."]
    }
  ]
}
```

## Live Site

https://sgervase.github.io/MLB-HR-Pool
