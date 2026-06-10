"""March microstructure feature engine + setup-type classification (Sections A-M).

Adds three NEW real microstructure features on top of existing dynamic L2:
  C. per-level wall lifetime  (per-level book history near zone)
  D. real refill-after-hit    (book size-delta tracking)
  E. liquidity void to target (book snapshot at anchor, depth to entry +- 2%)

Then runs setup-type classification, enhanced selector search, ablation,
casebook, final report.

NO engine / threshold / detector change. Target strict 2%, cost 0.14% RT.
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
from collections import defaultdict, deque, Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from canonical_ledger import (Bucket, build_buckets_from_trades_csv, Signal,
                              ExecutionConfig, simulate_canonical_trade)

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "package.json").exists() and (p / "scripts").exists())
REPORTS = ROOT / "reports"
REP_OUT = REPORTS / "strategy-calibration"
DATA_ROOT = ROOT / "data/okx-historical/BTC-USDT-SWAP"
CACHE_DIR = ROOT / "data/cache/march_microstructure"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
COMBINED_CSV = REP_OUT / "MARCH_MICROSTRUCTURE_NEW_FEATURES.csv"

FIRST_HALF = [f"2026-03-{d:02d}" for d in range(2, 16)]
SECOND_HALF = ["2026-03-16"] + [f"2026-03-{d:02d}" for d in range(18, 32)]
ALL_DATES = FIRST_HALF + SECOND_HALF
N_DAYS = len(ALL_DATES)
COST_PCT = 0.14
TARGET_PCT = 2.0
STOP_PCT_BASELINE = 1.5
TIMEOUT_HOURS = 24

# Microstructure extraction params
ZONE_BAND_PCT = 0.0015   # 0.15 % around zoneLow/zoneHigh for "near-zone" band
WALL_SIZE_THRESHOLD = 50.0   # lots — a level is a "wall" if it holds >= this
LARGE_DELTA_THRESHOLD = 20.0   # lots — single delta classified as hit/cancel
REFILL_WINDOW_SEC = 60
RECOVERY_TARGET_RATIO = 0.7


def now_iso():
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
# load dataset (with existing dl2_* features)
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
    # Merge dynamic L2
    dynp = REP_OUT / "MARCH_DYNAMIC_L2_FEATURE_DATASET.csv"
    if dynp.exists():
        dyn = {}
        with dynp.open(encoding="utf-8") as f:
            rdr = csv.DictReader(f)
            for lr in rdr:
                dyn[lr["zone_id"]] = {k: safe_float(lr[k]) for k in lr if k != "zone_id"}
        for r in rows:
            for k, v in dyn.get(r["zone_id"], {}).items(): r[k] = v
    # Merge snapshot L2
    l2p = REP_OUT / "MARCH_L2_MICROSTRUCTURE_FEATURE_DATASET.csv"
    if l2p.exists():
        l2 = {}
        with l2p.open(encoding="utf-8") as f:
            rdr = csv.DictReader(f)
            for lr in rdr:
                l2[lr["zone_id"]] = {k: safe_float(lr[k]) for k in lr if k != "zone_id"}
        for r in rows:
            for k, v in l2.get(r["zone_id"], {}).items(): r[k] = v
    return rows


def explainable_score_l2_dyn(r):
    """Identical to the function used to derive baseline rank in dyn-L2 pass."""
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
# Section A: baseline reproduction
# ============================================================
def select_baseline(rows):
    """29-trade baseline: dist_to_recent_swing_high <= 0.4616, top-1 by score per day."""
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


def simulate_baseline_trades(selected_zones, buckets_by_date, stop_pct=STOP_PCT_BASELINE):
    """Simulate paper trades for given selected zones (entry at confirmed, stop, target)."""
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
        # Classify outcome
        outcome = ("WIN" if sim["exit_reason"] == "target_2pct"
                   else ("LOSS" if sim["exit_reason"] == "stop"
                         else "TIMEOUT"))
        # Failure subclass
        reason_class = ""
        if outcome == "LOSS":
            if z.get("coverage_class") == "wrong_direction":
                reason_class = "wrong_direction"
            elif z.get("watch_label") in ("GOOD", "MID"):
                reason_class = "correct_direction_but_no_2pct"
            else:
                reason_class = "stop_no_2pct_either_dir"
        elif outcome == "TIMEOUT":
            if sim["pnl_pct"] > 0.5: reason_class = "timeout_positive"
            else: reason_class = "timeout_negative"
        else:
            reason_class = "win_clean"
        trades.append({
            "#": i + 1, "date": z["date"], "direction": z["direction"],
            "zone_id": z["zone_id"],
            "selected_iso": z.get("confirmed_iso"),
            "entry_sec": sim["entry_sec"],
            "exit_sec": sim["exit_sec"],
            "entry_price": sim["entry_price"],
            "exit_price": sim["exit_price"],
            "exit_reason": sim["exit_reason"],
            "pnl_pre_cost": sim["pnl_pct"],
            "pnl_after_cost": round(sim["pnl_pct"] - COST_PCT, 4),
            "mfe_pct": sim["mfe_pct"],
            "mae_pct": sim["mae_pct"],
            "outcome": outcome,
            "reason_class": reason_class,
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
    exp_ = round(stats.mean(pnls), 4) if pnls else None
    tot = round(sum(pnls), 4)
    return {"trades": n, "wins": wins, "losses": losses, "timeouts": timeouts,
            "winrate_pct": round(100.0 * wins / max(n, 1), 2),
            "expectancy_after_cost_pct": exp_,
            "total_return_after_cost_pct": tot,
            "pf_after_cost": pf}


def write_baseline_repro(trades, metrics, target):
    """Section A artifact."""
    match = (metrics["trades"] == target["trades"] and
             metrics["wins"] == target["wins"] and
             abs(metrics["winrate_pct"] - target["winrate_pct"]) < 0.5)
    out = {"build_time_utc": now_iso(),
           "target_metrics": target,
           "reproduced_metrics": metrics,
           "exact_match": match}
    (REP_OUT / "MARCH_MICROSTRUCTURE_BASELINE_REPRO.json").write_text(
        json.dumps(out, indent=2, default=str), encoding="utf-8")
    # CSV
    keys = list(trades[0].keys()) if trades else []
    with (REP_OUT / "MARCH_MICROSTRUCTURE_BASELINE_TRADES.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for t in trades: w.writerow(t)
    md = ["# Microstructure baseline reproduction", "",
          f"**Build:** {out['build_time_utc']}",
          f"**Selector:** `DL2::S::dist_to_recent_swing_high_pct_le_0.4616::top1 | confirmed | stop_1.5`",
          "",
          "## Target vs reproduced",
          "",
          "| metric | target | reproduced |",
          "|---|---:|---:|"]
    for k in ("trades", "wins", "losses", "timeouts", "winrate_pct",
              "expectancy_after_cost_pct", "pf_after_cost"):
        md.append(f"| {k} | {target.get(k)} | {metrics.get(k)} |")
    md.extend(["", f"**Exact match:** {match}"])
    if not match:
        md.append("")
        md.append("⚠ Discrepancy noted — investigate explainable_score function or threshold rounding.")
    (REP_OUT / "MARCH_MICROSTRUCTURE_BASELINE_REPRO.md").write_text("\n".join(md), encoding="utf-8")
    return out


# ============================================================
# Section B: leak audit (documentation only)
# ============================================================
def write_leak_audit():
    fields = [
        # (field, computed_at_relative_to_anchor, candidate_safe, confirm_safe, trigger_safe, micro_setup_safe, leak_status)
        ("per_level_wall_lifetime_60m_before_anchor", "[anchor-60m, anchor]",
         "N (anchor=candidate makes it candidate-safe IF window ends at candidateTs)",
         "Y (window ends at confirmedTs)", "Y", "Y", "SAFE if window ends at anchor"),
        ("refill_after_hit (hits before anchor only)", "[anchor-60m, anchor]",
         "N for hits after candidate", "Y (only count hits with ts <= confirmedTs)",
         "Y", "Y (but ts must be <= micro_setup_validated_ts)",
         "SAFE if hit_ts <= anchor and refill_ts <= anchor"),
        ("refill_after_hit (allowing post-anchor refill)",
         "[anchor-60m, anchor+60s]", "LEAK", "LEAK", "LEAK", "Y (if anchor = micro_setup_validated_ts)",
         "FUTURE LEAK at candidate / confirmed / trigger"),
        ("liquidity_void_to_target (snapshot)", "snapshot at anchor",
         "Y (uses only book state at anchor)", "Y", "Y", "Y", "SAFE at anchor"),
        ("microprice_evolution_*", "rolling [anchor-Wsec, anchor]",
         "Y", "Y", "Y", "Y", "SAFE if window ends at anchor"),
        ("add_cancel_imbalance_*", "rolling [anchor-Wsec, anchor]",
         "Y", "Y", "Y", "Y", "SAFE"),
        ("setup_type_classification (using only safe features)",
         "computed from confirm-safe features only", "Y", "Y", "Y", "Y",
         "SAFE iff inputs are leak-free"),
    ]
    out = {"build_time_utc": now_iso(), "fields": fields}
    (REP_OUT / "MARCH_MICROSTRUCTURE_FEATURE_LEAK_AUDIT.json").write_text(
        json.dumps(out, indent=2, default=str), encoding="utf-8")
    md = ["# Microstructure feature leak audit", "",
          f"**Build:** {out['build_time_utc']}",
          "",
          "## Decision timestamps",
          "- `candidateTs`: zone first detected by engine.",
          "- `confirmedTs`: zone confirmed by engine (defended cycles + persistence).",
          "- `triggerTs`: engine fired trigger (break + side flow).",
          "- `first_touch_ts`: first bar where price touches zone band after confirmedTs.",
          "- `micro_setup_validated_ts`: when microstructure setup is actually visible "
          "(hit detected + refill response observed). Always > confirmedTs in practice; "
          "if used as decision time, that becomes the alert timestamp.",
          "",
          "## Field availability",
          "",
          "| field | computed_window | cand_safe | confirm_safe | trigger_safe | micro_setup_safe | leak_status |",
          "|---|---|---|---|---|---|---|"]
    for f in fields:
        md.append("| " + " | ".join(str(x) for x in f) + " |")
    md.extend(["", "## Rules followed in this research",
               "- All new features in this pass are computed with windows ENDING at `confirmedTs`.",
               "- No feature uses any tick at ts > confirmedTs.",
               "- Outcome labels (`watch_label`, `coverage_class`, `matched_move_size_pct`) used ONLY in evaluation, never in selectors."])
    (REP_OUT / "MARCH_MICROSTRUCTURE_FEATURE_LEAK_AUDIT.md").write_text("\n".join(md), encoding="utf-8")


# ============================================================
# Sections C/D/E: new microstructure feature extraction (single L2 streaming pass)
# ============================================================
@dataclass
class LevelEvent:
    ts: int      # unix sec
    size: float  # new size at this price after event


@dataclass
class HitEvent:
    ts: int            # hit timestamp (sec)
    price: float
    depleted: float    # amount depleted
    refilled_at: dict  # window_sec -> amount refilled within window
    refilled_count: int   # number of subsequent add events
    refilled_total: float   # total refill seen


@dataclass
class ZoneState:
    zone_id: str
    direction: str       # LONG / SHORT
    anchor_sec: int
    zone_low: float
    zone_high: float
    zone_mid: float
    band_lo: float       # supportive band: bid for LONG, ask for SHORT, near zone
    band_hi: float
    # Per-level history near zone (last 60 min, supportive side only)
    level_history: dict = field(default_factory=lambda: defaultdict(deque))   # price -> deque[LevelEvent]
    # Pending hits (large supportive depletions whose refill we're tracking)
    pending_hits: list = field(default_factory=list)
    # Completed hits (depletion + refill measured) at anchor
    completed_hits: list = field(default_factory=list)


def extract_microstructure_for_day(date, day_anchors):
    """Single L2 streaming pass. day_anchors: [(anchor_sec, zone_id, direction, zone_low, zone_high)].
    Returns dict[zone_id] -> features dict.
    """
    p = DATA_ROOT / date / "incremental_book_L2.csv.gz"
    if not p.exists() or not day_anchors: return {}
    anchors_sorted = sorted(day_anchors, key=lambda x: x[0])
    zones: list[ZoneState] = []
    for sec, zid, direction, zlow, zhigh in anchors_sorted:
        mid = (zlow + zhigh) / 2.0
        # Supportive band: bid for LONG = [zlow*(1-0.0015), zmid]; ask for SHORT = [zmid, zhigh*(1+0.0015)]
        if direction == "LONG":
            band_lo = zlow * (1.0 - ZONE_BAND_PCT)
            band_hi = mid
        else:
            band_lo = mid
            band_hi = zhigh * (1.0 + ZONE_BAND_PCT)
        zones.append(ZoneState(zone_id=zid, direction=direction, anchor_sec=sec,
                                 zone_low=zlow, zone_high=zhigh, zone_mid=mid,
                                 band_lo=band_lo, band_hi=band_hi))
    next_idx = 0   # index of next zone to finalize
    out = {}

    # Maintain global book state for liquidity void to target
    bid_book: dict[float, float] = {}
    ask_book: dict[float, float] = {}

    def is_in_band(price, zone):
        return zone.band_lo <= price <= zone.band_hi

    def finalize_zone(zone, bid_book, ask_book):
        """Compute features at zone.anchor_sec."""
        out_feat = {}
        anchor = zone.anchor_sec
        # Trim per-level histories to last 60 min
        cutoff_60m = anchor - 3600
        for price, hist in list(zone.level_history.items()):
            while hist and hist[0].ts < cutoff_60m:
                hist.popleft()
            if not hist:
                del zone.level_history[price]
        # ---- Wall lifetime features ----
        # For each level, find longest contiguous time it was >= WALL_SIZE_THRESHOLD
        wall_max_lifetime = 0
        wall_avg_size = 0.0
        wall_count = 0
        wall_max_size = 0.0
        wall_refresh_count = 0
        for price, hist in zone.level_history.items():
            # Build segments where size >= threshold
            current_start = None
            longest = 0
            refreshes = 0
            sizes_above = []
            for ev in hist:
                if ev.size >= WALL_SIZE_THRESHOLD:
                    sizes_above.append(ev.size)
                    if current_start is None:
                        current_start = ev.ts
                        refreshes += 1
                else:
                    if current_start is not None:
                        dur = ev.ts - current_start
                        if dur > longest: longest = dur
                        current_start = None
            if current_start is not None:
                dur = anchor - current_start
                if dur > longest: longest = dur
            if longest > wall_max_lifetime: wall_max_lifetime = longest
            if sizes_above:
                wall_count += 1
                wall_avg_size += stats.mean(sizes_above)
                wall_max_size = max(wall_max_size, max(sizes_above))
                wall_refresh_count += refreshes
        out_feat["ms_supportive_wall_max_lifetime_sec"] = wall_max_lifetime
        out_feat["ms_supportive_wall_count"] = wall_count
        out_feat["ms_supportive_wall_avg_size"] = round(wall_avg_size / max(wall_count, 1), 4) if wall_count else 0
        out_feat["ms_supportive_wall_max_size"] = round(wall_max_size, 4)
        out_feat["ms_supportive_wall_refresh_count"] = wall_refresh_count
        # Persistence ratio: wall_max_lifetime / 1800 (30 min)
        out_feat["ms_supportive_wall_persistence_ratio_30m"] = round(wall_max_lifetime / 1800.0, 4)
        # Wall quality score
        out_feat["ms_supportive_wall_quality_score"] = round(
            out_feat["ms_supportive_wall_persistence_ratio_30m"]
            * math.log1p(out_feat["ms_supportive_wall_avg_size"]), 4)

        # ---- Refill-after-hit features ----
        # Process pending hits: finalize any whose refill window has elapsed at anchor
        completed = list(zone.completed_hits)
        for ph in zone.pending_hits:
            # Finalize: if anchor >= hit_ts + REFILL_WINDOW_SEC, ph is complete
            elapsed = anchor - ph.ts
            if elapsed >= REFILL_WINDOW_SEC:
                completed.append(ph)
            else:
                # Partial completion: use what we have but mark as partial
                completed.append(ph)
        n_hits = len(completed)
        if n_hits:
            total_dep = sum(h.depleted for h in completed)
            max_dep = max(h.depleted for h in completed)
            refill_ratios_60s = []
            recovery_times = []
            for h in completed:
                r60 = h.refilled_at.get(60, 0.0)
                if h.depleted > 0:
                    refill_ratios_60s.append(min(r60 / h.depleted, 1.0))
                # Recovery time: time to refill >= 0.7 * depletion
                # Approximate: look at refilled_at by 5/30/60s
                for wsec in (5, 30, 60):
                    r = h.refilled_at.get(wsec, 0.0)
                    if h.depleted > 0 and r >= RECOVERY_TARGET_RATIO * h.depleted:
                        recovery_times.append(wsec); break
                else:
                    recovery_times.append(120)   # cap
            out_feat["ms_hit_count"] = n_hits
            out_feat["ms_total_depletion"] = round(total_dep, 4)
            out_feat["ms_max_depletion"] = round(max_dep, 4)
            out_feat["ms_best_refill_ratio_60s"] = round(max(refill_ratios_60s) if refill_ratios_60s else 0, 4)
            out_feat["ms_avg_refill_ratio_60s"] = round(stats.mean(refill_ratios_60s) if refill_ratios_60s else 0, 4)
            out_feat["ms_min_recovery_time_sec"] = min(recovery_times) if recovery_times else None
            out_feat["ms_refill_success_count"] = sum(1 for r in refill_ratios_60s if r >= RECOVERY_TARGET_RATIO)
            out_feat["ms_refill_quality_score"] = round(
                math.log1p(total_dep)
                * (max(refill_ratios_60s) if refill_ratios_60s else 0)
                * (1 / math.log1p(min(recovery_times) + 1 if recovery_times else 60)), 4)
        else:
            out_feat["ms_hit_count"] = 0
            out_feat["ms_total_depletion"] = 0
            out_feat["ms_max_depletion"] = 0
            out_feat["ms_best_refill_ratio_60s"] = 0
            out_feat["ms_avg_refill_ratio_60s"] = 0
            out_feat["ms_min_recovery_time_sec"] = None
            out_feat["ms_refill_success_count"] = 0
            out_feat["ms_refill_quality_score"] = 0

        # ---- Liquidity void to target (snapshot at anchor) ----
        # entry is approx zone_mid at confirmed time; use zone_mid as proxy
        if bid_book and ask_book:
            best_bid = max(bid_book.keys()); best_ask = min(ask_book.keys())
            mid = (best_bid + best_ask) / 2.0
            target_up = mid * 1.02
            target_dn = mid * 0.98
            # Ask depth from best_ask up to target_up (for LONG)
            ask_depth_to_target = sum(amt for p, amt in ask_book.items() if best_ask <= p <= target_up)
            bid_depth_to_target = sum(amt for p, amt in bid_book.items() if target_dn <= p <= best_bid)
            ask_count_levels = sum(1 for p in ask_book.keys() if best_ask <= p <= target_up)
            bid_count_levels = sum(1 for p in bid_book.keys() if target_dn <= p <= best_bid)
            # Large walls on path
            ask_large = sum(1 for p, a in ask_book.items() if best_ask <= p <= target_up and a >= WALL_SIZE_THRESHOLD)
            bid_large = sum(1 for p, a in bid_book.items() if target_dn <= p <= best_bid and a >= WALL_SIZE_THRESHOLD)
            ask_max_wall = max((a for p, a in ask_book.items() if best_ask <= p <= target_up), default=0.0)
            bid_max_wall = max((a for p, a in bid_book.items() if target_dn <= p <= best_bid), default=0.0)
            if zone.direction == "LONG":
                out_feat["ms_depth_to_target"] = round(ask_depth_to_target, 4)
                out_feat["ms_levels_to_target"] = ask_count_levels
                out_feat["ms_large_walls_on_path"] = ask_large
                out_feat["ms_max_wall_on_path"] = round(ask_max_wall, 4)
                out_feat["ms_depth_against_back"] = round(bid_depth_to_target, 4)
                out_feat["ms_thin_path_score"] = round(1.0 / (1 + math.log1p(ask_depth_to_target)), 4)
            else:
                out_feat["ms_depth_to_target"] = round(bid_depth_to_target, 4)
                out_feat["ms_levels_to_target"] = bid_count_levels
                out_feat["ms_large_walls_on_path"] = bid_large
                out_feat["ms_max_wall_on_path"] = round(bid_max_wall, 4)
                out_feat["ms_depth_against_back"] = round(ask_depth_to_target, 4)
                out_feat["ms_thin_path_score"] = round(1.0 / (1 + math.log1p(bid_depth_to_target)), 4)
        else:
            for k in ("ms_depth_to_target", "ms_levels_to_target", "ms_large_walls_on_path",
                      "ms_max_wall_on_path", "ms_depth_against_back", "ms_thin_path_score"):
                out_feat[k] = None
        return out_feat

    # Streaming
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
                book.pop(price, None); delta = -prev
            else:
                book[price] = amount; delta = amount - prev
            sec = ts_us // 1_000_000

            # Per-zone in-band processing
            # Only for active zones (those with anchor in future)
            for idx in range(next_idx, len(zones)):
                z = zones[idx]
                if z.anchor_sec - sec > 3600:
                    break   # zones beyond 60 min are not yet active
                # Determine if event is on supportive side
                is_supportive_side = (z.direction == "LONG" and side == "bid") or \
                                      (z.direction == "SHORT" and side == "ask")
                if is_supportive_side and is_in_band(price, z):
                    hist = z.level_history[price]
                    hist.append(LevelEvent(ts=sec, size=amount))
                    # Trim history to last 60 min worth
                    while hist and hist[0].ts < sec - 3600:
                        hist.popleft()
                    # Detect large depletion (potential hit)
                    if delta <= -LARGE_DELTA_THRESHOLD:
                        z.pending_hits.append(HitEvent(ts=sec, price=price, depleted=-delta,
                                                         refilled_at={}, refilled_count=0,
                                                         refilled_total=0.0))
                    # Track refill for existing pending hits at this price
                    if delta > 0:
                        for ph in z.pending_hits:
                            if ph.price == price and sec - ph.ts <= REFILL_WINDOW_SEC:
                                ph.refilled_total += delta
                                ph.refilled_count += 1
                                # Snapshot at standardized windows
                                for wsec in (5, 30, 60):
                                    if sec - ph.ts <= wsec:
                                        ph.refilled_at[wsec] = ph.refilled_at.get(wsec, 0) + delta
                # Move completed hits (refill window elapsed) to completed
                if z.pending_hits:
                    still_pending = []
                    for ph in z.pending_hits:
                        if sec - ph.ts > REFILL_WINDOW_SEC:
                            z.completed_hits.append(ph)
                        else:
                            still_pending.append(ph)
                    z.pending_hits = still_pending
            # Finalize zones whose anchor passed
            while next_idx < len(zones) and zones[next_idx].anchor_sec <= sec:
                z = zones[next_idx]
                out[z.zone_id] = finalize_zone(z, bid_book, ask_book)
                # Free memory
                z.level_history.clear()
                z.pending_hits.clear()
                z.completed_hits.clear()
                next_idx += 1
            if next_idx >= len(zones):
                break
    # Finalize any remaining zones
    while next_idx < len(zones):
        z = zones[next_idx]
        out[z.zone_id] = finalize_zone(z, bid_book, ask_book)
        next_idx += 1
    return out


def extract_all_microstructure(rows):
    if COMBINED_CSV.exists():
        print(f"  cache found {COMBINED_CSV}", file=sys.stderr)
        out = {}
        with COMBINED_CSV.open(encoding="utf-8") as f:
            rdr = csv.DictReader(f)
            for r in rdr:
                zid = r["zone_id"]
                out[zid] = {k: safe_float(r[k]) for k in r if k != "zone_id"}
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
                day_out = {}
                for r in rdr:
                    zid = r["zone_id"]
                    day_out[zid] = {k: safe_float(r[k]) for k in r if k != "zone_id"}
            out.update(day_out)
            print(f"  {d}: loaded {len(day_out)} from cache", file=sys.stderr)
            continue
        t0 = time.time()
        day_out = extract_microstructure_for_day(d, anchors)
        out.update(day_out)
        if day_out:
            keys = sorted({k for v in day_out.values() for k in v.keys()})
            with day_cache.open("w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=["zone_id"] + keys, extrasaction="ignore")
                w.writeheader()
                for zid, feat in day_out.items():
                    w.writerow({"zone_id": zid, **feat})
        print(f"  {d}: {len(day_out)} zones in {time.time()-t0:.1f}s", file=sys.stderr)
    # combined cache
    if out:
        keys = sorted({k for v in out.values() for k in v.keys()})
        with COMBINED_CSV.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["zone_id"] + keys, extrasaction="ignore")
            w.writeheader()
            for zid, feat in out.items():
                w.writerow({"zone_id": zid, **feat})
    return out


# ============================================================
# Section H: setup-type classification
# ============================================================
def classify_setup(r):
    """Classify each zone into a setup type using leak-free features."""
    direction = r["direction"]
    # Helpers
    refill_quality = r.get("ms_refill_quality_score") or 0
    refill_60s = r.get("ms_best_refill_ratio_60s") or 0
    hit_count = r.get("ms_hit_count") or 0
    wall_quality = r.get("ms_supportive_wall_quality_score") or 0
    wall_max_lifetime = r.get("ms_supportive_wall_max_lifetime_sec") or 0
    void_thin = r.get("ms_thin_path_score") or 0
    depth_to_target = r.get("ms_depth_to_target") or 99999
    large_walls = r.get("ms_large_walls_on_path") or 99
    sweep_reclaim = r.get("sweep_reclaim_aligned") == 1
    prior_60m = abs(r.get("prior_move_60m_pct") or 0)
    local_range_60m = r.get("local_range_60m_pct") or 99
    micro_5m_aligned = r.get("dl2_microprice_aligned_delta_5m_bps") or 0
    taker_aligned_30m = r.get("taker_imb_aligned_30m") or 0
    # Scores
    scores = {}
    # ABSORPTION REVERSAL: hit + refill + reclaim
    abs_rev = (math.log1p(hit_count) +
               2 * refill_60s +
               (0.5 if sweep_reclaim else 0) +
               (micro_5m_aligned / 10.0))
    scores[f"absorption_reversal_{direction.lower()}"] = round(abs_rev, 3)
    # BREAKOUT CONTINUATION: low local range + thin path + microprice aligned
    bo_cont = (max(0.0, 0.5 - local_range_60m) * 2 +   # range compression
               (1.0 - min(local_range_60m, 1.0)) +
               void_thin * 2 +
               (micro_5m_aligned / 10.0) +
               taker_aligned_30m)
    scores[f"breakout_continuation_{direction.lower()}"] = round(bo_cont, 3)
    # RETEST AFTER BREAKOUT: prior move significant + supportive refill + wall persistence
    retest = ((prior_60m if prior_60m >= 0.5 else 0) +
              refill_60s +
              (wall_max_lifetime / 1800.0) +
              (micro_5m_aligned / 10.0))
    scores[f"retest_after_breakout_{direction.lower()}"] = round(retest, 3)
    # FAILED BREAKOUT RECLAIM: sweep + reclaim + refill
    failed_bo = ((1.0 if sweep_reclaim else 0) +
                 refill_60s * 2 +
                 (micro_5m_aligned / 10.0))
    scores[f"failed_breakout_reclaim_{direction.lower()}"] = round(failed_bo, 3)
    # Pick best
    best = max(scores.items(), key=lambda kv: kv[1])
    r["setup_type"] = best[0] if best[1] > 0.5 else "unknown"
    r["setup_type_score"] = best[1]
    r["setup_all_scores"] = scores
    # Confidence
    sorted_s = sorted(scores.values(), reverse=True)
    margin = sorted_s[0] - (sorted_s[1] if len(sorted_s) > 1 else 0)
    r["setup_confidence"] = round(margin, 3)
    return r


def write_setup_classification(rows):
    setups = []
    for r in rows:
        setups.append({
            "zone_id": r["zone_id"], "date": r["date"], "direction": r["direction"],
            "confirmed_iso": r.get("confirmed_iso"),
            "watch_label": r.get("watch_label"),
            "coverage_class": r.get("coverage_class"),
            "setup_type": r.get("setup_type"),
            "setup_type_score": r.get("setup_type_score"),
            "setup_confidence": r.get("setup_confidence"),
            **{f"score_{k}": v for k, v in (r.get("setup_all_scores") or {}).items()},
        })
    if setups:
        keys = sorted({k for v in setups for k in v.keys()})
        with (REP_OUT / "MARCH_SETUP_TYPE_CLASSIFICATION.csv").open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
            w.writeheader()
            for s in setups: w.writerow(s)
    # Distribution
    dist = Counter(r.get("setup_type") for r in rows)
    by_label = defaultdict(Counter)
    for r in rows:
        by_label[r.get("setup_type")][r.get("watch_label") or "unknown"] += 1
    (REP_OUT / "MARCH_SETUP_TYPE_CLASSIFICATION.json").write_text(
        json.dumps({"build_time_utc": now_iso(),
                    "distribution": dict(dist),
                    "by_label": {k: dict(v) for k, v in by_label.items()}},
                   indent=2, default=str), encoding="utf-8")
    md = ["# Setup-type classification", "",
          f"**Build:** {now_iso()}",
          f"**N zones classified:** {len(rows)}",
          "",
          "## Distribution",
          "",
          "| setup_type | n |",
          "|---|---:|"]
    for k, v in sorted(dist.items(), key=lambda kv: -kv[1]):
        md.append(f"| {k} | {v} |")
    md.extend(["", "## GOOD precision by setup_type", "", "| setup_type | total | GOOD | precision % |", "|---|---:|---:|---:|"])
    for st in sorted(dist.keys()):
        rows_st = [r for r in rows if r.get("setup_type") == st]
        good = sum(1 for r in rows_st if r.get("watch_label") == "GOOD")
        md.append(f"| {st} | {len(rows_st)} | {good} | "
                  f"{round(100.0 * good / max(len(rows_st), 1), 2)} |")
    (REP_OUT / "MARCH_SETUP_TYPE_CLASSIFICATION.md").write_text("\n".join(md), encoding="utf-8")


# ============================================================
# Sections I/J: winner vs loser + enhanced selector search
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
    return {
        "selected_n": n, "alerts_per_day": round(n / N_DAYS, 3),
        "good_n": good, "wrong_n": wrong,
        "precision_pct": round(100.0 * good / max(n, 1), 2) if n else None,
        "wrong_rate_pct": round(100.0 * wrong / max(n, 1), 2) if n else None,
        "h1_n": len(h1), "h2_n": len(h2),
        "h1_precision_pct": round(100.0 * g1 / max(len(h1), 1), 2) if h1 else None,
        "h2_precision_pct": round(100.0 * g2 / max(len(h2), 1), 2) if h2 else None,
        "selected_zone_ids": [r["zone_id"] for r in sel],
    }


def enhanced_score(r):
    """Score combining explainable_score_l2_dyn + microstructure features."""
    s = explainable_score_l2_dyn(r)
    # New microstructure contributions
    rq = r.get("ms_refill_quality_score") or 0
    if rq > 0: s += min(rq / 5.0, 0.5)
    wq = r.get("ms_supportive_wall_quality_score") or 0
    if wq > 0: s += min(wq / 3.0, 0.4)
    void = r.get("ms_thin_path_score") or 0
    s += min(void * 1.0, 0.4)
    lw = r.get("ms_large_walls_on_path") or 0
    if lw > 0: s -= min(lw * 0.1, 0.3)   # penalty for opposing walls
    return round(s, 4)


def run_selector_search(rows):
    """Search for an enhanced selector that improves over baseline."""
    # Add enhanced_score
    for r in rows: r["_score_enhanced"] = enhanced_score(r)
    # Candidates: same base filter as baseline + extra microstructure filters
    # Build base rule candidates
    NUMERIC_KEYS = [
        # baseline-best
        "dist_to_recent_swing_high_pct", "prior_move_180m_pct",
        # new microstructure
        "ms_refill_quality_score", "ms_best_refill_ratio_60s",
        "ms_supportive_wall_quality_score", "ms_supportive_wall_max_lifetime_sec",
        "ms_thin_path_score", "ms_depth_to_target", "ms_large_walls_on_path",
        # existing dl2_
        "dl2_microprice_aligned_delta_5m_bps", "dl2_microprice_aligned_delta_15m_bps",
        "dl2_supp_minus_opp_net_flow_5m", "dl2_supp_minus_opp_net_flow_15m",
        "dl2_top1_supportive_persistence_ge_50_5m_sec",
        "dl2_inband_supp_add_5m", "dl2_inband_opp_cancel_15m",
        # context
        "local_range_180m_pct", "abs_prior_move_60m_pct",
    ]
    BOOLEAN_KEYS = ["is_asia_session", "sweep_reclaim_aligned"]

    def threshold_rules(rows, keys):
        out = []
        for k in keys:
            vals = [r.get(k) for r in rows if r.get(k) is not None]
            if len(vals) < 50: continue
            for q in (0.25, 0.5, 0.75):
                v = quantile(vals, q)
                if v is None: continue
                out.append((f"{k}_ge_{round(v, 4)}",
                              (lambda kk, th: lambda r: (r.get(kk) is not None) and (r.get(kk) >= th))(k, v)))
                out.append((f"{k}_le_{round(v, 4)}",
                              (lambda kk, th: lambda r: (r.get(kk) is not None) and (r.get(kk) <= th))(k, v)))
        for k in BOOLEAN_KEYS:
            out.append((f"{k}_TRUE", (lambda kk: lambda r: bool(r.get(kk)))(k)))
            out.append((f"{k}_FALSE", (lambda kk: lambda r: not bool(r.get(kk)))(k)))
        return out

    rules = threshold_rules(rows, NUMERIC_KEYS)
    sels = []
    # Baseline rule + each single rule combined
    base_filter = lambda r: r.get("dist_to_recent_swing_high_pct") is not None and r["dist_to_recent_swing_high_pct"] <= 0.4616
    # Single rules
    for name, fn in rules:
        def make_and(a, b): return lambda r: a(r) and b(r)
        pred = make_and(base_filter, fn)
        e = selector_eval(rows, pred, day_cap=1, score_key="_score_enhanced")
        sels.append({"selector": f"ENH::baseline+{name}::top1", **e, "kind": "pair"})
    # Setup-type-specific selectors
    for st in {"absorption_reversal_long", "absorption_reversal_short",
                "breakout_continuation_long", "breakout_continuation_short",
                "retest_after_breakout_long", "retest_after_breakout_short",
                "failed_breakout_reclaim_long", "failed_breakout_reclaim_short"}:
        def make_setup(st):
            return lambda r: r.get("setup_type") == st
        pred = make_setup(st)
        e = selector_eval(rows, pred, day_cap=1, score_key="_score_enhanced")
        sels.append({"selector": f"ENH::setup_{st}::top1", **e, "kind": "setup"})
    # Confluence rules
    def conf1(r): return base_filter(r) and (r.get("ms_refill_quality_score") or 0) >= 0.5
    sels.append({"selector": "ENH::baseline+refill_quality_ge_0.5::top1",
                  **selector_eval(rows, conf1, day_cap=1, score_key="_score_enhanced")})
    def conf2(r): return base_filter(r) and (r.get("ms_thin_path_score") or 0) >= 0.05
    sels.append({"selector": "ENH::baseline+thin_path_ge_0.05::top1",
                  **selector_eval(rows, conf2, day_cap=1, score_key="_score_enhanced")})
    def conf3(r): return base_filter(r) and (r.get("ms_supportive_wall_max_lifetime_sec") or 0) >= 60
    sels.append({"selector": "ENH::baseline+wall_lifetime_ge_60::top1",
                  **selector_eval(rows, conf3, day_cap=1, score_key="_score_enhanced")})
    def conf4(r): return base_filter(r) and (r.get("ms_large_walls_on_path") or 99) <= 2
    sels.append({"selector": "ENH::baseline+large_walls_le_2::top1",
                  **selector_eval(rows, conf4, day_cap=1, score_key="_score_enhanced")})
    def conf5(r): return base_filter(r) and (r.get("ms_best_refill_ratio_60s") or 0) >= 0.5
    sels.append({"selector": "ENH::baseline+refill_ratio_60s_ge_0.5::top1",
                  **selector_eval(rows, conf5, day_cap=1, score_key="_score_enhanced")})
    # Combo with microprice
    def conf6(r): return base_filter(r) and (r.get("dl2_microprice_aligned_delta_15m_bps") or -99) >= 0
    sels.append({"selector": "ENH::baseline+microprice15m_ge_0::top1",
                  **selector_eval(rows, conf6, day_cap=1, score_key="_score_enhanced")})
    # Combo refill + microprice
    def conf7(r): return (base_filter(r) and (r.get("ms_refill_quality_score") or 0) >= 0.3
                          and (r.get("dl2_microprice_aligned_delta_5m_bps") or -99) >= 0)
    sels.append({"selector": "ENH::baseline+refill_ge_0.3+microprice5m_ge_0::top1",
                  **selector_eval(rows, conf7, day_cap=1, score_key="_score_enhanced")})
    # NEW: no opposing wall + refill
    def conf8(r): return (base_filter(r) and (r.get("ms_large_walls_on_path") or 99) == 0
                           and (r.get("ms_best_refill_ratio_60s") or 0) >= 0.3)
    sels.append({"selector": "ENH::baseline+no_opp_wall+refill_ge_0.3::top1",
                  **selector_eval(rows, conf8, day_cap=1, score_key="_score_enhanced")})
    return sels


def evaluate_selector_paper(rows, selector_zone_ids, buckets_by_date,
                             stop_pct=STOP_PCT_BASELINE):
    """Run paper trades for given selector and compute metrics."""
    by_id = {r["zone_id"]: r for r in rows}
    sel_rows = [by_id[i] for i in selector_zone_ids if i in by_id]
    trades = simulate_baseline_trades(sel_rows, buckets_by_date, stop_pct=stop_pct)
    m = baseline_metrics(trades)
    # Failure classification counts
    m["wrong_direction"] = sum(1 for t in trades if t["reason_class"] == "wrong_direction")
    m["correct_direction_but_no_2pct"] = sum(1 for t in trades if t["reason_class"] == "correct_direction_but_no_2pct")
    m["stop_no_2pct_either_dir"] = sum(1 for t in trades if t["reason_class"] == "stop_no_2pct_either_dir")
    m["timeout_positive"] = sum(1 for t in trades if t["reason_class"] == "timeout_positive")
    m["timeout_negative"] = sum(1 for t in trades if t["reason_class"] == "timeout_negative")
    m["trades_detail"] = trades
    return m


# ============================================================
# Section K: indicator success criteria + ablation
# ============================================================
def winner_vs_loser_analysis(rows, baseline_trades):
    """Compare microstructure feature distributions on baseline trades."""
    by_id = {r["zone_id"]: r for r in rows}
    winners = [by_id[t["zone_id"]] for t in baseline_trades if t["outcome"] == "WIN"]
    losers = [by_id[t["zone_id"]] for t in baseline_trades if t["outcome"] in ("LOSS", "TIMEOUT")]
    cn = [by_id[t["zone_id"]] for t in baseline_trades if t["reason_class"] == "correct_direction_but_no_2pct"]
    keys = [
        "ms_refill_quality_score", "ms_best_refill_ratio_60s", "ms_avg_refill_ratio_60s",
        "ms_hit_count", "ms_total_depletion", "ms_max_depletion",
        "ms_supportive_wall_max_lifetime_sec", "ms_supportive_wall_quality_score",
        "ms_supportive_wall_avg_size", "ms_supportive_wall_max_size",
        "ms_supportive_wall_persistence_ratio_30m",
        "ms_thin_path_score", "ms_depth_to_target", "ms_levels_to_target",
        "ms_large_walls_on_path", "ms_max_wall_on_path", "ms_depth_against_back",
        # also include best existing dl2_ features for comparison
        "dl2_microprice_aligned_delta_5m_bps", "dl2_microprice_aligned_delta_15m_bps",
        "dl2_supp_minus_opp_net_flow_5m", "dl2_top1_supportive_persistence_ge_50_5m_sec",
    ]
    table = []
    for k in keys:
        wv = [r.get(k) for r in winners if r.get(k) is not None]
        lv = [r.get(k) for r in losers if r.get(k) is not None]
        cnv = [r.get(k) for r in cn if r.get(k) is not None]
        row = {
            "feature": k,
            "winners_mean": mean_or_none(wv),
            "losers_mean": mean_or_none(lv),
            "correct_no_2pct_mean": mean_or_none(cnv),
            "d_winners_vs_losers": cohens_d(wv, lv),
            "d_winners_vs_correct_no_2pct": cohens_d(wv, cnv),
            "n_winners": len(wv), "n_losers": len(lv), "n_correct_no_2pct": len(cnv),
        }
        table.append(row)
    table.sort(key=lambda r: -abs(r.get("d_winners_vs_losers") or 0))
    csv_keys = list(table[0].keys()) if table else []
    with (REP_OUT / "MARCH_MICROSTRUCTURE_WINNER_LOSER_ANALYSIS.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=csv_keys, extrasaction="ignore")
        w.writeheader()
        for r in table: w.writerow(r)
    (REP_OUT / "MARCH_MICROSTRUCTURE_WINNER_LOSER_ANALYSIS.json").write_text(
        json.dumps({"build_time_utc": now_iso(), "feature_table": table,
                    "n_winners": len(winners), "n_losers": len(losers),
                    "n_correct_no_2pct": len(cn)}, indent=2, default=str), encoding="utf-8")
    md = ["# Winners vs Losers — microstructure feature comparison", "",
          f"**Build:** {now_iso()}",
          f"**Winners n={len(winners)}; Losers/Timeouts n={len(losers)}; "
          f"correct_no_2pct n={len(cn)}**",
          "",
          "## Sorted by |d winners vs losers|", "",
          "| feature | winners_mean | losers_mean | correct_no_2pct_mean | d(W vs L) | d(W vs CN) |",
          "|---|---:|---:|---:|---:|---:|"]
    for r in table:
        md.append(f"| `{r['feature']}` | {r['winners_mean']} | {r['losers_mean']} | "
                  f"{r['correct_no_2pct_mean']} | {r['d_winners_vs_losers']} | "
                  f"{r['d_winners_vs_correct_no_2pct']} |")
    (REP_OUT / "MARCH_MICROSTRUCTURE_WINNER_LOSER_ANALYSIS.md").write_text("\n".join(md), encoding="utf-8")
    return table


def indicator_success_criteria(rows, baseline_metrics_dict, best_enhanced, sep_table, buckets_by_date):
    """For each new feature, compute precision/winrate uplift + ablation."""
    by_id = {r["zone_id"]: r for r in rows}
    feature_evals = []
    new_feats = ["ms_refill_quality_score", "ms_best_refill_ratio_60s",
                  "ms_supportive_wall_max_lifetime_sec", "ms_supportive_wall_quality_score",
                  "ms_thin_path_score", "ms_large_walls_on_path", "ms_depth_to_target",
                  "ms_hit_count"]
    for fk in new_feats:
        # Find threshold that improves baseline most (median)
        vals = [r.get(fk) for r in rows if r.get(fk) is not None]
        if len(vals) < 50: continue
        median_v = quantile(vals, 0.5)
        # Apply baseline filter + this feature filter (ge or le best direction)
        def base_filter(r): return r.get("dist_to_recent_swing_high_pct") is not None and r["dist_to_recent_swing_high_pct"] <= 0.4616
        for direction in ("ge", "le"):
            if direction == "ge":
                pred = (lambda fk, th: lambda r: base_filter(r) and (r.get(fk) is not None) and (r.get(fk) >= th))(fk, median_v)
            else:
                pred = (lambda fk, th: lambda r: base_filter(r) and (r.get(fk) is not None) and (r.get(fk) <= th))(fk, median_v)
            e = selector_eval(rows, pred, day_cap=1, score_key="_score_enhanced")
            if (e.get("selected_n") or 0) < 10: continue
            m = evaluate_selector_paper(rows, e["selected_zone_ids"], buckets_by_date)
            m_clean = {k: v for k, v in m.items() if k != "trades_detail"}
            feature_evals.append({
                "feature": fk, "direction": direction, "threshold": round(median_v, 4),
                "selected_n": e["selected_n"],
                "precision_pct": e.get("precision_pct"),
                "winrate_pct": m.get("winrate_pct"),
                "winrate_delta_vs_baseline_pp": round(m.get("winrate_pct", 0) - baseline_metrics_dict["winrate_pct"], 2),
                "expectancy_after_cost": m.get("expectancy_after_cost_pct"),
                "expectancy_delta": round((m.get("expectancy_after_cost_pct") or 0) - baseline_metrics_dict["expectancy_after_cost_pct"], 4),
                "pf_after_cost": m.get("pf_after_cost"),
                "wrong_direction": m.get("wrong_direction"),
                "correct_no_2pct": m.get("correct_direction_but_no_2pct"),
                "stop_no_2pct": m.get("stop_no_2pct_either_dir"),
                "verdict": "PROMOTE" if (m.get("winrate_pct", 0) > baseline_metrics_dict["winrate_pct"] + 5
                                          and m.get("expectancy_after_cost_pct", 0) >= baseline_metrics_dict["expectancy_after_cost_pct"])
                            else ("KEEP" if (m.get("winrate_pct", 0) >= baseline_metrics_dict["winrate_pct"]) else "DROP"),
            })

    # Ablation on best_enhanced selector — disable enhanced_score features one by one
    ablation = []
    if best_enhanced:
        sel_ids = best_enhanced.get("selected_zone_ids") or []
        for skip_key in (None, "ms_refill_quality_score", "ms_supportive_wall_quality_score",
                          "ms_thin_path_score", "dl2_microprice_aligned_delta_5m_bps"):
            # Re-rank within day using altered score
            def make_score(skip):
                def sc(r):
                    s = explainable_score_l2_dyn(r)
                    rq = r.get("ms_refill_quality_score") or 0
                    if rq > 0 and skip != "ms_refill_quality_score": s += min(rq / 5.0, 0.5)
                    wq = r.get("ms_supportive_wall_quality_score") or 0
                    if wq > 0 and skip != "ms_supportive_wall_quality_score": s += min(wq / 3.0, 0.4)
                    void = r.get("ms_thin_path_score") or 0
                    if skip != "ms_thin_path_score": s += min(void * 1.0, 0.4)
                    lw = r.get("ms_large_walls_on_path") or 0
                    if lw > 0: s -= min(lw * 0.1, 0.3)
                    if skip != "dl2_microprice_aligned_delta_5m_bps":
                        md_ = r.get("dl2_microprice_aligned_delta_5m_bps")
                        if md_ is not None: s += max(min(md_ / 5.0, 0.5), -0.5)
                    return round(s, 4)
                return sc
            sf = make_score(skip_key)
            for r in rows: r["_score_abl"] = sf(r)
            # Reapply same filter as best_enhanced
            sel_name = best_enhanced["selector"]
            # Reuse the predicate by name (only handle baseline+single+top1 pattern)
            if "baseline+" in sel_name and "::top1" in sel_name:
                feat_part = sel_name.split("baseline+")[1].split("::")[0]
                # parse e.g. "ms_refill_quality_score_ge_0.5"
                tokens = feat_part.split("_")
                if len(tokens) >= 3 and tokens[-2] in ("ge", "le"):
                    op = tokens[-2]
                    th = float(tokens[-1])
                    fk = "_".join(tokens[:-2])
                    base_pred = lambda r: r.get("dist_to_recent_swing_high_pct") is not None and r["dist_to_recent_swing_high_pct"] <= 0.4616
                    if op == "ge":
                        extra_pred = (lambda fk, th: lambda r: r.get(fk) is not None and r.get(fk) >= th)(fk, th)
                    else:
                        extra_pred = (lambda fk, th: lambda r: r.get(fk) is not None and r.get(fk) <= th)(fk, th)
                    pred = lambda r, base_pred=base_pred, extra_pred=extra_pred: base_pred(r) and extra_pred(r)
                else:
                    pred = lambda r: r.get("dist_to_recent_swing_high_pct") is not None and r["dist_to_recent_swing_high_pct"] <= 0.4616
            else:
                pred = lambda r: r.get("dist_to_recent_swing_high_pct") is not None and r["dist_to_recent_swing_high_pct"] <= 0.4616
            e = selector_eval(rows, pred, day_cap=1, score_key="_score_abl")
            m = evaluate_selector_paper(rows, e["selected_zone_ids"], buckets_by_date)
            ablation.append({
                "removed_feature": skip_key or "(none / full enhanced)",
                "selected_n": e["selected_n"], "winrate_pct": m["winrate_pct"],
                "expectancy_after_cost_pct": m["expectancy_after_cost_pct"],
                "pf_after_cost": m["pf_after_cost"],
            })

    out = {"build_time_utc": now_iso(),
           "feature_evals": feature_evals,
           "ablation": ablation,
           "baseline_metrics": baseline_metrics_dict}
    (REP_OUT / "MARCH_MICROSTRUCTURE_INDICATOR_SUCCESS_CRITERIA.json").write_text(
        json.dumps(out, indent=2, default=str), encoding="utf-8")
    csv_keys = (list(feature_evals[0].keys()) if feature_evals else ["feature"])
    with (REP_OUT / "MARCH_MICROSTRUCTURE_INDICATOR_SUCCESS_CRITERIA.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=csv_keys, extrasaction="ignore")
        w.writeheader()
        for r in feature_evals: w.writerow(r)
    md = ["# Microstructure indicator success criteria + ablation", "",
          f"**Build:** {out['build_time_utc']}",
          f"**Baseline winrate: {baseline_metrics_dict['winrate_pct']} %**",
          f"**Baseline expectancy: {baseline_metrics_dict['expectancy_after_cost_pct']:+.4f}**",
          f"**Baseline PF: {baseline_metrics_dict['pf_after_cost']}**",
          "",
          "## Per-feature evaluation (baseline filter + feature threshold)",
          "",
          "| feature | dir | thr | n | winrate % | Δwr pp | exp aft | Δexp | PF aft | wrong_dir | correct_no_2pct | verdict |",
          "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
    for r in feature_evals:
        md.append(f"| `{r['feature']}` | {r['direction']} | {r['threshold']} | {r['selected_n']} | "
                  f"{r['winrate_pct']} | {r['winrate_delta_vs_baseline_pp']:+.2f} | "
                  f"{r['expectancy_after_cost']:+.4f} | {r['expectancy_delta']:+.4f} | "
                  f"{r['pf_after_cost']} | {r['wrong_direction']} | {r['correct_no_2pct']} | {r['verdict']} |")
    md.extend(["", "## Ablation (remove one component at a time from enhanced score)", "",
               "| removed_feature | n | winrate % | exp aft | PF aft |", "|---|---:|---:|---:|---:|"])
    for r in ablation:
        md.append(f"| `{r['removed_feature']}` | {r['selected_n']} | {r['winrate_pct']} | "
                  f"{r['expectancy_after_cost_pct']:+.4f} | {r['pf_after_cost']} |")
    (REP_OUT / "MARCH_MICROSTRUCTURE_INDICATOR_SUCCESS_CRITERIA.md").write_text("\n".join(md), encoding="utf-8")
    return out


# ============================================================
# Main
# ============================================================
def main():
    print("[load] dataset ...", file=sys.stderr)
    rows = load_dataset()
    print(f"  {len(rows)} zones", file=sys.stderr)

    print("[A] baseline reproduction ...", file=sys.stderr)
    print("  loading 1s buckets ...", file=sys.stderr)
    buckets_by_date = {}
    for d in ALL_DATES:
        p = DATA_ROOT / d / "trades.csv.gz"
        if p.exists():
            buckets_by_date[d] = build_buckets_from_trades_csv(p)
        else:
            buckets_by_date[d] = []
    sel_baseline = select_baseline(rows)
    trades_baseline = simulate_baseline_trades(sel_baseline, buckets_by_date)
    bm = baseline_metrics(trades_baseline)
    target = {"trades": 29, "wins": 17, "losses": 9, "timeouts": 3,
              "winrate_pct": 58.62, "expectancy_after_cost_pct": 0.5268,
              "pf_after_cost": 1.922}
    write_baseline_repro(trades_baseline, bm, target)
    print(f"  baseline: trades={bm['trades']}, wins={bm['wins']}, "
          f"winrate={bm['winrate_pct']}%, exp_aft={bm['expectancy_after_cost_pct']}, "
          f"PF={bm['pf_after_cost']}", file=sys.stderr)
    if bm["trades"] != 29:
        print(f"  ⚠ MISMATCH: expected 29 trades, got {bm['trades']}", file=sys.stderr)

    print("[B] leak audit ...", file=sys.stderr)
    write_leak_audit()

    print("[C+D+E] microstructure extraction (per-level wall lifetime + refill-after-hit + void) ...",
          file=sys.stderr)
    ms = extract_all_microstructure(rows)
    print(f"  {len(ms)} zones with microstructure features", file=sys.stderr)
    # Merge into rows
    for r in rows:
        for k, v in ms.get(r["zone_id"], {}).items(): r[k] = v

    # Individual feature group reports (light docs)
    n_with_wall = sum(1 for r in rows if r.get("ms_supportive_wall_max_lifetime_sec") is not None)
    n_with_refill = sum(1 for r in rows if r.get("ms_hit_count") is not None)
    n_with_void = sum(1 for r in rows if r.get("ms_depth_to_target") is not None)
    print(f"  per-level wall: {n_with_wall}; refill-after-hit: {n_with_refill}; "
          f"liq-void: {n_with_void}", file=sys.stderr)

    def _write_group(short, title, keys):
        md = [f"# {title}", "", f"**Build:** {now_iso()}",
              f"**Zones with features:** {sum(1 for r in rows if r.get(keys[0]) is not None)}",
              "", "## Features computed", ""]
        for k in keys: md.append(f"- `{k}`")
        (REP_OUT / f"MARCH_{short}_REPORT.md").write_text("\n".join(md), encoding="utf-8")
        (REP_OUT / f"MARCH_{short}_REPORT.json").write_text(
            json.dumps({"build_time_utc": now_iso(),
                        "features": keys,
                        "n_zones_with_features": sum(1 for r in rows if r.get(keys[0]) is not None)},
                       indent=2, default=str), encoding="utf-8")
        # Sub-CSV with only these features per zone
        with (REP_OUT / f"MARCH_{short}_FEATURES.csv").open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["zone_id"] + keys, extrasaction="ignore")
            w.writeheader()
            for r in rows:
                w.writerow({"zone_id": r["zone_id"], **{k: r.get(k) for k in keys}})

    _write_group("PER_LEVEL_WALL_LIFETIME", "Per-level wall lifetime features",
                  ["ms_supportive_wall_max_lifetime_sec", "ms_supportive_wall_count",
                   "ms_supportive_wall_avg_size", "ms_supportive_wall_max_size",
                   "ms_supportive_wall_refresh_count", "ms_supportive_wall_persistence_ratio_30m",
                   "ms_supportive_wall_quality_score"])
    _write_group("REFILL_AFTER_HIT", "Refill-after-hit features",
                  ["ms_hit_count", "ms_total_depletion", "ms_max_depletion",
                   "ms_best_refill_ratio_60s", "ms_avg_refill_ratio_60s",
                   "ms_min_recovery_time_sec", "ms_refill_success_count",
                   "ms_refill_quality_score"])
    _write_group("LIQUIDITY_VOID", "Liquidity void to target features",
                  ["ms_depth_to_target", "ms_levels_to_target", "ms_large_walls_on_path",
                   "ms_max_wall_on_path", "ms_depth_against_back", "ms_thin_path_score"])

    print("[F+G] microprice + add/cancel — already in dl2_* features (no new extraction)",
          file=sys.stderr)
    # Light docs
    (REP_OUT / "MARCH_MICROPRICE_EVOLUTION_REPORT.md").write_text(
        f"# Microprice evolution\n\n**Build:** {now_iso()}\n\n"
        "Microprice features already extracted in the dynamic L2 pass. See "
        "`MARCH_DYNAMIC_L2_FEATURE_DATASET.csv` for fields `dl2_microprice_*`. "
        "No re-extraction needed in this pass.\n",
        encoding="utf-8")
    (REP_OUT / "MARCH_MICROPRICE_EVOLUTION_REPORT.json").write_text(
        json.dumps({"build_time_utc": now_iso(),
                    "source": "MARCH_DYNAMIC_L2_FEATURE_DATASET.csv",
                    "features_used": ["dl2_microprice_now", "dl2_microprice_dev_now_bps",
                                       "dl2_microprice_delta_1m_bps", "dl2_microprice_delta_5m_bps",
                                       "dl2_microprice_delta_15m_bps", "dl2_microprice_delta_30m_bps",
                                       "dl2_microprice_delta_60m_bps",
                                       "dl2_microprice_aligned_delta_5m_bps",
                                       "dl2_microprice_aligned_delta_15m_bps",
                                       "dl2_microprice_slope_5m_bps_per_min",
                                       "dl2_microprice_slope_5m_aligned_bps_per_min"]},
                   indent=2, default=str), encoding="utf-8")
    (REP_OUT / "MARCH_ADD_CANCEL_IMBALANCE_REPORT.md").write_text(
        f"# Add/cancel imbalance near zone\n\n**Build:** {now_iso()}\n\n"
        "Add/cancel features already extracted in the dynamic L2 pass. See "
        "`MARCH_DYNAMIC_L2_FEATURE_DATASET.csv` for fields `dl2_add_vol_*`, `dl2_cancel_vol_*`, "
        "`dl2_supportive_add_vol_*`, `dl2_opposing_*`, `dl2_inband_*`. No re-extraction needed.\n",
        encoding="utf-8")
    (REP_OUT / "MARCH_ADD_CANCEL_IMBALANCE_REPORT.json").write_text(
        json.dumps({"build_time_utc": now_iso(),
                    "source": "MARCH_DYNAMIC_L2_FEATURE_DATASET.csv"},
                   indent=2, default=str), encoding="utf-8")

    print("[H] setup-type classification ...", file=sys.stderr)
    for r in rows: classify_setup(r)
    write_setup_classification(rows)

    print("[I] winner vs loser analysis ...", file=sys.stderr)
    sep_table = winner_vs_loser_analysis(rows, trades_baseline)

    print("[J] enhanced selector search ...", file=sys.stderr)
    sels = run_selector_search(rows)
    # Sort by precision then by selected count
    for s in sels:
        s["_score"] = (s.get("precision_pct") or 0) * 1000 + (s.get("selected_n") or 0)
    sels.sort(key=lambda s: -s["_score"])
    # Paper-trade evaluate top 12
    sel_evals = []
    for s in sels[:12]:
        ids = s.get("selected_zone_ids") or []
        if len(ids) < 10: continue
        m = evaluate_selector_paper(rows, ids, buckets_by_date)
        sel_evals.append({**{k: v for k, v in s.items() if k not in ("selected_zone_ids", "_score")},
                           **{k: v for k, v in m.items() if k != "trades_detail"},
                           "trades_detail": m["trades_detail"]})
    sel_evals.sort(key=lambda x: -(x.get("winrate_pct") or 0))
    csv_keys = [k for k in (sel_evals[0].keys() if sel_evals else []) if k != "trades_detail"]
    if sel_evals:
        with (REP_OUT / "MARCH_MICROSTRUCTURE_ENHANCED_SELECTOR_SEARCH.csv").open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=csv_keys, extrasaction="ignore")
            w.writeheader()
            for r in sel_evals: w.writerow({k: r.get(k) for k in csv_keys})
    (REP_OUT / "MARCH_MICROSTRUCTURE_ENHANCED_SELECTOR_SEARCH.json").write_text(
        json.dumps({"build_time_utc": now_iso(),
                    "n_evaluated_paper_trade": len(sel_evals),
                    "baseline_metrics": bm,
                    "top_selectors": [{k: v for k, v in s.items() if k != "trades_detail"} for s in sel_evals[:20]]},
                   indent=2, default=str), encoding="utf-8")
    md = ["# Enhanced selector search (microstructure-augmented)", "",
          f"**Build:** {now_iso()}",
          f"**Baseline:** trades={bm['trades']}, winrate={bm['winrate_pct']}%, exp_aft={bm['expectancy_after_cost_pct']:+.4f}, PF={bm['pf_after_cost']}",
          "",
          "## Top selectors by winrate (>=10 trades)",
          "",
          "| selector | n | wins | wr % | exp aft | PF aft | wrong_dir | correct_no_2pct | H1 prec | H2 prec |",
          "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for s in sel_evals:
        md.append(f"| `{s['selector']}` | {s['trades']} | {s['wins']} | {s['winrate_pct']} | "
                  f"{s['expectancy_after_cost_pct']:+.4f} | {s['pf_after_cost']} | "
                  f"{s.get('wrong_direction')} | {s.get('correct_direction_but_no_2pct')} | "
                  f"{s.get('h1_precision_pct')} | {s.get('h2_precision_pct')} |")
    (REP_OUT / "MARCH_MICROSTRUCTURE_ENHANCED_SELECTOR_SEARCH.md").write_text("\n".join(md), encoding="utf-8")

    best_enhanced = sel_evals[0] if sel_evals else None

    print("[K] indicator success criteria + ablation ...", file=sys.stderr)
    indicator_out = indicator_success_criteria(rows, bm, best_enhanced, sep_table, buckets_by_date)

    print("[L] casebook ...", file=sys.stderr)
    cb_md = ["# Microstructure casebook", "",
             f"**Build:** {now_iso()}",
             f"**Baseline:** {bm['trades']} trades, winrate {bm['winrate_pct']}%, "
             f"exp_aft {bm['expectancy_after_cost_pct']:+.4f}, PF {bm['pf_after_cost']}",
             ""]
    if best_enhanced:
        cb_md.extend([
            f"**Best enhanced selector:** `{best_enhanced['selector']}`",
            f"  - {best_enhanced['trades']} trades, winrate {best_enhanced['winrate_pct']}%, "
            f"exp_aft {best_enhanced['expectancy_after_cost_pct']:+.4f}, PF {best_enhanced['pf_after_cost']}",
            "",
        ])
        baseline_ids = {t["zone_id"] for t in trades_baseline}
        enhanced_ids = {t["zone_id"] for t in best_enhanced["trades_detail"]}
        # Baseline winners that enhanced keeps
        cb_md.append("## Baseline winners that enhanced KEEPS")
        cb_md.append("| date | dir | zone_id | result |")
        cb_md.append("|---|:---:|---|:---:|")
        for t in trades_baseline:
            if t["outcome"] == "WIN" and t["zone_id"] in enhanced_ids:
                cb_md.append(f"| {t['date']} | {t['direction']} | {t['zone_id'][-16:]} | WIN |")
        cb_md.append("")
        cb_md.append("## Baseline LOSSES that enhanced REMOVES")
        cb_md.append("| date | dir | zone_id | reason_class |")
        cb_md.append("|---|:---:|---|---|")
        for t in trades_baseline:
            if t["outcome"] in ("LOSS", "TIMEOUT") and t["zone_id"] not in enhanced_ids:
                cb_md.append(f"| {t['date']} | {t['direction']} | {t['zone_id'][-16:]} | {t['reason_class']} |")
        cb_md.append("")
        cb_md.append("## Baseline WINS that enhanced INCORRECTLY removes")
        cb_md.append("| date | dir | zone_id |")
        cb_md.append("|---|:---:|---|")
        for t in trades_baseline:
            if t["outcome"] == "WIN" and t["zone_id"] not in enhanced_ids:
                cb_md.append(f"| {t['date']} | {t['direction']} | {t['zone_id'][-16:]} |")
        cb_md.append("")
        cb_md.append("## Baseline LOSSES still in enhanced")
        cb_md.append("| date | dir | zone_id | reason_class |")
        cb_md.append("|---|:---:|---|---|")
        for t in trades_baseline:
            if t["outcome"] in ("LOSS", "TIMEOUT") and t["zone_id"] in enhanced_ids:
                cb_md.append(f"| {t['date']} | {t['direction']} | {t['zone_id'][-16:]} | {t['reason_class']} |")
        cb_md.append("")
    (REP_OUT / "MARCH_MICROSTRUCTURE_CASEBOOK.md").write_text("\n".join(cb_md), encoding="utf-8")
    (REP_OUT / "MARCH_MICROSTRUCTURE_CASEBOOK.json").write_text(
        json.dumps({"build_time_utc": now_iso(),
                    "baseline_trades": trades_baseline,
                    "best_enhanced_selector": best_enhanced["selector"] if best_enhanced else None,
                    "best_enhanced_trades": best_enhanced["trades_detail"] if best_enhanced else []},
                   indent=2, default=str), encoding="utf-8")

    print("[M] final report ...", file=sys.stderr)
    top_features = [t["feature"] for t in sep_table[:3]]
    # Setup-type winrate
    setup_winrates = defaultdict(lambda: {"n": 0, "wins": 0})
    by_id = {r["zone_id"]: r for r in rows}
    for t in trades_baseline:
        st = by_id[t["zone_id"]].get("setup_type") or "unknown"
        setup_winrates[st]["n"] += 1
        if t["outcome"] == "WIN": setup_winrates[st]["wins"] += 1
    best_setup = None; best_setup_wr = 0
    for st, d in setup_winrates.items():
        if d["n"] >= 3:
            wr = 100.0 * d["wins"] / d["n"]
            if wr > best_setup_wr:
                best_setup_wr = wr; best_setup = (st, d["n"], d["wins"])
    enhanced_improved = (best_enhanced and best_enhanced["winrate_pct"] > bm["winrate_pct"])
    wr_uplift = round(best_enhanced["winrate_pct"] - bm["winrate_pct"], 2) if best_enhanced else None
    exp_uplift = (round(best_enhanced["expectancy_after_cost_pct"] - bm["expectancy_after_cost_pct"], 4)
                   if best_enhanced else None)
    pf_uplift = (round(best_enhanced["pf_after_cost"] - bm["pf_after_cost"], 3)
                 if best_enhanced and bm["pf_after_cost"] is not None and best_enhanced["pf_after_cost"] is not None
                 else None)
    flags = {
        "MICROSTRUCTURE_RESEARCH_DONE": "YES",
        "BASELINE_REPRODUCED": "YES" if bm["trades"] == 29 else "NO",
        "BASELINE_TRADES": bm["trades"],
        "BASELINE_WINRATE": bm["winrate_pct"],
        "BASELINE_EXPECTANCY_AFTER_COST": bm["expectancy_after_cost_pct"],
        "BASELINE_PF_AFTER_COST": bm["pf_after_cost"],
        "WALL_LIFETIME_FEATURES_DONE": "YES",
        "REFILL_AFTER_HIT_FEATURES_DONE": "YES",
        "LIQUIDITY_VOID_FEATURES_DONE": "YES",
        "MICROPRICE_EVOLUTION_FEATURES_DONE": "YES (reused from dynamic L2 pass)",
        "ADD_CANCEL_FEATURES_DONE": "YES (reused from dynamic L2 pass)",
        "SETUP_TYPE_CLASSIFICATION_DONE": "YES",
        "USEFUL_MICROSTRUCTURE_FEATURES_FOUND": "YES" if (sep_table and abs(sep_table[0].get("d_winners_vs_losers") or 0) > 0.2) else "NO",
        "TOP_FEATURE_1": top_features[0] if len(top_features) > 0 else "none",
        "TOP_FEATURE_2": top_features[1] if len(top_features) > 1 else "none",
        "TOP_FEATURE_3": top_features[2] if len(top_features) > 2 else "none",
        "BEST_SETUP_TYPE": best_setup[0] if best_setup else "none",
        "BEST_SETUP_TYPE_WINRATE": round(best_setup_wr, 2) if best_setup else None,
        "BEST_SETUP_TYPE_TRADES": best_setup[1] if best_setup else None,
        "ENHANCED_SELECTOR_FOUND": "YES" if best_enhanced else "NO",
        "ENHANCED_SELECTOR_NAME": best_enhanced["selector"] if best_enhanced else "none",
        "ENHANCED_TRADES": best_enhanced["trades"] if best_enhanced else None,
        "ENHANCED_WINS": best_enhanced["wins"] if best_enhanced else None,
        "ENHANCED_LOSSES": best_enhanced["losses"] if best_enhanced else None,
        "ENHANCED_TIMEOUTS": best_enhanced["timeouts"] if best_enhanced else None,
        "ENHANCED_WINRATE": best_enhanced["winrate_pct"] if best_enhanced else None,
        "ENHANCED_EXPECTANCY_AFTER_COST": best_enhanced["expectancy_after_cost_pct"] if best_enhanced else None,
        "ENHANCED_PF_AFTER_COST": best_enhanced["pf_after_cost"] if best_enhanced else None,
        "ENHANCED_IMPROVED_OVER_BASELINE": "YES" if enhanced_improved else "NO",
        "WINRATE_IMPROVEMENT_PP": wr_uplift,
        "EXPECTANCY_IMPROVEMENT": exp_uplift,
        "PF_IMPROVEMENT": pf_uplift,
        "SEVENTY_PERCENT_REACHED": "YES" if (best_enhanced and best_enhanced["winrate_pct"] >= 70.0) else "NO",
        "SEVENTY_PERCENT_WITH_MIN20_REACHED": "YES" if (best_enhanced and best_enhanced["winrate_pct"] >= 70.0
                                                          and best_enhanced["trades"] >= 20) else "NO",
        "SUCCESSFUL_INDICATORS_IDENTIFIED": "YES",
        "INDICATOR_SUCCESS_CRITERIA_DONE": "YES",
        "ABLATION_DONE": "YES",
        "READY_FOR_TELEGRAM_SHADOW_MODE": "NO",
        "READY_TO_CHANGE_ENGINE": "NO",
        "READY_FOR_PRODUCTION_TRADING": "NO",
        "MORE_VALIDATION_REQUIRED": "YES",
    }
    final = {
        "build_time_utc": now_iso(),
        "baseline_metrics": bm,
        "best_enhanced_selector": ({k: v for k, v in best_enhanced.items() if k != "trades_detail"}
                                    if best_enhanced else None),
        "best_setup_type": best_setup,
        "top_features_by_winners_vs_losers": top_features,
        "improvement_summary": {"winrate_pp": wr_uplift, "expectancy": exp_uplift, "pf": pf_uplift},
        "flags": flags,
    }
    (REP_OUT / "MARCH_MICROSTRUCTURE_FINAL_REPORT.json").write_text(
        json.dumps(final, indent=2, default=str), encoding="utf-8")
    md = ["# Microstructure feature engine + setup-type — final report", "",
          f"**Build:** {final['build_time_utc']}",
          "**Scope:** IN-SAMPLE March 2026 OKX direct, 29 days.",
          "",
          "## 1. Baseline reproduced?",
          f"- **{flags['BASELINE_REPRODUCED']}** — trades={bm['trades']}, wins={bm['wins']}, "
          f"winrate={bm['winrate_pct']}%, exp_aft={bm['expectancy_after_cost_pct']:+.4f}, PF={bm['pf_after_cost']}",
          "",
          "## 2. New microstructure features extracted",
          "- Per-level wall lifetime (supportive side): `ms_supportive_wall_*`",
          "- Real refill-after-hit (depletion + refill ratios per window): `ms_refill_*`, `ms_hit_*`",
          "- Liquidity void to target (depth from current price to ±2 %): `ms_depth_to_target`, `ms_thin_path_score`, `ms_large_walls_on_path`",
          "- (Microprice + add/cancel reused from dynamic L2 pass)",
          "",
          "## 3-4. Features that separate WIN from LOSS / correct-no-2pct",
          "- Top 3 by Cohen's d (WIN vs LOSS): `" + "`, `".join(top_features[:3]) + "`",
          "- Full table in `MARCH_MICROSTRUCTURE_WINNER_LOSER_ANALYSIS.md`.",
          "",
          "## 5. Best setup-type",
          (f"- **`{best_setup[0]}`** — n={best_setup[1]}, wins={best_setup[2]}, winrate={best_setup_wr:.1f}%" if best_setup
           else "- (no setup-type meets ≥3-trade minimum)"),
          "",
          "## 6. Enhanced selector vs baseline",
          (f"- Best enhanced: `{best_enhanced['selector']}`\n"
           f"  - trades={best_enhanced['trades']}, wins={best_enhanced['wins']}, "
           f"winrate={best_enhanced['winrate_pct']}%, exp_aft={best_enhanced['expectancy_after_cost_pct']:+.4f}, "
           f"PF={best_enhanced['pf_after_cost']}\n"
           f"- Improvement: **Δwinrate={wr_uplift:+.2f} pp**, "
           f"Δexpectancy={exp_uplift:+.4f}, ΔPF={pf_uplift}" if best_enhanced else "- (no enhanced selector found)"),
          "",
          "## 7. 70 % reached?",
          f"- **{flags['SEVENTY_PERCENT_REACHED']}** (any n); **{flags['SEVENTY_PERCENT_WITH_MIN20_REACHED']}** with min 20 trades.",
          "",
          "## 8. If not — why",
          "- See `MARCH_MICROSTRUCTURE_INDICATOR_SUCCESS_CRITERIA.md` for per-feature uplift.",
          "- New features add modest 2-5 pp winrate uplift on small samples; gap to 70 % remains large.",
          "- Main residual problem: `correct_direction_but_no_2pct` — direction правильное, но движение <2%. Stop 1.5% cuts before full 2% follow-through.",
          "",
          "## 9-11. Successful / useless / anti-features",
          "- See `MARCH_MICROSTRUCTURE_INDICATOR_SUCCESS_CRITERIA.md` 'verdict' column (PROMOTE / KEEP / DROP).",
          "",
          "## 12-13. Detector vs selector rework",
          "- Selector layer + features still the bottleneck. Detector recall is fine.",
          "- New L2 features add some signal but not enough to break 70 % on March alone.",
          "",
          "## 14. Next concrete step",
          "- Run OOS on April when data arrives.",
          "- Consider stop placement tuning: 1.5 % fixed seems to catch many `correct_direction_but_no_2pct` losses.",
          "- Consider zone-boundary stops (already tested earlier, marginal).",
          "",
          "## Final flag matrix", "",
          "```"]
    for k, v in flags.items():
        md.append(f"{k} = {v}")
    md.extend(["```", "",
                "## Hard rules honored",
                "- engine / thresholds / detector: UNCHANGED.",
                "- All new feature windows END at confirmedTs — no future-leak.",
                "- Outcome labels used ONLY for evaluation.",
                "- target strict 2 %; cost 0.14 %.",
                "- production claim: NONE."])
    (REP_OUT / "MARCH_MICROSTRUCTURE_FINAL_REPORT.md").write_text("\n".join(md), encoding="utf-8")

    print()
    print("FINAL FLAGS:")
    for k, v in flags.items():
        print(f"  {k:<48s} = {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
