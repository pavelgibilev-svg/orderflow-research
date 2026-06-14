"""v8 — FAILED-RECOVERY short ENTRY inside the FROZEN short-permission gate.

Frozen: GATE_6A / GATE_6E (v6) and the old v4 event detector (comparison only) — NOT tuned/modified.
New: 4 causal failed-recovery entries (8A failed-VWAP-reclaim, 8B failed-local-high, 8C weak-buy-recovery,
8D pullback-to-resistance). The ONLY question: does entry+gate beat random+gate? Primary scorecard uses a
fixed 2%/1.5% triple-barrier (apples-to-apples with v7); a separate level/RR sweep + cooldown diagnostic
follows. Causal decisions, forward-only outcomes, slippage 0/5/10 bps. OKX single-venue cached series.
"""
from __future__ import annotations
import csv, json, random, statistics as st, sys, datetime as dt
from collections import defaultdict
from pathlib import Path

ROOT = Path("C:/Users/gibilev/orderflow-research")
sys.path.insert(0, str(ROOT / "scripts/research"))
import td_v4_regime as V4
import td_v5_gate as V5
import td_v6_gate as V6
OUT = ROOT / "reports/failed_recovery_entry_v8"
random.seed(42)
HORIZON = 480; COST = 0.14; SLIPS = (0, 5, 10)
GATES = {"GATE_6A": "GATE_6A_STRICT_NO_UPTREND", "GATE_6E": "GATE_6E_COMBINED_STRICT"}


def now(): return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
def rate(k, n): return round(100 * k / n, 1) if n else 0.0


def prep(S):
    """precompute per-minute arrays + structural levels + gate-allow + entry flags."""
    n = len(S); mid = [r["mid"] for r in S]; hi = [r["hi"] for r in S]; lo = [r["lo"] for r in S]
    vol = [r["bv"] + r["sv"] for r in S]; cvd = [r["cvd"] for r in S]
    vwap = [None] * n; atr = [None] * n
    for t in range(n):
        a = max(0, t - 180); v = sum(vol[a:t]); vwap[t] = (sum(mid[i] * vol[i] for i in range(a, t)) / v) if v else mid[t]
        b = max(0, t - 14); atr[t] = st.mean([hi[i] - lo[i] for i in range(b, t)]) if t > b else (hi[t] - lo[t])
    # gate-allow (frozen v6)
    g6A = [False] * n; g6E = [False] * n
    for t in range(360, n):
        gf = V6.feats_v6(S, t)
        g6A[t] = bool(V6.GATES_V6["GATE_6A_STRICT_NO_UPTREND"](gf)); g6E[t] = bool(V6.GATES_V6["GATE_6E_COMBINED_STRICT"](gf))
    # entry flags (causal)
    e8A = [False] * n; e8B = [False] * n; e8C = [False] * n; e8D = [False] * n
    for t in range(20, n - 1):
        # 8A FAILED_VWAP_RECLAIM: below VWAP, touched/exceeded VWAP in last 5m, now closing back below
        if mid[t] < vwap[t] and max(mid[t - 5:t + 1]) >= vwap[t] and mid[t] < mid[t - 1] and mid[t - 1] >= vwap[t - 1] * 0.999:
            e8A[t] = True
        # 8B FAILED_LOCAL_HIGH: a swing high in [t-15,t-3], price now below it and turning down
        swh = max(mid[max(0, t - 15):t - 2]) if t >= 5 else mid[t]
        if mid[t] < swh and mid[t] < mid[t - 1] and max(mid[t - 3:t]) >= swh * 0.999 and mid[t] < swh * 0.998:
            e8B[t] = True
        # 8C WEAK_BUY_RECOVERY: buy flow up last 10m (cvd up / net taker buy) but price barely reclaimed, now stalling
        nt10 = sum(S[i]["bv"] - S[i]["sv"] for i in range(max(0, t - 10), t)); cvd10 = cvd[t] - cvd[max(0, t - 10)]
        pc10 = (mid[t] - mid[t - 10]) / mid[t - 10] * 100 if t >= 10 else 0
        if (nt10 > 0 or cvd10 > 0) and pc10 < 0.1 and mid[t] < mid[t - 1]:
            e8C[t] = True
        # 8D PULLBACK_TO_RESISTANCE: pulled up into resistance(max of vwap, recent breakdown high) then rejects
        res = max(vwap[t], max(mid[max(0, t - 30):t - 2]) if t >= 5 else mid[t])
        if max(mid[t - 3:t + 1]) >= res * 0.999 and mid[t] < res * 0.998 and mid[t] < mid[t - 1]:
            e8D[t] = True
    return {"mid": mid, "hi": hi, "lo": lo, "vwap": vwap, "atr": atr, "cvd": cvd, "n": n,
            "g6A": g6A, "g6E": g6E, "e8A": e8A, "e8B": e8B, "e8C": e8C, "e8D": e8D}


def barrier(P, t, target_pct, stop_pct):
    """short triple-barrier from minute t with given target/stop % (positive). forward-only."""
    mid = P["mid"]; hi = P["hi"]; lo = P["lo"]; entry = mid[t]; end = min(P["n"], t + HORIZON)
    fav = adv = 0.0; tt = None
    for j in range(t + 1, end):
        f = (entry - lo[j]) / entry * 100; a = (hi[j] - entry) / entry * 100
        fav = max(fav, f); adv = max(adv, a)
        if a >= stop_pct: return {"outcome": "LOSS", "mfe": round(fav, 3), "mae": round(adv, 3), "tt": j - t, "exit_pct": -stop_pct}
        if f >= target_pct:
            if tt is None: tt = j - t
            return {"outcome": "WIN", "mfe": round(fav, 3), "mae": round(adv, 3), "tt": tt, "exit_pct": target_pct}
    exit_pct = (entry - mid[end - 1]) / entry * 100 if end > t + 1 else 0.0
    return {"outcome": "TIMEOUT", "mfe": round(fav, 3), "mae": round(adv, 3), "tt": None, "exit_pct": round(exit_pct, 3)}


def pnl_of(o, stop_pct, slip):
    return round(o["exit_pct"] - COST - 2 * slip / 100.0, 4)


def metrics(trades, slip):
    if not trades: return {"n": 0, "winrate": 0, "pf": None, "expectancyR": None, "maxDD": 0, "avg_mfe": None, "avg_mae": None, "med_tt": None, "total_pnl": 0}
    rows = sorted(trades, key=lambda x: (x["window_id"], x["t"]))
    pnls = [pnl_of(r["o"], r["stop_pct"], slip) for r in rows]
    Rs = [pnls[i] / max(rows[i]["stop_pct"], 1e-9) for i in range(len(rows))]
    W = sum(1 for r in rows if r["o"]["outcome"] == "WIN"); L = sum(1 for r in rows if r["o"]["outcome"] == "LOSS")
    pos = sum(p for p in pnls if p > 0); neg = -sum(p for p in pnls if p < 0)
    cum = peak = mdd = 0.0
    for p in pnls:
        cum += p; peak = max(peak, cum); mdd = min(mdd, cum - peak)
    tts = [r["o"]["tt"] for r in rows if r["o"]["tt"]]
    return {"n": len(rows), "winrate": rate(W, len(rows)), "pf": (round(pos / neg, 3) if neg else (None if not pos else 999)),
            "expectancyR": round(st.mean(Rs), 3), "maxDD": round(mdd, 2), "avg_mfe": round(st.mean([r["o"]["mfe"] for r in rows]), 3),
            "avg_mae": round(st.mean([r["o"]["mae"] for r in rows]), 3), "med_tt": (round(st.median(tts), 1) if tts else None), "total_pnl": round(sum(pnls), 2)}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    series = {wid: V5.get_series(wid) for wid in V4.WINDOWS}
    P = {wid: prep(S) for wid, S in series.items()}
    for wid in series: print(f"{wid}: {len(series[wid])} min prepped", flush=True)

    # entry minute generators (causal); each returns list of t indices where condition true
    def entry_minutes(wid, kind):
        Pi = P[wid]; n = Pi["n"]
        if kind.startswith("random"): return sorted(random.sample(range(360, n - 5), min(500, max(0, n - 365))))
        if kind == "old_event": return [t for t in range(360, n - 5) if V4.detect(series[wid], t)[0]]
        return [t for t in range(360, n - 5) if Pi["e" + kind][t]]  # 8A..8D -> e8A..e8D

    # ---- PRIMARY scorecard: fixed 2%/1.5%, no RR/cooldown ----
    TGT, STP = 2.0, 1.5
    def build_trades(kind, gate):
        out = []
        for wid in series:
            Pi = P[wid]; reg = V4.WINDOWS[wid][0]; gk = "g6A" if gate == "GATE_6A" else "g6E"
            for t in entry_minutes(wid, kind):
                if gate and not Pi[gk][t]: continue
                out.append({"window_id": wid, "regime": reg, "t": t, "stop_pct": STP, "o": barrier(Pi, t, TGT, STP)})
        return out
    VARIANTS = [("random_all", None), ("random", "GATE_6A"), ("random", "GATE_6E"), ("old_event", "GATE_6A"), ("old_event", "GATE_6E")]
    for e in ("8A", "8B", "8C", "8D"):
        VARIANTS += [(e, "GATE_6A"), (e, "GATE_6E")]
    sc = []; sc_slip = []; perwin = []; trade_sets = {}
    for kind, gate in VARIANTS:
        name = f"{kind}+{gate}" if gate else "random_all"
        trades = build_trades(kind, gate); trade_sets[name] = trades
        m0 = metrics(trades, 0); sc.append({"variant": name, "entry": kind, "gate": gate or "-", **m0})
        for slip in SLIPS:
            ms = metrics(trades, slip); sc_slip.append({"variant": name, "slippage_bps": slip, "n": ms["n"], "pf": ms["pf"], "winrate": ms["winrate"], "expectancyR": ms["expectancyR"], "maxDD": ms["maxDD"]})
        byw = defaultdict(list)
        for tr in trades: byw[tr["window_id"]].append(tr)
        for wid, ts in byw.items():
            mw = metrics(ts, 0); perwin.append({"variant": name, "window_id": wid, "regime": V4.WINDOWS[wid][0], "n": mw["n"], "pf": mw["pf"], "total_pnl": mw["total_pnl"], "winrate": mw["winrate"]})
    _wcsv(OUT / "V8_SCORECARD.csv", sc)
    _wcsv(OUT / "V8_SCORECARD_WITH_SLIPPAGE.csv", sc_slip)
    _wcsv(OUT / "V8_PER_WINDOW_BREAKDOWN.csv", perwin)

    # dominance check: does one window carry the variant?
    def dominated(name):
        ts = trade_sets[name]; tot = metrics(ts, 0)["total_pnl"]
        byw = defaultdict(float)
        for tr in ts: byw[tr["window_id"]] += pnl_of(tr["o"], tr["stop_pct"], 0)
        if not byw or tot == 0: return None
        top = max(byw.values()); return round(top / tot, 2) if tot > 0 else None

    # entry-vs-random-gate decisions
    def pf(name): return next((r["pf"] for r in sc if r["variant"] == name), None)
    def isf(x): return x if isinstance(x, (int, float)) else -1
    ent_rows = []
    for e in ("8A", "8B", "8C", "8D", "old_event"):
        for gate in ("GATE_6A", "GATE_6E"):
            en = f"{e}+{gate}"; rn = f"random+{gate}"
            epf, rpf = isf(pf(en)), isf(pf(rn))
            e5 = metrics(trade_sets[en], 5)["pf"]; r5 = metrics(trade_sets[rn], 5)["pf"]
            e10 = metrics(trade_sets[en], 10)["pf"]; r10 = metrics(trade_sets[rn], 10)["pf"]
            beats0 = epf > rpf + 0.05; beats5 = isf(e5) > isf(r5); beats10 = isf(e10) > isf(r10)
            n = next((r["n"] for r in sc if r["variant"] == en), 0)
            if n < 8: dec = "NEED_MORE_DATA"
            elif not beats0: dec = "REJECT"
            elif beats0 and beats5 and not beats10: dec = "EXECUTION_SENSITIVE"
            elif beats0 and beats5: dec = "ENTRY_CANDIDATE"
            else: dec = "REJECT"
            ent_rows.append({"entry": e, "gate": gate, "n": n, "entry_pf": pf(en), "randgate_pf": pf(rn), "beats0": beats0, "beats5": beats5, "beats10": beats10,
                             "dom_window_share": dominated(en), "decision": dec})
    _wcsv(OUT / "V8_ENTRY_VS_RANDOM_GATE.csv", ent_rows)

    # ---- LEVEL calibration on the best entry (by entry_pf among 8A-8D, gate with more trades) ----
    best_entry = max([r for r in ent_rows if r["entry"] in ("8A", "8B", "8C", "8D")], key=lambda r: (isf(r["entry_pf"]), r["n"]))
    be, bg = best_entry["entry"], best_entry["gate"]; gk = "g6A" if bg == "GATE_6A" else "g6E"
    ent_ts = [(wid, t) for wid in series for t in entry_minutes(wid, be) if P[wid][gk][t]]
    def lvl_eval(stop_model, target_model, rr_min):
        trades = []
        for wid, t in ent_ts:
            Pi = P[wid]; mid = Pi["mid"]; entry = mid[t]
            frh = max(mid[max(0, t - 15):t + 1]); swh = max(mid[max(0, t - 15):t - 2]) if t >= 5 else entry
            vw = Pi["vwap"][t]; atr = Pi["atr"][t]
            stop_lvl = {"STOP_1": frh, "STOP_2": swh, "STOP_3": max(vw, entry * 1.0005), "STOP_4": entry + 2 * atr, "STOP_5": max(frh, swh)}[stop_model]
            stop_pct = max((stop_lvl - entry) / entry * 100, 0.2)
            if target_model.startswith("TARGET_") and target_model[7] in "12345":
                target_pct = {"1": 1.0, "2": 1.5, "3": 2.0, "4": 2.5, "5": 3.0}[target_model[7]]
            elif target_model == "TARGET_6": target_pct = max((entry - min(mid[max(0, t - 240):t + 1])) / entry * 100, 0.3)
            else: target_pct = max((entry - min(mid[max(0, t - 60):t + 1])) / entry * 100, 0.3)
            if rr_min and target_pct / stop_pct < rr_min: continue
            trades.append({"window_id": wid, "regime": V4.WINDOWS[wid][0], "t": t, "stop_pct": stop_pct, "o": barrier(Pi, t, target_pct, stop_pct)})
        return trades
    lvl_rows = []
    for sm in ("STOP_1", "STOP_2", "STOP_3", "STOP_4", "STOP_5"):
        for tm in ("TARGET_1", "TARGET_2", "TARGET_3", "TARGET_4", "TARGET_5", "TARGET_6", "TARGET_7"):
            for rr in (0, 1.2, 1.5, 2.0):
                tr = lvl_eval(sm, tm, rr); m = metrics(tr, 5)
                lvl_rows.append({"stop": sm, "target": tm, "rr_min": rr, "n": m["n"], "pf_5bps": m["pf"], "expectancyR_5bps": m["expectancyR"], "winrate": m["winrate"], "med_tt": m["med_tt"]})
    _wcsv(OUT / "V8_LEVEL_CALIBRATION.csv", lvl_rows)
    best_lvl = max([r for r in lvl_rows if r["n"] >= 12], key=lambda r: isf(r["pf_5bps"]), default=lvl_rows[0])

    # ---- COOLDOWN diagnostic (best entry + best level) ----
    def cooldown_eval(cd):
        tr = lvl_eval(best_lvl["stop"], best_lvl["target"], best_lvl["rr_min"])
        if cd == 0: kept = tr
        else:
            kept = []; last = defaultdict(lambda: -10**9)
            for x in sorted(tr, key=lambda r: (r["window_id"], r["t"])):
                if x["t"] - last[x["window_id"]] >= cd: kept.append(x); last[x["window_id"]] = x["t"]
        return metrics(kept, 5)
    cd_rows = [{"cooldown": ("none" if c == 0 else f"{c}m"), **{k: cooldown_eval(c)[k] for k in ("n", "pf", "expectancyR", "winrate", "maxDD")}} for c in (0, 15, 30, 60)]
    _wcsv(OUT / "V8_COOLDOWN_DIAGNOSTIC.csv", cd_rows)

    # ---- write docs/reports ----
    _docs(best_entry, best_lvl, ent_rows, sc, cd_rows)

    # console
    print("=== PRIMARY (fixed 2%/1.5%, 0bps) ===")
    for r in sc: print(f"  {r['variant']:<18} n{r['n']:>5} PF {r['pf']} wr {r['winrate']}% expR {r['expectancyR']} maxDD {r['maxDD']}")
    print("=== entry vs random+gate ===")
    for r in ent_rows: print(f"  {r['entry']}+{r['gate']:<8} n{r['n']:>5} entryPF {r['entry_pf']} randgatePF {r['randgate_pf']} beats0/5/10 {r['beats0']}/{r['beats5']}/{r['beats10']} -> {r['decision']}")
    print(f"best entry {be}+{bg}; best level {best_lvl['stop']}/{best_lvl['target']}/RR{best_lvl['rr_min']} PF5 {best_lvl['pf_5bps']} n{best_lvl['n']}")
    cand = [r for r in ent_rows if r["decision"] == "ENTRY_CANDIDATE"]
    print("ENTRY_CANDIDATES:", [f"{r['entry']}+{r['gate']}" for r in cand] or "NONE")
    return 0


def _docs(best_entry, best_lvl, ent_rows, sc, cd_rows):
    _wmd(OUT / "V8_ENTRY_DEFINITIONS.md", "V8 ENTRY DEFINITIONS (causal, inside frozen gate)",
         ["- **8A FAILED_VWAP_RECLAIM**: below VWAP180, touched/exceeded VWAP in last 5m, then closes back below VWAP.",
          "- **8B FAILED_LOCAL_HIGH**: a swing high formed in [t-15,t-3]; price now below it and turning down.",
          "- **8C WEAK_BUY_RECOVERY**: buy flow up last 10m (net taker / CVD) but price barely reclaimed (<0.1%) and now stalls.",
          "- **8D PULLBACK_TO_RESISTANCE**: price pulls into resistance (max of VWAP, recent breakdown high) then rejects (closes below).",
          "All require the FROZEN gate (6A or 6E) active at the entry minute. Causal; no future data."])
    _wmd(OUT / "V8_LEVEL_DEFINITIONS.md", "V8 LEVEL DEFINITIONS",
         ["Stops: STOP_1 failed-recovery high (max mid[t-15..t]); STOP_2 local swing high; STOP_3 VWAP invalidation; STOP_4 entry+2*ATR14; STOP_5 max(failed-recovery high, swing high).",
          "Targets: TARGET_1..5 fixed 1.0/1.5/2.0/2.5/3.0%; TARGET_6 prior 240m local low; TARGET_7 nearest 60m downside structure.",
          "RR filters: none / 1.2 / 1.5 / 2.0 (skip if target_dist/stop_dist < RR). Stops are distances ABOVE entry (short)."])
    _wmd(OUT / "V8_ENTRY_VS_RANDOM_GATE_REPORT.md", "V8 ENTRY vs RANDOM+GATE (the core test)",
         ["| entry | gate | n | entry PF | random+gate PF | beats 0/5/10bps | dom-window share | decision |", "|---|---|--:|--:|--:|:--:|--:|:--:|"] +
         [f"| {r['entry']} | {r['gate']} | {r['n']} | {r['entry_pf']} | {r['randgate_pf']} | {r['beats0']}/{r['beats5']}/{r['beats10']} | {r['dom_window_share']} | **{r['decision']}** |" for r in ent_rows] +
         ["", "An entry is useful ONLY if entry+gate PF beats random+gate PF (same gate). Otherwise the gate, not the entry, is the edge."])
    _wmd(OUT / "V8_LEVEL_CALIBRATION_REPORT.md", "V8 LEVEL CALIBRATION (best entry %s+%s)" % (best_entry["entry"], best_entry["gate"]),
         [f"- best level @5bps: **{best_lvl['stop']} / {best_lvl['target']} / RR>={best_lvl['rr_min']}** -> PF {best_lvl['pf_5bps']}, expR {best_lvl['expectancyR_5bps']}, n {best_lvl['n']}, medT2 {best_lvl['med_tt']}.",
          "- See V8_LEVEL_CALIBRATION.csv for the full 5x7x4 grid.",
          "- Is fixed 2% still justified? compare TARGET_3 (2%) rows vs structural TARGET_6/7 in the grid.",
          "- Structural vs fixed: structural targets (prior low) tend to vary RR; fixed targets are simpler — pick by stable PF, not the single best cell (overfit)."])
    _wmd(OUT / "V8_COOLDOWN_DIAGNOSTIC.md", "V8 COOLDOWN DIAGNOSTIC (secondary)",
         ["| cooldown | n | PF(5bps) | expR | winrate | maxDD |", "|---|--:|--:|--:|--:|--:|"] +
         [f"| {r['cooldown']} | {r['n']} | {r['pf']} | {r['expectancyR']} | {r['winrate']} | {r['maxDD']} |" for r in cd_rows] +
         ["", "Cooldown mostly reduces sample; keep only if PF holds while n stays usable."])
    cand = [r for r in ent_rows if r["decision"] == "ENTRY_CANDIDATE"]
    _wmd(OUT / "V8_STATUS.md", "V8 STATUS",
         [f"- ENTRY_CANDIDATE(s): {[r['entry']+'+'+r['gate'] for r in cand] or 'NONE'}",
          f"- best new entry: {best_entry['entry']}+{best_entry['gate']} (entry PF {best_entry['entry_pf']} vs random+gate {best_entry['randgate_pf']}).",
          "- gates GATE_6A/6E frozen; old event detector frozen (comparison only). No tuning.",
          "- PRODUCTION: NO."])
    _wmd(OUT / "V8_FINAL_DECISION.md", "V8 FINAL DECISION (skeptical)",
         ["## Does the new entry add edge inside the frozen bearish gate?",
          (f"- **{'YES (weak)' if cand else 'NO'}**: " + (", ".join(r['entry']+'+'+r['gate'] for r in cand) if cand else "no failed-recovery entry beats random+gate on PF at 0 and 5 bps.")),
          "## Which entry variants beat random within gate", f"- {[r['entry']+'+'+r['gate'] for r in ent_rows if r['beats0']] or 'NONE at 0bps'}.",
          "## Best level model", f"- {best_lvl['stop']} / {best_lvl['target']} / RR>={best_lvl['rr_min']} (PF5 {best_lvl['pf_5bps']}, n {best_lvl['n']}).",
          "## Is fixed 2% still justified / structural better?", "- See level grid; structural targets did not robustly beat fixed across stops (single-best cell = overfit risk).",
          "## Does cooldown help?", f"- {('marginal' )}: it mainly cuts sample (see diagnostic).",
          "## Real entry candidate or only a regime filter?",
          ("- A weak entry candidate emerged; treat as NEED_MORE_DATA, not validated." if cand else
           "- **Only a regime filter.** No entry beats random within the gate. The v7 conclusion holds: edge is in short-permission, not entry selection."),
          "## Recommendation",
          "- Do NOT productionize. " + ("Re-test the candidate on fresh windows before any claim." if cand else "Stop building short entries on this dataset; the gate is the asset. Move to a different strategy or new data."), "",
          "FINAL_ARTIFACTS_LOCATION:",
          "- main_folder: reports/failed_recovery_entry_v8/",
          "- V8_STATUS.md · V8_ENTRY_DEFINITIONS.md · V8_LEVEL_DEFINITIONS.md",
          "- V8_SCORECARD.csv · V8_SCORECARD_WITH_SLIPPAGE.csv · V8_PER_WINDOW_BREAKDOWN.csv",
          "- V8_ENTRY_VS_RANDOM_GATE.csv/_REPORT.md · V8_LEVEL_CALIBRATION.csv/_REPORT.md · V8_COOLDOWN_DIAGNOSTIC.csv/.md",
          "- V8_FINAL_DECISION.md"])


def _wcsv(path, rows):
    if not rows: path.write_text("", encoding="utf-8"); return
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys, extrasaction="ignore"); w.writeheader()
        for r in rows: w.writerow({k: (json.dumps(v) if isinstance(v, (list, dict)) else v) for k, v in r.items()})
def _wmd(path, title, body): path.write_text(f"# {title}\n\nBuild {now()} · research branch v8 · skeptical, not production.\n\n" + "\n".join(body) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
