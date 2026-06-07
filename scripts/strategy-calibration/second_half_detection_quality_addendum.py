"""OKX direct second-half March - detection quality / TG-watch addendum.

READ-ONLY post-hoc audit. Auto-discovers completed days from the chain results
JSON, runs on whatever is ready. Does NOT touch the running chain.

Re-runnable: each invocation rebuilds the addendum over current ready days.

Sections A-I per spec. NO engine / threshold / detector change.
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
from canonical_ledger import build_buckets_from_trades_csv, Bucket

ROOT = Path("C:/Users/gibilev/orderflow-research")
REPORTS = ROOT / "reports"
REP_OKX = REPORTS / "okx-direct"
REP_OUT = REPORTS / "strategy-calibration"
REP_OUT.mkdir(parents=True, exist_ok=True)
DATA_ROOT = ROOT / "data/okx-historical/BTC-USDT-SWAP"

WINDOW_MIN = 60
PRICE_BAND_PCT = 1.0
FAST_X_MIN_BASE = 60
MOVE_THRESHOLD_PCT = 2.0
SECONDARY_MOVE_THRESHOLD_PCT = 1.5

CHAIN_RESULTS_JSON = REP_OKX / "OKX_DIRECT_MARCH_PARTIAL_CHAIN_RESULTS.json"


# ---------- ready-day discovery ----------

def discover_ready_days() -> tuple[list[str], int, int, bool]:
    """Return (ready_days, completed_count, total_count, chain_done)."""
    if not CHAIN_RESULTS_JSON.exists():
        # Fall back: scan reports/okx-direct/ for OKX_DIRECT_TECHNICAL_REPLAY_<date>.json files
        rds = []
        for p in REP_OKX.glob("OKX_DIRECT_TECHNICAL_REPLAY_2026-03-*.json"):
            d = p.stem.replace("OKX_DIRECT_TECHNICAL_REPLAY_", "")
            if 16 <= int(d.split("-")[-1]) <= 31:
                rds.append(d)
        rds.sort()
        return rds, len(rds), 15, False
    d = json.loads(CHAIN_RESULTS_JSON.read_text(encoding="utf-8"))
    completed = d.get("completed_count", 0)
    total = d.get("total_count", 15)
    results = d.get("results", [])
    ready = sorted([r["date"] for r in results
                     if r.get("status") == "ok"
                     and (r.get("backtest") or {}).get("exit_code") == 0
                     and (REP_OKX / f"OKX_DIRECT_TECHNICAL_REPLAY_{r['date']}.json").exists()])
    chain_done = completed == total
    return ready, completed, total, chain_done


# ---------- shared helpers ----------

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


# ---------- ZigZag market moves ----------

@dataclass
class Move:
    date: str
    direction: str   # "UP" / "DOWN"
    start_sec: int
    end_sec: int
    start_price: float
    end_price: float
    size_pct: float
    secondary: bool


def detect_moves(date: str, buckets: list[Bucket]) -> list[Move]:
    if not buckets: return []
    out: list[Move] = []
    def scan(thresh: float, mark_sec: bool) -> list[Move]:
        moves: list[Move] = []
        first = buckets[0]
        ext_sec = first.sec; ext_h = first.high; ext_l = first.low
        ps_sec = first.sec; ps_price = first.last
        direction = None
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
                    moves.append(Move(date, "UP", ps_sec, ext_sec, ps_price, ext_h,
                                       round(size, 4), mark_sec))
                    direction = "DOWN"; ps_sec = ext_sec; ps_price = ext_h
                    ext_sec = b.sec; ext_h = b.high; ext_l = b.low
            else:
                if b.low < ext_l: ext_l = b.low; ext_sec = b.sec
                rally = (b.high - ext_l) / ext_l * 100.0
                if rally >= thresh:
                    size = (ps_price - ext_l) / ps_price * 100.0
                    moves.append(Move(date, "DOWN", ps_sec, ext_sec, ps_price, ext_l,
                                       round(size, 4), mark_sec))
                    direction = "UP"; ps_sec = ext_sec; ps_price = ext_l
                    ext_sec = b.sec; ext_h = b.high; ext_l = b.low
        return moves
    primary = scan(MOVE_THRESHOLD_PCT, mark_sec=False)
    secondary = scan(SECONDARY_MOVE_THRESHOLD_PCT, mark_sec=True)
    primary_starts = {(m.start_sec, m.direction) for m in primary}
    sec_extra = [m for m in secondary if m.size_pct < MOVE_THRESHOLD_PCT
                  and (m.start_sec, m.direction) not in primary_starts]
    return primary + sec_extra


def add_move_context(moves: list[Move], buckets: list[Bucket]) -> list[dict]:
    rows = []
    for m in moves:
        slice_b = [b for b in buckets if m.start_sec <= b.sec <= m.end_sec]
        max_pullback_pct = 0.0
        if slice_b:
            if m.direction == "UP":
                running_high = m.start_price
                for b in slice_b:
                    if b.high > running_high: running_high = b.high
                    pull = (running_high - b.low) / running_high * 100.0
                    if pull > max_pullback_pct: max_pullback_pct = pull
            else:
                running_low = m.start_price
                for b in slice_b:
                    if b.low < running_low: running_low = b.low
                    pull = (b.high - running_low) / running_low * 100.0
                    if pull > max_pullback_pct: max_pullback_pct = pull
        # local 60m range BEFORE start
        before_start_sec = m.start_sec - 3600
        pre_b = [b for b in buckets if before_start_sec <= b.sec < m.start_sec]
        if pre_b:
            hi = max(b.high for b in pre_b); lo = min(b.low for b in pre_b)
            pre_range_pct = (hi - lo) / lo * 100.0 if lo else 0
        else:
            pre_range_pct = None
        rows.append({
            "date": m.date, "direction": m.direction,
            "start_iso": sec_to_iso(m.start_sec), "end_iso": sec_to_iso(m.end_sec),
            "start_price": m.start_price, "end_price": m.end_price,
            "size_pct": m.size_pct, "duration_min": round((m.end_sec - m.start_sec) / 60.0, 2),
            "is_secondary_1_5pct": m.secondary,
            "max_pullback_inside_move_pct": round(max_pullback_pct, 4),
            "clean_or_choppy": "clean" if max_pullback_pct < 0.7 else "choppy",
            "local_60m_range_before_move_pct": round(pre_range_pct, 4) if pre_range_pct else None,
        })
    return rows


# ---------- coverage classification ----------

def classify_coverage(m: Move, zones_by_date, decisions) -> dict:
    """Per move: find best candidate/confirmed/trigger zone in correct direction."""
    zones = zones_by_date.get(m.date, [])
    correct_dir = "LONG" if m.direction == "UP" else "SHORT"
    # find any zones with correct direction whose candidate/confirmed/trigger touches the window
    look_back = m.start_sec - 3 * 3600
    look_forward = m.end_sec
    has_candidate_before = None
    has_confirmed_before = None
    has_trigger_before = None
    best_z = None
    best_score = None
    for z in zones:
        if z["direction"] != correct_dir: continue
        cand_sec = (z.get("startTs") or 0) // 1000
        conf_sec = (z.get("confirmedTs") or 0) // 1000
        trig_sec = (z.get("triggerTs") or 0) // 1000
        if cand_sec and look_back <= cand_sec <= look_forward:
            if cand_sec < m.start_sec:
                if has_candidate_before is None or cand_sec < has_candidate_before[1]:
                    has_candidate_before = (z["id"], cand_sec)
        if conf_sec and look_back <= conf_sec <= look_forward:
            if conf_sec < m.start_sec:
                if has_confirmed_before is None or conf_sec < has_confirmed_before[1]:
                    has_confirmed_before = (z["id"], conf_sec)
        if trig_sec and trig_sec >= look_back and trig_sec <= look_forward + 1800:
            if trig_sec < m.start_sec and (has_trigger_before is None or trig_sec > has_trigger_before[1]):
                has_trigger_before = (z["id"], trig_sec)
            score = abs(m.start_sec - trig_sec)
            if best_z is None or score < best_score:
                best_z = z; best_score = score
    move_dur_s = max(m.end_sec - m.start_sec, 1)
    pct_complete = None
    cls = None
    filter_reason = None
    # Determine class
    if best_z is None:
        cls = "missed_move"
    else:
        dec = decisions.get(best_z["id"], {})
        trig_sec = best_z["triggerTs"] // 1000
        pct_complete = max(0.0, min(1.0, (trig_sec - m.start_sec) / move_dur_s)) * 100.0
        if not dec.get("kept", True):
            cls = "filtered_correct_zone"
            if dec.get("dup_suppressed"): filter_reason = "duplicate_60m_price_band"
            elif not dec.get("fast_ok"): filter_reason = f"slow_trigger (ctm={dec.get('ctm_min'):.0f}m)"
            else: filter_reason = "unknown"
        elif has_confirmed_before and not (trig_sec < m.start_sec):
            cls = "covered_watch_early"
        elif trig_sec < m.start_sec:
            cls = "covered_trigger_early"
        elif pct_complete <= 50:
            cls = "covered_mid"
        else:
            cls = "covered_late"

    return {
        "date": m.date, "direction": m.direction, "size_pct": m.size_pct,
        "is_secondary_1_5pct": m.secondary,
        "move_start_iso": sec_to_iso(m.start_sec), "move_end_iso": sec_to_iso(m.end_sec),
        "duration_min": round((m.end_sec - m.start_sec) / 60.0, 2),
        "candidate_before_move_zone_id": has_candidate_before[0] if has_candidate_before else None,
        "candidate_before_move_iso": sec_to_iso(has_candidate_before[1]) if has_candidate_before else None,
        "confirmed_before_move_zone_id": has_confirmed_before[0] if has_confirmed_before else None,
        "confirmed_before_move_iso": sec_to_iso(has_confirmed_before[1]) if has_confirmed_before else None,
        "trigger_before_move_zone_id": has_trigger_before[0] if has_trigger_before else None,
        "trigger_before_move_iso": sec_to_iso(has_trigger_before[1]) if has_trigger_before else None,
        "best_matching_zone_id": best_z["id"] if best_z else None,
        "best_zone_class": best_z["_class"] if best_z else None,
        "pct_of_move_completed_by_trigger": round(pct_complete, 2) if pct_complete is not None else None,
        "filter_kept": (decisions.get(best_z["id"], {}).get("kept") if best_z else None),
        "filter_reason": filter_reason,
        "classification": cls,
    }


# ---------- direction explanation ----------

def reasons_dict(z):
    out = {}
    for r in z.get("reasons", []):
        out[r.get("stage")] = r.get("conditions") or {}
    return out


def direction_explanation(z: dict) -> dict:
    """Build human-readable direction explanation from pre-trigger conditions + scores."""
    rd = reasons_dict(z)
    cand = rd.get("candidate") or {}
    conf = rd.get("confirmed") or {}
    trig = rd.get("trigger") or {}
    scores = z.get("scores") or {}
    direction = z["direction"]
    notes = []
    have = []; missing = []
    if direction == "LONG":
        # Evidence list for LONG
        if cand.get("sellPressure") is not None:
            sp = cand["sellPressure"]
            if sp >= 0.6: notes.append(f"aggressive selling pressure {sp:.3f} (absorbed)")
            have.append("sell_pressure")
        else: missing.append("sell_pressure")
        if cand.get("absorbScore") is not None:
            if cand["absorbScore"] >= 0.6: notes.append(f"absorb score {cand['absorbScore']:.3f} (bid absorbed sells)")
            have.append("absorb_score")
        else: missing.append("absorb_score")
        if cand.get("bidRefillScore") is not None:
            have.append("bid_refill_score")
        else: missing.append("bid_refill_score")
        if cand.get("rangeCompression"): notes.append("range compression observed")
        if conf.get("voidScore") is not None:
            have.append("void_score")
        if conf.get("oppositeThinning") is not None:
            have.append("opposite_thinning")
        if conf.get("cyclesSeen"): notes.append(f"{conf['cyclesSeen']} defense cycles seen")
        if conf.get("defendedPersistenceSec"):
            notes.append(f"zone defended for {conf['defendedPersistenceSec']} s")
        if scores.get("ofiScore") is not None:
            if scores["ofiScore"] > 0.05: notes.append(f"OFI score {scores['ofiScore']:.3f} (buy-side)")
            elif scores["ofiScore"] < -0.05: notes.append(f"OFI score {scores['ofiScore']:.3f} (WARNING: sell-side)")
            have.append("ofi_score")
        if trig.get("flowMultiplier"):
            notes.append(f"trigger flow multiplier {trig['flowMultiplier']:.2f}x")
        if trig.get("breakPct"):
            notes.append(f"break {trig['breakPct']:.3f}% above zone")
        if trig.get("sideFlowOk"): notes.append("side-flow ok at trigger")
    else:   # SHORT
        if cand.get("buyPressure") is not None:
            bp = cand["buyPressure"]
            if bp >= 0.6: notes.append(f"aggressive buying pressure {bp:.3f} (absorbed)")
            have.append("buy_pressure")
        else: missing.append("buy_pressure")
        if cand.get("absorbScore") is not None:
            if cand["absorbScore"] >= 0.6: notes.append(f"absorb score {cand['absorbScore']:.3f} (ask absorbed buys)")
            have.append("absorb_score")
        else: missing.append("absorb_score")
        if cand.get("askRefillScore") is not None:
            have.append("ask_refill_score")
        else: missing.append("ask_refill_score")
        if cand.get("rangeCompression"): notes.append("range compression observed")
        if conf.get("voidScore") is not None:
            have.append("void_score")
        if conf.get("oppositeThinning") is not None:
            have.append("opposite_thinning")
        if conf.get("cyclesSeen"): notes.append(f"{conf['cyclesSeen']} defense cycles seen")
        if conf.get("defendedPersistenceSec"):
            notes.append(f"zone defended for {conf['defendedPersistenceSec']} s")
        if scores.get("ofiScore") is not None:
            if scores["ofiScore"] < -0.05: notes.append(f"OFI score {scores['ofiScore']:.3f} (sell-side)")
            elif scores["ofiScore"] > 0.05: notes.append(f"OFI score {scores['ofiScore']:.3f} (WARNING: buy-side)")
            have.append("ofi_score")
        if trig.get("flowMultiplier"):
            notes.append(f"trigger flow multiplier {trig['flowMultiplier']:.2f}x")
        if trig.get("breakPct"):
            notes.append(f"break {trig['breakPct']:.3f}% below zone")
        if trig.get("sideFlowOk"): notes.append("side-flow ok at trigger")
    # Confidence
    # MID if at least 3 evidence; HIGH if 5+; LOW otherwise
    n_evidence = len(notes)
    if n_evidence >= 5: confidence = "HIGH"
    elif n_evidence >= 3: confidence = "MID"
    else: confidence = "LOW"
    summary = (f"{direction} because " + "; ".join(notes)) if notes else f"{direction} (insufficient evidence)"
    return {
        "direction": direction,
        "confidence": confidence,
        "evidence_count": n_evidence,
        "summary": summary,
        "available_features": have,
        "missing_features": missing,
    }


# ---------- main ----------

def main() -> int:
    ready, completed, total, chain_done = discover_ready_days()
    print(f"chain progress: {completed}/{total}  chain_done={chain_done}", file=sys.stderr)
    print(f"ready days: {ready}", file=sys.stderr)
    if not ready:
        print("No ready days — abort.", file=sys.stderr)
        return 1

    # Load
    zones_all: list[dict] = []
    zones_by_date: dict[str, list[dict]] = {}
    for d in ready:
        zs = load_zones(d)
        zones_by_date[d] = zs
        zones_all.extend(zs)
    decisions = apply_passive_filter(zones_all)
    print(f"loaded {len(zones_all)} zones across {len(ready)} days", file=sys.stderr)

    # 1s buckets
    print("building 1s buckets ...", file=sys.stderr)
    buckets_by_date: dict[str, list[Bucket]] = {}
    for d in ready:
        p = DATA_ROOT / d / "trades.csv.gz"
        if p.exists():
            buckets_by_date[d] = build_buckets_from_trades_csv(p)
            print(f"  {d}: {len(buckets_by_date[d]):,} buckets", file=sys.stderr)
        else:
            buckets_by_date[d] = []

    # ---------- A: market moves ----------
    print("[A] market 2% moves ...", file=sys.stderr)
    moves_by_date: dict[str, list[Move]] = {}
    market_rows: list[dict] = []
    for d in ready:
        ms = detect_moves(d, buckets_by_date.get(d, []))
        moves_by_date[d] = ms
        market_rows.extend(add_move_context(ms, buckets_by_date.get(d, [])))
    n_primary_total = sum(1 for r in market_rows if not r["is_secondary_1_5pct"])
    n_up = sum(1 for r in market_rows if not r["is_secondary_1_5pct"] and r["direction"] == "UP")
    n_dn = n_primary_total - n_up

    market_json = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "ready_days": ready, "chain_complete": chain_done,
        "n_primary_2pct_moves": n_primary_total,
        "n_up_2pct": n_up, "n_down_2pct": n_dn,
        "n_secondary_1_5pct": sum(1 for r in market_rows if r["is_secondary_1_5pct"]),
        "moves": market_rows,
    }
    (REP_OUT / "OKX_SECOND_HALF_MARKET_2PCT_MOVES_PER_DAY.json").write_text(
        json.dumps(market_json, indent=2, default=str), encoding="utf-8")
    if market_rows:
        with (REP_OUT / "OKX_SECOND_HALF_MARKET_2PCT_MOVES_PER_DAY.csv").open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(market_rows[0].keys()))
            w.writeheader()
            for r in market_rows: w.writerow(r)
    md = [
        "# Market 2 % moves per day (ZigZag) - ready days",
        "",
        f"**Build:** {market_json['build_time_utc']}",
        f"**Ready days:** {ready}  (chain {completed}/{total}, complete={chain_done})",
        "",
        f"- primary >=2 % moves: **{n_primary_total}**  (UP={n_up}, DOWN={n_dn})",
        f"- secondary 1.5-2 %: **{market_json['n_secondary_1_5pct']}**",
        "",
        "| date | dir | start | end | size % | duration | pullback % | clean/choppy | local 60m before % |",
        "|---|---|---|---|---:|---:|---:|---|---:|",
    ]
    for r in market_rows:
        if r["is_secondary_1_5pct"]:
            continue
        md.append(f"| {r['date']} | {r['direction']} | {r['start_iso']} | {r['end_iso']} | "
                  f"{r['size_pct']} | {r['duration_min']} | {r['max_pullback_inside_move_pct']} | "
                  f"{r['clean_or_choppy']} | {r['local_60m_range_before_move_pct']} |")
    (REP_OUT / "OKX_SECOND_HALF_MARKET_2PCT_MOVES_PER_DAY.md").write_text("\n".join(md), encoding="utf-8")

    # ---------- B: engine coverage ----------
    print("[B] engine coverage ...", file=sys.stderr)
    coverage_rows: list[dict] = []
    for d in ready:
        for m in moves_by_date.get(d, []):
            if m.secondary: continue
            coverage_rows.append(classify_coverage(m, zones_by_date, decisions))
    counts = defaultdict(int)
    for c in coverage_rows: counts[c["classification"]] += 1
    coverage_json = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "counts": dict(counts),
        "moves": coverage_rows,
    }
    (REP_OUT / "OKX_SECOND_HALF_ENGINE_COVERAGE_EARLY_MID_LATE_MISSED.json").write_text(
        json.dumps(coverage_json, indent=2, default=str), encoding="utf-8")
    if coverage_rows:
        with (REP_OUT / "OKX_SECOND_HALF_ENGINE_COVERAGE_EARLY_MID_LATE_MISSED.csv").open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(coverage_rows[0].keys()), extrasaction="ignore")
            w.writeheader()
            for r in coverage_rows: w.writerow(r)
    md2 = [
        "# Engine coverage - early / mid / late / missed",
        "",
        f"**Build:** {coverage_json['build_time_utc']}",
        "",
        "## Classification counts",
        "",
    ]
    for k, v in sorted(counts.items(), key=lambda kv: -kv[1]):
        md2.append(f"- {k}: **{v}**")
    md2.extend(["", "## Per-move", "",
                 "| date | dir | size % | start | classification | best zone | % completed | filter kept | filter reason |",
                 "|---|---|---:|---|---|---|---:|:---:|---|"])
    for c in coverage_rows:
        md2.append(f"| {c['date']} | {c['direction']} | {c['size_pct']} | "
                   f"{c['move_start_iso']} | **{c['classification']}** | "
                   f"`{(c['best_matching_zone_id'] or '—')[-20:]}` | "
                   f"{c['pct_of_move_completed_by_trigger']} | "
                   f"{'Y' if c['filter_kept'] else 'N'} | {c['filter_reason']} |")
    (REP_OUT / "OKX_SECOND_HALF_ENGINE_COVERAGE_EARLY_MID_LATE_MISSED.md").write_text("\n".join(md2), encoding="utf-8")

    # ---------- C: correct zones suppressed by filter ----------
    print("[C] correct zones suppressed ...", file=sys.stderr)
    correct_suppressed = []
    for z in zones_all:
        if not is_triggered(z): continue
        dec = decisions.get(z["id"], {})
        if dec.get("kept"): continue
        if z["_class"] not in ("primary_unique_reached_move", "duplicate_reached_move"): continue
        reason = []
        if dec.get("dup_suppressed"): reason.append("duplicate_60m_price_band")
        if not dec.get("fast_ok"): reason.append(f"slow_trigger (ctm={dec.get('ctm_min'):.0f}m)")
        # Find the related market move
        related_move = None
        for d in ready:
            for m in moves_by_date.get(d, []):
                if m.secondary: continue
                if (m.direction == "UP" and z["direction"] == "LONG") or (m.direction == "DOWN" and z["direction"] == "SHORT"):
                    trig_sec = z["triggerTs"] // 1000
                    if trig_sec >= m.start_sec - 3 * 3600 and trig_sec <= m.end_sec:
                        if related_move is None or abs(m.start_sec - trig_sec) < abs(related_move.start_sec - trig_sec):
                            related_move = m
        correct_suppressed.append({
            "date": z["_date"], "zone_id": z["id"], "direction": z["direction"], "class": z["_class"],
            "isPrimary": bool(z.get("isPrimaryMoveZone")),
            "candidate_iso": ms_to_iso(z.get("startTs")),
            "confirmed_iso": ms_to_iso(z.get("confirmedTs")),
            "trigger_iso": ms_to_iso(z["triggerTs"]),
            "candidate_to_confirm_min": candidate_to_confirm_min(z),
            "confirm_to_trigger_min": confirm_to_trigger_min(z),
            "total_pre_trigger_min": total_pre_trigger_min(z),
            "suppress_reason": "; ".join(reason),
            "related_move_start_iso": sec_to_iso(related_move.start_sec) if related_move else None,
            "related_move_size_pct": related_move.size_pct if related_move else None,
            "zone_before_move": ((z["triggerTs"] // 1000) < related_move.start_sec) if related_move else None,
            "tg_watch_alert_useful": "YES (candidate/confirmed available before move)" if related_move and ((z.get("confirmedTs") or 0)//1000) < related_move.start_sec else "UNCLEAR",
            "filter_failure": True,
        })
    sup_json = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "n_correct_zones_suppressed": len(correct_suppressed),
        "rows": correct_suppressed,
    }
    (REP_OUT / "OKX_SECOND_HALF_CORRECT_ZONES_SUPPRESSED_BY_FILTER.json").write_text(
        json.dumps(sup_json, indent=2, default=str), encoding="utf-8")
    if correct_suppressed:
        with (REP_OUT / "OKX_SECOND_HALF_CORRECT_ZONES_SUPPRESSED_BY_FILTER.csv").open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(correct_suppressed[0].keys()), extrasaction="ignore")
            w.writeheader()
            for r in correct_suppressed: w.writerow(r)
    md3 = [
        "# Correct-direction zones suppressed by base filter",
        "",
        f"**Build:** {sup_json['build_time_utc']}",
        f"**Total suppressed correct zones:** {len(correct_suppressed)}",
        "",
        "| date | zone | dir | class | primary? | ctm min | suppress reason | related move size | zone before move? | TG watch useful? |",
        "|---|---|---|---|:---:|---:|---|---:|:---:|---|",
    ]
    for r in correct_suppressed:
        md3.append(f"| {r['date']} | `{r['zone_id'][-20:]}` | {r['direction']} | {r['class']} | "
                   f"{'Y' if r['isPrimary'] else 'N'} | {r['confirm_to_trigger_min']} | "
                   f"{r['suppress_reason']} | {r['related_move_size_pct']} | "
                   f"{'Y' if r['zone_before_move'] else 'N'} | {r['tg_watch_alert_useful']} |")
    (REP_OUT / "OKX_SECOND_HALF_CORRECT_ZONES_SUPPRESSED_BY_FILTER.md").write_text("\n".join(md3), encoding="utf-8")

    # ---------- D: slow-trigger correct zones ----------
    print("[D] slow-trigger correct zones ...", file=sys.stderr)
    slow_correct = []
    for z in zones_all:
        if not is_triggered(z): continue
        ctm = confirm_to_trigger_min(z)
        if ctm is None or ctm <= 60: continue
        # is direction "correct" vs nearest 2% move?
        related_move = None
        d = z["_date"]
        for m in moves_by_date.get(d, []):
            if m.secondary: continue
            if (m.direction == "UP" and z["direction"] == "LONG") or (m.direction == "DOWN" and z["direction"] == "SHORT"):
                trig_sec = z["triggerTs"] // 1000
                if trig_sec >= m.start_sec - 3 * 3600 and trig_sec <= m.end_sec:
                    if related_move is None or abs(m.start_sec - trig_sec) < abs(related_move.start_sec - trig_sec):
                        related_move = m
        if related_move is None and z["_class"] not in ("primary_unique_reached_move", "duplicate_reached_move"):
            continue   # not correct
        # at confirmed stage, what does engine already see?
        conf_cond = reasons_dict(z).get("confirmed") or {}
        cand_cond = reasons_dict(z).get("candidate") or {}
        of_score = (z.get("scores") or {}).get("ofiScore")
        confirmed_iso = ms_to_iso(z.get("confirmedTs"))
        # could we have alerted at confirmed?
        could_alert_at_confirmed = (confirmed_iso is not None
            and ((cand_cond.get("absorbScore") or 0) >= 0.6 or (conf_cond.get("cyclesSeen") or 0) >= 5))
        slow_correct.append({
            "date": z["_date"], "zone_id": z["id"], "direction": z["direction"], "class": z["_class"],
            "candidate_iso": ms_to_iso(z.get("startTs")),
            "confirmed_iso": confirmed_iso,
            "trigger_iso": ms_to_iso(z["triggerTs"]),
            "candidate_to_confirm_min": candidate_to_confirm_min(z),
            "confirm_to_trigger_min": ctm,
            "total_pre_trigger_min": total_pre_trigger_min(z),
            "confirmed_absorb_score": cand_cond.get("absorbScore"),
            "confirmed_cycles_seen": conf_cond.get("cyclesSeen"),
            "confirmed_defended_persistence_sec": conf_cond.get("defendedPersistenceSec"),
            "ofi_at_trigger_score": of_score,
            "related_move_start": sec_to_iso(related_move.start_sec) if related_move else None,
            "related_move_size_pct": related_move.size_pct if related_move else None,
            "could_alert_at_confirmed_stage": could_alert_at_confirmed,
            "verdict": "slow_but_correct_could_have_been_watch_alert" if could_alert_at_confirmed else "slow_marginal",
        })

    slow_json = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "n_slow_trigger_correct_zones": len(slow_correct),
        "n_could_alert_at_confirmed": sum(1 for r in slow_correct if r["could_alert_at_confirmed_stage"]),
        "rows": slow_correct,
    }
    (REP_OUT / "OKX_SECOND_HALF_SLOW_TRIGGER_CORRECT_ZONES.json").write_text(
        json.dumps(slow_json, indent=2, default=str), encoding="utf-8")
    md4 = [
        "# Slow-trigger correct zones (confirm→trigger > 60 m, direction matches market move)",
        "",
        f"**Build:** {slow_json['build_time_utc']}",
        f"**Total slow-trigger correct zones:** {len(slow_correct)}",
        f"**Could have been alerted at confirmed stage (absorb>=0.6 or cycles>=5):** {slow_json['n_could_alert_at_confirmed']}",
        "",
        "| date | zone | dir | class | ctm min | confirmed | trigger | absorb | cycles | OFI | verdict |",
        "|---|---|---|---|---:|---|---|---:|---:|---:|---|",
    ]
    for r in slow_correct:
        md4.append(
            f"| {r['date']} | `{r['zone_id'][-20:]}` | {r['direction']} | {r['class']} | "
            f"{r['confirm_to_trigger_min']} | {r['confirmed_iso']} | {r['trigger_iso']} | "
            f"{r['confirmed_absorb_score']} | {r['confirmed_cycles_seen']} | {r['ofi_at_trigger_score']} | "
            f"**{r['verdict']}** |"
        )
    (REP_OUT / "OKX_SECOND_HALF_SLOW_TRIGGER_CORRECT_ZONES.md").write_text("\n".join(md4), encoding="utf-8")

    # ---------- E: wrong-direction cases ----------
    print("[E] wrong-direction cases ...", file=sys.stderr)
    wrong_cases = []
    for z in zones_all:
        if not is_triggered(z): continue
        d = z["_date"]
        buckets = buckets_by_date.get(d) or []
        if not buckets: continue
        trig_sec = z["triggerTs"] // 1000
        tp = None
        for r in z.get("reasons", []):
            if r.get("stage") == "trigger":
                tp = (r.get("conditions") or {}).get("triggerPrice"); break
        if tp is None: tp = mid_price(z)
        if tp is None: continue
        end_sec = trig_sec + 4 * 3600
        slice_b = [b for b in buckets if trig_sec <= b.sec <= end_sec]
        if not slice_b: continue
        max_up = max((b.high - tp) / tp * 100.0 for b in slice_b)
        max_dn = max((tp - b.low) / tp * 100.0 for b in slice_b)
        is_wrong = False
        if z["direction"] == "LONG" and max_up < 2.0 and max_dn >= 2.0: is_wrong = True
        if z["direction"] == "SHORT" and max_dn < 2.0 and max_up >= 2.0: is_wrong = True
        if not is_wrong: continue
        # opposite candidate?
        opp_dir = "SHORT" if z["direction"] == "LONG" else "LONG"
        opp_cand = next((zz for zz in zones_all
                          if zz["_date"] == d and zz["direction"] == opp_dir
                          and zz.get("startTs") and abs((zz["startTs"]//1000) - trig_sec) <= 3600), None)
        cls = "wrong_direction_noise" if z["_class"] == "failed_triggered" else "ambiguous"
        if opp_cand:
            opp_dec = decisions.get(opp_cand["id"], {})
            if not opp_dec.get("kept") and is_triggered(opp_cand) and is_reached(opp_cand):
                cls = "filter_removed_correct_side"
        wrong_cases.append({
            "date": d, "zone_id": z["id"], "direction": z["direction"],
            "trigger_iso": ms_to_iso(z["triggerTs"]),
            "max_4h_up_pct": round(max_up, 4),
            "max_4h_down_pct": round(max_dn, 4),
            "engine_class": z["_class"],
            "opposite_candidate_present": bool(opp_cand),
            "opposite_candidate_zone_id": opp_cand["id"] if opp_cand else None,
            "classification": cls,
        })
    wrong_json = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "n_wrong_direction": len(wrong_cases),
        "rows": wrong_cases,
    }
    (REP_OUT / "OKX_SECOND_HALF_WRONG_DIRECTION_CASES.json").write_text(
        json.dumps(wrong_json, indent=2, default=str), encoding="utf-8")
    if wrong_cases:
        with (REP_OUT / "OKX_SECOND_HALF_WRONG_DIRECTION_CASES.csv").open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(wrong_cases[0].keys()), extrasaction="ignore")
            w.writeheader()
            for r in wrong_cases: w.writerow(r)
    md5 = [
        "# Wrong-direction cases (4h forward window had no 2% in engine direction)",
        "",
        f"**Build:** {wrong_json['build_time_utc']}",
        f"**Total wrong-direction triggers:** {len(wrong_cases)}",
        "",
        "| date | zone | dir | trigger | 4h up % | 4h down % | engine class | opp candidate? | classification |",
        "|---|---|---|---|---:|---:|---|:---:|---|",
    ]
    for r in wrong_cases:
        md5.append(f"| {r['date']} | `{r['zone_id'][-20:]}` | {r['direction']} | {r['trigger_iso']} | "
                   f"{r['max_4h_up_pct']} | {r['max_4h_down_pct']} | {r['engine_class']} | "
                   f"{'Y' if r['opposite_candidate_present'] else 'N'} | {r['classification']} |")
    (REP_OUT / "OKX_SECOND_HALF_WRONG_DIRECTION_CASES.md").write_text("\n".join(md5), encoding="utf-8")

    # ---------- F: direction explanations ----------
    print("[F] direction explanations ...", file=sys.stderr)
    # For each triggered+filtered-kept zone, plus key candidate/confirmed zones
    explanations = []
    for z in zones_all:
        # Include: all confirmed zones (regardless of trigger) — these are the TG-watch candidates
        if not z.get("confirmedTs"): continue
        dec = decisions.get(z["id"], {})
        expl = direction_explanation(z)
        stage = "trigger" if z.get("triggerTs") else "confirmed"
        explanations.append({
            "date": z["_date"], "zone_id": z["id"],
            "stage_max": stage,
            "candidate_iso": ms_to_iso(z.get("startTs")),
            "confirmed_iso": ms_to_iso(z.get("confirmedTs")),
            "trigger_iso": ms_to_iso(z.get("triggerTs")),
            "zone_low": z.get("zoneLow"), "zone_high": z.get("zoneHigh"),
            "zone_mid": mid_price(z),
            "direction": expl["direction"], "confidence": expl["confidence"],
            "evidence_count": expl["evidence_count"],
            "summary": expl["summary"],
            "filter_kept": dec.get("kept"),
            "engine_class": z["_class"],
        })
    expl_json = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "n_zones_with_explanation": len(explanations),
        "rows": explanations,
    }
    (REP_OUT / "OKX_SECOND_HALF_DIRECTION_EXPLANATIONS_FOR_TG_WATCH.json").write_text(
        json.dumps(expl_json, indent=2, default=str), encoding="utf-8")
    if explanations:
        with (REP_OUT / "OKX_SECOND_HALF_DIRECTION_EXPLANATIONS_FOR_TG_WATCH.csv").open("w", encoding="utf-8", newline="") as f:
            keys = ["date", "zone_id", "direction", "stage_max", "confidence", "evidence_count",
                    "confirmed_iso", "trigger_iso", "zone_low", "zone_high", "engine_class",
                    "filter_kept", "summary"]
            w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
            w.writeheader()
            for r in explanations: w.writerow(r)
    md6 = [
        "# Direction explanations for TG-watch candidates",
        "",
        f"**Build:** {expl_json['build_time_utc']}",
        f"**Confirmed zones with explanation:** {len(explanations)}",
        "",
        "## Confidence distribution",
        "",
    ]
    conf_dist = defaultdict(int)
    for r in explanations: conf_dist[r["confidence"]] += 1
    for k, v in conf_dist.items():
        md6.append(f"- {k}: **{v}**")
    md6.extend(["", "## Sample (first 20 by date)", "",
                 "| date | dir | stage | confidence | n evidence | confirmed | filter kept | engine class | summary |",
                 "|---|---|---|---|---:|---|:---:|---|---|"])
    for r in sorted(explanations, key=lambda x: (x["date"], x.get("confirmed_iso") or ""))[:20]:
        md6.append(
            f"| {r['date']} | {r['direction']} | {r['stage_max']} | {r['confidence']} | "
            f"{r['evidence_count']} | {r['confirmed_iso']} | "
            f"{'Y' if r['filter_kept'] else 'N'} | {r['engine_class']} | {r['summary'][:80]}... |"
        )
    (REP_OUT / "OKX_SECOND_HALF_DIRECTION_EXPLANATIONS_FOR_TG_WATCH.md").write_text("\n".join(md6), encoding="utf-8")

    # ---------- G: TG-watch volume ----------
    print("[G] TG-watch volume modes ...", file=sys.stderr)
    # Build per-mode alert lists
    by_date_zones = defaultdict(list)
    for r in explanations:
        by_date_zones[r["date"]].append(r)
    mode_results = {}
    n_days = len(ready)
    def evaluate_mode(name: str, predicate, max_per_day: int | None = None,
                     max_per_dir_per_day: int | None = None) -> dict:
        alerts = []
        for d in ready:
            day_alerts = [r for r in by_date_zones[d] if predicate(r)]
            day_alerts.sort(key=lambda r: r.get("confirmed_iso") or "")
            if max_per_dir_per_day is not None:
                seen = defaultdict(int)
                kept = []
                for r in day_alerts:
                    if seen[r["direction"]] < max_per_dir_per_day:
                        kept.append(r); seen[r["direction"]] += 1
                day_alerts = kept
            if max_per_day is not None:
                day_alerts = day_alerts[:max_per_day]
            alerts.extend(day_alerts)
        # Cross-reference with market moves: did each alert have a 2% move in correct direction within next 4h from confirmed_iso?
        covered_early = 0; missed = 0; wrong = 0
        lead_minutes = []
        n_long = 0; n_short = 0
        for a in alerts:
            if a["direction"] == "LONG": n_long += 1
            else: n_short += 1
            conf_iso = a.get("confirmed_iso")
            if not conf_iso: continue
            conf_dt = dt.datetime.fromisoformat(conf_iso)
            conf_sec = int(conf_dt.timestamp())
            d = a["date"]
            # any matching market move within 4h after confirmed?
            ms = [m for m in moves_by_date.get(d, []) if not m.secondary]
            matched = None
            for m in ms:
                if m.start_sec < conf_sec - 600: continue
                if m.start_sec > conf_sec + 4 * 3600: continue
                if a["direction"] == "LONG" and m.direction == "UP":
                    matched = m; break
                if a["direction"] == "SHORT" and m.direction == "DOWN":
                    matched = m; break
            if matched:
                covered_early += 1
                lead_minutes.append((matched.start_sec - conf_sec) / 60.0)
            else:
                # check opposite direction move
                opp_match = None
                for m in ms:
                    if abs(m.start_sec - conf_sec) > 4 * 3600: continue
                    if (a["direction"] == "LONG" and m.direction == "DOWN") or (a["direction"] == "SHORT" and m.direction == "UP"):
                        opp_match = m; break
                if opp_match: wrong += 1
                else: missed += 1
        return {
            "mode": name, "total_alerts": len(alerts),
            "alerts_per_day": round(len(alerts) / n_days, 3) if n_days else 0,
            "long_count": n_long, "short_count": n_short,
            "covered_2pct_move_after_confirmed": covered_early,
            "wrong_direction_alerts": wrong,
            "missed_or_no_move": missed,
            "avg_lead_minutes": round(stats.mean(lead_minutes), 2) if lead_minutes else None,
        }

    mode_results["mode_1_confirmed_only"] = evaluate_mode(
        "confirmed_only", lambda r: True)
    mode_results["mode_2_candidate_MID+"] = evaluate_mode(
        "candidate_MID+", lambda r: r["confidence"] in ("MID", "HIGH"))
    mode_results["mode_3_confirmed_MID+"] = evaluate_mode(
        "confirmed_MID+", lambda r: r["confidence"] in ("MID", "HIGH"))
    mode_results["mode_4_confirmed_HIGH_only"] = evaluate_mode(
        "confirmed_HIGH_only", lambda r: r["confidence"] == "HIGH")
    mode_results["mode_5_max1_per_direction_per_day"] = evaluate_mode(
        "max1_per_direction_per_day", lambda r: True, max_per_dir_per_day=1)
    mode_results["mode_6_max2_total_per_day"] = evaluate_mode(
        "max2_total_per_day", lambda r: True, max_per_day=2)

    vol_json = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "ready_days": ready, "n_days": n_days,
        "modes": mode_results,
    }
    (REP_OUT / "OKX_SECOND_HALF_TG_WATCH_CANDIDATE_VOLUME.json").write_text(
        json.dumps(vol_json, indent=2, default=str), encoding="utf-8")
    md7 = [
        "# TG-watch candidate volume per mode",
        "",
        f"**Build:** {vol_json['build_time_utc']}",
        f"**Days:** {n_days}",
        "",
        "| mode | total | per day | LONG | SHORT | covered 2% after confirm | wrong dir | missed | avg lead min |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for k, m in mode_results.items():
        md7.append(f"| `{m['mode']}` | {m['total_alerts']} | {m['alerts_per_day']} | "
                   f"{m['long_count']} | {m['short_count']} | "
                   f"{m['covered_2pct_move_after_confirmed']} | "
                   f"{m['wrong_direction_alerts']} | {m['missed_or_no_move']} | "
                   f"{m['avg_lead_minutes']} |")
    (REP_OUT / "OKX_SECOND_HALF_TG_WATCH_CANDIDATE_VOLUME.md").write_text("\n".join(md7), encoding="utf-8")

    # CSV
    with (REP_OUT / "OKX_SECOND_HALF_TG_WATCH_CANDIDATE_VOLUME.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(next(iter(mode_results.values())).keys()))
        w.writeheader()
        for k, m in mode_results.items(): w.writerow(m)

    # ---------- H: confirmation logic audit ----------
    print("[H] confirmation audit ...", file=sys.stderr)
    confirmed_zones = [z for z in zones_all if z.get("confirmedTs")]
    confirmed_then_reached = [z for z in confirmed_zones if is_reached(z)]
    confirmed_then_failed = [z for z in confirmed_zones if z["_class"] == "failed_triggered"]
    confirmed_no_trigger = [z for z in confirmed_zones if not z.get("triggerTs")]
    confirmed_slow_ctr = [z for z in confirmed_zones if (confirm_to_trigger_min(z) or 0) > 60]
    # Could TG watch at confirmed be useful? Cross-reference with market moves
    conf_useful = 0
    for z in confirmed_zones:
        d = z["_date"]
        conf_sec = z["confirmedTs"] // 1000
        ms = moves_by_date.get(d, [])
        for m in ms:
            if m.secondary: continue
            if m.start_sec < conf_sec - 600: continue
            if m.start_sec > conf_sec + 4 * 3600: continue
            correct = (z["direction"] == "LONG" and m.direction == "UP") or \
                      (z["direction"] == "SHORT" and m.direction == "DOWN")
            if correct:
                conf_useful += 1; break
    conf_useful_pct = round(100.0 * conf_useful / max(len(confirmed_zones), 1), 2)
    confirm_useful = "YES" if conf_useful_pct >= 20 else ("NO" if conf_useful_pct < 10 else "UNKNOWN")
    confirm_audit = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "n_confirmed_total": len(confirmed_zones),
        "n_reached_after_confirmed": len(confirmed_then_reached),
        "n_failed_after_confirmed": len(confirmed_then_failed),
        "n_no_trigger_after_confirmed": len(confirmed_no_trigger),
        "n_confirm_to_trigger_gt_60m": len(confirmed_slow_ctr),
        "n_confirmed_zones_with_correct_2pct_move_within_4h": conf_useful,
        "pct_confirmed_useful_for_watch": conf_useful_pct,
        "verdict_confirm_useful_for_tg_watch": confirm_useful,
    }
    (REP_OUT / "OKX_SECOND_HALF_CONFIRMATION_LOGIC_AUDIT.json").write_text(
        json.dumps(confirm_audit, indent=2, default=str), encoding="utf-8")
    md8 = [
        "# Confirmation logic audit",
        "",
        f"**Build:** {confirm_audit['build_time_utc']}",
        "",
        f"- n_confirmed total: **{confirm_audit['n_confirmed_total']}**",
        f"- of those reached_raw later: **{confirm_audit['n_reached_after_confirmed']}**",
        f"- of those failed (triggered then stopped): **{confirm_audit['n_failed_after_confirmed']}**",
        f"- of those never triggered: **{confirm_audit['n_no_trigger_after_confirmed']}**",
        f"- of those with confirm→trigger > 60 m: **{confirm_audit['n_confirm_to_trigger_gt_60m']}**",
        f"- of those with correct-direction 2% move within 4 h after confirmed: **{conf_useful}**",
        f"- % confirmed useful for watch-alert: **{conf_useful_pct} %**",
        "",
        f"**Verdict:** `CONFIRM_STAGE_USEFUL_FOR_TG_WATCH = {confirm_useful}`",
    ]
    (REP_OUT / "OKX_SECOND_HALF_CONFIRMATION_LOGIC_AUDIT.md").write_text("\n".join(md8), encoding="utf-8")

    # ---------- I: master addendum + flags ----------
    print("[I] master addendum ...", file=sys.stderr)
    covered_watch_early = counts.get("covered_watch_early", 0) + counts.get("covered_trigger_early", 0)
    n_trigger_early = counts.get("covered_trigger_early", 0)
    n_watch_early = counts.get("covered_watch_early", 0)
    n_mid = counts.get("covered_mid", 0)
    n_late = counts.get("covered_late", 0)
    n_missed = counts.get("missed_move", 0) + counts.get("filtered_correct_zone", 0)
    trigger_only_too_late = "YES" if (n_late + n_mid) > (n_trigger_early + 1) else "NO"
    n_can_1_2_per_day = mode_results["mode_5_max1_per_direction_per_day"]["alerts_per_day"]
    can_tg_1_2 = "YES" if n_can_1_2_per_day <= 2.5 else "NO"

    flags = {
        "DETECTION_QUALITY_ADDENDUM_DONE": "YES",
        "DAYS_INCLUDED": ready,
        "CHAIN_PROGRESS": f"{completed}/{total}",
        "MARKET_2PCT_MOVES_TOTAL": n_primary_total,
        "ENGINE_COVERED_WATCH_EARLY": n_watch_early,
        "ENGINE_COVERED_TRIGGER_EARLY": n_trigger_early,
        "ENGINE_COVERED_MID": n_mid,
        "ENGINE_COVERED_LATE": n_late,
        "ENGINE_MISSED_MOVES": n_missed,
        "CORRECT_ZONES_SUPPRESSED_BY_FILTER": len(correct_suppressed),
        "SLOW_TRIGGER_CORRECT_ZONES": len(slow_correct),
        "WRONG_DIRECTION_CASES": len(wrong_cases),
        "CONFIRM_STAGE_USEFUL_FOR_TG_WATCH": confirm_useful,
        "TRIGGER_ONLY_ALERTS_TOO_LATE": trigger_only_too_late,
        "TG_WATCH_CONFIRMED_ALERTS_PER_DAY": mode_results["mode_1_confirmed_only"]["alerts_per_day"],
        "TG_WATCH_HIGH_CONFIDENCE_ALERTS_PER_DAY": mode_results["mode_4_confirmed_HIGH_only"]["alerts_per_day"],
        "CAN_TG_WATCH_BE_1_2_PER_DAY": can_tg_1_2,
        "DIRECTION_EXPLANATIONS_AVAILABLE": "YES" if len(explanations) > 0 else "NO",
        "LOCAL_NORMALIZATION_STILL_RECOMMENDED": "UNKNOWN",
        "READY_TO_BUILD_TG_WATCH_ZONE_MODE": ("YES" if confirm_useful == "YES" and trigger_only_too_late == "YES"
                                                else "UNKNOWN"),
        "READY_TO_CHANGE_ENGINE": "NO",
        "MORE_VALIDATION_REQUIRED": "YES",
    }

    summary = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "scope": f"OKX direct second-half March - detection quality / TG-watch addendum over {len(ready)} ready days",
        "ready_days": ready, "chain_done": chain_done,
        "section_outputs": {
            "A_market_moves_per_day": "OKX_SECOND_HALF_MARKET_2PCT_MOVES_PER_DAY.{md,json,csv}",
            "B_engine_coverage": "OKX_SECOND_HALF_ENGINE_COVERAGE_EARLY_MID_LATE_MISSED.{md,json,csv}",
            "C_correct_zones_suppressed": "OKX_SECOND_HALF_CORRECT_ZONES_SUPPRESSED_BY_FILTER.{md,json,csv}",
            "D_slow_trigger_correct": "OKX_SECOND_HALF_SLOW_TRIGGER_CORRECT_ZONES.{md,json}",
            "E_wrong_direction": "OKX_SECOND_HALF_WRONG_DIRECTION_CASES.{md,json,csv}",
            "F_direction_explanations": "OKX_SECOND_HALF_DIRECTION_EXPLANATIONS_FOR_TG_WATCH.{md,json,csv}",
            "G_tg_watch_volume": "OKX_SECOND_HALF_TG_WATCH_CANDIDATE_VOLUME.{md,json,csv}",
            "H_confirmation_audit": "OKX_SECOND_HALF_CONFIRMATION_LOGIC_AUDIT.{md,json}",
        },
        "flags": flags,
    }
    (REP_OUT / "OKX_SECOND_HALF_DETECTION_QUALITY_TG_WATCH_ADDENDUM.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8")
    md_master = [
        "# OKX direct second-half March - Detection Quality / TG-Watch Addendum",
        "",
        f"**Build:** {summary['build_time_utc']}",
        f"**Scope:** {summary['scope']}",
        f"**Chain status:** {completed}/{total} days completed; chain done = **{chain_done}**.",
        f"**Days included:** {ready}",
        "",
        "## 1. Market 2 % moves per day",
        f"  - **{n_primary_total}** primary 2 % moves across {len(ready)} days.",
        "",
        "## 2. Engine coverage early/mid/late/missed",
        f"  - covered_watch_early: {n_watch_early}",
        f"  - covered_trigger_early: {n_trigger_early}",
        f"  - covered_mid (trigger after 0-50% of move): {n_mid}",
        f"  - covered_late (trigger after 50% of move): {n_late}",
        f"  - missed_move / filtered_correct_zone: {n_missed}",
        "",
        "## 3. Correct zones suppressed by filter",
        f"  - **{len(correct_suppressed)}** correct zones were suppressed by base filter (slow_trigger / duplicate_60m).",
        "",
        "## 4. Slow-trigger correct zones",
        f"  - **{len(slow_correct)}** zones had confirm→trigger > 60 m AND direction matches a market 2 % move.",
        f"  - Of those, **{slow_json['n_could_alert_at_confirmed']}** had strong-enough confirmed-stage evidence (absorb >= 0.6 OR cycles >= 5) to justify a watch alert.",
        "",
        "## 5. Wrong-direction cases",
        f"  - **{len(wrong_cases)}** triggered zones had no 2 % move in their direction within 4 h forward.",
        "",
        "## 6. Direction explanation examples",
        f"  - direction explanation generated for **{len(explanations)}** confirmed/triggered zones.",
        "",
        "## 7. TG-watch candidate count per day",
        "",
        "| mode | per day | covered move | wrong dir | missed | avg lead min |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for k, m in mode_results.items():
        md_master.append(f"| `{m['mode']}` | {m['alerts_per_day']} | "
                          f"{m['covered_2pct_move_after_confirmed']} | "
                          f"{m['wrong_direction_alerts']} | {m['missed_or_no_move']} | "
                          f"{m['avg_lead_minutes']} |")
    md_master.extend([
        "",
        "## 8. Whether confirmed stage is useful for TG-watch",
        f"  - {confirm_useful}. {conf_useful_pct} % of confirmed zones had a correct-direction 2 % move within 4 h after confirmed timestamp.",
        "",
        "## 9. Whether trigger-only alerts are too late",
        f"  - **{trigger_only_too_late}** (covered_late+covered_mid={n_late + n_mid} vs covered_trigger_early={n_trigger_early}).",
        "",
        "## 10. Recommended next action",
        "  - Build research-only TG-watch prototype: alert at `confirmed` stage with direction-explanation summary.",
        "  - Validate on second OOS period before any production integration.",
        "  - NO engine / threshold / detector change.",
        "",
        "## Final flag matrix",
        "",
        "```",
    ])
    for k, v in flags.items():
        md_master.append(f"{k} = {v}")
    md_master.extend(["```", "",
                       "## Hard rules honored",
                       "- strategy / thresholds / `zoneDetector`: UNCHANGED",
                       "- main chain NOT touched",
                       "- post-trigger fields used only as labels, never as features",
                       "- target STRICT 2 %",
                       "- READY_TO_CHANGE_ENGINE = NO"])
    (REP_OUT / "OKX_SECOND_HALF_DETECTION_QUALITY_TG_WATCH_ADDENDUM.md").write_text(
        "\n".join(md_master), encoding="utf-8")

    print()
    print("FINAL FLAGS:")
    for k, v in flags.items():
        print(f"  {k:<52s} = {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
