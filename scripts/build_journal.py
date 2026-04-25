#!/usr/bin/env python3
"""
build_journal.py — parse V3 bot's live trade logs and emit the static JSON
blobs that thrasherapps.com/signals.html (the Forex Bot Journal) renders.

Run this locally (it needs access to V3's log files) and commit the
regenerated `data/` files to the site repo. Intended to be wrapped in a
launchd plist on the user's laptop for automatic updates.

Outputs (relative to repo root):
  data/trades_v3.json   — newest-first array of closed trades, up to N most recent
  data/metrics_v3.json  — rolling metrics (all-time + last 30d + last 7d), per-pair,
                          per-strategy breakdown

(V4's parallel feed is in data/trades_v4.json + data/metrics_v4.json, written
by build_v4_journal.py.)

Usage:
  python3 scripts/build_journal.py
  python3 scripts/build_journal.py --v3-logs /custom/path/logs --max 200
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

DEFAULT_V3_LOGS = Path.home() / "Desktop" / "forex_trading_bot_V3" / "logs"
DEFAULT_SITE_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MAX_TRADES = 200

# Alpha-decay protection. We don't want anyone reverse-engineering our edge
# by reading the public journal, so the raw strategy names from V3's logs
# never leave this file. Order is by all-time trade count (most-used first).
# Anything outside this map gets "Other" so a new internal strategy can ship
# without leaking until we explicitly add a label.
STRATEGY_LABELS: dict[str, str] = {
    "trend_standard": "Strategy A",
    "scalp": "Strategy B",
    "divergence": "Strategy C",
    "mean_reversion_pullback": "Strategy D",
    "mean_reversion": "Strategy E",
    "m5_trend": "Strategy F",
}


def label_strategy(name: str | None) -> str:
    """Return the public label for an internal V3 strategy name."""
    if not name:
        return "Other"
    return STRATEGY_LABELS.get(name, "Other")


def parse_ts(s: str | None):
    """Parse an ISO-8601 timestamp from the bot's logs. Returns UTC datetime or None."""
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


def load_raw(log_dir: Path):
    """Load trade_entry and trade_closed events from all trade_signals*.jsonl
    files in log_dir. Dedups identical records seen across rotated backups."""
    files = sorted(log_dir.glob("trade_signals*.jsonl"))
    if not files:
        print(f"[build_journal] no trade_signals*.jsonl files in {log_dir}", file=sys.stderr)
        return [], []

    entry_seen: set[tuple] = set()
    close_seen: set[tuple] = set()
    entries: list[dict] = []
    closes: list[dict] = []

    for p in files:
        try:
            with open(p) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        j = json.loads(line)
                    except Exception:
                        continue
                    t = j.get("type")
                    if t == "trade_entry":
                        if not j.get("entry_price") or not j.get("pair"):
                            continue
                        # Skip entries from small/dummy accounts (wrong account logs mixed in backfill)
                        bal = j.get("balance", 0) or 0
                        if 0 < bal < 1000:
                            continue
                        key = (
                            j.get("pair"),
                            (j.get("timestamp") or "")[:19],
                            round(j.get("entry_price", 0), 6),
                        )
                        if key in entry_seen:
                            continue
                        entry_seen.add(key)
                        entries.append(j)
                    elif t == "trade_closed":
                        if not j.get("entry_price") or not j.get("exit_price"):
                            continue
                        if not j.get("pair"):
                            continue
                        # Guard against obviously corrupt records
                        p_pips = j.get("pnl_pips", 0) or 0
                        if abs(p_pips) > 500:
                            continue
                        key = (
                            j.get("pair"),
                            (j.get("timestamp") or "")[:19],
                            round(j.get("entry_price", 0), 6),
                            round(j.get("exit_price", 0), 6),
                        )
                        if key in close_seen:
                            continue
                        close_seen.add(key)
                        closes.append(j)
        except OSError as e:
            print(f"[build_journal] skip {p}: {e}", file=sys.stderr)
            continue

    return entries, closes


def match_trades(entries: list[dict], closes: list[dict]):
    """Match each close to its most-recent-earlier entry with matching pair +
    entry_price (within half a pip). Uses the algorithm from V3's
    extract_live_trades.py, simplified."""
    entries.sort(key=lambda j: parse_ts(j.get("timestamp")) or datetime.min.replace(tzinfo=timezone.utc))
    closes.sort(key=lambda j: parse_ts(j.get("timestamp")) or datetime.min.replace(tzinfo=timezone.utc))

    by_pair: dict[str, list[dict]] = defaultdict(list)
    for e in entries:
        by_pair[e["pair"]].append(e)

    matched: list[dict] = []
    unmatched_closes = 0

    for c in closes:
        pair = c["pair"]
        close_ts = parse_ts(c.get("timestamp"))
        entry_price = c.get("entry_price")
        if close_ts is None or entry_price is None:
            unmatched_closes += 1
            continue

        pip = 0.01 if "JPY" in pair else 0.0001
        best = None
        best_ts = None
        for e in by_pair.get(pair, []):
            e_ts = parse_ts(e.get("timestamp"))
            if e_ts is None or e_ts > close_ts:
                continue
            if abs((e.get("entry_price") or 0) - entry_price) > 0.5 * pip:
                continue
            if best is None or e_ts > best_ts:
                best = e
                best_ts = e_ts

        if best is None:
            unmatched_closes += 1
            continue

        side = c.get("side") or ("long" if best.get("signal") == "BUY" else "short")
        strategy = c.get("strategy") or best.get("strategy") or "unknown"
        pnl_pips = c.get("pnl_pips") or 0
        duration_s = None
        e_ts = parse_ts(best.get("timestamp"))
        if e_ts is not None:
            duration_s = int((close_ts - e_ts).total_seconds())

        rec = {
            "pair": pair,
            "side": side,
            # Public-facing label, NOT the internal strategy name. See
            # STRATEGY_LABELS at top of file for the alpha-decay rationale.
            "strategy": label_strategy(strategy),
            "regime": c.get("regime") or best.get("regime") or "UNKNOWN",
            "session": c.get("session") or best.get("session") or "unknown",
            "opened_at": best.get("timestamp"),
            "closed_at": c.get("timestamp"),
            "entry_price": best.get("entry_price"),
            "exit_price": c.get("exit_price"),
            "sl_price": best.get("sl_price"),
            "tp_price": best.get("tp_price"),
            "pnl_pips": round(pnl_pips, 1),
            "mfe_pips": round(c.get("max_favorable_pips", 0) or 0, 1),
            "duration_seconds": duration_s,
            "win": 1 if pnl_pips > 0 else 0,
        }
        matched.append(rec)

    return matched, unmatched_closes


def compute_metrics(trades: list[dict]):
    """Compute the header metrics we show on the journal page.

    Uses pips (not dollars) everywhere — V3 runs on a demo account, so
    dollars would be misleading anyway. Pips translate to any account size."""
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

    # Per-pair breakdown (all-time). Small, useful at a glance.
    by_pair: dict[str, list[dict]] = defaultdict(list)
    for t in trades:
        by_pair[t["pair"]].append(t)
    pair_breakdown = []
    for pair, ts in sorted(by_pair.items(), key=lambda kv: -len(kv[1])):
        pair_breakdown.append({"pair": pair, **stats(ts)})

    # Per-strategy breakdown
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
        "--v3-logs",
        type=Path,
        default=DEFAULT_V3_LOGS,
        help=f"Path to V3 log dir (default: {DEFAULT_V3_LOGS})",
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
        help="Cap the trades_v3.json feed to N most recent closes",
    )
    args = ap.parse_args()

    if not args.v3_logs.exists():
        print(f"V3 log dir not found: {args.v3_logs}", file=sys.stderr)
        return 2

    entries, closes = load_raw(args.v3_logs)
    matched, unmatched = match_trades(entries, closes)
    matched.sort(key=lambda t: parse_ts(t["closed_at"]) or datetime.min.replace(tzinfo=timezone.utc), reverse=True)

    data_dir = args.site_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    trades_out = data_dir / "trades_v3.json"
    metrics_out = data_dir / "metrics_v3.json"

    feed = matched[: args.max]
    trades_out.write_text(json.dumps(feed, indent=2) + "\n")
    metrics = compute_metrics(matched)
    metrics["n_unmatched_closes"] = unmatched
    metrics["feed_trade_count"] = len(feed)
    metrics["total_trade_count"] = len(matched)
    metrics_out.write_text(json.dumps(metrics, indent=2) + "\n")

    # Quick summary to stderr so launchd logs are informative.
    all_time = metrics["windows"]["all_time"]
    print(
        f"[build_journal] wrote {trades_out.name} ({len(feed)} trades) "
        f"+ {metrics_out.name}",
        file=sys.stderr,
    )
    print(
        f"[build_journal] all-time: n={all_time['n_trades']} "
        f"WR={all_time['win_rate_pct']}% PF={all_time['profit_factor']} "
        f"pips={all_time['total_pips']:+.1f}",
        file=sys.stderr,
    )
    if unmatched:
        print(
            f"[build_journal] {unmatched} unmatched closes "
            f"(entries in older rotated logs)",
            file=sys.stderr,
        )

    # Top 5 pairs for a quick check
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
