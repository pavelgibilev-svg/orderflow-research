"""v9 — PHASE SEPARATION AUDIT (diagnostic, not optimization, not production).

Checks whether the short module (td_s = old event detector / GATE_6A / GATE_6E / 8A) activates in the CORRECT
market phase and stays silent in the wrong ones. Causal phase classifier (no lookahead). Frozen components:
old event detector (td_s proxy), GATE_6A/6E, 8A. No threshold tuning. Uses cached per-minute series.
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
import td_v8_entry as V8
OKXH = ROOT / "data/okx-historical/BTC-USDT-SWAP"
OUT = ROOT / "reports/phase_separation_audit_v9"
random.seed(42)

TARGET_PHASES = ("TREND_DOWN_ACTIVE_MARKDOWN", "RANGE_DISTRIBUTION_INTO_DEMAND")           # short allowed
BLOCKED_PHASES = ("TREND_DOWN_ABSORPTION_REVERSAL", "RANGE_ACCUMULATION_UNDER_PRESSURE", "LOW_VOL_NO_CONTROL_CHOP", "TREND_UP_NO_SHORT")


def now(): return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
def rate(k, n): return round(100 * k / n, 1) if n else 0.0
def pf_of(rows):
    W = sum(1 for o in rows if o == "WIN"); L = sum(1 for o in rows if o == "LOSS")
    return (round(W * 1.86 / (L * 1.64), 3) if L else (None if not W else 999))


def phase(S, P, t):
    """causal market-phase label at minute t (>=360 warmup). UNKNOWN where ambiguous."""
    mid = P["mid"]; cvd = P["cvd"]; vwap = P["vwap"]
    if t < 360: return "UNKNOWN"
    def ret(k): return (mid[t] - mid[t - k]) / mid[t - k] * 100
    r3 = ret(180); r6 = ret(360)
    pv = (mid[t] - vwap[t]) / vwap[t] * 100
    look = mid[max(0, t - 180):t + 1]; rng180 = (max(look) - min(look)) / min(look) * 100
    rlow = min(mid[max(0, t - 120):t + 1]); rhigh = max(mid[max(0, t - 120):t + 1])
    up_from_low = (mid[t] - rlow) / rlow * 100; dn_from_high = (rhigh - mid[t]) / rhigh * 100
    cvd60 = cvd[t] - cvd[t - 60]; nt30 = sum(S[i]["bv"] - S[i]["sv"] for i in range(t - 30, t))
    new_low = mid[t] <= min(mid[max(0, t - 60):t]) * 1.001
    r30 = ret(30)
    # LOW VOL / chop first
    if rng180 < 0.9 or (abs(r3) < 0.3 and rng180 < 1.3):
        return "LOW_VOL_NO_CONTROL_CHOP"
    # TREND UP (short should be blocked) -> outside the 5-phase taxonomy but tracked
    if r3 >= 1.2 or r6 >= 2.5:
        return "TREND_UP_NO_SHORT"
    # TREND DOWN
    if r3 <= -1.2 or r6 <= -2.5:
        if (pv < 0) and (new_low or up_from_low < 0.6) and cvd60 < 0:
            return "TREND_DOWN_ACTIVE_MARKDOWN"
        if (cvd60 < 0) and (not new_low) and (up_from_low > 0.6 or r30 >= 0):   # selling absorbed, price holds/bounces
            return "TREND_DOWN_ABSORPTION_REVERSAL"
        return "UNKNOWN"
    # RANGE
    if abs(r3) < 1.2:
        # distribution: upper part / near vwap-resistance, rally failing
        if (pv > 0 or dn_from_high < 0.6) and (mid[t] < mid[t - 1] and r30 <= 0.1):
            return "RANGE_DISTRIBUTION_INTO_DEMAND"
        # accumulation: lower part / near low, sell pressure but lows defended
        if (pv < 0 or up_from_low < 0.6) and cvd60 < 0 and not new_low:
            return "RANGE_ACCUMULATION_UNDER_PRESSURE"
        return "UNKNOWN"
    return "UNKNOWN"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    series = {wid: V5.get_series(wid) for wid in V4.WINDOWS}
    P = {wid: V8.prep(S) for wid, S in series.items()}
    for wid in series: print(f"{wid}: prepped", flush=True)

    # ---- Step 1: data audit ----
    march_days = sorted(p.name for p in OKXH.iterdir() if p.is_dir() and p.name.startswith("2026-03")) if OKXH.exists() else []
    audit = []
    for wid in series:
        reg, src, days = V4.WINDOWS[wid]
        audit.append({"window_id": wid, "venue": "OKX", "symbol": "BTC-USDT-SWAP", "date_range": f"{days[0]}..{days[-1]}",
                      "data_types": "per-minute mid+trades(cvd/taker)" + ("+L2" if src.startswith("v2okx") else ""),
                      "per_minute_cache": "YES", "used_in_v4_v8": "YES", "usable_for_phase_audit": "YES", "intended_regime": reg, "source": src})
    audit.append({"window_id": "OKX-historical 2026-03", "venue": "OKX", "symbol": "BTC-USDT-SWAP", "date_range": f"{march_days[0] if march_days else '-'}..{march_days[-1] if march_days else '-'}",
                  "data_types": "trades.csv.gz (per-day)", "per_minute_cache": "partial (3 March windows cached)", "used_in_v4_v8": "partial",
                  "usable_for_phase_audit": "YES (build per-minute on demand)", "intended_regime": "MIXED", "source": "okx-historical"})
    audit.append({"window_id": "BINANCE", "venue": "Binance", "symbol": "-", "date_range": "-", "data_types": "NONE", "per_minute_cache": "NO",
                  "used_in_v4_v8": "NO", "usable_for_phase_audit": "NO", "intended_regime": "-", "source": "absent (data is Bybit+OKX, not Binance)"})
    _wcsv(OUT / "V9_AVAILABLE_DATA_AUDIT.csv", audit)
    march_status = "AVAILABLE (OKX-historical 2026-03, %d days; 3 March windows already cached)" % len(march_days) if march_days else "DATA_BLOCKED"

    # ---- Step 2/3: classify minutes + measure activation/perf by phase ----
    perminute = []
    for wid, S in series.items():
        Pi = P[wid]; mid = Pi["mid"]; n = Pi["n"]
        for t in range(360, n - 5):
            ph = phase(S, Pi, t)
            tds = bool(V4.detect(S, t)[0])  # old event detector = td_s proxy
            perminute.append({"window_id": wid, "regime": V4.WINDOWS[wid][0], "t": t, "phase": ph,
                              "tds": tds, "g6A": Pi["g6A"][t], "g6E": Pi["g6E"][t], "e8A": Pi["e8A"][t]})
    # window x phase classification table
    byw_ph = defaultdict(lambda: defaultdict(int))
    for r in perminute: byw_ph[r["window_id"]][r["phase"]] += 1
    wph = []
    for wid in series:
        tot = sum(byw_ph[wid].values()); dom = max(byw_ph[wid].items(), key=lambda x: x[1]) if byw_ph[wid] else ("UNKNOWN", 0)
        row = {"window_id": wid, "intended_regime": V4.WINDOWS[wid][0], "total_min": tot, "dominant_phase": dom[0], "dominant_pct": rate(dom[1], tot)}
        for ph in list(TARGET_PHASES) + list(BLOCKED_PHASES) + ["UNKNOWN"]: row[ph] = byw_ph[wid].get(ph, 0)
        wph.append(row)
    _wcsv(OUT / "V9_WINDOW_PHASE_CLASSIFICATION.csv", wph)

    # per-phase activation + perf (perf via sampled outcomes)
    by_phase = defaultdict(list)
    for r in perminute: by_phase[r["phase"]].append(r)
    def short_out(wid, t): return V4.outcome_short(P[wid]["mid"], t, P[wid]["mid"][t])["outcome"]
    tds_rows = []
    for ph in list(TARGET_PHASES) + list(BLOCKED_PHASES) + ["UNKNOWN"]:
        rs = by_phase.get(ph, []); n = len(rs)
        if n == 0: tds_rows.append({"phase": ph, "minutes": 0}); continue
        tds_rate = rate(sum(1 for r in rs if r["tds"]), n); g6A = rate(sum(1 for r in rs if r["g6A"]), n)
        g6E = rate(sum(1 for r in rs if r["g6E"]), n); e8A = sum(1 for r in rs if r["e8A"])
        # perf: random sample short outcomes (any minute), gated (g6A), 8A
        samp = random.sample(rs, min(300, n))
        rand_out = [short_out(r["window_id"], r["t"]) for r in samp]
        gated = [r for r in rs if r["g6A"]]; gsamp = random.sample(gated, min(300, len(gated))) if gated else []
        gate_out = [short_out(r["window_id"], r["t"]) for r in gsamp]
        a8 = [r for r in rs if r["e8A"]]; a8_out = [short_out(r["window_id"], r["t"]) for r in a8]
        tds_rows.append({"phase": ph, "minutes": n, "tds_activation_rate": tds_rate, "gate6A_rate": g6A, "gate6E_rate": g6E, "setup_8A_count": e8A,
                         "random_short_hit2": rate(sum(1 for o in rand_out if o == "WIN"), len(rand_out)), "random_short_pf": pf_of(rand_out),
                         "gate6A_short_hit2": rate(sum(1 for o in gate_out if o == "WIN"), len(gate_out)) if gate_out else None, "gate6A_short_pf": pf_of(gate_out) if gate_out else None,
                         "entry8A_hit2": rate(sum(1 for o in a8_out if o == "WIN"), len(a8_out)) if a8_out else None, "entry8A_pf": pf_of(a8_out) if a8_out else None,
                         "is_target_phase": ph in TARGET_PHASES, "is_blocked_phase": ph in BLOCKED_PHASES})
    _wcsv(OUT / "V9_TD_S_BY_PHASE.csv", tds_rows)
    _wcsv(OUT / "V9_GATE_BY_PHASE_SCORECARD.csv", [{k: r.get(k) for k in ("phase", "minutes", "gate6A_rate", "gate6E_rate", "gate6A_short_hit2", "gate6A_short_pf", "is_target_phase", "is_blocked_phase")} for r in tds_rows])
    _wcsv(OUT / "V9_8A_BY_PHASE_SCORECARD.csv", [{k: r.get(k) for k in ("phase", "minutes", "setup_8A_count", "entry8A_hit2", "entry8A_pf", "is_target_phase", "is_blocked_phase")} for r in tds_rows])

    # ---- Step 4: phase quality tests ----
    def avg(metric, phases):
        rows = [r for r in tds_rows if r["phase"] in phases and r.get("minutes")]
        num = sum(r[metric] * r["minutes"] for r in rows if r.get(metric) is not None); den = sum(r["minutes"] for r in rows if r.get(metric) is not None)
        return round(num / den, 1) if den else None
    tds_target = avg("tds_activation_rate", TARGET_PHASES); tds_blocked = avg("tds_activation_rate", BLOCKED_PHASES)
    g6A_target = avg("gate6A_rate", TARGET_PHASES); g6A_blocked = avg("gate6A_rate", BLOCKED_PHASES)
    g6E_target = avg("gate6E_rate", TARGET_PHASES); g6E_blocked = avg("gate6E_rate", BLOCKED_PHASES)
    # 8A by phase: does it only work in ACTIVE_MARKDOWN?
    a8_am = next((r for r in tds_rows if r["phase"] == "TREND_DOWN_ACTIVE_MARKDOWN"), {})
    a8_other = [r for r in tds_rows if r["phase"] != "TREND_DOWN_ACTIVE_MARKDOWN" and (r.get("setup_8A_count") or 0) >= 5]
    # RANGE split?
    range_acc = next((r for r in tds_rows if r["phase"] == "RANGE_ACCUMULATION_UNDER_PRESSURE"), {})
    range_dist = next((r for r in tds_rows if r["phase"] == "RANGE_DISTRIBUTION_INTO_DEMAND"), {})
    range_splits = (range_acc.get("minutes", 0) >= 30 and range_dist.get("minutes", 0) >= 30)

    # false / missed permission
    fp = _wmd(OUT / "V9_FALSE_PERMISSION_ANALYSIS.md", "FALSE / MISSED SHORT-PERMISSION ANALYSIS",
        [f"- **gate6A activation in TARGET phases (markdown/distribution): {g6A_target}%** vs **BLOCKED phases (absorption/accumulation/chop/uptrend): {g6A_blocked}%**.",
         f"- gate6E activation: target {g6E_target}% vs blocked {g6E_blocked}%.",
         f"- td_s (old event) activation: target {tds_target}% vs blocked {tds_blocked}%.", "",
         "- **FALSE short-permission** = gate/td_s firing in BLOCKED phases. If blocked-phase activation is HIGH, the current gate does NOT do phase separation (it only knows trend direction, not absorption vs markdown / accumulation vs distribution).",
         "- **MISSED short-permission** = gate NOT firing in TARGET phases (low target activation).", "",
         "## Per-phase activation (key rows)"] +
        [f"- {r['phase']}: td_s {r.get('tds_activation_rate')}% · gate6A {r.get('gate6A_rate')}% · gate6E {r.get('gate6E_rate')}% · 8A_setups {r.get('setup_8A_count')} · n {r['minutes']}" for r in tds_rows if r.get("minutes")])

    # ---- Step 5: decision ----
    separated = (g6A_blocked is not None and g6A_target is not None and g6A_target >= g6A_blocked + 20)  # clear gap
    fires_everywhere = (g6A_blocked is not None and g6A_blocked >= 30)
    absorption_false = next((r["gate6A_rate"] for r in tds_rows if r["phase"] == "TREND_DOWN_ABSORPTION_REVERSAL"), None)
    if not march_days:
        status = "DATA_BLOCKED"
    elif separated and not fires_everywhere:
        status = "PHASE_MODEL_PROMISING"
    elif fires_everywhere or (absorption_false is not None and absorption_false >= 40):
        status = "PHASE_MODEL_NEED_MORE_DATA"  # gate conflates markdown with absorption; classifier needed
    else:
        status = "PHASE_MODEL_NEED_MORE_DATA"
    a8_only_markdown = (a8_am.get("setup_8A_count", 0) >= 10 and len(a8_other) == 0)

    _wmd(OUT / "V9_PHASE_FEATURE_DEFINITIONS.md", "V9 PHASE FEATURE DEFINITIONS (causal)",
         ["All from minutes <= t. Phases: TREND_DOWN_ACTIVE_MARKDOWN, TREND_DOWN_ABSORPTION_REVERSAL,",
          "RANGE_ACCUMULATION_UNDER_PRESSURE, RANGE_DISTRIBUTION_INTO_DEMAND, LOW_VOL_NO_CONTROL_CHOP, TREND_UP_NO_SHORT, UNKNOWN.",
          "- direction: ret_180m (3h), ret_360m (6h). price_vs_vwap180. range_180m.",
          "- markdown: below VWAP + making new 60m lows / weak bounce + CVD_60<0.",
          "- absorption: still selling (CVD_60<0) BUT not new low AND price holds/bounces (up_from_low>0.6 or ret_30>=0).",
          "- distribution: range + near highs/VWAP + rally failing (mid down, ret_30<=0.1).",
          "- accumulation: range + near lows + sell pressure (CVD_60<0) but lows defended (not new low).",
          "- low-vol/chop: range_180<0.9% or (|ret_3h|<0.3 and range_180<1.3%).", "",
          "Ex-post outcomes (V4.outcome_short, mid TP2/SL1.5) are used ONLY for per-phase perf diagnostics, not for live classification."])
    _wmd(OUT / "V9_PHASE_MODEL_DECISION.md", "V9 PHASE MODEL DECISION (skeptical)",
         [f"**STATUS: {status}**", f"- March data: {march_status}", "",
          "## A) Does td_s/gate mainly activate in correct phases?",
          f"- gate6A: target {g6A_target}% vs blocked {g6A_blocked}% -> {'SEPARATES' if separated else 'does NOT separate cleanly'}.",
          f"- td_s(old event): target {tds_target}% vs blocked {tds_blocked}%.",
          "## B) Does it wrongly activate in blocked phases?",
          f"- gate6A in TREND_DOWN_ABSORPTION_REVERSAL: **{absorption_false}%** (false permission if high).",
          f"- gate6A blocked-phase average: {g6A_blocked}% -> {'FIRES in blocked phases (false permission)' if fires_everywhere else 'mostly silent in blocked phases'}.",
          "## C) Does 8A only work in ACTIVE_MARKDOWN?",
          f"- 8A setups: ACTIVE_MARKDOWN n={a8_am.get('setup_8A_count')} (hit2 {a8_am.get('entry8A_hit2')}%); other phases with >=5 setups: {[r['phase'] for r in a8_other]} -> {'8A is ACTIVE_MARKDOWN-only' if a8_only_markdown else '8A also fires elsewhere'}.",
          "## D) Does RANGE split into accumulation vs distribution?",
          f"- RANGE_ACCUMULATION n={range_acc.get('minutes')}, RANGE_DISTRIBUTION n={range_dist.get('minutes')} -> {'YES, both behaviors present -> separate RANGE modules warranted' if range_splits else 'not enough range minutes to split (NEED_MORE_DATA)'}.",
          "## E) Is LOW_VOL/CHOP a no-trade filter?",
          f"- LOW_VOL_NO_CONTROL_CHOP gate6A {next((r['gate6A_rate'] for r in tds_rows if r['phase']=='LOW_VOL_NO_CONTROL_CHOP'),None)}% -> {'gate already mostly silent there (good no-trade)' }.", "",
          "## Skeptical reading",
          "- The frozen GATE_6A/6E only encode TREND DIRECTION (no-uptrend / downtrend-only). They have NO absorption-vs-markdown or accumulation-vs-distribution logic.",
          "- So if gate activation is similar in ACTIVE_MARKDOWN and ABSORPTION_REVERSAL, the gate is NOT a phase separator; a dedicated phase classifier is needed before any td_l calibration."])
    nb = ("A" if status == "PHASE_MODEL_PROMISING" else ("C" if status == "DATA_BLOCKED" else "B"))
    _wmd(OUT / "V9_NEXT_BRANCH_RECOMMENDATION.md", "V9 NEXT BRANCH RECOMMENDATION",
         [f"**Recommended option: {nb}**", "",
          "- **Option A (phase separation works):** build td_l / long-permission gate ONLY for ACCUMULATION_UNDER_PRESSURE + ABSORPTION_REVERSAL phases.",
          "- **Option B (phase separation fails):** do NOT calibrate td_l yet; improve the phase classifier first (add absorption/accumulation detection the gate lacks).",
          "- **Option C (data insufficient):** collect fresh windows per phase (ACTIVE_MARKDOWN, ABSORPTION_REVERSAL, ACCUMULATION_UNDER_PRESSURE, DISTRIBUTION_INTO_DEMAND, LOW_VOL_CHOP).", "",
          f"Given STATUS={status}: " + {"A": "phase separation holds -> proceed to td_l for accumulation/absorption.",
           "B": "the gate does not separate phases (it only knows trend direction) -> build a proper phase classifier BEFORE td_l.",
           "C": "March/phase data insufficient -> collect per-phase windows first."}[nb]])
    _wmd(OUT / "V9_PHASE_STATUS.md", "V9 PHASE STATUS",
         [f"- STATUS: **{status}**", f"- March data: {march_status}", f"- gate6A target {g6A_target}% vs blocked {g6A_blocked}%",
          f"- 8A ACTIVE_MARKDOWN-only: {a8_only_markdown}", f"- RANGE splits accumulation/distribution: {range_splits}", "- PRODUCTION: NO."])

    # console
    print("=== phases (minutes, td_s%, g6A%, g6E%, 8A setups) ===")
    for r in tds_rows:
        if r.get("minutes"): print(f"  {r['phase']:<34} n{r['minutes']:>6} tds {r.get('tds_activation_rate')}% g6A {r.get('gate6A_rate')}% g6E {r.get('gate6E_rate')}% 8A {r.get('setup_8A_count')}")
    print(f"gate6A target {g6A_target}% vs blocked {g6A_blocked}% | absorption false {absorption_false}% | separated {separated}")
    print(f"8A markdown-only {a8_only_markdown} | range splits {range_splits} | STATUS {status} | next {nb}")
    return 0


def _wcsv(path, rows):
    if not rows: path.write_text("", encoding="utf-8"); return
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys, extrasaction="ignore"); w.writeheader()
        for r in rows: w.writerow({k: (json.dumps(v) if isinstance(v, (list, dict)) else v) for k, v in r.items()})
def _wmd(path, title, body):
    path.write_text(f"# {title}\n\nBuild {now()} · phase-separation audit v9 · skeptical, not production.\n\n" + "\n".join(body) + "\n", encoding="utf-8"); return True


if __name__ == "__main__":
    sys.exit(main())
