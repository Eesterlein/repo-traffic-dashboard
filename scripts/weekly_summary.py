"""Write a Markdown summary of the last 7 complete days of traffic.

Compares against the 7 days before, lists the top repos, referrers and
popular pages, and lists repos created this week.
Prints the issue title on the first line and the body after it.
"""

import json
import os
from datetime import date, timedelta
from pathlib import Path

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "traffic.json"
DASHBOARD = "https://eesterlein.github.io/repo-traffic-dashboard/"
OWNER = os.environ.get("GH_OWNER", "Eesterlein")


def days(end, n):
    return {(end - timedelta(days=i)).isoformat() for i in range(n)}


def totals(repo, window):
    t = {"v": 0, "vu": 0, "c": 0, "cu": 0}
    for d, row in repo["daily"].items():
        if d in window:
            for k in t:
                t[k] += row.get(k, 0)
    return t


def change(now, before):
    if before == 0:
        return "up from 0" if now else "–"
    pct = round((now - before) / before * 100)
    return f"{'+' if pct >= 0 else ''}{pct}%"


def fmt_day(d):
    return date.fromisoformat(d).strftime("%b %-d")


def main():
    data = json.loads(DATA_FILE.read_text())
    repos = {n: r for n, r in data["repos"].items()
             if not (r["meta"]["archived"] or r["meta"]["fork"])}

    # GitHub days are UTC; today is still partial, so the week ends yesterday.
    end = date.fromisoformat(data["collected_at"][:10]) - timedelta(days=1)
    this_week, last_week = days(end, 7), days(end - timedelta(days=7), 7)
    start = end - timedelta(days=6)

    rows = []
    for name, r in repos.items():
        now, before = totals(r, this_week), totals(r, last_week)
        rows.append((name, r, now, before))

    def total(which, k):
        return sum(x[which][k] for x in ({"now": n, "before": b} for _, _, n, b in rows))

    v, v0 = total("now", "v"), total("before", "v")
    vu, vu0 = total("now", "vu"), total("before", "vu")
    c, c0 = total("now", "c"), total("before", "c")

    title = f"Weekly traffic summary: {fmt_day(start.isoformat())} – {fmt_day(end.isoformat())}, {end.year}"
    out = [
        f"@{OWNER} here's your GitHub traffic for **{fmt_day(start.isoformat())} – {fmt_day(end.isoformat())}**, "
        f"compared with the week before. [Open the dashboard]({DASHBOARD})",
        "",
        "| | This week | Last week | Change |",
        "|---|---:|---:|---:|",
        f"| Page views | {v} | {v0} | {change(v, v0)} |",
        f"| Unique visitors (per repo per day) | {vu} | {vu0} | {change(vu, vu0)} |",
        f"| Clones (mostly bots and builds) | {c} | {c0} | {change(c, c0)} |",
        "",
    ]

    viewed = sorted((x for x in rows if x[2]["v"]), key=lambda x: -x[2]["v"])[:5]
    out.append("### Most viewed repos")
    if viewed:
        out += [f"{i}. [{n}]({r['meta']['url']}): **{now['v']}** views, {now['vu']} unique "
                f"({change(now['v'], before['v'])} vs last week)"
                for i, (n, r, now, before) in enumerate(viewed, 1)]
    else:
        out.append("No page views this week.")
    out.append("")

    refs = {}
    for r in repos.values():
        for x in r.get("referrers", []):
            refs[x["referrer"]] = refs.get(x["referrer"], 0) + x["count"]
    out.append("### Where visitors came from (last 14 days)")
    if refs:
        out += [f"- {k}: {n} views" for k, n in sorted(refs.items(), key=lambda kv: -kv[1])[:5]]
    else:
        out.append("No referrals.")
    out.append("")

    paths = []
    for r in repos.values():
        paths += r.get("paths", [])
    paths.sort(key=lambda p: -p["count"])
    out.append("### Most opened pages (last 14 days)")
    if paths:
        out += [f"- `{p['path'].replace(f'/{OWNER}/', '', 1)}`: {p['count']} views, {p['uniques']} unique"
                for p in paths[:5]]
    else:
        out.append("No page views.")

    new = sorted(n for n, r in repos.items() if r["meta"]["created"] >= start.isoformat())
    if new:
        out += ["", "### New repos this week (now on the dashboard)", *[f"- {n}" for n in new]]

    print(title)
    print("\n".join(out))


if __name__ == "__main__":
    main()
