"""Addendum: isolate BE effect on the FULL enhanced 29-trade set.

The main run gated Model C by target-zone>=2% (which collapsed 29->4, unusable),
conflating the target-zone filter with BE. This addendum applies BE variants to
the SAME enhanced 29 zones with FIXED 2% TP + 1.5% SL, so BE's effect is measured
on a real n=29 sample. Reuses target-zone heatmap CSV (no recompute of swings).
"""
from __future__ import annotations
import csv, json, math, statistics as stats, sys, time, datetime as dt
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from march_target_zone_fuel import (load_dataset, explainable_score_l2_dyn,
    select_topn_per_day, build_buckets_with_volume, merge_forward_buckets,
    simulate_trade, classify_reason, metrics, ALL_DATES, FIRST_HALF, SECOND_HALF,
    DATA_ROOT, iso_to_sec, TARGET_PCT, STOP_PCT)

REP_OUT = next(p for p in Path(__file__).resolve().parents if (p / "package.json").exists() and (p / "scripts").exists()) / "reports" / "strategy-calibration"
def now_iso(): return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def run_model_fixedTP(zones, buckets_cache, be_variant=None):
    """Fixed 2% TP, 1.5% SL, optional BE. No target-zone gate."""
    trades = []
    for z in zones:
        confirmed_sec = iso_to_sec(z.get("confirmed_iso"))
        if confirmed_sec is None: continue
        direction = z["direction"]
        fwd = merge_forward_buckets(z["date"], buckets_cache, lookahead=2)
        if not fwd[0]: continue
        secs = fwd[0]
        lo, hi = 0, len(secs)
        while lo < hi:
            m = (lo + hi) // 2
            if secs[m] < confirmed_sec: lo = m + 1
            else: hi = m
        if lo >= len(secs): continue
        entry_sec = secs[lo]; entry_price = fwd[3][lo]
        if entry_price <= 0: continue
        if direction == "LONG":
            tp_price = entry_price * (1 + TARGET_PCT/100.0)
            sl_price = entry_price * (1 - STOP_PCT/100.0)
        else:
            tp_price = entry_price * (1 - TARGET_PCT/100.0)
            sl_price = entry_price * (1 + STOP_PCT/100.0)
        sim = simulate_trade(direction, entry_sec, entry_price, tp_price, sl_price, fwd,
                             be_variant=be_variant, target_distance_pct=TARGET_PCT,
                             entry_microprice_aligned=z.get("dl2_microprice_aligned_delta_5m_bps"),
                             entry_opp_wall=z.get("ms_large_walls_on_path"))
        if sim.get("exit_reason") == "no_data": continue
        er = sim["exit_reason"]
        outcome = ("WIN" if er=="target" else ("BE" if er=="be" else ("LOSS" if er=="stop" else "TIMEOUT")))
        reason = classify_reason(z, sim, outcome)
        trades.append({"date": z["date"], "direction": direction, "zone_id": z["zone_id"],
            "outcome": outcome, "reason_class": reason, "exit_reason": er,
            "pnl_pre_cost": sim["pnl_pre_cost"], "pnl_after_cost": sim["pnl_after_cost"],
            "mfe_pct": sim["mfe_pct"], "mae_pct": sim["mae_pct"], "be_armed": sim["be_armed"],
            "watch_label": z.get("watch_label"), "coverage_class": z.get("coverage_class")})
    return trades


def main():
    print("[load] ...", file=sys.stderr)
    rows = load_dataset()
    # merge target-zone heatmap (already computed) for completeness
    tzp = REP_OUT / "MARCH_TARGET_ZONE_HEATMAP_FEATURES.csv"
    if tzp.exists():
        with tzp.open(encoding="utf-8") as f:
            rdr = csv.DictReader(f)
            tz = {}
            for lr in rdr:
                d = {}
                for k, v in lr.items():
                    if k == "zone_id": continue
                    try: d[k] = float(v) if v not in ("", "None", None) else None
                    except: d[k] = v if v else None
                tz[lr["zone_id"]] = d
        for r in rows:
            for k, v in tz.get(r["zone_id"], {}).items():
                if k not in r: r[k] = v
    enh_filter = lambda r: (r.get("dist_to_recent_swing_high_pct") is not None and r["dist_to_recent_swing_high_pct"] <= 0.4616
                            and r.get("dl2_supp_minus_opp_net_flow_15m") is not None and r["dl2_supp_minus_opp_net_flow_15m"] <= 4497.76)
    enhanced_zones = select_topn_per_day(rows, enh_filter, explainable_score_l2_dyn, 1)
    print(f"  enhanced zones={len(enhanced_zones)}", file=sys.stderr)

    print("[buckets] ...", file=sys.stderr)
    buckets_cache = {}
    needed = set(ALL_DATES); needed.add("2026-03-01"); needed.add("2026-04-01")
    for d in sorted(needed):
        p = DATA_ROOT / d / "trades.csv.gz"
        if p.exists():
            buckets_cache[d] = build_buckets_with_volume(p)

    # Reference: fixed 2% TP, NO BE
    ref = run_model_fixedTP(enhanced_zones, buckets_cache, be_variant=None)
    ref_by_zone = {t["zone_id"]: t for t in ref}
    mref = metrics(ref)

    out_models = {"A_enhanced_fixed2pct_noBE": {"trades": ref, "m": mref}}
    for bev in ("C1", "C2", "C3", "C4"):
        t = run_model_fixedTP(enhanced_zones, buckets_cache, be_variant=bev)
        m = metrics(t)
        # BE accounting vs reference
        saved = killed = be_before_target = 0
        for tr in t:
            if tr["outcome"] != "BE": continue
            a = ref_by_zone.get(tr["zone_id"])
            if not a: continue
            if a["outcome"] == "LOSS": saved += 1
            elif a["outcome"] == "WIN": killed += 1; be_before_target += 1
        m["losses_saved_by_BE"] = saved
        m["winners_killed_by_BE"] = killed
        m["BE_before_later_target"] = be_before_target
        out_models[f"A_enhanced_fixed2pct_BE_{bev}"] = {"trades": t, "m": m}

    # write report
    report = {"build_time_utc": now_iso(),
              "note": "BE isolated on FULL enhanced 29-trade set (fixed 2% TP + 1.5% SL + BE), "
                      "NO target-zone gate. This is the correct test of BE's standalone effect.",
              "models": {name: {**{k: v for k, v in d["m"].items()}} for name, d in out_models.items()}}
    (REP_OUT / "MARCH_BE_ISOLATION_ADDENDUM.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    md = ["# BE isolation addendum (full enhanced 29-trade set, fixed 2% TP)", "",
          f"**Build:** {now_iso()}",
          "**Why:** main Model C gated by target-zone>=2% collapsed to n=4. This isolates BE on the real n=29.",
          "",
          "| model | trades | W | L | TO | BE | winrate% | exp_aft% | PF_aft | totRet% | maxCL | saved | killed |",
          "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for name, d in out_models.items():
        m = d["m"]
        md.append(f"| {name} | {m['trades']} | {m['wins']} | {m['losses']} | {m['timeouts']} | {m['be_exits']} | "
                  f"{m['winrate_pct']} | {m['expectancy_after_cost_pct']} | {m['pf_after_cost']} | "
                  f"{m['total_return_after_cost_pct']} | {m['max_consecutive_losses']} | "
                  f"{m.get('losses_saved_by_BE','-')} | {m.get('winners_killed_by_BE','-')} |")
    md.append("")
    # verdict
    best_be = max((k for k in out_models if "BE_" in k),
                  key=lambda k: out_models[k]["m"]["expectancy_after_cost_pct"] or -99)
    be_helps = out_models[best_be]["m"]["expectancy_after_cost_pct"] > mref["expectancy_after_cost_pct"]
    md += [f"**Reference (no BE):** winrate {mref['winrate_pct']}%, exp_aft {mref['expectancy_after_cost_pct']}%, PF {mref['pf_after_cost']}, totRet {mref['total_return_after_cost_pct']}%",
           f"**Best BE variant:** {best_be} (exp_aft {out_models[best_be]['m']['expectancy_after_cost_pct']}%)",
           f"**BE improves expectancy over no-BE on full 29:** {'YES' if be_helps else 'NO'}",
           "",
           "Each BE variant moves stop to entry after its arm condition; BE exit ≈ -0.14% (cost). "
           "losses_saved = trades that were a full -1.64% loss in no-BE but exited ≈breakeven with BE. "
           "winners_killed = trades that were +1.86% wins in no-BE but got stopped at breakeven first."]
    (REP_OUT / "MARCH_BE_ISOLATION_ADDENDUM.md").write_text("\n".join(md), encoding="utf-8")

    print()
    print("BE ISOLATION (full enhanced 29, fixed 2% TP):")
    print(f"{'model':<32} {'tr':>3} {'W':>3} {'L':>3} {'TO':>3} {'BE':>3} {'wr%':>6} {'exp%':>7} {'PF':>6} {'ret%':>8} {'saved':>5} {'kill':>4}")
    for name, d in out_models.items():
        m = d["m"]
        print(f"{name:<32} {m['trades']:>3} {m['wins']:>3} {m['losses']:>3} {m['timeouts']:>3} {m['be_exits']:>3} "
              f"{m['winrate_pct']:>6} {m['expectancy_after_cost_pct']:>7} {str(m['pf_after_cost']):>6} "
              f"{m['total_return_after_cost_pct']:>8} {m.get('losses_saved_by_BE','-'):>5} {m.get('winners_killed_by_BE','-'):>4}")
    print(f"\nBE_HELPS_ON_FULL_29 = {'YES' if be_helps else 'NO'}; BEST_BE_VARIANT = {best_be}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
