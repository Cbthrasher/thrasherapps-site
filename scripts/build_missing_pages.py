#!/usr/bin/env python3
"""
Builds product pages for the apps that never got one, using their real
App Store metadata. Existing pages are left alone.
"""

import json
import os
import urllib.request

SITE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PAGES = [
    {
        "key": "trialmate", "appid": "6748589882", "emoji": "⚖️",
        "badge": "iOS · Trial preparation for attorneys",
        "lead": "The trial preparation companion for attorneys. Manage unlimited cases with complete data isolation, analyze documents, organize exhibits and witnesses, and walk into the courtroom with everything in order.",
        "features": [
            ("📁 Multi trial management", "Run unlimited trial cases side by side with complete data isolation. Switch between matters without anything bleeding across."),
            ("📄 Document analysis", "Scan legal documents and pull out the key facts, arguments, and issues worth flagging before you are standing up."),
            ("🗂️ Built for the courtroom", "Exhibits, witnesses, and the running order kept in one place, so prep survives contact with a live trial day."),
            ("🔒 Private by design", "Your case material stays yours. No advertising and no tracking."),
        ],
        "links": ["privacy.html", "terms.html"],
    },
    {
        "key": "streakquest", "appid": "6743329674", "emoji": "🔥",
        "badge": "iOS · Habit building",
        "lead": "Habit building as a daily challenge. Create habits across fitness, learning, productivity, and wellness, check in each day, and watch the streak grow into something you do not want to break.",
        "features": [
            ("📈 Streaks that motivate", "Every completed day grows the streak. The longer it runs, the more it pulls you back tomorrow."),
            ("🧊 Streak freezes", "Life happens. A freeze saves the run on the day everything goes sideways, so one bad day does not undo a month."),
            ("🗂️ Categories that fit", "Fitness, learning, productivity, wellness. Build the set of habits you actually want, not a template."),
            ("🔒 Yours alone", "Your habits stay on your device. No ads, no tracking."),
        ],
        "links": ["privacy.html", "terms.html", "support.html"],
    },
    {
        "key": "blockthrasher", "appid": "6746172717", "emoji": "🧱",
        "badge": "iOS · Neon block puzzle",
        "lead": "Tap. Clear. Thrash. A fast, satisfying block clearing puzzle with an electrifying neon arcade style. Tap groups of three or more matching blocks, watch the board collapse and refill, and chain quick clears into massive combos.",
        "features": [
            ("⚡ Simple to play, hard to put down", "Tap any group of three or more touching blocks of the same color. Bigger groups mean bigger points; clear five or more and the whole row explodes."),
            ("🔗 Combo chains", "Chain clears back to back to build a multiplier up to five times. Speed pays."),
            ("🎆 Neon arcade style", "Level up with a burst of neon celebration as the progress bar fills."),
            ("🔀 Out of moves", "Reshuffle when the board stalls, but choose your moment."),
        ],
        "links": [],
    },
    {
        "key": "lavadash", "appid": "6742521742", "emoji": "🌋",
        "badge": "iOS · Reflex arcade game",
        "lead": "Can you survive when the floor turns to lava? A fast, reaction based game that tests your reflexes and timing. Green means safe, red means danger, and the timing is never quite what you expect.",
        "features": [
            ("⏱️ Pure reflex", "Watch the floor and move before it turns. One wrong step ends the run."),
            ("🎲 Unpredictable by design", "The pattern shifts so you cannot memorize your way through it."),
            ("🎮 Easy to play, hard to master", "Perfect for a quick session, punishing enough to keep pulling you back."),
            ("🏆 Beat your own record", "Last as long as you can and push the streak further each time."),
        ],
        "links": [],
    },
]

TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{name} — {tagline} | ThrasherApps</title>
  <meta name="description" content="{desc}" />
  <link rel="canonical" href="https://thrasherapps.com/{key}/" />
  <link rel="stylesheet" href="/assets/site.css">
  <meta property="og:title" content="{name} — {tagline}" />
  <meta property="og:description" content="{desc}" />
  <meta property="og:type" content="website" />
  <meta property="og:url" content="https://thrasherapps.com/{key}/" />
  <meta property="og:image" content="https://thrasherapps.com/assets/share/{key}.png" />
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:image" content="https://thrasherapps.com/assets/share/{key}.png" />
  <script type="application/ld+json">{schema}</script>
</head>
<body>

  <header class="site-header">
    <div class="container nav">
      <a class="brand" href="/">ThrasherApps</a>
      <nav class="nav-links">
        <a href="/">Home</a>
        <a href="/apps.html">Apps</a>
        <a href="/ai.html">AI Solutions</a>
        <a href="/about.html">About</a>
        <a href="/contact.html">Contact</a>
      </nav>
    </div>
  </header>

  <section class="hero">
    <div class="container hero-inner">
      <span class="badge">{badge}</span>
      <h1>{emoji} {name}</h1>
      <p class="lead">{lead}</p>
      <div class="mt-2">
        <span class="badge">Now on the App Store</span>
      </div>
      <div class="mt-2">
        <a class="btn" href="https://apps.apple.com/us/app/id{appid}">Download on the App Store</a>
        <a class="btn btn-secondary" href="#features">See what it does ↓</a>
      </div>
    </div>
  </section>

  <section class="section section--tight" id="features">
    <div class="container">
      <h2 class="h2">What it does</h2>
      <div class="grid grid-2 mt-3">
{cards}      </div>
    </div>
  </section>

  <footer class="site-footer">
    <div class="container">
      <div>© 2026 ThrasherApps.com — Built by Chris Thrasher</div>
      <div class="mt-2">
        <a href="/apps.html">All apps</a>{extra} ·
        <a href="/contact.html">Contact</a>
      </div>
    </div>
  </footer>

</body>
</html>
"""


def main():
    made = []
    for spec in PAGES:
        key = spec["key"]
        outdir = os.path.join(SITE, key)
        os.makedirs(outdir, exist_ok=True)
        path = os.path.join(outdir, "index.html")
        if os.path.exists(path):
            print(f"{key}: already has a page, left alone")
            continue

        url = f"https://itunes.apple.com/lookup?id={spec['appid']}&country=us"
        with urllib.request.urlopen(url, timeout=20) as r:
            meta = json.load(r)["results"][0]

        name = meta["trackName"]
        tagline = spec["badge"].split("· ", 1)[-1]
        desc = spec["lead"][:180]
        schema = json.dumps({
            "@context": "https://schema.org",
            "@type": "SoftwareApplication",
            "name": name,
            "operatingSystem": "iOS",
            "applicationCategory": "GameApplication" if meta.get("primaryGenreName") == "Games" else "MobileApplication",
            "url": f"https://thrasherapps.com/{key}/",
            "downloadUrl": f"https://apps.apple.com/us/app/id{spec['appid']}",
            "description": desc,
            "author": {"@type": "Person", "name": "Chris Thrasher"},
            "offers": {"@type": "Offer", "price": f"{meta.get('price', 0.0):.2f}", "priceCurrency": "USD"},
        }, separators=(",", ":"))

        cards = ""
        for title, body in spec["features"]:
            cards += (f'        <div class="card">\n          <h3>{title}</h3>\n'
                      f'          <p class="mt-1">{body}</p>\n        </div>\n')

        extra = ""
        for link in spec["links"]:
            label = link.replace(".html", "").capitalize()
            if os.path.exists(os.path.join(outdir, link)):
                extra += f' ·\n        <a href="{link}">{label}</a>'

        open(path, "w").write(TEMPLATE.format(
            name=name, tagline=tagline, desc=desc, key=key, schema=schema,
            badge=spec["badge"], emoji=spec["emoji"], lead=spec["lead"],
            appid=spec["appid"], cards=cards, extra=extra))
        made.append(key)
        print(f"{key}: page created")
    print(f"\npages created: {len(made)}")


if __name__ == "__main__":
    main()
