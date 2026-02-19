#!/usr/bin/env python3
"""
Phase 1 — INVENTORY (static analysis edition)
Parses all source files in src/ to extract links, checks reachable
external URLs, and writes link_audit.json.
"""

import json
import os
import re
import time
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
SRC_DIR = Path("src")
OUTPUT = "link_audit.json"
SITE_ROOT = "https://jpwolfson.com"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; LinkAuditor/1.0)"}
REQUEST_TIMEOUT = 15
DELAY = 0.3

# Domains allowed through the sandbox proxy (derived from proxy JWT allowlist)
PROXY_ALLOWED_DOMAINS = {
    "github.com", "www.github.com", "gist.github.com", "codeload.github.com",
    "raw.githubusercontent.com", "camo.githubusercontent.com",
    "pypi.org", "www.pypi.org", "pypi.python.org",
    "npmjs.org", "www.npmjs.org", "www.npmjs.com",
    "golang.org", "www.golang.org", "pkg.go.dev",
    "api.anthropic.com", "claude.ai", "platform.claude.com", "docs.claude.com",
    "sentry.io",
}

# ---------------------------------------------------------------------------
# Markdown / HTML link extraction
# ---------------------------------------------------------------------------
MD_LINK_RE = re.compile(r'\[([^\]]*)\]\(([^)]+)\)')
HTML_HREF_RE = re.compile(r'href=["\']([^"\']+)["\']', re.IGNORECASE)
HTML_SRC_RE = re.compile(r'src=["\']([^"\']+)["\']', re.IGNORECASE)

def extract_links_from_file(path: Path) -> list:
    text = path.read_text(encoding="utf-8")
    results = []

    def add(url, anchor, lineno):
        url = url.strip()
        if url.startswith(("mailto:", "tel:", "javascript:", "#")):
            return
        results.append({
            "url": url,
            "anchor_text": anchor.strip()[:200],
            "source_file": str(path),
            "line": lineno,
        })

    lines = text.splitlines()
    for i, line in enumerate(lines, 1):
        for anchor, url in MD_LINK_RE.findall(line):
            add(url, anchor, i)
        for url in HTML_HREF_RE.findall(line):
            add(url, "[href]", i)
        for url in HTML_SRC_RE.findall(line):
            add(url, "[src]", i)
    return results


def collect_all_links() -> list:
    all_links = []
    for ext in ("*.md", "*.njk", "*.html", "*.yml"):
        for path in sorted(SRC_DIR.rglob(ext)):
            all_links.extend(extract_links_from_file(path))
    return all_links


# ---------------------------------------------------------------------------
# De-duplicate while preserving all occurrence info
# ---------------------------------------------------------------------------
def group_by_url(raw_links: list) -> dict:
    grouped = {}
    for link in raw_links:
        url = link["url"]
        if url not in grouped:
            grouped[url] = {"url": url, "occurrences": []}
        grouped[url]["occurrences"].append({
            "anchor_text": link["anchor_text"],
            "source_file": link["source_file"],
            "line": link["line"],
        })
    return grouped


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------
def resolve_url(url: str) -> str:
    if url.startswith("http://") or url.startswith("https://"):
        return url
    if url.startswith("/"):
        return SITE_ROOT + url
    return url


def is_proxy_reachable(url: str) -> bool:
    m = re.match(r"https?://([^/]+)", url)
    if not m:
        return False
    host = m.group(1)
    return host in PROXY_ALLOWED_DOMAINS


def is_internal(url: str) -> bool:
    return url.startswith("/") or "jpwolfson.com" in url


# ---------------------------------------------------------------------------
# HTTP check
# ---------------------------------------------------------------------------
def check_url(url: str, session: requests.Session) -> dict:
    try:
        start = time.time()
        r = session.head(url, headers=HEADERS, timeout=REQUEST_TIMEOUT,
                         allow_redirects=True)
        elapsed = int((time.time() - start) * 1000)
        if r.status_code in (405, 400, 403):
            r = session.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT,
                            allow_redirects=True, stream=True)
            r.close()
            elapsed = int((time.time() - start) * 1000)
        chain = [h.url for h in r.history]
        return {
            "http_status": r.status_code,
            "final_url": r.url,
            "redirect_chain": chain,
            "error": None,
            "response_time_ms": elapsed,
        }
    except requests.exceptions.Timeout:
        return {"http_status": None, "final_url": None, "redirect_chain": [],
                "error": "TIMEOUT", "response_time_ms": None}
    except requests.exceptions.TooManyRedirects:
        return {"http_status": None, "final_url": None, "redirect_chain": [],
                "error": "TOO_MANY_REDIRECTS", "response_time_ms": None}
    except Exception as e:
        return {"http_status": None, "final_url": None, "redirect_chain": [],
                "error": str(e)[:200], "response_time_ms": None}


# ---------------------------------------------------------------------------
# Classify
# ---------------------------------------------------------------------------
def classify(record: dict, reachability: str) -> str:
    if reachability == "internal":
        return "internal_unverified"
    if reachability == "internal_file":
        return "ok" if not record["error"] else "broken"
    if reachability == "sandbox_blocked":
        return "pending_external_verification"
    # checked externally
    if record["error"]:
        return "broken"
    status = record.get("http_status")
    if status is None:
        return "unknown"
    if status == 200:
        return "ok"
    if status in (301, 302, 307, 308):
        return "redirect"
    if status == 404:
        return "broken"
    if status >= 400:
        return "broken"
    return "unknown"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    os.chdir(Path(__file__).parent)

    print("[1/3] Extracting links from source files...")
    raw_links = collect_all_links()
    grouped = group_by_url(raw_links)
    print(f"      {len(raw_links)} raw instances → {len(grouped)} unique URLs")

    session = requests.Session()
    session.max_redirects = 10

    results = []
    total = len(grouped)

    print(f"\n[2/3] Auditing {total} URLs...")
    for i, (url, entry) in enumerate(grouped.items(), 1):
        abs_url = resolve_url(url)
        check_result = {
            "http_status": None, "final_url": None, "redirect_chain": [],
            "error": None, "response_time_ms": None,
        }

        if is_internal(url):
            reachability = "internal"
            if url.startswith("/files/"):
                fname = url.replace("/files/", "src/files/")
                check_result["error"] = None if Path(fname).exists() else "FILE_NOT_FOUND"
                reachability = "internal_file"
        elif is_proxy_reachable(abs_url):
            reachability = "checked"
            check_result = check_url(abs_url, session)
            time.sleep(DELAY)
        else:
            reachability = "sandbox_blocked"

        classification = classify(check_result, reachability)

        status_str = (
            f"HTTP {check_result['http_status']}" if check_result["http_status"]
            else check_result["error"] or reachability
        )
        print(f"  ({i:3d}/{total}) [{classification:35s}] {url[:75]}  →  {status_str}")

        results.append({
            "url": url,
            "resolved_url": abs_url if abs_url != url else None,
            "reachability": reachability,
            "http_status": check_result["http_status"],
            "final_url": check_result["final_url"],
            "redirect_chain": check_result["redirect_chain"],
            "error": check_result["error"],
            "response_time_ms": check_result["response_time_ms"],
            "classification": classification,
            "occurrences": entry["occurrences"],
            "proposed_replacement": None,
            "replacement_confidence": None,
            "patched": False,
        })

    sort_order = {
        "broken": 0, "redirect": 1,
        "pending_external_verification": 2,
        "internal_unverified": 3,
        "ok": 4, "unknown": 5,
    }
    results.sort(key=lambda r: sort_order.get(r["classification"], 9))

    by_class: dict = {}
    for r in results:
        c = r["classification"]
        by_class[c] = by_class.get(c, 0) + 1

    summary = {
        "crawled_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "site_root": SITE_ROOT,
        "total_unique_urls": len(results),
        "total_raw_instances": len(raw_links),
        "by_classification": by_class,
        "sandbox_note": (
            "HTTP checks only performed for proxy-allow-listed domains. "
            "All other external URLs are classified pending_external_verification "
            "and must be re-checked from a non-sandboxed environment in Phase 2."
        ),
    }

    output = {"summary": summary, "links": results}

    print(f"\n[3/3] Writing {OUTPUT}...")
    with open(OUTPUT, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n=== INVENTORY COMPLETE ===")
    print(f"Total unique URLs : {summary['total_unique_urls']}")
    for k, v in sorted(by_class.items(), key=lambda x: sort_order.get(x[0], 9)):
        print(f"  {k:40s}: {v}")


if __name__ == "__main__":
    main()
