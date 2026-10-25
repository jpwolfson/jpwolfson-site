#!/usr/bin/env python3
"""Deterministic CSP checks on the built site. Run from jpwolfson-site/ after build.

1. Every page's meta CSP contains the required directives with the required values.
2. The SHA-256 of the inline MathJax config block matches a hash listed in script-src
   (replaces the manual 'recompute the hash' procedure; prints the new hash on mismatch).
"""
import base64, hashlib, html, pathlib, re, sys

REQUIRED = {
    "default-src": {"'self'"},
    "base-uri": {"'self'"},
    "form-action": {"'none'"},
    "object-src": {"'none'"},
}
FORBIDDEN_IN_SCRIPT_SRC = {"'unsafe-inline'", "'unsafe-eval'", "*", "data:", "http:"}

def parse_csp(policy: str) -> dict:
    out = {}
    for part in policy.split(";"):
        toks = part.split()
        if toks:
            out[toks[0]] = set(toks[1:])
    return out

fail = False
pages = sorted(pathlib.Path("_site").rglob("*.html"))
if not pages:
    print("FAIL no built pages found"); sys.exit(1)

for page in pages:
    text = page.read_text(encoding="utf-8")
    m = re.search(r'http-equiv="Content-Security-Policy"\s+content="([^"]+)"', text, re.S)
    if not m:
        print(f"FAIL {page}: no CSP meta"); fail = True; continue
    csp = parse_csp(html.unescape(" ".join(m.group(1).split())))
    for d, want in REQUIRED.items():
        if d not in csp or not want <= csp[d]:
            print(f"FAIL {page}: {d} must include {sorted(want)}, got {sorted(csp.get(d, []))}"); fail = True
    bad = FORBIDDEN_IN_SCRIPT_SRC & csp.get("script-src", set())
    if bad:
        print(f"FAIL {page}: script-src contains {sorted(bad)}"); fail = True
    inline = re.findall(r"<script>(.*?)</script>", text, re.S)
    if len(inline) != 1:
        print(f"FAIL {page}: expected 1 inline script, found {len(inline)}"); fail = True; continue
    digest = "sha256-" + base64.b64encode(hashlib.sha256(inline[0].encode("utf-8")).digest()).decode()
    if f"'{digest}'" not in csp.get("script-src", set()):
        print(f"FAIL {page}: inline script hash {digest} is not in script-src. "
              f"Update the hash in src/_includes/base.njk (CSP meta and the comment above the block)."); fail = True

print("FAIL" if fail else f"ok   CSP checks passed on {len(pages)} pages")
sys.exit(1 if fail else 0)
