#!/usr/bin/env python3
"""
build_market.py — emit `data/market.json` for thrasherapps.com/dashboard.html.

Pulls only *free, no-API-key* public data so this can run on the free GitHub
Actions tier (or locally on a laptop). Each widget is computed independently;
if one source is offline, the others still publish.

Sources
-------
- CFTC Commitments of Traders (COT):
  https://www.cftc.gov/dea/newcot/FinFutWk.txt  (text, weekly)
  We derive **net non-commercial** (i.e. large speculator) positioning for
  the majors. That's the classic "smart-money positioning" tape.

- US Treasury daily yield curve (home.treasury.gov public CSV):
  https://home.treasury.gov/resource-center/data-chart-center/interest-rates/...
  No auth. Returns year-to-date daily rates for 1mo .. 30yr maturities.
  We pick 2-year and 10-year for the rate-tape widget. We historically
  tried FRED as well, but its fredgraph.csv endpoint intermittently
  returns HTTP/2 INTERNAL_ERROR to Python/curl requests — so Treasury
  is the primary source.

Usage
-----
    python3 scripts/build_market.py
    python3 scripts/build_market.py --site-root /custom/path
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

DEFAULT_SITE_ROOT = Path(__file__).resolve().parent.parent
HTTP_TIMEOUT = 15

# Which maturities we pull from the Treasury daily-yield-curve CSV. The
# label -> source_column mapping lets us rename for display without touching
# the fetcher.
TREASURY_SERIES = {
    "us_2y":  "2 Yr",
    "us_10y": "10 Yr",
    "us_30y": "30 Yr",
}

def _recent_start() -> str:
    from datetime import timedelta
    return (datetime.now(timezone.utc) - timedelta(days=180)).strftime("%Y-%m-%d")

# CFTC "Financial Futures" weekly file. Columns are fixed-width-ish CSV and we
# only care about a handful of products. Mapping from CFTC market name ->
# the pair our bot trades (for display).
COT_PRODUCTS = {
    # Keys are substrings the CFTC uses in the "Market and Exchange Names"
    # field. Values are what we surface on the dashboard.
    "EURO FX": "EUR/USD",
    "BRITISH POUND": "GBP/USD",
    "JAPANESE YEN": "USD/JPY",
    "SWISS FRANC": "USD/CHF",
    "CANADIAN DOLLAR": "USD/CAD",
    "AUSTRALIAN DOLLAR": "AUD/USD",
    "NEW ZEALAND DOLLAR": "NZD/USD",
    "GOLD - COMMODITY EXCHANGE INC.": "XAU/USD",
}

CFTC_URL = "https://www.cftc.gov/dea/newcot/FinFutWk.txt"
# Fallback — same weekly commitments file, reported for commodities.
CFTC_COMM_URL = "https://www.cftc.gov/dea/newcot/deacot.txt"


def _http_get(url: str) -> Optional[bytes]:
    """Two-tier HTTP GET.

    Python's urllib is flaky against some CDN-fronted endpoints on macOS
    (esp. FRED). We try it first for CI-friendliness, then fall back to
    shelling out to `curl`, which is ubiquitous on Linux + macOS and has
    its own battle-tested TLS/HTTP stack.
    """
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "thrasherapps-dashboard/1.0"},
        )
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            return resp.read()
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
        print(f"[build_market] urllib {url} failed ({e}); trying curl", file=sys.stderr)
    curl = shutil.which("curl")
    if not curl:
        return None
    try:
        # Two quick tries via curl: first HTTP/2 (the default), then
        # HTTP/1.1 in case the server's HTTP/2 stream is misbehaving.
        for extra in ([], ["--http1.1"]):
            try:
                out = subprocess.run(
                    [curl, "-sSL", "-m", str(HTTP_TIMEOUT), *extra,
                     "-H", "User-Agent: thrasherapps-dashboard/1.0",
                     url],
                    capture_output=True,
                    check=True,
                    timeout=HTTP_TIMEOUT + 3,
                )
                if out.stdout:
                    return out.stdout
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
                print(f"[build_market] curl {extra} {url} failed: {e}", file=sys.stderr)
        return None
    except subprocess.CalledProcessError as e:
        print(f"[build_market] curl {url} failed: rc={e.returncode} stderr={e.stderr!r}", file=sys.stderr)
        return None


def _latest_non_empty(rows: list[list[str]], col_idx: int) -> Optional[tuple[str, str]]:
    """Walk a CSV in reverse until we find a row whose column `col_idx`
    is non-empty. Returns (date, value) or None."""
    for row in reversed(rows):
        if len(row) <= col_idx:
            continue
        v = row[col_idx].strip()
        if v and v != ".":
            return row[0], v
    return None


def fetch_treasury_rates() -> dict:
    """Pull the current-year daily Treasury yield curve.

    Treasury.gov publishes a single CSV with one row per business day and
    one column per maturity (1 Mo, 2 Mo, ..., 30 Yr). We return a dict
    keyed by our internal label (us_2y, us_10y, us_30y) with the same
    shape as the old FRED fetcher.
    """
    year = datetime.now(timezone.utc).year
    url = (
        "https://home.treasury.gov/resource-center/data-chart-center/"
        f"interest-rates/daily-treasury-rates.csv/{year}/all"
        f"?type=daily_treasury_yield_curve&field_tdr_date_value={year}"
    )
    raw = _http_get(url)
    if not raw:
        print("[build_market] Treasury rate feed unavailable", file=sys.stderr)
        return {}
    text = raw.decode("utf-8", errors="replace")
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if len(rows) < 2:
        return {}
    header = rows[0]
    # CSV arrives *newest-first*, so reverse so we can treat it like a
    # normal time series (old -> new).
    data = list(reversed(rows[1:]))

    # Map display-label -> header column index
    col_idx: dict[str, int] = {}
    for label, heading in TREASURY_SERIES.items():
        if heading in header:
            col_idx[label] = header.index(heading)

    out: dict[str, dict] = {}
    for label, idx in col_idx.items():
        latest = _latest_non_empty(data, idx)
        if not latest:
            continue
        latest_date, latest_val = latest
        prev_val = None
        for r in reversed(data):
            if len(r) <= idx:
                continue
            v = r[idx].strip()
            if v and v != latest_val:
                prev_val = v
                break
        try:
            change = round(float(latest_val) - float(prev_val), 3) if prev_val else None
        except ValueError:
            change = None
        out[label] = {
            "series": TREASURY_SERIES[label],
            "latest_date": latest_date,
            "latest_value": latest_val,
            "prev_value": prev_val,
            "change": change,
            "source": "US Treasury",
            "source_url": "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?type=daily_treasury_yield_curve",
        }
    return out


def _parse_cot_number(s: str) -> Optional[int]:
    s = s.strip().replace(",", "")
    if not s or s == "." or s == "N/A":
        return None
    try:
        return int(float(s))
    except ValueError:
        return None


def fetch_cot() -> Optional[list[dict]]:
    """Parse the weekly CFTC Financial Futures report.

    We only want the classic "Large Speculators" net position:
        net = non_comm_long - non_comm_short
    Against the prior week's net so we can show a directional arrow.
    """
    raw = _http_get(CFTC_URL) or _http_get(CFTC_COMM_URL)
    if not raw:
        return None
    text = raw.decode("utf-8", errors="replace")
    lines = text.splitlines()
    # The CFTC text file is one CSV line per (contract, report_date, etc.)
    # We filter by product name substring.
    products: dict[str, list[list[str]]] = {key: [] for key in COT_PRODUCTS}
    for line in lines:
        if "," not in line:
            continue
        row = next(csv.reader(io.StringIO(line)))
        if not row:
            continue
        name = row[0].upper()
        for key in COT_PRODUCTS:
            if key in name:
                products[key].append(row)
                break
    out: list[dict] = []
    # COT file column layout varies slightly, but dealer/non-commercial longs
    # and shorts are in well-known positions. We look them up by header match
    # if available; otherwise fall back to canonical indices used for years.
    #
    # Canonical legacy format (deacot.txt / FinFutWk.txt), 0-indexed:
    #   0  Market and Exchange Names
    #   2  Report date (YYMMDD)
    #   8  Non-commercial positions-long
    #   9  Non-commercial positions-short
    for key, label in COT_PRODUCTS.items():
        rows = products.get(key, [])
        if not rows:
            continue
        # sort by report date (col 2 when numeric)
        def _key(r):
            try:
                return r[2].strip()
            except IndexError:
                return ""
        rows.sort(key=_key)
        latest = rows[-1] if rows else None
        prev = rows[-2] if len(rows) >= 2 else None
        if not latest or len(latest) < 10:
            continue
        nl = _parse_cot_number(latest[8])
        ns = _parse_cot_number(latest[9])
        if nl is None or ns is None:
            continue
        net = nl - ns
        prev_net = None
        if prev and len(prev) >= 10:
            pnl = _parse_cot_number(prev[8])
            pns = _parse_cot_number(prev[9])
            if pnl is not None and pns is not None:
                prev_net = pnl - pns
        change = (net - prev_net) if prev_net is not None else None
        out.append({
            "pair": label,
            "cftc_name": key,
            "report_date": latest[2].strip() if len(latest) > 2 else None,
            "non_comm_long": nl,
            "non_comm_short": ns,
            "net": net,
            "prev_net": prev_net,
            "change": change,
            "source": "CFTC",
            "source_url": "https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm",
        })
    return out


def fetch_upcoming_events() -> list[dict]:
    """Static, hand-curated calendar of high-impact weekly events.

    We're not scraping ForexFactory (TOS issues) and there's no free
    alternative that's reliably structured. Instead we publish a short
    reminder list that gets refreshed when we refresh the blog.
    """
    return [
        {
            "label": "US CPI",
            "cadence": "Monthly",
            "impact": "high",
            "notes": "Drives USD and rate expectations. Avoid trading EUR/USD, GBP/USD, USD/JPY during the 8:30 ET release.",
        },
        {
            "label": "FOMC Rate Decision",
            "cadence": "8× / year",
            "impact": "high",
            "notes": "USD volatility spike. We pause the bot for 30 min around 2:00 ET.",
        },
        {
            "label": "US NFP (Jobs)",
            "cadence": "1st Friday of month",
            "impact": "high",
            "notes": "Biggest USD move of the month. 8:30 ET.",
        },
        {
            "label": "ECB Rate Decision",
            "cadence": "8× / year",
            "impact": "high",
            "notes": "Euro volatility. Press conference 45 min after the release tends to move markets more than the decision.",
        },
        {
            "label": "UK CPI",
            "cadence": "Monthly",
            "impact": "medium",
            "notes": "GBP driver. 2:00 ET.",
        },
    ]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--site-root",
        type=Path,
        default=DEFAULT_SITE_ROOT,
        help=f"Path to site repo (default: {DEFAULT_SITE_ROOT})",
    )
    args = ap.parse_args()

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "rates": {},
        "cot": [],
        "events": fetch_upcoming_events(),
        "sources": [
            "CFTC Commitments of Traders (weekly)",
            "US Treasury daily yield curve (home.treasury.gov)",
        ],
    }

    rates = fetch_treasury_rates()
    if rates:
        out["rates"] = rates
    else:
        print("[build_market] rates feed unavailable", file=sys.stderr)

    cot = fetch_cot()
    if cot:
        out["cot"] = cot
    else:
        print("[build_market] CFTC feed unavailable", file=sys.stderr)

    data_dir = args.site_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    target = data_dir / "market.json"
    target.write_text(json.dumps(out, indent=2) + "\n")

    print(
        f"[build_market] wrote {target.name}: "
        f"rates={len(out['rates'])} cot_rows={len(out['cot'])} events={len(out['events'])}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
