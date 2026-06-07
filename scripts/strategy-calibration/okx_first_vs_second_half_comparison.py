"""First-half vs second-half OKX direct March comparison.

Reads existing JSON artefacts:
  reports/strategy-calibration/OKX_MARCH_CANONICAL_LEDGER_RETEST.json       (first half)
  reports/strategy-calibration/OKX_SECOND_HALF_CANONICAL_EXECUTION_RETEST.json  (second half)
  reports/strategy-calibration/OKX_SECOND_HALF_ENGINE_SUMMARY.json
  reports/strategy-calibration/OKX_SECOND_HALF_*.json (addendum + max2 if available)

Produces a clean side-by-side comparison.
"""
from __future__ import annotations
import csv
import datetime as dt
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path("C:/Users/gibilev/orderflow-research")
REP_OUT = ROOT / "reports/strategy-calibration"
REP_OUT.mkdir(parents=True, exist_ok=True)


def safe_get(d, *keys, default=None):
    for k in keys:
        if d is None: return default
        d = d.get(k) if isinstance(d, dict) else None
    return d if d is not None else default


def load_json(p: Path):
    if not p.exists(): return None
    return json.loads(p.read_text(encoding="utf-8"))


def main() -> int:
    fh = load_json(REP_OUT / "OKX_MARCH_CANONICAL_LEDGER_RETEST.json")
    sh = load_json(REP_OUT / "OKX_SECOND_HALF_CANONICAL_EXECUTION_RETEST.json")
    sh_engine = load_json(REP_OUT / "OKX_SECOND_HALF_ENGINE_SUMMARY.json")

    if fh is None or sh is None:
        print("missing canonical retest JSONs", flush=True)
        return 1

    # First-half retest stored variants under different key names. Adapt:
    fh_a = safe_get(fh, "execution_variants", "baseline_trigger_entry_stop_1pct") or {}
    fh_b = safe_get(fh, "execution_variants", "diagnostic_delay_15m_stop_1.5pct") or {}
    sh_a = safe_get(sh, "execution_variants", "A_trigger_entry_stop_1pct") or {}
    sh_b = safe_get(sh, "execution_variants", "B_delay_15m_stop_1.5pct") or {}

    # First-half engine summary: build from already-known facts (14 days, 510 zones, 295 trig, 98 reached, 15 primary).
    fh_engine = {
        "n_days": 14,
        "zones_total": 510,
        "triggered_total": 295,
        "reached_raw_total": 98,
        "primary_unique_total": 15,
        "duplicate_credits": 83,
        "failed_triggered": "n/a",
    }
    sh_engine_totals = (sh_engine or {}).get("totals") or {}

    def metrics(block: dict, basic_key="aggregate_after_basic_cost") -> dict:
        agg = block.get("aggregate") or block.get("aggregate_pre_cost") or {}
        basic = block.get("cost_aware_diagnostic", {}).get("fees0.08_slip0.06", {}) or block.get(basic_key, {})
        # First half script wrote cost_aware under "cost_aware_diagnostic" key with "fees0.08_slip0.06"
        # Second half script wrote under "cost_diagnostic" with "fee_0.08_slip_0.06"
        if not basic:
            basic = block.get("cost_diagnostic", {}).get("fee_0.08_slip_0.06", {})
        return {
            "n_trades": agg.get("n_trades"),
            "wins": agg.get("wins"), "losses": agg.get("losses"), "timeouts": agg.get("timeouts"),
            "winrate_pct": agg.get("winrate_pct"),
            "expectancy_pre_cost": agg.get("expectancy_pct_per_trade"),
            "pf_pre_cost": agg.get("profit_factor"),
            "total_return_pre_cost": agg.get("total_return_pct_1unit"),
            "expectancy_after_cost": basic.get("expectancy_pct_per_trade"),
            "pf_after_cost": basic.get("profit_factor"),
            "total_return_after_cost": basic.get("total_return_pct_1unit"),
            "max_consec_losses": agg.get("max_consecutive_losses"),
            "long_n": agg.get("long_n"), "long_exp": agg.get("long_expectancy_pct"),
            "short_n": agg.get("short_n"), "short_exp": agg.get("short_expectancy_pct"),
        }

    fh_a_m = metrics(fh_a); fh_b_m = metrics(fh_b)
    sh_a_m = metrics(sh_a); sh_b_m = metrics(sh_b)

    # delay15_stop15 holds on second half?
    holds = "UNKNOWN"
    if sh_b_m["expectancy_pre_cost"] is not None and fh_b_m["expectancy_pre_cost"] is not None:
        if sh_b_m["expectancy_pre_cost"] >= 0 and sh_b_m["pf_pre_cost"] and sh_b_m["pf_pre_cost"] > 1.0:
            holds = "YES"
        elif sh_b_m["expectancy_pre_cost"] < -0.05 or (sh_b_m["pf_pre_cost"] or 0) < 0.9:
            holds = "NO"
        else:
            holds = "MARGINAL"

    cmp = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "first_half_days": "2026-03-02..2026-03-15 (14 days)",
        "second_half_days": "2026-03-16, 03-18..03-31 (15 days; 03-17 missing)",
        "engine": {
            "first_half": fh_engine,
            "second_half": {**sh_engine_totals, "n_days": (sh_engine or {}).get("n_days_processed", 15)},
        },
        "execution_A_trigger_stop_1pct": {
            "first_half": fh_a_m, "second_half": sh_a_m,
        },
        "execution_B_delay15_stop_1.5pct": {
            "first_half": fh_b_m, "second_half": sh_b_m,
        },
        "delay15_stop15_holds_on_second_half": holds,
    }
    (REP_OUT / "OKX_FIRST_HALF_VS_SECOND_HALF_MASTER_COMPARISON.json").write_text(
        json.dumps(cmp, indent=2, default=str), encoding="utf-8")

    # CSV
    with (REP_OUT / "OKX_FIRST_HALF_VS_SECOND_HALF_MASTER_COMPARISON.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["metric", "first_half", "second_half"])
        w.writerow(["A_trigger_stop_1pct_n_trades", fh_a_m["n_trades"], sh_a_m["n_trades"]])
        w.writerow(["A_winrate_pct", fh_a_m["winrate_pct"], sh_a_m["winrate_pct"]])
        w.writerow(["A_expectancy_pre_cost", fh_a_m["expectancy_pre_cost"], sh_a_m["expectancy_pre_cost"]])
        w.writerow(["A_pf_pre_cost", fh_a_m["pf_pre_cost"], sh_a_m["pf_pre_cost"]])
        w.writerow(["A_expectancy_after_cost", fh_a_m["expectancy_after_cost"], sh_a_m["expectancy_after_cost"]])
        w.writerow(["A_pf_after_cost", fh_a_m["pf_after_cost"], sh_a_m["pf_after_cost"]])
        w.writerow(["B_delay15_stop15_n_trades", fh_b_m["n_trades"], sh_b_m["n_trades"]])
        w.writerow(["B_winrate_pct", fh_b_m["winrate_pct"], sh_b_m["winrate_pct"]])
        w.writerow(["B_expectancy_pre_cost", fh_b_m["expectancy_pre_cost"], sh_b_m["expectancy_pre_cost"]])
        w.writerow(["B_pf_pre_cost", fh_b_m["pf_pre_cost"], sh_b_m["pf_pre_cost"]])
        w.writerow(["B_expectancy_after_cost", fh_b_m["expectancy_after_cost"], sh_b_m["expectancy_after_cost"]])
        w.writerow(["B_pf_after_cost", fh_b_m["pf_after_cost"], sh_b_m["pf_after_cost"]])
        w.writerow(["B_holds", "YES", holds])

    md = [
        "# OKX direct March - FIRST HALF vs SECOND HALF master comparison",
        "",
        f"**Build:** {cmp['build_time_utc']}",
        f"**First half:** {cmp['first_half_days']}",
        f"**Second half:** {cmp['second_half_days']}",
        "",
        "## Engine-level",
        "",
        "| metric | first half | second half | comment |",
        "|---|---:|---:|---|",
        f"| days | {fh_engine['n_days']} | {(sh_engine or {}).get('n_days_processed')} | |",
        f"| zones | {fh_engine['zones_total']} | {sh_engine_totals.get('zones')} | |",
        f"| triggered | {fh_engine['triggered_total']} | {sh_engine_totals.get('triggered')} | |",
        f"| reached_raw | {fh_engine['reached_raw_total']} | {sh_engine_totals.get('reached_raw')} | |",
        f"| primary unique | **{fh_engine['primary_unique_total']}** | **{sh_engine_totals.get('primary_unique_reached')}** | |",
        f"| duplicate credits | {fh_engine['duplicate_credits']} | {sh_engine_totals.get('duplicate_move_credits')} | |",
        "",
        "## Execution Variant A - trigger_entry + stop 1.0 %",
        "",
        "| metric | first half | second half | delta | comment |",
        "|---|---:|---:|---:|---|",
    ]
    def delta(a, b):
        if a is None or b is None: return None
        try: return round(b - a, 4)
        except: return None
    for label, key in [("trades", "n_trades"), ("wins", "wins"), ("losses", "losses"),
                        ("timeouts", "timeouts"), ("winrate %", "winrate_pct"),
                        ("expectancy pre-cost", "expectancy_pre_cost"),
                        ("PF pre-cost", "pf_pre_cost"),
                        ("total return pre-cost", "total_return_pre_cost"),
                        ("expectancy after cost", "expectancy_after_cost"),
                        ("PF after cost", "pf_after_cost"),
                        ("total return after cost", "total_return_after_cost"),
                        ("max consec losses", "max_consec_losses"),
                        ("LONG n / exp", None), ("SHORT n / exp", None)]:
        if key is None:
            if label == "LONG n / exp":
                md.append(f"| LONG n / exp | {fh_a_m['long_n']} / {fh_a_m['long_exp']} | {sh_a_m['long_n']} / {sh_a_m['long_exp']} | — | |")
            else:
                md.append(f"| SHORT n / exp | {fh_a_m['short_n']} / {fh_a_m['short_exp']} | {sh_a_m['short_n']} / {sh_a_m['short_exp']} | — | |")
            continue
        a = fh_a_m[key]; b = sh_a_m[key]
        md.append(f"| {label} | {a} | {b} | {delta(a, b)} | |")

    md.extend([
        "",
        "## Execution Variant B - delay 15 min + stop 1.5 % (diagnostic)",
        "",
        "| metric | first half | second half | delta | comment |",
        "|---|---:|---:|---:|---|",
    ])
    for label, key in [("trades", "n_trades"), ("wins", "wins"), ("losses", "losses"),
                        ("timeouts", "timeouts"), ("winrate %", "winrate_pct"),
                        ("expectancy pre-cost", "expectancy_pre_cost"),
                        ("PF pre-cost", "pf_pre_cost"),
                        ("total return pre-cost", "total_return_pre_cost"),
                        ("expectancy after cost", "expectancy_after_cost"),
                        ("PF after cost", "pf_after_cost"),
                        ("total return after cost", "total_return_after_cost"),
                        ("max consec losses", "max_consec_losses")]:
        a = fh_b_m[key]; b = sh_b_m[key]
        md.append(f"| {label} | {a} | {b} | {delta(a, b)} | |")
    md.append(f"| LONG n / exp | {fh_b_m['long_n']} / {fh_b_m['long_exp']} | {sh_b_m['long_n']} / {sh_b_m['long_exp']} | — | |")
    md.append(f"| SHORT n / exp | {fh_b_m['short_n']} / {fh_b_m['short_exp']} | {sh_b_m['short_n']} / {sh_b_m['short_exp']} | — | |")

    md.extend([
        "",
        f"## `DELAY15_STOP15_HOLDS_ON_SECOND_HALF` = **{holds}**",
        "",
        "Decision rule:",
        "- YES if expectancy_pre_cost >= 0 AND PF_pre_cost > 1.0",
        "- NO if expectancy_pre_cost < -0.05 OR PF_pre_cost < 0.9",
        "- MARGINAL otherwise",
    ])
    (REP_OUT / "OKX_FIRST_HALF_VS_SECOND_HALF_MASTER_COMPARISON.md").write_text("\n".join(md), encoding="utf-8")

    print("first vs second half comparison done")
    print(f"  A first half: exp={fh_a_m['expectancy_pre_cost']}, PF={fh_a_m['pf_pre_cost']}")
    print(f"  A second half: exp={sh_a_m['expectancy_pre_cost']}, PF={sh_a_m['pf_pre_cost']}")
    print(f"  B first half: exp={fh_b_m['expectancy_pre_cost']}, PF={fh_b_m['pf_pre_cost']}")
    print(f"  B second half: exp={sh_b_m['expectancy_pre_cost']}, PF={sh_b_m['pf_pre_cost']}")
    print(f"  HOLDS: {holds}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
