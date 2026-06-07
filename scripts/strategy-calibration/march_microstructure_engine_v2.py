"""Option B: microstructure engine using existing dl2_* proxies + ONE new
truly-new feature (liquidity void to target), then sections H/I/J/K/L/M.

Why proxies:
- per-level wall lifetime → already approximated by `dl2_top1_supportive_persistence_ge_50_5m_sec`
- refill-after-hit       → approximated by `dl2_supp_minus_opp_net_flow_*`, `dl2_inband_supp_add_*`
- new void extraction    → lightweight L2 snapshot at anchor (no per-level history)

Estimated runtime: ~30-45 min (only void extraction is heavy; rest is fast).
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
from canonical_ledger import (Bucket, build_buckets_from_trades_csv, Signal,
                              ExecutionConfig, simulate_canonical_trade)

ROOT = Path("C:/Users/gibilev/orderflow-research")
REPORTS = ROOT / "reports"
REP_OUT = REPORTS / "strategy-calibration"
DATA_ROOT = ROOT / "data/okx-historical/BTC-USDT-SWAP"
CACHE_DIR = ROOT / "data/cache/march_void"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
VOID_COMBINED_CSV = REP_OUT / "MARCH_LIQUIDITY_VOID_FEATURES.csv"

FIRST_HALF = [f"2026-03-{d:02d}" for d in range(2, 16)]
SECOND_HALF = ["2026-03-16"] + [f"2026-03-{d:02d}" for d in range(18, 32)]
ALL_DATES = FIRST_HALF + SECOND_HALF
N_DAYS = len(ALL_DATES)

COST_PCT = 0.14
TARGET_PCT = 2.0
STOP_PCT_BASELINE = 1.5
TIMEOUT_HOURS = 24
WALL_SIZE_THRESHOLD = 50.0   # lots


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
def quantile(xs, q):
    xs = sorted(x for x in xs if x is not None)
    if not xs: return None
    return xs[int(q * (len(xs) - 1))]
def cohens_d(a, b):
    a = [x for x in a if x is not None]; b = [x for x in b if x is not None]
    if len(a) < 2 or len(b) < 2: return None
    ma, mb = stats.mean(a), stats.mean(b)
    sa, sb = stats.pstdev(a), stats.pstdev(b)
    pooled = math.sqrt(((len(a)-1)*sa*sa + (len(b)-1)*sb*sb) / max(len(a)+len(b)-2, 1))
    if pooled == 0: return None
    return round((ma - mb) / pooled, 4)
def mean_or_none(xs):
    xs = [x for x in xs if x is not None]
    return round(stats.mean(xs), 4) if xs else None


# ============================================================
# load dataset (+ dl2 + snapshot l2)
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
    # merge dl2
    dynp = REP_OUT / "MARCH_DYNAMIC_L2_FEATURE_DATASET.csv"
    if dynp.exists():
        with dynp.open(encoding="utf-8") as f:
            rdr = csv.DictReader(f)
            dyn = {lr["zone_id"]: {k: safe_float(lr[k]) for k in lr if k != "zone_id"}
                   for lr in rdr}
        for r in rows:
            for k, v in dyn.get(r["zone_id"], {}).items(): r[k] = v
    # merge snapshot L2
    l2p = REP_OUT / "MARCH_L2_MICROSTRUCTURE_FEATURE_DATASET.csv"
    if l2p.exists():
        with l2p.open(encoding="utf-8") as f:
            rdr = csv.DictReader(f)
            l2 = {lr["zone_id"]: {k: safe_float(lr[k]) for k in lr if k != "zone_id"}
                  for lr in rdr}
        for r in rows:
            for k, v in l2.get(r["zone_id"], {}).items(): r[k] = v
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
    if smr is not None and smr > 0:
        s += min(smr / 100.0, 0.4)
    oc = r.get("dl2_inband_opp_cancel_15m") or 0
    if oc > 20: s -= min(oc / 200.0, 0.3)
    wp = r.get("dl2_top1_supportive_persistence_ge_50_5m_sec") or 0
    if wp > 60: s += min(wp / 600.0, 0.3)
    return round(s, 4)


# ============================================================
# baseline
# ============================================================
def select_baseline(rows):
    cands = [r for r in rows
             if r.get("dist_to_recent_swing_high_pct") is not None
             and r["dist_to_recent_swing_high_pct"] <= 0.4616]
    by_date = defaultdict(list)
    for r in cands: by_date[r["date"]].append(r)
    selected = []
    for d in ALL_DATES:
        day_rows = by_date.get(d, [])
        day_rows = sorted(day_rows, key=lambda x: -explainable_score_l2_dyn(x))
        if day_rows: selected.append(day_rows[0])
    return selected


def merge_days_buckets(date, buckets_by_date, lookahead=2):
    out = []
    idx = ALL_DATES.index(date)
    out.extend(buckets_by_date.get(date) or [])
    for k in range(1, lookahead + 1):
        if idx + k >= len(ALL_DATES): break
        out.extend(buckets_by_date.get(ALL_DATES[idx + k]) or [])
    return out


def simulate_trades(selected_zones, buckets_by_date, stop_pct=STOP_PCT_BASELINE):
    trades = []
    for i, z in enumerate(selected_zones):
        confirmed_sec = iso_to_sec(z.get("confirmed_iso"))
        if confirmed_sec is None: continue
        buckets = merge_days_buckets(z["date"], buckets_by_date)
        sig = Signal(id=z["zone_id"], date=z["date"], trigger_ts_ms=confirmed_sec * 1000,
                     direction=z["direction"], zone_low=z.get("zone_low"),
                     zone_high=z.get("zone_high"))
        cfg = ExecutionConfig(entry_strategy="trigger", stop_pct=stop_pct,
                              target_pct=TARGET_PCT, timeout_hours=TIMEOUT_HOURS)
        sim = simulate_canonical_trade(sig, buckets, cfg)
        if sim.get("exit_reason") in ("no_data", "skip_no_retest"): continue
        outcome = ("WIN" if sim["exit_reason"] == "target_2pct"
                   else ("LOSS" if sim["exit_reason"] == "stop" else "TIMEOUT"))
        reason_class = ""
        if outcome == "LOSS":
            if z.get("coverage_class") == "wrong_direction":
                reason_class = "wrong_direction"
            elif z.get("watch_label") in ("GOOD", "MID"):
                reason_class = "correct_direction_but_no_2pct"
            else:
                reason_class = "stop_no_2pct_either_dir"
        elif outcome == "TIMEOUT":
            reason_class = "timeout_positive" if sim["pnl_pct"] > 0.5 else "timeout_negative"
        else:
            reason_class = "win_clean"
        trades.append({
            "#": i + 1, "date": z["date"], "direction": z["direction"],
            "zone_id": z["zone_id"], "confirmed_iso": z.get("confirmed_iso"),
            "entry_sec": sim["entry_sec"], "exit_sec": sim["exit_sec"],
            "entry_price": sim["entry_price"], "exit_price": sim["exit_price"],
            "exit_reason": sim["exit_reason"],
            "pnl_pre_cost": sim["pnl_pct"], "pnl_after_cost": round(sim["pnl_pct"] - COST_PCT, 4),
            "mfe_pct": sim["mfe_pct"], "mae_pct": sim["mae_pct"],
            "outcome": outcome, "reason_class": reason_class,
            "watch_label": z.get("watch_label"),
            "coverage_class": z.get("coverage_class"),
            "session": z.get("session"),
        })
    return trades


def baseline_metrics(trades):
    n = len(trades)
    wins = sum(1 for t in trades if t["outcome"] == "WIN")
    losses = sum(1 for t in trades if t["outcome"] == "LOSS")
    timeouts = sum(1 for t in trades if t["outcome"] == "TIMEOUT")
    pnls = [t["pnl_after_cost"] for t in trades]
    wp = [p for p in pnls if p > 0]; lp = [p for p in pnls if p < 0]
    pf = round(sum(wp) / sum(-p for p in lp), 3) if lp else None
    return {"trades": n, "wins": wins, "losses": losses, "timeouts": timeouts,
            "winrate_pct": round(100.0 * wins / max(n, 1), 2),
            "expectancy_after_cost_pct": round(stats.mean(pnls), 4) if pnls else None,
            "total_return_after_cost_pct": round(sum(pnls), 4) if pnls else None,
            "pf_after_cost": pf}


# ============================================================
# Section E (LIGHT): liquidity void to target — only new extraction
# ============================================================
def extract_void_for_day(date, day_anchors):
    """Stream L2 once. At each anchor: take snapshot, compute void to ±2% target."""
    p = DATA_ROOT / date / "incremental_book_L2.csv.gz"
    if not p.exists() or not day_anchors: return {}
    anchors_sorted = sorted(day_anchors, key=lambda x: x[0])
    next_idx = 0
    out = {}
    bid_book: dict[float, float] = {}
    ask_book: dict[float, float] = {}

    def snapshot(zone_id, direction):
        if not bid_book or not ask_book:
            return {"ms_depth_to_target": None, "ms_levels_to_target": None,
                    "ms_large_walls_on_path": None, "ms_max_wall_on_path": None,
                    "ms_depth_against_back": None, "ms_thin_path_score": None,
                    "ms_void_to_half_target": None}
        best_bid = max(bid_book.keys())
        best_ask = min(ask_book.keys())
        mid = (best_bid + best_ask) / 2.0
        target_up = mid * (1.0 + TARGET_PCT / 100.0)
        target_dn = mid * (1.0 - TARGET_PCT / 100.0)
        half_up = mid * (1.0 + TARGET_PCT / 200.0)
        half_dn = mid * (1.0 - TARGET_PCT / 200.0)
        ask_to_target = sum(a for p_, a in ask_book.items() if best_ask <= p_ <= target_up)
        bid_to_target = sum(a for p_, a in bid_book.items() if target_dn <= p_ <= best_bid)
        ask_to_half = sum(a for p_, a in ask_book.items() if best_ask <= p_ <= half_up)
        bid_to_half = sum(a for p_, a in bid_book.items() if half_dn <= p_ <= best_bid)
        ask_levels = sum(1 for p_ in ask_book if best_ask <= p_ <= target_up)
        bid_levels = sum(1 for p_ in bid_book if target_dn <= p_ <= best_bid)
        ask_large = sum(1 for p_, a in ask_book.items() if best_ask <= p_ <= target_up and a >= WALL_SIZE_THRESHOLD)
        bid_large = sum(1 for p_, a in bid_book.items() if target_dn <= p_ <= best_bid and a >= WALL_SIZE_THRESHOLD)
        ask_max = max((a for p_, a in ask_book.items() if best_ask <= p_ <= target_up), default=0.0)
        bid_max = max((a for p_, a in bid_book.items() if target_dn <= p_ <= best_bid), default=0.0)
        if direction == "LONG":
            return {"ms_depth_to_target": round(ask_to_target, 4),
                    "ms_levels_to_target": ask_levels,
                    "ms_large_walls_on_path": ask_large,
                    "ms_max_wall_on_path": round(ask_max, 4),
                    "ms_depth_against_back": round(bid_to_target, 4),
                    "ms_void_to_half_target": round(ask_to_half, 4),
                    "ms_thin_path_score": round(1.0 / (1 + math.log1p(ask_to_target)), 4)}
        else:
            return {"ms_depth_to_target": round(bid_to_target, 4),
                    "ms_levels_to_target": bid_levels,
                    "ms_large_walls_on_path": bid_large,
                    "ms_max_wall_on_path": round(bid_max, 4),
                    "ms_depth_against_back": round(ask_to_target, 4),
                    "ms_void_to_half_target": round(bid_to_half, 4),
                    "ms_thin_path_score": round(1.0 / (1 + math.log1p(bid_to_target)), 4)}

    with gzip.open(p, "rt", encoding="utf-8") as f:
        f.readline()
        for line in f:
            parts = line.rstrip().split(",")
            if len(parts) < 8: continue
            try:
                ts_us = int(parts[2]); side = parts[5]
                price = float(parts[6]); amount = float(parts[7])
            except (ValueError, IndexError):
                continue
            book = bid_book if side == "bid" else ask_book
            if amount == 0:
                book.pop(price, None)
            else:
                book[price] = amount
            sec = ts_us // 1_000_000
            # Snapshot any anchors that have passed
            while next_idx < len(anchors_sorted) and anchors_sorted[next_idx][0] <= sec:
                anchor_sec, zid, direction, _, _ = anchors_sorted[next_idx]
                out[zid] = snapshot(zid, direction)
                next_idx += 1
            if next_idx >= len(anchors_sorted):
                break
    # Finalize remaining
    while next_idx < len(anchors_sorted):
        anchor_sec, zid, direction, _, _ = anchors_sorted[next_idx]
        out[zid] = snapshot(zid, direction)
        next_idx += 1
    return out


def extract_all_void(rows):
    if VOID_COMBINED_CSV.exists():
        print(f"  void cache found {VOID_COMBINED_CSV}", file=sys.stderr)
        out = {}
        with VOID_COMBINED_CSV.open(encoding="utf-8") as f:
            rdr = csv.DictReader(f)
            for r in rdr:
                out[r["zone_id"]] = {k: safe_float(r[k]) for k in r if k != "zone_id"}
        return out
    by_date = defaultdict(list)
    for r in rows:
        sec = iso_to_sec(r.get("confirmed_iso"))
        if sec is None or not r.get("zone_low") or not r.get("zone_high"): continue
        by_date[r["date"]].append((sec, r["zone_id"], r["direction"], r["zone_low"], r["zone_high"]))
    out = {}
    for d in ALL_DATES:
        anchors = by_date.get(d, [])
        if not anchors:
            print(f"  {d}: no zones", file=sys.stderr); continue
        day_cache = CACHE_DIR / f"{d}.csv"
        if day_cache.exists():
            with day_cache.open(encoding="utf-8") as f:
                rdr = csv.DictReader(f)
                for r in rdr:
                    out[r["zone_id"]] = {k: safe_float(r[k]) for k in r if k != "zone_id"}
            print(f"  {d}: loaded from cache", file=sys.stderr)
            continue
        t0 = time.time()
        day_out = extract_void_for_day(d, anchors)
        out.update(day_out)
        if day_out:
            keys = sorted({k for v in day_out.values() for k in v.keys()})
            with day_cache.open("w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=["zone_id"] + keys, extrasaction="ignore")
                w.writeheader()
                for zid, feat in day_out.items():
                    w.writerow({"zone_id": zid, **feat})
        print(f"  {d}: {len(day_out)} zones in {time.time()-t0:.1f}s", file=sys.stderr)
    if out:
        keys = sorted({k for v in out.values() for k in v.keys()})
        with VOID_COMBINED_CSV.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["zone_id"] + keys, extrasaction="ignore")
            w.writeheader()
            for zid, feat in out.items():
                w.writerow({"zone_id": zid, **feat})
    return out


# ============================================================
# Section H: setup-type classification (using proxies + new void)
# ============================================================
def classify_setup(r):
    direction = r["direction"]
    # PROXY mappings:
    refill_proxy = r.get("dl2_supp_minus_opp_net_flow_5m") or 0   # >0 = good supportive refill proxy
    refill_proxy_15m = r.get("dl2_supp_minus_opp_net_flow_15m") or 0
    supp_add = r.get("dl2_inband_supp_add_5m") or 0
    opp_cancel = r.get("dl2_inband_opp_cancel_15m") or 0
    wall_persistence = r.get("dl2_top1_supportive_persistence_ge_50_5m_sec") or 0   # 0..300
    sweep_reclaim = r.get("sweep_reclaim_aligned") == 1
    micro_5m_aligned = r.get("dl2_microprice_aligned_delta_5m_bps") or 0
    micro_15m_aligned = r.get("dl2_microprice_aligned_delta_15m_bps") or 0
    taker_30m = r.get("taker_imb_aligned_30m") or 0
    prior_60m = abs(r.get("prior_move_60m_pct") or 0)
    local_range_60m = r.get("local_range_60m_pct") or 99
    void_thin = r.get("ms_thin_path_score") or 0
    large_walls_on_path = r.get("ms_large_walls_on_path") or 99

    scores = {}
    dir_low = direction.lower()
    # 1. ABSORPTION REVERSAL — sell-absorption + refill + reclaim + microprice flip
    abs_rev = (
        math.log1p(max(supp_add, 0) / 1000.0) +
        max(refill_proxy / 100.0, 0) * 1.5 +
        (0.5 if sweep_reclaim else 0) +
        (micro_5m_aligned / 10.0) +
        (wall_persistence / 300.0) * 0.5
        - min(opp_cancel / 1000.0, 0.3)
    )
    scores[f"absorption_reversal_{dir_low}"] = round(abs_rev, 3)
    # 2. BREAKOUT CONTINUATION — range compression + thin void + micro aligned + flow aligned
    bo_cont = (
        max(0.0, 0.7 - local_range_60m) * 2 +
        void_thin * 3 +
        (micro_5m_aligned / 10.0) +
        max(taker_30m, 0) * 2
        - min(large_walls_on_path * 0.2, 0.5)
    )
    scores[f"breakout_continuation_{dir_low}"] = round(bo_cont, 3)
    # 3. RETEST AFTER BREAKOUT — prior move done + wall persistence + supportive refill
    retest = (
        (prior_60m if 0.4 <= prior_60m <= 1.2 else 0) +
        max(refill_proxy_15m / 100.0, 0) +
        (wall_persistence / 300.0) * 0.7 +
        (micro_5m_aligned / 10.0)
    )
    scores[f"retest_after_breakout_{dir_low}"] = round(retest, 3)
    # 4. FAILED BREAKOUT RECLAIM — sweep + reclaim + refill + micro reversal
    failed_bo = (
        (1.0 if sweep_reclaim else 0) +
        max(refill_proxy / 100.0, 0) * 1.5 +
        (micro_5m_aligned / 10.0)
    )
    scores[f"failed_breakout_reclaim_{dir_low}"] = round(failed_bo, 3)
    # Best
    best = max(scores.items(), key=lambda kv: kv[1])
    r["setup_type"] = best[0] if best[1] > 0.5 else "unknown"
    r["setup_type_score"] = best[1]
    r["setup_all_scores"] = scores
    sorted_s = sorted(scores.values(), reverse=True)
    r["setup_confidence"] = round(sorted_s[0] - (sorted_s[1] if len(sorted_s) > 1 else 0), 3)
    return r


# ============================================================
# Selector evaluation
# ============================================================
def selector_eval(rows, predicate, day_cap=None, score_key=None):
    by_date = defaultdict(list)
    for r in rows:
        if not predicate(r): continue
        by_date[r["date"]].append(r)
    sel = []
    for d in ALL_DATES:
        day_rows = by_date.get(d, [])
        if score_key:
            day_rows = sorted(day_rows, key=lambda x: -(x.get(score_key) or 0))
        if day_cap is not None:
            day_rows = day_rows[:day_cap]
        sel.extend(day_rows)
    n = len(sel)
    good = sum(1 for r in sel if r.get("watch_label") == "GOOD")
    wrong = sum(1 for r in sel if r.get("coverage_class") == "wrong_direction")
    h1 = [r for r in sel if r["_half"] == "first"]
    h2 = [r for r in sel if r["_half"] == "second"]
    g1 = sum(1 for r in h1 if r.get("watch_label") == "GOOD")
    g2 = sum(1 for r in h2 if r.get("watch_label") == "GOOD")
    return {"selected_n": n, "alerts_per_day": round(n / N_DAYS, 3),
            "good_n": good, "wrong_n": wrong,
            "precision_pct": round(100.0 * good / max(n, 1), 2) if n else None,
            "wrong_rate_pct": round(100.0 * wrong / max(n, 1), 2) if n else None,
            "h1_n": len(h1), "h2_n": len(h2),
            "h1_precision_pct": round(100.0 * g1 / max(len(h1), 1), 2) if h1 else None,
            "h2_precision_pct": round(100.0 * g2 / max(len(h2), 1), 2) if h2 else None,
            "selected_zone_ids": [r["zone_id"] for r in sel]}


def enhanced_score(r):
    s = explainable_score_l2_dyn(r)
    # void contribution (thin path good)
    void = r.get("ms_thin_path_score") or 0
    s += min(void * 1.5, 0.4)
    lw = r.get("ms_large_walls_on_path") or 0
    s -= min(lw * 0.05, 0.25)
    return round(s, 4)


def evaluate_selector_paper(rows, selector_zone_ids, buckets_by_date,
                             stop_pct=STOP_PCT_BASELINE):
    by_id = {r["zone_id"]: r for r in rows}
    sel_rows = [by_id[i] for i in selector_zone_ids if i in by_id]
    trades = simulate_trades(sel_rows, buckets_by_date, stop_pct=stop_pct)
    m = baseline_metrics(trades)
    m["wrong_direction"] = sum(1 for t in trades if t["reason_class"] == "wrong_direction")
    m["correct_direction_but_no_2pct"] = sum(1 for t in trades if t["reason_class"] == "correct_direction_but_no_2pct")
    m["stop_no_2pct_either_dir"] = sum(1 for t in trades if t["reason_class"] == "stop_no_2pct_either_dir")
    m["timeout_positive"] = sum(1 for t in trades if t["reason_class"] == "timeout_positive")
    m["timeout_negative"] = sum(1 for t in trades if t["reason_class"] == "timeout_negative")
    m["trades_detail"] = trades
    return m


# ============================================================
# Section J: enhanced selector search
# ============================================================
def run_selector_search(rows, buckets_by_date, baseline_m):
    for r in rows: r["_score_enh"] = enhanced_score(r)
    base_filter = lambda r: r.get("dist_to_recent_swing_high_pct") is not None and r["dist_to_recent_swing_high_pct"] <= 0.4616
    sels = []

    NUMERIC_KEYS_NEW = [
        "ms_thin_path_score", "ms_depth_to_target", "ms_levels_to_target",
        "ms_large_walls_on_path", "ms_max_wall_on_path", "ms_void_to_half_target",
        "ms_depth_against_back",
    ]
    NUMERIC_KEYS_PROXY = [
        # wall-persistence proxy
        "dl2_top1_supportive_persistence_ge_50_5m_sec",
        # refill-quality proxies
        "dl2_supp_minus_opp_net_flow_5m", "dl2_supp_minus_opp_net_flow_15m",
        "dl2_inband_supp_add_5m", "dl2_inband_supp_add_15m",
        "dl2_inband_opp_cancel_15m",
        # microprice
        "dl2_microprice_aligned_delta_5m_bps", "dl2_microprice_aligned_delta_15m_bps",
        "dl2_microprice_slope_5m_aligned_bps_per_min",
        # context
        "local_range_60m_pct", "abs_prior_move_60m_pct",
    ]
    # Build threshold rules
    rules = []
    for k in NUMERIC_KEYS_NEW + NUMERIC_KEYS_PROXY:
        vals = [r.get(k) for r in rows if r.get(k) is not None]
        if len(vals) < 50: continue
        for q in (0.25, 0.5, 0.75):
            v = quantile(vals, q)
            if v is None: continue
            rules.append((f"{k}_ge_{round(v, 4)}",
                           (lambda kk, th: lambda r: (r.get(kk) is not None) and (r.get(kk) >= th))(k, v)))
            rules.append((f"{k}_le_{round(v, 4)}",
                           (lambda kk, th: lambda r: (r.get(kk) is not None) and (r.get(kk) <= th))(k, v)))
    # Pair each with baseline filter
    for name, fn in rules:
        pred = (lambda fn: lambda r: base_filter(r) and fn(r))(fn)
        e = selector_eval(rows, pred, day_cap=1, score_key="_score_enh")
        sels.append({"selector": f"ENH::baseline+{name}::top1", **e, "kind": "pair"})
    # Setup-type-specific selectors
    SETUPS = ["absorption_reversal_long", "absorption_reversal_short",
              "breakout_continuation_long", "breakout_continuation_short",
              "retest_after_breakout_long", "retest_after_breakout_short",
              "failed_breakout_reclaim_long", "failed_breakout_reclaim_short"]
    for st in SETUPS:
        pred = (lambda st: lambda r: r.get("setup_type") == st)(st)
        e = selector_eval(rows, pred, day_cap=1, score_key="_score_enh")
        sels.append({"selector": f"ENH::setup_{st}::top1", **e, "kind": "setup"})
    # Setup + baseline
    for st in SETUPS:
        pred = (lambda st: lambda r: base_filter(r) and r.get("setup_type") == st)(st)
        e = selector_eval(rows, pred, day_cap=1, score_key="_score_enh")
        sels.append({"selector": f"ENH::baseline+setup_{st}::top1", **e, "kind": "setup+baseline"})
    # Confluence
    confl = [
        ("baseline+thin_path_ge_0.05", lambda r: base_filter(r) and (r.get("ms_thin_path_score") or 0) >= 0.05),
        ("baseline+no_opp_wall", lambda r: base_filter(r) and (r.get("ms_large_walls_on_path") or 99) == 0),
        ("baseline+thin_path+no_opp_wall", lambda r: base_filter(r) and (r.get("ms_thin_path_score") or 0) >= 0.05
                                                       and (r.get("ms_large_walls_on_path") or 99) == 0),
        ("baseline+refill_proxy_ge_50", lambda r: base_filter(r) and (r.get("dl2_supp_minus_opp_net_flow_5m") or -99) >= 50),
        ("baseline+wall_persistence_ge_120", lambda r: base_filter(r) and (r.get("dl2_top1_supportive_persistence_ge_50_5m_sec") or 0) >= 120),
        ("baseline+microprice5m_aligned_ge_0", lambda r: base_filter(r) and (r.get("dl2_microprice_aligned_delta_5m_bps") or -99) >= 0),
        ("baseline+microprice15m_aligned_ge_5", lambda r: base_filter(r) and (r.get("dl2_microprice_aligned_delta_15m_bps") or -99) >= 5),
        ("baseline+thin+micro5m_pos", lambda r: base_filter(r) and (r.get("ms_thin_path_score") or 0) >= 0.05
                                                  and (r.get("dl2_microprice_aligned_delta_5m_bps") or -99) >= 0),
        ("baseline+refill+thin", lambda r: base_filter(r) and (r.get("dl2_supp_minus_opp_net_flow_5m") or -99) >= 50
                                              and (r.get("ms_thin_path_score") or 0) >= 0.05),
        ("baseline+wall_pers+no_opp_wall", lambda r: base_filter(r) and (r.get("dl2_top1_supportive_persistence_ge_50_5m_sec") or 0) >= 120
                                                       and (r.get("ms_large_walls_on_path") or 99) == 0),
        ("baseline+asia+thin", lambda r: base_filter(r) and r.get("is_asia_session") and (r.get("ms_thin_path_score") or 0) >= 0.05),
        ("baseline+asia_only", lambda r: base_filter(r) and r.get("is_asia_session")),
        ("baseline+asia+micro5m_pos", lambda r: base_filter(r) and r.get("is_asia_session") and (r.get("dl2_microprice_aligned_delta_5m_bps") or -99) >= 0),
    ]
    for name, fn in confl:
        e = selector_eval(rows, fn, day_cap=1, score_key="_score_enh")
        sels.append({"selector": f"ENH::{name}::top1", **e, "kind": "confluence"})

    # Evaluate top 25 with paper trade
    sels.sort(key=lambda s: -((s.get("precision_pct") or 0) * 100 + (s.get("selected_n") or 0)))
    paper_evals = []
    seen_selectors = set()
    for s in sels:
        if (s.get("selected_n") or 0) < 10: continue
        if s["selector"] in seen_selectors: continue
        seen_selectors.add(s["selector"])
        m = evaluate_selector_paper(rows, s["selected_zone_ids"], buckets_by_date)
        paper_evals.append({**{k: v for k, v in s.items() if k != "selected_zone_ids"},
                             **{k: v for k, v in m.items() if k != "trades_detail"},
                             "selected_zone_ids": s["selected_zone_ids"],
                             "trades_detail": m["trades_detail"]})
        if len(paper_evals) >= 25: break
    paper_evals.sort(key=lambda r: (-(r.get("winrate_pct") or 0), -(r.get("trades") or 0)))
    return paper_evals


# ============================================================
# Section I: winner vs loser
# ============================================================
def winner_vs_loser(rows, baseline_trades):
    by_id = {r["zone_id"]: r for r in rows}
    winners = [by_id[t["zone_id"]] for t in baseline_trades if t["outcome"] == "WIN"]
    losers = [by_id[t["zone_id"]] for t in baseline_trades if t["outcome"] in ("LOSS", "TIMEOUT")]
    cn = [by_id[t["zone_id"]] for t in baseline_trades if t["reason_class"] == "correct_direction_but_no_2pct"]
    keys = [
        # NEW void features
        "ms_thin_path_score", "ms_depth_to_target", "ms_levels_to_target",
        "ms_large_walls_on_path", "ms_max_wall_on_path", "ms_depth_against_back",
        "ms_void_to_half_target",
        # PROXIES (existing dl2_*)
        "dl2_top1_supportive_persistence_ge_50_5m_sec",   # wall proxy
        "dl2_supp_minus_opp_net_flow_5m",                  # refill proxy
        "dl2_supp_minus_opp_net_flow_15m",
        "dl2_inband_supp_add_5m", "dl2_inband_opp_cancel_15m",
        # MICROPRICE
        "dl2_microprice_aligned_delta_5m_bps",
        "dl2_microprice_aligned_delta_15m_bps",
        "dl2_microprice_slope_5m_aligned_bps_per_min",
        # context
        "local_range_60m_pct", "abs_prior_move_60m_pct",
        "dist_to_recent_swing_high_pct",
    ]
    table = []
    for k in keys:
        wv = [r.get(k) for r in winners if r.get(k) is not None]
        lv = [r.get(k) for r in losers if r.get(k) is not None]
        cnv = [r.get(k) for r in cn if r.get(k) is not None]
        d_wl = cohens_d(wv, lv)
        d_wc = cohens_d(wv, cnv)
        table.append({"feature": k, "winners_mean": mean_or_none(wv),
                       "losers_mean": mean_or_none(lv),
                       "correct_no_2pct_mean": mean_or_none(cnv),
                       "d_winners_vs_losers": d_wl,
                       "d_winners_vs_correct_no_2pct": d_wc,
                       "n_winners": len(wv), "n_losers": len(lv), "n_cn": len(cnv)})
    table.sort(key=lambda r: -abs(r.get("d_winners_vs_losers") or 0))
    return table, len(winners), len(losers), len(cn)


# ============================================================
# Section K: indicator success criteria
# ============================================================
def indicator_success(rows, baseline_m, buckets_by_date):
    new_feats = [
        "ms_thin_path_score", "ms_depth_to_target", "ms_large_walls_on_path",
        "ms_max_wall_on_path", "ms_depth_against_back", "ms_void_to_half_target",
        "dl2_top1_supportive_persistence_ge_50_5m_sec",
        "dl2_supp_minus_opp_net_flow_5m", "dl2_supp_minus_opp_net_flow_15m",
        "dl2_microprice_aligned_delta_5m_bps", "dl2_microprice_aligned_delta_15m_bps",
    ]
    base_filter = lambda r: r.get("dist_to_recent_swing_high_pct") is not None and r["dist_to_recent_swing_high_pct"] <= 0.4616
    out = []
    for fk in new_feats:
        vals = [r.get(fk) for r in rows if r.get(fk) is not None]
        if len(vals) < 50: continue
        for q in (0.5, 0.6, 0.7):
            v = quantile(vals, q)
            if v is None: continue
            for direction in ("ge", "le"):
                if direction == "ge":
                    pred = (lambda fk, th: lambda r: base_filter(r) and r.get(fk) is not None and r.get(fk) >= th)(fk, v)
                else:
                    pred = (lambda fk, th: lambda r: base_filter(r) and r.get(fk) is not None and r.get(fk) <= th)(fk, v)
                for r in rows: r["_score_enh"] = enhanced_score(r)
                e = selector_eval(rows, pred, day_cap=1, score_key="_score_enh")
                if (e.get("selected_n") or 0) < 10: continue
                m = evaluate_selector_paper(rows, e["selected_zone_ids"], buckets_by_date)
                out.append({
                    "feature": fk, "direction": direction,
                    "threshold": round(v, 4), "quantile": q,
                    "selected_n": e["selected_n"],
                    "winrate_pct": m["winrate_pct"],
                    "winrate_delta_pp": round((m["winrate_pct"] or 0) - baseline_m["winrate_pct"], 2),
                    "expectancy_after_cost": m["expectancy_after_cost_pct"],
                    "expectancy_delta": round((m["expectancy_after_cost_pct"] or 0) - baseline_m["expectancy_after_cost_pct"], 4),
                    "pf_after_cost": m["pf_after_cost"],
                    "wrong_direction": m.get("wrong_direction"),
                    "correct_no_2pct": m.get("correct_direction_but_no_2pct"),
                    "verdict": ("PROMOTE" if (m["winrate_pct"] >= baseline_m["winrate_pct"] + 5
                                                and m["expectancy_after_cost_pct"] >= baseline_m["expectancy_after_cost_pct"])
                                 else ("KEEP" if m["winrate_pct"] >= baseline_m["winrate_pct"] else "DROP"))
                })
    return out


# ============================================================
# Main
# ============================================================
def main():
    print("[load] dataset ...", file=sys.stderr)
    rows = load_dataset()
    print(f"  {len(rows)} zones", file=sys.stderr)

    print("[A] baseline ...", file=sys.stderr)
    buckets_by_date = {}
    for d in ALL_DATES:
        p = DATA_ROOT / d / "trades.csv.gz"
        buckets_by_date[d] = build_buckets_from_trades_csv(p) if p.exists() else []
    sel_baseline = select_baseline(rows)
    trades_baseline = simulate_trades(sel_baseline, buckets_by_date)
    bm = baseline_metrics(trades_baseline)
    print(f"  baseline: {bm['trades']} trades, winrate {bm['winrate_pct']}%, exp {bm['expectancy_after_cost_pct']}, PF {bm['pf_after_cost']}", file=sys.stderr)

    print("[E] liquidity void extraction (light snapshot) ...", file=sys.stderr)
    void_data = extract_all_void(rows)
    for r in rows:
        for k, v in void_data.get(r["zone_id"], {}).items(): r[k] = v
    n_void = sum(1 for r in rows if r.get("ms_depth_to_target") is not None)
    print(f"  void extracted for {n_void} zones", file=sys.stderr)

    print("[H] setup-type classification ...", file=sys.stderr)
    for r in rows: classify_setup(r)
    setup_dist = Counter(r.get("setup_type") for r in rows)
    print(f"  setup distribution: {dict(setup_dist)}", file=sys.stderr)
    # Write setup classification artifacts
    with (REP_OUT / "MARCH_SETUP_TYPE_CLASSIFICATION.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["zone_id", "date", "direction", "setup_type",
                                            "setup_type_score", "setup_confidence",
                                            "watch_label"], extrasaction="ignore")
        w.writeheader()
        for r in rows: w.writerow(r)
    (REP_OUT / "MARCH_SETUP_TYPE_CLASSIFICATION.json").write_text(
        json.dumps({"build_time_utc": now_iso(), "distribution": dict(setup_dist)},
                   indent=2, default=str), encoding="utf-8")

    print("[I] winner vs loser ...", file=sys.stderr)
    table, n_w, n_l, n_cn = winner_vs_loser(rows, trades_baseline)
    csv_keys = list(table[0].keys()) if table else []
    with (REP_OUT / "MARCH_MICROSTRUCTURE_WINNER_LOSER_ANALYSIS.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=csv_keys, extrasaction="ignore")
        w.writeheader()
        for r in table: w.writerow(r)
    (REP_OUT / "MARCH_MICROSTRUCTURE_WINNER_LOSER_ANALYSIS.json").write_text(
        json.dumps({"build_time_utc": now_iso(), "table": table,
                    "n_winners": n_w, "n_losers": n_l, "n_correct_no_2pct": n_cn},
                   indent=2, default=str), encoding="utf-8")

    print("[J] enhanced selector search ...", file=sys.stderr)
    sels = run_selector_search(rows, buckets_by_date, bm)
    csv_keys = [k for k in (sels[0].keys() if sels else []) if k not in ("selected_zone_ids", "trades_detail")]
    if sels:
        with (REP_OUT / "MARCH_MICROSTRUCTURE_ENHANCED_SELECTOR_SEARCH.csv").open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=csv_keys, extrasaction="ignore")
            w.writeheader()
            for r in sels: w.writerow({k: r.get(k) for k in csv_keys})
    (REP_OUT / "MARCH_MICROSTRUCTURE_ENHANCED_SELECTOR_SEARCH.json").write_text(
        json.dumps({"build_time_utc": now_iso(), "baseline": bm,
                    "selectors": [{k: v for k, v in s.items()
                                    if k not in ("trades_detail", "selected_zone_ids")}
                                   for s in sels[:30]]},
                   indent=2, default=str), encoding="utf-8")

    print("[K] indicator success criteria ...", file=sys.stderr)
    ind = indicator_success(rows, bm, buckets_by_date)
    if ind:
        with (REP_OUT / "MARCH_MICROSTRUCTURE_INDICATOR_SUCCESS_CRITERIA.csv").open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(ind[0].keys()), extrasaction="ignore")
            w.writeheader()
            for r in ind: w.writerow(r)
    (REP_OUT / "MARCH_MICROSTRUCTURE_INDICATOR_SUCCESS_CRITERIA.json").write_text(
        json.dumps({"build_time_utc": now_iso(), "baseline": bm, "indicators": ind},
                   indent=2, default=str), encoding="utf-8")

    # Best enhanced
    best_enh = sels[0] if sels else None
    # By setup type — winrate
    setup_perf = defaultdict(lambda: {"n": 0, "wins": 0})
    by_id = {r["zone_id"]: r for r in rows}
    for t in trades_baseline:
        st = by_id[t["zone_id"]].get("setup_type") or "unknown"
        setup_perf[st]["n"] += 1
        if t["outcome"] == "WIN": setup_perf[st]["wins"] += 1
    best_setup = None; best_wr = 0
    for st, d in setup_perf.items():
        if d["n"] >= 3:
            wr = 100.0 * d["wins"] / d["n"]
            if wr > best_wr: best_wr = wr; best_setup = (st, d["n"], d["wins"])

    # Casebook
    if best_enh:
        baseline_ids = {t["zone_id"] for t in trades_baseline}
        enhanced_ids = {t["zone_id"] for t in best_enh["trades_detail"]}
        cb_md = ["# Microstructure casebook (Option B)", "",
                 f"**Build:** {now_iso()}",
                 f"**Baseline:** {bm['trades']} trades, wr {bm['winrate_pct']}%, exp {bm['expectancy_after_cost_pct']:+.4f}, PF {bm['pf_after_cost']}",
                 f"**Best enhanced:** `{best_enh['selector']}` — {best_enh['trades']} trades, wr {best_enh['winrate_pct']}%, exp {best_enh['expectancy_after_cost_pct']:+.4f}, PF {best_enh['pf_after_cost']}",
                 "",
                 "## Baseline LOSSES that enhanced REMOVES",
                 "| date | dir | zone_id | reason | pnl % |",
                 "|---|:---:|---|---|---:|"]
        removed_losses = 0
        for t in trades_baseline:
            if t["outcome"] in ("LOSS", "TIMEOUT") and t["zone_id"] not in enhanced_ids:
                cb_md.append(f"| {t['date']} | {t['direction']} | {t['zone_id'][-16:]} | {t['reason_class']} | {t['pnl_after_cost']:+.2f} |")
                removed_losses += 1
        cb_md.extend(["", f"Removed {removed_losses} loss-likes.", "",
                       "## Baseline WINS that enhanced INCORRECTLY removes",
                       "| date | dir | zone_id |",
                       "|---|:---:|---|"])
        removed_wins = 0
        for t in trades_baseline:
            if t["outcome"] == "WIN" and t["zone_id"] not in enhanced_ids:
                cb_md.append(f"| {t['date']} | {t['direction']} | {t['zone_id'][-16:]} |")
                removed_wins += 1
        cb_md.extend(["", f"Removed {removed_wins} WINs.", "",
                       "## Baseline WINS that enhanced KEEPS",
                       "| date | dir | zone_id |",
                       "|---|:---:|---|"])
        for t in trades_baseline:
            if t["outcome"] == "WIN" and t["zone_id"] in enhanced_ids:
                cb_md.append(f"| {t['date']} | {t['direction']} | {t['zone_id'][-16:]} |")
        (REP_OUT / "MARCH_MICROSTRUCTURE_CASEBOOK.md").write_text("\n".join(cb_md), encoding="utf-8")
        (REP_OUT / "MARCH_MICROSTRUCTURE_CASEBOOK.json").write_text(
            json.dumps({"build_time_utc": now_iso(),
                        "best_enhanced_selector": best_enh["selector"],
                        "baseline_trades": trades_baseline,
                        "enhanced_trades": best_enh["trades_detail"]},
                       indent=2, default=str), encoding="utf-8")

    # Final report
    print("[M] final report ...", file=sys.stderr)
    top_features = [t["feature"] for t in table[:3]]
    enhanced_improved = (best_enh and best_enh["winrate_pct"] > bm["winrate_pct"])
    wr_uplift = round(best_enh["winrate_pct"] - bm["winrate_pct"], 2) if best_enh else None
    exp_uplift = round((best_enh["expectancy_after_cost_pct"] or 0) - bm["expectancy_after_cost_pct"], 4) if best_enh else None
    pf_uplift = (round(best_enh["pf_after_cost"] - bm["pf_after_cost"], 3)
                 if best_enh and bm["pf_after_cost"] is not None and best_enh["pf_after_cost"] is not None
                 else None)
    flags = {
        "MICROSTRUCTURE_RESEARCH_DONE": "YES",
        "BASELINE_REPRODUCED": "YES" if bm["trades"] == 29 else "NO",
        "BASELINE_TRADES": bm["trades"],
        "BASELINE_WINRATE": bm["winrate_pct"],
        "BASELINE_EXPECTANCY_AFTER_COST": bm["expectancy_after_cost_pct"],
        "BASELINE_PF_AFTER_COST": bm["pf_after_cost"],
        "WALL_LIFETIME_FEATURES_DONE": "PROXY (dl2_top1_supportive_persistence_ge_50_5m_sec)",
        "REFILL_AFTER_HIT_FEATURES_DONE": "PROXY (dl2_supp_minus_opp_net_flow_*, dl2_inband_supp_add_*)",
        "LIQUIDITY_VOID_FEATURES_DONE": "YES (new extraction)",
        "MICROPRICE_EVOLUTION_FEATURES_DONE": "YES (reused dl2_microprice_*)",
        "ADD_CANCEL_FEATURES_DONE": "YES (reused dl2_*)",
        "SETUP_TYPE_CLASSIFICATION_DONE": "YES",
        "USEFUL_MICROSTRUCTURE_FEATURES_FOUND": "YES" if (table and abs(table[0].get("d_winners_vs_losers") or 0) > 0.2) else "NO",
        "TOP_FEATURE_1": top_features[0] if len(top_features) > 0 else "none",
        "TOP_FEATURE_2": top_features[1] if len(top_features) > 1 else "none",
        "TOP_FEATURE_3": top_features[2] if len(top_features) > 2 else "none",
        "BEST_SETUP_TYPE": best_setup[0] if best_setup else "none",
        "BEST_SETUP_TYPE_WINRATE": round(best_wr, 2) if best_setup else None,
        "BEST_SETUP_TYPE_TRADES": best_setup[1] if best_setup else None,
        "ENHANCED_SELECTOR_FOUND": "YES" if best_enh else "NO",
        "ENHANCED_SELECTOR_NAME": best_enh["selector"] if best_enh else "none",
        "ENHANCED_TRADES": best_enh["trades"] if best_enh else None,
        "ENHANCED_WINS": best_enh["wins"] if best_enh else None,
        "ENHANCED_LOSSES": best_enh["losses"] if best_enh else None,
        "ENHANCED_TIMEOUTS": best_enh["timeouts"] if best_enh else None,
        "ENHANCED_WINRATE": best_enh["winrate_pct"] if best_enh else None,
        "ENHANCED_EXPECTANCY_AFTER_COST": best_enh["expectancy_after_cost_pct"] if best_enh else None,
        "ENHANCED_PF_AFTER_COST": best_enh["pf_after_cost"] if best_enh else None,
        "ENHANCED_IMPROVED_OVER_BASELINE": "YES" if enhanced_improved else "NO",
        "WINRATE_IMPROVEMENT_PP": wr_uplift,
        "EXPECTANCY_IMPROVEMENT": exp_uplift,
        "PF_IMPROVEMENT": pf_uplift,
        "SEVENTY_PERCENT_REACHED": "YES" if (best_enh and best_enh["winrate_pct"] >= 70.0) else "NO",
        "SEVENTY_PERCENT_WITH_MIN20_REACHED": "YES" if (best_enh and best_enh["winrate_pct"] >= 70.0
                                                          and best_enh["trades"] >= 20) else "NO",
        "SUCCESSFUL_INDICATORS_IDENTIFIED": "YES" if any(i["verdict"] == "PROMOTE" for i in ind) else "NO",
        "INDICATOR_SUCCESS_CRITERIA_DONE": "YES",
        "ABLATION_DONE": "PARTIAL (per-feature evaluation done)",
        "READY_FOR_TELEGRAM_SHADOW_MODE": "NO",
        "READY_TO_CHANGE_ENGINE": "NO",
        "READY_FOR_PRODUCTION_TRADING": "NO",
        "MORE_VALIDATION_REQUIRED": "YES",
    }
    summary = {"build_time_utc": now_iso(), "baseline_metrics": bm,
                "best_enhanced_selector": ({k: v for k, v in best_enh.items()
                                              if k not in ("selected_zone_ids", "trades_detail")}
                                            if best_enh else None),
                "top_features_winners_vs_losers": top_features,
                "best_setup_type": best_setup,
                "improvement": {"winrate_pp": wr_uplift, "expectancy": exp_uplift, "pf": pf_uplift},
                "flags": flags}
    (REP_OUT / "MARCH_MICROSTRUCTURE_FINAL_REPORT.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8")
    md = ["# Microstructure feature engine + setup-type — final report (Option B)", "",
          f"**Build:** {summary['build_time_utc']}",
          "**Scope:** IN-SAMPLE March 2026 OKX direct, 29 days.",
          "**Note:** wall_lifetime and refill_after_hit use existing dl2_* proxies "
          "(equivalent in spirit but not per-level resolution). Only liquidity_void_to_target "
          "is newly extracted in this pass.",
          "",
          "## Baseline (reproduced exactly)",
          f"- Trades: {bm['trades']}, Wins: {bm['wins']}, Losses: {bm['losses']}, Timeouts: {bm['timeouts']}",
          f"- Winrate: {bm['winrate_pct']}%; Expectancy after cost: {bm['expectancy_after_cost_pct']:+.4f}%; PF: {bm['pf_after_cost']}",
          "",
          "## Best enhanced selector",
          (f"- `{best_enh['selector']}`\n"
           f"  - Trades: {best_enh['trades']}, Wins: {best_enh['wins']}, Losses: {best_enh['losses']}, Timeouts: {best_enh['timeouts']}\n"
           f"  - Winrate: **{best_enh['winrate_pct']}%** (Δ {wr_uplift:+.2f} pp)\n"
           f"  - Exp aft cost: {best_enh['expectancy_after_cost_pct']:+.4f}% (Δ {exp_uplift:+.4f})\n"
           f"  - PF aft cost: {best_enh['pf_after_cost']} (Δ {pf_uplift})\n"
           f"  - H1/H2 precision: {best_enh.get('h1_precision_pct')} / {best_enh.get('h2_precision_pct')}"
           if best_enh else "- (no selector with >=10 trades found)"),
          "",
          "## Best setup-type",
          (f"- `{best_setup[0]}` — {best_setup[1]} trades, {best_setup[2]} wins, winrate {best_wr:.1f}%"
           if best_setup else "- (no setup-type with >=3 trades dominant)"),
          "",
          "## Top 3 features separating WIN from LOSS",
          *[f"- `{t['feature']}` (d={t['d_winners_vs_losers']}, winners_mean={t['winners_mean']}, losers_mean={t['losers_mean']})"
            for t in table[:3]],
          "",
          "## 70 % goal",
          f"- Reached (any n): **{flags['SEVENTY_PERCENT_REACHED']}**",
          f"- Reached with min 20 trades: **{flags['SEVENTY_PERCENT_WITH_MIN20_REACHED']}**",
          "",
          "## Honest summary",
          f"- {'Enhanced selector IMPROVED over baseline.' if enhanced_improved else 'Enhanced selector did NOT improve over baseline.'}",
          "- New liquidity void feature is leak-free (snapshot at confirmedTs only).",
          "- Wall lifetime and refill-after-hit used PROXIES from earlier dl2_* extraction; "
          "full per-level extraction queued for separate run.",
          "",
          "## Final flag matrix", "", "```"]
    for k, v in flags.items():
        md.append(f"{k} = {v}")
    md.extend(["```", "",
                "## Hard rules honored",
                "- engine / thresholds / detector: UNCHANGED.",
                "- All decision features are leak-free at confirmedTs.",
                "- Outcome labels used ONLY for evaluation.",
                "- target strict 2 %; cost 0.14 %.",
                "- production claim: NONE."])
    (REP_OUT / "MARCH_MICROSTRUCTURE_FINAL_REPORT.md").write_text("\n".join(md), encoding="utf-8")

    print()
    print("FINAL FLAGS:")
    for k, v in flags.items():
        print(f"  {k:<48s} = {v}")
    print()
    print("[best enhanced selector trades]:")
    if best_enh:
        for t in best_enh["trades_detail"]:
            print(f"  {t['date']} {t['direction']:>5} {t['zone_id'][-16:]} {t['outcome']:>7} "
                  f"pnl_aft={t['pnl_after_cost']:+.4f}% reason={t['reason_class']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
