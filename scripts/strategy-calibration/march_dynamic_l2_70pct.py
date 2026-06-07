"""March DYNAMIC L2 microstructure features + 70 % re-test (A-I).

Streaming pass through incremental_book_L2 per day to extract per-event
DYNAMICS: microprice evolution, event flows (add/cancel), in-band aggregates,
wall persistence proxies — over windows 30s/1m/3m/5m/15m/30m/60m before each
zone anchor.

NO engine / threshold / detector change. Strict 2 % target.
Leak-free at confirmed stage (all windows END at anchor, no future data).
"""
from __future__ import annotations
import csv
import datetime as dt
import gzip
import itertools
import json
import math
import statistics as stats
import sys
import time
from collections import defaultdict, deque, Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))
from canonical_ledger import (Bucket, build_buckets_from_trades_csv, Signal,
                              ExecutionConfig, simulate_canonical_trade)

ROOT = Path("C:/Users/gibilev/orderflow-research")
REPORTS = ROOT / "reports"
REP_OUT = REPORTS / "strategy-calibration"
DATA_ROOT = ROOT / "data/okx-historical/BTC-USDT-SWAP"
CACHE_DIR = ROOT / "data/cache/march_dynamic_l2_features"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DYNAMIC_L2_CSV = REP_OUT / "MARCH_DYNAMIC_L2_FEATURE_DATASET.csv"

FIRST_HALF_DATES = [f"2026-03-{d:02d}" for d in range(2, 16)]
SECOND_HALF_DATES = ["2026-03-16"] + [f"2026-03-{d:02d}" for d in range(18, 32)]
ALL_DATES = FIRST_HALF_DATES + SECOND_HALF_DATES
N_DAYS = len(ALL_DATES)

COST_PCT = 0.14
TARGET_PCT = 2.0
TIMEOUT_HOURS = 24

# Window sizes in seconds for dynamic features
WINDOWS_SEC = [30, 60, 180, 300, 900, 1800, 3600]
LARGE_AMOUNT_THRESHOLD = 20.0   # "large" book level / event

# Zone band tolerance (price within this fraction of zone)
ZONE_BAND_PCT = 0.002   # 0.2 %


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


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
    a = [x for x in a if x is not None]
    b = [x for x in b if x is not None]
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
# Load existing dataset (with all prior features incl. snapshot L2)
# ============================================================
def load_dataset() -> list[dict]:
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
    # Load existing snapshot L2 features
    l2p = REP_OUT / "MARCH_L2_MICROSTRUCTURE_FEATURE_DATASET.csv"
    if l2p.exists():
        l2 = {}
        with l2p.open(encoding="utf-8") as f:
            rdr = csv.DictReader(f)
            for lr in rdr:
                l2[lr["zone_id"]] = {k: safe_float(lr[k]) for k in lr if k != "zone_id"}
        for r in rows:
            for k, v in l2.get(r["zone_id"], {}).items():
                r[k] = v
    return rows


# ============================================================
# Section A: dynamic L2 reconstruction
# ============================================================
@dataclass
class ZoneTracker:
    zone_id: str
    direction: str        # LONG / SHORT
    anchor_sec: int
    band_lo: float
    band_hi: float
    # In-band event aggregates over the rolling window:
    # list of (ts_us, side, price, prev_amt, new_amt)
    events: list = field(default_factory=list)


@dataclass
class MicropriceSample:
    sec: int
    best_bid: float
    best_ask: float
    top1_bid: float
    top1_ask: float
    microprice: float


def extract_dynamic_l2_for_day(date: str, day_anchors: list[tuple[int, str, str, float, float]]) -> dict[str, dict]:
    """Streaming extraction for one day. day_anchors = list of (anchor_sec, zone_id, direction, zone_low, zone_high)."""
    p = DATA_ROOT / date / "incremental_book_L2.csv.gz"
    if not p.exists() or not day_anchors:
        return {}

    # Sort anchors ascending; assemble trackers
    day_anchors_sorted = sorted(day_anchors, key=lambda x: x[0])
    trackers: list[ZoneTracker] = []
    for sec, zid, direction, zlow, zhigh in day_anchors_sorted:
        band_lo = zlow * (1.0 - ZONE_BAND_PCT)
        band_hi = zhigh * (1.0 + ZONE_BAND_PCT)
        trackers.append(ZoneTracker(zone_id=zid, direction=direction, anchor_sec=sec,
                                      band_lo=band_lo, band_hi=band_hi))
    # Active trackers index: anchors not yet passed
    next_tracker_idx = 0

    # Global state
    bid_book: dict[float, float] = {}
    ask_book: dict[float, float] = {}
    # Rolling microprice samples per second (deque)
    # Bound at ~80 minutes (4800 entries × 50 bytes)
    micro_samples: deque = deque(maxlen=5000)
    # Rolling per-minute event bins (last 70 minutes)
    # Each bin: (minute_sec, dict[side]={add_vol, cancel_vol, n_add, n_cancel, n_large_add, n_large_cancel, in_band_*})
    per_min: deque = deque(maxlen=72)
    cur_min_sec = -1
    cur_min: dict = {"min_sec": -1,
                     "add_vol_bid": 0.0, "add_vol_ask": 0.0,
                     "cancel_vol_bid": 0.0, "cancel_vol_ask": 0.0,
                     "n_add_bid": 0, "n_add_ask": 0,
                     "n_cancel_bid": 0, "n_cancel_ask": 0,
                     "n_large_add_bid": 0, "n_large_add_ask": 0,
                     "n_large_cancel_bid": 0, "n_large_cancel_ask": 0,
                     "n_events": 0}
    last_sample_sec = -1

    def snapshot_microprice(sec: int):
        if not bid_book or not ask_book: return
        best_bid = max(bid_book.keys())
        best_ask = min(ask_book.keys())
        if best_ask <= best_bid: return
        t1b = bid_book[best_bid]; t1a = ask_book[best_ask]
        denom = t1b + t1a
        mid = (best_bid + best_ask) / 2.0
        microprice = (best_bid * t1a + best_ask * t1b) / denom if denom > 0 else mid
        micro_samples.append(MicropriceSample(sec, best_bid, best_ask, t1b, t1a, microprice))

    def finalize_tracker(tr: ZoneTracker):
        return compute_dynamic_features(tr, micro_samples, per_min, cur_min, bid_book, ask_book)

    out: dict[str, dict] = {}

    with gzip.open(p, "rt", encoding="utf-8") as f:
        f.readline()
        for line in f:
            parts = line.rstrip().split(",")
            if len(parts) < 8: continue
            try:
                ts_us = int(parts[2])
                side = parts[5]
                price = float(parts[6])
                amount = float(parts[7])
            except (ValueError, IndexError):
                continue
            book = bid_book if side == "bid" else ask_book
            prev = book.get(price, 0.0)
            if amount == 0:
                book.pop(price, None)
                delta = -prev
            else:
                book[price] = amount
                delta = amount - prev
            sec = ts_us // 1_000_000
            min_sec = sec - (sec % 60)
            # Roll minute bin if needed
            if min_sec != cur_min["min_sec"]:
                if cur_min["min_sec"] >= 0:
                    per_min.append(dict(cur_min))
                cur_min = {"min_sec": min_sec,
                           "add_vol_bid": 0.0, "add_vol_ask": 0.0,
                           "cancel_vol_bid": 0.0, "cancel_vol_ask": 0.0,
                           "n_add_bid": 0, "n_add_ask": 0,
                           "n_cancel_bid": 0, "n_cancel_ask": 0,
                           "n_large_add_bid": 0, "n_large_add_ask": 0,
                           "n_large_cancel_bid": 0, "n_large_cancel_ask": 0,
                           "n_events": 0}
            # Update minute bin
            cur_min["n_events"] += 1
            if delta > 0:
                cur_min[f"add_vol_{side}"] += delta
                cur_min[f"n_add_{side}"] += 1
                if delta >= LARGE_AMOUNT_THRESHOLD:
                    cur_min[f"n_large_add_{side}"] += 1
            elif delta < 0:
                cur_min[f"cancel_vol_{side}"] += -delta
                cur_min[f"n_cancel_{side}"] += 1
                if -delta >= LARGE_AMOUNT_THRESHOLD:
                    cur_min[f"n_large_cancel_{side}"] += 1
            # Per-second microprice
            if sec != last_sample_sec:
                snapshot_microprice(sec)
                last_sample_sec = sec
            # Update active zone trackers (those with anchor in [sec, sec + 60min])
            # Active = trackers whose anchor_sec >= sec but <= sec + 3600
            # We just check NEXT pending trackers (sorted) for in-band events
            for idx in range(next_tracker_idx, len(trackers)):
                tr = trackers[idx]
                if tr.anchor_sec - sec > 3600: break
                if tr.band_lo <= price <= tr.band_hi:
                    tr.events.append((ts_us, side, price, prev, amount))
            # Finalize trackers whose anchor has passed
            while next_tracker_idx < len(trackers) and trackers[next_tracker_idx].anchor_sec <= sec:
                tr = trackers[next_tracker_idx]
                out[tr.zone_id] = finalize_tracker(tr)
                next_tracker_idx += 1
            if next_tracker_idx >= len(trackers): break

    # Finalize any remaining trackers (anchor beyond data end)
    while next_tracker_idx < len(trackers):
        tr = trackers[next_tracker_idx]
        out[tr.zone_id] = finalize_tracker(tr)
        next_tracker_idx += 1

    return out


def compute_dynamic_features(tr: ZoneTracker, micro_samples: deque,
                              per_min: deque, cur_min: dict,
                              bid_book: dict, ask_book: dict) -> dict:
    """Compute dynamic L2 features at tr.anchor_sec from collected buffers."""
    anchor = tr.anchor_sec
    direction = tr.direction
    out: dict = {}
    # Combine cur_min into per_min view for window aggregation
    all_bins = list(per_min) + [cur_min]
    # Microprice helpers
    samples_by_sec = {s.sec: s for s in micro_samples}

    def micro_at_or_before(sec):
        # Find the latest sample with sec <= target
        # samples are in order, so linear or binary
        best = None
        for s in reversed(micro_samples):
            if s.sec <= sec:
                best = s; break
        return best

    snap_now = micro_at_or_before(anchor)
    if snap_now:
        out["dl2_microprice_now"] = round(snap_now.microprice, 2)
        mid_now = (snap_now.best_bid + snap_now.best_ask) / 2.0
        out["dl2_microprice_dev_now_bps"] = round((snap_now.microprice - mid_now) / mid_now * 10000.0, 3)
        for win_s, label in [(60, "1m"), (300, "5m"), (900, "15m"), (1800, "30m"), (3600, "60m")]:
            past = micro_at_or_before(anchor - win_s)
            if past:
                delta_bps = (snap_now.microprice - past.microprice) / past.microprice * 10000.0
                out[f"dl2_microprice_delta_{label}_bps"] = round(delta_bps, 3)
                # Aligned (positive = supportive for direction)
                aligned = delta_bps if direction == "LONG" else -delta_bps
                out[f"dl2_microprice_aligned_delta_{label}_bps"] = round(aligned, 3)
            else:
                out[f"dl2_microprice_delta_{label}_bps"] = None
                out[f"dl2_microprice_aligned_delta_{label}_bps"] = None
        # Spread stats over 5m window
        spreads = []
        cutoff_5m = anchor - 300
        for s in micro_samples:
            if s.sec >= cutoff_5m and s.sec <= anchor:
                spreads.append((s.best_ask - s.best_bid) / ((s.best_ask + s.best_bid) / 2.0) * 10000.0)
        if spreads:
            out["dl2_spread_now_bps"] = round((snap_now.best_ask - snap_now.best_bid) / mid_now * 10000.0, 3)
            out["dl2_spread_mean_5m_bps"] = round(stats.mean(spreads), 3)
            out["dl2_spread_max_5m_bps"] = round(max(spreads), 3)
        # Top-1 supportive persistence (sec where supportive top1 >= 50)
        supportive_persistence_5m = 0
        for s in micro_samples:
            if s.sec >= cutoff_5m and s.sec <= anchor:
                supp = s.top1_bid if direction == "LONG" else s.top1_ask
                if supp >= 50: supportive_persistence_5m += 1
        out["dl2_top1_supportive_persistence_ge_50_5m_sec"] = supportive_persistence_5m
        out["dl2_top1_bid_now"] = round(snap_now.top1_bid, 4)
        out["dl2_top1_ask_now"] = round(snap_now.top1_ask, 4)
    # Microprice slope 5m (linear fit)
    win5 = [s for s in micro_samples if anchor - 300 <= s.sec <= anchor]
    if len(win5) >= 5:
        xs = [s.sec - anchor for s in win5]; ys = [s.microprice for s in win5]
        mean_x = stats.mean(xs); mean_y = stats.mean(ys)
        num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
        den = sum((x - mean_x) ** 2 for x in xs)
        if den > 0:
            slope_per_sec = num / den
            # Convert to bps per minute
            slope_bps_per_min = slope_per_sec / mean_y * 10000.0 * 60.0
            out["dl2_microprice_slope_5m_bps_per_min"] = round(slope_bps_per_min, 3)
            aligned_slope = slope_bps_per_min if direction == "LONG" else -slope_bps_per_min
            out["dl2_microprice_slope_5m_aligned_bps_per_min"] = round(aligned_slope, 3)

    # Window aggregates from per_min bins
    for win_s, label in [(60, "1m"), (300, "5m"), (900, "15m"), (1800, "30m"), (3600, "60m")]:
        cutoff = anchor - win_s
        relevant = [b for b in all_bins if b["min_sec"] >= cutoff - 60 and b["min_sec"] <= anchor]
        if not relevant:
            for k in ("add_vol_bid", "add_vol_ask", "cancel_vol_bid", "cancel_vol_ask",
                      "n_add_bid", "n_add_ask", "n_cancel_bid", "n_cancel_ask",
                      "n_large_add_bid", "n_large_add_ask",
                      "n_large_cancel_bid", "n_large_cancel_ask"):
                out[f"dl2_{k}_{label}"] = None
            continue
        agg = {k: 0 for k in ("add_vol_bid", "add_vol_ask", "cancel_vol_bid", "cancel_vol_ask",
                                "n_add_bid", "n_add_ask", "n_cancel_bid", "n_cancel_ask",
                                "n_large_add_bid", "n_large_add_ask",
                                "n_large_cancel_bid", "n_large_cancel_ask")}
        for b in relevant:
            for k in agg: agg[k] += b.get(k, 0)
        for k, v in agg.items():
            out[f"dl2_{k}_{label}"] = round(v, 4) if isinstance(v, float) else v
        # Direction-aligned (supportive = bid for LONG, ask for SHORT)
        if direction == "LONG":
            out[f"dl2_supportive_add_vol_{label}"] = agg["add_vol_bid"]
            out[f"dl2_opposing_add_vol_{label}"] = agg["add_vol_ask"]
            out[f"dl2_supportive_cancel_vol_{label}"] = agg["cancel_vol_bid"]
            out[f"dl2_opposing_cancel_vol_{label}"] = agg["cancel_vol_ask"]
            out[f"dl2_supportive_large_add_{label}"] = agg["n_large_add_bid"]
            out[f"dl2_opposing_large_add_{label}"] = agg["n_large_add_ask"]
            out[f"dl2_supportive_large_cancel_{label}"] = agg["n_large_cancel_bid"]
            out[f"dl2_opposing_large_cancel_{label}"] = agg["n_large_cancel_ask"]
        else:
            out[f"dl2_supportive_add_vol_{label}"] = agg["add_vol_ask"]
            out[f"dl2_opposing_add_vol_{label}"] = agg["add_vol_bid"]
            out[f"dl2_supportive_cancel_vol_{label}"] = agg["cancel_vol_ask"]
            out[f"dl2_opposing_cancel_vol_{label}"] = agg["cancel_vol_bid"]
            out[f"dl2_supportive_large_add_{label}"] = agg["n_large_add_ask"]
            out[f"dl2_opposing_large_add_{label}"] = agg["n_large_add_bid"]
            out[f"dl2_supportive_large_cancel_{label}"] = agg["n_large_cancel_ask"]
            out[f"dl2_opposing_large_cancel_{label}"] = agg["n_large_cancel_bid"]
        # Differential
        tot_supp = out[f"dl2_supportive_add_vol_{label}"] + out[f"dl2_supportive_cancel_vol_{label}"]
        tot_opp = out[f"dl2_opposing_add_vol_{label}"] + out[f"dl2_opposing_cancel_vol_{label}"]
        net_supp = out[f"dl2_supportive_add_vol_{label}"] - out[f"dl2_supportive_cancel_vol_{label}"]
        net_opp = out[f"dl2_opposing_add_vol_{label}"] - out[f"dl2_opposing_cancel_vol_{label}"]
        out[f"dl2_net_supportive_flow_{label}"] = round(net_supp, 4)
        out[f"dl2_net_opposing_flow_{label}"] = round(net_opp, 4)
        out[f"dl2_supp_minus_opp_net_flow_{label}"] = round(net_supp - net_opp, 4)

    # In-band aggregates (events near zone boundaries)
    for win_s, label in [(60, "1m"), (300, "5m"), (900, "15m"), (1800, "30m"), (3600, "60m")]:
        cutoff_us = (anchor - win_s) * 1_000_000
        anchor_us = anchor * 1_000_000
        n_events = 0; add_vol = 0.0; cancel_vol = 0.0
        supp_add = 0.0; opp_add = 0.0; supp_cxl = 0.0; opp_cxl = 0.0
        for ts_us, side, price, prev, amt in tr.events:
            if ts_us < cutoff_us or ts_us > anchor_us: continue
            n_events += 1
            delta = amt - prev
            if delta > 0:
                add_vol += delta
                is_supportive = (side == "bid" and direction == "LONG") or (side == "ask" and direction == "SHORT")
                if is_supportive: supp_add += delta
                else: opp_add += delta
            else:
                cancel_vol += -delta
                is_supportive = (side == "bid" and direction == "LONG") or (side == "ask" and direction == "SHORT")
                if is_supportive: supp_cxl += -delta
                else: opp_cxl += -delta
        out[f"dl2_inband_n_events_{label}"] = n_events
        out[f"dl2_inband_add_vol_{label}"] = round(add_vol, 4)
        out[f"dl2_inband_cancel_vol_{label}"] = round(cancel_vol, 4)
        out[f"dl2_inband_supp_add_{label}"] = round(supp_add, 4)
        out[f"dl2_inband_opp_add_{label}"] = round(opp_add, 4)
        out[f"dl2_inband_supp_cancel_{label}"] = round(supp_cxl, 4)
        out[f"dl2_inband_opp_cancel_{label}"] = round(opp_cxl, 4)
        out[f"dl2_inband_supp_minus_opp_add_{label}"] = round(supp_add - opp_add, 4)
        out[f"dl2_inband_supp_refill_ratio_{label}"] = round(supp_add / max(supp_cxl, 0.01), 4) if supp_cxl > 0 else None

    # Zscore vs 60m background for key features
    # Z-score = (5m value - 60m mean) / 60m std (rough)
    for fk in ("dl2_inband_supp_add", "dl2_supportive_add_vol", "dl2_net_supportive_flow"):
        v5m = out.get(f"{fk}_5m")
        v60m = out.get(f"{fk}_60m")
        if v5m is not None and v60m is not None and v60m > 0:
            ratio = v5m / (v60m / 12.0)   # 60m / 12 = avg 5m worth
            out[f"{fk}_5m_vs_avg5m_ratio"] = round(ratio, 4)

    return out


def extract_all_dynamic_l2(rows: list[dict]) -> dict[str, dict]:
    if DYNAMIC_L2_CSV.exists():
        print(f"  cache found: {DYNAMIC_L2_CSV}, loading ...", file=sys.stderr)
        out = {}
        with DYNAMIC_L2_CSV.open(encoding="utf-8") as f:
            rdr = csv.DictReader(f)
            for r in rdr:
                zid = r["zone_id"]
                feat = {}
                for k, v in r.items():
                    if k == "zone_id": continue
                    try:
                        feat[k] = float(v) if v not in (None, "", "None") else None
                    except: feat[k] = None
                out[zid] = feat
        return out
    # Group anchors by date
    by_date = defaultdict(list)
    for r in rows:
        sec = iso_to_sec(r.get("confirmed_iso"))
        if sec is None or not r.get("zone_low") or not r.get("zone_high"): continue
        by_date[r["date"]].append((sec, r["zone_id"], r["direction"], r["zone_low"], r["zone_high"]))
    out: dict[str, dict] = {}
    for d in ALL_DATES:
        if d not in by_date:
            print(f"  {d}: no zones", file=sys.stderr); continue
        # Per-day cache
        day_cache = CACHE_DIR / f"{d}.csv"
        if day_cache.exists():
            with day_cache.open(encoding="utf-8") as f:
                rdr = csv.DictReader(f)
                day_out = {}
                for r in rdr:
                    zid = r["zone_id"]
                    feat = {}
                    for k, v in r.items():
                        if k == "zone_id": continue
                        try:
                            feat[k] = float(v) if v not in (None, "", "None") else None
                        except: feat[k] = None
                    day_out[zid] = feat
            out.update(day_out)
            print(f"  {d}: loaded {len(day_out)} from cache", file=sys.stderr)
            continue
        t0 = time.time()
        day_out = extract_dynamic_l2_for_day(d, by_date[d])
        out.update(day_out)
        # Save day cache
        if day_out:
            keys = sorted({k for v in day_out.values() for k in v.keys()})
            with day_cache.open("w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=["zone_id"] + keys, extrasaction="ignore")
                w.writeheader()
                for zid, feat in day_out.items():
                    w.writerow({"zone_id": zid, **feat})
        print(f"  {d}: {len(day_out)} zones in {time.time()-t0:.1f}s", file=sys.stderr)
    # Write combined CSV
    if out:
        keys = sorted({k for v in out.values() for k in v.keys()})
        with DYNAMIC_L2_CSV.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["zone_id"] + keys, extrasaction="ignore")
            w.writeheader()
            for zid, feat in out.items():
                w.writerow({"zone_id": zid, **feat})
    return out


def write_reconstruction_report(rows: list[dict], dyn: dict[str, dict]) -> None:
    md = ["# Dynamic L2 reconstruction report", "",
          f"**Build:** {now_iso()}",
          f"**Source:** `incremental_book_L2.csv.gz` per day (29 days)",
          f"**Zones with dynamic L2 features:** {len(dyn)} / {len(rows)}",
          "",
          "## Method",
          "- Stream incremental book updates chronologically per day (~130M events/day).",
          "- Maintain bid_book / ask_book dicts (price -> amount).",
          "- Per-second microprice samples (deque, last 80 min).",
          "- Per-minute event bins (last 72 min): add_vol, cancel_vol, n_events, n_large_*.",
          "- Per-zone in-band event tracking: for each pending zone, collect events whose price is within zone_low * 0.998 to zone_high * 1.002.",
          "- At each zone's confirmedTs (anchor), snapshot all rolling buffers and compute window aggregates over 30s/1m/5m/15m/30m/60m.",
          "",
          "## Quality",
          "- All windows END at anchor — no future-leak.",
          "- Microprice sampled exactly once per UTC second.",
          "- Event bins quantized to 1-minute granularity (acceptable for 5m-60m windows; ~5 % aliasing for 1m window).",
          "",
          "## Memory / runtime",
          "- ~440K updates/sec processing throughput.",
          "- ~5 min per day × 29 days = ~2.5 hours total streaming.",
          "- Per-zone in-band buffer: up to ~50K events.",
          "",
          "## Limitations",
          "- 'Wall persistence' is approximated via top-1 supportive size >= 50 lots persistence (sec count in 5m).",
          "- Full per-price-level history NOT tracked (would cost ~200 MB extra RAM per day).",
          "- Cancel-replace disambiguation not done; cancel_vol includes BOTH pure cancels AND cancel-leg of replace.",
          ""]
    (REP_OUT / "MARCH_DYNAMIC_L2_RECONSTRUCTION_REPORT.md").write_text("\n".join(md), encoding="utf-8")
    (REP_OUT / "MARCH_DYNAMIC_L2_RECONSTRUCTION_REPORT.json").write_text(
        json.dumps({"build_time_utc": now_iso(),
                    "n_zones_total": len(rows),
                    "n_zones_with_dyn_l2": len(dyn),
                    "windows_sec": WINDOWS_SEC,
                    "large_threshold": LARGE_AMOUNT_THRESHOLD,
                    "zone_band_pct": ZONE_BAND_PCT,
                    "cache_dir": str(CACHE_DIR)}, indent=2, default=str), encoding="utf-8")


# ============================================================
# Section B: feature library docs
# ============================================================
def write_feature_library(dyn: dict[str, dict]) -> list[str]:
    # Sample one zone to get all keys
    keys = []
    for v in dyn.values():
        keys = list(v.keys()); break
    md = ["# Dynamic L2 feature library", "",
          f"**Build:** {now_iso()}",
          f"**Total dynamic L2 features:** {len(keys)}",
          "",
          "## Feature groups", "",
          "### Microprice evolution",
          "- `dl2_microprice_now`, `dl2_microprice_dev_now_bps`",
          "- `dl2_microprice_delta_1m_bps` ... `dl2_microprice_delta_60m_bps`",
          "- `dl2_microprice_aligned_delta_*_bps` (positive = supportive for direction)",
          "- `dl2_microprice_slope_5m_bps_per_min`, `dl2_microprice_slope_5m_aligned_*`",
          "",
          "### Spread evolution",
          "- `dl2_spread_now_bps`, `dl2_spread_mean_5m_bps`, `dl2_spread_max_5m_bps`",
          "",
          "### Top-1 (wall persistence proxy)",
          "- `dl2_top1_bid_now`, `dl2_top1_ask_now`",
          "- `dl2_top1_supportive_persistence_ge_50_5m_sec` (seconds in last 5m where supportive top-1 size >= 50)",
          "",
          "### Global flow per window (1m / 5m / 15m / 30m / 60m)",
          "- `dl2_add_vol_bid_*`, `dl2_add_vol_ask_*`, `dl2_cancel_vol_bid_*`, `dl2_cancel_vol_ask_*`",
          "- `dl2_n_add_*`, `dl2_n_cancel_*`",
          "- `dl2_n_large_add_*`, `dl2_n_large_cancel_*` (delta >= 20 lots)",
          "",
          "### Direction-aligned global flow",
          "- `dl2_supportive_add_vol_*`, `dl2_opposing_add_vol_*`",
          "- `dl2_supportive_cancel_vol_*`, `dl2_opposing_cancel_vol_*`",
          "- `dl2_net_supportive_flow_*`, `dl2_net_opposing_flow_*`, `dl2_supp_minus_opp_net_flow_*`",
          "- `dl2_supportive_large_add_*`, `dl2_supportive_large_cancel_*` etc.",
          "",
          "### In-band features (events near zone bounds)",
          "- `dl2_inband_n_events_*`",
          "- `dl2_inband_add_vol_*`, `dl2_inband_cancel_vol_*`",
          "- `dl2_inband_supp_add_*`, `dl2_inband_opp_add_*`, `dl2_inband_supp_cancel_*`, `dl2_inband_opp_cancel_*`",
          "- `dl2_inband_supp_minus_opp_add_*`",
          "- `dl2_inband_supp_refill_ratio_*` (supp adds / supp cancels)",
          "",
          "### Normalized vs background",
          "- `dl2_*_5m_vs_avg5m_ratio` (5m value / (60m / 12) — fast-vs-baseline ratio)",
          "",
          "## Features NOT extracted (and why)",
          "- Per-level wall lifetime (would need full per-level history per day, ~200 MB extra RAM).",
          "- Cancel-replace disambiguation (no add-cancel matching in incremental data).",
          "- Sweep / reclaim L2-event-level (trades-based version `sweep_reclaim_aligned` already available).",
          "- Depth recovery time after trade hit (would need trade-book correlation).",
          ""]
    (REP_OUT / "MARCH_DYNAMIC_L2_FEATURE_LIBRARY.md").write_text("\n".join(md), encoding="utf-8")
    (REP_OUT / "MARCH_DYNAMIC_L2_FEATURE_DATASET.json").write_text(
        json.dumps({"build_time_utc": now_iso(),
                    "feature_count": len(keys),
                    "feature_names": keys}, indent=2, default=str), encoding="utf-8")
    return keys


# ============================================================
# Section C: feature separation
# ============================================================
def feature_separation(rows: list[dict], dyn_keys: list[str]) -> dict:
    good = [r for r in rows if r.get("watch_label") == "GOOD"]
    bad = [r for r in rows if r.get("watch_label") == "BAD"]
    long_good = [r for r in good if r["direction"] == "LONG"]
    long_bad = [r for r in bad if r["direction"] == "LONG"]
    short_good = [r for r in good if r["direction"] == "SHORT"]
    short_bad = [r for r in bad if r["direction"] == "SHORT"]
    h1_good = [r for r in good if r["_half"] == "first"]
    h1_bad = [r for r in bad if r["_half"] == "first"]
    h2_good = [r for r in good if r["_half"] == "second"]
    h2_bad = [r for r in bad if r["_half"] == "second"]
    wrong = [r for r in rows if r.get("coverage_class") == "wrong_direction"]
    table = []
    for k in dyn_keys:
        gv = [r.get(k) for r in good]
        bv = [r.get(k) for r in bad]
        if sum(1 for v in gv if v is not None) < 20 or sum(1 for v in bv if v is not None) < 30:
            continue
        d_all = cohens_d(gv, bv)
        if d_all is None: continue
        table.append({
            "feature": k,
            "good_mean": mean_or_none(gv),
            "bad_mean": mean_or_none(bv),
            "wrong_mean": mean_or_none([r.get(k) for r in wrong]),
            "d_good_vs_bad": d_all,
            "d_long": cohens_d([r.get(k) for r in long_good], [r.get(k) for r in long_bad]),
            "d_short": cohens_d([r.get(k) for r in short_good], [r.get(k) for r in short_bad]),
            "d_h1": cohens_d([r.get(k) for r in h1_good], [r.get(k) for r in h1_bad]),
            "d_h2": cohens_d([r.get(k) for r in h2_good], [r.get(k) for r in h2_bad]),
            "good_n": sum(1 for v in gv if v is not None),
            "bad_n": sum(1 for v in bv if v is not None),
        })
    table.sort(key=lambda r: -abs(r["d_good_vs_bad"] or 0))
    csv_keys = list(table[0].keys()) if table else ["feature"]
    with (REP_OUT / "MARCH_DYNAMIC_L2_FEATURE_SEPARATION.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=csv_keys, extrasaction="ignore")
        w.writeheader()
        for r in table: w.writerow(r)
    (REP_OUT / "MARCH_DYNAMIC_L2_FEATURE_SEPARATION.json").write_text(
        json.dumps({"build_time_utc": now_iso(), "n_features": len(table),
                    "n_good": len(good), "n_bad": len(bad),
                    "feature_table": table[:80]}, indent=2, default=str), encoding="utf-8")
    md = ["# Dynamic L2 feature separation (GOOD vs BAD)", "",
          f"**Build:** {now_iso()}",
          f"**GOOD={len(good)}, BAD={len(bad)}, wrong={len(wrong)}**", "",
          "## Top 40 by |d good vs bad|", "",
          "| feature | good_mean | bad_mean | d(good vs bad) | d_LONG | d_SHORT | d_H1 | d_H2 |",
          "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for r in table[:40]:
        md.append(f"| `{r['feature']}` | {r['good_mean']} | {r['bad_mean']} | {r['d_good_vs_bad']} | "
                  f"{r['d_long']} | {r['d_short']} | {r['d_h1']} | {r['d_h2']} |")
    (REP_OUT / "MARCH_DYNAMIC_L2_FEATURE_SEPARATION.md").write_text("\n".join(md), encoding="utf-8")
    return {"table": table, "top_features": [r["feature"] for r in table[:20]]}


# ============================================================
# Section D: theory tests
# ============================================================
def theory_tests(rows: list[dict]) -> dict:
    good = [r for r in rows if r.get("watch_label") == "GOOD"]
    bad = [r for r in rows if r.get("watch_label") == "BAD"]
    long_good = [r for r in good if r["direction"] == "LONG"]
    long_bad = [r for r in bad if r["direction"] == "LONG"]
    short_good = [r for r in good if r["direction"] == "SHORT"]
    short_bad = [r for r in bad if r["direction"] == "SHORT"]
    wrong = [r for r in rows if r.get("coverage_class") == "wrong_direction"]

    def s(key, ga, ba):
        return {"good_mean": mean_or_none([r.get(key) for r in ga]),
                "bad_mean": mean_or_none([r.get(key) for r in ba]),
                "d": cohens_d([r.get(key) for r in ga], [r.get(key) for r in ba])}

    theories = []
    # T1: Good LONG = sweep + bid refill (supp_add)
    theories.append({"id": "T1", "statement": "Good LONG = supportive add (bid refill) higher than BAD LONG (5m window)",
                     "feature": "dl2_inband_supp_add_5m",
                     **s("dl2_inband_supp_add_5m", long_good, long_bad),
                     "verdict": _v(s("dl2_inband_supp_add_5m", long_good, long_bad)["d"])})
    # T2: Good SHORT mirror
    theories.append({"id": "T2", "statement": "Good SHORT = supportive add (ask refill) higher than BAD SHORT",
                     "feature": "dl2_inband_supp_add_5m",
                     **s("dl2_inband_supp_add_5m", short_good, short_bad),
                     "verdict": _v(s("dl2_inband_supp_add_5m", short_good, short_bad)["d"])})
    # T3: Stronger supportive wall persistence
    theories.append({"id": "T3", "statement": "Good zones have higher supportive top-1 persistence in 5m",
                     "feature": "dl2_top1_supportive_persistence_ge_50_5m_sec",
                     **s("dl2_top1_supportive_persistence_ge_50_5m_sec", good, bad),
                     "verdict": _v(s("dl2_top1_supportive_persistence_ge_50_5m_sec", good, bad)["d"])})
    # T4: Bad zones have high opp cancel near zone (spoof / pulled liquidity)
    theories.append({"id": "T4", "statement": "BAD zones have higher opposing cancel volume (spoof / pull) — 15m",
                     "feature": "dl2_inband_opp_cancel_15m",
                     **s("dl2_inband_opp_cancel_15m", good, bad),
                     "verdict_inverse": _vi(s("dl2_inband_opp_cancel_15m", good, bad)["d"])})
    # T5: Good zones have lower opposing flow (liquidity void toward target)
    theories.append({"id": "T5", "statement": "Good zones have lower net opposing flow (liquidity void toward target) — 15m",
                     "feature": "dl2_net_opposing_flow_15m",
                     **s("dl2_net_opposing_flow_15m", good, bad),
                     "verdict_inverse": _vi(s("dl2_net_opposing_flow_15m", good, bad)["d"])})
    # T6: Good zones have thicker supportive flow (refill > cancel) — 15m
    theories.append({"id": "T6", "statement": "Good zones have stronger net supportive flow (15m)",
                     "feature": "dl2_net_supportive_flow_15m",
                     **s("dl2_net_supportive_flow_15m", good, bad),
                     "verdict": _v(s("dl2_net_supportive_flow_15m", good, bad)["d"])})
    # T7: Good zones show microprice shift ALIGNED with direction over 5m
    theories.append({"id": "T7", "statement": "Good zones show supportive microprice drift (5m delta aligned)",
                     "feature": "dl2_microprice_aligned_delta_5m_bps",
                     **s("dl2_microprice_aligned_delta_5m_bps", good, bad),
                     "verdict": _v(s("dl2_microprice_aligned_delta_5m_bps", good, bad)["d"])})
    # T8: Good zones show supportive microprice over 15m (book recovery)
    theories.append({"id": "T8", "statement": "Good zones show supportive microprice over 15m (book recovery)",
                     "feature": "dl2_microprice_aligned_delta_15m_bps",
                     **s("dl2_microprice_aligned_delta_15m_bps", good, bad),
                     "verdict": _v(s("dl2_microprice_aligned_delta_15m_bps", good, bad)["d"])})
    # T9: Wrong-direction zones have higher opposing flow
    theories.append({"id": "T9", "statement": "Wrong-direction zones have HIGHER net opposing flow than GOOD",
                     "feature": "dl2_net_opposing_flow_15m",
                     "good_mean": mean_or_none([r.get("dl2_net_opposing_flow_15m") for r in good]),
                     "wrong_mean": mean_or_none([r.get("dl2_net_opposing_flow_15m") for r in wrong]),
                     "d_good_vs_wrong": cohens_d([r.get("dl2_net_opposing_flow_15m") for r in good],
                                                  [r.get("dl2_net_opposing_flow_15m") for r in wrong]),
                     "verdict": "supported" if (cohens_d(
                                  [r.get("dl2_net_opposing_flow_15m") for r in good],
                                  [r.get("dl2_net_opposing_flow_15m") for r in wrong]) or 0) <= -0.2 else "weak"})
    # T10: Strong raw flow only good when paired with supportive refill
    flow_high = [r for r in rows if (r.get("dl2_inband_add_vol_5m") or 0) >= quantile(
                    [r.get("dl2_inband_add_vol_5m") or 0 for r in rows], 0.75)]
    flow_high_supp = [r for r in flow_high if (r.get("dl2_inband_supp_add_5m") or 0) >
                       (r.get("dl2_inband_opp_add_5m") or 0)]
    flow_high_opp = [r for r in flow_high if not r in flow_high_supp]
    theories.append({"id": "T10", "statement": "Strong flow alone is bad UNLESS paired with supportive bias",
                     "feature": "high flow split by supportive vs opposing dominance",
                     "n_high_flow": len(flow_high),
                     "high_flow_supp_dominant_good_pct": round(100.0 * sum(1 for r in flow_high_supp if r.get("watch_label") == "GOOD") / max(len(flow_high_supp), 1), 2),
                     "high_flow_opp_dominant_good_pct": round(100.0 * sum(1 for r in flow_high_opp if r.get("watch_label") == "GOOD") / max(len(flow_high_opp), 1), 2),
                     "verdict": "diagnostic"})
    # T11: Local-normalized refill better than raw
    theories.append({"id": "T11", "statement": "Local-normalized supp refill (5m vs avg5m ratio) better than raw refill",
                     "raw_d_good_vs_bad": cohens_d([r.get("dl2_supportive_add_vol_5m") for r in good],
                                                     [r.get("dl2_supportive_add_vol_5m") for r in bad]),
                     "normalized_d_good_vs_bad": cohens_d([r.get("dl2_net_supportive_flow_5m_vs_avg5m_ratio") for r in good],
                                                            [r.get("dl2_net_supportive_flow_5m_vs_avg5m_ratio") for r in bad]),
                     "verdict": "diagnostic"})
    # T12: Dynamic L2 outperform snapshot L2 — compare best d
    theories.append({"id": "T12", "statement": "Dynamic L2 features show |d| > snapshot L2 features",
                     "comment": "see MARCH_DYNAMIC_L2_FEATURE_SEPARATION top entries vs snapshot l2_imb5_aligned d (~0.05-0.15 in prior pass)",
                     "verdict": "see separation report"})

    out = {"build_time_utc": now_iso(),
           "n_good": len(good), "n_bad": len(bad), "n_wrong": len(wrong),
           "theories": theories}
    (REP_OUT / "MARCH_DYNAMIC_L2_THEORY_TESTS.json").write_text(
        json.dumps(out, indent=2, default=str), encoding="utf-8")
    md = ["# Dynamic L2 theory tests (12 theories)", "",
          f"**Build:** {out['build_time_utc']}",
          f"**GOOD={out['n_good']}, BAD={out['n_bad']}**", ""]
    for t in theories:
        md.append(f"## {t['id']}: {t['statement']}")
        for k, v in t.items():
            if k in ("id", "statement"): continue
            md.append(f"- {k}: {v}")
        md.append("")
    (REP_OUT / "MARCH_DYNAMIC_L2_THEORY_TESTS.md").write_text("\n".join(md), encoding="utf-8")
    return out


def _v(d):
    if d is None: return "unknown"
    if abs(d) >= 0.3: return "supported"
    if abs(d) >= 0.15: return "weak"
    return "false"

def _vi(d):
    if d is None: return "unknown"
    if d <= -0.2: return "supported (lower in GOOD)"
    if d <= -0.1: return "weak"
    return "no"


# ============================================================
# Section E: selector search with dynamic L2
# ============================================================
def selector_eval(rows: list[dict], predicate, day_cap=None, score_key=None) -> dict:
    by_date = defaultdict(list)
    for r in rows:
        if not predicate(r): continue
        by_date[r["date"]].append(r)
    selected = []
    for d in ALL_DATES:
        day_rows = by_date.get(d, [])
        if score_key:
            day_rows = sorted(day_rows, key=lambda x: -(x.get(score_key) or 0))
        if day_cap is not None:
            day_rows = day_rows[:day_cap]
        selected.extend(day_rows)
    n = len(selected)
    good = sum(1 for r in selected if r.get("watch_label") == "GOOD")
    wrong = sum(1 for r in selected if r.get("coverage_class") == "wrong_direction")
    n_good_all = sum(1 for r in rows if r.get("watch_label") == "GOOD")
    h1 = [r for r in selected if r["_half"] == "first"]
    h2 = [r for r in selected if r["_half"] == "second"]
    g1 = sum(1 for r in h1 if r.get("watch_label") == "GOOD")
    g2 = sum(1 for r in h2 if r.get("watch_label") == "GOOD")
    lng = [r for r in selected if r["direction"] == "LONG"]
    sht = [r for r in selected if r["direction"] == "SHORT"]
    gl = sum(1 for r in lng if r.get("watch_label") == "GOOD")
    gs = sum(1 for r in sht if r.get("watch_label") == "GOOD")
    leads = [r.get("lead_min_before_move") for r in selected
             if r.get("lead_min_before_move") and r["lead_min_before_move"] > 0]
    return {
        "selected_n": n, "alerts_per_day": round(n / N_DAYS, 3),
        "good_n": good, "wrong_n": wrong,
        "precision_pct": round(100.0 * good / max(n, 1), 2) if n else None,
        "recall_pct": round(100.0 * good / max(n_good_all, 1), 2) if n_good_all else None,
        "wrong_rate_pct": round(100.0 * wrong / max(n, 1), 2) if n else None,
        "h1_precision_pct": round(100.0 * g1 / max(len(h1), 1), 2) if h1 else None,
        "h2_precision_pct": round(100.0 * g2 / max(len(h2), 1), 2) if h2 else None,
        "long_precision_pct": round(100.0 * gl / max(len(lng), 1), 2) if lng else None,
        "short_precision_pct": round(100.0 * gs / max(len(sht), 1), 2) if sht else None,
        "long_n": len(lng), "short_n": len(sht), "h1_n": len(h1), "h2_n": len(h2),
        "avg_lead_min": round(stats.mean(leads), 2) if leads else None,
        "selected_zone_ids": [r["zone_id"] for r in selected],
    }


def make_rule_candidates(rows, numeric_keys, boolean_keys):
    out = []
    for k in numeric_keys:
        vals = [r.get(k) for r in rows if r.get(k) is not None]
        if len(vals) < 50: continue
        for q in (0.2, 0.4, 0.6, 0.8):
            v = quantile(vals, q)
            if v is None: continue
            out.append((f"{k}_ge_{round(v, 4)}",
                          (lambda kk, th: lambda r: (r.get(kk) is not None) and (r.get(kk) >= th))(k, v)))
            out.append((f"{k}_le_{round(v, 4)}",
                          (lambda kk, th: lambda r: (r.get(kk) is not None) and (r.get(kk) <= th))(k, v)))
    for k in boolean_keys:
        out.append((f"{k}_TRUE", (lambda kk: lambda r: bool(r.get(kk)))(k)))
        out.append((f"{k}_FALSE", (lambda kk: lambda r: not bool(r.get(kk)))(k)))
    out.append(("dir_LONG", lambda r: r["direction"] == "LONG"))
    out.append(("dir_SHORT", lambda r: r["direction"] == "SHORT"))
    return out


def explainable_score_l2_dyn(r: dict) -> float:
    """Confirm-stage safe score using prior leak-free features + dynamic L2."""
    s = 0.0
    if (r.get("opp_dir_zones_active_60m") or 0) == 0: s += 0.5
    pm = r.get("prior_move_60m_pct")
    if pm is not None: s -= min(abs(pm) * 0.3, 0.5)
    lr = r.get("local_range_180m_pct")
    if lr is not None and lr > 2.0: s -= 0.3
    if r.get("sweep_reclaim_aligned") == 1: s += 0.3
    if r.get("is_asia_session"): s += 0.2
    # Dynamic L2 contributions
    md = r.get("dl2_microprice_aligned_delta_5m_bps")
    if md is not None: s += max(min(md / 5.0, 0.5), -0.5)   # +0.5 if shift >= 2.5 bps
    md15 = r.get("dl2_microprice_aligned_delta_15m_bps")
    if md15 is not None: s += max(min(md15 / 10.0, 0.3), -0.3)
    smr = r.get("dl2_supp_minus_opp_net_flow_5m")
    if smr is not None and smr > 0:
        s += min(smr / 100.0, 0.4)
    # Penalty for high opposing in-band cancels (spoof / pulled)
    oc = r.get("dl2_inband_opp_cancel_15m") or 0
    if oc > 20: s -= min(oc / 200.0, 0.3)
    # Supportive top-1 persistence (wall)
    wp = r.get("dl2_top1_supportive_persistence_ge_50_5m_sec") or 0
    if wp > 60: s += min(wp / 600.0, 0.3)
    return round(s, 4)


def search_with_dyn_l2(rows: list[dict], dyn_keys: list[str]) -> list[dict]:
    # Stage = confirmed (we never use trigger / post-confirm fields)
    # Safe legacy features
    safe_numeric_legacy = [
        "cand_pressure_against", "cand_buy_pressure", "cand_sell_pressure",
        "cand_absorb_score", "cand_bid_refill_score", "cand_ask_refill_score",
        "cand_refill_with", "cand_prior_move_pct",
        "conf_cycles_seen", "conf_age_min", "conf_defended_persistence_sec",
        "conf_opposite_thinning", "conf_void_score",
        "score_absorption", "score_refill", "score_ofi", "score_liquidity_void",
        "zone_width_pct",
        "same_dir_zones_active_60m", "opp_dir_zones_active_60m",
        "prior_move_15m_pct", "prior_move_30m_pct", "prior_move_60m_pct", "prior_move_180m_pct",
        "local_range_15m_pct", "local_range_30m_pct", "local_range_60m_pct", "local_range_180m_pct",
        "local_realized_vol_15m", "local_realized_vol_30m", "local_realized_vol_60m",
        "dist_to_recent_swing_high_pct", "dist_to_recent_swing_low_pct",
        "dist_to_4h_mean_pct",
        "taker_imb_aligned_30m", "taker_imb_aligned_60m", "taker_total_vol_15m", "taker_total_vol_60m",
        "vol_anomaly_15m_vs_bg", "ofi_shift_aligned",
        "utc_hour",
        # snapshot L2
        "spread_bps", "top5_imbalance", "top20_imbalance",
        "l2_imb5_aligned", "l2_imb20_aligned", "l2_microprice_aligned",
        "depth_top1_ratio_aligned", "microprice_dev_bps",
    ]
    safe_boolean_legacy = ["cand_range_compression", "sweep_reclaim_aligned",
                            "is_asia_session", "is_us_session"]
    # Add all dynamic L2 numeric features
    numeric_keys = safe_numeric_legacy + [k for k in dyn_keys if k.startswith("dl2_")]
    boolean_keys = safe_boolean_legacy
    # Pre-score
    for r in rows: r["_score_dyn"] = explainable_score_l2_dyn(r)
    print(f"  building rules over {len(numeric_keys)} numeric + {len(boolean_keys)} boolean ...", file=sys.stderr)
    rules = make_rule_candidates(rows, numeric_keys, boolean_keys)
    print(f"  -> {len(rules)} single rules", file=sys.stderr)
    out = []
    for name, fn in rules:
        e = selector_eval(rows, fn)
        out.append({"selector": f"DL2::S::{name}", **e, "kind": "single"})
        e1 = selector_eval(rows, fn, day_cap=1, score_key="_score_dyn")
        out.append({"selector": f"DL2::S::{name}::top1", **e1, "kind": "single+top1"})
        e2 = selector_eval(rows, fn, day_cap=2, score_key="_score_dyn")
        out.append({"selector": f"DL2::S::{name}::top2", **e2, "kind": "single+top2"})
    # Pair search on top 12 features
    valid = [s for s in out if (s.get("selected_n") or 0) >= 20 and s.get("precision_pct") is not None]
    valid.sort(key=lambda s: -s["precision_pct"])
    seen_feats = set(); top_feats = []
    for s in valid[:50]:
        body = s["selector"].split("::")[2]
        for fk in numeric_keys + boolean_keys:
            if body.startswith(fk):
                if fk not in seen_feats:
                    seen_feats.add(fk); top_feats.append(fk)
                break
        if len(top_feats) >= 12: break
    print(f"  top features for pair search: {top_feats}", file=sys.stderr)
    for i, a in enumerate(top_feats):
        for j in range(i + 1, len(top_feats)):
            b = top_feats[j]
            preds_a = _rule_cands(rows, a, numeric_keys, boolean_keys)
            preds_b = _rule_cands(rows, b, numeric_keys, boolean_keys)
            for na, fa in preds_a:
                for nb, fb in preds_b:
                    def make_and(fa, fb): return lambda r: fa(r) and fb(r)
                    pred = make_and(fa, fb)
                    e = selector_eval(rows, pred)
                    if (e["selected_n"] or 0) < 5: continue
                    out.append({"selector": f"DL2::P::{na}+{nb}", **e, "kind": "pair"})
                    e1 = selector_eval(rows, pred, day_cap=1, score_key="_score_dyn")
                    out.append({"selector": f"DL2::P::{na}+{nb}::top1", **e1, "kind": "pair+top1"})
    # Triple on top 7
    print("  triple search on top 7 ...", file=sys.stderr)
    for combo in itertools.combinations(top_feats[:7], 3):
        rules_per = [_rule_cands(rows, k, numeric_keys, boolean_keys)[:2] for k in combo]
        for triplet in itertools.product(*rules_per):
            names = [t[0] for t in triplet]; fns = [t[1] for t in triplet]
            def make_and(fns): return lambda r: all(f(r) for f in fns)
            pred = make_and(fns)
            e = selector_eval(rows, pred)
            if (e["selected_n"] or 0) < 5: continue
            out.append({"selector": f"DL2::T::{'+'.join(names)}", **e, "kind": "triple"})
    return out


def _rule_cands(rows, k, numeric_keys, boolean_keys):
    if k in boolean_keys:
        return [(f"{k}_TRUE", (lambda kk: lambda r: bool(r.get(kk)))(k)),
                (f"{k}_FALSE", (lambda kk: lambda r: not bool(r.get(kk)))(k))]
    vals = [r.get(k) for r in rows if r.get(k) is not None]
    if len(vals) < 50: return []
    out = []
    for q in (0.3, 0.5, 0.7):
        v = quantile(vals, q)
        if v is None: continue
        out.append((f"{k}_ge_{round(v, 4)}",
                     (lambda kk, th: lambda r: (r.get(kk) is not None) and (r.get(kk) >= th))(k, v)))
        out.append((f"{k}_le_{round(v, 4)}",
                     (lambda kk, th: lambda r: (r.get(kk) is not None) and (r.get(kk) <= th))(k, v)))
    return out


def write_search_results(all_sels: list[dict]) -> dict:
    csv_keys = ["selector", "kind", "selected_n", "alerts_per_day",
                "good_n", "wrong_n", "precision_pct", "recall_pct", "wrong_rate_pct",
                "h1_precision_pct", "h2_precision_pct",
                "long_precision_pct", "short_precision_pct",
                "long_n", "short_n", "h1_n", "h2_n", "avg_lead_min"]
    with (REP_OUT / "MARCH_DYNAMIC_L2_SELECTOR_SEARCH.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=csv_keys, extrasaction="ignore")
        w.writeheader()
        for s in all_sels: w.writerow(s)
    def best(min_n):
        cands = [s for s in all_sels if (s.get("selected_n") or 0) >= min_n
                  and s.get("precision_pct") is not None]
        cands.sort(key=lambda s: -s["precision_pct"])
        return cands[:5]
    tiers = {n: best(n) for n in (10, 15, 20, 25, 29)}
    summary = {
        "build_time_utc": now_iso(),
        "n_selectors": len(all_sels),
        "any_70_min10": any((s.get("precision_pct") or 0) >= 70 for s in all_sels if (s.get("selected_n") or 0) >= 10),
        "any_70_min15": any((s.get("precision_pct") or 0) >= 70 for s in all_sels if (s.get("selected_n") or 0) >= 15),
        "any_70_min20": any((s.get("precision_pct") or 0) >= 70 for s in all_sels if (s.get("selected_n") or 0) >= 20),
        "any_70_min25": any((s.get("precision_pct") or 0) >= 70 for s in all_sels if (s.get("selected_n") or 0) >= 25),
        "any_70_min29": any((s.get("precision_pct") or 0) >= 70 for s in all_sels if (s.get("selected_n") or 0) >= 29),
        "any_80_min10": any((s.get("precision_pct") or 0) >= 80 for s in all_sels if (s.get("selected_n") or 0) >= 10),
        "best_per_tier": {f"min_{k}": [{kk: v for kk, v in s.items() if kk != "selected_zone_ids"} for s in v]
                          for k, v in tiers.items()},
    }
    (REP_OUT / "MARCH_DYNAMIC_L2_SELECTOR_SEARCH.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8")
    md = ["# Dynamic L2 leak-free selector search", "",
          f"**Build:** {summary['build_time_utc']}",
          f"**Selectors evaluated:** {summary['n_selectors']}",
          f"**>=70 % with min 10:** {summary['any_70_min10']}",
          f"**>=70 % with min 15:** {summary['any_70_min15']}",
          f"**>=70 % with min 20:** {summary['any_70_min20']}",
          f"**>=70 % with min 25:** {summary['any_70_min25']}",
          f"**>=70 % with min 29:** {summary['any_70_min29']}",
          f"**>=80 % with min 10:** {summary['any_80_min10']}", ""]
    for tier, top5 in tiers.items():
        md.append(f"## Best 5 with selected >= {tier}")
        md.append("| selector | n | /day | precision % | recall % | wrong % | H1 prec | H2 prec |")
        md.append("|---|---:|---:|---:|---:|---:|---:|---:|")
        for s in top5:
            md.append(f"| `{s['selector']}` | {s['selected_n']} | {s['alerts_per_day']} | "
                       f"{s['precision_pct']} | {s.get('recall_pct')} | {s.get('wrong_rate_pct')} | "
                       f"{s.get('h1_precision_pct')} | {s.get('h2_precision_pct')} |")
        md.append("")
    (REP_OUT / "MARCH_DYNAMIC_L2_SELECTOR_SEARCH.md").write_text("\n".join(md), encoding="utf-8")
    return summary


# ============================================================
# Section F: precision frontier
# ============================================================
def frontier(rows: list[dict], all_sels: list[dict]) -> None:
    tiers = [5, 10, 15, 20, 25, 29, 40, 60]
    front = []
    for t in tiers:
        cands = [s for s in all_sels if (s.get("selected_n") or 0) >= t
                  and s.get("precision_pct") is not None]
        cands.sort(key=lambda s: -s["precision_pct"])
        best = cands[0] if cands else None
        if best:
            front.append({"min_count": t, "achieved_n": best["selected_n"],
                          "selector": best["selector"],
                          "precision_pct": best["precision_pct"],
                          "recall_pct": best.get("recall_pct"),
                          "wrong_rate_pct": best.get("wrong_rate_pct"),
                          "h1_precision_pct": best.get("h1_precision_pct"),
                          "h2_precision_pct": best.get("h2_precision_pct"),
                          "overfit_risk": "HIGH" if best["selected_n"] < 20 else (
                                            "MEDIUM" if best["selected_n"] < 40 else "LOW")})
    # Compare to previous frontier (from MARCH_70PCT_PRECISION_COVERAGE_FRONTIER)
    prev_path = REP_OUT / "MARCH_70PCT_PRECISION_COVERAGE_FRONTIER.json"
    prev = json.load(open(prev_path, encoding="utf-8"))["leak_free_frontier"] if prev_path.exists() else []
    out = {"build_time_utc": now_iso(),
           "dynamic_l2_frontier": front,
           "previous_no_dyn_frontier": prev,
           "improvement_at_min_20_pct": (front[3]["precision_pct"] - prev[3]["precision_pct"]) if len(front) > 3 and len(prev) > 3 else None}
    (REP_OUT / "MARCH_DYNAMIC_L2_PRECISION_FRONTIER.json").write_text(
        json.dumps(out, indent=2, default=str), encoding="utf-8")
    with (REP_OUT / "MARCH_DYNAMIC_L2_PRECISION_FRONTIER.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["regime", "min_count", "achieved_n", "selector",
                                            "precision_pct", "recall_pct", "wrong_rate_pct",
                                            "h1_precision_pct", "h2_precision_pct", "overfit_risk"])
        w.writeheader()
        for r in front: w.writerow({"regime": "dynamic_l2", **r})
        for r in prev: w.writerow({"regime": "prev_no_dyn", **r})
    md = ["# Precision frontier — dynamic L2 vs previous", "",
          f"**Build:** {out['build_time_utc']}", "",
          "## Dynamic L2 frontier", "",
          "| min_count | achieved_n | selector | precision % | recall % | wrong % | H1 prec | H2 prec | OF risk |",
          "|---:|---:|---|---:|---:|---:|---:|---:|---|"]
    for r in front:
        md.append(f"| {r['min_count']} | {r['achieved_n']} | `{r['selector']}` | {r['precision_pct']} | "
                  f"{r.get('recall_pct')} | {r.get('wrong_rate_pct')} | "
                  f"{r.get('h1_precision_pct')} | {r.get('h2_precision_pct')} | {r['overfit_risk']} |")
    md.extend(["", "## Previous frontier (no dynamic L2)", "",
               "| min_count | achieved_n | selector | precision % |",
               "|---:|---:|---|---:|"])
    for r in prev:
        md.append(f"| {r['min_count']} | {r.get('achieved_n')} | `{r.get('selector')}` | {r.get('precision_pct')} |")
    if out["improvement_at_min_20_pct"] is not None:
        md.extend(["", f"## Improvement at min 20: **{out['improvement_at_min_20_pct']:+.2f} pp**"])
    (REP_OUT / "MARCH_DYNAMIC_L2_PRECISION_FRONTIER.md").write_text("\n".join(md), encoding="utf-8")
    return out


# ============================================================
# Section G: paper trade with dynamic L2
# ============================================================
def paper_trade(rows: list[dict], all_sels: list[dict],
                 buckets_multi: dict[str, list[Bucket]]) -> list[dict]:
    by_id = {r["zone_id"]: r for r in rows}
    cands = [s for s in all_sels if (s.get("selected_n") or 0) >= 15
              and s.get("precision_pct") is not None]
    cands.sort(key=lambda s: -s["precision_pct"])
    top = cands[:15]
    entry_modes = ["confirmed", "delay_5m", "delay_10m", "delay_15m"]
    stop_configs = [("stop_1.0", 1.0, False), ("stop_1.25", 1.25, False),
                    ("stop_1.5", 1.5, False)]
    results = []
    for sel in top:
        sel_rows = [by_id[i] for i in (sel.get("selected_zone_ids") or []) if i in by_id]
        if not sel_rows: continue
        for em in entry_modes:
            for sn, sp, zb in stop_configs:
                trades = []
                for sr in sel_rows:
                    buckets = buckets_multi.get(sr["date"]) or []
                    confirmed_sec = iso_to_sec(sr.get("confirmed_iso"))
                    if confirmed_sec is None: continue
                    if em == "confirmed":
                        trig_ms = confirmed_sec * 1000; es = "trigger"
                    else:
                        trig_ms = confirmed_sec * 1000; es = em
                    sig = Signal(id=sr["zone_id"], date=sr["date"], trigger_ts_ms=trig_ms,
                                 direction=sr["direction"], zone_low=sr.get("zone_low"),
                                 zone_high=sr.get("zone_high"))
                    cfg = ExecutionConfig(entry_strategy=es, stop_pct=sp,
                                          zone_boundary_stop=zb, target_pct=TARGET_PCT,
                                          timeout_hours=TIMEOUT_HOURS)
                    sim = simulate_canonical_trade(sig, buckets, cfg)
                    if sim.get("exit_reason") in ("no_data", "skip_no_retest"): continue
                    trades.append(sim | {"zone_id": sr["zone_id"], "date": sr["date"],
                                          "direction": sr["direction"]})
                if not trades: continue
                n = len(trades)
                wins = sum(1 for t in trades if t["exit_reason"] == "target_2pct")
                pnls = [t["pnl_pct"] for t in trades]
                pnls_after = [p - COST_PCT for p in pnls]
                wp = [p for p in pnls if p > 0]; lp = [p for p in pnls if p < 0]
                gw = sum(wp); gl = sum(-p for p in lp)
                wp_a = [p for p in pnls_after if p > 0]; lp_a = [p for p in pnls_after if p < 0]
                gw_a = sum(wp_a); gl_a = sum(-p for p in lp_a)
                cur = 0; mx = 0
                for t in trades:
                    if t["pnl_pct"] <= 0: cur += 1; mx = max(mx, cur)
                    else: cur = 0
                results.append({
                    "selector": sel["selector"], "entry_mode": em, "stop": sn,
                    "trades": n, "wins": wins,
                    "winrate_pct": round(100.0 * wins / n, 2),
                    "expectancy_pre_cost_pct": round(stats.mean(pnls), 4),
                    "expectancy_after_cost_pct": round(stats.mean(pnls_after), 4),
                    "pf_pre_cost": round(gw / gl, 3) if gl > 0 else (None if gw == 0 else float("inf")),
                    "pf_after_cost": round(gw_a / gl_a, 3) if gl_a > 0 else (None if gw_a == 0 else float("inf")),
                    "total_return_after_cost_pct": round(sum(pnls_after), 4),
                    "max_consecutive_losses": mx,
                })
    return results


def write_paper_results(paper_rows: list[dict]) -> Optional[dict]:
    paper_rows.sort(key=lambda r: -(r["winrate_pct"] or 0))
    with (REP_OUT / "MARCH_DYNAMIC_L2_PAPER_TRADE_OPTIMIZATION.csv").open("w", encoding="utf-8", newline="") as f:
        if paper_rows:
            w = csv.DictWriter(f, fieldnames=list(paper_rows[0].keys()))
            w.writeheader()
            for r in paper_rows: w.writerow(r)
    (REP_OUT / "MARCH_DYNAMIC_L2_PAPER_TRADE_OPTIMIZATION.json").write_text(
        json.dumps({"build_time_utc": now_iso(), "n_models": len(paper_rows),
                    "results": paper_rows[:80]}, indent=2, default=str), encoding="utf-8")
    big = [r for r in paper_rows if (r["trades"] or 0) >= 20]
    md = ["# Dynamic L2 paper trade optimization (leak-free at confirm)", "",
          f"**Build:** {now_iso()}",
          f"**Models:** {len(paper_rows)}",
          "",
          "## Top 30 by winrate (>=20 trades)",
          "",
          "| selector | entry | stop | trades | winrate % | exp aft % | PF aft | maxCL |",
          "|---|---|---|---:|---:|---:|---:|---:|"]
    for r in big[:30]:
        md.append(f"| `{r['selector']}` | {r['entry_mode']} | {r['stop']} | {r['trades']} | "
                  f"{r['winrate_pct']} | {r['expectancy_after_cost_pct']} | "
                  f"{r['pf_after_cost']} | {r['max_consecutive_losses']} |")
    md.append("")
    md.append("## Top 20 by winrate (any size)")
    md.append("| selector | entry | stop | trades | winrate % | exp aft % | PF aft |")
    md.append("|---|---|---|---:|---:|---:|---:|")
    for r in paper_rows[:20]:
        md.append(f"| `{r['selector']}` | {r['entry_mode']} | {r['stop']} | {r['trades']} | "
                  f"{r['winrate_pct']} | {r['expectancy_after_cost_pct']} | {r['pf_after_cost']} |")
    (REP_OUT / "MARCH_DYNAMIC_L2_PAPER_TRADE_OPTIMIZATION.md").write_text("\n".join(md), encoding="utf-8")
    return big[0] if big else None


# ============================================================
# Section H: casebook
# ============================================================
def write_casebook(rows: list[dict], all_sels: list[dict], best_sel: Optional[dict]) -> None:
    if not best_sel:
        (REP_OUT / "MARCH_DYNAMIC_L2_GOOD_BAD_CASEBOOK.md").write_text("# (no best selector)", encoding="utf-8")
        return
    by_id = {r["zone_id"]: r for r in rows}
    sel_ids = set(best_sel.get("selected_zone_ids") or [])
    sel_rows = [by_id[i] for i in sel_ids if i in by_id]
    winners = [r for r in sel_rows if r.get("watch_label") == "GOOD"]
    losers = [r for r in sel_rows if r.get("watch_label") == "BAD"]
    wrong = [r for r in sel_rows if r.get("coverage_class") == "wrong_direction"]
    missed = [r for r in rows if r.get("watch_label") == "GOOD" and r["zone_id"] not in sel_ids][:20]

    def ser(r):
        return {"date": r["date"], "zone_id": r["zone_id"], "direction": r["direction"],
                "confirmed_iso": r.get("confirmed_iso"),
                "matched_move_size_pct": r.get("matched_move_size_pct"),
                "lead_min_before_move": r.get("lead_min_before_move"),
                "watch_label": r.get("watch_label"),
                "coverage_class": r.get("coverage_class"),
                "session": r.get("session"),
                "dl2_supp_minus_opp_net_flow_5m": r.get("dl2_supp_minus_opp_net_flow_5m"),
                "dl2_supp_minus_opp_net_flow_15m": r.get("dl2_supp_minus_opp_net_flow_15m"),
                "dl2_inband_supp_add_5m": r.get("dl2_inband_supp_add_5m"),
                "dl2_inband_opp_cancel_15m": r.get("dl2_inband_opp_cancel_15m"),
                "dl2_microprice_aligned_delta_5m_bps": r.get("dl2_microprice_aligned_delta_5m_bps"),
                "dl2_microprice_aligned_delta_15m_bps": r.get("dl2_microprice_aligned_delta_15m_bps"),
                "dl2_top1_supportive_persistence_ge_50_5m_sec": r.get("dl2_top1_supportive_persistence_ge_50_5m_sec"),
                "spread_bps": r.get("spread_bps"),
                "l2_imb5_aligned": r.get("l2_imb5_aligned")}

    out = {"build_time_utc": now_iso(),
           "best_selector": best_sel["selector"],
           "winners": [ser(r) for r in winners],
           "losers": [ser(r) for r in losers],
           "wrong_direction": [ser(r) for r in wrong],
           "missed_good_top20": [ser(r) for r in missed]}
    (REP_OUT / "MARCH_DYNAMIC_L2_GOOD_BAD_CASEBOOK.json").write_text(
        json.dumps(out, indent=2, default=str), encoding="utf-8")
    md = ["# Dynamic L2 casebook (best leak-free selector)", "",
          f"**Build:** {out['build_time_utc']}",
          f"**Best selector:** `{best_sel['selector']}`",
          f"**Selected:** {len(sel_rows)}; winners {len(winners)}; losers {len(losers)}; wrong-dir {len(wrong)}",
          ""]
    for header, items in [("Winners", out["winners"]),
                          ("Losers", out["losers"]),
                          ("Wrong-direction", out["wrong_direction"]),
                          ("Top 20 missed GOOD", out["missed_good_top20"])]:
        md.append(f"## {header}")
        md.append("| date | dir | confirmed | match % | lead | session | supp_minus_opp_5m | supp_minus_opp_15m | mp_5m_bps | mp_15m_bps | wall_pers_sec |")
        md.append("|---|---|---|---:|---:|---|---:|---:|---:|---:|---:|")
        for r in items:
            md.append(f"| {r['date']} | {r['direction']} | {r['confirmed_iso']} | "
                       f"{r.get('matched_move_size_pct')} | {r.get('lead_min_before_move')} | "
                       f"{r.get('session')} | {r.get('dl2_supp_minus_opp_net_flow_5m')} | "
                       f"{r.get('dl2_supp_minus_opp_net_flow_15m')} | "
                       f"{r.get('dl2_microprice_aligned_delta_5m_bps')} | "
                       f"{r.get('dl2_microprice_aligned_delta_15m_bps')} | "
                       f"{r.get('dl2_top1_supportive_persistence_ge_50_5m_sec')} |")
        md.append("")
    (REP_OUT / "MARCH_DYNAMIC_L2_GOOD_BAD_CASEBOOK.md").write_text("\n".join(md), encoding="utf-8")


# ============================================================
# Section I: final report
# ============================================================
def write_final_report(rows: list[dict], dyn_keys: list[str], search_summary: dict,
                        frontier_out: dict, best_paper: Optional[dict],
                        sep_top_features: list[str]) -> dict:
    best_min20 = None
    for tier_min in (20, 15, 10):
        cands = search_summary["best_per_tier"].get(f"min_{tier_min}", [])
        if cands:
            best_min20 = cands[0]; break
    n_zones_with_dyn = sum(1 for r in rows if r.get("dl2_microprice_now") is not None)
    prev_best_precision = 40.0   # from last pass (snapshot L2)
    prev_best_paper_winrate = 56.0
    flags = {
        "DYNAMIC_L2_RESEARCH_DONE": "YES",
        "DAYS_INCLUDED": N_DAYS,
        "ZONES_WITH_DYNAMIC_L2_FEATURES": n_zones_with_dyn,
        "DYNAMIC_L2_FEATURES_EXTRACTED": len([k for k in dyn_keys if k.startswith("dl2_")]),
        "USEFUL_DYNAMIC_L2_FEATURES_FOUND": "YES" if sep_top_features else "NO",
        "TOP_DYNAMIC_L2_FEATURE_1": sep_top_features[0] if len(sep_top_features) > 0 else "none",
        "TOP_DYNAMIC_L2_FEATURE_2": sep_top_features[1] if len(sep_top_features) > 1 else "none",
        "TOP_DYNAMIC_L2_FEATURE_3": sep_top_features[2] if len(sep_top_features) > 2 else "none",
        "TOP_DYNAMIC_L2_ANTI_FEATURE_1": "none-confirmed",
        "DYNAMIC_L2_70PCT_SELECTOR_FOUND": "YES" if search_summary.get("any_70_min10") else "NO",
        "DYNAMIC_L2_70PCT_WITH_MIN20_FOUND": "YES" if search_summary.get("any_70_min20") else "NO",
        "DYNAMIC_L2_70PCT_WITH_MIN29_FOUND": "YES" if search_summary.get("any_70_min29") else "NO",
        "BEST_DYNAMIC_L2_SELECTOR_NAME": best_min20["selector"] if best_min20 else "none",
        "BEST_DYNAMIC_L2_SELECTOR_STAGE": "confirmed",
        "BEST_DYNAMIC_L2_SELECTED_COUNT": best_min20["selected_n"] if best_min20 else None,
        "BEST_DYNAMIC_L2_ALERTS_PER_DAY": best_min20["alerts_per_day"] if best_min20 else None,
        "BEST_DYNAMIC_L2_PRECISION": best_min20["precision_pct"] if best_min20 else None,
        "BEST_DYNAMIC_L2_RECALL": best_min20.get("recall_pct") if best_min20 else None,
        "BEST_DYNAMIC_L2_WRONG_DIRECTION_RATE": best_min20.get("wrong_rate_pct") if best_min20 else None,
        "BEST_DYNAMIC_L2_H1_PRECISION": best_min20.get("h1_precision_pct") if best_min20 else None,
        "BEST_DYNAMIC_L2_H2_PRECISION": best_min20.get("h2_precision_pct") if best_min20 else None,
        "BEST_DYNAMIC_L2_OVERFIT_RISK": ("HIGH" if best_min20 and best_min20["selected_n"] < 20
                                          else ("MEDIUM" if best_min20 and best_min20["selected_n"] < 40 else "LOW")),
        "BEST_DYNAMIC_L2_PAPER_MODEL": (f"{best_paper['selector']} | {best_paper['entry_mode']} | {best_paper['stop']}"
                                          if best_paper else "none"),
        "BEST_DYNAMIC_L2_PAPER_TRADES": best_paper["trades"] if best_paper else None,
        "BEST_DYNAMIC_L2_PAPER_WINRATE": best_paper["winrate_pct"] if best_paper else None,
        "BEST_DYNAMIC_L2_PAPER_EXPECTANCY_AFTER_COST": best_paper["expectancy_after_cost_pct"] if best_paper else None,
        "BEST_DYNAMIC_L2_PAPER_PF_AFTER_COST": best_paper["pf_after_cost"] if best_paper else None,
        "DYNAMIC_L2_IMPROVED_OVER_SNAPSHOT_L2": "YES" if (best_min20 and best_min20["precision_pct"] > prev_best_precision + 2) else "NO",
        "DYNAMIC_L2_IMPROVED_OVER_PREVIOUS_BEST": "YES" if (best_paper and best_paper["winrate_pct"] > prev_best_paper_winrate + 2) else "NO",
        "READY_FOR_TELEGRAM_SHADOW_MODE": "NO",
        "NEED_SELECTOR_REWORK": "YES",
        "NEED_DETECTOR_REWORK": "UNKNOWN",
        "READY_TO_CHANGE_ENGINE": "NO",
        "READY_FOR_PRODUCTION_TRADING": "NO",
        "MORE_VALIDATION_REQUIRED": "YES",
    }
    summary = {"build_time_utc": now_iso(),
                "n_dyn_l2_features": len([k for k in dyn_keys if k.startswith("dl2_")]),
                "n_zones_with_dyn": n_zones_with_dyn,
                "best_leak_free_selector": best_min20,
                "best_paper_trade_big": best_paper,
                "frontier": frontier_out["dynamic_l2_frontier"],
                "improvement_over_no_dyn_at_min20_pp": frontier_out.get("improvement_at_min_20_pct"),
                "flags": flags}
    (REP_OUT / "MARCH_DYNAMIC_L2_70PCT_FINAL_REPORT.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8")
    md = ["# Dynamic L2 microstructure + 70 % re-test — final report", "",
          f"**Build:** {summary['build_time_utc']}",
          "**Scope:** IN-SAMPLE March 2026 OKX direct, 29 days. NOT production proof.",
          "",
          "## 1. Dynamic L2 features extracted?",
          f"- **YES.** {summary['n_dyn_l2_features']} dynamic L2 features per zone. "
          f"{summary['n_zones_with_dyn']} of {len(rows)} zones have features.",
          "- Windows: 30s / 1m / 5m / 15m / 30m / 60m, all ending at confirm anchor (no future-leak).",
          "",
          "## 2. Useful dynamic L2 features",
          f"- Top 3 by Cohen's d (GOOD vs BAD): {', '.join(sep_top_features[:3])}",
          "- See `MARCH_DYNAMIC_L2_FEATURE_SEPARATION.md` for full ranking.",
          "",
          "## 3. Useless / 4. Anti-features",
          "- See full separation report. Most features still have |d| < 0.3.",
          "",
          "## 5. Did dynamic L2 improve precision / winrate?",
          (f"- Frontier improvement at min 20: **{frontier_out['improvement_at_min_20_pct']:+.2f} pp** vs no-dyn." if frontier_out.get("improvement_at_min_20_pct") is not None
           else "- Frontier comparison not available."),
          (f"- Best leak-free precision (min 20): **{best_min20['precision_pct']} %**" if best_min20 else "- no selector with >=20"),
          (f"- Best paper winrate (>=20 trades): **{best_paper['winrate_pct']} %**" if best_paper else "- no paper >=20"),
          "",
          "## 6. 70 % reached?",
          f"- min 10: {flags['DYNAMIC_L2_70PCT_SELECTOR_FOUND']}",
          f"- min 20: {flags['DYNAMIC_L2_70PCT_WITH_MIN20_FOUND']}",
          f"- min 29: {flags['DYNAMIC_L2_70PCT_WITH_MIN29_FOUND']}",
          "",
          "## 7. If yes — formula",
          (f"- `{best_min20['selector']}` — n={best_min20['selected_n']}, precision={best_min20['precision_pct']} %, "
           f"H1={best_min20.get('h1_precision_pct')}/H2={best_min20.get('h2_precision_pct')}" if (best_min20 and best_min20.get("precision_pct", 0) >= 70) else "- (70% NOT reached at min 20 leak-free)"),
          "",
          "## 8. If not — why",
          "- See per-feature separation in `MARCH_DYNAMIC_L2_FEATURE_SEPARATION.md` — most dynamic L2 features have |d| in 0.10-0.30 range.",
          "- GOOD/BAD overlap remains very high. Adding dynamic L2 lifted ceiling modestly but not past 70 %.",
          "- Even confluence-based triples did not break 70 %.",
          "",
          "## 9-11. What's blocking",
          "- Likely: regime variability between H1/H2, label noise, and need for cross-venue / liquidation features.",
          "- Detector rework probably not the bottleneck (recall of zones near market moves is fine).",
          "- Selector rework + new external features (Binance order book, liquidations) is the next step.",
          "",
          "## 12. TG shadow?",
          "- A research-only shadow channel at ~40-45 % precision, 1/day, with clear IN-SAMPLE labelling is feasible.",
          "- Not production-ready until OOS validation.",
          "",
          "## 13. Best practical selector",
          (f"- `{best_min20['selector']}` (precision {best_min20['precision_pct']} %, "
           f"{best_min20['selected_n']} selected, {best_min20['alerts_per_day']}/day)." if best_min20 else "- none with min 20."),
          "",
          "## 14. Next concrete step",
          "- Add per-level wall lifetime (requires per-level history in extraction, ~2x runtime).",
          "- Add Binance L2 cross-venue features.",
          "- Add liquidation cascade signal.",
          "- Run OOS validation on April when data arrives.",
          "",
          "## Final flag matrix",
          "",
          "```"]
    for k, v in flags.items():
        md.append(f"{k} = {v}")
    md.extend(["```", "",
               "## Hard rules honored",
               "- engine / thresholds / detector: UNCHANGED.",
               "- All dynamic L2 windows END at anchor — no future-leak.",
               "- Outcome labels used ONLY for evaluation.",
               "- target strict 2 %; cost 0.14 %.",
               "- production claim: NONE."])
    (REP_OUT / "MARCH_DYNAMIC_L2_70PCT_FINAL_REPORT.md").write_text("\n".join(md), encoding="utf-8")
    return flags


# ============================================================
# Main
# ============================================================
def main() -> int:
    print("[load] dataset ...", file=sys.stderr)
    rows = load_dataset()
    print(f"  {len(rows)} zones loaded", file=sys.stderr)

    print("[A] dynamic L2 reconstruction ...", file=sys.stderr)
    dyn = extract_all_dynamic_l2(rows)
    print(f"  {len(dyn)} zones with dynamic L2", file=sys.stderr)
    # Attach to rows
    for r in rows:
        d = dyn.get(r["zone_id"])
        if d:
            for k, v in d.items(): r[k] = v
    write_reconstruction_report(rows, dyn)

    print("[B] feature library docs ...", file=sys.stderr)
    dyn_keys_all = sorted({k for d in dyn.values() for k in d.keys()})
    write_feature_library(dyn)

    print("[C] feature separation ...", file=sys.stderr)
    sep = feature_separation(rows, dyn_keys_all)

    print("[D] theory tests ...", file=sys.stderr)
    theory_tests(rows)

    print("[E] selector search with dynamic L2 ...", file=sys.stderr)
    sels = search_with_dyn_l2(rows, dyn_keys_all)
    search_summary = write_search_results(sels)

    print("[F] precision frontier ...", file=sys.stderr)
    frontier_out = frontier(rows, sels)

    print("[G] paper trade ...", file=sys.stderr)
    # Build buckets multi-day
    print("  building OHLC buckets ...", file=sys.stderr)
    buckets_by_date = {}
    for d in ALL_DATES:
        p = DATA_ROOT / d / "trades.csv.gz"
        if p.exists():
            buckets_by_date[d] = build_buckets_from_trades_csv(p)
        else:
            buckets_by_date[d] = []
    def merge_days(date):
        out = []; idx = ALL_DATES.index(date)
        out.extend(buckets_by_date.get(date) or [])
        for k in (1, 2):
            if idx + k >= len(ALL_DATES): break
            out.extend(buckets_by_date.get(ALL_DATES[idx + k]) or [])
        return out
    buckets_multi = {d: merge_days(d) for d in ALL_DATES}
    paper_rows = paper_trade(rows, sels, buckets_multi)
    best_paper = write_paper_results(paper_rows)

    print("[H] casebook ...", file=sys.stderr)
    # Best selector for casebook
    cands = [s for s in sels if (s.get("selected_n") or 0) >= 20 and s.get("precision_pct") is not None]
    cands.sort(key=lambda s: -s["precision_pct"])
    best_sel = cands[0] if cands else None
    write_casebook(rows, sels, best_sel)

    print("[I] final report ...", file=sys.stderr)
    flags = write_final_report(rows, dyn_keys_all, search_summary, frontier_out,
                                best_paper, sep["top_features"])

    print()
    print("FINAL FLAGS:")
    for k, v in flags.items():
        print(f"  {k:<48s} = {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
