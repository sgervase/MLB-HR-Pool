"""
HR Pool Stats Fetcher
Pulls home run data from the MLB Stats API and generates a standings webpage.
Runs automatically via GitHub Actions on a schedule.
"""
 
import json
import os
import unicodedata
import requests
from datetime import datetime, timezone, timedelta
 
# ── Config ────────────────────────────────────────────────────────────────────
 
CONFIG_FILE  = "config.json"
CACHE_FILE   = "player_id_cache.json"
HISTORY_FILE = "history.json"
OUTPUT_FILE  = "index.html"
MLB_API      = "https://statsapi.mlb.com/api/v1"
 
TEAM_COLORS = [
    "#e8341c", "#4a9eff", "#2ecc71",
    "#f39c12", "#9b59b6", "#1abc9c", "#e91e63",
]
 
# ── Name helpers ──────────────────────────────────────────────────────────────
 
def normalize_name(name):
    """Strip accents and lowercase for fuzzy matching."""
    return unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
 
# ── MLB API helpers ───────────────────────────────────────────────────────────
 
def search_player_id(name):
    try:
        url = f"{MLB_API}/people/search?names={requests.utils.quote(name)}&sportIds=1"
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        people = r.json().get("people", [])
        if not people:
            print(f"  ⚠️  Could not find player: '{name}'")
            return None, None
        p = people[0]
        return p["id"], p["fullName"]
    except Exception as e:
        print(f"  ❌ Error searching for '{name}': {e}")
        return None, None
 
 
def get_season_hr(player_id, season):
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
 
 
def fetch_hr_leaders(season, limit=50):
    """Fetch the top HR leaders league-wide for the season."""
    try:
        url = (
            f"{MLB_API}/stats/leaders"
            f"?leaderCategories=homeRuns"
            f"&season={season}"
            f"&leaderGameTypes=R"
            f"&limit={limit}"
            f"&sportId=1"
        )
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        leaders = []
        for cat in r.json().get("leagueLeaders", []):
            for entry in cat.get("leaders", []):
                leaders.append({
                    "name": entry["person"]["fullName"],
                    "hr":   int(entry.get("value", 0)),
                })
        return leaders
    except Exception as e:
        print(f"  ❌ Error fetching HR leaders: {e}")
        return []
 
# ── Cache helpers ─────────────────────────────────────────────────────────────
 
def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE) as f:
            return json.load(f)
    return {}
 
 
def save_cache(cache):
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)
 
# ── History helpers ───────────────────────────────────────────────────────────
 
def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE) as f:
            return json.load(f)
    return {"snapshots": []}
 
 
def save_weekly_snapshot(history, results, today):
    """Save one snapshot per calendar week (keyed to Monday)."""
    week_start = (today - timedelta(days=today.weekday())).strftime("%Y-%m-%d")
    existing   = {s["week_start"] for s in history["snapshots"]}
    if week_start in existing:
        return history
    snapshot = {
        "week_start": week_start,
        "date": today.strftime("%Y-%m-%d"),
        "standings": {
            team["name"]: {"total": team["total"], "rank": i + 1}
            for i, team in enumerate(results)
        },
    }
    history["snapshots"].append(snapshot)
    history["snapshots"].sort(key=lambda s: s["week_start"])
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)
    print(f"  Saved weekly snapshot for week of {week_start}")
    return history
 
# ── Draft board helper ────────────────────────────────────────────────────────
 
def build_participant_picks(participants):
    """
    Snake-draft logic: returns {name: [{player, round, overall}, ...]}
    where picks are listed in the order the participant made them.
    """
    n          = len(participants)
    num_rounds = len(participants[0]["players"])
    picks      = {p["name"]: [] for p in participants}
    overall    = 1
 
    for round_num in range(num_rounds):
        order = list(range(n)) if round_num % 2 == 0 else list(range(n - 1, -1, -1))
        for team_idx in order:
            p = participants[team_idx]
            picks[p["name"]].append({
                "player":  p["players"][round_num],
                "round":   round_num + 1,
                "overall": overall,
            })
            overall += 1
 
    return picks
 
# ── Main ──────────────────────────────────────────────────────────────────────
 
def main():
    with open(CONFIG_FILE) as f:
        config = json.load(f)
 
    pool_name    = config.get("pool_name", "Home Run Pool")
    season       = config.get("season", datetime.now().year)
    top_n        = config.get("top_n_count", 4)
    participants = config["participants"]
 
    cache   = load_cache()
    results = []
 
    for participant in participants:
        print(f"\nProcessing {participant['name']}...")
        player_stats = []
 
        for raw_name in participant["players"]:
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
 
        player_stats.sort(key=lambda p: p["hr"], reverse=True)
        for i, p in enumerate(player_stats):
            p["counts"] = p["found"] and (i < top_n)
 
        total = sum(p["hr"] for p in player_stats if p["counts"])
        results.append({"name": participant["name"], "players": player_stats, "total": total})
 
    save_cache(cache)
    results.sort(key=lambda x: (-x["total"], x["name"]))
 
    # League leaders
    print("\nFetching league HR leaders...")
    hr_leaders = fetch_hr_leaders(season, limit=50)
 
    # Build normalised set of all drafted names
    all_drafted_norm = set()
    for p in participants:
        for raw in p["players"]:
            all_drafted_norm.add(normalize_name(raw))
            if raw in cache:
                all_drafted_norm.add(normalize_name(cache[raw]["full_name"]))
 
    # Weekly snapshot
    today   = datetime.now(timezone.utc).date()
    history = load_history()
    history = save_weekly_snapshot(history, results, today)
 
    # Draft board
    participant_picks = build_participant_picks(participants)
 
    edt     = timezone(timedelta(hours=-4))
    updated = datetime.now(edt).strftime("%-I:%M %p EDT on %B %-d, %Y")
 
    generate_html(
        results, pool_name, season, top_n, updated,
        hr_leaders, all_drafted_norm,
        participants, participant_picks, history,
    )
    print(f"\n✅ Done! Standings updated at {updated}")
 
# ── HTML entry point ──────────────────────────────────────────────────────────
 
def generate_html(results, pool_name, season, top_n, updated,
                  hr_leaders, all_drafted_norm,
                  participants, participant_picks, history):
 
    # Assign stable colors by original draft order
    color_map = {
        p["name"]: TEAM_COLORS[i % len(TEAM_COLORS)]
        for i, p in enumerate(participants)
    }
 
    standings_html = _standings_section(results, top_n)
    draft_html     = _draft_section(participants, participant_picks, color_map)
    leaders_html   = _leaders_section(
        hr_leaders, all_drafted_norm,
        len(participants), len(participants[0]["players"])
    )
    tracker_html   = _tracker_section(history, results, color_map)
 
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>{pool_name}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: #0f1923;
      color: #e8edf2;
      min-height: 100vh;
      padding: 24px 16px 48px;
    }}
 
    /* ── Header ── */
    .header {{ text-align: center; margin-bottom: 24px; }}
    .header h1 {{
      font-size: clamp(1.5rem, 5vw, 2.4rem);
      font-weight: 800;
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
      margin-top: 8px;
    }}
    .updated {{ font-size: 0.75rem; color: #4a6070; margin-top: 6px; }}
 
    /* ── Tabs ── */
    .tab-nav {{
      display: flex;
      gap: 6px;
      max-width: 1100px;
      margin: 0 auto 20px;
      overflow-x: auto;
      padding-bottom: 2px;
    }}
    .tab-btn {{
      background: #1a2635;
      border: 1px solid #243447;
      border-radius: 8px;
      color: #8aa0b8;
      cursor: pointer;
      font-size: 0.85rem;
      font-weight: 600;
      padding: 9px 18px;
      white-space: nowrap;
      transition: all 0.15s;
    }}
    .tab-btn:hover {{ background: #1f3148; color: #c8d8e8; }}
    .tab-btn.active {{ background: #e8341c; border-color: #e8341c; color: #fff; }}
    .tab-content {{ display: none; }}
    .tab-content.active {{ display: block; }}
 
    /* ── Standings cards ── */
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
    .card-header {{ display: flex; align-items: center; gap: 8px; margin-bottom: 10px; }}
    .card-rank {{ font-size: 1.4rem; line-height: 1; }}
    .card-owner {{ font-size: 1.1rem; font-weight: 800; color: #1a1a1a; flex: 1; }}
    .card-total {{ text-align: right; }}
    .total-num {{ font-size: 2rem; font-weight: 900; color: #c0392b; line-height: 1; }}
    .total-label {{ font-size: 0.75rem; color: #888; font-weight: 600; }}
    .card-divider {{
      height: 2px;
      background: repeating-linear-gradient(90deg, #c0392b 0px, #c0392b 6px, transparent 6px, transparent 10px);
      margin-bottom: 10px;
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
    .player-name {{ font-size: 0.85rem; font-weight: 600; color: #2a2a2a; flex: 1; }}
    .player-hr {{ font-size: 1.1rem; font-weight: 800; color: #1a1a1a; min-width: 28px; text-align: right; }}
 
    /* ── Shared section wrapper ── */
    .section-card {{
      background: #1a2635;
      border: 1px solid #243447;
      border-radius: 12px;
      max-width: 1100px;
      margin: 0 auto;
      overflow: hidden;
    }}
    .section-title {{
      font-size: 0.95rem;
      font-weight: 700;
      color: #fff;
      padding: 14px 18px;
      background: #152030;
      border-bottom: 1px solid #243447;
    }}
 
    /* ── Draft board ── */
    .draft-table {{ width: 100%; border-collapse: collapse; }}
    .draft-table th {{
      background: #111e2b;
      color: #556a80;
      font-size: 0.68rem;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      padding: 10px 14px;
      text-align: left;
      white-space: nowrap;
    }}
    .draft-table td {{
      padding: 11px 14px;
      border-bottom: 1px solid #1e2d3d;
      vertical-align: top;
    }}
    .draft-table tr:last-child td {{ border-bottom: none; }}
    .draft-table tr:hover td {{ background: #1f3148; }}
    .owner-cell {{
      font-weight: 700;
      color: #fff;
      white-space: nowrap;
      border-left-width: 3px;
      border-left-style: solid;
    }}
    .round-cell {{ font-size: 0.75rem; font-weight: 700; color: #556a80; white-space: nowrap; }}
    .pick-player {{ font-size: 0.85rem; color: #c8d8e8; }}
    .pick-meta {{ font-size: 0.65rem; color: #3a5570; margin-top: 3px; }}
    .chart-subtitle {{ font-size: 0.8rem; font-weight: 600; color: #556a80; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 12px; }}
 
    /* ── Leaders table ── */
    .leaders-summary {{
      display: flex;
      gap: 32px;
      padding: 16px 18px;
      border-bottom: 1px solid #243447;
      background: #111e2b;
    }}
    .summary-stat {{ text-align: center; }}
    .summary-num {{ font-size: 1.8rem; font-weight: 800; color: #e8341c; line-height: 1; }}
    .summary-label {{
      font-size: 0.68rem;
      color: #556a80;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      margin-top: 3px;
    }}
    .leaders-table {{ width: 100%; border-collapse: collapse; }}
    .leaders-table th {{
      background: #111e2b;
      color: #556a80;
      font-size: 0.68rem;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      padding: 10px 14px;
      text-align: left;
    }}
    .leaders-table th.num {{ text-align: right; }}
    .leaders-table td {{
      padding: 9px 14px;
      border-bottom: 1px solid #1e2d3d;
      font-size: 0.875rem;
    }}
    .leaders-table tr:last-child td {{ border-bottom: none; }}
    .leaders-table tr.drafted td {{ background: rgba(46,204,113,0.06); }}
    .leaders-table tr:hover td {{ background: #1f3148; }}
    .rank-col {{ color: #3a5570; font-size: 0.8rem; width: 36px; }}
    .hr-col {{ text-align: right; font-weight: 700; color: #fff; width: 60px; }}
    .badge-yes {{
      display: inline-block;
      background: rgba(46,204,113,0.18);
      color: #2ecc71;
      border-radius: 4px;
      padding: 2px 9px;
      font-size: 0.7rem;
      font-weight: 700;
    }}
    .badge-no {{
      display: inline-block;
      background: rgba(231,76,60,0.12);
      color: #e74c3c;
      border-radius: 4px;
      padding: 2px 9px;
      font-size: 0.7rem;
      font-weight: 700;
    }}
    .divider-row td {{
      padding: 6px 14px;
      font-size: 0.7rem;
      color: #3a5570;
      background: #111e2b;
      border-bottom: 1px solid #243447;
    }}
 
    /* ── Season tracker ── */
    .tracker-wrap {{ padding: 20px 18px; overflow-x: auto; }}
    .no-data {{ color: #3a5570; font-size: 0.875rem; text-align: center; padding: 48px 20px; }}
  </style>
</head>
<body>
  <div class="header">
    <h1>⚾ {pool_name.replace('Home Run', '<span>Home Run</span>')}</h1>
    <div class="season-badge">{season} Season &nbsp;·&nbsp; Top {top_n} of 6 count</div>
    <div class="updated">Updated {updated}</div>
  </div>
 
  <nav class="tab-nav">
    <button class="tab-btn active" onclick="showTab('standings', this)">Standings</button>
    <button class="tab-btn" onclick="showTab('draft', this)">Draft Board</button>
    <button class="tab-btn" onclick="showTab('leaders', this)">Who Should We Have Drafted?</button>
    <button class="tab-btn" onclick="showTab('tracker', this)">Season Tracker</button>
  </nav>
 
  <div id="standings" class="tab-content active">{standings_html}</div>
  <div id="draft"     class="tab-content">{draft_html}</div>
  <div id="leaders"   class="tab-content">{leaders_html}</div>
  <div id="tracker"   class="tab-content">{tracker_html}</div>
 
  <script>
    function showTab(id, btn) {{
      document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
      document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
      document.getElementById(id).classList.add('active');
      btn.classList.add('active');
    }}
  </script>
</body>
</html>"""
 
    with open(OUTPUT_FILE, "w") as f:
        f.write(html)
 
# ── Section builders ──────────────────────────────────────────────────────────
 
def _standings_section(results, top_n):
    cards = ""
    for rank, team in enumerate(results, 1):
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(rank, f"#{rank}")
        rows  = ""
        for p in team["players"]:
            cls = "not-found" if not p["found"] else ("counting" if p["counts"] else "bench")
            hr  = "—" if not p["found"] else str(p["hr"])
            rows += (
                f'<div class="player-row {cls}">'
                f'<span class="player-name">{p["name"]}</span>'
                f'<span class="player-hr">{hr}</span>'
                f'</div>'
            )
        cards += (
            f'<div class="ball-card">'
            f'<div class="card-header">'
            f'<div class="card-rank">{medal}</div>'
            f'<div class="card-owner">{team["name"]}</div>'
            f'<div class="card-total">'
            f'<span class="total-num">{team["total"]}</span>'
            f'<span class="total-label"> HR</span>'
            f'</div></div>'
            f'<div class="card-divider"></div>'
            f'<div class="player-list">{rows}</div>'
            f'</div>'
        )
    return f'<div class="cards-grid">{cards}</div>'
 
 
def _draft_section(participants, participant_picks, color_map):
    num_rounds = len(participants[0]["players"])
 
    # Header: one column per team, with color bar on top
    header_cells = "<th>Round</th>" + "".join(
        f'<th style="border-top:3px solid {color_map.get(p["name"], "#fff")};color:#c8d8e8">' +
        p["name"] + "</th>"
        for p in participants
    )
 
    # Rows: one row per round
    rows = ""
    for round_idx in range(num_rounds):
        round_num = round_idx + 1
        row = f'<td class="round-cell">Round {round_num}</td>'
        for p in participants:
            pick = participant_picks[p["name"]][round_idx]
            row += (
                f'<td>'
                f'<div class="pick-player">{pick["player"]}</div>'
                f'<div class="pick-meta">Overall #{pick["overall"]}</div>'
                f'</td>'
            )
        rows += f"<tr>{row}</tr>"
 
    return (
        f'<div class="section-card">'
        f'<div class="section-title">'
        f'Draft Board — {len(participants)}-Team Snake Draft'
        f'</div>'
        f'<div style="overflow-x:auto">'
        f'<table class="draft-table">'
        f'<thead><tr>{header_cells}</tr></thead>'
        f'<tbody>{rows}</tbody>'
        f'</table>'
        f'</div></div>'
    )
 
 
def _leaders_section(hr_leaders, all_drafted_norm, num_teams, picks_per_team):
    pool_size  = num_teams * picks_per_team   # 36 — the number to measure against
    hr_leaders = sorted(hr_leaders, key=lambda x: x["hr"], reverse=True)
 
    if not hr_leaders:
        return (
            '<div class="section-card">'
            '<p class="no-data">Could not fetch league leaders.</p>'
            '</div>'
        )
 
    top_pool      = hr_leaders[:pool_size]
    drafted_count = sum(1 for p in top_pool if normalize_name(p["name"]) in all_drafted_norm)
    missed        = pool_size - drafted_count
    pct           = (drafted_count / pool_size * 100) if pool_size else 0
 
    summary = (
        f'<div class="leaders-summary">'
        f'<div class="summary-stat">'
        f'<div class="summary-num">{drafted_count}</div>'
        f'<div class="summary-label">Drafted from Top {pool_size}</div>'
        f'</div>'
        f'<div class="summary-stat">'
        f'<div class="summary-num">{missed}</div>'
        f'<div class="summary-label">Missed</div>'
        f'</div>'
        f'<div class="summary-stat">'
        f'<div class="summary-num">{pct:.0f}%</div>'
        f'<div class="summary-label">Hit Rate</div>'
        f'</div>'
        f'</div>'
    )
 
    row_list = []
    for rank, p in enumerate(hr_leaders, 1):
        is_drafted = normalize_name(p["name"]) in all_drafted_norm
        badge      = '<span class="badge-yes">Drafted</span>' if is_drafted else '<span class="badge-no">Missed</span>'
        cls        = 'drafted' if is_drafted else ''
        fade       = '' if rank <= pool_size else ' style="opacity:0.45"'
        row_list.append(
            f'<tr class="{cls}"{fade}>'
            f'<td class="rank-col">{rank}</td>'
            f'<td>{p["name"]}</td>'
            f'<td class="hr-col">{p["hr"]}</td>'
            f'<td>{badge}</td>'
            f'</tr>'
        )
        if rank == pool_size:
            row_list.append(
                f'<tr class="divider-row">'
                f'<td colspan="4">'
                f'— Top {pool_size} counted above &nbsp;·&nbsp; remaining shown for reference —'
                f'</td></tr>'
            )
 
    return (
        f'<div class="section-card">'
        f'<div class="section-title">'
        f'Who Should We Have Drafted? — Top {len(hr_leaders)} MLB HR Leaders'
        f'</div>'
        f'{summary}'
        f'<div style="overflow-x:auto">'
        f'<table class="leaders-table">'
        f'<thead><tr>'
        f'<th>#</th><th>Player</th><th class="num">HR</th><th>Drafted?</th>'
        f'</tr></thead>'
        f'<tbody>{"".join(row_list)}</tbody>'
        f'</table>'
        f'</div></div>'
    )
 
 
def _tracker_section(history, results, color_map):
    snapshots = history.get("snapshots", [])
 
    if not snapshots:
        return (
            '<div class="section-card">'
            '<div class="section-title">Season Tracker</div>'
            '<p class="no-data">'
            'No data yet — the tracker will populate after the first weekly snapshot. Check back next week!'
            '</p></div>'
        )
 
    participants = [r["name"] for r in results]
    n            = len(participants)
    n_weeks      = len(snapshots)
 
    rank_svg = _rank_chart(snapshots, participants, n, n_weeks, color_map)
    hr_svg   = _hr_chart(snapshots, participants, n, n_weeks, color_map)
 
    return (
        '<div class="section-card">'
        '<div class="section-title">Season Tracker</div>'
        '<div class="tracker-wrap">'
        '<div class="chart-subtitle">Standings (Rank)</div>'
        + rank_svg +
        '<div class="chart-subtitle" style="margin-top:32px">Total Home Runs</div>'
        + hr_svg +
        '</div></div>'
    )
 
 
def _rank_chart(snapshots, participants, n, n_weeks, color_map):
    ml, mr, mt, mb = 44, 160, 20, 44
    inner_w = max(360, n_weeks * 90)
    inner_h = 220
    svg_w   = inner_w + ml + mr
    svg_h   = inner_h + mt + mb
 
    def x_pos(i):
        return inner_w / 2 if n_weeks == 1 else i * inner_w / (n_weeks - 1)
 
    def y_pos(rank):
        return 0.0 if n == 1 else (rank - 1) * inner_h / (n - 1)
 
    # Grid lines
    grid = ""
    for rank in range(1, n + 1):
        y       = y_pos(rank)
        ordinal = {1: "1st", 2: "2nd", 3: "3rd"}.get(rank, f"{rank}th")
        grid += (
            f'<line x1="0" y1="{y:.1f}" x2="{inner_w}" y2="{y:.1f}" '
            f'stroke="#1e2d3d" stroke-width="1"/>'
            f'<text x="-8" y="{y + 4:.1f}" text-anchor="end" '
            f'fill="#3a5570" font-size="11">{ordinal}</text>'
        )
 
    # X axis labels
    x_labels = ""
    for i, snap in enumerate(snapshots):
        x = x_pos(i)
        try:
            d     = datetime.strptime(snap["week_start"], "%Y-%m-%d")
            label = d.strftime("%b %-d")
        except Exception:
            label = snap["week_start"]
        x_labels += (
            f'<text x="{x:.1f}" y="{inner_h + 28:.1f}" '
            f'text-anchor="middle" fill="#3a5570" font-size="10">{label}</text>'
        )
 
    # Lines, dots, and endpoint labels
    series = ""
    for pi, name in enumerate(participants):
        color  = color_map.get(name, TEAM_COLORS[pi % len(TEAM_COLORS)])
        points = []
        for i, snap in enumerate(snapshots):
            if name in snap["standings"]:
                rank  = snap["standings"][name]["rank"]
                total = snap["standings"][name]["total"]
                points.append((x_pos(i), y_pos(rank), rank, total))
 
        if not points:
            continue
 
        if len(points) > 1:
            path_d = " ".join(
                f"{{'M' if j == 0 else 'L'}}{x:.1f},{y:.1f}"
                for j, (x, y, _, _) in enumerate(points)
            )
            series += (
                f'<path d="{path_d}" stroke="{color}" stroke-width="2.5" '
                f'fill="none" stroke-linejoin="round" stroke-linecap="round"/>'
            )
 
        for x, y, rank, total in points:
            ordinal = {1: "1st", 2: "2nd", 3: "3rd"}.get(rank, f"{rank}th")
            series += (
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" '
                f'fill="{color}" stroke="#0f1923" stroke-width="2">'
                f'<title>{name}: {ordinal} ({total} HR)</title>'
                f'</circle>'
            )
 
        # Label at most recent point
        if points:
            lx, ly, lrank, ltotal = points[-1]
            ordinal = {1: "1st", 2: "2nd", 3: "3rd"}.get(lrank, f"{lrank}th")
            series += (
                f'<text x="{lx + 10:.1f}" y="{ly + 4:.1f}" '
                f'fill="{color}" font-size="10" font-weight="600">'
                f'{name} ({ltotal} HR)</text>'
            )
 
    svg = (
        f'<svg viewBox="0 0 {svg_w} {svg_h}" xmlns="http://www.w3.org/2000/svg" '
        f'style="width:100%;max-width:{svg_w}px;display:block;">'
        f'<g transform="translate({ml},{mt})">'
        f'{grid}{x_labels}{series}'
        f'</g></svg>'
    )
    return svg
 
 
def _hr_chart(snapshots, participants, n, n_weeks, color_map):
    ml, mr, mt, mb = 50, 160, 20, 44
    inner_w = max(360, n_weeks * 90)
    inner_h = 220
    svg_w   = inner_w + ml + mr
    svg_h   = inner_h + mt + mb
 
    # Determine Y max
    all_totals = [
        data["total"]
        for snap in snapshots
        for data in snap["standings"].values()
    ]
    raw_max = max(all_totals) if all_totals else 10
    y_max   = max(10, ((raw_max // 10) + 1) * 10)
 
    def x_pos(i):
        return inner_w / 2 if n_weeks == 1 else i * inner_w / (n_weeks - 1)
 
    def y_pos(total):
        # 0 at bottom (inner_h), y_max at top (0)
        return inner_h - (total / y_max) * inner_h
 
    # Grid lines at 0, mid, max
    grid = ""
    for hr_val in [0, y_max // 2, y_max]:
        y = y_pos(hr_val)
        grid += (
            f'<line x1="0" y1="{y:.1f}" x2="{inner_w}" y2="{y:.1f}" '
            f'stroke="#1e2d3d" stroke-width="1"/>'
            f'<text x="-8" y="{y + 4:.1f}" text-anchor="end" '
            f'fill="#3a5570" font-size="11">{hr_val}</text>'
        )
 
    # X axis labels
    x_labels = ""
    for i, snap in enumerate(snapshots):
        x = x_pos(i)
        try:
            d     = datetime.strptime(snap["week_start"], "%Y-%m-%d")
            label = d.strftime("%b %-d")
        except Exception:
            label = snap["week_start"]
        x_labels += (
            f'<text x="{x:.1f}" y="{inner_h + 28:.1f}" '
            f'text-anchor="middle" fill="#3a5570" font-size="10">{label}</text>'
        )
 
    # Lines, dots, and endpoint labels
    series = ""
    for pi, name in enumerate(participants):
        color  = color_map.get(name, TEAM_COLORS[pi % len(TEAM_COLORS)])
        points = []
        for i, snap in enumerate(snapshots):
            if name in snap["standings"]:
                total = snap["standings"][name]["total"]
                points.append((x_pos(i), y_pos(total), total))
 
        if not points:
            continue
 
        if len(points) > 1:
            path_d = " ".join(
                f"{{'M' if j == 0 else 'L'}}{x:.1f},{y:.1f}"
                for j, (x, y, _) in enumerate(points)
            )
            series += (
                f'<path d="{path_d}" stroke="{color}" stroke-width="2.5" '
                f'fill="none" stroke-linejoin="round" stroke-linecap="round"/>'
            )
 
        for x, y, total in points:
            series += (
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" '
                f'fill="{color}" stroke="#0f1923" stroke-width="2">'
                f'<title>{name}: {total} HR</title>'
                f'</circle>'
            )
 
        # Label at most recent point
        if points:
            lx, ly, ltotal = points[-1]
            series += (
                f'<text x="{lx + 10:.1f}" y="{ly + 4:.1f}" '
                f'fill="{color}" font-size="10" font-weight="600">'
                f'{name} ({ltotal} HR)</text>'
            )
 
    svg = (
        f'<svg viewBox="0 0 {svg_w} {svg_h}" xmlns="http://www.w3.org/2000/svg" '
        f'style="width:100%;max-width:{svg_w}px;display:block;">'
        f'<g transform="translate({ml},{mt})">'
        f'{grid}{x_labels}{series}'
        f'</g></svg>'
    )
    return svg
 
 
 
if __name__ == "__main__":
    main()
 
