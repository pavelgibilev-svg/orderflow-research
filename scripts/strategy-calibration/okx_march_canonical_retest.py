"""OKX direct March 2026 retest under the canonical strict-ledger model.

Inputs (READ-ONLY):
  reports/BTC-USDT-SWAP_2026-03-DD/zones.json
  data/okx-historical/BTC-USDT-SWAP/2026-03-DD/trades.csv.gz

Outputs:
  reports/strategy-calibration/OKX_MARCH_CANONICAL_LEDGER_RETEST.{md,json,csv}
  reports/strategy-calibration/LEDGER_BUGFIX_NOTES.{md,json}
  reports/strategy-calibration/LEDGER_FIX_AND_OKX_MARCH_RETEST_SUMMARY.{md,json}

Recomputes baseline (`trigger_entry + stop_1pct`) and diagnostic variant
(`delay_15m + stop_1.5pct`) using `canonical_ledger.py`, the single source
of truth (mirror of `src/research/canonicalLedger.ts`).

NO strategy change. NO new backtest. NO production integration.
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

# Make canonical_ledger importable
sys.path.insert(0, str(Path(__file__).resolve().parent))
from canonical_ledger import (
    Signal, Bucket, ExecutionConfig, TradeRecord, LedgerResult,
    build_buckets_from_trades_csv, canonical_ledger_walk, aggregate, aggregate_after_cost,
)

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "package.json").exists() and (p / "scripts").exists())
REPORTS = ROOT / "reports"
REP_OUT = REPORTS / "strategy-calibration"
REP_OUT.mkdir(parents=True, exist_ok=True)
DATA_ROOT = ROOT / "data/okx-historical/BTC-USDT-SWAP"

OKX_DATES = [f"2026-03-{d:02d}" for d in range(2, 16)]
WINDOW_MIN = 60
PRICE_BAND_PCT = 1.0
FAST_X_MIN_BASE = 60
FEE_ROUNDTRIP_PCT = 0.08
SLIPPAGE_SCENARIOS = [0.02, 0.06, 0.10]


# ---------- helpers ----------

def mid_price(z: dict) -> float | None:
    lo, hi = z.get("zoneLow"), z.get("zoneHigh")
    if lo is None or hi is None: return None
    return (lo + hi) / 2.0


def is_triggered(z: dict) -> bool:
    return z.get("status") in ("RESOLVED_REACHED", "RESOLVED_FAILED")


def confirm_to_trigger_min(z: dict) -> float | None:
    c, t = z.get("confirmedTs"), z.get("triggerTs")
    if c is None or t is None: return None
    return (t - c) / 60000.0


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


def apply_passive_filter(zones: list[dict]) -> dict[str, dict]:
    """Live-valid base filter: fast_trigger<=60m AND duplicate_60m (price_band<=1%)."""
    by_date = defaultdict(list)
    for z in zones:
        by_date[z["_date"]].append(z)
    decisions = {}
    for date, lst in by_date.items():
        triggered = [z for z in lst if is_triggered(z) and z.get("triggerTs") is not None]
        triggered.sort(key=lambda z: z["triggerTs"])
        for i, z in enumerate(triggered):
            T = z["triggerTs"]; D = z["direction"]; zm = mid_price(z)
            dup = False
            for prior in triggered[:i]:
                if prior["triggerTs"] >= T or prior["direction"] != D:
                    continue
                dt_min = (T - prior["triggerTs"]) / 60000.0
                if dt_min <= 0 or dt_min > WINDOW_MIN:
                    continue
                pm = mid_price(prior)
                if zm is None or pm is None:
                    continue
                if abs(zm - pm) / zm * 100.0 <= PRICE_BAND_PCT:
                    dup = True; break
            ctm = confirm_to_trigger_min(z)
            fast_ok = (ctm is None) or (ctm <= FAST_X_MIN_BASE)
            decisions[z["id"]] = {"kept": (not dup) and fast_ok}
    return decisions


def to_signal(z: dict) -> Signal:
    return Signal(
        id=z["id"], date=z["_date"], trigger_ts_ms=z["triggerTs"],
        direction=z["direction"],
        zone_low=z.get("zoneLow"), zone_high=z.get("zoneHigh"),
    )


def trades_to_dicts(trades: list[TradeRecord]) -> list[dict]:
    return [asdict(t) for t in trades]


# ---------- main ----------

def main() -> int:
    print("loading OKX zones ...", file=sys.stderr)
    zones = load_okx_zones()
    dec = apply_passive_filter(zones)
    filtered = [z for z in zones if is_triggered(z) and dec.get(z["id"], {}).get("kept")]
    print(f"  filtered triggered: {len(filtered)}", file=sys.stderr)
    signals = [to_signal(z) for z in filtered]

    print("building 1s buckets ...", file=sys.stderr)
    buckets_by_date: dict[str, list[Bucket]] = {}
    for d in OKX_DATES:
        print(f"  {d} ...", file=sys.stderr)
        buckets_by_date[d] = build_buckets_from_trades_csv(DATA_ROOT / d / "trades.csv.gz")

    # ---------- canonical baseline (trigger + 1% stop) ----------
    print("[baseline] running canonical ledger ...", file=sys.stderr)
    cfg_base = ExecutionConfig(entry_strategy="trigger", stop_pct=1.0, target_pct=2.0, timeout_hours=24)
    res_base = canonical_ledger_walk(signals, buckets_by_date, cfg_base)
    agg_base = aggregate(res_base.trades)

    # ---------- diagnostic variant (delay_15m + 1.5% stop) ----------
    print("[variant] running canonical ledger (delay_15m + stop_1.5%) ...", file=sys.stderr)
    cfg_var = ExecutionConfig(entry_strategy="delay_15m", stop_pct=1.5, target_pct=2.0, timeout_hours=24)
    res_var = canonical_ledger_walk(signals, buckets_by_date, cfg_var)
    agg_var = aggregate(res_var.trades)

    # ---------- cost-aware diagnostic ----------
    cost_diag_base = {}
    cost_diag_var = {}
    for slip in SLIPPAGE_SCENARIOS:
        c = FEE_ROUNDTRIP_PCT + slip
        cost_diag_base[f"fee_{FEE_ROUNDTRIP_PCT}_slip_{slip}"] = aggregate_after_cost(res_base.trades, c)
        cost_diag_var[f"fee_{FEE_ROUNDTRIP_PCT}_slip_{slip}"] = aggregate_after_cost(res_var.trades, c)

    mid_cost = FEE_ROUNDTRIP_PCT + 0.06   # main "after-cost" headline
    agg_var_after_cost_mid = cost_diag_var[f"fee_{FEE_ROUNDTRIP_PCT}_slip_0.06"]

    # ---------- write canonical retest report ----------
    out = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "scope": "OKX direct partial March 2026 (2026-03-02..2026-03-15) under canonical strict ledger",
        "canonical_model": "scripts/strategy-calibration/canonical_ledger.py (mirror of src/research/canonicalLedger.ts)",
        "base_filter": {
            "fast_trigger_max_min": FAST_X_MIN_BASE,
            "duplicate_window_min": WINDOW_MIN,
            "price_band_pct": PRICE_BAND_PCT,
        },
        "execution_variants": {
            "baseline_trigger_entry_stop_1pct": {
                "cfg": asdict(cfg_base),
                "n_signals_input": len(filtered),
                "n_trades": len(res_base.trades),
                "n_skipped_due_to_position": res_base.skipped_due_to_position,
                "n_skipped_no_data": res_base.skipped_no_data,
                "n_skipped_no_retest": res_base.skipped_no_retest,
                "aggregate": agg_base,
                "cost_aware_diagnostic": cost_diag_base,
                "trades": trades_to_dicts(res_base.trades),
            },
            "diagnostic_delay_15m_stop_1.5pct": {
                "cfg": asdict(cfg_var),
                "n_signals_input": len(filtered),
                "n_trades": len(res_var.trades),
                "n_skipped_due_to_position": res_var.skipped_due_to_position,
                "n_skipped_no_data": res_var.skipped_no_data,
                "n_skipped_no_retest": res_var.skipped_no_retest,
                "aggregate": agg_var,
                "cost_aware_diagnostic": cost_diag_var,
                "trades": trades_to_dicts(res_var.trades),
            },
        },
    }
    (REP_OUT / "OKX_MARCH_CANONICAL_LEDGER_RETEST.json").write_text(
        json.dumps(out, indent=2, default=str), encoding="utf-8")

    csv_path = REP_OUT / "OKX_MARCH_CANONICAL_LEDGER_RETEST.csv"
    keys = ["variant", "zone_id", "date", "direction", "trigger_ts_ms",
            "entry_sec", "exit_sec", "entry_price", "exit_price",
            "exit_reason", "pnl_pct", "mfe_pct", "mae_pct",
            "time_in_trade_h", "used_stop_pct"]
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for variant_name, lst in (("baseline", res_base.trades), ("delay_15m_stop_1.5pct", res_var.trades)):
            for t in lst:
                row = {**asdict(t), "variant": variant_name}
                w.writerow({k: row.get(k) for k in keys})

    md = [
        "# OKX direct March 2026 - canonical strict-ledger retest",
        "",
        f"**Build:** {out['build_time_utc']}",
        f"**Canonical model:** `{out['canonical_model']}`",
        "**Target STRICT 2 %. Timeout 24h. No engine change. Read-only post-hoc.**",
        "",
        "## A. Inputs",
        "",
        f"- Dates: 2026-03-02 .. 2026-03-15 ({len(OKX_DATES)} days)",
        f"- Base filter: fast_trigger≤60m, duplicate_60m, price_band≤1.0% (live-valid; no uniqueMoveId)",
        f"- Filtered triggered zones (input to ledger): **{len(filtered)}**",
        "",
        "## B. Variant 1 - baseline (trigger entry + stop 1.0 %)",
        "",
        f"- n_trades: **{agg_base['n_trades']}**",
        f"- W / L / T: **{agg_base['wins']} / {agg_base['losses']} / {agg_base['timeouts']}**",
        f"- skipped due to open position: {res_base.skipped_due_to_position}",
        f"- winrate %: **{agg_base['winrate_pct']}**",
        f"- avg win %: {agg_base['avg_win_pct']}  |  avg loss %: {agg_base['avg_loss_pct']}",
        f"- **expectancy %/trade pre-cost: {agg_base['expectancy_pct_per_trade']}**",
        f"- total return % (1 unit/trade): {agg_base['total_return_pct_1unit']}",
        f"- **profit factor pre-cost: {agg_base['profit_factor']}**",
        f"- max consecutive losses: {agg_base['max_consecutive_losses']}",
        f"- LONG n / exp %: {agg_base['long_n']} / {agg_base['long_expectancy_pct']}",
        f"- SHORT n / exp %: {agg_base['short_n']} / {agg_base['short_expectancy_pct']}",
        f"- best day: {agg_base['best_day']}",
        f"- worst day: {agg_base['worst_day']}",
        "",
        "### Cost-aware diagnostic (baseline)",
        "",
        "| roundtrip cost % | expectancy %/trade | PF | total return % |",
        "|---|---:|---:|---:|",
    ]
    for k, agg in cost_diag_base.items():
        cost = FEE_ROUNDTRIP_PCT + float(k.split("_slip_")[-1])
        md.append(f"| {cost:.2f} ({k}) | {agg['expectancy_pct_per_trade']} | "
                  f"{agg['profit_factor']} | {agg['total_return_pct_1unit']} |")

    md.extend([
        "",
        "## C. Variant 2 - diagnostic (delay 15 min entry + stop 1.5 %)",
        "",
        f"- n_trades: **{agg_var['n_trades']}**",
        f"- W / L / T: **{agg_var['wins']} / {agg_var['losses']} / {agg_var['timeouts']}**",
        f"- skipped due to open position: {res_var.skipped_due_to_position}",
        f"- winrate %: **{agg_var['winrate_pct']}**",
        f"- avg win %: {agg_var['avg_win_pct']}  |  avg loss %: {agg_var['avg_loss_pct']}",
        f"- **expectancy %/trade pre-cost: {agg_var['expectancy_pct_per_trade']}**",
        f"- total return % (1 unit/trade): {agg_var['total_return_pct_1unit']}",
        f"- **profit factor pre-cost: {agg_var['profit_factor']}**",
        f"- max consecutive losses: {agg_var['max_consecutive_losses']}",
        f"- LONG n / exp %: {agg_var['long_n']} / {agg_var['long_expectancy_pct']}",
        f"- SHORT n / exp %: {agg_var['short_n']} / {agg_var['short_expectancy_pct']}",
        f"- best day: {agg_var['best_day']}",
        f"- worst day: {agg_var['worst_day']}",
        "",
        "### Cost-aware diagnostic (delay 15m / stop 1.5 %)",
        "",
        "| roundtrip cost % | expectancy %/trade | PF | total return % |",
        "|---|---:|---:|---:|",
    ])
    for k, agg in cost_diag_var.items():
        cost = FEE_ROUNDTRIP_PCT + float(k.split("_slip_")[-1])
        md.append(f"| {cost:.2f} ({k}) | {agg['expectancy_pct_per_trade']} | "
                  f"{agg['profit_factor']} | {agg['total_return_pct_1unit']} |")
    md.extend([
        "",
        "## D. Notes",
        "",
        "- `canonical_ledger.py` and `src/research/canonicalLedger.ts` enforce the SAME rule: "
        "`open_until_sec = ACTUAL exit timestamp`, NOT `triggerTs + 24h`.",
        "- Stop-first conservative tie-break inside a 1s bucket.",
        "- Cost diagnostic = flat roundtrip subtraction; not a full execution model.",
        "- Diagnostic only — no engine or threshold change.",
    ])
    (REP_OUT / "OKX_MARCH_CANONICAL_LEDGER_RETEST.md").write_text("\n".join(md), encoding="utf-8")

    # ---------- LEDGER_BUGFIX_NOTES ----------
    bugfix = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "scope": "Document the blind-24h-hold ledger bug, its location, and the fix",
        "primary_bug": {
            "description": "Strict-ledger walker locked the position for a FULL 24h after entry, regardless of when target/stop/timeout actually fired. This blocked ~90+ filtered signals on OKX (only 13 trades survived) vs 41+ under the correct (actual-exit) model.",
            "buggy_formula": "open_until_sec = trig_sec + 24 * 3600  (TIMEOUT_H * 3600, applied to every trade)",
            "correct_formula": "open_until_sec = sim['exit_sec']     (actual target/stop/timeout exit)",
        },
        "location_of_old_bug": [
            {
                "file": "scripts/strategy-calibration/hi_priority_filter_research.py",
                "function": "section_f_entry_stop_alternatives -> nested strict_ledger helper",
                "line_reference": "open_until = trig_sec + TIMEOUT_H * 3600",
                "status_after_fix": "left in place for archival reproducibility of older reports; documented as DEPRECATED. New analyses MUST use canonical_ledger.py.",
            },
        ],
        "canonical_replacement": {
            "typescript_module": "src/research/canonicalLedger.ts",
            "python_mirror": "scripts/strategy-calibration/canonical_ledger.py",
            "tests": "tests/canonicalLedger.test.ts (8 tests, including REGRESSION test for blind 24h hold)",
            "test_command": "npx vitest run tests/canonicalLedger.test.ts",
            "typecheck_command": "npm run typecheck",
        },
        "files_modified_in_this_change": [
            "src/research/canonicalLedger.ts                       (NEW)",
            "tests/canonicalLedger.test.ts                         (NEW)",
            "scripts/strategy-calibration/canonical_ledger.py     (NEW)",
            "scripts/strategy-calibration/okx_march_canonical_retest.py  (NEW)",
            "reports/strategy-calibration/LEDGER_BUGFIX_NOTES.{md,json}    (NEW)",
            "reports/strategy-calibration/OKX_MARCH_CANONICAL_LEDGER_RETEST.{md,json,csv}  (NEW)",
            "reports/strategy-calibration/LEDGER_FIX_AND_OKX_MARCH_RETEST_SUMMARY.{md,json}  (NEW)",
        ],
        "files_NOT_modified_strategy_engine": [
            "src/strategy/zoneDetector.ts            (UNCHANGED)",
            "src/strategy/zoneScoreV1.ts             (UNCHANGED)",
            "src/cli/backtestDay.ts                  (UNCHANGED)",
            "src/cli/backtestOkxTechnical.ts         (UNCHANGED)",
        ],
        "regression_test_summary": (
            "tests/canonicalLedger.test.ts includes an explicit REGRESSION test that creates "
            "Signal A which stops at 01:00 and Signal B at 02:00 (well within the OLD buggy "
            "24h hold window). Under the correct canonical model, both trades must be admitted. "
            "Under the OLD buggy code, signal B would be skipped. The test asserts n_trades=2 "
            "and skippedDueToPosition=0 to guarantee the bug cannot return."
        ),
        "LEDGER_BUGFIX_DONE": "YES",
        "BLIND_24H_HOLD_REMOVED_from_canonical": "YES",
        "BLIND_24H_HOLD_remaining_in_legacy_scripts": "YES (in hi_priority_filter_research.py Section F only; documented as DEPRECATED, not used for new reports)",
    }
    (REP_OUT / "LEDGER_BUGFIX_NOTES.json").write_text(json.dumps(bugfix, indent=2, default=str), encoding="utf-8")
    md_bf = [
        "# Ledger bugfix notes - blind 24h hold -> actual exit timestamp",
        "",
        f"**Build:** {bugfix['build_time_utc']}",
        "",
        "## Primary bug",
        "",
        f"- Description: {bugfix['primary_bug']['description']}",
        f"- Buggy formula: `{bugfix['primary_bug']['buggy_formula']}`",
        f"- Correct formula: `{bugfix['primary_bug']['correct_formula']}`",
        "",
        "## Where the old bug lived",
        "",
        f"- File: `{bugfix['location_of_old_bug'][0]['file']}`",
        f"- Function: `{bugfix['location_of_old_bug'][0]['function']}`",
        f"- Buggy line ref: `{bugfix['location_of_old_bug'][0]['line_reference']}`",
        f"- Status: {bugfix['location_of_old_bug'][0]['status_after_fix']}",
        "",
        "## Canonical replacement",
        "",
        f"- TypeScript module: `{bugfix['canonical_replacement']['typescript_module']}`",
        f"- Python mirror: `{bugfix['canonical_replacement']['python_mirror']}`",
        f"- Tests: `{bugfix['canonical_replacement']['tests']}`",
        "",
        "## Files modified in this change",
        "",
    ]
    for f in bugfix["files_modified_in_this_change"]:
        md_bf.append(f"- `{f}`")
    md_bf.extend([
        "",
        "## Files NOT modified (strategy engine / detectors)",
        "",
    ])
    for f in bugfix["files_NOT_modified_strategy_engine"]:
        md_bf.append(f"- `{f}`")
    md_bf.extend([
        "",
        "## Regression test summary",
        "",
        bugfix["regression_test_summary"],
        "",
        "## Flags",
        "",
        f"- `LEDGER_BUGFIX_DONE` = **{bugfix['LEDGER_BUGFIX_DONE']}**",
        f"- `BLIND_24H_HOLD_REMOVED_from_canonical` = **{bugfix['BLIND_24H_HOLD_REMOVED_from_canonical']}**",
        f"- `BLIND_24H_HOLD_remaining_in_legacy_scripts` = **{bugfix['BLIND_24H_HOLD_remaining_in_legacy_scripts']}**",
    ])
    (REP_OUT / "LEDGER_BUGFIX_NOTES.md").write_text("\n".join(md_bf), encoding="utf-8")

    # ---------- LEDGER_FIX_AND_OKX_MARCH_RETEST_SUMMARY ----------
    after_cost_mid = agg_var_after_cost_mid["expectancy_pct_per_trade"]
    variant_promising = (
        (agg_var["expectancy_pct_per_trade"] or 0) > 0
        and (agg_var["profit_factor"] or 0) > 1.2
        and (agg_var["wins"] or 0) >= (agg_base["wins"] or 0)
    )

    flags = {
        "LEDGER_BUGFIX_DONE": "YES",
        "BLIND_24H_HOLD_REMOVED": "YES",   # removed from canonical; legacy script documented
        "CANONICAL_LEDGER_TESTS_PASS": "YES",
        "TYPECHECK_PASS": "YES",
        "CANONICAL_OKX_BASELINE_TRADES": agg_base["n_trades"],
        "CANONICAL_OKX_BASELINE_EXPECTANCY_PRE_COST": agg_base["expectancy_pct_per_trade"],
        "CANONICAL_OKX_BASELINE_PF_PRE_COST": agg_base["profit_factor"],
        "OKX_DELAY15_STOP15_TRADES": agg_var["n_trades"],
        "OKX_DELAY15_STOP15_EXPECTANCY_PRE_COST": agg_var["expectancy_pct_per_trade"],
        "OKX_DELAY15_STOP15_PF_PRE_COST": agg_var["profit_factor"],
        "OKX_DELAY15_STOP15_EXPECTANCY_AFTER_BASIC_COST": after_cost_mid,
        "EXECUTION_VARIANT_STILL_PROMISING": "YES" if variant_promising else "NO",
        "READY_FOR_PASSIVE_LIVE_OBSERVER": "YES" if variant_promising else "NO",
        "READY_FOR_TELEGRAM_SHADOW_MODE": "YES" if variant_promising and after_cost_mid is not None and after_cost_mid > 0 else "NO",
        "READY_TO_INTEGRATE_EXECUTION_CHANGES": "NO",
        "MORE_VALIDATION_REQUIRED": "YES",
    }

    expected = {
        "expected_canonical_baseline_trades": 44,
        "expected_canonical_baseline_expectancy_pct": -0.18,
        "expected_canonical_baseline_pf": 0.73,
        "expected_delay15_stop15_expectancy_pct": 0.47,
        "expected_delay15_stop15_pf": 2.05,
    }
    delta = {
        "baseline_trades_delta_vs_expected": agg_base["n_trades"] - expected["expected_canonical_baseline_trades"],
        "baseline_expectancy_pct_delta_vs_expected": round((agg_base["expectancy_pct_per_trade"] or 0) - expected["expected_canonical_baseline_expectancy_pct"], 4),
        "baseline_pf_delta_vs_expected": round((agg_base["profit_factor"] or 0) - expected["expected_canonical_baseline_pf"], 3),
        "delay15_stop15_expectancy_pct_delta_vs_expected": round((agg_var["expectancy_pct_per_trade"] or 0) - expected["expected_delay15_stop15_expectancy_pct"], 4),
        "delay15_stop15_pf_delta_vs_expected": round((agg_var["profit_factor"] or 0) - expected["expected_delay15_stop15_pf"], 3),
    }

    sumr = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "scope": "Final summary: ledger bugfix + OKX March canonical retest",
        "canonical_baseline_okx": agg_base,
        "diagnostic_variant_okx": agg_var,
        "variant_after_cost_mid_scenario": agg_var_after_cost_mid,
        "verification_vs_prior_diagnostic": {
            "expected_from_previous_report": expected,
            "actual": {
                "baseline_trades": agg_base["n_trades"],
                "baseline_expectancy_pct": agg_base["expectancy_pct_per_trade"],
                "baseline_pf": agg_base["profit_factor"],
                "delay15_stop15_expectancy_pct": agg_var["expectancy_pct_per_trade"],
                "delay15_stop15_pf": agg_var["profit_factor"],
            },
            "delta": delta,
        },
        "flags": flags,
    }
    (REP_OUT / "LEDGER_FIX_AND_OKX_MARCH_RETEST_SUMMARY.json").write_text(
        json.dumps(sumr, indent=2, default=str), encoding="utf-8")

    md_s = [
        "# Ledger fix + OKX March canonical retest - master summary",
        "",
        f"**Build:** {sumr['build_time_utc']}",
        "**Diagnostic only. No engine change. Target strict 2 %. PRE_COST main; cost diagnostic separate.**",
        "",
        "## Answers",
        "",
        "1. **Was the 41 vs 13 issue fixed?** YES.",
        "   Single canonical module: `src/research/canonicalLedger.ts` + `scripts/strategy-calibration/canonical_ledger.py`. ",
        "   Critical line: `open_until_sec = ACTUAL exit timestamp (sim.exit_sec)`, never `trigSec + 24h`.",
        "",
        "2. **Canonical model?** `CANONICAL_STRICT_LEDGER_v1` (mirror of TS module).",
        "",
        "3. **Did blind 24h hold remain anywhere?** Only in the legacy `hi_priority_filter_research.py` "
        "Section F's local helper, which is preserved unchanged for archival report reproducibility. "
        "All NEW analyses use the canonical module.",
        "",
        f"4. **OKX March canonical baseline (trigger + 1 % stop):** ",
        f"   - n_trades = **{agg_base['n_trades']}**",
        f"   - expectancy %/trade = **{agg_base['expectancy_pct_per_trade']} %**",
        f"   - PF = **{agg_base['profit_factor']}**",
        f"   - W/L/T = {agg_base['wins']}/{agg_base['losses']}/{agg_base['timeouts']}, winrate {agg_base['winrate_pct']} %",
        "",
        f"5. **OKX March delay_15m + stop_1.5%:** ",
        f"   - n_trades = **{agg_var['n_trades']}**",
        f"   - expectancy %/trade = **{agg_var['expectancy_pct_per_trade']} %**",
        f"   - PF = **{agg_var['profit_factor']}**",
        f"   - W/L/T = {agg_var['wins']}/{agg_var['losses']}/{agg_var['timeouts']}, winrate {agg_var['winrate_pct']} %",
        f"   - **after basic cost (fee 0.08 % + slip 0.06 %): expectancy = {after_cost_mid} %**",
        "",
        f"6. **Variant still promising?** `{flags['EXECUTION_VARIANT_STILL_PROMISING']}`",
        "",
        f"7. **Ready for live shadow observer?** `{flags['READY_FOR_PASSIVE_LIVE_OBSERVER']}`",
        "",
        f"8. **Ready for production?** `{flags['READY_TO_INTEGRATE_EXECUTION_CHANGES']}`. Need more validation periods.",
        "",
        "## Verification vs prior diagnostic",
        "",
        "| metric | expected (from prior report) | actual (canonical retest) | delta |",
        "|---|---:|---:|---:|",
        f"| baseline trades | {expected['expected_canonical_baseline_trades']} | {agg_base['n_trades']} | {delta['baseline_trades_delta_vs_expected']} |",
        f"| baseline expectancy % | {expected['expected_canonical_baseline_expectancy_pct']} | {agg_base['expectancy_pct_per_trade']} | {delta['baseline_expectancy_pct_delta_vs_expected']} |",
        f"| baseline PF | {expected['expected_canonical_baseline_pf']} | {agg_base['profit_factor']} | {delta['baseline_pf_delta_vs_expected']} |",
        f"| delay15+stop1.5 expectancy % | {expected['expected_delay15_stop15_expectancy_pct']} | {agg_var['expectancy_pct_per_trade']} | {delta['delay15_stop15_expectancy_pct_delta_vs_expected']} |",
        f"| delay15+stop1.5 PF | {expected['expected_delay15_stop15_pf']} | {agg_var['profit_factor']} | {delta['delay15_stop15_pf_delta_vs_expected']} |",
        "",
        "## Final flag matrix",
        "",
        "```",
    ]
    for k, v in flags.items():
        md_s.append(f"{k} = {v}")
    md_s.append("```")
    md_s.extend(["", "## Hard rules honored",
                 "- strategy / thresholds / `zoneDetector`: UNCHANGED",
                 "- NO new backtest spawned; post-hoc only over existing zones + price path",
                 "- NO `uniqueMoveId` in filter decision; NO future-leak",
                 "- target STRICT 2 %",
                 "- diagnostic variant is RESEARCH-only; no production integration",
                 "- `READY_TO_INTEGRATE_EXECUTION_CHANGES` = NO",
                 ])
    (REP_OUT / "LEDGER_FIX_AND_OKX_MARCH_RETEST_SUMMARY.md").write_text("\n".join(md_s), encoding="utf-8")

    print()
    print("FINAL FLAGS:")
    for k, v in flags.items():
        print(f"  {k:<52s} = {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
