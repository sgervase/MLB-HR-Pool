"""
HR Pool Stats Fetcher
Pulls home run data from the MLB Stats API and generates a standings webpage.
Runs automatically via GitHub Actions on a schedule.
"""

import json
import os
import requests
from datetime import datetime, timezone

# ── Config ────────────────────────────────────────────────────────────────────

CONFIG_FILE = "config.json"
CACHE_FILE = "player_id_cache.json"  # Stores resolved player IDs so we don't re-search each run
OUTPUT_FILE = "index.html"

MLB_API = "https://statsapi.mlb.com/api/v1"

# ── MLB API Helpers ───────────────────────────────────────────────────────────

def search_player_id(name: str) -> tuple[int | None, str | None]:
    """Search MLB API for a player by name. Returns (player_id, full_name) or (None, None)."""
    try:
        url = f"{MLB_API}/people/search?names={requests.utils.quote(name)}&sportIds=1"
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        people = r.json().get("people", [])
        if not people:
            print(f"  ⚠️  Could not find player: '{name}'")
            return None, None
        # Use the first (best) match
        p = people[0]
        return p["id"], p["fullName"]
    except Exception as e:
        print(f"  ❌ Error searching for '{name}': {e}")
        return None, None


def get_season_hr(player_id: int, season: int) -> int:
    """Fetch a player's home run total for the given season. Returns 0 if not found."""
    try:
        url = f"{MLB_API}/people/{player_id}/stats?stats=season&season={season}&group=hitting"
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        stats = r.json().get("stats", [])
        if not stats or not stats[0].get("splits"):
            return 0
        return int(stats[0]["splits"][0]["stat"].get("homeRuns", 0))
    except Exception as e:
        print(f"  ❌ Error fetching stats for player ID {player_id}: {e}")
        return 0

# ── Cache Helpers ─────────────────────────────────────────────────────────────

def load_cache() -> dict:
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE) as f:
            return json.load(f)
    return {}


def save_cache(cache: dict):
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)

# ── Main Logic ────────────────────────────────────────────────────────────────

def main():
    with open(CONFIG_FILE) as f:
        config = json.load(f)

    pool_name = config.get("pool_name", "Home Run Pool")
    season = config.get("season", datetime.now().year)
    top_n = config.get("top_n_count", 4)
    participants = config["participants"]

    cache = load_cache()
    results = []

    for participant in participants:
        print(f"\n📋 Processing {participant['name']}...")
        player_stats = []

        for raw_name in participant["players"]:
            # Resolve player ID (use cache if available)
            if raw_name in cache:
                player_id = cache[raw_name]["id"]
                full_name = cache[raw_name]["full_name"]
            else:
                player_id, full_name = search_player_id(raw_name)
                if player_id:
                    cache[raw_name] = {"id": player_id, "full_name": full_name}

            if player_id:
                hrs = get_season_hr(player_id, season)
                print(f"  ✅ {full_name}: {hrs} HR")
                player_stats.append({"name": full_name, "hr": hrs, "found": True})
            else:
                player_stats.append({"name": raw_name, "hr": 0, "found": False})

        # Sort by HRs descending; top N count toward the team total
        player_stats.sort(key=lambda p: p["hr"], reverse=True)
        for i, p in enumerate(player_stats):
            p["counts"] = p["found"] and (i < top_n)

        total = sum(p["hr"] for p in player_stats if p["counts"])
        results.append({
            "name": participant["name"],
            "players": player_stats,
            "total": total,
        })

    # Save updated cache so next run is faster
    save_cache(cache)

    # Sort standings: highest total first, alphabetical tiebreak
    results.sort(key=lambda x: (-x["total"], x["name"]))

    updated = datetime.now(timezone.utc).strftime("%-I:%M %p UTC on %B %-d, %Y")
    generate_html(results, pool_name, season, top_n, updated)
    print(f"\n✅ Done! Standings updated at {updated}")


# ── HTML Generation ───────────────────────────────────────────────────────────

def generate_html(results: list, pool_name: str, season: int, top_n: int, updated: str):
    """Generate a clean card-style standings page."""

    participant_cards = ""
    for rank, team in enumerate(results, 1):
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(rank, f"#{rank}")
        player_rows = ""
        for p in team["players"]:
            if not p["found"]:
                row_class = "not-found"
            elif p["counts"]:
                row_class = "counting"
            else:
                row_class = "bench"
            hr_display = "—" if not p["found"] else str(p["hr"])
            player_rows += (
                f'<div class="player-row {row_class}">'
                f'<span class="player-name">{p["name"]}</span>'
                f'<span class="player-hr">{hr_display}</span>'
                f'</div>'
            )

        participant_cards += (
            f'<div class="ball-card">'
            f'<div class="card-header">'
            f'<div class="card-rank">{medal}</div>'
            f'<div class="card-owner">{team["name"]}</div>'
            f'<div class="card-total"><span class="total-num">{team["total"]}</span><span class="total-label"> HR</span></div>'
            f'</div>'
            f'<div class="card-divider"></div>'
            f'<div class="player-list">{player_rows}</div>'
            f'</div>'
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{pool_name}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}

    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: #0f1923;
      color: #1a1a1a;
      min-height: 100vh;
      padding: 24px 16px 48px;
    }}

    .header {{
      text-align: center;
      margin-bottom: 32px;
    }}
    .header h1 {{
      font-size: clamp(1.5rem, 5vw, 2.4rem);
      font-weight: 800;
      color: #fff;
      letter-spacing: -0.5px;
    }}
    .header h1 span {{ color: #e8341c; }}
    .season-badge {{
      display: inline-block;
      background: #1e2d3d;
      border: 1px solid #2e4560;
      border-radius: 20px;
      padding: 4px 14px;
      font-size: 0.8rem;
      color: #8aa0b8;
      margin-top: 8px;
    }}
    .updated {{
      font-size: 0.75rem;
      color: #4a6070;
      margin-top: 8px;
    }}

    .cards-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
      gap: 20px;
      max-width: 1100px;
      margin: 0 auto;
    }}

    .ball-card {{
      background: #f5f0e8;
      border-radius: 16px;
      border: 3px solid #d4c9b0;
      padding: 16px 18px;
      box-shadow: 0 4px 20px rgba(0,0,0,0.4);
    }}

    .card-header {{
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 10px;
    }}
    .card-rank {{ font-size: 1.4rem; line-height: 1; }}
    .card-owner {{
      font-size: 1.1rem;
      font-weight: 800;
      color: #1a1a1a;
      flex: 1;
    }}
    .card-total {{ text-align: right; }}
    .total-num {{
      font-size: 2rem;
      font-weight: 900;
      color: #c0392b;
      line-height: 1;
    }}
    .total-label {{
      font-size: 0.75rem;
      color: #888;
      font-weight: 600;
    }}

    .card-divider {{
      height: 2px;
      background: repeating-linear-gradient(90deg, #c0392b 0px, #c0392b 6px, transparent 6px, transparent 10px);
      margin-bottom: 10px;
      border-radius: 2px;
    }}

    .player-row {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 5px 0;
      border-bottom: 1px solid #e0d8c8;
      gap: 8px;
    }}
    .player-row:last-child {{ border-bottom: none; }}
    .player-row.bench {{ opacity: 0.4; }}
    .player-row.not-found {{ opacity: 0.35; }}

    .player-name {{
      font-size: 0.85rem;
      font-weight: 600;
      color: #2a2a2a;
      flex: 1;
    }}
    .player-hr {{
      font-size: 1.1rem;
      font-weight: 800;
      color: #1a1a1a;
      min-width: 28px;
      text-align: right;
    }}
  </style>
</head>
<body>
  <div class="header">
    <h1>⚾ {pool_name.replace('Home Run', '<span>Home Run</span>')}</h1>
    <div class="season-badge">{season} Season &nbsp;·&nbsp; Top {top_n} of 6 count</div>
    <div class="updated">Updated {updated}</div>
  </div>
  <div class="cards-grid">
    {participant_cards}
  </div>
</body>
</html>"""

    with open(OUTPUT_FILE, "w") as f:
        f.write(html)


if __name__ == "__main__":
    main()
