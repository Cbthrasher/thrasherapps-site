#!/usr/bin/env python3
"""
Fetches the official committee notes for every Federal Rule of Evidence and writes
scripts/data/fre_committee_notes.json for build_trialmate_reference.py.

Why (30 Oct 2026): the rule pages carried the rule text alone, 300 to 500 words that
uscourts.gov and Cornell already rank for. Search Console, October: 4,160 impressions,
9 clicks, average position 10.3. The pages needed depth, and the no commentary rule
still stands (ThrasherApps is not a law firm). The committee notes are the depth that
keeps it: the Advisory Committee's notes on the proposed rules and on every amendment,
and the House, Senate and Conference reports, as Congress printed them with the rules.
Lawyers read them to argue what a rule means. They are a US government work.

Source: United States Code, 2024 Edition, Title 28 Appendix, from govinfo.gov (the
Government Publishing Office). uscode.house.gov was running in a reduced mode on 30 Oct
2026 and served no rule pages.

Checks, all of which stop the run:
  * each govinfo rule text must equal TrialMate's corpus text word for word, so the
    notes belong to the same edition of the rule (one known corpus defect, the Rule 412
    title split at "Pre-disposition", is allowed and named);
  * every note keeps its words: the plain text written to the JSON must equal the plain
    text of the govinfo page section it came from.

Editorial notes by the Law Revision Counsel ("Amendment by Public Law", "Effective
Date", "References in Text" and the like) are left out; they are not committee notes.

Run:  python3 scripts/fetch_fre_committee_notes.py            (downloads, about a minute)
      python3 scripts/fetch_fre_committee_notes.py --from DIR (DIR holds 101.htm ... 1103.htm)
"""

import html
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent
TM = Path.home() / "Desktop" / "TrialMate" / "TrialMate" / "Resources"
OUT = SITE / "scripts" / "data" / "fre_committee_notes.json"
EDITION = "2024"
URL = ("https://www.govinfo.gov/content/pkg/USCODE-{ed}-title28/html/"
       "USCODE-{ed}-title28-app-federalru-dup2-rule{n}.htm")

NOTE_START = re.compile(r"^(Notes of|Committee Notes|Explanatory Note)")
EDITORIAL = re.compile(r"^(Amendment by Public Law|Effective Date|References in Text|Short Title|"
                       r"Termination of Trust Territory|Congressional Modification)")
# govinfo paragraph classes to the indent the page shows them at.
INDENT = {"note-body": 0, "note-body-1em": 1, "note-body-block": 1, "note-body-block-1em": 2,
          "statutory-body": 1, "statutory-body-1em": 1, "statutory-body-2em": 2, "statutory-body-3em": 3}
KEEP_TAGS = re.compile(r"</?(i|b|sup)>")


def words(s):
    """Text reduced to its words, for comparing two copies that differ only in typography."""
    s = html.unescape(s)
    for a, b in (("’", "'"), ("‘", "'"), ("“", '"'), ("”", '"'), ("\xa0", " ")):
        s = s.replace(a, b)
    return re.sub(r"[^A-Za-z0-9]+", " ", s).lower().split()


def strip_tags(s):
    return re.sub(r"<[^>]+>", " ", s)


def clean_inline(raw):
    """govinfo inline HTML to safe inline HTML: keeps <i>, <b>, <sup>; drops links and spans."""
    out = []
    for piece in re.split(r"(<[^>]+>)", raw):
        if piece.startswith("<"):
            if KEEP_TAGS.fullmatch(piece):
                out.append(piece)
            continue
        out.append(html.escape(html.unescape(piece), quote=False))
    s = re.sub(r"\s+", " ", "".join(out)).strip()
    return re.sub(r"<(i|b|sup)>\s*</\1>", "", s)


def parse(n, page, corpus_rule):
    page = re.sub(r"<!--\s*PDFPage:\d+\s*-->", "", page)
    m = re.search(r"</h3>(.*?)<p class=\"source-credit\">(.*?)</p>(.*)</body>", page, re.S)
    if not m:
        raise SystemExit(f"Rule {n}: page layout not recognised")
    gov_text, credit, rest = m.groups()

    ours = words((corpus_rule.get("text") or "") or (corpus_rule.get("preamble") or ""))
    theirs = words(strip_tags(gov_text))
    if n == "412" and ours[:1] == ["disposition"]:
        ours = ours[1:]   # corpus defect: the title's "Pre-" line break left "disposition" in the text
    if ours != theirs:
        raise SystemExit(f"Rule {n}: govinfo text differs from the TrialMate corpus; wrong edition?")

    notes, current, skipping, kept_plain = [], None, False, []
    for tag, cls, inner in re.findall(r'<(h4|p)(?: class="([^"]*)")?[^>]*>(.*?)</\1>', rest, re.S):
        text = re.sub(r"\s+", " ", html.unescape(strip_tags(inner))).strip()
        if not text:
            continue
        if tag == "h4" and cls == "note-head":
            if NOTE_START.match(text):
                current, skipping = {"heading": text, "blocks": []}, False
                notes.append(current)
                kept_plain.append(text)
                continue
            if EDITORIAL.match(text) or current is None:
                skipping = True
                continue
        if skipping or current is None:
            continue
        if tag == "h4":
            current["blocks"].append({"kind": "subhead", "html": clean_inline(inner)})
        elif cls == "5802I92":
            current["blocks"].append({"kind": "break", "html": html.escape(text)})
        elif cls == "footnote":
            current["blocks"].append({"kind": "footnote", "html": clean_inline(inner)})
        elif cls in INDENT:
            current["blocks"].append({"kind": "p", "indent": INDENT[cls], "html": clean_inline(inner)})
        else:
            raise SystemExit(f"Rule {n}: unknown paragraph class {cls!r}; look at it before publishing")
        kept_plain.append(text)

    shown = " ".join(x for nt in notes for x in [nt["heading"]] + [strip_tags(b["html"]) for b in nt["blocks"]])
    if words(shown) != words(" ".join(kept_plain)):
        raise SystemExit(f"Rule {n}: a note lost or changed a word while cleaning")
    return {"credit": re.sub(r"\s+", " ", html.unescape(strip_tags(credit))).strip(), "notes": notes,
            "url": URL.format(ed=EDITION, n=n), "words": len(words(shown))}


def main():
    src = Path(sys.argv[sys.argv.index("--from") + 1]) if "--from" in sys.argv else None
    rules = json.loads((TM / "FRE.json").read_text())["rules"]
    out = {"source": f"United States Code, {EDITION} Edition, Title 28 Appendix, Federal Rules of Evidence",
           "publisher": "U.S. Government Publishing Office, govinfo.gov", "rules": {}}
    for r in rules:
        n = str(r["number"])
        if src:
            page = (src / f"{n}.htm").read_text(errors="replace")
        else:
            with urllib.request.urlopen(URL.format(ed=EDITION, n=n), timeout=30) as resp:
                page = resp.read().decode("utf-8", errors="replace")
            time.sleep(0.5)
        out["rules"][n] = parse(n, page, r)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    total = sum(v["words"] for v in out["rules"].values())
    empty = [n for n, v in out["rules"].items() if not v["notes"]]
    print(f"wrote {OUT.relative_to(SITE)}: {len(out['rules'])} rules, {total:,} words of notes"
          + (f"; no notes for {', '.join(empty)}" if empty else ""))


if __name__ == "__main__":
    main()
