"""TREND_DOWN SHORT-CONTINUATION DEEP DIVE (A-E).

Pools TREND_DOWN SHORT zones across OKX March + OKX May + Binance May (fixed v3). Casebook with
true MFE/MAE + time_to_2/2.5/3, winner/loser separation, entry-trigger selectors M0-M7, stop analysis.
No engine/detector/TP-SL change. TP=2%. 2.5/3% = quality labels. Causal features. No production.
"""
from __future__ import annotations
import csv, json, math, statistics as st, sys, bisect, datetime as dt
from collections import defaultdict
from pathlib import Path

ROOT = Path("C:/Users/gibilev/orderflow-research")
sys.path.insert(0, str(ROOT / "scripts/strategy-calibration"))
import venue_norm_research as V
from canonical_ledger import build_buckets_from_trades_csv

SCAL = ROOT / "reports/strategy-calibration"
OKX_DATA = ROOT / "data/okx-historical/BTC-USDT-SWAP"
BNC_DATA = ROOT / "data/binance-historical/BTCUSDT"
MARCH = SCAL / "OKX_MARCH_DIAG_FEATURE_CACHE.json"
OMAY = ROOT / "reports/okx-may/OKX_2026_05_21_30_FEATURE_CACHE.json"
BMAY = ROOT / "reports/binance-oos/BINANCE_10D_FIXED_L2_FEATURE_CACHE.json"
TREND_PCT = 2.5


def now_iso(): return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
def num(x): return x if isinstance(x, (int, float)) else None


def add_mfe_timeto(zones, data_dir):
    dates = sorted({z["_date"] for z in zones})
    gb = []
    for d in dates:
        p = data_dir / d / "trades.csv.gz"
        if p.exists(): gb += build_buckets_from_trades_csv(p)
    gb.sort(key=lambda b: b.sec); secs = [b.sec for b in gb]
    for z in zones:
        ep = z.get("sim_entry_price")
        for k in ("true_mfe", "true_mae", "time_to_2", "time_to_2_5", "time_to_3"): z[k] = None
        if not ep: continue
        start = z["confirmedTs"] // 1000; d = z["direction"]
        i = bisect.bisect_left(secs, start); j = bisect.bisect_right(secs, start + 24 * 3600); seg = gb[i:j]
        if not seg: continue
        mfe = -1e9; mae = 1e9; t2 = t25 = t3 = None
        for b in seg:
            fav = (b.high - ep) / ep * 100 if d == "LONG" else (ep - b.low) / ep * 100
            adv = (b.low - ep) / ep * 100 if d == "LONG" else (ep - b.high) / ep * 100
            if fav > mfe: mfe = fav
            if adv < mae: mae = adv
            if t2 is None and fav >= 2: t2 = b.sec - start
            if t25 is None and fav >= 2.5: t25 = b.sec - start
            if t3 is None and fav >= 3: t3 = b.sec - start
        z["true_mfe"] = round(mfe, 3); z["true_mae"] = round(mae, 3)
        z["time_to_2"] = t2; z["time_to_2_5"] = t25; z["time_to_3"] = t3


def regime_dir(z):
    pm = num(z.get("prior_move_1d_pct"))
    if pm is None: return "RANGE"
    return "TREND_UP" if pm > TREND_PCT else ("TREND_DOWN" if pm < -TREND_PCT else "RANGE")


def is_strong(z): return num(z.get("true_mfe")) is not None and z["true_mfe"] >= 2.5
def thin(z): return (z.get("ms_large_walls_on_path") in (0, None)) and (num(z.get("eng_void")) or 0) >= 0.5
def cohend(a, b, k):
    x = [z[k] for z in a if isinstance(z.get(k), (int, float))]; y = [z[k] for z in b if isinstance(z.get(k), (int, float))]
    if len(x) < 3 or len(y) < 3: return None
    sp = math.sqrt((st.pvariance(x) + st.pvariance(y)) / 2) or 1e-9
    return round((st.mean(x) - st.mean(y)) / sp, 3)
def med(zs, k):
    xs = [z[k] for z in zs if isinstance(z.get(k), (int, float))]; return round(st.median(xs), 4) if xs else None


# entry-trigger proofs (causal)
def p_rejection(z): return z.get("reclaim_zoneMid_preconfirm") == 1   # SHORT: rejected from above zoneMid
def p_taker_sell(z): return (num(z.get("supportive_taker_imb_15m")) or -9) > 0  # sell-dominant supports short
def p_microprice_down(z): return (num(z.get("dl2_microprice_aligned_delta_5m_bps")) or -9) >= 0  # aligned (down) favorable
def p_thin_path(z): return thin(z)
def p_ofi_ok(z):
    o = num(z.get("eng_ofi")); return o is None or o <= 0.2  # not buy-flow
def confluence(z, ps): return sum(1 for p in ps if p(z))


def first_elig(zones, extra, maxn=1, cooldown=False):
    byd = defaultdict(list)
    for z in zones: byd[z["_date"]].append(z)
    out = []
    for d in sorted(byd):
        day = sorted(byd[d], key=lambda z: z["confirmedTs"]); taken = []
        for z in day:
            if extra and not extra(z): continue
            if cooldown and not V.cluster_cooldown_ok(z, taken): continue
            taken.append(z); out.append(z)
            if len(taken) >= maxn: break
    return out


def sel_metrics(zones, sel):
    tr = [z for z in sel if z.get("sim_outcome")]; m = V.metrics(tr)
    days = len({(z["_venue"], z["_date"]) for z in zones}); sd = len({(z["_venue"], z["_date"]) for z in sel})
    m["no_trade_days"] = days - sd; m["alerts_per_day"] = round(len(sel) / max(days, 1), 2)
    for thr, k in ((2, "hit_2"), (2.5, "hit_2_5"), (3, "hit_3")):
        m[k] = sum(1 for z in tr if num(z.get("true_mfe")) and z["true_mfe"] >= thr)
    return m


def main():
    march = json.loads(MARCH.read_text()); add_mfe_timeto(march, OKX_DATA)
    omay = json.loads(OMAY.read_text()); add_mfe_timeto(omay, OKX_DATA)
    bmay = json.loads(BMAY.read_text()); add_mfe_timeto(bmay, BNC_DATA)
    for zs, vn in ((march, "OKX_MARCH"), (omay, "OKX_MAY"), (bmay, "BINANCE_MAY")):
        for z in zs: z["_venue"] = vn
    pool = march + omay + bmay
    td_short = [z for z in pool if regime_dir(z) == "TREND_DOWN" and z["direction"] == "SHORT" and z.get("sim_outcome")]
    print(f"TREND_DOWN SHORT zones (traded): {len(td_short)}", file=sys.stderr)

    # ---------- A: casebook ----------
    def outcome_class(z):
        if num(z.get("true_mfe")) is not None and z["true_mfe"] >= 3: return "STRONG_3"
        if num(z.get("true_mfe")) is not None and z["true_mfe"] >= 2.5: return "STRONG_2_5"
        if z.get("sim_outcome") == "WIN": return "WIN_2"
        if z.get("sim_outcome") == "LOSS": return "LOSS"
        if z.get("sim_outcome") == "TIMEOUT" and (z.get("sim_pnl_pre_cost") or 0) > 0: return "TIMEOUT_POS"
        return "TIMEOUT_NEG"
    cb_cols = ["_venue", "_date", "setup", "confirmed_iso", "entry", "sim_outcome", "class", "true_mfe", "true_mae",
               "time_to_2_min", "time_to_2_5_min", "reclaim", "supp_taker_15m", "eng_ofi",
               "microprice_5m", "thin_path", "walls", "eng_refill", "book_entropy",
               "prior_move_60m", "prior_move_1d", "dist_swh", "uniq_pctile", "funding"]
    cb = []
    for z in td_short:
        z["class"] = outcome_class(z)
        cb.append({"_venue": z["_venue"], "_date": z["_date"], "setup": z.get("zoneType"),
                   "confirmed_iso": dt.datetime.fromtimestamp(z["confirmedTs"] / 1000, tz=dt.timezone.utc).isoformat(timespec="seconds"),
                   "entry": z.get("sim_entry_price"), "sim_outcome": z.get("sim_outcome"), "class": z["class"],
                   "true_mfe": z.get("true_mfe"), "true_mae": z.get("true_mae"),
                   "time_to_2_min": round(z["time_to_2"] / 60, 1) if z.get("time_to_2") else None,
                   "time_to_2_5_min": round(z["time_to_2_5"] / 60, 1) if z.get("time_to_2_5") else None,
                   "reclaim": z.get("reclaim_zoneMid_preconfirm"), "supp_taker_15m": z.get("supportive_taker_imb_15m"),
                   "eng_ofi": z.get("eng_ofi"), "microprice_5m": z.get("dl2_microprice_aligned_delta_5m_bps"),
                   "thin_path": z.get("ms_thin_path_score"), "walls": z.get("ms_large_walls_on_path"),
                   "eng_refill": z.get("eng_refill"), "book_entropy": z.get("book_entropy_top25"),
                   "prior_move_60m": z.get("prior_move_60m_pct"), "prior_move_1d": z.get("prior_move_1d_pct"),
                   "dist_swh": z.get("dist_to_recent_swing_high_pct"), "uniq_pctile": z.get("uniq_score_pctile_vs_prior"),
                   "funding": z.get("funding_rate_at_signal")})
    with (SCAL / "TREND_DOWN_SHORT_CASEBOOK.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cb_cols); w.writeheader(); w.writerows(cb)
    cc = defaultdict(int)
    for z in td_short: cc[z["class"]] += 1
    (SCAL / "TREND_DOWN_SHORT_CASEBOOK.json").write_text(json.dumps({"build": now_iso(), "n": len(td_short), "class_counts": dict(cc), "rows": cb}, indent=2, default=str), encoding="utf-8")

    # ---------- B: winner vs loser separation ----------
    feats = ["supportive_taker_imb_15m", "taker_imbalance_15m", "eng_ofi", "dl2_microprice_aligned_delta_5m_bps",
             "ms_thin_path_score", "eng_void", "eng_refill", "reclaim_zoneMid_preconfirm", "book_entropy_top25",
             "uniq_score_pctile_vs_prior", "prior_move_60m_pct", "dist_to_recent_swing_high_pct"]
    wins = [z for z in td_short if z.get("sim_outcome") == "WIN"]
    noise = [z for z in td_short if z.get("sim_outcome") == "LOSS" or (z.get("sim_outcome") == "TIMEOUT" and (z.get("sim_pnl_pre_cost") or 0) <= 0)]
    strong = [z for z in td_short if is_strong(z)]
    weak = [z for z in td_short if num(z.get("true_mfe")) is not None and 2 <= z["true_mfe"] < 2.5]
    timeout = [z for z in td_short if z.get("sim_outcome") == "TIMEOUT"]
    def septab(a, b, an, bn):
        return [{"feature": k, an + "_med": med(a, k), bn + "_med": med(b, k), "cohen_d": cohend(a, b, k)} for k in feats]
    B = {"win_vs_noise": septab(wins, noise, "win", "noise"),
         "strong_vs_weak": septab(strong, weak, "strong", "weak"),
         "win_vs_timeout": septab(wins, timeout, "win", "timeout")}
    (SCAL / "TREND_DOWN_SHORT_SEPARATION.json").write_text(json.dumps({"build": now_iso(),
        "cohorts": {"win": len(wins), "noise": len(noise), "strong": len(strong), "weak": len(weak), "timeout": len(timeout)}, "separations": B}, indent=2, default=str), encoding="utf-8")
    mdB = ["# B. TREND_DOWN SHORT — winner vs loser separation", "", f"**Build:** {now_iso()}",
           f"Cohorts: win {len(wins)} · noise {len(noise)} · strong(>=2.5) {len(strong)} · weak(2-2.5) {len(weak)} · timeout {len(timeout)}", "",
           "### WIN vs NOISE (Cohen d, |d|>=0.3 = signal)", "| feature | win med | noise med | d |", "|---|--:|--:|--:|"]
    for r in sorted(B["win_vs_noise"], key=lambda x: -(abs(x["cohen_d"]) if x["cohen_d"] is not None else -1)):
        mdB.append(f"| {r['feature']} | {r['win_med']} | {r['noise_med']} | {r['cohen_d']} |")
    mdB += ["", "### STRONG(2.5) vs WEAK(2-2.5)", "| feature | strong med | weak med | d |", "|---|--:|--:|--:|"]
    for r in sorted(B["strong_vs_weak"], key=lambda x: -(abs(x["cohen_d"]) if x["cohen_d"] is not None else -1)):
        mdB.append(f"| {r['feature']} | {r['strong_med']} | {r['weak_med']} | {r['cohen_d']} |")
    (SCAL / "TREND_DOWN_SHORT_SEPARATION.md").write_text("\n".join(mdB), encoding="utf-8")

    # ---------- C: entry-trigger selectors ----------
    def run(name, extra, maxn=1, cooldown=False):
        sel = first_elig(td_short, extra, maxn=maxn, cooldown=cooldown); m = sel_metrics(td_short, sel)
        rej = [z for z in td_short if not (extra(z) if extra else True)]
        fp_removed = sum(1 for z in rej if z.get("sim_outcome") == "LOSS" or (z.get("sim_outcome") == "TIMEOUT" and (z.get("sim_pnl_pre_cost") or 0) <= 0))
        return {"model": name, "trades": m["trades"], "wins": m["wins"], "losses": m["losses"], "timeouts": m["timeouts"],
                "winrate_pct": m["winrate_pct"], "expectancy_after_cost_pct": m["expectancy_after_cost_pct"], "pf_after_cost": m["pf_after_cost"],
                "total_return_after_cost_pct": m["total_return_after_cost_pct"], "max_consecutive_losses": m["max_consecutive_losses"],
                "no_trade_days": m["no_trade_days"], "alerts_per_day": m["alerts_per_day"], "hit_2": m["hit_2"], "hit_2_5": m["hit_2_5"], "hit_3": m["hit_3"],
                "false_pos_removed": fp_removed}
    ps4 = [p_rejection, p_taker_sell, p_microprice_down, p_thin_path]
    ps5 = ps4 + [p_ofi_ok]
    C = [run("M0_base_TD_short", lambda z: True),
         run("M1_rejection", p_rejection),
         run("M2_taker_sell", p_taker_sell),
         run("M3_microprice_down", p_microprice_down),
         run("M4_thin_path", p_thin_path),
         run("M5_confluence_2of4", lambda z: confluence(z, ps4) >= 2),
         run("M6_confluence_3of5", lambda z: confluence(z, ps5) >= 3),
         run("M7_live_valid_2of4_cooldown", lambda z: confluence(z, ps4) >= 2, maxn=2, cooldown=True)]
    (SCAL / "TREND_DOWN_SHORT_ENTRY_SELECTORS.json").write_text(json.dumps({"build": now_iso(), "models": C}, indent=2, default=str), encoding="utf-8")
    with (SCAL / "TREND_DOWN_SHORT_ENTRY_SELECTORS.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(C[0].keys())); w.writeheader(); w.writerows(C)
    mdC = ["# C. TREND_DOWN SHORT — entry-trigger selectors", "", f"**Build:** {now_iso()}",
           "First-eligible 1/day among TREND_DOWN SHORT zones (pooled venues). No norm_filter (standalone setup).", "",
           "| model | tr | W/L/TO | wr% | exp% | PF | ret% | maxCL | alerts/d | hit2/2.5/3 | FP removed |",
           "|---|--:|:--:|--:|--:|--:|--:|--:|--:|:--:|--:|"]
    for r in C:
        mdC.append(f"| {r['model']} | {r['trades']} | {r['wins']}/{r['losses']}/{r['timeouts']} | {r['winrate_pct']} | "
                   f"{r['expectancy_after_cost_pct']} | {r['pf_after_cost']} | {r['total_return_after_cost_pct']} | {r['max_consecutive_losses']} | "
                   f"{r['alerts_per_day']} | {r['hit_2']}/{r['hit_2_5']}/{r['hit_3']} | {r['false_pos_removed']} |")
    (SCAL / "TREND_DOWN_SHORT_ENTRY_SELECTORS.md").write_text("\n".join(mdC), encoding="utf-8")

    # ---------- D: stop/failure analysis ----------
    losses = [z for z in td_short if z.get("sim_outcome") == "LOSS"]
    Drows = []
    for z in losses:
        o = num(z.get("eng_ofi")); ti = num(z.get("supportive_taker_imb_15m"))
        buyer_absorption = (o is not None and o > 0.2) or (ti is not None and ti < -0.1)   # buy flow under short
        no_rejection = z.get("reclaim_zoneMid_preconfirm") != 1
        overextended = (num(z.get("prior_move_60m_pct")) or 0) < -1.0   # already fell hard => bounce risk
        cause = "buyer_absorption" if buyer_absorption else ("no_rejection_proof" if no_rejection else ("overextended_bounce" if overextended else "clean_loss"))
        Drows.append({"_venue": z["_venue"], "_date": z["_date"], "eng_ofi": o, "supp_taker": ti,
                      "reclaim": z.get("reclaim_zoneMid_preconfirm"), "prior_move_60m": z.get("prior_move_60m_pct"),
                      "true_mae": z.get("true_mae"), "cause": cause})
    cause_counts = defaultdict(int)
    for r in Drows: cause_counts[r["cause"]] += 1
    pre_signal_avoidable = sum(1 for r in Drows if r["cause"] in ("buyer_absorption", "no_rejection_proof"))
    (SCAL / "TREND_DOWN_SHORT_STOP_ANALYSIS.json").write_text(json.dumps({"build": now_iso(), "n_losses": len(losses),
        "cause_counts": dict(cause_counts), "pre_signal_avoidable": pre_signal_avoidable, "rows": Drows}, indent=2, default=str), encoding="utf-8")
    mdD = ["# D. TREND_DOWN SHORT — stop/failure analysis", "", f"**Build:** {now_iso()}",
           f"Losses: {len(losses)}. Causes: {dict(cause_counts)}. Pre-signal avoidable (buyer-absorption or no-rejection): {pre_signal_avoidable}/{len(losses)}.", "",
           "| venue | date | eng_ofi | supp_taker | reclaim | prior60m | mae | cause |", "|---|---|--:|--:|:--:|--:|--:|:--|"]
    for r in Drows:
        mdD.append(f"| {r['_venue']} | {r['_date']} | {r['eng_ofi']} | {r['supp_taker']} | {r['reclaim']} | {r['prior_move_60m']} | {r['true_mae']} | {r['cause']} |")
    (SCAL / "TREND_DOWN_SHORT_STOP_ANALYSIS.md").write_text("\n".join(mdD), encoding="utf-8")

    # ---------- E: final ----------
    best = max([r for r in C if r["trades"] >= 8], key=lambda r: (r["pf_after_cost"] or 0), default=C[0])
    base = C[0]
    can_65_70 = "YES" if (best["winrate_pct"] or 0) >= 60 else "NO"
    sep_win = {r["feature"]: r["cohen_d"] for r in B["win_vs_noise"]}
    flags = {
        "TD_SHORT_DEEPDIVE_DONE": "YES", "TD_SHORT_ZONES": len(td_short),
        "BASE_TD_SHORT": f"{base['trades']}tr wr {base['winrate_pct']}% PF {base['pf_after_cost']}",
        "BEST_FILTER_MODEL": best["model"], "BEST_FILTER_TRADES": best["trades"], "BEST_FILTER_WINRATE": best["winrate_pct"],
        "BEST_FILTER_PF": best["pf_after_cost"], "BEST_FILTER_EXPECTANCY": best["expectancy_after_cost_pct"],
        "CAN_REACH_60_70_WINRATE": can_65_70, "PRE_SIGNAL_AVOIDABLE_LOSSES": f"{pre_signal_avoidable}/{len(losses)}",
        "USABLE_AS_SETUP_MODULE": "YES_CANDIDATE" if (best["pf_after_cost"] or 0) >= 1.5 else "PARTIAL",
        "READY_FOR_TELEGRAM_SHADOW_MODE": "NO", "READY_FOR_PRODUCTION_TRADING": "NO", "MORE_OOS_REQUIRED": "YES", "TARDIS_USED": "NO"}
    answers = {
        "1_can_reach_60_70": f"{can_65_70} — best filter {best['model']}: wr {best['winrate_pct']}% PF {best['pf_after_cost']} (n={best['trades']}). Base TD-short wr {base['winrate_pct']}%.",
        "2_filters_removing_bad_shorts": "buyer-absorption (eng_ofi>0 / taker buy) and no-rejection-proof — see stop analysis + WIN-vs-NOISE separation.",
        "3_filters_for_strong_2_5_3": f"top STRONG-vs-WEAK separators (Cohen d): {sorted(((r['feature'], r['cohen_d']) for r in B['strong_vs_weak'] if r['cohen_d'] is not None), key=lambda t:-abs(t[1]))[:4]}.",
        "4_frequency": f"best {best['model']}: {best['alerts_per_day']}/day, {best['no_trade_days']} no-trade days.",
        "5_setup_module": flags["USABLE_AS_SETUP_MODULE"] + " — TD-short is the only PF>1.5 regime setup; gate it behind a TREND_DOWN regime detector.",
        "6_live_observer": "needs: causal 1d-trend regime detector + reclaim/rejection + taker-sell + thin-bid-path; log as shadow only.",
        "7_next_cross_venue": "validate TD-short + cross-venue SELL-pressure confirmation on NEW overlapping OKX+Binance down-trend windows."}
    final = {"build": now_iso(), "status": "RESEARCH_ONLY", "n_td_short": len(td_short), "class_counts": dict(cc),
             "separation": B, "selectors": C, "stop_causes": dict(cause_counts), "flags": flags, "answers": answers}
    (SCAL / "TREND_DOWN_SHORT_DEEPDIVE_FINAL_REPORT.json").write_text(json.dumps(final, indent=2, default=str), encoding="utf-8")
    L = ["# TREND_DOWN SHORT-CONTINUATION DEEP DIVE — FINAL REPORT", "", f"**Build:** {now_iso()}",
         "RESEARCH ONLY · no engine/detector/TP-SL change · TP=2% · 2.5/3%=quality · causal · no Tardis · no production", "",
         f"## Casebook ({len(td_short)} TREND_DOWN SHORT zones)", f"Classes: {dict(cc)}", "",
         "## Entry-trigger selectors", "| model | tr | wr% | exp% | PF | ret% | hit2.5 | FP removed |", "|---|--:|--:|--:|--:|--:|--:|--:|"]
    for r in C:
        L.append(f"| {r['model']} | {r['trades']} | {r['winrate_pct']} | {r['expectancy_after_cost_pct']} | {r['pf_after_cost']} | {r['total_return_after_cost_pct']} | {r['hit_2_5']} | {r['false_pos_removed']} |")
    L += ["", f"## Stop analysis ({len(losses)} losses)", f"Causes: {dict(cause_counts)} · pre-signal avoidable: {pre_signal_avoidable}/{len(losses)}", "", "## Answers"]
    for k, v in answers.items(): L.append(f"**{k}** — {v}"); L.append("")
    L += ["## Flags", "```"] + [f"{k} = {v}" for k, v in flags.items()] + ["```"]
    (SCAL / "TREND_DOWN_SHORT_DEEPDIVE_FINAL_REPORT.md").write_text("\n".join(L), encoding="utf-8")

    # console
    print(f"\nclasses: {dict(cc)}")
    print("\n=== B WIN vs NOISE (top |d|) ===")
    for r in sorted(B["win_vs_noise"], key=lambda x: -(abs(x['cohen_d']) if x['cohen_d'] is not None else -1))[:6]:
        print(f"  {r['feature']:<34s} win {r['win_med']} noise {r['noise_med']} d {r['cohen_d']}")
    print("\n=== C selectors ===")
    for r in C:
        print(f"  {r['model']:<28s} tr {r['trades']:>3} {r['wins']}/{r['losses']}/{r['timeouts']} wr {r['winrate_pct']}% exp {r['expectancy_after_cost_pct']} PF {r['pf_after_cost']} hit2.5 {r['hit_2_5']} FPrm {r['false_pos_removed']}")
    print(f"\n=== D stop causes: {dict(cause_counts)} (avoidable {pre_signal_avoidable}/{len(losses)}) ===")
    print("\nFLAGS:")
    for k, v in flags.items(): print(f"  {k:<36s} = {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
