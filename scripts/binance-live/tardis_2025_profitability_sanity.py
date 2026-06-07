"""Binance Tardis 2025 profitability / Telegram-signal sanity check (READ-ONLY).

Inputs:
  reports/binance-tardis/BTCUSDT_<date>/zones.json
  reports/binance-tardis/BINANCE_TARDIS_2025_REGIME_TABLE.json
  data/tardis/binance-futures/BTCUSDT/<date>/trades.csv.gz  (for per-second high/low/last)

Outputs (in reports/binance-tardis/):
  BINANCE_TARDIS_2025_TELEGRAM_SIGNAL_SIMULATION.{csv,json}
  BINANCE_TARDIS_2025_DIRECTION_CORRECTNESS.{md,json,csv}
  BINANCE_TARDIS_2025_PRE_COST_TRADE_LEDGER.{csv,json}
  BINANCE_TARDIS_2025_PRE_COST_PROFITABILITY_SANITY.{md,json}
  BINANCE_TARDIS_2025_BASELINE_VS_FILTERED_EXECUTION.{md,json}
  BINANCE_TARDIS_2025_PRIMARY_UNIQUE_MOVES_AUDIT.{md,json}
  BINANCE_TARDIS_2025_STRATEGY_PROFITABILITY_SANITY_SUMMARY.{md,json}

NO strategy / threshold / engine change. NO new backtest spawned.
Target = 2 % strictly; pre-cost (no fees / slippage).
"""
from __future__ import annotations
import csv
import datetime as dt
import gzip
import json
import statistics as stats
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path("C:/Users/gibilev/orderflow-research")
REPORTS = ROOT / "reports/binance-tardis"
DATA_ROOT = ROOT / "data/tardis/binance-futures/BTCUSDT"

DATES = [f"2025-{m:02d}-01" for m in range(1, 13)]
WINDOW_MIN = 60
PRICE_BAND_PCT = 1.0
FAST_X_MIN = 60
TARGET_PCT = 2.0
STOP_PCT = 1.0
TIMEOUT_H = 24
TIMEOUT_MS = TIMEOUT_H * 3600 * 1000


def ms_to_iso(ms: int | None) -> str | None:
    if ms is None:
        return None
    return dt.datetime.fromtimestamp(ms / 1000, tz=dt.timezone.utc).isoformat(timespec="milliseconds")


def mid_price(z: dict) -> float | None:
    lo, hi = z.get("zoneLow"), z.get("zoneHigh")
    if lo is None or hi is None:
        return None
    return (lo + hi) / 2.0


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


# ---------- live-valid filter (NO uniqueMoveId) ----------

def apply_filter(zones: list[dict]) -> dict[str, dict]:
    by_date = defaultdict(list)
    for z in zones:
        by_date[z["_date"]].append(z)
    decisions = {}
    for date, lst in by_date.items():
        triggered = [z for z in lst if is_triggered(z) and z.get("triggerTs") is not None]
        triggered.sort(key=lambda z: z["triggerTs"])
        for i, z in enumerate(triggered):
            T = z["triggerTs"]; D = z["direction"]; z_mid = mid_price(z)
            dup = False; parent_id = None; lost_reason = None
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
                    parent_id = prior["id"]
                    break
            ctm = confirm_to_trigger_min(z)
            fast_ok = (ctm is None) or (ctm <= FAST_X_MIN)
            kept = (not dup) and fast_ok
            if not kept:
                if dup and not fast_ok:
                    lost_reason = "duplicate_60m_AND_slow_trigger"
                elif dup:
                    lost_reason = "duplicate_60m_price_band"
                else:
                    lost_reason = "slow_trigger_gt_60min"
            decisions[z["id"]] = {
                "kept": kept,
                "lost_reason": lost_reason,
                "parent_id": parent_id,
                "confirm_to_trigger_min": ctm,
            }
    return decisions


# ---------- 1s bucket high/low ----------

def trades_buckets_high_low(date: str) -> list[tuple[int, float, float, float]]:
    """List of (sec_unix, high, low, last) sorted by sec."""
    p = DATA_ROOT / date / "trades.csv.gz"
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
                ts_us = int(row[idx_ts])
                price = float(row[idx_price])
            except Exception:
                continue
            sec = ts_us // 1_000_000
            if sec in high:
                if price > high[sec]:
                    high[sec] = price
                if price < low[sec]:
                    low[sec] = price
            else:
                high[sec] = price
                low[sec] = price
            last[sec] = price
    out = [(s, high[s], low[s], last[s]) for s in sorted(high.keys())]
    return out


# ---------- trade simulation ----------

def simulate_trade(z: dict, buckets: list[tuple[int, float, float, float]]) -> dict:
    """Walk forward from triggerTs; return dict with exit_reason / exit_price / pnl_pct / etc."""
    T = z.get("triggerTs")
    entry = trigger_price(z) or mid_price(z)
    direction = z["direction"]
    if T is None or entry is None or entry <= 0 or not buckets:
        return {"exit_reason": "no_data", "pnl_pct": None}
    trig_sec = T // 1000
    if direction == "LONG":
        target = entry * (1.0 + TARGET_PCT / 100.0)
        stop = entry * (1.0 - STOP_PCT / 100.0)
    else:
        target = entry * (1.0 - TARGET_PCT / 100.0)
        stop = entry * (1.0 + STOP_PCT / 100.0)
    timeout_sec = trig_sec + TIMEOUT_H * 3600
    # binary search start
    lo, hi = 0, len(buckets)
    while lo < hi:
        m = (lo + hi) // 2
        if buckets[m][0] < trig_sec:
            lo = m + 1
        else:
            hi = m
    start_idx = lo
    mfe = 0.0
    mae = 0.0
    exit_reason = "timeout"
    exit_ts_sec = timeout_sec
    exit_price = None
    for idx in range(start_idx, len(buckets)):
        sec, h, l, last = buckets[idx]
        if sec > timeout_sec:
            break
        # update mfe/mae
        if direction == "LONG":
            up = (h - entry) / entry * 100.0
            dn = (entry - l) / entry * 100.0
            if up > mfe:
                mfe = up
            if dn > mae:
                mae = dn
            target_hit = h >= target
            stop_hit = l <= stop
        else:
            up = (entry - l) / entry * 100.0
            dn = (h - entry) / entry * 100.0
            if up > mfe:
                mfe = up
            if dn > mae:
                mae = dn
            target_hit = l <= target
            stop_hit = h >= stop
        if target_hit and stop_hit:
            # conservative: stop first (per spec)
            exit_reason = "stop_1pct"
            exit_ts_sec = sec
            exit_price = stop
            break
        if target_hit:
            exit_reason = "target_2pct"
            exit_ts_sec = sec
            exit_price = target
            break
        if stop_hit:
            exit_reason = "stop_1pct"
            exit_ts_sec = sec
            exit_price = stop
            break
    if exit_reason == "timeout":
        # use last bucket within [trig_sec, timeout_sec]
        timeout_idx = start_idx
        for idx in range(start_idx, len(buckets)):
            if buckets[idx][0] > timeout_sec:
                break
            timeout_idx = idx
        if 0 <= timeout_idx < len(buckets):
            exit_price = buckets[timeout_idx][3]
            exit_ts_sec = buckets[timeout_idx][0]
    if exit_price is None:
        pnl_pct = None
    else:
        sgn = 1.0 if direction == "LONG" else -1.0
        pnl_pct = sgn * (exit_price - entry) / entry * 100.0
    return {
        "entry_ts": T,
        "entry_iso": ms_to_iso(T),
        "entry_price": entry,
        "direction": direction,
        "target_price": target,
        "stop_price": stop,
        "exit_reason": exit_reason,
        "exit_ts_sec": exit_ts_sec,
        "exit_iso": ms_to_iso(exit_ts_sec * 1000),
        "exit_price": exit_price,
        "pnl_pct": round(pnl_pct, 4) if pnl_pct is not None else None,
        "max_favorable_excursion_pct": round(mfe, 4),
        "max_adverse_excursion_pct": round(mae, 4),
        "time_in_trade_h": round((exit_ts_sec - trig_sec) / 3600.0, 4),
    }


# ---------- main ----------

def load_zones() -> list[dict]:
    out: list[dict] = []
    for d in DATES:
        p = REPORTS / f"BTCUSDT_{d}" / "zones.json"
        if not p.exists():
            continue
        obj = json.loads(p.read_text(encoding="utf-8"))
        zones = obj if isinstance(obj, list) else obj.get("zones", [])
        for z in zones:
            z["_date"] = d
            z["_class"] = class_label(z)
        out.extend(zones)
    return out


def main() -> int:
    REPORTS.mkdir(parents=True, exist_ok=True)
    print("loading zones ...", file=sys.stderr)
    zones = load_zones()
    decisions = apply_filter(zones)
    triggered = [z for z in zones if is_triggered(z) and z.get("triggerTs") is not None]
    triggered.sort(key=lambda z: z["triggerTs"])
    print(f"  {len(triggered)} triggered zones", file=sys.stderr)

    # Load regime table
    rt = json.loads((REPORTS / "BINANCE_TARDIS_2025_REGIME_TABLE.json").read_text(encoding="utf-8"))
    regime_map: dict[str, dict] = {r["date"]: r for r in rt.get("per_date", [])}

    # Build per-date 1s buckets with high/low
    print("building 1s buckets per date ...", file=sys.stderr)
    buckets_by_date: dict[str, list] = {}
    for d in DATES:
        print(f"  {d} ...", file=sys.stderr)
        buckets_by_date[d] = trades_buckets_high_low(d)

    # ---------- A. Telegram signal simulation (alert-level, MODE 1) ----------
    print("[A] Telegram signal simulation (filtered only) ...", file=sys.stderr)
    filtered_signals = [z for z in triggered if decisions.get(z["id"], {}).get("kept")]
    sim_rows: list[dict] = []
    for z in filtered_signals:
        sim = simulate_trade(z, buckets_by_date[z["_date"]])
        sim_rows.append({
            "date": z["_date"],
            "zone_id": z["id"],
            "triggerTs": z["triggerTs"],
            "triggerTs_iso": ms_to_iso(z["triggerTs"]),
            "direction": z["direction"],
            "engine_status": z["status"],
            "class_label": z["_class"],
            "entry_price": sim["entry_price"],
            "target_price": sim["target_price"],
            "zoneLow": z.get("zoneLow"),
            "zoneHigh": z.get("zoneHigh"),
            "reached_2pct": sim["exit_reason"] == "target_2pct",
            "exit_reason": sim["exit_reason"],
            "exit_iso": sim["exit_iso"],
            "exit_price": sim["exit_price"],
            "pnl_pct": sim["pnl_pct"],
            "mfe_pct": sim["max_favorable_excursion_pct"],
            "mae_pct": sim["max_adverse_excursion_pct"],
            "time_in_trade_h": sim["time_in_trade_h"],
            "engine_isPrimaryMoveZone": z.get("isPrimaryMoveZone"),
        })

    n_alerts = len(sim_rows)
    n_long = sum(1 for r in sim_rows if r["direction"] == "LONG")
    n_short = n_alerts - n_long
    n_reached = sum(1 for r in sim_rows if r["reached_2pct"])
    n_failed = n_alerts - n_reached
    reached_rate = round(100.0 * n_reached / n_alerts, 2) if n_alerts else None

    sim_json = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "scope": "Filtered triggered zones across Binance Tardis 2025 (12 dates), live-valid filter",
        "n_telegram_alerts": n_alerts,
        "alerts_per_day": round(n_alerts / len(DATES), 3),
        "long_alerts": n_long,
        "short_alerts": n_short,
        "reached_2pct_count": n_reached,
        "reached_2pct_rate_pct": reached_rate,
        "failed_or_timeout_count": n_failed,
        "rows": sim_rows,
    }
    (REPORTS / "BINANCE_TARDIS_2025_TELEGRAM_SIGNAL_SIMULATION.json").write_text(
        json.dumps(sim_json, indent=2, default=str), encoding="utf-8")
    keys = ["date", "zone_id", "triggerTs_iso", "direction", "engine_status", "class_label",
            "entry_price", "target_price", "exit_reason", "exit_iso", "exit_price",
            "pnl_pct", "mfe_pct", "mae_pct", "time_in_trade_h", "reached_2pct",
            "engine_isPrimaryMoveZone"]
    with (REPORTS / "BINANCE_TARDIS_2025_TELEGRAM_SIGNAL_SIMULATION.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        for r in sim_rows:
            w.writerow(r)

    # ---------- B. Direction correctness ----------
    print("[B] direction correctness ...", file=sys.stderr)
    dir_rows = []
    days_up = 0; days_down = 0; days_both = 0; days_no = 0
    correct_dir_days = 0
    missed_opp_days = 0
    wrong_dir_alert_days = 0
    wrong_dir_alerts_total = 0
    signals_matching = 0
    signals_against = 0
    reached_matching_dir = 0

    for d in DATES:
        rg = regime_map.get(d, {})
        f24 = rg.get("forward_max_moves", {}).get("24h", {})
        up_feas = f24.get("max_up", 0) >= 2.0
        down_feas = f24.get("max_down", 0) >= 2.0
        if up_feas and down_feas: days_both += 1
        elif up_feas: days_up += 1
        elif down_feas: days_down += 1
        else: days_no += 1
        day_signals = [r for r in sim_rows if r["date"] == d]
        n_long_d = sum(1 for r in day_signals if r["direction"] == "LONG")
        n_short_d = sum(1 for r in day_signals if r["direction"] == "SHORT")
        n_reached_d = sum(1 for r in day_signals if r["reached_2pct"])
        # direction correctness: any signal in the feasible direction?
        sent_long_when_up = up_feas and n_long_d > 0
        sent_short_when_down = down_feas and n_short_d > 0
        any_match = sent_long_when_up or sent_short_when_down
        any_feasible = up_feas or down_feas
        # wrong-direction alerts: signals against the ONLY-feasible direction
        wrong_alerts_today = 0
        if up_feas and not down_feas:
            wrong_alerts_today = n_short_d
        elif down_feas and not up_feas:
            wrong_alerts_today = n_long_d
        if any_feasible:
            if any_match:
                correct_dir_days += 1
                signals_matching += (n_long_d if up_feas else 0) + (n_short_d if down_feas else 0)
                reached_matching_dir += n_reached_d
            else:
                missed_opp_days += 1
        else:
            # neither up nor down 2% feasible
            if n_long_d + n_short_d > 0:
                # noise alerts on no-2% day — count as wrong-direction-alert day
                wrong_dir_alert_days += 1
                wrong_alerts_today = n_long_d + n_short_d
        if wrong_alerts_today > 0:
            wrong_dir_alerts_total += wrong_alerts_today
            signals_against += wrong_alerts_today
            if d not in [r["date"] for r in dir_rows] or wrong_alerts_today:
                pass
        # Annotate row
        dir_rows.append({
            "date": d,
            "day_return_pct": rg.get("day_return_pct"),
            "day_range_pct": rg.get("day_range_pct"),
            "max_24h_up_pct": f24.get("max_up"),
            "max_24h_down_pct": f24.get("max_down"),
            "up_2pct_feasible": up_feas,
            "down_2pct_feasible": down_feas,
            "n_long_alerts": n_long_d,
            "n_short_alerts": n_short_d,
            "n_reached_2pct": n_reached_d,
            "verdict": (
                "BOTH_FEASIBLE" if up_feas and down_feas
                else "UP_ONLY" if up_feas
                else "DOWN_ONLY" if down_feas
                else "NEITHER"
            ),
            "direction_correct": (
                None if not any_feasible
                else "YES" if any_match else "NO"
            ),
            "wrong_direction_alerts": wrong_alerts_today,
        })

    dir_json = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "per_day": dir_rows,
        "days_with_up_2pct": days_up + days_both,
        "days_with_down_2pct": days_down + days_both,
        "days_with_both_2pct": days_both,
        "days_with_no_2pct": days_no,
        "correct_direction_days": correct_dir_days,
        "missed_opportunity_days": missed_opp_days,
        "wrong_direction_alert_days": wrong_dir_alert_days,
        "filtered_signals_against_only_feasible_direction": signals_against,
        "filtered_signals_matching_feasible_direction": signals_matching,
        "reached_2pct_matching_direction": reached_matching_dir,
    }
    (REPORTS / "BINANCE_TARDIS_2025_DIRECTION_CORRECTNESS.json").write_text(
        json.dumps(dir_json, indent=2, default=str), encoding="utf-8")

    keys = ["date", "day_return_pct", "day_range_pct", "max_24h_up_pct", "max_24h_down_pct",
            "up_2pct_feasible", "down_2pct_feasible", "verdict",
            "n_long_alerts", "n_short_alerts", "n_reached_2pct",
            "direction_correct", "wrong_direction_alerts"]
    with (REPORTS / "BINANCE_TARDIS_2025_DIRECTION_CORRECTNESS.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in dir_rows:
            w.writerow(r)
    md_dir = [
        "# Binance Tardis 2025 - direction correctness",
        "",
        f"**Build:** {dir_json['build_time_utc']}",
        "**Scope:** day-level 2 % feasibility (24h horizon) vs filtered Telegram alerts; live-valid filter.",
        "",
        "| date | day Δ % | rng % | 24h up % | 24h dn % | verdict | LONG alerts | SHORT alerts | reached 2 % | direction correct | wrong-dir alerts |",
        "|---|---:|---:|---:|---:|---|---:|---:|---:|---|---:|",
    ]
    for r in dir_rows:
        md_dir.append(
            f"| {r['date']} | {r['day_return_pct']} | {r['day_range_pct']} | "
            f"{r['max_24h_up_pct']} | {r['max_24h_down_pct']} | {r['verdict']} | "
            f"{r['n_long_alerts']} | {r['n_short_alerts']} | {r['n_reached_2pct']} | "
            f"{r['direction_correct']} | {r['wrong_direction_alerts']} |"
        )
    md_dir.extend([
        "",
        "## Summary",
        "",
        f"- days with up 2 % feasible: **{dir_json['days_with_up_2pct']} / 12**",
        f"- days with down 2 % feasible: **{dir_json['days_with_down_2pct']} / 12**",
        f"- days with both 2 % feasible: **{dir_json['days_with_both_2pct']}**",
        f"- days with NO 2 % feasible: **{dir_json['days_with_no_2pct']}**",
        f"- correct-direction days: **{dir_json['correct_direction_days']}**",
        f"- missed-opportunity days (feasible but no matching signal): **{dir_json['missed_opportunity_days']}**",
        f"- wrong-direction-alert days (no 2 % feasible AND filter still sent alerts): **{dir_json['wrong_direction_alert_days']}**",
        f"- filtered signals against only-feasible direction: **{dir_json['filtered_signals_against_only_feasible_direction']}**",
        f"- filtered signals matching feasible direction: **{dir_json['filtered_signals_matching_feasible_direction']}**",
        f"- reached 2 % matching direction: **{dir_json['reached_2pct_matching_direction']}**",
    ])
    (REPORTS / "BINANCE_TARDIS_2025_DIRECTION_CORRECTNESS.md").write_text("\n".join(md_dir), encoding="utf-8")

    # ---------- C. Trade ledger MODE 1 + MODE 2 ----------
    print("[C] trade ledger ...", file=sys.stderr)
    # MODE 1: every filtered signal becomes an independent trade
    mode1_trades = []
    for r in sim_rows:
        mode1_trades.append({**r, "_mode": "mode1_alert_level"})

    # MODE 2: walk filtered signals chronologically, skip if position open
    # Sort by triggerTs across all dates
    sorted_signals = sorted(sim_rows, key=lambda r: r["triggerTs"])
    mode2_trades = []
    open_until_ts_sec = -1
    skipped = []
    for r in sorted_signals:
        trig_sec = r["triggerTs"] // 1000
        if trig_sec < open_until_ts_sec:
            skipped.append({"zone_id": r["zone_id"], "reason": "position_open",
                            "open_until_iso": ms_to_iso(open_until_ts_sec * 1000)})
            continue
        # Take this trade; exit_ts_sec is already simulated
        mode2_trades.append({**r, "_mode": "mode2_strict_ledger"})
        open_until_ts_sec = int(r.get("exit_iso", "").replace("T", " ")[:0]) if False else None
        # safer: use stored exit_ts_sec via re-simulation; but simulate_trade returned that — we
        # can reconstruct from time_in_trade_h since we have triggerTs and time_in_trade_h
        time_h = r["time_in_trade_h"] or 0
        open_until_ts_sec = trig_sec + int(time_h * 3600)

    def aggregate(trades: list[dict]) -> dict:
        n = len(trades)
        wins = sum(1 for t in trades if t["exit_reason"] == "target_2pct")
        losses = sum(1 for t in trades if t["exit_reason"] == "stop_1pct")
        timeouts = sum(1 for t in trades if t["exit_reason"] == "timeout")
        pnls = [t["pnl_pct"] for t in trades if t["pnl_pct"] is not None]
        wins_pnls = [p for p in pnls if p > 0]
        losses_pnls = [p for p in pnls if p < 0]
        gross_w = sum(wins_pnls)
        gross_l = sum(-p for p in losses_pnls)
        # consecutive losses
        max_cons_losses = 0
        cur = 0
        for t in trades:
            if (t["pnl_pct"] or 0) < 0:
                cur += 1
                if cur > max_cons_losses:
                    max_cons_losses = cur
            else:
                cur = 0
        # by direction
        long_trades = [t for t in trades if t["direction"] == "LONG"]
        short_trades = [t for t in trades if t["direction"] == "SHORT"]
        long_pnls = [t["pnl_pct"] for t in long_trades if t["pnl_pct"] is not None]
        short_pnls = [t["pnl_pct"] for t in short_trades if t["pnl_pct"] is not None]
        # by day
        by_day = defaultdict(list)
        for t in trades:
            if t["pnl_pct"] is not None:
                by_day[t["date"]].append(t["pnl_pct"])
        best_day = max(by_day.items(), key=lambda kv: sum(kv[1]), default=(None, []))
        worst_day = min(by_day.items(), key=lambda kv: sum(kv[1]), default=(None, []))
        depends = False
        if pnls:
            total = sum(pnls)
            best_sum = sum(best_day[1])
            depends = total > 0 and best_sum > total
        return {
            "n_trades": n,
            "wins": wins,
            "losses": losses,
            "timeouts": timeouts,
            "winrate_pct": round(100.0 * wins / n, 2) if n else None,
            "avg_win_pct": round(stats.mean(wins_pnls), 4) if wins_pnls else None,
            "avg_loss_pct": round(stats.mean(losses_pnls), 4) if losses_pnls else None,
            "expectancy_pct_per_trade": round(stats.mean(pnls), 4) if pnls else None,
            "total_return_pct_1unit": round(sum(pnls), 4) if pnls else None,
            "profit_factor": round(gross_w / gross_l, 3) if gross_l > 0 else (None if gross_w == 0 else float("inf")),
            "max_consecutive_losses": max_cons_losses,
            "best_day": {"date": best_day[0], "sum_pnl_pct": round(sum(best_day[1]), 4) if best_day[0] else None},
            "worst_day": {"date": worst_day[0], "sum_pnl_pct": round(sum(worst_day[1]), 4) if worst_day[0] else None},
            "long_n": len(long_trades),
            "long_expectancy_pct": round(stats.mean(long_pnls), 4) if long_pnls else None,
            "short_n": len(short_trades),
            "short_expectancy_pct": round(stats.mean(short_pnls), 4) if short_pnls else None,
            "result_depends_on_one_day": depends,
        }

    mode1_agg = aggregate(mode1_trades)
    mode2_agg = aggregate(mode2_trades)

    ledger_json = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "scope": "Binance Tardis 2025 (12 dates) pre-cost trade simulation; target 2 %, stop 1 %, timeout 24 h",
        "execution_model": {
            "target_pct": TARGET_PCT, "stop_pct": STOP_PCT, "timeout_hours": TIMEOUT_H,
            "tiebreak_target_and_stop_same_second": "stop_first_conservative",
            "PRE_COST_ONLY": "YES",
            "FEES_SLIPPAGE_INCLUDED": "NO",
        },
        "mode1_alert_level": {"trades": mode1_trades, "aggregate": mode1_agg},
        "mode2_strict_ledger": {
            "trades": mode2_trades, "aggregate": mode2_agg,
            "n_skipped_due_to_open_position": len(skipped),
            "skipped_examples": skipped[:20],
        },
    }
    (REPORTS / "BINANCE_TARDIS_2025_PRE_COST_TRADE_LEDGER.json").write_text(
        json.dumps(ledger_json, indent=2, default=str), encoding="utf-8")

    led_keys = ["mode", "date", "zone_id", "direction", "triggerTs_iso", "entry_price",
                "target_price", "stop_price", "exit_reason", "exit_iso", "exit_price",
                "pnl_pct", "mfe_pct", "mae_pct", "time_in_trade_h"]
    with (REPORTS / "BINANCE_TARDIS_2025_PRE_COST_TRADE_LEDGER.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=led_keys)
        w.writeheader()
        for set_name, lst in [("mode1", mode1_trades), ("mode2", mode2_trades)]:
            for t in lst:
                w.writerow({
                    "mode": set_name, "date": t["date"], "zone_id": t["zone_id"],
                    "direction": t["direction"], "triggerTs_iso": t["triggerTs_iso"],
                    "entry_price": t["entry_price"], "target_price": t["target_price"],
                    "stop_price": "(implicit)", "exit_reason": t["exit_reason"],
                    "exit_iso": t["exit_iso"], "exit_price": t["exit_price"],
                    "pnl_pct": t["pnl_pct"], "mfe_pct": t["mfe_pct"],
                    "mae_pct": t["mae_pct"], "time_in_trade_h": t["time_in_trade_h"],
                })

    # ---------- D. Profitability sanity metrics ----------
    md_p = [
        "# Binance Tardis 2025 - pre-cost profitability sanity",
        "",
        f"**Build:** {ledger_json['build_time_utc']}",
        "**`PRE_COST_ONLY = YES`, `FEES_SLIPPAGE_INCLUDED = NO`, `PROFITABILITY_CLAIM = NO`.**",
        "**Target = 2 % (strict). Stop = 1 % fixed. Timeout = 24h.**",
        "",
        "## MODE 1 (alert-level, every filtered signal is an independent trade)",
        "",
        "| metric | value |",
        "|---|---:|",
    ]
    for k, v in mode1_agg.items():
        if isinstance(v, dict):
            md_p.append(f"| {k} | {v.get('date')} ({v.get('sum_pnl_pct')}%) |")
        else:
            md_p.append(f"| {k} | {v} |")
    md_p.extend(["", "## MODE 2 (strict ledger, one trade at a time)", "",
                 f"- skipped due to open position: **{len(skipped)}**", "",
                 "| metric | value |", "|---|---:|"])
    for k, v in mode2_agg.items():
        if isinstance(v, dict):
            md_p.append(f"| {k} | {v.get('date')} ({v.get('sum_pnl_pct')}%) |")
        else:
            md_p.append(f"| {k} | {v} |")
    (REPORTS / "BINANCE_TARDIS_2025_PRE_COST_PROFITABILITY_SANITY.md").write_text("\n".join(md_p), encoding="utf-8")
    (REPORTS / "BINANCE_TARDIS_2025_PRE_COST_PROFITABILITY_SANITY.json").write_text(
        json.dumps({"mode1": mode1_agg, "mode2": mode2_agg, "skipped_count_mode2": len(skipped)},
                   indent=2, default=str), encoding="utf-8")

    # ---------- E. Baseline vs filtered execution ----------
    print("[E] baseline vs filtered execution ...", file=sys.stderr)
    baseline_trades = []
    for z in triggered:
        sim = simulate_trade(z, buckets_by_date[z["_date"]])
        baseline_trades.append({**sim, "date": z["_date"], "zone_id": z["id"],
                                "direction": z["direction"]})

    # Baseline MODE 2 (strict ledger)
    sorted_b = sorted(baseline_trades, key=lambda r: r["entry_ts"])
    baseline_mode2 = []
    open_until = -1
    base_skipped = 0
    for r in sorted_b:
        trig_sec = r["entry_ts"] // 1000
        if trig_sec < open_until:
            base_skipped += 1
            continue
        baseline_mode2.append(r)
        time_h = r["time_in_trade_h"] or 0
        open_until = trig_sec + int(time_h * 3600)

    def to_pnl_trades(rows):
        return [{
            "date": r["date"], "direction": r["direction"], "exit_reason": r["exit_reason"],
            "pnl_pct": r["pnl_pct"], "mfe_pct": r["max_favorable_excursion_pct"],
            "mae_pct": r["max_adverse_excursion_pct"], "time_in_trade_h": r["time_in_trade_h"],
        } for r in rows]

    base1 = aggregate(to_pnl_trades(baseline_trades))
    base2 = aggregate(to_pnl_trades(baseline_mode2))

    # wrong-direction alerts among baseline triggered zones
    base_wrong_dir = 0
    for z in triggered:
        d = z["_date"]
        rg = regime_map.get(d, {})
        f24 = rg.get("forward_max_moves", {}).get("24h", {})
        up_feas = f24.get("max_up", 0) >= 2.0
        down_feas = f24.get("max_down", 0) >= 2.0
        if up_feas and not down_feas and z["direction"] == "SHORT":
            base_wrong_dir += 1
        elif down_feas and not up_feas and z["direction"] == "LONG":
            base_wrong_dir += 1
        elif not up_feas and not down_feas:
            base_wrong_dir += 1

    bf_json = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "baseline": {
            "n_triggered": len(triggered),
            "wrong_direction_alerts": base_wrong_dir,
            "mode1_aggregate": base1, "mode2_aggregate": base2, "mode2_skipped": base_skipped,
        },
        "filtered": {
            "n_triggered": n_alerts,
            "wrong_direction_alerts": wrong_dir_alerts_total,
            "mode1_aggregate": mode1_agg, "mode2_aggregate": mode2_agg, "mode2_skipped": len(skipped),
        },
    }
    (REPORTS / "BINANCE_TARDIS_2025_BASELINE_VS_FILTERED_EXECUTION.json").write_text(
        json.dumps(bf_json, indent=2, default=str), encoding="utf-8")

    md_bf = [
        "# Binance Tardis 2025 - baseline vs filtered execution (pre-cost)",
        "",
        f"**Build:** {bf_json['build_time_utc']}",
        "**Same target=2 %, stop=1 %, timeout=24h applied to BOTH sets.**",
        "",
        "## MODE 1 (alert-level)",
        "",
        "| metric | baseline | filtered | delta |",
        "|---|---:|---:|---|",
    ]
    for k in ("n_trades", "wins", "losses", "timeouts", "winrate_pct",
              "avg_win_pct", "avg_loss_pct", "expectancy_pct_per_trade",
              "total_return_pct_1unit", "profit_factor", "max_consecutive_losses",
              "long_n", "long_expectancy_pct", "short_n", "short_expectancy_pct"):
        bv = base1.get(k); fv = mode1_agg.get(k)
        if isinstance(bv, (int, float)) and isinstance(fv, (int, float)):
            md_bf.append(f"| {k} | {bv} | {fv} | {round(fv - bv, 4)} |")
        else:
            md_bf.append(f"| {k} | {bv} | {fv} | — |")
    md_bf.extend(["", "## MODE 2 (strict ledger)", "",
                  "| metric | baseline | filtered | delta |", "|---|---:|---:|---|"])
    for k in ("n_trades", "wins", "losses", "timeouts", "winrate_pct",
              "avg_win_pct", "avg_loss_pct", "expectancy_pct_per_trade",
              "total_return_pct_1unit", "profit_factor", "max_consecutive_losses",
              "long_n", "long_expectancy_pct", "short_n", "short_expectancy_pct"):
        bv = base2.get(k); fv = mode2_agg.get(k)
        if isinstance(bv, (int, float)) and isinstance(fv, (int, float)):
            md_bf.append(f"| {k} | {bv} | {fv} | {round(fv - bv, 4)} |")
        else:
            md_bf.append(f"| {k} | {bv} | {fv} | — |")
    md_bf.extend(["", "## Wrong-direction alerts", "",
                  f"- baseline: **{base_wrong_dir}** (out of {len(triggered)} triggered)",
                  f"- filtered: **{wrong_dir_alerts_total}** (out of {n_alerts} alerts)"])
    (REPORTS / "BINANCE_TARDIS_2025_BASELINE_VS_FILTERED_EXECUTION.md").write_text("\n".join(md_bf), encoding="utf-8")

    # ---------- F. Primary unique moves audit ----------
    print("[F] primary unique moves audit ...", file=sys.stderr)
    primaries = [z for z in zones if z.get("isPrimaryMoveZone") and z.get("status") == "RESOLVED_REACHED"]
    audit = []
    for z in primaries:
        dec = decisions.get(z["id"], {})
        # Did filter keep it?
        kept = dec.get("kept", False)
        lost_reason = dec.get("lost_reason")
        # If kept, would alert-level trade also succeed?
        sim = simulate_trade(z, buckets_by_date[z["_date"]])
        rg = regime_map.get(z["_date"], {})
        # If lost, explain
        explanation = lost_reason if lost_reason else "kept_by_filter"
        # In strict ledger, was this primary actually taken or skipped due to open position?
        # Reconstruct: find this primary in sorted_signals; if it's in skipped, mark
        was_in_ledger = any(t["zone_id"] == z["id"] for t in mode2_trades)
        was_skipped_in_ledger = any(s["zone_id"] == z["id"] for s in skipped)
        audit.append({
            "date": z["_date"],
            "zone_id": z["id"],
            "direction": z["direction"],
            "regime": rg.get("regime"),
            "day_return_pct": rg.get("day_return_pct"),
            "confirm_to_trigger_min": dec.get("confirm_to_trigger_min"),
            "filter_kept": kept,
            "lost_reason": explanation,
            "trade_target_reached_in_sim": sim["exit_reason"] == "target_2pct",
            "sim_exit_reason": sim["exit_reason"],
            "sim_pnl_pct": sim["pnl_pct"],
            "sim_time_in_trade_h": sim["time_in_trade_h"],
            "telegram_alert_would_have_been_sent": kept,
            "strict_ledger_took_this_trade": was_in_ledger,
            "strict_ledger_skipped_due_position_open": was_skipped_in_ledger,
        })

    (REPORTS / "BINANCE_TARDIS_2025_PRIMARY_UNIQUE_MOVES_AUDIT.json").write_text(
        json.dumps(audit, indent=2, default=str), encoding="utf-8")
    md_au = [
        "# Binance Tardis 2025 - audit of 7 primary unique moves",
        "",
        f"**Build:** {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}",
        "**Each row = one engine-flagged primary_unique_reached_move zone. Filter decision audit + sim-trade outcome at target 2 % / stop 1 % / timeout 24 h.**",
        "",
        "| date | regime | direction | conf->trig min | filter kept | lost reason | sim exit | sim pnl % | sim time (h) | telegram alert | strict ledger took |",
        "|---|---|---|---:|:---:|---|---|---:|---:|:---:|:---:|",
    ]
    for r in audit:
        md_au.append(
            f"| {r['date']} | {r['regime']} | {r['direction']} | "
            f"{r['confirm_to_trigger_min']} | "
            f"{'YES' if r['filter_kept'] else 'NO'} | {r['lost_reason']} | "
            f"{r['sim_exit_reason']} | {r['sim_pnl_pct']} | {r['sim_time_in_trade_h']} | "
            f"{'YES' if r['telegram_alert_would_have_been_sent'] else 'NO'} | "
            f"{'YES' if r['strict_ledger_took_this_trade'] else 'NO'} |"
        )
    md_au.extend(["", "## Counts", "",
                  f"- total primary unique reached zones: **{len(audit)}**",
                  f"- kept by filter: **{sum(1 for r in audit if r['filter_kept'])}**",
                  f"- lost by filter: **{sum(1 for r in audit if not r['filter_kept'])}**",
                  f"- target reached in sim (any of the 7): **{sum(1 for r in audit if r['trade_target_reached_in_sim'])}**",
                  f"- strict-ledger took (out of kept): **{sum(1 for r in audit if r['strict_ledger_took_this_trade'])}**"])
    (REPORTS / "BINANCE_TARDIS_2025_PRIMARY_UNIQUE_MOVES_AUDIT.md").write_text("\n".join(md_au), encoding="utf-8")

    # ---------- G. Final decision report + flags ----------
    n_kept_primary = sum(1 for r in audit if r["filter_kept"])
    primary_recall = round(100.0 * n_kept_primary / len(audit), 2) if audit else None
    expectancy_positive_mode1 = mode1_agg["expectancy_pct_per_trade"] is not None and mode1_agg["expectancy_pct_per_trade"] > 0
    expectancy_positive_mode2 = mode2_agg["expectancy_pct_per_trade"] is not None and mode2_agg["expectancy_pct_per_trade"] > 0
    filter_improves_expectancy = "UNKNOWN"
    if base1.get("expectancy_pct_per_trade") is not None and mode1_agg.get("expectancy_pct_per_trade") is not None:
        if mode1_agg["expectancy_pct_per_trade"] > base1["expectancy_pct_per_trade"] + 0.05:
            filter_improves_expectancy = "YES"
        elif mode1_agg["expectancy_pct_per_trade"] < base1["expectancy_pct_per_trade"] - 0.05:
            filter_improves_expectancy = "NO"
        else:
            filter_improves_expectancy = "UNCLEAR"
    # Strategy probably profitable?
    strategy_probably_profitable = "UNKNOWN"
    if mode2_agg["n_trades"] is not None and mode2_agg["n_trades"] >= 10:
        if expectancy_positive_mode2 and (mode2_agg["profit_factor"] or 0) > 1.2:
            strategy_probably_profitable = "YES"
        elif (mode2_agg["expectancy_pct_per_trade"] or 0) <= 0:
            strategy_probably_profitable = "NO"
    elif mode2_agg["n_trades"] is None or mode2_agg["n_trades"] < 10:
        strategy_probably_profitable = "UNKNOWN"

    flags = {
        "BINANCE_PROFITABILITY_SANITY_DONE": "YES",
        "TARGET_USED_FOR_PROFITABILITY": "2.0%",
        "TELEGRAM_ALERTS_TOTAL": n_alerts,
        "TELEGRAM_ALERTS_PER_DAY": round(n_alerts / 12, 3),
        "TELEGRAM_ALERTS_REACHED_2PCT": n_reached,
        "TELEGRAM_ALERT_REACHED_2PCT_RATE_PCT": reached_rate,
        "DAYS_WITH_2PCT_OPPORTUNITY": dir_json["days_with_up_2pct"] + dir_json["days_with_down_2pct"] - dir_json["days_with_both_2pct"],
        "DAYS_WITH_CORRECT_DIRECTION_SIGNAL": dir_json["correct_direction_days"],
        "DAYS_WITH_MISSED_2PCT_OPPORTUNITY": dir_json["missed_opportunity_days"],
        "WRONG_DIRECTION_ALERTS_TOTAL": wrong_dir_alerts_total,
        "FILTERED_PRIMARY_UNIQUE_KEPT": n_kept_primary,
        "FILTERED_PRIMARY_UNIQUE_TOTAL": len(audit),
        "FILTERED_PRIMARY_RECALL_PCT": primary_recall,
        "STRICT_LEDGER_TRADES": mode2_agg["n_trades"],
        "STRICT_LEDGER_WINS": mode2_agg["wins"],
        "STRICT_LEDGER_LOSSES": mode2_agg["losses"],
        "STRICT_LEDGER_TIMEOUTS": mode2_agg["timeouts"],
        "STRICT_LEDGER_WINRATE_PCT": mode2_agg["winrate_pct"],
        "STRICT_LEDGER_EXPECTANCY_PRE_COST_PCT": mode2_agg["expectancy_pct_per_trade"],
        "STRICT_LEDGER_PROFIT_FACTOR_PRE_COST": mode2_agg["profit_factor"],
        "FILTER_IMPROVES_EXPECTANCY": filter_improves_expectancy,
        "PRE_COST_EXPECTANCY_POSITIVE": "YES" if expectancy_positive_mode2 else ("NO" if mode2_agg["expectancy_pct_per_trade"] is not None else "UNKNOWN"),
        "STRATEGY_PROBABLY_PROFITABLE": strategy_probably_profitable,
        "READY_FOR_PASSIVE_LIVE_OBSERVER": "YES" if (primary_recall or 0) >= 70 else "NO",
        "READY_TO_INTEGRATE_FILTER_IN_STRATEGY": "NO",
        "MORE_VALIDATION_REQUIRED": "YES",
    }

    sumr_json = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "scope": "Binance Tardis 2025 first-of-month (12 dates) — pre-cost sanity at strict 2 % target",
        "PRE_COST_ONLY": "YES",
        "FEES_SLIPPAGE_INCLUDED": "NO",
        "PROFITABILITY_CLAIM": "NO",
        "execution_model": {"target_pct": TARGET_PCT, "stop_pct": STOP_PCT,
                            "timeout_h": TIMEOUT_H,
                            "tiebreak": "stop_first_conservative"},
        "answers": {
            "telegram_alerts_12d": n_alerts,
            "reached_2pct": n_reached,
            "correct_direction_days": dir_json["correct_direction_days"],
            "wrong_direction_alerts": wrong_dir_alerts_total,
            "missed_2pct_opportunity_days": dir_json["missed_opportunity_days"],
            "filter_vs_baseline_mode2_expectancy_delta_pp": (
                round((mode2_agg["expectancy_pct_per_trade"] or 0) - (base2["expectancy_pct_per_trade"] or 0), 4)
                if mode2_agg["expectancy_pct_per_trade"] is not None
                and base2["expectancy_pct_per_trade"] is not None else None
            ),
            "pre_cost_expectancy_positive_mode2": expectancy_positive_mode2,
            "probably_profitable": strategy_probably_profitable,
        },
        "flags": flags,
    }
    (REPORTS / "BINANCE_TARDIS_2025_STRATEGY_PROFITABILITY_SANITY_SUMMARY.json").write_text(
        json.dumps(sumr_json, indent=2, default=str), encoding="utf-8")

    md_s = [
        "# Binance Tardis 2025 — strategy profitability sanity summary (pre-cost)",
        "",
        f"**Build:** {sumr_json['build_time_utc']}",
        "**`PRE_COST_ONLY=YES`, `FEES_SLIPPAGE_INCLUDED=NO`, `PROFITABILITY_CLAIM=NO`. Target 2 % strict.**",
        "",
        "## Answers",
        "",
        f"1. Telegram alerts for 12 days: **{n_alerts}** (~{round(n_alerts/12, 2)}/day)",
        f"2. Reached 2 % strict: **{n_reached}** (= {reached_rate} %)",
        f"3. Correct-direction days (any feasible direction has matching signal): "
        f"**{dir_json['correct_direction_days']}** / 12",
        f"4. Wrong-direction alerts total: **{wrong_dir_alerts_total}**",
        f"5. Missed 2 % opportunity days (feasible but no matching signal): "
        f"**{dir_json['missed_opportunity_days']}**",
        f"6. Filter vs baseline MODE-2 expectancy delta: "
        f"**{sumr_json['answers']['filter_vs_baseline_mode2_expectancy_delta_pp']} pp**",
        f"7. Pre-cost positive expectancy (MODE 2): **{'YES' if expectancy_positive_mode2 else 'NO'}**",
        f"8. STRATEGY_PROBABLY_PROFITABLE = **{strategy_probably_profitable}**",
        "",
        "## Blockers (if any)",
        "",
    ]
    blockers = []
    if (primary_recall or 0) < 70:
        blockers.append(f"primary recall {primary_recall}% < 70%")
    if mode2_agg["n_trades"] is not None and mode2_agg["n_trades"] < 10:
        blockers.append(f"only {mode2_agg['n_trades']} trades in strict ledger (n < 10)")
    if dir_json["missed_opportunity_days"] >= 3:
        blockers.append(f"missed 2% opportunity on {dir_json['missed_opportunity_days']} days")
    if wrong_dir_alerts_total > 0:
        blockers.append(f"{wrong_dir_alerts_total} wrong-direction alerts on no-2%-feasible days")
    if (mode2_agg["expectancy_pct_per_trade"] or 0) <= 0:
        blockers.append(f"pre-cost expectancy {mode2_agg['expectancy_pct_per_trade']} % per trade — not positive")
    if not blockers:
        md_s.append("(none — but sample size is still thin; see caveats below)")
    else:
        for b in blockers:
            md_s.append(f"- {b}")
    md_s.extend([
        "",
        "## Caveats",
        "",
        "- Sample = 12 first-of-month days only; not a representative full year.",
        "- 1-second price buckets (high/low/last). Sub-second target-vs-stop tiebreak ⇒ conservative stop-first.",
        "- NO fees, NO slippage, NO funding. Real trading costs would reduce pnl materially.",
        "- Engine triggers might not be the actual user-Telegram entry point in production.",
        "",
        "## Final flag matrix",
        "",
        "```",
    ])
    for k, v in flags.items():
        md_s.append(f"{k} = {v}")
    md_s.append("```")
    md_s.extend(["", "## Hard rules honored",
                 "- strategy / thresholds / `zoneDetector`: UNCHANGED",
                 "- NO new backtest spawned; pure post-hoc simulation over existing zones + price path",
                 "- NO `uniqueMoveId` in filter decision; NO future-leak in suppress",
                 "- target STRICT 2 % (no 0.5/1/1.5 considered as 'win')",
                 "- no production integration; no profitability claim"])
    (REPORTS / "BINANCE_TARDIS_2025_STRATEGY_PROFITABILITY_SANITY_SUMMARY.md").write_text("\n".join(md_s), encoding="utf-8")

    print()
    print("FINAL FLAGS:")
    for k, v in flags.items():
        print(f"  {k:<48s} = {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
