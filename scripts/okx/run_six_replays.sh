#!/usr/bin/env bash
# Run OKX technical replays on the 6 selected first-of-month dates.
# Reads the selection from reports/OKX_SIX_SELECTED_DATES.json.
# Usage:
#   bash scripts/okx/run_six_replays.sh 3h        # 3-hour cap (default)
#   bash scripts/okx/run_six_replays.sh full-day  # full UTC day
set -euo pipefail

WINDOW="${1:-3h}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

DATES=$("C:/Users/gibilev/AppData/Local/Programs/Python/Python312/python.exe" -c '
import json
d = json.load(open("reports/OKX_SIX_SELECTED_DATES.json","r",encoding="utf-8"))
for c in d["chosen"]:
    print(c["date"])
')

echo "[okx-six] window=$WINDOW dates:"
echo "$DATES" | sed "s/^/  /"
echo ""

for d in $DATES; do
  echo "================================================================"
  echo "[okx-six] starting $d ($WINDOW)"
  echo "================================================================"
  npm run backtest:okx-technical -- --date "$d" --window "$WINDOW" || {
    echo "[okx-six] FAIL on $d; continuing with next"
  }
done

echo ""
echo "[okx-six] all 6 done. Reports:"
ls -la reports/OKX_TECHNICAL_REPLAY_*.md 2>&1 | tail -12
