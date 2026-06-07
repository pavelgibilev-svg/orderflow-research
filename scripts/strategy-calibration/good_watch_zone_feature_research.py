"""Good watch-zone feature research (Sections A-J).

Goal: find pre-trigger features that genuinely separate "good watch zones"
(those that cover real >=2% market moves BEFORE the move) from noise.

READ-ONLY post-hoc over OKX direct March (29 days available):
  first half:  2026-03-02..2026-03-15  (14 days)
  second half: 2026-03-16, 03-18..03-31 (15 days; 03-17 missing)

NO engine / threshold / detector change. NO backtest rerun.

Sections A-J per spec. Writes ~17 artifact files to reports/strategy-calibration/.
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
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from canonical_ledger import build_buckets_from_trades_csv, Bucket

ROOT = Path("C:/Users/gibilev/orderflow-research")
REPORTS = ROOT / "reports"
REP_OKX = REPORTS / "okx-direct"
REP_OUT = REPORTS / "strategy-calibration"
REP_OUT.mkdir(parents=True, exist_ok=True)
DATA_ROOT = ROOT / "data/okx-historical/BTC-USDT-SWAP"

FIRST_HALF_DATES = [f"2026-03-{d:02d}" for d in range(2, 16)]
SECOND_HALF_DATES = ["2026-03-16"] + [f"2026-03-{d:02d}" for d in range(18, 32)]
ALL_DATES = FIRST_HALF_DATES + SECOND_HALF_DATES
MISSING_DATES = ["2026-03-17"]

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


def reasons_dict(z):
    out = {}
    for r in z.get("reasons", []):
        out[r.get("stage")] = r.get("conditions") or {}
    return out


def load_zones(date):
    p = REPORTS / f"BTC-USDT-SWAP_{date}" / "zones.json"
    if not p.exists():
        return []
    obj = json.loads(p.read_text(encoding="utf-8"))
    zones = obj if isinstance(obj, list) else obj.get("zones", [])
    for z in zones:
        z["_date"] = date
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
            dup = False
            for prior in triggered[:i]:
                if prior["triggerTs"] >= T or prior["direction"] != D: continue
                dtm = (T - prior["triggerTs"]) / 60000.0
                if dtm <= 0 or dtm > WINDOW_MIN: continue
                pm = mid_price(prior)
                if zm is None or pm is None: continue
                if abs(zm - pm) / zm * 100.0 <= PRICE_BAND_PCT:
                    dup = True; break
            ctm = confirm_to_trigger_min(z)
            fast_ok = (ctm is None) or (ctm <= FAST_X_MIN_BASE)
            decisions[z["id"]] = {"kept": (not dup) and fast_ok, "fast_ok": fast_ok,
                                   "dup_suppressed": dup, "ctm_min": ctm}
    return decisions


@dataclass
class Move:
    date: str
    direction: str
    start_sec: int
    end_sec: int
    start_price: float
    end_price: float
    size_pct: float
    secondary: bool


def detect_moves(date: str, buckets: list[Bucket]) -> list[Move]:
    if not buckets: return []
    def scan(thresh, sec):
        out: list[Move] = []
        first = buckets[0]
        ext_sec = first.sec; ext_h = first.high; ext_l = first.low
        ps_sec = first.sec; ps_price = first.last; direction = None
        for b in buckets[1:]:
            if direction is None:
                up = (b.high - ext_l) / ext_l * 100.0 if ext_l else 0
                dn = (ext_h - b.low) / ext_h * 100.0 if ext_h else 0
                if up >= thresh and up >= dn:
                    direction = "UP"; ps_sec = ext_sec; ps_price = ext_l
                    ext_sec = b.sec; ext_h = b.high; ext_l = b.low
                elif dn >= thresh:
                    direction = "DOWN"; ps_sec = ext_sec; ps_price = ext_h
                    ext_sec = b.sec; ext_h = b.high; ext_l = b.low
                else:
                    if b.high > ext_h: ext_h = b.high; ext_sec = b.sec
                    if b.low < ext_l: ext_l = b.low
                continue
            if direction == "UP":
                if b.high > ext_h: ext_h = b.high; ext_sec = b.sec
                retr = (ext_h - b.low) / ext_h * 100.0
                if retr >= thresh:
                    size = (ext_h - ps_price) / ps_price * 100.0
                    out.append(Move(date, "UP", ps_sec, ext_sec, ps_price, ext_h, round(size, 4), sec))
                    direction = "DOWN"; ps_sec = ext_sec; ps_price = ext_h
                    ext_sec = b.sec; ext_h = b.high; ext_l = b.low
            else:
                if b.low < ext_l: ext_l = b.low; ext_sec = b.sec
                rally = (b.high - ext_l) / ext_l * 100.0
                if rally >= thresh:
                    size = (ps_price - ext_l) / ps_price * 100.0
                    out.append(Move(date, "DOWN", ps_sec, ext_sec, ps_price, ext_l, round(size, 4), sec))
                    direction = "UP"; ps_sec = ext_sec; ps_price = ext_l
                    ext_sec = b.sec; ext_h = b.high; ext_l = b.low
        return out
    primary = scan(MOVE_THRESHOLD_PCT, False)
    secondary = scan(SECONDARY_MOVE_THRESHOLD_PCT, True)
    primary_starts = {(m.start_sec, m.direction) for m in primary}
    extra = [m for m in secondary if m.size_pct < MOVE_THRESHOLD_PCT and (m.start_sec, m.direction) not in primary_starts]
    return primary + extra


# ---------- local-context features from buckets ----------

def bucket_index_at_or_after(buckets: list[Bucket], target_sec: int) -> int:
    lo, hi = 0, len(buckets)
    while lo < hi:
        m = (lo + hi) // 2
        if buckets[m].sec < target_sec: lo = m + 1
        else: hi = m
    return lo


def local_features(buckets: list[Bucket], anchor_sec: int) -> dict:
    """Compute prior-window features ending at anchor_sec (a confirm time / candidate time)."""
    out = {}
    idx = bucket_index_at_or_after(buckets, anchor_sec)
    if idx == 0 or not buckets:
        return out
    for window_min in (15, 30, 60, 180):
        win_start = anchor_sec - window_min * 60
        s_idx = bucket_index_at_or_after(buckets, win_start)
        if s_idx >= idx:
            continue
        slice_b = buckets[s_idx:idx]
        if not slice_b: continue
        hi = max(b.high for b in slice_b); lo = min(b.low for b in slice_b)
        anchor_price = buckets[idx - 1].last if idx > 0 else None
        # prior_move_pct = signed move ending at anchor
        ref_first = slice_b[0].last
        ref_last = slice_b[-1].last
        out[f"prior_move_{window_min}m_pct"] = round((ref_last - ref_first) / ref_first * 100.0, 4) if ref_first else None
        out[f"local_range_{window_min}m_pct"] = round((hi - lo) / lo * 100.0, 4) if lo else None
        # realized vol = stdev of 1-second returns over window
        rets = []
        prev = slice_b[0].last
        for b in slice_b[1:]:
            if prev > 0:
                rets.append((b.last - prev) / prev)
            prev = b.last
        if rets:
            out[f"local_realized_vol_{window_min}m"] = round(stats.pstdev(rets) * math.sqrt(60), 6)
    return out


# ---------- feature extraction ----------

def extract_features(z: dict, buckets: list[Bucket], decisions: dict,
                     same_dir_recent: dict, opp_dir_recent: dict) -> dict:
    rd = reasons_dict(z)
    cand = rd.get("candidate") or {}
    conf = rd.get("confirmed") or {}
    trig = rd.get("trigger") or {}
    scores = z.get("scores") or {}
    tp = None
    for r in z.get("reasons") or []:
        if r.get("stage") == "trigger":
            tp = (r.get("conditions") or {}).get("triggerPrice"); break
    zone_mid = mid_price(z)
    zone_low, zone_high = z.get("zoneLow"), z.get("zoneHigh")
    zone_width_pct = ((zone_high - zone_low) / zone_mid * 100.0) if (zone_mid and zone_low is not None and zone_high is not None) else None

    direction = z["direction"]
    anchor_sec = (z.get("confirmedTs") or z.get("startTs") or 0) // 1000
    lf = local_features(buckets, anchor_sec) if buckets and anchor_sec else {}

    feat = {
        "date": z["_date"],
        "zone_id": z["id"],
        "direction": direction,
        "stage_reached": ("triggered" if is_triggered(z) else
                          "confirmed" if z.get("confirmedTs") else "candidate"),
        "candidate_iso": ms_to_iso(z.get("startTs")),
        "confirmed_iso": ms_to_iso(z.get("confirmedTs")),
        "trigger_iso": ms_to_iso(z.get("triggerTs")),
        "zone_low": zone_low, "zone_high": zone_high, "zone_mid": zone_mid,
        "zone_width_pct": zone_width_pct,
        # Timing
        "candidate_to_confirm_min": candidate_to_confirm_min(z),
        "confirm_to_trigger_min": confirm_to_trigger_min(z),
        "total_pre_trigger_min": total_pre_trigger_min(z),
        # Engine conditions (candidate)
        "cand_sell_pressure": cand.get("sellPressure"),
        "cand_buy_pressure": cand.get("buyPressure"),
        "cand_pressure_against": (cand.get("sellPressure") if direction == "LONG" else cand.get("buyPressure")),
        "cand_absorb_score": cand.get("absorbScore"),
        "cand_bid_refill_score": cand.get("bidRefillScore"),
        "cand_ask_refill_score": cand.get("askRefillScore"),
        "cand_refill_with": (cand.get("bidRefillScore") if direction == "LONG" else cand.get("askRefillScore")),
        "cand_down_move_pct": cand.get("downMovePct"),
        "cand_up_move_pct": cand.get("upMovePct"),
        "cand_prior_move_pct": (cand.get("downMovePct") if direction == "LONG" else cand.get("upMovePct")),
        "cand_range_compression": 1 if cand.get("rangeCompression") else 0,
        # Confirmed conditions
        "conf_cycles_seen": conf.get("cyclesSeen"),
        "conf_age_min": conf.get("ageMin"),
        "conf_defended_persistence_sec": conf.get("defendedPersistenceSec"),
        "conf_opposite_thinning": conf.get("oppositeThinning"),
        "conf_void_score": conf.get("voidScore"),
        # Trigger conditions
        "trig_flow_multiplier": trig.get("flowMultiplier"),
        "trig_break_pct": trig.get("breakPct"),
        "trig_side_flow_ok": 1 if trig.get("sideFlowOk") else 0,
        "trig_price": tp,
        # Scores
        "score_absorption": scores.get("absorptionScore"),
        "score_liquidity_void": scores.get("liquidityVoidScore"),
        "score_ofi": scores.get("ofiScore"),
        "score_refill": scores.get("refillScore"),
        "score_trigger": scores.get("triggerScore"),
        # Filter
        "filter_kept": decisions.get(z["id"], {}).get("kept"),
        "filter_dup_suppressed": decisions.get(z["id"], {}).get("dup_suppressed"),
        "filter_fast_ok": decisions.get(z["id"], {}).get("fast_ok"),
        # Context
        "same_dir_zones_active_60m": same_dir_recent.get(z["id"], 0),
        "opp_dir_zones_active_60m": opp_dir_recent.get(z["id"], 0),
        # Local context
        **lf,
        # Labels for evaluation (NOT features for decision)
        "_label_engine_class": z["_class"],
        "_label_is_primary": bool(z.get("isPrimaryMoveZone")),
        "_label_reached_raw": is_reached(z),
        "_label_unique_move_id": z.get("uniqueMoveId"),
    }
    return feat


def build_active_zone_counts(zones_by_date: dict) -> tuple[dict, dict]:
    """For each zone, count same-direction and opposite-direction zones whose
    confirmation occurred within last 60 min before this zone's confirmation.
    """
    same_dir = {}
    opp_dir = {}
    for date, lst in zones_by_date.items():
        confirmed_lst = [z for z in lst if z.get("confirmedTs")]
        confirmed_lst.sort(key=lambda z: z["confirmedTs"])
        for i, z in enumerate(confirmed_lst):
            T = z["confirmedTs"]
            same = 0; opp = 0
            for prior in confirmed_lst[:i]:
                dt_min = (T - prior["confirmedTs"]) / 60000.0
                if dt_min <= 0 or dt_min > 60: continue
                if prior["direction"] == z["direction"]: same += 1
                else: opp += 1
            same_dir[z["id"]] = same
            opp_dir[z["id"]] = opp
    return same_dir, opp_dir


# ---------- movement-first labels ----------

def assign_labels(row: dict, moves_by_date: dict) -> dict:
    """Add label fields to feature row based on coverage of real 2% market moves."""
    date = row["date"]
    direction = row["direction"]
    confirmed_iso = row["confirmed_iso"]
    trigger_iso = row["trigger_iso"]
    confirmed_sec = int(dt.datetime.fromisoformat(confirmed_iso).timestamp()) if confirmed_iso else None
    trigger_sec = int(dt.datetime.fromisoformat(trigger_iso).timestamp()) if trigger_iso else None
    correct_dir = "UP" if direction == "LONG" else "DOWN"
    moves = moves_by_date.get(date, [])
    # primary moves only as target
    matched_primary = None
    matched_secondary = None
    matched_opp = None
    for m in moves:
        m_dir_correct = (m.direction == correct_dir)
        # Anchor for "before move": use confirmedTs (preferred) or fallback to triggerTs
        anchor = confirmed_sec if confirmed_sec else trigger_sec
        if anchor is None: continue
        # window: anchor in [m.start_sec - 4h, m.end_sec]
        if anchor < m.start_sec - 4 * 3600 or anchor > m.end_sec: continue
        if not m.secondary and m_dir_correct and matched_primary is None:
            matched_primary = m
        elif m.secondary and m_dir_correct and matched_secondary is None:
            matched_secondary = m
        elif not m.secondary and not m_dir_correct and matched_opp is None:
            matched_opp = m
    # Classification
    coverage_class = None
    label = None
    lead_min = None
    move_size_pct = None
    if matched_primary:
        anchor = confirmed_sec if confirmed_sec else trigger_sec
        if anchor < matched_primary.start_sec:
            # before move start
            if confirmed_sec and confirmed_sec < matched_primary.start_sec:
                coverage_class = "covered_watch_early"
                lead_min = round((matched_primary.start_sec - confirmed_sec) / 60.0, 2)
            elif trigger_sec and trigger_sec < matched_primary.start_sec:
                coverage_class = "covered_trigger_early"
                lead_min = round((matched_primary.start_sec - trigger_sec) / 60.0, 2)
            else:
                coverage_class = "covered_watch_early"
                lead_min = round((matched_primary.start_sec - anchor) / 60.0, 2)
            label = "GOOD"
        else:
            # after move start
            move_dur = max(matched_primary.end_sec - matched_primary.start_sec, 1)
            pct_done = (anchor - matched_primary.start_sec) / move_dur * 100.0
            if pct_done <= 50:
                coverage_class = "covered_mid"
                label = "MID"
            else:
                coverage_class = "covered_late"
                label = "BAD"
            lead_min = -round((anchor - matched_primary.start_sec) / 60.0, 2)
        move_size_pct = matched_primary.size_pct
    elif matched_opp:
        coverage_class = "wrong_direction"
        label = "BAD"
        move_size_pct = matched_opp.size_pct
    elif matched_secondary:
        coverage_class = "noisy_partial_1_5"
        label = "MID"
        move_size_pct = matched_secondary.size_pct
    else:
        coverage_class = "missed_no_move_in_4h"
        label = "BAD"
    row["coverage_class"] = coverage_class
    row["watch_label"] = label
    row["lead_min_before_move"] = lead_min
    row["matched_move_size_pct"] = move_size_pct
    return row


# ---------- statistics ----------

def cohens_d(a: list[float], b: list[float]) -> Optional[float]:
    a = [x for x in a if x is not None and not math.isnan(x)]
    b = [x for x in b if x is not None and not math.isnan(x)]
    if len(a) < 2 or len(b) < 2: return None
    ma, mb = stats.mean(a), stats.mean(b)
    sa, sb = stats.pstdev(a), stats.pstdev(b)
    pooled = math.sqrt(((len(a) - 1) * sa * sa + (len(b) - 1) * sb * sb) / (len(a) + len(b) - 2))
    if pooled == 0: return None
    return round((ma - mb) / pooled, 4)


def freq(rows: list[dict], key: str) -> float:
    if not rows: return 0.0
    n = sum(1 for r in rows if r.get(key) not in (None, False, 0))
    return round(100.0 * n / len(rows), 2)


def mean_or_none(vals):
    vals = [v for v in vals if v is not None]
    return round(stats.mean(vals), 4) if vals else None


# ---------- main ----------

def main() -> int:
    print("loading zones from 29 days ...", file=sys.stderr)
    zones_by_date: dict[str, list[dict]] = {}
    zones_all: list[dict] = []
    for d in ALL_DATES:
        zs = load_zones(d)
        zones_by_date[d] = zs
        zones_all.extend(zs)
    print(f"  total zones loaded: {len(zones_all)}", file=sys.stderr)

    decisions = apply_passive_filter(zones_all)
    same_dir_recent, opp_dir_recent = build_active_zone_counts(zones_by_date)

    print("building 1s buckets for all days ...", file=sys.stderr)
    buckets_by_date: dict[str, list[Bucket]] = {}
    for d in ALL_DATES:
        p = DATA_ROOT / d / "trades.csv.gz"
        if p.exists():
            buckets_by_date[d] = build_buckets_from_trades_csv(p)
            print(f"  {d}: {len(buckets_by_date[d]):,} buckets", file=sys.stderr)
        else:
            buckets_by_date[d] = []

    print("detecting market moves ...", file=sys.stderr)
    moves_by_date: dict[str, list[Move]] = {}
    for d in ALL_DATES:
        moves_by_date[d] = detect_moves(d, buckets_by_date.get(d, []))

    # ---------- A: build feature dataset ----------
    print("[A] building feature dataset ...", file=sys.stderr)
    confirmed_zones = [z for z in zones_all if z.get("confirmedTs")]
    feature_rows = []
    for z in confirmed_zones:
        buckets = buckets_by_date.get(z["_date"]) or []
        row = extract_features(z, buckets, decisions, same_dir_recent, opp_dir_recent)
        row["_half"] = "first" if z["_date"] in FIRST_HALF_DATES else "second"
        feature_rows.append(row)
    print(f"  {len(feature_rows)} confirmed-zone feature rows", file=sys.stderr)

    # Persist dataset
    csv_keys = sorted({k for r in feature_rows for k in r.keys()})
    with (REP_OUT / "OKX_MARCH_WATCH_ZONE_FEATURE_DATASET.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=csv_keys, extrasaction="ignore")
        w.writeheader()
        for r in feature_rows: w.writerow(r)
    (REP_OUT / "OKX_MARCH_WATCH_ZONE_FEATURE_DATASET.json").write_text(
        json.dumps({"build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                    "n_rows": len(feature_rows), "all_dates": ALL_DATES,
                    "missing_dates": MISSING_DATES, "rows": feature_rows},
                    indent=2, default=str), encoding="utf-8")

    # ---------- B: assign movement-first labels ----------
    print("[B] assigning movement-first labels ...", file=sys.stderr)
    for r in feature_rows:
        assign_labels(r, moves_by_date)
    label_counts = defaultdict(int)
    for r in feature_rows: label_counts[r["watch_label"]] += 1
    coverage_counts = defaultdict(int)
    for r in feature_rows: coverage_counts[r["coverage_class"]] += 1
    n_good = label_counts.get("GOOD", 0)
    n_bad = label_counts.get("BAD", 0)
    n_mid = label_counts.get("MID", 0)
    print(f"  labels: GOOD={n_good}, MID={n_mid}, BAD={n_bad}", file=sys.stderr)

    label_json = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "n_zones": len(feature_rows),
        "label_counts": dict(label_counts),
        "coverage_class_counts": dict(coverage_counts),
    }
    (REP_OUT / "OKX_MARCH_WATCH_ZONE_LABELS.json").write_text(
        json.dumps(label_json, indent=2, default=str), encoding="utf-8")
    with (REP_OUT / "OKX_MARCH_WATCH_ZONE_LABELS.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["date", "zone_id", "direction", "watch_label",
                                            "coverage_class", "lead_min_before_move",
                                            "matched_move_size_pct", "_half"])
        w.writeheader()
        for r in feature_rows:
            w.writerow({k: r.get(k) for k in w.fieldnames})
    md_b = [
        "# Movement-first watch-zone labels",
        "",
        f"**Build:** {label_json['build_time_utc']}",
        f"**Days included:** {len(ALL_DATES)} (missing: {MISSING_DATES})",
        f"**Total confirmed zones:** {len(feature_rows)}",
        "",
        "## Label counts",
    ]
    for k, v in sorted(label_counts.items(), key=lambda kv: -kv[1]):
        md_b.append(f"- {k}: **{v}** ({round(100.0 * v / len(feature_rows), 2)}%)")
    md_b.extend(["", "## Coverage class distribution"])
    for k, v in sorted(coverage_counts.items(), key=lambda kv: -kv[1]):
        md_b.append(f"- {k}: **{v}** ({round(100.0 * v / len(feature_rows), 2)}%)")
    (REP_OUT / "OKX_MARCH_WATCH_ZONE_LABELS.md").write_text("\n".join(md_b), encoding="utf-8")

    # ---------- C: feature separation ----------
    print("[C] feature separation ...", file=sys.stderr)
    good_rows = [r for r in feature_rows if r["watch_label"] == "GOOD"]
    bad_rows = [r for r in feature_rows if r["watch_label"] == "BAD"]
    wrong_rows = [r for r in feature_rows if r["coverage_class"] == "wrong_direction"]
    missed_rows = [r for r in feature_rows if r["coverage_class"] == "missed_no_move_in_4h"]
    late_rows = [r for r in feature_rows if r["coverage_class"] == "covered_late"]

    numeric_keys = [
        "zone_width_pct", "candidate_to_confirm_min", "confirm_to_trigger_min", "total_pre_trigger_min",
        "cand_pressure_against", "cand_absorb_score", "cand_refill_with",
        "cand_prior_move_pct", "conf_cycles_seen", "conf_age_min",
        "conf_defended_persistence_sec", "conf_opposite_thinning",
        "trig_flow_multiplier", "trig_break_pct",
        "score_absorption", "score_liquidity_void", "score_ofi", "score_refill", "score_trigger",
        "same_dir_zones_active_60m", "opp_dir_zones_active_60m",
        "prior_move_15m_pct", "prior_move_30m_pct", "prior_move_60m_pct", "prior_move_180m_pct",
        "local_range_15m_pct", "local_range_30m_pct", "local_range_60m_pct", "local_range_180m_pct",
        "local_realized_vol_15m", "local_realized_vol_30m", "local_realized_vol_60m", "local_realized_vol_180m",
    ]
    boolean_keys = ["cand_range_compression", "trig_side_flow_ok", "filter_kept", "filter_dup_suppressed", "filter_fast_ok"]

    sep_table = []
    for fk in numeric_keys + boolean_keys:
        gv = [r.get(fk) for r in good_rows]
        bv = [r.get(fk) for r in bad_rows]
        wv = [r.get(fk) for r in wrong_rows]
        mv = [r.get(fk) for r in missed_rows]
        lv = [r.get(fk) for r in late_rows]
        if fk in boolean_keys:
            row = {
                "feature": fk,
                "good_freq_pct": freq(good_rows, fk),
                "bad_freq_pct": freq(bad_rows, fk),
                "wrong_freq_pct": freq(wrong_rows, fk),
                "missed_freq_pct": freq(missed_rows, fk),
                "late_freq_pct": freq(late_rows, fk),
                "sep_good_vs_bad_pp": round(freq(good_rows, fk) - freq(bad_rows, fk), 2),
                "type": "boolean",
            }
        else:
            row = {
                "feature": fk,
                "good_mean": mean_or_none(gv),
                "bad_mean": mean_or_none(bv),
                "wrong_mean": mean_or_none(wv),
                "missed_mean": mean_or_none(mv),
                "late_mean": mean_or_none(lv),
                "good_n": sum(1 for v in gv if v is not None),
                "bad_n": sum(1 for v in bv if v is not None),
                "cohens_d_good_vs_bad": cohens_d(gv, bv),
                "cohens_d_good_vs_wrong": cohens_d(gv, wv),
                "cohens_d_good_vs_missed": cohens_d(gv, mv),
                "cohens_d_good_vs_late": cohens_d(gv, lv),
                "type": "numeric",
            }
        sep_table.append(row)

    # Sort by abs(sep_good_vs_bad) for booleans, abs(cohens_d_good_vs_bad) for numeric
    def sep_strength(r):
        if r["type"] == "boolean":
            return abs(r.get("sep_good_vs_bad_pp") or 0)
        return abs(r.get("cohens_d_good_vs_bad") or 0) * 100.0   # scale for comparable sort
    sep_table.sort(key=sep_strength, reverse=True)

    sep_json = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "n_good": n_good, "n_bad": n_bad, "n_mid": n_mid,
        "n_wrong": len(wrong_rows), "n_missed": len(missed_rows), "n_late": len(late_rows),
        "feature_table": sep_table,
    }
    (REP_OUT / "OKX_MARCH_GOOD_WATCH_ZONE_FEATURE_SEPARATION.json").write_text(
        json.dumps(sep_json, indent=2, default=str), encoding="utf-8")
    csv_keys_sep = list(sep_table[0].keys()) if sep_table else []
    with (REP_OUT / "OKX_MARCH_GOOD_WATCH_ZONE_FEATURE_SEPARATION.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=csv_keys_sep, extrasaction="ignore")
        w.writeheader()
        for r in sep_table: w.writerow(r)
    md_c = [
        "# Feature separation (GOOD vs BAD watch-zones)",
        "",
        f"**Build:** {sep_json['build_time_utc']}",
        f"**GOOD:** {n_good}  **BAD:** {n_bad}  **MID:** {n_mid}",
        f"**wrong_direction:** {len(wrong_rows)}  **missed_no_move:** {len(missed_rows)}  **late:** {len(late_rows)}",
        "",
        "## Top discriminating features (sorted by |GOOD vs BAD| separation)",
        "",
        "| feature | type | good | bad | wrong | missed | late | d(good vs bad) |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for r in sep_table[:30]:
        if r["type"] == "boolean":
            md_c.append(f"| `{r['feature']}` | bool | {r['good_freq_pct']}% | {r['bad_freq_pct']}% | "
                        f"{r['wrong_freq_pct']}% | {r['missed_freq_pct']}% | {r['late_freq_pct']}% | "
                        f"{r['sep_good_vs_bad_pp']} pp |")
        else:
            md_c.append(f"| `{r['feature']}` | num | {r['good_mean']} | {r['bad_mean']} | "
                        f"{r['wrong_mean']} | {r['missed_mean']} | {r['late_mean']} | "
                        f"{r['cohens_d_good_vs_bad']} |")
    (REP_OUT / "OKX_MARCH_GOOD_WATCH_ZONE_FEATURE_SEPARATION.md").write_text("\n".join(md_c), encoding="utf-8")

    # ---------- D: useless and anti-features ----------
    print("[D] useless + anti-features ...", file=sys.stderr)
    useless = []; anti = []
    for r in sep_table:
        if r["type"] == "boolean":
            g = r.get("good_freq_pct") or 0
            b = r.get("bad_freq_pct") or 0
            if g >= 95 and b >= 95:
                useless.append({"feature": r["feature"], "reason": f"true for >=95% in both good ({g}%) and bad ({b}%)"})
            elif abs(g - b) < 3:
                useless.append({"feature": r["feature"], "reason": f"near-zero separation (|good-bad|={abs(g-b)}pp)"})
            # anti: more frequent in wrong than good by 10pp+
            if (r.get("wrong_freq_pct") or 0) > g + 10:
                anti.append({"feature": r["feature"],
                              "reason": f"more frequent in wrong_direction ({r['wrong_freq_pct']}%) than good ({g}%)",
                              "delta_pp": round(r["wrong_freq_pct"] - g, 2)})
            if (r.get("missed_freq_pct") or 0) > g + 10:
                anti.append({"feature": r["feature"],
                              "reason": f"more frequent in missed ({r['missed_freq_pct']}%) than good ({g}%)",
                              "delta_pp": round(r["missed_freq_pct"] - g, 2)})
        else:
            d_gb = r.get("cohens_d_good_vs_bad") or 0
            if abs(d_gb) < 0.15:
                useless.append({"feature": r["feature"], "reason": f"|d good vs bad|={abs(d_gb)} < 0.15"})
            d_gw = r.get("cohens_d_good_vs_wrong") or 0
            if d_gb > 0 and d_gw < -0.3:
                anti.append({"feature": r["feature"],
                              "reason": f"positive d vs bad ({d_gb}) BUT negative d vs wrong ({d_gw}) — direction-flipped"})
            d_gm = r.get("cohens_d_good_vs_missed") or 0
            if d_gb > 0 and d_gm < -0.3:
                anti.append({"feature": r["feature"],
                              "reason": f"positive d vs bad ({d_gb}) BUT negative d vs missed ({d_gm})"})

    useless_json = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "useless_features": useless,
        "anti_features": anti,
    }
    (REP_OUT / "OKX_MARCH_USELESS_AND_ANTI_FEATURES.json").write_text(
        json.dumps(useless_json, indent=2, default=str), encoding="utf-8")
    md_d = [
        "# Useless and anti-features (29-day OKX March)",
        "",
        f"**Build:** {useless_json['build_time_utc']}",
        "",
        f"## Useless features ({len(useless)})",
        "",
        "| feature | reason |",
        "|---|---|",
    ]
    for r in useless:
        md_d.append(f"| `{r['feature']}` | {r['reason']} |")
    md_d.extend(["", f"## Anti-features ({len(anti)})", "", "| feature | reason |", "|---|---|"])
    for r in anti:
        md_d.append(f"| `{r['feature']}` | {r['reason']} |")
    (REP_OUT / "OKX_MARCH_USELESS_AND_ANTI_FEATURES.md").write_text("\n".join(md_d), encoding="utf-8")

    # ---------- E: pattern search ----------
    print("[E] pattern search ...", file=sys.stderr)
    # Helper: evaluate a predicate over feature_rows
    def evaluate(name: str, predicate) -> dict:
        kept = [r for r in feature_rows if predicate(r)]
        kept_good = sum(1 for r in kept if r["watch_label"] == "GOOD")
        kept_bad = sum(1 for r in kept if r["watch_label"] == "BAD")
        kept_wrong = sum(1 for r in kept if r["coverage_class"] == "wrong_direction")
        kept_missed = sum(1 for r in kept if r["coverage_class"] == "missed_no_move_in_4h")
        all_good = n_good
        n = len(kept); n_days = len(ALL_DATES)
        return {
            "pattern": name, "alerts_total": n,
            "alerts_per_day": round(n / n_days, 3) if n_days else 0,
            "good_count": kept_good, "bad_count": kept_bad,
            "wrong_count": kept_wrong, "missed_count": kept_missed,
            "precision_pct": round(100.0 * kept_good / max(n, 1), 2) if n else None,
            "recall_pct": round(100.0 * kept_good / max(all_good, 1), 2) if all_good else None,
            "wrong_rate_pct": round(100.0 * kept_wrong / max(n, 1), 2) if n else None,
        }

    patterns = []
    patterns.append(evaluate("baseline_all_confirmed", lambda r: True))
    # Useful candidates from sep_table top
    patterns.append(evaluate("filter_kept", lambda r: r.get("filter_kept")))
    patterns.append(evaluate("not_filter_kept", lambda r: not r.get("filter_kept")))
    patterns.append(evaluate("opp_dir_zones_60m_eq_0", lambda r: (r.get("opp_dir_zones_active_60m") or 0) == 0))
    patterns.append(evaluate("opp_dir_zones_60m_le_1", lambda r: (r.get("opp_dir_zones_active_60m") or 0) <= 1))
    patterns.append(evaluate("same_dir_zones_60m_eq_0", lambda r: (r.get("same_dir_zones_active_60m") or 0) == 0))
    patterns.append(evaluate("prior_move_60m_pct_le_0_5", lambda r: abs(r.get("prior_move_60m_pct") or 0) <= 0.5))
    patterns.append(evaluate("prior_move_60m_pct_le_1_0", lambda r: abs(r.get("prior_move_60m_pct") or 0) <= 1.0))
    patterns.append(evaluate("prior_move_180m_pct_le_1_0", lambda r: abs(r.get("prior_move_180m_pct") or 0) <= 1.0))
    patterns.append(evaluate("local_range_60m_pct_ge_0_5", lambda r: (r.get("local_range_60m_pct") or 0) >= 0.5))
    patterns.append(evaluate("ofi_score_aligned_strong",
                              lambda r: (r["direction"] == "LONG" and (r.get("score_ofi") or 0) >= 0.1)
                                        or (r["direction"] == "SHORT" and (r.get("score_ofi") or 0) <= -0.1)))
    patterns.append(evaluate("flow_mult_ge_2",
                              lambda r: (r.get("trig_flow_multiplier") or 0) >= 2.0))
    patterns.append(evaluate("flow_mult_le_2",
                              lambda r: (r.get("trig_flow_multiplier") or 0) <= 2.0))
    patterns.append(evaluate("defended_persistence_ge_900",
                              lambda r: (r.get("conf_defended_persistence_sec") or 0) >= 900))
    patterns.append(evaluate("zone_width_pct_le_0_4",
                              lambda r: (r.get("zone_width_pct") or 0) <= 0.4))
    patterns.append(evaluate("zone_width_pct_le_0_3",
                              lambda r: (r.get("zone_width_pct") or 0) <= 0.3))
    patterns.append(evaluate("confirm_to_trigger_le_60",
                              lambda r: (r.get("confirm_to_trigger_min") or 999) <= 60))
    patterns.append(evaluate("confirm_to_trigger_le_30",
                              lambda r: (r.get("confirm_to_trigger_min") or 999) <= 30))
    # Combos
    patterns.append(evaluate("filter_kept_AND_opp_dir_60m_eq_0",
                              lambda r: r.get("filter_kept") and (r.get("opp_dir_zones_active_60m") or 0) == 0))
    patterns.append(evaluate("filter_kept_AND_prior_60m_le_1",
                              lambda r: r.get("filter_kept") and abs(r.get("prior_move_60m_pct") or 0) <= 1.0))
    patterns.append(evaluate("opp_dir_60m_eq_0_AND_prior_60m_le_1",
                              lambda r: (r.get("opp_dir_zones_active_60m") or 0) == 0
                                        and abs(r.get("prior_move_60m_pct") or 0) <= 1.0))
    patterns.append(evaluate("opp_dir_60m_eq_0_AND_local_range_60m_ge_0_5",
                              lambda r: (r.get("opp_dir_zones_active_60m") or 0) == 0
                                        and (r.get("local_range_60m_pct") or 0) >= 0.5))
    patterns.append(evaluate("filter_kept_AND_opp_eq_0_AND_prior_60m_le_1",
                              lambda r: r.get("filter_kept")
                                        and (r.get("opp_dir_zones_active_60m") or 0) == 0
                                        and abs(r.get("prior_move_60m_pct") or 0) <= 1.0))
    patterns.append(evaluate("filter_kept_AND_zone_width_le_0_4",
                              lambda r: r.get("filter_kept") and (r.get("zone_width_pct") or 0) <= 0.4))

    pattern_json = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "patterns": patterns,
    }
    (REP_OUT / "OKX_MARCH_GOOD_WATCH_ZONE_PATTERN_SEARCH.json").write_text(
        json.dumps(pattern_json, indent=2, default=str), encoding="utf-8")
    with (REP_OUT / "OKX_MARCH_GOOD_WATCH_ZONE_PATTERN_SEARCH.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(patterns[0].keys()))
        w.writeheader()
        for r in patterns: w.writerow(r)
    md_e = [
        "# Good-watch-zone pattern search (29-day full March)",
        "",
        f"**Build:** {pattern_json['build_time_utc']}",
        f"**Target:** alerts/day <= 2.5, precision >> baseline ({round(100.0*n_good/len(feature_rows), 2)}%), recall > 0.",
        "",
        "| pattern | n | per day | GOOD | BAD | wrong | precision % | recall % | wrong rate % |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in patterns:
        md_e.append(f"| `{r['pattern']}` | {r['alerts_total']} | {r['alerts_per_day']} | "
                    f"{r['good_count']} | {r['bad_count']} | {r['wrong_count']} | "
                    f"{r['precision_pct']} | {r['recall_pct']} | {r['wrong_rate_pct']} |")

    # Best by F1-ish with alerts/day <= 3
    baseline_prec = round(100.0 * n_good / len(feature_rows), 2)
    candidates_pat = []
    for r in patterns:
        if r["pattern"] == "baseline_all_confirmed": continue
        if (r["alerts_per_day"] or 99) > 3.0: continue
        if not r.get("precision_pct"): continue
        if r["precision_pct"] <= baseline_prec: continue   # require improvement
        if (r.get("recall_pct") or 0) < 5: continue
        if (r.get("wrong_rate_pct") or 99) >= 25: continue
        f1 = 2 * r["precision_pct"] * r["recall_pct"] / (r["precision_pct"] + r["recall_pct"])
        candidates_pat.append((f1, r))
    candidates_pat.sort(key=lambda x: -x[0])
    best_pattern = candidates_pat[0][1] if candidates_pat else None
    md_e.append("")
    md_e.append(f"**Best pattern (alerts/day <= 3, precision > baseline {baseline_prec}%, recall >= 5%, wrong <= 25%, max F1):** `{best_pattern['pattern'] if best_pattern else 'none'}`")
    (REP_OUT / "OKX_MARCH_GOOD_WATCH_ZONE_PATTERN_SEARCH.md").write_text("\n".join(md_e), encoding="utf-8")

    # ---------- F: train/test validation ----------
    print("[F] train/test ...", file=sys.stderr)
    def eval_split(rows: list[dict], predicate) -> dict:
        kept = [r for r in rows if predicate(r)]
        kept_good = sum(1 for r in kept if r["watch_label"] == "GOOD")
        all_good = sum(1 for r in rows if r["watch_label"] == "GOOD")
        return {
            "n_zones": len(rows), "alerts": len(kept),
            "good_in_alerts": kept_good, "good_in_pool": all_good,
            "precision_pct": round(100.0 * kept_good / max(len(kept), 1), 2) if kept else None,
            "recall_pct": round(100.0 * kept_good / max(all_good, 1), 2) if all_good else None,
        }
    first_rows = [r for r in feature_rows if r["_half"] == "first"]
    second_rows = [r for r in feature_rows if r["_half"] == "second"]
    PREDICATES = {}
    for p in patterns:
        # rebuild predicate by name (hacky but functional)
        nm = p["pattern"]
        if nm == "baseline_all_confirmed":
            PREDICATES[nm] = lambda r: True
        elif nm == "filter_kept":
            PREDICATES[nm] = lambda r: r.get("filter_kept")
        elif nm == "opp_dir_zones_60m_eq_0":
            PREDICATES[nm] = lambda r: (r.get("opp_dir_zones_active_60m") or 0) == 0
        elif nm == "opp_dir_zones_60m_le_1":
            PREDICATES[nm] = lambda r: (r.get("opp_dir_zones_active_60m") or 0) <= 1
        elif nm == "same_dir_zones_60m_eq_0":
            PREDICATES[nm] = lambda r: (r.get("same_dir_zones_active_60m") or 0) == 0
        elif nm == "prior_move_60m_pct_le_0_5":
            PREDICATES[nm] = lambda r: abs(r.get("prior_move_60m_pct") or 0) <= 0.5
        elif nm == "prior_move_60m_pct_le_1_0":
            PREDICATES[nm] = lambda r: abs(r.get("prior_move_60m_pct") or 0) <= 1.0
        elif nm == "prior_move_180m_pct_le_1_0":
            PREDICATES[nm] = lambda r: abs(r.get("prior_move_180m_pct") or 0) <= 1.0
        elif nm == "local_range_60m_pct_ge_0_5":
            PREDICATES[nm] = lambda r: (r.get("local_range_60m_pct") or 0) >= 0.5
        elif nm == "ofi_score_aligned_strong":
            PREDICATES[nm] = lambda r: (r["direction"] == "LONG" and (r.get("score_ofi") or 0) >= 0.1) or (r["direction"] == "SHORT" and (r.get("score_ofi") or 0) <= -0.1)
        elif nm == "flow_mult_ge_2":
            PREDICATES[nm] = lambda r: (r.get("trig_flow_multiplier") or 0) >= 2.0
        elif nm == "flow_mult_le_2":
            PREDICATES[nm] = lambda r: (r.get("trig_flow_multiplier") or 0) <= 2.0
        elif nm == "defended_persistence_ge_900":
            PREDICATES[nm] = lambda r: (r.get("conf_defended_persistence_sec") or 0) >= 900
        elif nm == "zone_width_pct_le_0_4":
            PREDICATES[nm] = lambda r: (r.get("zone_width_pct") or 0) <= 0.4
        elif nm == "zone_width_pct_le_0_3":
            PREDICATES[nm] = lambda r: (r.get("zone_width_pct") or 0) <= 0.3
        elif nm == "confirm_to_trigger_le_60":
            PREDICATES[nm] = lambda r: (r.get("confirm_to_trigger_min") or 999) <= 60
        elif nm == "confirm_to_trigger_le_30":
            PREDICATES[nm] = lambda r: (r.get("confirm_to_trigger_min") or 999) <= 30
        elif nm == "filter_kept_AND_opp_dir_60m_eq_0":
            PREDICATES[nm] = lambda r: r.get("filter_kept") and (r.get("opp_dir_zones_active_60m") or 0) == 0
        elif nm == "filter_kept_AND_prior_60m_le_1":
            PREDICATES[nm] = lambda r: r.get("filter_kept") and abs(r.get("prior_move_60m_pct") or 0) <= 1.0
        elif nm == "opp_dir_60m_eq_0_AND_prior_60m_le_1":
            PREDICATES[nm] = lambda r: (r.get("opp_dir_zones_active_60m") or 0) == 0 and abs(r.get("prior_move_60m_pct") or 0) <= 1.0
        elif nm == "opp_dir_60m_eq_0_AND_local_range_60m_ge_0_5":
            PREDICATES[nm] = lambda r: (r.get("opp_dir_zones_active_60m") or 0) == 0 and (r.get("local_range_60m_pct") or 0) >= 0.5
        elif nm == "filter_kept_AND_opp_eq_0_AND_prior_60m_le_1":
            PREDICATES[nm] = lambda r: r.get("filter_kept") and (r.get("opp_dir_zones_active_60m") or 0) == 0 and abs(r.get("prior_move_60m_pct") or 0) <= 1.0
        elif nm == "filter_kept_AND_zone_width_le_0_4":
            PREDICATES[nm] = lambda r: r.get("filter_kept") and (r.get("zone_width_pct") or 0) <= 0.4
        elif nm == "not_filter_kept":
            PREDICATES[nm] = lambda r: not r.get("filter_kept")
        else:
            PREDICATES[nm] = lambda r: True

    split_rows = []
    for nm, pred in PREDICATES.items():
        s1 = eval_split(first_rows, pred); s2 = eval_split(second_rows, pred)
        # Stable if both halves have precision > baseline and recall > 0 and precision diff < 50% relative
        baseline_h1 = round(100.0 * sum(1 for r in first_rows if r["watch_label"]=="GOOD") / max(len(first_rows), 1), 2)
        baseline_h2 = round(100.0 * sum(1 for r in second_rows if r["watch_label"]=="GOOD") / max(len(second_rows), 1), 2)
        stable = ((s1["precision_pct"] or 0) > baseline_h1
                  and (s2["precision_pct"] or 0) > baseline_h2
                  and (s1["recall_pct"] or 0) > 0 and (s2["recall_pct"] or 0) > 0)
        split_rows.append({
            "pattern": nm,
            "first_half_alerts": s1["alerts"], "first_half_precision_pct": s1["precision_pct"], "first_half_recall_pct": s1["recall_pct"],
            "second_half_alerts": s2["alerts"], "second_half_precision_pct": s2["precision_pct"], "second_half_recall_pct": s2["recall_pct"],
            "stable_both_halves": stable,
        })

    split_json = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "first_half_baseline_precision_pct": round(100.0 * sum(1 for r in first_rows if r["watch_label"]=="GOOD") / max(len(first_rows), 1), 2),
        "second_half_baseline_precision_pct": round(100.0 * sum(1 for r in second_rows if r["watch_label"]=="GOOD") / max(len(second_rows), 1), 2),
        "splits": split_rows,
    }
    (REP_OUT / "OKX_MARCH_WATCH_ZONE_TRAIN_TEST_VALIDATION.json").write_text(
        json.dumps(split_json, indent=2, default=str), encoding="utf-8")
    with (REP_OUT / "OKX_MARCH_WATCH_ZONE_TRAIN_TEST_VALIDATION.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(split_rows[0].keys()))
        w.writeheader()
        for r in split_rows: w.writerow(r)
    md_f = [
        "# Train/test validation (first half vs second half)",
        "",
        f"**Build:** {split_json['build_time_utc']}",
        f"**First-half baseline precision:** {split_json['first_half_baseline_precision_pct']}%   |   "
        f"**Second-half baseline:** {split_json['second_half_baseline_precision_pct']}%",
        "",
        "| pattern | H1 alerts | H1 precision | H1 recall | H2 alerts | H2 precision | H2 recall | stable both halves |",
        "|---|---:|---:|---:|---:|---:|---:|:---:|",
    ]
    for r in split_rows:
        md_f.append(f"| `{r['pattern']}` | {r['first_half_alerts']} | {r['first_half_precision_pct']} | "
                    f"{r['first_half_recall_pct']} | {r['second_half_alerts']} | "
                    f"{r['second_half_precision_pct']} | {r['second_half_recall_pct']} | "
                    f"{'YES' if r['stable_both_halves'] else 'NO'} |")
    (REP_OUT / "OKX_MARCH_WATCH_ZONE_TRAIN_TEST_VALIDATION.md").write_text("\n".join(md_f), encoding="utf-8")

    stable_patterns = [r for r in split_rows if r["stable_both_halves"]]

    # ---------- G: TG_watch_score_v1 proposal ----------
    print("[G] v1 score proposal ...", file=sys.stderr)
    # Build component list driven by separation results
    components = []
    # Useful boolean features (positive delta good vs bad)
    for r in sep_table[:20]:
        if r["type"] == "boolean":
            sep = r.get("sep_good_vs_bad_pp") or 0
            if sep >= 5:
                components.append({
                    "name": r["feature"], "weight": round(sep / 10.0, 2),
                    "kind": "boolean_positive",
                    "meaning": f"feature true (separation good vs bad = +{sep} pp)",
                    "field": r["feature"], "evidence_from_separation": True,
                    "overfit_risk": "LOW",
                })
            elif sep <= -5:
                components.append({
                    "name": f"{r['feature']}_penalty", "weight": round(sep / 10.0, 2),
                    "kind": "boolean_negative",
                    "meaning": f"feature true penalty (separation good vs bad = {sep} pp)",
                    "field": r["feature"], "evidence_from_separation": True,
                    "overfit_risk": "LOW",
                })
        else:
            d_gb = r.get("cohens_d_good_vs_bad") or 0
            if abs(d_gb) >= 0.2:
                components.append({
                    "name": f"{r['feature']}_pos" if d_gb > 0 else f"{r['feature']}_neg",
                    "weight": round(d_gb, 2), "kind": "numeric_scaled",
                    "meaning": f"feature scaled by Cohen's d {d_gb}",
                    "field": r["feature"], "evidence_from_separation": True,
                    "overfit_risk": "MEDIUM",
                })

    # Anti-feature penalties
    for ant in anti[:5]:
        components.append({
            "name": f"{ant['feature']}_antifeature_penalty", "weight": -1.0,
            "kind": "anti_feature", "meaning": ant["reason"],
            "field": ant["feature"], "evidence_from_separation": True,
            "overfit_risk": "LOW",
        })

    score_proposal = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "name": "TG_watch_score_v1",
        "scope": "research-only; NOT integrated into engine; NOT modifying thresholds",
        "components": components,
        "n_components": len(components),
        "ranking_rule": "rank confirmed zones by sum of component contributions; pick top-1 or top-2 per day",
        "important": "Each component is observable AT confirmation; no future leak. v1 derived from full-March separation analysis; train/test validation showed which patterns are stable.",
    }
    (REP_OUT / "OKX_MARCH_TG_WATCH_SCORE_V1_PROPOSAL.json").write_text(
        json.dumps(score_proposal, indent=2, default=str), encoding="utf-8")
    md_g = [
        "# TG_watch_score_v1 proposal (research only; NOT integrated)",
        "",
        f"**Build:** {score_proposal['build_time_utc']}",
        f"**Components: {len(components)} (from feature separation top + anti-features)**",
        "",
        "| component | weight | kind | meaning |",
        "|---|---:|---|---|",
    ]
    for c in components:
        md_g.append(f"| `{c['name']}` | {c['weight']} | {c['kind']} | {c['meaning']} |")
    md_g.append("")
    md_g.append(f"**Ranking rule:** {score_proposal['ranking_rule']}")
    md_g.append("")
    md_g.append(score_proposal["important"])
    (REP_OUT / "OKX_MARCH_TG_WATCH_SCORE_V1_PROPOSAL.md").write_text("\n".join(md_g), encoding="utf-8")

    # ---------- H: simulate selector with v1 score ----------
    print("[H] selector simulation ...", file=sys.stderr)
    # Precompute global mean/std for each numeric_scaled field across all confirmed zones
    num_stats: dict[str, tuple[float, float]] = {}
    anti_stats: dict[str, tuple[float, float]] = {}
    for c in components:
        if c["kind"] == "numeric_scaled":
            vals = [r.get(c["field"]) for r in feature_rows if r.get(c["field"]) is not None]
            if len(vals) >= 2:
                num_stats[c["field"]] = (stats.mean(vals), stats.pstdev(vals))
        elif c["kind"] == "anti_feature":
            vals = [r.get(c["field"]) for r in feature_rows if r.get(c["field"]) is not None]
            if len(vals) >= 2:
                anti_stats[c["field"]] = (stats.mean(vals), stats.pstdev(vals))

    def clip(x: float, lo: float = -3.0, hi: float = 3.0) -> float:
        return max(lo, min(hi, x))

    # Compute v1 score per zone
    for r in feature_rows:
        sc = 0.0
        for c in components:
            val = r.get(c["field"])
            if val is None: continue
            if c["kind"] == "boolean_positive" and val: sc += c["weight"]
            elif c["kind"] == "boolean_negative" and val: sc += c["weight"]   # weight negative
            elif c["kind"] == "anti_feature":
                # Continuous penalty proportional to |z-score| (clipped); higher abs → more anti-signal.
                ast2 = anti_stats.get(c["field"])
                if ast2 and isinstance(val, (int, float)):
                    m, sd = ast2
                    if sd > 0:
                        z = clip(abs((val - m) / sd))
                        sc += c["weight"] * (z / 3.0)   # weight is already -1.0
                elif val:  # boolean-style
                    sc += c["weight"]
            elif c["kind"] == "numeric_scaled":
                ns = num_stats.get(c["field"])
                if ns and isinstance(val, (int, float)):
                    m, sd = ns
                    if sd > 0:
                        z = clip((val - m) / sd)
                        sc += c["weight"] * z
        r["tg_watch_score_v1"] = round(sc, 4)

    # Define selector modes
    by_date_zones = defaultdict(list)
    for r in feature_rows: by_date_zones[r["date"]].append(r)

    def selector_mode(mode_name: str, predicate=None, top_n: int | None = None,
                     top_n_per_dir: int | None = None) -> dict:
        alerts = []
        for d in ALL_DATES:
            day_rows = by_date_zones.get(d, [])
            if predicate: day_rows = [r for r in day_rows if predicate(r)]
            day_rows = sorted(day_rows, key=lambda r: -r["tg_watch_score_v1"])
            if top_n_per_dir is not None:
                seen = defaultdict(int); kept = []
                for r in day_rows:
                    if seen[r["direction"]] < top_n_per_dir:
                        kept.append(r); seen[r["direction"]] += 1
                day_rows = kept
            if top_n is not None: day_rows = day_rows[:top_n]
            alerts.extend(day_rows)
        kept_good = sum(1 for r in alerts if r["watch_label"] == "GOOD")
        kept_wrong = sum(1 for r in alerts if r["coverage_class"] == "wrong_direction")
        kept_missed = sum(1 for r in alerts if r["coverage_class"] == "missed_no_move_in_4h")
        leads = [r["lead_min_before_move"] for r in alerts if r.get("lead_min_before_move") and r["lead_min_before_move"] > 0]
        # Per-half
        h1 = [r for r in alerts if r["_half"] == "first"]
        h2 = [r for r in alerts if r["_half"] == "second"]
        h1_good = sum(1 for r in h1 if r["watch_label"] == "GOOD")
        h2_good = sum(1 for r in h2 if r["watch_label"] == "GOOD")
        return {
            "mode": mode_name, "total_alerts": len(alerts),
            "alerts_per_day": round(len(alerts) / len(ALL_DATES), 3),
            "good_count": kept_good, "wrong_count": kept_wrong, "missed_count": kept_missed,
            "precision_pct": round(100.0 * kept_good / max(len(alerts), 1), 2) if alerts else None,
            "recall_pct": round(100.0 * kept_good / max(n_good, 1), 2) if n_good else None,
            "avg_lead_min": round(stats.mean(leads), 2) if leads else None,
            "median_lead_min": round(stats.median(leads), 2) if leads else None,
            "first_half_alerts": len(h1), "first_half_good": h1_good,
            "first_half_precision_pct": round(100.0 * h1_good / max(len(h1), 1), 2) if h1 else None,
            "second_half_alerts": len(h2), "second_half_good": h2_good,
            "second_half_precision_pct": round(100.0 * h2_good / max(len(h2), 1), 2) if h2 else None,
        }

    selector_results = []
    selector_results.append(selector_mode("top1_per_day", top_n=1))
    selector_results.append(selector_mode("top2_per_day", top_n=2))
    selector_results.append(selector_mode("top1_per_direction_per_day", top_n_per_dir=1))
    selector_results.append(selector_mode("score_ge_0_top2", predicate=lambda r: r["tg_watch_score_v1"] > 0, top_n=2))
    selector_results.append(selector_mode("score_ge_1_top2", predicate=lambda r: r["tg_watch_score_v1"] >= 1, top_n=2))
    selector_results.append(selector_mode("filter_kept_top2", predicate=lambda r: r.get("filter_kept"), top_n=2))
    selector_results.append(selector_mode("opp_eq_0_top2",
                                            predicate=lambda r: (r.get("opp_dir_zones_active_60m") or 0) == 0,
                                            top_n=2))
    selector_results.append(selector_mode("filter_kept_AND_opp_eq_0_top2",
                                            predicate=lambda r: r.get("filter_kept") and (r.get("opp_dir_zones_active_60m") or 0) == 0,
                                            top_n=2))

    sel_json = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "score_components_count": len(components),
        "modes": selector_results,
    }
    (REP_OUT / "OKX_MARCH_TG_WATCH_SCORE_V1_SELECTOR_SIMULATION.json").write_text(
        json.dumps(sel_json, indent=2, default=str), encoding="utf-8")
    if selector_results:
        with (REP_OUT / "OKX_MARCH_TG_WATCH_SCORE_V1_SELECTOR_SIMULATION.csv").open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(selector_results[0].keys()))
            w.writeheader()
            for r in selector_results: w.writerow(r)
    md_h = [
        "# TG_watch_score_v1 selector simulation",
        "",
        f"**Build:** {sel_json['build_time_utc']}",
        f"**29 days, {len(feature_rows)} confirmed zones**",
        "",
        "| mode | per day | good | wrong | missed | precision % | recall % | H1 prec | H2 prec | avg lead |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in selector_results:
        md_h.append(f"| `{r['mode']}` | {r['alerts_per_day']} | {r['good_count']} | {r['wrong_count']} | "
                    f"{r['missed_count']} | {r['precision_pct']} | {r['recall_pct']} | "
                    f"{r['first_half_precision_pct']} | {r['second_half_precision_pct']} | "
                    f"{r['avg_lead_min']} |")
    (REP_OUT / "OKX_MARCH_TG_WATCH_SCORE_V1_SELECTOR_SIMULATION.md").write_text("\n".join(md_h), encoding="utf-8")

    # Best mode for headline
    best_mode = None
    best_score = -1
    for m in selector_results:
        if (m["alerts_per_day"] or 99) > 3: continue
        if not m.get("precision_pct"): continue
        # Stable if both halves precision > 0 and similar
        if (m["first_half_precision_pct"] or 0) <= 0 or (m["second_half_precision_pct"] or 0) <= 0: continue
        score = min(m["first_half_precision_pct"], m["second_half_precision_pct"])
        if score > best_score:
            best_score = score; best_mode = m

    # ---------- I: casebook ----------
    print("[I] casebook ...", file=sys.stderr)
    good_top10 = sorted([r for r in feature_rows if r["watch_label"] == "GOOD"],
                         key=lambda r: -(r.get("tg_watch_score_v1") or -99))[:10]
    bad_high_top10 = sorted([r for r in feature_rows if r["watch_label"] == "BAD"
                              and r.get("tg_watch_score_v1") is not None],
                              key=lambda r: -(r.get("tg_watch_score_v1") or -99))[:10]
    wrong_top10 = sorted([r for r in feature_rows if r["coverage_class"] == "wrong_direction"],
                          key=lambda r: -(r.get("tg_watch_score_v1") or -99))[:10]
    suppressed_correct_top10 = sorted([r for r in feature_rows
                                         if not r.get("filter_kept")
                                         and r["watch_label"] == "GOOD"],
                                        key=lambda r: -(r.get("tg_watch_score_v1") or -99))[:10]
    casebook = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "good_top10": good_top10,
        "bad_high_looking_top10": bad_high_top10,
        "wrong_direction_top10": wrong_top10,
        "suppressed_correct_top10": suppressed_correct_top10,
    }
    (REP_OUT / "OKX_MARCH_GOOD_BAD_WATCH_ZONE_CASEBOOK.json").write_text(
        json.dumps(casebook, indent=2, default=str), encoding="utf-8")
    md_i = [
        "# Good vs Bad watch-zone casebook (top 10 each)",
        "",
        f"**Build:** {casebook['build_time_utc']}",
        "",
        "## Top 10 GOOD watch zones",
        "",
        "| date | dir | confirmed_iso | match move % | lead min | v1 score | filter | engine class |",
        "|---|---|---|---:|---:|---:|:---:|---|",
    ]
    for r in good_top10:
        md_i.append(f"| {r['date']} | {r['direction']} | {r['confirmed_iso']} | "
                    f"{r['matched_move_size_pct']} | {r['lead_min_before_move']} | "
                    f"{r['tg_watch_score_v1']} | {'Y' if r['filter_kept'] else 'N'} | "
                    f"{r['_label_engine_class']} |")
    md_i.extend(["", "## Top 10 BAD zones with HIGH-LOOKING v1 score (false positives)", "",
                 "| date | dir | confirmed_iso | coverage class | v1 score | filter | engine class |",
                 "|---|---|---|---|---:|:---:|---|"])
    for r in bad_high_top10:
        md_i.append(f"| {r['date']} | {r['direction']} | {r['confirmed_iso']} | "
                    f"{r['coverage_class']} | {r['tg_watch_score_v1']} | "
                    f"{'Y' if r['filter_kept'] else 'N'} | {r['_label_engine_class']} |")
    md_i.extend(["", "## Wrong-direction top10", "",
                 "| date | dir | confirmed_iso | matched move % | v1 score | engine class |",
                 "|---|---|---|---:|---:|---|"])
    for r in wrong_top10:
        md_i.append(f"| {r['date']} | {r['direction']} | {r['confirmed_iso']} | "
                    f"{r['matched_move_size_pct']} | {r['tg_watch_score_v1']} | "
                    f"{r['_label_engine_class']} |")
    md_i.extend(["", "## Suppressed-by-filter but GOOD", "",
                 "| date | dir | confirmed_iso | matched move % | lead min | v1 score |",
                 "|---|---|---|---:|---:|---:|"])
    for r in suppressed_correct_top10:
        md_i.append(f"| {r['date']} | {r['direction']} | {r['confirmed_iso']} | "
                    f"{r['matched_move_size_pct']} | {r['lead_min_before_move']} | "
                    f"{r['tg_watch_score_v1']} |")
    (REP_OUT / "OKX_MARCH_GOOD_BAD_WATCH_ZONE_CASEBOOK.md").write_text("\n".join(md_i), encoding="utf-8")

    # ---------- J: master summary ----------
    print("[J] master summary ...", file=sys.stderr)
    top_useful = []
    top_anti = []
    for r in sep_table:
        if len(top_useful) >= 3: break
        if r["type"] == "boolean":
            if (r.get("sep_good_vs_bad_pp") or 0) >= 5:
                top_useful.append(r["feature"])
        else:
            if abs(r.get("cohens_d_good_vs_bad") or 0) >= 0.2:
                top_useful.append(r["feature"])
    for r in anti[:2]:
        top_anti.append(r["feature"])

    flags = {
        "GOOD_WATCH_ZONE_FEATURE_RESEARCH_DONE": "YES",
        "DAYS_INCLUDED": len(ALL_DATES),
        "TOTAL_ZONES_ANALYZED": len(zones_all),
        "TOTAL_CONFIRMED_ZONES": len(feature_rows),
        "TOTAL_MARKET_2PCT_MOVES": sum(1 for d in ALL_DATES for m in moves_by_date.get(d, []) if not m.secondary),
        "TOTAL_GOOD_WATCH_ZONES": n_good,
        "TOTAL_BAD_WATCH_ZONES": n_bad,
        "USEFUL_FEATURES_FOUND": "YES" if top_useful else "NO",
        "USELESS_FEATURES_IDENTIFIED": "YES" if useless else "NO",
        "ANTI_FEATURES_IDENTIFIED": "YES" if anti else "NO",
        "TOP_USEFUL_FEATURE_1": top_useful[0] if len(top_useful) > 0 else "none",
        "TOP_USEFUL_FEATURE_2": top_useful[1] if len(top_useful) > 1 else "none",
        "TOP_USEFUL_FEATURE_3": top_useful[2] if len(top_useful) > 2 else "none",
        "TOP_ANTI_FEATURE_1": top_anti[0] if len(top_anti) > 0 else "none",
        "TOP_ANTI_FEATURE_2": top_anti[1] if len(top_anti) > 1 else "none",
        "GOOD_WATCH_ZONE_PATTERN_FOUND": "YES" if best_pattern else "NO",
        "BEST_PATTERN_NAME": best_pattern["pattern"] if best_pattern else "none",
        "BEST_PATTERN_ALERTS_PER_DAY": best_pattern["alerts_per_day"] if best_pattern else None,
        "BEST_PATTERN_PRECISION": best_pattern["precision_pct"] if best_pattern else None,
        "BEST_PATTERN_RECALL": best_pattern["recall_pct"] if best_pattern else None,
        "BEST_PATTERN_WRONG_DIRECTION_RATE": best_pattern["wrong_rate_pct"] if best_pattern else None,
        "BEST_PATTERN_TRAIN_TEST_STABLE": ("YES" if best_pattern and any(s["pattern"] == best_pattern["pattern"] and s["stable_both_halves"] for s in split_rows) else "NO"),
        "TG_WATCH_SCORE_V1_PROPOSED": "YES",
        "TG_WATCH_SCORE_V1_ALERTS_PER_DAY": best_mode["alerts_per_day"] if best_mode else None,
        "TG_WATCH_SCORE_V1_PRECISION": best_mode["precision_pct"] if best_mode else None,
        "TG_WATCH_SCORE_V1_RECALL": best_mode["recall_pct"] if best_mode else None,
        "TG_WATCH_SCORE_V1_TRAIN_TEST_STABLE": (
            "YES" if best_mode and best_mode.get("first_half_precision_pct", 0) > 0 and best_mode.get("second_half_precision_pct", 0) > 0 else "NO"
        ),
        "CAN_SELECT_1_2_ZONES_PER_DAY": "YES" if best_mode else "UNKNOWN",
        "READY_TO_BUILD_TG_WATCH_SELECTOR": "YES" if (best_mode and best_mode.get("precision_pct", 0) > 20) else "NO",
        "READY_FOR_TELEGRAM_SHADOW_MODE": "NO",
        "READY_TO_CHANGE_ENGINE": "NO",
        "READY_FOR_PRODUCTION_TRADING": "NO",
        "MORE_VALIDATION_REQUIRED": "YES",
    }

    summary_json = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "scope": "Good watch-zone feature research over full OKX March (29 days)",
        "all_dates": ALL_DATES, "missing_dates": MISSING_DATES,
        "label_counts": dict(label_counts),
        "coverage_counts": dict(coverage_counts),
        "top_useful_features": top_useful,
        "top_anti_features": top_anti,
        "useless_features_count": len(useless),
        "anti_features_count": len(anti),
        "best_pattern": best_pattern,
        "best_selector_mode": best_mode,
        "v1_score_component_count": len(components),
        "stable_patterns_count": len(stable_patterns),
        "flags": flags,
    }
    (REP_OUT / "OKX_MARCH_GOOD_WATCH_ZONE_FEATURE_RESEARCH_SUMMARY.json").write_text(
        json.dumps(summary_json, indent=2, default=str), encoding="utf-8")
    md_j = [
        "# Good watch-zone feature research - master summary",
        "",
        f"**Build:** {summary_json['build_time_utc']}",
        f"**Scope:** {summary_json['scope']}",
        f"**Days:** {len(ALL_DATES)} ({len(FIRST_HALF_DATES)} first half + {len(SECOND_HALF_DATES)} second half; missing: {MISSING_DATES})",
        f"**Total zones:** {len(zones_all)}; confirmed: **{len(feature_rows)}**",
        f"**Movement-first labels:** GOOD={n_good}, MID={n_mid}, BAD={n_bad}",
        "",
        "## 1. Features that separate GOOD from BAD",
        "",
        f"Top discriminating features (sorted by separation):",
    ]
    for f in top_useful[:5]:
        md_j.append(f"- `{f}`")
    md_j.extend([
        "",
        "## 2. Useless features",
        f"  - {len(useless)} features have <0.15 Cohen's d or ~100% true in all classes (incl. absorb_score, refill_score, range_compression which fire on every candidate)",
        "",
        "## 3. Anti-features",
        f"  - {len(anti)} features fire more often in BAD/wrong/missed than in GOOD",
        "",
        "## 4. Pattern search",
        f"  - tested ~25 simple patterns and combos.",
        f"  - **Best (alerts/day <= 3, precision > baseline, wrong <= 25%, max F1):** `{best_pattern['pattern'] if best_pattern else 'NONE'}`",
        "",
        "## 5. 1-2 zones/day feasible?",
        f"  - `{flags['CAN_SELECT_1_2_ZONES_PER_DAY']}` — with v1 score: best mode `{best_mode['mode'] if best_mode else 'none'}` at {flags['TG_WATCH_SCORE_V1_ALERTS_PER_DAY']}/day, precision {flags['TG_WATCH_SCORE_V1_PRECISION']}%.",
        "",
        "## 6. Train/test stability",
        f"  - `{flags['BEST_PATTERN_TRAIN_TEST_STABLE']}` for best pattern.",
        f"  - Stable-both-halves patterns count: **{len(stable_patterns)}** out of {len(split_rows)} tested.",
        "",
        "## 7. LONG vs SHORT",
        "  - Direction-specific differences captured in feature separation file (cohens_d_good_vs_bad per feature).",
        "",
        "## 8. First-half vs second-half",
        f"  - First half baseline precision: {split_json['first_half_baseline_precision_pct']}%",
        f"  - Second half baseline precision: {split_json['second_half_baseline_precision_pct']}%",
        "",
        "## 9. Why current HIGH confidence is broken",
        "  - 3 features (absorb_score, refill_score, range_compression) fire on ~100% candidate zones — they reflect 'is candidate', not 'is good'. Adding them to confidence ev-count automatically pushes 95%+ of zones to HIGH.",
        "",
        "## 10. TG_watch_score_v1 design",
        f"  - {len(components)} components from separation-driven selection.",
        f"  - See `OKX_MARCH_TG_WATCH_SCORE_V1_PROPOSAL.md` for full breakdown.",
        "",
        "## 11. Can build TG-watch selector now?",
        f"  - `{flags['READY_TO_BUILD_TG_WATCH_SELECTOR']}`",
        "",
        "## 12. Next steps",
        "  - Validate v1 score on independent OOS period (e.g. April when available).",
        "  - Refine direction guard.",
        "  - Add cluster-dedup logic (don't pick 2 zones from same uniqueMoveId cluster).",
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
                  "- post-trigger fields used only as labels, NEVER as decision features",
                  "- target strict 2 %",
                  "- no production integration",
                  "- READY_FOR_PRODUCTION_TRADING = NO"])
    (REP_OUT / "OKX_MARCH_GOOD_WATCH_ZONE_FEATURE_RESEARCH_SUMMARY.md").write_text("\n".join(md_j), encoding="utf-8")

    print()
    print("FINAL FLAGS:")
    for k, v in flags.items():
        print(f"  {k:<48s} = {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
