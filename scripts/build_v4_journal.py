#!/usr/bin/env python3
"""
build_v4_journal.py — read V4's SQLite trades.db and emit static JSON the
website can render.

V4 (the Rust forex bot) writes one row per shadow / live trade to
`state/trades.db`. Schema (table `shadow_trades`):

    tag (PK), strategy, pair, side, entry_ts, entry_price, sl_price,
    sl_pips, atr_pips, stretch_pips, mean_price, spread_pips, units_would,
    equity_at_entry, reason, closed_at, exit_price, exit_reason, pnl_pips,
    max_favorable_pips, max_adverse_pips, duration_seconds, win

Output (relative to site repo root) — schema mirrors build_journal.py so the
front-end can swap data sources without front-end changes:

  data/trades_v4.json   — newest-first array of closed trades, up to N most recent
  data/metrics_v4.json  — rolling metrics (all-time + last 30d + last 7d),
                          per-pair, per-strategy breakdown

Differences from V3's shape:
  - V4 does not track regime/session in the DB → both default to "unknown"
  - V4 uses brain exits, not fixed TPs → tp_price is null
  - V4 only writes closed trades (closed_at NOT NULL) — no orphans to match

Usage:
  python3 scripts/build_v4_journal.py
  python3 scripts/build_v4_journal.py --v4-db /custom/path/trades.db --max 200
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

DEFAULT_V4_DB = Path.home() / "Desktop" / "forex_trading_bot_V4" / "state" / "trades.db"
DEFAULT_SITE_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MAX_TRADES = 200

# Alpha-decay protection. The V4 bot trades two named strategies; we don't want
# anyone reverse-engineering our edge by reading the public journal, so the
# raw strategy names never leave this file. The website renders the labels.
# Map order is meaningful — A is the dominant-volume strategy.
STRATEGY_LABELS: dict[str, str] = {
    "mr_scalp": "Strategy A",
    "liq_sweep": "Strategy B",
}


def label_strategy(name: str | None) -> str:
    """Return the public label for an internal V4 strategy name.

    Anything not in STRATEGY_LABELS gets "Other" — guarantees no internal
    name ever lands in the JSON the site reads.
    """
    if not name:
        return "Other"
    return STRATEGY_LABELS.get(name, "Other")


def parse_ts(s: str | None):
    """Parse ISO-8601 from rusqlite (rfc3339). Returns UTC datetime or None."""
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def load_closed(db_path: Path) -> list[dict]:
    """Read every closed shadow_trades row, newest-first.

    Skips rows where closed_at is NULL — those are open trades that haven't
    been resolved yet and would otherwise inflate counts in the public feed.
    """
    if not db_path.exists():
        print(f"[build_v4_journal] no V4 trades.db at {db_path}", file=sys.stderr)
        return []

    # Open in read-only URI mode so we never lock the DB while the bot is
    # writing. WAL journaling on the bot's side means concurrent readers work
    # cleanly anyway, but ?mode=ro is the belt + suspenders.
    uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute(
            """
            SELECT
                tag, strategy, pair, side,
                entry_ts, entry_price, sl_price, sl_pips,
                atr_pips, stretch_pips, mean_price, spread_pips,
                units_would, equity_at_entry, reason,
                closed_at, exit_price, exit_reason,
                pnl_pips, max_favorable_pips, max_adverse_pips,
                duration_seconds, win
            FROM shadow_trades
            WHERE closed_at IS NOT NULL
            ORDER BY closed_at DESC
            """
        )
        rows = [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()

    out: list[dict] = []
    for r in rows:
        pnl_pips = r.get("pnl_pips") or 0.0
        # Guard against the same kind of corrupt/stale records build_journal.py
        # filters out — V4's DB is much cleaner but this is a cheap safeguard.
        if abs(pnl_pips) > 500:
            continue
        out.append({
            "pair": r["pair"],
            "side": r["side"],
            # Public-facing label, NOT the internal strategy name. See
            # STRATEGY_LABELS at top of file for the alpha-decay rationale.
            "strategy": label_strategy(r["strategy"]),
            # V4 has no regime/session in the DB. Empty placeholders keep the
            # JSON shape identical to V3 so the front-end can render uniformly.
            "regime": "unknown",
            "session": "unknown",
            "opened_at": r["entry_ts"],
            "closed_at": r["closed_at"],
            "entry_price": r["entry_price"],
            "exit_price": r["exit_price"],
            "sl_price": r["sl_price"],
            # V4 uses brain-driven exits, not fixed TPs.
            "tp_price": None,
            "pnl_pips": round(pnl_pips, 1),
            "mfe_pips": round(r.get("max_favorable_pips") or 0.0, 1),
            "mae_pips": round(r.get("max_adverse_pips") or 0.0, 1),
            "duration_seconds": r.get("duration_seconds"),
            "win": 1 if pnl_pips > 0 else 0,
            # V4-specific extras — useful for journal storytelling, harmless
            # to V3-only consumers because they read by key.
            "spread_pips_at_entry": r.get("spread_pips"),
            "units_would": r.get("units_would"),
            "exit_reason": r.get("exit_reason"),
        })
    return out


def compute_metrics(trades: list[dict]) -> dict:
    """Compute the same header/breakdown metrics V3 emits.

    Pips, not dollars — V4 launches at $273.20 of live equity, so dollar
    figures would be misleading and embarrassing in the same breath.
    """
    now = datetime.now(timezone.utc)
    windows = {
        "all_time": None,
        "last_30d": now - timedelta(days=30),
        "last_7d": now - timedelta(days=7),
    }

    def stats(subset: list[dict]) -> dict:
        n = len(subset)
        wins = [t for t in subset if t["win"]]
        losses = [t for t in subset if not t["win"]]
        gross_win = sum(t["pnl_pips"] for t in wins) if wins else 0.0
        gross_loss = abs(sum(t["pnl_pips"] for t in losses)) if losses else 0.0
        pf = round(gross_win / gross_loss, 2) if gross_loss > 0 else None
        wr = round(len(wins) / n * 100, 1) if n > 0 else None
        total_pips = round(sum(t["pnl_pips"] for t in subset), 1)
        avg_win = round(sum(t["pnl_pips"] for t in wins) / len(wins), 1) if wins else 0.0
        avg_loss = round(sum(t["pnl_pips"] for t in losses) / len(losses), 1) if losses else 0.0
        return {
            "n_trades": n,
            "wins": len(wins),
            "losses": len(losses),
            "win_rate_pct": wr,
            "profit_factor": pf,
            "total_pips": total_pips,
            "avg_win_pips": avg_win,
            "avg_loss_pips": avg_loss,
        }

    def filter_window(cutoff: datetime | None) -> list[dict]:
        if cutoff is None:
            return trades
        return [
            t for t in trades
            if (parse_ts(t["closed_at"]) or datetime.min.replace(tzinfo=timezone.utc)) >= cutoff
        ]

    windowed = {name: stats(filter_window(cutoff)) for name, cutoff in windows.items()}

    by_pair: dict[str, list[dict]] = defaultdict(list)
    for t in trades:
        by_pair[t["pair"]].append(t)
    pair_breakdown = []
    for pair, ts in sorted(by_pair.items(), key=lambda kv: -len(kv[1])):
        pair_breakdown.append({"pair": pair, **stats(ts)})

    by_strat: dict[str, list[dict]] = defaultdict(list)
    for t in trades:
        by_strat[t["strategy"]].append(t)
    strat_breakdown = []
    for strat, ts in sorted(by_strat.items(), key=lambda kv: -len(kv[1])):
        strat_breakdown.append({"strategy": strat, **stats(ts)})

    return {
        "generated_at": now.isoformat(timespec="seconds"),
        "windows": windowed,
        "by_pair": pair_breakdown,
        "by_strategy": strat_breakdown,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--v4-db",
        type=Path,
        default=DEFAULT_V4_DB,
        help=f"Path to V4 trades.db (default: {DEFAULT_V4_DB})",
    )
    ap.add_argument(
        "--site-root",
        type=Path,
        default=DEFAULT_SITE_ROOT,
        help=f"Path to site repo (default: {DEFAULT_SITE_ROOT})",
    )
    ap.add_argument(
        "--max",
        type=int,
        default=DEFAULT_MAX_TRADES,
        help="Cap the trades_v4.json feed to N most recent closes",
    )
    args = ap.parse_args()

    closed = load_closed(args.v4_db)

    data_dir = args.site_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    trades_out = data_dir / "trades_v4.json"
    metrics_out = data_dir / "metrics_v4.json"

    feed = closed[: args.max]
    trades_out.write_text(json.dumps(feed, indent=2) + "\n")
    metrics = compute_metrics(closed)
    # No "unmatched closes" concept here — V4 only writes a row when it has
    # both an entry and exit. Leave the field at 0 so consumers reading
    # metrics_v3.json + metrics_v4.json see the same key set.
    metrics["n_unmatched_closes"] = 0
    metrics["feed_trade_count"] = len(feed)
    metrics["total_trade_count"] = len(closed)
    # V4 distinguishes shadow vs live by config; surface so the front-end
    # can render a "SHADOW" or "LIVE" badge once execute_trades flips on.
    metrics["bot"] = "v4"
    metrics_out.write_text(json.dumps(metrics, indent=2) + "\n")

    all_time = metrics["windows"]["all_time"]
    print(
        f"[build_v4_journal] wrote {trades_out.name} ({len(feed)} trades) "
        f"+ {metrics_out.name}",
        file=sys.stderr,
    )
    print(
        f"[build_v4_journal] all-time: n={all_time['n_trades']} "
        f"WR={all_time['win_rate_pct']}% PF={all_time['profit_factor']} "
        f"pips={all_time['total_pips']:+.1f}",
        file=sys.stderr,
    )

    for row in metrics["by_pair"][:5]:
        pf_str = f"{row['profit_factor']:.2f}" if row['profit_factor'] is not None else "--"
        print(
            f"    {row['pair']:<8} n={row['n_trades']:>3} "
            f"WR={row['win_rate_pct']}% PF={pf_str} pips={row['total_pips']:+.1f}",
            file=sys.stderr,
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
