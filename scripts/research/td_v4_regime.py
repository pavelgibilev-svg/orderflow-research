"""v4 — REGIME CONTROL TEST for the frozen v3 event trigger (NO threshold tuning, NO TP/SL change).

Question: does the v3 event-short trigger beat a RANDOM-short baseline ACROSS regimes (DOWN/UP/RANGE/BOUNCE)?
If it only "wins" in TREND_DOWN (where random short also wins), it is regime exposure, not an edge.

DATA: the 3 cross-venue windows have Bybit+OKX L2+trades. Control regimes (UP/RANGE/BOUNCE) exist locally only
as OKX trades (okx-historical). So v4 is OKX SINGLE-VENUE, TRADES-ONLY, and uses a DI-FREE variant of the v3
detector (documented modification: depth_imbalance conditions dropped because control windows have no L2;
ABSORPTION_EVENT needs depth -> N/A in controls). Thresholds otherwise identical to v3. TP=2%/SL=1.5%.
"""
from __future__ import annotations
import csv, gzip, json, random, statistics as st, sys, datetime as dt
from collections import defaultdict
from pathlib import Path

ROOT = Path("C:/Users/gibilev/orderflow-research")
OKXH = ROOT / "data/okx-historical/BTC-USDT-SWAP"
V2N = ROOT / "reports/trend_down_crossvenue_v2/_normalized"
OUT = ROOT / "reports/event_trigger_regime_control_v4"
TP, SL, HORIZON, COOLDOWN = 2.0, 1.5, 480, 30
random.seed(42)

# window -> (regime, source, [days])
def rng(a, b):
    da, db = dt.date.fromisoformat(a), dt.date.fromisoformat(b); o = []
    while da <= db: o.append(da.isoformat()); da += dt.timedelta(days=1)
    return o
WINDOWS = {
    "DOWN_NOV": ("TREND_DOWN", "v2okx:W1_NOVEMBER", rng("2025-11-19", "2025-11-22")),
    "DOWN_JAN": ("TREND_DOWN", "v2okx:W3_JANUARY", rng("2026-01-28", "2026-01-31")),
    "DOWN_APR": ("TREND_DOWN", "v2okx:W4_APRIL", rng("2024-04-12", "2024-04-17")),
    "DOWN_0327": ("TREND_DOWN", "okxhist", rng("2026-03-27", "2026-03-30")),
    "UP_0310": ("TREND_UP", "okxhist", rng("2026-03-10", "2026-03-16")),
    "RANGE_0508": ("RANGE_CHOP", "okxhist", rng("2026-05-08", "2026-05-11")),
    "RANGE_0303": ("RANGE_CHOP", "okxhist", rng("2026-03-03", "2026-03-06")),
    "BOUNCE_0512": ("REVERSAL_BOUNCE", "okxhist", rng("2026-05-12", "2026-05-15")),
}


def now(): return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
def fnum(x):
    try: return float(x)
    except (TypeError, ValueError): return None
def med(v): v = [x for x in v if x is not None]; return round(st.median(v), 4) if v else None
def pf_of(W, L): return round((W * 1.86) / (L * 1.64), 3) if L else ("inf" if W else None)
def rate(k, n): return round(100 * k / n, 1) if n else 0.0
def log(m): print(f"[{dt.datetime.now().strftime('%H:%M:%S')}] {m}", flush=True)


def okxhist_minute(days):
    """OKX-historical trades -> per-minute (mid OHLC, taker buy/sell vol, trade_count, cvd). di = None (no L2)."""
    bym = defaultdict(lambda: {"px": [], "bv": 0.0, "sv": 0.0, "tc": 0})
    for d in days:
        f = OKXH / d / "trades.csv.gz"
        if not f.exists(): continue
        with gzip.open(f, "rt", encoding="utf-8") as fh:
            rd = csv.reader(fh); next(rd, None)
            for row in rd:
                try: ts = int(row[2]); side = row[5]; px = float(row[6]); amt = float(row[7])
                except (IndexError, ValueError): continue
                r = bym[ts // 60_000_000]; r["px"].append(px)
                if side == "buy": r["bv"] += amt
                else: r["sv"] += amt
                r["tc"] += 1
    S = []; cvd = 0.0
    for m in sorted(bym):
        r = bym[m]; px = r["px"]
        cvd += (r["bv"] - r["sv"])
        S.append({"m": m, "date": dt.datetime.fromtimestamp(m * 60, tz=dt.timezone.utc).strftime("%Y-%m-%d"),
                  "mid": px[-1], "hi": max(px), "lo": min(px), "bv": r["bv"], "sv": r["sv"], "tc": r["tc"], "cvd": round(cvd, 4), "di": None, "spread": None})
    return S


def v2okx_minute(wid):
    p = V2N / f"OKX_{wid}_1m.csv.gz"; S = []
    if not p.exists(): return S
    with gzip.open(p, "rt", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            mid = fnum(r["mid_c"])
            if mid is None: continue
            S.append({"m": int(r["ts_min"]), "date": r["date"], "mid": mid, "hi": fnum(r["mid_h"]) or mid, "lo": fnum(r["mid_l"]) or mid,
                      "bv": fnum(r["taker_buy_vol"]) or 0, "sv": fnum(r["taker_sell_vol"]) or 0, "tc": fnum(r["trade_count"]) or 0,
                      "cvd": fnum(r["cvd"]) or 0, "di": fnum(r["depth_imbalance"]), "spread": fnum(r["spread_bps"])})
    S.sort(key=lambda x: x["m"]); return S


def load_series(src, days):
    if src.startswith("v2okx:"): return v2okx_minute(src.split(":")[1])
    return okxhist_minute(days)


# ---- DI-FREE detector (v3 thresholds minus depth conditions) ----
def detect(S, t):
    mid = [r["mid"] for r in S]
    def back(n): return mid[t - n] if t >= n else None
    def s(n, k): return sum(S[i][k] for i in range(max(0, t - n), t))
    pc5 = (mid[t] - back(5)) / back(5) * 100 if back(5) else None
    pc15 = (mid[t] - back(15)) / back(15) * 100 if back(15) else None
    nt5 = s(5, "bv") - s(5, "sv"); nt15 = s(15, "bv") - s(15, "sv")
    cvd5 = S[t]["cvd"] - (S[t - 5]["cvd"] if t >= 5 else S[0]["cvd"]); cvd15 = S[t]["cvd"] - (S[t - 15]["cvd"] if t >= 15 else S[0]["cvd"])
    tc5 = s(5, "tc"); base_tc = st.median([S[i]["tc"] for i in range(max(0, t - 180), t)]) if t > 10 else 1
    spike5 = (tc5 / 5) / (base_tc or 1) if base_tc else None
    look = mid[max(0, t - 240):t + 1]; dist_low = (mid[t] - min(look)) / min(look) * 100 if look else None
    cvd_min60 = min(S[i]["cvd"] for i in range(max(0, t - 60), t + 1))
    out = {}
    if cvd15 < 0 and nt15 < 0 and pc15 is not None and pc15 < -0.15 and (dist_low is None or dist_low > 0.3):
        out["ACTIVE_MARKDOWN_EVENT"] = 1
    if spike5 is not None and spike5 >= 2.5 and pc5 is not None and pc5 <= -0.4 and nt5 < 0:
        out["FORCED_UNWIND_EVENT"] = 1
    if S[t]["cvd"] <= cvd_min60 and pc5 is not None and pc5 <= 0 and t >= 1 and mid[t] <= mid[t - 1]:
        out["CVD_BREAKDOWN_EVENT"] = 1
    if nt15 < 0 and pc15 is not None and pc15 < -0.1:
        out["SELL_PRESSURE_NO_ABSORPTION_EVENT"] = 1
    return out, {"cvd15": round(cvd15, 1), "nt15": round(nt15, 3), "pc15": round(pc15, 3) if pc15 is not None else None,
                 "pc5": round(pc5, 3) if pc5 is not None else None, "spike5": round(spike5, 2) if spike5 else None,
                 "initiative_control": int((cvd15 < 0) + (nt15 < 0)), "effort_vs_result": (round((-(pc15 or 0)) * (s(15, "sv") - s(15, "bv")) / max(s(15, "bv") + s(15, "sv"), 1e-9), 3))}


def outcome_short(mid, t, entry):
    fav = adv = 0.0; t2 = None; oc = "TIMEOUT"; end = min(len(mid), t + HORIZON)
    for j in range(t + 1, end):
        fv = (entry - mid[j]) / entry * 100; av = (mid[j] - entry) / entry * 100
        fav = max(fav, fv); adv = max(adv, av)
        if t2 is None and fav >= 2: t2 = j - t
        if av >= SL and t2 is None: oc = "LOSS"; break
        if fv >= TP: oc = "WIN"; break
    return {"outcome": oc, "mfe": round(fav, 3), "mae": round(adv, 3), "hit2": int(fav >= 2), "hit2_5": int(fav >= 2.5), "hit3": int(fav >= 3),
            "loss": int(oc == "LOSS"), "timeout": int(oc == "TIMEOUT"), "time_to_2": t2}


def grp(rows):
    W = sum(1 for r in rows if r["outcome"] == "WIN"); L = sum(1 for r in rows if r["outcome"] == "LOSS"); TO = sum(1 for r in rows if r["outcome"] == "TIMEOUT")
    pnls = [1.86 if r["outcome"] == "WIN" else -1.64 if r["outcome"] == "LOSS" else 0 for r in rows]
    # max drawdown proxy over the sequence
    cum = 0; peak = 0; mdd = 0
    for p in pnls:
        cum += p; peak = max(peak, cum); mdd = min(mdd, cum - peak)
    return {"n": len(rows), "hit2": sum(r["hit2"] for r in rows), "hit2_rate": rate(sum(r["hit2"] for r in rows), len(rows)),
            "W": W, "L": L, "TO": TO, "pf": pf_of(W, L), "expectancy": round(st.mean(pnls), 3) if pnls else None,
            "median_mfe": med([r["mfe"] for r in rows]), "median_mae": med([r["mae"] for r in rows]), "max_dd_proxy": round(mdd, 2)}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    series = {}
    for wid, (reg, src, days) in WINDOWS.items():
        S = load_series(src, days); series[wid] = (reg, src, days, S)
        log(f"{wid} [{reg}] src {src}: {len(S)} minutes")

    # ---- 3: regime validation ----
    reg_rows = []
    for wid, (reg, src, days, S) in series.items():
        if not S: reg_rows.append({"window_id": wid, "regime_label": "NO_DATA", "source": src}); continue
        o, c = S[0]["mid"], S[-1]["mid"]; hi = max(r["hi"] for r in S); lo = min(r["lo"] for r in S)
        rets = [(S[i]["mid"] - S[i - 1]["mid"]) / S[i - 1]["mid"] for i in range(1, len(S)) if S[i - 1]["mid"]]
        rv = round(st.pstdev(rets) * (60 ** 0.5) * 100, 3) if len(rets) > 2 else None
        byd = defaultdict(list)
        for r in S: byd[r["date"]].append(r)
        dr = [round((max(p["hi"] for p in xs) - min(p["lo"] for p in xs)) / xs[0]["mid"] * 100, 2) for xs in byd.values()]
        net = round((c - o) / o * 100, 2)
        auto = "TREND_DOWN" if net <= -2 else "TREND_UP" if net >= 3 else "RANGE_CHOP"
        reg_rows.append({"window_id": wid, "intended_regime": reg, "source": src, "dates": f"{days[0]}..{days[-1]}", "net_pct": net,
                         "median_daily_range_pct": round(st.median(dr), 2), "rv_hourly_proxy_pct": rv, "max_down_leg_pct": round((lo - hi) / hi * 100, 2),
                         "max_bounce_pct": round((hi - lo) / lo * 100, 2), "regime_label_auto": auto, "agrees": auto == reg or (reg == "REVERSAL_BOUNCE")})
    _wcsv(OUT / "REGIME_WINDOWS_SUMMARY.csv", reg_rows)
    _wmd(OUT / "REGIME_WINDOWS_SUMMARY.md", "REGIME WINDOWS SUMMARY",
         ["| window | intended | source | dates | net% | medRange% | maxDown% | maxBounce% | auto |", "|---|---|---|---|--:|--:|--:|--:|---|"] +
         [f"| {r['window_id']} | {r.get('intended_regime','-')} | {r['source']} | {r.get('dates','-')} | {r.get('net_pct','-')} | {r.get('median_daily_range_pct','-')} | {r.get('max_down_leg_pct','-')} | {r.get('max_bounce_pct','-')} | {r.get('regime_label_auto','-')} |" for r in reg_rows])

    # ---- 4: events per window ----
    all_events = []
    for wid, (reg, src, days, S) in series.items():
        if not S: continue
        mid = [r["mid"] for r in S]
        for t in range(60, len(S) - 5):
            fams, f = detect(S, t)
            for fam in fams:
                oc = outcome_short(mid, t, mid[t])
                all_events.append({"event_id": f"{wid}-{fam[:4]}-{t}", "regime": reg, "window_id": wid, "exchange": "OKX", "ts_iso": dt.datetime.fromtimestamp(S[t]["m"] * 60, tz=dt.timezone.utc).isoformat(),
                                   "event_family": fam, "entry_policy": "EVENT_CLOSE", "entry_price": round(mid[t], 2), **oc,
                                   "cvd_delta_15m": f["cvd15"], "net_taker_15m": f["nt15"], "pc15": f["pc15"], "initiative_control": f["initiative_control"], "effort_vs_result": f["effort_vs_result"]})
    _wcsv(OUT / "EVENT_CANDIDATES_ALL_REGIMES.csv", all_events)
    _wcsv(OUT / "EVENT_OUTCOMES_ALL_REGIMES.csv", [{k: e[k] for k in ("event_id", "regime", "window_id", "event_family", "outcome", "hit2", "loss", "timeout", "mfe", "mae", "time_to_2")} for e in all_events])

    # ---- 5: random baseline by regime + event-vs-random ----
    rnd_rows = []; evr = []
    by_reg = defaultdict(list)
    for e in all_events: by_reg[e["regime"]].append(e)
    rnd_by_reg = defaultdict(list)
    for wid, (reg, src, days, S) in series.items():
        if len(S) < 80: continue
        mid = [r["mid"] for r in S]; cand = list(range(60, len(S) - 5))
        samp = random.sample(cand, min(500, len(cand)))
        for t in samp: rnd_by_reg[reg].append({"window_id": wid, **outcome_short(mid, t, mid[t])})
    for reg in ("TREND_DOWN", "TREND_UP", "RANGE_CHOP", "REVERSAL_BOUNCE"):
        ev = grp(by_reg.get(reg, [])); rb = grp(rnd_by_reg.get(reg, []))
        rnd_rows.append({"regime": reg, **{("rand_" + k): v for k, v in rb.items()}})
        evr.append({"regime": reg, "event_n": ev["n"], "event_hit2": ev["hit2_rate"], "event_pf": ev["pf"], "event_exp": ev["expectancy"],
                    "rand_n": rb["n"], "rand_hit2": rb["hit2_rate"], "rand_pf": rb["pf"], "rand_exp": rb["expectancy"],
                    "lift_hit2": (round(ev["hit2_rate"] - rb["hit2_rate"], 1) if rb["n"] else None),
                    "lift_pf": (round(ev["pf"] - rb["pf"], 3) if isinstance(ev["pf"], float) and isinstance(rb["pf"], float) else None),
                    "lift_exp": (round((ev["expectancy"] or 0) - (rb["expectancy"] or 0), 3) if rb["n"] else None)})
    _wcsv(OUT / "RANDOM_BASELINE_BY_REGIME.csv", rnd_rows)
    _wcsv(OUT / "EVENT_VS_RANDOM_BY_REGIME_table.csv", evr)
    _wmd(OUT / "EVENT_VS_RANDOM_BY_REGIME.md", "EVENT vs RANDOM by regime (the v4 core test)",
         ["di-free detector, OKX single-venue. random = 500 random-minute shorts/window, same TP2/SL1.5/horizon.", "",
          "| regime | event n | event hit2% | event PF | rand hit2% | rand PF | **lift hit2** | **lift PF** |", "|---|--:|--:|--:|--:|--:|--:|--:|"] +
         [f"| {r['regime']} | {r['event_n']} | {r['event_hit2']} | {r['event_pf']} | {r['rand_hit2']} | {r['rand_pf']} | {r['lift_hit2']} | {r['lift_pf']} |" for r in evr] +
         ["", "**Read it like this:** a real edge shows POSITIVE lift over random in MULTIPLE regimes — especially staying out of trouble in TREND_UP/RANGE where random short loses. Lift ~0 in TREND_DOWN = regime exposure."])

    # ---- 6: independent moments ----
    dd_rows = []; indep_all = []
    for reg in ("TREND_DOWN", "TREND_UP", "RANGE_CHOP", "REVERSAL_BOUNCE"):
        es = sorted(by_reg.get(reg, []), key=lambda e: (e["window_id"], e["ts_iso"]))
        indep = []; last = {}
        for e in es:
            key = e["window_id"]; tm = dt.datetime.fromisoformat(e["ts_iso"]).timestamp() / 60
            if key not in last or tm - last[key] > 60: indep.append(e); last[key] = tm
            else: last[key] = max(last[key], tm)
        indep_all += indep; g = grp(indep)
        dd_rows.append({"regime": reg, "raw_events": len(es), "independent_moments": len(indep), "indep_hit2": g["hit2_rate"], "indep_pf": g["pf"], "indep_exp": g["expectancy"]})
    _wcsv(OUT / "INDEPENDENT_MOMENTS.csv", indep_all and [{k: e[k] for k in ("event_id", "regime", "window_id", "event_family", "ts_iso", "outcome", "hit2")} for e in indep_all] or [])
    _wmd(OUT / "DEDUP_SUMMARY.md", "DEDUP SUMMARY (raw events -> independent moments)",
         ["| regime | raw events | independent moments | indep hit2% | indep PF |", "|---|--:|--:|--:|--:|"] +
         [f"| {r['regime']} | {r['raw_events']} | {r['independent_moments']} | {r['indep_hit2']} | {r['indep_pf']} |" for r in dd_rows])

    # ---- 8: template re-scoring (lift over random per regime) ----
    fam_reg = defaultdict(lambda: defaultdict(list))
    for e in all_events: fam_reg[e["event_family"]][e["regime"]].append(e)
    rand_pf = {r["regime"]: r["rand_pf"] for r in evr}; rand_hit2 = {r["regime"]: r["rand_hit2"] for r in evr}
    templates = []
    for fam, tid in [("ACTIVE_MARKDOWN_EVENT", "TD_ACTIVE_MARKDOWN_EVENT_SHORT_TEMPLATE"), ("FORCED_UNWIND_EVENT", "TD_FORCED_UNWIND_EVENT_SHORT_TEMPLATE"),
                     ("CVD_BREAKDOWN_EVENT", "TD_CVD_BREAKDOWN_EVENT_SHORT_TEMPLATE"), ("SELL_PRESSURE_NO_ABSORPTION_EVENT", "TD_SELL_PRESSURE_NO_ABSORPTION_SHORT_TEMPLATE")]:
        perreg = {}
        for reg in ("TREND_DOWN", "TREND_UP", "RANGE_CHOP", "REVERSAL_BOUNCE"):
            g = grp(fam_reg[fam].get(reg, []))
            lift = (round(g["hit2_rate"] - rand_hit2[reg], 1) if rand_hit2.get(reg) is not None and g["n"] else None)
            pf_lift = (round(g["pf"] - rand_pf[reg], 3) if isinstance(g["pf"], float) and isinstance(rand_pf.get(reg), float) else None)
            perreg[reg] = {"n": g["n"], "hit2": g["hit2_rate"], "pf": g["pf"], "lift_hit2": lift, "pf_lift": pf_lift}
        # HONEST status: must beat random on PF (not just hit2). PF<=random in down => regime exposure => REJECT.
        down = perreg["TREND_DOWN"]; up = perreg["TREND_UP"]
        beats_random_down = (down["pf_lift"] is not None and down["pf_lift"] > 0.1)
        up_not_worse = (up["n"] < 10) or (up["pf_lift"] is not None and up["pf_lift"] >= -0.05)
        regimes_pf_lift = sum(1 for reg in perreg if perreg[reg]["pf_lift"] is not None and perreg[reg]["pf_lift"] > 0.1)
        if down["n"] < 4: status = "NEED_MORE_DATA"
        elif not beats_random_down: status = "REJECT"          # random >= event in down -> no edge
        elif regimes_pf_lift >= 2 and up_not_worse: status = "RESEARCH_CANDIDATE"
        else: status = "NEED_MORE_DATA"
        regimes_with_lift = regimes_pf_lift
        templates.append({"template_id": tid, "trigger_family": fam, "per_regime": perreg, "regimes_with_positive_lift": regimes_with_lift, "status": status,
                          "overfit_risk": "HIGH", "note": "di-free; OKX single-venue"})
    # carry-forward veto templates (cross-venue tested only on DOWN -> need control data)
    for tid, fam in [("TD_TRUE_DISAGREEMENT_VETO", "cross_venue"), ("TD_ABSORPTION_DIVERGENCE_NO_SHORT", "absorption(L2)"), ("TD_VENUE_NOISE_IGNORE", "cross_venue"), ("TD_LEAD_LAG_MARKDOWN_SHORT_TEMPLATE", "cross_venue")]:
        templates.append({"template_id": tid, "trigger_family": fam, "per_regime": {}, "regimes_with_positive_lift": None,
                          "status": "NEED_MORE_DATA", "overfit_risk": "HIGH", "note": "cross-venue/L2 not testable in OKX-only control regimes -> needs Bybit+OKX+L2 control data (see DOWNLOAD_REQUIREMENTS)"})
    (OUT / "TEMPLATE_DECISIONS_V4.md").write_text("# TEMPLATE DECISIONS v4 (status = lift over random across regimes)\n\nBuild %s\n\n" % now() +
        "\n".join(f"- **{t['template_id']}** [{t['trigger_family']}] -> **{t['status']}** · per-regime (n / event_PF / pf_lift_vs_random): " +
                  (", ".join(f"{reg}:n{t['per_regime'][reg]['n']}/PF{t['per_regime'][reg]['pf']}/dPF{t['per_regime'][reg]['pf_lift']}" for reg in t['per_regime']) if t['per_regime'] else t['note']) for t in templates) +
        "\n\n_Rule: event must beat RANDOM on PF in TREND_DOWN to avoid REJECT. hit2-lift alone is not enough (FORCED_UNWIND had +16pp hit2 but PF 1.59 < random 2.49)._\n", encoding="utf-8")
    with (OUT / "TEMPLATE_SCORECARD_V4.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh); w.writerow(["template_id", "trigger_family", "status", "regimes_with_positive_lift", "down_lift", "up_lift", "range_lift", "note"])
        for t in templates:
            pr = t["per_regime"]; w.writerow([t["template_id"], t["trigger_family"], t["status"], t["regimes_with_positive_lift"],
                                              pr.get("TREND_DOWN", {}).get("lift_hit2"), pr.get("TREND_UP", {}).get("lift_hit2"), pr.get("RANGE_CHOP", {}).get("lift_hit2"), t["note"]])

    # ---- DOWNLOAD_REQUIREMENTS (cross-venue + L2 control data) ----
    (OUT / "DOWNLOAD_REQUIREMENTS.md").write_text("\n".join([
        "# DOWNLOAD REQUIREMENTS (to complete v4 cross-venue + L2 regime control)", "", f"Build {now()}",
        "v4 control regimes are OKX-only, trades-only (no Bybit, no L2). To test cross-venue (sync/lead-lag/disagreement)",
        "and depth-based families (ABSORPTION, full FORCED_UNWIND) across regimes, download Bybit+OKX L2+trades for:", "",
        "| regime | dates | exchange | instrument | data_type | reason |",
        "|---|---|---|---|---|---|",
        "| TREND_UP | 2026-03-10..03-16 | Bybit | BTCUSDT | OrderBook + Public Trading History | cross-venue + L2 in an up regime |",
        "| TREND_UP | 2026-03-10..03-16 | OKX | BTC-USDT-SWAP | OrderBook + Trade history (UTC+8) | depth for di-based families |",
        "| RANGE_CHOP | 2026-05-08..05-11 | Bybit+OKX | BTCUSDT / BTC-USDT-SWAP | OrderBook + Trades | chop control with L2 |",
        "| RANGE_CHOP | 2026-03-03..03-06 | Bybit+OKX | as above | OrderBook + Trades | high-intraday chop control |",
        "| REVERSAL_BOUNCE | 2026-05-12..05-15 | Bybit+OKX | as above | OrderBook + Trades | late-short / bounce control |",
        "", "Note: OKX trades use a UTC+8 day boundary — for UTC day D download labels D and D+1."]), encoding="utf-8")

    # ---- final report ----
    final(reg_rows, evr, dd_rows, templates)

    # console
    print("EVENT vs RANDOM by regime:")
    for r in evr: print(f"  {r['regime']:<16} event n{r['event_n']:>4} hit2 {r['event_hit2']}% PF {r['event_pf']} | rand hit2 {r['rand_hit2']}% PF {r['rand_pf']} | lift_hit2 {r['lift_hit2']} lift_pf {r['lift_pf']}")
    print("dedup:")
    for r in dd_rows: print(f"  {r['regime']:<16} raw {r['raw_events']} indep {r['independent_moments']} hit2 {r['indep_hit2']}% PF {r['indep_pf']}")
    print("templates:")
    for t in templates:
        if t["per_regime"]: print(f"  {t['template_id']:<46} {t['status']} liftDOWN {t['per_regime']['TREND_DOWN']['lift_hit2']} liftUP {t['per_regime']['TREND_UP']['lift_hit2']} liftRANGE {t['per_regime']['RANGE_CHOP']['lift_hit2']}")
    rc = [t["template_id"] for t in templates if t["status"] == "RESEARCH_CANDIDATE"]
    print("RESEARCH_CANDIDATE:", rc or "NONE")
    return 0


def final(reg_rows, evr, dd_rows, templates):
    rc = [t["template_id"] for t in templates if t["status"] == "RESEARCH_CANDIDATE"]
    rej = [t["template_id"] for t in templates if t["status"] == "REJECT"]
    down = next((r for r in evr if r["regime"] == "TREND_DOWN"), {}); up = next((r for r in evr if r["regime"] == "TREND_UP"), {})
    md = ["# EVENT TRIGGER REGIME CONTROL v4 — FINAL REPORT", "", f"Build {now()} · RESEARCH/CALIBRATION, not production. TP=2%/SL=1.5%. di-free detector, OKX single-venue control.", "",
          "## 1. Executive summary",
          f"- Tested the frozen v3 event-short trigger vs RANDOM short across regimes. DOWN lift_hit2 {down.get('lift_hit2')} / lift_PF {down.get('lift_pf')}; UP lift_hit2 {up.get('lift_hit2')} / lift_PF {up.get('lift_pf')}.",
          f"- RESEARCH_CANDIDATE templates: {rc or 'NONE'}.",
          "## 2. Regimes/windows"] + [f"- {r['window_id']} [{r.get('intended_regime')}] net {r.get('net_pct')}% -> auto {r.get('regime_label_auto')}" for r in reg_rows] + [
          "## 3. Event vs random"] + [f"- {r['regime']}: event PF {r['event_pf']} vs random PF {r['rand_pf']} (lift_hit2 {r['lift_hit2']})" for r in evr] + [
          "## 4. Raw vs independent moments"] + [f"- {r['regime']}: raw {r['raw_events']} -> {r['independent_moments']} independent" for r in dd_rows] + [
          "## 5-6. Which families give real lift vs just regime", "- See TEMPLATE_DECISIONS_V4; a family is regime-exposure if lift over random ~0 in DOWN and it still fires/loses in UP.",
          "## 7. RANGE/CHOP behaviour: does the trigger stay quiet / not bleed? see EVENT_VS_RANDOM (RANGE row).",
          "## 8. TREND_UP behaviour: does it stop shorting or keep catching the minus? (UP row).",
          "## 9. REVERSAL/BOUNCE: late-short check (BOUNCE row).",
          "## 10. cross-venue/lead-lag: NOT testable in OKX-only controls -> NEED_MORE_DATA (DOWNLOAD_REQUIREMENTS).",
          f"## 11. RESEARCH_CANDIDATE: {'YES ' + str(rc) if rc else 'NO'}",
          "## 12. Download next: Bybit+OKX L2+trades for UP/RANGE/BOUNCE (see DOWNLOAD_REQUIREMENTS.md).", "",
          "FINAL_ARTIFACTS_LOCATION:",
          "- main_folder: reports/event_trigger_regime_control_v4/",
          "- regime_windows_summary: REGIME_WINDOWS_SUMMARY.csv/.md", "- event_candidates: EVENT_CANDIDATES_ALL_REGIMES.csv",
          "- event_outcomes: EVENT_OUTCOMES_ALL_REGIMES.csv", "- random_baseline: RANDOM_BASELINE_BY_REGIME.csv",
          "- event_vs_random: EVENT_VS_RANDOM_BY_REGIME.md (+ _table.csv)", "- independent_moments: INDEPENDENT_MOMENTS.csv (+ DEDUP_SUMMARY.md)",
          "- template_scorecard: TEMPLATE_SCORECARD_V4.csv", "- template_decisions: TEMPLATE_DECISIONS_V4.md",
          "- final_report: EVENT_TRIGGER_REGIME_CONTROL_V4_FINAL_REPORT.md", "- download_requirements: DOWNLOAD_REQUIREMENTS.md"]
    (OUT / "EVENT_TRIGGER_REGIME_CONTROL_V4_FINAL_REPORT.md").write_text("\n".join(md), encoding="utf-8")


def _wcsv(path, rows):
    if not rows: path.write_text("", encoding="utf-8"); return
    keys = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys, extrasaction="ignore"); w.writeheader()
        for r in rows: w.writerow({k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v) for k, v in r.items()})
def _wmd(path, title, body): path.write_text(f"# {title}\n\nBuild {now()} · research/calibration.\n\n" + "\n".join(body) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
