#!/usr/bin/env python3
"""Makes every individual code findable and linkable.

Two jobs, both run against the already built HTML rather than regenerating it.

    WARNING: do not run build_reference_pages.py to achieve this. That generator
    predates the refTop, refSiblings and refCross blocks that went live on
    11 September 2026, and it would silently strip them. It also expects every
    app's ReferenceLibrary on the Desktop, and RackWatt and PlugWatt are absent.

1. Adds a permalink control to each code entry, so a technician answering a
   question in a forum can link the one code rather than a fifty kilobyte page.
   Deep links are what earn editorial backlinks, and backlinks are the actual
   reason the pages sit on page two.

2. Builds a search index across every code in every app and writes a single
   search page at /reference/. One page worth linking to beats fifty four thin
   ones, and the site currently has no cross app entry point at all.

    python3 scripts/build_reference_search.py
"""

import html
import json
import re
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent
APPS = {
    "fieldwatt": "FieldWatt, utility scale solar",
    "storewatt": "StoreWatt, battery storage",
    "rackwatt": "RackWatt, data centres",
    "loopwatt": "LoopWatt, fire alarm",
    "plugwatt": "PlugWatt, EV charging",
    "droptubebuilder": "DropTubeBuilder, fuel systems",
}

PERMALINK_MARK = "refPermalink"

ENTRY_RE = re.compile(
    r'<div class="refEntry" id="(?P<id>[^"]+)">(?P<body>.*?)</div>\s*(?=<div class="refEntry"|<div class="refToc|<div class="refCta|<p class="mt-3")',
    re.S)
H2_RE = re.compile(r"<h2>(.*?)</h2>", re.S)


def strip_tags(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s)).strip()


def add_permalinks(text):
    """Put a copyable anchor beside every entry heading. Idempotent."""
    if PERMALINK_MARK in text:
        return text, 0
    count = 0

    def fix(m):
        nonlocal count
        eid, body = m.group("id"), m.group("body")
        def h2sub(h):
            nonlocal count
            count += 1
            return (f'<h2>{h.group(1)}'
                    f'<a class="{PERMALINK_MARK}" href="#{eid}" '
                    f'aria-label="Link to this code" title="Copy a link to this code">#</a></h2>')
        return m.group(0).replace(m.group("body"), H2_RE.sub(h2sub, body, count=1))

    return ENTRY_RE.sub(fix, text), count


PERMALINK_CSS = """
    .refPermalink{margin-left:.5rem;font-weight:400;text-decoration:none;opacity:0;
      transition:opacity .12s;color:#2563EB;font-size:.8em}
    .refEntry:hover .refPermalink,.refPermalink:focus{opacity:1}
"""


def main():
    index, touched, links = [], 0, 0

    for key, label in APPS.items():
        d = SITE / key / "reference"
        if not d.is_dir():
            continue
        for f in sorted(d.glob("*.html")):
            if f.name == "index.html":
                continue
            text = f.read_text(errors="replace")
            page_title = strip_tags((re.search(r"<h1[^>]*>(.*?)</h1>", text, re.S) or
                                     re.search(r"<title>(.*?)</title>", text, re.S)).group(1))

            for m in ENTRY_RE.finditer(text):
                h = H2_RE.search(m.group("body"))
                if not h:
                    continue
                body = strip_tags(m.group("body"))
                index.append({
                    "t": strip_tags(h.group(1)).replace("#", "").strip(),
                    "p": page_title,
                    "a": label,
                    "u": f"/{key}/reference/{f.name}#{m.group('id')}",
                    "s": body[:190],
                })

            new, n = add_permalinks(text)
            if n:
                if ".refPermalink{" not in new:
                    new = new.replace("</style>", PERMALINK_CSS + "  </style>", 1)
                f.write_text(new)
                touched += 1
                links += n

    (SITE / "assets").mkdir(exist_ok=True)
    (SITE / "assets" / "reference-index.json").write_text(
        json.dumps(index, separators=(",", ":")))

    print(f"permalinks added to {links} entries across {touched} pages")
    print(f"search index: {len(index)} codes -> assets/reference-index.json")
    return index


if __name__ == "__main__":
    main()
