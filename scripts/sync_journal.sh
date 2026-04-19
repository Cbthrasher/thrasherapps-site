#!/bin/bash
# sync_journal.sh — run build_journal.py, commit the data files, push.
#
# Runs locally because the V3 bot's JSONL logs live on the laptop, not in CI.
# Wrap this in a launchd plist (see scripts/com.thrasherapps.journal.plist)
# to refresh every N minutes automatically.
#
# Idempotent: if nothing changed, nothing is committed.

set -euo pipefail

SITE_ROOT="${SITE_ROOT:-/Users/christhrasher/Desktop/thrasherapps-site}"
V3_LOGS="${V3_LOGS:-/Users/christhrasher/Desktop/forex_trading_bot_V3/logs}"
PYBIN="${PYBIN:-/usr/bin/python3}"
STAMP=$(date -u "+%Y-%m-%dT%H:%M:%SZ")

cd "$SITE_ROOT"

if [ ! -d "$V3_LOGS" ]; then
  echo "[$STAMP] sync_journal: V3 log dir not found: $V3_LOGS" >&2
  exit 2
fi

# Rebuild the trade journal data files.
"$PYBIN" scripts/build_journal.py --v3-logs "$V3_LOGS" --site-root "$SITE_ROOT"

# Nothing to commit? bail cheaply.
if git diff --quiet -- data/trades.json data/metrics.json; then
  echo "[$STAMP] sync_journal: no change in data/, skipping commit"
  exit 0
fi

git add data/trades.json data/metrics.json
git commit -m "chore(journal): refresh live trade feed ${STAMP}" >/dev/null
git push --quiet origin main
echo "[$STAMP] sync_journal: pushed new journal data"
