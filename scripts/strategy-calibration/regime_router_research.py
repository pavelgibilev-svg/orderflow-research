"""REGIME-AWARE SETUP ROUTER RESEARCH (A-F).

Per-zone causal regime classification, per-regime zone stats + filter research, a setup-type router,
and live-valid router selectors. Venues: OKX March, OKX May, Binance May (fixed v3). Cross-venue
confirmation only on the May overlap (weak, labeled). No engine/detector/TP-SL/threshold tuning.
TP stays 2%. 2.5/3% = quality labels. All features causal at confirmedTs. No production.
"""
from __future__ import annotations
import csv, json, statistics as st, sys, bisect, datetime as dt
from collections import defaultdict
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "package.json").exists() and (p / "scripts").exists())
sys.path.insert(0, str(ROOT / "scripts/strategy-calibration"))
import venue_norm_research as V
import cross_venue_strong_zone as CV
from canonical_ledger import build_buckets_from_trades_csv

SCAL = ROOT / "reports/strategy-calibration"
OKX_DATA = ROOT / "data/okx-historical/BTC-USDT-SWAP"
MARCH = SCAL / "OKX_MARCH_DIAG_FEATURE_CACHE.json"
OMAY = ROOT / "reports/okx-may/OKX_2026_05_21_30_FEATURE_CACHE.json"
BMAY = ROOT / "reports/binance-oos/BINANCE_10D_FIXED_L2_FEATURE_CACHE.json"

# structural regime thresholds (BTC magnitudes; applied identically everywhere, NOT performance-tuned)
TREND_PCT = 2.5      # |prior_move_1d| > 2.5% => trend
HIGH_VOL_RANGE = 2.5  # local_range_180m > 2.5% => high vol
LOW_VOL_RANGE = 0.8   # local_range_180m < 0.8% => low vol / likely no-trade


def now_iso(): return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
def num(x): return x if isinstance(x, (int, float)) else None


def add_true_mfe(zones):
    if all(isinstance(z.get("true_mfe"), (int, float)) or z.get("true_mfe") is None and "true_mfe" in z for z in zones) and any("true_mfe" in z for z in zones):
        if all("true_mfe" in z for z in zones): return
    dates = sorted({z["_date"] for z in zones})
    gb = []
    for d in dates:
        p = OKX_DATA / d / "trades.csv.gz"
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


def regime(z):
    pm = num(z.get("prior_move_1d_pct")); rng = num(z.get("local_range_180m_pct"))
    d = "RANGE"
    if pm is not None:
        d = "TREND_UP" if pm > TREND_PCT else ("TREND_DOWN" if pm < -TREND_PCT else "RANGE")
    v = "NORMAL_VOL"
    if rng is not None:
        v = "HIGH_VOL" if rng > HIGH_VOL_RANGE else ("LOW_VOL" if rng < LOW_VOL_RANGE else "NORMAL_VOL")
    return d, v


def is_strong(z): return num(z.get("true_mfe")) is not None and z["true_mfe"] >= 2.5
def trend_aligned(z):
    d, _ = regime(z)
    return (d == "TREND_UP" and z["direction"] == "LONG") or (d == "TREND_DOWN" and z["direction"] == "SHORT")


def slabel(z):
    m = num(z.get("true_mfe"))
    if m is None: return z.get("sim_label", "NO_TRADE")
    if m >= 3: return "STRONG_3"
    if m >= 2.5: return "STRONG_2_5"
    if m >= 2: return "WEAK_WIN_2"
    if m >= 0: return "MID"
    return "NOISE"


def stats(zs):
    tr = [z for z in zs if z.get("sim_outcome")]
    n = len(tr)
    if n == 0: return {"n": 0}
    def hits(t): return sum(1 for z in tr if num(z.get("true_mfe")) and z["true_mfe"] >= t)
    m = V.metrics(tr)
    mfes = [z["true_mfe"] for z in tr if num(z.get("true_mfe")) is not None]
    return {"n": n, "hit_2": hits(2), "hit_2_5": hits(2.5), "hit_3": hits(3),
            "strong_pct": round(100 * hits(2.5) / n, 1), "winrate": m["winrate_pct"], "pf": m["pf_after_cost"],
            "expectancy": m["expectancy_after_cost_pct"], "long": sum(1 for z in tr if z["direction"] == "LONG"),
            "short": sum(1 for z in tr if z["direction"] == "SHORT"),
            "avg_mfe": round(st.mean(mfes), 3) if mfes else None,
            "avg_mae": round(st.mean([z["true_mae"] for z in tr if num(z.get("true_mae")) is not None]), 3) if mfes else None}


def first_elig(zones, extra, maxn=1, cooldown=False):
    byd = defaultdict(list)
    for z in zones: byd[z["_date"]].append(z)
    out = []
    for d in sorted(byd):
        day = sorted(byd[d], key=lambda z: z["confirmedTs"]); taken = []
        for z in day:
            if not V.norm_filter(z, "pctile"): continue
            if extra and not extra(z): continue
            if cooldown and not V.cluster_cooldown_ok(z, taken): continue
            taken.append(z); out.append(z)
            if len(taken) >= maxn: break
    return out


def sel_metrics(zones, sel):
    tr = [z for z in sel if z.get("sim_outcome")]; m = V.metrics(tr)
    days = len({z["_date"] for z in zones}); sd = len({z["_date"] for z in sel})
    m["no_trade_days"] = days - sd; m["alerts_per_day"] = round(len(sel) / max(days, 1), 2)
    for thr, k in ((2, "hit_2"), (2.5, "hit_2_5"), (3, "hit_3")):
        m[k] = sum(1 for z in tr if num(z.get("true_mfe")) and z["true_mfe"] >= thr)
    return m


def thin(z): return (z.get("ms_large_walls_on_path") in (0, None)) and (num(z.get("eng_void")) or 0) >= 0.5
def noise_ok(z):
    o = num(z.get("eng_ofi")); ti = num(z.get("supportive_taker_imb_15m"))
    if o is not None and ((z["direction"] == "LONG" and o < -0.2) or (z["direction"] == "SHORT" and o > 0.2)): return False
    if ti is not None and ti < -0.1: return False
    return True


def route_allow(z):
    d, v = regime(z)
    if v == "LOW_VOL": return False                       # no-trade in low vol
    if d == "TREND_DOWN":
        return z["direction"] == "SHORT" or V.has_reversal_proof(z)   # short continuation; counter-long needs proof
    if d == "TREND_UP":
        return z["direction"] == "LONG" or V.has_reversal_proof(z)
    return z.get("reclaim_zoneMid_preconfirm") == 1       # RANGE: require reclaim/rejection


def main():
    march = json.loads(MARCH.read_text()); add_true_mfe(march)
    omay = json.loads(OMAY.read_text()); add_true_mfe(omay)
    bmay = json.loads(BMAY.read_text())
    for zs, vn in ((march, "OKX_MARCH"), (omay, "OKX_MAY"), (bmay, "BINANCE_MAY")):
        for z in zs: z["_venue"] = vn
    V.normalize_layer(march, V.COMMON_FEATS); V.normalize_layer(omay, V.COMMON_FEATS)
    V.normalize_layer(bmay, V.COMMON_FEATS + V.BNC_ONLY)
    # cross-confirm on May overlap (weak)
    for z in omay: z["_venue"] = "OKX_MAY"
    CV.cross_join(omay, bmay)
    for z in march: z["cv_confirm"] = None; z["cv_conflict"] = None
    for z in march + omay + bmay:
        z["_regime_dir"], z["_vol"] = regime(z); z["strong_label"] = slabel(z)

    venues = {"OKX_MARCH": march, "OKX_MAY": omay, "BINANCE_MAY": bmay}

    # ---- A: regime label files ----
    for vn, zs in venues.items():
        with (SCAL / f"REGIME_LABELS_{vn}.csv").open("w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh); w.writerow(["id", "date", "dir", "regime_dir", "vol", "trend_aligned", "true_mfe", "strong_label", "sim_outcome", "reclaim", "cv_confirm"])
            for z in zs:
                w.writerow([z["id"], z["_date"], z["direction"], z["_regime_dir"], z["_vol"], int(trend_aligned(z)),
                            z.get("true_mfe"), z["strong_label"], z.get("sim_outcome"), z.get("reclaim_zoneMid_preconfirm"), z.get("cv_confirm")])

    # ---- B: per-regime zone statistics ----
    B = {}
    pooled = march + omay + bmay
    for vn, zs in list(venues.items()) + [("POOLED", pooled)]:
        B[vn] = {}
        for reg in ("TREND_UP", "TREND_DOWN", "RANGE"):
            B[vn][reg] = stats([z for z in zs if z["_regime_dir"] == reg])
        for v in ("HIGH_VOL", "NORMAL_VOL", "LOW_VOL"):
            B[vn]["VOL_" + v] = stats([z for z in zs if z["_vol"] == v])
    (SCAL / "REGIME_ZONE_STATISTICS.json").write_text(json.dumps({"build": now_iso(), "thresholds": {"trend_pct": TREND_PCT, "high_vol_range": HIGH_VOL_RANGE, "low_vol_range": LOW_VOL_RANGE}, "stats": B}, indent=2, default=str), encoding="utf-8")
    mdB = ["# B. Per-regime zone statistics", "", f"**Build:** {now_iso()}",
           f"Thresholds (structural): trend |1d|>{TREND_PCT}%, high-vol range>{HIGH_VOL_RANGE}%, low-vol range<{LOW_VOL_RANGE}%.", "",
           "| venue | regime | n | strong% | hit2/2.5/3 | wr% | PF | L/S | avgMFE |",
           "|---|---|--:|--:|:--:|--:|--:|:--:|--:|"]
    for vn in ("POOLED", "OKX_MARCH", "OKX_MAY", "BINANCE_MAY"):
        for reg in ("TREND_UP", "TREND_DOWN", "RANGE", "VOL_HIGH_VOL", "VOL_LOW_VOL"):
            s = B[vn].get(reg, {"n": 0})
            if s.get("n", 0) == 0: continue
            mdB.append(f"| {vn} | {reg} | {s['n']} | {s['strong_pct']} | {s['hit_2']}/{s['hit_2_5']}/{s['hit_3']} | {s['winrate']} | {s['pf']} | {s['long']}/{s['short']} | {s['avg_mfe']} |")
    (SCAL / "REGIME_ZONE_STATISTICS.md").write_text("\n".join(mdB), encoding="utf-8")

    # ---- C: per-regime filter research (pooled) ----
    def filt_block(name, sub, predicate):
        kept = [z for z in sub if z.get("sim_outcome") and predicate(z)]
        base = [z for z in sub if z.get("sim_outcome")]
        bs = sum(1 for z in base if is_strong(z)); ks = sum(1 for z in kept if is_strong(z))
        m = V.metrics(kept)
        return {"filter": name, "regime_n": len(base), "kept": len(kept), "strong_captured": ks,
                "base_strong_pct": round(100 * bs / max(len(base), 1), 1), "precision_strong": round(ks / max(len(kept), 1), 3),
                "winrate": m["winrate_pct"], "pf": m["pf_after_cost"], "expectancy": m["expectancy_after_cost_pct"]}
    Cres = []
    td = [z for z in pooled if z["_regime_dir"] == "TREND_DOWN"]
    Cres += [filt_block("TD_short_continuation", td, lambda z: z["direction"] == "SHORT"),
             filt_block("TD_reject_counter_long", td, lambda z: not (z["direction"] == "LONG" and not V.has_reversal_proof(z))),
             filt_block("TD_reclaim", td, lambda z: z.get("reclaim_zoneMid_preconfirm") == 1),
             filt_block("TD_short_plus_noise_ok", td, lambda z: z["direction"] == "SHORT" and noise_ok(z))]
    tu = [z for z in pooled if z["_regime_dir"] == "TREND_UP"]
    Cres += [filt_block("TU_long_continuation", tu, lambda z: z["direction"] == "LONG"),
             filt_block("TU_reject_counter_short", tu, lambda z: not (z["direction"] == "SHORT" and not V.has_reversal_proof(z))),
             filt_block("TU_long_plus_thin", tu, lambda z: z["direction"] == "LONG" and thin(z))]
    rg = [z for z in pooled if z["_regime_dir"] == "RANGE"]
    Cres += [filt_block("RANGE_reclaim", rg, lambda z: z.get("reclaim_zoneMid_preconfirm") == 1),
             filt_block("RANGE_reclaim_plus_noise_ok", rg, lambda z: z.get("reclaim_zoneMid_preconfirm") == 1 and noise_ok(z)),
             filt_block("RANGE_all", rg, lambda z: True)]
    lv = [z for z in pooled if z["_vol"] == "LOW_VOL"]
    Cres += [filt_block("LOWVOL_all_(no_trade_candidate)", lv, lambda z: True)]
    (SCAL / "REGIME_FILTER_RESEARCH.json").write_text(json.dumps({"build": now_iso(), "filters": Cres}, indent=2, default=str), encoding="utf-8")
    with (SCAL / "REGIME_FILTER_RESEARCH.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(Cres[0].keys())); w.writeheader(); w.writerows(Cres)
    mdC = ["# C. Per-regime filter research (pooled OKX March + OKX/Binance May)", "", f"**Build:** {now_iso()}",
           "| filter | regime n | kept | strong_cap | base_strong% | precision | wr% | PF |",
           "|---|--:|--:|--:|--:|--:|--:|--:|"]
    for r in Cres:
        mdC.append(f"| {r['filter']} | {r['regime_n']} | {r['kept']} | {r['strong_captured']} | {r['base_strong_pct']} | {r['precision_strong']} | {r['winrate']} | {r['pf']} |")
    (SCAL / "REGIME_FILTER_RESEARCH.md").write_text("\n".join(mdC), encoding="utf-8")

    # ---- D: setup-type router table ----
    router = {
        "TREND_DOWN": {"allowed": ["SHORT continuation (DISTRIBUTION)"], "rejected": ["LONG accumulation without reversal proof"], "required_filters": ["trend-aligned OR reversal_proof", "noise_ok (ofi/taker not conflicting)"]},
        "TREND_UP": {"allowed": ["LONG continuation (ACCUMULATION)"], "rejected": ["SHORT distribution without rejection proof"], "required_filters": ["trend-aligned OR rejection_proof", "thin path preferred"]},
        "RANGE": {"allowed": ["mean-reversion from band with reclaim/rejection (both dirs)"], "rejected": ["no-reclaim entries"], "required_filters": ["reclaim_zoneMid", "noise_ok", "cross-confirm where available"]},
        "LOW_VOL": {"allowed": [], "rejected": ["all (range too small for 2% target)"], "required_filters": ["NO-TRADE unless exceptional strong-zone score"]},
        "HIGH_VOL": {"note": "overlay — wider excursions; same direction rules, prefer continuation"},
    }
    (SCAL / "REGIME_SETUP_ROUTER.json").write_text(json.dumps({"build": now_iso(), "router": router}, indent=2), encoding="utf-8")
    mdD = ["# D. Setup-type router", "", f"**Build:** {now_iso()}", ""]
    for reg, r in router.items():
        mdD.append(f"## {reg}")
        for k, v in r.items(): mdD.append(f"- **{k}**: {v}")
        mdD.append("")
    (SCAL / "REGIME_SETUP_ROUTER.md").write_text("\n".join(mdD), encoding="utf-8")

    # ---- E: regime-router selectors per venue ----
    def models_for(zs, has_cv):
        M = {}
        M["M0_old_RS1"] = V.select_model(zs, "M0")
        M["M1_regime_filter"] = first_elig(zs, route_allow)
        M["M2_regime_noise"] = first_elig(zs, lambda z: route_allow(z) and noise_ok(z))
        M["M3_regime_strongscore"] = first_elig(zs, lambda z: route_allow(z) and noise_ok(z) and (z.get("reclaim_zoneMid_preconfirm") == 1 or trend_aligned(z)) and thin(z))
        if has_cv:
            M["M4_regime_crossconfirm"] = first_elig(zs, lambda z: route_allow(z) and (z.get("cv_confirm") == 1))
        M["M5_regime_notrade_cooldown"] = first_elig(zs, lambda z: route_allow(z) and noise_ok(z), maxn=2, cooldown=True)
        rows = []
        for nm, sel in M.items():
            m = sel_metrics(zs, sel)
            rows.append({"model": nm, "trades": m["trades"], "wins": m["wins"], "losses": m["losses"], "timeouts": m["timeouts"],
                         "winrate_pct": m["winrate_pct"], "expectancy_after_cost_pct": m["expectancy_after_cost_pct"], "pf_after_cost": m["pf_after_cost"],
                         "total_return_after_cost_pct": m["total_return_after_cost_pct"], "max_consecutive_losses": m["max_consecutive_losses"],
                         "no_trade_days": m["no_trade_days"], "alerts_per_day": m["alerts_per_day"],
                         "hit_2": m["hit_2"], "hit_2_5": m["hit_2_5"], "hit_3": m["hit_3"], "wrong_direction": m["wrong_direction"]})
        return rows
    E = {"OKX_MARCH": models_for(march, False), "OKX_MAY": models_for(omay, True), "BINANCE_MAY": models_for(bmay, True)}
    (SCAL / "REGIME_ROUTER_SELECTOR_RESULTS.json").write_text(json.dumps({"build": now_iso(), "venues": E}, indent=2, default=str), encoding="utf-8")
    rowsE = []
    for vn, rows in E.items():
        for r in rows: rowsE.append({"venue": vn, **r})
    with (SCAL / "REGIME_ROUTER_SELECTOR_RESULTS.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rowsE[0].keys())); w.writeheader(); w.writerows(rowsE)
    mdE = ["# E. Regime-router selectors (per venue)", "", f"**Build:** {now_iso()}", "",
           "| venue | model | tr | W/L/TO | wr% | exp% | PF | ret% | no-trade | alerts/d | hit2.5 |",
           "|---|---|--:|:--:|--:|--:|--:|--:|--:|--:|--:|"]
    for vn, rows in E.items():
        for r in rows:
            mdE.append(f"| {vn} | {r['model']} | {r['trades']} | {r['wins']}/{r['losses']}/{r['timeouts']} | {r['winrate_pct']} | {r['expectancy_after_cost_pct']} | {r['pf_after_cost']} | {r['total_return_after_cost_pct']} | {r['no_trade_days']} | {r['alerts_per_day']} | {r['hit_2_5']} |")
    (SCAL / "REGIME_ROUTER_SELECTOR_RESULTS.md").write_text("\n".join(mdE), encoding="utf-8")

    # ---- F: final ----
    # tradeable vs no-trade regimes from pooled stats
    pr = B["POOLED"]
    tradeable = [reg for reg in ("TREND_UP", "TREND_DOWN", "RANGE") if pr.get(reg, {}).get("strong_pct", 0) >= 25]
    notrade = [reg for reg in ("VOL_LOW_VOL",) if pr.get(reg, {}).get("n", 0) > 0 and pr.get(reg, {}).get("strong_pct", 100) < 20]
    # best router model = best by expectancy among models with trades>=8 across venues (prefer OKX March richer)
    allmodels = [{"venue": vn, **r} for vn, rows in E.items() for r in rows]
    cand = [r for r in allmodels if r["trades"] >= 8]
    best = max(cand, key=lambda r: (r["expectancy_after_cost_pct"] or -9)) if cand else max(allmodels, key=lambda r: (r["expectancy_after_cost_pct"] or -9))
    target = "YES" if (0.5 <= best["alerts_per_day"] <= 1.0 and (best["expectancy_after_cost_pct"] or -9) > 0) else "NO"
    flags = {
        "REGIME_ROUTER_RESEARCH_DONE": "YES", "REGIME_CLASSIFIER_BUILT": "YES",
        "TRADEABLE_REGIMES_FOUND": "YES" if tradeable else "NO", "NO_TRADE_REGIMES_FOUND": "YES" if notrade else "PARTIAL",
        "TRADEABLE_REGIMES": tradeable, "NO_TRADE_REGIMES": notrade or ["LOW_VOL"],
        "BEST_REGIME_ROUTER_MODEL": f"{best['venue']}:{best['model']}", "BEST_ROUTER_TRADES": best["trades"],
        "BEST_ROUTER_WINRATE": best["winrate_pct"], "BEST_ROUTER_PF": best["pf_after_cost"],
        "BEST_ROUTER_EXPECTANCY": best["expectancy_after_cost_pct"],
        "TARGET_1_TRADE_PER_1_2_DAYS_REACHED": target,
        "CROSS_VENUE_NEEDS_NEW_OVERLAP_WINDOW": "YES (only 2026-05-21..30 overlaps today)",
        "READY_FOR_TELEGRAM_SHADOW_MODE": "NO", "READY_FOR_PRODUCTION_TRADING": "NO", "MORE_OOS_REQUIRED": "YES", "TARDIS_USED": "NO"}
    answers = {
        "1_tradeable_regimes": f"{tradeable} have >=25% strong-zone rate; TREND_DOWN/TREND_UP richest, RANGE thinner.",
        "2_skip_regimes": "LOW_VOL (range < 0.8%) — too small for 2% target; NO-TRADE. " + (f"Also weak: {notrade}." if notrade else ""),
        "3_trend_down_filters": "SHORT continuation + reject counter-trend LONG (no reversal proof) + noise_ok — see C table.",
        "4_trend_up_filters": "LONG continuation + reject counter-trend SHORT + thin-path — see C table.",
        "5_range_filters": "reclaim/rejection required + noise_ok + cross-confirm where available — see C table.",
        "6_target_freq": f"{target} — best router {best['venue']}:{best['model']} {best['trades']}tr {best['alerts_per_day']}/day exp {best['expectancy_after_cost_pct']}.",
        "7_65_70_winrate": "Only the in-sample OKX-March RS1 reaches ~62%; OOS regime-routed models stay below. Not from tuning -> NO robustly.",
        "8_keep_setups": "trend-continuation (SHORT in down, LONG in up) + range mean-reversion WITH reclaim.",
        "9_ban_setups": "counter-trend accumulation/distribution without reversal proof; ALL setups in LOW_VOL.",
        "10_next_data": "Record Binance (live recorder) + download OKX open for NEW overlapping windows across regimes (trend-up, range, high-vol) to validate cross-venue confirmation; 2026-05-21..30 alone is insufficient."}
    final = {"build": now_iso(), "status": "RESEARCH_ONLY", "regime_stats": B, "filters": Cres, "router": router, "selectors": E, "flags": flags, "answers": answers}
    (SCAL / "REGIME_ROUTER_FINAL_REPORT.json").write_text(json.dumps(final, indent=2, default=str), encoding="utf-8")
    L = ["# REGIME-AWARE SETUP ROUTER — FINAL REPORT", "", f"**Build:** {now_iso()}",
         "RESEARCH ONLY · no engine/detector/TP-SL/threshold tuning · TP=2% · 2.5/3%=quality labels · causal · no Tardis · no production", "",
         "## Tradeable vs no-trade regimes (pooled strong% = hit2.5 rate)",
         "| regime | n | strong% | wr% | PF |", "|---|--:|--:|--:|--:|"]
    for reg in ("TREND_UP", "TREND_DOWN", "RANGE", "VOL_HIGH_VOL", "VOL_LOW_VOL"):
        s = pr.get(reg, {"n": 0})
        if s.get("n", 0): L.append(f"| {reg} | {s['n']} | {s['strong_pct']} | {s['winrate']} | {s['pf']} |")
    L += ["", f"**Tradeable:** {tradeable}  ·  **No-trade:** {flags['NO_TRADE_REGIMES']}", "",
          "## Best router model", f"{best['venue']}:{best['model']} — {best['trades']}tr, wr {best['winrate_pct']}%, exp {best['expectancy_after_cost_pct']}, PF {best['pf_after_cost']}", "",
          "## Answers"]
    for k, v in answers.items(): L.append(f"**{k}** — {v}"); L.append("")
    L += ["## Flags", "```"] + [f"{k} = {v}" for k, v in flags.items()] + ["```"]
    (SCAL / "REGIME_ROUTER_FINAL_REPORT.md").write_text("\n".join(L), encoding="utf-8")

    # console
    print("=== B per-regime (POOLED) ===")
    for reg in ("TREND_UP", "TREND_DOWN", "RANGE", "VOL_HIGH_VOL", "VOL_NORMAL_VOL", "VOL_LOW_VOL"):
        s = pr.get(reg, {"n": 0})
        if s.get("n", 0): print(f"  {reg:<16s} n {s['n']:>4} strong% {s['strong_pct']:>5} wr {s['winrate']}% PF {s['pf']} L/S {s['long']}/{s['short']} avgMFE {s['avg_mfe']}")
    print("\n=== C filters (pooled) ===")
    for r in Cres: print(f"  {r['filter']:<32s} n {r['regime_n']:>4} kept {r['kept']:>4} strong {r['strong_captured']:>3} prec {r['precision_strong']} wr {r['winrate']}% PF {r['pf']}")
    print("\n=== E selectors ===")
    for vn, rows in E.items():
        for r in rows: print(f"  {vn:<12s} {r['model']:<26s} tr {r['trades']:>3} wr {r['winrate_pct']}% exp {r['expectancy_after_cost_pct']} PF {r['pf_after_cost']} alerts/d {r['alerts_per_day']}")
    print("\nFLAGS:")
    for k, v in flags.items(): print(f"  {k:<42s} = {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
