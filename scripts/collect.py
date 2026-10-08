"""Collect GitHub traffic stats for every public repo owned by a user.

GitHub only keeps 14 days of traffic, so this runs daily and merges each
day's numbers into data/traffic.json to build a permanent history. New repos
are picked up automatically because the repo list is fetched on every run.

Env:
  GH_TOKEN   token with read access to repo administration (traffic) data
  GH_OWNER   account to track (default: Eesterlein)
"""

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

OWNER = os.environ.get("GH_OWNER", "Eesterlein")
TOKEN = os.environ.get("GH_TOKEN")
DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "traffic.json"
API = "https://api.github.com"


def get(path):
    req = urllib.request.Request(
        API + path,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "repo-traffic-dashboard",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def list_repos():
    repos, page = [], 1
    while True:
        batch = get(f"/user/repos?affiliation=owner&visibility=public&per_page=100&page={page}")
        repos += [r for r in batch if r["owner"]["login"].lower() == OWNER.lower()]
        if len(batch) < 100:
            return repos
        page += 1


def merge_daily(existing, rows, total_key, unique_key):
    """Fold the API's 14-day daily rows into the stored history.

    Recent days can still be revised by GitHub, so the newer value wins.
    """
    for row in rows:
        day = row["timestamp"][:10]
        entry = existing.setdefault(day, {})
        entry[total_key] = row["count"]
        entry[unique_key] = row["uniques"]


def main():
    if not TOKEN:
        sys.exit("GH_TOKEN is not set")

    data = json.loads(DATA_FILE.read_text()) if DATA_FILE.exists() else {"repos": {}}
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    failures = []

    for r in list_repos():
        name = r["name"]
        stored = data["repos"].setdefault(name, {"daily": {}, "first_tracked": now[:10]})
        stored["meta"] = {
            "description": r["description"] or "",
            "url": r["html_url"],
            "homepage": r["homepage"] or "",
            "pages": r["has_pages"],
            "language": r["language"] or "",
            "stars": r["stargazers_count"],
            "forks": r["forks_count"],
            "watchers": r["subscribers_count"] if "subscribers_count" in r else r["watchers_count"],
            "archived": r["archived"],
            "fork": r["fork"],
            "created": r["created_at"][:10],
            "pushed": (r["pushed_at"] or "")[:10],
            "size_kb": r["size"],
        }
        try:
            views = get(f"/repos/{OWNER}/{name}/traffic/views")
            clones = get(f"/repos/{OWNER}/{name}/traffic/clones")
            referrers = get(f"/repos/{OWNER}/{name}/traffic/popular/referrers")
            paths = get(f"/repos/{OWNER}/{name}/traffic/popular/paths")
        except urllib.error.HTTPError as e:
            failures.append(f"{name}: HTTP {e.code}")
            continue

        merge_daily(stored["daily"], views["views"], "v", "vu")
        merge_daily(stored["daily"], clones["clones"], "c", "cu")
        stored["last14"] = {
            "views": views["count"], "visitors": views["uniques"],
            "clones": clones["count"], "cloners": clones["uniques"],
        }
        stored["referrers"] = referrers
        stored["paths"] = [
            {"path": p["path"], "title": p["title"], "count": p["count"], "uniques": p["uniques"]}
            for p in paths
        ]
        stored["updated"] = now

    data["owner"] = OWNER
    data["collected_at"] = now
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n")

    print(f"Collected {len(data['repos'])} repos at {now}")
    if failures:
        print("Failed:", *failures, sep="\n  ")
        sys.exit(1)


if __name__ == "__main__":
    main()
