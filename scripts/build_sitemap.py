#!/usr/bin/env python3
"""Builds sitemap.xml from what is actually on disk.

Why this exists: on 13 September 2026 the sitemap held 97 urls while the site
had 141 pages. Forty four were missing, including the whole product pages for
LoopWatt, PlugWatt, PaidUp, Pause Meno and Side Work Tax. Pages Google is never
told about are pages Google has no reason to crawl, and the indexing report was
sitting at 15 "discovered, currently not indexed".

Hand maintained sitemaps drift. This one is generated, so it cannot.

    python3 scripts/build_sitemap.py
"""

import subprocess
from datetime import date
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent
BASE = "https://thrasherapps.com/"

# Deliberately left out of the sitemap.
EXCLUDE_DIRS = {
    # Training material carrying an employer's name, published without a robots
    # directive. Not something to hand to Google without a decision first.
    "petroplus",
}
EXCLUDE_FILES = {
    "thank-you.html",   # post form confirmation, no search value
    "signals.html",     # redirect stub, "moved to /dashboard"
    "404.html",
}

# Pages worth telling Google are important. Everything else gets the default.
PRIORITY = {
    "": "1.0",
    "apps.html": "0.9",
}


def git_date(path: Path) -> str:
    """Last commit date for a file, so lastmod means something."""
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%cs", "--", str(path.relative_to(SITE))],
            cwd=SITE, capture_output=True, text=True, timeout=15).stdout.strip()
        if out:
            return out
    except Exception:
        pass
    return date.today().isoformat()


def url_for(p: Path) -> str:
    rel = p.relative_to(SITE).as_posix()
    if rel == "index.html":
        return ""
    if rel.endswith("/index.html"):
        return rel[: -len("index.html")]
    return rel


def main() -> None:
    urls = []
    for p in sorted(SITE.rglob("*.html")):
        rel = p.relative_to(SITE).as_posix()
        if rel.startswith(".git") or "node_modules" in rel:
            continue
        if rel.split("/")[0] in EXCLUDE_DIRS:
            continue
        if p.name in EXCLUDE_FILES:
            continue
        urls.append((url_for(p), git_date(p)))

    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u, mod in urls:
        lines.append("  <url>")
        lines.append(f"    <loc>{BASE}{u}</loc>")
        lines.append(f"    <lastmod>{mod}</lastmod>")
        if u in PRIORITY:
            lines.append(f"    <priority>{PRIORITY[u]}</priority>")
        lines.append("  </url>")
    lines.append("</urlset>")

    (SITE / "sitemap.xml").write_text("\n".join(lines) + "\n")
    print(f"sitemap.xml written with {len(urls)} urls")
    skipped = sorted(EXCLUDE_DIRS | EXCLUDE_FILES)
    print("deliberately excluded:", ", ".join(skipped))


if __name__ == "__main__":
    main()
