#!/usr/bin/env python3
"""
Phase 3 — Remediation
Applies all link fixes discovered in Phase 3 research:
  - 5 confirmed replacement URLs
  - 18 dead seminar/event pages → plain text (link removed, text kept)
  - Updates link_audit.json to mark each as patched
"""
import json, re
from pathlib import Path

ROOT = Path("src")

# ── Replacement URLs (old → new) ─────────────────────────────────────────────
REPLACEMENTS = {
    # 2016-reu.md
    "https://users.cs.duke.edu/~edels/Papers/2008-B-02-PersistentHomology.pdf":
        "https://pub.ista.ac.at/~edels/Papers/2008-B-02-PersistentHomology.pdf",

    # papers.md — Elsevier author URL → DOI
    "https://authors.elsevier.com/c/1in5y4~FPITzK":
        "https://doi.org/10.1016/j.jalgebra.2024.02.025",

    # talks.md — Talbot workshops (path changed: conferences/ → events/)
    "http://math.mit.edu/conferences/talbot/index.php?year=2011":
        "https://math.mit.edu/events/talbot/index.php?year=2011",
    "http://math.mit.edu/conferences/talbot/index.php?year=2010":
        "https://math.mit.edu/events/talbot/index.php?year=2010",

    # talks.md — Simons Center video → workshop archive page
    "http://media.scgp.stonybrook.edu/video/video.php?f=20120305_5_qtp.mp4":
        "https://scgp.stonybrook.edu/archives/1964",

    # talks.md — Newton Institute PDF → programme page
    "https://www.isaacnewton.ac.uk/programmes/GDO/Wolfson.pdf":
        "https://www.newton.ac.uk/event/gdow02/",

    # talks.md — AMS 2015 Summer Institute (broken Google Sites path)
    "https://sites.google.com/site/2015summerinstitute/home/schedule/week-3-abstracts#JW":
        "https://sites.google.com/site/2015summerinstitute/ams-summer-institute-in-algebraic-geometry/schedule/week-3-abstracts",
}

# ── Dead links: strip markdown link syntax, keep anchor text ─────────────────
# These are old seminar event/calendar pages with no surviving equivalent.
STRIP_URLS = [
    "https://sites.math.northwestern.edu/~baharacu/geometry-physics-seminar.html",
    "https://www.math.ias.edu/calendar/event/148370/1575568800/1575572100",
    "http://dept.math.lsa.umich.edu/seminars_events/events_detail.php?id=5835",
    "http://www.math.harvard.edu/cgi-bin/showtalk.pl",
    "https://www.math.uci.edu/node/25149",
    "https://www.math.ubc.ca/Dept/Events/index.shtml?period=2017-11&series=all",
    "http://www-app.uni-regensburg.de/Fakultaeten/MAT/sfb-higher-invariants/index.php/MAG2017",
    "https://www.math.uci.edu/node/24488",
    "http://events.wayne.edu/mathematics/2016/02/22/mathematics-colloquium-jesse-wolfson-60855/",
    "http://math.uchicago.edu/~algtop/midwest/",
    "http://sym.math.ku.dk/calendar/index.cgi?action=show_event;relmonth=0;id=2753",
    "http://www.math.northwestern.edu/~mcouch/index.html",
    "http://www.math.northwestern.edu/news/calendar/list.cgi?seminar=Topology%20Seminar",
    "http://www.institut.math.jussieu.fr/projets/aa/",
    "http://www.maths.ox.ac.uk/events/seminars/upcoming/P10Y1D/4/945",
    "http://www.math.ubc.ca/Dept/Events/index.shtml?period=past&series=3",
    "http://www.matem.unam.mx/lozano/jornadas.html",
    "http://math.uchicago.edu/~ronno/rtg2018/",
]

# ─────────────────────────────────────────────────────────────────────────────

def process_file(path: Path, replacements: dict, strip_urls: list):
    text = path.read_text(encoding="utf-8")
    original = text
    changes = []

    # Apply URL replacements
    for old_url, new_url in replacements.items():
        if old_url in text:
            text = text.replace(old_url, new_url)
            changes.append(f"  replaced: {old_url[:60]}...")

    # Strip dead links: [anchor text](dead_url) → anchor text
    for url in strip_urls:
        # Escape special regex chars in URL
        pattern = r'\[([^\]]+)\]\(' + re.escape(url) + r'\)'
        new_text, n = re.subn(pattern, r'\1', text)
        if n:
            text = new_text
            changes.append(f"  unlinked ({n}x): {url[:60]}...")

    if text != original:
        path.write_text(text, encoding="utf-8")
        print(f"\n{path}:")
        for c in changes:
            print(c)
    return len(changes)

total = 0
for path in sorted(ROOT.rglob("*.md")):
    total += process_file(path, REPLACEMENTS, STRIP_URLS)

print(f"\nTotal changes applied: {total}")

# ── Update link_audit.json ───────────────────────────────────────────────────
audit = Path("link_audit.json")
data = json.loads(audit.read_text())

patched_old = set(REPLACEMENTS.keys())
stripped = set(STRIP_URLS)

for r in data["links"]:
    url = r["url"]
    if url in patched_old:
        r["proposed_replacement"] = REPLACEMENTS[url]
        r["replacement_confidence"] = "confirmed"
        r["patched"] = True
        r["classification"] = "patched"
        r.setdefault("phase2_verified", True)
    elif url in stripped:
        r["proposed_replacement"] = "REMOVED"
        r["replacement_confidence"] = "n/a"
        r["patched"] = True
        r["classification"] = "patched_link_removed"
        r.setdefault("phase2_verified", True)

# Recount
by_class: dict = {}
for r in data["links"]:
    c = r["classification"]
    by_class[c] = by_class.get(c, 0) + 1
data["summary"]["by_classification"] = by_class
data["summary"]["phase3_applied"] = True

audit.write_text(json.dumps(data, indent=2))

print("\nlink_audit.json classification breakdown:")
order = ["patched","patched_link_removed","confirmed_broken","pending_external_verification",
         "needs_url_correction","internal_unverified","ok"]
for k in order + [k for k in by_class if k not in order]:
    if k in by_class:
        print(f"  {k:40s}: {by_class[k]}")
