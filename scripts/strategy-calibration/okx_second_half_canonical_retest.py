"""Canonical execution retest for OKX direct March SECOND HALF (15 days).

Dates: 2026-03-16, 03-18..03-31 (03-17 missing in source).

Mirrors first-half `okx_march_canonical_retest.py`, applied to second-half.
Uses canonical_ledger.py (single source of truth, mirror of TS module).

Variants:
  A) trigger_entry__stop_1pct (baseline)
  B) delay_15m__stop_1.5pct (diagnostic)

Cost diagnostic: fee 0.08% + slippage {0.02, 0.06, 0.10}% roundtrip.
Headline "after basic cost" = fee 0.08 + slip 0.06 = 0.14%.

NO engine / threshold / detector change. NO new backtest.
"""
from __future__ import annotations
import csv
import datetime as dt
import json
import statistics as stats
import sys
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from canonical_ledger import (
    Signal, Bucket, ExecutionConfig, TradeRecord,
    build_buckets_from_trades_csv, canonical_ledger_walk, aggregate, aggregate_after_cost,
)

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "package.json").exists() and (p / "scripts").exists())
REPORTS = ROOT / "reports"
REP_OUT = REPORTS / "strategy-calibration"
REP_OUT.mkdir(parents=True, exist_ok=True)
DATA_ROOT = ROOT / "data/okx-historical/BTC-USDT-SWAP"

OKX_DATES = ["2026-03-16"] + [f"2026-03-{d:02d}" for d in range(18, 32)]   # 15 days, no 03-17
WINDOW_MIN = 60
PRICE_BAND_PCT = 1.0
FAST_X_MIN_BASE = 60
FEE_ROUNDTRIP_PCT = 0.08
SLIPPAGE_SCENARIOS = [0.02, 0.06, 0.10]
BASIC_COST_PCT = 0.14   # fee 0.08 + slip 0.06


def mid_price(z):
    lo, hi = z.get("zoneLow"), z.get("zoneHigh")
    return None if lo is None or hi is None else (lo + hi) / 2.0


def is_triggered(z): return z.get("status") in ("RESOLVED_REACHED", "RESOLVED_FAILED")


def confirm_to_trigger_min(z):
    c, t = z.get("confirmedTs"), z.get("triggerTs")
    return None if c is None or t is None else (t - c) / 60000.0


def load_okx_zones() -> list[dict]:
    out: list[dict] = []
    for d in OKX_DATES:
        p = REPORTS / f"BTC-USDT-SWAP_{d}" / "zones.json"
        if not p.exists():
            continue
        obj = json.loads(p.read_text(encoding="utf-8"))
        zones = obj if isinstance(obj, list) else obj.get("zones", [])
        for z in zones:
            z["_date"] = d
        out.extend(zones)
    return out


def apply_passive_filter(zones):
    by_date = defaultdict(list)
    for z in zones: by_date[z["_date"]].append(z)
    decisions = {}
    for date, lst in by_date.items():
        triggered = [z for z in lst if is_triggered(z) and z.get("triggerTs") is not None]
        triggered.sort(key=lambda z: z["triggerTs"])
        for i, z in enumerate(triggered):
            T = z["triggerTs"]; D = z["direction"]; zm = mid_price(z)
            dup = False
            for prior in triggered[:i]:
                if prior["triggerTs"] >= T or prior["direction"] != D: continue
                dtm = (T - prior["triggerTs"]) / 60000.0
                if dtm <= 0 or dtm > WINDOW_MIN: continue
                pm = mid_price(prior)
                if zm is None or pm is None: continue
                if abs(zm - pm) / zm * 100.0 <= PRICE_BAND_PCT:
                    dup = True; break
            ctm = confirm_to_trigger_min(z)
            fast_ok = (ctm is None) or (ctm <= FAST_X_MIN_BASE)
            decisions[z["id"]] = {"kept": (not dup) and fast_ok}
    return decisions


def to_signal(z):
    return Signal(id=z["id"], date=z["_date"], trigger_ts_ms=z["triggerTs"],
                  direction=z["direction"], zone_low=z.get("zoneLow"), zone_high=z.get("zoneHigh"))


def trades_to_dicts(trades): return [asdict(t) for t in trades]


def main() -> int:
    print("loading OKX zones (second half) ...", file=sys.stderr)
    zones = load_okx_zones()
    dec = apply_passive_filter(zones)
    filtered = [z for z in zones if is_triggered(z) and dec.get(z["id"], {}).get("kept")]
    print(f"  filtered triggered: {len(filtered)}", file=sys.stderr)
    signals = [to_signal(z) for z in filtered]

    print("building 1s buckets ...", file=sys.stderr)
    buckets_by_date: dict[str, list[Bucket]] = {}
    for d in OKX_DATES:
        p = DATA_ROOT / d / "trades.csv.gz"
        if not p.exists():
            print(f"  MISSING {p}", file=sys.stderr)
            buckets_by_date[d] = []
            continue
        buckets_by_date[d] = build_buckets_from_trades_csv(p)
        print(f"    {d}: {len(buckets_by_date[d]):,} buckets", file=sys.stderr)

    cfg_base = ExecutionConfig(entry_strategy="trigger", stop_pct=1.0, target_pct=2.0, timeout_hours=24)
    cfg_var = ExecutionConfig(entry_strategy="delay_15m", stop_pct=1.5, target_pct=2.0, timeout_hours=24)

    print("[A] baseline trigger_entry+stop_1pct ...", file=sys.stderr)
    res_base = canonical_ledger_walk(signals, buckets_by_date, cfg_base)
    agg_base = aggregate(res_base.trades)
    print(f"  trades: {agg_base['n_trades']}  expectancy: {agg_base['expectancy_pct_per_trade']}  PF: {agg_base['profit_factor']}",
          file=sys.stderr)

    print("[B] diagnostic delay_15m+stop_1.5pct ...", file=sys.stderr)
    res_var = canonical_ledger_walk(signals, buckets_by_date, cfg_var)
    agg_var = aggregate(res_var.trades)
    print(f"  trades: {agg_var['n_trades']}  expectancy: {agg_var['expectancy_pct_per_trade']}  PF: {agg_var['profit_factor']}",
          file=sys.stderr)

    cost_base = {}; cost_var = {}
    for slip in SLIPPAGE_SCENARIOS:
        c = FEE_ROUNDTRIP_PCT + slip
        cost_base[f"fee_{FEE_ROUNDTRIP_PCT}_slip_{slip}"] = aggregate_after_cost(res_base.trades, c)
        cost_var[f"fee_{FEE_ROUNDTRIP_PCT}_slip_{slip}"] = aggregate_after_cost(res_var.trades, c)
    agg_base_basic = cost_base[f"fee_{FEE_ROUNDTRIP_PCT}_slip_0.06"]
    agg_var_basic = cost_var[f"fee_{FEE_ROUNDTRIP_PCT}_slip_0.06"]

    out = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "scope": "OKX direct partial March SECOND HALF 2026 (2026-03-16, 03-18..03-31) under canonical strict ledger",
        "canonical_model": "scripts/strategy-calibration/canonical_ledger.py (mirror of src/research/canonicalLedger.ts)",
        "dates_processed": OKX_DATES,
        "missing_dates": ["2026-03-17"],
        "base_filter": {"fast_trigger_max_min": FAST_X_MIN_BASE, "duplicate_window_min": WINDOW_MIN,
                         "price_band_pct": PRICE_BAND_PCT},
        "n_filtered_signals": len(filtered),
        "execution_variants": {
            "A_trigger_entry_stop_1pct": {
                "cfg": asdict(cfg_base),
                "n_trades": len(res_base.trades),
                "n_skipped_due_to_position": res_base.skipped_due_to_position,
                "aggregate_pre_cost": agg_base,
                "aggregate_after_basic_cost": agg_base_basic,
                "cost_diagnostic": cost_base,
                "trades": trades_to_dicts(res_base.trades),
            },
            "B_delay_15m_stop_1.5pct": {
                "cfg": asdict(cfg_var),
                "n_trades": len(res_var.trades),
                "n_skipped_due_to_position": res_var.skipped_due_to_position,
                "aggregate_pre_cost": agg_var,
                "aggregate_after_basic_cost": agg_var_basic,
                "cost_diagnostic": cost_var,
                "trades": trades_to_dicts(res_var.trades),
            },
        },
    }
    (REP_OUT / "OKX_SECOND_HALF_CANONICAL_EXECUTION_RETEST.json").write_text(
        json.dumps(out, indent=2, default=str), encoding="utf-8")

    keys = ["variant", "zone_id", "date", "direction", "entry_sec", "exit_sec",
            "entry_price", "exit_price", "exit_reason", "pnl_pct",
            "mfe_pct", "mae_pct", "time_in_trade_h", "used_stop_pct"]
    with (REP_OUT / "OKX_SECOND_HALF_CANONICAL_EXECUTION_RETEST.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for name, lst in [("A_trigger_stop_1pct", res_base.trades), ("B_delay15_stop_1.5pct", res_var.trades)]:
            for t in lst:
                row = {**asdict(t), "variant": name}
                w.writerow({k: row.get(k) for k in keys})

    md = [
        "# OKX direct SECOND HALF March 2026 - canonical execution retest (15 days)",
        "",
        f"**Build:** {out['build_time_utc']}",
        f"**Days processed:** {len(OKX_DATES)} (2026-03-16, 03-18..03-31); 03-17 missing in source",
        f"**Canonical model:** `{out['canonical_model']}`",
        "**Target STRICT 2 %. Timeout 24h. NO engine change. Read-only post-hoc.**",
        "",
        f"- filtered triggered signals: **{len(filtered)}**",
        "",
        "## Variant A - trigger_entry + stop 1.0 % (canonical baseline)",
        "",
        "| metric | pre-cost | after basic cost (0.14 %) |",
        "|---|---:|---:|",
        f"| n_trades | {agg_base['n_trades']} | {agg_base_basic['n_trades']} |",
        f"| W / L / T | {agg_base['wins']} / {agg_base['losses']} / {agg_base['timeouts']} | (same) |",
        f"| winrate % | {agg_base['winrate_pct']} | (same) |",
        f"| avg win % | {agg_base['avg_win_pct']} | (cost reduces each) |",
        f"| avg loss % | {agg_base['avg_loss_pct']} | (cost worsens each) |",
        f"| **expectancy %/trade** | **{agg_base['expectancy_pct_per_trade']}** | **{agg_base_basic['expectancy_pct_per_trade']}** |",
        f"| total return % | {agg_base['total_return_pct_1unit']} | {agg_base_basic['total_return_pct_1unit']} |",
        f"| **profit factor** | **{agg_base['profit_factor']}** | **{agg_base_basic['profit_factor']}** |",
        f"| max consecutive losses | {agg_base['max_consecutive_losses']} | — |",
        f"| LONG n / exp % | {agg_base['long_n']} / {agg_base['long_expectancy_pct']} | — |",
        f"| SHORT n / exp % | {agg_base['short_n']} / {agg_base['short_expectancy_pct']} | — |",
        f"| skipped due to open position | {res_base.skipped_due_to_position} | — |",
        "",
        "### Cost-aware diagnostic (Variant A)",
        "| roundtrip cost % | expectancy %/trade | PF | total return % |",
        "|---|---:|---:|---:|",
    ]
    for k, agg in cost_base.items():
        cost = FEE_ROUNDTRIP_PCT + float(k.split("_slip_")[-1])
        md.append(f"| {cost:.2f} | {agg['expectancy_pct_per_trade']} | {agg['profit_factor']} | {agg['total_return_pct_1unit']} |")

    md.extend([
        "",
        "## Variant B - delay 15min + stop 1.5 % (diagnostic)",
        "",
        "| metric | pre-cost | after basic cost (0.14 %) |",
        "|---|---:|---:|",
        f"| n_trades | {agg_var['n_trades']} | {agg_var_basic['n_trades']} |",
        f"| W / L / T | {agg_var['wins']} / {agg_var['losses']} / {agg_var['timeouts']} | (same) |",
        f"| winrate % | {agg_var['winrate_pct']} | (same) |",
        f"| avg win % | {agg_var['avg_win_pct']} | — |",
        f"| avg loss % | {agg_var['avg_loss_pct']} | — |",
        f"| **expectancy %/trade** | **{agg_var['expectancy_pct_per_trade']}** | **{agg_var_basic['expectancy_pct_per_trade']}** |",
        f"| total return % | {agg_var['total_return_pct_1unit']} | {agg_var_basic['total_return_pct_1unit']} |",
        f"| **profit factor** | **{agg_var['profit_factor']}** | **{agg_var_basic['profit_factor']}** |",
        f"| max consecutive losses | {agg_var['max_consecutive_losses']} | — |",
        f"| LONG n / exp % | {agg_var['long_n']} / {agg_var['long_expectancy_pct']} | — |",
        f"| SHORT n / exp % | {agg_var['short_n']} / {agg_var['short_expectancy_pct']} | — |",
        f"| skipped due to open position | {res_var.skipped_due_to_position} | — |",
        "",
        "### Cost-aware diagnostic (Variant B)",
        "| roundtrip cost % | expectancy %/trade | PF | total return % |",
        "|---|---:|---:|---:|",
    ])
    for k, agg in cost_var.items():
        cost = FEE_ROUNDTRIP_PCT + float(k.split("_slip_")[-1])
        md.append(f"| {cost:.2f} | {agg['expectancy_pct_per_trade']} | {agg['profit_factor']} | {agg['total_return_pct_1unit']} |")

    (REP_OUT / "OKX_SECOND_HALF_CANONICAL_EXECUTION_RETEST.md").write_text("\n".join(md), encoding="utf-8")

    print()
    print("=== SUMMARY ===")
    print(f"Variant A trigger+stop_1%:  trades={agg_base['n_trades']}  exp={agg_base['expectancy_pct_per_trade']}%  PF={agg_base['profit_factor']}  after-cost={agg_base_basic['expectancy_pct_per_trade']}%")
    print(f"Variant B delay15+stop1.5%: trades={agg_var['n_trades']}  exp={agg_var['expectancy_pct_per_trade']}%  PF={agg_var['profit_factor']}  after-cost={agg_var_basic['expectancy_pct_per_trade']}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
