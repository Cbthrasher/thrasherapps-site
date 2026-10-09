#!/usr/bin/env python3
"""
Builds /trialmate/reference/: one page per Federal Rule of Evidence, plus an index.

Why: the field app reference pages are the only channel that compounds (they rank
for real technician searches and feed AI assistants). TrialMate had none. The
Federal Rules of Evidence are a US government work, so the official text can be
published in full, and attorneys search for rules by number ("FRE 801", "rule 803
hearsay exceptions") constantly.

What these pages are, and are not. They reproduce the official text, verbatim,
from TrialMate's own corpus (TrialMate/Resources/FRE.json, built from the
Administrative Office of the US Courts PDF of December 1, 2024 and checked by
hand), plus the Rule 801 amendment from the Supreme Court order of April 8, 2026.
They carry NO commentary, summaries or explanations of what a rule means. ThrasherApps
is not a law firm, and the official text is the authority, not us.

Every page is checked before it is written: the text shown, with spacing
normalised, must equal the corpus text exactly. If a single word is lost or
changed, the build stops.

Run:  python3 scripts/build_trialmate_reference.py
Rebuild on 1 December 2026, when amended Rule 801 becomes the text in force.
"""

import html
import json
import re
from datetime import date
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent
TM = Path.home() / "Desktop" / "TrialMate" / "TrialMate" / "Resources"
OUT = SITE / "trialmate" / "reference"
APP = "https://apps.apple.com/us/app/id6748589882"
SOURCE_PDF = "https://www.uscourts.gov/rules-policies/current-rules-practice-procedure/federal-rules-evidence"

CORPUS = json.loads((TM / "FRE.json").read_text())
AMEND = json.loads((TM / "FRE_amendments.json").read_text())
AMENDED = {r["number"]: (a, r) for a in AMEND["amendments"] for r in a["rules"]}
TODAY = date.today().isoformat()

LABEL = re.compile(r"^\(([0-9]+|[a-z]+|[A-Z]+)\)")
ROMAN = {"i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x"}


def norm(s):
    return re.sub(r"\s+", " ", s).strip()


def paragraphs(text):
    """Split the PDF text into its numbered paragraphs, joining wrapped lines.

    A line break starts a new paragraph only when the next line opens with a
    label like (a), (1), (A) or (i), or when a sentence has ended and the next
    line starts a new one. Otherwise it is a line wrap from the PDF.
    """
    lines = text.split("\n")
    out = []
    for ln in lines:
        s = ln.strip()
        if not s:
            continue
        starts_label = bool(LABEL.match(s))
        new_sentence = out and re.search(r"[.:;]$", out[-1]) and s[:1].isupper() and not starts_label
        if not out or starts_label or new_sentence:
            out.append(s)
        else:
            out[-1] += " " + s
    return out


def levels(paras):
    lv, last = [], 0
    for p in paras:
        m = LABEL.match(p)
        if not m:
            lvl = max(0, last - 1) if last else 0
        else:
            lab = m.group(1)
            if lab.isdigit():
                lvl = 1
            elif lab.isupper():
                lvl = 2
            elif lab in ROMAN and last >= 2:
                lvl = 3
            else:
                lvl = 0
            last = lvl
        lv.append(lvl)
    return lv


def render_text(text):
    paras = paragraphs(text)
    shown = " ".join(paras)
    if norm(shown) != norm(text):
        raise SystemExit("text changed while laying it out; refusing to build")
    rows = []
    for p, lvl in zip(paras, levels(paras)):
        rows.append(f'<p class="fre l{lvl}">{html.escape(p)}</p>')
    return "\n".join(rows)


SMALL = {"and", "or", "of", "the", "to", "in", "for", "a", "an", "by", "on"}


def art_name(a):
    """'ARTICLE VIII. HEARSAY' to 'Article VIII. Hearsay'; str.title() wrote 'Viii'."""
    head, _, rest = a.partition(". ")
    words = rest.lower().split()
    rest = " ".join(w if (i and w in SMALL) else w.capitalize() for i, w in enumerate(words))
    return head.replace("ARTICLE", "Article") + (". " + rest if rest else "")


def slug(n):
    return f"rule-{n}.html"


def short_title(r):
    return f"Rule {r['number']}. {r['title']}"


STYLE = """
    .fre{margin:6px 0;line-height:1.55}
    .fre.l1{margin-left:1.4em}.fre.l2{margin-left:2.8em}.fre.l3{margin-left:4.2em}
    .ruleBox{background:#fff;border:1px solid #E5E7EB;border-radius:12px;padding:18px 20px;margin:16px 0}
    .ruleMeta{font-size:.88em;color:#475569;margin-top:12px}
    .amend{background:#FFFBEB;border:1px solid #FCD34D;border-radius:12px;padding:16px 18px;margin:16px 0}
    .amend h2{font-size:1.05em;margin:0 0 6px}
    .amend .was{color:#64748B}
    .refTop{display:flex;gap:14px;align-items:center;flex-wrap:wrap;justify-content:space-between;
      background:#EFF6FF;border:1px solid #BFDBFE;border-radius:12px;padding:14px 16px;margin:14px 0}
    .refTop p{margin:4px 0 0 0;font-size:.93em;color:#1E3A5F}
    .refTop strong{font-size:.78em;font-weight:800;letter-spacing:.05em;text-transform:uppercase;color:#1D4ED8}
    .refTop .refTopText{flex:1 1 380px;min-width:260px}
    .refTop a.btn{flex:0 0 auto;background:#007AFF;color:#fff;border:0}
    .refNav{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;margin:18px 0}
    .refSiblings{background:#fff;border:1px solid #E5E7EB;border-radius:12px;padding:14px 18px;margin:16px 0}
    .refSiblings strong{display:block;font-size:.78em;font-weight:800;letter-spacing:.05em;
      text-transform:uppercase;color:#475569;margin-bottom:6px}
    .refSiblings a{display:inline-block;margin:3px 14px 3px 0;font-size:.92em}
    .article{margin-top:22px}
    .article a{display:block;margin:4px 0}
    .crumb{font-size:.9em;color:#475569;margin-bottom:6px}
    @media (max-width:520px){.refTop{flex-direction:column;align-items:stretch}.refTop a.btn{width:100%;text-align:center}
      .fre.l1{margin-left:.9em}.fre.l2{margin-left:1.8em}.fre.l3{margin-left:2.7em}}
"""

HEADER = """  <header class="site-header">
    <div class="container nav">
      <a class="brand" href="/">ThrasherApps</a>
      <nav class="nav-links">
        <a href="/">Home</a>
        <a href="/apps.html">Apps</a>
        <a href="/trialmate/">TrialMate</a>
        <a href="/trialmate/reference/">Rules of Evidence</a>
        <a href="/trialmate/support.html">Support</a>
      </nav>
    </div>
  </header>"""

FOOTER = """  <footer class="site-footer">
    <div class="container">
      <div>© 2026 ThrasherApps.com</div>
      <div class="mt-2">
        <a href="/trialmate/">TrialMate</a> ·
        <a href="/trialmate/privacy.html">Privacy</a> ·
        <a href="/trialmate/terms.html">Terms</a> ·
        <a href="/trialmate/support.html">Support</a>
      </div>
    </div>
  </footer>"""

TOP = f"""      <div class="refTop">
        <div class="refTopText">
          <strong>Offline in TrialMate</strong>
          <p>All 69 rules are searchable in TrialMate with no signal, which is what a courtroom usually leaves you. The amendment to Rule 801 takes effect in the app on December 1, 2026.</p>
        </div>
        <a class="btn" href="{APP}">Get TrialMate on the App Store</a>
      </div>"""

NOTICE = """      <p class="mt-3" style="font-size:.85em;color:#475569">This page reproduces the official text of the Federal Rules of Evidence for reference. It is not legal advice and adds no commentary. It does not replace the official publication, local rules, or the law that applies in your court. Check the current official text before relying on it.</p>"""


def page(title, desc, canonical, body, extra_head=""):
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{html.escape(title)}</title>
  <meta name="description" content="{html.escape(desc)}" />
  <link rel="canonical" href="{canonical}" />
  <link rel="stylesheet" href="/assets/site.css">
  <style>{STYLE}  </style>
{extra_head}</head>
<body>
{HEADER}
  <section class="section">
    <div class="container">
{body}
    </div>
  </section>
{FOOTER}
</body>
</html>
"""


def amendment_box(r):
    """Rule 801 only: what changes on 1 December 2026, both wordings in full."""
    if r["number"] not in AMENDED:
        return ""
    a, new = AMENDED[r["number"]]
    old_p, new_p = paragraphs(r["text"]), paragraphs(new["text"])
    changed = [(o, n) for o, n in zip(old_p, new_p) if norm(o) != norm(n)]
    if len(old_p) != len(new_p) or not changed:
        raise SystemExit("amendment does not line up paragraph for paragraph; check by hand")
    rows = "".join(
        f'<p class="was"><b>Through November 30, 2026:</b> {html.escape(o)}</p>'
        f'<p><b>From {date.fromisoformat(a["effective"]).strftime("%B %-d, %Y")}:</b> {html.escape(n)}</p>'
        for o, n in changed)
    return f"""      <div class="amend">
        <h2>Amended effective {date.fromisoformat(a["effective"]).strftime("%B %-d, %Y")}</h2>
        <p>The Supreme Court adopted an amendment to this rule by order of April 8, 2026. Under the Rules Enabling Act it takes effect on December 1, 2026 unless Congress provides otherwise. Only this wording changes:</p>
        {rows}
        <p class="ruleMeta">Source: <a href="{html.escape(AMEND["sourceUrl"])}">Supreme Court order of April 8, 2026</a>.</p>
      </div>"""



# ---- "At a glance" (added 9 Oct 2026 so each page carries original, factual structure Google can
# index: the rule's parts, its amendment record and its cross references, all read mechanically from
# the official text. Still no commentary or interpretation.)
MONTHS = {"Jan": "January", "Feb": "February", "Mar": "March", "Apr": "April", "May": "May", "June": "June",
          "July": "July", "Aug": "August", "Sept": "September", "Oct": "October", "Nov": "November", "Dec": "December"}


def cited_rules(r, numbers):
    """Rule numbers this rule's own text names ("Rule 104(a)", "Rules 413 and 414")."""
    t = re.sub(r"\s+", " ", (r.get("text") or "") + " " + (r.get("preamble") or ""))
    out = set()
    for m in re.finditer(r"\bRules?\s", t):
        seg = re.split(r"[.;:]\s|\bof\b|\bthe\b|\bthat\b|\bif\b", t[m.end():m.end() + 60])[0]
        for n in re.findall(r"\b(\d{3,4})\b", seg):
            if n in numbers and n != str(r["number"]):
                out.add(n)
    return sorted(out, key=int)


def amendment_record(history):
    effs = re.findall(r"eff\.\s+([A-Z][a-z]+)\.?\s+(\d{1,2}),\s+(\d{4})", history or "")
    if not effs:
        return ""
    mon, day, year = effs[-1]
    n = len(effs)
    return (f"Amended {n} time{'s' if n != 1 else ''} since enactment; the most recent amendment took effect "
            f"{MONTHS.get(mon, mon)} {day}, {year}.")


def glance_box(r, position, article_size, cites, cited_by):
    parts = [html.escape("(" + n["label"] + ") " + n["heading"]) for n in (r.get("nodes") or [])
             if n.get("label") and n.get("heading")]
    rows = [f"<li>{html.escape(art_name(r['article']))}: rule {position} of {article_size} in this article.</li>"]
    if parts:
        rows.append("<li>Parts: " + " · ".join(parts) + ".</li>")
    rec = amendment_record(r.get("history"))
    if rec:
        rows.append(f"<li>{html.escape(rec)}</li>")
    link = lambda n: f'<a href="/trialmate/reference/{slug(n)}">Rule {n}</a>'
    if cites:
        rows.append("<li>Its text refers to " + ", ".join(link(n) for n in cites) + ".</li>")
    if cited_by:
        rows.append("<li>Referred to by " + ", ".join(link(n) for n in cited_by) + ".</li>")
    rows.append("<li>In TrialMate: the Rules tab, searchable with no signal.</li>")
    return ('      <div class="refSiblings">\n        <strong>At a glance</strong>\n        <ul style="margin:4px 0 0 18px;padding:0;line-height:1.6">'
            + "".join(rows) + "</ul>\n      </div>")


def build():
    rules = CORPUS["rules"]
    if len(rules) != CORPUS["ruleCount"]:
        raise SystemExit("rule count does not match the corpus header")
    OUT.mkdir(parents=True, exist_ok=True)
    by_article = {}
    for r in rules:
        by_article.setdefault(r["article"], []).append(r)
    numbers = {str(r["number"]) for r in rules}
    cites = {str(r["number"]): cited_rules(r, numbers) for r in rules}
    cited_by = {n: sorted((m for m, c in cites.items() if n in c), key=int) for n in numbers}

    for i, r in enumerate(rules):
        prev_r = rules[i - 1] if i else None
        next_r = rules[i + 1] if i + 1 < len(rules) else None
        siblings = "".join(f'<a href="/trialmate/reference/{slug(s["number"])}">{html.escape(short_title(s))}</a>'
                           for s in by_article[r["article"]] if s is not r)
        nav = '<div class="refNav">' + \
            (f'<a href="/trialmate/reference/{slug(prev_r["number"])}">&larr; Rule {prev_r["number"]}</a>' if prev_r else "<span></span>") + \
            (f'<a href="/trialmate/reference/{slug(next_r["number"])}">Rule {next_r["number"]} &rarr;</a>' if next_r else "<span></span>") + \
            "</div>"
        first = norm(paragraphs(r["text"])[0]) if r["text"].strip() else r["title"]
        desc = f"Federal Rule of Evidence {r['number']}, {r['title']}. Official text: {first}"[:300]
        ld = json.dumps({
            "@context": "https://schema.org", "@type": "Legislation",
            "name": f"Federal Rule of Evidence {r['number']}: {r['title']}",
            "legislationIdentifier": f"Fed. R. Evid. {r['number']}",
            "legislationJurisdiction": "United States", "legislationType": "Rule",
            "isPartOf": {"@type": "Legislation", "name": "Federal Rules of Evidence"},
            "url": f"https://thrasherapps.com/trialmate/reference/{slug(r['number'])}"}, indent=1)
        body = f"""      <div class="crumb"><a href="/trialmate/reference/">Federal Rules of Evidence</a> · {html.escape(art_name(r['article']))}</div>
      <h1 class="h2">{html.escape(short_title(r))}</h1>
      <p class="lead">Federal Rules of Evidence, official text as in effect December 1, 2024.</p>
{TOP}
{amendment_box(r)}
      <div class="ruleBox">
{render_text(r['text']) if r['text'].strip() else '<p class="fre">' + html.escape(r['preamble'] or '[Reserved]') + '</p>'}
        <p class="ruleMeta">{html.escape(r['history'])}</p>
        <p class="ruleMeta">Source: Federal Rules of Evidence, December 1, 2024, Administrative Office of the United States Courts, <a href="{SOURCE_PDF}">uscourts.gov</a>.</p>
      </div>
{glance_box(r, by_article[r["article"]].index(r) + 1, len(by_article[r["article"]]), cites[str(r["number"])], cited_by[str(r["number"])])}
{nav}
      <div class="refSiblings">
        <strong>More in {html.escape(art_name(r['article']))}</strong>
        {siblings or '<span>This is the only rule in this article.</span>'}
      </div>
{NOTICE}"""
        (OUT / slug(r["number"])).write_text(page(
            f"Federal Rule of Evidence {r['number']}: {r['title']} | TrialMate reference",
            desc, f"https://thrasherapps.com/trialmate/reference/{slug(r['number'])}", body,
            f'  <script type="application/ld+json">\n{ld}\n  </script>\n'))

    arts = "".join(
        f'<div class="article"><h2 style="font-size:1.05em">{html.escape(art_name(art))}</h2>' +
        "".join(f'<a href="/trialmate/reference/{slug(r["number"])}">{html.escape(short_title(r))}</a>' for r in rs) +
        "</div>" for art, rs in by_article.items())
    body = f"""      <div class="crumb"><a href="/trialmate/">TrialMate</a></div>
      <h1 class="h2">Federal Rules of Evidence</h1>
      <p class="lead">The official text of all {len(rules)} rules, as in effect December 1, 2024, with the amendment to Rule 801 that takes effect December 1, 2026. One page per rule, no commentary.</p>
{TOP}
      <div class="ruleBox">{arts}</div>
{NOTICE}"""
    (OUT / "index.html").write_text(page(
        "Federal Rules of Evidence, full text by rule | TrialMate reference",
        f"The official text of all {len(rules)} Federal Rules of Evidence, one page per rule, with the Rule 801 amendment effective December 1, 2026. Free to read, no account.",
        "https://thrasherapps.com/trialmate/reference/", body))
    print(f"built {len(rules)} rule pages and the index in {OUT.relative_to(SITE)}")


if __name__ == "__main__":
    build()
