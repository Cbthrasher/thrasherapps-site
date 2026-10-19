#!/usr/bin/env python3
"""Links the hand written how to guides from the generated reference pages (19 Oct 2026).

"how to clear veeder root alarm" (TLS-350, TLS-450) is the biggest fuel search found on 19 Oct, and the guide that
answers it lives at droptubebuilder/reference/how-to-clear-veeder-root-alarm.html. The reference pages are generated,
so this inserts a marked block after each page's lead paragraph and is safe to run again after any rebuild:
    python3 scripts/add_guide_links.py
"""
import re
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent
REF = SITE / "droptubebuilder" / "reference"
BEGIN, END = "<!-- guide-links:begin -->", "<!-- guide-links:end -->"
BLOCK = (BEGIN + '\n      <div class="refSiblings"><strong>How to</strong>'
         '<a href="/droptubebuilder/reference/how-to-clear-veeder-root-alarm.html">How to clear a Veeder-Root alarm '
         '(TLS-350, TLS-450PLUS, TLS4)</a></div>\n      ' + END)
PAGES = ["index.html", "veeder-root-tls-350.html", "veeder-root-tls-450-plus.html", "veeder-root-tls-450.html",
         "veeder-root-tls4.html", "veeder-root-tls-300.html"]


def main():
    for name in PAGES:
        p = REF / name
        s = p.read_text(encoding="utf-8")
        s2 = re.sub(r"\n\s*" + re.escape(BEGIN) + r".*?" + re.escape(END), "", s, flags=re.S)
        s2 = re.sub(r'(<p class="lead">.*?</p>)', lambda m: m.group(1) + "\n      " + BLOCK, s2, count=1, flags=re.S)
        if s2 != s:
            p.write_text(s2, encoding="utf-8")
        print(("updated " if s2 != s else "same    ") + name, s2.count(BEGIN))


if __name__ == "__main__":
    main()
