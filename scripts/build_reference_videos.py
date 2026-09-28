#!/usr/bin/env python3
"""Put Chris's YouTube videos on the reference page for the code they cover.

Each video is one entry in data/reference_videos.json:

    {"page": "droptubebuilder/reference/veeder-root-tls-300.html",
     "anchor": "fuel-alarm",
     "youtube": "VIDEO_ID",
     "title": "Veeder-Root TLS-300 Fuel Alarm: what it means and how to fix it",
     "uploaded": "2026-09-28",
     "shape": "short"}            # "short" (9:16) or "wide" (16:9)

The video is embedded at the end of that code's section, and every video on a page
is also described to Google as a VideoObject, so the page can show up in video
results for that code. Running it again replaces what it added and never
duplicates it; an empty list removes everything it added.

    python3 scripts/build_reference_videos.py
"""
import html, json, re, sys
from collections import defaultdict
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent
DATA = SITE / "data" / "reference_videos.json"
# What is inserted is exactly what these remove, so runs never accumulate.
BLOCK = re.compile(r"<!-- refVideo:[^>]*-->.*?<!-- /refVideo -->\n      ", re.S)
LD = re.compile(r'<script type="application/ld\+json" id="refVideoLd">.*?</script>\n', re.S)
ENTRY_END = ('\n      <div class="refEntry"', '\n      <div class="refToc', '\n      <div class="refCta')


def embed(v):
    vid = v["youtube"]
    ratio = "9/16" if v.get("shape", "short") == "short" else "16/9"
    width = "360px" if ratio == "9/16" else "720px"
    return (f'<!-- refVideo:{vid} -->'
            f'<div class="refVideo" style="position:relative;width:100%;max-width:{width};'
            f'aspect-ratio:{ratio};margin:16px 0">'
            f'<iframe src="https://www.youtube-nocookie.com/embed/{vid}" title="{html.escape(v["title"])}" '
            f'loading="lazy" allow="accelerometer; encrypted-media; gyroscope; picture-in-picture; web-share" '
            f'allowfullscreen style="position:absolute;inset:0;width:100%;height:100%;border:0;'
            f'border-radius:12px"></iframe></div>'
            f'<!-- /refVideo -->\n      ')


def video_ld(videos, page):
    items = [{
        "@context": "https://schema.org", "@type": "VideoObject",
        "name": v["title"],
        "description": v.get("description") or v["title"],
        "thumbnailUrl": f"https://i.ytimg.com/vi/{v['youtube']}/hqdefault.jpg",
        "uploadDate": v["uploaded"],
        "embedUrl": f"https://www.youtube.com/embed/{v['youtube']}",
        "contentUrl": f"https://www.youtube.com/watch?v={v['youtube']}",
        "url": f"https://thrasherapps.com/{page}#{v['anchor']}",
    } for v in videos]
    return ('<script type="application/ld+json" id="refVideoLd">'
            + json.dumps(items if len(items) > 1 else items[0], indent=1) + "</script>\n")


def main():
    videos = json.loads(DATA.read_text()).get("videos", []) if DATA.exists() else []
    by_page = defaultdict(list)
    for v in videos:
        by_page[v["page"]].append(v)
    # Every page that might hold a block from an earlier run, plus every page named now.
    pages = {p.relative_to(SITE).as_posix() for p in SITE.glob("*/reference/*.html")} | set(by_page)
    changed, problems = [], []
    for page in sorted(pages):
        path = SITE / page
        if not path.exists():
            problems.append(f"no such page: {page}")
            continue
        s = orig = path.read_text()
        s = LD.sub("", BLOCK.sub("", s))
        for v in by_page.get(page, []):
            start = s.find(f'<div class="refEntry" id="{v["anchor"]}"')
            if start < 0:
                problems.append(f"no code #{v['anchor']} on {page}")
                continue
            ends = [i for i in (s.find(m, start + 1) for m in ENTRY_END) if i > 0]
            close = s.rfind("</div>", start, min(ends) if ends else len(s))
            s = s[:close] + embed(v) + s[close:]
        if by_page.get(page):
            s = s.replace("</head>", video_ld(by_page[page], page) + "</head>", 1)
        if s != orig:
            path.write_text(s)
            changed.append(page)
    print(f"{len(videos)} videos, {len(changed)} pages changed")
    for c in changed:
        print("  ", c)
    for p in problems:
        print("  PROBLEM:", p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
