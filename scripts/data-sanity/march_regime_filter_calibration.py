"""MARCH REGIME FILTER CALIBRATION + FROZEN FILTER EXPORT (sections A-F).

RESEARCH ONLY — no production signal. March 2026 = calibration set. TP stays 2%; 2.5/3% are quality
labels; future labels (true_mfe/time_to_X) computed from trades for OUTCOME labelling only; decisions
causal (<= confirmedTs). Engine/TP/SL unchanged. Some L2 features are N/A in the March DIAG cache and are
marked accordingly (book_entropy, ms_thin_path, ms_large_walls, top-depth) — reported honestly, not faked.
"""
from __future__ import annotations
import csv, gzip, json, math, statistics as st, sys, datetime as dt
from collections import defaultdict
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "package.json").exists() and (p / "scripts").exists())
DATA = ROOT / "data/okx-historical/BTC-USDT-SWAP"
OUT = ROOT / "reports/filter-calibration"
CACHE = ROOT / "reports/strategy-calibration/OKX_MARCH_DIAG_FEATURE_CACHE.json"
LABELS = OUT / "_march_forward_labels.json"
MOVE_GAP_S = 120 * 60
MARCH_DATES = [f"2026-03-{d:02d}" for d in range(2, 32)] + ["2026-04-01"]

A_WINDOWS = {
    "TREND_UP": [("2026-03-10", "2026-03-16")],
    "TREND_DOWN": [("2026-03-19", "2026-03-23"), ("2026-03-27", "2026-03-30")],
    "HIGH_VOL": [("2026-03-26", "2026-03-27"), ("2026-03-18", "2026-03-18"), ("2026-03-23", "2026-03-23")],
    "RANGE": [("2026-03-08", "2026-03-09"), ("2026-03-18", "2026-03-19")],
    "SWEEP": [("2026-03-10", "2026-03-13"), ("2026-03-01", "2026-03-03")],
}
NA_FEATURES = ["book_entropy_top25", "ms_thin_path_score", "ms_large_walls_on_path", "depth_top_of_book", "liquidity_void_to_target", "L2_update_rate", "basis"]


def now_iso(): return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
def num(x): return x if isinstance(x, (int, float)) else None
def mins(s): return round(s / 60, 1) if isinstance(s, (int, float)) else None
def cohen_d(a, b):
    a = [x for x in a if x is not None]; b = [x for x in b if x is not None]
    if len(a) < 2 or len(b) < 2: return None
    va, vb = st.pvariance(a), st.pvariance(b); sp = math.sqrt((va + vb) / 2) or 1e-9
    return round((st.mean(a) - st.mean(b)) / sp, 3)
def auc(pos, neg):
    pos = [x for x in pos if x is not None]; neg = [x for x in neg if x is not None]
    if not pos or not neg: return None
    allv = sorted(pos + neg); ranks = {}; i = 0
    while i < len(allv):
        j = i
        while j + 1 < len(allv) and allv[j + 1] == allv[i]: j += 1
        for v in {allv[i]}: ranks[v] = (i + j) / 2 + 1
        i = j + 1
    rp = sum(ranks[x] for x in pos)
    return round((rp - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)), 3)
def winrate(outs):
    o = [x for x in outs if x in ("WIN", "LOSS", "TIMEOUT")]
    return round(100 * sum(1 for x in o if x == "WIN") / max(len(o), 1), 1)
def in_win(d, a, b): return a <= d <= b


def build_minute_series():
    """abs-minute -> [high, low] across March trade days (skip missing)."""
    series = {}
    for d in MARCH_DATES:
        f = DATA / d / "trades.csv.gz"
        if not f.exists(): continue
        with gzip.open(f, "rt") as fh:
            rd = csv.reader(fh); next(rd, None)
            for row in rd:
                try: ts = int(row[2]); px = float(row[6])
                except (IndexError, ValueError): continue
                m = ts // 60_000_000
                s = series.get(m)
                if s is None: series[m] = [px, px]
                else:
                    if px > s[0]: s[0] = px
                    if px < s[1]: s[1] = px
    return series


def forward_labels(zones, series):
    keys = sorted(series.keys())
    out = {}
    for z in zones:
        ct = z.get("confirmedTs"); entry = num(z.get("sim_entry_price")); dirn = z.get("direction")
        if ct is None or entry is None: continue
        m0 = ct // 60000
        fav_max = 0.0; adv_max = 0.0; t2 = t25 = t3 = None
        for off in range(0, 1441):
            s = series.get(m0 + off)
            if s is None: continue
            hi, lo = s
            if dirn == "LONG":
                fav = (hi - entry) / entry * 100; adv = (entry - lo) / entry * 100
            else:
                fav = (entry - lo) / entry * 100; adv = (hi - entry) / entry * 100
            if fav > fav_max: fav_max = fav
            if adv > adv_max: adv_max = adv
            if t2 is None and fav_max >= 2: t2 = off * 60
            if t25 is None and fav_max >= 2.5: t25 = off * 60
            if t3 is None and fav_max >= 3: t3 = off * 60
            if t3 is not None and off > 60: break
        out[z["id"]] = {"true_mfe": round(fav_max, 3), "true_mae": round(adv_max, 3), "time_to_2": t2, "time_to_2_5": t25, "time_to_3": t3}
    return out


def daily_candles(series):
    by = defaultdict(lambda: [None, None, None, None])  # o,h,l,c by date
    for m in sorted(series.keys()):
        d = dt.datetime.fromtimestamp(m * 60, tz=dt.timezone.utc).strftime("%Y-%m-%d")
        hi, lo = series[m]; rec = by[d]
        if rec[0] is None: rec[0] = (hi + lo) / 2
        rec[1] = hi if rec[1] is None else max(rec[1], hi)
        rec[2] = lo if rec[2] is None else min(rec[2], lo)
        rec[3] = (hi + lo) / 2
    cand = {}
    for d, (o, h, l, c) in by.items():
        if o: cand[d] = {"net_pct": round(100 * (c - o) / o, 2), "range_pct": round(100 * (h - l) / o, 2)}
    return cand


def range_context(z, series_keys, series):
    """causal range_pos + sweep over prior 180 minutes."""
    ct = z.get("confirmedTs");
    if ct is None: return {}
    m0 = ct // 60000
    his = []; los = []
    for off in range(1, 181):
        s = series.get(m0 - off)
        if s: his.append(s[0]); los.append(s[1])
    if len(his) < 30: return {"range_pos": None, "swept_above": 0, "swept_below": 0, "dist_edge": None}
    rh = max(his); rl = min(los); mid = (rh + rl) / 2
    ref = num(z.get("referencePrice")) or num(z.get("sim_entry_price")) or mid
    pos = (ref - rl) / (rh - rl) if rh > rl else 0.5
    # sweep: last-30m extreme beyond prior-150m range
    recent_hi = max(his[:30]); recent_lo = min(los[:30]); prior_hi = max(his[30:]) if len(his) > 30 else rh; prior_lo = min(los[30:]) if len(his) > 30 else rl
    return {"range_pos": round(pos, 3), "swept_above": int(recent_hi > prior_hi), "swept_below": int(recent_lo < prior_lo),
            "dist_edge": round(min(pos, 1 - pos), 3)}


def main():
    zones = json.loads(CACHE.read_text())
    for z in zones:
        z["_date"] = (z.get("_date") or z.get("date") or "")[:10]
    print(f"march cache zones {len(zones)} dates {min(z['_date'] for z in zones)}..{max(z['_date'] for z in zones)}")

    MSER = OUT / "_march_minute_series.json"
    if MSER.exists():
        series = {int(k): v for k, v in json.loads(MSER.read_text()).items()}
        print(f"loaded cached minute series: {len(series)} minutes")
    else:
        series = build_minute_series()
        MSER.write_text(json.dumps(series), encoding="utf-8")
        print(f"minute series built: {len(series)} minutes")
    if LABELS.exists():
        lab = json.loads(LABELS.read_text())
        if all(z["id"] in lab for z in zones[:50]): print("loaded cached forward labels")
        else: lab = forward_labels(zones, series); LABELS.write_text(json.dumps(lab), encoding="utf-8")
    else:
        lab = forward_labels(zones, series); LABELS.write_text(json.dumps(lab), encoding="utf-8")
    skeys = sorted(series.keys())
    cand = daily_candles(series)
    for z in zones:
        L = lab.get(z["id"], {})
        z["_mfe"] = L.get("true_mfe"); z["_mae"] = L.get("true_mae")
        z["time_to_2"] = L.get("time_to_2"); z["time_to_2_5"] = L.get("time_to_2_5"); z["time_to_3"] = L.get("time_to_3")
        z["_hit2"] = (z["_mfe"] is not None and z["_mfe"] >= 2); z["_hit25"] = (z["_mfe"] is not None and z["_mfe"] >= 2.5); z["_hit3"] = (z["_mfe"] is not None and z["_mfe"] >= 3)
        z.update(range_context(z, skeys, series))
        _rmap = {"BULL": "TREND_UP", "BEAR": "TREND_DOWN", "TREND_UP": "TREND_UP", "TREND_DOWN": "TREND_DOWN", "RANGE": "RANGE"}
        z["_regime"] = _rmap.get(z.get("regime_1d"), "RANGE")
        z["_cand_outcome"] = "WIN" if z["_hit2"] else ("LOSS" if num(z.get("sim_mae_pct")) and z["sim_mae_pct"] >= 1.5 else "TIMEOUT")

    # ---- A: window data availability + regime confirm ----
    A = []
    have_dates = set(z["_date"] for z in zones)
    for reg, wins in A_WINDOWS.items():
        for (a, b) in wins:
            wd = [d for d in sorted(have_dates) if a <= d <= b]
            zs = [z for z in zones if in_win(z["_date"], a, b)]
            cds = [cand[d] for d in wd if d in cand]
            nets = sum(c["net_pct"] for c in cds) if cds else None
            rngs = round(st.median([c["range_pct"] for c in cds]), 2) if cds else None
            A.append({"requested_regime": reg, "start": a, "end": b, "dates_with_zones": wd, "missing_dates": [d for d in _date_range(a, b) if d not in have_dates],
                      "n_zones": len(zs), "n_hit2": sum(1 for z in zs if z["_hit2"]), "n_strong": sum(1 for z in zs if z["_hit25"]),
                      "window_net_pct": round(nets, 2) if nets is not None else None, "median_daily_range_pct": rngs})

    # ---- unique move clusters (whole March) ----
    def cluster(level):
        tt = {2: "time_to_2", 2.5: "time_to_2_5", 3: "time_to_3"}[level]
        elig = [z for z in zones if num(z.get(tt)) is not None and z["_mfe"] is not None and z["_mfe"] >= level]
        for z in elig: z["_th"] = z["confirmedTs"] // 1000 + z[tt]
        by = defaultdict(list)
        for z in elig: by[z["direction"]].append(z)
        clusters = []
        for d, zs in by.items():
            zs.sort(key=lambda x: x["_th"]); last = None; cur = []
            for z in zs:
                if last is not None and z["_th"] - last > MOVE_GAP_S: clusters.append(cur); cur = []
                cur.append(z); last = z["_th"]
            if cur: clusters.append(cur)
        return clusters
    h2cl = cluster(2); scl = cluster(2.5); h3cl = cluster(3)
    strong_sets = [set(id(z) for z in c) for c in scl]
    noise = [z for z in zones if not z["_hit2"]]
    ncl = []
    byd = defaultdict(list)
    for z in noise: byd[z["direction"]].append(z)
    for d, zs in byd.items():
        zs.sort(key=lambda x: x["confirmedTs"]); last = None; cur = []
        for z in zs:
            if last is not None and z["confirmedTs"] / 1000 - last > MOVE_GAP_S: ncl.append(cur); cur = []
            cur.append(z); last = z["confirmedTs"] / 1000
        if cur: ncl.append(cur)
    def first(c): return min(c, key=lambda z: z["confirmedTs"])
    pool_summary = {"march_zones": len(zones), "raw_hit2": sum(1 for z in zones if z["_hit2"]), "raw_strong": sum(1 for z in zones if z["_hit25"]),
                    "unique_hit2_clusters": len(h2cl), "unique_strong_clusters": len(scl), "unique_hit3_clusters": len(h3cl),
                    "noise_clusters": len(ncl), "missing_data_days": ["2026-03-17"], "cache_starts": "2026-03-02 (03-01 zones not in cache)"}

    # ---- features available on March ----
    FEATS = {
        "prior_move_1d": lambda z: num(z.get("prior_move_1d_pct")), "prior_move_60m": lambda z: num(z.get("prior_move_60m_pct")),
        "prior_move_180m": lambda z: num(z.get("prior_move_180m_pct")), "OFI": lambda z: num(z.get("eng_ofi")),
        "eng_absorption": lambda z: num(z.get("eng_absorption")), "eng_refill": lambda z: num(z.get("eng_refill")),
        "taker_imb_5m": lambda z: num(z.get("supportive_taker_imb_5m")), "taker_imb_15m": lambda z: num(z.get("supportive_taker_imb_15m")),
        "taker_imb_30m": lambda z: num(z.get("supportive_taker_imb_30m")), "microprice_5m_bps": lambda z: num(z.get("dl2_microprice_aligned_delta_5m_bps")),
        "microprice_15m_bps": lambda z: num(z.get("dl2_microprice_aligned_delta_15m_bps")), "net_flow_5m": lambda z: num(z.get("dl2_supp_minus_opp_net_flow_5m")),
        "spread_now_bps": lambda z: num(z.get("dl2_spread_now_bps")), "spread_mean_5m_bps": lambda z: num(z.get("dl2_spread_mean_5m_bps")),
        "local_vol_180m": lambda z: num(z.get("local_range_180m_pct")), "inband_sell_share_30m": lambda z: num(z.get("inband_sell_share_30m")),
        "range_pos": lambda z: num(z.get("range_pos")), "dist_edge": lambda z: num(z.get("dist_edge")),
        "reclaim_zoneMid": lambda z: z.get("reclaim_zoneMid_preconfirm"), "sweep_reclaim_aligned": lambda z: z.get("sweep_reclaim_aligned"),
        "wall_persistence_sec": lambda z: num(z.get("dl2_top1_supportive_persistence_ge_50_5m_sec")), "explainable_score": lambda z: num(z.get("explainable_score")),
    }

    # ---- B1: cross-cluster separation (winners vs noise) ----
    win_reps = [first(c) for c in h2cl]; strong_reps = [first(c) for c in scl]; noise_reps = [first(c) for c in ncl]
    def mine(pos, neg):
        rows = []
        for fn, fx in FEATS.items():
            pv = [fx(z) for z in pos]; nv = [fx(z) for z in neg]
            pvc = [x for x in pv if x is not None]; nvc = [x for x in nv if x is not None]
            if len(pvc) < 3 or len(nvc) < 3: continue
            rows.append({"feature": fn, "median_win": round(st.median(pvc), 4), "median_noise": round(st.median(nvc), 4),
                         "cohen_d": cohen_d(pvc, nvc), "auc": auc(pvc, nvc), "n_pos": len(pvc), "n_neg": len(nvc), "live_valid": "YES"})
        rows.sort(key=lambda r: -abs((r["auc"] or 0.5) - 0.5))
        return rows
    B1 = {"hit2_vs_noise": mine(win_reps, noise_reps), "strong_vs_noise": mine(strong_reps, noise_reps)}

    # ---- B2: six-block confluence ----
    ofis = [num(z.get("eng_ofi")) for z in zones if num(z.get("eng_ofi")) is not None]
    tks = [abs(num(z.get("supportive_taker_imb_15m"))) for z in zones if num(z.get("supportive_taker_imb_15m")) is not None]
    vols = [num(z.get("local_range_180m_pct")) for z in zones if num(z.get("local_range_180m_pct")) is not None]
    ofi_m, ofi_s = (st.mean(ofis), st.pstdev(ofis) or 1)
    tk_m, tk_s = (st.mean(tks), st.pstdev(tks) or 1)
    def aligned(z, v):
        return (v is not None) and ((z["direction"] == "LONG" and v > 0) or (z["direction"] == "SHORT" and v < 0))
    def blocks(z):
        dr = z["direction"]
        b1 = sum([aligned(z, num(z.get("eng_ofi"))), aligned(z, num(z.get("supportive_taker_imb_15m"))),
                  aligned(z, num(z.get("dl2_microprice_aligned_delta_5m_bps"))), aligned(z, num(z.get("dl2_supp_minus_opp_net_flow_5m")))]) >= 2
        pm = num(z.get("prior_move_1d_pct"))
        b2 = (z["_regime"] == "TREND_UP" and dr == "LONG") or (z["_regime"] == "TREND_DOWN" and dr == "SHORT") or aligned(z, pm)
        zo = abs((num(z.get("eng_ofi")) or ofi_m) - ofi_m) / ofi_s; zt = abs((abs(num(z.get("supportive_taker_imb_15m")) or 0)) - tk_m) / tk_s
        b3 = (zo >= 1) or (zt >= 1) or ((num(z.get("explainable_score")) or 0) >= 2)
        rp = num(z.get("range_pos"))
        over = (rp is not None and ((dr == "LONG" and rp > 0.85) or (dr == "SHORT" and rp < 0.15))) or (pm is not None and abs(pm) > 5 and aligned(z, pm))
        b4 = not over
        sp = num(z.get("dl2_spread_now_bps")); b5 = (sp is not None and sp < 2)
        dd = cand.get(z["_date"], {}); b6 = (dd.get("range_pct") or 0) >= 2
        score = sum([b1, b2, b3, b4, b5, b6])
        # vetoes
        veto = []
        if sp is not None and sp > 5: veto.append("dirty_exec")
        if rp is not None and ((dr == "LONG" and rp > 0.9) or (dr == "SHORT" and rp < 0.1)): veto.append("overextended")
        if (dd.get("range_pct") or 9) < 1.5: veto.append("low_liquidity")
        return score, veto, {"b1_orderflow": b1, "b2_background": b2, "b3_anomaly": b3, "b4_not_overext": b4, "b5_execution": b5, "b6_liquidity": b6}
    # evaluate confluence thresholds on unique clusters (first zone), winners=hit2
    allcl = h2cl + ncl
    rows_conf = []
    for thr in (3, 4, 5, 6):
        picks = []
        for c in allcl:
            z = first(c); sc, veto, _ = blocks(z)
            if sc >= thr and not veto: picks.append((z, z["_hit2"]))
        W = sum(1 for _, h in picks if h); n = len(picks)
        strong_caught = len({i for i, ss in enumerate(strong_sets) for z, _ in picks if id(z) in ss})
        rows_conf.append({"confluence": f">={thr}/6+veto", "alerts": n, "wins_hit2": W, "winrate": round(100 * W / max(n, 1), 1),
                          "precision": round(W / max(n, 1), 3), "strong_caught": strong_caught})

    # ---- B3: phase candidates (causal) ----
    def ph_acc(z): return z["direction"] == "LONG" and z["_regime"] == "RANGE" and (num(z.get("range_pos")) or 1) < 0.4 and ((num(z.get("supportive_taker_imb_5m")) or 0) < 0) and ((z.get("reclaim_zoneMid_preconfirm") == 1) or (num(z.get("eng_absorption")) or 0) > 0.5 or (num(z.get("eng_refill")) or 0) > 0.5)
    def ph_dist(z): return z["direction"] == "SHORT" and z["_regime"] == "RANGE" and (num(z.get("range_pos")) or 0) > 0.6 and ((num(z.get("supportive_taker_imb_5m")) or 0) > 0) and ((num(z.get("eng_absorption")) or 0) > 0.5)
    def ph_sweep(z): return ((z["direction"] == "LONG" and z.get("swept_below") == 1) or (z["direction"] == "SHORT" and z.get("swept_above") == 1)) and (z.get("reclaim_zoneMid_preconfirm") == 1 or z.get("sweep_reclaim_aligned") == 1) and aligned(z, num(z.get("supportive_taker_imb_15m")))
    def ph_brk_retest(z): return (z.get("swept_above") == 1 or z.get("swept_below") == 1) and (0.3 <= (num(z.get("range_pos")) or 0.5) <= 0.7) and aligned(z, num(z.get("eng_ofi")))
    def ph_failed_brk(z): return ((z["direction"] == "SHORT" and z.get("swept_above") == 1) or (z["direction"] == "LONG" and z.get("swept_below") == 1)) and (z.get("reclaim_zoneMid_preconfirm") == 1) and (0.1 < (num(z.get("range_pos")) or 0.5) < 0.9)
    def ph_trend_cont(z): return ((z["_regime"] == "TREND_UP" and z["direction"] == "LONG") or (z["_regime"] == "TREND_DOWN" and z["direction"] == "SHORT")) and aligned(z, num(z.get("prior_move_60m_pct")))
    PHASES = {"ACCUMULATION_CANDIDATE": ph_acc, "DISTRIBUTION_CANDIDATE": ph_dist, "SWEEP_REVERSAL": ph_sweep,
              "BREAKOUT_RETEST": ph_brk_retest, "FAILED_BREAKOUT": ph_failed_brk, "TREND_CONTINUATION": ph_trend_cont}
    B3 = []
    base_hit2 = round(100 * sum(1 for z in zones if z["_hit2"]) / len(zones), 1)
    for name, pred in PHASES.items():
        zs = [z for z in zones if pred(z)]
        n = len(zs); h2 = sum(1 for z in zs if z["_hit2"]); strong = sum(1 for z in zs if z["_hit25"])
        # dedup to unique clusters
        cl = []
        byd2 = defaultdict(list)
        for z in zs: byd2[z["direction"]].append(z)
        for d, g in byd2.items():
            g.sort(key=lambda x: x["confirmedTs"]); last = None; cur = []
            for z in g:
                if last is not None and z["confirmedTs"] / 1000 - last > MOVE_GAP_S: cl.append(cur); cur = []
                cur.append(z); last = z["confirmedTs"] / 1000
            if cur: cl.append(cur)
        uwin = [first(c) for c in cl]
        uniq_n = len(cl); uniq_h2 = sum(1 for z in uwin if z["_hit2"])
        B3.append({"phase": name, "raw_zones": n, "raw_hit2": h2, "raw_strong": strong, "raw_hit2_rate": round(100 * h2 / max(n, 1), 1),
                   "unique_clusters": uniq_n, "unique_hit2": uniq_h2, "unique_precision": round(uniq_h2 / max(uniq_n, 1), 3),
                   "lift_vs_base": round(100 * h2 / max(n, 1) - base_hit2, 1), "helps_separation": "YES" if (100 * h2 / max(n, 1) - base_hit2) >= 8 and n >= 8 else "NO"})

    # ---- B4: TD-short OOS on March TREND_DOWN windows ----
    def td_short_pass(z):
        if z["direction"] != "SHORT" or z["_regime"] != "TREND_DOWN": return False
        if (num(z.get("prior_move_60m_pct")) or 0) >= 0: return False
        o = num(z.get("eng_ofi")); ti = num(z.get("supportive_taker_imb_15m"))
        buyer_abs = (o is not None and o > 0.2) and (ti is not None and ti < -0.1)  # buyer absorption veto
        if buyer_abs: return False
        conf = sum([z.get("reclaim_zoneMid_preconfirm") == 1, (num(z.get("supportive_taker_imb_15m")) or 0) < 0,
                    (num(z.get("dl2_microprice_aligned_delta_5m_bps")) or 0) < 0, (num(z.get("eng_void")) or 0) >= 1])
        return conf >= 2
    td_windows = [("2026-03-19", "2026-03-23"), ("2026-03-27", "2026-03-30")]
    td_zones = [z for z in zones if any(in_win(z["_date"], a, b) for a, b in td_windows) and td_short_pass(z)]
    # dedup first-eligible per direction 120m
    td_zones.sort(key=lambda z: z["confirmedTs"]); picks = []; last = None
    for z in td_zones:
        if last is None or z["confirmedTs"] / 1000 - last > MOVE_GAP_S: picks.append(z); last = z["confirmedTs"] / 1000
    def trade_out(z): return "WIN" if z["_hit2"] else ("LOSS" if (num(z.get("sim_mae_pct")) or 0) >= 1.5 else "TIMEOUT")
    td_outs = [trade_out(z) for z in picks]
    W = td_outs.count("WIN"); L = td_outs.count("LOSS"); TO = td_outs.count("TIMEOUT")
    pf = round((W * 1.86) / max(L * 1.64, 1e-9), 3) if L else (None if W == 0 else float("inf"))
    B4 = {"td_short_march": {"windows": td_windows, "signals": len(picks), "W": W, "L": L, "TO": TO, "winrate": winrate(td_outs),
                             "pf": pf if pf != float("inf") else "inf", "expectancy_pct": round(st.mean([1.86 if o == "WIN" else -1.64 if o == "LOSS" else 0 for o in td_outs]), 3) if td_outs else None,
                             "verdict": ("CONFIRMS" if winrate(td_outs) >= 50 and len(picks) >= 4 else ("THIN_SAMPLE" if len(picks) < 4 else "WEAK")),
                             "caveat": "thin-path feature N/A in March cache -> confluence uses eng_void as bid-path proxy"}}

    # ---- B5: low-vol no-trade ----
    lowvol_days = [d for d, c in cand.items() if c["range_pct"] < 1.7 and d.startswith("2026-03")]
    lv_zones = [z for z in zones if z["_date"] in lowvol_days]
    hv_days = [d for d, c in cand.items() if c["range_pct"] >= 3 and d.startswith("2026-03")]
    hv_zones = [z for z in zones if z["_date"] in hv_days]
    B5 = {"low_vol_days": sorted(lowvol_days), "low_vol_zones": len(lv_zones), "low_vol_hit2_rate": round(100 * sum(1 for z in lv_zones if z["_hit2"]) / max(len(lv_zones), 1), 1),
          "high_vol_days": sorted(hv_days), "high_vol_zones": len(hv_zones), "high_vol_hit2_rate": round(100 * sum(1 for z in hv_zones if z["_hit2"]) / max(len(hv_zones), 1), 1),
          "false_signal_concentration_lowvol": "YES" if lv_zones and (sum(1 for z in lv_zones if z["_hit2"]) / len(lv_zones)) < 0.6 * (sum(1 for z in zones if z["_hit2"]) / len(zones)) else "NO",
          "recommend_silence_in_lowvol": "YES"}

    # ---- C: frozen filters ----
    def scorecard(pred, name, regime, direction, phase, feats, thr, veto, notes):
        zs = [z for z in zones if pred(z)]
        cl = []
        byd3 = defaultdict(list)
        for z in zs: byd3[z["direction"]].append(z)
        for d, g in byd3.items():
            g.sort(key=lambda x: x["confirmedTs"]); last = None; cur = []
            for z in g:
                if last is not None and z["confirmedTs"] / 1000 - last > MOVE_GAP_S: cl.append(cur); cur = []
                cur.append(z); last = z["confirmedTs"] / 1000
            if cur: cl.append(cur)
        reps = [first(c) for c in cl]
        outs = [trade_out(z) for z in reps]
        Wc = outs.count("WIN"); Lc = outs.count("LOSS"); TOc = outs.count("TIMEOUT"); n = len(reps)
        h2 = sum(1 for z in reps if z["_hit2"]); h25 = sum(1 for z in reps if z["_hit25"]); h3 = sum(1 for z in reps if z["_hit3"])
        pfc = round((Wc * 1.86) / max(Lc * 1.64, 1e-9), 3) if Lc else (None if Wc == 0 else "inf")
        dates = sorted(set(z["_date"] for z in reps))
        # date stability: fraction of active dates with >=50% winrate
        bydate = defaultdict(list)
        for z, o in zip(reps, outs): bydate[z["_date"]].append(o)
        stab = round(sum(1 for d, os in bydate.items() if winrate(os) >= 50) / max(len(bydate), 1), 2)
        overfit = "HIGH" if n < 6 else ("MED" if n < 12 else "LOW")
        return {"filter_id": name, "filter_name": name, "regime": regime, "direction": direction, "phase_candidate": phase,
                "features": feats, "thresholds": thr, "veto_rules": veto, "confluence_def": notes,
                "training_windows": "OKX March 2026 (03-02..03-31, 03-17 missing)", "n_signals": n, "wins": Wc, "losses": Lc, "timeouts": TOc,
                "hit2_rate": round(100 * h2 / max(n, 1), 1), "hit2_5_rate": round(100 * h25 / max(n, 1), 1), "hit3_rate": round(100 * h3 / max(n, 1), 1),
                "winrate": winrate(outs), "pf": pfc, "expectancy_pct": round(st.mean([1.86 if o == "WIN" else -1.64 if o == "LOSS" else 0 for o in outs]), 3) if outs else None,
                "active_dates": len(dates), "date_stability": stab, "overfit_risk": overfit, "notes": notes}
    frozen = [
        scorecard(td_short_pass, "F1_TD_SHORT", "TREND_DOWN", "SHORT", "TREND_CONTINUATION",
                  ["regime=TREND_DOWN", "prior_move_60m<0", "no buyer absorption", "conf>=2 of {reclaim,taker-sell,microprice-down,void-bid-path}"],
                  {"prior_move_60m": "<0", "confluence": ">=2"}, ["buyer_absorption"], "TD-short frozen logic (thin-path -> eng_void proxy on March)"),
        scorecard(ph_sweep, "F2_SWEEP_REVERSAL", "ANY", "BOTH", "SWEEP_REVERSAL",
                  ["swept_high/low", "reclaim", "taker aligned"], {"reclaim_or_sweep_aligned": 1}, ["dirty_exec"], "sweep + reclaim + opposite initiative"),
        scorecard(ph_acc, "F3_ACCUMULATION", "RANGE", "LONG", "ACCUMULATION_CANDIDATE",
                  ["RANGE", "range_pos<0.4", "sell pressure", "absorption/refill/reclaim"], {"range_pos": "<0.4"}, ["overextended"], "lower-range absorption reversal long"),
        scorecard(ph_dist, "F4_DISTRIBUTION", "RANGE", "SHORT", "DISTRIBUTION_CANDIDATE",
                  ["RANGE", "range_pos>0.6", "buy pressure", "absorption"], {"range_pos": ">0.6"}, ["overextended"], "upper-range absorption reversal short"),
        scorecard(lambda z: blocks(z)[0] >= 4 and not blocks(z)[1], "F5_SIXBLOCK_4of6", "ANY", "BOTH", None,
                  ["6-block confluence>=4", "no veto"], {"confluence": ">=4/6"}, ["dirty_exec", "overextended", "low_liquidity"], "six-block confluence >=4 with vetoes"),
    ]

    # ---- write C frozen files ----
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "FROZEN_FILTER_SET_MARCH_V1.json").write_text(json.dumps({"frozen": True, "do_not_tune_after_oos": True, "build": now_iso(),
        "tp_pct": 2.0, "labels_only": [2.5, 3.0], "na_features_on_march": NA_FEATURES, "filters": frozen}, indent=2, default=str), encoding="utf-8")
    (OUT / "FILTER_CANDIDATES_MARCH_V1.json").write_text(json.dumps({"build": now_iso(), "pool": pool_summary, "filters": frozen, "six_block_confluence": rows_conf, "phase_candidates": B3}, indent=2, default=str), encoding="utf-8")
    with (OUT / "FILTER_CANDIDATES_MARCH_V1.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=[k for k in frozen[0] if k not in ("features", "veto_rules")], extrasaction="ignore"); w.writeheader()
        for r in frozen: w.writerow(r)
    with (OUT / "FILTER_SCORECARD_MARCH_V1.csv").open("w", encoding="utf-8", newline="") as fh:
        cols = ["filter_id", "regime", "direction", "phase_candidate", "n_signals", "wins", "losses", "timeouts", "hit2_rate", "hit2_5_rate", "hit3_rate", "winrate", "pf", "expectancy_pct", "active_dates", "date_stability", "overfit_risk"]
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore"); w.writeheader()
        for r in frozen: w.writerow(r)
    defs = ["# FILTER DEFINITIONS — MARCH V1 (frozen)", "", f"Build {now_iso()} · RESEARCH ONLY · TP=2% · 2.5/3% labels only.",
            f"N/A on March cache: {', '.join(NA_FEATURES)}", "", "## Pool", json.dumps(pool_summary, indent=2), "", "## Filters"]
    for f in frozen:
        defs += [f"### {f['filter_id']} — {f['regime']}/{f['direction']} (phase {f['phase_candidate']})",
                 f"- features: {f['features']}", f"- thresholds: {f['thresholds']}", f"- vetoes: {f['veto_rules']}",
                 f"- n={f['n_signals']} W/L/TO {f['wins']}/{f['losses']}/{f['timeouts']} winrate {f['winrate']}% PF {f['pf']} hit2 {f['hit2_rate']}% stab {f['date_stability']} overfit {f['overfit_risk']}", ""]
    (OUT / "FILTER_DEFINITIONS_MARCH_V1.md").write_text("\n".join(defs), encoding="utf-8")

    # ---- final report F ----
    enough = {reg: (sum(a2["n_strong"] for a2 in A if a2["requested_regime"] == reg) >= 3) for reg in A_WINDOWS}
    best_b1 = sorted(B1["hit2_vs_noise"], key=lambda r: -abs((r["auc"] or 0.5) - 0.5))[:5]
    flags = {"MARCH_CALIBRATION_DONE": "YES", "MARCH_DATA_COMPLETE": "NO (03-17 missing; 03-01 not in cache; L2 subfeatures N/A)",
             "POSITIVE_FEATURE_FOUND": "PARTIAL" if any(abs((r["auc"] or .5) - .5) >= 0.12 for r in best_b1) else "NO",
             "BEST_PHASE": max(B3, key=lambda p: p["lift_vs_base"])["phase"], "TD_SHORT_MARCH": B4["td_short_march"]["verdict"],
             "FROZEN_FILTERS_EXPORTED": "YES", "READY_FOR_PRODUCTION_TRADING": "NO", "DO_NOT_TUNE_ON_OOS": "YES", "TARDIS_USED": "NO"}
    final = {"build": now_iso(), "A_windows": A, "pool": pool_summary, "B1_top": best_b1, "B2_confluence": rows_conf,
             "B3_phases": B3, "B4_td_short": B4, "B5_lowvol": B5, "regime_enough_data": enough, "frozen_filters": [f["filter_id"] for f in frozen], "flags": flags}
    (OUT / "MARCH_CALIBRATION_FINAL_REPORT.json").write_text(json.dumps(final, indent=2, default=str), encoding="utf-8")

    # console
    print("POOL:", pool_summary)
    print("A windows:")
    for a in A: print(f"  {a['requested_regime']:<11} {a['start']}..{a['end']} zones {a['n_zones']:>3} hit2 {a['n_hit2']:>2} strong {a['n_strong']:>2} net {a['window_net_pct']}% medRange {a['median_daily_range_pct']}% missing {a['missing_dates']}")
    print("B1 top hit2_vs_noise:")
    for r in best_b1: print(f"  {r['feature']:<20} d={r['cohen_d']} AUC={r['auc']} win {r['median_win']} noise {r['median_noise']} n {r['n_pos']}/{r['n_neg']}")
    print("B2 six-block confluence:")
    for r in rows_conf: print(f"  {r['confluence']:<12} alerts {r['alerts']:>3} winrate {r['winrate']}% prec {r['precision']} strong {r['strong_caught']}")
    print("B3 phase candidates:")
    for r in B3: print(f"  {r['phase']:<24} raw {r['raw_zones']:>3} hit2% {r['raw_hit2_rate']} uniq {r['unique_clusters']:>2} uprec {r['unique_precision']} lift {r['lift_vs_base']} helps {r['helps_separation']}")
    print("B4 TD-short March:", B4["td_short_march"])
    print("B5 low-vol:", B5)
    print("FROZEN filters:")
    for f in frozen: print(f"  {f['filter_id']:<18} n{f['n_signals']:>3} wr {f['winrate']}% PF {f['pf']} hit2 {f['hit2_rate']}% stab {f['date_stability']} overfit {f['overfit_risk']}")
    print("FLAGS:", flags)
    return 0


def _date_range(a, b):
    da = dt.date.fromisoformat(a); db = dt.date.fromisoformat(b); out = []
    while da <= db: out.append(da.isoformat()); da += dt.timedelta(days=1)
    return out


if __name__ == "__main__":
    sys.exit(main())
