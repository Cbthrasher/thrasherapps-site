#!/usr/bin/env python3
"""
Builds Open Graph share cards (1200x630) for each app, and injects og:image,
twitter card, and schema.org SoftwareApplication markup into product pages.

Why: without an og:image, a link shared on LinkedIn, Reddit, or in a text
message renders as a bare blue string. With one, it renders as a card with the
app icon and name, which is the difference between people clicking and not.
The schema.org block lets Google show price and category in results.

Re run any time:
    python3 scripts/build_share_cards.py
"""

import json
import os
import re
import urllib.request

from PIL import Image, ImageDraw, ImageFont

SITE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(SITE, "assets", "share")

APPS = {
    "fieldwatt":       ("6787932579", "Offline field toolkit for utility scale solar technicians"),
    "storewatt":       ("6788153038", "Offline field toolkit for grid scale battery storage"),
    "rackwatt":        ("6790170168", "Offline toolkit for data center critical facilities"),
    "loopwatt":        ("6790129179", "NFPA 72 inspections and tools for fire alarm techs"),
    "plugwatt":        ("6788584092", "Offline toolkit for EV charging technicians"),
    "winnow":          ("6787541045", "Find duplicates and free up space, all on device"),
    "paidup":          ("6785131011", "Clean invoices in seconds, private and on device"),
    "pausemeno":       ("6785331336", "Track menopause symptoms and see your patterns"),
    "headpainjournal": ("6785294370", "Track migraines in one tap, find your triggers"),
    "sideworktax":     ("6782625305", "Set aside the right tax on every side job"),
    "droptubebuilder": ("6740597739", "Drop tube cut math for fuel system installers"),
    "trialmate":       ("6748589882", "Clinical trial companion, private by design"),
    "streakquest":     ("6743329674", "Build habits with streaks that stick"),
}

BG = (15, 23, 42)
ACCENT = (56, 189, 248)
TEXT = (241, 245, 249)
DIM = (148, 163, 184)


def font(size, bold=False):
    paths = [
        "/System/Library/Fonts/SFNSDisplay.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial Bold.ttf" if bold else "/Library/Fonts/Arial.ttf",
    ]
    for p in paths:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size, index=1 if (bold and p.endswith(".ttc")) else 0)
            except Exception:
                continue
    return ImageFont.load_default()


def lookup(appid):
    url = f"https://itunes.apple.com/lookup?id={appid}&country=us"
    with urllib.request.urlopen(url, timeout=20) as r:
        data = json.load(r)
    return data["results"][0] if data.get("resultCount") else None


def wrap(draw, text, fnt, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if draw.textlength(trial, font=fnt) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def build_card(key, meta, tagline):
    img = Image.new("RGB", (1200, 630), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 1200, 8], fill=ACCENT)

    # App icon, rounded
    try:
        with urllib.request.urlopen(meta["artworkUrl512"], timeout=20) as r:
            icon = Image.open(r).convert("RGBA").resize((260, 260), Image.LANCZOS)
        mask = Image.new("L", (260, 260), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, 259, 259], radius=58, fill=255)
        img.paste(icon, (90, 185), mask)
        text_x = 400
    except Exception:
        text_x = 90

    name = meta.get("trackName", key).split(":")[0].strip()
    d.text((text_x, 190), name, font=font(72, True), fill=TEXT)

    fnt = font(34)
    y = 290
    for line in wrap(d, tagline, fnt, 1200 - text_x - 90)[:3]:
        d.text((text_x, y), line, font=fnt, fill=DIM)
        y += 46

    d.text((text_x, y + 26), "thrasherapps.com  ·  iPhone and iPad",
           font=font(28, True), fill=ACCENT)

    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f"{key}.png")
    img.save(path, "PNG", optimize=True)
    return path


def inject(key, meta):
    """Add og:image, twitter card, and SoftwareApplication schema to the page."""
    p = os.path.join(SITE, key, "index.html")
    if not os.path.exists(p):
        return False
    t = open(p).read()
    if "og:image" in t and "application/ld+json" in t:
        return False

    img_url = f"https://thrasherapps.com/assets/share/{key}.png"
    page_url = f"https://thrasherapps.com/{key}/"
    name = meta.get("trackName", key)
    desc = re.sub(r"\s+", " ", (meta.get("description") or ""))[:180].strip()
    price = meta.get("price", 0.0) or 0.0
    genre = meta.get("primaryGenreName", "Utilities")

    add = []
    if "og:image" not in t:
        add.append(f'  <meta property="og:image" content="{img_url}" />')
        add.append('  <meta name="twitter:card" content="summary_large_image" />')
        add.append(f'  <meta name="twitter:image" content="{img_url}" />')
    if "application/ld+json" not in t:
        schema = {
            "@context": "https://schema.org",
            "@type": "SoftwareApplication",
            "name": name,
            "operatingSystem": "iOS 17.6 or later",
            "applicationCategory": "BusinessApplication" if genre in ("Utilities", "Business", "Productivity") else "MobileApplication",
            "url": page_url,
            "downloadUrl": f"https://apps.apple.com/us/app/id{meta['trackId']}",
            "description": desc,
            "author": {"@type": "Person", "name": "Chris Thrasher"},
            "offers": {"@type": "Offer", "price": f"{price:.2f}", "priceCurrency": "USD"},
        }
        add.append('  <script type="application/ld+json">'
                   + json.dumps(schema, separators=(",", ":")) + "</script>")

    t = t.replace("</head>", "\n".join(add) + "\n</head>", 1)
    open(p, "w").write(t)
    return True


def main():
    made, injected = [], []
    for key, (appid, tagline) in APPS.items():
        try:
            meta = lookup(appid)
        except Exception as e:
            print(f"{key}: lookup failed ({e})")
            continue
        if not meta:
            print(f"{key}: not found on the App Store")
            continue
        build_card(key, meta, tagline)
        made.append(key)
        if inject(key, meta):
            injected.append(key)
    print(f"share cards built: {len(made)}")
    print(f"pages updated with og:image and schema: {len(injected)}")


if __name__ == "__main__":
    main()
