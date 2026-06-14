"""TASK1 / C-H — TREND_DOWN calibration analysis on normalized L2 (Bybit ob200, mid-price).

SIMPLIFIED L2 ZONE BUILDER (no trades available in-window) — clearly marked. Causal decisions (<= entry ts);
forward-only outcomes; TP=2%, SL=1.5% (unchanged); 2.5/3% are quality labels. Trade-flow blocks are L2 PROXY
or N/A. Research/calibration only — NOT production.
"""
from __future__ import annotations
import csv, gzip, json, math, statistics as st, sys, datetime as dt
from collections import defaultdict
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "package.json").exists() and (p / "scripts").exists())
NORM = ROOT / "reports/trend_down_calibration_v1/_normalized"
OUT = ROOT / "reports/trend_down_calibration_v1"
WINDOWS = {"W1": ("2025-11-19", "2025-11-22"), "W2": ("2026-02-11", "2026-02-14"), "W3": ("2026-01-28", "2026-01-31")}
TP, SL, HORIZON_MIN, PIVOT_W, COOLDOWN_MIN = 2.0, 1.5, 480, 2, 30
EX = "Bybit"


def now_iso(): return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
def num(x):
    try: return float(x)
    except (TypeError, ValueError): return None
def daterange(a, b):
    da, db = dt.date.fromisoformat(a), dt.date.fromisoformat(b); out = []
    while da <= db: out.append(da.isoformat()); da += dt.timedelta(days=1)
    return out
def pf_of(W, L): return round((W * 1.86) / (L * 1.64), 3) if L else ("inf" if W else None)


def load_minute(window_days):
    """concatenate per-second L2 rows across window days -> per-minute OHLC(mid) + L2 aggregates."""
    persec = []
    for d in window_days:
        f = NORM / f"{EX}_BTCUSDT_{d}_l2_1s.csv.gz"
        if not f.exists(): continue
        with gzip.open(f, "rt", encoding="utf-8") as fh:
            rd = csv.DictReader(fh)
            for r in rd:
                persec.append((int(r["ts_sec"]), num(r["mid"]), num(r["spread_bps"]), num(r["depth_imbalance"]),
                               num(r["bid_depth_top10"]), num(r["ask_depth_top10"]), num(r["top_bid_size"]), num(r["top_ask_size"]), num(r["update_count"])))
    persec.sort()
    bym = defaultdict(list)
    for row in persec: bym[row[0] // 60].append(row)
    minutes = []
    for m in sorted(bym):
        g = bym[m]; mids = [x[1] for x in g if x[1] is not None]
        if not mids: continue
        minutes.append({"m": m, "o": mids[0], "h": max(mids), "l": min(mids), "c": mids[-1],
                        "spread": st.mean([x[2] for x in g if x[2] is not None] or [None]) if any(x[2] is not None for x in g) else None,
                        "depth_imb": st.mean([x[3] for x in g if x[3] is not None] or [0]) if any(x[3] is not None for x in g) else None,
                        "bid_depth": st.mean([x[4] for x in g if x[4] is not None] or [0]),
                        "ask_depth": st.mean([x[5] for x in g if x[5] is not None] or [0]),
                        "updates": sum(x[8] for x in g if x[8] is not None)})
    return minutes


def window_summary(window_days, minutes):
    if not minutes: return None
    o = minutes[0]["o"]; c = minutes[-1]["c"]; hi = max(x["h"] for x in minutes); lo = min(x["l"] for x in minutes)
    rets = [(minutes[i]["c"] - minutes[i - 1]["c"]) / minutes[i - 1]["c"] for i in range(1, len(minutes)) if minutes[i - 1]["c"]]
    rv = round(st.pstdev(rets) * math.sqrt(60) * 100, 3) if len(rets) > 2 else None  # hourly realized vol proxy %
    # per-day ranges
    byday = defaultdict(list)
    for x in minutes: byday[dt.datetime.fromtimestamp(x["m"] * 60, tz=dt.timezone.utc).strftime("%Y-%m-%d")].append(x)
    dranges = []; down_days = []; bounce_days = []
    for d, xs in sorted(byday.items()):
        do = xs[0]["o"]; dc = xs[-1]["c"]; dh = max(p["h"] for p in xs); dl = min(p["l"] for p in xs)
        rng = (dh - dl) / do * 100; net = (dc - do) / do * 100; dranges.append(rng)
        down_days.append((d, round(net, 2))); bounce_days.append((d, round((dh - dl) / do * 100, 2)))
    net = (c - o) / o * 100
    return {"net_pct": round(net, 2), "median_daily_range_pct": round(st.median(dranges), 2), "max_daily_range_pct": round(max(dranges), 2),
            "max_intraday_dd_pct": round((lo - hi) / hi * 100, 2), "max_intraday_bounce_pct": round((hi - lo) / lo * 100, 2),
            "total_updates": sum(x["updates"] for x in minutes), "rv_hourly_proxy_pct": rv,
            "trend_down_confirmed": "YES" if net <= -1.0 else ("PARTIAL" if net <= 0.5 else "NO"),
            "strongest_down_days": sorted(down_days, key=lambda x: x[1])[:2], "strongest_bounce_days": sorted(bounce_days, key=lambda x: -x[1])[:2],
            "minutes": len(minutes)}


def build_zones(window_id, minutes):
    """causal pivot-based candidate zones. SHORT at confirmed lower-high; LONG at confirmed higher-low."""
    mids = [x["c"] for x in minutes]
    zones = []; last_trig = {"SHORT": -10**9, "LONG": -10**9}
    for t in range(40, len(minutes) - 5):
        m = minutes[t]
        # confirmed local peak 2 min ago over prior 32 min
        peak_idx = t - PIVOT_W
        prior = mids[max(0, peak_idx - 30):peak_idx + 1]
        trough = mids[max(0, peak_idx - 30):peak_idx + 1]
        pm60 = (mids[t] - mids[t - 60]) / mids[t - 60] * 100 if t >= 60 else None
        # SHORT: lower-high rollover in down/flat context
        if mids[peak_idx] == max(prior) and mids[t] < mids[peak_idx] and (pm60 is None or pm60 <= 0.3) and (t - last_trig["SHORT"]) >= COOLDOWN_MIN:
            zones.append(_mkzone(window_id, "SHORT", t, minutes, mids)); last_trig["SHORT"] = t
        # LONG (absorption-reversal watch): higher-low bounce after down pressure
        elif mids[peak_idx] == min(trough) and mids[t] > mids[peak_idx] and (pm60 is not None and pm60 <= -0.5) and (t - last_trig["LONG"]) >= COOLDOWN_MIN:
            zones.append(_mkzone(window_id, "LONG", t, minutes, mids)); last_trig["LONG"] = t
    return zones


def _mkzone(window_id, direction, t, minutes, mids):
    m = minutes[t]; entry = mids[t]
    # forward outcome (TP2/SL1.5), forward-only
    fav_max = 0.0; adv_max = 0.0; t2 = t25 = t3 = None; outcome = "TIMEOUT"
    end = min(len(mids), t + HORIZON_MIN)
    for j in range(t + 1, end):
        if direction == "SHORT": fav = (entry - mids[j]) / entry * 100; adv = (mids[j] - entry) / entry * 100
        else: fav = (mids[j] - entry) / entry * 100; adv = (entry - mids[j]) / entry * 100
        fav_max = max(fav_max, fav); adv_max = max(adv_max, adv)
        if t2 is None and fav_max >= 2: t2 = j - t
        if t25 is None and fav_max >= 2.5: t25 = j - t
        if t3 is None and fav_max >= 3: t3 = j - t
        if adv >= SL and t2 is None: outcome = "LOSS"; break
        if fav >= TP: outcome = "WIN"; break
    # decision features (causal, <= t)
    def back(n): return mids[t - n] if t >= n else None
    pm60 = (entry - back(60)) / back(60) * 100 if back(60) else None
    pm180 = (entry - back(180)) / back(180) * 100 if back(180) else None
    pm1d = (entry - back(1440)) / back(1440) * 100 if back(1440) else None
    rets = [(mids[k] - mids[k - 1]) / mids[k - 1] for k in range(max(1, t - 180), t) if mids[k - 1]]
    lv = round(st.pstdev(rets) * 100, 3) if len(rets) > 2 else None
    lookback = mids[max(0, t - 240):t + 1]
    dist_from_low = round((entry - min(lookback)) / min(lookback) * 100, 3) if lookback else None
    dist_from_high = round((max(lookback) - entry) / max(lookback) * 100, 3) if lookback else None
    # bounce/up-leg into peak (for SHORT) or down-leg into trough (LONG)
    seg = mids[max(0, t - 30):t + 1]
    bounce = round((max(seg) - min(seg)) / min(seg) * 100, 3) if seg else None
    return {"window_id": window_id, "exchange": EX, "ts_min": m["m"], "ts_iso": dt.datetime.fromtimestamp(m["m"] * 60, tz=dt.timezone.utc).isoformat(),
            "date": dt.datetime.fromtimestamp(m["m"] * 60, tz=dt.timezone.utc).strftime("%Y-%m-%d"), "direction_candidate": direction,
            "entry_price": round(entry, 2), "future_mfe_pct": round(fav_max, 3), "future_mae_pct": round(adv_max, 3),
            "hit2": int(fav_max >= 2), "hit2_5": int(fav_max >= 2.5), "hit3": int(fav_max >= 3),
            "loss": int(outcome == "LOSS"), "timeout": int(outcome == "TIMEOUT"), "outcome": outcome,
            "time_to_2_min": t2, "time_to_2_5_min": t25, "time_to_3_min": t3,
            "prior_move_60m": round(pm60, 3) if pm60 is not None else None, "prior_move_180m": round(pm180, 3) if pm180 is not None else None,
            "prior_move_1d": round(pm1d, 3) if pm1d is not None else None, "local_vol_180m": lv,
            "dist_from_recent_low_pct": dist_from_low, "dist_from_recent_high_pct": dist_from_high, "bounce_into_pivot_pct": bounce,
            "spread_bps": round(m["spread"], 3) if m["spread"] is not None else None, "depth_imbalance": round(m["depth_imb"], 4) if m["depth_imb"] is not None else None,
            "bid_depth_top10": round(m["bid_depth"], 3), "ask_depth_top10": round(m["ask_depth"], 3), "update_rate": m["updates"]}


def cluster(zones):
    """dedup same-direction zones within 120 min by trigger time."""
    out = []; by = defaultdict(list)
    for z in zones: by[(z["window_id"], z["direction_candidate"])].append(z)
    cid = 0
    for k, zs in by.items():
        zs.sort(key=lambda x: x["ts_min"]); cur = []; last = None
        for z in zs:
            if last is not None and z["ts_min"] - last > 120: out.append((cid, cur)); cid += 1; cur = []
            cur.append(z); last = z["ts_min"]
        if cur: out.append((cid, cur)); cid += 1
    clusters = []
    for cid2, cl in out:
        prim = cl[0]
        any_hit2 = max(z["hit2"] for z in cl); best_mfe = max(z["future_mfe_pct"] for z in cl)
        clusters.append({"cluster_id": f"{prim['window_id']}-{prim['direction_candidate']}-{cid2}", "primary": prim, "zones": cl,
                         "duplicate_cluster_size": len(cl), "any_hit2": any_hit2, "best_mfe": round(best_mfe, 3)})
    return clusters


# ---------- capital state ----------
def capital_state(c):
    z = c["primary"]; di = z.get("depth_imbalance"); pm60 = z.get("prior_move_60m"); pm180 = z.get("prior_move_180m")
    bounce = z.get("bounce_into_pivot_pct"); upd = z.get("update_rate") or 0; lv = z.get("local_vol_180m") or 0
    sp = z.get("spread_bps"); dist_low = z.get("dist_from_recent_low_pct")
    ev = []
    # FORCED_UNWIND: acceleration + activity spike + thin book
    if (pm60 is not None and pm60 <= -1.5) and upd > 0 and (lv is not None and lv >= 0.12) and (di is not None and di < -0.1):
        return "FORCED_UNWIND", 0.6, ["fast down accel pm60<=-1.5", "elevated local vol", "ask-heavy/thin bid"], "liquidation-like acceleration", "not absorption: bid not refilling"
    # ABSORPTION_AFTER_SELL_PRESSURE: prior sell pressure but price stops falling + bid-heavy depth
    if (pm180 is not None and pm180 <= -1.0) and (di is not None and di > 0.15) and (dist_low is not None and dist_low < 0.6):
        return "ABSORPTION_AFTER_SELL_PRESSURE", 0.55, ["prior markdown pm180<=-1", "bid-heavy depth_imb>0.15", "near recent low"], "supply being absorbed near low", "not active markdown: bid depth dominant -> short dangerous"
    # DISTRIBUTION_INTO_BOUNCE: there is a bounce but ask-heavy depth (selling into strength)
    if z["direction_candidate"] == "SHORT" and (bounce is not None and bounce >= 0.4) and (di is not None and di < -0.05) and (pm180 is not None and pm180 <= 0.5):
        return "DISTRIBUTION_INTO_BOUNCE", 0.55, ["bounce>=0.4% into pivot", "ask-heavy depth (supply)", "down/flat background"], "buyers stall, sellers reload at highs", "not active markdown: required a bounce first"
    # ACTIVE_MARKDOWN: down context, weak bounce, not bid-heavy
    if (pm60 is not None and pm60 <= -0.3) and (bounce is None or bounce < 0.6) and (di is None or di <= 0.1):
        return "ACTIVE_MARKDOWN", 0.5, ["down pm60<=-0.3", "weak/no bounce", "no bid dominance"], "seller in control, easy downside", "not distribution: bounce too weak"
    # NO_CONTROL_CHOP: depth imbalance near zero, mixed
    if di is not None and abs(di) < 0.05:
        return "NO_CONTROL_CHOP", 0.4, ["depth_imb ~0", "no clear control"], "flow flips, no capital control", "no dominant side"
    return "UNKNOWN", 0.2, ["insufficient evidence"], "cannot classify honestly", "—"


# ---------- evidence blocks (0-3 or N/A) ----------
def evidence_blocks(c):
    z = c["primary"]; di = z.get("depth_imbalance"); pm60 = z.get("prior_move_60m"); pm180 = z.get("prior_move_180m")
    bounce = z.get("bounce_into_pivot_pct"); upd = z.get("update_rate") or 0; lv = z.get("local_vol_180m"); sp = z.get("spread_bps")
    bd = z.get("bid_depth_top10") or 0; ad = z.get("ask_depth_top10") or 0; dist_low = z.get("dist_from_recent_low_pct"); dist_high = z.get("dist_from_recent_high_pct")
    dirn = z["direction_candidate"]
    def lvl(cond3, cond2, cond1): return 3 if cond3 else (2 if cond2 else (1 if cond1 else 0))
    # 1 effort_vs_result (PROXY from L2: activity/depth vs price progress; true trade effort N/A)
    # for SHORT absorption: ask-heavy + small bounce = result weak vs supply -> low; active markdown = aligned
    ev1 = "N/A_trades"
    if di is not None and bounce is not None:
        if dirn == "SHORT":
            ev1 = lvl(di < -0.2 and bounce < 0.5, di < -0.1, di < 0)  # supply dominant, weak bounce
        else:
            ev1 = lvl(di > 0.2, di > 0.1, di > 0)
    # 2 absorption_refill (PROXY: depth imbalance toward the defending side)
    ev2 = "N/A"
    if di is not None:
        ev2 = lvl(abs(di) > 0.3, abs(di) > 0.15, abs(di) > 0.05)
    # 3 initiative_control (PROXY: depth imbalance sign aligned with intended direction)
    ev3 = "N/A"
    if di is not None:
        aligned = (di < 0 and dirn == "SHORT") or (di > 0 and dirn == "LONG")
        ev3 = lvl(aligned and abs(di) > 0.2, aligned and abs(di) > 0.1, aligned)
    # 4 background_alignment (prior move down for SHORT continuation)
    ev4 = 0
    if pm60 is not None and pm180 is not None:
        if dirn == "SHORT": ev4 = lvl(pm60 <= -1 and pm180 <= -1, pm60 <= -0.3, pm60 <= 0.3)
        else: ev4 = lvl(pm180 <= -1.5, pm180 <= -0.5, pm180 <= 0)  # long counter-trend: aligned if prior down (reversal)
    # 5 not_overextended (room to TP; not already at the low for SHORT)
    ev5 = "N/A"
    if dist_low is not None and dist_high is not None:
        if dirn == "SHORT": ev5 = lvl(dist_low > 1.5, dist_low > 0.8, dist_low > 0.3)  # above recent low -> room down
        else: ev5 = lvl(dist_high > 1.5, dist_high > 0.8, dist_high > 0.3)
    # 6 liquidity_execution (spread tight, depth present, activity)
    ev6 = "N/A"
    if sp is not None:
        ev6 = lvl(sp < 1 and (bd + ad) > 2 and upd > 5, sp < 3 and (bd + ad) > 1, sp < 8)
    return {"effort_vs_result": ev1, "absorption_refill": ev2, "initiative_control": ev3,
            "background_alignment": ev4, "not_overextended": ev5, "liquidity_execution": ev6}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    all_summ = []; all_zones = []; all_clusters = []
    for wid, (a, b) in WINDOWS.items():
        days = daterange(a, b)
        minutes = load_minute(days)
        s = window_summary(days, minutes)
        if s is None:
            all_summ.append({"window_id": wid, "start_date": a, "end_date": b, "status": "NO_NORMALIZED_DATA"}); continue
        all_summ.append({"window_id": wid, "start_date": a, "end_date": b, "exchange": EX, **{k: v for k, v in s.items() if k != "minutes"}})
        zs = build_zones(wid, minutes); all_zones += zs
        all_clusters += cluster(zs)

    # ---- C: windows summary ----
    with (OUT / "TREND_DOWN_WINDOWS_SUMMARY.csv").open("w", encoding="utf-8", newline="") as fh:
        cols = ["window_id", "start_date", "end_date", "exchange", "net_pct", "median_daily_range_pct", "max_daily_range_pct",
                "max_intraday_dd_pct", "max_intraday_bounce_pct", "total_updates", "rv_hourly_proxy_pct", "trend_down_confirmed",
                "strongest_down_days", "strongest_bounce_days", "status"]
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore"); w.writeheader()
        for r in all_summ: w.writerow({k: (json.dumps(v) if isinstance(v, list) else v) for k, v in r.items()})
    cmd = ["# TREND_DOWN WINDOWS SUMMARY", "", f"Build {now_iso()} · Bybit ob200 mid-price (no in-window trades). CALIBRATION.", "",
           "| window | dates | net% | medRange% | maxRange% | maxDD% | maxBounce% | RVproxy | TREND_DOWN? |", "|---|---|--:|--:|--:|--:|--:|--:|:--:|"]
    for r in all_summ:
        if r.get("status") == "NO_NORMALIZED_DATA": cmd.append(f"| {r['window_id']} | {r['start_date']}..{r['end_date']} | — | — | — | — | — | — | NO_DATA |"); continue
        cmd.append(f"| {r['window_id']} | {r['start_date']}..{r['end_date']} | {r['net_pct']} | {r['median_daily_range_pct']} | {r['max_daily_range_pct']} | {r['max_intraday_dd_pct']} | {r['max_intraday_bounce_pct']} | {r['rv_hourly_proxy_pct']} | {r['trend_down_confirmed']} |")
    for r in all_summ:
        if r.get("status") != "NO_NORMALIZED_DATA":
            cmd.append(f"\n**{r['window_id']}** strongest_down_days={r['strongest_down_days']} strongest_bounce_days={r['strongest_bounce_days']}")
    (OUT / "TREND_DOWN_WINDOWS_SUMMARY.md").write_text("\n".join(cmd), encoding="utf-8")

    # ---- D: zones + clusters ----
    if all_zones:
        zcols = list(all_zones[0].keys())
        with (OUT / "TREND_DOWN_ZONES_RAW.csv").open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=zcols, extrasaction="ignore"); w.writeheader()
            for z in all_zones: w.writerow(z)
    ccols = ["cluster_id", "window_id", "exchange", "date", "direction_candidate", "ts_iso", "entry_price",
             "duplicate_cluster_size", "is_primary_cluster", "any_hit2", "best_mfe", "primary_outcome", "primary_hit2", "primary_hit2_5", "primary_hit3",
             "primary_loss", "primary_timeout", "time_to_2_min", "time_to_2_5_min", "time_to_3_min"]
    crows = []
    for c in all_clusters:
        p = c["primary"]
        crows.append({"cluster_id": c["cluster_id"], "window_id": p["window_id"], "exchange": EX, "date": p["date"], "direction_candidate": p["direction_candidate"],
                      "ts_iso": p["ts_iso"], "entry_price": p["entry_price"], "duplicate_cluster_size": c["duplicate_cluster_size"], "is_primary_cluster": 1,
                      "any_hit2": c["any_hit2"], "best_mfe": c["best_mfe"], "primary_outcome": p["outcome"], "primary_hit2": p["hit2"], "primary_hit2_5": p["hit2_5"],
                      "primary_hit3": p["hit3"], "primary_loss": p["loss"], "primary_timeout": p["timeout"],
                      "time_to_2_min": p["time_to_2_min"], "time_to_2_5_min": p["time_to_2_5_min"], "time_to_3_min": p["time_to_3_min"]})
    with (OUT / "TREND_DOWN_UNIQUE_CLUSTERS.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=ccols, extrasaction="ignore"); w.writeheader()
        for r in crows: w.writerow(r)

    # ---- E: capital state + F: evidence ----
    cb_rows = []; ev_rows = []
    for c in all_clusters:
        p = c["primary"]; cs, conf, why, why2, whynot = capital_state(c); eb = evidence_blocks(c)
        cb_rows.append({"cluster_id": c["cluster_id"], "exchange": EX, "date": p["date"], "window_id": p["window_id"],
                        "capital_state_candidate": cs, "confidence": conf, "direction_candidate": p["direction_candidate"],
                        "hit2": p["hit2"], "hit2_5": p["hit2_5"], "hit3": p["hit3"], "loss": p["loss"], "timeout": p["timeout"],
                        "evidence_summary": "; ".join(why), "why_this_state": why2, "why_not_other_state": whynot,
                        "notes": f"depth_imb={p.get('depth_imbalance')} pm60={p.get('prior_move_60m')} bounce={p.get('bounce_into_pivot_pct')}"})
        ev_rows.append({"cluster_id": c["cluster_id"], "capital_state": cs, "direction": p["direction_candidate"], "outcome": p["outcome"], **eb})
    with (OUT / "CAPITAL_STATE_CASEBOOK.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(cb_rows[0].keys()) if cb_rows else ["cluster_id"], extrasaction="ignore"); w.writeheader()
        for r in cb_rows: w.writerow(r)
    (OUT / "CAPITAL_STATE_CASEBOOK.json").write_text(json.dumps({"build": now_iso(), "clusters": cb_rows}, indent=2, default=str), encoding="utf-8")
    cs_counts = defaultdict(lambda: [0, 0, 0])  # n, hit2, loss
    for r in cb_rows:
        a = cs_counts[r["capital_state_candidate"]]; a[0] += 1; a[1] += r["hit2"]; a[2] += r["loss"]
    csmd = ["# CAPITAL STATE CASEBOOK (TREND_DOWN)", "", f"Build {now_iso()} · capital_state is the primary label (retail terms only in notes).", "",
            "## Distribution", "| capital_state | clusters | hit2 | loss |", "|---|--:|--:|--:|"]
    for k, v in sorted(cs_counts.items(), key=lambda x: -x[1][0]): csmd.append(f"| {k} | {v[0]} | {v[1]} | {v[2]} |")
    csmd += ["", "## Per-cluster (first 40)"]
    for r in cb_rows[:40]:
        csmd.append(f"- **{r['cluster_id']}** [{r['capital_state_candidate']} c={r['confidence']}] {r['direction_candidate']} hit2={r['hit2']} loss={r['loss']} — {r['why_this_state']} ({r['notes']})")
    (OUT / "CAPITAL_STATE_CASEBOOK.md").write_text("\n".join(csmd), encoding="utf-8")
    with (OUT / "EVIDENCE_BLOCK_SCORES.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(ev_rows[0].keys()) if ev_rows else ["cluster_id"], extrasaction="ignore"); w.writeheader()
        for r in ev_rows: w.writerow(r)

    # ---- G: candidate filters ----
    def stats_for(pred):
        cl = [c for c in all_clusters if pred(c)]
        prim = [c["primary"] for c in cl]
        W = sum(1 for p in prim if p["outcome"] == "WIN"); L = sum(1 for p in prim if p["outcome"] == "LOSS"); TO = sum(1 for p in prim if p["outcome"] == "TIMEOUT")
        h2 = sum(p["hit2"] for p in prim); n = len(prim)
        wins = sorted({p["window_id"] for p in prim})
        return {"clusters": n, "hit2_count": h2, "loss_count": L, "timeout_count": TO, "wins": W,
                "winrate": round(100 * W / max(n, 1), 1), "pf": pf_of(W, L), "expectancy_pct": round(st.mean([1.86 if p["outcome"] == "WIN" else -1.64 if p["outcome"] == "LOSS" else 0 for p in prim]), 3) if prim else None,
                "windows_observed": wins}
    def state_is(c, s): return capital_state(c)[0] == s
    def qual(s):
        n = s["clusters"]
        if n < 4: return "NEED_MORE_DATA"
        if (s["pf"] not in (None, "inf") and s["pf"] >= 1.2 and s["winrate"] >= 45): return "PROMISING"
        if (s["pf"] not in (None, "inf") and s["pf"] >= 0.9): return "WEAK"
        return "REJECT"
    templates = [
        ("TD_ACTIVE_MARKDOWN_SHORT_CANDIDATE", "ACTIVE_MARKDOWN", "SHORT", lambda c: state_is(c, "ACTIVE_MARKDOWN") and c["primary"]["direction_candidate"] == "SHORT",
         ["background_alignment>=2", "effort_vs_result>=1", "initiative_control>=1"], ["bid-heavy depth_imb>0.15 (absorption)", "spread>8bps"]),
        ("TD_DISTRIBUTION_INTO_BOUNCE_SHORT_CANDIDATE", "DISTRIBUTION_INTO_BOUNCE", "SHORT", lambda c: state_is(c, "DISTRIBUTION_INTO_BOUNCE"),
         ["bounce>=0.4%", "ask-heavy depth", "not_overextended>=1"], ["bid refill (depth_imb>0.15)", "low liquidity"]),
        ("TD_FORCED_UNWIND_CONTINUATION_CANDIDATE", "FORCED_UNWIND", "SHORT", lambda c: state_is(c, "FORCED_UNWIND"),
         ["acceleration pm60<=-1.5", "activity spike", "liquidity_execution>=1"], ["already at recent low (dist_low<0.5)", "spread blown out"]),
        ("TD_ABSORPTION_AFTER_SELL_PRESSURE_NO_SHORT_OR_REVERSAL_WATCH", "ABSORPTION_AFTER_SELL_PRESSURE", "NO_SHORT/LONG_WATCH", lambda c: state_is(c, "ABSORPTION_AFTER_SELL_PRESSURE"),
         ["bid-heavy depth_imb>0.15", "near recent low", "prior markdown"], ["fresh down acceleration", "depth_imb flips negative"]),
        ("TD_NO_CONTROL_CHOP_NO_TRADE", "NO_CONTROL_CHOP", "NO_TRADE", lambda c: state_is(c, "NO_CONTROL_CHOP"),
         ["depth_imb ~0", "flow flips"], ["—"]),
    ]
    filt = []
    for fid, state, direction, pred, req, veto in templates:
        s = stats_for(pred)
        filt.append({"filter_id": fid, "filter_name": fid, "level_1_background": "TREND_DOWN", "capital_state": state, "intended_direction": direction,
                     "required_conditions": req, "veto_conditions": veto, "optional_confirmations": ["microprice/CVD when trades available"],
                     "evidence_blocks_used": ["effort_vs_result", "absorption_refill", "initiative_control", "background_alignment", "not_overextended", "liquidity_execution"],
                     "suggested_thresholds": "capital_state match + >=3/6 evidence (>=2 each on bg/initiative)", "windows_observed": s["windows_observed"],
                     "number_of_clusters": s["clusters"], "hit2_count": s["hit2_count"], "loss_count": s["loss_count"], "timeout_count": s["timeout_count"],
                     "winrate": s["winrate"], "pf": s["pf"], "expectancy_pct": s["expectancy_pct"], "quality": qual(s),
                     "overfit_risk": "HIGH" if s["clusters"] < 6 else ("MED" if s["clusters"] < 15 else "LOW"),
                     "notes": "L2-only calibration; trade-flow confirmations N/A; SHORT entries are pivot/lower-high proxies"})
    (OUT / "FILTER_CANDIDATES_TREND_DOWN_V1.json").write_text(json.dumps({"build": now_iso(), "status": "CALIBRATION_CANDIDATE_LIBRARY", "filters": filt}, indent=2, default=str), encoding="utf-8")
    with (OUT / "FILTER_CANDIDATES_TREND_DOWN_V1.csv").open("w", encoding="utf-8", newline="") as fh:
        cols = ["filter_id", "capital_state", "intended_direction", "number_of_clusters", "hit2_count", "loss_count", "timeout_count", "winrate", "pf", "expectancy_pct", "quality", "overfit_risk", "windows_observed"]
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore"); w.writeheader()
        for r in filt: w.writerow({**r, "windows_observed": json.dumps(r["windows_observed"])})

    steps = ["# FILTER STEPS — TREND_DOWN V1 (candidate library, calibration)", "", f"Build {now_iso()} · NOT a production rule. TP=2%, SL=1.5% unchanged.", "",
             "## 1. Level 1 = TREND_DOWN", "Confirm window net <= -1% (or PARTIAL <= +0.5%) on Bybit mid; prior 60m/180m move down.", "",
             "## 2. Capital state", "Classify each unique cluster into one of: ACTIVE_MARKDOWN / DISTRIBUTION_INTO_BOUNCE / FORCED_UNWIND /",
             "ABSORPTION_AFTER_SELL_PRESSURE / NO_CONTROL_CHOP / UNKNOWN using prior move, bounce size, depth_imbalance, activity.", "",
             "## 3. Evidence blocks (0-3 each, N/A if feature absent)",
             "effort_vs_result (PROXY), absorption_refill (PROXY), initiative_control (PROXY), background_alignment, not_overextended, liquidity_execution.", "",
             "## 4. Required conditions (per template)"] + [f"- {t[0]}: {t[4]}" for t in templates] + ["",
             "## 5. Veto conditions"] + [f"- {t[0]}: {t[5]}" for t in templates] + ["",
             "## 6. When entry is forbidden", "- NO_CONTROL_CHOP -> no trade.", "- ABSORPTION_AFTER_SELL_PRESSURE -> no fresh short (reversal watch only).",
             "- low liquidity / blown spread -> no trade.", "",
             "## 7. What counts as promising", "PF>=1.2 AND winrate>=45% AND clusters>=4 across >=2 windows.", "",
             "## 8. What NOT to use yet", "- Any template with <4 clusters (NEED_MORE_DATA).",
             "- Trade-flow confirmations (taker imbalance/CVD) until in-window trades exist.", "- Anything tuned to a single window/day."]
    (OUT / "FILTER_STEPS_TREND_DOWN_V1.md").write_text("\n".join(steps), encoding="utf-8")

    # ---- evidence definitions ----
    (OUT / "EVIDENCE_BLOCK_DEFINITIONS.md").write_text("\n".join([
        "# EVIDENCE BLOCK DEFINITIONS (TREND_DOWN v1)", "", f"Build {now_iso()} · scores 0=none,1=weak,2=med,3=strong, N/A=feature absent.", "",
        "1. **effort_vs_result** — PROXY (no trades): L2 depth_imbalance vs price progress. SHORT: ask-heavy depth + weak bounce = high. True taker-effort N/A.",
        "2. **absorption_refill** — PROXY: magnitude of depth_imbalance toward the defending side (bid refill after dip / ask refill after pop).",
        "3. **initiative_control** — PROXY: depth_imbalance sign aligned with intended direction (seller initiative for SHORT).",
        "4. **background_alignment** — prior 60m/180m move down for SHORT continuation (causal).",
        "5. **not_overextended** — distance above recent low (SHORT) so there is room to TP2; penalize entries already at the low.",
        "6. **liquidity_execution** — spread tight, top-10 depth present, update activity sufficient.", "",
        "Reliable on this dataset: background_alignment, not_overextended, liquidity_execution, absorption_refill/initiative (L2 proxy).",
        "N/A: effort_vs_result from real executions, taker imbalance, CVD, true volume (no in-window trades)."]), encoding="utf-8")

    # ---- H: technical report ----
    cs_dist = {k: v[0] for k, v in cs_counts.items()}
    tech = ["# TREND_DOWN CALIBRATION — TECHNICAL REPORT", "", f"Build {now_iso()} · RESEARCH/CALIBRATION ONLY · TP=2% SL=1.5% unchanged · no production/Telegram.", "",
            "## 1-2. Data found / missing", "- Bybit ob200 (L2): COMPLETE 12/12 window days. OKX L2: only 3 last-days. Bybit trades: NONE. OKX trades: out-of-window only.",
            "- See DATA_INVENTORY.md. In-window price/L2 from Bybit ob200 mid; trade-flow N/A (proxied).", "",
            "## 3-4. Exchanges / windows processed", f"- Bybit, windows: {list(WINDOWS.keys())} ({', '.join(a+'..'+b for a,b in WINDOWS.values())}).", "",
            "## 5. Zones / clusters", f"- raw zones: {len(all_zones)}; unique clusters: {len(all_clusters)} (SIMPLIFIED L2-pivot builder, causal, forward-labeled).", "",
            "## 6. Capital states observed", f"- {cs_dist}", "",
            "## 7-8. Evidence reliability", "- Reliable: background_alignment, not_overextended, liquidity_execution, depth-based absorption/initiative (PROXY).",
            "- N/A (no in-window trades): effort_vs_result from executions, taker imbalance, CVD, true volume.", "",
            "## 9. Candidate filters saved", "| filter | state | n | hit2 | loss | winrate | PF | quality |", "|---|---|--:|--:|--:|--:|--:|:--:|"]
    for r in filt: tech.append(f"| {r['filter_id']} | {r['capital_state']} | {r['number_of_clusters']} | {r['hit2_count']} | {r['loss_count']} | {r['winrate']} | {r['pf']} | {r['quality']} |")
    tech += ["", "## 10. Artifacts", "(see ARTIFACTS_LOCATION below)", "",
             "## 11. Next pass", "- Add in-window TRADES (Bybit + OKX) to unlock effort_vs_result / taker imbalance / CVD.",
             "- Re-run with full trade-flow evidence; compare capital_state separation with trades vs L2-proxy.",
             "- Get OKX full 4-day L2 per window for cross-venue capital-state agreement.", "",
             "ARTIFACTS_LOCATION:",
             "- main_folder: reports/trend_down_calibration_v1/",
             "- inventory: DATA_INVENTORY.csv / DATA_INVENTORY.md",
             "- normalized_schema: NORMALIZED_SCHEMA.md (+ _normalized/*.csv.gz)",
             "- windows_summary: TREND_DOWN_WINDOWS_SUMMARY.csv / .md",
             "- raw_zones: TREND_DOWN_ZONES_RAW.csv",
             "- unique_clusters: TREND_DOWN_UNIQUE_CLUSTERS.csv",
             "- capital_state_casebook: CAPITAL_STATE_CASEBOOK.csv / .json / .md",
             "- evidence_scores: EVIDENCE_BLOCK_SCORES.csv (+ EVIDENCE_BLOCK_DEFINITIONS.md)",
             "- filter_candidates: FILTER_CANDIDATES_TREND_DOWN_V1.json / .csv",
             "- filter_steps: FILTER_STEPS_TREND_DOWN_V1.md",
             "- technical_report: TREND_DOWN_CALIBRATION_TECHNICAL_REPORT.md"]
    (OUT / "TREND_DOWN_CALIBRATION_TECHNICAL_REPORT.md").write_text("\n".join(tech), encoding="utf-8")

    # console
    print("WINDOWS:")
    for r in all_summ: print(" ", {k: r.get(k) for k in ("window_id", "net_pct", "median_daily_range_pct", "trend_down_confirmed", "status")})
    print(f"zones {len(all_zones)} | clusters {len(all_clusters)}")
    print("capital states:", dict(cs_dist))
    print("FILTERS:")
    for r in filt: print(f"  {r['filter_id']:<52} n{r['number_of_clusters']:>3} hit2 {r['hit2_count']} loss {r['loss_count']} wr {r['winrate']}% PF {r['pf']} {r['quality']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
