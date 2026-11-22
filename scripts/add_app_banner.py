#!/usr/bin/env python3
"""Adds Apple's Smart App Banner to every page of each live app's folder (22 Nov 2026).

App Analytics, 22 Oct to 21 Nov 2026: the site's fault code and reference pages get real Google traffic, yet "Web
Referrer" brought about 2 downloads a month across all apps, and no page carried the banner. On an iPhone in Safari the
banner shows the app's icon, rating and a Get or Open button above the page; elsewhere the tag does nothing.

Only apps that are live on the App Store are listed (a banner for an app that is not live shows nothing useful).
Add UST Tester (6834855611) here on its release day. Idempotent, so run it again after any page builder:
    python3 scripts/add_app_banner.py
"""
import os
import re

SITE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APPS = {
    "droptubebuilder": "6740597739", "loopwatt": "6790129179", "fieldwatt": "6787932579", "storewatt": "6788153038",
    "plugwatt": "6788584092", "rackwatt": "6790170168", "trialmate": "6748589882", "winnow": "6787541045",
    "paidup": "6785131011", "pausemeno": "6785331336", "sideworktax": "6782625305", "lavadash": "6742521742",
    "blockthrasher": "6746172717", "plainread": "6824189689", "plainqr": "6821741458", "headpainjournal": "6785294370",
    "streakquest": "6743329674",
}


def main():
    added = skipped = 0
    for folder, app_id in APPS.items():
        root_dir = os.path.join(SITE, folder)
        if not os.path.isdir(root_dir):
            continue
        tag = f'<meta name="apple-itunes-app" content="app-id={app_id}" />'
        for root, dirs, files in os.walk(root_dir):
            for f in files:
                if not f.endswith(".html"):
                    continue
                p = os.path.join(root, f)
                s = open(p, encoding="utf-8").read()
                if 'name="apple-itunes-app"' in s:
                    skipped += 1
                    continue
                m = re.search(r"<meta name=\"viewport\"[^>]*>", s) or re.search(r"<head[^>]*>", s, re.I)
                if not m:
                    continue
                s = s[:m.end()] + "\n  " + tag + s[m.end():]
                open(p, "w", encoding="utf-8").write(s)
                added += 1
    print(f"banner added to {added} pages, {skipped} already had it")


if __name__ == "__main__":
    main()
