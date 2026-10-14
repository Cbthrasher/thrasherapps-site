#!/usr/bin/env python3
"""Adds Cloudflare Web Analytics to every page (14 Oct 2026, Chris asked for a private visitor counter).

Cloudflare Web Analytics sets no cookies and does not track individual visitors; it counts page views and visits
in aggregate. The site is served by GitHub Pages (not proxied through Cloudflare), so Cloudflare's "automatic setup"
cannot inject it; this puts the beacon tag before </body>. The token is public by design (it is in every page).
Skips pages that already have it, so run it again after any page builder:
    python3 scripts/add_analytics.py
"""
import os

SITE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TAG = ("<!-- Cloudflare Web Analytics --><script defer src='https://static.cloudflareinsights.com/beacon.min.js' "
       "data-cf-beacon='{\"token\": \"b89f3a0b9dd94ecb991c6e31aae799f8\"}'></script><!-- End Cloudflare Web Analytics -->")


def main():
    added = skipped = nobody = 0
    for root, dirs, files in os.walk(SITE):
        dirs[:] = [d for d in dirs if d not in (".git", "scripts", "data")]
        for f in files:
            if not f.endswith(".html"):
                continue
            p = os.path.join(root, f)
            s = open(p, encoding="utf-8").read()
            if "static.cloudflareinsights.com/beacon" in s:
                skipped += 1
                continue
            i = s.lower().rfind("</body>")
            if i < 0:
                nobody += 1
                continue
            open(p, "w", encoding="utf-8").write(s[:i] + TAG + "\n" + s[i:])
            added += 1
    print(f"added {added}, already had it {skipped}, no </body> {nobody}")


if __name__ == "__main__":
    main()
