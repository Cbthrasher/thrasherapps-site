#!/usr/bin/env python3
"""
Builds search indexed reference pages on thrasherapps.com from the bundled
reference libraries inside the app projects.

Why: technicians search for very specific things at odd hours ("SMA 3512",
"IEC 62446 insulation minimum", "NFPA 72 battery calculation"). The apps
already contain that content. Publishing it as real pages earns free,
perfectly targeted traffic and gives each app a place to convert from.

Re run any time the app content changes:
    python3 scripts/build_reference_pages.py
"""

import json
import os
import re
import html
from datetime import date

DESKTOP = os.path.expanduser("~/Desktop")
SITE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

APPS = [
    {
        "key": "fieldwatt",
        "name": "FieldWatt",
        "appid": "6787932579",
        "trade": "utility scale solar technicians",
        "blurb": "Reference notes from FieldWatt, the offline field toolkit for utility scale solar commissioning and O&amp;M technicians.",
        "library": f"{DESKTOP}/FieldWatt/FieldWatt/Resources/ReferenceLibrary",
        "schema": "entries",
    },
    {
        "key": "storewatt",
        "name": "StoreWatt",
        "appid": "6788153038",
        "trade": "grid scale battery storage technicians",
        "blurb": "Reference notes from StoreWatt, the offline field toolkit for grid scale battery energy storage technicians.",
        "library": f"{DESKTOP}/StoreWatt/StoreWatt/Resources/ReferenceLibrary",
        "schema": "entries",
    },
    {
        "key": "loopwatt",
        "name": "LoopWatt",
        "appid": "6790129179",
        "trade": "fire alarm and life safety technicians",
        "blurb": "Reference notes from LoopWatt, the offline field toolkit for fire alarm and life safety technicians.",
        "library": f"{DESKTOP}/LoopWatt/LoopWatt/Resources/ReferenceLibrary",
        "schema": "loose",
    },
    {
        "key": "rackwatt",
        "name": "RackWatt",
        "appid": "6790170168",
        "trade": "data center critical facilities technicians",
        "blurb": "Reference notes from RackWatt, the offline field toolkit for data center critical facilities technicians.",
        "library": f"{DESKTOP}/RackWatt/RackWatt/Resources/ReferenceData",
        "schema": "loose",
    },
    {
        "key": "plugwatt",
        "name": "PlugWatt",
        "appid": "6788584092",
        "trade": "EV charging technicians",
        "blurb": "Reference notes from PlugWatt, the offline field toolkit for electric vehicle charging installation and service technicians.",
        "library": f"{DESKTOP}/PlugWatt/PlugWatt/Resources/library",
        "schema": "entries",
    },
    {
        "key": "droptubebuilder",
        "name": "DropTubeBuilder",
        "appid": "6740597739",
        "trade": "fuel system and underground storage tank technicians",
        "blurb": "Reference notes from DropTubeBuilder, the offline field tool for fuel system technicians who cut overfill drop tubes, build tank charts and chase dispenser faults.",
        "library": f"{DESKTOP}/../Documents/DropTubeBuilder",
        "schema": "droptube",
    },
]

# Human titles for known file and category names.
TITLES = {
    # PlugWatt. Its files are lowercase single words, which auto title into
    # things like "Faultfamilies". These are written for what a technician
    # actually types into a search box.
    "faultfamilies": "EV Charger Fault Codes and Fault Families",
    "brands": "EV Charger Brand and Equipment Library",
    "anatomy": "EV Charging Station Anatomy",
    "comms": "OCPP and EV Charger Communications",
    "safety": "EV Charging Field Safety",
    "standards": "EV Charging Standards and NEC 625",

    "inverterFaultCodes": "Inverter Fault Codes",
    "combinerOm": "DC Combiner Operations and Maintenance",
    "trackerProcedures": "Solar Tracker Procedures",
    "plcNotes": "PLC Notes",
    "commsProtocols": "Communications and Protocols",
    "modbusFunctionCodes": "Modbus Function and Exception Codes",
    "scadaNotes": "SCADA Notes",
    "powerPlantController": "Power Plant Controller",
    "protectionAnsi": "Protection and ANSI Device Numbers",
    "metStation": "Meteorological Station",
    "codeTables": "NEC and IEC Tables",
    "meteringCheatSheet": "Field Metering Cheat Sheet",
    "safetyContent": "Field Safety",
    "troubleFamilies": "Trouble Families",
    "panelLibrary": "Fire Alarm Panel Library",
    "necArticle760": "NEC Article 760",
    "inspectionFrequencies": "Inspection Frequencies",
    "candelaTables": "Candela and Notification Tables",
    "spacingTables": "Device Spacing Tables",
    "deviceCurrentDraw": "Device Current Draw",
    "wireResistance": "Wire Resistance",
    "batterySizes": "Battery Sizes",
    "eolResistors": "End of Line Resistors",
    "referenceTroubleshooting": "Troubleshooting Reference",
    "calcReference": "Calculation Reference",
    "proceduresLibrary": "Procedures Library",
    "safetyTopics": "Safety Topics",
    "standardsTiers": "Standards and Tiers",
    "maintenanceCadence": "Maintenance Cadence",
}

SKIP_FILES = {
    "formTemplates", "decisionTrees", "manifest", "procedureTemplatesSeed",
    # PlugWatt uses lowercase names and keeps a manifest alongside the library.
    "formtemplates", "decisiontrees", "librarymanifest",
}

FIELD_LABELS = [
    ("body", None),
    ("summary", None),
    ("function", "Function"),
    ("scope", "Scope"),
    ("symptoms", "Symptoms"),
    ("causes", "Common causes"),
    ("likelyCauses", "Likely causes"),
    ("failureModes", "Failure modes"),
    ("diagnosis", "Diagnosis"),
    ("method", "Method"),
    ("warningSigns", "Warning signs"),
    ("troubleNotes", "Trouble notes"),
    ("menuConcepts", "Menu concepts"),
    ("families", "Families"),
    ("bands", "Bands"),
    ("keyPoints", "Key points"),
    ("points", "Points"),
    ("sections", "Sections"),
    ("models", "Models"),
    ("meaning", None),
    ("checks", "What to check, in order"),
    ("safeResponse", "Safe response"),
    ("notes", "Notes"),
    ("brands", "Brands"),
    ("citation", "Citation"),
    ("citations", "Citations"),
    ("verifyNote", "Verify against"),
    ("verifyAgainstManual", "Verify against the manual"),
]


def nice_title(stem):
    if stem in TITLES:
        return TITLES[stem]
    spaced = re.sub(r"(?<!^)(?=[A-Z])", " ", stem)
    return spaced[:1].upper() + spaced[1:]


def as_text(value):
    """Flatten a JSON value into readable paragraphs."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, (int, float)):
        return [str(value)]
    if isinstance(value, list):
        out = []
        for item in value:
            if isinstance(item, str):
                out.append(item)
            elif isinstance(item, dict):
                bits = [f"{k}: {v}" for k, v in item.items()
                        if isinstance(v, (str, int, float)) and str(v).strip()]
                if bits:
                    out.append(". ".join(bits))
        return out
    if isinstance(value, dict):
        return [f"{k}: {v}" for k, v in value.items()
                if isinstance(v, (str, int, float))]
    return []


PLACEHOLDER = re.compile(r"content pending|coming in a future|placeholder", re.I)


def normalize(raw):
    """Turn one library entry into {id, title, tag, blocks:[(label, [paragraphs])]}."""
    title = raw.get("title") or raw.get("name")
    if not title:
        return None
    # Skip stub entries: thin pages hurt search quality and help nobody.
    if PLACEHOLDER.search(str(title)) or PLACEHOLDER.search(str(raw.get("body", ""))):
        return None
    tag_bits = [raw.get("brand"), raw.get("domain"), raw.get("code")]
    tag = " · ".join([str(t) for t in tag_bits if t])
    blocks = []
    for field, label in FIELD_LABELS:
        paras = as_text(raw.get(field))
        if paras:
            blocks.append((label, paras))
    if not blocks:
        return None
    return {
        "id": re.sub(r"[^a-z0-9]+", "-", str(raw.get("id", title)).lower()).strip("-"),
        "title": str(title),
        "tag": tag,
        "blocks": blocks,
    }


# Some libraries nest the actual codes one level down, inside a panel or a
# brand. LoopWatt keeps troubleCodes on each panel and PlugWatt keeps
# faultCodes on each brand. Those are the exact strings a technician types
# into a search box, so they each need their own indexable entry rather than
# being buried inside the parent.
NESTED_CODE_FIELDS = ("troubleCodes", "faultCodes")


def expand_nested_codes(raw):
    parent = raw.get("name") or raw.get("title") or ""
    out = []
    for field in NESTED_CODE_FIELDS:
        codes = raw.get(field)
        if not isinstance(codes, list):
            continue
        for code in codes:
            if not isinstance(code, dict):
                continue
            shown = code.get("display") or code.get("code") or ""
            label = code.get("title") or ""
            if shown and label and shown != label:
                title = f"{shown} — {label}"
            else:
                title = shown or label
            if not title:
                continue
            flat = dict(code)
            flat["title"] = title
            flat["brand"] = parent
            flat["id"] = f"{raw.get('id', parent)}-{code.get('id') or code.get('code') or title}"
            entry = normalize(flat)
            if entry:
                out.append(entry)
    return out


def load_groups(app):
    """Return [(stem, human_title, [entries])] for an app."""
    lib = app["library"]
    if not os.path.isdir(lib):
        return []
    groups = []
    for fname in sorted(os.listdir(lib)):
        if not fname.endswith(".json"):
            continue
        stem = fname[:-5]
        if stem in SKIP_FILES:
            continue
        try:
            data = json.load(open(os.path.join(lib, fname)))
        except Exception:
            continue
        # Most apps wrap their entries in {"entries": [...]}. PlugWatt stores a
        # bare list per file. Accept either rather than reshaping the app data.
        if isinstance(data, dict):
            raws = data.get("entries")
        elif isinstance(data, list):
            raws = data
        else:
            raws = None
        if not isinstance(raws, list):
            continue
        entries = []
        for raw in raws:
            if not isinstance(raw, dict):
                continue
            top = normalize(raw)
            if top:
                entries.append(top)
            entries.extend(expand_nested_codes(raw))
        if entries:
            groups.append((stem, nice_title(stem), entries))
    return groups


# --- DropTubeBuilder -------------------------------------------------------
# Its data is shaped differently from the Watt apps: nested dictionaries of
# manufacturer, then model, then code to description. Product names keep their
# real spelling, hyphens included, because those are the exact strings
# technicians type into a search box.

DTB_GROUP_TITLES = {
    ("Gilbarco", "500s"): ("gilbarco-500-series", "Gilbarco 500 Series Dispenser Error Codes"),
    ("Gilbarco", "700s"): ("gilbarco-700-series", "Gilbarco 700 Series Dispenser Error Codes"),
    ("Gilbarco", "Encore 300"): ("gilbarco-encore-300", "Gilbarco Encore 300 Error Codes"),
    ("Wayne", "Ovation"): ("wayne-ovation", "Wayne Ovation Dispenser Error Codes"),
    ("Veeder-Root", "TLS-300"): ("veeder-root-tls-300", "Veeder-Root TLS-300 Alarm Codes"),
    ("Veeder-Root", "TLS-350"): ("veeder-root-tls-350", "Veeder-Root TLS-350 Alarm Codes"),
    ("Veeder-Root", "TLS-450"): ("veeder-root-tls-450", "Veeder-Root TLS-450 Alarm Codes"),
    ("Veeder-Root", "TLS-450 PLUS"): ("veeder-root-tls-450-plus", "Veeder-Root TLS-450 PLUS Alarm Codes"),
    ("Veeder-Root", "TLS4 / TLS-4i"): ("veeder-root-tls4", "Veeder-Root TLS4 and TLS-4i Alarm Codes"),
    ("Franklin / INCON", "EVO 550 / 5000"): ("franklin-incon-evo", "Franklin INCON EVO 550 and EVO 5000 Alarms"),
}


def _slug(text):
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-") or "entry"


def load_groups_droptube(app):
    root = os.path.normpath(app["library"])
    groups = []

    codes_path = os.path.join(root, "ErrorCodes.json")
    if os.path.isfile(codes_path):
        data = json.load(open(codes_path))
        for maker, models in data.items():
            if not isinstance(models, dict):
                continue
            for model, codes in models.items():
                if not isinstance(codes, dict):
                    continue
                stem, gtitle = DTB_GROUP_TITLES.get(
                    (maker, model),
                    (_slug(f"{maker}-{model}"), f"{maker} {model} Error Codes"))
                entries = []
                for code, text in codes.items():
                    if not str(text).strip():
                        continue
                    entries.append({
                        "id": _slug(f"{code}"),
                        "title": str(code),
                        "tag": f"{maker} \u00b7 {model}",
                        "blocks": [(None, [str(text)])],
                    })
                if entries:
                    groups.append((stem, gtitle, entries))

    pumps_path = os.path.join(root, "PumpControllers.json")
    if os.path.isfile(pumps_path):
        data = json.load(open(pumps_path))
        for controller, info in data.items():
            if not isinstance(info, dict):
                continue
            entries = []
            overview = info.get("overview")
            if overview:
                blocks = [(None, [str(overview)])]
                if info.get("source"):
                    blocks.append(("Source", [str(info["source"])]))
                entries.append({"id": "overview", "title": "Overview",
                                "tag": controller, "blocks": blocks})
            for row in info.get("faultCodes") or []:
                blocks = []
                for key, label in (("condition", None), ("cause", "Likely cause"),
                                   ("action", "Action")):
                    if row.get(key):
                        blocks.append((label, [str(row[key])]))
                if blocks:
                    entries.append({
                        "id": _slug("fault-" + str(row.get("code", ""))),
                        "title": f"Fault code {row.get('code', '')}".strip(),
                        "tag": f"{controller} \u00b7 fault", "blocks": blocks})
            for row in info.get("statusCodes") or []:
                if row.get("text"):
                    entries.append({
                        "id": _slug("status-" + str(row.get("code", ""))),
                        "title": f"Status {row.get('code', '')} {row.get('name', '')}".strip(),
                        "tag": f"{controller} \u00b7 status",
                        "blocks": [(None, [str(row["text"])])]})
            dips = info.get("dipSwitches") or []
            if dips:
                paras = []
                for row in dips:
                    bits = [f"{row.get('bank','')} pole {row.get('pole','')}".strip()]
                    if row.get("on"):
                        bits.append(f"ON: {row['on']}")
                    if row.get("off"):
                        bits.append(f"OFF: {row['off']}")
                    if row.get("factory"):
                        bits.append(f"Factory: {row['factory']}")
                    if row.get("note"):
                        bits.append(str(row["note"]))
                    paras.append(". ".join(bits))
                entries.append({"id": "dip-switches", "title": "DIP switch settings",
                                "tag": f"{controller} \u00b7 configuration",
                                "blocks": [(None, paras)]})
            if entries:
                groups.append((_slug(controller), f"{controller} Fault and Status Codes", entries))

    return groups


HEAD = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title}</title>
  <meta name="description" content="{desc}" />
  <link rel="canonical" href="https://thrasherapps.com/{path}" />
  <link rel="stylesheet" href="/assets/site.css">
  <style>
    .refEntry{{background:#fff;border:1px solid #E5E7EB;border-radius:12px;padding:16px 18px;margin:16px 0}}
    .refEntry h2{{margin:0 0 4px 0;font-size:1.15em}}
    .refTag{{display:inline-block;font-size:.78em;font-weight:700;color:#007AFF;background:#EFF6FF;border-radius:999px;padding:2px 10px;margin-bottom:8px}}
    .refLabel{{font-size:.75em;font-weight:800;letter-spacing:.05em;text-transform:uppercase;color:#475569;margin-top:10px}}
    .refEntry p{{margin:4px 0;white-space:pre-wrap}}
    .refToc{{background:#fff;border:1px solid #E5E7EB;border-radius:12px;padding:14px 18px}}
    .refToc a{{display:inline-block;margin:3px 12px 3px 0;font-size:.92em}}
    .refCta{{background:#0F172A;color:#fff;border-radius:12px;padding:18px;margin:24px 0}}
    .refCta a.btn{{background:#007AFF;color:#fff;border:0}}
    .refCta p{{color:#CBD5E1;margin:6px 0 12px}}
    .crumb{{font-size:.9em;color:#475569;margin-bottom:6px}}
  </style>
</head>
<body>
  <header class="site-header">
    <div class="container nav">
      <a class="brand" href="/">ThrasherApps</a>
      <nav class="nav-links">
        <a href="/">Home</a>
        <a href="/apps.html">Apps</a>
        <a href="/{key}/">{name}</a>
        <a href="/{key}/reference/">Reference</a>
        <a href="/{key}/support.html">Support</a>
      </nav>
    </div>
  </header>
  <section class="section">
    <div class="container">
"""

FOOT = """    </div>
  </section>
  <footer class="site-footer">
    <div class="container">
      <div>© {year} ThrasherApps.com — Built by Chris Thrasher</div>
      <div class="mt-2">
        <a href="/{key}/">{name}</a> ·
        <a href="/{key}/privacy.html">Privacy</a> ·
        <a href="/{key}/terms.html">Terms</a> ·
        <a href="/{key}/support.html">Support</a>
      </div>
    </div>
  </footer>
</body>
</html>
"""


def cta(app):
    return f"""      <div class="refCta">
        <strong>These notes come from {app['name']}</strong>
        <p>{app['blurb']} It works with no cell signal, because the sites do not have any.</p>
        <a class="btn" href="https://apps.apple.com/us/app/id{app['appid']}">Get {app['name']} on the App Store</a>
      </div>
"""


def render_group(app, stem, gtitle, entries, all_groups):
    e = html.escape
    path = f"{app['key']}/reference/{stem}.html"
    first = entries[0]
    desc_src = " ".join(first["blocks"][0][1])[:150].replace('"', "'")
    parts = [HEAD.format(
        title=e(f"{gtitle} | {app['name']} field reference"),
        desc=e(f"{gtitle} for {app['trade']}. {desc_src}"),
        path=path, key=app["key"], name=app["name"])]
    parts.append(f'      <div class="crumb"><a href="/{app["key"]}/reference/">{e(app["name"])} reference</a></div>\n')
    parts.append(f'      <h1 class="h2">{e(gtitle)}</h1>\n')
    parts.append(f'      <p class="lead">Field reference for {e(app["trade"])}. '
                 f'{len(entries)} entries, taken from the {e(app["name"])} app.</p>\n')

    parts.append('      <div class="refToc mt-3"><strong>On this page</strong><br>\n')
    for en in entries:
        parts.append(f'        <a href="#{en["id"]}">{e(en["title"])}</a>\n')
    parts.append("      </div>\n")
    parts.append(cta(app))

    for en in entries:
        parts.append(f'      <div class="refEntry" id="{en["id"]}">\n')
        if en["tag"]:
            parts.append(f'        <div class="refTag">{e(en["tag"])}</div>\n')
        parts.append(f'        <h2>{e(en["title"])}</h2>\n')
        for label, paras in en["blocks"]:
            if label:
                parts.append(f'        <div class="refLabel">{e(label)}</div>\n')
            for p in paras:
                parts.append(f"        <p>{e(p)}</p>\n")
        parts.append("      </div>\n")

    others = [(s, t) for s, t, _ in all_groups if s != stem]
    if others:
        parts.append('      <div class="refToc mt-4"><strong>More reference</strong><br>\n')
        for s, t in others:
            parts.append(f'        <a href="/{app["key"]}/reference/{s}.html">{e(t)}</a>\n')
        parts.append("      </div>\n")

    parts.append(cta(app))
    parts.append('      <p class="mt-3" style="font-size:.85em;color:#475569">These notes are a field aid, '
                 'not a substitute for the governing codes, the stamped drawings, the authority having '
                 'jurisdiction, or manufacturer manuals. Verify against the current documentation for your '
                 'installed equipment.</p>\n')
    parts.append(FOOT.format(year=date.today().year, key=app["key"], name=app["name"]))
    return path, "".join(parts)


def render_hub(app, groups):
    e = html.escape
    path = f"{app['key']}/reference/index.html"
    total = sum(len(g[2]) for g in groups)
    parts = [HEAD.format(
        title=e(f"{app['name']} field reference library"),
        desc=e(f"Free field reference for {app['trade']}: {total} entries across {len(groups)} topics."),
        path=f"{app['key']}/reference/", key=app["key"], name=app["name"])]
    parts.append(f'      <h1 class="h2">{e(app["name"])} field reference</h1>\n')
    parts.append(f'      <p class="lead">{e(app["blurb"])} '
                 f'{total} entries across {len(groups)} topics, free to read here.</p>\n')
    parts.append(cta(app))
    parts.append('      <div class="grid grid-2 mt-3">\n')
    for stem, gtitle, entries in groups:
        sample = ", ".join(en["title"] for en in entries[:3])
        parts.append(f'        <article class="card"><h3><a href="/{app["key"]}/reference/{stem}.html">{e(gtitle)}</a></h3>'
                     f'<p class="mt-1" style="font-size:.9em;color:#475569">{len(entries)} entries: {e(sample)}…</p></article>\n')
    parts.append("      </div>\n")
    parts.append(FOOT.format(year=date.today().year, key=app["key"], name=app["name"]))
    return path, "".join(parts)


def main():
    written = []
    for app in APPS:
        groups = (load_groups_droptube(app) if app.get("schema") == "droptube"
                  else load_groups(app))
        if not groups:
            print(f"{app['name']}: no usable library, skipped")
            continue
        outdir = os.path.join(SITE, app["key"], "reference")
        os.makedirs(outdir, exist_ok=True)
        for stem, gtitle, entries in groups:
            path, htmlstr = render_group(app, stem, gtitle, entries, groups)
            open(os.path.join(SITE, path), "w").write(htmlstr)
            written.append(path)
        path, htmlstr = render_hub(app, groups)
        open(os.path.join(SITE, path), "w").write(htmlstr)
        written.append(path)
        print(f"{app['name']}: {len(groups)} topic pages, "
              f"{sum(len(g[2]) for g in groups)} entries")
    print(f"\ntotal pages written: {len(written)}")
    return written


if __name__ == "__main__":
    main()
