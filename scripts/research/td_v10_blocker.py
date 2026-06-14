"""v10 — ABSORPTION/ACCUMULATION BLOCKER (diagnostic layer, not optimization, not production).

Adds a CAUSAL blocker on top of frozen GATE_6A / GATE_6E / ENTRY_8A (none modified). Goal: cut false
short-permission in ABSORPTION_REVERSAL / ACCUMULATION_UNDER_PRESSURE / CHOP without killing ACTIVE_MARKDOWN.
No threshold tuning to results: blocker thresholds are fixed interpretable defaults (disclosed). Future
outcome used ONLY in the ex-post diagnostic section, never as a live feature.
"""
from __future__ import annotations
import csv, json, random, sys, datetime as dt, statistics as stats
from collections import defaultdict
from pathlib import Path

ROOT = Path("C:/Users/gibilev/orderflow-research")
sys.path.insert(0, str(ROOT / "scripts/research"))
import td_v4_regime as V4
import td_v5_gate as V5
import td_v8_entry as V8
import td_v9_phase as V9            # reuse the frozen v9 causal phase classifier
OUT = ROOT / "reports/absorption_accumulation_blocker_v10"
random.seed(42)

PHASES = ["TREND_DOWN_ACTIVE_MARKDOWN", "RANGE_DISTRIBUTION_INTO_DEMAND", "TREND_DOWN_ABSORPTION_REVERSAL",
          "RANGE_ACCUMULATION_UNDER_PRESSURE", "LOW_VOL_NO_CONTROL_CHOP", "TREND_UP_NO_SHORT", "UNKNOWN"]
TARGET = ("TREND_DOWN_ACTIVE_MARKDOWN", "RANGE_DISTRIBUTION_INTO_DEMAND")          # keep shorts
BLOCK = ("TREND_DOWN_ABSORPTION_REVERSAL", "RANGE_ACCUMULATION_UNDER_PRESSURE", "LOW_VOL_NO_CONTROL_CHOP")
BLOCKERS = ["b10A", "b10B", "b10C", "b10D", "b10E", "b10F"]


def now(): return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
def rate(k, n): return round(100 * k / n, 1) if n else 0.0


def pf_slip(rows, bps):
    """PF + net R at a slippage level. Base WIN +1.86 / LOSS -1.64 (incl ~14bps cost); slippage adds 2*bps/100 %."""
    w = 1.86 - 2 * bps / 100.0; l = 1.64 + 2 * bps / 100.0
    W = sum(1 for o in rows if o == "WIN"); L = sum(1 for o in rows if o == "LOSS")
    pf = round(W * w / (L * l), 3) if L else (None if not W else 999)
    return pf, round(W * w - L * l, 1), W, L


def blockers(S, P, t):
    """all causal (<=t). Fixed interpretable defaults, NOT tuned to outcomes."""
    mid = P["mid"]; lo = P["lo"]; vwap = P["vwap"]; atr = P["atr"]; cvd = P["cvd"]
    pv = (mid[t] - vwap[t]) / vwap[t] * 100
    ret30 = (mid[t] - mid[t - 30]) / mid[t - 30] * 100
    cvd30 = cvd[t] - cvd[t - 30]
    sv30 = sum(S[i]["sv"] for i in range(t - 30, t)); bv30 = sum(S[i]["bv"] for i in range(t - 30, t))
    sell_frac = sv30 / (sv30 + bv30) if (sv30 + bv30) > 0 else 0.5
    rlow60 = min(mid[t - 60:t])                       # prior 60m low (excl t)
    low_recent = min(lo[t - 10:t + 1])                # intrabar low last 10m
    # F1 PRICE_RESPONSE_TO_SELL_PRESSURE: heavy selling but weak downside
    f1 = (sell_frac >= 0.55 and cvd30 < 0 and ret30 >= -0.10)
    # F2 FAILED_BREAKDOWN: broke prior low intrabar, closed back above it
    f2 = (low_recent < rlow60 and mid[t] > rlow60 * 1.0003)
    # F3 VWAP_RECLAIM_OR_HOLD: at/above VWAP under sell pressure after being below
    below_recent = any(mid[i] < vwap[i] for i in range(t - 15, t))
    f3 = (cvd30 < 0 and pv >= -0.05 and below_recent)
    # F4 LOW_DEFENSE: repeated tests of recent low, no continuation
    touches = sum(1 for i in range(t - 30, t) if lo[i] <= rlow60 * 1.0008)
    f4 = (touches >= 3 and mid[t] > rlow60 * 1.001)
    # F5 CVD_PRICE_DIVERGENCE: CVD new 60m low, price NOT new 60m low
    f5 = (cvd[t] <= min(cvd[t - 60:t]) and mid[t] > min(mid[t - 60:t]) * 1.001)
    # F6 LOW_VOL_CHOP: low ATR + near VWAP + tight range
    look = mid[max(0, t - 180):t + 1]; rng180 = (max(look) - min(look)) / min(look) * 100
    f6 = (atr[t] / mid[t] * 100 < 0.12 and abs(pv) < 0.10 and rng180 < 1.0)
    signs = sum([f1, f2, f3, f4, f5])
    return {"b10A": f1, "b10B": f2, "b10C": f3, "b10D": f5,
            "b10E": signs >= 2, "b10F": (signs >= 1 or f6), "f4": f4, "f6": f6, "signs": signs}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    series = {wid: V5.get_series(wid) for wid in V4.WINDOWS}
    P = {wid: V8.prep(S) for wid, S in series.items()}
    for wid in series: print(f"{wid}: prepped", flush=True)

    # per-minute record
    rec = []
    for wid, S in series.items():
        Pi = P[wid]; n = Pi["n"]
        for t in range(360, n - 65):                  # leave room for 60m forward diagnostic
            ph = V9.phase(S, Pi, t)
            b = blockers(S, Pi, t)
            rec.append({"wid": wid, "t": t, "ph": ph, "g6A": Pi["g6A"][t], "g6E": Pi["g6E"][t], "e8A": Pi["e8A"][t],
                        **{k: b[k] for k in BLOCKERS}})
    print(f"records {len(rec)}", flush=True)

    def short_out(wid, t): return V4.outcome_short(P[wid]["mid"], t, P[wid]["mid"][t])["outcome"]

    # ---- activation before/after per (gate, blocker, phase) ----
    rows_ba = []; fp_rows = []; mk_rows = []; di_rows = []
    for gate in ("g6A", "g6E"):
        for ph in PHASES:
            ph_recs = [r for r in rec if r["ph"] == ph]
            n_ph = len(ph_recs)
            act = [r for r in ph_recs if r[gate]]
            orig = rate(len(act), n_ph)
            row = {"gate": gate, "phase": ph, "minutes": n_ph, "orig_activation_pct": orig, "gate_active_n": len(act)}
            for bk in BLOCKERS:
                kept = [r for r in act if not r[bk]]
                row[f"{bk}_after_pct"] = rate(len(kept), n_ph)
                row[f"{bk}_blocked_of_active_pct"] = rate(len(act) - len(kept), len(act)) if act else 0.0
            rows_ba.append(row)
            # false-permission reduction (blocked phases) / retention (target phases)
            for bk in BLOCKERS:
                kept = [r for r in act if not r[bk]]; after = rate(len(kept), n_ph)
                if ph in BLOCK:
                    fp_rows.append({"gate": gate, "phase": ph, "blocker": bk, "orig_fp_pct": orig, "after_fp_pct": after,
                                    "abs_reduction_pp": round(orig - after, 1), "rel_reduction_pct": rate(orig - after, orig) if orig else 0.0})
                if ph == "TREND_DOWN_ACTIVE_MARKDOWN":
                    mk_rows.append({"gate": gate, "blocker": bk, "orig_activation_pct": orig, "after_activation_pct": after,
                                    "retention_pct": rate(len(kept), len(act)) if act else 0.0, "kept_n": len(kept)})
                if ph == "RANGE_DISTRIBUTION_INTO_DEMAND":
                    di_rows.append({"gate": gate, "blocker": bk, "orig_activation_pct": orig, "after_activation_pct": after,
                                    "retention_pct": rate(len(kept), len(act)) if act else 0.0, "kept_n": len(kept)})
    _wcsv(OUT / "V10_PHASE_ACTIVATION_BEFORE_AFTER.csv", rows_ba)
    _wcsv(OUT / "V10_FALSE_PERMISSION_REDUCTION.csv", fp_rows)
    _wcsv(OUT / "V10_MARKDOWN_RETENTION.csv", mk_rows)
    _wcsv(OUT / "V10_DISTRIBUTION_RETENTION.csv", di_rows)

    # ---- perf before/after: random+gate and 8A+gate, sampled outcomes, all blockers, all slippage ----
    sc_rows = []; e8_rows = []; slip_rows = []; pw_rows = []
    for gate in ("g6A", "g6E"):
        # RANDOM+GATE: sample gate-active minutes per phase, cache outcome once
        for ph in PHASES + ["ALL_VALID_SHORT"]:
            if ph == "ALL_VALID_SHORT":
                pool = [r for r in rec if r[gate] and r["ph"] in TARGET]
            else:
                pool = [r for r in rec if r[gate] and r["ph"] == ph]
            if not pool: continue
            samp = random.sample(pool, min(700, len(pool)))
            outc = {(r["wid"], r["t"]): short_out(r["wid"], r["t"]) for r in samp}
            before = [outc[(r["wid"], r["t"])] for r in samp]
            for bk in BLOCKERS:
                after = [outc[(r["wid"], r["t"])] for r in samp if not r[bk]]
                pf0, net0, W0, L0 = pf_slip(before, 0); pfa, neta, Wa, La = pf_slip(after, 0)
                sc_rows.append({"gate": gate, "phase": ph, "blocker": bk, "n_before": len(before), "n_after": len(after),
                                "pf_before_0bps": pf0, "pf_after_0bps": pfa, "net_before": net0, "net_after": neta,
                                "hit2_before": rate(W0, len(before)), "hit2_after": rate(Wa, len(after))})
                if bk in ("b10E", "b10F") and ph in ("ALL_VALID_SHORT",) + BLOCK:
                    for bps in (0, 5, 10):
                        pb = pf_slip(before, bps); pa = pf_slip(after, bps)
                        slip_rows.append({"gate": gate, "phase": ph, "blocker": bk, "bps": bps,
                                          "pf_before": pb[0], "pf_after": pa[0], "net_before": pb[1], "net_after": pa[1], "n_after": len(after)})
        # 8A+GATE before/after
        for ph in PHASES + ["ALL_VALID_SHORT"]:
            if ph == "ALL_VALID_SHORT":
                pool = [r for r in rec if r[gate] and r["e8A"] and r["ph"] in TARGET]
            else:
                pool = [r for r in rec if r[gate] and r["e8A"] and r["ph"] == ph]
            if not pool: continue
            outc = {(r["wid"], r["t"]): short_out(r["wid"], r["t"]) for r in pool}
            before = [outc[(r["wid"], r["t"])] for r in pool]
            for bk in ("b10E", "b10F"):
                after = [outc[(r["wid"], r["t"])] for r in pool if not r[bk]]
                pf0 = pf_slip(before, 0); pfa = pf_slip(after, 0); pf5 = pf_slip(after, 5)
                e8_rows.append({"gate": gate, "phase": ph, "blocker": bk, "setups_before": len(before), "setups_after": len(after),
                                "pf_before_0": pf0[0], "pf_after_0": pfa[0], "pf_after_5": pf5[0],
                                "hit2_before": rate(pf0[2], len(before)), "hit2_after": rate(pfa[2], len(after)) if after else None})
    _wcsv(OUT / "V10_GATE_SCORECARD_BEFORE_AFTER.csv", sc_rows)
    _wcsv(OUT / "V10_ENTRY_8A_BEFORE_AFTER.csv", e8_rows)
    _wcsv(OUT / "V10_SLIPPAGE_SCORECARD.csv", slip_rows)

    # ---- per-window: where does the headline blocker (g6A + b10E) act? ----
    for wid in series:
        for ph_group, phset in (("BLOCK_phases", BLOCK), ("TARGET_phases", TARGET)):
            act = [r for r in rec if r["wid"] == wid and r["g6A"] and r["ph"] in phset]
            blk = [r for r in act if r["b10E"]]
            pw_rows.append({"window": wid, "phase_group": ph_group, "g6A_active_n": len(act),
                            "b10E_blocked_n": len(blk), "blocked_pct": rate(len(blk), len(act)) if act else 0.0})
    _wcsv(OUT / "V10_PER_WINDOW_BREAKDOWN.csv", pw_rows)

    # ---- ex-post absorption diagnostic (FUTURE outcome — diagnostic only) ----
    def fwd_min_ret(wid, t):
        mid = P[wid]["mid"]; return (min(mid[t + 1:t + 61]) - mid[t]) / mid[t] * 100
    diag = []
    for ph in ["TREND_DOWN_ACTIVE_MARKDOWN", "TREND_DOWN_ABSORPTION_REVERSAL", "RANGE_ACCUMULATION_UNDER_PRESSURE"]:
        act = [r for r in rec if r["g6A"] and r["ph"] == ph]
        fired = [fwd_min_ret(r["wid"], r["t"]) for r in act if r["b10E"]]
        notf = [fwd_min_ret(r["wid"], r["t"]) for r in act if not r["b10E"]]
        diag.append((ph, len(fired), len(notf),
                     round(stats.median(fired), 2) if fired else None,
                     round(stats.median(notf), 2) if notf else None))

    # ---- decision ----
    def fp_after(gate, ph, bk):
        r = next((x for x in fp_rows if x["gate"] == gate and x["phase"] == ph and x["blocker"] == bk), None)
        return r["after_fp_pct"] if r else None
    def mk_ret(gate, bk):
        r = next((x for x in mk_rows if x["gate"] == gate and x["blocker"] == bk), None)
        return r["retention_pct"] if r else None
    def di_ret(gate, bk):
        r = next((x for x in di_rows if x["gate"] == gate and x["blocker"] == bk), None)
        return r["retention_pct"] if r else None
    # pick best phase-behaved blocker on g6A: absorption+accum down, markdown retained
    cands = []
    for bk in BLOCKERS:
        ab = fp_after("g6A", "TREND_DOWN_ABSORPTION_REVERSAL", bk)
        ac = fp_after("g6A", "RANGE_ACCUMULATION_UNDER_PRESSURE", bk)
        mk = mk_ret("g6A", bk); di = di_ret("g6A", bk)
        cands.append((bk, ab, ac, mk, di))
    # headline = b10E unless another clearly dominates; we report all, decide on b10E/b10F
    hb = next(c for c in cands if c[0] == "b10E"); hf = next(c for c in cands if c[0] == "b10F")
    def good(c):  # absorption<20, accum<20, markdown>=35, not blocking everything (markdown ret>distribution-ish)
        return c[1] is not None and c[1] < 20 and c[2] is not None and c[2] < 20 and c[3] is not None and c[3] >= 35
    # one-window dominance for b10E blocks
    blk_by_w = [r["b10E_blocked_n"] for r in pw_rows if r["phase_group"] == "BLOCK_phases"]
    dom = round(max(blk_by_w) / sum(blk_by_w), 2) if sum(blk_by_w) else 0.0
    # ex-post sanity: does b10E fire where forward downside is weaker than non-fire (absorption)?
    expost_ok = all((d[3] is not None and d[4] is not None and d[3] > d[4]) for d in diag if d[0] != "TREND_DOWN_ACTIVE_MARKDOWN")
    chosen = "b10E" if good(hb) else ("b10F" if good(hf) else "b10E")
    cc = hb if chosen == "b10E" else hf
    if good(cc) and dom < 0.6:
        status = "BLOCKER_PROMISING"
    elif good(cc):
        status = "BLOCKER_NEED_MORE_DATA"   # works but one-window dominance / sample
    elif any(good(next(x for x in cands if x[0] == b)) for b in BLOCKERS):
        status = "BLOCKER_NEED_MORE_DATA"
    else:
        status = "BLOCKER_REJECTED"

    _wmd(OUT / "V10_FEATURE_DEFINITIONS.md", "V10 BLOCKER FEATURE DEFINITIONS (causal, fixed defaults)",
         ["All features use minutes <= t only. Thresholds are interpretable defaults, NOT tuned to outcomes.",
          "- F1 PRICE_RESPONSE_TO_SELL_PRESSURE: sell_frac_30m>=0.55 AND cvd_30<0 AND ret_30m>=-0.10% (heavy selling, weak downside).",
          "- F2 FAILED_BREAKDOWN: intrabar low last 10m < prior 60m low, but mid[t] back above that low*1.0003 (breakdown reclaimed).",
          "- F3 VWAP_RECLAIM_OR_HOLD: cvd_30<0 AND price_vs_vwap>=-0.05% AND was below VWAP in last 15m (holds/reclaims VWAP under selling).",
          "- F4 LOW_DEFENSE: >=3 tests of prior 60m low in last 30m AND mid[t]>low*1.001 (defended low). [used inside combined]",
          "- F5 CVD_PRICE_DIVERGENCE: cvd[t] new 60m low BUT mid[t] NOT new 60m low (seller effort, no bearish result).",
          "- F6 LOW_VOL_CHOP: ATR/price<0.12% AND |price_vs_vwap|<0.10% AND range_180m<1.0% (no control). [used inside b10F]",
          "Slippage model: WIN +1.86 / LOSS -1.64 base (incl ~14bps cost); each bps adds 2*bps/100 % to round-trip cost."])
    _wmd(OUT / "V10_BLOCKER_DEFINITIONS.md", "V10 BLOCKER VARIANTS",
         ["Blocker is an ADDITIONAL layer: short_allowed = gate_allow AND NOT blocker_fires. Frozen gates/8A unchanged.",
          "- BLOCKER_10A_ABSORPTION_BASIC = F1.", "- BLOCKER_10B_FAILED_BREAKDOWN = F2.",
          "- BLOCKER_10C_VWAP_RECLAIM = F3.", "- BLOCKER_10D_CVD_PRICE_DIVERGENCE = F5.",
          "- BLOCKER_10E_COMBINED_CONSERVATIVE = (F1+F2+F3+F4+F5 count) >= 2 absorption signs.",
          "- BLOCKER_10F_COMBINED_AGGRESSIVE = any of F1..F5 OR F6 chop.",
          "", "⚠️ CIRCULARITY NOTE: the v9 phase labels for ABSORPTION/ACCUMULATION were themselves defined with"
          " similar 'selling-but-no-new-low' logic, so a blocker built from absorption features will mechanically"
          " fire in those phases. The non-circular evidence is (a) markdown retention staying HIGH and (b) the"
          " ex-post forward-downside diagnostic (the gate has no absorption knowledge)."])
    _wmd(OUT / "V10_EXPOST_ABSORPTION_DIAGNOSTIC.md", "V10 EX-POST ABSORPTION DIAGNOSTIC (future outcome — diagnostic only, NOT a live feature)",
         ["Median forward 60m worst-case downside (most negative ret) for g6A-active minutes, blocker-fire vs not:"] +
         [f"- {d[0]}: b10E FIRES n={d[1]} median_fwd_min {d[3]}%  |  NOT-fire n={d[2]} median_fwd_min {d[4]}%" for d in diag] +
         ["", "Interpretation: if in ABSORPTION/ACCUMULATION the blocker-fire minutes have a LESS negative forward"
          " downside than not-fire minutes, the blocker is catching genuine absorption (price stops falling). In"
          " ACTIVE_MARKDOWN we WANT the opposite ordering / few fires (continuation should remain).",
          f"- ex-post ordering consistent with absorption in blocked phases: {expost_ok}."])
    _wmd(OUT / "V10_BLOCKER_DECISION.md", "V10 BLOCKER DECISION (skeptical)",
         [f"**STATUS: {status}**  (headline blocker: {chosen} on GATE_6A)", "",
          "## Numbers (GATE_6A)",
          f"- ABSORPTION false-permission: orig 40.6% -> after {cc[1]}%  (b10E) / {hf[1]}% (b10F).",
          f"- ACCUMULATION false-permission: orig 28.9% -> after {cc[2]}% (b10E) / {hf[2]}% (b10F).",
          f"- ACTIVE_MARKDOWN retention: {cc[3]}% (b10E) / {hf[3]}% (b10F)  [want >=35%].",
          f"- DISTRIBUTION retention: {cc[4]}% (b10E) / {hf[4]}% (b10F).",
          f"- one-window dominance of b10E blocks (BLOCK phases): {dom} (>=0.6 = concentrated).",
          f"- ex-post absorption ordering holds: {expost_ok}.", "",
          "## Skeptical reading",
          "- Reducing absorption/accumulation activation is PARTLY circular (phase labels share absorption logic). The"
          " honest signals are markdown retention + the ex-post forward-downside test, both reported above.",
          "- All in-sample, single-venue OKX, 1 uptrend window, heuristic phase labels. Per-window dominance and small"
          " n in DISTRIBUTION/ABSORPTION cells make any PF read unreliable — treat PF as diagnostic only.",
          "- This is a SAFER ROUTER, not a validated strategy. No production."])
    nb = "OOS validation + more phase windows" if status in ("BLOCKER_PROMISING", "BLOCKER_NEED_MORE_DATA") else "more phase classifier work"
    _wmd(OUT / "V10_NEXT_BRANCH_RECOMMENDATION.md", "V10 NEXT BRANCH RECOMMENDATION",
         [f"**Recommended next: {nb} — NOT td_l calibration yet.**", "",
          "- If BLOCKER_PROMISING/NEED_MORE_DATA: lock the blocker as a router layer and validate OOS on fresh windows"
          " (and collect a real ACCUMULATION + DISTRIBUTION + 2nd UPTREND window) before any td_l.",
          "- If BLOCKER_REJECTED: the blocker cannot separate absorption from markdown — improve the phase classifier first.",
          "- Do NOT calibrate td_l until absorption/accumulation detection is OOS-validated: a long module anchored on an"
          " in-sample, partly-circular phase boundary would be built on sand.",
          "- 8A stays a TIMING overlay inside ACTIVE_MARKDOWN only; it is not a standalone short entry (v8)."])
    _wmd(OUT / "V10_STATUS.md", "V10 STATUS",
         [f"- STATUS: **{status}** (headline {chosen} on GATE_6A)",
          f"- ABSORPTION false-perm 40.6% -> {cc[1]}% | ACCUMULATION 28.9% -> {cc[2]}%",
          f"- ACTIVE_MARKDOWN retention {cc[3]}% | DISTRIBUTION retention {cc[4]}%",
          f"- one-window dominance {dom} | ex-post absorption ordering {expost_ok}",
          "- causal blocker (no future features); future used only in ex-post diagnostic.",
          "- in-sample, single-venue OKX, 1 uptrend window, partly-circular phase labels. PRODUCTION: NO."])

    # console
    print("=== g6A false-permission after blocker ===")
    for bk in BLOCKERS:
        ab = fp_after("g6A", "TREND_DOWN_ABSORPTION_REVERSAL", bk); ac = fp_after("g6A", "RANGE_ACCUMULATION_UNDER_PRESSURE", bk)
        print(f"  {bk}: absorption 40.6->{ab}%  accum 28.9->{ac}%  markdown_ret {mk_ret('g6A',bk)}%  dist_ret {di_ret('g6A',bk)}%")
    for d in diag: print(f"  expost {d[0]}: fire {d[3]}% vs notfire {d[4]}% (n {d[1]}/{d[2]})")
    print(f"one-window dominance b10E {dom} | expost_ok {expost_ok} | STATUS {status} | chosen {chosen}")
    return 0


def _wcsv(path, rows):
    if not rows: path.write_text("", encoding="utf-8"); return
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys, extrasaction="ignore"); w.writeheader()
        for r in rows: w.writerow(r)
def _wmd(path, title, body):
    path.write_text(f"# {title}\n\nBuild {now()} · absorption/accumulation blocker v10 · skeptical, not production.\n\n" + "\n".join(body) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
