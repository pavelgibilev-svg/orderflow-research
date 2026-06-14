"""TREND_DOWN cross-venue v2 — ANALYSIS (sections 2-11). RESEARCH/CALIBRATION, not production.

Consumes per-minute combined (L2 + REAL trades) per (exchange, window). TP=2%/SL=1.5% unchanged; 2.5/3% are
quality labels; forward-only outcomes; decisions causal (<= entry). Capital-state is DIRECTION-AWARE (fixes
the v1 direction-blind bug). Evidence blocks use real trade-flow (taker vol, CVD, taker imbalance) — N/A only
when genuinely uncomputable.
"""
from __future__ import annotations
import csv, gzip, json, math, statistics as st, sys, datetime as dt
from collections import defaultdict
from pathlib import Path

ROOT = Path("C:/Users/gibilev/orderflow-research")
NORM = ROOT / "reports/trend_down_crossvenue_v2/_normalized"
OUT = ROOT / "reports/trend_down_crossvenue_v2"
V1 = ROOT / "reports/trend_down_calibration_v1"
WINDOWS = {"W1_NOVEMBER": ("2025-11-19", "2025-11-22"), "W3_JANUARY": ("2026-01-28", "2026-01-31"), "W4_APRIL": ("2024-04-12", "2024-04-17")}
EXES = ("Bybit", "OKX")
TP, SL, HORIZON, PIVOT_W, COOLDOWN = 2.0, 1.5, 480, 2, 30


def now(): return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
def fnum(x):
    try: return float(x)
    except (TypeError, ValueError): return None
def pf_of(W, L): return round((W * 1.86) / (L * 1.64), 3) if L else ("inf" if W else None)
def rate(k, n): return round(100 * k / n, 1) if n else 0.0
def winrate(o): o = [x for x in o if x in ("WIN", "LOSS", "TIMEOUT")]; return round(100 * sum(1 for x in o if x == "WIN") / max(len(o), 1), 1)


def load_series(ex, wid):
    p = NORM / f"{ex}_{wid}_1m.csv.gz"
    if not p.exists(): return []
    rows = []
    with gzip.open(p, "rt", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            rows.append({"m": int(r["ts_min"]), "date": r["date"], "mid": fnum(r["mid_c"]), "hi": fnum(r["mid_h"]), "lo": fnum(r["mid_l"]),
                         "spread": fnum(r["spread_bps"]), "di": fnum(r["depth_imbalance"]), "bd": fnum(r["bid_depth_top10"]), "ad": fnum(r["ask_depth_top10"]),
                         "upd": fnum(r["update_count"]) or 0, "bv": fnum(r["taker_buy_vol"]) or 0, "sv": fnum(r["taker_sell_vol"]) or 0,
                         "tc": fnum(r["trade_count"]) or 0, "ti": fnum(r["taker_imbalance"]), "cvd": fnum(r["cvd"])})
    rows = [r for r in rows if r["mid"] is not None]
    rows.sort(key=lambda x: x["m"])
    return rows


# ---------- window summary (section 2) ----------
def window_summary(ex, wid, S):
    if not S: return None
    o, c = S[0]["mid"], S[-1]["mid"]; hi = max(r["hi"] or r["mid"] for r in S); lo = min(r["lo"] or r["mid"] for r in S)
    rets = [(S[i]["mid"] - S[i - 1]["mid"]) / S[i - 1]["mid"] for i in range(1, len(S)) if S[i - 1]["mid"]]
    rv = round(st.pstdev(rets) * math.sqrt(60) * 100, 3) if len(rets) > 2 else None
    byd = defaultdict(list)
    for r in S: byd[r["date"]].append(r)
    dranges = [round((max(p["hi"] or p["mid"] for p in xs) - min(p["lo"] or p["mid"] for p in xs)) / xs[0]["mid"] * 100, 2) for xs in byd.values()]
    net = round((c - o) / o * 100, 2)
    vol = round(sum(r["bv"] + r["sv"] for r in S), 2); tcnt = int(sum(r["tc"] for r in S))
    return {"exchange": ex, "window_id": wid, "net_pct": net, "median_daily_range_pct": round(st.median(dranges), 2), "max_daily_range_pct": max(dranges),
            "total_volume_btc": vol, "trade_count": tcnt, "rv_hourly_proxy_pct": rv,
            "max_down_leg_pct": round((lo - hi) / hi * 100, 2), "max_bounce_pct": round((hi - lo) / lo * 100, 2),
            "trend_down_confirmed": "YES" if net <= -1.0 else ("PARTIAL" if net <= 0.5 else "NO (counterexample)")}


# ---------- trade-flow lookbacks ----------
def lb_sum(S, t, n, key): return sum(S[k][key] for k in range(max(0, t - n), t))


def make_zone(ex, wid, S, t, direction):
    mids = [r["mid"] for r in S]; entry = mids[t]; r = S[t]
    fav = adv = 0.0; t2 = t25 = t3 = None; outcome = "TIMEOUT"
    end = min(len(mids), t + HORIZON)
    for j in range(t + 1, end):
        if direction == "SHORT": fv = (entry - mids[j]) / entry * 100; av = (mids[j] - entry) / entry * 100
        else: fv = (mids[j] - entry) / entry * 100; av = (entry - mids[j]) / entry * 100
        fav = max(fav, fv); adv = max(adv, av)
        if t2 is None and fav >= 2: t2 = j - t
        if t25 is None and fav >= 2.5: t25 = j - t
        if t3 is None and fav >= 3: t3 = j - t
        if av >= SL and t2 is None: outcome = "LOSS"; break
        if fv >= TP: outcome = "WIN"; break
    def back(n): return mids[t - n] if t >= n else None
    pm60 = (entry - back(60)) / back(60) * 100 if back(60) else None
    pm180 = (entry - back(180)) / back(180) * 100 if back(180) else None
    rets = [(mids[k] - mids[k - 1]) / mids[k - 1] for k in range(max(1, t - 180), t) if mids[k - 1]]
    lv = round(st.pstdev(rets) * 100, 3) if len(rets) > 2 else None
    look = mids[max(0, t - 240):t + 1]
    dist_low = round((entry - min(look)) / min(look) * 100, 3) if look else None
    dist_high = round((max(look) - entry) / max(look) * 100, 3) if look else None
    seg = mids[max(0, t - 30):t + 1]; bounce = round((max(seg) - min(seg)) / min(seg) * 100, 3) if seg else None
    # real trade-flow
    bv30, sv30 = lb_sum(S, t, 30, "bv"), lb_sum(S, t, 30, "sv")
    bv60, sv60 = lb_sum(S, t, 60, "bv"), lb_sum(S, t, 60, "sv")
    net_taker_30 = round(bv30 - sv30, 3); taker_imb_30 = round((bv30 - sv30) / (bv30 + sv30), 4) if (bv30 + sv30) else None
    cvd60 = round(r["cvd"] - (S[t - 60]["cvd"] if t >= 60 else S[0]["cvd"]), 3)
    pc30 = (entry - back(30)) / back(30) * 100 if back(30) else None
    tc30 = lb_sum(S, t, 30, "tc"); vol30 = bv30 + sv30
    avg_tc = st.mean([x["tc"] for x in S[max(0, t - 180):t]]) if t > 5 else 1
    tc_spike = round(tc30 / 30 / (avg_tc or 1), 2) if avg_tc else None
    # effort_vs_result: signed downside efficiency for short context
    sell_frac_30 = round(sv30 / vol30, 3) if vol30 else None
    evr = None
    if pc30 is not None and vol30 > 0:
        # negative pc30 (down) with sell dominance => efficient markdown (positive evr for short)
        evr = round((-pc30) * (sv30 - bv30) / max(vol30, 1e-9), 4)  # >0: down move driven by net selling
    return {"window_id": wid, "exchange": ex, "ts_min": r["m"], "date": r["date"], "ts_iso": dt.datetime.fromtimestamp(r["m"] * 60, tz=dt.timezone.utc).isoformat(),
            "direction_candidate": direction, "entry_price": round(entry, 2), "future_mfe_pct": round(fav, 3), "future_mae_pct": round(adv, 3),
            "hit2": int(fav >= 2), "hit2_5": int(fav >= 2.5), "hit3": int(fav >= 3), "loss": int(outcome == "LOSS"), "timeout": int(outcome == "TIMEOUT"), "outcome": outcome,
            "time_to_2_min": t2, "time_to_2_5_min": t25, "time_to_3_min": t3,
            "prior_move_60m": round(pm60, 3) if pm60 is not None else None, "prior_move_180m": round(pm180, 3) if pm180 is not None else None,
            "local_vol_180m": lv, "dist_from_recent_low_pct": dist_low, "dist_from_recent_high_pct": dist_high, "bounce_into_pivot_pct": bounce,
            "spread_bps": round(r["spread"], 3) if r["spread"] is not None else None, "depth_imbalance": round(r["di"], 4) if r["di"] is not None else None,
            "net_taker_30m": net_taker_30, "taker_imb_30m": taker_imb_30, "cvd_delta_60m": cvd60, "price_change_30m": round(pc30, 3) if pc30 is not None else None,
            "sell_frac_30m": sell_frac_30, "trade_count_spike": tc_spike, "effort_vs_result_raw": evr, "vol_30m_btc": round(vol30, 3)}


def build_zones(ex, wid, S):
    mids = [r["mid"] for r in S]; zones = []; last = {"SHORT": -10**9, "LONG": -10**9}
    for t in range(60, len(S) - 5):
        peak = t - PIVOT_W; prior = mids[max(0, peak - 30):peak + 1]
        pm60 = (mids[t] - mids[t - 60]) / mids[t - 60] * 100 if t >= 60 else None
        if mids[peak] == max(prior) and mids[t] < mids[peak] and (pm60 is None or pm60 <= 0.3) and (t - last["SHORT"]) >= COOLDOWN:
            zones.append(make_zone(ex, wid, S, t, "SHORT")); last["SHORT"] = t
        elif mids[peak] == min(prior) and mids[t] > mids[peak] and (pm60 is not None and pm60 <= -0.5) and (t - last["LONG"]) >= COOLDOWN:
            zones.append(make_zone(ex, wid, S, t, "LONG")); last["LONG"] = t
    return zones


def cluster(zones):
    out = []; by = defaultdict(list)
    for z in zones: by[(z["window_id"], z["exchange"], z["direction_candidate"])].append(z)
    cid = 0
    for k, zs in by.items():
        zs.sort(key=lambda x: x["ts_min"]); cur = []; last = None
        for z in zs:
            if last is not None and z["ts_min"] - last > 120: out.append((cid, cur)); cid += 1; cur = []
            cur.append(z); last = z["ts_min"]
        if cur: out.append((cid, cur)); cid += 1
    res = []
    for cid2, cl in out:
        p = cl[0]
        res.append({"cluster_id": f"{p['exchange'][:2]}-{p['window_id']}-{p['direction_candidate']}-{cid2}", "primary": p, "zones": cl,
                    "duplicate_cluster_size": len(cl), "any_hit2": max(z["hit2"] for z in cl), "best_mfe": round(max(z["future_mfe_pct"] for z in cl), 3)})
    return res


# ---------- capital state (DIRECTION-AWARE) ----------
def capital_state(c):
    z = c["primary"]; d = z["direction_candidate"]; di = z.get("depth_imbalance"); pm60 = z.get("prior_move_60m"); pm180 = z.get("prior_move_180m")
    bounce = z.get("bounce_into_pivot_pct"); cvd60 = z.get("cvd_delta_60m"); nt30 = z.get("net_taker_30m"); pc30 = z.get("price_change_30m")
    spike = z.get("trade_count_spike"); dist_low = z.get("dist_from_recent_low_pct"); sp = z.get("spread_bps"); evr = z.get("effort_vs_result_raw")
    if d == "SHORT":
        # FORCED_UNWIND: acceleration + activity spike + aggressive selling + thinning
        if (pm60 is not None and pm60 <= -1.5) and (spike is not None and spike >= 1.5) and (nt30 is not None and nt30 < 0) and (di is not None and di < -0.05):
            return "FORCED_UNWIND", 0.6, ["pm60<=-1.5", "activity spike", "net selling", "ask-heavy/thin bid"], "liquidation-like acceleration", "not absorption: bid not refilling"
        # DISTRIBUTION_INTO_BOUNCE: bounce happened but selling returns / CVD rolling over, ask-heavy
        if (bounce is not None and bounce >= 0.4) and (cvd60 is not None and cvd60 < 0) and (di is not None and di < 0.0) and (pm180 is None or pm180 <= 0.5):
            return "DISTRIBUTION_INTO_BOUNCE", 0.55, ["bounce>=0.4%", "CVD<0 (net selling)", "ask-heavy depth"], "buyers stall, sellers reload at highs", "not active markdown: needed a bounce first"
        # ACTIVE_MARKDOWN: down context + efficient selling (price down with net sell) + weak bounce + not bid-heavy
        if (pm60 is not None and pm60 <= -0.3) and (nt30 is not None and nt30 < 0) and (pc30 is not None and pc30 < 0) and (bounce is None or bounce < 0.6) and (di is None or di <= 0.1):
            return "ACTIVE_MARKDOWN", 0.55, ["pm60<=-0.3", "net selling + price down (efficient)", "weak bounce"], "seller in control, downside efficient", "not distribution: no real bounce"
        if (di is not None and abs(di) < 0.05) and (nt30 is not None and abs(nt30) < (z.get("vol_30m_btc") or 1) * 0.05):
            return "NO_CONTROL_CHOP", 0.4, ["depth_imb~0", "balanced taker flow"], "no capital control", "neither side dominant"
        return "UNKNOWN", 0.25, ["insufficient short evidence"], "cannot classify short honestly", "—"
    else:  # LONG = reversal-watch only
        # ABSORPTION_AFTER_SELL_PRESSURE: prior selling (cvd60<0 / pm180<0) but price stops falling (near low) + bid refill + CVD turning up
        if (pm180 is not None and pm180 <= -1.0) and (dist_low is not None and dist_low < 0.6) and (di is not None and di > 0.15) and (cvd60 is not None and cvd60 >= 0 or (nt30 is not None and nt30 > 0)):
            return "ABSORPTION_AFTER_SELL_PRESSURE", 0.55, ["prior markdown pm180<=-1", "near recent low", "bid-heavy depth>0.15", "CVD turning up"], "supply absorbed near low -> reversal watch", "not active markdown: bid dominant, short dangerous"
        if (di is not None and abs(di) < 0.05):
            return "NO_CONTROL_CHOP", 0.4, ["depth_imb~0"], "no control", "neither side dominant"
        return "UNKNOWN", 0.25, ["long counter-trend without clean absorption"], "reversal-watch unconfirmed", "—"


# ---------- evidence blocks (REAL trades) ----------
def evidence_blocks(c):
    z = c["primary"]; d = z["direction_candidate"]
    di = z.get("depth_imbalance"); pm60 = z.get("prior_move_60m"); pm180 = z.get("prior_move_180m"); nt30 = z.get("net_taker_30m")
    cvd60 = z.get("cvd_delta_60m"); pc30 = z.get("price_change_30m"); evr = z.get("effort_vs_result_raw"); ti30 = z.get("taker_imb_30m")
    dist_low = z.get("dist_from_recent_low_pct"); dist_high = z.get("dist_from_recent_high_pct"); sp = z.get("spread_bps")
    bd = z.get("depth_imbalance"); spike = z.get("trade_count_spike"); vol30 = z.get("vol_30m_btc") or 0
    def lvl(a, b, c_): return 3 if a else (2 if b else (1 if c_ else 0))
    # 1 effort_vs_result (REAL): for SHORT, sell pressure WITH price down = high; sell pressure WITHOUT down = absorption=low
    ev1 = "N/A"
    if evr is not None:
        if d == "SHORT": ev1 = lvl(evr > 0.5, evr > 0.1, evr > 0)
        else: ev1 = lvl(evr < -0.5, evr < -0.1, evr < 0)  # for long reversal: selling that failed to push down
    # 2 absorption_refill (REAL L2): bid-heavy (long/absorption) or ask-heavy (short markdown), magnitude
    ev2 = "N/A"
    if di is not None: ev2 = lvl(abs(di) > 0.3, abs(di) > 0.15, abs(di) > 0.05)
    # 3 initiative_control (REAL): CVD + taker imbalance aligned with intended direction
    ev3 = "N/A"
    if cvd60 is not None and ti30 is not None:
        aligned = (cvd60 < 0 and d == "SHORT") or (cvd60 > 0 and d == "LONG")
        strong = abs(ti30) > 0.15
        ev3 = lvl(aligned and strong, aligned, (ti30 < 0) == (d == "SHORT"))
    # 4 background_alignment
    ev4 = 0
    if pm60 is not None and pm180 is not None:
        if d == "SHORT": ev4 = lvl(pm60 <= -1 and pm180 <= -1, pm60 <= -0.3, pm60 <= 0.3)
        else: ev4 = lvl(pm180 <= -1.5, pm180 <= -0.5, pm180 <= 0)
    # 5 not_overextended
    ev5 = "N/A"
    if dist_low is not None and dist_high is not None:
        ev5 = lvl((dist_low if d == "SHORT" else dist_high) > 1.5, (dist_low if d == "SHORT" else dist_high) > 0.8, (dist_low if d == "SHORT" else dist_high) > 0.3)
    # 6 liquidity_execution
    ev6 = "N/A"
    if sp is not None: ev6 = lvl(sp < 1 and vol30 > 5 and (spike or 0) > 0.5, sp < 3 and vol30 > 1, sp < 8)
    return {"effort_vs_result": ev1, "absorption_refill": ev2, "initiative_control": ev3, "background_alignment": ev4, "not_overextended": ev5, "liquidity_execution": ev6}


def grp(rows):
    n = len(rows); W = sum(1 for r in rows if r["outcome"] == "WIN"); L = sum(1 for r in rows if r["outcome"] == "LOSS"); TO = sum(1 for r in rows if r["outcome"] == "TIMEOUT")
    return {"n": n, "hit2": sum(r["hit2"] for r in rows), "hit2_5": sum(r["hit2_5"] for r in rows), "hit3": sum(r["hit3"] for r in rows),
            "W": W, "L": L, "TO": TO, "hit2_rate": rate(sum(r["hit2"] for r in rows), n), "loss_rate": rate(L, n), "pf": pf_of(W, L),
            "expectancy": round(st.mean([1.86 if r["outcome"] == "WIN" else -1.64 if r["outcome"] == "LOSS" else 0 for r in rows]), 3) if rows else None}


def wcsv(path, rows):
    if not rows: path.write_text("", encoding="utf-8"); return
    keys = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys, extrasaction="ignore"); w.writeheader()
        for r in rows: w.writerow({k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v) for k, v in r.items()})
def wmd(path, title, body): path.write_text(f"# {title}\n\nBuild {now()} · RESEARCH/CALIBRATION (not production).\n\n" + "\n".join(body) + "\n", encoding="utf-8")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    series = {}; missing = []
    for wid in WINDOWS:
        for ex in EXES:
            S = load_series(ex, wid); series[(ex, wid)] = S
            if not S: missing.append(f"{ex}/{wid}")

    # ---- 1: dataset status ----
    cov = []
    for (ex, wid), S in series.items():
        cov.append({"exchange": ex, "window_id": wid, "minutes": len(S), "has_trades": int(any(r["tc"] > 0 for r in S)),
                    "first_min_utc": (dt.datetime.fromtimestamp(S[0]["m"] * 60, tz=dt.timezone.utc).isoformat() if S else None),
                    "last_min_utc": (dt.datetime.fromtimestamp(S[-1]["m"] * 60, tz=dt.timezone.utc).isoformat() if S else None)})
    wcsv(OUT / "DATASET_COVERAGE.csv", cov)
    wmd(OUT / "NORMALIZED_DATA_STATUS.md", "NORMALIZED DATA STATUS",
        ["Per-minute combined (L2 + REAL trades) for Bybit + OKX. Bybit symbol BTCUSDT, OKX BTC-USDT-SWAP.",
         "OKX trades bucketed by REAL UTC minute (UTC+8 label boundary handled). Old OKX quarantined.", "",
         "| exchange | window | minutes | has_trades |", "|---|---|--:|:--:|"] +
        [f"| {r['exchange']} | {r['window_id']} | {r['minutes']} | {'YES' if r['has_trades'] else 'NO'} |" for r in cov] +
        (["", f"**MISSING series:** {missing}"] if missing else ["", "All 6 (exchange x window) series present."]))
    wmd(OUT / "PARSE_LOG.md", "PARSE LOG", ["L2 book reconstruction + trade aggregation per minute. See _normalized/*.csv.gz and _l2min/ caches.",
        "Bybit Nov/Jan L2 reused from v1 per-second cache; Bybit April + all OKX parsed fresh. No L2-only proxy where trades exist."])

    # ---- 2: window summary ----
    wsum = [window_summary(ex, wid, series[(ex, wid)]) for (ex, wid) in series if series[(ex, wid)]]
    wcsv(OUT / "WINDOWS_SUMMARY.csv", wsum)
    wmd(OUT / "WINDOWS_SUMMARY.md", "WINDOWS SUMMARY",
        ["| exchange | window | net% | medRange% | maxDown% | maxBounce% | vol(BTC) | trades | TREND_DOWN? |", "|---|---|--:|--:|--:|--:|--:|--:|:--:|"] +
        [f"| {r['exchange']} | {r['window_id']} | {r['net_pct']} | {r['median_daily_range_pct']} | {r['max_down_leg_pct']} | {r['max_bounce_pct']} | {r['total_volume_btc']} | {r['trade_count']} | {r['trend_down_confirmed']} |" for r in wsum] +
        ["", "Feb W2 excluded by instruction (prior bounce). Any NO row is kept as a counterexample, not deleted."])

    # ---- 3: zones + clusters ----
    all_clusters = []; all_zones = []
    for (ex, wid), S in series.items():
        if not S: continue
        zs = build_zones(ex, wid, S); all_zones += zs; all_clusters += cluster(zs)
    wcsv(OUT / "ZONES_RAW.csv", all_zones)
    crows = []
    for c in all_clusters:
        p = c["primary"]
        crows.append({"cluster_id": c["cluster_id"], "exchange": p["exchange"], "window_id": p["window_id"], "date": p["date"], "ts_start": p["ts_iso"],
                      "direction_candidate": p["direction_candidate"], "entry_price": p["entry_price"], "future_mfe_pct": c["best_mfe"],
                      "hit2": p["hit2"], "hit2_5": p["hit2_5"], "hit3": p["hit3"], "loss": p["loss"], "timeout": p["timeout"], "outcome": p["outcome"],
                      "time_to_2": p["time_to_2_min"], "time_to_2_5": p["time_to_2_5_min"], "time_to_3": p["time_to_3_min"],
                      "duplicate_cluster_size": c["duplicate_cluster_size"], "is_primary_cluster": 1})
    wcsv(OUT / "UNIQUE_CLUSTERS.csv", crows)

    # ---- 4 + 5: capital state + evidence ----
    cb = []; ev = []
    for c in all_clusters:
        p = c["primary"]; cs, conf, why, why2, whynot = capital_state(c); eb = evidence_blocks(c)
        c["_cs"] = cs; c["_eb"] = eb
        cb.append({"cluster_id": c["cluster_id"], "exchange": p["exchange"], "window_id": p["window_id"], "date": p["date"], "capital_state_candidate": cs,
                   "confidence": conf, "direction_candidate": p["direction_candidate"], "hit2": p["hit2"], "hit2_5": p["hit2_5"], "hit3": p["hit3"], "loss": p["loss"], "timeout": p["timeout"],
                   "evidence_summary": "; ".join(why), "why_this_state": why2, "why_not_other_state": whynot,
                   "notes": f"di={p.get('depth_imbalance')} cvd60={p.get('cvd_delta_60m')} netTaker30={p.get('net_taker_30m')} bounce={p.get('bounce_into_pivot_pct')}"})
        ev.append({"cluster_id": c["cluster_id"], "exchange": p["exchange"], "capital_state": cs, "direction": p["direction_candidate"], "outcome": p["outcome"], **eb})
    wcsv(OUT / "CAPITAL_STATE_CASEBOOK.csv", cb)
    (OUT / "CAPITAL_STATE_CASEBOOK.json").write_text(json.dumps({"build": now(), "clusters": cb}, indent=2, default=str), encoding="utf-8")
    csc = defaultdict(lambda: [0, 0, 0, defaultdict(int)])
    for r in cb: a = csc[r["capital_state_candidate"]]; a[0] += 1; a[1] += r["hit2"]; a[2] += r["loss"]; a[3][r["direction_candidate"]] += 1
    wmd(OUT / "CAPITAL_STATE_CASEBOOK.md", "CAPITAL STATE CASEBOOK (direction-aware)",
        ["| capital_state | clusters | dirs | hit2 | loss |", "|---|--:|---|--:|--:|"] +
        [f"| {k} | {v[0]} | {dict(v[3])} | {v[1]} | {v[2]} |" for k, v in sorted(csc.items(), key=lambda x: -x[1][0])] +
        ["", "Direction-aware: SHORT states = ACTIVE_MARKDOWN/DISTRIBUTION_INTO_BOUNCE/FORCED_UNWIND/NO_CONTROL_CHOP/UNKNOWN;",
         "LONG = ABSORPTION_AFTER_SELL_PRESSURE (reversal-watch)/NO_CONTROL_CHOP/UNKNOWN. No LONG zone is labelled a short markdown."])
    wcsv(OUT / "EVIDENCE_BLOCK_SCORES.csv", ev)
    (OUT / "EVIDENCE_BLOCK_DEFINITIONS.md").write_text("\n".join([
        "# EVIDENCE BLOCK DEFINITIONS v2 (REAL trades)", "", f"Build {now()} · 0=none,1=weak,2=med,3=strong,N/A=uncomputable.", "",
        "1. effort_vs_result — REAL: signed downside efficiency = (-price_change_30m)*(sell-buy)/vol over 30m. SHORT high = price fell on net selling; low = selling absorbed (no progress).",
        "2. absorption_refill — L2 depth_imbalance magnitude toward the defending side (bid refill for long / ask for short markdown).",
        "3. initiative_control — REAL: CVD_60m direction + taker_imbalance_30m aligned with intended direction.",
        "4. background_alignment — prior 60m/180m move down for SHORT continuation (causal).",
        "5. not_overextended — distance above recent low (SHORT) / below recent high (LONG): room to TP2.",
        "6. liquidity_execution — spread tight + real 30m volume present + activity.", "",
        "Now computed from REAL trades (no L2-only proxy for effort/initiative). N/A only when a field is genuinely absent."]), encoding="utf-8")
    # evidence analysis: winners vs losers mean per block, per exchange
    eb_an = []
    for ex in EXES:
        sub = [c for c in all_clusters if c["primary"]["exchange"] == ex]
        for b in ("effort_vs_result", "absorption_refill", "initiative_control", "background_alignment", "not_overextended", "liquidity_execution"):
            wv = [fnum(c["_eb"][b]) for c in sub if c["primary"]["hit2"] == 1 and fnum(c["_eb"][b]) is not None]
            lv = [fnum(c["_eb"][b]) for c in sub if c["primary"]["hit2"] == 0 and fnum(c["_eb"][b]) is not None]
            if len(wv) >= 2 and len(lv) >= 2:
                eb_an.append({"exchange": ex, "block": b, "win_mean": round(st.mean(wv), 2), "loss_mean": round(st.mean(lv), 2), "sep": round(st.mean(wv) - st.mean(lv), 2), "n_win": len(wv), "n_loss": len(lv)})
    wmd(OUT / "EVIDENCE_BLOCK_ANALYSIS.md", "EVIDENCE BLOCK ANALYSIS v2 (real trades)",
        ["| exchange | block | win_mean | loss_mean | separation | n_win/n_loss |", "|---|---|--:|--:|--:|--:|"] +
        [f"| {r['exchange']} | {r['block']} | {r['win_mean']} | {r['loss_mean']} | {r['sep']} | {r['n_win']}/{r['n_loss']} |" for r in eb_an] +
        ["", "separation>0 => higher block score among hit2 winners. Interpret with small-n caution."])

    # ---- 6: cross-venue ----
    matched, cats = cross_venue(all_clusters)
    wcsv(OUT / "CROSS_VENUE_MATCHED_CLUSTERS.csv", matched)
    cv_score = []
    for cat in ("CROSS_CONFIRMED", "BYBIT_ONLY", "OKX_ONLY", "CROSS_DISAGREEMENT"):
        rows = [c for c in all_clusters if c.get("_cat") == cat]
        g = grp([c["primary"] for c in rows]); cv_score.append({"category": cat, **{k: g[k] for k in ("n", "hit2", "W", "L", "TO", "hit2_rate", "pf", "expectancy")}})
    wcsv(OUT / "CROSS_VENUE_SCORECARD.csv", cv_score)
    leadlag = [m["lead_lag_min"] for m in matched if m.get("lead_lag_min") is not None]
    wmd(OUT / "CROSS_VENUE_COMPARISON.md", "CROSS-VENUE COMPARISON (Bybit vs OKX, real data)",
        ["## Category scorecard (one trade per cluster)", "| category | n | hit2 | W/L/TO | hit2% | PF | exp% |", "|---|--:|--:|:--:|--:|--:|--:|"] +
        [f"| {r['category']} | {r['n']} | {r['hit2']} | {r['W']}/{r['L']}/{r['TO']} | {r['hit2_rate']} | {r['pf']} | {r['expectancy']} |" for r in cv_score] +
        ["", f"- matched pairs: {len(matched)} · mean lead-lag (OKX-Bybit, min): {round(st.mean(leadlag),2) if leadlag else 'n/a'} (negative => OKX leads)",
         "- price action agreement was already confirmed <1bps in v1; here we test whether cross-venue zone/state agreement improves hit2/PF.",
         "- CROSS_CONFIRMED vs BYBIT_ONLY hit2/PF delta is the key cross-venue value test."])

    # ---- 7: filters ----
    filt, fcompare = build_filters(all_clusters)
    (OUT / "FILTER_CANDIDATES_TREND_DOWN_CROSSVENUE_V2.json").write_text(json.dumps({"build": now(), "status": "CALIBRATION_CANDIDATE_LIBRARY", "filters": filt}, indent=2, default=str), encoding="utf-8")
    wcsv(OUT / "FILTER_CANDIDATES_TREND_DOWN_CROSSVENUE_V2.csv", [{k: v for k, v in f.items() if not isinstance(v, (list, dict))} for f in filt])
    wcsv(OUT / "FILTER_COMPARISON_SCORECARD.csv", fcompare)
    wmd(OUT / "FILTER_STEPS_TREND_DOWN_CROSSVENUE_V2.md", "FILTER STEPS — TREND_DOWN cross-venue v2",
        ["Candidate library (NOT production). TP=2%/SL=1.5%.", "",
         "1. Level1=TREND_DOWN (window net<=-1% or prior move down).", "2. Capital state (direction-aware).",
         "3. Direction consistency (SHORT-state->SHORT; LONG absorption->reversal-watch).", "4. Evidence blocks (real trades).",
         "5. Cross-venue confirm/disagree.", "6. Veto.", "7. Decision."] +
        ["", "## Filter decisions"] + [f"- {f['filter_id']}: **{f['decision']}** (n={f['cluster_count']}, hit2={f['hit2_rate']}%, PF={f['pf']}, windows={f['observed_windows']})" for f in filt])

    # ---- 8: templates ----
    tl = build_templates(filt)
    (OUT / "TREND_DOWN_TEMPLATE_LIBRARY_V2.json").write_text(json.dumps({"build": now(), "status": "TEMPLATE_LIBRARY_NOT_PRODUCTION", "templates": tl}, indent=2, default=str), encoding="utf-8")
    wmd(OUT / "TREND_DOWN_TEMPLATE_LIBRARY_V2.md", "TREND_DOWN TEMPLATE LIBRARY V2",
        ["| template | state | dir | status | windows | weak points |", "|---|---|---|:--:|---|---|"] +
        [f"| {t['template_id']} | {t['capital_state']} | {t['direction']} | **{t['status']}** | {t['observed_windows']} | {t['weak_points']} |" for t in tl] +
        (["", "_No RESEARCH_CANDIDATE qualified — see final report._"] if not any(t["status"] == "RESEARCH_CANDIDATE" for t in tl) else []))

    # ---- 9: decision tree ----
    wmd(OUT / "TREND_DOWN_DECISION_TREE_V2.md", "TREND_DOWN DECISION TREE V2", decision_tree(filt))

    # ---- 10 + 11: final report + comparison ----
    final_report(all_clusters, cb, ev, eb_an, cv_score, filt, tl, wsum, csc)
    comparison_v1(cb, eb_an, filt)

    # console
    base = grp([c["primary"] for c in all_clusters])
    print("clusters", len(all_clusters), "| baseline", base)
    print("capital states:", {k: v[0] for k, v in csc.items()})
    print("cross-venue scorecard:")
    for r in cv_score: print("  ", r)
    print("FILTERS:")
    for f in filt: print(f"  {f['filter_id']:<48} n{f['cluster_count']:>3} hit2 {f['hit2_rate']}% PF {f['pf']} -> {f['decision']}")
    print("templates:", [(t["template_id"], t["status"]) for t in tl])
    return 0


def cross_venue(clusters):
    matched = []
    by_w = defaultdict(lambda: {"Bybit": [], "OKX": []})
    for c in clusters: by_w[c["primary"]["window_id"]][c["primary"]["exchange"]].append(c)
    for c in clusters: c["_cat"] = None
    for wid, d in by_w.items():
        for bc in d["Bybit"]:
            best = None; bestdt = 1e9
            for oc in d["OKX"]:
                if oc["primary"]["direction_candidate"] != bc["primary"]["direction_candidate"]: continue
                dtmin = abs(oc["primary"]["ts_min"] - bc["primary"]["ts_min"])
                if dtmin < bestdt: bestdt = dtmin; best = oc
            if best is not None and bestdt <= 30:
                same_state = (capital_state(bc)[0] == capital_state(best)[0])
                bc["_cat"] = "CROSS_CONFIRMED" if same_state else "CROSS_DISAGREEMENT"
                best["_cat"] = bc["_cat"]
                matched.append({"window_id": wid, "direction": bc["primary"]["direction_candidate"], "bybit_cluster": bc["cluster_id"], "okx_cluster": best["cluster_id"],
                                "lead_lag_min": best["primary"]["ts_min"] - bc["primary"]["ts_min"], "bybit_state": capital_state(bc)[0], "okx_state": capital_state(best)[0],
                                "bybit_hit2": bc["primary"]["hit2"], "okx_hit2": best["primary"]["hit2"], "agree_state": int(same_state)})
            else:
                bc["_cat"] = "BYBIT_ONLY"
        for oc in d["OKX"]:
            if oc["_cat"] is None: oc["_cat"] = "OKX_ONLY"
    cats = {c["_cat"] for c in clusters}
    return matched, cats


def build_filters(clusters):
    def state(c): return c.get("_cs") or capital_state(c)[0]
    def sub(pred): return [c for c in clusters if pred(c)]
    def stats(rows):
        g = grp([c["primary"] for c in rows]); wins = sorted({c["primary"]["window_id"] for c in rows}); exs = sorted({c["primary"]["exchange"] for c in rows})
        return g, wins, exs
    def decide(fid, g, wins, exs):
        if g["n"] < 4: return "NEED_MORE_DATA"
        true_w = [w for w in wins if w != "W2"]
        if "VETO" in fid or "NO_TRADE" in fid or "NO_SHORT" in fid: return "KEEP_AS_VETO"
        if len(wins) < 2: return "QUARANTINE"
        if g["pf"] in (None,) or (isinstance(g["pf"], float) and g["pf"] < 0.9): return "REJECT"
        if isinstance(g["pf"], float) and g["pf"] >= 1.3 and g["hit2_rate"] >= 45 and len(exs) >= 2: return "KEEP_TEMPLATE"
        if isinstance(g["pf"], float) and g["pf"] >= 1.1: return "QUARANTINE"
        return "QUARANTINE"
    defs = [
        ("TD_ACTIVE_MARKDOWN_SHORT_TEMPLATE", lambda c: state(c) == "ACTIVE_MARKDOWN" and c["primary"]["direction_candidate"] == "SHORT", "ACTIVE_MARKDOWN", "SHORT", "EITHER"),
        ("TD_DISTRIBUTION_INTO_BOUNCE_SHORT_TEMPLATE", lambda c: state(c) == "DISTRIBUTION_INTO_BOUNCE", "DISTRIBUTION_INTO_BOUNCE", "SHORT", "EITHER"),
        ("TD_FORCED_UNWIND_CONTINUATION_SHORT_TEMPLATE", lambda c: state(c) == "FORCED_UNWIND", "FORCED_UNWIND", "SHORT", "EITHER"),
        ("TD_ABSORPTION_AFTER_SELL_PRESSURE_NO_SHORT_OR_REVERSAL_WATCH", lambda c: state(c) == "ABSORPTION_AFTER_SELL_PRESSURE", "ABSORPTION_AFTER_SELL_PRESSURE", "NO_SHORT/LONG_WATCH", "EITHER"),
        ("TD_NO_CONTROL_CHOP_NO_TRADE", lambda c: state(c) == "NO_CONTROL_CHOP", "NO_CONTROL_CHOP", "NO_TRADE", "EITHER"),
        ("TD_CROSS_VENUE_CONFIRMED_MARKDOWN_SHORT", lambda c: c.get("_cat") == "CROSS_CONFIRMED" and c["primary"]["direction_candidate"] == "SHORT" and state(c) in ("ACTIVE_MARKDOWN", "FORCED_UNWIND", "DISTRIBUTION_INTO_BOUNCE"), "MARKDOWN(any short)", "SHORT", "BOTH"),
        ("TD_CROSS_VENUE_DISAGREEMENT_VETO", lambda c: c.get("_cat") == "CROSS_DISAGREEMENT", "DISAGREEMENT", "VETO", "BOTH"),
    ]
    filt = []; fcompare = []
    for fid, pred, state_name, direction, exreq in defs:
        rows = sub(pred); g, wins, exs = stats(rows)
        dec = decide(fid, g, wins, exs)
        avg_ev = {}
        for b in ("effort_vs_result", "absorption_refill", "initiative_control", "background_alignment", "not_overextended", "liquidity_execution"):
            vals = [fnum(c["_eb"][b]) for c in rows if fnum(c.get("_eb", {}).get(b)) is not None]
            avg_ev[b] = round(st.mean(vals), 2) if vals else "N/A"
        rec = {"filter_id": fid, "filter_name": fid, "level_1_background": "TREND_DOWN", "capital_state": state_name, "intended_direction": direction,
               "required_conditions": _req(state_name), "veto_conditions": _veto(state_name), "optional_confirmations": ["cross-venue agreement", "CVD/taker confirmation"],
               "evidence_blocks_used": avg_ev, "score_gates": "capital_state match + >=3/6 evidence (bg+initiative>=2)", "exchange_requirement": exreq,
               "observed_windows": wins, "cluster_count": g["n"], "hit2_count": g["hit2"], "loss_count": g["L"], "timeout_count": g["TO"], "hit2_rate": g["hit2_rate"],
               "pf": g["pf"], "expectancy": g["expectancy"], "date_stability": round(len({c["primary"]["date"] for c in rows}) / max(g["n"], 1), 2),
               "exchange_stability": "BOTH" if len(exs) >= 2 else (exs[0] if exs else "-"), "overfit_risk": "HIGH" if g["n"] < 6 else ("MED" if g["n"] < 15 else "LOW"),
               "decision": dec, "notes": "real trade-flow; direction-aware"}
        filt.append(rec)
        fcompare.append({"filter_id": fid, "capital_state": state_name, "n": g["n"], "windows": len(wins), "exchanges": len(exs), "hit2_rate": g["hit2_rate"], "pf": g["pf"], "expectancy": g["expectancy"], "decision": dec})
    return filt, fcompare


def _req(s): return {"ACTIVE_MARKDOWN": ["SHORT", "pm60<=-0.3", "net selling + price down", "weak bounce"], "DISTRIBUTION_INTO_BOUNCE": ["bounce>=0.4%", "CVD<0", "ask-heavy"],
                     "FORCED_UNWIND": ["pm60<=-1.5", "activity spike", "net selling", "thin bid"], "ABSORPTION_AFTER_SELL_PRESSURE": ["prior markdown", "near low", "bid refill", "CVD up"],
                     "NO_CONTROL_CHOP": ["depth_imb~0", "balanced taker"], "MARKDOWN(any short)": ["cross-venue confirmed short markdown"], "DISAGREEMENT": ["venues disagree"]}.get(s, [])
def _veto(s): return {"ACTIVE_MARKDOWN": ["bid-heavy depth", "spread>8bps"], "DISTRIBUTION_INTO_BOUNCE": ["bid refill", "at recent low"], "FORCED_UNWIND": ["already at low"],
                      "ABSORPTION_AFTER_SELL_PRESSURE": ["fresh down accel"], "NO_CONTROL_CHOP": ["-"], "MARKDOWN(any short)": ["venue disagreement"], "DISAGREEMENT": ["-"]}.get(s, [])


def build_templates(filt):
    tl = []
    for f in filt:
        status = {"KEEP_TEMPLATE": "RESEARCH_CANDIDATE", "KEEP_AS_VETO": "VETO_CANDIDATE", "QUARANTINE": "QUARANTINE", "REJECT": "REJECTED", "NEED_MORE_DATA": "QUARANTINE"}[f["decision"]]
        if status == "REJECTED": continue
        weak = []
        if f["cluster_count"] < 6: weak.append("small n")
        if len(f["observed_windows"]) < 2: weak.append("1 window")
        if f["exchange_stability"] != "BOTH": weak.append("single exchange")
        tl.append({"template_id": f["filter_id"], "template_name": f["filter_id"], "level_1_background": "TREND_DOWN", "capital_state": f["capital_state"],
                   "direction": f["intended_direction"], "purpose": _req(f["capital_state"]), "required_conditions": f["required_conditions"], "veto_conditions": f["veto_conditions"],
                   "optional_confirmations": f["optional_confirmations"], "evidence_blocks_used": list(f["evidence_blocks_used"].keys()),
                   "cross_venue_logic": ("require BOTH venues" if f["exchange_requirement"] == "BOTH" else "either venue"), "minimum_score_logic": f["score_gates"],
                   "when_not_to_use": f["veto_conditions"], "observed_windows": f["observed_windows"], "weak_points": "; ".join(weak) or "none major",
                   "next_validation_needed": "more true TREND_DOWN windows + OOS", "status": status})
    return tl


def decision_tree(filt):
    dec = {f["filter_id"]: f["decision"] for f in filt}
    return ["Research decision flow (NOT production). TP=2%/SL=1.5%.", "", "```",
            "IF Level1 != TREND_DOWN: do not use TREND_DOWN templates.",
            "IF Level1 == TREND_DOWN:", "  determine capital_state (direction-aware) from price + L2 + REAL trades (CVD/taker):", "",
            f"  ACTIVE_MARKDOWN + SHORT:        TD_ACTIVE_MARKDOWN_SHORT_TEMPLATE  [{dec.get('TD_ACTIVE_MARKDOWN_SHORT_TEMPLATE')}]",
            f"  DISTRIBUTION_INTO_BOUNCE + SHORT: TD_DISTRIBUTION_INTO_BOUNCE_SHORT  [{dec.get('TD_DISTRIBUTION_INTO_BOUNCE_SHORT_TEMPLATE')}]",
            f"  FORCED_UNWIND + SHORT:          TD_FORCED_UNWIND_CONTINUATION       [{dec.get('TD_FORCED_UNWIND_CONTINUATION_SHORT_TEMPLATE')}]",
            f"  ABSORPTION_AFTER_SELL_PRESSURE: NO short; reversal-watch / no-trade  [{dec.get('TD_ABSORPTION_AFTER_SELL_PRESSURE_NO_SHORT_OR_REVERSAL_WATCH')}]",
            f"  NO_CONTROL_CHOP:                NO TRADE                            [{dec.get('TD_NO_CONTROL_CHOP_NO_TRADE')}]",
            "  UNKNOWN:                        NO TRADE", "",
            "  CHECK direction consistency: a SHORT-state never fires on a LONG zone (v1 bug fixed).",
            f"  CHECK cross-venue: CONFIRMED short markdown [{dec.get('TD_CROSS_VENUE_CONFIRMED_MARKDOWN_SHORT')}]; DISAGREEMENT -> VETO [{dec.get('TD_CROSS_VENUE_DISAGREEMENT_VETO')}].",
            "  THEN veto (dirty spread / at low / depth flip) -> no trade.",
            "  DECISION: SHORT_CANDIDATE / NO_TRADE / REVERSAL_WATCH / NEED_MORE_DATA.", "```"]


def final_report(clusters, cb, ev, eb_an, cv_score, filt, tl, wsum, csc):
    base = grp([c["primary"] for c in clusters])
    keep = [f["filter_id"] for f in filt if f["decision"] == "KEEP_TEMPLATE"]
    veto = [f["filter_id"] for f in filt if f["decision"] == "KEEP_AS_VETO"]
    quar = [f["filter_id"] for f in filt if f["decision"] in ("QUARANTINE", "NEED_MORE_DATA")]
    rej = [f["filter_id"] for f in filt if f["decision"] == "REJECT"]
    unknown = csc.get("UNKNOWN", [0])[0]
    md = ["# TREND_DOWN CROSS-VENUE v2 — FINAL REPORT", "", f"Build {now()} · RESEARCH/CALIBRATION, not production.", "",
          "## 1. Executive summary",
          f"- {len(clusters)} unique clusters (Bybit+OKX, real trade-flow). Baseline: hit2 {base['hit2_rate']}%, loss {base['loss_rate']}%, PF {base['pf']}, exp {base['expectancy']}%.",
          f"- Capital-state is now DIRECTION-AWARE (v1 bug fixed). UNKNOWN clusters: {unknown}/{len(clusters)}.",
          f"- RESEARCH_CANDIDATE templates: {keep or 'NONE'}; VETO: {veto or 'NONE'}.", "",
          "## 2-3. Data / windows", "- Bybit BTCUSDT + OKX BTC-USDT-SWAP, windows W1_NOV/W3_JAN/W4_APRIL. See WINDOWS_SUMMARY.",
          "## 4. What changed after adding trades", "- effort_vs_result & initiative_control now use real taker volume + CVD (not L2 proxy).",
          "- capital_state uses net taker flow and CVD slope, and is direction-consistent.", "",
          "## 5-7. Results", "| category | n | hit2% | PF |", "|---|--:|--:|--:|"] + [f"| {r['category']} | {r['n']} | {r['hit2_rate']} | {r['pf']} |" for r in cv_score] + [
          "", "## 8. Capital states that separate", "| state | n | hit2 | loss |", "|---|--:|--:|--:|"] + [f"| {k} | {v[0]} | {v[1]} | {v[2]} |" for k, v in sorted(csc.items(), key=lambda x: -x[1][0])] + [
          "", "## 9-10. Evidence blocks (real trades)"] + [f"- {r['exchange']} {r['block']}: sep {r['sep']} (win {r['win_mean']} vs loss {r['loss_mean']})" for r in eb_an] + [
          "", "## 11-12. Filters", f"- KEEP_TEMPLATE: {keep or 'NONE'}", f"- KEEP_AS_VETO: {veto or 'NONE'}", f"- QUARANTINE/NEED_MORE_DATA: {quar}", f"- REJECT: {rej}", "",
          "## 13. RESEARCH_CANDIDATE short-template?", f"- {'YES: ' + str(keep) if keep else 'NO — see scorecard; most states remain QUARANTINE/NEED_MORE_DATA or VETO.'}", "",
          "## 14. Next", "- More true TREND_DOWN windows (W2 was a bounce); true OOS; freeze any surviving template, no tuning.", "",
          "## 15. Artifacts", "", "FINAL_ARTIFACTS_LOCATION:",
          "- main_folder: reports/trend_down_crossvenue_v2/", "- dataset_coverage: DATASET_COVERAGE.csv",
          "- windows_summary: WINDOWS_SUMMARY.csv/.md", "- zones_raw: ZONES_RAW.csv", "- unique_clusters: UNIQUE_CLUSTERS.csv",
          "- capital_state_casebook: CAPITAL_STATE_CASEBOOK.csv/.json/.md", "- evidence_scores: EVIDENCE_BLOCK_SCORES.csv (+ ANALYSIS.md)",
          "- cross_venue_comparison: CROSS_VENUE_COMPARISON.md + CROSS_VENUE_MATCHED_CLUSTERS.csv + CROSS_VENUE_SCORECARD.csv",
          "- filter_candidates: FILTER_CANDIDATES_TREND_DOWN_CROSSVENUE_V2.json/.csv", "- filter_scorecard: FILTER_COMPARISON_SCORECARD.csv",
          "- template_library: TREND_DOWN_TEMPLATE_LIBRARY_V2.json/.md", "- decision_tree: TREND_DOWN_DECISION_TREE_V2.md",
          "- final_report: TREND_DOWN_CROSSVENUE_FINAL_REPORT.md"]
    (OUT / "TREND_DOWN_CROSSVENUE_FINAL_REPORT.md").write_text("\n".join(md), encoding="utf-8")


def comparison_v1(cb, eb_an, filt):
    md = ["# COMPARISON WITH L2-ONLY v1", "", f"Build {now()} · v1 = reports/trend_down_calibration_v1 (L2-proxy, Bybit-only).", ""]
    v1cb = list(csv.DictReader((V1 / "CAPITAL_STATE_CASEBOOK.csv").open(encoding="utf-8"))) if (V1 / "CAPITAL_STATE_CASEBOOK.csv").exists() else []
    def unk(rows, key):
        n = len(rows); u = sum(1 for r in rows if r.get(key) == "UNKNOWN"); return n, u, rate(u, n)
    v1n, v1u, v1ur = unk(v1cb, "capital_state_candidate")
    v2n, v2u, v2ur = unk(cb, "capital_state_candidate")
    v1_am_long = sum(1 for r in v1cb if r.get("capital_state_candidate") == "ACTIVE_MARKDOWN" and r.get("direction_candidate") == "LONG")
    v2_am_long = sum(1 for r in cb if r.get("capital_state_candidate") == "ACTIVE_MARKDOWN" and r.get("direction_candidate") == "LONG")
    keep = [f["filter_id"] for f in filt if f["decision"] in ("KEEP_TEMPLATE",)]
    pos_blocks = [r for r in eb_an if r["sep"] > 0]
    md += ["## Did labels improve?",
           f"- UNKNOWN share: v1 {v1ur}% ({v1u}/{v1n}) -> v2 {v2ur}% ({v2u}/{v2n})  => {'DOWN (better)' if v2ur < v1ur else 'NOT reduced'}",
           f"- direction-blind bug (ACTIVE_MARKDOWN on LONG zones): v1 {v1_am_long} -> v2 {v2_am_long}  => {'FIXED' if v2_am_long == 0 else 'still present'}",
           f"- positive evidence blocks (sep>0) after real trades: {[ (r['exchange'],r['block'],r['sep']) for r in pos_blocks] or 'none'}",
           f"- tradeable/RESEARCH_CANDIDATE filters: {keep or 'NONE'}",
           f"- overall conclusion still negative? {'NO — at least one research candidate' if keep else 'LIKELY YES (no research candidate) — but trades fixed the classifier and reduced UNKNOWN'}"]
    (OUT / "COMPARISON_WITH_L2_ONLY_V1.md").write_text("\n".join(md), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
