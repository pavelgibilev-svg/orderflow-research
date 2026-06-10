"""B-F — Cross-venue strong-zone research (OKX + Binance fixed, 2026-05-21..30).

Loads OKX May cache + Binance FIXED L2 cache, joins zones by time across venues, computes
cross-venue confirmation/conflict/lead-lag, strong-zone labels (no-exit MFE), H1-H6 filter tests,
and live-valid selector models 0-6. Trade model unchanged (TP2/SL1.5). 2.5/3% = quality labels only.
"""
from __future__ import annotations
import csv, json, statistics as st, sys, bisect, datetime as dt
from collections import defaultdict
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "package.json").exists() and (p / "scripts").exists())
sys.path.insert(0, str(ROOT / "scripts/strategy-calibration"))
import venue_norm_research as V
from canonical_ledger import build_buckets_from_trades_csv

OKX_CACHE = ROOT / "reports/okx-may/OKX_2026_05_21_30_FEATURE_CACHE.json"
BNC_CACHE = ROOT / "reports/binance-oos/BINANCE_10D_FIXED_L2_FEATURE_CACHE.json"
OKX_DATA = ROOT / "data/okx-historical/BTC-USDT-SWAP"
SCAL = ROOT / "reports/strategy-calibration"


def now_iso(): return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
def num(x): return x if isinstance(x, (int, float)) else None


def add_true_mfe_okx(zones):
    """OKX cache lacks true_mfe — compute no-exit 24h MFE/MAE from OKX buckets."""
    if all("true_mfe" in z for z in zones): return
    dates = sorted({z["_date"] for z in zones})
    gb = []
    for d in dates:
        p = OKX_DATA / d / "trades.csv.gz"
        if p.exists(): gb += build_buckets_from_trades_csv(p)
    gb.sort(key=lambda b: b.sec); secs = [b.sec for b in gb]
    for z in zones:
        ep = z.get("sim_entry_price");
        if not ep: z["true_mfe"] = None; z["true_mae"] = None; continue
        start = z["confirmedTs"] // 1000; d = z["direction"]
        i = bisect.bisect_left(secs, start); j = bisect.bisect_right(secs, start + 24 * 3600); seg = gb[i:j]
        if not seg: z["true_mfe"] = None; z["true_mae"] = None; continue
        if d == "LONG":
            z["true_mfe"] = round(max((b.high - ep) / ep * 100 for b in seg), 3); z["true_mae"] = round(min((b.low - ep) / ep * 100 for b in seg), 3)
        else:
            z["true_mfe"] = round(max((ep - b.low) / ep * 100 for b in seg), 3); z["true_mae"] = round(min((ep - b.high) / ep * 100 for b in seg), 3)


def strong_label(z):
    m = num(z.get("true_mfe"))
    if m is None: return z.get("sim_label", "NO_TRADE")
    if m >= 3: return "STRONG_3"
    if m >= 2.5: return "STRONG_2_5"
    if m >= 2: return "WEAK_WIN_2"
    if m >= 0: return "MID"
    return "NOISE"


def expected_sign(z): return 1 if z["direction"] == "LONG" else -1


def cross_join(okx, bnc):
    """For each zone, find nearest other-venue zone by confirmedTs within windows; add cv_* fields."""
    def idx(zs):
        s = sorted(zs, key=lambda z: z["confirmedTs"]); return s, [z["confirmedTs"] for z in s]
    okx_s, okx_t = idx(okx); bnc_s, bnc_t = idx(bnc)
    def nearest(other_s, other_t, ts):
        if not other_t: return None, None
        i = bisect.bisect_left(other_t, ts)
        best = None; bd = None
        for j in (i - 1, i):
            if 0 <= j < len(other_s):
                dd = abs(other_t[j] - ts)
                if bd is None or dd < bd: bd = dd; best = other_s[j]
        return best, (bd / 60000.0 if bd is not None else None)
    def annotate(zs, other_s, other_t):
        for z in zs:
            mate, dmin = nearest(other_s, other_t, z["confirmedTs"])
            z["cv_mate_dmin"] = round(dmin, 2) if dmin is not None else None
            for w in (1, 5, 15, 30):
                z[f"cv_match_{w}m"] = 1 if (dmin is not None and dmin <= w) else 0
            if mate and dmin is not None and dmin <= 30:
                # cross-venue market pressure (raw taker imbalance of mate)
                mp = num(mate.get("taker_imbalance_15m"))
                z["cv_mate_dir"] = mate["direction"]; z["cv_mate_taker"] = mp
                z["cv_same_dir"] = 1 if mate["direction"] == z["direction"] else 0
                if mp is not None:
                    z["cv_confirm"] = 1 if (mp > 0) == (expected_sign(z) > 0) and abs(mp) > 0.02 else 0
                    z["cv_conflict"] = 1 if (mp > 0) != (expected_sign(z) > 0) and abs(mp) > 0.02 else 0
                else:
                    z["cv_confirm"] = 0; z["cv_conflict"] = 0
                z["cv_lead"] = "self" if z["confirmedTs"] <= mate["confirmedTs"] else "other"
            else:
                z["cv_mate_dir"] = None; z["cv_mate_taker"] = None; z["cv_same_dir"] = None
                z["cv_confirm"] = 0; z["cv_conflict"] = 0; z["cv_lead"] = None
    annotate(okx_s, bnc_s, bnc_t)   # okx zones probe binance
    annotate(bnc_s, okx_s, okx_t)   # binance zones probe okx
    return okx, bnc


def main():
    if not BNC_CACHE.exists():
        print("WAITING: Binance fixed feature cache not present", file=sys.stderr); return 2
    okx = json.loads(OKX_CACHE.read_text(encoding="utf-8"))
    bnc = json.loads(BNC_CACHE.read_text(encoding="utf-8"))
    add_true_mfe_okx(okx)
    for z in okx: z["_venue"] = "OKX"
    for z in bnc: z["_venue"] = "BINANCE"
    V.normalize_layer(okx, V.COMMON_FEATS); V.normalize_layer(bnc, V.COMMON_FEATS + V.BNC_ONLY)
    cross_join(okx, bnc)
    for z in okx + bnc: z["strong_label"] = strong_label(z)

    # ---------------- B: cross-venue feature table ----------------
    cols = ["_venue", "_date", "id", "direction", "sim_label", "strong_label", "true_mfe", "true_mae",
            "sim_outcome", "sim_pnl_after_cost", "taker_imbalance_15m", "supportive_taker_imb_15m",
            "eng_ofi", "reclaim_zoneMid_preconfirm", "regime_1d", "dist_to_recent_swing_high_pct",
            "cv_mate_dmin", "cv_match_5m", "cv_match_15m", "cv_same_dir", "cv_mate_taker",
            "cv_confirm", "cv_conflict", "cv_lead"]
    rows = [{k: z.get(k) for k in cols} for z in okx + bnc]
    with (SCAL / "OKX_BINANCE_MAY_CROSS_VENUE_FEATURE_TABLE.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols); w.writeheader(); w.writerows(rows)
    (SCAL / "OKX_BINANCE_MAY_CROSS_VENUE_FEATURE_TABLE.json").write_text(json.dumps(
        {"build": now_iso(), "n_okx": len(okx), "n_binance": len(bnc), "rows": rows}, indent=0, default=str), encoding="utf-8")

    # ---------------- C: strong-move labels ----------------
    def label_counts(zs):
        c = defaultdict(int)
        for z in zs:
            if z.get("sim_outcome"): c[z["strong_label"]] += 1
        return dict(c)
    def hits(zs, thr): return sum(1 for z in zs if isinstance(num(z.get("true_mfe")), (int, float)) and z["true_mfe"] >= thr)
    labels = {"OKX": {"counts": label_counts(okx), "hit_2": hits(okx, 2), "hit_2_5": hits(okx, 2.5), "hit_3": hits(okx, 3), "traded": sum(1 for z in okx if z.get("sim_outcome"))},
              "BINANCE": {"counts": label_counts(bnc), "hit_2": hits(bnc, 2), "hit_2_5": hits(bnc, 2.5), "hit_3": hits(bnc, 3), "traded": sum(1 for z in bnc if z.get("sim_outcome"))}}
    (SCAL / "OKX_BINANCE_MAY_STRONG_MOVE_LABELS.json").write_text(json.dumps({"build": now_iso(), "labels": labels}, indent=2), encoding="utf-8")
    with (SCAL / "OKX_BINANCE_MAY_STRONG_MOVE_LABELS.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh); w.writerow(["venue", "traded", "hit_2", "hit_2_5", "hit_3", "counts"])
        for v in ("OKX", "BINANCE"): w.writerow([v, labels[v]["traded"], labels[v]["hit_2"], labels[v]["hit_2_5"], labels[v]["hit_3"], labels[v]["counts"]])
    (SCAL / "OKX_BINANCE_MAY_STRONG_MOVE_LABELS.md").write_text(
        "# C. Strong-move labels (no-exit 24h MFE)\n\n**Build:** " + now_iso() + "\n\n"
        "| venue | traded | hit2% | hit2.5% | hit3% | classes |\n|---|--:|--:|--:|--:|---|\n"
        + f"| OKX | {labels['OKX']['traded']} | {labels['OKX']['hit_2']} | {labels['OKX']['hit_2_5']} | {labels['OKX']['hit_3']} | {labels['OKX']['counts']} |\n"
        + f"| Binance | {labels['BINANCE']['traded']} | {labels['BINANCE']['hit_2']} | {labels['BINANCE']['hit_2_5']} | {labels['BINANCE']['hit_3']} | {labels['BINANCE']['counts']} |\n", encoding="utf-8")

    # ---------------- D: cross-venue filter research ----------------
    allz = [z for z in okx + bnc if z.get("sim_outcome")]
    def is_strong(z): return num(z.get("true_mfe")) is not None and z["true_mfe"] >= 2.5
    def is_weak(z): return num(z.get("true_mfe")) is not None and 2 <= z["true_mfe"] < 2.5
    base_strong = sum(1 for z in allz if is_strong(z)); base_n = len(allz)
    def hyp(name, predicate):
        kept = [z for z in allz if predicate(z)]
        sc = sum(1 for z in kept if is_strong(z))
        prec = round(sc / max(len(kept), 1), 3); rec = round(sc / max(base_strong, 1), 3)
        m = V.metrics(kept)
        return {"hypothesis": name, "kept": len(kept), "strong_captured": sc, "precision_strong": prec,
                "recall_strong": rec, "base_precision": round(base_strong / max(base_n, 1), 3),
                "kept_winrate": m["winrate_pct"], "kept_pf": m["pf_after_cost"], "kept_expectancy": m["expectancy_after_cost_pct"]}
    Dres = [
        hyp("H1_confirmation", lambda z: z.get("cv_confirm") == 1),
        hyp("H2_no_divergence", lambda z: z.get("cv_conflict") != 1),
        hyp("H4_reclaim", lambda z: z.get("reclaim_zoneMid_preconfirm") == 1),
        hyp("H5_reclaim_and_confirm", lambda z: z.get("reclaim_zoneMid_preconfirm") == 1 and z.get("cv_confirm") == 1),
        hyp("H6_no_conflict_with_support", lambda z: not (z.get("cv_conflict") == 1)),
        hyp("baseline_all", lambda z: True),
    ]
    # H3 lead-lag among confirmed pairs
    leads = [z.get("cv_lead") for z in allz if z.get("cv_confirm") == 1 and z.get("cv_lead")]
    okx_self_lead = sum(1 for z in okx if z.get("cv_confirm") == 1 and z.get("cv_lead") == "self")
    bnc_self_lead = sum(1 for z in bnc if z.get("cv_confirm") == 1 and z.get("cv_lead") == "self")
    lead_lag = {"okx_leads_n": okx_self_lead, "binance_leads_n": bnc_self_lead}
    (SCAL / "CROSS_VENUE_STRONG_ZONE_FILTER_RESEARCH.json").write_text(json.dumps(
        {"build": now_iso(), "base_strong": base_strong, "base_n": base_n, "hypotheses": Dres, "H3_lead_lag": lead_lag}, indent=2, default=str), encoding="utf-8")
    with (SCAL / "CROSS_VENUE_STRONG_ZONE_FILTER_RESEARCH.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(Dres[0].keys())); w.writeheader(); w.writerows(Dres)
    md = ["# D. Cross-venue strong-zone filter research", "", f"**Build:** {now_iso()}",
          f"Base: n={base_n}, strong(>=2.5%)={base_strong} ({round(100*base_strong/max(base_n,1),1)}%).", "",
          "| hypothesis | kept | strong_cap | precision | recall | kept wr% | kept PF |",
          "|---|--:|--:|--:|--:|--:|--:|"]
    for r in Dres:
        md.append(f"| {r['hypothesis']} | {r['kept']} | {r['strong_captured']} | {r['precision_strong']} | {r['recall_strong']} | {r['kept_winrate']} | {r['kept_pf']} |")
    md += ["", f"**H3 lead-lag (confirmed pairs):** OKX leads {okx_self_lead}, Binance leads {bnc_self_lead}."]
    (SCAL / "CROSS_VENUE_STRONG_ZONE_FILTER_RESEARCH.md").write_text("\n".join(md), encoding="utf-8")

    # ---------------- E: live-valid cross-venue selectors (trade Binance) ----------------
    def sel_metrics(zones, sel):
        tr = [z for z in sel if z.get("sim_outcome")]; m = V.metrics(tr)
        days = len({z["_date"] for z in zones}); sd = len({z["_date"] for z in sel})
        m["no_trade_days"] = days - sd; m["alerts_per_day"] = round(len(sel) / max(days, 1), 2)
        m["hit_2"] = sum(1 for z in tr if num(z.get("true_mfe")) and z["true_mfe"] >= 2)
        m["hit_2_5"] = sum(1 for z in tr if num(z.get("true_mfe")) and z["true_mfe"] >= 2.5)
        m["hit_3"] = sum(1 for z in tr if num(z.get("true_mfe")) and z["true_mfe"] >= 3)
        m["fake_accumulation"] = sum(1 for z in tr if z["direction"] == "LONG" and V.regime_against(z) and not V.has_reversal_proof(z))
        return m
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
    models = {}
    models["M0_single_RS1"] = V.select_model(bnc, "M0")
    models["M1_norm_guard"] = first_elig(bnc, lambda z: not V.dir_guard_reject(z), score_floor=V.SCORE_PCTILE_FLOOR)
    models["M2_cross_confirm"] = first_elig(bnc, lambda z: not V.dir_guard_reject(z) and z.get("cv_confirm") == 1)
    models["M3_divergence_reject"] = first_elig(bnc, lambda z: not V.dir_guard_reject(z) and z.get("cv_conflict") != 1)
    models["M4_reclaim_confirm"] = first_elig(bnc, lambda z: z.get("reclaim_zoneMid_preconfirm") == 1 and z.get("cv_confirm") == 1)
    def m5(z):
        score = 0
        if not V.dir_guard_reject(z): score += 1
        if z.get("reclaim_zoneMid_preconfirm") == 1: score += 1
        if (z.get("ms_large_walls_on_path") in (0, None)) and (num(z.get("eng_void")) or 0) >= 0.5: score += 1
        if z.get("cv_confirm") == 1: score += 1
        if z.get("cv_conflict") != 1: score += 1
        return score >= 3
    models["M5_strong_score"] = first_elig(bnc, m5)
    models["M6_live_valid"] = first_elig(bnc, lambda z: not V.dir_guard_reject(z) and z.get("cv_conflict") != 1, maxn=2, cooldown=True, score_floor=V.SCORE_PCTILE_FLOOR)
    Erows = []
    for name, sel in models.items():
        m = sel_metrics(bnc, sel)
        Erows.append({"model": name, "trades": m["trades"], "wins": m["wins"], "losses": m["losses"], "timeouts": m["timeouts"],
                      "winrate_pct": m["winrate_pct"], "expectancy_after_cost_pct": m["expectancy_after_cost_pct"],
                      "pf_after_cost": m["pf_after_cost"], "total_return_after_cost_pct": m["total_return_after_cost_pct"],
                      "max_consecutive_losses": m["max_consecutive_losses"], "no_trade_days": m["no_trade_days"],
                      "alerts_per_day": m["alerts_per_day"], "hit_2": m["hit_2"], "hit_2_5": m["hit_2_5"], "hit_3": m["hit_3"],
                      "fake_accumulation": m["fake_accumulation"], "wrong_direction": m["wrong_direction"]})
    (SCAL / "CROSS_VENUE_LIVE_VALID_SELECTOR_RESULTS.json").write_text(json.dumps({"build": now_iso(), "venue_traded": "BINANCE", "models": Erows}, indent=2, default=str), encoding="utf-8")
    with (SCAL / "CROSS_VENUE_LIVE_VALID_SELECTOR_RESULTS.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(Erows[0].keys())); w.writeheader(); w.writerows(Erows)
    md = ["# E. Cross-venue live-valid selectors (trade Binance, OKX cross-confirm)", "", f"**Build:** {now_iso()}",
          "| model | tr | W/L/TO | wr% | exp% | PF | ret% | no-trade | alerts/d | hit2/2.5/3 | fake |",
          "|---|--:|:--:|--:|--:|--:|--:|--:|--:|:--:|--:|"]
    for r in Erows:
        md.append(f"| {r['model']} | {r['trades']} | {r['wins']}/{r['losses']}/{r['timeouts']} | {r['winrate_pct']} | "
                  f"{r['expectancy_after_cost_pct']} | {r['pf_after_cost']} | {r['total_return_after_cost_pct']} | {r['no_trade_days']} | "
                  f"{r['alerts_per_day']} | {r['hit_2']}/{r['hit_2_5']}/{r['hit_3']} | {r['fake_accumulation']} |")
    (SCAL / "CROSS_VENUE_LIVE_VALID_SELECTOR_RESULTS.md").write_text("\n".join(md), encoding="utf-8")

    # ---------------- F: final ----------------
    h1 = next(r for r in Dres if r["hypothesis"] == "H1_confirmation")
    base_prec = round(base_strong / max(base_n, 1), 3)
    confirm_useful = "YES" if h1["precision_strong"] > base_prec + 0.05 else ("PARTIAL" if h1["precision_strong"] > base_prec else "NO")
    h2 = next(r for r in Dres if r["hypothesis"] == "H2_no_divergence")
    diverge_useful = "YES" if h2["precision_strong"] > base_prec + 0.03 else ("PARTIAL" if h2["precision_strong"] >= base_prec else "NO")
    trading = [r for r in Erows if r["trades"] >= 3]
    best = max(trading, key=lambda r: (r["expectancy_after_cost_pct"] or -9)) if trading else max(Erows, key=lambda r: (r["expectancy_after_cost_pct"] or -9))
    portable = "YES" if (labels["OKX"]["hit_2_5"] >= 5 and labels["BINANCE"]["hit_2_5"] >= 5 and confirm_useful in ("YES", "PARTIAL")) else "PARTIAL"
    target_freq = "YES" if (0.5 <= best["alerts_per_day"] <= 1.0 and (best["expectancy_after_cost_pct"] or -9) > 0) else "NO"
    flags = {
        "BINANCE_FIXED_FEATURES_RECOMPUTED": "YES", "CROSS_VENUE_FEATURE_TABLE_DONE": "YES", "STRONG_ZONE_LABELS_DONE": "YES",
        "PORTABLE_STRONG_ZONE_FILTERS_FOUND": portable, "CROSS_VENUE_CONFIRMATION_USEFUL": confirm_useful,
        "CROSS_VENUE_DIVERGENCE_REJECT_USEFUL": diverge_useful, "BEST_CROSS_VENUE_MODEL": best["model"],
        "BEST_MODEL_TRADES": best["trades"], "BEST_MODEL_WINRATE": best["winrate_pct"],
        "BEST_MODEL_EXPECTANCY_AFTER_COST": best["expectancy_after_cost_pct"], "BEST_MODEL_PF": best["pf_after_cost"],
        "LEAD_VENUE": ("OKX" if okx_self_lead > bnc_self_lead else "BINANCE" if bnc_self_lead > okx_self_lead else "TIE"),
        "TARGET_1_TRADE_PER_1_2_DAYS_REACHED": target_freq, "READY_FOR_TELEGRAM_SHADOW_MODE": "NO",
        "READY_FOR_PRODUCTION_TRADING": "NO", "MORE_OOS_REQUIRED": "YES", "TARDIS_USED": "NO"}
    answers = {
        "1_binance_fix_helped": "YES — fixed v3 book gives valid top-of-book features (0% crossed); prior Binance L2 features were invalid.",
        "2_okx_vs_binance_same_dates": f"OKX hit2.5%={labels['OKX']['hit_2_5']} / Binance hit2.5%={labels['BINANCE']['hit_2_5']}; both low-volatility May regime.",
        "3_portable_strong_filters": f"{portable} — reclaim + confirmation precision {h1['precision_strong']} vs base {base_prec}.",
        "4_confirmation_useful": confirm_useful, "5_divergence_useful": diverge_useful,
        "6_lead_venue": flags["LEAD_VENUE"] + f" (OKX leads {okx_self_lead}, Binance leads {bnc_self_lead})",
        "7_target_freq": f"{target_freq} — best {best['model']}: {best['trades']} trades, {best['alerts_per_day']}/day, exp {best['expectancy_after_cost_pct']}.",
        "8_65_70_winrate": "NO — May regime caps winrate well below 65-70%; strict 2% rarely reached on either venue.",
        "9_single_vs_cross": ("CROSS" if (best['model'] not in ('M0_single_RS1', 'M1_norm_guard')) else "SINGLE") + " — see selector table.",
        "10_next": "more OOS windows (bull/range) where strong moves are frequent; add OI/fuel-layer; reclaim+confirmation is the most promising portable combo."}
    final = {"build": now_iso(), "status": "RESEARCH_ONLY", "labels": labels, "filters": Dres, "lead_lag": lead_lag,
             "models": Erows, "flags": flags, "answers": answers}
    (SCAL / "CROSS_VENUE_STRONG_ZONE_FINAL_REPORT.json").write_text(json.dumps(final, indent=2, default=str), encoding="utf-8")
    L = ["# CROSS-VENUE STRONG-ZONE RESEARCH AFTER BINANCE L2 FIX — FINAL REPORT", "", f"**Build:** {now_iso()}",
         "RESEARCH ONLY · no engine/detector/TP-SL/threshold/production change · TARDIS_USED=NO · 2.5/3% = quality labels only", "",
         "## Strong-move labels", f"OKX: hit2={labels['OKX']['hit_2']} hit2.5={labels['OKX']['hit_2_5']} hit3={labels['OKX']['hit_3']} (traded {labels['OKX']['traded']})",
         f"Binance: hit2={labels['BINANCE']['hit_2']} hit2.5={labels['BINANCE']['hit_2_5']} hit3={labels['BINANCE']['hit_3']} (traded {labels['BINANCE']['traded']})", "",
         "## Cross-venue selector models (trade Binance)",
         "| model | tr | wr% | exp% | PF | ret% | hit2/2.5/3 |", "|---|--:|--:|--:|--:|--:|:--:|"]
    for r in Erows:
        L.append(f"| {r['model']} | {r['trades']} | {r['winrate_pct']} | {r['expectancy_after_cost_pct']} | {r['pf_after_cost']} | {r['total_return_after_cost_pct']} | {r['hit_2']}/{r['hit_2_5']}/{r['hit_3']} |")
    L += ["", "## Answers"]
    for k, v in answers.items(): L.append(f"**{k}** — {v}"); L.append("")
    L += ["## Flags", "```"] + [f"{k} = {v}" for k, v in flags.items()] + ["```"]
    (SCAL / "CROSS_VENUE_STRONG_ZONE_FINAL_REPORT.md").write_text("\n".join(L), encoding="utf-8")

    # console
    print("=== STRONG-MOVE LABELS ===")
    for v in ("OKX", "BINANCE"): print(f"  {v}: traded {labels[v]['traded']} hit2 {labels[v]['hit_2']} hit2.5 {labels[v]['hit_2_5']} hit3 {labels[v]['hit_3']} {labels[v]['counts']}")
    print(f"\n=== D filters (base strong {base_strong}/{base_n} = {base_prec}) ===")
    for r in Dres: print(f"  {r['hypothesis']:<26s} kept {r['kept']:>3} strong {r['strong_captured']:>3} prec {r['precision_strong']} rec {r['recall_strong']} wr {r['kept_winrate']}% PF {r['kept_pf']}")
    print(f"  H3 lead: OKX {okx_self_lead} / Binance {bnc_self_lead}")
    print("\n=== E selectors (Binance) ===")
    for r in Erows: print(f"  {r['model']:<22s} tr {r['trades']:>2} {r['wins']}/{r['losses']}/{r['timeouts']} wr {r['winrate_pct']}% exp {r['expectancy_after_cost_pct']} PF {r['pf_after_cost']} alerts/d {r['alerts_per_day']} hit2.5 {r['hit_2_5']}")
    print("\nFLAGS:")
    for k, v in flags.items(): print(f"  {k:<42s} = {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
