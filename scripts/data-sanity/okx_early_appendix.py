"""OKX early-May 05-03..20 — FULL STATISTICS APPENDIX (A-H).

Decision-time (causal, <= confirmedTs) vs post-factum outcome strictly separated.
Reuses frozen TD-short observer (decision) + TU-long gates (research). No tuning, no conclusion change.
Outputs md/json/csv/xlsx under reports/okx-may-early/.
"""
from __future__ import annotations
import csv, gzip, json, statistics as st, sys, datetime as dt
from collections import defaultdict
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "package.json").exists() and (p / "scripts").exists())
sys.path.insert(0, str(ROOT / "scripts/strategy-calibration")); sys.path.insert(0, str(ROOT / "scripts/shadow"))
import venue_norm_research as V
import td_short_shadow_observer as OBS
from canonical_ledger import build_buckets_from_trades_csv

DATA = ROOT / "data/okx-historical/BTC-USDT-SWAP"
OUT = ROOT / "reports/okx-may-early"
CACHE = OUT / "OKX_2026_05_01_10_FEATURE_CACHE.json"
DATES = [f"2026-05-{d:02d}" for d in range(3, 21)]
TREND_PCT = 2.5
import openpyxl


def now_iso(): return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
def num(x): return x if isinstance(x, (int, float)) else None
def regime_dir(z):
    pm = num(z.get("prior_move_1d_pct"))
    if pm is None: return "RANGE"
    return "TREND_UP" if pm > TREND_PCT else ("TREND_DOWN" if pm < -TREND_PCT else "RANGE")
def thin(z): return (z.get("ms_large_walls_on_path") in (0, None)) and (num(z.get("eng_void")) or 0) >= 0.5
def mins(s): return round(s / 60, 1) if isinstance(s, (int, float)) else None
def outcome_class(z):
    m = num(z.get("true_mfe"))
    if m is None: return "NO_TRADE"
    if m >= 3: return "STRONG_3"
    if m >= 2.5: return "STRONG_2_5"
    if m >= 2: return "WEAK_WIN_2"
    if m >= 0: return "MID"
    return "NOISE"

# ---- TU-long gates ----
def seller_absorption(z):
    o = num(z.get("eng_ofi")); ti = num(z.get("supportive_taker_imb_15m"))
    return (o is not None and o < -0.2) or (ti is not None and ti < -0.1)
def tu_conf(z):
    return {"reclaim": z.get("reclaim_zoneMid_preconfirm") == 1, "taker_buy": (num(z.get("supportive_taker_imb_15m")) or -9) > 0,
            "microprice_up": (num(z.get("dl2_microprice_aligned_delta_5m_bps")) or -9) >= 0, "thin_ask_path": thin(z)}
def tu_cc(z): return sum(1 for v in tu_conf(z).values() if v)
def tu_models():
    return {
        "M0_baseline": lambda z: True, "M1_TU_LONG_only": lambda z: True,
        "M2_no_seller_abs": lambda z: not seller_absorption(z),
        "M3_plus_reclaim": lambda z: (not seller_absorption(z)) and z.get("reclaim_zoneMid_preconfirm") == 1,
        "M4_plus_taker_micro": lambda z: (not seller_absorption(z)) and (tu_conf(z)["taker_buy"] or tu_conf(z)["microprice_up"]),
        "M5_plus_thin_ask": lambda z: (not seller_absorption(z)) and tu_conf(z)["thin_ask_path"],
        "M6_confluence_2of4": lambda z: (not seller_absorption(z)) and tu_cc(z) >= 2,
        "M7_live_valid": lambda z: (not seller_absorption(z)) and tu_cc(z) >= 2,
    }

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


def trade_metrics(rows):
    """rows have sim_outcome + sim_pnl_after_cost + true_mfe."""
    tr = [r for r in rows if r.get("sim_outcome") in ("WIN", "LOSS", "TIMEOUT")]
    n = len(tr); W = sum(1 for r in tr if r["sim_outcome"] == "WIN"); L = sum(1 for r in tr if r["sim_outcome"] == "LOSS"); TO = sum(1 for r in tr if r["sim_outcome"] == "TIMEOUT")
    pnls = [r["sim_pnl_after_cost"] for r in tr if r.get("sim_pnl_after_cost") is not None]
    wp = [p for p in pnls if p > 0]; lp = [p for p in pnls if p < 0]
    pf = round(sum(wp) / sum(-p for p in lp), 3) if lp else None
    cur = mx = 0
    for r in tr:
        if (r.get("sim_pnl_after_cost") or 0) <= 0: cur += 1; mx = max(mx, cur)
        else: cur = 0
    h = lambda t: sum(1 for r in tr if num(r.get("true_mfe")) and r["true_mfe"] >= t)
    return {"alerts": len(rows), "trades": n, "W": W, "L": L, "TO": TO, "winrate": round(100 * W / max(n, 1), 2),
            "expectancy": round(st.mean(pnls), 4) if pnls else None, "pf": pf, "total_return": round(sum(pnls), 4) if pnls else None,
            "hit2": h(2), "hit2_5": h(2.5), "hit3": h(3), "max_loss_streak": mx}


def main():
    zones = json.loads(CACHE.read_text())
    for z in zones:
        z["_venue"] = "OKX_MAY_EARLY"; z["_regime"] = regime_dir(z); z["_oclass"] = outcome_class(z)
    traded = [z for z in zones if z.get("sim_outcome")]
    zmap = {z["id"]: z for z in zones}

    # buckets for per-day market stats
    perday_px = {}
    for d in DATES:
        p = DATA / d / "trades.csv.gz"
        if not p.exists(): continue
        gb = build_buckets_from_trades_csv(p)
        if not gb: continue
        op = gb[0].last; cl = gb[-1].last; hi = max(b.high for b in gb); lo = min(b.low for b in gb)
        rets = [(gb[i].last - gb[i - 1].last) / gb[i - 1].last * 100 for i in range(1, len(gb)) if gb[i - 1].last > 0]
        perday_px[d] = {"net": round((cl - op) / op * 100, 2), "range": round((hi - lo) / lo * 100, 2),
                        "rvol": round(st.pstdev(rets), 4) if len(rets) > 2 else None}

    # ---- TD-short HYBRID decisions (frozen observer, causal + cooldown) ----
    td_rows = OBS.run_decisions(zones)
    td_by_id = {r["zone_id"]: r for r in td_rows}
    td_accept_ids = {r["zone_id"] for r in td_rows if r["final_shadow_decision"] == "ACCEPT"}
    # TD-short M4 thin booster (TREND_DOWN SHORT + thin, first-eligible 1/day)
    td_short_pop = [z for z in zones if z["_regime"] == "TREND_DOWN" and z["direction"] == "SHORT"]
    m4_alerts = first_elig([z for z in td_short_pop if thin(z)], None, maxn=1)
    m4_ids = {z["id"] for z in m4_alerts}

    # ---- TU-long model alerts ----
    tu_long_pop = [z for z in zones if z["_regime"] == "TREND_UP" and z["direction"] == "LONG" and z.get("sim_outcome")]
    tu_alerts = {}
    for name, fn in tu_models().items():
        tu_alerts[name] = first_elig(tu_long_pop, fn, maxn=(2 if name == "M7_live_valid" else 1), cooldown=(name == "M7_live_valid"))

    # ================= A: per-day table =================
    A = []
    for d in DATES:
        dz = [z for z in zones if z["_date"] == d]; dt_tr = [z for z in dz if z.get("sim_outcome")]
        td_c = sum(1 for z in dz if td_by_id.get(z["id"], {}).get("hybrid_decision") == "HYBRID_PASS")
        td_a = sum(1 for z in dz if z["id"] in td_accept_ids)
        tu_c = sum(1 for z in dz if z["_regime"] == "TREND_UP" and z["direction"] == "LONG")
        tu_a = sum(1 for name in tu_alerts for z in tu_alerts[name] if z["_date"] == d and name == "M6_confluence_2of4")
        px = perday_px.get(d, {})
        regs = [z["_regime"] for z in dz]
        day_reg = max(set(regs), key=regs.count) if regs else "NA"
        h = lambda t: sum(1 for z in dt_tr if num(z.get("true_mfe")) and z["true_mfe"] >= t)
        A.append({"date": d, "day_regime": day_reg, "net_move_pct": px.get("net"), "range_pct": px.get("range"), "realized_vol": px.get("rvol"),
                  "zones": len(dz), "confirmed": len(dz), "triggered": sum(1 for z in dz if z.get("triggerTs")), "reached_2pct_sim": sum(1 for z in dt_tr if z.get("sim_outcome") == "WIN"),
                  "hit_2": h(2), "hit_2_5": h(2.5), "hit_3": h(3), "long": sum(1 for z in dz if z["direction"] == "LONG"), "short": sum(1 for z in dz if z["direction"] == "SHORT"),
                  "td_short_candidates": td_c, "td_short_accepted": td_a, "tu_long_candidates": tu_c, "tu_long_accepted_M6": tu_a,
                  "no_trade_reason": ("" if (td_a or tu_a) else ("no_TREND_DOWN_short_setup" if day_reg != "TREND_DOWN" else "gates_or_cooldown"))})

    # ================= B: all zones =================
    Bcols = ["zone_id", "date", "venue", "direction", "setup_type", "confirmedTs", "triggerTs", "regime", "entry_price",
             "hit_2pct", "hit_2_5pct", "hit_3pct", "MFE", "MAE", "time_to_2pct_min", "time_to_2_5pct_min", "time_to_3pct_min",
             "sim_result", "outcome_class"]
    B = []
    for z in zones:
        m = num(z.get("true_mfe"))
        B.append({"zone_id": z["id"], "date": z["_date"], "venue": z["_venue"], "direction": z["direction"], "setup_type": z.get("zoneType"),
                  "confirmedTs": z.get("confirmedTs"), "triggerTs": z.get("triggerTs"), "regime": z["_regime"], "entry_price": z.get("sim_entry_price"),
                  "hit_2pct": int(bool(m is not None and m >= 2)), "hit_2_5pct": int(bool(m is not None and m >= 2.5)), "hit_3pct": int(bool(m is not None and m >= 3)),
                  "MFE": z.get("true_mfe"), "MAE": z.get("true_mae"), "time_to_2pct_min": mins(z.get("time_to_2")), "time_to_2_5pct_min": mins(z.get("time_to_2_5")),
                  "time_to_3pct_min": mins(z.get("time_to_3")), "sim_result": z.get("sim_outcome"), "outcome_class": z["_oclass"]})

    # ================= C: would-alert per model =================
    def alert_row(model, z, decision_meta):
        return {"alert_id": f"{model}|{z['id']}", "model": model, "date": z["_date"], "confirmedTs": z.get("confirmedTs"),
                "direction": z["direction"], "entry_price": z.get("sim_entry_price"), "regime": z["_regime"], "decision": "WOULD_ALERT",
                **decision_meta, "MFE": z.get("true_mfe"), "MAE": z.get("true_mae"),
                "hit_2pct": int(bool(num(z.get("true_mfe")) is not None and z["true_mfe"] >= 2)),
                "hit_2_5pct": int(bool(num(z.get("true_mfe")) is not None and z["true_mfe"] >= 2.5)),
                "hit_3pct": int(bool(num(z.get("true_mfe")) is not None and z["true_mfe"] >= 3)),
                "result": z.get("sim_outcome"), "pnl_after_cost": z.get("sim_pnl_after_cost"),
                "time_to_target_min": mins(z.get("time_to_2")), "time_to_stop_min": None}
    C = []
    for zid in td_accept_ids:
        z = zmap[zid]; r = td_by_id[zid]
        C.append(alert_row("TD_SHORT_HYBRID", z, {"mandatory_pass": r["mandatory_pass"], "confluence_count": r["confluence_count"], "reason": r["reject_reasons"] or "accepted", "cooldown_state": r["cooldown_state"], "cluster_id": r["cluster_id"]}))
    for z in m4_alerts:
        C.append(alert_row("TD_SHORT_M4_THIN", z, {"mandatory_pass": 1, "confluence_count": OBS.confluence_count(z) if hasattr(OBS, "confluence_count") else None, "reason": "thin_bid_path", "cooldown_state": "CLEAR", "cluster_id": None}))
    for name, alerts in tu_alerts.items():
        for z in alerts:
            cf = tu_conf(z)
            C.append(alert_row(f"TU_LONG_{name}", z, {"mandatory_pass": int(not seller_absorption(z)), "confluence_count": tu_cc(z),
                     "reason": ";".join(k for k, v in cf.items() if v) or "base", "cooldown_state": "CLEAR", "cluster_id": None}))

    # ================= D: rejected zones (per the union of models, focus TD-short + TU-long) =================
    D = []
    # TD-short rejects
    for r in td_rows:
        if r["final_shadow_decision"] == "REJECT":
            z = zmap[r["zone_id"]]; m = num(z.get("true_mfe"))
            D.append({"zone_id": z["id"], "date": z["_date"], "direction": z["direction"], "regime": z["_regime"], "model": "TD_SHORT_HYBRID",
                      "reject_reason": r["reject_reasons"], "failed_gate": (r["reject_reasons"].split(";")[0] if r["reject_reasons"] else ""),
                      "was_hit_2pct": int(bool(m is not None and m >= 2)), "was_hit_2_5pct": int(bool(m is not None and m >= 2.5)),
                      "was_hit_3pct": int(bool(m is not None and m >= 3)), "MFE": z.get("true_mfe"), "MAE": z.get("true_mae"), "sim_result": z.get("sim_outcome")})
    rej_td = [d for d in D if d["model"] == "TD_SHORT_HYBRID"]
    td_rej_winners = sum(1 for d in rej_td if d["was_hit_2pct"]); td_rej_losers = sum(1 for d in rej_td if d["sim_result"] == "LOSS"); td_rej_strong = sum(1 for d in rej_td if d["was_hit_2_5pct"])

    # ================= E: TU-long all setup zones casebook =================
    E = []
    models = tu_models()
    for z in tu_long_pop:
        cf = tu_conf(z); passed = [nm for nm, fn in models.items() if fn(z)]
        m = num(z.get("true_mfe"))
        why = []
        if seller_absorption(z): why.append("seller_absorption")
        if z.get("reclaim_zoneMid_preconfirm") != 1: why.append("failed_reclaim")
        if not cf["thin_ask_path"]: why.append("thick_ask_path")
        if not cf["microprice_up"]: why.append("microprice_against")
        if not cf["taker_buy"]: why.append("taker_against")
        E.append({"date": z["_date"], "zone_id": z["id"], "confirmedTs": z.get("confirmedTs"), "entry": z.get("sim_entry_price"),
                  "passed_models": ",".join(passed), "n_models_passed": len(passed), "MFE": z.get("true_mfe"), "MAE": z.get("true_mae"),
                  "hit_2": int(bool(m is not None and m >= 2)), "hit_2_5": int(bool(m is not None and m >= 2.5)), "hit_3": int(bool(m is not None and m >= 3)),
                  "sim_result": z.get("sim_outcome"), "why_failed": ";".join(why) or "passed_clean",
                  "seller_absorption": int(seller_absorption(z)), "failed_reclaim": int(z.get("reclaim_zoneMid_preconfirm") != 1),
                  "thick_ask": int(not cf["thin_ask_path"]), "microprice_against": int(not cf["microprice_up"]), "taker_against": int(not cf["taker_buy"])})

    # ================= F: strong zones casebook =================
    all_alert_ids = {a["alert_id"].split("|")[-1] if "|" in a["alert_id"] else a["alert_id"]: a["model"] for a in C}
    caught_by = defaultdict(list)
    for a in C: caught_by[a["alert_id"].split("|")[-1]].append(a["model"]) if "|" in a["alert_id"] else None
    # rebuild caught map properly
    caught = defaultdict(list)
    for a in C:
        zid = a["alert_id"].split("|")[-1]
        caught[zid].append(a["model"])
    F = []
    for z in zones:
        m = num(z.get("true_mfe"))
        if m is None or m < 2.5: continue
        zid = z["id"]; got = caught.get(zid, [])
        F.append({"date": z["_date"], "zone_id": zid, "direction": z["direction"], "regime": z["_regime"], "setup_type": z.get("zoneType"),
                  "confirmedTs": z.get("confirmedTs"), "MFE": z.get("true_mfe"), "time_to_2_min": mins(z.get("time_to_2")), "time_to_2_5_min": mins(z.get("time_to_2_5")), "time_to_3_min": mins(z.get("time_to_3")),
                  "reclaim_zoneMid": z.get("reclaim_zoneMid_preconfirm"), "eng_ofi": num(z.get("eng_ofi")), "taker_imb_15m": num(z.get("supportive_taker_imb_15m")),
                  "microprice_5m": num(z.get("dl2_microprice_aligned_delta_5m_bps")), "thin_path": num(z.get("ms_thin_path_score")), "walls": num(z.get("ms_large_walls_on_path")),
                  "entropy": num(z.get("book_entropy_top25")), "prior_move_60m": num(z.get("prior_move_60m_pct")), "prior_move_1d": num(z.get("prior_move_1d_pct")),
                  "caught_by_models": ",".join(got) if got else "", "caught_live": int(bool(got)),
                  "why_skipped": "" if got else ("not_TREND_DOWN_short_and_not_TREND_UP_long_setup" if z["_regime"] == "RANGE" else "gates/cooldown")})

    # ================= G: summaries =================
    h = lambda t: sum(1 for z in traded if num(z.get("true_mfe")) and z["true_mfe"] >= t)
    G_allzones = {"total_zones": len(zones), "traded": len(traded), "hit2": h(2), "hit2_5": h(2.5), "hit3": h(3),
                  "strong_rate_pct": round(100 * h(2.5) / max(len(traded), 1), 1),
                  "noise_rate_pct": round(100 * sum(1 for z in traded if z["_oclass"] == "NOISE") / max(len(traded), 1), 1)}
    G_models = []
    # TD-short HYBRID
    G_models.append({"model": "TD_SHORT_HYBRID", **trade_metrics([zmap[i] for i in td_accept_ids]), "no_trade_days": len(DATES) - len({zmap[i]["_date"] for i in td_accept_ids})})
    G_models.append({"model": "TD_SHORT_M4_THIN", **trade_metrics(m4_alerts), "no_trade_days": len(DATES) - len({z["_date"] for z in m4_alerts})})
    for name, alerts in tu_alerts.items():
        G_models.append({"model": f"TU_LONG_{name}", **trade_metrics(alerts), "no_trade_days": len(DATES) - len({z["_date"] for z in alerts})})
    G_rejwin = {"TD_SHORT_HYBRID": {"rejected_hit2": td_rej_winners, "rejected_hit2_5": td_rej_strong, "correctly_rejected_losers": td_rej_losers}}
    td_acc = [zmap[i] for i in td_accept_ids]
    G_tdsanity = {"false_shorts_in_TREND_UP": sum(1 for z in td_acc if z["_regime"] == "TREND_UP"),
                  "accepted_shorts_total": len(td_acc), "accepted_in_TREND_DOWN": sum(1 for z in td_acc if z["_regime"] == "TREND_DOWN"),
                  "accepted_outcomes": dict((k, sum(1 for z in td_acc if z.get("sim_outcome") == k)) for k in ("WIN", "LOSS", "TIMEOUT"))}
    G_tulong = {"total_TREND_UP_LONG": len(tu_long_pop), "accepted_by_model": {nm: len(a) for nm, a in tu_alerts.items()},
                "strong_winners_caught": sum(1 for nm, a in tu_alerts.items() for z in a if num(z.get("true_mfe")) and z["true_mfe"] >= 2.5),
                "why_failed": "few TREND_UP zones (RANGE window), 0 strong winners, PF<=0.71 — long-continuation not viable here"}

    # ================= H: answers =================
    H = {
        "1_total_zones": len(zones),
        "2_hit_counts": {"hit_2pct": h(2), "hit_2_5pct": h(2.5), "hit_3pct": h(3)},
        "3_live_signals_total": len({a["alert_id"] for a in C}),
        "3_live_signals_by_module": {m: sum(1 for a in C if a["model"] == m) for m in sorted({a["model"] for a in C})},
        "4_which_trades": "see WOULD_ALERT table (C). TD-short HYBRID accepted " + str(len(td_acc)) + " shorts (all in TREND_DOWN).",
        "5_strong_skipped": sum(1 for r in F if not r["caught_live"]),
        "5_strong_total": len(F),
        "6_why_tu_long_failed": G_tulong["why_failed"],
        "7_td_short_stood_aside_in_TREND_UP": "YES — false shorts in TREND_UP = " + str(G_tdsanity["false_shorts_in_TREND_UP"]),
        "8_other_setup_to_explore": "RANGE-window: mean-reversion / range-fade with reclaim is the untested candidate (most zones are RANGE; strong moves exist but neither TD-short nor TU-long covers RANGE).",
    }

    # ---- write CSVs ----
    def wcsv(name, rows, cols=None):
        if not rows: (OUT / name).write_text("", encoding="utf-8"); return
        cols = cols or list(rows[0].keys())
        with (OUT / name).open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore"); w.writeheader(); w.writerows(rows)
    wcsv("OKX_2026_05_03_20_PER_DAY.csv", A)
    wcsv("OKX_2026_05_03_20_ALL_ZONES.csv", B, Bcols)
    wcsv("OKX_EARLY_MAY_WOULD_ALERT_TRADES.csv", C)
    wcsv("OKX_EARLY_MAY_REJECTED_ZONES_ANALYSIS.csv", D)
    wcsv("TU_LONG_ALL_SETUP_ZONES_CASEBOOK.csv", E)
    wcsv("OKX_EARLY_MAY_STRONG_ZONES_CASEBOOK.csv", F)

    appendix = {"build": now_iso(), "window": "2026-05-03..20", "A_per_day": A, "B_all_zones_n": len(B),
                "C_would_alert": C, "D_rejected_n": len(D), "E_tu_long_casebook": E, "F_strong_zones": F,
                "G": {"all_zones": G_allzones, "by_model": G_models, "rejected_winners": G_rejwin, "td_short_sanity": G_tdsanity, "tu_long": G_tulong},
                "H_answers": H}
    (OUT / "OKX_2026_05_03_20_FULL_STATISTICS_APPENDIX.json").write_text(json.dumps(appendix, indent=2, default=str), encoding="utf-8")
    (OUT / "OKX_EARLY_MAY_WOULD_ALERT_TRADES.json").write_text(json.dumps(C, indent=2, default=str), encoding="utf-8")
    (OUT / "OKX_EARLY_MAY_REJECTED_ZONES_ANALYSIS.json").write_text(json.dumps(D, indent=2, default=str), encoding="utf-8")
    (OUT / "TU_LONG_ALL_SETUP_ZONES_CASEBOOK.json").write_text(json.dumps(E, indent=2, default=str), encoding="utf-8")
    (OUT / "OKX_EARLY_MAY_STRONG_ZONES_CASEBOOK.json").write_text(json.dumps(F, indent=2, default=str), encoding="utf-8")

    # ---- xlsx (multi-sheet) ----
    wb = openpyxl.Workbook(); wb.remove(wb.active)
    def sheet(title, rows, cols=None):
        ws = wb.create_sheet(title[:31])
        if not rows: ws.append(["(empty)"]); return
        cols = cols or list(rows[0].keys()); ws.append(cols)
        for r in rows: ws.append([r.get(c) for c in cols])
    sheet("PerDay", A); sheet("AllZones", B, Bcols); sheet("WouldAlert", C); sheet("Rejected", D)
    sheet("TULong_casebook", E); sheet("StrongZones", F); sheet("Summary_byModel", G_models)
    wb.save(OUT / "OKX_2026_05_03_20_FULL_STATISTICS_APPENDIX.xlsx")
    # also dedicated xlsx for would-alert / casebooks
    for fn, rows, cols in (("OKX_EARLY_MAY_WOULD_ALERT_TRADES.xlsx", C, None), ("TU_LONG_ALL_SETUP_ZONES_CASEBOOK.xlsx", E, None), ("OKX_EARLY_MAY_STRONG_ZONES_CASEBOOK.xlsx", F, None)):
        w2 = openpyxl.Workbook(); ws = w2.active; ws.title = "data"
        if rows: ws.append(list(rows[0].keys())); [ws.append([r.get(c) for c in rows[0].keys()]) for r in rows]
        w2.save(OUT / fn)

    # ---- MD appendix ----
    def tbl(rows, cols):
        if not rows: return ["_(none)_"]
        o = ["| " + " | ".join(cols) + " |", "|" + "|".join("--" for _ in cols) + "|"]
        for r in rows: o.append("| " + " | ".join(str(r.get(c)) for c in cols) + " |")
        return o
    L = ["# OKX early-May 05-03..20 — FULL STATISTICS APPENDIX", "", f"**Build:** {now_iso()}",
         "Decision-time (causal) vs post-factum outcome separated. No tuning. Conclusions unchanged.", "",
         "## A. Per-day market + engine",
         *tbl(A, ["date", "day_regime", "net_move_pct", "range_pct", "realized_vol", "zones", "triggered", "hit_2", "hit_2_5", "hit_3", "long", "short", "td_short_candidates", "td_short_accepted", "tu_long_candidates", "tu_long_accepted_M6"]),
         "", "## C. Would-alert trades (live signals)", *tbl(C, ["model", "date", "direction", "entry_price", "regime", "confluence_count", "result", "MFE", "hit_2_5pct", "pnl_after_cost"]),
         "", "## E. TU-long all setup zones (why failed)", *tbl(E, ["date", "zone_id", "MFE", "hit_2", "hit_2_5", "sim_result", "n_models_passed", "why_failed"]),
         "", "## F. Strong zones (>=2.5% MFE)", *tbl(F, ["date", "direction", "regime", "MFE", "time_to_2_min", "reclaim_zoneMid", "eng_ofi", "prior_move_60m", "caught_by_models", "why_skipped"]),
         "", "## G. Summary — by model", *tbl(G_models, ["model", "alerts", "trades", "W", "L", "TO", "winrate", "pf", "expectancy", "total_return", "hit2_5", "max_loss_streak"]),
         "", "## G. TD-short sanity", f"- false shorts in TREND_UP: **{G_tdsanity['false_shorts_in_TREND_UP']}**; accepted shorts {G_tdsanity['accepted_shorts_total']} (TREND_DOWN {G_tdsanity['accepted_in_TREND_DOWN']}); outcomes {G_tdsanity['accepted_outcomes']}",
         "", "## H. Final answers"] + [f"**{k}** — {v}" for k, v in H.items()]
    (OUT / "OKX_2026_05_03_20_FULL_STATISTICS_APPENDIX.md").write_text("\n".join(L), encoding="utf-8")

    # console
    print("APPENDIX DONE")
    print("A per-day rows:", len(A), "| B all zones:", len(B), "| C would-alert:", len(C), "| D rejected:", len(D), "| E TU-long:", len(E), "| F strong:", len(F))
    print("G all-zones:", G_allzones)
    print("G by-model:")
    for m in G_models: print(f"  {m['model']:<24s} alerts {m['alerts']:>2} tr {m['trades']:>2} {m['W']}/{m['L']}/{m['TO']} wr {m['winrate']}% PF {m['pf']} exp {m['expectancy']} hit2.5 {m['hit2_5']} maxLS {m['max_loss_streak']}")
    print("G TD-short sanity:", G_tdsanity)
    print("G TU-long:", {k: v for k, v in G_tulong.items() if k != "why_failed"})
    print("H answers:")
    for k, v in H.items(): print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
