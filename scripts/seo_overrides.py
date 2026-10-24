#!/usr/bin/env python3
"""Search titles and descriptions for the pages Google shows most (14 Oct 2026).

Search Console, 28 days to 11 Oct: 2,820 impressions, 11 clicks (0.4%), average position 9.5. The top pages were
being shown and not clicked: the TLS-450 PLUS page 353 times and the MagVFC page 316 times, both with 0 clicks.
At the bottom of page one the title and description are the whole pitch, so they now lead with what the searcher
typed (the controller and "alarm codes" or "FRE 802") and say what they get, without promising anything the page
does not have. The FieldWatt tables page also had fault code wording ("likely cause") on a page of NEC tables.

The reference pages were last edited by hand after generation, so this runs on the built HTML and is safe to run
again after any rebuild:
    python3 scripts/seo_overrides.py
"""
import html
import os
import re

SITE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PAGES = {
    "droptubebuilder/reference/veeder-root-tls-450-plus.html": (
        "TLS-450 PLUS Alarms: CSLD, Probe Out, Sudden Loss, Line Leak",
        "Veeder-Root TLS-450 PLUS alarm meanings and fixes: CSLD Rate Increase Warning, CSLD Idle Time Warning, Gross Test Needed, Probe Out, Sudden Loss and Pressure Line Leak, each with the most likely cause first. All 51 alarms, free, from a fuel tech with 25 years in the field."),
    "droptubebuilder/reference/fe-petro-magvfc.html": (
        "FE Petro MagVFC Fault Codes (UL, LI, Er, OC, SC) and Fixes",
        "Every FE Petro MagVFC fault and status code, what it means, the likely cause and what to check, plus the DIP "
        "switch settings. Free, from a fuel systems tech with 25 years in the field."),
    "droptubebuilder/reference/veeder-root-tls-350.html": (
        "Veeder-Root TLS-350 Alarm Codes: Meanings and Fixes",
        "What each Veeder-Root TLS-350 alarm means, the most likely cause first, and the checks to make on site. "
        "All 48 alarms, free, from a fuel systems tech with 25 years in the field."),
    "droptubebuilder/reference/guardian-spgc-220-single-phase.html": (
        "Guardian SPGC-220 Fault Codes (Single Phase): Causes and Fixes",
        "Every Guardian SPGC-220 single phase submersible pump controller fault and status code, with the likely cause "
        "and what to check. Free, from a fuel systems tech with 25 years in the field."),
    "droptubebuilder/reference/franklin-incon-evo.html": (
        "Franklin Incon EVO Alarm Codes: Meanings and Fixes",
        "What each Franklin Fueling Incon EVO alarm means, the likely cause, and what to check on site. Free, from a "
        "fuel systems tech with 25 years in the field."),
    "fieldwatt/reference/codeTables.html": (
        "NEC 690 Solar Tables: Voltage Correction, Ampacity, Conduit Fill",
        "NEC Table 690.7(A) voltage correction, ambient temperature correction for 90 C conductors, conduit fill "
        "adjustment, conductor ampacity, and NEC 690 versus 691, in one place for solar PV techs. Free."),
    "trialmate/reference/rule-802.html": (
        "FRE 802: The Rule Against Hearsay (Full Text)",
        "Federal Rule of Evidence 802, the rule against hearsay, in its official text, with where it sits in Article "
        "VIII and links to Rules 801 and 803. Current, free, no account."),
    "trialmate/reference/rule-105.html": (
        "FRE 105: Limiting Evidence (Full Text)",
        "Federal Rule of Evidence 105, limiting evidence that is not admissible against other parties or for other "
        "purposes, in its official text with its amendment history. Current, free, no account."),
    "trialmate/reference/rule-610.html": (
        "FRE 610: Religious Beliefs or Opinions (Full Text)",
        "Federal Rule of Evidence 610, religious beliefs or opinions, in its official text with its amendment history "
        "and the rest of Article VI on witnesses. Current, free, no account."),
    "trialmate/reference/rule-501.html": (
        "FRE 501: Privilege in General (Full Text)",
        "Federal Rule of Evidence 501, privilege in general, in its official text, with Rule 502 on attorney client "
        "privilege and work product. Current, free, no account."),
    # 19 Oct 2026: the next pages by impressions (Search Console, 28 days: TLS-450 103, rules 614 113, 1001 104,
    # 805 104, 605 76, 606 71). Searches are "fre 614", "rule 805", "federal rule of evidence 611", so the title leads
    # with "FRE nnn" and stays short enough that Google does not cut it.
    "droptubebuilder/reference/veeder-root-tls-450.html": (
        "TLS-450 Alarms: CSLD Rate Increase, Probe Out, Sudden Loss",
        "Veeder-Root TLS-450 alarm meanings and fixes: CSLD Rate Increase Warning, CSLD Idle Time Warning, Gross Test Needed, Probe Out, Sudden Loss and Pressure Line Leak, each with the most likely cause first. All 51 alarms, free, from a fuel tech with 25 years in the field."),
    "droptubebuilder/reference/index.html": (
        "Fuel System Fault Codes: Veeder-Root, Gilbarco, Wayne, Franklin",
        "Free fault and alarm code reference for fuel system techs: Veeder-Root TLS consoles, Gilbarco and Wayne "
        "dispensers, Franklin Fueling and pump controllers. Likely cause first, then the checks in order."),
    "trialmate/reference/rule-614.html": (
        "FRE 614: Court's Calling or Examining a Witness (Full Text)",
        "Federal Rule of Evidence 614, the court calling or examining a witness and objecting to it, in its official "
        "text with its amendment history. Current, free, no account."),
    "trialmate/reference/rule-1001.html": (
        "FRE 1001: Definitions for Writings, Recordings and Photos",
        "Federal Rule of Evidence 1001, the definitions behind the best evidence rule: writing, recording, photograph, "
        "original and duplicate, in its official text. Current, free, no account."),
    "trialmate/reference/rule-805.html": (
        "FRE 805: Hearsay Within Hearsay (Full Text)",
        "Federal Rule of Evidence 805, hearsay within hearsay, in its official text, with links to Rules 801 to 807. "
        "Current, free, no account."),
    "trialmate/reference/rule-605.html": (
        "FRE 605: Judge's Competency as a Witness (Full Text)",
        "Federal Rule of Evidence 605, the presiding judge may not testify as a witness, in its official text with its "
        "amendment history. Current, free, no account."),
    "trialmate/reference/rule-606.html": (
        "FRE 606: Juror's Competency as a Witness (Full Text)",
        "Federal Rule of Evidence 606, juror testimony at trial and about a verdict, in its official text with its "
        "amendment history. Current, free, no account."),
    "trialmate/reference/rule-1003.html": (
        "FRE 1003: Admissibility of Duplicates (Full Text)",
        "Federal Rule of Evidence 1003, when a duplicate is admissible like the original, in its official text with "
        "the definitions in Rule 1001. Current, free, no account."),
    "trialmate/reference/rule-406.html": (
        "FRE 406: Habit; Routine Practice (Full Text)",
        "Federal Rule of Evidence 406, evidence of a person's habit or an organization's routine practice, in its "
        "official text with its amendment history. Current, free, no account."),
    "trialmate/reference/rule-611.html": (
        "FRE 611: Mode and Order of Examining Witnesses (Full Text)",
        "Federal Rule of Evidence 611, control of the mode and order of examining witnesses, scope of cross and "
        "leading questions, in its official text. Current, free, no account."),
}


def rule_pages():
    """25 Oct 2026: every Federal Rules of Evidence page, not just the top dozen. Searches are "fre 105", "fre 610",
    "federal rule of evidence 501", "rule 406", so the title leads with "FRE nnn" and the description with the full
    "Federal Rule of Evidence nnn". Pages already tuned by hand in PAGES keep their own wording."""
    out = {}
    folder = os.path.join(SITE, "trialmate", "reference")
    for name in sorted(os.listdir(folder)):
        m = re.fullmatch(r"rule-(\d+)\.html", name)
        path = f"trialmate/reference/{name}"
        if not m or path in PAGES:
            continue
        s = open(os.path.join(folder, name), encoding="utf-8").read()
        h = re.search(r"<h1[^>]*>\s*Rule\s+\d+\.\s*([^<]+)", s)
        if not h:
            continue
        n, rule = m.group(1), html.unescape(h.group(1)).strip().rstrip(".")
        title = f"FRE {n}: {rule} (Full Text)"
        if len(title) > 62:
            title = f"FRE {n}: {rule}"
        desc = (f"Federal Rule of Evidence {n}, {rule}, in its official current text with its amendment notes. "
                f"Free to read, no account, from the TrialMate rules reference.")
        out[path] = (title, desc)
    return out


def main():
    for path, (title, desc) in {**PAGES, **rule_pages()}.items():
        full = os.path.join(SITE, path)
        s = open(full, encoding="utf-8").read()
        new = re.sub(r"<title>.*?</title>", f"<title>{html.escape(title)}</title>", s, count=1, flags=re.S)
        new = re.sub(r'<meta name="description" content="[^"]*"\s*/?>',
                     f'<meta name="description" content="{html.escape(desc, quote=True)}" />', new, count=1)
        if new != s:
            open(full, "w", encoding="utf-8").write(new)
        print(f"{'updated' if new != s else 'same   '} {len(title):3d}/{len(desc):3d}  {path}")


if __name__ == "__main__":
    main()
