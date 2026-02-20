#!/usr/bin/env python3
"""
Phase 2 patch — applies human-verified link findings to link_audit.json.
Run once after manual audit; idempotent.
"""
import json
from pathlib import Path

DATA = Path("link_audit.json")

# ── confirmed broken, no replacement known ────────────────────────────────────
CONFIRMED_BROKEN = [
    "https://users.cs.duke.edu/~edels/Papers/2008-B-02-PersistentHomology.pdf",
    "https://authors.elsevier.com/c/1in5y4~FPITzK",
    "https://sites.math.northwestern.edu/~baharacu/geometry-physics-seminar.html",
    "https://www.math.ias.edu/calendar/event/148370/1575568800/1575572100",
    "http://dept.math.lsa.umich.edu/seminars_events/events_detail.php?id=5835",
    "http://www.math.harvard.edu/cgi-bin/showtalk.pl",
    "https://www.math.uci.edu/node/25149",
    "https://www.math.ubc.ca/Dept/Events/index.shtml?period=2017-11&series=all",
    "http://www-app.uni-regensburg.de/Fakultaeten/MAT/sfb-higher-invariants/index.php/MAG2017",
    "https://www.math.uci.edu/node/24488",
    "http://events.wayne.edu/mathematics/2016/02/22/mathematics-colloquium-jesse-wolfson-60855/",
    "https://sites.google.com/site/2015summerinstitute/home/schedule/week-3-abstracts#JW",
    "http://math.uchicago.edu/~algtop/midwest/",
    "http://sym.math.ku.dk/calendar/index.cgi?action=show_event;relmonth=0;id=2753",
    "http://www.math.northwestern.edu/~mcouch/index.html",
    "http://www.math.northwestern.edu/news/calendar/list.cgi?seminar=Topology%20Seminar",
    "http://www.institut.math.jussieu.fr/projets/aa/",
    "http://www.maths.ox.ac.uk/events/seminars/upcoming/P10Y1D/4/945",
    "http://www.math.ubc.ca/Dept/Events/index.shtml?period=past&series=3",
    "http://media.scgp.stonybrook.edu/video/video.php?f=20120305_5_qtp.mp4",
    "http://math.mit.edu/conferences/talbot/index.php?year=2011",
    "http://math.mit.edu/conferences/talbot/index.php?year=2010",
    "https://www.isaacnewton.ac.uk/programmes/GDO/Wolfson.pdf",
    "http://www.matem.unam.mx/lozano/jornadas.html",
    "http://math.uchicago.edu/~ronno/rtg2018/",
]

# ── confirmed working despite sandbox block ───────────────────────────────────
CONFIRMED_OK = [
    "https://scholar.google.com/citations?user=AJKrw6YAAAAJ&hl=en",
]

# ── link works but URL should be updated (no fix yet, flagged for phase 3) ───
NEEDS_CORRECTION = {
    "http://www.math.ucsd.edu/~nts/": "URL works but redirects to wrong destination; correct endpoint needed.",
}

# ─────────────────────────────────────────────────────────────────────────────

data = json.loads(DATA.read_text())
links = data["links"]

url_index = {r["url"]: r for r in links}
patched = skipped = 0

for url in CONFIRMED_BROKEN:
    r = url_index.get(url)
    if r:
        r["classification"] = "confirmed_broken"
        r["phase2_verified"] = True
        r["phase2_status"] = "confirmed_broken"
        patched += 1
    else:
        print(f"  [skip] not in JSON: {url}")
        skipped += 1

for url in CONFIRMED_OK:
    r = url_index.get(url)
    if r:
        r["classification"] = "ok"
        r["phase2_verified"] = True
        r["phase2_status"] = "confirmed_ok"
        patched += 1
    else:
        print(f"  [skip] not in JSON: {url}")
        skipped += 1

for url, note in NEEDS_CORRECTION.items():
    r = url_index.get(url)
    if r:
        r["phase2_verified"] = True
        r["phase2_status"] = "needs_url_correction"
        r["phase2_notes"] = note
        patched += 1
    else:
        print(f"  [skip] not in JSON: {url}")
        skipped += 1

# Update summary
by_class: dict = {}
for r in links:
    c = r["classification"]
    by_class[c] = by_class.get(c, 0) + 1
data["summary"]["by_classification"] = by_class
data["summary"]["phase2_applied"] = True

DATA.write_text(json.dumps(data, indent=2))
print(f"Patched {patched} records ({skipped} not found in JSON).")
print("Classification breakdown:")
order = ["confirmed_broken","broken","redirect","pending_external_verification","needs_url_correction","internal_unverified","ok"]
for k in order + [k for k in by_class if k not in order]:
    if k in by_class:
        print(f"  {k:40s}: {by_class[k]}")
