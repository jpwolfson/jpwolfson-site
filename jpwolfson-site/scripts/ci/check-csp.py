#!/usr/bin/env python3
"""DOM-level security invariants on the built site. Run from jpwolfson-site/ after build.

Parses every HTML page with html.parser (case-insensitive, attribute-order-independent)
and requires:
  * the template's CSP, normalised, equals EXPECTED_CSP below (so weakening the template
    fails CI; change the constant deliberately, in the same PR, when the policy changes);
  * the policy also satisfies a directive floor (REQUIRED) and bans (FORBIDDEN_IN_SCRIPT_SRC),
    as a second line of defence if the constant is edited carelessly;
  * every page carries exactly one CSP meta whose normalised policy equals EXPECTED_CSP;
  * the script-src hashes are exactly the two known ones;
  * exactly two <script> elements: the inline MathJax config (whose SHA-256 must be in
    script-src) and the external MathJax loader with integrity + crossorigin;
  * every <iframe> src is on an allowed https host; no srcdoc; no <base>, <object>, <embed>,
    <form>, <meta http-equiv=refresh>, inline event handlers, or CDATA/unknown declarations
    (which browsers and html.parser tokenize differently).
On a hash mismatch the new hash is printed so the template can be updated.
"""
import base64, hashlib, pathlib, re, sys
from html.parser import HTMLParser
from urllib.parse import urlsplit

EXPECTED_CSP = (
    "base-uri 'self'; connect-src 'self' https://cloudflareinsights.com; default-src 'self'; font-src 'self' https://cdn.jsdelivr.net/npm/mathjax@3.2.2/; form-action 'none'; frame-src https://player.vimeo.com https://www.youtube.com; img-src 'self' data: https:; object-src 'none'; script-src 'self' 'sha256-MdMapQxvxeL6vP8KdU8o5Ie9nNnnk3l94+maA3yW+k8=' 'sha256-ieoeWczDHkReVBsRBqaal5AFMlBtNjMzgwKvLqi/tSU=' https://cdn.jsdelivr.net/npm/mathjax@3.2.2/ https://static.cloudflareinsights.com; style-src 'self' 'unsafe-inline'"
)
REQUIRED = {
    "default-src": {"'self'"},
    "base-uri": {"'self'"},
    "form-action": {"'none'"},
    "object-src": {"'none'"},
}
FORBIDDEN_IN_SCRIPT_SRC = {"'unsafe-inline'", "'unsafe-eval'", "'unsafe-hashes'", "'strict-dynamic'", "*", "data:", "blob:", "http:", "https:"}
ALLOWED_HASHES = {
    "'sha256-MdMapQxvxeL6vP8KdU8o5Ie9nNnnk3l94+maA3yW+k8='",   # MathJax config block
    "'sha256-ieoeWczDHkReVBsRBqaal5AFMlBtNjMzgwKvLqi/tSU='",   # Cloudflare analytics beacon
}
MATHJAX_SRC = "https://cdn.jsdelivr.net/npm/mathjax@3.2.2/es5/tex-chtml.js"
FRAME_HOSTS = {"player.vimeo.com", "www.youtube.com"}
FORBIDDEN_TAGS = {"base", "object", "embed", "form", "applet"}
# Any markup declaration other than the doctype or an HTML comment.
BAD_DECL = re.compile(r"<!(?!doctype\s|--)", re.I)

def normalise(policy: str) -> str:
    directives = []
    for part in policy.split(";"):
        toks = part.split()
        if toks:
            directives.append(toks[0] + " " + " ".join(sorted(toks[1:])))
    return "; ".join(sorted(directives))

def parse(policy: str) -> dict:
    return {d.split()[0]: set(d.split()[1:]) for d in normalise(policy).split("; ") if d}

class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.csp, self.scripts, self.iframes, self.forbidden, self.handlers = [], [], [], [], []
        self._in_script = None
    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "meta" and a.get("http-equiv", "").lower() == "content-security-policy":
            self.csp.append(a.get("content", ""))
        if tag == "meta" and a.get("http-equiv", "").lower() == "refresh":
            self.forbidden.append("meta http-equiv=refresh")
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
    template_csp = normalise(tpl[start:tpl.index('"', start)])
    fail = False
    def bad(page, msg):
        nonlocal fail; fail = True; print(f"FAIL {page}: {msg}")
    if template_csp != EXPECTED_CSP:
        fail = True
        print("FAIL base.njk CSP differs from EXPECTED_CSP in scripts/ci/check-csp.py.")
        print("     If the change is intended, update the constant in the same PR so the reviewer sees both.")
        print(f"     template: {template_csp}")
        print(f"     expected: {EXPECTED_CSP}")
    parsed = parse(EXPECTED_CSP)
    for d, want in REQUIRED.items():
        if not want <= parsed.get(d, set()):
            fail = True; print(f"FAIL EXPECTED_CSP floor: {d} must include {sorted(want)}")
    banned = FORBIDDEN_IN_SCRIPT_SRC & parsed.get("script-src", set())
    if banned:
        fail = True; print(f"FAIL EXPECTED_CSP floor: script-src contains {sorted(banned)}")
    canon_hashes = {t for t in parsed.get("script-src", set()) if t.startswith("'sha")}
    if canon_hashes != ALLOWED_HASHES:
        fail = True; print(f"FAIL script-src hashes {sorted(canon_hashes)} != allowed {sorted(ALLOWED_HASHES)}")
    for page in pages:
        text = page.read_text(encoding="utf-8")
        for m in BAD_DECL.finditer(text):
            bad(page, f"markup declaration other than doctype/comment at offset {m.start()}: {text[m.start():m.start()+12]!r}")
        p = Page(); p.feed(text)
        if len(p.csp) != 1:
            bad(page, f"expected exactly 1 CSP meta, found {len(p.csp)}")
        elif normalise(p.csp[0]) != EXPECTED_CSP:
            bad(page, "CSP differs from EXPECTED_CSP")
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
