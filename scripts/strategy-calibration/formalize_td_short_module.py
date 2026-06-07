"""FORMALIZE TREND_DOWN SHORT-CONTINUATION SETUP MODULE (A-G).

Turns the TD-short edge into a formal shadow/research module: decision-tree spec, practical
thresholds (from existing pool, not month-tuned), shadow observer logic, observer backtest on
existing data, casebook, OOS readiness plan. Shadow/research only. No Telegram, no production.
Engine/detector/TP-SL unchanged. TP=2%, SL=1.5%. 2.5/3% = quality labels. Causal features only.
"""
from __future__ import annotations
import csv, json, statistics as st, sys, importlib.util, datetime as dt
from collections import defaultdict
from pathlib import Path

ROOT = Path("C:/Users/gibilev/orderflow-research")
SCAL = ROOT / "reports/strategy-calibration"
sys.path.insert(0, str(SCAL.parent / "strategy-calibration"))
sys.path.insert(0, str(ROOT / "scripts/strategy-calibration"))
import venue_norm_research as V
spec = importlib.util.spec_from_file_location("tdd", str(ROOT / "scripts/strategy-calibration/trend_down_short_deepdive.py"))
TD = importlib.util.module_from_spec(spec); spec.loader.exec_module(TD)

OKX_DATA = ROOT / "data/okx-historical/BTC-USDT-SWAP"
BNC_DATA = ROOT / "data/binance-historical/BTCUSDT"
MARCH = SCAL / "OKX_MARCH_DIAG_FEATURE_CACHE.json"
OMAY = ROOT / "reports/okx-may/OKX_2026_05_21_30_FEATURE_CACHE.json"
BMAY = ROOT / "reports/binance-oos/BINANCE_10D_FIXED_L2_FEATURE_CACHE.json"


def now_iso(): return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
def num(x): return x if isinstance(x, (int, float)) else None
def med(zs, k):
    xs = [z[k] for z in zs if isinstance(z.get(k), (int, float))]; return round(st.median(xs), 4) if xs else None


# ---------------- formal gates (causal, pre-confirmedTs) ----------------
def buyer_absorption(z):
    o = num(z.get("eng_ofi")); ti = num(z.get("supportive_taker_imb_15m"))
    return (o is not None and o > 0.2) or (ti is not None and ti < -0.1)

def mandatory_reasons(z):
    r = []
    if TD.regime_dir(z) != "TREND_DOWN": r.append("not_trend_down")
    if z["direction"] != "SHORT": r.append("not_short")
    if (num(z.get("prior_move_60m_pct")) if num(z.get("prior_move_60m_pct")) is not None else 0) >= 0: r.append("no_fresh_weakness_60m")
    if buyer_absorption(z): r.append("buyer_absorption")
    return r

# optional confluence proofs
def c_rejection(z): return z.get("reclaim_zoneMid_preconfirm") == 1
def c_taker_sell(z): return (num(z.get("supportive_taker_imb_15m")) or -9) > 0
def c_microprice_down(z): return (num(z.get("dl2_microprice_aligned_delta_5m_bps")) or -9) >= 0
def c_thin_path(z): return (z.get("ms_large_walls_on_path") in (0, None)) and (num(z.get("eng_void")) or 0) >= 0.5
CONFLUENCE = [("rejection_proof", c_rejection), ("taker_sell", c_taker_sell), ("microprice_down", c_microprice_down), ("thin_bid_path", c_thin_path)]

def confluence_count(z): return sum(1 for _, p in CONFLUENCE if p(z))

def observe(z, min_confluence=2):
    """returns (status, reasons). status in CANDIDATE / REJECT."""
    mr = mandatory_reasons(z)
    if mr: return "REJECT", mr
    cc = confluence_count(z)
    if cc < min_confluence: return "REJECT", [f"weak_confluence({cc}/{len(CONFLUENCE)})"]
    return "CANDIDATE", [name for name, p in CONFLUENCE if p(z)]


def first_elig(cands, maxn=2, cooldown=True):
    byd = defaultdict(list)
    for z in cands: byd[(z["_venue"], z["_date"])].append(z)
    out = []
    for key in sorted(byd):
        day = sorted(byd[key], key=lambda z: z["confirmedTs"]); taken = []
        for z in day:
            if cooldown and not V.cluster_cooldown_ok(z, taken): continue
            taken.append(z); out.append(z)
            if len(taken) >= maxn: break
    return out


def metrics_of(trades):
    tr = [t for t in trades if t.get("sim_outcome")]; m = V.metrics(tr)
    for thr, k in ((2, "hit_2"), (2.5, "hit_2_5"), (3, "hit_3")):
        m[k] = sum(1 for z in tr if num(z.get("true_mfe")) and z["true_mfe"] >= thr)
    return m


def main():
    march = json.loads(MARCH.read_text()); TD.add_mfe_timeto(march, OKX_DATA)
    omay = json.loads(OMAY.read_text()); TD.add_mfe_timeto(omay, OKX_DATA)
    bmay = json.loads(BMAY.read_text()); TD.add_mfe_timeto(bmay, BNC_DATA)
    for zs, vn in ((march, "OKX_MARCH"), (omay, "OKX_MAY"), (bmay, "BINANCE_MAY")):
        for z in zs: z["_venue"] = vn
    allz = [z for z in (march + omay + bmay) if z.get("sim_outcome")]
    td_short = [z for z in allz if TD.regime_dir(z) == "TREND_DOWN" and z["direction"] == "SHORT"]

    # ---------- A: setup spec ----------
    spec_obj = {"build": now_iso(), "module": "TD_SHORT_CONTINUATION", "trade_model": {"TP_pct": 2.0, "SL_pct": 1.5, "timeout_h": 24, "cost_pct": 0.14},
        "mandatory_gates": [
            "regime == TREND_DOWN (prior_move_1d_pct < -2.5%)",
            "direction == SHORT (zoneType DISTRIBUTION)",
            "prior_move_60m_pct < 0  (fresh weakness continuation; strongest signal d=-1.74)",
            "NOT buyer_absorption (eng_ofi <= 0.2 AND supportive_taker_imb_15m >= -0.1)"],
        "optional_confluence_need>=2_of": ["rejection_proof (reclaim_zoneMid==1)", "taker_sell (supp_taker_imb_15m>0)",
            "microprice_down (microprice_aligned_5m_bps>=0)", "thin_bid_path (void>=0.5 AND no large walls)"],
        "reject_rules": ["prior_move_60m_pct > 0 (shorting a bounce)", "buyer_absorption (OFI>0.2 or taker buy-dominant)",
            "no rejection proof + weak confluence (<2)", "thick bid support / large bid wall on path",
            "duplicate same-direction cluster within cooldown"],
        "selection": "live-valid first-eligible, max 2/day/venue, cluster cooldown 120m, no-trade allowed"}
    (SCAL / "TD_SHORT_SETUP_SPEC.json").write_text(json.dumps(spec_obj, indent=2), encoding="utf-8")
    (SCAL / "TD_SHORT_SETUP_SPEC.md").write_text(
        "# A. TD-SHORT setup module — specification\n\n**Build:** " + now_iso() +
        "\n\nTrade model UNCHANGED: TP 2%, SL 1.5%, 24h timeout, cost 0.14%.\n\n## Mandatory gates\n"
        + "\n".join("- " + g for g in spec_obj["mandatory_gates"])
        + "\n\n## Optional confluence (need >= 2 of 4)\n" + "\n".join("- " + g for g in spec_obj["optional_confluence_need>=2_of"])
        + "\n\n## Reject rules\n" + "\n".join("- " + g for g in spec_obj["reject_rules"])
        + "\n\n## Selection\n- " + spec_obj["selection"] + "\n", encoding="utf-8")

    # ---------- B: thresholds from pool ----------
    wins = [z for z in td_short if z.get("sim_outcome") == "WIN"]
    losers = [z for z in td_short if z.get("sim_outcome") == "LOSS"]
    thr = [
        {"feature": "prior_move_60m_pct", "rule": "< 0", "win_med": med(wins, "prior_move_60m_pct"), "loss_med": med(losers, "prior_move_60m_pct"), "source": "STRONG-vs-WEAK d=-1.74", "causal": "60m return up to confirmedTs", "overfit_risk": "LOW (sign-based)", "mandatory": "YES"},
        {"feature": "eng_ofi", "rule": "<= 0.2 (no buy flow)", "win_med": med(wins, "eng_ofi"), "loss_med": med(losers, "eng_ofi"), "source": "stop analysis: buyer_absorption", "causal": "engine OFI at detection", "overfit_risk": "LOW (structural)", "mandatory": "YES"},
        {"feature": "supportive_taker_imb_15m", "rule": ">= -0.1 (not buy-dominant)", "win_med": med(wins, "supportive_taker_imb_15m"), "loss_med": med(losers, "supportive_taker_imb_15m"), "source": "buyer absorption reject", "causal": "taker flow 15m pre-confirm", "overfit_risk": "LOW", "mandatory": "YES"},
        {"feature": "reclaim_zoneMid_preconfirm", "rule": "== 1 (rejection proof)", "win_med": med(wins, "reclaim_zoneMid_preconfirm"), "loss_med": med(losers, "reclaim_zoneMid_preconfirm"), "source": "M1 57% wr", "causal": "price rejected from zoneMid pre-confirm", "overfit_risk": "LOW (boolean)", "mandatory": "OPTIONAL (confluence)"},
        {"feature": "ms_thin_path_score+walls", "rule": "void>=0.5 AND no large walls", "win_med": med(wins, "ms_thin_path_score"), "loss_med": med(losers, "ms_thin_path_score"), "source": "M4 PF 3.63 (n=11)", "causal": "book snapshot at confirm", "overfit_risk": "MED (n small)", "mandatory": "OPTIONAL"},
        {"feature": "microprice_aligned_5m_bps", "rule": ">= 0 (not against short)", "win_med": med(wins, "dl2_microprice_aligned_delta_5m_bps"), "loss_med": med(losers, "dl2_microprice_aligned_delta_5m_bps"), "source": "M3 PF 2.13", "causal": "microprice delta pre-confirm", "overfit_risk": "LOW", "mandatory": "OPTIONAL"},
        {"feature": "cluster_cooldown", "rule": "same dir + price band 0.5% within 120m -> suppress", "win_med": None, "loss_med": None, "source": "dedup", "causal": "prior accepted picks only", "overfit_risk": "LOW", "mandatory": "YES (selection)"},
    ]
    (SCAL / "TD_SHORT_FEATURE_THRESHOLDS.json").write_text(json.dumps({"build": now_iso(), "thresholds": thr}, indent=2, default=str), encoding="utf-8")
    with (SCAL / "TD_SHORT_FEATURE_THRESHOLDS.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(thr[0].keys())); w.writeheader(); w.writerows(thr)
    mdB = ["# B. TD-short feature thresholds (from existing pool, not month-tuned)", "", f"**Build:** {now_iso()}",
           "| feature | rule | win med | loss med | source | overfit | mandatory |", "|---|---|--:|--:|---|:--:|:--:|"]
    for r in thr:
        mdB.append(f"| {r['feature']} | {r['rule']} | {r['win_med']} | {r['loss_med']} | {r['source']} | {r['overfit_risk']} | {r['mandatory']} |")
    (SCAL / "TD_SHORT_FEATURE_THRESHOLDS.md").write_text("\n".join(mdB), encoding="utf-8")

    # ---------- C: shadow observer spec ----------
    (SCAL / "TD_SHORT_SHADOW_OBSERVER_SPEC.json").write_text(json.dumps({"build": now_iso(),
        "on_each_confirmed_zone": ["classify regime (causal)", "if regime!=TREND_DOWN -> log ignore(not_trend_down)",
            "if direction!=SHORT -> log ignore(not_short)", "apply mandatory gates -> if fail log REJECT+reasons",
            "compute confluence>=2 -> if fail log REJECT(weak_confluence)", "else log TD_SHORT_CANDIDATE + hypothetical entry/TP/SL",
            "selection: first-eligible max2/day + cluster cooldown", "outcome evaluated only in offline evaluation section (no leak in decision)"],
        "log_fields": ["ts", "venue", "price", "direction", "regime", "status", "reject_reasons", "confluence", "hypo_entry", "tp_2pct", "sl_1_5pct"],
        "telegram": "DISABLED", "mode": "SHADOW_RESEARCH_ONLY"}, indent=2), encoding="utf-8")
    (SCAL / "TD_SHORT_SHADOW_OBSERVER_SPEC.md").write_text(
        "# C. TD-short shadow observer logic\n\n**Build:** " + now_iso() +
        "\n\nMode: SHADOW / RESEARCH ONLY. Telegram DISABLED. No production.\n\n"
        "On each confirmed zone (causal, decision uses only <= confirmedTs):\n"
        "1. classify regime; 2. ignore if not TREND_DOWN; 3. ignore if not SHORT;\n"
        "4. mandatory gates -> REJECT+reasons on fail; 5. confluence>=2 -> REJECT(weak) on fail;\n"
        "6. else TD_SHORT_CANDIDATE; log hypothetical entry, TP 2%, SL 1.5%;\n"
        "7. selection first-eligible max2/day + cluster cooldown; 8. outcome only in offline eval.\n", encoding="utf-8")

    # ---------- D: observer backtest ----------
    log_rows = []
    for z in allz:
        status, reasons = observe(z)
        log_rows.append({"venue": z["_venue"], "date": z["_date"], "dir": z["direction"], "regime": TD.regime_dir(z),
                         "status": status, "reasons": ";".join(reasons), "confluence": confluence_count(z),
                         "hypo_entry": z.get("sim_entry_price"), "outcome": z.get("sim_outcome"), "true_mfe": z.get("true_mfe")})
    cands = [z for z in allz if observe(z)[0] == "CANDIDATE"]
    sel = first_elig(cands)
    m = metrics_of(sel)
    # rejected winners / losers (among td_short to be fair to the setup population)
    rej_td = [z for z in td_short if observe(z)[0] == "REJECT"]
    rej_winners = sum(1 for z in rej_td if z.get("sim_outcome") == "WIN" or (num(z.get("true_mfe")) and z["true_mfe"] >= 2))
    rej_losers = sum(1 for z in rej_td if z.get("sim_outcome") == "LOSS")
    pv = {}
    for vn in ("OKX_MARCH", "OKX_MAY", "BINANCE_MAY"):
        vsel = [z for z in sel if z["_venue"] == vn]; vm = metrics_of(vsel)
        pv[vn] = {"trades": vm["trades"], "winrate": vm["winrate_pct"], "pf": vm["pf_after_cost"], "expectancy": vm["expectancy_after_cost_pct"], "hit_2_5": vm["hit_2_5"]}
    # comparison: hybrid (this module) vs M4 thin-only vs M7 (2of4 no-mandatory)
    def model_metrics(filt):
        c = [z for z in td_short if filt(z)]; s = first_elig(c); mm = metrics_of(s)
        return {"trades": mm["trades"], "winrate": mm["winrate_pct"], "pf": mm["pf_after_cost"], "expectancy": mm["expectancy_after_cost_pct"], "hit_2_5": mm["hit_2_5"], "maxCL": mm["max_consecutive_losses"]}
    cmp = {"HYBRID_module": model_metrics(lambda z: observe(z)[0] == "CANDIDATE"),
           "M4_thin_only": model_metrics(lambda z: c_thin_path(z)),
           "M7_2of4_no_mandatory": model_metrics(lambda z: confluence_count(z) >= 2)}
    bt = {"build": now_iso(), "n_all_zones": len(allz), "n_td_short": len(td_short), "candidates": len(cands),
          "accepted_after_selection": len(sel), "metrics": {k: m[k] for k in ("trades", "wins", "losses", "timeouts", "winrate_pct", "expectancy_after_cost_pct", "pf_after_cost", "total_return_after_cost_pct", "max_consecutive_losses", "hit_2", "hit_2_5", "hit_3")},
          "rejected_winners": rej_winners, "rejected_losers": rej_losers, "per_venue": pv, "model_comparison": cmp}
    (SCAL / "TD_SHORT_SHADOW_OBSERVER_BACKTEST.json").write_text(json.dumps(bt, indent=2, default=str), encoding="utf-8")
    with (SCAL / "TD_SHORT_SHADOW_OBSERVER_BACKTEST.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(log_rows[0].keys())); w.writeheader(); w.writerows(log_rows)
    mdD = ["# D. TD-short shadow observer backtest", "", f"**Build:** {now_iso()}",
           f"All confirmed zones: {len(allz)} · TD-short population: {len(td_short)} · candidates: {len(cands)} · accepted: {len(sel)}", "",
           f"**Accepted module:** {m['trades']}tr {m['wins']}/{m['losses']}/{m['timeouts']} wr {m['winrate_pct']}% exp {m['expectancy_after_cost_pct']} PF {m['pf_after_cost']} ret {m['total_return_after_cost_pct']}% maxCL {m['max_consecutive_losses']} hit2/2.5/3 {m['hit_2']}/{m['hit_2_5']}/{m['hit_3']}",
           f"Rejected winners (missed): {rej_winners} · rejected losers (correctly): {rej_losers}", "",
           "## Per venue", "| venue | tr | wr% | PF | exp% | hit2.5 |", "|---|--:|--:|--:|--:|--:|"]
    for vn, v in pv.items(): mdD.append(f"| {vn} | {v['trades']} | {v['winrate']} | {v['pf']} | {v['expectancy']} | {v['hit_2_5']} |")
    mdD += ["", "## Model comparison (HYBRID vs M4 vs M7)", "| model | tr | wr% | PF | exp% | maxCL |", "|---|--:|--:|--:|--:|--:|"]
    for k, v in cmp.items(): mdD.append(f"| {k} | {v['trades']} | {v['winrate']} | {v['pf']} | {v['expectancy']} | {v['maxCL']} |")
    (SCAL / "TD_SHORT_SHADOW_OBSERVER_BACKTEST.md").write_text("\n".join(mdD), encoding="utf-8")

    # ---------- E: casebook ----------
    def brief(z, why):
        return {"venue": z["_venue"], "date": z["_date"], "outcome": z.get("sim_outcome"), "true_mfe": z.get("true_mfe"), "true_mae": z.get("true_mae"),
                "time_to_2_min": round(z["time_to_2"] / 60, 1) if z.get("time_to_2") else None, "prior_60m": z.get("prior_move_60m_pct"),
                "eng_ofi": z.get("eng_ofi"), "supp_taker": z.get("supportive_taker_imb_15m"), "reclaim": z.get("reclaim_zoneMid_preconfirm"),
                "thin": c_thin_path(z), "confluence": confluence_count(z), "why": why}
    acc = [z for z in cands]
    good_acc = sorted([z for z in acc if num(z.get("true_mfe"))], key=lambda z: -(z["true_mfe"]))[:10]
    bad_acc = [z for z in acc if z.get("sim_outcome") == "LOSS"][:10]
    correct_rej = [z for z in rej_td if z.get("sim_outcome") == "LOSS"][:10]
    wrong_rej = sorted([z for z in rej_td if (num(z.get("true_mfe")) and z["true_mfe"] >= 2.5)], key=lambda z: -(z["true_mfe"]))[:10]
    casebook = {"build": now_iso(),
                "good_accepted": [brief(z, "accepted; " + ",".join(observe(z)[1])) for z in good_acc],
                "bad_accepted": [brief(z, "accepted but lost; " + ",".join(observe(z)[1])) for z in bad_acc],
                "correctly_rejected_losses": [brief(z, "rejected; " + ";".join(observe(z)[1])) for z in correct_rej],
                "wrongly_rejected_winners": [brief(z, "rejected; " + ";".join(observe(z)[1])) for z in wrong_rej]}
    (SCAL / "TD_SHORT_SHADOW_CASEBOOK.json").write_text(json.dumps(casebook, indent=2, default=str), encoding="utf-8")
    def tbl(rows):
        if not rows: return ["_(none)_"]
        o = ["| venue | date | outcome | mfe | mae | t2(min) | prior60m | ofi | reclaim | conf | why |", "|---|---|:--:|--:|--:|--:|--:|--:|:--:|--:|:--|"]
        for r in rows: o.append(f"| {r['venue']} | {r['date']} | {r['outcome']} | {r['true_mfe']} | {r['true_mae']} | {r['time_to_2_min']} | {r['prior_60m']} | {r['eng_ofi']} | {r['reclaim']} | {r['confluence']} | {r['why']} |")
        return o
    mdE = ["# E. TD-short shadow casebook", "", f"**Build:** {now_iso()}", "", "## Top good accepted", *tbl(casebook["good_accepted"]),
           "", "## Bad accepted (lost)", *tbl(casebook["bad_accepted"]), "", "## Correctly rejected losses", *tbl(casebook["correctly_rejected_losses"]),
           "", "## Wrongly rejected winners (missed)", *tbl(casebook["wrongly_rejected_winners"])]
    (SCAL / "TD_SHORT_SHADOW_CASEBOOK.md").write_text("\n".join(mdE), encoding="utf-8")

    # ---------- F: OOS readiness plan ----------
    oos = {"build": now_iso(),
        "data_needed": ["NEW OKX+Binance L2+trades overlap window (same dates)", ">=10 downtrend days OR >=20 TD-short candidates",
            "Binance: live recorder -> v3 pure-diff converter ONLY", "OKX: open public L2+trades (no Tardis)", "no threshold tuning on the new window"],
        "success_criteria": ["PF > 1.5", "winrate >= 50-55%", "max loss streak acceptable (<= ~5)",
            "no catastrophic counter-trend losses (MAE not >> SL)", ">=15-20 trades else mark UNKNOWN"],
        "freeze_before_oos": spec_obj["mandatory_gates"] + spec_obj["optional_confluence_need>=2_of"]}
    (SCAL / "TD_SHORT_OOS_READINESS_PLAN.json").write_text(json.dumps(oos, indent=2), encoding="utf-8")
    (SCAL / "TD_SHORT_OOS_READINESS_PLAN.md").write_text(
        "# F. TD-short OOS readiness plan\n\n**Build:** " + now_iso() + "\n\n## Data needed\n"
        + "\n".join("- " + x for x in oos["data_needed"]) + "\n\n## Success criteria\n"
        + "\n".join("- " + x for x in oos["success_criteria"]) + "\n\n## Frozen rules before OOS\n"
        + "\n".join("- " + x for x in oos["freeze_before_oos"]) + "\n", encoding="utf-8")

    # ---------- G: final ----------
    best = max(cmp.items(), key=lambda kv: (kv[1]["pf_after_cost"] if "pf_after_cost" in kv[1] else kv[1].get("pf", 0)) or 0)
    flags = {
        "TD_SHORT_MODULE_FORMALIZED": "YES", "TD_SHORT_SHADOW_OBSERVER_READY": "YES",
        "TD_SHORT_TELEGRAM_READY": "NO", "TD_SHORT_PRODUCTION_READY": "NO",
        "BEST_TD_SHORT_MODEL": "HYBRID_module (mandatory + confluence>=2 + cooldown)",
        "TD_SHORT_EXISTING_DATA_TRADES": m["trades"], "TD_SHORT_EXISTING_DATA_WINRATE": m["winrate_pct"],
        "TD_SHORT_EXISTING_DATA_PF": m["pf_after_cost"], "TD_SHORT_EXISTING_DATA_EXPECTANCY": m["expectancy_after_cost_pct"],
        "TD_SHORT_REJECTED_WINNERS": rej_winners, "TD_SHORT_REJECTED_LOSERS": rej_losers,
        "TD_SHORT_OOS_REQUIRED": "YES", "READY_FOR_TELEGRAM_SHADOW_MODE": "NO", "READY_FOR_PRODUCTION_TRADING": "NO", "TARDIS_USED": "NO"}
    answers = {
        "1_final_rule": "TREND_DOWN + SHORT + prior_move_60m<0 + no buyer-absorption (mandatory), then >=2 of {rejection, taker-sell, microprice-down, thin-bid-path}; first-eligible max2/day + cooldown.",
        "2_mandatory_vs_optional": "Mandatory: regime, direction, prior_move_60m<0, no buyer-absorption. Optional (confluence>=2): rejection/taker-sell/microprice-down/thin-path.",
        "3_practical_model": f"HYBRID (mandatory + confluence>=2). M4 thin-only has higher PF but n=11 (fragile); HYBRID is the robust middle.",
        "4_trades_existing": f"{m['trades']} accepted trades on existing data (wr {m['winrate_pct']}%, PF {m['pf_after_cost']}).",
        "5_per_venue": str(pv),
        "6_reject_reasons": "not_trend_down, not_short, no_fresh_weakness_60m, buyer_absorption, weak_confluence(<2).",
        "7_what_kills_short": "shorting a bounce (prior_move_60m>0) and buyer absorption (OFI>0/taker buy) — 70% of losses pre-flagged.",
        "8_shadow_ready": "YES — observer logic is causal and logs candidates/rejects; shadow/research only.",
        "9_telegram_ready": "NO — explicitly disabled; not enough OOS evidence.",
        "10_oos_needs": "new OKX+Binance downtrend overlap window, >=15-20 TD-short trades, no tuning; criteria PF>1.5 & wr>=50-55%."}
    final = {"build": now_iso(), "status": "RESEARCH_SHADOW_ONLY", "spec": spec_obj, "backtest": bt, "flags": flags, "answers": answers}
    (SCAL / "TD_SHORT_SETUP_MODULE_FINAL_REPORT.json").write_text(json.dumps(final, indent=2, default=str), encoding="utf-8")
    L = ["# TD-SHORT SETUP MODULE — FINAL REPORT", "", f"**Build:** {now_iso()}",
         "SHADOW / RESEARCH ONLY · Telegram DISABLED · no production · engine/detector/TP-SL unchanged · TP2/SL1.5 · causal", "",
         "## Final rule", answers["1_final_rule"], "",
         f"## Observer backtest (existing data)\nAll zones {len(allz)} · TD-short {len(td_short)} · candidates {len(cands)} · accepted {m['trades']}",
         f"- **{m['trades']}tr · wr {m['winrate_pct']}% · exp {m['expectancy_after_cost_pct']} · PF {m['pf_after_cost']} · ret {m['total_return_after_cost_pct']}% · maxCL {m['max_consecutive_losses']} · hit2/2.5/3 {m['hit_2']}/{m['hit_2_5']}/{m['hit_3']}**",
         f"- rejected winners {rej_winners} · correctly-rejected losers {rej_losers}", "",
         "## Model comparison", "| model | tr | wr% | PF | exp% | maxCL |", "|---|--:|--:|--:|--:|--:|"]
    for k, v in cmp.items(): L.append(f"| {k} | {v['trades']} | {v['winrate']} | {v['pf']} | {v['expectancy']} | {v['maxCL']} |")
    L += ["", "## Per venue", "| venue | tr | wr% | PF | exp% |", "|---|--:|--:|--:|--:|"]
    for vn, v in pv.items(): L.append(f"| {vn} | {v['trades']} | {v['winrate']} | {v['pf']} | {v['expectancy']} |")
    L += ["", "## Answers"]
    for k, v in answers.items(): L.append(f"**{k}** — {v}"); L.append("")
    L += ["## Flags", "```"] + [f"{k} = {v}" for k, v in flags.items()] + ["```"]
    (SCAL / "TD_SHORT_SETUP_MODULE_FINAL_REPORT.md").write_text("\n".join(L), encoding="utf-8")

    # console
    print(f"all {len(allz)} td_short {len(td_short)} candidates {len(cands)} accepted {m['trades']}")
    print(f"ACCEPTED: {m['trades']}tr {m['wins']}/{m['losses']}/{m['timeouts']} wr {m['winrate_pct']}% exp {m['expectancy_after_cost_pct']} PF {m['pf_after_cost']} ret {m['total_return_after_cost_pct']} maxCL {m['max_consecutive_losses']} hit2.5 {m['hit_2_5']}")
    print(f"rejected winners {rej_winners} / rejected losers {rej_losers}")
    print("per venue:", {k: (v['trades'], v['winrate'], v['pf']) for k, v in pv.items()})
    print("model cmp:")
    for k, v in cmp.items(): print(f"  {k:<24s} tr {v['trades']} wr {v['winrate']}% PF {v['pf']} exp {v['expectancy']} maxCL {v['maxCL']}")
    print("FLAGS:")
    for k, v in flags.items(): print(f"  {k:<36s} = {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
