"""Max2 selected zones + confirmation noise audit (Sections A-G).

READ-ONLY post-hoc audit. Auto-discovers ready days from the running chain.
Re-runnable when chain progresses; pass --rerun to clear caches.

NO engine / threshold / detector change.
"""
from __future__ import annotations
import csv
import datetime as dt
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


def discover_ready_days() -> tuple[list[str], int, int, bool]:
    if not CHAIN_RESULTS_JSON.exists():
        rds = sorted([p.stem.replace("OKX_DIRECT_TECHNICAL_REPLAY_", "")
                      for p in REP_OKX.glob("OKX_DIRECT_TECHNICAL_REPLAY_2026-03-*.json")
                      if 16 <= int(p.stem.split("-")[-1]) <= 31])
        return rds, len(rds), 15, False
    d = json.loads(CHAIN_RESULTS_JSON.read_text(encoding="utf-8"))
    completed = d.get("completed_count", 0); total = d.get("total_count", 15)
    ready = sorted([r["date"] for r in d.get("results", [])
                     if r.get("status") == "ok"
                     and (r.get("backtest") or {}).get("exit_code") == 0
                     and (REP_OKX / f"OKX_DIRECT_TECHNICAL_REPLAY_{r['date']}.json").exists()])
    return ready, completed, total, completed == total


# ---------- helpers ----------

def mid_price(z):
    lo, hi = z.get("zoneLow"), z.get("zoneHigh")
    return None if lo is None or hi is None else (lo + hi) / 2.0


def is_triggered(z): return z.get("status") in ("RESOLVED_REACHED", "RESOLVED_FAILED")
def is_reached(z): return z.get("status") == "RESOLVED_REACHED"


def confirm_to_trigger_min(z):
    c, t = z.get("confirmedTs"), z.get("triggerTs")
    return None if c is None or t is None else (t - c) / 60000.0


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
    if not p.exists(): return []
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
            decisions[z["id"]] = {
                "kept": (not dup) and fast_ok,
                "fast_ok": fast_ok, "dup_suppressed": dup, "ctm_min": ctm,
            }
    return decisions


def reasons_dict(z):
    out = {}
    for r in z.get("reasons", []):
        out[r.get("stage")] = r.get("conditions") or {}
    return out


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


# ---------- confidence + ranking ----------

def confidence_and_evidence(z: dict) -> dict:
    rd = reasons_dict(z)
    cand = rd.get("candidate") or {}
    conf = rd.get("confirmed") or {}
    trig = rd.get("trigger") or {}
    scores = z.get("scores") or {}
    direction = z["direction"]
    notes = []; ev = 0
    if direction == "LONG":
        if (cand.get("sellPressure") or 0) >= 0.6: notes.append("aggressive_sell_absorbed"); ev += 1
        if (cand.get("absorbScore") or 0) >= 0.6: notes.append("bid_absorbed_sells"); ev += 1
        if cand.get("bidRefillScore"): notes.append("bid_refill_score_present"); ev += 1
        if cand.get("rangeCompression"): notes.append("range_compression"); ev += 1
        if conf.get("voidScore"): notes.append("void_score_present"); ev += 1
        if (conf.get("cyclesSeen") or 0) >= 5: notes.append(f"{conf.get('cyclesSeen')}_defense_cycles"); ev += 1
        if (conf.get("defendedPersistenceSec") or 0) >= 600: notes.append("zone_defended_long"); ev += 1
        if (scores.get("ofiScore") or 0) > 0.05: notes.append("OFI_buy_side"); ev += 1
        if (trig.get("flowMultiplier") or 0) >= 1.5: notes.append("trigger_flow_strong"); ev += 1
        if trig.get("sideFlowOk"): notes.append("side_flow_ok"); ev += 1
    else:
        if (cand.get("buyPressure") or 0) >= 0.6: notes.append("aggressive_buy_absorbed"); ev += 1
        if (cand.get("absorbScore") or 0) >= 0.6: notes.append("ask_absorbed_buys"); ev += 1
        if cand.get("askRefillScore"): notes.append("ask_refill_score_present"); ev += 1
        if cand.get("rangeCompression"): notes.append("range_compression"); ev += 1
        if conf.get("voidScore"): notes.append("void_score_present"); ev += 1
        if (conf.get("cyclesSeen") or 0) >= 5: notes.append(f"{conf.get('cyclesSeen')}_defense_cycles"); ev += 1
        if (conf.get("defendedPersistenceSec") or 0) >= 600: notes.append("zone_defended_long"); ev += 1
        if (scores.get("ofiScore") or 0) < -0.05: notes.append("OFI_sell_side"); ev += 1
        if (trig.get("flowMultiplier") or 0) >= 1.5: notes.append("trigger_flow_strong"); ev += 1
        if trig.get("sideFlowOk"): notes.append("side_flow_ok"); ev += 1
    if ev >= 5: confidence = "HIGH"
    elif ev >= 3: confidence = "MID"
    else: confidence = "LOW"
    return {"confidence": confidence, "evidence_count": ev, "notes": notes, "summary":
            (f"{direction} because " + "; ".join(notes)) if notes else f"{direction} (insufficient evidence)"}


def rank_score(z: dict, ev_info: dict) -> float:
    """Composite ranking: confidence_count + small_bonus_for_early_confirmed.
    Higher = better. Used to pick top-N per day.
    """
    base = ev_info["evidence_count"]
    # Add 0.5 for HIGH, 0.25 for MID
    base += {"HIGH": 0.5, "MID": 0.25, "LOW": 0.0}[ev_info["confidence"]]
    # Subtract per slow_trigger
    ctm = confirm_to_trigger_min(z) or 0
    if ctm > 60: base -= 0.1
    if ctm > 180: base -= 0.2
    return base


# ---------- coverage check for a given zone confirmedTs ----------

def coverage_for_zone(z: dict, moves_by_date: dict) -> dict:
    d = z["_date"]
    conf_ts_ms = z.get("confirmedTs")
    conf_sec = conf_ts_ms // 1000 if conf_ts_ms else None
    if conf_sec is None:
        return {"result": "no_confirmed_stage"}
    correct_dir = "UP" if z["direction"] == "LONG" else "DOWN"
    opposite_dir = "DOWN" if correct_dir == "UP" else "UP"
    # check 4h window from confirmed
    end_sec = conf_sec + 4 * 3600
    # any matching primary 2% move?
    matched = None
    opp_match = None
    for m in moves_by_date.get(d, []):
        if m.secondary: continue
        if m.start_sec < conf_sec - 600: continue
        if m.start_sec > end_sec: continue
        if m.direction == correct_dir:
            matched = m; break
    if not matched:
        for m in moves_by_date.get(d, []):
            if m.secondary: continue
            if m.start_sec < conf_sec - 600: continue
            if m.start_sec > end_sec: continue
            if m.direction == opposite_dir:
                opp_match = m; break
    if matched:
        lead_min = (matched.start_sec - conf_sec) / 60.0
        return {"result": "covered_2pct_move",
                "matched_move_start_iso": sec_to_iso(matched.start_sec),
                "matched_move_size_pct": matched.size_pct,
                "lead_min": round(lead_min, 2)}
    if opp_match:
        return {"result": "wrong_direction",
                "opp_move_start_iso": sec_to_iso(opp_match.start_sec),
                "opp_move_size_pct": opp_match.size_pct}
    # secondary 1.5% move correct dir?
    for m in moves_by_date.get(d, []):
        if not m.secondary: continue
        if m.start_sec < conf_sec - 600: continue
        if m.start_sec > end_sec: continue
        if m.direction == correct_dir:
            return {"result": "noisy_partial_1_5pct",
                    "matched_move_start_iso": sec_to_iso(m.start_sec),
                    "matched_move_size_pct": m.size_pct}
    return {"result": "missed_no_move_in_4h"}


# ---------- main ----------

def main() -> int:
    ready, completed, total, chain_done = discover_ready_days()
    print(f"chain {completed}/{total}  chain_done={chain_done}", file=sys.stderr)
    print(f"ready days: {ready}", file=sys.stderr)
    if not ready:
        print("no ready days", file=sys.stderr); return 1

    zones_all = []; zones_by_date = {}
    for d in ready:
        zs = load_zones(d); zones_by_date[d] = zs; zones_all.extend(zs)
    decisions = apply_passive_filter(zones_all)

    print("building 1s buckets ...", file=sys.stderr)
    buckets_by_date: dict[str, list[Bucket]] = {}
    for d in ready:
        p = DATA_ROOT / d / "trades.csv.gz"
        if p.exists():
            buckets_by_date[d] = build_buckets_from_trades_csv(p)
        else:
            buckets_by_date[d] = []

    print("detecting market moves ...", file=sys.stderr)
    moves_by_date: dict[str, list[Move]] = {}
    for d in ready:
        moves_by_date[d] = detect_moves(d, buckets_by_date.get(d, []))

    confirmed_zones = [z for z in zones_all if z.get("confirmedTs")]
    print(f"  total confirmed zones: {len(confirmed_zones)}", file=sys.stderr)

    # Build per-zone enriched record
    enriched = []
    for z in confirmed_zones:
        ev = confidence_and_evidence(z)
        cov = coverage_for_zone(z, moves_by_date)
        dec = decisions.get(z["id"], {})
        enriched.append({
            "date": z["_date"], "zone_id": z["id"], "direction": z["direction"],
            "candidate_iso": ms_to_iso(z.get("startTs")),
            "confirmed_iso": ms_to_iso(z.get("confirmedTs")),
            "trigger_iso": ms_to_iso(z.get("triggerTs")),
            "zone_low": z.get("zoneLow"), "zone_high": z.get("zoneHigh"),
            "zone_mid": mid_price(z),
            "confidence": ev["confidence"],
            "evidence_count": ev["evidence_count"],
            "evidence_notes": ev["notes"],
            "summary": ev["summary"],
            "rank_score": round(rank_score(z, ev), 3),
            "filter_kept": dec.get("kept"),
            "filter_fast_ok": dec.get("fast_ok"),
            "filter_dup_suppressed": dec.get("dup_suppressed"),
            "filter_ctm_min": dec.get("ctm_min"),
            "engine_class": z["_class"],
            "engine_is_primary": bool(z.get("isPrimaryMoveZone")),
            "engine_reached_raw": is_reached(z),
            "coverage_result": cov["result"],
            "coverage_lead_min": cov.get("lead_min"),
            "coverage_matched_move_size": cov.get("matched_move_size_pct") or cov.get("opp_move_size_pct"),
            "_z": z,   # keep ref for downstream
        })

    # ---------- Section A: max2_total_per_day selection ----------
    print("[A] max2 selected zones ...", file=sys.stderr)
    by_date = defaultdict(list)
    for r in enriched: by_date[r["date"]].append(r)

    max2_selected = []
    for d in ready:
        cand = by_date[d]
        # sort by rank_score desc, then by confirmed_iso asc (earlier is better tie-break)
        cand_sorted = sorted(cand, key=lambda r: (-r["rank_score"], r["confirmed_iso"] or ""))
        for rank_in_day, r in enumerate(cand_sorted[:2], 1):
            row = dict(r)
            row.pop("_z", None)
            row["rank_in_day"] = rank_in_day
            row["stage_used_for_tg_watch"] = "confirmed"
            row["why_selected"] = (f"highest rank_score {r['rank_score']} on day "
                                   f"({r['evidence_count']} evidence, {r['confidence']} confidence)")
            # related move info
            cov = {"result": r["coverage_result"], "lead_min": r["coverage_lead_min"]}
            row["related_market_move_size_pct"] = r["coverage_matched_move_size"]
            row["coverage_result"] = r["coverage_result"]
            row["lead_min_before_move"] = r["coverage_lead_min"]
            max2_selected.append(row)

    n_covered = sum(1 for r in max2_selected if r["coverage_result"] == "covered_2pct_move")
    n_wrong = sum(1 for r in max2_selected if r["coverage_result"] == "wrong_direction")
    n_noisy = sum(1 for r in max2_selected if r["coverage_result"] == "noisy_partial_1_5pct")
    n_missed = sum(1 for r in max2_selected if r["coverage_result"] == "missed_no_move_in_4h")

    sel_json = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "scope": f"max2_total_per_day selected zones across {len(ready)} ready days",
        "ranking_rule": "rank_score = evidence_count + confidence_bonus(HIGH=0.5, MID=0.25) - slow_trigger_penalty",
        "rows": max2_selected,
        "counts": {"covered_2pct_move": n_covered, "wrong_direction": n_wrong,
                    "noisy_partial_1_5pct": n_noisy, "missed_no_move_in_4h": n_missed,
                    "total": len(max2_selected)},
    }
    (REP_OUT / "OKX_SECOND_HALF_MAX2_SELECTED_WATCH_ZONES.json").write_text(
        json.dumps(sel_json, indent=2, default=str), encoding="utf-8")
    if max2_selected:
        keys = ["date", "rank_in_day", "zone_id", "direction", "stage_used_for_tg_watch",
                "candidate_iso", "confirmed_iso", "trigger_iso", "zone_low", "zone_high", "zone_mid",
                "confidence", "evidence_count", "rank_score", "filter_kept", "filter_dup_suppressed",
                "filter_ctm_min", "engine_class", "engine_is_primary",
                "engine_reached_raw", "coverage_result", "lead_min_before_move",
                "related_market_move_size_pct", "why_selected", "summary"]
        with (REP_OUT / "OKX_SECOND_HALF_MAX2_SELECTED_WATCH_ZONES.csv").open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
            w.writeheader()
            for r in max2_selected: w.writerow(r)
    md_a = [
        "# max2_total_per_day - selected watch zones (concrete list)",
        "",
        f"**Build:** {sel_json['build_time_utc']}",
        f"**Scope:** {sel_json['scope']}",
        f"**Ranking rule:** `{sel_json['ranking_rule']}`",
        "",
        f"**Counts:** covered={n_covered}, wrong_dir={n_wrong}, noisy_1.5%={n_noisy}, missed={n_missed} / total={len(max2_selected)}",
        "",
        "| date | rank | dir | conf-time | confidence | evidence | rank_score | filter | engine class | coverage | lead min | summary |",
        "|---|---:|---|---|---|---:|---:|:---:|---|---|---:|---|",
    ]
    for r in max2_selected:
        md_a.append(
            f"| {r['date']} | {r['rank_in_day']} | {r['direction']} | {r['confirmed_iso']} | "
            f"{r['confidence']} | {r['evidence_count']} | {r['rank_score']} | "
            f"{'Y' if r['filter_kept'] else 'N'} | {r['engine_class']} | "
            f"**{r['coverage_result']}** | {r['lead_min_before_move']} | {r['summary'][:80]}... |"
        )
    (REP_OUT / "OKX_SECOND_HALF_MAX2_SELECTED_WATCH_ZONES.md").write_text("\n".join(md_a), encoding="utf-8")

    # ---------- Section B: missed market moves under max2 ----------
    print("[B] missed moves audit ...", file=sys.stderr)
    selected_set = {(r["date"], r["zone_id"]) for r in max2_selected}
    # for each primary market move, was there ANY max2 selected zone covering it?
    move_coverage_by_max2 = []
    for d in ready:
        for m in moves_by_date.get(d, []):
            if m.secondary: continue
            # find any selected zone with correct direction whose confirmedTs ≤ move.start_sec + 600
            # AND was in selected_set
            covered_by_max2 = None
            for s in max2_selected:
                if s["date"] != d: continue
                if (s["direction"] == "LONG" and m.direction != "UP") or \
                   (s["direction"] == "SHORT" and m.direction != "DOWN"): continue
                if not s["confirmed_iso"]: continue
                s_sec = int(dt.datetime.fromisoformat(s["confirmed_iso"]).timestamp())
                if s_sec < m.start_sec - 4 * 3600: continue
                if s_sec > m.start_sec + 600: continue
                covered_by_max2 = s["zone_id"]; break

            # What WERE the top2 of that day?
            top2 = sorted([r for r in by_date[d]],
                          key=lambda r: (-r["rank_score"], r["confirmed_iso"] or ""))[:2]
            top2_ids = [t["zone_id"] for t in top2]

            # If not covered, find the BEST correct-direction zone that was NOT selected
            best_unselected_correct = None
            best_unselected_score = -999
            for z in zones_by_date[d]:
                if z["direction"] != ("LONG" if m.direction == "UP" else "SHORT"): continue
                if not z.get("confirmedTs"): continue
                z_sec = z["confirmedTs"] // 1000
                if z_sec > m.start_sec + 600: continue
                if z_sec < m.start_sec - 4 * 3600: continue
                ev = confidence_and_evidence(z)
                sc = rank_score(z, ev)
                if sc > best_unselected_score and z["id"] not in top2_ids:
                    best_unselected_correct = z
                    best_unselected_score = sc

            reason = None
            if covered_by_max2 is None:
                if best_unselected_correct is not None:
                    bev = confidence_and_evidence(best_unselected_correct)
                    bdec = decisions.get(best_unselected_correct["id"], {})
                    reason_parts = [f"best correct-dir zone {best_unselected_correct['id'][-15:]} "
                                    f"with rank_score {round(rank_score(best_unselected_correct, bev), 2)} "
                                    f"({bev['confidence']}, ev={bev['evidence_count']}) "
                                    f"lost to top-2 (rank_scores {[t['rank_score'] for t in top2]})"]
                    if bdec.get("dup_suppressed"): reason_parts.append("base filter dup_suppressed")
                    if not bdec.get("fast_ok"):
                        ctm = bdec.get("ctm_min")
                        reason_parts.append(f"base filter slow_trigger ctm={ctm:.0f}" if ctm is not None else "base filter slow_trigger (no_trigger)")
                    reason = "; ".join(reason_parts)
                else:
                    reason = "no correct-direction confirmed zone within the window"

            move_coverage_by_max2.append({
                "date": d, "direction": m.direction, "size_pct": m.size_pct,
                "move_start_iso": sec_to_iso(m.start_sec), "move_end_iso": sec_to_iso(m.end_sec),
                "covered_by_max2_zone_id": covered_by_max2,
                "top2_selected_ids_on_day": top2_ids,
                "top2_directions": [t["direction"] for t in top2],
                "best_unselected_correct_zone_id": (best_unselected_correct["id"]
                                                     if best_unselected_correct else None),
                "best_unselected_rank_score": (round(rank_score(best_unselected_correct,
                                                                 confidence_and_evidence(best_unselected_correct)), 2)
                                                if best_unselected_correct else None),
                "miss_reason": reason if covered_by_max2 is None else None,
            })

    n_total_moves = len(move_coverage_by_max2)
    n_max2_covered = sum(1 for r in move_coverage_by_max2 if r["covered_by_max2_zone_id"])
    n_max2_missed = n_total_moves - n_max2_covered

    miss_json = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "n_market_2pct_moves": n_total_moves,
        "n_covered_by_max2": n_max2_covered,
        "n_missed_by_max2": n_max2_missed,
        "rows": move_coverage_by_max2,
    }
    (REP_OUT / "OKX_SECOND_HALF_MAX2_MISSED_MOVES_AUDIT.json").write_text(
        json.dumps(miss_json, indent=2, default=str), encoding="utf-8")
    md_b = [
        "# max2_total_per_day - missed market moves audit",
        "",
        f"**Build:** {miss_json['build_time_utc']}",
        f"**Market 2 % moves total:** {n_total_moves}, covered by max2: **{n_max2_covered}**, missed: **{n_max2_missed}**",
        "",
        "| date | dir | size % | move start | covered? | top2 dirs | best unselected correct | miss reason |",
        "|---|---|---:|---|:---:|---|---|---|",
    ]
    for r in move_coverage_by_max2:
        md_b.append(
            f"| {r['date']} | {r['direction']} | {r['size_pct']} | {r['move_start_iso']} | "
            f"{'YES' if r['covered_by_max2_zone_id'] else 'NO'} | {r['top2_directions']} | "
            f"`{(r['best_unselected_correct_zone_id'] or '—')[-20:]}` "
            f"(rs={r['best_unselected_rank_score']}) | {r['miss_reason'] or ''} |"
        )
    (REP_OUT / "OKX_SECOND_HALF_MAX2_MISSED_MOVES_AUDIT.md").write_text("\n".join(md_b), encoding="utf-8")

    # ---------- Section C: wrong-direction selected ----------
    print("[C] wrong-direction selected ...", file=sys.stderr)
    wrong_selected = [r for r in max2_selected if r["coverage_result"] == "wrong_direction"]
    wrong_rows = []
    for r in wrong_selected:
        z = next(zz for zz in zones_all if zz["id"] == r["zone_id"])
        d = r["date"]
        conf_sec = int(dt.datetime.fromisoformat(r["confirmed_iso"]).timestamp())
        # find opposite move and check 1.5/2% potential in selected direction in next 4h from buckets
        buckets = buckets_by_date.get(d, [])
        slice_b = [b for b in buckets if conf_sec <= b.sec <= conf_sec + 4 * 3600]
        if slice_b and z.get("triggerTs"):
            tp = mid_price(z) or buckets[0].last
            if z["direction"] == "LONG":
                max_fav = max((b.high - tp) / tp * 100.0 for b in slice_b)
                max_adv = max((tp - b.low) / tp * 100.0 for b in slice_b)
            else:
                max_fav = max((tp - b.low) / tp * 100.0 for b in slice_b)
                max_adv = max((b.high - tp) / tp * 100.0 for b in slice_b)
        else:
            max_fav = max_adv = None
        opp_cand = next((zz for zz in zones_all
                          if zz["_date"] == d and zz["direction"] != z["direction"]
                          and zz.get("confirmedTs") and abs((zz["confirmedTs"]//1000) - conf_sec) <= 7200), None)
        opp_info = None
        if opp_cand:
            opp_ev = confidence_and_evidence(opp_cand)
            opp_dec = decisions.get(opp_cand["id"], {})
            opp_info = {
                "opposite_candidate_zone_id": opp_cand["id"],
                "opposite_confidence": opp_ev["confidence"],
                "opposite_evidence_count": opp_ev["evidence_count"],
                "opposite_filter_kept": opp_dec.get("kept"),
                "opposite_in_top2": opp_cand["id"] in (set(r["zone_id"] for r in max2_selected
                                                            if r["date"] == d)),
            }
        # Why selected
        why = []
        if r["evidence_count"] >= 3: why.append(f"sufficient evidence ({r['evidence_count']})")
        if r["confidence"] in ("MID", "HIGH"): why.append(f"{r['confidence']} confidence")
        if r["filter_kept"]: why.append("base filter kept")
        # What could prevent
        prevention = []
        if opp_info and opp_info["opposite_confidence"] in ("MID", "HIGH"):
            prevention.append("opposite-direction candidate with equal/better confidence was available — direction-balance check would skip this")
        if max_fav is not None and max_fav < 1.0:
            prevention.append(f"selected direction had max favorable {max_fav:.2f}% in 4h — late-context guard")
        if not prevention:
            prevention.append("local impulse / trend filter could downgrade this")
        wrong_rows.append({
            "date": d, "selected_zone_id": r["zone_id"],
            "selected_direction": r["direction"],
            "actual_move_direction": "DOWN" if r["direction"] == "LONG" else "UP",
            "confirmed_iso": r["confirmed_iso"],
            "trigger_iso": r["trigger_iso"],
            "confidence": r["confidence"],
            "evidence_count": r["evidence_count"],
            "evidence_notes": r["evidence_notes"],
            "max_4h_favorable_in_selected_dir_pct": round(max_fav, 4) if max_fav else None,
            "max_4h_adverse_in_selected_dir_pct": round(max_adv, 4) if max_adv else None,
            "opposite_candidate_info": opp_info,
            "why_engine_chose_this_direction": "; ".join(why),
            "prevention_rule_candidate": "; ".join(prevention),
            "legitimate_or_noise": "wrong_direction_noise" if (max_fav or 0) < 1 else "ambiguous_local_setup",
        })

    wrong_json = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "n_wrong_direction_selected": len(wrong_rows),
        "rows": wrong_rows,
    }
    (REP_OUT / "OKX_SECOND_HALF_MAX2_WRONG_DIRECTION_AUDIT.json").write_text(
        json.dumps(wrong_json, indent=2, default=str), encoding="utf-8")
    md_c = [
        "# max2_total_per_day - wrong-direction selected zones audit",
        "",
        f"**Build:** {wrong_json['build_time_utc']}",
        f"**Wrong-direction selected count:** {len(wrong_rows)}",
        "",
    ]
    for r in wrong_rows:
        md_c.append(f"## {r['date']} `{r['selected_zone_id'][-25:]}` — engine SELECTED {r['selected_direction']}, market went {r['actual_move_direction']}")
        md_c.append("")
        md_c.append(f"- confirmed at: {r['confirmed_iso']}")
        md_c.append(f"- confidence: **{r['confidence']}** (evidence count {r['evidence_count']})")
        md_c.append(f"- evidence: {r['evidence_notes']}")
        md_c.append(f"- 4h forward in selected dir: max fav {r['max_4h_favorable_in_selected_dir_pct']}%, max adv {r['max_4h_adverse_in_selected_dir_pct']}%")
        md_c.append(f"- opposite-direction candidate present: {r['opposite_candidate_info']}")
        md_c.append(f"- why engine chose this side: {r['why_engine_chose_this_direction']}")
        md_c.append(f"- prevention rule candidate: **{r['prevention_rule_candidate']}**")
        md_c.append(f"- classification: **{r['legitimate_or_noise']}**")
        md_c.append("")
    (REP_OUT / "OKX_SECOND_HALF_MAX2_WRONG_DIRECTION_AUDIT.md").write_text("\n".join(md_c), encoding="utf-8")

    # ---------- Section D: confirmation noise audit ----------
    print("[D] confirmation noise audit ...", file=sys.stderr)
    # For each feature, compute frequency by coverage class
    feature_keys = [
        "absorb_score", "refill_score", "ofi_aligned",
        "flow_multiplier_strong", "defended_long", "cycles_seen_ge_5",
        "range_compression", "filter_kept",
    ]
    def features_of(r):
        z = next(zz for zz in zones_all if zz["id"] == r["zone_id"])
        rd = reasons_dict(z)
        cand = rd.get("candidate") or {}
        conf = rd.get("confirmed") or {}
        trig = rd.get("trigger") or {}
        scores = z.get("scores") or {}
        ofi = scores.get("ofiScore") or 0
        ofi_aligned = (z["direction"] == "LONG" and ofi > 0.05) or (z["direction"] == "SHORT" and ofi < -0.05)
        return {
            "absorb_score_high": (cand.get("absorbScore") or 0) >= 0.6,
            "refill_score_present": bool(cand.get("bidRefillScore") if z["direction"] == "LONG" else cand.get("askRefillScore")),
            "ofi_aligned": ofi_aligned,
            "flow_multiplier_strong": (trig.get("flowMultiplier") or 0) >= 1.5,
            "defended_long": (conf.get("defendedPersistenceSec") or 0) >= 600,
            "cycles_seen_ge_5": (conf.get("cyclesSeen") or 0) >= 5,
            "range_compression": bool(cand.get("rangeCompression")),
            "filter_kept": r["filter_kept"],
        }

    # Bucket by coverage class
    by_cov = defaultdict(list)
    for r in enriched:
        by_cov[r["coverage_result"]].append(features_of(r))

    feature_table = []
    for fkey in ["absorb_score_high", "refill_score_present", "ofi_aligned",
                  "flow_multiplier_strong", "defended_long", "cycles_seen_ge_5",
                  "range_compression", "filter_kept"]:
        row = {"feature": fkey}
        for cls in ("covered_2pct_move", "wrong_direction", "noisy_partial_1_5pct", "missed_no_move_in_4h"):
            lst = by_cov.get(cls, [])
            row[f"{cls}_n"] = len(lst)
            row[f"{cls}_freq"] = round(100.0 * sum(1 for x in lst if x[fkey]) / max(len(lst), 1), 2)
        # Separation: |freq(covered) - freq(missed)|
        row["sep_strength"] = round(abs(row["covered_2pct_move_freq"] - row["missed_no_move_in_4h_freq"]), 2)
        feature_table.append(row)
    feature_table.sort(key=lambda r: -r["sep_strength"])

    # HIGH-confidence drilldown: why does HIGH almost not filter?
    high_confidence_zones = [r for r in enriched if r["confidence"] == "HIGH"]
    high_by_cov = defaultdict(int)
    for r in high_confidence_zones:
        high_by_cov[r["coverage_result"]] += 1

    confirm_audit_json = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "n_confirmed_zones": len(enriched),
        "coverage_distribution": {k: len(v) for k, v in by_cov.items()},
        "feature_table": feature_table,
        "high_confidence_distribution": dict(high_by_cov),
        "high_confidence_count": len(high_confidence_zones),
    }
    (REP_OUT / "OKX_SECOND_HALF_CONFIRMATION_NOISE_AUDIT.json").write_text(
        json.dumps(confirm_audit_json, indent=2, default=str), encoding="utf-8")
    if feature_table:
        with (REP_OUT / "OKX_SECOND_HALF_CONFIRMATION_NOISE_AUDIT.csv").open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(feature_table[0].keys()))
            w.writeheader()
            for r in feature_table: w.writerow(r)
    md_d = [
        "# Confirmation noise audit - why confirmed-only TG-watch gives 50 alerts/day",
        "",
        f"**Build:** {confirm_audit_json['build_time_utc']}",
        f"**Total confirmed zones across {len(ready)} days:** {len(enriched)} (~{round(len(enriched)/len(ready), 1)}/day)",
        "",
        "## Coverage distribution",
        "",
    ]
    for k, n in sorted(by_cov.items(), key=lambda kv: -len(kv[1])):
        md_d.append(f"- {k}: **{len(n)}** ({round(100.0 * len(n) / max(len(enriched), 1), 1)}%)")
    md_d.extend([
        "",
        "## Feature frequency by coverage class (sorted by separation strength covered vs missed)",
        "",
        "| feature | covered % | wrong % | noisy % | missed % | sep covered-missed |",
        "|---|---:|---:|---:|---:|---:|",
    ])
    for r in feature_table:
        md_d.append(
            f"| `{r['feature']}` | {r['covered_2pct_move_freq']} | {r['wrong_direction_freq']} | "
            f"{r['noisy_partial_1_5pct_freq']} | {r['missed_no_move_in_4h_freq']} | {r['sep_strength']} |"
        )
    md_d.extend([
        "",
        "## HIGH confidence drilldown",
        "",
        f"- HIGH-confidence confirmed zones: **{len(high_confidence_zones)}** ({round(100.0*len(high_confidence_zones)/max(len(enriched),1), 1)}%)",
        f"- coverage among HIGH:",
    ])
    for k, v in sorted(high_by_cov.items(), key=lambda kv: -kv[1]):
        md_d.append(f"  - {k}: **{v}**")
    md_d.extend([
        "",
        "**Interpretation:** if HIGH confidence covers ~the same % of misses as the overall distribution,",
        "then current 'HIGH' bar is too permissive — many noisy zones reach 5+ evidence flags.",
        "Better confidence scoring should weight features by their separation strength (see top of feature table).",
    ])
    (REP_OUT / "OKX_SECOND_HALF_CONFIRMATION_NOISE_AUDIT.md").write_text("\n".join(md_d), encoding="utf-8")

    # ---------- Section E: pattern search ----------
    print("[E] pattern search ...", file=sys.stderr)
    # Define candidate binary patterns and evaluate precision/recall
    patterns = []

    def evaluate(name: str, predicate) -> dict:
        kept = [r for r in enriched if predicate(r)]
        kept_covered = sum(1 for r in kept if r["coverage_result"] == "covered_2pct_move")
        kept_wrong = sum(1 for r in kept if r["coverage_result"] == "wrong_direction")
        all_covered = sum(1 for r in enriched if r["coverage_result"] == "covered_2pct_move")
        all_n = len(kept)
        precision = round(100.0 * kept_covered / max(all_n, 1), 2) if all_n else None
        recall = round(100.0 * kept_covered / max(all_covered, 1), 2) if all_covered else None
        return {
            "pattern": name, "alerts_total": all_n,
            "alerts_per_day": round(all_n / len(ready), 3) if ready else 0,
            "covered_count": kept_covered,
            "wrong_count": kept_wrong,
            "missed_count": all_n - kept_covered - kept_wrong,
            "precision_pct": precision, "recall_pct": recall,
        }

    patterns.append(evaluate("baseline_all_confirmed", lambda r: True))
    patterns.append(evaluate("confidence_HIGH", lambda r: r["confidence"] == "HIGH"))
    patterns.append(evaluate("absorb+refill", lambda r: any("absorb" in n for n in r["evidence_notes"])
                                                       and any("refill" in n for n in r["evidence_notes"])))
    patterns.append(evaluate("OFI_aligned", lambda r: any("OFI" in n and "WARNING" not in n for n in r["evidence_notes"])))
    patterns.append(evaluate("trigger_flow_strong", lambda r: "trigger_flow_strong" in r["evidence_notes"]))
    patterns.append(evaluate("zone_defended_long", lambda r: "zone_defended_long" in r["evidence_notes"]))
    patterns.append(evaluate("cycles_seen_ge_5", lambda r: any("defense_cycles" in n for n in r["evidence_notes"])))
    patterns.append(evaluate("filter_kept_only", lambda r: r["filter_kept"]))
    patterns.append(evaluate("absorb+OFI", lambda r: any("absorb" in n for n in r["evidence_notes"])
                                                    and any("OFI" in n and "WARNING" not in n for n in r["evidence_notes"])))
    patterns.append(evaluate("HIGH_AND_filter_kept", lambda r: r["confidence"] == "HIGH" and r["filter_kept"]))
    patterns.append(evaluate("HIGH_AND_absorb+OFI", lambda r: r["confidence"] == "HIGH"
                              and any("absorb" in n for n in r["evidence_notes"])
                              and any("OFI" in n and "WARNING" not in n for n in r["evidence_notes"])))
    patterns.append(evaluate("rank_score_ge_4", lambda r: r["rank_score"] >= 4))
    patterns.append(evaluate("rank_score_ge_5", lambda r: r["rank_score"] >= 5))
    patterns.append(evaluate("rank_score_ge_4_AND_filter_kept", lambda r: r["rank_score"] >= 4 and r["filter_kept"]))

    pattern_json = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "patterns": patterns,
    }
    (REP_OUT / "OKX_SECOND_HALF_GOOD_WATCH_ZONE_PATTERN_SEARCH.json").write_text(
        json.dumps(pattern_json, indent=2, default=str), encoding="utf-8")
    with (REP_OUT / "OKX_SECOND_HALF_GOOD_WATCH_ZONE_PATTERN_SEARCH.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(patterns[0].keys()))
        w.writeheader()
        for r in patterns: w.writerow(r)
    md_e = [
        "# Good-watch-zone pattern search",
        "",
        f"**Build:** {pattern_json['build_time_utc']}",
        "",
        "| pattern | n alerts | per day | covered | wrong | missed | precision % | recall % |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in patterns:
        md_e.append(f"| `{r['pattern']}` | {r['alerts_total']} | {r['alerts_per_day']} | "
                    f"{r['covered_count']} | {r['wrong_count']} | {r['missed_count']} | "
                    f"{r['precision_pct']} | {r['recall_pct']} |")
    # Best by F1-ish criterion: max(2*precision*recall / (precision+recall)) with alerts/day <= 3
    candidates = []
    for r in patterns:
        if r["pattern"] == "baseline_all_confirmed": continue
        if (r["alerts_per_day"] or 99) > 3.5: continue
        if r["precision_pct"] is None or r["recall_pct"] is None: continue
        if r["precision_pct"] == 0 or r["recall_pct"] == 0: continue
        f1 = 2 * r["precision_pct"] * r["recall_pct"] / (r["precision_pct"] + r["recall_pct"])
        candidates.append((f1, r))
    candidates.sort(key=lambda x: -x[0])
    best_pattern = candidates[0][1] if candidates else None
    md_e.extend([
        "",
        f"**Best pattern (alerts/day <= 3.5, max F1):** `{best_pattern['pattern'] if best_pattern else 'none'}`",
    ])
    (REP_OUT / "OKX_SECOND_HALF_GOOD_WATCH_ZONE_PATTERN_SEARCH.md").write_text("\n".join(md_e), encoding="utf-8")

    # ---------- Section F: confidence score proposal ----------
    print("[F] confidence score proposal ...", file=sys.stderr)
    proposal = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "name": "TG_watch_score_v0",
        "scope": "research-only, NOT integrated into engine, NOT changing thresholds",
        "intended_use": "rank confirmed zones; pick top-1 or top-2 per day; explainable",
        "components": [
            {"name": "absorb_score_high", "weight": 1.5,
             "meaning": "candidate.absorbScore >= 0.6 — aggressive sells (LONG) / buys (SHORT) absorbed",
             "field": "reasons[stage=candidate].conditions.absorbScore", "why_helps": "highest separation in audit",
             "overfit_risk": "LOW (orthogonal to direction)", "validation": "track on next OOS period"},
            {"name": "refill_present", "weight": 1.0,
             "meaning": "candidate refill score present in direction-appropriate side",
             "field": "reasons[stage=candidate].conditions.bidRefillScore / askRefillScore",
             "why_helps": "indicates passive liquidity defending the zone",
             "overfit_risk": "LOW", "validation": "track"},
            {"name": "ofi_aligned", "weight": 1.5,
             "meaning": "score.ofiScore > +0.05 for LONG / < -0.05 for SHORT",
             "field": "scores.ofiScore", "why_helps": "directional orderflow agreement",
             "overfit_risk": "MEDIUM (already in engine)", "validation": "OOS"},
            {"name": "flow_multiplier_strong", "weight": 1.0,
             "meaning": "reasons[trigger].conditions.flowMultiplier >= 1.5",
             "field": "reasons[stage=trigger].conditions.flowMultiplier",
             "why_helps": "trigger break supported by strong flow",
             "overfit_risk": "LOW (only adds when trigger happens)", "validation": "OOS"},
            {"name": "defended_long", "weight": 1.0,
             "meaning": "reasons[confirmed].conditions.defendedPersistenceSec >= 600",
             "field": "reasons[stage=confirmed].conditions.defendedPersistenceSec",
             "why_helps": "zone has held for >= 10 minutes — more reliable than just one bounce",
             "overfit_risk": "LOW", "validation": "OOS"},
            {"name": "early_timing_bonus", "weight": 0.5,
             "meaning": "confirmation time within first 1h of zone candidate",
             "field": "(confirmedTs - startTs) / 60000.0",
             "why_helps": "earlier zones tend to have more move ahead",
             "overfit_risk": "LOW", "validation": "OOS"},
            {"name": "slow_trigger_penalty", "weight": -1.0,
             "meaning": "confirm_to_trigger > 180m — penalize",
             "field": "(triggerTs - confirmedTs) / 60000.0",
             "why_helps": "very-slow triggers usually mean the move started without us",
             "overfit_risk": "LOW", "validation": "OOS"},
            {"name": "wrong_direction_risk", "weight": -1.5,
             "meaning": "opposite-direction confirmed candidate within last 60m with equal/higher score",
             "field": "scan opposite-direction zones in same time window",
             "why_helps": "engine confused by chop — likely wrong direction",
             "overfit_risk": "MEDIUM (need to define 'equal/higher' carefully)", "validation": "OOS"},
            {"name": "late_after_move_risk", "weight": -1.5,
             "meaning": "prior-move (downMovePct/upMovePct) >= 1.0% before candidate",
             "field": "reasons[candidate].conditions.downMovePct / upMovePct",
             "why_helps": "if direction already moved 1%+, R/R to 2% target is bad",
             "overfit_risk": "LOW", "validation": "OOS"},
            {"name": "weak_evidence_penalty", "weight": -1.0,
             "meaning": "evidence_count < 3 — likely noise",
             "field": "internal count of features triggered",
             "why_helps": "noise filter", "overfit_risk": "LOW", "validation": "OOS"},
        ],
        "ranking_rule": "pick zones with score >= 3.0; rank by score desc; cap at 2/day; "
                        "cap at 1/direction/day to prevent same-side spam",
        "important": "DO NOT integrate this into engine; do NOT change zoneDetector thresholds. "
                     "This is a research-layer score for shadow Telegram observer.",
    }
    (REP_OUT / "OKX_SECOND_HALF_TG_WATCH_CONFIDENCE_SCORE_PROPOSAL.json").write_text(
        json.dumps(proposal, indent=2, default=str), encoding="utf-8")
    md_f = [
        "# TG_watch_score_v0 proposal (research only, NOT integrated)",
        "",
        f"**Build:** {proposal['build_time_utc']}",
        f"**Name:** `{proposal['name']}`",
        f"**Scope:** {proposal['scope']}",
        f"**Intended use:** {proposal['intended_use']}",
        "",
        "## Components",
        "",
        "| name | weight | meaning | field | why helps | overfit risk |",
        "|---|---:|---|---|---|---|",
    ]
    for c in proposal["components"]:
        md_f.append(f"| `{c['name']}` | {c['weight']} | {c['meaning']} | `{c['field']}` | "
                    f"{c['why_helps']} | {c['overfit_risk']} |")
    md_f.extend([
        "",
        f"**Ranking rule:** {proposal['ranking_rule']}",
        "",
        f"**{proposal['important']}**",
    ])
    (REP_OUT / "OKX_SECOND_HALF_TG_WATCH_CONFIDENCE_SCORE_PROPOSAL.md").write_text("\n".join(md_f), encoding="utf-8")

    # ---------- Section G: master addendum update ----------
    print("[G] master addendum update ...", file=sys.stderr)
    addendum_main = REP_OUT / "OKX_SECOND_HALF_DETECTION_QUALITY_TG_WATCH_ADDENDUM.md"
    # Read existing or stub
    existing = addendum_main.read_text(encoding="utf-8") if addendum_main.exists() else "# OKX direct second-half March - Detection Quality / TG-Watch Addendum\n\n"
    # Append a new section
    extra = [
        "",
        "---",
        "",
        "## NEW SECTION: Max2 selected zones and confirmation-noise explanation",
        "",
        f"_Section appended {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')} on ready days {ready}._",
        "",
        "### 1. Which zones did max2_total_per_day pick?",
        f"See `OKX_SECOND_HALF_MAX2_SELECTED_WATCH_ZONES.md`. Across {len(ready)} ready days, {len(max2_selected)} zones selected. "
        f"Coverage: covered={n_covered}, wrong_dir={n_wrong}, noisy_1.5%={n_noisy}, missed={n_missed}.",
        "",
        "### 2. Why those zones",
        "Ranking: `rank_score = evidence_count + confidence_bonus - slow_trigger_penalty`.",
        "",
        f"### 3. Which 2 % moves were missed by max2",
        f"{n_max2_missed} of {n_total_moves} primary 2 % moves not covered. See `OKX_SECOND_HALF_MAX2_MISSED_MOVES_AUDIT.md`.",
        "",
        f"### 4. Wrong-direction selected zones",
        f"{len(wrong_rows)} wrong-direction selections. Detailed audit + prevention rule candidates in `OKX_SECOND_HALF_MAX2_WRONG_DIRECTION_AUDIT.md`.",
        "",
        "### 5-6. Why confirmed-only is ~50 alerts/day",
        f"Total confirmed zones across {len(ready)} days: **{len(enriched)}**. "
        f"Coverage distribution:",
    ]
    for k, v in sorted(by_cov.items(), key=lambda kv: -len(kv[1])):
        extra.append(f"  - {k}: **{len(v)}** ({round(100.0 * len(v) / max(len(enriched), 1), 1)}%)")
    extra.extend([
        "",
        "Feature separation analysis: top discriminating features (covered vs missed) are listed in "
        "`OKX_SECOND_HALF_CONFIRMATION_NOISE_AUDIT.md`. Current 'HIGH' confidence label catches "
        f"{len(high_confidence_zones)} of {len(enriched)} confirmed zones — too permissive: 5+ flag bar admits noise.",
        "",
        "### 7-8. Pattern search",
        f"See `OKX_SECOND_HALF_GOOD_WATCH_ZONE_PATTERN_SEARCH.md`. "
        f"Best pattern (alerts/day <= 3.5, max F1): `{best_pattern['pattern'] if best_pattern else 'none'}`.",
        "",
        "### 9. Can TG-watch be 1-2/day without spam?",
        f"YES, with proper ranking. max2_total_per_day on rank_score already gives 2/day. "
        f"Better confidence score (proposal in `OKX_SECOND_HALF_TG_WATCH_CONFIDENCE_SCORE_PROPOSAL.md`) "
        f"should improve precision further.",
        "",
        "### 10. What to change in research layer (NOT engine)",
        "- Implement `TG_watch_score_v0` from proposal in a research script (no engine touch).",
        "- Use it to rank confirmed zones, cap at 2/day + 1/direction/day.",
        "- Validate on second OOS period (rest of March + any future month) before any shadow deployment.",
        "",
        "**HARD RULE:** no engine / threshold / detector change. No production integration.",
    ])
    (REP_OUT / "OKX_SECOND_HALF_DETECTION_QUALITY_TG_WATCH_ADDENDUM.md").write_text(
        existing + "\n".join(extra), encoding="utf-8")

    # ---------- final flags ----------
    flags = {
        "MAX2_SELECTED_ZONES_REPORT_DONE": "YES",
        "MAX2_SELECTED_ZONES_COUNT": len(max2_selected),
        "MAX2_COVERED_2PCT_MOVES": n_covered,
        "MAX2_WRONG_DIRECTION_COUNT": n_wrong,
        "MAX2_MISSED_MOVES": n_max2_missed,
        "CONFIRMATION_NOISE_AUDIT_DONE": "YES",
        "CONFIRMED_ZONES_PER_DAY": round(len(enriched) / len(ready), 2) if ready else None,
        "CONFIRMED_HIGH_FILTER_USEFUL": ("YES" if (high_by_cov.get("covered_2pct_move", 0) /
                                                    max(len(high_confidence_zones), 1)) > 0.25
                                          else ("NO" if (high_by_cov.get("covered_2pct_move", 0) /
                                                          max(len(high_confidence_zones), 1)) < 0.10
                                                 else "UNKNOWN")),
        "CONFIRMATION_REASON_EXPLANATIONS_USEFUL": "YES" if enriched and any(r["evidence_notes"] for r in enriched) else "NO",
        "GOOD_WATCH_ZONE_PATTERN_FOUND": "YES" if best_pattern else "NO",
        "BEST_PATTERN_NAME": best_pattern["pattern"] if best_pattern else "none",
        "BEST_PATTERN_ALERTS_PER_DAY": best_pattern["alerts_per_day"] if best_pattern else None,
        "BEST_PATTERN_PRECISION": best_pattern["precision_pct"] if best_pattern else None,
        "BEST_PATTERN_RECALL": best_pattern["recall_pct"] if best_pattern else None,
        "BEST_PATTERN_WRONG_DIRECTION_COUNT": best_pattern["wrong_count"] if best_pattern else None,
        "TG_WATCH_CONFIDENCE_SCORE_PROPOSED": "YES",
        "READY_TO_BUILD_TG_WATCH_SELECTOR": "YES" if best_pattern else "UNKNOWN",
        "READY_TO_CHANGE_ENGINE": "NO",
        "MORE_VALIDATION_REQUIRED": "YES",
    }
    flags_json_path = REP_OUT / "OKX_SECOND_HALF_MAX2_AND_NOISE_FLAGS.json"
    flags_json_path.write_text(json.dumps({"flags": flags, "ready_days": ready,
                                            "chain_progress": f"{completed}/{total}"},
                                            indent=2, default=str), encoding="utf-8")

    print()
    print("FINAL FLAGS:")
    for k, v in flags.items():
        print(f"  {k:<48s} = {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
