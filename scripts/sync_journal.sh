#!/bin/bash
# sync_journal.sh — run build_journal.py + build_v4_journal.py, commit the
# data files, push.
#
# Runs locally because the V3 logs and V4 trades.db live on the laptop, not
# in CI. Wrap this in a launchd plist (see scripts/com.thrasherapps.journal.plist)
# to refresh every N minutes automatically.
#
# Idempotent: if nothing changed, nothing is committed.

set -euo pipefail

SITE_ROOT="${SITE_ROOT:-/Users/christhrasher/Desktop/thrasherapps-site}"
V3_LOGS="${V3_LOGS:-/Users/christhrasher/Desktop/forex_trading_bot_V3/logs}"
V4_DB="${V4_DB:-/Users/christhrasher/Desktop/forex_trading_bot_V4/state/trades.db}"
PYBIN="${PYBIN:-/usr/bin/python3}"
STAMP=$(date -u "+%Y-%m-%dT%H:%M:%SZ")

cd "$SITE_ROOT"

if [ ! -d "$V3_LOGS" ]; then
  echo "[$STAMP] sync_journal: V3 log dir not found: $V3_LOGS" >&2
  exit 2
fi

# Rebuild the V3 trade journal data files.
"$PYBIN" scripts/build_journal.py --v3-logs "$V3_LOGS" --site-root "$SITE_ROOT"

# Rebuild V4 if the SQLite DB exists. Missing DB is not a failure — V4 may
# not have run yet on a fresh machine, and we still want V3's journal pushed.
if [ -f "$V4_DB" ]; then
  "$PYBIN" scripts/build_v4_journal.py --v4-db "$V4_DB" --site-root "$SITE_ROOT"
else
  echo "[$STAMP] sync_journal: V4 trades.db not found at $V4_DB — skipping V4 build" >&2
fi

# Track the full set of journal files (V3 always, V4 if it was built).
TRACKED=(data/trades_v3.json data/metrics_v3.json)
if [ -f data/trades_v4.json ] && [ -f data/metrics_v4.json ]; then
  TRACKED+=(data/trades_v4.json data/metrics_v4.json)
fi

# Nothing to commit? bail cheaply.
if git diff --quiet -- "${TRACKED[@]}"; then
  echo "[$STAMP] sync_journal: no change in data/, skipping commit"
  exit 0
fi

git add "${TRACKED[@]}"
git commit -m "chore(journal): refresh live trade feed ${STAMP}" >/dev/null
git push --quiet origin main
echo "[$STAMP] sync_journal: pushed new journal data"
