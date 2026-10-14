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
        "Veeder-Root TLS-450 PLUS Alarm Codes: Meanings and Fixes",
        "What each Veeder-Root TLS-450 PLUS alarm means, the most likely cause first, and the checks to make on site. "
        "All 51 alarms, free, from a fuel systems tech with 25 years in the field."),
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
}


def main():
    for path, (title, desc) in PAGES.items():
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
