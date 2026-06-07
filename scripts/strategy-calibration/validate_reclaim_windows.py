"""VALIDATE RECLAIM + CROSS-VENUE CONFIRMATION ON NEW WINDOWS.

Data constraint (verified): OKX+Binance L2 overlap ONLY on 2026-05-21..30. So cross-venue
confirmation cannot be tested on a NEW window. We validate:
  - RECLAIM (portable single-venue component) on OKX March 2026 (new/healthier regime) + regime breakdown,
    vs OKX May (reference).
  - CROSS-VENUE confirmation only via a May temporal split (21-25 vs 26-30) — weak internal check, labeled.
No engine/detector/TP-SL/threshold change. 2.5/3% = quality labels only. TP stays 2%. No Tardis. No production.
"""
from __future__ import annotations
import csv, json, statistics as st, sys, bisect, datetime as dt
from collections import defaultdict
from pathlib import Path

ROOT = Path("C:/Users/gibilev/orderflow-research")
sys.path.insert(0, str(ROOT / "scripts/strategy-calibration"))
import venue_norm_research as V
import cross_venue_strong_zone as CV
from canonical_ledger import build_buckets_from_trades_csv

OKX_DATA = ROOT / "data/okx-historical/BTC-USDT-SWAP"
SCAL = ROOT / "reports/strategy-calibration"
MARCH_CACHE = SCAL / "OKX_MARCH_DIAG_FEATURE_CACHE.json"
OKX_MAY_CACHE = ROOT / "reports/okx-may/OKX_2026_05_21_30_FEATURE_CACHE.json"
BNC_MAY_CACHE = ROOT / "reports/binance-oos/BINANCE_10D_FIXED_L2_FEATURE_CACHE.json"


def now_iso(): return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
def num(x): return x if isinstance(x, (int, float)) else None


def add_true_mfe(zones, data_dir):
    dates = sorted({z["_date"] for z in zones})
    gb = []
    for d in dates:
        p = data_dir / d / "trades.csv.gz"
        if p.exists(): gb += build_buckets_from_trades_csv(p)
    gb.sort(key=lambda b: b.sec); secs = [b.sec for b in gb]
    for z in zones:
        ep = z.get("sim_entry_price")
        if not ep: z["true_mfe"] = None; z["true_mae"] = None; continue
        start = z["confirmedTs"] // 1000; d = z["direction"]
        i = bisect.bisect_left(secs, start); j = bisect.bisect_right(secs, start + 24 * 3600); seg = gb[i:j]
        if not seg: z["true_mfe"] = None; z["true_mae"] = None; continue
        if d == "LONG":
            z["true_mfe"] = round(max((b.high - ep) / ep * 100 for b in seg), 3); z["true_mae"] = round(min((b.low - ep) / ep * 100 for b in seg), 3)
        else:
            z["true_mfe"] = round(max((ep - b.low) / ep * 100 for b in seg), 3); z["true_mae"] = round(min((ep - b.high) / ep * 100 for b in seg), 3)
    return gb


def window_regime(gb):
    if not gb: return {"return_pct": None, "range_pct": None, "regime": "UNKNOWN"}
    op = gb[0].last; cl = gb[-1].last; hi = max(b.high for b in gb); lo = min(b.low for b in gb)
    ret = (cl - op) / op * 100; rng = (hi - lo) / lo * 100
    regime = "TREND_UP" if ret > 3 else "TREND_DOWN" if ret < -3 else "RANGE"
    if rng > 12: regime += "_HIGHVOL"
    return {"return_pct": round(ret, 2), "range_pct": round(rng, 2), "regime": regime}


def is_strong(z): return num(z.get("true_mfe")) is not None and z["true_mfe"] >= 2.5


def reclaim_test(zones):
    tr = [z for z in zones if z.get("sim_outcome")]
    base = sum(1 for z in tr if is_strong(z)); n = len(tr)
    def block(sub):
        s = sum(1 for z in sub if is_strong(z)); m = V.metrics(sub)
        return {"n": len(sub), "strong": s, "precision_strong": round(s / max(len(sub), 1), 3),
                "winrate": m["winrate_pct"], "pf": m["pf_after_cost"], "expectancy": m["expectancy_after_cost_pct"]}
    rec1 = [z for z in tr if z.get("reclaim_zoneMid_preconfirm") == 1]
    rec0 = [z for z in tr if z.get("reclaim_zoneMid_preconfirm") != 1]
    return {"base_n": n, "base_strong": base, "base_precision": round(base / max(n, 1), 3),
            "reclaim_1": block(rec1), "reclaim_0": block(rec0)}


def first_elig(zones, extra, maxn=1, cooldown=False, score_floor=None):
    byd = defaultdict(list)
    for z in zones: byd[z["_date"]].append(z)
    out = []
    for d in sorted(byd):
        day = sorted(byd[d], key=lambda z: z["confirmedTs"]); taken = []
        for z in day:
            if not V.norm_filter(z, "pctile"): continue
            if score_floor is not None and (num(z.get("explainable_score__pctile_prior")) or 0) < score_floor: continue
            if extra and not extra(z): continue
            if cooldown and not V.cluster_cooldown_ok(z, taken): continue
            taken.append(z); out.append(z)
            if len(taken) >= maxn: break
    return out


def sel_metrics(zones, sel):
    tr = [z for z in sel if z.get("sim_outcome")]; m = V.metrics(tr)
    days = len({z["_date"] for z in zones}); sd = len({z["_date"] for z in sel})
    m["no_trade_days"] = days - sd; m["alerts_per_day"] = round(len(sel) / max(days, 1), 2)
    for thr, key in ((2, "hit_2"), (2.5, "hit_2_5"), (3, "hit_3")):
        m[key] = sum(1 for z in tr if num(z.get("true_mfe")) and z["true_mfe"] >= thr)
    m["fake_accumulation"] = sum(1 for z in tr if z["direction"] == "LONG" and V.regime_against(z) and not V.has_reversal_proof(z))
    return m


def thin(z): return (z.get("ms_large_walls_on_path") in (0, None)) and (num(z.get("eng_void")) or 0) >= 0.5


def run_single_venue_models(zones, has_cv=False):
    models = {}
    models["M0_single_RS1"] = V.select_model(zones, "M0")
    models["M1_norm_guard"] = first_elig(zones, lambda z: not V.dir_guard_reject(z), score_floor=V.SCORE_PCTILE_FLOOR)
    if has_cv:
        models["M2_cross_confirm"] = first_elig(zones, lambda z: not V.dir_guard_reject(z) and z.get("cv_confirm") == 1)
        models["M3_divergence_reject"] = first_elig(zones, lambda z: not V.dir_guard_reject(z) and z.get("cv_conflict") != 1)
        models["M4_reclaim_confirm"] = first_elig(zones, lambda z: z.get("reclaim_zoneMid_preconfirm") == 1 and z.get("cv_confirm") == 1)
        models["M5_reclaim_confirm_strong"] = first_elig(zones, lambda z: (not V.dir_guard_reject(z)) and z.get("reclaim_zoneMid_preconfirm") == 1 and thin(z) and z.get("cv_confirm") == 1 and z.get("cv_conflict") != 1)
        models["M6_live_valid"] = first_elig(zones, lambda z: not V.dir_guard_reject(z) and z.get("cv_conflict") != 1, maxn=2, cooldown=True, score_floor=V.SCORE_PCTILE_FLOOR)
    else:
        models["M4_reclaim_only"] = first_elig(zones, lambda z: not V.dir_guard_reject(z) and z.get("reclaim_zoneMid_preconfirm") == 1)
        models["M5_reclaim_strong_singleVenue"] = first_elig(zones, lambda z: (not V.dir_guard_reject(z)) and z.get("reclaim_zoneMid_preconfirm") == 1 and thin(z))
    rows = []
    for name, sel in models.items():
        m = sel_metrics(zones, sel)
        rows.append({"model": name, "trades": m["trades"], "wins": m["wins"], "losses": m["losses"], "timeouts": m["timeouts"],
                     "winrate_pct": m["winrate_pct"], "expectancy_after_cost_pct": m["expectancy_after_cost_pct"],
                     "pf_after_cost": m["pf_after_cost"], "total_return_after_cost_pct": m["total_return_after_cost_pct"],
                     "no_trade_days": m["no_trade_days"], "alerts_per_day": m["alerts_per_day"],
                     "hit_2": m["hit_2"], "hit_2_5": m["hit_2_5"], "hit_3": m["hit_3"],
                     "fake_accumulation": m["fake_accumulation"], "wrong_direction": m["wrong_direction"]})
    return rows


def main():
    out = {"build": now_iso(), "status": "RESEARCH_ONLY",
           "data_constraint": "OKX+Binance L2 overlap only 2026-05-21..30; cross-venue cannot be tested on a NEW window.",
           "windows": {}}

    # ---- OKX March (NEW window, reclaim validation) ----
    march = json.loads(MARCH_CACHE.read_text(encoding="utf-8"))
    gb_m = add_true_mfe(march, OKX_DATA)
    V.normalize_layer(march, V.COMMON_FEATS)
    reg_m = window_regime(gb_m)
    rec_m = reclaim_test(march)
    mdl_m = run_single_venue_models(march, has_cv=False)
    # regime breakdown by day
    by_day = defaultdict(list)
    for z in march: by_day[z["_date"]].append(z)
    day_gb = defaultdict(list)
    for b in gb_m: day_gb[dt.datetime.utcfromtimestamp(b.sec).strftime("%Y-%m-%d")].append(b)
    regime_groups = defaultdict(list)
    for d, zs in by_day.items():
        r = window_regime(day_gb.get(d, []))["regime"]
        for z in zs: z["_day_regime"] = r; regime_groups[r.split("_HIGHVOL")[0]].append(z)
    reg_break = {}
    for r, zs in regime_groups.items():
        tr = [z for z in zs if z.get("sim_outcome")]
        rec1 = [z for z in tr if z.get("reclaim_zoneMid_preconfirm") == 1]
        base = sum(1 for z in tr if is_strong(z)); s1 = sum(1 for z in rec1 if is_strong(z))
        reg_break[r] = {"n": len(tr), "base_strong_pct": round(100 * base / max(len(tr), 1), 1),
                        "reclaim_n": len(rec1), "reclaim_strong_pct": round(100 * s1 / max(len(rec1), 1), 1),
                        "reclaim_winrate": V.metrics(rec1)["winrate_pct"], "reclaim_pf": V.metrics(rec1)["pf_after_cost"]}
    out["windows"]["OKX_MARCH_2026"] = {"regime": reg_m, "reclaim_test": rec_m, "models": mdl_m, "regime_breakdown": reg_break}

    # ---- OKX May (reference) ----
    omay = json.loads(OKX_MAY_CACHE.read_text(encoding="utf-8"))
    gb_om = add_true_mfe(omay, OKX_DATA)
    V.normalize_layer(omay, V.COMMON_FEATS)
    out["windows"]["OKX_MAY_2026"] = {"regime": window_regime(gb_om), "reclaim_test": reclaim_test(omay),
                                      "models": run_single_venue_models(omay, has_cv=False)}

    # ---- May cross-venue temporal split (weak check) ----
    bnc = json.loads(BNC_MAY_CACHE.read_text(encoding="utf-8"))
    for z in omay: z["_venue"] = "OKX"
    for z in bnc: z["_venue"] = "BINANCE"
    CV.add_true_mfe_okx(omay)
    V.normalize_layer(bnc, V.COMMON_FEATS + V.BNC_ONLY)
    CV.cross_join(omay, bnc)
    H1 = [f"2026-05-{d:02d}" for d in range(21, 26)]; H2 = [f"2026-05-{d:02d}" for d in range(26, 31)]
    split = {}
    for label, ds in (("H1_21_25", H1), ("H2_26_30", H2)):
        sub = [z for z in bnc if z["_date"] in ds]
        split[label] = {"regime": window_regime([b for b in gb_om if dt.datetime.utcfromtimestamp(b.sec).strftime('%Y-%m-%d') in ds]),
                        "models": run_single_venue_models(sub, has_cv=True)}
    out["windows"]["BINANCE_MAY_CROSS_VENUE_SPLIT"] = split

    # ---- answers + flags ----
    march_rec = rec_m["reclaim_1"]; march_rec0 = rec_m["reclaim_0"]
    reclaim_holds_march = "YES" if march_rec["precision_strong"] > rec_m["base_precision"] + 0.03 else ("PARTIAL" if march_rec["precision_strong"] >= rec_m["base_precision"] else "NO")
    may_rec = out["windows"]["OKX_MAY_2026"]["reclaim_test"]
    reclaim_holds_may = "YES" if may_rec["reclaim_1"]["precision_strong"] > may_rec["base_precision"] + 0.03 else ("PARTIAL" if may_rec["reclaim_1"]["precision_strong"] >= may_rec["base_precision"] else "NO")
    best_march = max(mdl_m, key=lambda r: (r["pf_after_cost"] or 0))
    pf15_or_wr = "YES" if ((best_march["pf_after_cost"] or 0) >= 1.5 or (best_march["winrate_pct"] or 0) >= 60) else "NO"
    flags = {
        "RECLAIM_VALIDATION_DONE": "YES", "OKX_MARCH_REGIME": reg_m["regime"], "OKX_MAY_REGIME": out["windows"]["OKX_MAY_2026"]["regime"]["regime"],
        "RECLAIM_HOLDS_OKX_MARCH": reclaim_holds_march, "RECLAIM_HOLDS_OKX_MAY": reclaim_holds_may,
        "CROSS_VENUE_VALIDATED_ON_NEW_WINDOW": "NO_DATA (only May overlaps)",
        "BEST_MARCH_MODEL": best_march["model"], "BEST_MARCH_PF": best_march["pf_after_cost"], "BEST_MARCH_WINRATE": best_march["winrate_pct"],
        "TOGETHER_PF_1_5_OR_WR_60_70": pf15_or_wr,
        "FUEL_LAYER_NEEDED": "LIKELY (OI/liquidations) to lift quality further",
        "READY_FOR_TELEGRAM_SHADOW_MODE": "NO", "READY_FOR_PRODUCTION_TRADING": "NO", "MORE_OOS_REQUIRED": "YES", "TARDIS_USED": "NO"}
    answers = {
        "1_reclaim_holds": f"OKX March ({reg_m['regime']}): reclaim precision {march_rec['precision_strong']} vs base {rec_m['base_precision']} (winrate {march_rec['winrate']}% vs {march_rec0['winrate']}% no-reclaim) -> {reclaim_holds_march}. OKX May -> {reclaim_holds_may}.",
        "2_cross_confirm_holds": "CANNOT be tested on a new window — OKX+Binance L2 overlap only 2026-05-21..30. May temporal split provided as a weak internal check only.",
        "3_together_pf15_wr": f"{pf15_or_wr} — best March model {best_march['model']}: PF {best_march['pf_after_cost']}, winrate {best_march['winrate_pct']}%.",
        "4_which_regimes": f"reclaim strong-precision by March sub-regime: {reg_break}.",
        "5_fuel_needed": "LIKELY — reclaim+confirmation improves precision but not to 60-70%; OI/liquidations fuel-layer is the next lever."}
    out["flags"] = flags; out["answers"] = answers
    (SCAL / "RECLAIM_CROSSVENUE_NEW_WINDOWS_VALIDATION.json").write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")

    L = ["# VALIDATE RECLAIM + CROSS-VENUE CONFIRMATION ON NEW WINDOWS", "", f"**Build:** {now_iso()}",
         "RESEARCH ONLY · no engine/detector/TP-SL/threshold change · TP stays 2% · 2.5/3% = quality labels · no Tardis · no production", "",
         f"**Data constraint:** OKX+Binance L2 overlap ONLY 2026-05-21..30 → cross-venue confirmation cannot be tested on a NEW window.", "",
         f"## OKX March 2026 — regime {reg_m['regime']} (ret {reg_m['return_pct']}%, range {reg_m['range_pct']}%)",
         f"Reclaim test: base strong {rec_m['base_precision']} | reclaim=1 precision {march_rec['precision_strong']} wr {march_rec['winrate']}% PF {march_rec['pf']} | reclaim=0 precision {march_rec0['precision_strong']} wr {march_rec0['winrate']}%", "",
         "| model | tr | wr% | exp% | PF | ret% | hit2/2.5/3 |", "|---|--:|--:|--:|--:|--:|:--:|"]
    for r in mdl_m:
        L.append(f"| {r['model']} | {r['trades']} | {r['winrate_pct']} | {r['expectancy_after_cost_pct']} | {r['pf_after_cost']} | {r['total_return_after_cost_pct']} | {r['hit_2']}/{r['hit_2_5']}/{r['hit_3']} |")
    L += ["", "### March regime breakdown (reclaim strong-precision)"]
    for r, v in reg_break.items():
        L.append(f"- **{r}** (n={v['n']}): base strong {v['base_strong_pct']}% → reclaim strong {v['reclaim_strong_pct']}% (wr {v['reclaim_winrate']}%, PF {v['reclaim_pf']})")
    omod = out["windows"]["OKX_MAY_2026"]["models"]
    L += ["", f"## OKX May 2026 — regime {out['windows']['OKX_MAY_2026']['regime']['regime']} (reference)",
          "| model | tr | wr% | exp% | PF | hit2/2.5/3 |", "|---|--:|--:|--:|--:|:--:|"]
    for r in omod:
        L.append(f"| {r['model']} | {r['trades']} | {r['winrate_pct']} | {r['expectancy_after_cost_pct']} | {r['pf_after_cost']} | {r['hit_2']}/{r['hit_2_5']}/{r['hit_3']} |")
    L += ["", "## Binance May cross-venue temporal split (weak check, NOT a new window)"]
    for half, dd in split.items():
        L.append(f"### {half} — regime {dd['regime']['regime']}")
        L.append("| model | tr | wr% | exp% | PF | hit2.5 |")
        L.append("|---|--:|--:|--:|--:|--:|")
        for r in dd["models"]:
            L.append(f"| {r['model']} | {r['trades']} | {r['winrate_pct']} | {r['expectancy_after_cost_pct']} | {r['pf_after_cost']} | {r['hit_2_5']} |")
    L += ["", "## Answers"]
    for k, v in answers.items(): L.append(f"**{k}** — {v}"); L.append("")
    L += ["## Flags", "```"] + [f"{k} = {v}" for k, v in flags.items()] + ["```"]
    (SCAL / "RECLAIM_CROSSVENUE_NEW_WINDOWS_VALIDATION.md").write_text("\n".join(L), encoding="utf-8")

    # console
    print(f"OKX March regime {reg_m['regime']} ret {reg_m['return_pct']}% range {reg_m['range_pct']}%")
    print(f"March reclaim: base {rec_m['base_precision']} | rec1 prec {march_rec['precision_strong']} wr {march_rec['winrate']}% PF {march_rec['pf']} | rec0 prec {march_rec0['precision_strong']} wr {march_rec0['winrate']}%")
    print("March models:")
    for r in mdl_m: print(f"  {r['model']:<28s} tr {r['trades']:>3} wr {r['winrate_pct']}% exp {r['expectancy_after_cost_pct']} PF {r['pf_after_cost']} hit2.5 {r['hit_2_5']}")
    print("March regime breakdown:")
    for r, v in reg_break.items(): print(f"  {r:<14s} n {v['n']:>3} base_strong {v['base_strong_pct']}% reclaim_strong {v['reclaim_strong_pct']}% wr {v['reclaim_winrate']}% PF {v['reclaim_pf']}")
    print("May (OKX) models:")
    for r in omod: print(f"  {r['model']:<28s} tr {r['trades']:>3} wr {r['winrate_pct']}% PF {r['pf_after_cost']}")
    print("FLAGS:")
    for k, v in flags.items(): print(f"  {k:<40s} = {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
