"""A4/A5/A6 — March-filter retest on OKX May + strong-move labels + March-vs-May comparison.

Reuses venue_norm_research (V) selector logic. Thresholds frozen from OKX March only.
Gates on OKX_2026_05_21_30_FEATURE_CACHE.json. No tuning on May; causal features.
"""
from __future__ import annotations
import csv, json, statistics as st, sys, datetime as dt
from collections import defaultdict
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "package.json").exists() and (p / "scripts").exists())
sys.path.insert(0, str(ROOT / "scripts/strategy-calibration"))
import venue_norm_research as V

OUT = ROOT / "reports/okx-may"
MAY_CACHE = OUT / "OKX_2026_05_21_30_FEATURE_CACHE.json"
MARCH_CACHE = ROOT / "reports/strategy-calibration/OKX_MARCH_DIAG_FEATURE_CACHE.json"
OKX_MARCH_REF = {"trades": 29, "winrate": 62.07, "exp": 0.6475, "pf": 2.258, "ret": 18.78}


def now_iso(): return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
def num(x): return x if isinstance(x, (int, float)) else None


def classify_counts(trades):
    cd = sum(1 for t in trades if t.get("sim_outcome") == "TIMEOUT" and (t.get("sim_pnl_pre_cost") or 0) > 0)
    wrong = sum(1 for t in trades if not t.get("sim_correct_direction"))
    stop = sum(1 for t in trades if t.get("sim_outcome") == "LOSS")
    to_neg = sum(1 for t in trades if t.get("sim_outcome") == "TIMEOUT" and (t.get("sim_pnl_pre_cost") or 0) <= 0)
    fake = sum(1 for t in trades if t["direction"] == "LONG" and V.regime_against(t) and not V.has_reversal_proof(t))
    return {"correct_dir_no_2pct": cd, "wrong_direction": wrong, "stop_no_2pct": stop,
            "timeout_negative": to_neg, "fake_accumulation": fake}


def model_metrics(zones, sel):
    tr = [z for z in sel if z.get("sim_outcome")]
    m = V.metrics(tr); m.update(classify_counts(tr))
    days = len({z["_date"] for z in zones}); seldays = len({z["_date"] for z in sel})
    m["no_trade_days"] = days - seldays; m["alerts_per_day"] = round(len(sel) / max(days, 1), 2)
    m["long_winrate"] = round(100 * sum(1 for t in tr if t["direction"] == "LONG" and t["sim_outcome"] == "WIN") / max(sum(1 for t in tr if t["direction"] == "LONG"), 1), 2)
    m["short_winrate"] = round(100 * sum(1 for t in tr if t["direction"] == "SHORT" and t["sim_outcome"] == "WIN") / max(sum(1 for t in tr if t["direction"] == "SHORT"), 1), 2)
    return m


def main():
    if not MAY_CACHE.exists():
        print("WAITING: OKX May feature cache not present", file=sys.stderr); return 2
    may = json.loads(MAY_CACHE.read_text(encoding="utf-8"))
    V.normalize_layer(may, V.COMMON_FEATS)
    print(f"OKX May zones {len(may)}", file=sys.stderr)

    # ---- A4: models M0..M5 ----
    models = {}
    models["M0_absolute_march"] = V.select_model(may, "M0")
    models["M1_norm_pctile"] = V.select_model(may, "M0")  # placeholder, replaced below
    # M1/M2 use norm filter top1/day
    def topbyday(passers):
        byd = defaultdict(list)
        for z in passers: byd[z["_date"]].append(z)
        return [sorted(byd[d], key=lambda x: -x["explainable_score"])[0] for d in sorted(byd)]
    models["M1_norm_pctile"] = topbyday([z for z in may if V.norm_filter(z, "pctile")])
    models["M2_norm_zscore"] = topbyday([z for z in may if V.norm_filter(z, "z")])
    models["M3_dir_guard"] = V.select_model(may, "M2")        # norm filter + score floor + dir guard, 1/day
    models["M4_noise_confluence"] = V.select_model(may, "M3") # + noise
    models["M5_live_valid"] = V.select_model(may, "M5")       # first-eligible + floor + guard + noise + cooldown + no-trade

    rows = []
    for name, sel in models.items():
        m = model_metrics(may, sel)
        rows.append({"model": name, **m})
    with (OUT / "OKX_2026_05_21_30_MARCH_FILTER_RETEST.csv").open("w", encoding="utf-8", newline="") as fh:
        keys = ["model", "trades", "wins", "losses", "timeouts", "winrate_pct", "expectancy_after_cost_pct",
                "pf_after_cost", "total_return_after_cost_pct", "max_consecutive_losses", "no_trade_days",
                "alerts_per_day", "long_winrate", "short_winrate", "fake_accumulation", "wrong_direction",
                "correct_dir_no_2pct", "stop_no_2pct", "timeout_negative"]
        w = csv.DictWriter(fh, fieldnames=keys, extrasaction="ignore"); w.writeheader(); w.writerows(rows)
    (OUT / "OKX_2026_05_21_30_MARCH_FILTER_RETEST.json").write_text(json.dumps(
        {"build": now_iso(), "okx_march_ref": OKX_MARCH_REF, "models": rows,
         "thresholds_from_march": {"swing_max": V.SWING_MAX, "supp_opp_abs": V.SUPP_OPP_ABS,
                                   "supp_opp_pctile": V.SUPP_OPP_PCTILE_CUT, "supp_opp_z": V.SUPP_OPP_Z_CUT,
                                   "score_pctile_floor": V.SCORE_PCTILE_FLOOR}}, indent=2, default=str), encoding="utf-8")
    md = ["# A4. OKX May — March-filter retest (frozen, no tuning)", "", f"**Build:** {now_iso()}",
          f"OKX March ref: 29 tr, 62.07%, exp +0.6475, PF 2.258. Thresholds frozen from March.", "",
          "| model | tr | W/L/TO | wr% | exp% | PF | totRet% | maxCL | no-trade | alerts/d | L/S wr | fake | wrongdir |",
          "|---|--:|:--:|--:|--:|--:|--:|--:|--:|--:|:--:|--:|--:|"]
    for r in rows:
        md.append(f"| {r['model']} | {r['trades']} | {r['wins']}/{r['losses']}/{r['timeouts']} | {r['winrate_pct']} | "
                  f"{r['expectancy_after_cost_pct']} | {r['pf_after_cost']} | {r['total_return_after_cost_pct']} | "
                  f"{r['max_consecutive_losses']} | {r['no_trade_days']} | {r['alerts_per_day']} | "
                  f"{r['long_winrate']}/{r['short_winrate']} | {r['fake_accumulation']} | {r['wrong_direction']} |")
    (OUT / "OKX_2026_05_21_30_MARCH_FILTER_RETEST.md").write_text("\n".join(md), encoding="utf-8")

    # ---- A5: strong-move labels ----
    lab_rows = []
    cls_counts = defaultdict(int)
    for z in may:
        if not z.get("sim_outcome"):
            continue
        mfe = num(z.get("sim_mfe_pct")) or 0; mae = num(z.get("sim_mae_pct")) or 0
        hit2 = z["sim_outcome"] == "WIN"; hit25 = mfe >= 2.5; hit3 = mfe >= 3.0
        if z["sim_label"] == "NOISE": cls = "NOISE"
        elif hit3: cls = "STRONG_WIN_3"
        elif hit25: cls = "STRONG_WIN_2_5"
        elif hit2: cls = "WEAK_WIN"
        else: cls = "MID"
        cls_counts[cls] += 1
        lab_rows.append({"date": z["_date"], "dir": z["direction"], "label_class": cls,
                         "hit_2pct": int(hit2), "hit_2_5pct": int(hit25), "hit_3pct": int(hit3),
                         "mfe_pct": mfe, "mae_pct": mae, "time_to_2pct_sec": (z.get("sim_exit_sec") if hit2 else None),
                         "supp_opp_15m": z.get("dl2_supp_minus_opp_net_flow_15m"), "eng_ofi": z.get("eng_ofi"),
                         "reclaim": z.get("reclaim_zoneMid_preconfirm"), "regime_1d": z.get("regime_1d")})
    with (OUT / "OKX_2026_05_21_30_STRONG_MOVE_LABELS.csv").open("w", encoding="utf-8", newline="") as fh:
        if lab_rows:
            w = csv.DictWriter(fh, fieldnames=list(lab_rows[0].keys())); w.writeheader(); w.writerows(lab_rows)
    (OUT / "OKX_2026_05_21_30_STRONG_MOVE_LABELS.json").write_text(json.dumps(
        {"build": now_iso(), "class_counts": dict(cls_counts), "n_traded": len(lab_rows)}, indent=2), encoding="utf-8")
    (OUT / "OKX_2026_05_21_30_STRONG_MOVE_LABELS.md").write_text(
        f"# A5. OKX May — strong-move labels\n\n**Build:** {now_iso()}\n\n"
        f"Traded zones: {len(lab_rows)}. Class counts: {dict(cls_counts)}\n\n"
        "Primary win = strict 2%. STRONG_WIN_2_5/3 use MFE>=2.5/3.0%.\n", encoding="utf-8")

    # ---- A6: March vs May comparison ----
    march = json.loads(MARCH_CACHE.read_text(encoding="utf-8"))
    V.normalize_layer(march, V.COMMON_FEATS)
    m_traded = [z for z in march if z.get("sim_outcome")]; may_traded = [z for z in may if z.get("sim_outcome")]
    def base_rate(zs): return round(100 * sum(1 for z in zs if z["sim_label"] == "GOOD") / max(len(zs), 1), 2)
    m0 = next(r for r in rows if r["model"] == "M0_absolute_march")
    transfer = "YES" if (m0["winrate_pct"] >= 55 and (m0["pf_after_cost"] or 0) >= 1.5) else (
        "PARTIAL" if ((m0["expectancy_after_cost_pct"] or -9) > 0 and (m0["pf_after_cost"] or 0) >= 1.2) else "NO")
    best = max(rows, key=lambda r: (r["expectancy_after_cost_pct"] or -9))
    guard_helps = "YES" if (next(r for r in rows if r["model"] == "M3_dir_guard")["expectancy_after_cost_pct"] or -9) > (m0["expectancy_after_cost_pct"] or -9) else "NO"
    lv = next(r for r in rows if r["model"] == "M5_live_valid")
    comp = {"build": now_iso(), "march_base_rate_pct": base_rate(m_traded), "may_base_rate_pct": base_rate(may_traded),
            "march_traded": len(m_traded), "may_traded": len(may_traded),
            "m0_may": m0, "okx_march_ref": OKX_MARCH_REF, "transfer_status": transfer, "best_model": best["model"],
            "direction_guard_helps": guard_helps, "live_valid_trades": lv["trades"], "live_valid_no_trade_days": lv["no_trade_days"],
            "flags": {"OKX_MAY_MARCH_FILTER_RETEST_DONE": "YES",
                      "OKX_MARCH_FILTERS_TRANSFER_TO_OKX_MAY": transfer,
                      "OKX_NORMALIZED_RULES_WORK_ON_MAY": "YES" if (next(r for r in rows if r["model"] == "M1_norm_pctile")["pf_after_cost"] or 0) >= 1.3 else "PARTIAL",
                      "OKX_DIRECTION_GUARD_HELPS": guard_helps,
                      "OKX_LIVE_VALID_SELECTOR_WORKS": "YES" if (lv["trades"] >= 3 and (lv["expectancy_after_cost_pct"] or -9) > 0) else "PARTIAL" if lv["trades"] > 0 else "STANDS_ASIDE",
                      "OKX_STRONG_MOVE_LABELS_DONE": "YES"}}
    (OUT / "OKX_MARCH_VS_OKX_MAY_FILTER_TRANSFER.json").write_text(json.dumps(comp, indent=2, default=str), encoding="utf-8")
    (OUT / "OKX_MARCH_VS_OKX_MAY_FILTER_TRANSFER.md").write_text(
        f"# A6. OKX March vs OKX May — filter transfer\n\n**Build:** {now_iso()}\n\n"
        f"- base 2% rate: March {comp['march_base_rate_pct']}% (n={len(m_traded)}) vs May {comp['may_base_rate_pct']}% (n={len(may_traded)})\n"
        f"- M0 absolute March rule on May: {m0['trades']} tr, {m0['winrate_pct']}%, exp {m0['expectancy_after_cost_pct']}, PF {m0['pf_after_cost']}\n"
        f"- **TRANSFER = {transfer}** · best model = {best['model']} · direction guard helps = {guard_helps}\n"
        f"- live-valid M5: {lv['trades']} trades, {lv['no_trade_days']} no-trade days\n\n"
        "## Answers\n"
        f"1. March filters transfer to May: **{transfer}**.\n"
        f"2. If not full: see base-rate {comp['may_base_rate_pct']}% vs {comp['march_base_rate_pct']}% (regime) + model table (filter).\n"
        f"3. Absolute vs normalized: M0 {m0['winrate_pct']}%/PF{m0['pf_after_cost']} vs M1 {next(r for r in rows if r['model']=='M1_norm_pctile')['winrate_pct']}%/PF{next(r for r in rows if r['model']=='M1_norm_pctile')['pf_after_cost']}.\n"
        f"4. Direction guard: **{guard_helps}**.\n"
        f"5. Live-valid first-eligible: {lv['trades']} trades ({'trades' if lv['trades']>0 else 'stands aside'}).\n"
        f"6. Strong 2.5-3% zones: see A5 class counts.\n", encoding="utf-8")

    print("\n=== OKX MAY MARCH-FILTER RETEST ===")
    for r in rows:
        print(f"  {r['model']:<22s} tr={r['trades']:>2} {r['wins']}/{r['losses']}/{r['timeouts']} wr={r['winrate_pct']}% "
              f"exp={r['expectancy_after_cost_pct']} PF={r['pf_after_cost']} ret={r['total_return_after_cost_pct']} "
              f"no-trade={r['no_trade_days']} fake={r['fake_accumulation']}")
    print(f"base rate: March {comp['march_base_rate_pct']}% vs May {comp['may_base_rate_pct']}%")
    print(f"TRANSFER={transfer} best={best['model']} guard_helps={guard_helps}")
    print("strong-move classes:", dict(cls_counts))
    print("flags:", comp["flags"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
