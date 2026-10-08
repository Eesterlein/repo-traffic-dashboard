"""Collect live-site visits from GoatCounter into data/sites.json.

Covers every page that loads the GoatCounter script (the portfolio and any
project sites under the same domain). Daily and hour-of-day per-page counts
(in the GoatCounter account's timezone) are merged into a permanent history;
referrers, countries and devices are a rolling 30-day snapshot because
GoatCounter only reports those as totals for a range.

Env:
  GOATCOUNTER_TOKEN  API token with "Read statistics"
  GOATCOUNTER_CODE   site code (default: eesterlein)
"""

import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

TOKEN = os.environ.get("GOATCOUNTER_TOKEN")
CODE = os.environ.get("GOATCOUNTER_CODE", "eesterlein")
API = f"https://{CODE}.goatcounter.com/api/v0"
DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "sites.json"

# GoatCounter's hits are counted visitors, not raw page loads.
HISTORY_DAYS = 14
SNAPSHOT_DAYS = 30


def get(path, **params):
    url = f"{API}/{path}?{urllib.parse.urlencode(params, doseq=True)}"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
        "User-Agent": "repo-traffic-dashboard",
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def stamp(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def all_hits(start, end):
    """Page through /stats/hits; GoatCounter returns at most 100 paths per call."""
    hits, seen = [], []
    while True:
        params = {"start": stamp(start), "end": stamp(end), "limit": 100}
        if seen:
            params["exclude_paths"] = seen
        page = get("stats/hits", **params)
        hits += page["hits"]
        seen += [h["path_id"] for h in page["hits"]]
        if not page.get("more") or not page["hits"]:
            return hits


def top(kind, start, end):
    page = get(f"stats/{kind}", start=stamp(start), end=stamp(end), limit=20)
    return [{"name": s["name"] or s["id"], "count": s["count"]} for s in page["stats"] if s["count"]]


def main():
    if not TOKEN:
        print("GOATCOUNTER_TOKEN not set; skipping live-site stats")
        return

    data = json.loads(DATA_FILE.read_text()) if DATA_FILE.exists() else {"pages": {}}
    now = datetime.now(timezone.utc)
    end = now.replace(hour=23, minute=59, second=59, microsecond=0)
    hist_start = (now - timedelta(days=HISTORY_DAYS - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
    snap_start = (now - timedelta(days=SNAPSHOT_DAYS - 1)).replace(hour=0, minute=0, second=0, microsecond=0)

    for h in all_hits(hist_start, end):
        page = data["pages"].setdefault(h["path"], {"daily": {}})
        page["title"] = h["title"]
        page["event"] = h["event"]
        hourly = page.setdefault("hourly", {})
        for day in h["stats"]:
            if day["daily"] or day["day"] in page["daily"]:
                page["daily"][day["day"]] = day["daily"]
            # Keep only the hours with visits, as {"hour": count}
            hours = {str(i): n for i, n in enumerate(day.get("hourly") or []) if n}
            if hours:
                hourly[day["day"]] = hours
            else:
                hourly.pop(day["day"], None)

    data["snapshot"] = {
        "start": snap_start.strftime("%Y-%m-%d"),
        "end": now.strftime("%Y-%m-%d"),
        "referrers": top("toprefs", snap_start, end),
        "countries": top("locations", snap_start, end),
        "browsers": top("browsers", snap_start, end),
        "systems": top("systems", snap_start, end),
        "sizes": top("sizes", snap_start, end),
    }
    try:
        settings = get("me")["user"].get("settings", {})
        data["timezone"] = settings.get("timezone") or data.get("timezone", "")
    except Exception:
        pass
    data["code"] = CODE
    data["collected_at"] = stamp(now)
    DATA_FILE.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n")
    print(f"Collected {len(data['pages'])} pages/events from GoatCounter at {stamp(now)}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # never block the GitHub collection
        print(f"GoatCounter collection failed: {e}", file=sys.stderr)
        sys.exit(1)
