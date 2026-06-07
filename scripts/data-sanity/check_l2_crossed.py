"""Fast crossed-book check for a single reconstructed Binance L2 day.

Reuses the EXACT replay/bnc_rows logic from l2_parity_audit.py (the acceptance
validator) so a pass here means a pass there. Reports crossed events, negative
sizes, snapshots/resets, and median spread over a window.

Usage:
  python check_l2_crossed.py 2026-05-23            # first 60 min (matches audit)
  python check_l2_crossed.py 2026-05-23 --full     # whole day
"""
from __future__ import annotations
import argparse
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import l2_parity_audit as PA


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("date")
    ap.add_argument("--full", action="store_true", help="scan the whole day, not just 60 min")
    args = ap.parse_args()

    window_s = PA.WIN_MIN * 60
    if args.full:
        window_s = 36 * 3600  # cover a full day with margin

    p = PA.BNC_L2 / args.date / "incremental_book_L2.csv.gz"
    if not p.exists():
        print(f"MISSING: {p}", file=sys.stderr)
        return 2

    t0 = time.time()
    m = PA.replay(PA.bnc_rows(args.date, 10**18), 1.0, window_s=window_s)
    dur = time.time() - t0

    print(f"=== L2 crossed-check {args.date} ({'full day' if args.full else '60 min'}) ===")
    print(f"rows={m['rows']:,}  events={m['events']:,}  snapshots/resets={m['snaps']}/{m['resets']}")
    print(f"CROSSED={m['crossed']}   neg_size={m['negsize']}   zero_deletes={m['zerodel']}")
    print(f"median_spread_bps={m['median_spread_bps']}  p99_spread_bps={m['p99_spread_bps']}  max_gap_s={m['maxgap']}")
    print(f"top1/top5/top20 USD med = {m['top1_depth_med_usd']}/{m['top5_depth_med_usd']}/{m['top20_depth_med_usd']}")
    print(f"replay {dur:.0f}s")
    print("VERDICT:", "PASS (0 crossed, 0 neg)" if (m["crossed"] == 0 and m["negsize"] == 0) else "FAIL")
    return 0 if (m["crossed"] == 0 and m["negsize"] == 0) else 1


if __name__ == "__main__":
    sys.exit(main())
