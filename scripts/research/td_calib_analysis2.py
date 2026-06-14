"""TASK2 — TREND_DOWN cross-window comparison + template decision (analysis of SAVED artifacts only).

Does NOT recompute raw L2/trades. Loads reports/trend_down_calibration_v1/ artifacts, compares the 3 windows,
scores capital states + evidence blocks, decides which candidate filters become templates / veto / quarantine
/ reject / need-more-data. RESEARCH analysis, not production validation.
"""
from __future__ import annotations
import csv, json, statistics as st, sys, datetime as dt
from collections import defaultdict, Counter
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "package.json").exists() and (p / "scripts").exists())
D = ROOT / "reports/trend_down_calibration_v1"
NORM = D / "_normalized"
WINDOWS = {"W1": ("2025-11-19", "2025-11-22"), "W2": ("2026-02-11", "2026-02-14"), "W3": ("2026-01-28", "2026-01-31")}
TRUE_TD = {"W1", "W3"}  # confirmed net <= -1% (W2 bounced +1.42%)


def now_iso(): return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
def fnum(x):
    try: return float(x)
    except (TypeError, ValueError): return None
def pf_of(W, L): return round((W * 1.86) / (L * 1.64), 3) if L else ("inf" if W else None)
def rate(k, n): return round(100 * k / n, 1) if n else 0.0
def req(name):
    p = D / name
    if not p.exists(): print(f"MISSING ARTIFACT: {name}"); sys.exit(2)
    return p


def load():
    cl = {r["cluster_id"]: r for r in csv.DictReader(req("TREND_DOWN_UNIQUE_CLUSTERS.csv").open(encoding="utf-8"))}
    cb = {r["cluster_id"]: r for r in csv.DictReader(req("CAPITAL_STATE_CASEBOOK.csv").open(encoding="utf-8"))}
    ev = {r["cluster_id"]: r for r in csv.DictReader(req("EVIDENCE_BLOCK_SCORES.csv").open(encoding="utf-8"))}
    filt = json.loads(req("FILTER_CANDIDATES_TREND_DOWN_V1.json").read_text())["filters"]
    wsum = {r["window_id"]: r for r in csv.DictReader(req("TREND_DOWN_WINDOWS_SUMMARY.csv").open(encoding="utf-8"))}
    rows = []
    for cid, c in cl.items():
        b = cb.get(cid, {}); e = ev.get(cid, {})
        rows.append({"cluster_id": cid, "window_id": c["window_id"], "date": c["date"], "direction": c["direction_candidate"],
                     "outcome": c["primary_outcome"], "hit2": int(b.get("hit2", c.get("primary_hit2", 0)) or 0),
                     "hit2_5": int(b.get("hit2_5", c.get("primary_hit2_5", 0)) or 0), "hit3": int(b.get("hit3", c.get("primary_hit3", 0)) or 0),
                     "loss": int(b.get("loss", 0) or 0), "timeout": int(b.get("timeout", 0) or 0),
                     "capital_state": b.get("capital_state_candidate", "UNKNOWN"),
                     **{k: e.get(k) for k in ("effort_vs_result", "absorption_refill", "initiative_control", "background_alignment", "not_overextended", "liquidity_execution")}})
    return rows, filt, wsum


EBLOCKS = ["effort_vs_result", "absorption_refill", "initiative_control", "background_alignment", "not_overextended", "liquidity_execution"]
STATES = ["ACTIVE_MARKDOWN", "DISTRIBUTION_INTO_BOUNCE", "FORCED_UNWIND", "ABSORPTION_AFTER_SELL_PRESSURE", "NO_CONTROL_CHOP", "UNKNOWN"]


def grp_stats(rows):
    n = len(rows); W = sum(1 for r in rows if r["outcome"] == "WIN"); L = sum(1 for r in rows if r["outcome"] == "LOSS"); TO = sum(1 for r in rows if r["outcome"] == "TIMEOUT")
    return {"n": n, "hit2": sum(r["hit2"] for r in rows), "hit2_5": sum(r["hit2_5"] for r in rows), "hit3": sum(r["hit3"] for r in rows),
            "loss": L, "timeout": TO, "win": W, "hit2_rate": rate(sum(r["hit2"] for r in rows), n), "loss_rate": rate(L, n), "timeout_rate": rate(TO, n),
            "pf": pf_of(W, L), "expectancy": round(st.mean([1.86 if r["outcome"] == "WIN" else -1.64 if r["outcome"] == "LOSS" else 0 for r in rows]), 3) if rows else None}


def main():
    rows, filt, wsum = load()
    base = grp_stats(rows)

    # ---------- B: by window ----------
    bw = []
    for wid in WINDOWS:
        wr = [r for r in rows if r["window_id"] == wid]
        if not wr: continue
        st_counts = Counter(r["capital_state"] for r in wr)
        st_perf = {}
        for s in set(r["capital_state"] for r in wr):
            sr = [r for r in wr if r["capital_state"] == s]; st_perf[s] = grp_stats(sr)["hit2_rate"]
        real_states = {s: v for s, v in st_perf.items() if st_counts[s] >= 3 and s != "UNKNOWN"}
        # evidence separation in-window: corr of block score with hit2 (mean diff winners vs losers)
        sep = {}
        for b in EBLOCKS:
            wv = [fnum(r[b]) for r in wr if r["hit2"] == 1 and fnum(r[b]) is not None]
            lv = [fnum(r[b]) for r in wr if r["hit2"] == 0 and fnum(r[b]) is not None]
            if len(wv) >= 2 and len(lv) >= 2: sep[b] = round(st.mean(wv) - st.mean(lv), 2)
        sep_sorted = sorted(sep.items(), key=lambda x: -abs(x[1]))
        g = grp_stats(wr)
        bw.append({"window_id": wid, "dates": f"{WINDOWS[wid][0]}..{WINDOWS[wid][1]}", "net_pct": wsum.get(wid, {}).get("net_pct"),
                   "trend_down_confirmed": wsum.get(wid, {}).get("trend_down_confirmed"), "clusters": g["n"], "hit2": g["hit2"], "hit2_5": g["hit2_5"],
                   "hit3": g["hit3"], "loss": g["loss"], "timeout": g["timeout"], "dominant_capital_state": st_counts.most_common(1)[0][0],
                   "best_state": (max(real_states, key=real_states.get) if real_states else "none>=3"),
                   "worst_state": (min(real_states, key=real_states.get) if real_states else "none>=3"),
                   "evidence_high_sep": [k for k, v in sep_sorted[:2]] or ["none"], "evidence_failed": [k for k, v in sep_sorted if abs(v) < 0.2] or ["—"],
                   "notes": ("NOT a true TREND_DOWN window (bounced)" if wid not in TRUE_TD else "true markdown window")})
    _wcsv(D / "ANALYSIS_BY_WINDOW.csv", bw)
    _wmd(D / "ANALYSIS_BY_WINDOW.md", "ANALYSIS BY WINDOW",
         ["| window | dates | net% | TD? | clusters | hit2 | loss | TO | dominant state | best state | worst state | high-sep evidence |",
          "|---|---|--:|:--:|--:|--:|--:|--:|---|---|---|---|"] +
         [f"| {r['window_id']} | {r['dates']} | {r['net_pct']} | {r['trend_down_confirmed']} | {r['clusters']} | {r['hit2']} | {r['loss']} | {r['timeout']} | {r['dominant_capital_state']} | {r['best_state']} | {r['worst_state']} | {', '.join(r['evidence_high_sep'])} |" for r in bw] +
         ["", "**Note:** W2 (2026-02-11..14) net +1.42% — bounced, NOT a true TREND_DOWN slice. Only W1 & W3 are markdown windows."])

    # ---------- C: cross-exchange ----------
    okx_files = sorted(NORM.glob("OKX_*_l2_1s.csv.gz"))
    cx_status = "SINGLE_EXCHANGE_ONLY"
    cx_notes = ["Clusters/capital-states were built from **Bybit ob200 only**. OKX provides L2 for just the LAST day of",
                "each window (no in-window OKX trades), so cluster-level cross-venue confirmation is NOT possible.",
                f"OKX normalized files available so far: {[p.name for p in okx_files] or 'none yet (parse may still be running)'}.",
                "Cross-exchange capital-state agreement, both-venue-confirmed clusters, and venue-veto are therefore",
                "**deferred** until full-coverage OKX (or Bybit-trades) data exists."]
    cx_rows = [{"comparison": "bybit_only_clusters", "value": len(rows)}, {"comparison": "okx_clusters", "value": 0},
               {"comparison": "overlapping_full_days", "value": 0}, {"comparison": "both_confirmed_clusters", "value": "N/A"},
               {"comparison": "single_venue_only", "value": len(rows)}, {"comparison": "status", "value": cx_status}]
    _wcsv(D / "CROSS_EXCHANGE_COMPARISON.csv", cx_rows)
    _wmd(D / "CROSS_EXCHANGE_COMPARISON.md", "CROSS-EXCHANGE COMPARISON", [f"**STATUS: {cx_status}**", ""] + ["- " + x for x in cx_notes] +
         ["", "Answers:", "1. Does Bybit see same states as OKX? — **cannot test** (OKX clusters not built).",
          "2. Vice versa — cannot test.", "3-6. cross-venue confirmation/veto — **N/A until OKX full coverage or Bybit trades**."])

    # ---------- D: capital state scorecard ----------
    ds = []
    for s in STATES:
        sr = [r for r in rows if r["capital_state"] == s]
        if not sr: ds.append({"capital_state": s, "clusters": 0, "note": "not observed"}); continue
        g = grp_stats(sr)
        ev_means = {b: round(st.mean([fnum(r[b]) for r in sr if fnum(r[b]) is not None]), 2) if any(fnum(r[b]) is not None for r in sr) else "N/A" for b in EBLOCKS}
        byw = {w: grp_stats([r for r in sr if r["window_id"] == w])["hit2_rate"] for w in set(r["window_id"] for r in sr)}
        wins_true = {w: v for w, v in byw.items() if w in TRUE_TD}
        ds.append({"capital_state": s, "clusters": g["n"], "directions": dict(Counter(r["direction"] for r in sr)),
                   "hit2_rate": g["hit2_rate"], "hit2_5_rate": rate(g["hit2_5"], g["n"]), "hit3_rate": rate(g["hit3"], g["n"]),
                   "loss_rate": g["loss_rate"], "timeout_rate": g["timeout_rate"], "pf": g["pf"], "expectancy": g["expectancy"],
                   "avg_evidence": ev_means, "best_window": (max(byw, key=byw.get) if byw else None), "worst_window": (min(byw, key=byw.get) if byw else None),
                   "windows_present": sorted(byw.keys()), "date_stability": round(len(set(r["date"] for r in sr)) / max(g["n"], 1), 2),
                   "exchange_stability": "SINGLE_EXCHANGE(Bybit)",
                   "interpretation": _interp_state(s, g, sr)})
    _wcsv(D / "CAPITAL_STATE_SCORECARD.csv", [{k: (json.dumps(v) if isinstance(v, dict) else v) for k, v in r.items()} for r in ds])
    _wmd(D / "CAPITAL_STATE_SCORECARD.md", "CAPITAL STATE SCORECARD",
         ["Baseline (all clusters): n=%d hit2=%.1f%% loss=%.1f%% PF=%s" % (base["n"], base["hit2_rate"], base["loss_rate"], base["pf"]), "",
          "| capital_state | n | hit2% | loss% | TO% | PF | windows | interpretation |", "|---|--:|--:|--:|--:|--:|---|---|"] +
         [f"| {r['capital_state']} | {r['clusters']} | {r.get('hit2_rate','-')} | {r.get('loss_rate','-')} | {r.get('timeout_rate','-')} | {r.get('pf','-')} | {','.join(r.get('windows_present',[])) or '-'} | {r.get('interpretation', r.get('note',''))} |" for r in ds])

    # ---------- E: evidence block analysis ----------
    eb = []
    for b in EBLOCKS:
        vals = [(fnum(r[b]), r["hit2"], r["window_id"]) for r in rows if fnum(r[b]) is not None]
        na = len(rows) - len(vals)
        if len(vals) < 8:
            eb.append({"evidence_block": b, "suggested_role": "NEED_MORE_DATA", "uplift": None, "stability": None, "overfit_risk": "HIGH", "n_scored": len(vals), "n_na": na, "notes": "too few scored (mostly N/A or trades-dependent)"}); continue
        hi = [v for v in vals if v[0] >= 2]; lo = [v for v in vals if v[0] < 2]
        up = round(rate(sum(h[1] for h in hi), len(hi)) - base["hit2_rate"], 1) if hi else None
        # stability across true-TD windows
        upw = {}
        for w in TRUE_TD:
            vv = [v for v in vals if v[2] == w]; hh = [v for v in vv if v[0] >= 2]
            if hh: upw[w] = round(rate(sum(h[1] for h in hh), len(hh)) - grp_stats([r for r in rows if r["window_id"] == w])["hit2_rate"], 1)
        stab = "STABLE" if upw and len(upw) >= 2 and len(set(1 if v > 0 else (0 if v == 0 else -1) for v in upw.values())) == 1 else ("MIXED" if upw else "ONE_WINDOW")
        role = ("REQUIRED" if (up or 0) >= 12 and stab == "STABLE" else "OPTIONAL" if (up or 0) >= 5 else "VETO" if (up or 0) <= -10 else "REJECT" if abs(up or 0) < 3 else "OPTIONAL")
        eb.append({"evidence_block": b, "suggested_role": role, "uplift": up, "stability": stab, "overfit_risk": "MED" if stab == "STABLE" else "HIGH",
                   "n_scored": len(vals), "n_na": na, "uplift_by_window": upw, "notes": _interp_ev(b, up, stab, na)})
    _wcsv(D / "EVIDENCE_BLOCK_ANALYSIS.csv", [{k: (json.dumps(v) if isinstance(v, dict) else v) for k, v in r.items()} for r in eb])
    _wmd(D / "EVIDENCE_BLOCK_ANALYSIS.md", "EVIDENCE BLOCK ANALYSIS",
         ["| block | role | uplift(pp) | stability | overfit | n_scored/n_NA | notes |", "|---|---|--:|---|:--:|---|---|"] +
         [f"| {r['evidence_block']} | {r['suggested_role']} | {r['uplift']} | {r['stability']} | {r['overfit_risk']} | {r['n_scored']}/{r['n_na']} | {r['notes']} |" for r in eb])

    # ---------- F: filter comparison ----------
    fc = []
    state_of = {"TD_ACTIVE_MARKDOWN_SHORT_CANDIDATE": ("ACTIVE_MARKDOWN", "SHORT"), "TD_DISTRIBUTION_INTO_BOUNCE_SHORT_CANDIDATE": ("DISTRIBUTION_INTO_BOUNCE", None),
                "TD_FORCED_UNWIND_CONTINUATION_CANDIDATE": ("FORCED_UNWIND", None), "TD_ABSORPTION_AFTER_SELL_PRESSURE_NO_SHORT_OR_REVERSAL_WATCH": ("ABSORPTION_AFTER_SELL_PRESSURE", None),
                "TD_NO_CONTROL_CHOP_NO_TRADE": ("NO_CONTROL_CHOP", None)}
    for f in filt:
        s, dirn = state_of.get(f["filter_id"], (None, None))
        sr = [r for r in rows if r["capital_state"] == s and (dirn is None or r["direction"] == dirn)]
        g = grp_stats(sr); wins = sorted(set(r["window_id"] for r in sr)); true_wins = [w for w in wins if w in TRUE_TD]
        avg_ev = {b: round(st.mean([fnum(r[b]) for r in sr if fnum(r[b]) is not None]), 2) if any(fnum(r[b]) is not None for r in sr) else "N/A" for b in EBLOCKS}
        decision = _filter_decision(f["filter_id"], g, wins, true_wins)
        fc.append({"filter_id": f["filter_id"], "capital_state": s, "intended_direction": f["intended_direction"], "n_clusters": g["n"],
                   "n_windows": len(wins), "windows": wins, "n_true_td_windows": len(true_wins), "hit2_rate": g["hit2_rate"], "pf": g["pf"], "expectancy": g["expectancy"],
                   "date_stability": round(len(set(r["date"] for r in sr)) / max(g["n"], 1), 2), "exchange_stability": "SINGLE(Bybit)", "avg_evidence": avg_ev,
                   "why": _filter_why(f["filter_id"], g, sr), "decision": decision})
    _wcsv(D / "FILTER_COMPARISON_SCORECARD.csv", [{k: (json.dumps(v) if isinstance(v, (dict, list)) else v) for k, v in r.items()} for r in fc])
    _wmd(D / "FILTER_COMPARISON_SCORECARD.md", "FILTER COMPARISON SCORECARD",
         ["| filter | state | n | windows | hit2% | PF | decision | why |", "|---|---|--:|--:|--:|--:|:--:|---|"] +
         [f"| {r['filter_id']} | {r['capital_state']} | {r['n_clusters']} | {len(r['windows'])} | {r['hit2_rate']} | {r['pf']} | **{r['decision']}** | {r['why']} |" for r in fc])

    # ---------- G: template library ----------
    tl = []
    for r in fc:
        status = {"KEEP_TEMPLATE": "RESEARCH_CANDIDATE", "KEEP_AS_VETO": "VETO_CANDIDATE", "QUARANTINE": "QUARANTINE", "REJECT": "REJECTED", "NEED_MORE_DATA": "QUARANTINE"}[r["decision"]]
        if status == "REJECTED": continue
        tl.append({"template_id": r["filter_id"].replace("CANDIDATE", "TEMPLATE"), "template_name": r["filter_id"], "level_1_background": "TREND_DOWN",
                   "capital_state": r["capital_state"], "direction": r["intended_direction"], "purpose": _purpose(r["capital_state"]),
                   "required_conditions": _req_cond(r["capital_state"]), "veto_conditions": _veto_cond(r["capital_state"]),
                   "optional_confirmations": ["taker imbalance / CVD (need in-window trades)", "cross-venue OKX agreement (need full OKX)"],
                   "evidence_blocks_used": EBLOCKS, "minimum_score_logic": "capital_state match + background_alignment>=2 + not flagged by veto",
                   "when_not_to_use": _when_not(r["capital_state"]), "observed_windows": r["windows"], "weak_points": _weak(r, status),
                   "next_validation_needed": "in-window trades + >=2 more true TREND_DOWN windows", "status": status})
    (D / "TREND_DOWN_TEMPLATE_LIBRARY_V1.json").write_text(json.dumps({"build": now_iso(), "status": "TEMPLATE_LIBRARY_NOT_PRODUCTION", "templates": tl}, indent=2, default=str), encoding="utf-8")
    _wmd(D / "TREND_DOWN_TEMPLATE_LIBRARY_V1.md", "TREND_DOWN TEMPLATE LIBRARY V1",
         ["NOT a frozen production filter — research template library.", "", "| template | state | dir | status | observed windows | weak points |", "|---|---|---|:--:|---|---|"] +
         [f"| {t['template_id']} | {t['capital_state']} | {t['direction']} | **{t['status']}** | {','.join(t['observed_windows'])} | {t['weak_points']} |" for t in tl] +
         (["", "_No template qualified as RESEARCH_CANDIDATE on this data — all are QUARANTINE/VETO pending trades + more windows._"] if not any(t["status"] == "RESEARCH_CANDIDATE" for t in tl) else []))

    # ---------- H: decision tree ----------
    _wmd(D / "TREND_DOWN_DECISION_TREE_V1.md", "TREND_DOWN DECISION TREE V1", [
        "Research decision flow (NOT production). TP=2%/SL=1.5% unchanged.", "",
        "```",
        "IF Level1 != TREND_DOWN:            -> do not use TREND_DOWN templates.",
        "IF Level1 == TREND_DOWN:",
        "  determine capital_state from L2 (prior move, bounce size, depth_imbalance, activity):",
        "",
        "  ACTIVE_MARKDOWN (SHORT):          -> TD_ACTIVE_MARKDOWN_SHORT_TEMPLATE  [QUARANTINE: n too small]",
        "  DISTRIBUTION_INTO_BOUNCE (SHORT): -> shorting the bounce LOST here (PF<0.5) -> DO NOT short yet [REJECTED on L2-only]",
        "  FORCED_UNWIND:                    -> not observed -> NEED_MORE_DATA",
        "  ABSORPTION_AFTER_SELL_PRESSURE:   -> DO NOT short; reversal-watch / no-trade",
        "  NO_CONTROL_CHOP:                  -> NO TRADE (default veto)",
        "  UNKNOWN (53% of clusters):        -> NO TRADE (cannot classify on L2-only)",
        "",
        "  THEN check veto: dirty spread / at recent low / depth_imbalance flip -> no trade.",
        "  THEN optional confirmations (taker/CVD/cross-venue) -> N/A until trades exist.",
        "  THEN: trade / no-trade / reversal-watch.",
        "```", "",
        "Bottom line: on L2-only data the tree mostly routes to **NO-TRADE / reversal-watch**; no state yet gives a",
        "tradeable short edge across both true down windows."])

    # ---------- I: final report ----------
    states_seen = {s: sum(1 for r in rows if r["capital_state"] == s) for s in STATES if any(r["capital_state"] == s for r in rows)}
    promising = [r["filter_id"] for r in fc if r["decision"] in ("KEEP_TEMPLATE",)]
    quarantine = [r["filter_id"] for r in fc if r["decision"] in ("QUARANTINE", "NEED_MORE_DATA")]
    rejected = [r["filter_id"] for r in fc if r["decision"] == "REJECT"]
    veto = [r["filter_id"] for r in fc if r["decision"] == "KEEP_AS_VETO"]
    useful_ev = [r["evidence_block"] for r in eb if r["suggested_role"] in ("REQUIRED", "OPTIONAL")]
    junk_ev = [r["evidence_block"] for r in eb if r["suggested_role"] in ("REJECT",)]
    nmd_ev = [r["evidence_block"] for r in eb if r["suggested_role"] == "NEED_MORE_DATA"]
    fr = ["# TREND_DOWN ANALYSIS — FINAL REPORT", "", f"Build {now_iso()} · RESEARCH analysis of saved calibration artifacts · NOT production.", "",
          "## 1. Executive summary",
          f"- {len(rows)} unique clusters across 3 windows (Bybit ob200 only). Overall: hit2 {base['hit2_rate']}%, loss {base['loss_rate']}%, PF {base['pf']}.",
          "- **Only W1 (−8.9%) and W3 (−11.8%) are true TREND_DOWN; W2 (+1.4%) bounced** and is a counter-example, not a down window.",
          "- **53% of clusters are UNKNOWN** and the classifier mislabels 12 LONG zones as ACTIVE_MARKDOWN -> capital-state",
          "  labeling on L2-only proxy is too coarse/direction-blind. No capital_state yet yields a tradeable short edge on both down windows.",
          "- Net: **no RESEARCH_CANDIDATE template** survives; the useful outputs are VETO/NO-TRADE rules + a clear data gap (need trades).", "",
          "## 2. Windows compared", "- " + " · ".join(f"{w}: {a}..{b} ({'true TD' if w in TRUE_TD else 'bounce'})" for w, (a, b) in WINDOWS.items()), "",
          "## 3. Exchanges", "- Bybit ob200 only for clusters. OKX = 1 L2 day/window (no in-window trades) -> CROSS_EXCHANGE = SINGLE_EXCHANGE_ONLY.", "",
          "## 4. Capital states observed", f"- {states_seen}", "",
          "## 5. Promising states", "- " + (", ".join(r["capital_state"] for r in ds if isinstance(r.get("pf"), (int, float)) and r["pf"] not in (None,) and (r["pf"] or 0) >= 1.2 and r["clusters"] >= 4) or "NONE on this data (all weak/insufficient)"), "",
          "## 6-7. Evidence blocks", f"- Useful: {useful_ev or 'none clearly'} · Need-more-data (mostly N/A/trades): {nmd_ev} · Junk: {junk_ev or 'none'}", "",
          "## 8-9. Filters/templates", f"- KEEP as research template: {promising or 'NONE'}", f"- KEEP as veto: {veto or 'NONE'}",
          f"- QUARANTINE / need-more-data: {quarantine}", f"- REJECT: {rejected}", "",
          "## 10. Continue TREND_DOWN research?", "- **YES but data-gated.** The structure is sound; the blocker is missing in-window TRADES (no taker/CVD/effort) and",
          "  only 2 true down windows. Without trades, capital-state separation stays weak (mostly UNKNOWN / NO-TRADE).", "",
          "## 11. Next windows/data to download",
          "- **In-window TRADES** (Bybit + OKX) for W1 (2025-11-19..22) and W3 (2026-01-28..31) — unlocks effort/CVD/taker.",
          "- **Full 4-day OKX L2** for W1/W3 (currently only last day) -> cross-venue capital-state agreement.",
          "- **2-3 more true TREND_DOWN windows** (e.g. 2025-11 full, 2024-04, 2026-02 only if it actually trends down) with trades.",
          "- Replace the bounce window W2 with a genuine markdown window.", "",
          "## 12. Outputs location (below)", "",
          "FINAL_ARTIFACTS_LOCATION:",
          "- analysis_by_window: reports/trend_down_calibration_v1/ANALYSIS_BY_WINDOW.csv/.md",
          "- cross_exchange_comparison: reports/trend_down_calibration_v1/CROSS_EXCHANGE_COMPARISON.csv/.md",
          "- capital_state_scorecard: reports/trend_down_calibration_v1/CAPITAL_STATE_SCORECARD.csv/.md",
          "- evidence_block_analysis: reports/trend_down_calibration_v1/EVIDENCE_BLOCK_ANALYSIS.csv/.md",
          "- filter_comparison: reports/trend_down_calibration_v1/FILTER_COMPARISON_SCORECARD.csv/.md",
          "- template_library: reports/trend_down_calibration_v1/TREND_DOWN_TEMPLATE_LIBRARY_V1.json/.md",
          "- decision_tree: reports/trend_down_calibration_v1/TREND_DOWN_DECISION_TREE_V1.md",
          "- final_report: reports/trend_down_calibration_v1/TREND_DOWN_ANALYSIS_FINAL_REPORT.md"]
    (D / "TREND_DOWN_ANALYSIS_FINAL_REPORT.md").write_text("\n".join(fr), encoding="utf-8")

    # console
    print("BASELINE:", base)
    print("BY WINDOW:")
    for r in bw: print(f"  {r['window_id']} {r['dates']} net{r['net_pct']} TD={r['trend_down_confirmed']} n{r['clusters']} hit2 {r['hit2']} loss {r['loss']} TO {r['timeout']} dom={r['dominant_capital_state']}")
    print("CAPITAL STATES:")
    for r in ds:
        if r["clusters"]: print(f"  {r['capital_state']:<32} n{r['clusters']:>2} hit2 {r.get('hit2_rate')}% loss {r.get('loss_rate')}% PF {r.get('pf')} wins {r.get('windows_present')}")
    print("EVIDENCE:")
    for r in eb: print(f"  {r['evidence_block']:<22} role {r['suggested_role']} uplift {r['uplift']} stab {r['stability']} n {r['n_scored']}/{r['n_na']}NA")
    print("FILTERS:")
    for r in fc: print(f"  {r['filter_id']:<52} n{r['n_clusters']:>2} win{len(r['windows'])} hit2 {r['hit2_rate']}% PF {r['pf']} -> {r['decision']}")
    print("TEMPLATES kept:", [t["template_id"] + "=" + t["status"] for t in tl])
    return 0


# ---- helpers ----
def _wcsv(path, rows):
    if not rows: path.write_text("", encoding="utf-8"); return
    keys = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys, extrasaction="ignore"); w.writeheader()
        for r in rows: w.writerow(r)
def _wmd(path, title, body): path.write_text(f"# {title}\n\nBuild {now_iso()} · research/calibration.\n\n" + "\n".join(body) + "\n", encoding="utf-8")
def _interp_state(s, g, sr):
    if s == "UNKNOWN": return "unclassifiable on L2-only (53%% of pool) -> NO TRADE"
    if g["n"] < 4: return "too few to judge (NEED_MORE_DATA)"
    if s == "ACTIVE_MARKDOWN" and any(r["direction"] == "LONG" for r in sr): return "classifier direction-blind: labels LONG zones too -> flawed; SHORT subset tiny"
    if (g["pf"] in (None, "inf")) or g["pf"] < 0.9: return f"weak/losing (PF {g['pf']})"
    if g["pf"] >= 1.2 and g["hit2_rate"] >= 45: return f"promising (PF {g['pf']})"
    return f"marginal (PF {g['pf']})"
def _interp_ev(b, up, stab, na):
    if b in ("effort_vs_result",) and na > 0: return f"partly N/A (no trades); proxy uplift {up}pp {stab}"
    return f"uplift {up}pp, {stab}"
def _filter_decision(fid, g, wins, true_wins):
    if g["n"] < 4: return "NEED_MORE_DATA"
    if len(true_wins) < 2: return "QUARANTINE"   # only one true-TD window
    if g["pf"] in (None,) or (isinstance(g["pf"], float) and g["pf"] < 0.9): return "REJECT"
    if fid.endswith("NO_TRADE") or "NO_SHORT" in fid: return "KEEP_AS_VETO"
    if isinstance(g["pf"], float) and g["pf"] >= 1.2 and g["hit2_rate"] >= 45: return "KEEP_TEMPLATE"
    return "QUARANTINE"
def _filter_why(fid, g, sr):
    if g["n"] < 4: return "sample too small"
    if fid.endswith("NO_TRADE"): return f"chop-state; default veto (PF {g['pf']} on tiny n is noise)"
    if "ABSORPTION" in fid: return "reversal-watch / no-short by design"
    if "DISTRIBUTION" in fid and (g["pf"] in (None,) or g["pf"] < 0.9): return f"shorting the bounce LOST (PF {g['pf']}, hit2 {g['hit2_rate']}%)"
    return f"PF {g['pf']}, hit2 {g['hit2_rate']}%, windows {sorted(set(r['window_id'] for r in sr))}"
def _purpose(s): return {"ACTIVE_MARKDOWN": "short-continuation in clean markdown", "DISTRIBUTION_INTO_BOUNCE": "short the failing bounce",
                         "FORCED_UNWIND": "ride liquidation-like acceleration", "ABSORPTION_AFTER_SELL_PRESSURE": "AVOID shorts; reversal watch",
                         "NO_CONTROL_CHOP": "stay flat", "UNKNOWN": "stay flat"}.get(s, "")
def _req_cond(s): return {"ACTIVE_MARKDOWN": ["SHORT", "prior 60m/180m down", "weak bounce", "no bid dominance"],
                          "DISTRIBUTION_INTO_BOUNCE": ["bounce>=0.4%", "ask-heavy depth", "down/flat background"],
                          "FORCED_UNWIND": ["pm60<=-1.5", "activity spike", "thin bid"],
                          "ABSORPTION_AFTER_SELL_PRESSURE": ["bid-heavy depth>0.15", "near recent low", "prior markdown"],
                          "NO_CONTROL_CHOP": ["depth_imb ~0"]}.get(s, [])
def _veto_cond(s): return {"ACTIVE_MARKDOWN": ["bid-heavy depth (absorption)", "spread>8bps"], "DISTRIBUTION_INTO_BOUNCE": ["bid refill", "at recent low"],
                           "FORCED_UNWIND": ["already at low", "blown spread"], "ABSORPTION_AFTER_SELL_PRESSURE": ["fresh down accel"], "NO_CONTROL_CHOP": ["—"]}.get(s, [])
def _when_not(s): return {"ACTIVE_MARKDOWN": "when bid depth dominates (absorption)", "DISTRIBUTION_INTO_BOUNCE": "when bounce holds & bid refills",
                          "FORCED_UNWIND": "when already exhausted at the low", "ABSORPTION_AFTER_SELL_PRESSURE": "never short here", "NO_CONTROL_CHOP": "always (no trade)"}.get(s, "")
def _weak(r, status):
    bits = []
    if r["n_clusters"] < 6: bits.append("small n")
    if r["n_true_td_windows"] < 2: bits.append("only 1 true-TD window")
    bits.append("L2-only (no trade-flow confirmation)")
    return "; ".join(bits)


if __name__ == "__main__":
    sys.exit(main())
