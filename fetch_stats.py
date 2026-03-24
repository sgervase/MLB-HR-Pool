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
    """Generate a clean, mobile-friendly standings page."""

    # Build standings rows
    standings_rows = ""
    for rank, team in enumerate(results, 1):
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(rank, f"{rank}")
        standings_rows += f"""
        <tr class="standings-row" onclick="toggleDetail('{team['name']}')">
          <td class="rank">{medal}</td>
          <td class="owner-name">{team['name']}</td>
          <td class="total">{team['total']}</td>
          <td class="expand-icon">▾</td>
        </tr>
        <tr class="detail-row" id="detail-{team['name'].replace(' ', '-')}">
          <td colspan="4">
            <div class="player-grid">
              {build_player_cards(team['players'], top_n)}
            </div>
          </td>
        </tr>"""

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
      color: #e8edf2;
      min-height: 100vh;
      padding: 20px 16px 40px;
    }}

    /* ── Header ── */
    .header {{
      text-align: center;
      margin-bottom: 28px;
    }}
    .header h1 {{
      font-size: clamp(1.4rem, 5vw, 2.2rem);
      font-weight: 800;
      letter-spacing: -0.5px;
      color: #fff;
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
      margin-top: 6px;
    }}
    .updated {{
      font-size: 0.75rem;
      color: #556a80;
      margin-top: 8px;
    }}

    /* ── Card wrapper ── */
    .card {{
      background: #1a2635;
      border: 1px solid #243447;
      border-radius: 12px;
      overflow: hidden;
      max-width: 700px;
      margin: 0 auto 16px;
    }}

    /* ── Standings table ── */
    table {{ width: 100%; border-collapse: collapse; }}
    thead th {{
      background: #152030;
      color: #8aa0b8;
      font-size: 0.7rem;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      padding: 10px 16px;
      text-align: left;
    }}
    thead th.num {{ text-align: right; }}

    .standings-row {{
      cursor: pointer;
      transition: background 0.15s;
      border-top: 1px solid #1e2d3d;
    }}
    .standings-row:hover {{ background: #1f3148; }}
    .standings-row td {{
      padding: 14px 16px;
      vertical-align: middle;
    }}
    .rank {{ font-size: 1.1rem; width: 44px; }}
    .owner-name {{ font-weight: 600; font-size: 1rem; }}
    .total {{
      text-align: right;
      font-size: 1.4rem;
      font-weight: 800;
      color: #e8341c;
      width: 70px;
    }}
    .expand-icon {{
      text-align: right;
      color: #556a80;
      font-size: 1rem;
      width: 30px;
      transition: transform 0.2s;
    }}
    .expanded .expand-icon {{ transform: rotate(180deg); }}

    /* ── Detail row ── */
    .detail-row {{ display: none; background: #111e2b; }}
    .detail-row td {{ padding: 0; }}
    .detail-row.open {{ display: table-row; }}

    .player-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
      gap: 10px;
      padding: 14px 16px;
    }}

    .player-card {{
      background: #1a2d42;
      border-radius: 8px;
      padding: 10px 12px;
      position: relative;
      border: 1px solid transparent;
    }}
    .player-card.counts {{
      border-color: #2a4a6b;
    }}
    .player-card.benched {{
      opacity: 0.45;
    }}
    .player-card.not-found {{
      border-color: #5c2a2a;
      opacity: 0.5;
    }}
    .player-name {{
      font-size: 0.82rem;
      font-weight: 600;
      color: #c8d8e8;
      margin-bottom: 4px;
      line-height: 1.25;
    }}
    .player-hr {{
      font-size: 1.3rem;
      font-weight: 800;
      color: #fff;
    }}
    .player-hr span {{ font-size: 0.7rem; color: #556a80; font-weight: 400; }}
    .counts-badge {{
      font-size: 0.65rem;
      color: #4a9eff;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      margin-top: 2px;
    }}
    .benched-badge {{
      font-size: 0.65rem;
      color: #556a80;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      margin-top: 2px;
    }}

    /* ── Hint ── */
    .hint {{
      text-align: center;
      font-size: 0.75rem;
      color: #3a5068;
      margin-top: 6px;
    }}
  </style>
</head>
<body>
  <div class="header">
    <h1>⚾ {pool_name.replace('Home Run', '<span>Home Run</span>')}</h1>
    <div class="season-badge">{season} Season · Top {top_n} of 6 count</div>
    <div class="updated">Updated {updated}</div>
  </div>

  <div class="card">
    <table>
      <thead>
        <tr>
          <th colspan="2">Owner</th>
          <th class="num">HRs</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        {standings_rows}
      </tbody>
    </table>
  </div>

  <p class="hint">Tap any row to see player breakdown</p>

  <script>
    function toggleDetail(name) {{
      const safeId = name.replace(/ /g, '-');
      const detailRow = document.getElementById('detail-' + safeId);
      const standingsRows = document.querySelectorAll('.standings-row');
      // Find the standings row for this owner
      standingsRows.forEach(row => {{
        if (row.querySelector('.owner-name') && row.querySelector('.owner-name').textContent === name) {{
          row.classList.toggle('expanded');
        }}
      }});
      detailRow.classList.toggle('open');
    }}
  </script>
</body>
</html>"""

    with open(OUTPUT_FILE, "w") as f:
        f.write(html)


def build_player_cards(players: list, top_n: int) -> str:
    cards = ""
    for p in players:
        if not p["found"]:
            cards += f"""
            <div class="player-card not-found">
              <div class="player-name">{p['name']}</div>
              <div class="player-hr">—</div>
              <div class="benched-badge">Not found</div>
            </div>"""
        elif p["counts"]:
            cards += f"""
            <div class="player-card counts">
              <div class="player-name">{p['name']}</div>
              <div class="player-hr">{p['hr']} <span>HR</span></div>
              <div class="counts-badge">✦ Counting</div>
            </div>"""
        else:
            cards += f"""
            <div class="player-card benched">
              <div class="player-name">{p['name']}</div>
              <div class="player-hr">{p['hr']} <span>HR</span></div>
              <div class="benched-badge">Bench</div>
            </div>"""
    return cards


if __name__ == "__main__":
    main()
