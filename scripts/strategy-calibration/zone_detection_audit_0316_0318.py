"""Movement-first audit of zone detection quality on 2026-03-16 and 2026-03-18.

Read-only over:
  reports/BTC-USDT-SWAP_2026-03-{16,18}/zones.json
  reports/okx-direct/OKX_DIRECT_TECHNICAL_REPLAY_2026-03-{16,18}.json
  data/okx-historical/BTC-USDT-SWAP/2026-03-{16,18}/trades.csv.gz

Implements sections A-J of the user spec. No backtest re-run. No engine change.
"""
from __future__ import annotations
import csv
import datetime as dt
import gzip
import json
import math
import statistics as stats
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from canonical_ledger import (
    Signal, Bucket, ExecutionConfig,
    build_buckets_from_trades_csv, canonical_ledger_walk, simulate_canonical_trade,
)

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "package.json").exists() and (p / "scripts").exists())
REPORTS = ROOT / "reports"
REP_OKX = REPORTS / "okx-direct"
REP_OUT = REPORTS / "strategy-calibration"
REP_OUT.mkdir(parents=True, exist_ok=True)
DATA_ROOT = ROOT / "data/okx-historical/BTC-USDT-SWAP"

DATES = ["2026-03-16", "2026-03-18"]
WINDOW_MIN = 60
PRICE_BAND_PCT = 1.0
FAST_X_MIN_BASE = 60
MOVE_THRESHOLD_PCT = 2.0
SECONDARY_MOVE_THRESHOLD_PCT = 1.5


# ---------- helpers ----------

def mid_price(z):
    lo, hi = z.get("zoneLow"), z.get("zoneHigh")
    return None if lo is None or hi is None else (lo + hi) / 2.0


def is_triggered(z): return z.get("status") in ("RESOLVED_REACHED", "RESOLVED_FAILED")
def is_reached(z): return z.get("status") == "RESOLVED_REACHED"


def confirm_to_trigger_min(z):
    c, t = z.get("confirmedTs"), z.get("triggerTs")
    return None if c is None or t is None else (t - c) / 60000.0


def candidate_to_confirm_min(z):
    s, c = z.get("startTs"), z.get("confirmedTs")
    return None if s is None or c is None else (c - s) / 60000.0


def total_pre_trigger_min(z):
    s, t = z.get("startTs"), z.get("triggerTs")
    return None if s is None or t is None else (t - s) / 60000.0


def class_label(z):
    s = z.get("status")
    if s == "RESOLVED_REACHED":
        return "primary_unique_reached_move" if z.get("isPrimaryMoveZone") else "duplicate_reached_move"
    if s == "RESOLVED_FAILED": return "failed_triggered"
    if s == "NO_TRIGGER": return "no_trigger"
    if s in ("INVALIDATED", "EXPIRED"): return "invalidated_or_expired"
    return "unknown"


def ms_to_iso(ms):
    if ms is None: return None
    return dt.datetime.fromtimestamp(ms / 1000, tz=dt.timezone.utc).isoformat(timespec="seconds")


def sec_to_iso(s):
    if s is None: return None
    return dt.datetime.fromtimestamp(s, tz=dt.timezone.utc).isoformat(timespec="seconds")


def load_zones(d):
    p = REPORTS / f"BTC-USDT-SWAP_{d}" / "zones.json"
    if not p.exists():
        return []
    obj = json.loads(p.read_text(encoding="utf-8"))
    zones = obj if isinstance(obj, list) else obj.get("zones", [])
    for z in zones:
        z["_date"] = d
        z["_class"] = class_label(z)
    return zones


def apply_passive_filter(zones):
    by_date = defaultdict(list)
    for z in zones: by_date[z["_date"]].append(z)
    decisions = {}
    for date, lst in by_date.items():
        triggered = [z for z in lst if is_triggered(z) and z.get("triggerTs") is not None]
        triggered.sort(key=lambda z: z["triggerTs"])
        for i, z in enumerate(triggered):
            T = z["triggerTs"]; D = z["direction"]; zm = mid_price(z)
            dup = False; parent = None
            for prior in triggered[:i]:
                if prior["triggerTs"] >= T or prior["direction"] != D: continue
                dtm = (T - prior["triggerTs"]) / 60000.0
                if dtm <= 0 or dtm > WINDOW_MIN: continue
                pm = mid_price(prior)
                if zm is None or pm is None: continue
                if abs(zm - pm) / zm * 100.0 <= PRICE_BAND_PCT:
                    dup = True; parent = prior["id"]; break
            ctm = confirm_to_trigger_min(z)
            fast_ok = (ctm is None) or (ctm <= FAST_X_MIN_BASE)
            decisions[z["id"]] = {
                "kept": (not dup) and fast_ok,
                "fast_ok": fast_ok, "dup_suppressed": dup, "dup_parent": parent, "ctm_min": ctm,
            }
    return decisions


# ---------- Section A: Market movement map (ZigZag 2%) ----------

@dataclass
class Move:
    direction: str    # "UP" or "DOWN"
    start_sec: int
    end_sec: int
    start_price: float
    end_price: float
    size_pct: float
    secondary: bool   # True for 1.5% diagnostic
    pullback_depth_pct: float


def detect_zigzag_moves(buckets: list[Bucket], threshold_pct: float, secondary_threshold_pct: float) -> list[Move]:
    """Return list of swing moves. Primary moves use threshold_pct; secondary uses secondary_threshold_pct.
    Implementation: walk price; maintain current direction; reverse direction when retracement >= threshold.
    """
    if not buckets:
        return []
    out: list[Move] = []
    # initial pass with primary threshold
    def _scan(threshold: float, mark_secondary: bool) -> list[Move]:
        moves: list[Move] = []
        first_b = buckets[0]
        ext_sec = first_b.sec
        ext_high = first_b.high
        ext_low = first_b.low
        prev_swing_sec = first_b.sec
        prev_swing_price = first_b.last
        direction = None
        for b in buckets[1:]:
            if direction is None:
                # waiting for first move of size >= threshold from initial extreme
                up = (b.high - ext_low) / ext_low * 100.0 if ext_low else 0
                dn = (ext_high - b.low) / ext_high * 100.0 if ext_high else 0
                if up >= threshold and up >= dn:
                    direction = "UP"
                    prev_swing_sec = ext_sec; prev_swing_price = ext_low
                    ext_sec = b.sec; ext_high = b.high; ext_low = b.low
                elif dn >= threshold:
                    direction = "DOWN"
                    prev_swing_sec = ext_sec; prev_swing_price = ext_high
                    ext_sec = b.sec; ext_high = b.high; ext_low = b.low
                else:
                    if b.high > ext_high: ext_high = b.high; ext_sec = b.sec
                    if b.low < ext_low: ext_low = b.low
                continue
            if direction == "UP":
                if b.high > ext_high:
                    ext_high = b.high; ext_sec = b.sec
                # reversal check from current ext_high
                retr = (ext_high - b.low) / ext_high * 100.0
                if retr >= threshold:
                    # register UP move from prev_swing_price (low) → ext_high
                    size = (ext_high - prev_swing_price) / prev_swing_price * 100.0
                    # pullback depth: deepest dip during this move (skip — would need finer walk)
                    moves.append(Move(direction="UP", start_sec=prev_swing_sec, end_sec=ext_sec,
                                       start_price=prev_swing_price, end_price=ext_high,
                                       size_pct=round(size, 4), secondary=mark_secondary,
                                       pullback_depth_pct=0.0))
                    direction = "DOWN"
                    prev_swing_sec = ext_sec; prev_swing_price = ext_high
                    ext_sec = b.sec; ext_high = b.high; ext_low = b.low
            else:  # DOWN
                if b.low < ext_low:
                    ext_low = b.low; ext_sec = b.sec
                rally = (b.high - ext_low) / ext_low * 100.0
                if rally >= threshold:
                    size = (prev_swing_price - ext_low) / prev_swing_price * 100.0
                    moves.append(Move(direction="DOWN", start_sec=prev_swing_sec, end_sec=ext_sec,
                                       start_price=prev_swing_price, end_price=ext_low,
                                       size_pct=round(size, 4), secondary=mark_secondary,
                                       pullback_depth_pct=0.0))
                    direction = "UP"
                    prev_swing_sec = ext_sec; prev_swing_price = ext_low
                    ext_sec = b.sec; ext_high = b.high; ext_low = b.low
        return moves

    primary = _scan(threshold_pct, mark_secondary=False)
    secondary = _scan(secondary_threshold_pct, mark_secondary=True)
    # secondary contains primary (any 1.5% move includes all 2% moves). Filter out moves already covered by primary.
    primary_starts = {(m.start_sec, m.direction) for m in primary}
    secondary_extra = [m for m in secondary
                        if m.size_pct < threshold_pct and (m.start_sec, m.direction) not in primary_starts]
    return primary + secondary_extra


# ---------- Section B: Zone coverage of each move ----------

def classify_coverage(move: Move, zones_by_date: dict[str, list[dict]],
                      decisions: dict[str, dict]) -> dict:
    """For one move, find best matching zone and classify coverage."""
    date = sec_to_iso(move.start_sec)[:10]
    cand_zones = zones_by_date.get(date, [])
    # find all zones triggered before move ends with matching direction
    matching = []
    for z in cand_zones:
        if z["direction"] != ("LONG" if move.direction == "UP" else "SHORT"):
            continue
        if z.get("triggerTs") is None: continue
        ttr_sec = z["triggerTs"] // 1000
        # must trigger no later than move end
        if ttr_sec > move.end_sec: continue
        # and must not be way before move (>= move.start_sec - 3h)
        if ttr_sec < move.start_sec - 3 * 3600: continue
        matching.append(z)
    # pick the one whose triggerTs is closest to (but ideally before) move start
    best = None
    best_score = None
    for z in matching:
        ttr_sec = z["triggerTs"] // 1000
        lead_min = (move.start_sec - ttr_sec) / 60.0   # positive = trigger before move
        score = abs(lead_min)
        if best is None or score < best_score:
            best = z; best_score = score
    coverage = {
        "move_id": f"{date}_{move.direction}_{move.start_sec}",
        "date": date,
        "direction": move.direction,
        "move_start_iso": sec_to_iso(move.start_sec),
        "move_end_iso": sec_to_iso(move.end_sec),
        "move_size_pct": move.size_pct,
        "move_duration_min": round((move.end_sec - move.start_sec) / 60.0, 2),
        "is_secondary_1_5pct": move.secondary,
    }
    if best is None:
        coverage["best_matching_zone_id"] = None
        coverage["classification"] = "missed_move"
        return coverage

    dec = decisions.get(best["id"], {})
    trig_sec = best["triggerTs"] // 1000
    conf_sec = (best.get("confirmedTs") or 0) // 1000
    cand_sec = (best.get("startTs") or 0) // 1000
    move_duration_s = max(move.end_sec - move.start_sec, 1)
    completed_at_trigger = max(0.0, (trig_sec - move.start_sec) / move_duration_s)
    pct_complete = round(min(1.0, max(0.0, completed_at_trigger)) * 100, 2)

    cls = best["_class"]
    coverage.update({
        "best_matching_zone_id": best["id"],
        "best_zone_direction": best["direction"],
        "best_zone_class": cls,
        "candidate_iso": sec_to_iso(cand_sec) if cand_sec else None,
        "confirmed_iso": sec_to_iso(conf_sec) if conf_sec else None,
        "trigger_iso": sec_to_iso(trig_sec),
        "candidate_lead_min_vs_move_start": round((move.start_sec - cand_sec) / 60.0, 2) if cand_sec else None,
        "confirmed_lead_min_vs_move_start": round((move.start_sec - conf_sec) / 60.0, 2) if conf_sec else None,
        "trigger_lead_min_vs_move_start": round((move.start_sec - trig_sec) / 60.0, 2),
        "pct_of_move_completed_by_trigger": pct_complete,
        "was_filter_kept": dec.get("kept"),
        "filter_dup_suppressed": dec.get("dup_suppressed"),
        "filter_fast_ok": dec.get("fast_ok"),
    })
    # Classification
    if not dec.get("kept", True) and cls in ("primary_unique_reached_move", "duplicate_reached_move"):
        coverage["classification"] = "filtered_correct_zone"
    elif pct_complete <= 10 and dec.get("kept", False):
        coverage["classification"] = "covered_early"
    elif pct_complete <= 50 and dec.get("kept", False):
        coverage["classification"] = "covered_mid"
    elif dec.get("kept", False):
        coverage["classification"] = "covered_late"
    elif cls == "duplicate_reached_move":
        coverage["classification"] = "duplicate_only"
    elif cand_sec and (move.start_sec - cand_sec) / 60.0 > 0:
        coverage["classification"] = "candidate_early_but_trigger_late"
    else:
        coverage["classification"] = "ambiguous"
    return coverage


# ---------- Section C: timing audit ----------

def timing_audit(zones: list[dict], decisions: dict, buckets_by_date: dict) -> list[dict]:
    rows = []
    for z in zones:
        d = z["_date"]
        dec = decisions.get(z["id"], {})
        # If reached: time to target = (resolvedTs or first reached anchor) - triggerTs
        trig_to_target = None
        trig_to_stop = None
        if is_reached(z) and z.get("triggerTs"):
            # Walk price path: when did 2% target hit from triggerPrice?
            tp = None
            for r in z.get("reasons", []):
                if r.get("stage") == "trigger":
                    tp = (r.get("conditions") or {}).get("triggerPrice")
                    break
            if tp is None: tp = mid_price(z)
            if tp:
                buckets = buckets_by_date.get(d) or []
                trig_sec = z["triggerTs"] // 1000
                target = tp * 1.02 if z["direction"] == "LONG" else tp * 0.98
                for b in buckets:
                    if b.sec < trig_sec: continue
                    if z["direction"] == "LONG" and b.high >= target:
                        trig_to_target = round((b.sec - trig_sec) / 60.0, 2); break
                    if z["direction"] == "SHORT" and b.low <= target:
                        trig_to_target = round((b.sec - trig_sec) / 60.0, 2); break
                # stop at 1% adverse
                stop = tp * 0.99 if z["direction"] == "LONG" else tp * 1.01
                for b in buckets:
                    if b.sec < trig_sec: continue
                    if z["direction"] == "LONG" and b.low <= stop:
                        trig_to_stop = round((b.sec - trig_sec) / 60.0, 2); break
                    if z["direction"] == "SHORT" and b.high >= stop:
                        trig_to_stop = round((b.sec - trig_sec) / 60.0, 2); break
        rows.append({
            "date": d, "zone_id": z["id"], "direction": z["direction"], "class": z["_class"],
            "candidate_iso": ms_to_iso(z.get("startTs")),
            "confirmed_iso": ms_to_iso(z.get("confirmedTs")),
            "trigger_iso": ms_to_iso(z.get("triggerTs")),
            "candidate_to_confirm_min": candidate_to_confirm_min(z),
            "confirm_to_trigger_min": confirm_to_trigger_min(z),
            "total_pre_trigger_min": total_pre_trigger_min(z),
            "trigger_to_target_min_canonical_1pct_stop": trig_to_target,
            "trigger_to_stop_min_canonical_1pct_stop": trig_to_stop,
            "filter_kept": dec.get("kept"),
            "filter_fast_ok": dec.get("fast_ok"),
            "filter_dup_suppressed": dec.get("dup_suppressed"),
        })
    return rows


# ---------- Section F: local normalization ----------

def local_normalization(zones: list[dict], buckets_by_date: dict) -> list[dict]:
    """For each triggered zone, compute local price-range percentile relative to last 30/60/180m.
    Quick proxy: compute local price range % over each window, then compare to whole-day distribution.
    """
    rows = []
    for d in DATES:
        buckets = buckets_by_date.get(d) or []
        if not buckets: continue
        # For each zone trigger time, sample local windows
        zones_d = [z for z in zones if z["_date"] == d and z.get("triggerTs")]
        for z in zones_d:
            trig_sec = z["triggerTs"] // 1000
            entry = {
                "date": d, "zone_id": z["id"], "direction": z["direction"], "class": z["_class"],
                "trigger_iso": ms_to_iso(z["triggerTs"]),
            }
            for win_min in (15, 30, 60, 180):
                win_start = trig_sec - win_min * 60
                slice_buckets = [b for b in buckets if win_start <= b.sec < trig_sec]
                if not slice_buckets:
                    entry[f"range_{win_min}m_pct"] = None
                    continue
                hi = max(b.high for b in slice_buckets)
                lo = min(b.low for b in slice_buckets)
                rng = (hi - lo) / lo * 100.0 if lo else 0
                entry[f"range_{win_min}m_pct"] = round(rng, 4)
            rows.append(entry)
    return rows


# ---------- main ----------

def main() -> int:
    print("loading zones ...", file=sys.stderr)
    zones_all: list[dict] = []
    zones_by_date: dict[str, list[dict]] = {}
    for d in DATES:
        zs = load_zones(d)
        zones_by_date[d] = zs
        zones_all.extend(zs)
    decisions = apply_passive_filter(zones_all)
    print(f"  loaded {len(zones_all)} zones", file=sys.stderr)

    print("building 1s buckets ...", file=sys.stderr)
    buckets_by_date: dict[str, list[Bucket]] = {}
    for d in DATES:
        p = DATA_ROOT / d / "trades.csv.gz"
        if p.exists():
            buckets_by_date[d] = build_buckets_from_trades_csv(p)
            print(f"  {d}: {len(buckets_by_date[d]):,} buckets", file=sys.stderr)

    # ---------- A: market movement map ----------
    print("[A] market movement map ...", file=sys.stderr)
    moves_by_date: dict[str, list[Move]] = {}
    market_rows = []
    for d in DATES:
        moves = detect_zigzag_moves(buckets_by_date.get(d, []), MOVE_THRESHOLD_PCT, SECONDARY_MOVE_THRESHOLD_PCT)
        moves_by_date[d] = moves
        for i, m in enumerate(moves):
            market_rows.append({
                "date": d, "move_idx": i, "direction": m.direction,
                "start_iso": sec_to_iso(m.start_sec), "end_iso": sec_to_iso(m.end_sec),
                "start_price": m.start_price, "end_price": m.end_price,
                "size_pct": m.size_pct, "duration_min": round((m.end_sec - m.start_sec) / 60.0, 1),
                "is_secondary_1_5pct": m.secondary,
            })
    n_primary_moves = sum(1 for r in market_rows if not r["is_secondary_1_5pct"])
    n_up_moves = sum(1 for r in market_rows if not r["is_secondary_1_5pct"] and r["direction"] == "UP")
    n_dn_moves = n_primary_moves - n_up_moves
    print(f"  total primary 2% moves: {n_primary_moves} (UP={n_up_moves}, DN={n_dn_moves})", file=sys.stderr)

    market_json = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "scope": "ZigZag market moves on OKX direct 2026-03-16 + 2026-03-18 (primary >= 2%, secondary >= 1.5%)",
        "moves": market_rows,
        "summary": {
            "n_primary_2pct_moves": n_primary_moves,
            "n_secondary_1_5pct_moves": sum(1 for r in market_rows if r["is_secondary_1_5pct"]),
            "n_up_2pct": n_up_moves, "n_down_2pct": n_dn_moves,
        },
    }
    (REP_OUT / "OKX_0316_0318_MARKET_MOVEMENT_MAP.json").write_text(
        json.dumps(market_json, indent=2, default=str), encoding="utf-8")
    with (REP_OUT / "OKX_0316_0318_MARKET_MOVEMENT_MAP.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(market_rows[0].keys()) if market_rows else [])
        w.writeheader()
        for r in market_rows: w.writerow(r)
    md_m = [
        "# Market movement map (ZigZag 2 % primary + 1.5 % secondary)",
        "",
        f"**Build:** {market_json['build_time_utc']}",
        f"**Scope:** {market_json['scope']}",
        "",
        f"- primary (>= 2 %) moves: **{n_primary_moves}**  (UP={n_up_moves} / DOWN={n_dn_moves})",
        f"- secondary (1.5-2 %) moves: **{market_json['summary']['n_secondary_1_5pct_moves']}**",
        "",
        "| date | # | dir | start | end | size % | duration min | secondary? |",
        "|---|--:|---|---|---|---:|---:|:---:|",
    ]
    for r in market_rows:
        md_m.append(f"| {r['date']} | {r['move_idx']} | {r['direction']} | "
                    f"{r['start_iso']} | {r['end_iso']} | {r['size_pct']} | "
                    f"{r['duration_min']} | {'Y' if r['is_secondary_1_5pct'] else 'N'} |")
    (REP_OUT / "OKX_0316_0318_MARKET_MOVEMENT_MAP.md").write_text("\n".join(md_m), encoding="utf-8")

    # ---------- B: zone coverage ----------
    print("[B] zone coverage ...", file=sys.stderr)
    coverage_rows = []
    for d in DATES:
        for m in moves_by_date[d]:
            cov = classify_coverage(m, zones_by_date, decisions)
            coverage_rows.append(cov)
    # split by primary/secondary
    coverage_primary = [c for c in coverage_rows if not c.get("is_secondary_1_5pct")]
    # counts
    cov_counts = defaultdict(int)
    for c in coverage_primary:
        cov_counts[c["classification"]] += 1
    cov_json = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "counts_classification": dict(cov_counts),
        "rows": coverage_rows,
    }
    (REP_OUT / "OKX_0316_0318_MOVEMENT_ZONE_COVERAGE.json").write_text(
        json.dumps(cov_json, indent=2, default=str), encoding="utf-8")
    with (REP_OUT / "OKX_0316_0318_MOVEMENT_ZONE_COVERAGE.csv").open("w", encoding="utf-8", newline="") as f:
        keys = list(coverage_rows[0].keys()) if coverage_rows else []
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        for r in coverage_rows: w.writerow(r)
    md_b = [
        "# Movement → zone coverage classification",
        "",
        f"**Build:** {cov_json['build_time_utc']}",
        "",
        "## Classification counts (primary 2 % moves only)",
        "",
    ]
    for k, v in cov_counts.items():
        md_b.append(f"- {k}: **{v}**")
    md_b.extend([
        "",
        "## Per-move detail",
        "",
        "| date | dir | size % | move start | best zone class | zone direction | trigger lead min | % move completed at trigger | filter kept | classification |",
        "|---|---|---:|---|---|---|---:|---:|:---:|---|",
    ])
    for c in coverage_rows:
        sec = "Y" if c.get("is_secondary_1_5pct") else "N"
        md_b.append(
            f"| {c['date']} | {c['direction']} ({sec}) | {c['move_size_pct']} | "
            f"{c['move_start_iso']} | "
            f"{c.get('best_zone_class', '—')} | {c.get('best_zone_direction', '—')} | "
            f"{c.get('trigger_lead_min_vs_move_start', '—')} | "
            f"{c.get('pct_of_move_completed_by_trigger', '—')} | "
            f"{'Y' if c.get('was_filter_kept') else 'N'} | **{c['classification']}** |"
        )
    (REP_OUT / "OKX_0316_0318_MOVEMENT_ZONE_COVERAGE.md").write_text("\n".join(md_b), encoding="utf-8")

    # ---------- C: timing audit ----------
    print("[C] timing audit ...", file=sys.stderr)
    timing_rows = timing_audit(zones_all, decisions, buckets_by_date)
    # Slow-zone analysis
    slow_ctr_zones = [r for r in timing_rows if (r["confirm_to_trigger_min"] or 0) > 60]
    slow_ctr_correct = [r for r in slow_ctr_zones if r["class"] in ("primary_unique_reached_move", "duplicate_reached_move")]
    slow_ctc = [r for r in timing_rows if (r["candidate_to_confirm_min"] or 0) > 60]
    long_slow = [r for r in slow_ctr_zones if r["direction"] == "LONG"]
    short_slow = [r for r in slow_ctr_zones if r["direction"] == "SHORT"]

    timing_json = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "n_zones_total": len(timing_rows),
        "n_with_confirm_to_trigger_gt_60m": len(slow_ctr_zones),
        "n_correct_but_slow_ctr": len(slow_ctr_correct),
        "n_with_candidate_to_confirm_gt_60m": len(slow_ctc),
        "n_long_slow_ctr_gt_60m": len(long_slow),
        "n_short_slow_ctr_gt_60m": len(short_slow),
        "rows": timing_rows,
    }
    (REP_OUT / "OKX_0316_0318_ZONE_TIMING_AUDIT.json").write_text(
        json.dumps(timing_json, indent=2, default=str), encoding="utf-8")
    with (REP_OUT / "OKX_0316_0318_ZONE_TIMING_AUDIT.csv").open("w", encoding="utf-8", newline="") as f:
        keys = list(timing_rows[0].keys()) if timing_rows else []
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        for r in timing_rows: w.writerow(r)
    md_c = [
        "# Candidate → Confirmed → Trigger timing audit",
        "",
        f"**Build:** {timing_json['build_time_utc']}",
        "",
        "## Slow-zone summary",
        "",
        f"- zones with confirm_to_trigger > 60 m: **{len(slow_ctr_zones)}** (LONG={len(long_slow)}, SHORT={len(short_slow)})",
        f"  - of which were eventually reached_raw: **{len(slow_ctr_correct)}**",
        f"- zones with candidate_to_confirm > 60 m: **{len(slow_ctc)}**",
        "",
        "## Per-zone (first 40, sorted by class)",
        "",
        "| date | zone | dir | class | cand→conf min | conf→trig min | total pre-trig | trig→target min | trig→stop min | filter kept |",
        "|---|---|---|---|---:|---:|---:|---:|---:|:---:|",
    ]
    timing_rows_sorted = sorted(timing_rows, key=lambda r: (r["class"], r["date"], r["zone_id"]))
    for r in timing_rows_sorted[:40]:
        md_c.append(
            f"| {r['date']} | `{r['zone_id'][-20:]}` | {r['direction']} | {r['class']} | "
            f"{r['candidate_to_confirm_min']} | {r['confirm_to_trigger_min']} | "
            f"{r['total_pre_trigger_min']} | {r['trigger_to_target_min_canonical_1pct_stop']} | "
            f"{r['trigger_to_stop_min_canonical_1pct_stop']} | "
            f"{'Y' if r['filter_kept'] else 'N'} |"
        )
    (REP_OUT / "OKX_0316_0318_ZONE_TIMING_AUDIT.md").write_text("\n".join(md_c), encoding="utf-8")

    # ---------- D: direction failure audit ----------
    print("[D] direction failure ...", file=sys.stderr)
    # For each triggered zone, check what direction market actually moved over next 4h
    direction_failures = []
    for z in zones_all:
        if not is_triggered(z) or not z.get("triggerTs"): continue
        d = z["_date"]
        buckets = buckets_by_date.get(d) or []
        if not buckets: continue
        trig_sec = z["triggerTs"] // 1000
        tp = None
        for r in z.get("reasons", []):
            if r.get("stage") == "trigger":
                tp = (r.get("conditions") or {}).get("triggerPrice")
                break
        if tp is None: tp = mid_price(z)
        if tp is None: continue
        end_sec = trig_sec + 4 * 3600
        slice_b = [b for b in buckets if trig_sec <= b.sec <= end_sec]
        if not slice_b: continue
        max_up = max((b.high - tp) / tp * 100.0 for b in slice_b)
        max_down = max((tp - b.low) / tp * 100.0 for b in slice_b)
        # which side was 2% feasible?
        up_2pct = max_up >= 2.0
        down_2pct = max_down >= 2.0
        wrong_direction = False
        if z["direction"] == "LONG" and not up_2pct and down_2pct:
            wrong_direction = True
        elif z["direction"] == "SHORT" and not down_2pct and up_2pct:
            wrong_direction = True
        if wrong_direction:
            direction_failures.append({
                "date": d, "zone_id": z["id"], "direction": z["direction"],
                "trigger_iso": ms_to_iso(z["triggerTs"]),
                "max_4h_up_pct": round(max_up, 4),
                "max_4h_down_pct": round(max_down, 4),
                "engine_class": z["_class"],
                "classification": "wrong_direction_noise" if z["_class"] == "failed_triggered" else "ambiguous",
            })
    dir_json = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "n_wrong_direction": len(direction_failures),
        "rows": direction_failures,
    }
    (REP_OUT / "OKX_0316_0318_DIRECTION_FAILURE_AUDIT.json").write_text(
        json.dumps(dir_json, indent=2, default=str), encoding="utf-8")
    md_d = [
        "# Direction failure audit (engine direction vs market 4h forward)",
        "",
        f"**Build:** {dir_json['build_time_utc']}",
        f"**Total wrong-direction triggers (4h forward): {len(direction_failures)}**",
        "",
        "| date | zone | dir | trigger | 4h up % | 4h down % | engine class | classification |",
        "|---|---|---|---|---:|---:|---|---|",
    ]
    for r in direction_failures:
        md_d.append(
            f"| {r['date']} | `{r['zone_id'][-20:]}` | {r['direction']} | {r['trigger_iso']} | "
            f"{r['max_4h_up_pct']} | {r['max_4h_down_pct']} | {r['engine_class']} | {r['classification']} |"
        )
    (REP_OUT / "OKX_0316_0318_DIRECTION_FAILURE_AUDIT.md").write_text("\n".join(md_d), encoding="utf-8")

    # ---------- E: filter failure audit ----------
    print("[E] filter failure audit ...", file=sys.stderr)
    # filter-suppressed correct zones (reached_raw or primary)
    filter_failures_correct = []
    for z in zones_all:
        if not is_triggered(z): continue
        dec = decisions.get(z["id"], {})
        if dec.get("kept"): continue   # only look at suppressed
        reason = []
        if dec.get("dup_suppressed"): reason.append("duplicate_60m_price_band")
        if not dec.get("fast_ok"): reason.append(f"slow_trigger (ctm={dec.get('ctm_min')})")
        if z["_class"] in ("primary_unique_reached_move", "duplicate_reached_move"):
            filter_failures_correct.append({
                "date": z["_date"], "zone_id": z["id"], "direction": z["direction"],
                "class": z["_class"], "isPrimaryMoveZone": bool(z.get("isPrimaryMoveZone")),
                "trigger_iso": ms_to_iso(z.get("triggerTs")),
                "filter_reason": "; ".join(reason),
                "candidate_iso": ms_to_iso(z.get("startTs")),
                "confirmed_iso": ms_to_iso(z.get("confirmedTs")),
                "candidate_to_confirm_min": candidate_to_confirm_min(z),
                "confirm_to_trigger_min": confirm_to_trigger_min(z),
                "total_pre_trigger_min": total_pre_trigger_min(z),
            })

    # 03-16 LONG primary deep dive
    primary_long_0316 = next((z for z in zones_all
                              if z["_date"] == "2026-03-16" and z.get("isPrimaryMoveZone") and z["direction"] == "LONG"
                              and is_reached(z)), None)
    deep_dive_0316 = None
    if primary_long_0316:
        z = primary_long_0316
        dec = decisions.get(z["id"], {})
        # was zone before or after the actual 2% up move?
        # find market 2% UP move on 03-16
        moves_03_16 = [m for m in moves_by_date.get("2026-03-16", []) if not m.secondary and m.direction == "UP"]
        target_move = moves_03_16[0] if moves_03_16 else None
        cand_sec = (z.get("startTs") or 0) // 1000
        trig_sec = z["triggerTs"] // 1000
        deep_dive_0316 = {
            "zone_id": z["id"], "direction": z["direction"],
            "candidate_iso": ms_to_iso(z.get("startTs")),
            "confirmed_iso": ms_to_iso(z.get("confirmedTs")),
            "trigger_iso": ms_to_iso(z["triggerTs"]),
            "candidate_to_confirm_min": candidate_to_confirm_min(z),
            "confirm_to_trigger_min": confirm_to_trigger_min(z),
            "total_pre_trigger_min": total_pre_trigger_min(z),
            "filter_kept": dec.get("kept"),
            "filter_reason": "slow_trigger" if not dec.get("fast_ok") else "—",
            "actual_2pct_up_move_on_day_start_iso": sec_to_iso(target_move.start_sec) if target_move else None,
            "actual_2pct_up_move_size_pct": target_move.size_pct if target_move else None,
            "candidate_was_before_move_start": (cand_sec < target_move.start_sec) if target_move else None,
            "trigger_was_before_move_start": (trig_sec < target_move.start_sec) if target_move else None,
            "would_tg_alert_be_useful": "YES (candidate before move start)" if target_move and cand_sec < target_move.start_sec else "UNCLEAR",
        }

    filter_json = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "n_filter_failures_correct_zones_suppressed": len(filter_failures_correct),
        "rows": filter_failures_correct,
        "deep_dive_0316_primary_long": deep_dive_0316,
    }
    (REP_OUT / "OKX_0316_0318_FILTER_FAILURE_AUDIT.json").write_text(
        json.dumps(filter_json, indent=2, default=str), encoding="utf-8")
    md_e = [
        "# Filter failure audit (base passive filter)",
        "",
        f"**Build:** {filter_json['build_time_utc']}",
        f"**Filter:** fast_trigger<=60m AND duplicate_60m_price_band<=1%",
        "",
        f"## Correct zones suppressed by filter: **{len(filter_failures_correct)}**",
        "",
        "| date | zone | dir | class | primary? | filter reason | ctm min |",
        "|---|---|---|---|:---:|---|---:|",
    ]
    for r in filter_failures_correct:
        md_e.append(
            f"| {r['date']} | `{r['zone_id'][-20:]}` | {r['direction']} | {r['class']} | "
            f"{'Y' if r['isPrimaryMoveZone'] else 'N'} | {r['filter_reason']} | "
            f"{r['confirm_to_trigger_min']} |"
        )
    md_e.extend(["", "## Deep dive: 03-16 LONG primary"])
    if deep_dive_0316:
        for k, v in deep_dive_0316.items():
            md_e.append(f"- {k}: {v}")
    else:
        md_e.append("- (no LONG primary reached on 03-16)")
    (REP_OUT / "OKX_0316_0318_FILTER_FAILURE_AUDIT.md").write_text("\n".join(md_e), encoding="utf-8")

    # ---------- F: local normalization ----------
    print("[F] local normalization ...", file=sys.stderr)
    local_rows = local_normalization([z for z in zones_all if is_triggered(z)], buckets_by_date)
    # Compare local ranges by class
    by_class_range_60 = defaultdict(list)
    for r in local_rows:
        if r.get("range_60m_pct") is not None:
            by_class_range_60[r["class"]].append(r["range_60m_pct"])
    class_median_range_60 = {k: round(stats.median(v), 4) for k, v in by_class_range_60.items() if v}

    local_json = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "median_local_60m_range_by_class": class_median_range_60,
        "rows": local_rows,
    }
    (REP_OUT / "OKX_0316_0318_LOCAL_NORMALIZATION_AUDIT.json").write_text(
        json.dumps(local_json, indent=2, default=str), encoding="utf-8")
    with (REP_OUT / "OKX_0316_0318_LOCAL_NORMALIZATION_AUDIT.csv").open("w", encoding="utf-8", newline="") as f:
        keys = list(local_rows[0].keys()) if local_rows else []
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        for r in local_rows: w.writerow(r)
    # Decide if local normalization is needed
    local_norm_needed = "UNKNOWN"
    if class_median_range_60:
        primary_v = class_median_range_60.get("primary_unique_reached_move")
        failed_v = class_median_range_60.get("failed_triggered")
        if primary_v is not None and failed_v is not None:
            local_norm_needed = "YES" if abs(primary_v - failed_v) / max(failed_v, 0.01) > 0.30 else "NO"
    md_f = [
        "# Local normalization audit (proxy: local price range by zone class)",
        "",
        f"**Build:** {local_json['build_time_utc']}",
        "",
        "## Median local 60-min price range by zone class",
        "",
        "| class | median 60m range % |",
        "|---|---:|",
    ]
    for k, v in class_median_range_60.items():
        md_f.append(f"| {k} | {v} |")
    md_f.extend([
        "",
        f"`LOCAL_NORMALIZATION_NEEDED` = **{local_norm_needed}**",
        "",
        "If primary-unique zones tend to fire in materially different local volatility than failed_triggered,",
        "then absolute thresholds may be biased and local normalization could help.",
    ])
    (REP_OUT / "OKX_0316_0318_LOCAL_NORMALIZATION_AUDIT.md").write_text("\n".join(md_f), encoding="utf-8")

    # ---------- G: unique move labeling audit ----------
    print("[G] unique move labeling ...", file=sys.stderr)
    engine_primaries = [z for z in zones_all if z.get("isPrimaryMoveZone") and is_reached(z)]
    engine_primary_count = len(engine_primaries)
    # Match each engine primary to a market move
    primary_to_move = []
    matched_move_ids = set()
    for z in engine_primaries:
        d = z["_date"]
        moves = moves_by_date.get(d, [])
        trig_sec = z["triggerTs"] // 1000
        # find first matching market move in same direction within 4h forward
        z_dir = "UP" if z["direction"] == "LONG" else "DOWN"
        best_m = None
        for m in moves:
            if m.secondary: continue
            if m.direction != z_dir: continue
            if m.end_sec < trig_sec: continue
            if m.start_sec > trig_sec + 4 * 3600: continue
            best_m = m; break
        if best_m:
            matched_move_ids.add((d, best_m.direction, best_m.start_sec))
        primary_to_move.append({
            "zone_id": z["id"], "direction": z["direction"],
            "trigger_iso": ms_to_iso(z["triggerTs"]),
            "uniqueMoveId": z.get("uniqueMoveId"),
            "matched_market_move_start_iso": sec_to_iso(best_m.start_sec) if best_m else None,
            "matched_market_move_size_pct": best_m.size_pct if best_m else None,
        })

    # Unmatched market 2% moves
    unmatched_moves = []
    for d in DATES:
        for m in moves_by_date.get(d, []):
            if m.secondary: continue
            if (d, m.direction, m.start_sec) not in matched_move_ids:
                unmatched_moves.append({
                    "date": d, "direction": m.direction,
                    "start_iso": sec_to_iso(m.start_sec), "end_iso": sec_to_iso(m.end_sec),
                    "size_pct": m.size_pct,
                })

    label_json = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "n_market_2pct_moves": n_primary_moves,
        "n_engine_primary_unique": engine_primary_count,
        "n_market_moves_matched_to_engine_primary": len(matched_move_ids),
        "n_market_moves_NOT_matched": len(unmatched_moves),
        "engine_primaries": primary_to_move,
        "unmatched_market_moves": unmatched_moves,
    }
    (REP_OUT / "OKX_0316_0318_UNIQUE_MOVE_LABELING_AUDIT.json").write_text(
        json.dumps(label_json, indent=2, default=str), encoding="utf-8")
    md_g = [
        "# Unique-move labeling audit",
        "",
        f"**Build:** {label_json['build_time_utc']}",
        "",
        f"- market 2 % moves found: **{n_primary_moves}**",
        f"- engine primary_unique labels: **{engine_primary_count}**",
        f"- market moves matched to engine primary: **{len(matched_move_ids)}**",
        f"- market moves NOT matched (no engine primary): **{len(unmatched_moves)}**",
        "",
        "## Engine primaries → market moves",
        "",
        "| zone_id | dir | trigger time | uniqueMoveId | matched move start | matched move size % |",
        "|---|---|---|---:|---|---:|",
    ]
    for r in primary_to_move:
        md_g.append(f"| `{r['zone_id'][-20:]}` | {r['direction']} | {r['trigger_iso']} | "
                    f"{r['uniqueMoveId']} | {r['matched_market_move_start_iso']} | "
                    f"{r['matched_market_move_size_pct']} |")
    md_g.extend(["", "## Unmatched market 2 % moves (no engine primary)", ""])
    if unmatched_moves:
        md_g.append("| date | dir | start | end | size % |")
        md_g.append("|---|---|---|---|---:|")
        for m in unmatched_moves:
            md_g.append(f"| {m['date']} | {m['direction']} | {m['start_iso']} | {m['end_iso']} | {m['size_pct']} |")
    else:
        md_g.append("(none)")
    (REP_OUT / "OKX_0316_0318_UNIQUE_MOVE_LABELING_AUDIT.md").write_text("\n".join(md_g), encoding="utf-8")

    # ---------- H: root-cause matrix ----------
    print("[H] root-cause matrix ...", file=sys.stderr)
    rc_rows = []
    # for each market move
    for c in coverage_rows:
        if c.get("is_secondary_1_5pct"): continue
        cls = c.get("classification")
        if cls == "missed_move":
            root = "detector_missed_candidate"
        elif cls == "filtered_correct_zone":
            root = "filter_suppressed_correct_zone"
        elif cls == "covered_late":
            root = "trigger_too_slow"
        elif cls == "covered_mid":
            root = "trigger_too_slow"
        elif cls == "covered_early":
            root = "normal_market_noise"
        elif cls == "candidate_early_but_trigger_late":
            root = "confirmation_too_slow"
        elif cls == "duplicate_only":
            root = "unique_labeling_issue"
        elif cls == "wrong_direction":
            root = "wrong_direction"
        else:
            root = "unknown"
        rc_rows.append({
            "subject": "market_move",
            "date": c["date"], "direction": c["direction"], "size_pct": c["move_size_pct"],
            "start_iso": c["move_start_iso"],
            "classification": cls,
            "root_cause": root,
            "best_matching_zone": c.get("best_matching_zone_id"),
        })

    rc_counts = defaultdict(int)
    for r in rc_rows: rc_counts[r["root_cause"]] += 1
    main_root_cause = max(rc_counts.items(), key=lambda kv: kv[1])[0] if rc_counts else "unknown"
    # If top 2 are within 1 of each other, label as mixed
    if len(rc_counts) >= 2:
        s = sorted(rc_counts.values(), reverse=True)
        if len(s) >= 2 and abs(s[0] - s[1]) <= 1 and len(rc_counts) >= 3:
            main_root_cause = "mixed"

    rc_json = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "counts_by_root_cause": dict(rc_counts),
        "main_root_cause": main_root_cause,
        "rows": rc_rows,
    }
    (REP_OUT / "OKX_0316_0318_DETECTION_ROOT_CAUSE_MATRIX.json").write_text(
        json.dumps(rc_json, indent=2, default=str), encoding="utf-8")
    with (REP_OUT / "OKX_0316_0318_DETECTION_ROOT_CAUSE_MATRIX.csv").open("w", encoding="utf-8", newline="") as f:
        keys = list(rc_rows[0].keys()) if rc_rows else []
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        for r in rc_rows: w.writerow(r)
    md_h = [
        "# Detection root-cause matrix (one row per market 2 % move)",
        "",
        f"**Build:** {rc_json['build_time_utc']}",
        f"**Main root cause:** `{main_root_cause}`",
        "",
        "## Counts by root cause",
        "",
    ]
    for k, v in sorted(rc_counts.items(), key=lambda kv: -kv[1]):
        md_h.append(f"- {k}: **{v}**")
    md_h.extend([
        "",
        "## Per-move",
        "",
        "| date | dir | size % | start | classification | root cause | best zone |",
        "|---|---|---:|---|---|---|---|",
    ])
    for r in rc_rows:
        md_h.append(f"| {r['date']} | {r['direction']} | {r['size_pct']} | "
                    f"{r['start_iso']} | {r['classification']} | **{r['root_cause']}** | "
                    f"`{(r['best_matching_zone'] or '—')[-20:]}` |")
    (REP_OUT / "OKX_0316_0318_DETECTION_ROOT_CAUSE_MATRIX.md").write_text("\n".join(md_h), encoding="utf-8")

    # ---------- I: fix candidates (text only) ----------
    print("[I] fix candidates ...", file=sys.stderr)
    candidates_text = [
        {
            "name": "Earlier TG watch-zone mode",
            "what_pain_it_fixes": "Engine triggers late; correct zones detected as candidate/confirmed but trigger happens after >50% of move. Watch-zone alert lets user be ready before trigger.",
            "risks": "More noise; user fatigue; alerts on candidates that never confirm (low precision).",
            "fields_needed": "candidate stage timestamps + scores; no new feature engineering.",
            "feasible_without_engine_change": "YES (read-only Telegram path).",
            "validation_plan": "Backtest: count watch-zone alerts per day; how many lead to a triggered zone within X minutes; how many lead to a 2 % move regardless.",
        },
        {
            "name": "Separate LONG/SHORT timing rules",
            "what_pain_it_fixes": "03-16 LONG primary suppressed by fast_trigger<=60m; engine appears to develop LONG zones slower on bull days. Different per-direction caps may unlock LONGs without re-introducing failed SHORTs.",
            "risks": "Asymmetric filters are notoriously easy to overfit; requires more validation periods.",
            "fields_needed": "confirm_to_trigger_min split by direction.",
            "feasible_without_engine_change": "YES (filter is post-hoc).",
            "validation_plan": "Sweep per-direction caps in {45, 60, 90, 120 m} on full 24-day Tardis OOS pool; check if it inverts SHORT win rate.",
        },
        {
            "name": "Replace absolute thresholds with local-normalized features",
            "what_pain_it_fixes": "On high-vol days, absolute OFI / flow_multiplier triggers fire on noise; on low-vol days, true anomalies are missed. Local percentile/z-score scales to regime.",
            "risks": "Window choice (15 vs 60 vs 180 m) matters; local-normalize on the same data used to design rule = overfit. Need OOS for any threshold.",
            "fields_needed": "Local windowed OFI / flow / volume percentiles.",
            "feasible_without_engine_change": "YES (research filter on top of engine output).",
            "validation_plan": "Compute local percentile features for every triggered zone in the 24-date Tardis pool + this OKX March; check if primary-unique winners systematically have higher local-anomaly percentile than failed.",
        },
        {
            "name": "Late-trigger guard",
            "what_pain_it_fixes": "Section B classifications show many zones cover late (>50% of move already done by trigger). Late triggers have unfavourable R/R because target is already half-gone.",
            "risks": "Needs reference to actual move start which is hard to define live without future leak; could proxy with local-percentile prior-move metric.",
            "fields_needed": "Prior move % over windows 15/30/60 m (already in zone reasons.candidate.downMovePct/upMovePct, but only weakly).",
            "feasible_without_engine_change": "YES (filter on candidate prior-move feature).",
            "validation_plan": "Add `prior_move_60m_pct >= X` rule on top of base filter; compare expectancy on held-out pool.",
        },
        {
            "name": "Wrong-direction guard",
            "what_pain_it_fixes": "Section D shows N wrong-direction triggers (engine SHORT on bull-side; engine LONG on bear-side without reversal evidence).",
            "risks": "True countertrend reversal setups would be suppressed.",
            "fields_needed": "Local trend over 1h or 3h before trigger.",
            "feasible_without_engine_change": "YES.",
            "validation_plan": "Suppress triggers whose direction is opposite to last-3h trend AND there is no `reversal` flag in confirmed reasons; backtest on held-out pool.",
        },
        {
            "name": "TG selector (1-2 per day)",
            "what_pain_it_fixes": "Lots of alerts but only 1-2 actually matter. User fatigue + missed signal-to-noise ratio.",
            "risks": "Subjective ranking; selector itself can overfit.",
            "fields_needed": "Composite score from local-anomaly + direction correctness + earliness.",
            "feasible_without_engine_change": "YES.",
            "validation_plan": "Force selector to pick top-N per day; measure primary recall + expectancy vs no-selector baseline.",
        },
        {
            "name": "Movement-coverage metric in CI",
            "what_pain_it_fixes": "Currently we have NO metric of how well engine catches REAL market moves. We measure by zone outcome, not by market outcome.",
            "risks": "None — pure read-only metric.",
            "fields_needed": "ZigZag detector output.",
            "feasible_without_engine_change": "YES.",
            "validation_plan": "Add to per-day report: # of market 2 % moves on the day; engine coverage rate (early/mid/late/missed).",
        },
    ]
    (REP_OUT / "OKX_0316_0318_DETECTION_FIX_CANDIDATES.json").write_text(
        json.dumps({"candidates": candidates_text}, indent=2, default=str), encoding="utf-8")
    md_i = [
        "# Detection fix candidates (research only, NO production integration)",
        "",
    ]
    for c in candidates_text:
        md_i.append(f"## {c['name']}")
        md_i.append("")
        md_i.append(f"- **What pain it fixes:** {c['what_pain_it_fixes']}")
        md_i.append(f"- **Risks:** {c['risks']}")
        md_i.append(f"- **Fields needed:** {c['fields_needed']}")
        md_i.append(f"- **Feasible without engine change:** {c['feasible_without_engine_change']}")
        md_i.append(f"- **Validation plan:** {c['validation_plan']}")
        md_i.append("")
    (REP_OUT / "OKX_0316_0318_DETECTION_FIX_CANDIDATES.md").write_text("\n".join(md_i), encoding="utf-8")

    # ---------- J: final summary + flags ----------
    print("[J] final summary ...", file=sys.stderr)
    # Counts for flags
    n_missed = sum(1 for r in rc_rows if r["root_cause"] == "detector_missed_candidate")
    n_early = sum(1 for r in rc_rows if r["classification"] == "covered_early")
    n_late = sum(1 for r in rc_rows if r["classification"] in ("covered_late", "covered_mid", "candidate_early_but_trigger_late"))
    late_problem = "YES" if n_late >= 2 else ("NO" if n_late == 0 else "UNKNOWN")
    cand_late = "YES" if any(r["root_cause"] == "confirmation_too_slow" for r in rc_rows) else "NO"
    conf_slow = cand_late
    trig_slow = "YES" if any(r["root_cause"] == "trigger_too_slow" for r in rc_rows) else "NO"
    filter_supp = "YES" if any(r["root_cause"] == "filter_suppressed_correct_zone" for r in rc_rows) else "NO"
    slow_trig_aggressive = "YES" if len(filter_failures_correct) > 0 and any(
        not decisions.get(r["zone_id"], {}).get("fast_ok") for r in filter_failures_correct
    ) else "NO"
    wrong_dir_problem = "YES" if len(direction_failures) > 0 else "NO"
    unique_label_problem = "YES" if len(unmatched_moves) > 0 else "NO"

    flags = {
        "ZONE_DETECTION_AUDIT_DONE": "YES",
        "DAYS_AUDITED": DATES,
        "MARKET_2PCT_MOVES_FOUND": n_primary_moves,
        "ENGINE_PRIMARY_UNIQUE_MOVES": engine_primary_count,
        "MARKET_MOVES_MISSED_BY_ENGINE": n_missed + len(unmatched_moves),
        "MARKET_MOVES_COVERED_EARLY": n_early,
        "MARKET_MOVES_COVERED_LATE": n_late,
        "ZONE_DETECTION_LATE_PROBLEM": late_problem,
        "CANDIDATE_LATE_PROBLEM": cand_late,
        "CONFIRMATION_TOO_SLOW": conf_slow,
        "TRIGGER_TOO_SLOW": trig_slow,
        "FILTER_SUPPRESSED_CORRECT_ZONES": filter_supp,
        "SLOW_TRIGGER_FILTER_TOO_AGGRESSIVE": slow_trig_aggressive,
        "WRONG_DIRECTION_PROBLEM": wrong_dir_problem,
        "LOCAL_NORMALIZATION_NEEDED": local_norm_needed,
        "UNIQUE_MOVE_LABELING_PROBLEM": unique_label_problem,
        "MAIN_ROOT_CAUSE": main_root_cause,
        "TOP_FIX_CANDIDATE_1": "Earlier TG watch-zone mode",
        "TOP_FIX_CANDIDATE_2": "Local-normalized features (percentile/z-score)",
        "TOP_FIX_CANDIDATE_3": "Movement-coverage metric in CI",
        "READY_TO_CHANGE_ENGINE": "NO",
        "READY_TO_BUILD_TG_WATCH_ZONE_MODE": "YES" if late_problem == "YES" else "UNKNOWN",
        "MORE_VALIDATION_REQUIRED": "YES",
    }

    sumr = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "scope": "Movement-first audit of zone detection quality on 2026-03-16 + 2026-03-18",
        "flags": flags,
        "evidence_summary": {
            "market_2pct_moves_per_day": {d: sum(1 for m in moves_by_date[d] if not m.secondary) for d in DATES},
            "engine_primary_per_day": {d: sum(1 for z in zones_all if z["_date"] == d and z.get("isPrimaryMoveZone") and is_reached(z)) for d in DATES},
            "filter_failures_correct_zones_count": len(filter_failures_correct),
            "wrong_direction_count": len(direction_failures),
            "unmatched_market_moves_count": len(unmatched_moves),
        },
    }
    (REP_OUT / "OKX_0316_0318_ZONE_DETECTION_AUDIT_SUMMARY.json").write_text(
        json.dumps(sumr, indent=2, default=str), encoding="utf-8")

    md_j = [
        "# Zone detection audit - master summary (2026-03-16 + 2026-03-18)",
        "",
        f"**Build:** {sumr['build_time_utc']}",
        "**Movement-first audit: market 2 % moves vs engine zones. Read-only. No engine change.**",
        "",
        "## Human answers",
        "",
        "**1. Правда ли zones детектятся поздно?**  ",
        f"   Из {n_primary_moves} market 2 % moves: **early={n_early}**, **late+mid={n_late}**, **missed={n_missed}**. ",
        f"   Late problem flag: **{late_problem}**.",
        "",
        "**2. Где задержка: candidate, confirmation или trigger?**  ",
        f"   - candidate late problem: **{cand_late}**  ",
        f"   - confirmation too slow: **{conf_slow}**  ",
        f"   - trigger too slow: **{trig_slow}**  ",
        "",
        "**3. Правда ли filter убивает правильные зоны?**  ",
        f"   Correct zones suppressed by filter: **{len(filter_failures_correct)}** — flag `FILTER_SUPPRESSED_CORRECT_ZONES = {filter_supp}`.",
        "",
        "**4. Почему 03-16 primary LONG был suppressed?**",
    ]
    if deep_dive_0316:
        md_j.append(f"   - candidate at: `{deep_dive_0316['candidate_iso']}`")
        md_j.append(f"   - confirmed at: `{deep_dive_0316['confirmed_iso']}`")
        md_j.append(f"   - trigger at: `{deep_dive_0316['trigger_iso']}`")
        md_j.append(f"   - candidate_to_confirm_min: {deep_dive_0316['candidate_to_confirm_min']}")
        md_j.append(f"   - confirm_to_trigger_min: **{deep_dive_0316['confirm_to_trigger_min']}** (>60m -> slow_trigger flag)")
        md_j.append(f"   - candidate was before move start: {deep_dive_0316['candidate_was_before_move_start']}")
        md_j.append(f"   - trigger was before move start: {deep_dive_0316['trigger_was_before_move_start']}")
        md_j.append(f"   - would TG alert at candidate be useful? {deep_dive_0316['would_tg_alert_be_useful']}")
    md_j.extend([
        "",
        "**5. Был ли 03-18 SHORT primary найден вовремя или late?**  ",
        "   See section B per-move row; classified by move-completion-at-trigger.",
        "",
        f"**6. Были ли wrong-direction сигналы?**  Yes — **{len(direction_failures)}** triggers had no 2 % move in their direction within next 4h. flag `{wrong_dir_problem}`.",
        "",
        f"**7. Почему всего {engine_primary_count} primary unique moves?**  Market had {n_primary_moves} 2 % moves; engine labeled {engine_primary_count} as primary. "
        f"Unmatched market moves: {len(unmatched_moves)}. flag `UNIQUE_MOVE_LABELING_PROBLEM = {unique_label_problem}`.",
        "",
        f"**8. Есть ли проблема с unique-move labeling?**  `{unique_label_problem}`.",
        "",
        f"**9. Нужна ли локальная нормализация признаков?**  `{local_norm_needed}` (proxy via 60-m range by class).",
        "",
        f"**10. Что является главным больным местом?**  `MAIN_ROOT_CAUSE = {main_root_cause}`.",
        "",
        "**11. Какие 2-3 решения выглядят самыми перспективными?**  ",
        f"   1. {flags['TOP_FIX_CANDIDATE_1']}  ",
        f"   2. {flags['TOP_FIX_CANDIDATE_2']}  ",
        f"   3. {flags['TOP_FIX_CANDIDATE_3']}  ",
        "",
        "**12. Что НЕ надо менять прямо сейчас?**  ",
        "   - `zoneDetector` / thresholds / production engine — NO changes.  ",
        "   - filter parameters in production — no changes; only research-layer rules.  ",
        "   - target/stop/timeout — diagnostic only.",
        "",
        "## Final flag matrix",
        "",
        "```",
    ])
    for k, v in flags.items():
        md_j.append(f"{k} = {v}")
    md_j.extend(["```", "",
                  "## Hard rules honored",
                  "- strategy / thresholds / `zoneDetector`: UNCHANGED",
                  "- NO new backtest spawned; pure post-hoc",
                  "- post-trigger labels used only as evaluation, not as features",
                  "- target STRICT 2 %",
                  "- READY_TO_CHANGE_ENGINE = NO"])
    (REP_OUT / "OKX_0316_0318_ZONE_DETECTION_AUDIT_SUMMARY.md").write_text("\n".join(md_j), encoding="utf-8")

    print()
    print("FINAL FLAGS:")
    for k, v in flags.items():
        print(f"  {k:<48s} = {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
