#!/usr/bin/env python3
"""
Phase 1 — INVENTORY
Parses all source files in src/ to extract links, checks HTTP status of every
external URL, and writes link_audit.json.

In sandboxed environments (HTTPS_PROXY set) some domains are blocked at the
proxy level; those are recorded as sandbox_blocked and re-checked automatically
when this script runs in GitHub Actions (no proxy restrictions).
"""

import json
import os
import re
import time
from pathlib import Path
from urllib.parse import unquote

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


def is_internal(url: str) -> bool:
    return url.startswith("/") or "jpwolfson.com" in url


def check_internal_file(url: str) -> dict:
    """Verify /files/... links exist on disk (URL-decode the path first)."""
    decoded = unquote(url)  # /files/Batson%20-... -> /files/Batson -...
    rel_path = decoded.lstrip("/")          # files/Batson -...
    local_path = SRC_DIR / rel_path         # src/files/Batson -...
    if local_path.exists():
        return {"error": None}
    return {"error": f"FILE_NOT_FOUND: {local_path}"}


# ---------------------------------------------------------------------------
# HTTP check — attempts every URL; records proxy blocks separately
# ---------------------------------------------------------------------------
def check_url(url: str, session: requests.Session) -> tuple[dict, str]:
    """
    Returns (result_dict, reachability).
    reachability is one of: 'checked', 'sandbox_blocked'.
    """
    try:
        start = time.time()
        r = session.head(url, headers=HEADERS, timeout=REQUEST_TIMEOUT,
                         allow_redirects=True)
        elapsed = int((time.time() - start) * 1000)
        # Some servers reject HEAD — fall back to GET
        if r.status_code in (405, 400):
            r = session.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT,
                            allow_redirects=True, stream=True)
            r.close()
            elapsed = int((time.time() - start) * 1000)
        # Detect sandbox proxy block: proxy returns HTTP 403 with
        # x-deny-reason: host_not_allowed instead of forwarding the request.
        if (r.status_code == 403
                and r.headers.get("x-deny-reason") == "host_not_allowed"):
            return {
                "http_status": None, "final_url": None, "redirect_chain": [],
                "error": "SANDBOX_PROXY_BLOCKED",
                "response_time_ms": None,
            }, "sandbox_blocked"
        chain = [h.url for h in r.history]
        return {
            "http_status": r.status_code,
            "final_url": r.url,
            "redirect_chain": chain,
            "error": None,
            "response_time_ms": elapsed,
        }, "checked"
    except requests.exceptions.ProxyError:
        # Sandbox proxy rejected the host at the connection level
        return {
            "http_status": None, "final_url": None, "redirect_chain": [],
            "error": "SANDBOX_PROXY_BLOCKED",
            "response_time_ms": None,
        }, "sandbox_blocked"
    except requests.exceptions.Timeout:
        return {"http_status": None, "final_url": None, "redirect_chain": [],
                "error": "TIMEOUT", "response_time_ms": None}, "checked"
    except requests.exceptions.TooManyRedirects:
        return {"http_status": None, "final_url": None, "redirect_chain": [],
                "error": "TOO_MANY_REDIRECTS", "response_time_ms": None}, "checked"
    except Exception as e:
        return {"http_status": None, "final_url": None, "redirect_chain": [],
                "error": str(e)[:200], "response_time_ms": None}, "checked"


# ---------------------------------------------------------------------------
# Classify
# ---------------------------------------------------------------------------
def classify(result: dict, reachability: str) -> str:
    if reachability == "internal":
        return "internal_unverified"
    if reachability == "internal_file":
        return "ok" if not result["error"] else "broken"
    if reachability == "sandbox_blocked":
        return "pending_external_verification"
    if result["error"] and result["error"] != "SANDBOX_PROXY_BLOCKED":
        # Timeout, SSL errors, connection errors — server is reachable but
        # uncooperative; not definitively dead.
        return "uncertain"
    status = result.get("http_status")
    if status is None:
        return "unknown"
    if status == 200:
        return "ok"
    if status in (301, 302, 307, 308):
        return "redirect"
    if status in (404, 410):
        # Definitively gone.
        return "broken"
    if status >= 400:
        # 401/403 = auth/bot-block; 5xx = server error — not definitively dead.
        return "uncertain"
    return "unknown"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    # Script lives in scripts/; the Eleventy project (src/) is one level up.
    os.chdir(Path(__file__).resolve().parent.parent)

    in_sandbox = bool(os.environ.get("HTTPS_PROXY"))
    env_label = "sandbox (proxy-restricted)" if in_sandbox else "unrestricted"
    print(f"[env] Running in {env_label} environment")

    print("\n[1/3] Extracting links from source files...")
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

        if is_internal(url):
            if url.startswith("/files/"):
                file_result = check_internal_file(url)
                reachability = "internal_file"
                result = {**file_result, "http_status": None,
                          "final_url": None, "redirect_chain": [],
                          "response_time_ms": None}
            else:
                reachability = "internal"
                result = {"http_status": None, "final_url": None,
                          "redirect_chain": [], "error": None,
                          "response_time_ms": None}
        else:
            result, reachability = check_url(abs_url, session)
            time.sleep(DELAY)

        classification = classify(result, reachability)
        status_str = (
            f"HTTP {result['http_status']}" if result["http_status"]
            else result.get("error") or reachability
        )
        print(f"  ({i:3d}/{total}) [{classification:35s}] {url[:75]}  →  {status_str}")

        results.append({
            "url": url,
            "resolved_url": abs_url if abs_url != url else None,
            "reachability": reachability,
            "http_status": result["http_status"],
            "final_url": result["final_url"],
            "redirect_chain": result["redirect_chain"],
            "error": result["error"],
            "response_time_ms": result["response_time_ms"],
            "classification": classification,
            "occurrences": entry["occurrences"],
            "proposed_replacement": None,
            "replacement_confidence": None,
            "patched": False,
        })

    sort_order = {
        "broken": 0, "redirect": 1,
        "uncertain": 2,
        "pending_external_verification": 3,
        "internal_unverified": 4,
        "ok": 5, "unknown": 6,
    }
    results.sort(key=lambda r: sort_order.get(r["classification"], 9))

    by_class: dict = {}
    for r in results:
        c = r["classification"]
        by_class[c] = by_class.get(c, 0) + 1

    summary = {
        "crawled_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "environment": env_label,
        "site_root": SITE_ROOT,
        "total_unique_urls": len(results),
        "total_raw_instances": len(raw_links),
        "by_classification": by_class,
    }
    if in_sandbox:
        summary["sandbox_note"] = (
            "Some external URLs were blocked by the sandbox proxy and are "
            "classified pending_external_verification. Run via GitHub Actions "
            "for unrestricted HTTP checks."
        )

    output = {"summary": summary, "links": results}

    print(f"\n[3/3] Writing {OUTPUT}...")
    with open(OUTPUT, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n=== INVENTORY COMPLETE ===")
    print(f"Total unique URLs : {summary['total_unique_urls']}")
    for k, v in sorted(by_class.items(), key=lambda x: sort_order.get(x[0], 9)):
        print(f"  {k:40s}: {v}")

    # Exit non-zero if there are confirmed broken links (for CI)
    if by_class.get("broken", 0) > 0:
        print(f"\n[FAIL] {by_class['broken']} broken link(s) found.")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
