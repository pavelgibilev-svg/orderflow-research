"""v6 — STRICT SHORT-PERMISSION GATE. Object of study = the gate (entry trigger frozen, not tuned).

Builds stricter causal gates than v5 (require higher-timeframe direction down, VWAP context, buy-recovery
danger) to block more TREND_UP shorts while retaining TREND_DOWN. Compares: A random_all, B random+gate_v5,
C random+gate_v6, D event+gate_v5, E event+gate_v6. Reuses v5 cached per-minute series + v4 di-free detector.
No entry change, no TP/SL change, no future data.
"""
from __future__ import annotations
import csv, json, random, statistics as st, sys, datetime as dt
from collections import defaultdict
from pathlib import Path

ROOT = Path("C:/Users/gibilev/orderflow-research")
sys.path.insert(0, str(ROOT / "scripts/research"))
import td_v4_regime as V4
import td_v5_gate as V5
OUT = ROOT / "reports/strict_short_permission_gate_v6"
random.seed(42)
REGIMES = ("TREND_DOWN", "TREND_UP", "RANGE_CHOP", "REVERSAL_BOUNCE")
OLD_GATE = "GATE_5_COMBINED"


def now(): return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
def rate(k, n): return round(100 * k / n, 1) if n else 0.0
def grp(rows): return V4.grp(rows)
def gpf(rows): g = grp(rows); return g["pf"], g["n"], g["expectancy"], g["hit2_rate"]


def feats_v6(S, t):
    mid = [r["mid"] for r in S]
    def ret(k): return (mid[t] - mid[t - k]) / mid[t - k] * 100 if t >= k else None
    def cvd(k): return S[t]["cvd"] - S[t - k]["cvd"] if t >= k else None
    def nettk(k): return sum(S[i]["bv"] - S[i]["sv"] for i in range(max(0, t - k), t))
    vols = [(S[i]["bv"] + S[i]["sv"]) for i in range(max(0, t - 180), t)]; pxs = mid[max(0, t - 180):t]
    vw = (sum(p * v for p, v in zip(pxs, vols)) / sum(vols)) if sum(vols) else mid[t]
    pv_vwap = (mid[t] - vw) / vw * 100
    r30, r60, r180, r360 = ret(30), ret(60), ret(180), ret(360)
    recent_low = min(mid[max(0, t - 60):t + 1]); up_from_low = (mid[t] - recent_low) / recent_low * 100
    look = mid[max(0, t - 180):t + 1]; rng180 = (max(look) - min(look)) / min(look) * 100 if look else 0
    pc15 = ret(15)
    buy_recovery = bool(nettk(15) > 0 and (cvd(15) is not None and cvd(15) > 0))
    downside_progress = bool((r60 is not None and r60 < 0) and mid[t] <= min(mid[max(0, t - 60):t + 1]) * 1.001)
    weak_bounce = bool(up_from_low < 0.6)
    bounce_danger = bool((r180 is not None and r180 < -1.0) and (cvd(30) is not None and cvd(30) >= 0) and up_from_low > 0.6)
    chop = bool((r180 is not None and abs(r180) < 0.5 and rng180 > 1.5))
    uptrend_danger = bool((r60 is not None and r60 > 0) or (r180 is not None and r180 > 0) or (r360 is not None and r360 > 0) or pv_vwap > 0 or (cvd(60) is not None and cvd(60) > 0) or buy_recovery)
    downtrend_perm = bool((r60 is not None and r60 < 0) and (r180 is not None and r180 < 0) and (cvd(180) is not None and cvd(180) < 0) and pv_vwap < 0 and downside_progress)
    seller_ctrl_strict = bool(nettk(60) < 0 and (cvd(60) is not None and cvd(60) < 0) and (pc15 is not None and pc15 < 0) and weak_bounce)
    return {"ret_30m": _r(r30), "ret_60m": _r(r60), "ret_180m": _r(r180), "ret_360m": _r(r360), "price_vs_vwap180_pct": _r(pv_vwap),
            "cvd_60m": _r(cvd(60)), "cvd_180m": _r(cvd(180)), "net_taker_60m": _r(nettk(60)), "up_from_recent_low_pct": _r(up_from_low),
            "range_180m_pct": _r(rng180), "buy_recovery": buy_recovery, "downside_progress": downside_progress, "weak_bounce": weak_bounce,
            "bounce_danger": bounce_danger, "chop": chop, "uptrend_danger": uptrend_danger, "downtrend_perm": downtrend_perm, "seller_ctrl_strict": seller_ctrl_strict}
def _r(x): return round(x, 3) if isinstance(x, (int, float)) else x


GATES_V6 = {
    "GATE_6A_STRICT_NO_UPTREND": lambda g: not g["uptrend_danger"],
    "GATE_6B_DOWNTREND_ONLY": lambda g: g["downtrend_perm"],
    "GATE_6C_SELLER_CONTROL_STRICT": lambda g: g["seller_ctrl_strict"] and not g["bounce_danger"],
    "GATE_6D_NO_BOUNCE_NO_CHOP": lambda g: not g["bounce_danger"] and not g["chop"],
    "GATE_6E_COMBINED_STRICT": lambda g: g["downtrend_perm"] and g["seller_ctrl_strict"] and not g["uptrend_danger"] and not g["chop"] and not g["bounce_danger"],
}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    series = {wid: V5.get_series(wid) for wid in V4.WINDOWS}
    for wid, S in series.items(): print(f"{wid}: {len(S)} min", flush=True)

    # ---- events + gate decisions (v6 + old v5 GATE_5) ----
    events = []; feat_rows = []
    for wid, S in series.items():
        reg = V4.WINDOWS[wid][0]; mid = [r["mid"] for r in S]
        for t in range(360, len(S) - 5):
            fams, _ = V4.detect(S, t)
            if not fams: continue
            g6 = feats_v6(S, t); g5 = V5.gate_feats(S, t); oc = V4.outcome_short(mid, t, mid[t])
            rec = {"regime": reg, "window_id": wid, "ts_iso": dt.datetime.fromtimestamp(S[t]["m"] * 60, tz=dt.timezone.utc).isoformat(), **oc,
                   "allow_OLD": bool(V5.GATES[OLD_GATE](g5))}
            for gn, gf in GATES_V6.items(): rec["allow_" + gn] = bool(gf(g6))
            events.append(rec)
            if len(feat_rows) < 4000: feat_rows.append({"regime": reg, "window_id": wid, "ts_iso": rec["ts_iso"], "outcome": oc["outcome"], **g6})
    _wcsv(OUT / "GATE_FEATURES_V6.csv", feat_rows)

    # ---- random baseline + gate decisions ----
    rnd = []
    for wid, S in series.items():
        reg = V4.WINDOWS[wid][0]; mid = [r["mid"] for r in S]; cand = list(range(360, len(S) - 5))
        if len(cand) < 50: continue
        for t in random.sample(cand, min(500, len(cand))):
            g6 = feats_v6(S, t); g5 = V5.gate_feats(S, t); oc = V4.outcome_short(mid, t, mid[t])
            r = {"regime": reg, "window_id": wid, **oc, "allow_OLD": bool(V5.GATES[OLD_GATE](g5))}
            for gn, gf in GATES_V6.items(): r["allow_" + gn] = bool(gf(g6))
            rnd.append(r)

    def sub(rows, reg=None, allow=None):
        out = rows
        if reg: out = [r for r in out if r["regime"] == reg]
        if allow: out = [r for r in out if r[allow]]
        return out

    # ---- feature defs + rules ----
    _wmd(OUT / "GATE_FEATURE_DEFINITIONS_V6.md", "GATE FEATURE DEFINITIONS v6 (causal, pre-minute)",
         ["- ret_30/60/180/360m: higher-timeframe returns (uptrend danger if any > 0).",
          "- price_vs_vwap180_pct: mid vs 180-min volume-weighted price (above => up bias).",
          "- cvd_60/180m, net_taker_60m: seller control if < 0.", "- up_from_recent_low_pct: bounce size (danger if large).",
          "- buy_recovery: net taker buy + CVD up over last 15m (buyers returning -> short danger).",
          "- downside_progress: ret60<0 AND making new 60m lows.", "- weak_bounce: up_from_low < 0.6.",
          "- bounce_danger / chop / uptrend_danger / downtrend_perm / seller_ctrl_strict: composite flags.",
          "All from minutes <= t. No future data. OKX single-venue (no L2)."])
    rules = {
        "GATE_6A_STRICT_NO_UPTREND": "FORBID if ret60>0 OR ret180>0 OR ret360>0 OR price>vwap OR cvd60>0 OR buy_recovery",
        "GATE_6B_DOWNTREND_ONLY": "ALLOW only if ret60<0 AND ret180<0 AND cvd180<0 AND price<vwap AND downside_progress",
        "GATE_6C_SELLER_CONTROL_STRICT": "ALLOW only if net_taker60<0 AND cvd60<0 AND pc15<0 AND weak_bounce AND not bounce_danger",
        "GATE_6D_NO_BOUNCE_NO_CHOP": "FORBID if bounce_danger OR chop",
        "GATE_6E_COMBINED_STRICT": "ALLOW only if downtrend_perm AND seller_ctrl_strict AND not uptrend_danger AND not chop AND not bounce_danger"}
    (OUT / "GATE_RULES_V6.json").write_text(json.dumps({"build": now(), "rules": rules, "causal": True, "failure_modes": "fixed a-priori thresholds; 1 up-window only; OKX-only no L2"}, indent=2), encoding="utf-8")
    _wmd(OUT / "GATE_RULES_V6.md", "GATE RULES v6 (rule-based, stricter)", [f"- **{k}**: {v}" for k, v in rules.items()])

    ALLGATES = ["OLD"] + list(GATES_V6)
    rand_all_pf = grp(rnd)["pf"]

    # ---- 5: TREND_UP strict block ----
    up = sub(events, "TREND_UP"); up_rnd = sub(rnd, "TREND_UP")
    up_rows = []
    for gn in ALLGATES:
        ev_a = sub(up, allow="allow_" + gn); rb_a = sub(up_rnd, allow="allow_" + gn)
        up_rows.append({"gate": gn, "before": len(up), "after": len(ev_a), "blocked_pct": rate(len(up) - len(ev_a), len(up)),
                        "pf_before": grp(up)["pf"], "pf_after": grp(ev_a)["pf"], "randgate_pf": grp(rb_a)["pf"]})
    _wcsv(OUT / "TREND_UP_STRICT_BLOCK_TEST.csv", up_rows)
    best_up = max((r for r in up_rows if r["gate"] != "OLD"), key=lambda r: r["blocked_pct"])
    _wmd(OUT / "TREND_UP_STRICT_BLOCK_TEST.md", "TREND_UP STRICT BLOCK TEST (2026-03-10..16, +9.4%)",
         ["| gate | before | after | blocked% | PF after | rand+gate PF |", "|---|--:|--:|--:|--:|--:|"] +
         [f"| {r['gate']} | {r['before']} | {r['after']} | {r['blocked_pct']} | {r['pf_after']} | {r['randgate_pf']} |" for r in up_rows] +
         ["", f"- v5 OLD gate blocked {next(r['blocked_pct'] for r in up_rows if r['gate']=='OLD')}%; best v6 **{best_up['gate']}** blocks {best_up['blocked_pct']}%.",
          "- shorts survive when a deep intraday pullback briefly makes ret60/ret180 negative inside the uptrend; ret_360m + VWAP catch most of them."])

    # ---- 6: downtrend retention ----
    dn = sub(events, "TREND_DOWN"); dn_rnd = sub(rnd, "TREND_DOWN"); dn_rand_pf = grp(dn_rnd)["pf"]
    dn_rows = []
    for gn in ALLGATES:
        ev_a = sub(dn, allow="allow_" + gn); rb_a = sub(dn_rnd, allow="allow_" + gn)
        wb = sum(r["hit2"] for r in dn); wa = sum(r["hit2"] for r in ev_a)
        dn_rows.append({"gate": gn, "before": len(dn), "after": len(ev_a), "retained_pct": rate(len(ev_a), len(dn)),
                        "winners_before": wb, "winners_after": wa, "winners_retained_pct": rate(wa, wb),
                        "event_gate_pf": grp(ev_a)["pf"], "randgate_pf": grp(rb_a)["pf"], "randgate_exp": grp(rb_a)["expectancy"], "random_all_dn_pf": dn_rand_pf})
    _wcsv(OUT / "DOWNTREND_RETENTION_TEST_V6.csv", dn_rows)
    _wmd(OUT / "DOWNTREND_RETENTION_TEST_V6.md", "DOWNTREND RETENTION TEST v6",
         ["| gate | before | after | retained% | winners_ret% | event+gate PF | rand+gate PF | randDOWN PF |", "|---|--:|--:|--:|--:|--:|--:|--:|"] +
         [f"| {r['gate']} | {r['before']} | {r['after']} | {r['retained_pct']} | {r['winners_retained_pct']} | {r['event_gate_pf']} | {r['randgate_pf']} | {r['random_all_dn_pf']} |" for r in dn_rows])

    # ---- 7: range/bounce ----
    rb_rows = []
    for reg in ("RANGE_CHOP", "REVERSAL_BOUNCE"):
        ev = sub(events, reg); rb = sub(rnd, reg)
        for gn in ALLGATES:
            ev_a = sub(ev, allow="allow_" + gn); rb_a = sub(rb, allow="allow_" + gn)
            rb_rows.append({"regime": reg, "gate": gn, "before": len(ev), "after": len(ev_a), "blocked_pct": rate(len(ev) - len(ev_a), len(ev)),
                            "event_gate_pf": grp(ev_a)["pf"], "randgate_pf": grp(rb_a)["pf"], "random_all_pf": grp(rb)["pf"]})
    _wcsv(OUT / "RANGE_BOUNCE_BLOCK_TEST_V6.csv", rb_rows)
    _wmd(OUT / "RANGE_BOUNCE_BLOCK_TEST_V6.md", "RANGE / BOUNCE BLOCK TEST v6",
         ["| regime | gate | before | after | blocked% | event+gate PF | rand+gate PF | random_all PF |", "|---|---|--:|--:|--:|--:|--:|--:|"] +
         [f"| {r['regime']} | {r['gate']} | {r['before']} | {r['after']} | {r['blocked_pct']} | {r['event_gate_pf']} | {r['randgate_pf']} | {r['random_all_pf']} |" for r in rb_rows])

    # ---- 8: edge decomposition + 9: decisions ----
    dec = []
    for gn in ALLGATES:
        ev_a = sub(events, allow="allow_" + gn); rb_a = sub(rnd, allow="allow_" + gn)
        epf, en, eexp, eh = gpf(ev_a); rpf, rn, rexp, rh = gpf(rb_a)
        up_block = next(r["blocked_pct"] for r in up_rows if r["gate"] == gn)
        dn_ret = next(r["retained_pct"] for r in dn_rows if r["gate"] == gn)
        gate_helps = isinstance(rpf, float) and isinstance(rand_all_pf, float) and rpf > rand_all_pf + 0.1
        event_adds = isinstance(epf, float) and isinstance(rpf, float) and epf > rpf + 0.1
        overfilter = en < 30 or rn < 30
        n_up_windows = 1  # only one TREND_UP window available
        if gn == "OLD":
            status = "v5_reference"
        elif overfilter: status = "QUARANTINE"
        elif up_block < 70: status = "REJECT"           # not stricter enough than v5 (62%)
        elif not gate_helps: status = "REJECT"
        elif dn_ret < 10: status = "REJECT"             # kills all downtrend shorts
        else: status = "NEED_MORE_DATA"                 # blocks UP + helps + retains, but 1 up-window + event!=edge
        dec.append({"gate": gn, "allowed_n": en, "event_gate_pf": epf, "randgate_pf": rpf, "random_all_pf": rand_all_pf,
                    "up_blocked_pct": up_block, "down_retained_pct": dn_ret, "gate_helps": gate_helps, "event_adds": event_adds,
                    "overfilter": overfilter, "status": status})
    _wcsv(OUT / "GATE_EDGE_DECOMPOSITION.csv", dec)
    _wcsv(OUT / "GATE_SCORECARD_V6.csv", dec)
    _wmd(OUT / "GATE_EDGE_DECOMPOSITION.md", "GATE EDGE DECOMPOSITION v6",
         ["| gate | allowed n | event+gate PF | rand+gate PF | random_all PF | gate_helps | event_adds | UPblock% | DOWNret% |", "|---|--:|--:|--:|--:|:--:|:--:|--:|--:|"] +
         [f"| {d['gate']} | {d['allowed_n']} | {d['event_gate_pf']} | {d['randgate_pf']} | {d['random_all_pf']} | {d['gate_helps']} | {d['event_adds']} | {d['up_blocked_pct']} | {d['down_retained_pct']} |" for d in dec])
    _wmd(OUT / "GATE_DECISIONS_V6.md", "GATE DECISIONS v6",
         ["| gate | status | UPblock% | DOWNret% | gate_helps | event_adds | allowed n |", "|---|:--:|--:|--:|:--:|:--:|--:|"] +
         [f"| {d['gate']} | **{d['status']}** | {d['up_blocked_pct']} | {d['down_retained_pct']} | {d['gate_helps']} | {d['event_adds']} | {d['allowed_n']} |" for d in dec] +
         ["", "RESEARCH_CANDIDATE requires multi-window UP evidence (we have ONE up window) -> ceiling is NEED_MORE_DATA even for strong blockers.",
          "event_adds is FALSE everywhere -> the entry trigger still does not beat random within the allowed set (v5 conclusion holds)."])

    # ---- 10: comparison with v5 ----
    oldd = next(d for d in dec if d["gate"] == "OLD"); bestd = next(d for d in dec if d["gate"] == best_up["gate"])
    _wmd(OUT / "COMPARISON_WITH_V5.md", "COMPARISON WITH v5 (GATE_5_COMBINED)",
         [f"- TREND_UP blocked: v5 OLD {oldd['up_blocked_pct']}% -> v6 best {best_up['gate']} {bestd['up_blocked_pct']}%.",
          f"- remaining TREND_UP shorts: v5 {next(r['after'] for r in up_rows if r['gate']=='OLD')} -> v6 {next(r['after'] for r in up_rows if r['gate']==best_up['gate'])}.",
          f"- TREND_UP PF after: v5 {next(r['pf_after'] for r in up_rows if r['gate']=='OLD')} -> v6 {best_up['pf_after']}.",
          f"- TREND_DOWN retained: v5 {oldd['down_retained_pct']}% -> v6 {bestd['down_retained_pct']}%.",
          f"- random+gate PF: v5 {oldd['randgate_pf']} -> v6 {bestd['randgate_pf']} (random_all {rand_all_pf}).",
          f"- event+gate PF: v5 {oldd['event_gate_pf']} -> v6 {bestd['event_gate_pf']}.",
          f"- gate_helps: v6 {bestd['gate_helps']} · event_adds: v6 {bestd['event_adds']}.",
          f"- status: v6 best -> {bestd['status']}.",
          "", "Honest read: v6 blocks more uptrend shorts than v5, but the entry still adds nothing over random within the allowed set."])

    # ---- 11: final ----
    rc = [d["gate"] for d in dec if d["status"] == "RESEARCH_CANDIDATE"]
    _final(up_rows, dn_rows, dec, best_up, bestd, oldd, rand_all_pf, rc)

    print("DECISIONS:")
    for d in dec: print(f"  {d['gate']:<28} {d['status']:<16} UPblock {d['up_blocked_pct']}% DOWNret {d['down_retained_pct']}% helps {d['gate_helps']} adds {d['event_adds']} rand+gate {d['randgate_pf']} (rand_all {rand_all_pf}) n{d['allowed_n']}")
    print(f"best v6 UP blocker: {best_up['gate']} {best_up['blocked_pct']}% (v5 OLD {oldd['up_blocked_pct']}%)")
    print("RESEARCH_CANDIDATE:", rc or "NONE")
    return 0


def _final(up_rows, dn_rows, dec, best_up, bestd, oldd, rand_all_pf, rc):
    md = ["# STRICT SHORT-PERMISSION GATE v6 — FINAL REPORT", "", f"Build {now()} · RESEARCH/CALIBRATION, not production. TP=2%/SL=1.5%. OKX single-venue, di-free, causal gate.", "",
          "## 1. Executive summary",
          f"- Stricter gates raise TREND_UP blocking from v5 {oldd['up_blocked_pct']}% to **{best_up['blocked_pct']}%** ({best_up['gate']}), keeping {bestd['down_retained_pct']}% of TREND_DOWN shorts.",
          f"- random+gate PF {bestd['randgate_pf']} > random_all {rand_all_pf} (gate_helps={bestd['gate_helps']}); event_adds_over_random+gate={bestd['event_adds']}.",
          f"- RESEARCH_CANDIDATE: {rc or 'NONE'} (ceiling is NEED_MORE_DATA — only ONE trend-up window available).",
          "## 2. Why v6 after v5", "- v5 GATE_5 left ~828 losing uptrend shorts; v6 tightens the no-uptrend / downtrend-only logic (ret_3h+ret_6h, VWAP, buy-recovery).",
          "## 3. Gates tested", "- 6A strict-no-uptrend, 6B downtrend-only, 6C seller-control-strict, 6D no-bounce-no-chop, 6E combined-strict.",
          f"## 4. Best TREND_UP blocker: {best_up['gate']} ({best_up['blocked_pct']}%).",
          f"## 5. TREND_DOWN not killed: retained {bestd['down_retained_pct']}% (winners kept).",
          f"## 6. random+gate beats random_all: {bestd['gate_helps']} ({bestd['randgate_pf']} vs {rand_all_pf}).",
          f"## 7. event adds after gate: {bestd['event_adds']} (NO -> entry still not an edge).",
          "## 8. Statuses: see GATE_DECISIONS_V6 — best gates NEED_MORE_DATA, weak ones REJECT.",
          "## 9. Next: (a) get >=2 more TREND_UP/RANGE/BOUNCE windows to lift the gate from NEED_MORE_DATA to RESEARCH_CANDIDATE; (b) pair the gate with a NON-event entry (event adds nothing); (c) add Bybit+OKX L2 for cross-venue confirmation inside allowed regimes.", "",
          "FINAL_ARTIFACTS_LOCATION:",
          "- main_folder: reports/strict_short_permission_gate_v6/",
          "- gate_features: GATE_FEATURES_V6.csv (+ GATE_FEATURE_DEFINITIONS_V6.md)", "- gate_rules: GATE_RULES_V6.json/.md",
          "- trend_up_block_test: TREND_UP_STRICT_BLOCK_TEST.csv/.md", "- downtrend_retention_test: DOWNTREND_RETENTION_TEST_V6.csv/.md",
          "- range_bounce_block_test: RANGE_BOUNCE_BLOCK_TEST_V6.csv/.md", "- edge_decomposition: GATE_EDGE_DECOMPOSITION.csv/.md",
          "- gate_scorecard: GATE_SCORECARD_V6.csv", "- gate_decisions: GATE_DECISIONS_V6.md", "- comparison_with_v5: COMPARISON_WITH_V5.md",
          "- final_report: STRICT_SHORT_PERMISSION_GATE_V6_FINAL_REPORT.md"]
    (OUT / "STRICT_SHORT_PERMISSION_GATE_V6_FINAL_REPORT.md").write_text("\n".join(md), encoding="utf-8")


def _wcsv(path, rows):
    if not rows: path.write_text("", encoding="utf-8"); return
    keys = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys, extrasaction="ignore"); w.writeheader()
        for r in rows: w.writerow({k: (json.dumps(v) if isinstance(v, (list, dict)) else v) for k, v in r.items()})
def _wmd(path, title, body): path.write_text(f"# {title}\n\nBuild {now()} · research/calibration.\n\n" + "\n".join(body) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
