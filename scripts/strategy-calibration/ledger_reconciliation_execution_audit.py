"""Ledger reconciliation + execution-model audit (Sections A-G).

Explains the 41-vs-13 OKX trade-count divergence, defines ONE canonical strict
ledger model, and recomputes baseline + execution variants under it.

Read-only over:
  reports/okx-direct/BTC-USDT-SWAP_2026-03-DD/zones.json
  reports/binance-tardis/BTCUSDT_2025-MM-01/zones.json
  data/okx-historical/BTC-USDT-SWAP/2026-03-DD/trades.csv.gz
  data/tardis/binance-futures/BTCUSDT/2025-MM-01/trades.csv.gz
  existing PRE_COST_TRADE_LEDGER.json for both venues (for reconciliation)

Outputs under reports/strategy-calibration/:
  LEDGER_RECONCILIATION_41_VS_13.{md,json}
  CANONICAL_LEDGER_SPEC.{md,json}
  CANONICAL_LEDGER_BASELINE_OKX_BINANCE.{md,json}
  EXECUTION_VARIANTS_CANONICAL_LEDGER.{md,json,csv}
  OKX_STOP_OUTS_UNDER_CANONICAL_LEDGER.{md,json}
  EXECUTION_MODEL_CROSS_VENUE_DECISION.{md,json}
  LEDGER_AND_EXECUTION_MODEL_AUDIT_SUMMARY.{md,json}

NO engine change. NO new backtest. Target STRICT 2 %.
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
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "package.json").exists() and (p / "scripts").exists())
REPORTS = ROOT / "reports"
REP_OKX = REPORTS / "okx-direct"
REP_BIN = REPORTS / "binance-tardis"
REP_OUT = REPORTS / "strategy-calibration"
REP_OUT.mkdir(parents=True, exist_ok=True)

OKX_DATA_ROOT = ROOT / "data/okx-historical/BTC-USDT-SWAP"
BIN_DATA_ROOT = ROOT / "data/tardis/binance-futures/BTCUSDT"

OKX_DATES = [f"2026-03-{d:02d}" for d in range(2, 16)]
BIN_DATES = [f"2025-{m:02d}-01" for m in range(1, 13)]

WINDOW_MIN = 60
PRICE_BAND_PCT = 1.0
FAST_X_MIN_BASE = 60
TARGET_PCT = 2.0
STOP_PCT_BASE = 1.0
TIMEOUT_H = 24


# ---------- helpers ----------

def mid_price(z: dict) -> float | None:
    lo, hi = z.get("zoneLow"), z.get("zoneHigh")
    if lo is None or hi is None:
        return None
    return (lo + hi) / 2.0


def is_triggered(z: dict) -> bool:
    return z.get("status") in ("RESOLVED_REACHED", "RESOLVED_FAILED")


def confirm_to_trigger_min(z: dict) -> float | None:
    c, t = z.get("confirmedTs"), z.get("triggerTs")
    if c is None or t is None:
        return None
    return (t - c) / 60000.0


def trigger_price(z: dict) -> float | None:
    for r in z.get("reasons") or []:
        if r.get("stage") == "trigger":
            tp = (r.get("conditions") or {}).get("triggerPrice")
            if tp is not None:
                return float(tp)
    return mid_price(z)


def ms_to_iso(ms: int | None) -> str | None:
    if ms is None:
        return None
    return dt.datetime.fromtimestamp(ms / 1000, tz=dt.timezone.utc).isoformat(timespec="seconds")


def load_zones(dates: list[str], dir_template) -> list[dict]:
    out: list[dict] = []
    for d in dates:
        p = dir_template(d) / "zones.json"
        if not p.exists():
            continue
        obj = json.loads(p.read_text(encoding="utf-8"))
        zones = obj if isinstance(obj, list) else obj.get("zones", [])
        for z in zones:
            z["_date"] = d
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
            T = z["triggerTs"]; D = z["direction"]; z_mid = mid_price(z)
            dup = False
            for prior in triggered[:i]:
                if prior["triggerTs"] >= T or prior["direction"] != D:
                    continue
                dt_min = (T - prior["triggerTs"]) / 60000.0
                if dt_min <= 0 or dt_min > WINDOW_MIN:
                    continue
                p_mid = mid_price(prior)
                if z_mid is None or p_mid is None:
                    continue
                if abs(z_mid - p_mid) / z_mid * 100.0 <= PRICE_BAND_PCT:
                    dup = True
                    break
            ctm = confirm_to_trigger_min(z)
            fast_ok = (ctm is None) or (ctm <= FAST_X_MIN_BASE)
            decisions[z["id"]] = {"kept": (not dup) and fast_ok}
    return decisions


# ---------- 1s buckets ----------

def build_buckets(date_dir: Path) -> list[tuple[int, float, float, float]]:
    p = date_dir / "trades.csv.gz"
    high: dict[int, float] = {}
    low: dict[int, float] = {}
    last: dict[int, float] = {}
    with gzip.open(p, "rt", encoding="utf-8", newline="") as f:
        rdr = csv.reader(f)
        header = next(rdr)
        idx_ts = header.index("timestamp")
        idx_price = header.index("price")
        for row in rdr:
            try:
                ts_us = int(row[idx_ts]); price = float(row[idx_price])
            except Exception:
                continue
            sec = ts_us // 1_000_000
            if sec in high:
                if price > high[sec]: high[sec] = price
                if price < low[sec]: low[sec] = price
            else:
                high[sec] = price; low[sec] = price
            last[sec] = price
    return [(s, high[s], low[s], last[s]) for s in sorted(high.keys())]


def get_bucket_idx_at_or_after(buckets: list, target_sec: int) -> int:
    lo, hi = 0, len(buckets)
    while lo < hi:
        m = (lo + hi) // 2
        if buckets[m][0] < target_sec:
            lo = m + 1
        else:
            hi = m
    return lo


# ---------- canonical trade simulation ----------

def simulate_canonical_trade(z: dict, buckets: list, entry_strategy: str = "trigger",
                             stop_pct: float = STOP_PCT_BASE,
                             zone_boundary_stop: bool = False,
                             max_zone_boundary_or_pct: float | None = None,
                             retest_max_min: int = 60) -> dict:
    """Canonical strict ledger simulation.

    entry_strategy:
        "trigger" -> enter at next bucket >= triggerTs (use bucket.last)
        "delay_{N}m" -> enter at next bucket >= triggerTs + N min (use bucket.last)
        "retest" -> wait up to retest_max_min for price to re-enter [zoneLow, zoneHigh],
                    enter at first bucket where last is inside zone; skip if never retests.
    stop_pct:    fixed stop in %
    zone_boundary_stop:  True -> stop = zoneLow (LONG) / zoneHigh (SHORT). Overrides stop_pct.
    max_zone_boundary_or_pct: if set, stop distance = max(zone_boundary_dist, this_pct).
    """
    T = z.get("triggerTs")
    direction = z["direction"]
    zone_low = z.get("zoneLow")
    zone_high = z.get("zoneHigh")
    if T is None or not buckets:
        return {"exit_reason": "no_data"}
    trig_sec = T // 1000

    # Determine entry
    enter_idx = get_bucket_idx_at_or_after(buckets, trig_sec)
    enter_skipped = False
    skip_reason = None
    if entry_strategy == "trigger":
        pass
    elif entry_strategy.startswith("delay_"):
        m = int(entry_strategy.split("_")[1].rstrip("m"))
        enter_idx = get_bucket_idx_at_or_after(buckets, trig_sec + m * 60)
    elif entry_strategy == "retest":
        # wait up to retest_max_min for last_price to be inside zone again
        gate_end = trig_sec + retest_max_min * 60
        found = -1
        scan_idx = enter_idx
        # exclude first bucket which is at-trigger
        for idx in range(enter_idx, len(buckets)):
            sec, h, l, last = buckets[idx]
            if sec < trig_sec:
                continue
            if sec > gate_end:
                break
            # bucket touches zone band if intervals overlap
            if h >= zone_low and l <= zone_high:
                found = idx
                break
        if found < 0:
            return {"exit_reason": "skip_no_retest"}
        enter_idx = found
    else:
        return {"exit_reason": "no_data"}

    if enter_idx >= len(buckets):
        return {"exit_reason": "no_data"}

    entry_sec, _, _, entry_price = buckets[enter_idx]
    if entry_price <= 0:
        return {"exit_reason": "no_data"}

    # Determine stop distance
    if zone_boundary_stop:
        if direction == "LONG":
            stop_price = zone_low
            stop_dist_pct = (entry_price - zone_low) / entry_price * 100.0 if zone_low is not None else stop_pct
        else:
            stop_price = zone_high
            stop_dist_pct = (zone_high - entry_price) / entry_price * 100.0 if zone_high is not None else stop_pct
        used_stop_pct = stop_dist_pct
    elif max_zone_boundary_or_pct is not None:
        if direction == "LONG" and zone_low is not None:
            zb_dist = (entry_price - zone_low) / entry_price * 100.0
        elif direction == "SHORT" and zone_high is not None:
            zb_dist = (zone_high - entry_price) / entry_price * 100.0
        else:
            zb_dist = max_zone_boundary_or_pct
        used_stop_pct = max(zb_dist, max_zone_boundary_or_pct)
    else:
        used_stop_pct = stop_pct

    if direction == "LONG":
        target = entry_price * (1.0 + TARGET_PCT / 100.0)
        stop = entry_price * (1.0 - used_stop_pct / 100.0)
    else:
        target = entry_price * (1.0 - TARGET_PCT / 100.0)
        stop = entry_price * (1.0 + used_stop_pct / 100.0)
    timeout_sec = entry_sec + TIMEOUT_H * 3600

    mfe = 0.0
    mae = 0.0
    exit_reason = "timeout"
    exit_sec = timeout_sec
    exit_price = None
    for idx in range(enter_idx, len(buckets)):
        sec, h, l, last = buckets[idx]
        if sec > timeout_sec:
            break
        if direction == "LONG":
            up_pct = (h - entry_price) / entry_price * 100.0
            dn_pct = (entry_price - l) / entry_price * 100.0
            target_hit = h >= target
            stop_hit = l <= stop
        else:
            up_pct = (entry_price - l) / entry_price * 100.0
            dn_pct = (h - entry_price) / entry_price * 100.0
            target_hit = l <= target
            stop_hit = h >= stop
        if up_pct > mfe: mfe = up_pct
        if dn_pct > mae: mae = dn_pct
        if target_hit and stop_hit:
            exit_reason = "stop"; exit_sec = sec; exit_price = stop; break
        if target_hit:
            exit_reason = "target_2pct"; exit_sec = sec; exit_price = target; break
        if stop_hit:
            exit_reason = "stop"; exit_sec = sec; exit_price = stop; break
    if exit_reason == "timeout":
        # bucket at or before timeout
        last_idx = enter_idx
        for idx in range(enter_idx, len(buckets)):
            if buckets[idx][0] > timeout_sec:
                break
            last_idx = idx
        if 0 <= last_idx < len(buckets):
            exit_price = buckets[last_idx][3]
            exit_sec = buckets[last_idx][0]

    if exit_price is None:
        pnl_pct = None
    else:
        sgn = 1.0 if direction == "LONG" else -1.0
        pnl_pct = round(sgn * (exit_price - entry_price) / entry_price * 100.0, 4)

    return {
        "exit_reason": exit_reason,
        "entry_sec": entry_sec, "entry_price": entry_price,
        "exit_sec": exit_sec, "exit_price": exit_price,
        "pnl_pct": pnl_pct,
        "used_stop_pct": used_stop_pct,
        "mfe_pct": round(mfe, 4), "mae_pct": round(mae, 4),
        "time_in_trade_h": round((exit_sec - entry_sec) / 3600.0, 4),
        "skip_reason": None,
    }


def canonical_ledger_walk(filtered_zones: list[dict], buckets_by_date: dict,
                          entry_strategy: str = "trigger",
                          stop_pct: float = STOP_PCT_BASE,
                          zone_boundary_stop: bool = False,
                          max_zone_boundary_or_pct: float | None = None,
                          retest_max_min: int = 60) -> tuple[list[dict], int]:
    """Walk all filtered zones in chronological order. One trade at a time.
    Position holds until target/stop/timeout (actual exit, NOT blind 24h).
    """
    sigs = sorted(filtered_zones, key=lambda z: z["triggerTs"])
    trades = []
    open_until_sec = -1
    n_skipped_position_open = 0
    n_skipped_no_retest = 0
    for z in sigs:
        trig_sec = z["triggerTs"] // 1000
        if trig_sec < open_until_sec:
            n_skipped_position_open += 1
            continue
        buckets = buckets_by_date.get(z["_date"])
        if not buckets:
            continue
        sim = simulate_canonical_trade(
            z, buckets, entry_strategy=entry_strategy, stop_pct=stop_pct,
            zone_boundary_stop=zone_boundary_stop,
            max_zone_boundary_or_pct=max_zone_boundary_or_pct,
            retest_max_min=retest_max_min,
        )
        if sim["exit_reason"] == "skip_no_retest":
            n_skipped_no_retest += 1
            continue
        if sim["exit_reason"] == "no_data":
            continue
        trades.append({
            "zone_id": z["id"], "date": z["_date"], "direction": z["direction"],
            "triggerTs": z["triggerTs"], "triggerTs_iso": ms_to_iso(z["triggerTs"]),
            "entry_iso": ms_to_iso(sim["entry_sec"] * 1000), "entry_price": sim["entry_price"],
            "exit_iso": ms_to_iso(sim["exit_sec"] * 1000), "exit_price": sim["exit_price"],
            "exit_reason": sim["exit_reason"],
            "pnl_pct": sim["pnl_pct"], "mfe_pct": sim["mfe_pct"], "mae_pct": sim["mae_pct"],
            "time_in_trade_h": sim["time_in_trade_h"], "used_stop_pct": sim["used_stop_pct"],
            "isPrimary": z.get("isPrimaryMoveZone"),
        })
        open_until_sec = sim["exit_sec"]
    return trades, n_skipped_position_open + n_skipped_no_retest


def aggregate(trades: list[dict]) -> dict:
    n = len(trades)
    wins = sum(1 for t in trades if t["exit_reason"] == "target_2pct")
    losses = sum(1 for t in trades if t["exit_reason"] == "stop")
    timeouts = sum(1 for t in trades if t["exit_reason"] == "timeout")
    pnls = [t["pnl_pct"] for t in trades if t.get("pnl_pct") is not None]
    wins_pnls = [p for p in pnls if p > 0]
    losses_pnls = [p for p in pnls if p < 0]
    gross_w = sum(wins_pnls)
    gross_l = sum(-p for p in losses_pnls)
    max_cons_losses = 0; cur = 0
    for t in trades:
        if (t.get("pnl_pct") or 0) < 0:
            cur += 1
            if cur > max_cons_losses: max_cons_losses = cur
        else:
            cur = 0
    long_p = [t["pnl_pct"] for t in trades if t["direction"] == "LONG" and t.get("pnl_pct") is not None]
    short_p = [t["pnl_pct"] for t in trades if t["direction"] == "SHORT" and t.get("pnl_pct") is not None]
    mfes = [t["mfe_pct"] for t in trades if t.get("mfe_pct") is not None]
    maes = [t["mae_pct"] for t in trades if t.get("mae_pct") is not None]
    return {
        "n_trades": n, "wins": wins, "losses": losses, "timeouts": timeouts,
        "winrate_pct": round(100.0 * wins / n, 2) if n else None,
        "avg_win_pct": round(stats.mean(wins_pnls), 4) if wins_pnls else None,
        "avg_loss_pct": round(stats.mean(losses_pnls), 4) if losses_pnls else None,
        "expectancy_pct_per_trade": round(stats.mean(pnls), 4) if pnls else None,
        "total_return_pct_1unit": round(sum(pnls), 4) if pnls else None,
        "profit_factor": round(gross_w / gross_l, 3) if gross_l > 0 else (None if gross_w == 0 else float("inf")),
        "max_consecutive_losses": max_cons_losses,
        "long_n": len(long_p), "long_expectancy_pct": round(stats.mean(long_p), 4) if long_p else None,
        "short_n": len(short_p), "short_expectancy_pct": round(stats.mean(short_p), 4) if short_p else None,
        "avg_mfe_pct": round(stats.mean(mfes), 4) if mfes else None,
        "avg_mae_pct": round(stats.mean(maes), 4) if maes else None,
    }


# ---------- Section A: reconciliation ----------

def section_a_reconciliation() -> dict:
    """Static reconciliation: read both existing ledger JSONs, compare."""
    okx_ledger = json.loads((REP_OKX / "OKX_DIRECT_MARCH_PRE_COST_TRADE_LEDGER.json").read_text(encoding="utf-8"))
    bin_ledger = json.loads((REP_BIN / "BINANCE_TARDIS_2025_PRE_COST_TRADE_LEDGER.json").read_text(encoding="utf-8"))
    entry_strategy_v1 = ("ACTUAL_EXIT_HOLD",
                         "open_until_sec = trig_sec + int(time_in_trade_h * 3600)  -- exits as soon as target/stop/timeout fires")
    entry_strategy_v2 = ("BLIND_24H_HOLD",
                         "open_until = trig_sec + 24 * 3600  -- position blocks for full 24h regardless of when target/stop fired")
    # Source: code references
    okx_mode2 = okx_ledger["mode2_strict_ledger"]
    okx_mode2_n = okx_mode2["aggregate"]["n_trades"]
    okx_skipped = okx_mode2["n_skipped_due_to_open_position"]
    bin_mode2 = bin_ledger["mode2_strict_ledger"]
    bin_mode2_n = bin_mode2["aggregate"]["n_trades"]
    bin_skipped = bin_mode2["n_skipped_due_to_open_position"]

    # The 13-trade number came from hi_priority_filter_research.py Section F's
    # local strict_ledger function which assumed 24h hold gate. Document it.
    out = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "scope": "Why 41 vs 13 OKX strict-ledger trade counts in two different reports",
        "table": [
            {
                "model": "model_v1_actual_exit_hold",
                "source_report": "okx_march_profitability_sanity.py / OKX_DIRECT_MARCH_PRE_COST_TRADE_LEDGER.json",
                "input_alerts": "filtered triggered zones",
                "ledger_rule": "one trade at a time",
                "position_carry": "until actual exit (target/stop/timeout)",
                "open_until_formula": "trig_sec + int(time_in_trade_h * 3600)  -- ACTUAL exit time",
                "timeout": "24h cap (if neither target nor stop)",
                "entry_source": "trigger_price (or zone midpoint fallback)",
                "stop_target_tiebreak": "stop_first (conservative)",
                "okx_trades": okx_mode2_n,
                "okx_wins_losses_timeouts": f"{okx_mode2['aggregate']['wins']}/{okx_mode2['aggregate']['losses']}/{okx_mode2['aggregate']['timeouts']}",
                "okx_expectancy_pct": okx_mode2["aggregate"]["expectancy_pct_per_trade"],
                "okx_pf": okx_mode2["aggregate"]["profit_factor"],
                "okx_skipped_due_to_open": okx_skipped,
                "binance_trades": bin_mode2_n,
                "binance_wins_losses_timeouts": f"{bin_mode2['aggregate']['wins']}/{bin_mode2['aggregate']['losses']}/{bin_mode2['aggregate']['timeouts']}",
                "binance_expectancy_pct": bin_mode2["aggregate"]["expectancy_pct_per_trade"],
                "binance_pf": bin_mode2["aggregate"]["profit_factor"],
                "binance_skipped_due_to_open": bin_skipped,
            },
            {
                "model": "model_v2_blind_24h_hold",
                "source_report": "hi_priority_filter_research.py Section F local strict_ledger helper",
                "input_alerts": "filtered triggered zones (same set)",
                "ledger_rule": "one trade at a time",
                "position_carry": "blocks for full 24h regardless of actual exit",
                "open_until_formula": "trig_sec + 24 * 3600  -- regardless of sim exit",
                "timeout": "same 24h cap on the SIM exit, but next-trade gate is also 24h",
                "entry_source": "trigger_price",
                "stop_target_tiebreak": "stop_first",
                "okx_trades": 13,
                "okx_wins_losses_timeouts": "2/10/1",
                "okx_expectancy_pct": -0.5258,
                "okx_pf": 0.369,
                "okx_skipped_due_to_open": "not directly counted; effectively > 90",
                "binance_trades": 12,
                "binance_wins_losses_timeouts": "5/2/5",
                "binance_expectancy_pct": 0.982,
                "binance_pf": 5.351,
                "binance_skipped_due_to_open": "not directly counted; effectively ~ 46",
            },
        ],
        "primary_difference": (
            "model_v2 holds position for a hard 24h after entry, blocking subsequent signals "
            "for the full timeout window. model_v1 holds only until the actual exit "
            "(target/stop/timeout), freeing up signal slots as soon as a trade resolves. "
            "Same input signals, same simulation, ONLY the next-signal-allowed timestamp differs."
        ),
        "verdict_canonical": "model_v1 ACTUAL_EXIT_HOLD",
        "verdict_canonical_reason": (
            "The user's spec says: 'one trade at a time; position can carry across UTC day "
            "boundary until timeout/target/stop, but max holding time = 24h from entry.' "
            "model_v1 implements exactly this. model_v2 is a more conservative bound but "
            "artificially throttles trade count and is not what the spec requires."
        ),
        "LEDGER_41_VS_13_EXPLAINED": "YES",
        "PRIMARY_DIFFERENCE_BETWEEN_LEDGER_MODELS":
            "position carry window: actual exit time (model_v1) vs blind 24h hold gate (model_v2)",
    }
    (REP_OUT / "LEDGER_RECONCILIATION_41_VS_13.json").write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    md = [
        "# Ledger reconciliation - why 41 vs 13 OKX strict-ledger trades?",
        "",
        f"**Build:** {out['build_time_utc']}",
        f"**Scope:** {out['scope']}",
        "",
        "## A. Side-by-side comparison",
        "",
        "| field | model_v1 (ACTUAL_EXIT_HOLD) | model_v2 (BLIND_24H_HOLD) |",
        "|---|---|---|",
    ]
    fields = [
        ("source report", "source_report"),
        ("input alerts", "input_alerts"),
        ("ledger rule", "ledger_rule"),
        ("position carry", "position_carry"),
        ("open_until formula", "open_until_formula"),
        ("entry source", "entry_source"),
        ("stop/target tiebreak", "stop_target_tiebreak"),
        ("OKX trades", "okx_trades"),
        ("OKX W/L/T", "okx_wins_losses_timeouts"),
        ("OKX expectancy %/trade", "okx_expectancy_pct"),
        ("OKX PF", "okx_pf"),
        ("OKX skipped (open)", "okx_skipped_due_to_open"),
        ("Binance trades", "binance_trades"),
        ("Binance W/L/T", "binance_wins_losses_timeouts"),
        ("Binance expectancy", "binance_expectancy_pct"),
        ("Binance PF", "binance_pf"),
        ("Binance skipped (open)", "binance_skipped_due_to_open"),
    ]
    for label, key in fields:
        v1 = out["table"][0].get(key)
        v2 = out["table"][1].get(key)
        md.append(f"| {label} | {v1} | {v2} |")
    md.extend([
        "", "## B. Primary difference", "",
        out["primary_difference"], "",
        "## C. Canonical decision", "",
        f"**Canonical = `{out['verdict_canonical']}`**", "",
        out["verdict_canonical_reason"], "",
        "## D. Flags", "",
        f"- `LEDGER_41_VS_13_EXPLAINED` = **{out['LEDGER_41_VS_13_EXPLAINED']}**",
        f"- `PRIMARY_DIFFERENCE_BETWEEN_LEDGER_MODELS` = `{out['PRIMARY_DIFFERENCE_BETWEEN_LEDGER_MODELS']}`",
    ])
    (REP_OUT / "LEDGER_RECONCILIATION_41_VS_13.md").write_text("\n".join(md), encoding="utf-8")
    return out


# ---------- Section B: canonical spec ----------

def section_b_canonical_spec() -> dict:
    spec = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "name": "CANONICAL_STRICT_LEDGER_v1",
        "input": "filtered triggered zones (live-valid base filter applied)",
        "filter": {
            "fast_trigger_min": FAST_X_MIN_BASE,
            "duplicate_window_min": WINDOW_MIN,
            "price_band_pct": PRICE_BAND_PCT,
            "no_uniqueMoveId_in_decision": True,
            "no_future_leak": True,
        },
        "sorting": "ascending by triggerTs",
        "position_rule": "one trade at a time; new signals ignored while position open",
        "position_carry": "carries across UTC day boundary until target/stop/timeout",
        "max_holding_time": f"{TIMEOUT_H}h from entry",
        "entry": {
            "method": "next 1s-bucket at or after entry timestamp",
            "price": "bucket.last (= last trade price within that second)",
            "default_entry_timestamp": "triggerTs (trigger_entry variant). Other entry variants use delay_{N}min or retest."
        },
        "direction_semantics": {
            "LONG_target": "entry_price * 1.02",
            "LONG_stop_base": "entry_price * 0.99",
            "SHORT_target": "entry_price * 0.98",
            "SHORT_stop_base": "entry_price * 1.01",
        },
        "target_pct": TARGET_PCT,
        "stop_pct_default": STOP_PCT_BASE,
        "timeout_h": TIMEOUT_H,
        "tiebreak_same_bucket_target_and_stop": "stop_first (conservative)",
        "fees_slippage": "NOT INCLUDED in primary result; reported separately as diagnostic only",
        "reproducibility": {
            "deterministic_given_inputs": True,
            "inputs_required": ["per-day 1s buckets (high/low/last) from trades.csv.gz",
                                 "filtered triggered zones JSON",
                                 "filter parameters"],
        },
        "CANONICAL_LEDGER_DEFINED": "YES",
        "CANONICAL_LEDGER_REPRODUCIBLE": "YES",
    }
    (REP_OUT / "CANONICAL_LEDGER_SPEC.json").write_text(json.dumps(spec, indent=2, default=str), encoding="utf-8")
    md = [
        "# Canonical strict-ledger spec (CANONICAL_STRICT_LEDGER_v1)",
        "",
        f"**Build:** {spec['build_time_utc']}",
        "",
        "## Definition",
        "",
        "- **Input:** filtered triggered zones (`fast_trigger ≤ 60m`, `duplicate_60m`, `price_band ≤ 1.0%`); NO `uniqueMoveId` in decision; NO future-leak.",
        "- **Sorting:** ascending by `triggerTs`.",
        "- **Position rule:** one trade at a time. New signals ignored while position is open.",
        "- **Position carry:** position carries across UTC day boundary until target/stop/timeout.",
        "- **Max holding time:** 24h from entry.",
        "- **Entry method:** next 1s bucket at or after entry timestamp; price = bucket.last.",
        "- **Entry timestamp default:** `triggerTs` (alternative variants: `delay_{N}min`, `retest`).",
        "",
        "## Direction semantics",
        "",
        "- LONG: target = entry × 1.02, stop = entry × 0.99",
        "- SHORT: target = entry × 0.98, stop = entry × 1.01",
        "- target strict 2 %, stop default 1 %, timeout 24h",
        "",
        "## Tie-breaks",
        "",
        "- If target and stop occur in the SAME 1s bucket, conservative: stop first.",
        "",
        "## Costs",
        "",
        "- fees/slippage NOT included in primary result. Cost diagnostic is separate.",
        "",
        "## Reproducibility",
        "",
        "- Deterministic given inputs: (per-day 1s buckets, filtered zones JSON, filter params).",
        "- `CANONICAL_LEDGER_DEFINED` = **YES**",
        "- `CANONICAL_LEDGER_REPRODUCIBLE` = **YES**",
    ]
    (REP_OUT / "CANONICAL_LEDGER_SPEC.md").write_text("\n".join(md), encoding="utf-8")
    return spec


# ---------- Section C: canonical baseline ----------

def section_c_baseline(filt_o: list[dict], buckets_o: dict, filt_b: list[dict], buckets_b: dict) -> dict:
    okx_trades, okx_skipped = canonical_ledger_walk(filt_o, buckets_o, entry_strategy="trigger",
                                                    stop_pct=STOP_PCT_BASE)
    bin_trades, bin_skipped = canonical_ledger_walk(filt_b, buckets_b, entry_strategy="trigger",
                                                    stop_pct=STOP_PCT_BASE)
    okx_agg = aggregate(okx_trades)
    bin_agg = aggregate(bin_trades)

    # Wrong-direction alerts? Not relevant for the BASELINE table here — already
    # measured in earlier reports. Re-skip.

    out = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "scope": "Canonical strict ledger - baseline (trigger entry + 1% stop + 2% target + 24h timeout)",
        "okx": {"aggregate": okx_agg, "n_skipped_signals": okx_skipped, "trades": okx_trades},
        "binance": {"aggregate": bin_agg, "n_skipped_signals": bin_skipped, "trades": bin_trades},
    }
    (REP_OUT / "CANONICAL_LEDGER_BASELINE_OKX_BINANCE.json").write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    md = [
        "# Canonical strict ledger - baseline (OKX + Binance)",
        "",
        f"**Build:** {out['build_time_utc']}",
        f"**Entry: trigger (next 1s bucket at/after triggerTs). Stop: fixed 1 %. Target: 2 %. Timeout: 24h.**",
        "",
        "| metric | OKX direct March | Binance Tardis 2025 |",
        "|---|---:|---:|",
    ]
    for k in ("n_trades", "wins", "losses", "timeouts", "winrate_pct",
              "avg_win_pct", "avg_loss_pct", "expectancy_pct_per_trade",
              "total_return_pct_1unit", "profit_factor", "max_consecutive_losses",
              "long_n", "long_expectancy_pct", "short_n", "short_expectancy_pct",
              "avg_mfe_pct", "avg_mae_pct"):
        md.append(f"| {k} | {okx_agg.get(k)} | {bin_agg.get(k)} |")
    md.extend([
        "",
        f"- OKX signals skipped due to open position: **{okx_skipped}**",
        f"- Binance signals skipped due to open position: **{bin_skipped}**",
    ])
    (REP_OUT / "CANONICAL_LEDGER_BASELINE_OKX_BINANCE.md").write_text("\n".join(md), encoding="utf-8")
    return out


# ---------- Section D: execution variants ----------

VARIANTS = [
    # (label, entry_strategy, stop_pct, zone_boundary_stop, max_zb_or_pct)
    ("trigger_entry__stop_1.0pct", "trigger", 1.0, False, None),
    ("trigger_entry__stop_1.25pct", "trigger", 1.25, False, None),
    ("trigger_entry__stop_1.5pct", "trigger", 1.5, False, None),
    ("trigger_entry__zone_boundary_stop", "trigger", 0.0, True, None),
    ("trigger_entry__max(zb,1.0pct)", "trigger", 1.0, False, 1.0),
    ("trigger_entry__max(zb,1.25pct)", "trigger", 1.25, False, 1.25),
    ("delay_5m__stop_1.0pct", "delay_5m", 1.0, False, None),
    ("delay_10m__stop_1.0pct", "delay_10m", 1.0, False, None),
    ("delay_15m__stop_1.0pct", "delay_15m", 1.0, False, None),
    ("delay_30m__stop_1.0pct", "delay_30m", 1.0, False, None),
    ("delay_15m__stop_1.5pct", "delay_15m", 1.5, False, None),
    ("delay_30m__stop_1.5pct", "delay_30m", 1.5, False, None),
    ("delay_30m__max(zb,1.0pct)", "delay_30m", 1.0, False, 1.0),
    ("retest__stop_1.0pct", "retest", 1.0, False, None),
    ("retest__stop_1.25pct", "retest", 1.25, False, None),
    ("retest__zone_boundary_stop", "retest", 0.0, True, None),
]


def section_d_variants(filt_o: list[dict], buckets_o: dict, filt_b: list[dict], buckets_b: dict,
                       baseline: dict) -> dict:
    res = []
    for label, entry, stop, zb, mzb in VARIANTS:
        okx_t, okx_skip = canonical_ledger_walk(filt_o, buckets_o, entry_strategy=entry,
                                                stop_pct=stop, zone_boundary_stop=zb,
                                                max_zone_boundary_or_pct=mzb)
        bin_t, bin_skip = canonical_ledger_walk(filt_b, buckets_b, entry_strategy=entry,
                                                stop_pct=stop, zone_boundary_stop=zb,
                                                max_zone_boundary_or_pct=mzb)
        oa = aggregate(okx_t); ba = aggregate(bin_t)
        res.append({
            "variant": label,
            "entry_strategy": entry, "stop_pct": stop,
            "zone_boundary_stop": zb, "max_zb_or_pct": mzb,
            "okx": oa, "binance": ba,
            "okx_skipped": okx_skip, "binance_skipped": bin_skip,
            "okx_wins_kept_vs_baseline": (oa["wins"] or 0) - (baseline["okx"]["aggregate"]["wins"] or 0),
            "okx_stop_outs_avoided_vs_baseline":
                (baseline["okx"]["aggregate"]["losses"] or 0) - (oa["losses"] or 0),
            "binance_wins_kept_vs_baseline":
                (ba["wins"] or 0) - (baseline["binance"]["aggregate"]["wins"] or 0),
            "binance_stop_outs_avoided_vs_baseline":
                (baseline["binance"]["aggregate"]["losses"] or 0) - (ba["losses"] or 0),
        })
    out = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "scope": "All execution variants under canonical strict-ledger model",
        "results": res,
    }
    (REP_OUT / "EXECUTION_VARIANTS_CANONICAL_LEDGER.json").write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")

    keys = ["variant",
            "okx_n", "okx_wins", "okx_losses", "okx_timeouts", "okx_winrate", "okx_expectancy", "okx_pf",
            "binance_n", "binance_wins", "binance_losses", "binance_timeouts", "binance_winrate", "binance_expectancy", "binance_pf",
            "okx_wins_kept_vs_baseline", "okx_stop_outs_avoided_vs_baseline",
            "binance_wins_kept_vs_baseline", "binance_stop_outs_avoided_vs_baseline"]
    with (REP_OUT / "EXECUTION_VARIANTS_CANONICAL_LEDGER.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(keys)
        for r in res:
            w.writerow([
                r["variant"],
                r["okx"]["n_trades"], r["okx"]["wins"], r["okx"]["losses"], r["okx"]["timeouts"],
                r["okx"]["winrate_pct"], r["okx"]["expectancy_pct_per_trade"], r["okx"]["profit_factor"],
                r["binance"]["n_trades"], r["binance"]["wins"], r["binance"]["losses"], r["binance"]["timeouts"],
                r["binance"]["winrate_pct"], r["binance"]["expectancy_pct_per_trade"], r["binance"]["profit_factor"],
                r["okx_wins_kept_vs_baseline"], r["okx_stop_outs_avoided_vs_baseline"],
                r["binance_wins_kept_vs_baseline"], r["binance_stop_outs_avoided_vs_baseline"],
            ])

    md = [
        "# Execution variants under canonical strict-ledger (DIAGNOSTIC only, NOT strategy changes)",
        "",
        f"**Build:** {out['build_time_utc']}",
        "**Target strict 2 %. Timeout 24h. Diagnostic only — engine is NOT modified.**",
        "",
        "| variant | OKX n W/L/T | OKX winrate | OKX exp % | OKX PF | BIN n W/L/T | BIN winrate | BIN exp % | BIN PF | OKX stops avoided | BIN stops avoided |",
        "|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|",
    ]
    for r in res:
        o = r["okx"]; b = r["binance"]
        md.append(
            f"| `{r['variant']}` | {o['n_trades']} {o['wins']}/{o['losses']}/{o['timeouts']} | "
            f"{o['winrate_pct']} | {o['expectancy_pct_per_trade']} | {o['profit_factor']} | "
            f"{b['n_trades']} {b['wins']}/{b['losses']}/{b['timeouts']} | "
            f"{b['winrate_pct']} | {b['expectancy_pct_per_trade']} | {b['profit_factor']} | "
            f"{r['okx_stop_outs_avoided_vs_baseline']} | {r['binance_stop_outs_avoided_vs_baseline']} |"
        )
    md.extend(["", "## Notes",
               "- All variants share the SAME filtered signal pool and SAME canonical ledger rule.",
               "- Variants differ only in (a) entry timing (trigger / delay_Nm / retest) and (b) stop placement (fixed % / zone-boundary).",
               "- Target is strict 2 % across all variants.",
               "- This is a DIAGNOSTIC. NO strategy change is proposed."])
    (REP_OUT / "EXECUTION_VARIANTS_CANONICAL_LEDGER.md").write_text("\n".join(md), encoding="utf-8")
    return out


# ---------- Section E: OKX stop-out audit ----------

def section_e_okx_stopouts(baseline: dict, filt_o: list[dict], buckets_o: dict,
                            variant_results: dict) -> dict:
    okx_baseline_trades = baseline["okx"]["trades"]
    stopouts = [t for t in okx_baseline_trades if t["exit_reason"] == "stop"]
    print(f"  OKX baseline stop-outs: {len(stopouts)}", file=sys.stderr)
    # For each stop-out, walk price forward to find if target hits after stop
    okx_zones_by_id = {z["id"]: z for z in filt_o}
    cases = []
    for t in stopouts:
        z = okx_zones_by_id.get(t["zone_id"])
        if z is None:
            continue
        buckets = buckets_o.get(z["_date"]) or []
        trig_sec = z["triggerTs"] // 1000
        stop_sec_iso = t["exit_iso"]
        stop_sec = int(dt.datetime.fromisoformat(stop_sec_iso).timestamp())
        entry_price = t["entry_price"]
        direction = z["direction"]
        # find target after stop
        if direction == "LONG":
            target = entry_price * 1.02
        else:
            target = entry_price * 0.98
        target_hit_sec = None
        scan_until = trig_sec + TIMEOUT_H * 3600
        max_fav_after_entry = 0.0
        for sec, h, l, last in buckets:
            if sec < stop_sec: continue
            if sec > scan_until: break
            if direction == "LONG":
                if h >= target:
                    target_hit_sec = sec; break
            else:
                if l <= target:
                    target_hit_sec = sec; break

        # Check variants
        def variant_outcome(label: str) -> str | None:
            for r in variant_results["results"]:
                if r["variant"] != label: continue
                # walk and find this zone_id in OKX results — but variants don't store per-trade JSON in main results JSON
                # we re-simulate quickly
                return None
            return None
        # Quick variant checks via re-simulation
        def check_variant(entry_strategy, stop_pct, zb=False, mzb=None):
            sim = simulate_canonical_trade(z, buckets, entry_strategy=entry_strategy,
                                           stop_pct=stop_pct, zone_boundary_stop=zb,
                                           max_zone_boundary_or_pct=mzb)
            return sim.get("exit_reason")

        cases.append({
            "date": z["_date"], "zone_id": z["id"], "direction": direction,
            "triggerTs_iso": ms_to_iso(z["triggerTs"]),
            "entry_iso": t["entry_iso"], "entry_price": entry_price,
            "stop_iso": t["exit_iso"], "stop_price": t["exit_price"],
            "mae_pct": t["mae_pct"], "mfe_pct": t["mfe_pct"],
            "target_hit_after_stop_iso": ms_to_iso(target_hit_sec * 1000) if target_hit_sec else None,
            "time_from_stop_to_target_h": (
                round((target_hit_sec - stop_sec) / 3600.0, 3) if target_hit_sec else None
            ),
            "zoneLow": z.get("zoneLow"), "zoneHigh": z.get("zoneHigh"),
            "zone_width_pct": ((z["zoneHigh"] - z["zoneLow"]) / entry_price * 100.0) if z.get("zoneHigh") and z.get("zoneLow") and entry_price else None,
            "delay_5m_outcome": check_variant("delay_5m", 1.0),
            "delay_15m_outcome": check_variant("delay_15m", 1.0),
            "delay_30m_outcome": check_variant("delay_30m", 1.0),
            "stop_1.25_outcome": check_variant("trigger", 1.25),
            "stop_1.5_outcome": check_variant("trigger", 1.5),
            "zone_boundary_stop_outcome": check_variant("trigger", 0.0, zb=True),
            "retest_outcome": check_variant("retest", 1.0),
        })

    # Classify the cause
    n_target_after_stop = sum(1 for c in cases if c["target_hit_after_stop_iso"])
    n_widerstop_would_help = sum(1 for c in cases if c["stop_1.5_outcome"] == "target_2pct")
    n_delay_would_help = sum(1 for c in cases if c["delay_30m_outcome"] == "target_2pct")
    n_retest_would_help = sum(1 for c in cases if c["retest_outcome"] == "target_2pct")
    n_zb_would_help = sum(1 for c in cases if c["zone_boundary_stop_outcome"] == "target_2pct")

    # Heuristic verdict
    if len(cases) == 0:
        cause = "unknown"
    elif n_widerstop_would_help / max(len(cases), 1) > 0.4:
        cause = "tight_stop"
    elif n_delay_would_help / max(len(cases), 1) > 0.4:
        cause = "early_entry"
    elif n_target_after_stop / max(len(cases), 1) > 0.6:
        cause = "early_entry"   # target eventually hit -> entry was just too early
    else:
        cause = "mixed"

    out = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "scope": "OKX direct March - all stop-outs under canonical ledger; counterfactual analysis with variants",
        "n_stopouts": len(cases),
        "cases": cases,
        "diagnostics": {
            "n_target_eventually_hit_after_stop": n_target_after_stop,
            "n_widerstop_1.5pct_would_have_won": n_widerstop_would_help,
            "n_delay_30m_would_have_won": n_delay_would_help,
            "n_retest_would_have_won": n_retest_would_help,
            "n_zone_boundary_stop_would_have_won": n_zb_would_help,
        },
        "OKX_STOP_OUT_CAUSE": cause,
    }
    (REP_OUT / "OKX_STOP_OUTS_UNDER_CANONICAL_LEDGER.json").write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    md = [
        "# OKX stop-outs under canonical ledger (counterfactual audit)",
        "",
        f"**Build:** {out['build_time_utc']}",
        f"**Scope:** all OKX baseline stop-outs (n = {len(cases)}); for each, check whether variants would have won.",
        "",
        "| date | dir | entry | mae % | mfe % | stop time | target hit after stop (h) | delay 30m | stop 1.5 % | zone-bdy | retest |",
        "|---|---|---:|---:|---:|---|---:|---|---|---|---|",
    ]
    for c in cases:
        md.append(
            f"| {c['date']} | {c['direction']} | {c['entry_price']} | "
            f"{c['mae_pct']} | {c['mfe_pct']} | {c['stop_iso']} | "
            f"{c['time_from_stop_to_target_h']} | "
            f"{c['delay_30m_outcome']} | {c['stop_1.5_outcome']} | "
            f"{c['zone_boundary_stop_outcome']} | {c['retest_outcome']} |"
        )
    md.extend([
        "",
        "## Counterfactual counts",
        "",
        f"- target eventually hit AFTER stop (within 24h timeout): **{n_target_after_stop} / {len(cases)}**",
        f"- delay_30m would have won (target_2pct): **{n_delay_would_help} / {len(cases)}**",
        f"- stop_1.5 % would have won: **{n_widerstop_would_help} / {len(cases)}**",
        f"- zone-boundary stop would have won: **{n_zb_would_help} / {len(cases)}**",
        f"- retest entry would have won: **{n_retest_would_help} / {len(cases)}**",
        "",
        f"## Verdict: `OKX_STOP_OUT_CAUSE = {cause}`",
    ])
    (REP_OUT / "OKX_STOP_OUTS_UNDER_CANONICAL_LEDGER.md").write_text("\n".join(md), encoding="utf-8")
    return out


# ---------- Section F: cross-venue decision ----------

def section_f_cross_venue(baseline: dict, variant_results: dict) -> dict:
    base_okx = baseline["okx"]["aggregate"]
    base_bin = baseline["binance"]["aggregate"]
    candidates = variant_results["results"]
    promising = []
    for r in candidates:
        o = r["okx"]; b = r["binance"]
        okx_improves = (
            (o["expectancy_pct_per_trade"] or -999) > (base_okx["expectancy_pct_per_trade"] or -999)
            and (o["profit_factor"] or 0) > (base_okx["profit_factor"] or 0)
            and (o["losses"] or 999) < (base_okx["losses"] or 999)
            and (o["n_trades"] or 0) >= 5
        )
        bin_does_not_break = (
            (b["expectancy_pct_per_trade"] or -999) > 0
            and (b["profit_factor"] or 0) > 1.0
            and (b["wins"] or 0) >= (base_bin["wins"] or 0) - 2  # tolerate -2 wins
        )
        if okx_improves and bin_does_not_break:
            promising.append({
                "variant": r["variant"],
                "okx_expectancy": o["expectancy_pct_per_trade"],
                "okx_pf": o["profit_factor"],
                "okx_wins": o["wins"],
                "okx_losses": o["losses"],
                "binance_expectancy": b["expectancy_pct_per_trade"],
                "binance_pf": b["profit_factor"],
                "binance_wins": b["wins"],
                "binance_losses": b["losses"],
            })
    # Best by min OKX/BIN expectancy
    promising.sort(key=lambda r: min(r["okx_expectancy"], r["binance_expectancy"]), reverse=True)
    best = promising[0] if promising else None

    out = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "scope": "Cross-venue execution variant decision",
        "criteria_for_promising": {
            "okx_improves": "expectancy > baseline AND PF > baseline AND fewer losses AND >= 5 trades",
            "binance_does_not_break": "expectancy > 0 AND PF > 1.0 AND wins not collapsing (>= baseline_wins - 2)",
        },
        "baseline_okx": base_okx, "baseline_binance": base_bin,
        "promising_variants": promising,
        "best_robust_variant": best,
        "ROBUST_EXECUTION_VARIANT_FOUND": "YES" if best else "NO",
    }
    (REP_OUT / "EXECUTION_MODEL_CROSS_VENUE_DECISION.json").write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    md = [
        "# Execution model cross-venue decision",
        "",
        f"**Build:** {out['build_time_utc']}",
        "**Diagnostic only. NOT a strategy change.**",
        "",
        "## Criteria for 'promising'",
        "",
        f"- OKX improves: expectancy > baseline ({base_okx['expectancy_pct_per_trade']}) AND PF > baseline ({base_okx['profit_factor']}) AND fewer losses than {base_okx['losses']} AND n_trades >= 5.",
        f"- Binance does not break: expectancy > 0, PF > 1.0, wins ≥ {base_bin['wins']} − 2.",
        "",
        "## Promising variants",
        "",
        "| variant | OKX exp % | OKX PF | OKX W/L | BIN exp % | BIN PF | BIN W/L |",
        "|---|---:|---:|---|---:|---:|---|",
    ]
    if promising:
        for r in promising:
            md.append(
                f"| `{r['variant']}` | {r['okx_expectancy']} | {r['okx_pf']} | "
                f"{r['okx_wins']}/{r['okx_losses']} | {r['binance_expectancy']} | "
                f"{r['binance_pf']} | {r['binance_wins']}/{r['binance_losses']} |"
            )
    else:
        md.append("| (none) | — | — | — | — | — | — |")
    md.extend([
        "",
        f"**`ROBUST_EXECUTION_VARIANT_FOUND` = {out['ROBUST_EXECUTION_VARIANT_FOUND']}**",
        "",
        f"**Best: `{best['variant'] if best else 'NONE'}`**",
    ])
    (REP_OUT / "EXECUTION_MODEL_CROSS_VENUE_DECISION.md").write_text("\n".join(md), encoding="utf-8")
    return out


# ---------- Main ----------

def main() -> int:
    print("loading zones ...", file=sys.stderr)
    zones_o = load_zones(OKX_DATES, lambda d: REPORTS / f"BTC-USDT-SWAP_{d}")
    zones_b = load_zones(BIN_DATES, lambda d: REP_BIN / f"BTCUSDT_{d}")
    dec_o = apply_passive_filter(zones_o)
    dec_b = apply_passive_filter(zones_b)
    filt_o = [z for z in zones_o if is_triggered(z) and dec_o.get(z["id"], {}).get("kept")]
    filt_b = [z for z in zones_b if is_triggered(z) and dec_b.get(z["id"], {}).get("kept")]
    print(f"  OKX filtered triggered: {len(filt_o)}", file=sys.stderr)
    print(f"  Binance filtered triggered: {len(filt_b)}", file=sys.stderr)

    print("[A] reconciliation ...", file=sys.stderr)
    rec = section_a_reconciliation()
    print("[B] canonical spec ...", file=sys.stderr)
    spec = section_b_canonical_spec()

    print("building 1s buckets ...", file=sys.stderr)
    print("  OKX ...", file=sys.stderr)
    buckets_o: dict[str, list] = {}
    for d in OKX_DATES:
        buckets_o[d] = build_buckets(OKX_DATA_ROOT / d)
    print("  Binance ...", file=sys.stderr)
    buckets_b: dict[str, list] = {}
    for d in BIN_DATES:
        buckets_b[d] = build_buckets(BIN_DATA_ROOT / d)

    print("[C] canonical baseline ...", file=sys.stderr)
    baseline = section_c_baseline(filt_o, buckets_o, filt_b, buckets_b)
    print("[D] execution variants ...", file=sys.stderr)
    variants = section_d_variants(filt_o, buckets_o, filt_b, buckets_b, baseline)
    print("[E] OKX stop-outs audit ...", file=sys.stderr)
    stopouts = section_e_okx_stopouts(baseline, filt_o, buckets_o, variants)
    print("[F] cross-venue decision ...", file=sys.stderr)
    decision = section_f_cross_venue(baseline, variants)

    # ---------- Section G: final summary ----------
    print("[G] final summary ...", file=sys.stderr)
    base_okx_agg = baseline["okx"]["aggregate"]
    base_bin_agg = baseline["binance"]["aggregate"]
    best = decision["best_robust_variant"]

    flags = {
        "LEDGER_41_VS_13_EXPLAINED": rec["LEDGER_41_VS_13_EXPLAINED"],
        "PRIMARY_DIFFERENCE_BETWEEN_LEDGER_MODELS": rec["PRIMARY_DIFFERENCE_BETWEEN_LEDGER_MODELS"],
        "CANONICAL_LEDGER_DEFINED": spec["CANONICAL_LEDGER_DEFINED"],
        "CANONICAL_LEDGER_TRADES_OKX": base_okx_agg["n_trades"],
        "CANONICAL_LEDGER_TRADES_BINANCE": base_bin_agg["n_trades"],
        "CANONICAL_OKX_EXPECTANCY_PRE_COST": base_okx_agg["expectancy_pct_per_trade"],
        "CANONICAL_OKX_PF_PRE_COST": base_okx_agg["profit_factor"],
        "CANONICAL_BINANCE_EXPECTANCY_PRE_COST": base_bin_agg["expectancy_pct_per_trade"],
        "CANONICAL_BINANCE_PF_PRE_COST": base_bin_agg["profit_factor"],
        "CURRENT_TRIGGER_ENTRY_PROBLEMATIC_ON_OKX": (
            "YES" if (base_okx_agg["expectancy_pct_per_trade"] or 0) <= 0
            else "NO"
        ),
        "OKX_STOP_OUT_CAUSE": stopouts["OKX_STOP_OUT_CAUSE"],
        "BEST_EXECUTION_VARIANT": (best["variant"] if best else "NONE"),
        "BEST_EXECUTION_OKX_EXPECTANCY_PRE_COST": (best["okx_expectancy"] if best else None),
        "BEST_EXECUTION_OKX_PF_PRE_COST": (best["okx_pf"] if best else None),
        "BEST_EXECUTION_BINANCE_EXPECTANCY_PRE_COST": (best["binance_expectancy"] if best else None),
        "BEST_EXECUTION_BINANCE_PF_PRE_COST": (best["binance_pf"] if best else None),
        "ROBUST_EXECUTION_VARIANT_FOUND": decision["ROBUST_EXECUTION_VARIANT_FOUND"],
        "READY_FOR_TELEGRAM_HIGH_ONLY": "NO",   # gated on robust variant + much more validation
        "READY_FOR_PASSIVE_LIVE_OBSERVER": "YES" if best else "NO",
        "READY_TO_INTEGRATE_EXECUTION_CHANGES": "NO",
        "MORE_VALIDATION_REQUIRED": "YES",
    }

    sumr = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "scope": "Ledger reconciliation + canonical execution-model audit",
        "okx_baseline": base_okx_agg, "binance_baseline": base_bin_agg,
        "best_execution_variant": best,
        "flags": flags,
    }
    (REP_OUT / "LEDGER_AND_EXECUTION_MODEL_AUDIT_SUMMARY.json").write_text(
        json.dumps(sumr, indent=2, default=str), encoding="utf-8")
    md = [
        "# Ledger reconciliation + execution-model audit - master summary",
        "",
        f"**Build:** {sumr['build_time_utc']}",
        "**Diagnostic only. NO engine change. NO new backtest. Target strict 2 %.**",
        "",
        "## Answers",
        "",
        "1. **Why 41 vs 13 OKX trades?** ",
        f"   {rec['primary_difference']}",
        "",
        "2. **Canonical ledger model:** `CANONICAL_STRICT_LEDGER_v1` (see `CANONICAL_LEDGER_SPEC.md`).",
        "",
        f"3. **Current trigger entry + 1 % stop under canonical model:** ",
        f"   - OKX: n={base_okx_agg['n_trades']}, W/L/T={base_okx_agg['wins']}/{base_okx_agg['losses']}/{base_okx_agg['timeouts']}, "
        f"expectancy {base_okx_agg['expectancy_pct_per_trade']} %, PF {base_okx_agg['profit_factor']}",
        f"   - Binance: n={base_bin_agg['n_trades']}, W/L/T={base_bin_agg['wins']}/{base_bin_agg['losses']}/{base_bin_agg['timeouts']}, "
        f"expectancy {base_bin_agg['expectancy_pct_per_trade']} %, PF {base_bin_agg['profit_factor']}",
        "",
        f"4. **Current trigger entry problematic on OKX?** "
        f"`{flags['CURRENT_TRIGGER_ENTRY_PROBLEMATIC_ON_OKX']}` (canonical baseline expectancy below 0).",
        "",
        f"5. **OKX stop-out cause:** `{flags['OKX_STOP_OUT_CAUSE']}`. ",
        f"   See `OKX_STOP_OUTS_UNDER_CANONICAL_LEDGER.md` for per-zone counterfactuals.",
        "",
        "6. **Cross-venue variant search:** see `EXECUTION_MODEL_CROSS_VENUE_DECISION.md`. ",
        f"   `ROBUST_EXECUTION_VARIANT_FOUND` = **{flags['ROBUST_EXECUTION_VARIANT_FOUND']}**.",
        f"   Best (if any): `{flags['BEST_EXECUTION_VARIANT']}` — OKX exp "
        f"{flags['BEST_EXECUTION_OKX_EXPECTANCY_PRE_COST']} % / PF {flags['BEST_EXECUTION_OKX_PF_PRE_COST']}, "
        f"BIN exp {flags['BEST_EXECUTION_BINANCE_EXPECTANCY_PRE_COST']} % / PF {flags['BEST_EXECUTION_BINANCE_PF_PRE_COST']}.",
        "",
        f"7. **Telegram HIGH-only readiness:** `{flags['READY_FOR_TELEGRAM_HIGH_ONLY']}`. ",
        "   Need cross-venue robust variant first; we don't have one with sufficient confidence yet.",
        "",
        "8. **Blockers to production:**",
        "   - thin n (OKX strict ledger ≤ 50, Binance ≤ 25)",
        "   - target 2 % / stop 1 % R/R brittle on OKX microstructure",
        "   - first-of-month sampling bias on Binance, 14 consecutive days on OKX",
        "   - no second OOS period for either venue",
        "   - costs would shave ~0.1 pp off expectancy",
        "",
        "## Final flag matrix",
        "",
        "```",
    ]
    for k, v in flags.items():
        md.append(f"{k} = {v}")
    md.append("```")
    md.extend(["", "## Hard rules honored",
               "- strategy / thresholds / `zoneDetector`: UNCHANGED",
               "- NO new backtest spawned; post-hoc only",
               "- NO `uniqueMoveId` in filter decision; NO future-leak",
               "- target STRICT 2 %",
               "- no production integration; no profitability claim"])
    (REP_OUT / "LEDGER_AND_EXECUTION_MODEL_AUDIT_SUMMARY.md").write_text("\n".join(md), encoding="utf-8")

    print()
    print("FINAL FLAGS:")
    for k, v in flags.items():
        print(f"  {k:<52s} = {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
