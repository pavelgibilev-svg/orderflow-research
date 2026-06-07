"""Select ≥12 candidate dates for the zone_score_v2 full-day replay round.

Rules (deterministic):
  - Read reports/OKX_REGIME_TABLE.json (regenerated after the new L2 downloads).
  - Exclude ALL dates that have already been replayed full-day for the v1
    calibration or OOS validation:
        calibration: 2024-01-01, 2024-07-01, 2024-10-01, 2025-10-01,
                     2025-12-01, 2026-04-01
        OOS_v1:      2025-04-01, 2025-05-01, 2024-05-01, 2024-09-01,
                     2024-06-01, 2025-11-01
  - From the remaining pool, pick the most informative balanced set:
        bullish: pick by descending day_return_pct
        bearish: pick by ascending day_return_pct (most negative first)
        choppy:  pick by smallest |day_return_pct|, then by smallest range
  - Aim for ≥12 dates: 5 bullish + 5 bearish + 2 choppy (or as close as
    possible given the pool).
  - 2 % feasibility flagged per date (choppy will likely fail).
  - On-disk L2 presence flagged per date (so the operator knows what is
    already downloaded vs still to fetch).

Writes:
    reports/OKX_SCORE_V2_CANDIDATE_DATES.json
    reports/OKX_SCORE_V2_CANDIDATE_DATES.md
"""
from __future__ import annotations
import json
import sys
import time
from pathlib import Path

ROOT = Path("C:/Users/gibilev/orderflow-research")
REPORTS = ROOT / "reports"
DATA_ROOT = ROOT / "data" / "okx-historical" / "BTC-USDT-SWAP"

CALIB = {"2024-01-01", "2024-07-01", "2024-10-01", "2025-10-01", "2025-12-01", "2026-04-01"}
OOS_V1 = {"2025-04-01", "2025-05-01", "2024-05-01", "2024-09-01", "2024-06-01", "2025-11-01"}
USED = CALIB | OOS_V1

TARGET_BULLISH = 5
TARGET_BEARISH = 5
TARGET_CHOPPY = 2


def has_l2(date: str) -> bool:
    p = DATA_ROOT / date / "incremental_book_L2.csv.gz"
    return p.exists() and p.stat().st_size > 0


def main() -> int:
    regime = json.loads((REPORTS / "OKX_REGIME_TABLE.json").read_text(encoding="utf-8"))
    rows = [r for r in regime["dates"] if r.get("status") == "ok" and r["date"] not in USED]

    bullish = sorted([r for r in rows if r["regime"] == "bullish"], key=lambda r: -r["day_return_pct"])
    bearish = sorted([r for r in rows if r["regime"] == "bearish"], key=lambda r: r["day_return_pct"])
    choppy = sorted(
        [r for r in rows if r["regime"] == "choppy"],
        key=lambda r: (abs(r["day_return_pct"]), r["range_pct"]),
    )

    chosen: list[dict] = []
    for r in bullish[:TARGET_BULLISH]:
        chosen.append({**r, "bucket": "bullish"})
    for r in bearish[:TARGET_BEARISH]:
        chosen.append({**r, "bucket": "bearish"})
    for r in choppy[:TARGET_CHOPPY]:
        chosen.append({**r, "bucket": "choppy"})

    # If pool was thinner than target, top up with whatever is left in
    # bullish/bearish to reach >=12.
    while len(chosen) < 12:
        leftover_pool = (bullish[TARGET_BULLISH:] + bearish[TARGET_BEARISH:] + choppy[TARGET_CHOPPY:])
        leftover_pool = [r for r in leftover_pool if r["date"] not in {c["date"] for c in chosen}]
        if not leftover_pool:
            break
        # prefer 2%-feasible
        leftover_pool.sort(key=lambda r: (not r["feasibility"]["2.0pct"], -abs(r["day_return_pct"])))
        chosen.append({**leftover_pool[0], "bucket": leftover_pool[0]["regime"]})

    # Compose final entries
    final = []
    for c in chosen:
        d = c["date"]
        final.append({
            "date": d,
            "bucket": c["bucket"],
            "regime_native": c["regime"],
            "day_return_pct": c["day_return_pct"],
            "range_pct": c["range_pct"],
            "feasibility_2pct": c["feasibility"]["2.0pct"],
            "feasibility_1pct": c["feasibility"]["1.0pct"],
            "feasibility_0.5pct": c["feasibility"]["0.5pct"],
            "horizons": c["horizons"],
            "trades_n": c.get("trades_n"),
            "l2_on_disk": has_l2(d),
        })

    out = {
        "purpose": "v2 candidate selection — ≥12 NEW OKX BTC-USDT-SWAP dates for full-day replay",
        "build_time_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "selection_rule": "5 bullish + 5 bearish + 2 choppy, excluding the 12 calibration+OOS_v1 dates, then top up to ≥12 if needed",
        "excluded_dates": sorted(USED),
        "pool_sizes_after_exclusion": {
            "bullish": len(bullish),
            "bearish": len(bearish),
            "choppy": len(choppy),
        },
        "chosen": final,
        "count": len(final),
    }
    (REPORTS / "OKX_SCORE_V2_CANDIDATE_DATES.json").write_text(json.dumps(out, indent=2), encoding="utf-8")

    md = [
        "# OKX `zone_score_v2` — candidate dates for full-day replay",
        "",
        f"**Build time:** {out['build_time_utc']}",
        "**Goal:** ≥12 NEW OKX BTC-USDT-SWAP first-of-month dates for the v2 full-day chain.",
        "**Excluded:** all 12 dates already used (6 calibration + 6 OOS-v1 for zone_score_v1).",
        "",
        "## A. Selection rule",
        "",
        f"- {TARGET_BULLISH} bullish (top by descending day_return_pct in the remaining pool)",
        f"- {TARGET_BEARISH} bearish (top by ascending day_return_pct, most negative first)",
        f"- {TARGET_CHOPPY} choppy (smallest |day_return_pct|, then smallest range)",
        "- If pool thinner than target, top up by remaining 2%-feasible dates with strongest day_return.",
        "",
        f"Pool sizes after exclusion: bullish={out['pool_sizes_after_exclusion']['bullish']}, bearish={out['pool_sizes_after_exclusion']['bearish']}, choppy={out['pool_sizes_after_exclusion']['choppy']}.",
        "",
        "## B. Chosen dates",
        "",
        "| # | date | bucket | day Δ % | range % | 2% feas | 1% feas | L2 on disk | trades |",
        "|--:|------|--------|--------:|--------:|:-------:|:-------:|:----------:|-------:|",
    ]
    for i, c in enumerate(final, 1):
        f2 = "yes" if c["feasibility_2pct"] else "no"
        f1 = "yes" if c["feasibility_1pct"] else "no"
        l2 = "yes" if c["l2_on_disk"] else "no"
        md.append(
            f"| {i} | {c['date']} | {c['bucket']:<7s} | {c['day_return_pct']:+6.2f} | {c['range_pct']:6.2f} | "
            f" {f2:^3s}  | {f1:^3s}   | {l2:^5s}    | {c['trades_n']:>7,} |"
        )
    md.extend([
        "",
        f"**Total chosen:** {len(final)}",
        "",
        "## C. Caveats",
        "",
        "- These dates are CANDIDATES. The v2 full-day chain is **not** started by this script.",
        "- Choppy dates may be 2 %-infeasible (range too tight) — that is information, not failure.",
        "- Once full-day is run on these, the natural pipeline is: (1) regime+replay summary, (2) re-derive v2 weights on a held-out split, (3) OOS-test on yet-another held-out set. Steps 2–3 are explicitly out of scope here.",
        "",
        "Companion JSON: `reports/OKX_SCORE_V2_CANDIDATE_DATES.json`",
    ])
    (REPORTS / "OKX_SCORE_V2_CANDIDATE_DATES.md").write_text("\n".join(md), encoding="utf-8")

    print(f"wrote {REPORTS/'OKX_SCORE_V2_CANDIDATE_DATES.json'}  ({len(final)} dates)")
    print(f"wrote {REPORTS/'OKX_SCORE_V2_CANDIDATE_DATES.md'}")
    print()
    for c in final:
        f2 = "yes" if c["feasibility_2pct"] else "no"
        l2 = "yes" if c["l2_on_disk"] else "no"
        print(f"  {c['date']}  {c['bucket']:<7s}  dret={c['day_return_pct']:+6.2f}%  range={c['range_pct']:5.2f}%  2pct-feas={f2}  L2={l2}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
