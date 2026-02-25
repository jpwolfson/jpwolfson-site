#!/usr/bin/env python3
"""
WordPress.com Stats Exporter for jpwolfson.com
No external dependencies — uses only Python stdlib.

Run:  python3 export-wp-stats.py
Output directory: wp_stats_export/
  - raw_*.json         Raw API responses (future-proof archive)
  - daily_visits.csv   Date, Views, Visitors
  - top_posts.csv      Title, URL, Views
  - referrers.csv      Source, Visits
  - countries.csv      Country, Views
  - search_terms.csv   Term, Views
  - clicks.csv         URL, Clicks
  - dashboard.html     Interactive dashboard (open in any browser)

After running, revoke the token at:
  https://wordpress.com/me/security/connected-applications
"""

import urllib.request
import urllib.parse
import json
import csv
import html as html_module
import datetime
import time
import sys
import os

SITE = "46389591"
API  = f"https://public-api.wordpress.com/rest/v1.1/sites/{SITE}"
OUT_DIR = "wp_stats_export"

TOKEN = None


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def get_token():
    print("Paste your WordPress.com API token and press Enter:")
    t = input().strip()
    if not t:
        print("No token entered. Exiting.")
        sys.exit(1)
    return t


def get(path, params=None):
    url = API + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {TOKEN}"})
    label = path[:60] + ("..." if len(path) > 60 else "")
    print(f"  {label}", end="", flush=True)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode())
            print(" OK")
            return data
    except Exception as e:
        print(f" FAILED ({e})")
        return None


# ---------------------------------------------------------------------------
# Data fetchers — each returns parsed data AND saves raw JSON
# ---------------------------------------------------------------------------

def save_raw(name, data):
    path = os.path.join(OUT_DIR, f"raw_{name}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def fetch_visits():
    print("\nFetching daily visits (may take a minute)...")
    rows, seen, raw_pages = [], set(), []
    end = datetime.date.today()
    while True:
        d = get("/stats/visits", {"unit": "day", "quantity": 999,
                                   "date": end.isoformat()})
        if not d or not d.get("data"):
            break
        raw_pages.append(d)
        new = [r for r in d["data"] if r[0] not in seen]
        if not new:
            break
        for r in new:
            seen.add(r[0])
        rows = new + rows
        earliest = min(datetime.date.fromisoformat(r[0]) for r in new)
        end = earliest - datetime.timedelta(days=1)
        if end < datetime.date(2008, 1, 1):
            break
        time.sleep(0.3)
    save_raw("visits", raw_pages)
    return sorted(rows, key=lambda r: r[0])


def fetch_top_posts():
    print("\nFetching top posts/pages...")
    d = get("/stats/top-posts", {"period": "alltime", "num": 200})
    if d:
        save_raw("top_posts", d)
    if d and d.get("days"):
        key = list(d["days"].keys())[0]
        return d["days"][key].get("postviews", [])
    return []


def fetch_referrers():
    print("\nFetching referrers...")
    d = get("/stats/referrers", {"period": "alltime", "num": 200})
    if d:
        save_raw("referrers", d)
    if d and d.get("days"):
        key = list(d["days"].keys())[0]
        return d["days"][key].get("groups", [])
    return []


def fetch_countries():
    print("\nFetching countries...")
    d = get("/stats/country-views", {"period": "alltime", "num": 200})
    if d:
        save_raw("countries", d)
    if d and d.get("days"):
        key = list(d["days"].keys())[0]
        return d["days"][key].get("views", [])
    return []


def fetch_search_terms():
    print("\nFetching search terms...")
    d = get("/stats/search-terms", {"period": "alltime", "num": 200})
    if d:
        save_raw("search_terms", d)
    if d and d.get("days"):
        key = list(d["days"].keys())[0]
        return d["days"][key].get("search_terms", [])
    return []


def fetch_clicks():
    print("\nFetching outbound clicks...")
    d = get("/stats/clicks", {"period": "alltime", "num": 200})
    if d:
        save_raw("clicks", d)
    if d and d.get("days"):
        key = list(d["days"].keys())[0]
        return d["days"][key].get("clicks", [])
    return []


# ---------------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------------

def write_csv(filename, headers, rows):
    path = os.path.join(OUT_DIR, filename)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(headers)
        w.writerows(rows)
    print(f"  Saved {path} ({len(rows):,} rows)")


def export_csvs(visits, top_posts, referrers, countries, search_terms, clicks):
    print("\nExporting CSV files...")

    # Daily visits
    visit_rows = []
    for r in visits:
        date_str = r[0]
        views = r[1]
        visitors = r[2] if len(r) > 2 else 0
        visit_rows.append([date_str, views, visitors])
    write_csv("daily_visits.csv", ["Date", "Views", "Visitors"], visit_rows)

    # Top posts
    post_rows = [[p.get("title", ""), p.get("href", ""), p.get("views", 0)]
                 for p in top_posts]
    write_csv("top_posts.csv", ["Title", "URL", "Views"], post_rows)

    # Referrers
    ref_rows = [[r.get("name", ""), r.get("total", 0)] for r in referrers]
    write_csv("referrers.csv", ["Source", "Visits"], ref_rows)

    # Countries
    country_rows = [[c.get("country_full", ""), c.get("views", 0)]
                    for c in countries]
    write_csv("countries.csv", ["Country", "Views"], country_rows)

    # Search terms
    search_rows = [[s.get("term", ""), s.get("views", 0)]
                   for s in search_terms]
    write_csv("search_terms.csv", ["Term", "Views"], search_rows)

    # Clicks
    click_rows = [[c.get("url", ""), c.get("views", 0)] for c in clicks]
    write_csv("clicks.csv", ["URL", "Clicks"], click_rows)


# ---------------------------------------------------------------------------
# Interactive HTML dashboard
# ---------------------------------------------------------------------------

def esc(s):
    return html_module.escape(str(s) if s else "")


def build_dashboard(visits, top_posts, referrers, countries, search_terms, clicks):
    total_views = sum(r[1] for r in visits)
    total_visitors = sum(r[2] for r in visits) if visits and len(visits[0]) > 2 else 0
    first = visits[0][0] if visits else "?"
    last = visits[-1][0] if visits else "?"
    num_days = len(visits)

    # Prepare JSON data for Chart.js (embedded in the HTML)
    daily_labels = json.dumps([r[0] for r in visits])
    daily_views = json.dumps([r[1] for r in visits])
    daily_visitors = json.dumps([r[2] if len(r) > 2 else 0 for r in visits])

    # Monthly aggregation for the bar chart
    monthly = {}
    for r in visits:
        month = r[0][:7]
        if month not in monthly:
            monthly[month] = {"views": 0, "visitors": 0}
        monthly[month]["views"] += r[1]
        monthly[month]["visitors"] += r[2] if len(r) > 2 else 0
    months_sorted = sorted(monthly.keys())
    monthly_labels = json.dumps(months_sorted)
    monthly_views = json.dumps([monthly[m]["views"] for m in months_sorted])
    monthly_visitors = json.dumps([monthly[m]["visitors"] for m in months_sorted])

    # Yearly aggregation
    yearly = {}
    for r in visits:
        year = r[0][:4]
        if year not in yearly:
            yearly[year] = {"views": 0, "visitors": 0}
        yearly[year]["views"] += r[1]
        yearly[year]["visitors"] += r[2] if len(r) > 2 else 0
    years_sorted = sorted(yearly.keys())
    yearly_labels = json.dumps(years_sorted)
    yearly_views = json.dumps([yearly[y]["views"] for y in years_sorted])
    yearly_visitors = json.dumps([yearly[y]["visitors"] for y in years_sorted])

    # Table data
    def post_table_rows():
        rows = ""
        for p in top_posts:
            title = esc(p.get("title", "(untitled)"))
            href = esc(p.get("href", ""))
            views = p.get("views", 0)
            rows += (f'<tr><td><a href="{href}" target="_blank">{title}</a></td>'
                     f'<td class="num">{views:,}</td></tr>\n')
        return rows or '<tr><td colspan="2" class="muted">No data</td></tr>'

    def ref_table_rows():
        rows = ""
        for r in referrers:
            rows += (f'<tr><td>{esc(r.get("name", ""))}</td>'
                     f'<td class="num">{r.get("total", 0):,}</td></tr>\n')
        return rows or '<tr><td colspan="2" class="muted">No data</td></tr>'

    def country_table_rows():
        rows = ""
        for c in countries:
            rows += (f'<tr><td>{esc(c.get("country_full", ""))}</td>'
                     f'<td class="num">{c.get("views", 0):,}</td></tr>\n')
        return rows or '<tr><td colspan="2" class="muted">No data</td></tr>'

    def search_table_rows():
        rows = ""
        for s in search_terms:
            rows += (f'<tr><td>{esc(s.get("term", ""))}</td>'
                     f'<td class="num">{s.get("views", 0):,}</td></tr>\n')
        return rows or '<tr><td colspan="2" class="muted">No data</td></tr>'

    def click_table_rows():
        rows = ""
        for c in clicks:
            url = esc(c.get("url", ""))
            rows += (f'<tr><td><a href="{url}" target="_blank">{url}</a></td>'
                     f'<td class="num">{c.get("views", 0):,}</td></tr>\n')
        return rows or '<tr><td colspan="2" class="muted">No data</td></tr>'

    def daily_table_rows():
        rows = ""
        for r in reversed(visits):
            visitors = f'{r[2]:,}' if len(r) > 2 else "—"
            rows += (f'<tr><td>{esc(r[0])}</td>'
                     f'<td class="num">{r[1]:,}</td>'
                     f'<td class="num">{visitors}</td></tr>\n')
        return rows or '<tr><td colspan="3" class="muted">No data</td></tr>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>jpwolfson.com &mdash; Analytics Archive</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
<style>
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  background: #f1f5f9; color: #1e293b; padding: 2rem 1.5rem;
  max-width: 1200px; margin: 0 auto;
}}
h1 {{ font-size: 1.75rem; font-weight: 700; }}
.meta {{ color: #64748b; font-size: .875rem; margin: .35rem 0 2rem; }}
.cards {{ display: flex; flex-wrap: wrap; gap: 1rem; margin-bottom: 2rem; }}
.card {{
  background: #fff; border-radius: 12px; padding: 1.1rem 1.6rem;
  box-shadow: 0 1px 3px rgba(0,0,0,.08); min-width: 140px;
}}
.card .n {{ font-size: 2rem; font-weight: 700; color: #2563eb; line-height: 1; }}
.card .l {{
  font-size: .7rem; text-transform: uppercase; letter-spacing: .06em;
  color: #94a3b8; margin-top: .3rem;
}}
section {{
  background: #fff; border-radius: 12px;
  padding: 1.4rem 1.5rem; box-shadow: 0 1px 3px rgba(0,0,0,.08);
  margin-bottom: 1.5rem;
}}
h2 {{ font-size: 1rem; font-weight: 600; margin-bottom: 1rem; color: #0f172a; }}
.chart-controls {{
  display: flex; gap: .5rem; margin-bottom: 1rem; flex-wrap: wrap;
}}
.chart-controls button {{
  padding: .4rem .9rem; border: 1px solid #cbd5e1; border-radius: 6px;
  background: #fff; color: #475569; font-size: .8rem; cursor: pointer;
  transition: all .15s;
}}
.chart-controls button:hover {{ background: #f8fafc; }}
.chart-controls button.active {{
  background: #2563eb; color: #fff; border-color: #2563eb;
}}
.chart-container {{ position: relative; height: 350px; width: 100%; }}
table {{ width: 100%; border-collapse: collapse; font-size: .875rem; }}
th {{
  padding: .45rem .75rem; border-bottom: 2px solid #e2e8f0; color: #64748b;
  font-size: .7rem; text-transform: uppercase; letter-spacing: .06em;
  background: #f8fafc; text-align: left; position: sticky; top: 0;
  cursor: pointer;
}}
th:hover {{ background: #e2e8f0; }}
td {{ padding: .38rem .75rem; border-bottom: 1px solid #f1f5f9; }}
td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
tr:hover td {{ background: #f8fafc; }}
a {{ color: #2563eb; text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
.muted {{ color: #94a3b8; }}
.table-wrap {{
  max-height: 500px; overflow-y: auto; border: 1px solid #e2e8f0;
  border-radius: 8px;
}}
.search-box {{
  padding: .4rem .75rem; border: 1px solid #cbd5e1; border-radius: 6px;
  font-size: .8rem; width: 250px; margin-bottom: .75rem;
}}
.tab-nav {{ display: flex; gap: 0; margin-bottom: 0; }}
.tab-nav button {{
  padding: .6rem 1.2rem; border: 1px solid #cbd5e1; border-bottom: none;
  background: #f8fafc; color: #475569; font-size: .8rem; cursor: pointer;
  border-radius: 8px 8px 0 0; margin-right: -1px; transition: all .15s;
}}
.tab-nav button.active {{
  background: #fff; color: #0f172a; font-weight: 600;
  border-bottom: 1px solid #fff; position: relative; z-index: 1;
}}
.tab-content {{ display: none; }}
.tab-content.active {{ display: block; }}
</style>
</head>
<body>

<h1>jpwolfson.com &mdash; Analytics Archive</h1>
<p class="meta">
  Exported {datetime.date.today()}
  &nbsp;&middot;&nbsp; Data: {esc(first)} to {esc(last)}
  &nbsp;&middot;&nbsp; Source: WordPress.com Stats API
</p>

<!-- Summary cards -->
<div class="cards">
  <div class="card"><div class="n">{total_views:,}</div><div class="l">Total Views</div></div>
  <div class="card"><div class="n">{total_visitors:,}</div><div class="l">Total Visitors</div></div>
  <div class="card"><div class="n">{num_days:,}</div><div class="l">Days of Data</div></div>
  <div class="card"><div class="n">{len(top_posts)}</div><div class="l">Tracked Pages</div></div>
  <div class="card"><div class="n">{len(referrers)}</div><div class="l">Referral Sources</div></div>
  <div class="card"><div class="n">{len(countries)}</div><div class="l">Countries</div></div>
</div>

<!-- Traffic chart -->
<section>
  <h2>Traffic Over Time</h2>
  <div class="chart-controls">
    <button class="active" onclick="setGranularity('monthly')">Monthly</button>
    <button onclick="setGranularity('yearly')">Yearly</button>
    <button onclick="setGranularity('daily')">Daily</button>
  </div>
  <div class="chart-container">
    <canvas id="trafficChart"></canvas>
  </div>
</section>

<!-- Data tables as tabs -->
<section>
  <div class="tab-nav">
    <button class="active" onclick="showTab('posts')">Top Pages</button>
    <button onclick="showTab('referrers')">Referrers</button>
    <button onclick="showTab('countries')">Countries</button>
    <button onclick="showTab('search')">Search Terms</button>
    <button onclick="showTab('clicks')">Outbound Clicks</button>
    <button onclick="showTab('daily')">Daily Log</button>
  </div>

  <div id="tab-posts" class="tab-content active">
    <h2>Top Pages &amp; Posts (all time)</h2>
    <input type="text" class="search-box" placeholder="Filter pages..."
           oninput="filterTable(this, 'tbl-posts')">
    <div class="table-wrap">
      <table id="tbl-posts">
        <thead><tr><th onclick="sortTable('tbl-posts',0)">Page</th>
                    <th onclick="sortTable('tbl-posts',1)">Views</th></tr></thead>
        <tbody>{post_table_rows()}</tbody>
      </table>
    </div>
  </div>

  <div id="tab-referrers" class="tab-content">
    <h2>Top Referrers (all time)</h2>
    <input type="text" class="search-box" placeholder="Filter referrers..."
           oninput="filterTable(this, 'tbl-referrers')">
    <div class="table-wrap">
      <table id="tbl-referrers">
        <thead><tr><th onclick="sortTable('tbl-referrers',0)">Source</th>
                    <th onclick="sortTable('tbl-referrers',1)">Visits</th></tr></thead>
        <tbody>{ref_table_rows()}</tbody>
      </table>
    </div>
  </div>

  <div id="tab-countries" class="tab-content">
    <h2>Top Countries (all time)</h2>
    <input type="text" class="search-box" placeholder="Filter countries..."
           oninput="filterTable(this, 'tbl-countries')">
    <div class="table-wrap">
      <table id="tbl-countries">
        <thead><tr><th onclick="sortTable('tbl-countries',0)">Country</th>
                    <th onclick="sortTable('tbl-countries',1)">Views</th></tr></thead>
        <tbody>{country_table_rows()}</tbody>
      </table>
    </div>
  </div>

  <div id="tab-search" class="tab-content">
    <h2>Search Terms (all time)</h2>
    <input type="text" class="search-box" placeholder="Filter terms..."
           oninput="filterTable(this, 'tbl-search')">
    <div class="table-wrap">
      <table id="tbl-search">
        <thead><tr><th onclick="sortTable('tbl-search',0)">Term</th>
                    <th onclick="sortTable('tbl-search',1)">Views</th></tr></thead>
        <tbody>{search_table_rows()}</tbody>
      </table>
    </div>
  </div>

  <div id="tab-clicks" class="tab-content">
    <h2>Outbound Clicks (all time)</h2>
    <input type="text" class="search-box" placeholder="Filter URLs..."
           oninput="filterTable(this, 'tbl-clicks')">
    <div class="table-wrap">
      <table id="tbl-clicks">
        <thead><tr><th onclick="sortTable('tbl-clicks',0)">URL</th>
                    <th onclick="sortTable('tbl-clicks',1)">Clicks</th></tr></thead>
        <tbody>{click_table_rows()}</tbody>
      </table>
    </div>
  </div>

  <div id="tab-daily" class="tab-content">
    <h2>Daily Visits (complete history)</h2>
    <input type="text" class="search-box" placeholder="Filter by date (e.g. 2024)..."
           oninput="filterTable(this, 'tbl-daily')">
    <div class="table-wrap">
      <table id="tbl-daily">
        <thead><tr><th onclick="sortTable('tbl-daily',0)">Date</th>
                    <th onclick="sortTable('tbl-daily',1)">Views</th>
                    <th onclick="sortTable('tbl-daily',2)">Visitors</th></tr></thead>
        <tbody>{daily_table_rows()}</tbody>
      </table>
    </div>
  </div>
</section>

<p class="meta" style="margin-top:2rem">
  Raw data files (JSON, CSV) are in the same directory as this file.
  <br>Revoke your API token:
  <a href="https://wordpress.com/me/security/connected-applications" target="_blank">
    wordpress.com/me/security/connected-applications</a>
</p>

<script>
// --- Chart data ---
const data = {{
  daily:   {{ labels: {daily_labels}, views: {daily_views}, visitors: {daily_visitors} }},
  monthly: {{ labels: {monthly_labels}, views: {monthly_views}, visitors: {monthly_visitors} }},
  yearly:  {{ labels: {yearly_labels}, views: {yearly_views}, visitors: {yearly_visitors} }}
}};

let chart = null;
let currentGranularity = 'monthly';

function createChart(granularity) {{
  const ctx = document.getElementById('trafficChart').getContext('2d');
  const d = data[granularity];
  const chartType = granularity === 'yearly' ? 'bar' : 'bar';

  if (chart) chart.destroy();

  chart = new Chart(ctx, {{
    type: chartType,
    data: {{
      labels: d.labels,
      datasets: [
        {{
          label: 'Views',
          data: d.views,
          backgroundColor: 'rgba(37, 99, 235, 0.7)',
          borderColor: 'rgba(37, 99, 235, 1)',
          borderWidth: 1,
          borderRadius: granularity === 'daily' ? 0 : 4,
        }},
        {{
          label: 'Visitors',
          data: d.visitors,
          backgroundColor: 'rgba(16, 185, 129, 0.5)',
          borderColor: 'rgba(16, 185, 129, 1)',
          borderWidth: 1,
          borderRadius: granularity === 'daily' ? 0 : 4,
        }}
      ]
    }},
    options: {{
      responsive: true,
      maintainAspectRatio: false,
      interaction: {{ mode: 'index', intersect: false }},
      plugins: {{
        tooltip: {{
          callbacks: {{
            label: function(ctx) {{
              return ctx.dataset.label + ': ' + ctx.parsed.y.toLocaleString();
            }}
          }}
        }},
        legend: {{ position: 'top' }}
      }},
      scales: {{
        x: {{
          ticks: {{
            maxTicksLimit: granularity === 'daily' ? 20 : (granularity === 'monthly' ? 30 : 20),
            maxRotation: 45,
          }},
          grid: {{ display: false }}
        }},
        y: {{
          beginAtZero: true,
          ticks: {{
            callback: function(v) {{ return v.toLocaleString(); }}
          }}
        }}
      }}
    }}
  }});
}}

function setGranularity(g) {{
  currentGranularity = g;
  document.querySelectorAll('.chart-controls button').forEach(b => b.classList.remove('active'));
  event.target.classList.add('active');
  createChart(g);
}}

// --- Tab navigation ---
function showTab(name) {{
  document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.tab-nav button').forEach(el => el.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('active');
  event.target.classList.add('active');
}}

// --- Table filtering ---
function filterTable(input, tableId) {{
  const filter = input.value.toLowerCase();
  const rows = document.getElementById(tableId).querySelectorAll('tbody tr');
  rows.forEach(row => {{
    const text = row.textContent.toLowerCase();
    row.style.display = text.includes(filter) ? '' : 'none';
  }});
}}

// --- Table sorting ---
const sortState = {{}};
function sortTable(tableId, colIndex) {{
  const table = document.getElementById(tableId);
  const tbody = table.querySelector('tbody');
  const rows = Array.from(tbody.querySelectorAll('tr'));
  const key = tableId + '-' + colIndex;
  sortState[key] = !sortState[key]; // toggle asc/desc

  rows.sort((a, b) => {{
    let aVal = a.cells[colIndex]?.textContent.trim() || '';
    let bVal = b.cells[colIndex]?.textContent.trim() || '';
    // Try numeric comparison (strip commas)
    const aNum = parseFloat(aVal.replace(/,/g, ''));
    const bNum = parseFloat(bVal.replace(/,/g, ''));
    if (!isNaN(aNum) && !isNaN(bNum)) {{
      return sortState[key] ? aNum - bNum : bNum - aNum;
    }}
    return sortState[key]
      ? aVal.localeCompare(bVal)
      : bVal.localeCompare(aVal);
  }});

  rows.forEach(row => tbody.appendChild(row));
}}

// Initialize chart on load
createChart('monthly');
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    global TOKEN
    print("=" * 55)
    print("  WordPress.com Stats Exporter")
    print("  site: jpwolfson.com")
    print("=" * 55)
    print()
    print("Output directory:", OUT_DIR)
    print("  - Raw JSON files  (complete API responses)")
    print("  - CSV files       (structured, importable)")
    print("  - dashboard.html  (interactive charts)")
    print()

    TOKEN = get_token()

    os.makedirs(OUT_DIR, exist_ok=True)

    # Fetch all data
    visits       = fetch_visits()
    top_posts    = fetch_top_posts()
    referrers    = fetch_referrers()
    countries    = fetch_countries()
    search_terms = fetch_search_terms()
    clicks       = fetch_clicks()

    # Export CSVs
    export_csvs(visits, top_posts, referrers, countries, search_terms, clicks)

    # Build interactive dashboard
    dashboard_path = os.path.join(OUT_DIR, "dashboard.html")
    print(f"\nBuilding interactive dashboard ({len(visits):,} days of data)...")
    with open(dashboard_path, "w", encoding="utf-8") as f:
        f.write(build_dashboard(visits, top_posts, referrers, countries,
                                search_terms, clicks))
    print(f"  Saved {dashboard_path}")

    # Summary
    print()
    print("=" * 55)
    print(f"  Export complete!")
    print(f"  {len(visits):,} days of traffic data archived.")
    print(f"  Open {dashboard_path} in any browser.")
    print("=" * 55)
    print()
    print("Files saved:")
    for f in sorted(os.listdir(OUT_DIR)):
        size = os.path.getsize(os.path.join(OUT_DIR, f))
        print(f"  {f:30s} {size:>10,} bytes")
    print()
    print("Next steps:")
    print("  1. Open dashboard.html in your browser")
    print("  2. Verify the data looks complete")
    print("  3. Revoke your API token:")
    print("     https://wordpress.com/me/security/connected-applications")


if __name__ == "__main__":
    main()
