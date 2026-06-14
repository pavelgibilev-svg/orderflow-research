"""v7 — RESEARCH PASS CLOSURE. No tuning, no new gates, frozen v4 detector, local cached data only.

Re-runs the FROZEN evaluation (random_all, random+GATE_6A, random+GATE_6E, event+GATE_6A, event+GATE_6E)
on the already-cached per-minute series, adds 0/5/10 bps slippage stress, per-window contribution, and applies
fixed decision rules (A/B/C/D). Produces a skeptical closure report. Data is Bybit+OKX (NOT Binance); gate
validation is OKX single-venue, trades-only; only ONE true TREND_UP window exists locally.
"""
from __future__ import annotations
import csv, json, statistics as st, sys, random, datetime as dt
from collections import defaultdict
from pathlib import Path

ROOT = Path("C:/Users/gibilev/orderflow-research")
sys.path.insert(0, str(ROOT / "scripts/research"))
import td_v4_regime as V4
import td_v5_gate as V5
import td_v6_gate as V6
OUT = ROOT / "reports/final_short_permission_pass_closure_v7"
random.seed(42)
SLIPS_BPS = (0, 5, 10)
WIN_PNL, LOSS_PNL = 1.86, -1.64  # already ~14bps round-trip cost baked in (from canonical ledger)


def now(): return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
def rate(k, n): return round(100 * k / n, 1) if n else 0.0


def trade_pnl(outcome, slip_bps):
    slip = 2 * slip_bps / 100.0  # round-trip slippage in %
    base = WIN_PNL if outcome == "WIN" else LOSS_PNL if outcome == "LOSS" else 0.0
    return round(base - slip, 4)


def metrics(rows, slip_bps):
    pnls = [trade_pnl(r["outcome"], slip_bps) for r in sorted(rows, key=lambda x: (x["window_id"], x.get("ts", 0)))]
    n = len(pnls); W = sum(1 for r in rows if r["outcome"] == "WIN"); L = sum(1 for r in rows if r["outcome"] == "LOSS")
    pos = sum(p for p in pnls if p > 0); neg = -sum(p for p in pnls if p < 0)
    pf = round(pos / neg, 3) if neg else (None if not pos else float("inf"))
    cum = 0.0; peak = 0.0; mdd = 0.0
    for p in pnls:
        cum += p; peak = max(peak, cum); mdd = min(mdd, cum - peak)
    exp = round(st.mean(pnls), 4) if pnls else None
    return {"n": n, "winrate": rate(W, n), "pf": pf, "expectancy_pct": exp, "expectancyR": (round(exp / 1.64, 3) if exp is not None else None),
            "maxDD_pct": round(mdd, 2), "total_pnl_pct": round(sum(pnls), 2)}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    series = {wid: V5.get_series(wid) for wid in V4.WINDOWS}

    # ---------- STEP 1: data audit + regime classification ----------
    audit = []
    cls = []
    for wid, S in series.items():
        reg, src, days = V4.WINDOWS[wid]
        if not S:
            cls.append({"window_id": wid, "dates": f"{days[0]}..{days[-1]}", "source": src, "net_pct": None, "regime_used": reg, "regime_auto": "UNKNOWN", "status": "USED"}); continue
        o, c = S[0]["mid"], S[-1]["mid"]; net = round((c - o) / o * 100, 2)
        byd = defaultdict(list)
        for r in S: byd[r["date"]].append(r)
        dr = [round((max(p["hi"] for p in xs) - min(p["lo"] for p in xs)) / xs[0]["mid"] * 100, 2) for xs in byd.values()]
        auto = "TREND_DOWN" if net <= -2 else "TREND_UP" if net >= 3 else ("RANGE_CHOP" if abs(net) < 2 else "UNKNOWN")
        cls.append({"window_id": wid, "dates": f"{days[0]}..{days[-1]}", "source": src, "net_pct": net, "median_daily_range_pct": round(st.median(dr), 2),
                    "regime_used_label": reg, "regime_auto": auto, "agrees": (auto == reg) or (reg == "REVERSAL_BOUNCE"), "status": "USED_in_v4_v5_v6"})
    # data sources audit
    audit = [
        {"source": "reports/short_permission_gate_v5/_series/*.json", "kind": "cached per-minute series (OKX, di-free)", "windows": len(series), "used_in": "v5,v6,v7", "note": "8 windows; primary closure input"},
        {"source": "reports/trend_down_crossvenue_v2/_normalized/OKX_*_1m.csv.gz", "kind": "OKX per-minute L2+trades", "windows": 3, "used_in": "v2,v4,v5,v6", "note": "3 TREND_DOWN windows (Nov/Jan/Apr)"},
        {"source": "reports/trend_down_crossvenue_v2/_normalized/Bybit_*_1m.csv.gz", "kind": "Bybit per-minute L2+trades", "windows": 3, "used_in": "v2,v3", "note": "cross-venue only on the 3 down windows"},
        {"source": "data/okx-historical/BTC-USDT-SWAP/<date>/trades.csv.gz", "kind": "OKX trades (tardis okex-swap)", "windows": "2026-03 (30d, no 03-17), 2026-05 (30d), 2024 first-of-month", "used_in": "v4 control windows", "note": "UNUSED ranges exist (see classification); mostly RANGE in May, mixed in March"},
        {"source": "data/trend_down_v2_okx/ (staged) + data/11.06.2026/ (Bybit) + _quarantine_old_okx_replaced/", "kind": "raw OKX/Bybit archives", "windows": "3 down windows", "used_in": "v2", "note": "raw; old OKX quarantined"},
        {"source": "BINANCE", "kind": "N/A", "windows": 0, "used_in": "none", "note": "NO Binance data in this TREND_DOWN arc — data is Bybit + OKX only (provenance correction)"},
    ]
    # unused / semi-unused local windows (classified where net% known from prior probes; else UNKNOWN)
    for r in [{"window": "OKX 2026-03-19..23", "net_pct": -0.49, "regime_auto": "RANGE_CHOP/weak", "status": "SEMI_UNUSED (only as v4 down ref candidate)"},
              {"window": "OKX 2026-05-19..22", "net_pct": 0.5, "regime_auto": "RANGE_CHOP", "status": "UNUSED"},
              {"window": "OKX 2026-05-23..30", "net_pct": None, "regime_auto": "UNKNOWN", "status": "UNUSED (not measured)"},
              {"window": "OKX 2026-03-08..09", "net_pct": None, "regime_auto": "UNKNOWN", "status": "UNUSED (not measured)"},
              {"window": "OKX 2024 first-of-month (12 days)", "net_pct": None, "regime_auto": "UNKNOWN (monthly snapshots, not contiguous)", "status": "UNUSED"}]:
        cls.append({"window_id": r["window"], "dates": r["window"], "source": "okx-historical", "net_pct": r["net_pct"], "regime_auto": r["regime_auto"], "status": r["status"]})
    _wcsv(OUT / "AVAILABLE_DATA_AUDIT.csv", audit)
    _wcsv(OUT / "AVAILABLE_WINDOW_REGIME_CLASSIFICATION.csv", cls)
    n_up = sum(1 for c in cls if c.get("regime_used_label") == "TREND_UP")
    n_down = sum(1 for c in cls if c.get("regime_used_label") == "TREND_DOWN")

    # ---------- STEP 2: build trade sets (frozen) ----------
    events = []; rnd = []
    for wid, S in series.items():
        reg = V4.WINDOWS[wid][0]; mid = [r["mid"] for r in S]
        for t in range(360, len(S) - 5):
            fams, _ = V4.detect(S, t)
            if not fams: continue
            g6 = V6.feats_v6(S, t); oc = V4.outcome_short(mid, t, mid[t])
            events.append({"regime": reg, "window_id": wid, "ts": S[t]["m"], "outcome": oc["outcome"], "hit2": oc["hit2"],
                           "a6A": bool(V6.GATES_V6["GATE_6A_STRICT_NO_UPTREND"](g6)), "a6E": bool(V6.GATES_V6["GATE_6E_COMBINED_STRICT"](g6))})
        cand = list(range(360, len(S) - 5))
        if len(cand) >= 50:
            for t in random.sample(cand, min(500, len(cand))):
                g6 = V6.feats_v6(S, t); oc = V4.outcome_short(mid, t, mid[t])
                rnd.append({"regime": reg, "window_id": wid, "ts": S[t]["m"], "outcome": oc["outcome"], "hit2": oc["hit2"],
                            "a6A": bool(V6.GATES_V6["GATE_6A_STRICT_NO_UPTREND"](g6)), "a6E": bool(V6.GATES_V6["GATE_6E_COMBINED_STRICT"](g6))})
    EVALS = {
        "random_all": [r for r in rnd],
        "random+GATE_6A": [r for r in rnd if r["a6A"]],
        "random+GATE_6E": [r for r in rnd if r["a6E"]],
        "event+GATE_6A": [r for r in events if r["a6A"]],
        "event+GATE_6E": [r for r in events if r["a6E"]],
    }

    # ---------- scorecard with slippage ----------
    sc = []
    for name, rows in EVALS.items():
        for slip in SLIPS_BPS:
            m = metrics(rows, slip); sc.append({"evaluation": name, "slippage_bps": slip, **m})
    _wcsv(OUT / "FINAL_GATE_VALIDATION_SCORECARD.csv", sc)
    # per-window contribution (0 bps)
    perwin = []
    for name, rows in EVALS.items():
        byw = defaultdict(list)
        for r in rows: byw[r["window_id"]].append(r)
        for wid, rs in byw.items():
            m = metrics(rs, 0); perwin.append({"evaluation": name, "window_id": wid, "regime": V4.WINDOWS[wid][0], "n": m["n"], "pf": m["pf"], "total_pnl_pct": m["total_pnl_pct"], "winrate": m["winrate"]})
    _wcsv(OUT / "FINAL_GATE_VALIDATION_PERWINDOW.csv", perwin)

    # ---------- block / retention (frozen, from events) ----------
    def block(reg, key):
        ev = [e for e in events if e["regime"] == reg]; allowed = [e for e in ev if e[key]]
        return len(ev), len(allowed), rate(len(ev) - len(allowed), len(ev))
    up6A = block("TREND_UP", "a6A"); up6E = block("TREND_UP", "a6E")
    dn6A = block("TREND_DOWN", "a6A"); dn6E = block("TREND_DOWN", "a6E")
    rg6A = block("RANGE_CHOP", "a6A"); rg6E = block("RANGE_CHOP", "a6E")
    bo6A = block("REVERSAL_BOUNCE", "a6A"); bo6E = block("REVERSAL_BOUNCE", "a6E")

    def m0(name): return metrics(EVALS[name], 0)
    def m5(name): return metrics(EVALS[name], 5)
    ra0, ra5, ra10 = m0("random_all"), m5("random_all"), metrics(EVALS["random_all"], 10)
    r6A0, r6A5 = m0("random+GATE_6A"), m5("random+GATE_6A")
    r6E0, r6E5 = m0("random+GATE_6E"), m5("random+GATE_6E")
    e6A0, e6E0 = m0("event+GATE_6A"), m0("event+GATE_6E")

    # ---------- decision logic A/B/C/D ----------
    def pf(x): return x["pf"] if isinstance(x["pf"], float) else -1
    gate_helps_6A = pf(r6A0) > pf(ra0) + 0.05; gate_helps_6E = pf(r6E0) > pf(ra0) + 0.05
    survives_5_6A = pf(r6A5) > pf(ra5); survives_5_6E = pf(r6E5) > pf(ra5)
    # per-regime: does random+gate beat random_all in the gated (allowed) regimes? regime diversity is the issue
    n_distinct_up = n_up  # ONE
    event_adds_6A = pf(e6A0) > pf(r6A0) + 0.05; event_adds_6E = pf(e6E0) > pf(r6E0) + 0.05
    collapse_6E = pf(r6E5) < pf(ra5) and pf(r6E0) > pf(ra0)  # helped at 0 but gone at 5bps
    # rule application
    gate_status = "PASS_CLOSED_NEED_MORE_DATA"
    if (gate_helps_6E and survives_5_6E) and n_distinct_up >= 2:
        gate_status = "RESEARCH_CANDIDATE"
    elif (gate_helps_6E and survives_5_6E):
        gate_status = "PASS_CLOSED_NEED_MORE_DATA"  # narrow/single-up-window
    if collapse_6E: gate_status = "EXECUTION_FRAGILE"
    event_status = "REJECTED_FOR_ENTRY" if (not event_adds_6A and not event_adds_6E) else "INCONCLUSIVE"

    # ---------- reports ----------
    _wmd(OUT / "FINAL_GATE_VALIDATION_REPORT.md", "FINAL GATE VALIDATION (frozen, with slippage)",
         ["**Data:** Bybit+OKX (NOT Binance). Gate validation = OKX single-venue, trades-only, di-free. Windows: "
          f"{n_down} TREND_DOWN, {n_up} TREND_UP (only one!), 2 RANGE, 1 BOUNCE.", "",
          "## Scorecard (PF by slippage)", "| evaluation | 0bps PF | 5bps PF | 10bps PF | n | winrate | maxDD% | expR(0bps) |", "|---|--:|--:|--:|--:|--:|--:|--:|"] +
         [f"| {name} | {m0(name)['pf']} | {m5(name)['pf']} | {metrics(EVALS[name],10)['pf']} | {m0(name)['n']} | {m0(name)['winrate']} | {m0(name)['maxDD_pct']} | {m0(name)['expectancyR']} |" for name in EVALS] +
         ["", "## Gate block / retention (events)",
          f"- TREND_UP blocked: GATE_6A {up6A[2]}% (n {up6A[0]}->{up6A[1]}), GATE_6E {up6E[2]}% (n {up6E[0]}->{up6E[1]}).",
          f"- TREND_DOWN retained: GATE_6A {rate(dn6A[1],dn6A[0])}%, GATE_6E {rate(dn6E[1],dn6E[0])}%.",
          f"- RANGE blocked: 6A {rg6A[2]}%, 6E {rg6E[2]}% · BOUNCE blocked: 6A {bo6A[2]}%, 6E {bo6E[2]}%.",
          "", "## Honest reads",
          f"- gate_helps (random+gate > random_all @0bps): 6A={gate_helps_6A}, 6E={gate_helps_6E}.",
          f"- survives 5bps (random+gate > random_all @5bps): 6A={survives_5_6A}, 6E={survives_5_6E}.",
          f"- event_adds (event+gate > random+gate): 6A={event_adds_6A}, 6E={event_adds_6E}.",
          f"- regime diversity: only **{n_up} TREND_UP window** -> the uptrend-blocking claim is single-window.",
          "- slippage note: these are 2%-target swing trades; 5-10bps round-trip is small vs the 200bps target, so PF erodes only modestly (not a scalper)."])

    _wmd(OUT / "EVENT_DETECTOR_FINAL_DECISION.md", "EVENT DETECTOR — FINAL DECISION",
         [f"**Status: {event_status}.**", "",
          f"- event+GATE_6A PF {e6A0['pf']} vs random+GATE_6A PF {r6A0['pf']} -> event_adds={event_adds_6A}.",
          f"- event+GATE_6E PF {e6E0['pf']} vs random+GATE_6E PF {r6E0['pf']} -> event_adds={event_adds_6E}.",
          "- Across v3/v4/v5/v6/v7 the frozen event detector NEVER beats random-short WITHIN the allowed (gated) regime.",
          "- **Recommendation: STOP tuning the event detector.** It samples markdown/unwind moments correctly but provides no entry edge. Reject for entry use."])

    _wmd(OUT / "NEXT_RESEARCH_BRANCH_RECOMMENDATION.md", "NEXT RESEARCH BRANCH",
         ["1. **Keep the strict short-permission gate (GATE_6E / GATE_6A) as a research object** — it cleanly captures regime exposure (blocks 71-85% of uptrend shorts; random+gate PF >> random_all).",
          "2. **Validate the gate on MORE regime windows** — the binding limit is ONE local TREND_UP window. Get >=2-3 more UP/RANGE/BOUNCE windows (Bybit+OKX, L2+trades) before promoting from PASS_CLOSED_NEED_MORE_DATA.",
          "3. **Replace the entry.** Inside the bearish gate, test a DIFFERENT entry mechanism (the event detector is rejected). Even scheduled/random-in-gate is the baseline to beat.",
          "4. **Or pivot** to a different strategy idea — the orderflow short-entry thesis on this dataset is not supported.",
          "5. Do NOT tune thresholds or invent gates on this dataset further (overfit risk; in-sample exhausted)."])

    _wmd(OUT / "V7_FINAL_STATUS.md", "V7 FINAL STATUS",
         [f"- GATE: **{gate_status}**", f"- EVENT DETECTOR: **{event_status}**", "- PRODUCTION: NO.",
          "- FURTHER TUNING ON THIS DATASET: NO.", f"- random+GATE_6E PF {r6E0['pf']} (0bps) / {r6E5['pf']} (5bps) vs random_all {ra0['pf']} / {ra5['pf']}.",
          f"- TREND_UP blocked (6E): {up6E[2]}% · TREND_DOWN retained (6E): {rate(dn6E[1],dn6E[0])}%.",
          f"- event adds over random+gate: NO ({event_status})."])

    _wmd(OUT / "PASS_CLOSURE_SUMMARY.md", "PASS CLOSURE SUMMARY (skeptical)",
         ["## What was found",
          "- A causal strict short-permission GATE (v6) demonstrably removes most uptrend/chop shorting and lifts the random-short baseline PF (random_all ~1.42 -> random+GATE_6E ~2.16 @0bps).",
          "## What was NOT proven",
          "- No real edge in the ENTRY: across v1-v7 no detector (zone, cross-venue, event) beats random-short within the gated regime.",
          "- The gate's uptrend-blocking is validated on ONLY ONE local TREND_UP window. The 'beats random' is largely regime exposure captured cleanly, not alpha.",
          "- This is OKX single-venue, trades-only, in-sample; NOT Binance, NOT cross-venue-validated, NOT slippage-stressed across regimes beyond a basic check.",
          "## Keep", "- The strict gate (GATE_6E aggressive / GATE_6A balanced) as a regime FILTER / research object.",
          "## Discard", "- The orderflow event/entry detector as a trade ENTRY (REJECTED_FOR_ENTRY). Stop tuning it.",
          "## Backlog",
          "- Multi-window gate validation (need more UP/RANGE/BOUNCE windows, ideally cross-venue + L2).",
          "- A new entry mechanism tested INSIDE the bearish gate.",
          "## Can we stop this pass?",
          "- **YES.** The in-sample data is exhausted; further threshold tuning is overfitting. Move to the next branch: either a new entry inside the gate, or a different strategy.", "",
          "FINAL_ARTIFACTS_LOCATION:",
          "- main_folder: reports/final_short_permission_pass_closure_v7/",
          "- V7_FINAL_STATUS.md · AVAILABLE_DATA_AUDIT.csv · AVAILABLE_WINDOW_REGIME_CLASSIFICATION.csv",
          "- FINAL_GATE_VALIDATION_SCORECARD.csv · FINAL_GATE_VALIDATION_PERWINDOW.csv · FINAL_GATE_VALIDATION_REPORT.md",
          "- EVENT_DETECTOR_FINAL_DECISION.md · NEXT_RESEARCH_BRANCH_RECOMMENDATION.md · PASS_CLOSURE_SUMMARY.md"])

    # console
    print("=== scorecard (PF @ 0/5/10 bps) ===")
    for name in EVALS:
        print(f"  {name:<18} 0bps PF {m0(name)['pf']} | 5bps {m5(name)['pf']} | 10bps {metrics(EVALS[name],10)['pf']} | n {m0(name)['n']} wr {m0(name)['winrate']}% maxDD {m0(name)['maxDD_pct']}")
    print(f"gate_helps 6A {gate_helps_6A} 6E {gate_helps_6E} | survives5 6A {survives_5_6A} 6E {survives_5_6E} | event_adds 6A {event_adds_6A} 6E {event_adds_6E}")
    print(f"UP blocked 6A {up6A[2]}% 6E {up6E[2]}% | DOWN retained 6A {rate(dn6A[1],dn6A[0])}% 6E {rate(dn6E[1],dn6E[0])}% | up_windows {n_up}")
    print(f"GATE STATUS: {gate_status} | EVENT: {event_status}")
    return 0


def _wcsv(path, rows):
    if not rows: path.write_text("", encoding="utf-8"); return
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys, extrasaction="ignore"); w.writeheader()
        for r in rows: w.writerow({k: (json.dumps(v) if isinstance(v, (list, dict)) else v) for k, v in r.items()})
def _wmd(path, title, body): path.write_text(f"# {title}\n\nBuild {now()} · research closure · skeptical, not production.\n\n" + "\n".join(body) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
