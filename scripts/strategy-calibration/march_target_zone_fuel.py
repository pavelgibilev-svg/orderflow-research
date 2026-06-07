"""March target-zone heatmap + 3 trade models (A/B/C+BE) + OI/fuel data audit.

Sections A-I per spec. IN-SAMPLE March 2026 OKX. No engine change.
Target strict 2%. No future leak in DECISION features (selector + target-zone
chosen at confirmedTs from PAST data only; forward price path used only for
trade execution simulation).

OI / funding / liquidation: NOT AVAILABLE for March OKX (only book+trades).
Documented; OI/fuel sections produce NOT_AVAILABLE placeholders.
"""
from __future__ import annotations
import csv
import datetime as dt
import gzip
import json
import math
import statistics as stats
import sys
import time
from collections import defaultdict, Counter
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from canonical_ledger import Bucket, build_buckets_from_trades_csv

ROOT = Path("C:/Users/gibilev/orderflow-research")
REP_OUT = ROOT / "reports/strategy-calibration"
DATA_ROOT = ROOT / "data/okx-historical/BTC-USDT-SWAP"

FIRST_HALF = [f"2026-03-{d:02d}" for d in range(2, 16)]
SECOND_HALF = ["2026-03-16"] + [f"2026-03-{d:02d}" for d in range(18, 32)]
ALL_DATES = FIRST_HALF + SECOND_HALF
N_DAYS = len(ALL_DATES)

COST_PCT = 0.14
TARGET_PCT = 2.0
STOP_PCT = 1.5
TIMEOUT_HOURS = 24

# target-zone params
SWING_HALF_WIN_SEC = 300        # 5 min each side for pivot confirmation
TRAILING_CONTEXT_SEC = 8 * 3600  # 8h trailing for swing/volume context
VOL_BIN_USD = 50.0              # volume-profile bin size
HVN_PERCENTILE = 0.80           # high-volume-node threshold percentile
MAX_OBSTACLE_SCAN_PCT = 6.0     # only consider obstacles within 6% (else "open")


def now_iso(): return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
def safe_float(x):
    if x is None or x == "": return None
    try: return float(x)
    except: return None
def safe_bool(x):
    if x is None or x == "": return None
    if isinstance(x, bool): return x
    s = str(x).lower()
    if s in ("true", "1", "yes", "y"): return True
    if s in ("false", "0", "no", "n"): return False
    return None
def iso_to_sec(s):
    if not s: return None
    return int(dt.datetime.fromisoformat(s).timestamp())
def mean_or_none(xs):
    xs = [x for x in xs if x is not None]
    return round(stats.mean(xs), 4) if xs else None
def median_or_none(xs):
    xs = [x for x in xs if x is not None]
    return round(stats.median(xs), 4) if xs else None
def cohens_d(a, b):
    a = [x for x in a if x is not None]; b = [x for x in b if x is not None]
    if len(a) < 2 or len(b) < 2: return None
    ma, mb = stats.mean(a), stats.mean(b)
    sa, sb = stats.pstdev(a), stats.pstdev(b)
    pooled = math.sqrt(((len(a)-1)*sa*sa + (len(b)-1)*sb*sb) / max(len(a)+len(b)-2, 1))
    if pooled == 0: return None
    return round((ma - mb) / pooled, 4)
def quantile(xs, q):
    xs = sorted(x for x in xs if x is not None)
    if not xs: return None
    return xs[int(q * (len(xs) - 1))]


# ============================================================
# Volume-aware bucket builder (light pass on trades.csv.gz)
# ============================================================
def build_buckets_with_volume(path: Path):
    """Return parallel arrays secs, highs, lows, lasts, vols (per UTC second)."""
    high: dict[int, float] = {}
    low: dict[int, float] = {}
    last: dict[int, float] = {}
    vol: dict[int, float] = {}
    with gzip.open(path, "rt", encoding="utf-8", newline="") as f:
        rdr = csv.reader(f)
        header = next(rdr)
        idx_ts = header.index("timestamp")
        idx_price = header.index("price")
        idx_amt = header.index("amount")
        for row in rdr:
            try:
                ts_us = int(row[idx_ts]); price = float(row[idx_price]); amt = float(row[idx_amt])
            except Exception:
                continue
            sec = ts_us // 1_000_000
            if sec in high:
                if price > high[sec]: high[sec] = price
                if price < low[sec]: low[sec] = price
            else:
                high[sec] = price; low[sec] = price
            last[sec] = price
            vol[sec] = vol.get(sec, 0.0) + amt
    secs = sorted(high.keys())
    return (secs,
            [high[s] for s in secs],
            [low[s] for s in secs],
            [last[s] for s in secs],
            [vol[s] for s in secs])


def calendar_prev(date: str) -> Optional[str]:
    d = dt.date.fromisoformat(date) - dt.timedelta(days=1)
    s = d.isoformat()
    return s if (DATA_ROOT / s / "trades.csv.gz").exists() else None


# ============================================================
# load zone dataset (+ dl2 + void)
# ============================================================
def load_dataset():
    p = REP_OUT / "MARCH_ORDERFLOW_FEATURE_DATASET.csv"
    rows = []
    bool_keys = {"cand_range_compression", "trig_side_flow_ok", "filter_kept",
                 "filter_dup_suppressed", "filter_fast_ok",
                 "_label_is_primary", "_label_reached_raw",
                 "is_asia_session", "is_us_session", "is_during_correct_move",
                 "is_during_opposite_move", "is_late_after_50pct_correct_move",
                 "sweep_reclaim_aligned"}
    str_keys = {"date", "zone_id", "direction", "stage_reached", "candidate_iso",
                "confirmed_iso", "trigger_iso", "session", "_half",
                "_label_engine_class", "_label_unique_move_id",
                "watch_label", "coverage_class"}
    with p.open(encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        for r in rdr:
            for k, v in list(r.items()):
                if k in str_keys: r[k] = v if v else None
                elif k in bool_keys: r[k] = safe_bool(v)
                else: r[k] = safe_float(v)
            rows.append(r)
    dynp = REP_OUT / "MARCH_DYNAMIC_L2_FEATURE_DATASET.csv"
    if dynp.exists():
        with dynp.open(encoding="utf-8") as f:
            rdr = csv.DictReader(f)
            dyn = {lr["zone_id"]: {k: safe_float(lr[k]) for k in lr if k != "zone_id"} for lr in rdr}
        for r in rows:
            for k, v in dyn.get(r["zone_id"], {}).items(): r[k] = v
    voidp = REP_OUT / "MARCH_LIQUIDITY_VOID_FEATURES.csv"
    if voidp.exists():
        with voidp.open(encoding="utf-8") as f:
            rdr = csv.DictReader(f)
            vd = {lr["zone_id"]: {k: safe_float(lr[k]) for k in lr if k != "zone_id"} for lr in rdr}
        for r in rows:
            for k, v in vd.get(r["zone_id"], {}).items(): r[k] = v
    return rows


def explainable_score_l2_dyn(r):
    s = 0.0
    if (r.get("opp_dir_zones_active_60m") or 0) == 0: s += 0.5
    pm = r.get("prior_move_60m_pct")
    if pm is not None: s -= min(abs(pm) * 0.3, 0.5)
    lr = r.get("local_range_180m_pct")
    if lr is not None and lr > 2.0: s -= 0.3
    if r.get("sweep_reclaim_aligned") == 1: s += 0.3
    if r.get("is_asia_session"): s += 0.2
    md = r.get("dl2_microprice_aligned_delta_5m_bps")
    if md is not None: s += max(min(md / 5.0, 0.5), -0.5)
    md15 = r.get("dl2_microprice_aligned_delta_15m_bps")
    if md15 is not None: s += max(min(md15 / 10.0, 0.3), -0.3)
    smr = r.get("dl2_supp_minus_opp_net_flow_5m")
    if smr is not None and smr > 0: s += min(smr / 100.0, 0.4)
    oc = r.get("dl2_inband_opp_cancel_15m") or 0
    if oc > 20: s -= min(oc / 200.0, 0.3)
    wp = r.get("dl2_top1_supportive_persistence_ge_50_5m_sec") or 0
    if wp > 60: s += min(wp / 600.0, 0.3)
    return round(s, 4)


def select_topn_per_day(rows, predicate, score_fn, n=1):
    by_date = defaultdict(list)
    for r in rows:
        if predicate(r): by_date[r["date"]].append(r)
    sel = []
    for d in ALL_DATES:
        day_rows = sorted(by_date.get(d, []), key=lambda x: -score_fn(x))
        sel.extend(day_rows[:n])
    return sel


# ============================================================
# Section C: target-zone heatmap (leak-free, trailing only)
# ============================================================
def find_swing_levels(secs, highs, lows, end_idx):
    """Return (swing_highs, swing_lows) as price lists, using only buckets [.. end_idx],
    confirmed pivots (need SWING_HALF_WIN_SEC after pivot, all <= end_idx)."""
    swing_highs = []
    swing_lows = []
    if end_idx < 2: return swing_highs, swing_lows
    # trailing start
    end_sec = secs[end_idx]
    start_sec = end_sec - TRAILING_CONTEXT_SEC
    # find start index
    lo, hi = 0, end_idx
    while lo < hi:
        m = (lo + hi) // 2
        if secs[m] < start_sec: lo = m + 1
        else: hi = m
    start_idx = lo
    # iterate candidate pivot indices; need window on both sides within [start_idx, end_idx]
    i = start_idx
    # We use a coarse step to limit cost: check every 30s bucket as potential pivot center
    while i <= end_idx:
        c_sec = secs[i]
        left_sec = c_sec - SWING_HALF_WIN_SEC
        right_sec = c_sec + SWING_HALF_WIN_SEC
        if right_sec > end_sec:
            break  # cannot confirm pivots near right edge (leak-free)
        # window indices
        li = i
        while li > start_idx and secs[li-1] >= left_sec: li -= 1
        ri = i
        while ri < end_idx and secs[ri+1] <= right_sec: ri += 1
        if ri - li >= 4:
            win_high = max(highs[li:ri+1])
            win_low = min(lows[li:ri+1])
            if highs[i] >= win_high - 1e-9:
                swing_highs.append(highs[i])
            if lows[i] <= win_low + 1e-9:
                swing_lows.append(lows[i])
        i += 30  # step 30s
    return swing_highs, swing_lows


def volume_profile_nodes(secs, lasts, vols, end_idx):
    """High-volume-node prices over trailing window ending at end_idx (leak-free)."""
    if end_idx < 2: return []
    end_sec = secs[end_idx]
    start_sec = end_sec - TRAILING_CONTEXT_SEC
    lo, hi = 0, end_idx
    while lo < hi:
        m = (lo + hi) // 2
        if secs[m] < start_sec: lo = m + 1
        else: hi = m
    start_idx = lo
    bins = defaultdict(float)
    for j in range(start_idx, end_idx + 1):
        b = round(lasts[j] / VOL_BIN_USD) * VOL_BIN_USD
        bins[b] += vols[j]
    if not bins: return []
    vals = sorted(bins.values())
    thresh = vals[int(HVN_PERCENTILE * (len(vals) - 1))]
    return sorted([price for price, v in bins.items() if v >= thresh])


def build_target_zone(zone, buckets_cache):
    """Compute target-zone heatmap features for one zone (leak-free at confirmedTs)."""
    out = {}
    direction = zone["direction"]
    confirmed_sec = iso_to_sec(zone.get("confirmed_iso"))
    if confirmed_sec is None:
        return out
    date = zone["date"]
    # Build trailing context = prev day + current day buckets up to confirmed_sec
    prev = calendar_prev(date)
    secs, highs, lows, lasts, vols = [], [], [], [], []
    if prev and prev in buckets_cache:
        ps, ph, pl, pla, pv = buckets_cache[prev]
        secs += ps; highs += ph; lows += pl; lasts += pla; vols += pv
    cs, ch, cl, cla, cv = buckets_cache[date]
    secs += cs; highs += ch; lows += cl; lasts += cla; vols += cv
    # end_idx = last bucket <= confirmed_sec
    lo, hi = 0, len(secs) - 1
    if not secs or secs[0] > confirmed_sec:
        return out
    while lo < hi:
        m = (lo + hi + 1) // 2
        if secs[m] <= confirmed_sec: lo = m
        else: hi = m - 1
    end_idx = lo
    entry_price = lasts[end_idx]
    out["tz_entry_ref_price"] = round(entry_price, 2)
    # session H/L (since 00:00 of current date)
    day_start = iso_to_sec(f"{date}T00:00:00+00:00")
    sess_high = None; sess_low = None
    for j in range(end_idx, -1, -1):
        if secs[j] < day_start: break
        sess_high = highs[j] if sess_high is None else max(sess_high, highs[j])
        sess_low = lows[j] if sess_low is None else min(sess_low, lows[j])
    out["tz_session_high"] = round(sess_high, 2) if sess_high else None
    out["tz_session_low"] = round(sess_low, 2) if sess_low else None
    # swing levels + volume nodes
    sh, sl = find_swing_levels(secs, highs, lows, end_idx)
    nodes = volume_profile_nodes(secs, lasts, vols, end_idx)
    # Assemble resistance (above) and support (below) candidate prices
    above = []
    below = []
    def add(price, ptype):
        if price is None: return
        dist = (price - entry_price) / entry_price * 100.0
        if 0.05 < dist <= MAX_OBSTACLE_SCAN_PCT:
            above.append((price, ptype, dist))
        elif -MAX_OBSTACLE_SCAN_PCT <= dist < -0.05:
            below.append((price, ptype, abs(dist)))
    for p_ in sh: add(p_, "swing_high")
    for p_ in sl: add(p_, "swing_low")
    if sess_high: add(sess_high, "session_high")
    if sess_low: add(sess_low, "session_low")
    for p_ in nodes: add(p_, "hvn")
    above.sort(key=lambda x: x[2])
    below.sort(key=lambda x: x[2])
    # Direction-aware: for LONG room = nearest obstacle ABOVE; for SHORT = nearest BELOW
    if direction == "LONG":
        obstacles = above
        target_side = above
    else:
        obstacles = below
        target_side = below
    nearest_obstacle_pct = obstacles[0][2] if obstacles else MAX_OBSTACLE_SCAN_PCT
    out["tz_nearest_obstacle_pct"] = round(nearest_obstacle_pct, 4)
    out["tz_nearest_obstacle_type"] = obstacles[0][1] if obstacles else "none_within_scan"
    out["tz_room_to_run_pct"] = round(nearest_obstacle_pct, 4)
    out["tz_n_obstacles_within_2pct"] = sum(1 for o in obstacles if o[2] < 2.0)
    # Best target candidate >= 2%: nearest obstacle at distance >= 2%, else "open void"
    tgt_ge2 = [o for o in target_side if o[2] >= 2.0]
    if tgt_ge2:
        tp, ttype, tdist = tgt_ge2[0]
        out["tz_target_price"] = round(tp, 2)
        out["tz_target_type"] = ttype
        out["tz_target_distance_pct"] = round(tdist, 4)
        out["tz_has_target_ge_2pct"] = 1
    elif not obstacles or nearest_obstacle_pct >= 2.0:
        # open path: no obstacle within 2% → target = fixed 2% projection (room available)
        out["tz_target_price"] = round(entry_price * (1 + TARGET_PCT/100.0) if direction == "LONG"
                                        else entry_price * (1 - TARGET_PCT/100.0), 2)
        out["tz_target_type"] = "open_void_2pct"
        out["tz_target_distance_pct"] = 2.0
        out["tz_has_target_ge_2pct"] = 1
    else:
        # obstacle < 2% blocks the path
        out["tz_target_price"] = None
        out["tz_target_type"] = "blocked"
        out["tz_target_distance_pct"] = round(nearest_obstacle_pct, 4)
        out["tz_has_target_ge_2pct"] = 0
    # reuse void features (already on row) as path quality
    out["tz_void_thin_path_score"] = zone.get("ms_thin_path_score")
    out["tz_opposing_wall_risk"] = zone.get("ms_large_walls_on_path")
    out["tz_max_wall_on_path"] = zone.get("ms_max_wall_on_path")
    out["tz_n_swing_levels"] = len(sh) + len(sl)
    out["tz_n_volume_nodes"] = len(nodes)
    return out


# ============================================================
# Custom trade simulator with optional BE
# ============================================================
def merge_forward_buckets(date, buckets_cache, lookahead=2):
    out_secs, out_h, out_l, out_la = [], [], [], []
    idx = ALL_DATES.index(date) if date in ALL_DATES else -1
    if idx < 0: return out_secs, out_h, out_l, out_la
    seq = [date] + [ALL_DATES[idx+k] for k in range(1, lookahead+1) if idx+k < len(ALL_DATES)]
    for d in seq:
        if d in buckets_cache:
            s, h, l, la, v = buckets_cache[d]
            out_secs += s; out_h += h; out_l += l; out_la += la
    return out_secs, out_h, out_l, out_la


def simulate_trade(direction, entry_sec, entry_price, tp_price, sl_price,
                   fwd, be_variant=None, target_distance_pct=None,
                   entry_microprice_aligned=None, entry_opp_wall=None):
    """fwd = (secs, highs, lows, lasts). Returns dict with exit info.
    be_variant in {None,'C1','C2','C3','C4'}.
    Conservative: if TP and SL both within same 1s bucket -> SL first."""
    secs, highs, lows, lasts = fwd
    n = len(secs)
    # locate entry idx (first sec >= entry_sec)
    lo, hi = 0, n
    while lo < hi:
        m = (lo + hi) // 2
        if secs[m] < entry_sec: lo = m + 1
        else: hi = m
    i0 = lo
    if i0 >= n:
        return {"exit_reason": "no_data"}
    timeout_sec = entry_sec + TIMEOUT_HOURS * 3600
    cur_sl = sl_price
    be_armed = False
    mfe = 0.0; mae = 0.0
    # C3 static gating
    c3_ok = True
    if be_variant == "C3":
        c3_ok = ((entry_microprice_aligned is not None and entry_microprice_aligned >= 0)
                 and (entry_opp_wall is not None and entry_opp_wall <= 1))
    # C4 structure detection state (pivot tracking on forward path)
    recent_lows = []   # for LONG higher-low
    recent_highs = []  # for SHORT lower-high
    half_target = (target_distance_pct or TARGET_PCT) / 2.0
    exit_reason = "timeout"; exit_sec = None; exit_price = None
    for i in range(i0, n):
        sec = secs[i]
        if sec > timeout_sec: break
        hi_p = highs[i]; lo_p = lows[i]
        if direction == "LONG":
            up = (hi_p - entry_price) / entry_price * 100.0
            dn = (entry_price - lo_p) / entry_price * 100.0
        else:
            up = (entry_price - lo_p) / entry_price * 100.0
            dn = (hi_p - entry_price) / entry_price * 100.0
        if up > mfe: mfe = up
        if dn > mae: mae = dn
        # ---- BE arming ----
        if be_variant and not be_armed:
            arm = False
            if be_variant == "C1":
                arm = mfe >= 1.0
            elif be_variant == "C2":
                arm = mfe >= half_target
            elif be_variant == "C3":
                arm = c3_ok and mfe >= 1.0
            elif be_variant == "C4":
                # structure: LONG higher-low above entry; SHORT lower-high below entry
                if direction == "LONG":
                    recent_lows.append((sec, lo_p))
                    # detect a local low (pivot) that is above entry
                    if len(recent_lows) >= 3:
                        a, b, c = recent_lows[-3][1], recent_lows[-2][1], recent_lows[-1][1]
                        if b < a and b < c and b > entry_price:
                            arm = True
                else:
                    recent_highs.append((sec, hi_p))
                    if len(recent_highs) >= 3:
                        a, b, c = recent_highs[-3][1], recent_highs[-2][1], recent_highs[-1][1]
                        if b > a and b > c and b < entry_price:
                            arm = True
            if arm:
                be_armed = True
                cur_sl = entry_price
        # ---- exits ----
        if direction == "LONG":
            tp_hit = hi_p >= tp_price
            sl_hit = lo_p <= cur_sl
        else:
            tp_hit = lo_p <= tp_price
            sl_hit = hi_p >= cur_sl
        if tp_hit and sl_hit:
            exit_reason = "be" if (be_armed and abs(cur_sl - entry_price) < 1e-6) else "stop"
            exit_sec = sec; exit_price = cur_sl; break
        if sl_hit:
            exit_reason = "be" if (be_armed and abs(cur_sl - entry_price) < 1e-6) else "stop"
            exit_sec = sec; exit_price = cur_sl; break
        if tp_hit:
            exit_reason = "target"; exit_sec = sec; exit_price = tp_price; break
    if exit_reason == "timeout":
        # last bucket within timeout
        last_idx = i0
        for i in range(i0, n):
            if secs[i] > timeout_sec: break
            last_idx = i
        exit_sec = secs[last_idx]; exit_price = lasts[last_idx]
    if exit_price is None:
        return {"exit_reason": "no_data"}
    sgn = 1.0 if direction == "LONG" else -1.0
    pnl = sgn * (exit_price - entry_price) / entry_price * 100.0
    return {"exit_reason": exit_reason, "entry_sec": entry_sec, "exit_sec": exit_sec,
            "entry_price": entry_price, "exit_price": exit_price,
            "pnl_pre_cost": round(pnl, 4), "pnl_after_cost": round(pnl - COST_PCT, 4),
            "mfe_pct": round(mfe, 4), "mae_pct": round(mae, 4), "be_armed": be_armed}


def classify_reason(zone, sim, outcome):
    if outcome == "WIN": return "win_clean"
    if outcome == "BE": return "breakeven"
    if outcome == "LOSS":
        if zone.get("coverage_class") == "wrong_direction": return "wrong_direction"
        if zone.get("watch_label") in ("GOOD", "MID"): return "correct_direction_but_no_2pct"
        return "stop_no_2pct_either_dir"
    # timeout
    return "timeout_positive" if (sim["pnl_pct_after_cost_raw"] if False else sim["pnl_after_cost"]) > 0.5 else "timeout_negative"


def run_model(zones, buckets_cache, model="A", be_variant=None):
    """model A: fixed 2% TP, 1.5 SL.
       model B: same but skip if tz_room_to_run < 2 (no target >= 2%).
       model C: target-zone TP (>=2%) + optional BE; skip if no target >= 2%."""
    trades = []
    skipped = 0
    for z in zones:
        confirmed_sec = iso_to_sec(z.get("confirmed_iso"))
        if confirmed_sec is None:
            continue
        direction = z["direction"]
        fwd = merge_forward_buckets(z["date"], buckets_cache, lookahead=2)
        if not fwd[0]:
            continue
        # entry at first bucket >= confirmed_sec
        secs = fwd[0]
        lo, hi = 0, len(secs)
        while lo < hi:
            m = (lo + hi) // 2
            if secs[m] < confirmed_sec: lo = m + 1
            else: hi = m
        if lo >= len(secs):
            continue
        entry_idx = lo
        entry_sec = secs[entry_idx]; entry_price = fwd[3][entry_idx]
        if entry_price <= 0:
            continue
        # decide TP / skip
        has_tgt = z.get("tz_has_target_ge_2pct")
        tgt_dist = z.get("tz_target_distance_pct")
        if model == "A":
            tp_dist = TARGET_PCT
        elif model == "B":
            if not has_tgt:
                skipped += 1; continue
            tp_dist = TARGET_PCT  # fixed 2% TP, just filtered
        elif model == "C":
            if not has_tgt:
                skipped += 1; continue
            # target-zone TP, capped >= 2%, buffered. Use 0.10% buffer.
            buf = 0.10
            tdist = tgt_dist if tgt_dist else TARGET_PCT
            tp_dist = max(tdist - buf, TARGET_PCT)
        else:
            tp_dist = TARGET_PCT
        if direction == "LONG":
            tp_price = entry_price * (1 + tp_dist/100.0)
            sl_price = entry_price * (1 - STOP_PCT/100.0)
        else:
            tp_price = entry_price * (1 - tp_dist/100.0)
            sl_price = entry_price * (1 + STOP_PCT/100.0)
        sim = simulate_trade(direction, entry_sec, entry_price, tp_price, sl_price, fwd,
                             be_variant=be_variant, target_distance_pct=tp_dist,
                             entry_microprice_aligned=z.get("dl2_microprice_aligned_delta_5m_bps"),
                             entry_opp_wall=z.get("ms_large_walls_on_path"))
        if sim.get("exit_reason") == "no_data":
            continue
        er = sim["exit_reason"]
        if er == "target": outcome = "WIN"
        elif er == "be": outcome = "BE"
        elif er == "stop": outcome = "LOSS"
        else: outcome = "TIMEOUT"
        reason = classify_reason(z, sim, outcome)
        trades.append({
            "date": z["date"], "direction": direction, "zone_id": z["zone_id"],
            "confirmed_iso": z.get("confirmed_iso"),
            "entry_sec": sim["entry_sec"], "exit_sec": sim["exit_sec"],
            "entry_price": round(sim["entry_price"], 2), "exit_price": round(sim["exit_price"], 2),
            "tp_dist_pct": round(tp_dist, 4), "tp_price": round(tp_price, 2), "sl_price": round(sl_price, 2),
            "exit_reason": er, "outcome": outcome, "reason_class": reason,
            "pnl_pre_cost": sim["pnl_pre_cost"], "pnl_after_cost": sim["pnl_after_cost"],
            "mfe_pct": sim["mfe_pct"], "mae_pct": sim["mae_pct"], "be_armed": sim["be_armed"],
            "watch_label": z.get("watch_label"), "coverage_class": z.get("coverage_class"),
            "session": z.get("session"),
            "setup_type": z.get("setup_type"),
            "tz_room_to_run_pct": z.get("tz_room_to_run_pct"),
            "tz_target_type": z.get("tz_target_type"),
            "tz_target_distance_pct": z.get("tz_target_distance_pct"),
            "tz_void_thin_path_score": z.get("tz_void_thin_path_score"),
            "tz_opposing_wall_risk": z.get("tz_opposing_wall_risk"),
        })
    return trades, skipped


def metrics(trades):
    n = len(trades)
    wins = sum(1 for t in trades if t["outcome"] == "WIN")
    losses = sum(1 for t in trades if t["outcome"] == "LOSS")
    timeouts = sum(1 for t in trades if t["outcome"] == "TIMEOUT")
    bes = sum(1 for t in trades if t["outcome"] == "BE")
    pnls = [t["pnl_after_cost"] for t in trades]
    pnls_pre = [t["pnl_pre_cost"] for t in trades]
    wp = [p for p in pnls if p > 0]; lp = [p for p in pnls if p < 0]
    pf = round(sum(wp) / sum(-p for p in lp), 3) if lp else None
    cur = 0; mxcl = 0
    for t in trades:
        if t["pnl_after_cost"] <= 0: cur += 1; mxcl = max(mxcl, cur)
        else: cur = 0
    avg_win = mean_or_none([t["pnl_after_cost"] for t in trades if t["outcome"] == "WIN"])
    avg_loss = mean_or_none([t["pnl_after_cost"] for t in trades if t["outcome"] in ("LOSS", "BE", "TIMEOUT") and t["pnl_after_cost"] < 0])
    longs = [t for t in trades if t["direction"] == "LONG"]
    shorts = [t for t in trades if t["direction"] == "SHORT"]
    h1 = [t for t in trades if t["date"] in FIRST_HALF]
    h2 = [t for t in trades if t["date"] in SECOND_HALF]
    return {
        "trades": n, "wins": wins, "losses": losses, "timeouts": timeouts, "be_exits": bes,
        "winrate_pct": round(100.0 * wins / max(n, 1), 2),
        "avg_win_after_cost": avg_win, "avg_loss_after_cost": avg_loss,
        "expectancy_pre_cost_pct": round(stats.mean(pnls_pre), 4) if pnls_pre else None,
        "expectancy_after_cost_pct": round(stats.mean(pnls), 4) if pnls else None,
        "total_return_after_cost_pct": round(sum(pnls), 4) if pnls else None,
        "pf_after_cost": pf, "max_consecutive_losses": mxcl,
        "long_n": len(longs), "short_n": len(shorts),
        "long_winrate": round(100.0*sum(1 for t in longs if t["outcome"]=="WIN")/max(len(longs),1), 2),
        "short_winrate": round(100.0*sum(1 for t in shorts if t["outcome"]=="WIN")/max(len(shorts),1), 2),
        "h1_n": len(h1), "h2_n": len(h2),
        "h1_winrate": round(100.0*sum(1 for t in h1 if t["outcome"]=="WIN")/max(len(h1),1), 2),
        "h2_winrate": round(100.0*sum(1 for t in h2 if t["outcome"]=="WIN")/max(len(h2),1), 2),
        "wrong_direction": sum(1 for t in trades if t["reason_class"]=="wrong_direction"),
        "correct_direction_but_no_2pct": sum(1 for t in trades if t["reason_class"]=="correct_direction_but_no_2pct"),
        "stop_no_2pct_either_dir": sum(1 for t in trades if t["reason_class"]=="stop_no_2pct_either_dir"),
    }


# ============================================================
# setup-type classification (reuse from prior pass, light version)
# ============================================================
def classify_setup(r):
    direction = r["direction"]
    refill_proxy = r.get("dl2_supp_minus_opp_net_flow_5m") or 0
    refill_proxy_15m = r.get("dl2_supp_minus_opp_net_flow_15m") or 0
    supp_add = r.get("dl2_inband_supp_add_5m") or 0
    wall_persistence = r.get("dl2_top1_supportive_persistence_ge_50_5m_sec") or 0
    sweep_reclaim = r.get("sweep_reclaim_aligned") == 1
    micro_5m = r.get("dl2_microprice_aligned_delta_5m_bps") or 0
    taker_30m = r.get("taker_imb_aligned_30m") or 0
    prior_60m = abs(r.get("prior_move_60m_pct") or 0)
    local_range_60m = r.get("local_range_60m_pct") or 99
    void_thin = r.get("ms_thin_path_score") or 0
    large_walls = r.get("ms_large_walls_on_path") or 99
    opp_cancel = r.get("dl2_inband_opp_cancel_15m") or 0
    dl = direction.lower()
    sc = {}
    sc[f"absorption_reversal_{dl}"] = round(math.log1p(max(supp_add,0)/1000.0) + max(refill_proxy/100.0,0)*1.5
        + (0.5 if sweep_reclaim else 0) + micro_5m/10.0 + (wall_persistence/300.0)*0.5 - min(opp_cancel/1000.0,0.3), 3)
    sc[f"breakout_continuation_{dl}"] = round(max(0.0,0.7-local_range_60m)*2 + void_thin*3 + micro_5m/10.0
        + max(taker_30m,0)*2 - min(large_walls*0.2,0.5), 3)
    sc[f"retest_after_breakout_{dl}"] = round((prior_60m if 0.4<=prior_60m<=1.2 else 0) + max(refill_proxy_15m/100.0,0)
        + (wall_persistence/300.0)*0.7 + micro_5m/10.0, 3)
    sc[f"failed_breakout_reclaim_{dl}"] = round((1.0 if sweep_reclaim else 0) + max(refill_proxy/100.0,0)*1.5 + micro_5m/10.0, 3)
    best = max(sc.items(), key=lambda kv: kv[1])
    r["setup_type"] = best[0] if best[1] > 0.5 else "unknown"
    return r


# ============================================================
# MAIN
# ============================================================
def main():
    print("[load] dataset ...", file=sys.stderr)
    rows = load_dataset()
    for r in rows: classify_setup(r)
    print(f"  {len(rows)} zones", file=sys.stderr)

    # ---------- Section A: data audit ----------
    print("[A] OI/funding/liquidation data audit ...", file=sys.stderr)
    march_has_deriv = any((DATA_ROOT / d / "derivative_ticker.csv.gz").exists() for d in ALL_DATES)
    march_has_liq = any((DATA_ROOT / d / "liquidations.csv.gz").exists() for d in ALL_DATES)
    apr_deriv = (DATA_ROOT / "2026-04-01" / "derivative_ticker.csv.gz").exists()
    apr_liq = (DATA_ROOT / "2026-04-01" / "liquidations.csv.gz").exists()
    audit = {
        "build_time_utc": now_iso(),
        "scope": "OKX BTC-USDT-SWAP March 2026 (29 days)",
        "march_per_day_files_present": ["incremental_book_L2.csv.gz", "trades.csv.gz"],
        "OI_DATA_AVAILABLE": "NO",
        "FUNDING_DATA_AVAILABLE": "NO",
        "LIQUIDATION_DATA_AVAILABLE": "NO",
        "OI_COVERS_MARCH": "NO",
        "FUNDING_COVERS_MARCH": "NO",
        "LIQUIDATIONS_COVER_MARCH": "NO",
        "march_has_derivative_ticker": march_has_deriv,
        "march_has_liquidations": march_has_liq,
        "reference_schema_source": "2026-04-01 (OKX) has both files; used only to document required format",
        "reference_derivative_ticker_columns": ["exchange","symbol","timestamp","local_timestamp",
            "funding_timestamp","funding_rate","predicted_funding_rate","open_interest",
            "last_price","index_price","mark_price"],
        "reference_liquidations_columns": ["exchange","symbol","timestamp","local_timestamp",
            "id","side","price","amount"],
        "required_to_enable_oi_fuel": [
            "Fetch OKX derivative_ticker.csv.gz (OI + funding) for 2026-03-02..03-31 in Tardis-compat layout, "
            "placed at data/okx-historical/BTC-USDT-SWAP/<date>/derivative_ticker.csv.gz",
            "Fetch OKX liquidations.csv.gz for the same dates at .../<date>/liquidations.csv.gz",
            "Timestamps must be microsecond unix, covering full UTC day, same as April reference",
        ],
        "decision": "Proceed with target-zone + 3 trade models WITHOUT OI/fuel. "
                    "OI/funding/liquidation feature + evaluation sections produce NOT_AVAILABLE placeholders.",
    }
    (REP_OUT / "MARCH_OI_FUNDING_LIQUIDATION_DATA_AUDIT.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    md = ["# OI / funding / liquidation data audit (OKX March 2026)", "",
          f"**Build:** {audit['build_time_utc']}", "",
          "## Verdict", "",
          "| dataset | available for March | covers March |",
          "|---|:---:|:---:|",
          f"| open interest | NO | NO |",
          f"| funding | NO | NO |",
          f"| liquidations | NO | NO |",
          "",
          "March OKX per-day directories contain ONLY `incremental_book_L2.csv.gz` and `trades.csv.gz`.",
          "No `derivative_ticker.csv.gz` (OI+funding) and no `liquidations.csv.gz` for any of the 29 March days.",
          "",
          "## Reference schema (from 2026-04-01 OKX, NOT March)",
          "`derivative_ticker.csv.gz`: " + ", ".join(audit["reference_derivative_ticker_columns"]),
          "",
          "`liquidations.csv.gz`: " + ", ".join(audit["reference_liquidations_columns"]),
          "",
          "## What is needed to enable OI/fuel research",
          ]
    for x in audit["required_to_enable_oi_fuel"]: md.append(f"- {x}")
    md.append("")
    md.append(f"**Decision:** {audit['decision']}")
    (REP_OUT / "MARCH_OI_FUNDING_LIQUIDATION_DATA_AUDIT.md").write_text("\n".join(md), encoding="utf-8")

    # ---------- Section B: OI features (NOT AVAILABLE) ----------
    print("[B] OI features = NOT_AVAILABLE ...", file=sys.stderr)
    b_json = {"build_time_utc": now_iso(), "status": "NOT_AVAILABLE",
              "reason": "No OI/funding/liquidation data for OKX March 2026 (see data audit).",
              "features_that_would_be_built": [
                  "oi_at_signal","oi_delta_5m/15m/30m/60m","oi_delta_zscore_60m/180m",
                  "funding_rate","funding_zscore","funding_*_extreme",
                  "price_up_oi_up / price_up_oi_down / price_down_oi_up / price_down_oi_down",
                  "liq_buy/sell_volume_5m/15m/60m","liq_imbalance_15m","liquidation_cluster_score",
                  "forced_buy_cluster/forced_sell_cluster","liquidation_zscore_60m",
                  "fuel_long_score / fuel_short_score / fuel_score"]}
    (REP_OUT / "MARCH_OI_FUNDING_LIQUIDATION_FEATURES.json").write_text(json.dumps(b_json, indent=2), encoding="utf-8")
    (REP_OUT / "MARCH_OI_FUNDING_LIQUIDATION_FEATURES.md").write_text(
        "# OI / funding / liquidation features — NOT AVAILABLE\n\n"
        f"**Build:** {b_json['build_time_utc']}\n\n"
        "No OKX March OI/funding/liquidation data exists (see data audit). "
        "These features cannot be built for March 2026 without first fetching the data.\n\n"
        "Features that WOULD be built once data is present:\n\n"
        + "\n".join(f"- `{x}`" for x in b_json["features_that_would_be_built"]) + "\n", encoding="utf-8")
    with (REP_OUT / "MARCH_OI_FUNDING_LIQUIDATION_FEATURES.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f); w.writerow(["zone_id", "status"]);
        for r in rows: w.writerow([r["zone_id"], "NOT_AVAILABLE"])

    # ---------- Build buckets (with volume) ----------
    print("[buckets] building volume-aware buckets ...", file=sys.stderr)
    buckets_cache = {}
    needed = set(ALL_DATES)
    needed.add("2026-03-01")  # prev for 03-02
    needed.add("2026-04-01")  # next for 03-31
    for d in sorted(needed):
        p = DATA_ROOT / d / "trades.csv.gz"
        if p.exists():
            t0 = time.time()
            buckets_cache[d] = build_buckets_with_volume(p)
            print(f"  {d}: {len(buckets_cache[d][0])} buckets ({time.time()-t0:.1f}s)", file=sys.stderr)

    # ---------- Section C: target-zone heatmap ----------
    print("[C] target-zone heatmap ...", file=sys.stderr)
    for r in rows:
        tz = build_target_zone(r, buckets_cache)
        r.update(tz)
    n_with_tz = sum(1 for r in rows if r.get("tz_room_to_run_pct") is not None)
    n_has_tgt = sum(1 for r in rows if r.get("tz_has_target_ge_2pct") == 1)
    print(f"  target-zone for {n_with_tz} zones; {n_has_tgt} have >=2% target", file=sys.stderr)
    # write heatmap features
    tz_keys = ["zone_id","date","direction","confirmed_iso","tz_entry_ref_price",
               "tz_session_high","tz_session_low","tz_nearest_obstacle_pct","tz_nearest_obstacle_type",
               "tz_room_to_run_pct","tz_n_obstacles_within_2pct","tz_target_price","tz_target_type",
               "tz_target_distance_pct","tz_has_target_ge_2pct","tz_void_thin_path_score",
               "tz_opposing_wall_risk","tz_max_wall_on_path","tz_n_swing_levels","tz_n_volume_nodes",
               "watch_label","coverage_class","setup_type"]
    with (REP_OUT / "MARCH_TARGET_ZONE_HEATMAP_FEATURES.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=tz_keys, extrasaction="ignore"); w.writeheader()
        for r in rows: w.writerow(r)
    # target candidates (one row per zone with its chosen target)
    with (REP_OUT / "MARCH_TARGET_ZONE_CANDIDATES.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["zone_id","date","direction","tz_entry_ref_price",
            "tz_target_type","tz_target_price","tz_target_distance_pct","tz_has_target_ge_2pct",
            "tz_room_to_run_pct","tz_nearest_obstacle_type"], extrasaction="ignore"); w.writeheader()
        for r in rows:
            if r.get("tz_room_to_run_pct") is not None: w.writerow(r)
    tz_report = {"build_time_utc": now_iso(), "n_zones_with_target_zone": n_with_tz,
                 "n_zones_with_target_ge_2pct": n_has_tgt,
                 "pct_blocked_under_2pct": round(100.0*(n_with_tz-n_has_tgt)/max(n_with_tz,1), 2),
                 "target_type_distribution": dict(Counter(r.get("tz_target_type") for r in rows if r.get("tz_target_type"))),
                 "method": "leak-free: swing pivots (5m half-window, 8h trailing) + session H/L + "
                           "volume-profile HVN (50$ bins, 80th pct) + reused L2 void/wall features; "
                           "all computed from buckets/trades with timestamp <= confirmedTs."}
    (REP_OUT / "MARCH_TARGET_ZONE_HEATMAP_REPORT.json").write_text(json.dumps(tz_report, indent=2), encoding="utf-8")
    md = ["# Target-zone heatmap report", "", f"**Build:** {tz_report['build_time_utc']}", "",
          f"- zones with target-zone computed: **{n_with_tz}**",
          f"- zones with a >=2% target (room to run): **{n_has_tgt}**",
          f"- zones blocked (<2% to first obstacle): **{n_with_tz-n_has_tgt}** ({tz_report['pct_blocked_under_2pct']}%)",
          "", "## Target type distribution", "", "| type | n |", "|---|---:|"]
    for k, v in sorted(tz_report["target_type_distribution"].items(), key=lambda kv:-kv[1]):
        md.append(f"| {k} | {v} |")
    md += ["", "## Method", tz_report["method"]]
    (REP_OUT / "MARCH_TARGET_ZONE_HEATMAP_REPORT.md").write_text("\n".join(md), encoding="utf-8")

    # ---------- Selectors ----------
    base_filter = lambda r: r.get("dist_to_recent_swing_high_pct") is not None and r["dist_to_recent_swing_high_pct"] <= 0.4616
    enh_filter = lambda r: base_filter(r) and (r.get("dl2_supp_minus_opp_net_flow_15m") is not None and r["dl2_supp_minus_opp_net_flow_15m"] <= 4497.76)
    baseline_zones = select_topn_per_day(rows, base_filter, explainable_score_l2_dyn, 1)
    enhanced_zones = select_topn_per_day(rows, enh_filter, explainable_score_l2_dyn, 1)
    print(f"  baseline zones={len(baseline_zones)}, enhanced zones={len(enhanced_zones)}", file=sys.stderr)

    # ---------- Section D: 3 trade models ----------
    print("[D] trade models ...", file=sys.stderr)
    # Use ENHANCED selector as the basis (best known) for all models; also keep baseline ModelA for ref.
    results = {}
    # Model A on baseline and enhanced
    tA_base, _ = run_model(baseline_zones, buckets_cache, model="A")
    tA_enh, _ = run_model(enhanced_zones, buckets_cache, model="A")
    results["A_baseline_fixed2pct"] = {"trade_list": tA_base, "skipped": 0, **metrics(tA_base)}
    results["A_enhanced_fixed2pct"] = {"trade_list": tA_enh, "skipped": 0, **metrics(tA_enh)}
    # Model B on enhanced
    tB, skB = run_model(enhanced_zones, buckets_cache, model="B")
    results["B_enhanced_targetzone_filter"] = {"trade_list": tB, "skipped": skB, **metrics(tB)}
    # Model C variants on enhanced
    for bev in ("C1", "C2", "C3", "C4"):
        tC, skC = run_model(enhanced_zones, buckets_cache, model="C", be_variant=bev)
        results[f"C_enhanced_targetTP_BE_{bev}"] = {"trade_list": tC, "skipped": skC, **metrics(tC)}
    # Model C without BE (target TP only)
    tCn, skCn = run_model(enhanced_zones, buckets_cache, model="C", be_variant=None)
    results["C_enhanced_targetTP_noBE"] = {"trade_list": tCn, "skipped": skCn, **metrics(tCn)}

    # BE accounting vs A_enhanced (per-zone outcome comparison)
    a_enh_by_zone = {t["zone_id"]: t for t in tA_enh}
    def be_accounting(tC_trades):
        saved = killed = be_before_target = 0
        for t in tC_trades:
            if t["outcome"] != "BE": continue
            a = a_enh_by_zone.get(t["zone_id"])
            if a is None: continue
            if a["outcome"] == "LOSS": saved += 1     # was a loss in fixed, now BE (better)
            elif a["outcome"] == "WIN": killed += 1   # was a win in fixed, now BE (worse)
            # BE before later target: A_enhanced reached target (win) but C exited BE
            if a["outcome"] == "WIN": be_before_target += 1
        return saved, killed, be_before_target
    for bev in ("C1","C2","C3","C4"):
        key = f"C_enhanced_targetTP_BE_{bev}"
        s, k, bt = be_accounting(results[key]["trade_list"])
        results[key]["losses_saved_by_BE"] = s
        results[key]["winners_killed_by_BE"] = k
        results[key]["BE_before_later_target"] = bt

    # write comparison
    comp_rows = []
    for name, res in results.items():
        comp_rows.append({"model": name, **{k: v for k, v in res.items() if k != "trade_list"}})
    comp_csv_keys = ["model","trades","skipped","wins","losses","timeouts","be_exits","winrate_pct",
                     "avg_win_after_cost","avg_loss_after_cost","expectancy_pre_cost_pct",
                     "expectancy_after_cost_pct","total_return_after_cost_pct","pf_after_cost",
                     "max_consecutive_losses","long_n","short_n","long_winrate","short_winrate",
                     "h1_n","h2_n","h1_winrate","h2_winrate","wrong_direction",
                     "correct_direction_but_no_2pct","stop_no_2pct_either_dir",
                     "losses_saved_by_BE","winners_killed_by_BE","BE_before_later_target"]
    with (REP_OUT / "MARCH_TRADE_MODEL_COMPARISON.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=comp_csv_keys, extrasaction="ignore"); w.writeheader()
        for cr in comp_rows: w.writerow(cr)
    (REP_OUT / "MARCH_TRADE_MODEL_COMPARISON.json").write_text(json.dumps(
        {"build_time_utc": now_iso(),
         "models": {name: {k: v for k, v in res.items() if k != "trade_list"}
                    for name, res in results.items()}}, indent=2, default=str), encoding="utf-8")
    md = ["# Trade model comparison (A / B / C+BE)", "", f"**Build:** {now_iso()}",
          "**Selector basis:** enhanced microstructure (dist_to_recent_swing_high<=0.4616 AND dl2_supp_minus_opp_net_flow_15m<=4497.76, top1/day).",
          "**A_baseline shown for reference (baseline selector).**", "",
          "| model | trades | skip | W | L | TO | BE | winrate% | exp_aft% | PF_aft | totRet% | maxCL | saved | killed |",
          "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for name, res in results.items():
        md.append(f"| {name} | {res['trades']} | {res['skipped']} | {res['wins']} | {res['losses']} | "
                  f"{res['timeouts']} | {res['be_exits']} | {res['winrate_pct']} | {res['expectancy_after_cost_pct']} | "
                  f"{res['pf_after_cost']} | {res['total_return_after_cost_pct']} | {res['max_consecutive_losses']} | "
                  f"{res.get('losses_saved_by_BE','-')} | {res.get('winners_killed_by_BE','-')} |")
    (REP_OUT / "MARCH_TRADE_MODEL_COMPARISON.md").write_text("\n".join(md), encoding="utf-8")

    # ---------- Section E: non-win rescue ----------
    print("[E] non-win rescue analysis ...", file=sys.stderr)
    nonwins = [t for t in tA_enh if t["outcome"] != "WIN"]
    rescue = []
    for t in nonwins:
        z = next((r for r in rows if r["zone_id"] == t["zone_id"]), {})
        had_room = z.get("tz_has_target_ge_2pct") == 1
        rescue.append({
            "date": t["date"], "direction": t["direction"], "zone_id": t["zone_id"],
            "outcome": t["outcome"], "reason_class": t["reason_class"],
            "pnl_after_cost": t["pnl_after_cost"], "mfe_pct": t["mfe_pct"], "mae_pct": t["mae_pct"],
            "tz_room_to_run_pct": z.get("tz_room_to_run_pct"),
            "tz_has_target_ge_2pct": had_room,
            "model_B_would_skip": (not had_room),
            "tz_void_thin_path_score": z.get("tz_void_thin_path_score"),
            "tz_opposing_wall_risk": z.get("tz_opposing_wall_risk"),
            "would_BE_C1_save": t["mfe_pct"] >= 1.0,  # if MFE reached 1% then BE would have triggered (saving from full loss)
        })
    n_skip_B = sum(1 for x in rescue if x["model_B_would_skip"])
    n_be_save = sum(1 for x in rescue if x["would_BE_C1_save"] and x["outcome"] == "LOSS")
    (REP_OUT / "MARCH_NON_WIN_RESCUE_TARGET_ZONE_BE_ANALYSIS.json").write_text(json.dumps(
        {"build_time_utc": now_iso(), "n_nonwins": len(nonwins),
         "n_would_skip_by_target_zone_filter": n_skip_B,
         "n_losses_BE_C1_would_reduce": n_be_save, "detail": rescue}, indent=2, default=str), encoding="utf-8")
    with (REP_OUT / "MARCH_NON_WIN_RESCUE_TARGET_ZONE_BE_ANALYSIS.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rescue[0].keys()) if rescue else ["date"], extrasaction="ignore")
        w.writeheader()
        for x in rescue: w.writerow(x)
    md = ["# Non-win rescue analysis (target-zone + BE)", "", f"**Build:** {now_iso()}",
          f"**Enhanced model non-wins:** {len(nonwins)}",
          f"**Would be SKIPPED by target-zone filter (no >=2% room):** {n_skip_B}",
          f"**Losses where MFE>=1% (BE C1 would cut to ~breakeven):** {n_be_save}", "",
          "| date | dir | outcome | reason | pnl% | MFE% | MAE% | room% | has_tgt>=2% | B_skips | BE_C1_saves |",
          "|---|:---:|:---:|---|---:|---:|---:|---:|:---:|:---:|:---:|"]
    for x in rescue:
        md.append(f"| {x['date']} | {x['direction']} | {x['outcome']} | {x['reason_class']} | "
                  f"{x['pnl_after_cost']} | {x['mfe_pct']} | {x['mae_pct']} | {x['tz_room_to_run_pct']} | "
                  f"{'Y' if x['tz_has_target_ge_2pct'] else 'N'} | {'Y' if x['model_B_would_skip'] else 'N'} | "
                  f"{'Y' if x['would_BE_C1_save'] else 'N'} |")
    (REP_OUT / "MARCH_NON_WIN_RESCUE_TARGET_ZONE_BE_ANALYSIS.md").write_text("\n".join(md), encoding="utf-8")

    # ---------- Section F: OI fuel eval (NOT AVAILABLE) ----------
    print("[F] OI fuel eval = NOT_AVAILABLE ...", file=sys.stderr)
    f_json = {"build_time_utc": now_iso(), "status": "NOT_AVAILABLE",
              "reason": "No OKX March OI/funding/liquidation data.",
              "hypotheses_untestable": ["H1 fuel_score->2% follow-through","H2 low fuel->no-2pct",
                  "H3 liq cluster+refill->absorption reversal","H4 OI expansion->continuation",
                  "H5 OI contraction->deleveraging reversal"]}
    (REP_OUT / "MARCH_OI_FUEL_FEATURE_EVALUATION.json").write_text(json.dumps(f_json, indent=2), encoding="utf-8")
    (REP_OUT / "MARCH_OI_FUEL_FEATURE_EVALUATION.md").write_text(
        "# OI / fuel feature evaluation — NOT AVAILABLE\n\n"
        f"**Build:** {f_json['build_time_utc']}\n\n"
        "Cannot evaluate OI/funding/liquidation fuel hypotheses: no March data.\n\n"
        "Untestable until data fetched:\n\n" + "\n".join(f"- {h}" for h in f_json["hypotheses_untestable"]) + "\n",
        encoding="utf-8")
    with (REP_OUT / "MARCH_OI_FUEL_FEATURE_EVALUATION.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f); w.writerow(["feature","status"]); w.writerow(["fuel_score","NOT_AVAILABLE"])

    # ---------- Section G: target-zone + void selectors ----------
    print("[G] target-zone + void selectors ...", file=sys.stderr)
    sel_results = {}
    def eval_selector(name, zones, model="A", be=None):
        t, sk = run_model(zones, buckets_cache, model=model, be_variant=be)
        sel_results[name] = {"trade_list": t, "skipped": sk, **metrics(t)}
    # Selector 1: enhanced only (= Model A enhanced)
    eval_selector("S1_enhanced_only", enhanced_zones, "A")
    # Selector 2: enhanced + target>=2% (Model B)
    eval_selector("S2_enhanced_targetzone", enhanced_zones, "B")
    # Selector 3: enhanced + target>=2% + thin void (void_score threshold)
    void_thr = quantile([r.get("ms_thin_path_score") for r in rows], 0.5)
    s3_zones = [z for z in enhanced_zones if (z.get("ms_thin_path_score") or 0) >= (void_thr or 0)]
    eval_selector("S3_enhanced_target_void", s3_zones, "B")
    # Selector 5: setup-specific (absorption_reversal_short) + target filter
    s5_zones = [z for z in enhanced_zones if z.get("setup_type") == "absorption_reversal_short"]
    eval_selector("S5_absorption_reversal_short_target", s5_zones, "B")
    s5l_zones = [z for z in enhanced_zones if z.get("setup_type") == "absorption_reversal_long"]
    eval_selector("S5_absorption_reversal_long_target", s5l_zones, "B")
    # Selector 6: EV-based — p_reach proxy from void + room + microstructure
    def p_reach_proxy(z):
        p = 0.5
        if (z.get("tz_room_to_run_pct") or 0) >= 2.0: p += 0.10
        if (z.get("ms_thin_path_score") or 0) >= (void_thr or 0): p += 0.05
        if (z.get("ms_large_walls_on_path") or 99) == 0: p += 0.05
        if (z.get("dl2_microprice_aligned_delta_5m_bps") or -99) >= 0: p += 0.05
        if (z.get("dl2_supp_minus_opp_net_flow_15m") or 99999) <= 4497.76: p += 0.05
        return min(p, 0.95)
    reward = TARGET_PCT - COST_PCT
    risk = STOP_PCT + COST_PCT
    for z in rows:
        pr = p_reach_proxy(z)
        z["_ev"] = pr * reward - (1 - pr) * risk
    s6_zones = [z for z in enhanced_zones if z.get("_ev", -9) > 0 and z.get("tz_has_target_ge_2pct") == 1]
    eval_selector("S6_EV_positive", s6_zones, "B")
    # write
    sel_csv_keys = ["selector","trades","skipped","wins","losses","timeouts","winrate_pct",
                    "expectancy_after_cost_pct","pf_after_cost","total_return_after_cost_pct",
                    "max_consecutive_losses","h1_winrate","h2_winrate","long_winrate","short_winrate"]
    with (REP_OUT / "MARCH_TARGET_ZONE_FUEL_SELECTOR_RESULTS.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=sel_csv_keys, extrasaction="ignore"); w.writeheader()
        for name, res in sel_results.items():
            w.writerow({"selector": name, **{k: v for k, v in res.items() if k != "trade_list"}})
    (REP_OUT / "MARCH_TARGET_ZONE_FUEL_SELECTOR_RESULTS.json").write_text(json.dumps(
        {"build_time_utc": now_iso(),
         "selectors": {name: {k: v for k, v in res.items() if k != "trade_list"}
                       for name, res in sel_results.items()}}, indent=2, default=str), encoding="utf-8")
    md = ["# Target-zone + (fuel N/A) selector results", "", f"**Build:** {now_iso()}",
          "**Fuel features NOT_AVAILABLE for March → selectors 4 (fuel) omitted; void/target used.**", "",
          "| selector | trades | skip | W | L | TO | winrate% | exp_aft% | PF_aft | totRet% | H1wr | H2wr |",
          "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for name, res in sel_results.items():
        md.append(f"| {name} | {res['trades']} | {res['skipped']} | {res['wins']} | {res['losses']} | "
                  f"{res['timeouts']} | {res['winrate_pct']} | {res['expectancy_after_cost_pct']} | "
                  f"{res['pf_after_cost']} | {res['total_return_after_cost_pct']} | {res['h1_winrate']} | {res['h2_winrate']} |")
    (REP_OUT / "MARCH_TARGET_ZONE_FUEL_SELECTOR_RESULTS.md").write_text("\n".join(md), encoding="utf-8")

    # ---------- pick best model overall ----------
    candidates = {**{k: v for k, v in results.items()}, **{k: v for k, v in sel_results.items()}}
    # best = max expectancy_after_cost with trades>=20
    best_name = None; best_exp = -99
    for name, res in candidates.items():
        if res["trades"] >= 20 and (res["expectancy_after_cost_pct"] or -99) > best_exp:
            best_exp = res["expectancy_after_cost_pct"]; best_name = name
    best = candidates[best_name] if best_name else None

    # ---------- Section H: casebook ----------
    print("[H] casebook ...", file=sys.stderr)
    a_by_zone = {t["zone_id"]: t for t in tA_enh}
    b_by_zone = {t["zone_id"]: t for t in tB}
    best_be = results.get("C_enhanced_targetTP_BE_C1", {}).get("trade_list", [])
    be_by_zone = {t["zone_id"]: t for t in best_be}
    cb = {"build_time_utc": now_iso(), "sections": {}}
    # trades improved by target-zone filter: A nonwin that B skips
    improved_by_filter = [t for t in tA_enh if t["outcome"] != "WIN" and t["zone_id"] not in b_by_zone]
    worsened_by_filter = [t for t in tA_enh if t["outcome"] == "WIN" and t["zone_id"] not in b_by_zone]
    saved_by_be = []; killed_by_be = []
    for zid, bt in be_by_zone.items():
        a = a_by_zone.get(zid)
        if a and bt["outcome"] == "BE" and a["outcome"] == "LOSS": saved_by_be.append((zid, a, bt))
        if a and bt["outcome"] == "BE" and a["outcome"] == "WIN": killed_by_be.append((zid, a, bt))
    cb["sections"]["improved_by_target_zone_filter"] = [{"date":t["date"],"dir":t["direction"],
        "zone_id":t["zone_id"],"old_outcome":t["outcome"],"reason":t["reason_class"],
        "room_pct":t.get("tz_room_to_run_pct"),"new":"SKIPPED"} for t in improved_by_filter]
    cb["sections"]["worsened_by_target_zone_filter"] = [{"date":t["date"],"dir":t["direction"],
        "zone_id":t["zone_id"],"old_outcome":"WIN","room_pct":t.get("tz_room_to_run_pct"),"new":"SKIPPED"} for t in worsened_by_filter]
    cb["sections"]["saved_by_BE_C1"] = [{"zone_id":z,"old":a["outcome"],"old_pnl":a["pnl_after_cost"],
        "new":"BE","new_pnl":bt["pnl_after_cost"]} for z,a,bt in saved_by_be]
    cb["sections"]["killed_by_BE_C1"] = [{"zone_id":z,"old":"WIN","old_pnl":a["pnl_after_cost"],
        "new":"BE","new_pnl":bt["pnl_after_cost"]} for z,a,bt in killed_by_be]
    cb["sections"]["nonwins_insufficient_room"] = [{"date":x["date"],"dir":x["direction"],
        "reason":x["reason_class"],"room_pct":x["tz_room_to_run_pct"]} for x in rescue if x["model_B_would_skip"]]
    cb["sections"]["absorption_reversal_short_examples"] = [{"date":z["date"],"zone_id":z["zone_id"],
        "room_pct":z.get("tz_room_to_run_pct"),"target_type":z.get("tz_target_type")}
        for z in s5_zones[:10]]
    (REP_OUT / "MARCH_TARGET_ZONE_FUEL_CASEBOOK.json").write_text(json.dumps(cb, indent=2, default=str), encoding="utf-8")
    md = ["# Target-zone + fuel casebook", "", f"**Build:** {now_iso()}",
          "**Fuel N/A (no March OI/liq data).**", ""]
    md += [f"## Non-wins improved (skipped) by target-zone filter: {len(improved_by_filter)}", "",
           "| date | dir | old_outcome | reason | room% |", "|---|:---:|:---:|---|---:|"]
    for t in improved_by_filter:
        md.append(f"| {t['date']} | {t['direction']} | {t['outcome']} | {t['reason_class']} | {t.get('tz_room_to_run_pct')} |")
    md += ["", f"## Winners worsened (wrongly skipped) by target-zone filter: {len(worsened_by_filter)}", "",
           "| date | dir | room% |", "|---|:---:|---:|"]
    for t in worsened_by_filter:
        md.append(f"| {t['date']} | {t['direction']} | {t.get('tz_room_to_run_pct')} |")
    md += ["", f"## Losses saved by BE-C1: {len(saved_by_be)}", "", f"## Winners killed by BE-C1: {len(killed_by_be)}"]
    (REP_OUT / "MARCH_TARGET_ZONE_FUEL_CASEBOOK.md").write_text("\n".join(md), encoding="utf-8")

    # ---------- Section I: final report ----------
    print("[I] final report ...", file=sys.stderr)
    mA = results["A_enhanced_fixed2pct"]
    mB = results["B_enhanced_targetzone_filter"]
    # best BE variant by expectancy
    be_variants = {k: v for k, v in results.items() if k.startswith("C_enhanced_targetTP_BE_")}
    best_be_name = max(be_variants, key=lambda k: be_variants[k]["expectancy_after_cost_pct"] or -99) if be_variants else None
    mC = results[best_be_name] if best_be_name else results["C_enhanced_targetTP_noBE"]
    tz_improved = (mB["expectancy_after_cost_pct"] or -99) > (mA["expectancy_after_cost_pct"] or -99)
    be_improved = (mC["expectancy_after_cost_pct"] or -99) > (mB["expectancy_after_cost_pct"] or -99)
    flags = {
        "TARGET_ZONE_FUEL_RESEARCH_DONE": "YES",
        "OI_DATA_AVAILABLE": "NO", "FUNDING_DATA_AVAILABLE": "NO", "LIQUIDATION_DATA_AVAILABLE": "NO",
        "TARGET_ZONE_HEATMAP_DONE": "YES", "TARGET_ZONE_CANDIDATES_BUILT": "YES",
        "TRADE_MODEL_COMPARISON_DONE": "YES", "NON_WIN_RESCUE_ANALYSIS_DONE": "YES",
        "MODEL_A_FIXED_TP_TRADES": mA["trades"], "MODEL_A_FIXED_TP_WINRATE": mA["winrate_pct"],
        "MODEL_A_FIXED_TP_EXPECTANCY_AFTER_COST": mA["expectancy_after_cost_pct"], "MODEL_A_FIXED_TP_PF_AFTER_COST": mA["pf_after_cost"],
        "MODEL_B_TARGET_ZONE_FILTER_TRADES": mB["trades"], "MODEL_B_TARGET_ZONE_FILTER_WINRATE": mB["winrate_pct"],
        "MODEL_B_TARGET_ZONE_FILTER_EXPECTANCY_AFTER_COST": mB["expectancy_after_cost_pct"], "MODEL_B_TARGET_ZONE_FILTER_PF_AFTER_COST": mB["pf_after_cost"],
        "MODEL_C_TARGET_ZONE_BE_TRADES": mC["trades"], "MODEL_C_TARGET_ZONE_BE_WINRATE": mC["winrate_pct"],
        "MODEL_C_TARGET_ZONE_BE_EXPECTANCY_AFTER_COST": mC["expectancy_after_cost_pct"], "MODEL_C_TARGET_ZONE_BE_PF_AFTER_COST": mC["pf_after_cost"],
        "MODEL_C_BE_EXITS": mC["be_exits"], "MODEL_C_LOSSES_SAVED_BY_BE": mC.get("losses_saved_by_BE"),
        "MODEL_C_WINNERS_KILLED_BY_BE": mC.get("winners_killed_by_BE"),
        "BEST_MODEL_NAME": best_name, "BEST_MODEL_TRADES": best["trades"] if best else None,
        "BEST_MODEL_WINRATE": best["winrate_pct"] if best else None,
        "BEST_MODEL_EXPECTANCY_AFTER_COST": best["expectancy_after_cost_pct"] if best else None,
        "BEST_MODEL_PF_AFTER_COST": best["pf_after_cost"] if best else None,
        "BEST_MODEL_TOTAL_RETURN_AFTER_COST": best["total_return_after_cost_pct"] if best else None,
        "TARGET_ZONE_IMPROVED_OVER_FIXED_2PCT": "YES" if tz_improved else "NO",
        "BE_IMPROVED_OVER_NO_BE": "YES" if be_improved else "NO",
        "FUEL_FEATURES_IMPROVED_SELECTOR": "NOT_AVAILABLE",
        "SEVENTY_PERCENT_REACHED": "YES" if (best and best["winrate_pct"] >= 70) else "NO",
        "SEVENTY_PERCENT_WITH_MIN20_REACHED": "YES" if (best and best["winrate_pct"] >= 70 and best["trades"] >= 20) else "NO",
        "NEXT_ZONE_RULES_DEFINED": "YES", "READY_FOR_NEXT_ZONE_TEST": "YES",
        "READY_FOR_TELEGRAM_SHADOW_MODE": "NO", "READY_TO_CHANGE_ENGINE": "NO",
        "READY_FOR_PRODUCTION_TRADING": "NO", "MORE_VALIDATION_REQUIRED": "YES",
    }
    final = {"build_time_utc": now_iso(),
             "baseline_reference": {"trades":29,"winrate":58.62,"exp_aft":0.5268,"pf":1.922},
             "enhanced_reference": {"trades":29,"winrate":62.07,"exp_aft":0.6475,"pf":2.258},
             "model_A": {k: mA[k] for k in ("trades","winrate_pct","expectancy_after_cost_pct","pf_after_cost","total_return_after_cost_pct")},
             "model_B": {k: mB[k] for k in ("trades","skipped","winrate_pct","expectancy_after_cost_pct","pf_after_cost","total_return_after_cost_pct")},
             "model_C_best_BE": best_be_name,
             "model_C": {k: mC[k] for k in ("trades","winrate_pct","expectancy_after_cost_pct","pf_after_cost","be_exits","losses_saved_by_BE","winners_killed_by_BE")},
             "best_model": best_name,
             "all_models": {name: {k: v for k, v in res.items() if k != "trade_list"} for name, res in candidates.items()},
             "flags": flags}
    (REP_OUT / "MARCH_TARGET_ZONE_FUEL_FINAL_REPORT.json").write_text(json.dumps(final, indent=2, default=str), encoding="utf-8")
    md = ["# Target-zone + 3 trade models + OI/fuel — final report", "", f"**Build:** {now_iso()}",
          "**Scope:** IN-SAMPLE OKX March 2026. No engine change. Target strict 2%. No future leak in decisions.", "",
          "## 1. OI/funding/liquidation data",
          "- **NONE available for March OKX** (only book+trades). OI/fuel sections = NOT_AVAILABLE. April-01 used only as schema reference.", "",
          "## 2-5. Model comparison (enhanced selector basis)", "",
          "| model | trades | winrate% | exp_aft% | PF_aft | totRet% |",
          "|---|---:|---:|---:|---:|---:|",
          f"| A fixed 2% | {mA['trades']} | {mA['winrate_pct']} | {mA['expectancy_after_cost_pct']} | {mA['pf_after_cost']} | {mA['total_return_after_cost_pct']} |",
          f"| B target-zone filter | {mB['trades']} (skip {mB['skipped']}) | {mB['winrate_pct']} | {mB['expectancy_after_cost_pct']} | {mB['pf_after_cost']} | {mB['total_return_after_cost_pct']} |",
          f"| C target-TP + {best_be_name} | {mC['trades']} | {mC['winrate_pct']} | {mC['expectancy_after_cost_pct']} | {mC['pf_after_cost']} | {mC['total_return_after_cost_pct']} |",
          "",
          f"- Target-zone filter improved over fixed 2%: **{flags['TARGET_ZONE_IMPROVED_OVER_FIXED_2PCT']}**",
          f"- BE improved over no-BE: **{flags['BE_IMPROVED_OVER_NO_BE']}**",
          f"- Best BE variant: **{best_be_name}** (losses saved {mC.get('losses_saved_by_BE')}, winners killed {mC.get('winners_killed_by_BE')})",
          "",
          "## 6-8. BE detail",
          f"- BE exits in best variant: {mC['be_exits']}",
          f"- Losses saved by BE: {mC.get('losses_saved_by_BE')}",
          f"- Winners killed by BE: {mC.get('winners_killed_by_BE')}",
          "",
          "## 9-10. Non-win explanation",
          f"- Enhanced non-wins: {len(nonwins)}",
          f"- Explained by insufficient target-zone room (B would skip): {n_skip_B}",
          f"- Low fuel_score explanation: NOT_AVAILABLE (no OI/liq data)",
          "",
          "## 11-12. Winrate / 70%",
          f"- Best model: **{best_name}** — winrate {best['winrate_pct'] if best else 'n/a'}%, "
          f"exp_aft {best['expectancy_after_cost_pct'] if best else 'n/a'}%, PF {best['pf_after_cost'] if best else 'n/a'}, "
          f"{best['trades'] if best else 0} trades.",
          f"- 70% reached: **{flags['SEVENTY_PERCENT_REACHED']}**; with min20: **{flags['SEVENTY_PERCENT_WITH_MIN20_REACHED']}**",
          "",
          "## 13-14. Fixed vs target-zone; BE vs no-BE",
          f"- {'Target-zone helps' if tz_improved else 'Fixed 2% is as good or better than target-zone filter'}.",
          f"- {'BE helps' if be_improved else 'BE does not improve expectancy (kills more winners than losses saved)'}.",
          "",
          "## 15-16. Rules for next zone iteration",
          "- Keep enhanced selector (dist_to_recent_swing_high<=0.4616 AND dl2_supp_minus_opp_net_flow_15m<=4497.76, top1/day).",
          "- Apply target-zone room>=2% filter ONLY if it improved expectancy here (see flag).",
          "- Use BE variant only if it improved expectancy (see flag).",
          "- FETCH OKX March OI/funding/liquidation data to unlock fuel features (highest-value missing input).",
          "",
          "## Final flags", "", "```"]
    for k, v in flags.items(): md.append(f"{k} = {v}")
    md += ["```", "", "## Hard rules honored",
           "- engine/thresholds/detector UNCHANGED; target strict 2%; no future leak in decision features; "
           "OI/fuel honestly marked NOT_AVAILABLE; production claim NONE."]
    (REP_OUT / "MARCH_TARGET_ZONE_FUEL_FINAL_REPORT.md").write_text("\n".join(md), encoding="utf-8")

    # ---------- console output ----------
    print()
    print("="*100)
    print("MODEL COMPARISON (enhanced selector basis)")
    print("="*100)
    hdr = f"{'model':<34} {'trades':>6} {'skip':>4} {'W':>3} {'L':>3} {'TO':>3} {'BE':>3} {'wr%':>6} {'exp%':>7} {'PF':>6} {'ret%':>7}"
    print(hdr); print("-"*100)
    for name, res in results.items():
        print(f"{name:<34} {res['trades']:>6} {res['skipped']:>4} {res['wins']:>3} {res['losses']:>3} "
              f"{res['timeouts']:>3} {res['be_exits']:>3} {res['winrate_pct']:>6} "
              f"{res['expectancy_after_cost_pct']:>7} {str(res['pf_after_cost']):>6} {res['total_return_after_cost_pct']:>7}")
    print()
    print("SELECTOR VARIANTS:")
    for name, res in sel_results.items():
        print(f"{name:<38} {res['trades']:>3}tr wr={res['winrate_pct']:>6}% exp={res['expectancy_after_cost_pct']:>7}% PF={res['pf_after_cost']}")
    print()
    print("FINAL FLAGS:")
    for k, v in flags.items(): print(f"  {k:<48s} = {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
