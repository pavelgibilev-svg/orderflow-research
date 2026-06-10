"""Select 6 representative dates: 2 bullish + 2 bearish + 2 choppy
from reports/OKX_REGIME_TABLE.json.

Selection rules within each bucket:
  - among bullish: top-2 by absolute day_return (most clearly bullish)
  - among bearish: top-2 by absolute day_return (most clearly bearish)
  - among choppy:  top-2 by smallest |day_return| AND smallest range
                   (the flattest, lowest-vol days — most "choppy")
  - if a bucket has <2 entries, fall back to high_vol or any-other-date
    of nearest character; report the fallback explicitly.

Writes: reports/OKX_SIX_SELECTED_DATES.json
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

REPORTS = next(p for p in Path(__file__).resolve().parents if (p / "package.json").exists() and (p / "scripts").exists()) / "reports"


def main() -> int:
    src = REPORTS / "OKX_REGIME_TABLE.json"
    if not src.exists():
        print(f"missing {src}; run regime_analysis.py first.")
        return 1
    data = json.loads(src.read_text(encoding="utf-8"))
    all_rows = [r for r in data["dates"] if r.get("status") == "ok"]
    bullish = sorted(
        [r for r in all_rows if r["regime"] == "bullish"],
        key=lambda r: -r["day_return_pct"],
    )
    bearish = sorted(
        [r for r in all_rows if r["regime"] == "bearish"],
        key=lambda r: r["day_return_pct"],  # most negative first
    )
    choppy = sorted(
        [r for r in all_rows if r["regime"] == "choppy"],
        key=lambda r: (abs(r["day_return_pct"]), r["range_pct"]),
    )
    high_vol = sorted(
        [r for r in all_rows if r["regime"] == "high_vol"],
        key=lambda r: -r["range_pct"],
    )

    selection = {"bullish": bullish[:2], "bearish": bearish[:2], "choppy": choppy[:2]}
    fallbacks: list[str] = []
    for k in ("bullish", "bearish", "choppy"):
        while len(selection[k]) < 2:
            # Fallback: borrow from high_vol pool first, then any
            if high_vol:
                pick = high_vol.pop(0)
                fallbacks.append(f"{k}<-high_vol:{pick['date']}")
                selection[k].append(pick)
                continue
            pool = [r for r in all_rows if r not in sum(selection.values(), [])]
            if not pool:
                break
            pool.sort(
                key=lambda r: -abs(r["day_return_pct"]) if k != "choppy" else abs(r["day_return_pct"]),
            )
            pick = pool[0]
            fallbacks.append(f"{k}<-any:{pick['date']}")
            selection[k].append(pick)

    chosen = []
    for k in ("bullish", "bearish", "choppy"):
        for r in selection[k]:
            chosen.append({
                "date": r["date"],
                "bucket": k,
                "day_return_pct": r["day_return_pct"],
                "range_pct": r["range_pct"],
                "regime_native": r["regime"],
                "feasibility_2pct": r["feasibility"]["2.0pct"],
            })

    out = {
        "selection_rule": "2 bullish + 2 bearish + 2 choppy from first-of-month samples",
        "fallbacks_used": fallbacks,
        "chosen": chosen,
        "bullish_pool_size": len(bullish),
        "bearish_pool_size": len(bearish),
        "choppy_pool_size": len(choppy),
        "high_vol_pool_size_after_fallback": len(high_vol),
    }
    (REPORTS / "OKX_SIX_SELECTED_DATES.json").write_text(
        json.dumps(out, indent=2), encoding="utf-8"
    )
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
