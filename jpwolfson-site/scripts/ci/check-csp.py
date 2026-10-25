#!/usr/bin/env python3
"""DOM-level security invariants on the built site. Run from jpwolfson-site/ after build.

Parses every HTML page with html.parser (case-insensitive, attribute-order-independent)
and requires:
  * exactly one <meta http-equiv="Content-Security-Policy"> whose normalised policy is
    byte-for-byte the canonical policy below (no page may bring its own policy);
  * the canonical policy's script-src hashes are exactly the two known ones;
  * exactly two <script> elements: the inline MathJax config (whose SHA-256 must be in
    script-src) and the external MathJax loader with integrity + crossorigin;
  * every <iframe> src is on an allowed host; no srcdoc; no <base>, <object>, <embed>,
    <form>, or inline event handlers.
On a hash mismatch the new hash is printed so the template can be updated.
"""
import base64, hashlib, pathlib, sys
from html.parser import HTMLParser
from urllib.parse import urlsplit

ALLOWED_HASHES = {
    "'sha256-MdMapQxvxeL6vP8KdU8o5Ie9nNnnk3l94+maA3yW+k8='",   # MathJax config block
    "'sha256-ieoeWczDHkReVBsRBqaal5AFMlBtNjMzgwKvLqi/tSU='",   # Cloudflare analytics beacon
}
MATHJAX_SRC = "https://cdn.jsdelivr.net/npm/mathjax@3.2.2/es5/tex-chtml.js"
FRAME_HOSTS = {"player.vimeo.com", "www.youtube.com"}
FORBIDDEN_TAGS = {"base", "object", "embed", "form", "applet"}

def normalise(policy: str) -> str:
    directives = []
    for part in policy.split(";"):
        toks = part.split()
        if toks:
            directives.append(toks[0] + " " + " ".join(sorted(toks[1:])))
    return "; ".join(sorted(directives))

class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.csp, self.scripts, self.iframes, self.forbidden, self.handlers = [], [], [], [], []
        self._in_script = None
    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "meta" and a.get("http-equiv", "").lower() == "content-security-policy":
            self.csp.append(a.get("content", ""))
        if tag == "script":
            self._in_script = {"attrs": a, "body": ""}
        if tag == "iframe":
            self.iframes.append(a)
        if tag in FORBIDDEN_TAGS:
            self.forbidden.append(tag)
        for k in a:
            if k.startswith("on"):
                self.handlers.append(f"<{tag} {k}>")
    def handle_data(self, data):
        if self._in_script is not None:
            self._in_script["body"] += data
    def handle_endtag(self, tag):
        if tag == "script" and self._in_script is not None:
            self.scripts.append(self._in_script); self._in_script = None

def main() -> int:
    pages = sorted(pathlib.Path("_site").rglob("*.html"))
    if not pages:
        print("FAIL no built pages found"); return 1
    tpl = pathlib.Path("src/_includes/base.njk").read_text(encoding="utf-8")
    start = tpl.index('http-equiv="Content-Security-Policy"'); start = tpl.index('content="', start) + len('content="')
    canonical = normalise(tpl[start:tpl.index('"', start)])
    canon_hashes = {t for t in canonical.split("; ") if t.startswith("script-src")}.pop().split()[1:]
    canon_hashes = {t for t in canon_hashes if t.startswith("'sha256-")}
    fail = False
    def bad(page, msg):
        nonlocal fail; fail = True; print(f"FAIL {page}: {msg}")
    if canon_hashes != ALLOWED_HASHES:
        print(f"FAIL template script-src hashes {sorted(canon_hashes)} != allowed {sorted(ALLOWED_HASHES)}"); fail = True
    for page in pages:
        p = Page(); p.feed(page.read_text(encoding="utf-8"))
        if len(p.csp) != 1:
            bad(page, f"expected exactly 1 CSP meta, found {len(p.csp)}")
        elif normalise(p.csp[0]) != canonical:
            bad(page, "CSP differs from the template's canonical policy")
        inline = [s for s in p.scripts if "src" not in s["attrs"]]
        external = [s for s in p.scripts if "src" in s["attrs"]]
        if len(inline) != 1:
            bad(page, f"expected 1 inline <script> (MathJax config), found {len(inline)}")
        else:
            digest = "'sha256-" + base64.b64encode(hashlib.sha256(inline[0]["body"].encode("utf-8")).digest()).decode() + "'"
            if digest not in canon_hashes:
                bad(page, f"inline script hash {digest} not in script-src; update base.njk (meta + comment)")
        if len(external) != 1:
            bad(page, f"expected 1 external <script> (MathJax), found {len(external)}: {[s['attrs'].get('src') for s in external]}")
        else:
            a = external[0]["attrs"]
            if a.get("src") != MATHJAX_SRC: bad(page, f"unexpected external script {a.get('src')}")
            if not a.get("integrity", "").startswith("sha384-"): bad(page, "MathJax script lacks SRI integrity")
            if a.get("crossorigin") != "anonymous": bad(page, "MathJax script lacks crossorigin=anonymous")
        for fr in p.iframes:
            if "srcdoc" in fr: bad(page, "iframe uses srcdoc")
            host = urlsplit(fr.get("src", "")).hostname
            scheme = urlsplit(fr.get("src", "")).scheme
            if scheme != "https" or host not in FRAME_HOSTS: bad(page, f"iframe src not allowed: {fr.get('src')}")
        for t in p.forbidden: bad(page, f"forbidden element <{t}>")
        for h in p.handlers: bad(page, f"inline event handler {h}")
    print("FAIL" if fail else f"ok   DOM/CSP invariants hold on {len(pages)} pages")
    return 1 if fail else 0

if __name__ == "__main__":
    sys.exit(main())
