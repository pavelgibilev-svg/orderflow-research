"""Select 6 out-of-sample OKX dates for zone_score_v1 OOS validation.

Rules (deterministic):
  - Read reports/OKX_REGIME_TABLE.json
  - Exclude the 6 calibration dates already used in
    reports/OKX_SIX_SELECTED_DATES.json
  - Pick 2 bullish + 2 bearish + 2 choppy from the remaining pool:
      bullish: top-2 by abs day_return_pct (most clearly bullish among remaining)
      bearish: top-2 by abs day_return_pct (most clearly bearish among remaining)
      choppy:  top-2 by smallest |day_return_pct| then smallest range_pct
  - Flag 2%-feasibility status in the output (choppy days may not deliver 2%)
  - Write reports/OKX_OOS_SELECTED_DATES.json

NO strategy threshold change. NO score weight change.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path("C:/Users/gibilev/orderflow-research")
REPORTS = ROOT / "reports"


def main() -> int:
    regime = json.loads((REPORTS / "OKX_REGIME_TABLE.json").read_text(encoding="utf-8"))
    calib = json.loads((REPORTS / "OKX_SIX_SELECTED_DATES.json").read_text(encoding="utf-8"))
    calib_dates = {row["date"] for row in calib.get("chosen", [])}

    all_rows = [r for r in regime["dates"] if r.get("status") == "ok" and r["date"] not in calib_dates]

    bullish = sorted(
        [r for r in all_rows if r["regime"] == "bullish"],
        key=lambda r: -r["day_return_pct"],
    )
    bearish = sorted(
        [r for r in all_rows if r["regime"] == "bearish"],
        key=lambda r: r["day_return_pct"],
    )
    choppy = sorted(
        [r for r in all_rows if r["regime"] == "choppy"],
        key=lambda r: (abs(r["day_return_pct"]), r["range_pct"]),
    )

    selection = {"bullish": bullish[:2], "bearish": bearish[:2], "choppy": choppy[:2]}

    chosen: list[dict] = []
    for bucket in ("bullish", "bearish", "choppy"):
        for r in selection[bucket]:
            chosen.append({
                "date": r["date"],
                "bucket": bucket,
                "regime_native": r["regime"],
                "day_return_pct": r["day_return_pct"],
                "range_pct": r["range_pct"],
                "feasibility_2pct": r["feasibility"]["2.0pct"],
                "feasibility_1pct": r["feasibility"]["1.0pct"],
                "feasibility_0.5pct": r["feasibility"]["0.5pct"],
                "horizons": r["horizons"],
                "trades_n": r.get("trades_n"),
            })

    out = {
        "purpose": "out-of-sample validation of zone_score_v1 on OKX BTC-USDT-SWAP",
        "selection_rule": "2 bullish + 2 bearish + 2 choppy from regime table, excluding the 6 calibration dates",
        "excluded_calibration_dates": sorted(calib_dates),
        "pool_sizes_after_exclusion": {
            "bullish": len(bullish),
            "bearish": len(bearish),
            "choppy": len(choppy),
        },
        "chosen": chosen,
    }
    (REPORTS / "OKX_OOS_SELECTED_DATES.json").write_text(
        json.dumps(out, indent=2), encoding="utf-8"
    )
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
