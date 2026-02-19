#!/usr/bin/env python3
"""
WordPress.com Stats Exporter for jpwolfson.com
No external dependencies — uses only Python stdlib.

Run:  python3 export-wp-stats.py
Output: wp_stats_archive.html   (open in any browser)

After running, revoke the token at:
  https://wordpress.com/me/security/connected-applications
"""

import urllib.request
import urllib.parse
import json
import html as html_module
import datetime
import time
import sys

SITE = "46389591"
API  = f"https://public-api.wordpress.com/rest/v1.1/sites/{SITE}"

def get_token():
    print("Paste your WordPress.com API token and press Enter:")
    t = input().strip()
    if not t:
        print("No token entered. Exiting.")
        sys.exit(1)
    return t

TOKEN = None

def get(path, params=None):
    url = API + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {TOKEN}"})
    print(f"  {path[:60]}{'...' if len(path)>60 else ''}", end="", flush=True)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode())
            print(" OK")
            return data
    except Exception as e:
        print(f" FAILED ({e})")
        return None

def fetch_visits():
    print("\nFetching daily visits (may take a minute)...")
    rows, seen = [], set()
    end = datetime.date.today()
    while True:
        d = get("/stats/visits", {"unit": "day", "quantity": 999,
                                   "date": end.isoformat()})
        if not d or not d.get("data"):
            break
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
    return sorted(rows, key=lambda r: r[0])

def fetch_top_posts():
    print("\nFetching top posts/pages...")
    d = get("/stats/top-posts", {"period": "alltime", "num": 100})
    if d and d.get("days"):
        key = list(d["days"].keys())[0]
        return d["days"][key].get("postviews", [])
    return []

def fetch_referrers():
    print("\nFetching referrers...")
    d = get("/stats/referrers", {"period": "alltime", "num": 100})
    if d and d.get("days"):
        key = list(d["days"].keys())[0]
        return d["days"][key].get("groups", [])
    return []

def fetch_countries():
    print("\nFetching countries...")
    d = get("/stats/country-views", {"period": "alltime", "num": 100})
    if d and d.get("days"):
        key = list(d["days"].keys())[0]
        return d["days"][key].get("views", [])
    return []

def fetch_search_terms():
    print("\nFetching search terms...")
    d = get("/stats/search-terms", {"period": "alltime", "num": 100})
    if d and d.get("days"):
        key = list(d["days"].keys())[0]
        return d["days"][key].get("search_terms", [])
    return []

def fetch_clicks():
    print("\nFetching outbound clicks...")
    d = get("/stats/clicks", {"period": "alltime", "num": 50})
    if d and d.get("days"):
        key = list(d["days"].keys())[0]
        return d["days"][key].get("clicks", [])
    return []

def esc(s):
    return html_module.escape(str(s) if s else "")

def monthly_bar_chart(visits):
    monthly = {}
    for date_str, views, *_ in visits:
        month = date_str[:7]
        monthly[month] = monthly.get(month, 0) + views
    months = sorted(monthly.keys())
    if not months:
        return "<p>No data</p>"
    max_v = max(monthly.values())
    bw = max(3, min(14, 1100 // max(len(months), 1)))
    W  = len(months) * (bw + 1)
    H  = 140
    bars, labels = [], []
    for i, m in enumerate(months):
        h = int((monthly[m] / max_v) * H)
        x = i * (bw + 1)
        bars.append(
            f'<rect x="{x}" y="{H-h}" width="{bw}" height="{h}" '
            f'fill="#2563eb" opacity="0.85">'
            f'<title>{m}: {monthly[m]:,} views</title></rect>'
        )
        if m.endswith("-01"):
            labels.append(
                f'<text x="{x}" y="{H+14}" font-size="9" fill="#94a3b8">{m[:4]}</text>'
            )
    return (
        f'<div style="overflow-x:auto">'
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H+20}" '
        f'style="display:block">{"".join(bars)}{"".join(labels)}</svg></div>'
    )

def tbl(headers, rows, cols=None):
    aligns = cols or ["left"] * len(headers)
    th = "".join(
        f'<th style="text-align:{a};white-space:nowrap">{esc(h)}</th>'
        for h, a in zip(headers, aligns)
    )
    if not rows:
        return (f'<table><thead><tr>{th}</tr></thead><tbody>'
                f'<tr><td colspan="{len(headers)}" style="color:#94a3b8">'
                f'No data returned by API</td></tr></tbody></table>')
    body = ""
    for row in rows:
        body += "<tr>" + "".join(
            f'<td style="text-align:{a}">{c}</td>'
            for c, a in zip(row, aligns)
        ) + "</tr>"
    return f'<table><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table>'

def build_html(visits, top_posts, referrers, countries, search_terms, clicks):
    total_views    = sum(r[1] for r in visits)
    total_visitors = sum(r[2] for r in visits) if visits and len(visits[0]) > 2 else 0
    first = visits[0][0]  if visits else "?"
    last  = visits[-1][0] if visits else "?"

    post_rows = [
        [f'<a href="{esc(p.get("href",""))}" target="_blank">{esc(p.get("title","(untitled)"))}</a>',
         f'{p.get("views",0):,}']
        for p in top_posts[:60]
    ]
    ref_rows = [
        [esc(r.get("name","")), f'{r.get("total",0):,}']
        for r in referrers[:60]
    ]
    country_rows = [
        [esc(c.get("country_full","")), f'{c.get("views",0):,}']
        for c in countries[:60]
    ]
    search_rows = [
        [esc(s.get("term","")), f'{s.get("views",0):,}']
        for s in search_terms[:60]
    ]
    click_rows = [
        [f'<a href="{esc(c.get("url",""))}" target="_blank">{esc(c.get("url",""))}</a>',
         f'{c.get("views",0):,}']
        for c in clicks[:40]
    ]
    daily_rows = [
        [esc(r[0]), f'{r[1]:,}', f'{r[2]:,}' if len(r) > 2 else "—"]
        for r in reversed(visits[-365:])
    ]

    css = """
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
           background: #f1f5f9; color: #1e293b; padding: 2rem 1.5rem; }
    h1   { font-size: 1.75rem; font-weight: 700; }
    .meta { color: #64748b; font-size: .875rem; margin: .35rem 0 2rem; }
    .cards { display: flex; flex-wrap: wrap; gap: 1rem; margin-bottom: 2rem; }
    .card  { background: #fff; border-radius: 12px; padding: 1.1rem 1.6rem;
             box-shadow: 0 1px 3px rgba(0,0,0,.08); }
    .card .n { font-size: 2rem; font-weight: 700; color: #2563eb; line-height: 1; }
    .card .l { font-size: .7rem; text-transform: uppercase; letter-spacing: .06em;
               color: #94a3b8; margin-top: .3rem; }
    section { background: #fff; border-radius: 12px;
              padding: 1.4rem 1.5rem; box-shadow: 0 1px 3px rgba(0,0,0,.08);
              margin-bottom: 1.5rem; }
    h2 { font-size: 1rem; font-weight: 600; margin-bottom: 1rem; color: #0f172a; }
    table { width: 100%; border-collapse: collapse; font-size: .875rem; }
    th { padding: .45rem .75rem; border-bottom: 2px solid #e2e8f0; color: #64748b;
         font-size: .7rem; text-transform: uppercase; letter-spacing: .06em;
         background: #f8fafc; }
    td { padding: .38rem .75rem; border-bottom: 1px solid #f1f5f9; }
    tr:hover td { background: #f8fafc; }
    a  { color: #2563eb; text-decoration: none; }
    a:hover { text-decoration: underline; }
    """

    chart = monthly_bar_chart(visits)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>jpwolfson.com — Analytics Archive</title>
<style>{css}</style>
</head>
<body>
<h1>jpwolfson.com — Analytics Archive</h1>
<p class="meta">Exported {datetime.date.today()} &nbsp;·&nbsp; Data: {esc(first)} to {esc(last)}</p>
<div class="cards">
  <div class="card"><div class="n">{total_views:,}</div><div class="l">Total Views</div></div>
  <div class="card"><div class="n">{total_visitors:,}</div><div class="l">Unique Visitors</div></div>
  <div class="card"><div class="n">{len(visits):,}</div><div class="l">Days of Data</div></div>
  <div class="card"><div class="n">{len(top_posts)}</div><div class="l">Tracked Pages</div></div>
</div>
<section><h2>Traffic Over Time (monthly)</h2>{chart}</section>
<section><h2>Top Pages &amp; Posts (all time)</h2>{tbl(["Page","Views"],post_rows,["left","right"])}</section>
<section><h2>Top Referrers (all time)</h2>{tbl(["Source","Visits"],ref_rows,["left","right"])}</section>
<section><h2>Top Countries (all time)</h2>{tbl(["Country","Views"],country_rows,["left","right"])}</section>
<section><h2>Top Search Terms (all time)</h2>{tbl(["Term","Views"],search_rows,["left","right"])}</section>
<section><h2>Top Outbound Clicks (all time)</h2>{tbl(["URL","Clicks"],click_rows,["left","right"])}</section>
<section><h2>Daily Visits (most recent 365 days)</h2>{tbl(["Date","Views","Visitors"],daily_rows,["left","right","right"])}</section>
</body>
</html>"""

def main():
    global TOKEN
    print("=" * 50)
    print("  WordPress.com Stats Exporter")
    print("  site: jpwolfson.com")
    print("=" * 50)
    TOKEN = get_token()

    visits       = fetch_visits()
    top_posts    = fetch_top_posts()
    referrers    = fetch_referrers()
    countries    = fetch_countries()
    search_terms = fetch_search_terms()
    clicks       = fetch_clicks()

    out_file = "wp_stats_archive.html"
    print(f"\nBuilding report ({len(visits):,} days of data)...")
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(build_html(visits, top_posts, referrers, countries, search_terms, clicks))

    print(f"\nDone! Saved: {out_file}")
    print("Open it in any browser.")
    print("\nRevoke the token when done:")
    print("  https://wordpress.com/me/security/connected-applications")

if __name__ == "__main__":
    main()
