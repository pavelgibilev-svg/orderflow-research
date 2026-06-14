"""v5 — SHORT-PERMISSION / REGIME GATE before the frozen v3/v4 event trigger.

Logic: a causal (pre-event) regime gate decides SHORT_ALLOWED before any event fires. Events are only taken
when the gate allows. Key tests: does the gate BLOCK trend-up shorts, RETAIN downtrend shorts, and does
event+gate beat random (and random+gate)? No threshold tuning, no TP/SL change, no future data.
Reuses the v4 di-free detector + per-minute series (OKX single-venue control). Series cached for fast reruns.
"""
from __future__ import annotations
import csv, json, random, statistics as st, sys, datetime as dt
from collections import defaultdict
from pathlib import Path

ROOT = Path("C:/Users/gibilev/orderflow-research")
sys.path.insert(0, str(ROOT / "scripts/research"))
import td_v4_regime as V4
OUT = ROOT / "reports/short_permission_gate_v5"
SER = OUT / "_series"
random.seed(42)
REGIMES = ("TREND_DOWN", "TREND_UP", "RANGE_CHOP", "REVERSAL_BOUNCE")


def now(): return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
def pf_of(W, L): return round((W * 1.86) / (L * 1.64), 3) if L else ("inf" if W else None)
def rate(k, n): return round(100 * k / n, 1) if n else 0.0
def med(v): v = [x for x in v if x is not None]; return round(st.median(v), 4) if v else None


def get_series(wid):
    cache = SER / f"{wid}.json"
    if cache.exists(): return json.loads(cache.read_text())
    reg, src, days = V4.WINDOWS[wid]
    S = V4.load_series(src, days)
    SER.mkdir(parents=True, exist_ok=True); cache.write_text(json.dumps(S), encoding="utf-8")
    return S


def gate_feats(S, t):
    mid = [r["mid"] for r in S]
    def ret(k): return round((mid[t] - mid[t - k]) / mid[t - k] * 100, 3) if t >= k else None
    def cvd(k): return round(S[t]["cvd"] - S[t - k]["cvd"], 1) if t >= k else None
    def nettk(k): return round(sum(S[i]["bv"] - S[i]["sv"] for i in range(max(0, t - k), t)), 3)
    sma180 = st.mean(mid[max(0, t - 180):t]) if t > 5 else mid[t]
    pv_sma = round((mid[t] - sma180) / sma180 * 100, 3)
    look = mid[max(0, t - 180):t + 1]; rng180 = (max(look) - min(look)) / min(look) * 100 if look else 0
    r30, r60, r180, r360 = ret(30), ret(60), ret(180), ret(360)
    recent_low = min(mid[max(0, t - 60):t + 1]); up_from_low = round((mid[t] - recent_low) / recent_low * 100, 3)
    bounce_danger = bool((r180 is not None and r180 < -1.0) and (cvd(30) is not None and cvd(30) >= 0) and up_from_low > 0.8)
    chop = bool(r180 is not None and abs(r180) < 0.5 and rng180 > 1.5)
    uptrend = bool((r60 is not None and r60 > 0.3) or (r180 is not None and r180 > 0.5) or pv_sma > 0.2 or (cvd(60) is not None and cvd(60) > 0))
    seller_control = bool((nettk(60) < 0) and (r60 is not None and r60 < 0))
    downside_bg = bool((r60 is not None and r60 < 0) and (r180 is not None and r180 < 0) and (cvd(60) is not None and cvd(60) < 0))
    return {"ret_30m": r30, "ret_60m": r60, "ret_180m": r180, "ret_360m": r360, "ret_1d": ret(1440),
            "price_vs_sma180_pct": pv_sma, "cvd_30m": cvd(30), "cvd_60m": cvd(60), "cvd_180m": cvd(180),
            "net_taker_60m": nettk(60), "up_from_recent_low_pct": up_from_low, "range_180m_pct": round(rng180, 3),
            "bounce_danger": bounce_danger, "chop": chop, "uptrend": uptrend, "seller_control": seller_control, "downside_background": downside_bg}


# ---- gate rules (causal, a-priori) ----
GATES = {
    "GATE_1_STRICT_DOWNTREND": lambda g: (g["ret_60m"] is not None and g["ret_60m"] < 0) and (g["ret_180m"] is not None and g["ret_180m"] < 0) and (g["cvd_60m"] is not None and g["cvd_60m"] < 0) and not g["bounce_danger"],
    "GATE_2_SELLER_CONTROL": lambda g: g["seller_control"] and not g["bounce_danger"],
    "GATE_3_NO_UPTREND": lambda g: not g["uptrend"],
    "GATE_4_NO_CHOP": lambda g: not g["chop"],
    "GATE_5_COMBINED": lambda g: g["downside_background"] and g["seller_control"] and not g["uptrend"] and not g["chop"] and not g["bounce_danger"],
}


def grp(rows): return V4.grp(rows)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    series = {wid: get_series(wid) for wid in V4.WINDOWS}
    for wid, S in series.items(): print(f"{wid}: {len(S)} min", flush=True)

    # ---- detect events + gate features ----
    events = []  # each: regime, window, t, outcome..., gate features, gate allow flags
    gate_feat_rows = []
    for wid, S in series.items():
        reg = V4.WINDOWS[wid][0]; mid = [r["mid"] for r in S]
        for t in range(360, len(S) - 5):  # need 6h lookback for gate
            fams, _ = V4.detect(S, t)
            if not fams: continue
            g = gate_feats(S, t); oc = V4.outcome_short(mid, t, mid[t])
            allow = {gn: bool(gf(g)) for gn, gf in GATES.items()}
            rec = {"regime": reg, "window_id": wid, "t": t, "ts_iso": dt.datetime.fromtimestamp(S[t]["m"] * 60, tz=dt.timezone.utc).isoformat(),
                   "families": "|".join(fams), **oc, **{("g_" + k): v for k, v in g.items()}, **{("allow_" + gn): allow[gn] for gn in GATES}}
            events.append(rec)
            if len(gate_feat_rows) < 4000: gate_feat_rows.append({"regime": reg, "window_id": wid, "ts_iso": rec["ts_iso"], "families": rec["families"], "outcome": oc["outcome"], **g, **{("allow_" + gn): allow[gn] for gn in GATES}})
    _wcsv(OUT / "GATE_FEATURES.csv", gate_feat_rows)

    # ---- random baseline + gate decision at random minutes ----
    rnd = []
    for wid, S in series.items():
        reg = V4.WINDOWS[wid][0]; mid = [r["mid"] for r in S]; cand = list(range(360, len(S) - 5))
        if len(cand) < 50: continue
        for t in random.sample(cand, min(500, len(cand))):
            g = gate_feats(S, t); oc = V4.outcome_short(mid, t, mid[t])
            rnd.append({"regime": reg, "window_id": wid, **oc, **{("allow_" + gn): bool(gf(g)) for gn, gf in GATES.items()}})

    # ---- aggregate helpers ----
    def by_reg(rows, reg): return [r for r in rows if r["regime"] == reg]
    def gstat(rows):
        g = grp(rows); return {"n": g["n"], "hit2_rate": g["hit2_rate"], "pf": g["pf"], "expectancy": g["expectancy"], "W": g["W"], "L": g["L"], "TO": g["TO"]}

    # ---- 2/3: gate features defs + rules ----
    _wmd(OUT / "GATE_FEATURE_DEFINITIONS.md", "GATE FEATURE DEFINITIONS (all causal, pre-event)",
         ["- ret_30m/60m/180m/360m/1d: prior price return over k minutes (higher-timeframe direction).",
          "- price_vs_sma180_pct: mid vs 180-min mean (above => up bias).",
          "- cvd_30m/60m/180m: CVD change over k minutes (seller control if <0).",
          "- net_taker_60m: taker buy-sell volume over 60m (<0 = sell dominance).",
          "- up_from_recent_low_pct: bounce size from the last-60m low (bounce danger).",
          "- range_180m_pct: 180m high-low range (chop if large with ~0 net).",
          "- bounce_danger: prior drop (ret180<-1) AND CVD stopped falling AND up_from_low>0.8.",
          "- chop: |ret180|<0.5 with range180>1.5 (movement, no progress).",
          "- uptrend: ret60>0.3 OR ret180>0.5 OR above sma180 OR cvd60>0.",
          "- seller_control: net_taker_60m<0 AND ret60<0.", "- downside_background: ret60<0 AND ret180<0 AND cvd60<0.",
          "", "All computed only from minutes <= event minute. No future data. OKX single-venue (no L2 in control regimes)."])
    rules = {gn: {"logic": src, "features": list({k for k in ["ret_60m", "ret_180m", "cvd_60m", "net_taker_60m", "uptrend", "chop", "bounce_danger", "seller_control", "downside_background"]}),
                  "causal": True, "may_fail": "rule-based; fixed a-priori thresholds; small sample per regime"} for gn, src in {
        "GATE_1_STRICT_DOWNTREND": "ret60<0 AND ret180<0 AND cvd60<0 AND not bounce_danger",
        "GATE_2_SELLER_CONTROL": "net_taker_60m<0 AND ret60<0 AND not bounce_danger",
        "GATE_3_NO_UPTREND": "allowed unless uptrend(ret60>0.3 OR ret180>0.5 OR >sma180 OR cvd60>0)",
        "GATE_4_NO_CHOP": "allowed unless chop(|ret180|<0.5 AND range180>1.5)",
        "GATE_5_COMBINED": "downside_background AND seller_control AND not uptrend AND not chop AND not bounce_danger"}.items()}
    (OUT / "GATE_RULES.json").write_text(json.dumps({"build": now(), "gates": rules}, indent=2), encoding="utf-8")
    _wmd(OUT / "GATE_RULES.md", "GATE RULES (rule-based, causal)", [f"- **{gn}**: {r['logic']}" for gn, r in rules.items()])

    # ---- 4: gate performance by regime ----
    perf = []
    for reg in REGIMES:
        ev = by_reg(events, reg); rb = by_reg(rnd, reg)
        base = gstat(ev); rbase = gstat(rb)
        row = {"regime": reg, "event_no_gate_n": base["n"], "event_no_gate_hit2": base["hit2_rate"], "event_no_gate_pf": base["pf"], "event_no_gate_exp": base["expectancy"],
               "random_all_n": rbase["n"], "random_all_pf": rbase["pf"], "random_all_exp": rbase["expectancy"]}
        for gn in GATES:
            evg = [r for r in ev if r["allow_" + gn]]; rbg = [r for r in rb if r["allow_" + gn]]
            sg = gstat(evg); srg = gstat(rbg)
            row[gn + "_allowed"] = sg["n"]; row[gn + "_blocked_pct"] = rate(base["n"] - sg["n"], base["n"])
            row[gn + "_pf"] = sg["pf"]; row[gn + "_exp"] = sg["expectancy"]
            row[gn + "_pf_lift_vs_randall"] = (round(sg["pf"] - rbase["pf"], 3) if isinstance(sg["pf"], float) and isinstance(rbase["pf"], float) else None)
            row[gn + "_pf_lift_vs_randgate"] = (round(sg["pf"] - srg["pf"], 3) if isinstance(sg["pf"], float) and isinstance(srg["pf"], float) else None)
        perf.append(row)
    _wcsv(OUT / "GATE_PERFORMANCE_BY_REGIME.csv", perf)
    pmd = ["| regime | event no-gate (n/PF) | random_all PF |" + "".join(f" {gn} (allowed/blocked%/PF/dPFvsRandGate) |" for gn in GATES), "|---|---|---|" + "---|" * len(GATES)]
    for r in perf:
        cells = f"| {r['regime']} | {r['event_no_gate_n']}/{r['event_no_gate_pf']} | {r['random_all_pf']} |"
        for gn in GATES: cells += f" {r[gn+'_allowed']}/{r[gn+'_blocked_pct']}%/{r[gn+'_pf']}/{r[gn+'_pf_lift_vs_randgate']} |"
        pmd.append(cells)
    _wmd(OUT / "GATE_PERFORMANCE_BY_REGIME.md", "GATE PERFORMANCE BY REGIME", pmd +
         ["", "Read: high blocked% in TREND_UP/RANGE = gate working. pf_lift_vs_randgate>0 = event adds value on top of gate (else gate does the work)."])

    # ---- 5: TREND_UP block test ----
    up = by_reg(events, "TREND_UP")
    up_fams = defaultdict(int)
    for e in up:
        for fam in e["families"].split("|"): up_fams[fam] += 1
    up_rows = []
    for gn in GATES:
        allowed = [r for r in up if r["allow_" + gn]]; s = gstat(allowed)
        up_rows.append({"gate": gn, "up_events_before": len(up), "up_events_after": len(allowed), "blocked_pct": rate(len(up) - len(allowed), len(up)),
                        "pf_before": gstat(up)["pf"], "pf_after": s["pf"], "hit2_after": s["hit2_rate"]})
    _wcsv(OUT / "TREND_UP_SHORT_BLOCK_TEST.csv", up_rows)
    best_up = max(up_rows, key=lambda r: r["blocked_pct"])
    _wmd(OUT / "TREND_UP_SHORT_BLOCK_TEST.md", "TREND_UP SHORT BLOCK TEST (2026-03-10..16, +9.4%)",
         [f"- v3 short-events in the uptrend (after 6h warmup): **{len(up)}** · PF {gstat(up)['pf']} (loses).",
          f"- event families fired: {dict(up_fams)}",
          "- why false: pure downward-momentum events fire on every pullback inside an uptrend; price reverts up -> stopped.",
          "", "| gate | up before | up after | blocked% | PF after |", "|---|--:|--:|--:|--:|"] +
         [f"| {r['gate']} | {r['up_events_before']} | {r['up_events_after']} | {r['blocked_pct']} | {r['pf_after']} |" for r in up_rows] +
         ["", f"- best uptrend blocker: **{best_up['gate']}** ({best_up['blocked_pct']}% blocked).",
          "- remaining shorts after the best gate are pullback events the gate still permits; tighter ret/cvd thresholds would remove them but that is tuning (not done)."])

    # ---- 6: downtrend retention ----
    dn = by_reg(events, "TREND_DOWN")
    dn_rows = []
    for gn in GATES:
        allowed = [r for r in dn if r["allow_" + gn]]; s = gstat(allowed)
        win_before = sum(r["hit2"] for r in dn); win_after = sum(r["hit2"] for r in allowed)
        dn_rows.append({"gate": gn, "dn_before": len(dn), "dn_after": len(allowed), "retained_pct": rate(len(allowed), len(dn)),
                        "winners_before": win_before, "winners_after": win_after, "winners_retained_pct": rate(win_after, win_before),
                        "pf_after": s["pf"], "random_all_pf": gstat(by_reg(rnd, "TREND_DOWN"))["pf"]})
    _wcsv(OUT / "DOWNTREND_RETENTION_TEST.csv", dn_rows)
    _wmd(OUT / "DOWNTREND_RETENTION_TEST.md", "DOWNTREND RETENTION TEST (does the gate kill good shorts?)",
         ["| gate | dn before | dn after | retained% | winners retained% | PF after | randomDOWN PF |", "|---|--:|--:|--:|--:|--:|--:|"] +
         [f"| {r['gate']} | {r['dn_before']} | {r['dn_after']} | {r['retained_pct']} | {r['winners_retained_pct']} | {r['pf_after']} | {r['random_all_pf']} |" for r in dn_rows] +
         ["", "If retained% ~0 the gate is just 'no trade'. If PF after << randomDOWN PF, the entry still has no edge in down (regime exposure)."])

    # ---- 7: range/bounce block ----
    rbtest = []
    for reg in ("RANGE_CHOP", "REVERSAL_BOUNCE"):
        ev = by_reg(events, reg)
        for gn in GATES:
            allowed = [r for r in ev if r["allow_" + gn]]; s = gstat(allowed)
            rbtest.append({"regime": reg, "gate": gn, "events_before": len(ev), "events_after": len(allowed), "blocked_pct": rate(len(ev) - len(allowed), len(ev)),
                           "pf_before": gstat(ev)["pf"], "pf_after": s["pf"]})
    _wcsv(OUT / "RANGE_BOUNCE_BLOCK_TEST.csv", rbtest)
    _wmd(OUT / "RANGE_BOUNCE_BLOCK_TEST.md", "RANGE / BOUNCE BLOCK TEST",
         ["| regime | gate | before | after | blocked% | PF before | PF after |", "|---|---|--:|--:|--:|--:|--:|"] +
         [f"| {r['regime']} | {r['gate']} | {r['events_before']} | {r['events_after']} | {r['blocked_pct']} | {r['pf_before']} | {r['pf_after']} |" for r in rbtest])

    # ---- 8: gate decisions (pooled, honest) ----
    rand_all_pool = gstat(rnd); rand_all_pf = rand_all_pool["pf"]; rand_all_exp = rand_all_pool["expectancy"]
    decisions = []
    for gn in GATES:
        evg = [r for r in events if r["allow_" + gn]]; rbg = [r for r in rnd if r["allow_" + gn]]
        sg = gstat(evg); srg = gstat(rbg)
        up_block = next(r["blocked_pct"] for r in up_rows if r["gate"] == gn)
        rg_block = rate(sum(1 for r in by_reg(events, "RANGE_CHOP") if not r["allow_" + gn]), max(len(by_reg(events, "RANGE_CHOP")), 1))
        dn_ret = next(r["retained_pct"] for r in dn_rows if r["gate"] == gn)
        gate_helps = (isinstance(srg["pf"], float) and isinstance(rand_all_pf, float) and srg["pf"] > rand_all_pf + 0.1)  # random+gate beats random-all
        event_adds = (isinstance(sg["pf"], float) and isinstance(srg["pf"], float) and sg["pf"] > srg["pf"] + 0.1)        # event beats random within allowed
        if sg["n"] < 8: status = "NEED_MORE_DATA"
        elif up_block < 50: status = "REJECT"                       # fails to block uptrend
        elif dn_ret < 10: status = "REJECT"                         # kills all downtrend shorts (just no-trade)
        elif gate_helps and event_adds: status = "RESEARCH_CANDIDATE"
        elif gate_helps: status = "NEED_MORE_DATA"                  # gate blocks well but event adds nothing over random+gate
        else: status = "QUARANTINE"
        decisions.append({"gate": gn, "allowed_n": sg["n"], "event_gate_pf": sg["pf"], "event_gate_exp": sg["expectancy"],
                          "randomgate_pf": srg["pf"], "randomall_pf": rand_all_pf, "up_blocked_pct": up_block, "range_blocked_pct": rg_block,
                          "down_retained_pct": dn_ret, "gate_helps_vs_randall": gate_helps, "event_adds_vs_randgate": event_adds, "status": status})
    _wcsv(OUT / "GATE_SCORECARD.csv", decisions)
    _wmd(OUT / "GATE_DECISIONS.md", "GATE DECISIONS (status = blocks UP + retains DOWN + beats random)",
         ["| gate | allowed n | event+gate PF | random+gate PF | random_all PF | UP blocked% | RANGE blocked% | DOWN retained% | gate helps? | event adds? | **status** |", "|---|--:|--:|--:|--:|--:|--:|--:|:--:|:--:|:--:|"] +
         [f"| {d['gate']} | {d['allowed_n']} | {d['event_gate_pf']} | {d['randomgate_pf']} | {d['randomall_pf']} | {d['up_blocked_pct']} | {d['range_blocked_pct']} | {d['down_retained_pct']} | {d['gate_helps_vs_randall']} | {d['event_adds_vs_randgate']} | **{d['status']}** |" for d in decisions] +
         ["", "gate_helps = random+gate PF beats random_all (the gate removes losing regimes). event_adds = event beats random WITHIN the allowed set (the trigger itself has edge)."])

    # ---- 9: comparison with v4 + final ----
    best = max(decisions, key=lambda d: (d["up_blocked_pct"], (d["randomgate_pf"] if isinstance(d["randomgate_pf"], float) else -1)))
    _wmd(OUT / "COMPARISON_WITH_V4.md", "COMPARISON WITH v4 (no gate)",
         [f"- v4: event trigger with NO gate -> shorts TREND_UP and loses (PF ~0.18); event PF in DOWN below random.",
          f"- v5 best gate **{best['gate']}**: blocks {best['up_blocked_pct']}% of TREND_UP shorts; random+gate PF {best['randomgate_pf']} vs random_all PF {rand_all_pf}.",
          f"- fewer TREND_UP shorts? {'YES' if best['up_blocked_pct']>=50 else 'NO'}.",
          f"- DOWN shorts retained? {best['down_retained_pct']}%.",
          f"- edge over random? gate_helps={best['gate_helps_vs_randall']}, event_adds_over_random+gate={best['event_adds_vs_randgate']}.",
          "- honest read: a permission gate is the missing layer (it removes UP/RANGE shorting), but the event ENTRY still adds little over random within the allowed regime."])
    rc = [d["gate"] for d in decisions if d["status"] == "RESEARCH_CANDIDATE"]
    _final(perf, up_rows, dn_rows, rbtest, decisions, best, rand_all_pf, rc, len(up), gstat(up)["pf"])

    # console
    print("GATE DECISIONS:")
    for d in decisions: print(f"  {d['gate']:<24} allowed {d['allowed_n']:>4} ev+gate PF {d['event_gate_pf']} | rand+gate {d['randomgate_pf']} | rand_all {d['randomall_pf']} | UPblock {d['up_blocked_pct']}% DOWNret {d['down_retained_pct']}% helps {d['gate_helps_vs_randall']} adds {d['event_adds_vs_randgate']} -> {d['status']}")
    print("RESEARCH_CANDIDATE:", rc or "NONE")
    print(f"TREND_UP events before gate: {len(up)} (PF {gstat(up)['pf']}); best blocker {best['gate']} {best['up_blocked_pct']}%")
    return 0


def _final(perf, up_rows, dn_rows, rbtest, decisions, best, rand_all_pf, rc, up_n, up_pf):
    md = ["# SHORT-PERMISSION GATE v5 — FINAL REPORT", "", f"Build {now()} · RESEARCH/CALIBRATION, not production. TP=2%/SL=1.5%. OKX single-venue, di-free, causal gate.", "",
          "## 1. Executive summary",
          f"- A causal regime gate is placed BEFORE the v3 event trigger. Best gate **{best['gate']}** blocks **{best['up_blocked_pct']}%** of TREND_UP shorts and retains **{best['down_retained_pct']}%** of TREND_DOWN shorts.",
          f"- gate_helps (random+gate {best['randomgate_pf']} > random_all {rand_all_pf}) = {best['gate_helps_vs_randall']}; event_adds_over_random+gate = {best['event_adds_vs_randgate']}.",
          f"- RESEARCH_CANDIDATE gates: {rc or 'NONE'}.",
          "## 2. Why a regime gate", "- v4 proved the event trigger shorts uptrends and has no edge over random; the missing layer is short-permission.",
          "## 3. Gate rules tested", "- GATE_1 strict-downtrend, GATE_2 seller-control, GATE_3 no-uptrend, GATE_4 no-chop, GATE_5 combined.",
          f"## 4. TREND_UP: {up_n} short-events (PF {up_pf}); best blocker {best['gate']} removes {best['up_blocked_pct']}%.",
          "## 5. TREND_DOWN: retention per gate in DOWNTREND_RETENTION_TEST (avoid 'no-trade-always').",
          "## 6-7. RANGE/CHOP + REVERSAL/BOUNCE: see RANGE_BOUNCE_BLOCK_TEST.",
          "## 8. event+gate vs random: " + ("event adds edge" if best["event_adds_vs_randgate"] else "**event adds nothing over random within the allowed regime — the gate does the work, the entry is still not an edge**") + ".",
          f"## 9. RESEARCH_CANDIDATE: {'YES ' + str(rc) if rc else 'NO'}",
          "## 10. Next: if gate blocks UP/RANGE but event!=edge, pair the gate (as a short-permission veto) with a DIFFERENT entry; OR get Bybit+OKX L2 control data to test cross-venue confirmation inside allowed regimes.", "",
          "FINAL_ARTIFACTS_LOCATION:",
          "- main_folder: reports/short_permission_gate_v5/",
          "- gate_features: GATE_FEATURES.csv (+ GATE_FEATURE_DEFINITIONS.md)", "- gate_rules: GATE_RULES.json/.md",
          "- gate_performance: GATE_PERFORMANCE_BY_REGIME.csv/.md", "- trend_up_block_test: TREND_UP_SHORT_BLOCK_TEST.md/.csv",
          "- downtrend_retention_test: DOWNTREND_RETENTION_TEST.md/.csv", "- range_bounce_block_test: RANGE_BOUNCE_BLOCK_TEST.md/.csv",
          "- gate_scorecard: GATE_SCORECARD.csv", "- gate_decisions: GATE_DECISIONS.md", "- comparison_with_v4: COMPARISON_WITH_V4.md",
          "- final_report: SHORT_PERMISSION_GATE_V5_FINAL_REPORT.md"]
    (OUT / "SHORT_PERMISSION_GATE_V5_FINAL_REPORT.md").write_text("\n".join(md), encoding="utf-8")


def _wcsv(path, rows):
    if not rows: path.write_text("", encoding="utf-8"); return
    keys = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys, extrasaction="ignore"); w.writeheader()
        for r in rows: w.writerow({k: (json.dumps(v) if isinstance(v, (list, dict)) else v) for k, v in r.items()})
def _wmd(path, title, body): path.write_text(f"# {title}\n\nBuild {now()} · research/calibration.\n\n" + "\n".join(body) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
