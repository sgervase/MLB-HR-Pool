"""
One-time backfill: rebuild history.json from the git history of index.html.

Walks every commit that touched index.html, groups them into ISO calendar
weeks (Monday-start, matching fetch_stats.py's save_weekly_snapshot logic),
picks the LAST commit in each week as that week's snapshot, parses out each
team's total HR + rank from the rendered ball-cards, and writes history.json.

Run this from inside a full (non-shallow) clone or mirror of the repo, e.g.:
    git clone https://github.com/sgervase/MLB-HR-Pool.git
    cd MLB-HR-Pool
    python backfill_history.py
"""

import json
import re
import subprocess
from datetime import datetime, timedelta

# Old/renamed team names -> current canonical name (from config.json history)
NAME_ALIASES = {
    "Hentai should not be criminalized": "H.S.N.B.C",
    "Hsnbc": "H.S.N.B.C",
}

# Names to skip entirely (placeholder/template data from before the pool was set up)
PLACEHOLDER_NAMES = {"Alice", "Bob", "You"}

CARD_RE = re.compile(
    r'card-owner">([^<]*)<.*?total-num">(\d+)<',
    re.DOTALL,
)


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, check=True).stdout


def get_commits():
    """Return list of (commit_hash, datetime) for every commit touching index.html, oldest first."""
    out = run(["git", "log", "--follow", "--format=%H|%ad", "--date=iso-strict", "--", "index.html"])
    commits = []
    for line in out.strip().splitlines():
        h, d = line.split("|", 1)
        commits.append((h, datetime.fromisoformat(d)))
    commits.reverse()  # oldest first
    return commits


def parse_standings(html):
    """Extract {name: total} from the ball-cards in a rendered index.html."""
    standings = {}
    for name, total in CARD_RE.findall(html):
        name = name.strip()
        if name in PLACEHOLDER_NAMES:
            continue
        name = NAME_ALIASES.get(name, name)
        standings[name] = int(total)
    return standings


def week_start_of(dt):
    d = dt.date()
    return d - timedelta(days=d.weekday())


def main():
    commits = get_commits()
    print(f"Found {len(commits)} commits touching index.html")

    # Group commits by ISO week, keep the LAST commit per week
    by_week = {}
    for h, dt in commits:
        wk = week_start_of(dt)
        by_week[wk] = (h, dt)  # overwritten each time -> ends up as last commit in week

    snapshots = []
    skipped = []
    for wk in sorted(by_week):
        h, dt = by_week[wk]
        html = run(["git", "show", f"{h}:index.html"])
        standings = parse_standings(html)
        if not standings:
            skipped.append((wk, h))
            continue

        ranked = sorted(standings.items(), key=lambda kv: (-kv[1], kv[0]))
        snapshots.append({
            "week_start": wk.strftime("%Y-%m-%d"),
            "date": dt.strftime("%Y-%m-%d"),
            "standings": {
                name: {"total": total, "rank": i + 1}
                for i, (name, total) in enumerate(ranked)
            },
        })
        print(f"  {wk} (commit {h[:8]}, {dt.date()}): " +
              ", ".join(f"{n}={t['total']}" for n, t in snapshots[-1]["standings"].items()))

    if skipped:
        print(f"\nSkipped {len(skipped)} week(s) with no parsable standings (likely placeholder-only weeks):")
        for wk, h in skipped:
            print(f"  {wk} (commit {h[:8]})")

    history = {"snapshots": snapshots}
    with open("history.json", "w") as f:
        json.dump(history, f, indent=2)
    print(f"\nWrote history.json with {len(snapshots)} weekly snapshots.")


if __name__ == "__main__":
    main()
