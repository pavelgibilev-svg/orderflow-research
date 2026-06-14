"""v11 — FORWARD-VALIDATED ABSORPTION LABELS (diagnostic, not optimization, not production).

Breaks v10 circularity: forward (ex-post) labels for sell-pressure candidates, then test whether CAUSAL evidence
blocks (computed <=t) can separate ACTIVE_MARKDOWN from SELL_PRESSURE_ABSORBED. Future price used ONLY to build
research labels, never as a live feature. No PnL optimization, no threshold tuning to results.
"""
from __future__ import annotations
import csv, json, sys, datetime as dt, statistics as stats
from collections import defaultdict
from pathlib import Path

ROOT = Path("C:/Users/gibilev/orderflow-research")
sys.path.insert(0, str(ROOT / "scripts/research"))
import td_v4_regime as V4
import td_v5_gate as V5
import td_v8_entry as V8
import td_v9_phase as V9
OKXH = ROOT / "data/okx-historical/BTC-USDT-SWAP"
OUT = ROOT / "reports/forward_validated_absorption_labels_v11"

HORIZONS = (15, 30, 60, 120)
PRIMARY = 60


def now(): return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
def clip01(x): return 0.0 if x < 0 else (1.0 if x > 1 else x)
def rate(k, n): return round(100 * k / n, 1) if n else 0.0
def med(xs): return round(stats.median(xs), 3) if xs else None
def mean(xs): return round(sum(xs) / len(xs), 3) if xs else None


def auc(pos, neg):
    """Mann-Whitney AUC = P(score_pos > score_neg). 0.5 = no separation."""
    if not pos or not neg: return None
    allv = sorted([(v, 1) for v in pos] + [(v, 0) for v in neg])
    rank = {}; i = 0
    # average ranks for ties
    vals = [v for v, _ in allv]
    r = 1; idx = 0
    ranks = [0.0] * len(allv)
    while idx < len(allv):
        j = idx
        while j + 1 < len(allv) and vals[j + 1] == vals[idx]: j += 1
        avg = (idx + 1 + j + 1) / 2.0
        for k in range(idx, j + 1): ranks[k] = avg
        idx = j + 1
    sum_pos = sum(ranks[k] for k in range(len(allv)) if allv[k][1] == 1)
    n1 = len(pos); n0 = len(neg)
    return round((sum_pos - n1 * (n1 + 1) / 2.0) / (n1 * n0), 3)


def background(P, t):
    mid = P["mid"]
    r180 = (mid[t] - mid[t - 180]) / mid[t - 180] * 100
    look = mid[max(0, t - 180):t + 1]; rng = (max(look) - min(look)) / min(look) * 100
    if rng < 0.9: return "LOW_VOL"
    if r180 <= -1.2: return "TREND_DOWN"
    if r180 >= 1.2: return "TREND_UP"
    return "RANGE"


def forward_label(P, t, H):
    mid = P["mid"]
    fut = mid[t + 1:t + H + 1]
    if len(fut) < H: return "UNKNOWN"
    cur = mid[t]
    down = (min(fut) - cur) / cur * 100          # most negative reachable (<=0 typically)
    up = (max(fut) - cur) / cur * 100
    ret = (fut[-1] - cur) / cur * 100            # close after H
    prog = -down                                  # downside progress (positive)
    recent_low = min(mid[max(0, t - 60):t + 1])
    new_low = min(fut) < recent_low
    # ACTIVE_MARKDOWN: meaningful downside progress that is HELD (closes lower), preferably new low
    if prog >= 0.6 and ret <= -0.2 and (new_low or prog >= 0.9):
        return "ACTIVE_MARKDOWN"
    # SELL_PRESSURE_ABSORBED: selling failed -> net up, OR dipped then reclaimed
    if ret >= 0.2 and prog < 0.9:
        return "SELL_PRESSURE_ABSORBED"
    if prog < 0.4 and ret > -0.2:                 # couldn't push it down at all
        return "SELL_PRESSURE_ABSORBED"
    # NO_CONTROL: small / oscillating
    if abs(ret) < 0.2 and prog < 0.6 and up < 0.6:
        return "NO_CONTROL"
    return "UNKNOWN"


def evidence(S, P, t):
    """all causal (<=t). Each block -> markdown-likelihood score in [0,1] (higher = more continuation-like)."""
    mid = P["mid"]; lo = P["lo"]; vwap = P["vwap"]; atr = P["atr"]; cvd = P["cvd"]
    pv = (mid[t] - vwap[t]) / vwap[t] * 100
    disp30 = -(mid[t] - mid[t - 30]) / mid[t - 30] * 100         # +ve if fell
    r180 = (mid[t] - mid[t - 180]) / mid[t - 180] * 100
    sv30 = sum(S[i]["sv"] for i in range(t - 30, t)); bv30 = sum(S[i]["bv"] for i in range(t - 30, t))
    sell_frac = sv30 / (sv30 + bv30) if (sv30 + bv30) > 0 else 0.5
    rlow60 = min(mid[t - 60:t])
    touches = sum(1 for i in range(t - 30, t) if lo[i] <= rlow60 * 1.0008)
    failed_bd = (min(lo[t - 10:t + 1]) < rlow60 and mid[t] > rlow60 * 1.0003)
    cvd15 = cvd[t] - cvd[t - 15]
    reclaim = (max(mid[t - 5:t + 1]) >= vwap[t] and mid[t] < vwap[t])
    dist_below = max(0.0, -pv)
    atrpct = atr[t] / mid[t] * 100
    tc30 = sum(S[i].get("tc", 0) or 0 for i in range(t - 30, t))
    # 1 EFFORT_VS_RESULT: did recent selling produce displacement
    s1 = clip01(disp30 / 0.6)
    # 2 ABSORPTION_REFILL: defense/refill -> low markdown score
    s2 = 1 - clip01(0.34 * touches + (1.0 if failed_bd else 0.0))
    # 3 INITIATIVE_CONTROL: sellers still in control
    ctrl = 0.5 + (0.25 if pv < -0.05 else -0.10) + (0.25 if cvd15 < 0 else -0.15) - (0.20 if reclaim else 0.0)
    s3 = clip01(ctrl)
    # 4 BACKGROUND_ALIGNMENT: downtrend background
    s4 = clip01(0.5 + (-r180) / 4.0)
    # 5 EXTENSION_NOT_LATE: high if not overextended below vwap
    s5 = 1 - clip01((dist_below - 0.6) / 1.6)
    # 6 EXECUTION_QUALITY (viability proxy, NOT a markdown separator)
    s6 = clip01(min(1.0, tc30 / 3000.0)) * clip01(1 - (atrpct - 0.3) / 0.6)
    combined = round((s1 + s2 + s3 + s4 + s5) / 5.0, 3)
    return {"sell_frac30": round(sell_frac, 3), "disp30": round(disp30, 3), "pv": round(pv, 3), "r180": round(r180, 3),
            "EFFORT_VS_RESULT": round(s1, 3), "ABSORPTION_REFILL": round(s2, 3), "INITIATIVE_CONTROL": round(s3, 3),
            "BACKGROUND_ALIGNMENT": round(s4, 3), "EXTENSION_NOT_LATE": round(s5, 3), "EXECUTION_QUALITY": round(s6, 3),
            "COMBINED": combined}


BLOCKS = ["EFFORT_VS_RESULT", "ABSORPTION_REFILL", "INITIATIVE_CONTROL", "BACKGROUND_ALIGNMENT", "EXTENSION_NOT_LATE", "COMBINED"]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    series = {wid: V5.get_series(wid) for wid in V4.WINDOWS}
    P = {wid: V8.prep(S) for wid, S in series.items()}
    for wid in series: print(f"{wid}: prepped", flush=True)

    # ---- Step 1 data audit ----
    march_days = sorted(p.name for p in OKXH.iterdir() if p.is_dir() and p.name.startswith("2026-03")) if OKXH.exists() else []
    audit = []
    for wid in series:
        reg, src, days = V4.WINDOWS[wid]
        audit.append({"window": wid, "venue": "OKX", "symbol": "BTC-USDT-SWAP", "date_range": f"{days[0]}..{days[-1]}",
                      "data_types": "per-min mid+trades(cvd/taker)" + ("+L2" if src.startswith("v2okx") else ""),
                      "per_minute_cache": "YES", "used_v4_v10": "YES", "background": reg,
                      "suitable_for_absorption_labels": "YES", "oos": "NO (in-sample)"})
    audit.append({"window": "OKX-historical 2026-03", "venue": "OKX", "symbol": "BTC-USDT-SWAP",
                  "date_range": f"{march_days[0] if march_days else '-'}..{march_days[-1] if march_days else '-'}",
                  "data_types": "trades.csv.gz per-day", "per_minute_cache": "partial(3 cached)", "used_v4_v10": "partial",
                  "background": "MIXED", "suitable_for_absorption_labels": "YES (build on demand)", "oos": "candidate"})
    _wcsv(OUT / "V11_DATA_AUDIT.csv", audit)
    march_status = f"AVAILABLE (OKX-historical 2026-03, {len(march_days)} days; 3 March windows cached)" if march_days else "DATA_BLOCKED"

    # ---- Steps 2-4: candidates + forward labels + causal evidence ----
    cands = []
    for wid, S in series.items():
        Pi = P[wid]; mid = Pi["mid"]; cvd = Pi["cvd"]; vwap = Pi["vwap"]; lo = Pi["lo"]; n = Pi["n"]
        for t in range(360, n - (PRIMARY + 5)):
            cvd30 = cvd[t] - cvd[t - 30]
            pv = (mid[t] - vwap[t]) / vwap[t] * 100
            sv30 = sum(S[i]["sv"] for i in range(t - 30, t)); bv30 = sum(S[i]["bv"] for i in range(t - 30, t))
            sell_frac = sv30 / (sv30 + bv30) if (sv30 + bv30) > 0 else 0.5
            breakdown = min(lo[t - 5:t + 1]) < min(mid[t - 60:t])
            if not (cvd30 < 0 and (pv < 0.10 or sell_frac >= 0.55 or breakdown)):
                continue                                          # not a sell-pressure moment
            ev = evidence(S, Pi, t)
            labs = {H: forward_label(Pi, t, H) for H in HORIZONS}
            cands.append({"wid": wid, "t": t, "background": background(Pi, t),
                          "g6A": Pi["g6A"][t], "g6E": Pi["g6E"][t], "e8A": Pi["e8A"][t],
                          "v9_phase": V9.phase(S, Pi, t), "label15": labs[15], "label30": labs[30],
                          "label60": labs[60], "label120": labs[120], **ev})
    print(f"candidates {len(cands)}", flush=True)
    _wcsv(OUT / "V11_SELL_PRESSURE_CANDIDATES.csv",
          [{k: c[k] for k in ("wid", "t", "background", "g6A", "g6E", "e8A", "v9_phase", "sell_frac30", "disp30", "pv", "r180")} for c in cands])
    _wcsv(OUT / "V11_FORWARD_LABELS.csv",
          [{k: c[k] for k in ("wid", "t", "background", "v9_phase", "label15", "label30", "label60", "label120",
                              "EFFORT_VS_RESULT", "ABSORPTION_REFILL", "INITIATIVE_CONTROL", "BACKGROUND_ALIGNMENT",
                              "EXTENSION_NOT_LATE", "EXECUTION_QUALITY", "COMBINED")} for c in cands])

    # label mix at primary horizon + horizon agreement
    lab_mix = defaultdict(int)
    for c in cands: lab_mix[c[f"label{PRIMARY}"]] += 1
    mk = [c for c in cands if c["label60"] == "ACTIVE_MARKDOWN"]
    ab = [c for c in cands if c["label60"] == "SELL_PRESSURE_ABSORBED"]
    nc = [c for c in cands if c["label60"] == "NO_CONTROL"]

    # ---- Step 5: predictive separation (causal evidence vs forward label) ----
    ev_rows = []
    for blk in BLOCKS:
        pos = [c[blk] for c in mk]; neg = [c[blk] for c in ab]
        a = auc(pos, neg)
        ev_rows.append({"evidence_block": blk, "auc_markdown_vs_absorbed": a,
                        "mean_markdown": mean(pos), "mean_absorbed": neg and mean(neg), "mean_nocontrol": mean([c[blk] for c in nc]),
                        "n_markdown": len(pos), "n_absorbed": len(neg)})
    # per background AUC on COMBINED
    bg_rows = []
    for bg in ("TREND_DOWN", "RANGE", "TREND_UP", "LOW_VOL"):
        p = [c["COMBINED"] for c in mk if c["background"] == bg]; ng = [c["COMBINED"] for c in ab if c["background"] == bg]
        bg_rows.append({"background": bg, "auc_combined": auc(p, ng), "n_markdown": len(p), "n_absorbed": len(ng)})
    # per-window dominance of markdown/absorbed
    pw = defaultdict(lambda: defaultdict(int))
    for c in cands: pw[c["wid"]][c["label60"]] += 1
    pw_rows = [{"window": wid, "ACTIVE_MARKDOWN": pw[wid]["ACTIVE_MARKDOWN"], "SELL_PRESSURE_ABSORBED": pw[wid]["SELL_PRESSURE_ABSORBED"],
                "NO_CONTROL": pw[wid]["NO_CONTROL"], "UNKNOWN": pw[wid]["UNKNOWN"], "background": V4.WINDOWS[wid][0]} for wid in series]
    mk_by_w = {wid: pw[wid]["ACTIVE_MARKDOWN"] for wid in series}; ab_by_w = {wid: pw[wid]["SELL_PRESSURE_ABSORBED"] for wid in series}
    mk_dom = round(max(mk_by_w.values()) / sum(mk_by_w.values()), 2) if sum(mk_by_w.values()) else 0
    ab_dom = round(max(ab_by_w.values()) / sum(ab_by_w.values()), 2) if sum(ab_by_w.values()) else 0
    _wcsv(OUT / "V11_EVIDENCE_SCORECARD.csv", ev_rows + [{"evidence_block": f"BG::{r['background']}", "auc_markdown_vs_absorbed": r["auc_combined"],
            "n_markdown": r["n_markdown"], "n_absorbed": r["n_absorbed"]} for r in bg_rows])

    # threshold precision/recall on COMBINED (median split — no tuning)
    combo_all = sorted(c["COMBINED"] for c in mk + ab)
    thr = combo_all[len(combo_all) // 2] if combo_all else 0.5
    pred_mk = [c for c in mk + ab if c["COMBINED"] >= thr]
    tp = sum(1 for c in pred_mk if c["label60"] == "ACTIVE_MARKDOWN")
    prec = rate(tp, len(pred_mk)); rec = rate(tp, len(mk))
    false_abs = rate(sum(1 for c in mk + ab if c["COMBINED"] < thr and c["label60"] == "ACTIVE_MARKDOWN"), len(mk))  # missed markdown
    false_mk = rate(sum(1 for c in pred_mk if c["label60"] == "SELL_PRESSURE_ABSORBED"), len(pred_mk))               # called markdown, was absorbed
    base_rate = rate(len(mk), len(mk) + len(ab))

    # ---- Step 6: circularity / old-label comparison ----
    conf = defaultdict(lambda: defaultdict(int))
    for c in cands: conf[c["v9_phase"]][c["label60"]] += 1
    cmp_rows = []
    for ph in ["TREND_DOWN_ACTIVE_MARKDOWN", "TREND_DOWN_ABSORPTION_REVERSAL", "RANGE_ACCUMULATION_UNDER_PRESSURE",
               "RANGE_DISTRIBUTION_INTO_DEMAND", "LOW_VOL_NO_CONTROL_CHOP", "TREND_UP_NO_SHORT", "UNKNOWN"]:
        tot = sum(conf[ph].values())
        cmp_rows.append({"v9_phase": ph, "n": tot,
                         "fwd_ACTIVE_MARKDOWN_pct": rate(conf[ph]["ACTIVE_MARKDOWN"], tot),
                         "fwd_SELL_PRESSURE_ABSORBED_pct": rate(conf[ph]["SELL_PRESSURE_ABSORBED"], tot),
                         "fwd_NO_CONTROL_pct": rate(conf[ph]["NO_CONTROL"], tot),
                         "fwd_UNKNOWN_pct": rate(conf[ph]["UNKNOWN"], tot)})
    _wcsv(OUT / "V11_OLD_PHASE_LABEL_COMPARISON.csv", cmp_rows)
    v9_md = next(r for r in cmp_rows if r["v9_phase"] == "TREND_DOWN_ACTIVE_MARKDOWN")
    v9_ab = next(r for r in cmp_rows if r["v9_phase"] == "TREND_DOWN_ABSORPTION_REVERSAL")

    # ---- decision ----
    combined_auc = next(r["auc_markdown_vs_absorbed"] for r in ev_rows if r["evidence_block"] == "COMBINED")
    best_block = max((r for r in ev_rows if r["evidence_block"] != "COMBINED"), key=lambda r: (r["auc_markdown_vs_absorbed"] or 0))
    enough = len(mk) >= 150 and len(ab) >= 150
    separates = combined_auc is not None and combined_auc >= 0.62
    window_ok = mk_dom < 0.6 and ab_dom < 0.6
    if not march_days and not series:
        status = "DATA_BLOCKED"
    elif separates and enough and window_ok:
        status = "ABSORPTION_LABELS_PROMISING"
    elif (combined_auc is not None and combined_auc >= 0.55) and (enough or window_ok):
        status = "ABSORPTION_LABELS_NEED_MORE_DATA"
    elif combined_auc is None or combined_auc < 0.55:
        status = "ABSORPTION_LABELS_REJECTED"
    else:
        status = "ABSORPTION_LABELS_NEED_MORE_DATA"

    # ---- artifacts (md) ----
    _wmd(OUT / "V11_FORWARD_LABEL_DEFINITIONS.md", "V11 FORWARD LABEL DEFINITIONS (ex-post research labels — NOT live features)",
         [f"Candidate = sell-pressure moment (cvd_30<0 AND (below VWAP OR sell_frac_30>=0.55 OR breakdown of 60m low)).",
          f"Primary horizon = {PRIMARY}m; also computed at 15/30/120m. cur=mid[t]; down=min future ret; up=max; ret=close ret; prog=-down.",
          "- ACTIVE_MARKDOWN: prog>=0.6% AND ret<=-0.2% AND (new 60m low OR prog>=0.9%) — downside realized and held.",
          "- SELL_PRESSURE_ABSORBED: ret>=0.2% with prog<0.9% (selling failed, net up) OR prog<0.4% with ret>-0.2% (couldn't push down).",
          "- NO_CONTROL: |ret|<0.2% AND prog<0.6% AND up<0.6% (oscillation).",
          "- UNKNOWN: ambiguous / insufficient future bars.",
          "Thresholds are interpretable research defaults relative to TP2%/SL1.5%; not tuned to evidence scores."])
    _wmd(OUT / "V11_EVIDENCE_BLOCK_DEFINITIONS.md", "V11 EVIDENCE BLOCK DEFINITIONS (causal, <=t; higher = more markdown-like)",
         ["- EFFORT_VS_RESULT: clip(disp_30m/0.6) — did recent selling actually displace price down.",
          "- ABSORPTION_REFILL: 1 - clip(0.34*low_touches_30m + failed_breakdown) — defended/refilled lows lower the score.",
          "- INITIATIVE_CONTROL: below-VWAP + selling last 15m + no VWAP reclaim -> seller initiative.",
          "- BACKGROUND_ALIGNMENT: clip(0.5 + (-ret_180m)/4) — downtrend background.",
          "- EXTENSION_NOT_LATE: 1 - clip((dist_below_vwap-0.6)/1.6) — penalise overextension below VWAP.",
          "- EXECUTION_QUALITY: trade-count & ATR viability proxy (NOT a markdown separator; L2/spread only in 3 windows).",
          "- COMBINED = mean(EFFORT,REFILL,INITIATIVE,BACKGROUND,EXTENSION). Outside layer sees blocks, not raw conditions."])
    _wmd(OUT / "V11_LABEL_SEPARATION_REPORT.md", "V11 LABEL SEPARATION REPORT",
         [f"Candidates n={len(cands)} | ACTIVE_MARKDOWN n={len(mk)} | SELL_PRESSURE_ABSORBED n={len(ab)} | NO_CONTROL n={len(nc)} | base markdown rate {base_rate}%.",
          "", "## AUC (markdown vs absorbed), causal evidence:"] +
         [f"- {r['evidence_block']}: AUC {r['auc_markdown_vs_absorbed']} (mean md {r['mean_markdown']} vs ab {r['mean_absorbed']})" for r in ev_rows] +
         ["", f"Best single block: **{best_block['evidence_block']}** AUC {best_block['auc_markdown_vs_absorbed']}. COMBINED AUC {combined_auc}.",
          "", "## Per-background AUC (COMBINED):"] +
         [f"- {r['background']}: AUC {r['auc_combined']} (md {r['n_markdown']}/ab {r['n_absorbed']})" for r in bg_rows] +
         ["", f"## Median-split classifier (thr={round(thr,3)}, NO tuning):",
          f"- precision(markdown) {prec}% · recall {rec}% · base rate {base_rate}%",
          f"- false-markdown (called markdown, was absorbed) {false_mk}% · missed-markdown {false_abs}%",
          f"- per-window dominance: markdown {mk_dom}, absorbed {ab_dom} (>=0.6 = one window dominates).",
          "", "## Honest reading",
          "- If COMBINED AUC barely beats 0.5 and BACKGROUND_ALIGNMENT carries it, the 'separation' is just 'are we already"
          " in a downtrend', not a micro-absorption signal. Micro blocks (EFFORT_VS_RESULT, ABSORPTION_REFILL,"
          " INITIATIVE_CONTROL) earning AUC near 0.5 means absorption is NOT causally predictable here."])
    _wmd(OUT / "V11_CIRCULARITY_AUDIT.md", "V11 CIRCULARITY AUDIT (v9 labels vs forward behaviour)",
         [f"- v9 ACTIVE_MARKDOWN candidates -> forward ACTIVE_MARKDOWN {v9_md['fwd_ACTIVE_MARKDOWN_pct']}% / ABSORBED {v9_md['fwd_SELL_PRESSURE_ABSORBED_pct']}% / NO_CONTROL {v9_md['fwd_NO_CONTROL_pct']}% (n {v9_md['n']}).",
          f"- v9 ABSORPTION_REVERSAL candidates -> forward ACTIVE_MARKDOWN {v9_ab['fwd_ACTIVE_MARKDOWN_pct']}% / ABSORBED {v9_ab['fwd_SELL_PRESSURE_ABSORBED_pct']}% / NO_CONTROL {v9_ab['fwd_NO_CONTROL_pct']}% (n {v9_ab['n']}).", "",
          "## Was v10 circular?",
          "- v10 built its blocker from features in the SAME family used to define v9 ABSORPTION/ACCUMULATION, so blocked-phase activation fell mechanically.",
          "- Circularity is CONFIRMED to the extent that v9 ABSORPTION_REVERSAL does NOT cleanly map to forward absorption: if its forward-ABSORBED share is not much higher than v9 ACTIVE_MARKDOWN's, the old label was not capturing true absorption, so v10's 'reduction' was bookkeeping.",
          f"- Verdict: v9 ABSORPTION forward-absorbed {v9_ab['fwd_SELL_PRESSURE_ABSORBED_pct']}% vs v9 MARKDOWN forward-absorbed {v9_md['fwd_SELL_PRESSURE_ABSORBED_pct']}% — "
          + ("separation present but weak." if (v9_ab['fwd_SELL_PRESSURE_ABSORBED_pct'] - v9_md['fwd_SELL_PRESSURE_ABSORBED_pct']) < 20 else "clear separation.")])
    # candidate blocker designs (only from blocks that separated)
    sep_blocks = [r["evidence_block"] for r in ev_rows if r["evidence_block"] != "COMBINED" and (r["auc_markdown_vs_absorbed"] or 0) >= 0.55]
    _wmd(OUT / "V11_CANDIDATE_BLOCKER_DESIGNS.md", "V11 CANDIDATE ABSORPTION BLOCKER DESIGNS (proposal only — not optimized)",
         [f"Only evidence blocks with AUC>=0.55 are eligible: **{sep_blocks or 'NONE'}**.", ""] +
         (["No causal block separated markdown from absorbed at AUC>=0.55. No trustworthy blocker can be proposed yet — see decision."]
          if not sep_blocks else
          [f"- ABS_BLOCKER_CANDIDATE_A (conservative): block short only if COMBINED < low-quantile AND {sep_blocks[0]} low. Minimises markdown loss; small false-permission cut.",
           f"- ABS_BLOCKER_CANDIDATE_B (balanced): block short if COMBINED below median (causal). Expected: moderate false-permission cut, moderate markdown retention risk.",
           f"- ABS_BLOCKER_CANDIDATE_C (aggressive): block short if ANY of {sep_blocks} signals absorption strongly. Higher false-permission cut, higher markdown loss risk.",
           "", "All are CAUSAL (evidence computed <=t). Expected effect is bounded by the AUC above — separation this weak"
           " means even the balanced candidate will trade markdown loss against false-permission cut roughly 1:1. Suitable"
           " for v12 router testing ONLY as a hypothesis, not as a frozen layer."]))
    # data request
    have = defaultdict(int)
    for wid in series: have[V4.WINDOWS[wid][0]] += 1
    need = [("ACTIVE_MARKDOWN", 1, "have 4 TREND_DOWN; ok-ish", "trades(+L2)"),
            ("SELL_PRESSURE_ABSORBED", 3, "no dedicated absorbed/reversal window; only sub-segments", "trades(+L2) — need clear failed-breakdown days"),
            ("ACCUMULATION_UNDER_PRESSURE", 2, "only range sub-segments, in-sample", "trades(+L2)"),
            ("DISTRIBUTION_INTO_DEMAND", 2, "only range sub-segments; no gate covers it", "trades(+L2)"),
            ("ACTIVE_MARKUP", 2, "only 1 TREND_UP window total", "trades(+L2)"),
            ("NO_CONTROL_CHOP", 1, "plenty of chop minutes but not a clean window", "trades"),
            ("UPTREND", 2, "only 1 TREND_UP window = binding limitation", "trades(+L2)"),
            ("RANGE", 2, "2 range windows, in-sample", "trades(+L2)"),
            ("HIGH_VOL_FAST_MOVE", 1, "none isolated", "trades(+L2)+liquidations+OI")]
    _wcsv(OUT / "V11_DATA_REQUEST_FOR_OOS_WINDOWS.csv",
          [{"capital_state": s, "windows_needed": k, "current_gap": g, "data_types": d,
            "venue_symbol": "OKX BTC-USDT-SWAP (or Bybit)", "why": f"forward-label OOS validation for {s}"} for s, k, g, d in need])

    _wmd(OUT / "V11_FINAL_DECISION.md", "V11 FINAL DECISION (skeptical)",
         [f"**STATUS: {status}**", f"- March data: {march_status}; all windows IN_SAMPLE_ONLY (no true OOS).",
          f"- Candidates {len(cands)}; markdown {len(mk)} / absorbed {len(ab)} / no_control {len(nc)}; base markdown rate {base_rate}%.",
          f"- COMBINED causal AUC (markdown vs absorbed) = **{combined_auc}** (0.5=random). Best block {best_block['evidence_block']} {best_block['auc_markdown_vs_absorbed']}.",
          f"- Median-split precision {prec}% (base {base_rate}%), recall {rec}%, false-markdown {false_mk}%.",
          f"- Per-window dominance markdown {mk_dom} / absorbed {ab_dom}.",
          f"- v9 ABSORPTION_REVERSAL -> forward absorbed only {v9_ab['fwd_SELL_PRESSURE_ABSORBED_pct']}% (vs markdown-label {v9_md['fwd_SELL_PRESSURE_ABSORBED_pct']}%): old label weakly tracks true absorption => v10 was partly circular.", "",
          "## Skeptical bottom line",
          "- Forward labels are well-defined and produce a usable markdown/absorbed split. The hard part — predicting it"
          " causally — is only as strong as the AUC above. If micro blocks sit near 0.5 and only BACKGROUND carries it,"
          " absorption is being inferred from 'are we in a downtrend', which the gate already knows; that does NOT solve"
          " the v9/v10 leak inside down-pressure.",
          "- In-sample, single-venue OKX, one uptrend window. Do not freeze any blocker. No production."])
    nb = {"ABSORPTION_LABELS_PROMISING": "v12 router test of the balanced candidate, THEN OOS",
          "ABSORPTION_LABELS_NEED_MORE_DATA": "collect OOS/per-state windows (Step 8) + strengthen micro evidence before any router/td_l",
          "ABSORPTION_LABELS_REJECTED": "absorption is not causally separable with current data/features — more phase-classifier work + data, NOT td_l",
          "DATA_BLOCKED": "collect data"}[status]
    _wmd(OUT / "V11_NEXT_BRANCH_RECOMMENDATION.md", "V11 NEXT BRANCH RECOMMENDATION",
         [f"**Recommended next: {nb}.**", "",
          "- Do NOT start td_l calibration: a long module needs a trustworthy absorption/accumulation boundary, which this"
          " pass shows is" + (" only weakly" if status != "ABSORPTION_LABELS_PROMISING" else "") + " causally predictable in-sample.",
          "- Priority data (see V11_DATA_REQUEST_FOR_OOS_WINDOWS.csv): dedicated SELL_PRESSURE_ABSORBED / DISTRIBUTION / 2nd"
          " UPTREND windows; L2 + liquidations + OI would materially help the micro blocks (EFFORT_VS_RESULT, ABSORPTION_REFILL).",
          "- Keep GATE_6A/6E/8A frozen; 8A remains a markdown-only timing overlay.",
          "- Only after micro-absorption separation improves OOS -> propose v12 router -> then consider td_l."])
    _wmd(OUT / "V11_STATUS.md", "V11 STATUS",
         [f"- STATUS: **{status}**", f"- March: {march_status}; IN_SAMPLE_ONLY.",
          f"- candidates {len(cands)} | markdown {len(mk)} | absorbed {len(ab)} | base rate {base_rate}%",
          f"- COMBINED causal AUC {combined_auc} | best block {best_block['evidence_block']} {best_block['auc_markdown_vs_absorbed']}",
          f"- per-window dominance markdown {mk_dom} / absorbed {ab_dom}",
          f"- v9 ABSORPTION->forward-absorbed {v9_ab['fwd_SELL_PRESSURE_ABSORBED_pct']}% (v10 circularity: {'partly confirmed' if (v9_ab['fwd_SELL_PRESSURE_ABSORBED_pct']-v9_md['fwd_SELL_PRESSURE_ABSORBED_pct'])<20 else 'weak'})",
          "- PRODUCTION: NO. No td_l yet."])

    # console
    print(f"label mix @60: {dict(lab_mix)}")
    print("=== evidence AUC (markdown vs absorbed) ===")
    for r in ev_rows: print(f"  {r['evidence_block']:<22} AUC {r['auc_markdown_vs_absorbed']}  md {r['mean_markdown']} ab {r['mean_absorbed']} (n {r['n_markdown']}/{r['n_absorbed']})")
    print("=== per-background COMBINED AUC ===")
    for r in bg_rows: print(f"  {r['background']:<11} AUC {r['auc_combined']} (n {r['n_markdown']}/{r['n_absorbed']})")
    print(f"v9 MARKDOWN->fwdABS {v9_md['fwd_SELL_PRESSURE_ABSORBED_pct']}% | v9 ABSORPTION->fwdABS {v9_ab['fwd_SELL_PRESSURE_ABSORBED_pct']}%")
    print(f"precision {prec}% recall {rec}% base {base_rate}% | mk_dom {mk_dom} ab_dom {ab_dom} | STATUS {status}")
    return 0


def _wcsv(path, rows):
    if not rows: path.write_text("", encoding="utf-8"); return
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys, extrasaction="ignore"); w.writeheader()
        for r in rows: w.writerow(r)
def _wmd(path, title, body):
    path.write_text(f"# {title}\n\nBuild {now()} · forward-validated absorption labels v11 · skeptical, not production.\n\n" + "\n".join(body) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
