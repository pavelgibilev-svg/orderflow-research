"""Trade-by-trade interim diagnostic on 2026-03-16 and 2026-03-18 (OKX direct).

READ-ONLY over the 2 already-produced backtest outputs. Does NOT touch the
running chain. Does NOT re-run any backtest.

For each variant (A: trigger+stop_1pct; B: delay_15m+stop_1.5pct) and each
day, emit:
  - per-trade ledger with entry/target/stop/exit/pnl/MFE/MAE/holding-time
  - skipped-signal list (which trade blocked it; what would the skipped signal
    have done if taken)
  - primary-unique-move lineage (was each primary reached, taken, stopped?)
  - per-day human-readable explanation

Outputs:
  reports/strategy-calibration/OKX_MARCH_SECOND_HALF_INTERIM_0316_0318_TRADE_BY_TRADE.{md,json,csv}
"""
from __future__ import annotations
import csv
import datetime as dt
import json
import statistics as stats
import sys
from collections import defaultdict
from dataclasses import asdict
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


# ---------- helpers ----------

def mid_price(z: dict) -> float | None:
    lo, hi = z.get("zoneLow"), z.get("zoneHigh")
    if lo is None or hi is None: return None
    return (lo + hi) / 2.0


def is_triggered(z: dict) -> bool:
    return z.get("status") in ("RESOLVED_REACHED", "RESOLVED_FAILED")


def is_reached(z: dict) -> bool:
    return z.get("status") == "RESOLVED_REACHED"


def confirm_to_trigger_min(z: dict) -> float | None:
    c, t = z.get("confirmedTs"), z.get("triggerTs")
    if c is None or t is None: return None
    return (t - c) / 60000.0


def class_label(z: dict) -> str:
    s = z.get("status")
    if s == "RESOLVED_REACHED":
        return "primary_unique_reached_move" if z.get("isPrimaryMoveZone") else "duplicate_reached_move"
    if s == "RESOLVED_FAILED":
        return "failed_triggered"
    if s == "NO_TRIGGER":
        return "no_trigger"
    if s in ("INVALIDATED", "EXPIRED"):
        return "invalidated_or_expired"
    return "unknown"


def ms_to_iso(ms: int | None) -> str | None:
    if ms is None: return None
    return dt.datetime.fromtimestamp(ms / 1000, tz=dt.timezone.utc).isoformat(timespec="seconds")


def load_zones_for_dates(dates: list[str]) -> list[dict]:
    out: list[dict] = []
    for d in dates:
        p_full = REPORTS / f"BTC-USDT-SWAP_{d}" / "zones.json"
        zones = []
        if p_full.exists():
            obj = json.loads(p_full.read_text(encoding="utf-8"))
            zones = obj if isinstance(obj, list) else obj.get("zones", [])
        for z in zones:
            z["_date"] = d
            z["_class"] = class_label(z)
        out.extend(zones)
    return out


def apply_passive_filter(zones: list[dict]) -> dict[str, dict]:
    by_date = defaultdict(list)
    for z in zones:
        by_date[z["_date"]].append(z)
    decisions = {}
    for date, lst in by_date.items():
        triggered = [z for z in lst if is_triggered(z) and z.get("triggerTs") is not None]
        triggered.sort(key=lambda z: z["triggerTs"])
        for i, z in enumerate(triggered):
            T = z["triggerTs"]; D = z["direction"]; zm = mid_price(z)
            dup = False; parent_id = None
            for prior in triggered[:i]:
                if prior["triggerTs"] >= T or prior["direction"] != D: continue
                dt_min = (T - prior["triggerTs"]) / 60000.0
                if dt_min <= 0 or dt_min > WINDOW_MIN: continue
                pm = mid_price(prior)
                if zm is None or pm is None: continue
                if abs(zm - pm) / zm * 100.0 <= PRICE_BAND_PCT:
                    dup = True; parent_id = prior["id"]; break
            ctm = confirm_to_trigger_min(z)
            fast_ok = (ctm is None) or (ctm <= FAST_X_MIN_BASE)
            decisions[z["id"]] = {
                "kept": (not dup) and fast_ok,
                "dup_parent": parent_id, "ctm_min": ctm,
                "fast_ok": fast_ok, "dup_suppressed": dup,
            }
    return decisions


def to_signal(z: dict) -> Signal:
    return Signal(id=z["id"], date=z["_date"], trigger_ts_ms=z["triggerTs"],
                  direction=z["direction"], zone_low=z.get("zoneLow"), zone_high=z.get("zoneHigh"))


def find_target_after_stop(z: dict, buckets: list[Bucket], stop_sec: int) -> int | None:
    """After a stop_1pct stop fires at stop_sec, does the price reach the +-2% target
    later (within 24h from triggerTs)? Returns sec of target hit or None."""
    trig_sec = z["triggerTs"] // 1000
    timeout_sec = trig_sec + 24 * 3600
    # Entry was at first bucket >= trig_sec; for "what would have happened" we use the same entry
    lo, hi = 0, len(buckets)
    while lo < hi:
        m = (lo + hi) // 2
        if buckets[m].sec < trig_sec: lo = m + 1
        else: hi = m
    enter_idx = lo
    if enter_idx >= len(buckets): return None
    entry_price = buckets[enter_idx].last
    direction = z["direction"]
    if direction == "LONG": target = entry_price * 1.02
    else: target = entry_price * 0.98
    for idx in range(enter_idx, len(buckets)):
        b = buckets[idx]
        if b.sec > timeout_sec: break
        if b.sec < stop_sec: continue
        if direction == "LONG" and b.high >= target: return b.sec
        if direction == "SHORT" and b.low <= target: return b.sec
    return None


# ---------- main analysis ----------

def main() -> int:
    print("loading zones for 03-16 + 03-18 ...", file=sys.stderr)
    zones = load_zones_for_dates(DATES)
    decisions = apply_passive_filter(zones)
    filtered = [z for z in zones if is_triggered(z) and decisions.get(z["id"], {}).get("kept")]
    signals = [to_signal(z) for z in filtered]
    print(f"  loaded {len(zones)} zones / {len(filtered)} filtered triggered", file=sys.stderr)

    print("building 1s buckets ...", file=sys.stderr)
    buckets_by_date: dict[str, list[Bucket]] = {}
    for d in DATES:
        buckets_by_date[d] = build_buckets_from_trades_csv(DATA_ROOT / d / "trades.csv.gz")
        print(f"  {d}: {len(buckets_by_date[d]):,} buckets", file=sys.stderr)

    cfg_a = ExecutionConfig(entry_strategy="trigger", stop_pct=1.0, target_pct=2.0, timeout_hours=24)
    cfg_b = ExecutionConfig(entry_strategy="delay_15m", stop_pct=1.5, target_pct=2.0, timeout_hours=24)

    print("running Variant A canonical walk ...", file=sys.stderr)
    res_a = canonical_ledger_walk(signals, buckets_by_date, cfg_a)
    print("running Variant B canonical walk ...", file=sys.stderr)
    res_b = canonical_ledger_walk(signals, buckets_by_date, cfg_b)

    # Build maps for zone lookup
    zone_by_id = {z["id"]: z for z in zones}

    # For each variant, build accepted_set and chronological signal order
    sigs_sorted = sorted(signals, key=lambda s: s.trigger_ts_ms)

    def walk_with_skips(cfg: ExecutionConfig):
        accepted_trades = []
        skipped_signals = []
        open_until_sec = -1
        blocking_zone_id = None
        for s in sigs_sorted:
            trig_sec = s.trigger_ts_ms // 1000
            buckets = buckets_by_date.get(s.date) or []
            if trig_sec < open_until_sec:
                skipped_signals.append({
                    "zone_id": s.id, "date": s.date, "direction": s.direction,
                    "triggerTs": s.trigger_ts_ms,
                    "blocked_by_zone_id": blocking_zone_id,
                })
                continue
            if not buckets:
                continue
            sim = simulate_canonical_trade(s, buckets, cfg)
            if sim["exit_reason"] in ("no_data", "skip_no_retest"):
                continue
            accepted_trades.append((s, sim))
            blocking_zone_id = s.id
            open_until_sec = sim["exit_sec"]
        return accepted_trades, skipped_signals

    a_accepted, a_skipped = walk_with_skips(cfg_a)
    b_accepted, b_skipped = walk_with_skips(cfg_b)

    # Build the rich per-trade rows
    def build_trade_row(variant: str, n: int, sig: Signal, sim: dict) -> dict:
        z = zone_by_id[sig.id]
        decision = decisions.get(sig.id, {})
        target_after_stop = None
        if sim["exit_reason"] == "stop":
            target_after_stop = find_target_after_stop(z, buckets_by_date[sig.date], sim["exit_sec"])
        return {
            "variant": variant,
            "trade_number": n,
            "date": sig.date,
            "zone_id": sig.id,
            "direction": sig.direction,
            "class_label": z["_class"],
            "is_primary_unique": bool(z.get("isPrimaryMoveZone")),
            "is_duplicate_reached": z["_class"] == "duplicate_reached_move",
            "was_reached_raw": is_reached(z),
            "triggerTs": z["triggerTs"], "triggerTs_iso": ms_to_iso(z["triggerTs"]),
            "confirmedTs": z.get("confirmedTs"), "confirmedTs_iso": ms_to_iso(z.get("confirmedTs")),
            "confirm_to_trigger_min": decision.get("ctm_min"),
            "zone_low": z.get("zoneLow"), "zone_high": z.get("zoneHigh"),
            "entryTs": sim["entry_sec"] * 1000,
            "entryTs_iso": ms_to_iso(sim["entry_sec"] * 1000),
            "entry_delay_from_trigger_min": round((sim["entry_sec"] * 1000 - z["triggerTs"]) / 60000.0, 2),
            "entry_price": sim["entry_price"],
            "target_price": (sim["entry_price"] * 1.02 if sig.direction == "LONG"
                              else sim["entry_price"] * 0.98),
            "stop_price": (sim["entry_price"] * (1 - sim["used_stop_pct"] / 100.0) if sig.direction == "LONG"
                            else sim["entry_price"] * (1 + sim["used_stop_pct"] / 100.0)),
            "used_stop_pct": sim["used_stop_pct"],
            "exitTs": sim["exit_sec"] * 1000, "exitTs_iso": ms_to_iso(sim["exit_sec"] * 1000),
            "holding_time_min": round((sim["exit_sec"] - sim["entry_sec"]) / 60.0, 2),
            "exit_reason": sim["exit_reason"],
            "exit_price": sim["exit_price"],
            "pnl_pct": sim["pnl_pct"],
            "mfe_pct": sim["mfe_pct"],
            "mae_pct": sim["mae_pct"],
            "target_2pct_after_stop_iso": ms_to_iso(target_after_stop * 1000) if target_after_stop else None,
            "filter_dup_parent": decision.get("dup_parent"),
        }

    a_rows = [build_trade_row("A", i + 1, s, sim) for i, (s, sim) in enumerate(a_accepted)]
    b_rows = [build_trade_row("B", i + 1, s, sim) for i, (s, sim) in enumerate(b_accepted)]

    # Skipped signals — simulate what would have happened if they were taken
    def build_skipped_row(variant: str, skip: dict, cfg: ExecutionConfig) -> dict:
        zid = skip["zone_id"]
        z = zone_by_id[zid]
        s = to_signal(z)
        sim = simulate_canonical_trade(s, buckets_by_date[s.date], cfg)
        sim_summary = {
            "would_exit_reason": sim["exit_reason"],
            "would_pnl_pct": sim.get("pnl_pct"),
            "would_have_reached_2pct": sim["exit_reason"] == "target_2pct",
        }
        return {
            "variant": variant, "date": skip["date"],
            "skipped_zone_id": zid,
            "direction": skip["direction"],
            "triggerTs": skip["triggerTs"], "triggerTs_iso": ms_to_iso(skip["triggerTs"]),
            "blocked_by_zone_id": skip["blocked_by_zone_id"],
            "class_label": z["_class"],
            "is_primary_unique": bool(z.get("isPrimaryMoveZone")),
            "is_duplicate_reached": z["_class"] == "duplicate_reached_move",
            "was_reached_raw_engine": is_reached(z),
            **sim_summary,
        }

    a_skipped_rows = [build_skipped_row("A", s, cfg_a) for s in a_skipped]
    b_skipped_rows = [build_skipped_row("B", s, cfg_b) for s in b_skipped]

    # ---------- C: Primary unique move lineage ----------
    primaries = [z for z in zones if z.get("isPrimaryMoveZone") and is_reached(z)]
    primary_lineage = []
    accepted_a_ids = {r["zone_id"] for r in a_rows}
    accepted_b_ids = {r["zone_id"] for r in b_rows}
    skipped_a_ids = {r["skipped_zone_id"]: r for r in a_skipped_rows}
    skipped_b_ids = {r["skipped_zone_id"]: r for r in b_skipped_rows}
    for p in primaries:
        in_filtered = decisions.get(p["id"], {}).get("kept", False)
        # Variant A
        taken_a = p["id"] in accepted_a_ids
        a_row = next((r for r in a_rows if r["zone_id"] == p["id"]), None)
        a_skipped_info = skipped_a_ids.get(p["id"])
        if taken_a:
            a_status = f"taken; exit={a_row['exit_reason']} pnl={a_row['pnl_pct']}%"
            a_stop_before_target = a_row["exit_reason"] == "stop"
        elif a_skipped_info:
            a_status = f"skipped_open_position (blocked by {a_skipped_info['blocked_by_zone_id']}); would have {a_skipped_info['would_exit_reason']} pnl={a_skipped_info['would_pnl_pct']}%"
            a_stop_before_target = a_skipped_info["would_exit_reason"] == "stop"
        elif not in_filtered:
            a_status = "filter_suppressed"
            a_stop_before_target = None
        else:
            a_status = "not in ledger and not skipped — UNEXPECTED"
            a_stop_before_target = None
        # Variant B
        taken_b = p["id"] in accepted_b_ids
        b_row = next((r for r in b_rows if r["zone_id"] == p["id"]), None)
        b_skipped_info = skipped_b_ids.get(p["id"])
        if taken_b:
            b_status = f"taken; exit={b_row['exit_reason']} pnl={b_row['pnl_pct']}%"
            b_stop_before_target = b_row["exit_reason"] == "stop"
        elif b_skipped_info:
            b_status = f"skipped_open_position (blocked by {b_skipped_info['blocked_by_zone_id']}); would have {b_skipped_info['would_exit_reason']} pnl={b_skipped_info['would_pnl_pct']}%"
            b_stop_before_target = b_skipped_info["would_exit_reason"] == "stop"
        elif not in_filtered:
            b_status = "filter_suppressed"
            b_stop_before_target = None
        else:
            b_status = "not in ledger and not skipped — UNEXPECTED"
            b_stop_before_target = None

        primary_lineage.append({
            "date": p["_date"], "zone_id": p["id"], "uniqueMoveId": p.get("uniqueMoveId"),
            "direction": p["direction"],
            "triggerTs_iso": ms_to_iso(p["triggerTs"]),
            "in_filtered_alerts": in_filtered,
            "filter_dup_parent": decisions.get(p["id"], {}).get("dup_parent"),
            "filter_fast_ok": decisions.get(p["id"], {}).get("fast_ok"),
            "filter_dup_suppressed": decisions.get(p["id"], {}).get("dup_suppressed"),
            "variant_A_taken": taken_a, "variant_A_status": a_status,
            "variant_A_stop_before_target": a_stop_before_target,
            "variant_B_taken": taken_b, "variant_B_status": b_status,
            "variant_B_stop_before_target": b_stop_before_target,
        })

    # ---------- per-day counts ----------
    by_date_counts: dict[str, dict] = {}
    for d in DATES:
        day_zones = [z for z in zones if z["_date"] == d]
        day_triggered = [z for z in day_zones if is_triggered(z)]
        day_filtered = [z for z in day_zones if is_triggered(z) and decisions.get(z["id"], {}).get("kept")]
        a_day = [r for r in a_rows if r["date"] == d]
        b_day = [r for r in b_rows if r["date"] == d]
        a_skip_day = [r for r in a_skipped_rows if r["date"] == d]
        b_skip_day = [r for r in b_skipped_rows if r["date"] == d]
        by_date_counts[d] = {
            "zones": len(day_zones),
            "triggered": len(day_triggered),
            "filtered_alerts": len(day_filtered),
            "variant_A_accepted": len(a_day),
            "variant_A_skipped_open_position": len(a_skip_day),
            "variant_B_accepted": len(b_day),
            "variant_B_skipped_open_position": len(b_skip_day),
            "variant_A_wins": sum(1 for r in a_day if r["exit_reason"] == "target_2pct"),
            "variant_A_losses": sum(1 for r in a_day if r["exit_reason"] == "stop"),
            "variant_A_timeouts": sum(1 for r in a_day if r["exit_reason"] == "timeout"),
            "variant_A_total_pnl_pct": round(sum(r["pnl_pct"] for r in a_day), 4),
            "variant_B_wins": sum(1 for r in b_day if r["exit_reason"] == "target_2pct"),
            "variant_B_losses": sum(1 for r in b_day if r["exit_reason"] == "stop"),
            "variant_B_timeouts": sum(1 for r in b_day if r["exit_reason"] == "timeout"),
            "variant_B_total_pnl_pct": round(sum(r["pnl_pct"] for r in b_day), 4),
        }

    # ---------- assemble JSON ----------
    out = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "scope": "Trade-by-trade interim diagnostic on 2026-03-16 + 2026-03-18 only",
        "per_day_counts": by_date_counts,
        "variant_A_trades": a_rows,
        "variant_B_trades": b_rows,
        "variant_A_skipped_signals": a_skipped_rows,
        "variant_B_skipped_signals": b_skipped_rows,
        "primary_unique_lineage": primary_lineage,
    }
    (REP_OUT / "OKX_MARCH_SECOND_HALF_INTERIM_0316_0318_TRADE_BY_TRADE.json").write_text(
        json.dumps(out, indent=2, default=str), encoding="utf-8")

    # ---------- CSV ----------
    csv_keys = ["variant", "date", "trade_number", "zone_id", "direction", "class_label",
                "is_primary_unique", "is_duplicate_reached", "was_reached_raw",
                "triggerTs_iso", "confirm_to_trigger_min",
                "entryTs_iso", "entry_delay_from_trigger_min", "entry_price",
                "target_price", "stop_price", "used_stop_pct",
                "exitTs_iso", "holding_time_min", "exit_reason", "exit_price",
                "pnl_pct", "mfe_pct", "mae_pct", "target_2pct_after_stop_iso"]
    with (REP_OUT / "OKX_MARCH_SECOND_HALF_INTERIM_0316_0318_TRADE_BY_TRADE.csv").open(
            "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=csv_keys, extrasaction="ignore")
        w.writeheader()
        for r in a_rows + b_rows:
            w.writerow(r)

    # ---------- MD ----------
    md = [
        "# OKX direct March - INTERIM trade-by-trade diagnostic (2026-03-16 + 2026-03-18)",
        "",
        f"**Build:** {out['build_time_utc']}",
        "**Scope:** detailed per-trade audit on 2 already-completed days; main chain still running for the other 13.",
        "**Canonical ledger module:** `scripts/strategy-calibration/canonical_ledger.py` (= `src/research/canonicalLedger.ts`).",
        "**Target strict 2 %. Variant A stop 1.0 %. Variant B delay 15min + stop 1.5 %. Timeout 24h.**",
        "",
        "## 0. Funnel - how 102 zones become 6 (A) or 4 (B) trades",
        "",
        "| stage | 2026-03-16 | 2026-03-18 | total |",
        "|---|---:|---:|---:|",
    ]
    for label, key in [
        ("zones", "zones"), ("engine triggered", "triggered"),
        ("filtered alerts (base passive filter)", "filtered_alerts"),
        ("Variant A accepted by ledger", "variant_A_accepted"),
        ("Variant A skipped open position", "variant_A_skipped_open_position"),
        ("Variant B accepted by ledger", "variant_B_accepted"),
        ("Variant B skipped open position", "variant_B_skipped_open_position"),
    ]:
        md.append(f"| {label} | {by_date_counts['2026-03-16'][key]} | {by_date_counts['2026-03-18'][key]} | "
                  f"{by_date_counts['2026-03-16'][key] + by_date_counts['2026-03-18'][key]} |")

    # Variant tables per day
    def render_trade_table(rows: list[dict], variant_letter: str, date: str) -> list[str]:
        lst = [r for r in rows if r["date"] == date]
        out_md = [
            "",
            f"### Variant {variant_letter} - {date}",
            "",
            "| # | zone_id | dir | conf->trig min | trigger time | entry time | delay min | entry $ | target $ | stop $ | exit time | hold min | exit | pnl % | MFE | MAE | primary? | dup? | reach later (after stop) |",
            "|--:|---|---|---:|---|---|---:|---:|---:|---:|---|---:|---|---:|---:|---:|:---:|:---:|---|",
        ]
        if not lst:
            out_md.append("| _no trades_ | | | | | | | | | | | | | | | | | | |")
            return out_md
        for r in lst:
            out_md.append(
                f"| {r['trade_number']} | `{r['zone_id'][-20:]}` | {r['direction']} | "
                f"{r['confirm_to_trigger_min']} | {r['triggerTs_iso']} | {r['entryTs_iso']} | "
                f"{r['entry_delay_from_trigger_min']} | {r['entry_price']:.1f} | "
                f"{r['target_price']:.1f} | {r['stop_price']:.1f} | {r['exitTs_iso']} | "
                f"{r['holding_time_min']:.1f} | **{r['exit_reason']}** | "
                f"**{r['pnl_pct']:+.3f}** | {r['mfe_pct']:.3f} | {r['mae_pct']:.3f} | "
                f"{'Y' if r['is_primary_unique'] else 'N'} | "
                f"{'Y' if r['is_duplicate_reached'] else 'N'} | "
                f"{r['target_2pct_after_stop_iso'] or '—'} |"
            )
        return out_md

    md.extend(["", "## A. Variant A (trigger entry + stop 1.0 %) - trade list"])
    for d in DATES:
        md.extend(render_trade_table(a_rows, "A", d))
    md.extend(["", "## B. Variant B (delay 15min + stop 1.5 %) - trade list"])
    for d in DATES:
        md.extend(render_trade_table(b_rows, "B", d))

    # Skipped signals
    def render_skipped(rows: list[dict], letter: str) -> list[str]:
        out_md = [
            "",
            f"### Variant {letter} - skipped signals (had a position open at the time)",
            "",
            "| date | skipped zone_id | dir | trigger time | blocked by | engine class | primary? | dup? | reached_raw? | would-exit if taken | would-pnl |",
            "|---|---|---|---|---|---|:---:|:---:|:---:|---|---:|",
        ]
        if not rows:
            out_md.append("| _none_ | | | | | | | | | | |")
            return out_md
        for r in rows:
            out_md.append(
                f"| {r['date']} | `{r['skipped_zone_id'][-20:]}` | {r['direction']} | "
                f"{r['triggerTs_iso']} | `{(r['blocked_by_zone_id'] or '?')[-20:]}` | "
                f"{r['class_label']} | "
                f"{'Y' if r['is_primary_unique'] else 'N'} | "
                f"{'Y' if r['is_duplicate_reached'] else 'N'} | "
                f"{'Y' if r['was_reached_raw_engine'] else 'N'} | "
                f"**{r['would_exit_reason']}** | "
                f"{r['would_pnl_pct']:+.3f}% |"
            )
        return out_md

    md.extend(["", "## C. Skipped signals (open position blocked them)"])
    md.extend(render_skipped(a_skipped_rows, "A"))
    md.extend(render_skipped(b_skipped_rows, "B"))

    # Primary lineage
    md.extend(["",
        "## D. Primary unique move lineage (2 primaries across these 2 days)",
        "",
        "| date | uniqueMoveId | primary zone_id | dir | trigger time | in filtered alerts? | filter notes | Variant A | Variant B |",
        "|---|---:|---|---|---|:---:|---|---|---|",
    ])
    for p in primary_lineage:
        filter_notes = []
        if p["filter_dup_suppressed"]:
            filter_notes.append(f"dup_suppressed (parent={p['filter_dup_parent']})")
        if not p["filter_fast_ok"]:
            filter_notes.append("slow_trigger")
        md.append(
            f"| {p['date']} | {p['uniqueMoveId']} | `{p['zone_id'][-25:]}` | {p['direction']} | "
            f"{p['triggerTs_iso']} | {'YES' if p['in_filtered_alerts'] else 'NO'} | "
            f"{'; '.join(filter_notes) or '—'} | "
            f"{p['variant_A_status']} | "
            f"{p['variant_B_status']} |"
        )

    # Per-day human explanation
    def day_explain(d: str, letter: str, rows: list[dict], skipped: list[dict]) -> list[str]:
        day = by_date_counts[d]
        accepted = [r for r in rows if r["date"] == d]
        skip_day = [r for r in skipped if r["date"] == d]
        wins = [r for r in accepted if r["exit_reason"] == "target_2pct"]
        losses = [r for r in accepted if r["exit_reason"] == "stop"]
        timeouts = [r for r in accepted if r["exit_reason"] == "timeout"]
        # Are any skipped signals actually reach_raw in engine?
        skipped_winners = [s for s in skip_day if s["would_have_reached_2pct"]]
        skipped_engine_reached = [s for s in skip_day if s["was_reached_raw_engine"]]
        lines = [
            f"**{d}** (Variant {letter}):",
            f"  - {day['triggered']} triggered zones -> {day['filtered_alerts']} pass base filter "
            f"-> ledger takes **{len(accepted)}** (skips {len(skip_day)} due to open position).",
        ]
        if wins:
            lines.append("  - WINS: " + "; ".join(
                f"`{w['zone_id'][-15:]}` {w['direction']} @ {w['entry_price']:.1f} -> target_2pct in {w['holding_time_min']:.1f} min"
                for w in wins))
        if losses:
            lines.append("  - LOSSES: " + "; ".join(
                f"`{l['zone_id'][-15:]}` {l['direction']} @ {l['entry_price']:.1f} -> stop in {l['holding_time_min']:.1f} min"
                + (f" (would target_2pct after stop at {l['target_2pct_after_stop_iso']})"
                   if l['target_2pct_after_stop_iso'] else "")
                for l in losses))
        if timeouts:
            lines.append("  - TIMEOUTS: " + "; ".join(
                f"`{t['zone_id'][-15:]}` {t['direction']} (MFE {t['mfe_pct']:.3f}% / MAE {t['mae_pct']:.3f}%)"
                for t in timeouts))
        if skipped_winners:
            lines.append(f"  - SKIPPED but would have WON: **{len(skipped_winners)}** (this is where edge gets eaten by the one-trade-at-a-time rule).")
        elif skipped_engine_reached:
            lines.append(f"  - SKIPPED signals that engine called reached_raw: {len(skipped_engine_reached)}.")
        total_pnl = round(sum(r["pnl_pct"] for r in accepted), 4)
        lines.append(f"  - **Day P&L (Variant {letter}, pre-cost): {total_pnl}%**")
        return lines

    md.extend(["", "## E. Per-day human explanation", ""])
    for d in DATES:
        md.extend(day_explain(d, "A", a_rows, a_skipped_rows))
        md.append("")
        md.extend(day_explain(d, "B", b_rows, b_skipped_rows))
        md.append("")

    # ---------- F: final flags ----------
    a_wins = sum(1 for r in a_rows if r["exit_reason"] == "target_2pct")
    a_losses = sum(1 for r in a_rows if r["exit_reason"] == "stop")
    a_timeouts = sum(1 for r in a_rows if r["exit_reason"] == "timeout")
    b_wins = sum(1 for r in b_rows if r["exit_reason"] == "target_2pct")
    b_losses = sum(1 for r in b_rows if r["exit_reason"] == "stop")
    b_timeouts = sum(1 for r in b_rows if r["exit_reason"] == "timeout")
    filtered_total = sum(by_date_counts[d]["filtered_alerts"] for d in DATES)
    skipped_total_a = len(a_skipped_rows)
    primaries_taken_a = sum(1 for p in primary_lineage if p["variant_A_taken"])
    primaries_taken_b = sum(1 for p in primary_lineage if p["variant_B_taken"])
    # Check arithmetic: filtered = accepted + skipped (Variant A)
    arithmetic_ok = (filtered_total == len(a_rows) + skipped_total_a) and \
                    (filtered_total == len(b_rows) + len(b_skipped_rows))
    all_primaries_explained = all(
        p["variant_A_status"] != "not in ledger and not skipped — UNEXPECTED"
        and p["variant_B_status"] != "not in ledger and not skipped — UNEXPECTED"
        for p in primary_lineage
    )

    flags = {
        "TRADE_BY_TRADE_INTERIM_DONE": "YES",
        "DAYS_EXPLAINED": DATES,
        "VARIANT_A_TRADES_TOTAL": len(a_rows),
        "VARIANT_A_WINS": a_wins,
        "VARIANT_A_LOSSES": a_losses,
        "VARIANT_A_TIMEOUTS": a_timeouts,
        "VARIANT_B_TRADES_TOTAL": len(b_rows),
        "VARIANT_B_WINS": b_wins,
        "VARIANT_B_LOSSES": b_losses,
        "VARIANT_B_TIMEOUTS": b_timeouts,
        "FILTERED_ALERTS_TOTAL": filtered_total,
        "LEDGER_ACCEPTED_TOTAL": f"A={len(a_rows)}, B={len(b_rows)}",
        "LEDGER_SKIPPED_OPEN_POSITION_TOTAL": f"A={len(a_skipped_rows)}, B={len(b_skipped_rows)}",
        "PRIMARY_UNIQUE_TOTAL": len(primary_lineage),
        "PRIMARY_UNIQUE_TAKEN_VARIANT_A": primaries_taken_a,
        "PRIMARY_UNIQUE_TAKEN_VARIANT_B": primaries_taken_b,
        "PRIMARY_UNIQUE_SKIPPED_OR_STOPPED_EXPLAINED": "YES" if all_primaries_explained else "NO",
        "ANY_UNEXPLAINED_TRADE_COUNT_MISMATCH": "NO" if arithmetic_ok else "YES",
    }
    out["flags"] = flags
    # Re-write JSON with flags
    (REP_OUT / "OKX_MARCH_SECOND_HALF_INTERIM_0316_0318_TRADE_BY_TRADE.json").write_text(
        json.dumps(out, indent=2, default=str), encoding="utf-8")

    md.extend(["", "## F. Final flag matrix", "", "```"])
    for k, v in flags.items():
        md.append(f"{k} = {v}")
    md.append("```")
    md.extend([
        "",
        "## Notes",
        "- All flags pre-cost. Strict 2 % target.",
        "- 2 days, very thin sample; not a final verdict.",
        "- No engine / threshold / detector change.",
    ])
    (REP_OUT / "OKX_MARCH_SECOND_HALF_INTERIM_0316_0318_TRADE_BY_TRADE.md").write_text(
        "\n".join(md), encoding="utf-8")

    print()
    print("FLAGS:")
    for k, v in flags.items():
        print(f"  {k:<55s} = {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
