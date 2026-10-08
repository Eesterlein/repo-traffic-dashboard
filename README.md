# Repo Traffic Dashboard

**Live dashboard: https://eesterlein.github.io/repo-traffic-dashboard/**

A single dashboard for views, unique visitors, clones, referrers and popular pages across all of my public GitHub repositories.

GitHub only keeps 14 days of traffic data per repo. A scheduled GitHub Action runs daily, pulls traffic for every public repo I own, and merges it into `data/traffic.json`, so history builds up over time. New repos are picked up automatically on the next run.

## How it works

- `scripts/collect.py` lists all public repos owned by the account and calls the GitHub traffic API for each one (views, clones, referrers, popular paths), then merges the daily numbers into `data/traffic.json`.
- `scripts/collect_sites.py` pulls visits to the live sites (portfolio and project pages) from GoatCounter into `data/sites.json`.
- `.github/workflows/collect.yml` runs both scripts every day and commits the updated data.
- `.github/workflows/weekly-summary.yml` posts a weekly summary as an issue every Monday morning, which GitHub emails to me.
- `index.html` is a static page (GitHub Pages) that reads `data/traffic.json` and renders the KPIs, charts and tables.

## Setup

1. Create a fine-grained personal access token with access to **All repositories** and the repository permission **Administration: Read-only** (Metadata: Read-only is added automatically).
2. Save it as a repository secret named `TRAFFIC_TOKEN`.
3. For live-site stats, create a GoatCounter API token with **Read statistics** and save it as `GOATCOUNTER_TOKEN`.
4. Enable GitHub Pages from the `main` branch, root folder.
5. Run the **Collect traffic** workflow once by hand (Actions tab, then Run workflow) to confirm it works.

## Notes on the numbers

- Unique counts are per repo per day, so one person visiting two repos, or on two days, is counted more than once.
- Clone counts include GitHub Pages builds, CI runs and crawlers. Page views are the better signal of real interest.
- Your own visits while logged in can show up in views.
