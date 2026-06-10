"""OKX direct partial March 2026 profitability / Telegram-signal sanity check (READ-ONLY).

Mirrors scripts/binance-live/tardis_2025_profitability_sanity.py but on OKX direct March data.

Inputs:
  reports/BTC-USDT-SWAP_2026-03-DD/zones.json     (per-zone dump from backtestDay)
  data/okx-historical/BTC-USDT-SWAP/2026-03-DD/trades.csv.gz  (Tardis-compat CSV.gz)
  reports/okx-direct/OKX_DIRECT_TECHNICAL_REPLAY_2026-03-DD.json  (wrapper, used as fallback)

Outputs (in reports/okx-direct/):
  OKX_DIRECT_MARCH_TELEGRAM_SIGNAL_SIMULATION.{csv,json}
  OKX_DIRECT_MARCH_DIRECTION_CORRECTNESS.{md,json,csv}
  OKX_DIRECT_MARCH_PRE_COST_TRADE_LEDGER.{csv,json}
  OKX_DIRECT_MARCH_PROFITABILITY_SANITY.{md,json}
  OKX_DIRECT_MARCH_BASELINE_VS_FILTERED_EXECUTION.{md,json}
  OKX_DIRECT_MARCH_PRIMARY_UNIQUE_MOVES_AUDIT.{md,json}
  OKX_DIRECT_MARCH_VS_BINANCE_TARDIS_2025_COMPARISON.{md,json}
  OKX_DIRECT_MARCH_STRATEGY_PROFITABILITY_SANITY_SUMMARY.{md,json}

NO strategy / threshold / engine change. NO new backtest. Pre-cost main metric;
cost-aware diagnostic with fee_roundtrip 0.08% + slippage {0.02, 0.06, 0.10}%.
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

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "package.json").exists() and (p / "scripts").exists())
REPORTS = ROOT / "reports"
REPORTS_OKX = ROOT / "reports/okx-direct"
DATA_ROOT = ROOT / "data/okx-historical/BTC-USDT-SWAP"
SYMBOL = "BTC-USDT-SWAP"

DATES = [f"2026-03-{d:02d}" for d in range(2, 16)]   # 2026-03-02 .. 2026-03-15
WINDOW_MIN = 60
PRICE_BAND_PCT = 1.0
FAST_X_MIN = 60
TARGET_PCT = 2.0
STOP_PCT = 1.0
TIMEOUT_H = 24

# cost-aware diagnostic settings (NOT main metric)
FEE_ROUNDTRIP_PCT = 0.08
SLIPPAGE_SCENARIOS = [0.02, 0.06, 0.10]   # roundtrip slippage %


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


# ---------- live-valid filter ----------

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


# ---------- 1s buckets ----------

def trades_buckets_high_low(date: str) -> list[tuple[int, float, float, float]]:
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


def day_feasibility(buckets: list[tuple[int, float, float, float]]) -> dict:
    """Compute day-level 24h forward up/down % from buckets (used as diagnostic only)."""
    if not buckets:
        return {"open": None, "high": None, "low": None, "close": None,
                "max_24h_up_pct": 0.0, "max_24h_down_pct": 0.0}
    open_p = buckets[0][3]
    close_p = buckets[-1][3]
    high = max(b[1] for b in buckets)
    low = min(b[2] for b in buckets)
    # Forward max moves: for each anchor (entry at "last" within day), max future high - entry / entry
    # Use any-anchor convention as in regime tables
    secs = [b[0] for b in buckets]
    prices = [b[3] for b in buckets]
    highs = [b[1] for b in buckets]
    lows = [b[2] for b in buckets]
    h_24 = 24 * 3600
    max_up = 0.0
    max_down = 0.0
    from collections import deque
    dq_max = deque()
    dq_min = deque()
    j = 0
    N = len(buckets)
    for i in range(N):
        while j < N and secs[j] - secs[i] <= h_24:
            while dq_max and highs[dq_max[-1]] <= highs[j]:
                dq_max.pop()
            dq_max.append(j)
            while dq_min and lows[dq_min[-1]] >= lows[j]:
                dq_min.pop()
            dq_min.append(j)
            j += 1
        while dq_max and dq_max[0] < i:
            dq_max.popleft()
        while dq_min and dq_min[0] < i:
            dq_min.popleft()
        if dq_max and dq_min:
            p0 = prices[i]
            up = (highs[dq_max[0]] - p0) / p0 * 100.0
            dn = (p0 - lows[dq_min[0]]) / p0 * 100.0
            if up > max_up:
                max_up = up
            if dn > max_down:
                max_down = dn
    return {
        "open": open_p, "high": high, "low": low, "close": close_p,
        "day_return_pct": round((close_p - open_p) / open_p * 100.0, 4) if open_p else None,
        "day_range_pct": round((high - low) / low * 100.0, 4) if low > 0 else None,
        "max_24h_up_pct": round(max_up, 4),
        "max_24h_down_pct": round(max_down, 4),
    }


# ---------- trade simulation ----------

def simulate_trade(z: dict, buckets: list[tuple[int, float, float, float]]) -> dict:
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


# ---------- load ----------

def load_zones() -> list[dict]:
    out: list[dict] = []
    for d in DATES:
        p_full = REPORTS / f"BTC-USDT-SWAP_{d}" / "zones.json"
        p_wrap = REPORTS_OKX / f"OKX_DIRECT_TECHNICAL_REPLAY_{d}.json"
        zones = []
        if p_full.exists():
            obj = json.loads(p_full.read_text(encoding="utf-8"))
            zones = obj if isinstance(obj, list) else obj.get("zones", [])
        elif p_wrap.exists():
            wrap = json.loads(p_wrap.read_text(encoding="utf-8"))
            zones = (wrap.get("underlying_backtest_summary") or {}).get("zones") or []
        else:
            print(f"  WARN: no zones for {d}", file=sys.stderr)
            continue
        for z in zones:
            z["_date"] = d
            z["_class"] = class_label(z)
        out.extend(zones)
    return out


# ---------- aggregation ----------

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
    max_cons_losses = 0
    cur = 0
    for t in trades:
        if (t["pnl_pct"] or 0) < 0:
            cur += 1
            if cur > max_cons_losses:
                max_cons_losses = cur
        else:
            cur = 0
    long_trades = [t for t in trades if t["direction"] == "LONG"]
    short_trades = [t for t in trades if t["direction"] == "SHORT"]
    long_pnls = [t["pnl_pct"] for t in long_trades if t["pnl_pct"] is not None]
    short_pnls = [t["pnl_pct"] for t in short_trades if t["pnl_pct"] is not None]
    by_day = defaultdict(list)
    for t in trades:
        if t["pnl_pct"] is not None:
            by_day[t["date"]].append(t["pnl_pct"])
    best_day = max(by_day.items(), key=lambda kv: sum(kv[1]), default=(None, []))
    worst_day = min(by_day.items(), key=lambda kv: sum(kv[1]), default=(None, []))
    depends = False
    if pnls:
        total = sum(pnls)
        if best_day[1]:
            best_sum = sum(best_day[1])
            depends = total > 0 and best_sum > total
    # exit-reason breakdown
    pnl_from_wins = sum(t["pnl_pct"] for t in trades if t["exit_reason"] == "target_2pct")
    pnl_from_losses = sum(t["pnl_pct"] for t in trades if t["exit_reason"] == "stop_1pct")
    timeout_pnls = [t["pnl_pct"] for t in trades if t["exit_reason"] == "timeout" and t["pnl_pct"] is not None]
    pnl_from_timeouts = sum(timeout_pnls)
    timeout_positive = sum(1 for p in timeout_pnls if p > 0.05)
    timeout_negative = sum(1 for p in timeout_pnls if p < -0.05)
    timeout_nearzero = sum(1 for p in timeout_pnls if -0.05 <= p <= 0.05)
    # expectancy if timeouts forced to 0
    pnls_to_force = [t["pnl_pct"] if t["exit_reason"] != "timeout" else 0.0 for t in trades]
    expectancy_timeouts_zero = stats.mean(pnls_to_force) if pnls_to_force else None
    # expectancy if timeouts conservatively treated as -0.5% (small adverse)
    pnls_conservative = [
        t["pnl_pct"] if t["exit_reason"] != "timeout" else -0.5 for t in trades
    ]
    expectancy_timeouts_conservative = stats.mean(pnls_conservative) if pnls_conservative else None
    return {
        "n_trades": n,
        "wins": wins, "losses": losses, "timeouts": timeouts,
        "winrate_pct": round(100.0 * wins / n, 2) if n else None,
        "avg_win_pct": round(stats.mean(wins_pnls), 4) if wins_pnls else None,
        "avg_loss_pct": round(stats.mean(losses_pnls), 4) if losses_pnls else None,
        "expectancy_pct_per_trade": round(stats.mean(pnls), 4) if pnls else None,
        "total_return_pct_1unit": round(sum(pnls), 4) if pnls else None,
        "profit_factor": round(gross_w / gross_l, 3) if gross_l > 0 else (None if gross_w == 0 else float("inf")),
        "max_consecutive_losses": max_cons_losses,
        "best_day": {"date": best_day[0], "sum_pnl_pct": round(sum(best_day[1]), 4) if best_day[0] else None},
        "worst_day": {"date": worst_day[0], "sum_pnl_pct": round(sum(worst_day[1]), 4) if worst_day[0] else None},
        "long_n": len(long_trades), "long_expectancy_pct": round(stats.mean(long_pnls), 4) if long_pnls else None,
        "short_n": len(short_trades), "short_expectancy_pct": round(stats.mean(short_pnls), 4) if short_pnls else None,
        "result_depends_on_one_day": depends,
        "exit_breakdown": {
            "pnl_from_wins": round(pnl_from_wins, 4),
            "pnl_from_losses": round(pnl_from_losses, 4),
            "pnl_from_timeouts": round(pnl_from_timeouts, 4),
            "timeout_positive_count": timeout_positive,
            "timeout_negative_count": timeout_negative,
            "timeout_nearzero_count": timeout_nearzero,
            "expectancy_if_timeouts_zero": round(expectancy_timeouts_zero, 4) if expectancy_timeouts_zero is not None else None,
            "expectancy_if_timeouts_negative_0_5pct": round(expectancy_timeouts_conservative, 4) if expectancy_timeouts_conservative is not None else None,
        },
    }


def cost_aware_aggregate(trades: list[dict], cost_pct_roundtrip: float) -> dict:
    """Apply flat cost_pct_roundtrip to pnl per trade and re-aggregate."""
    adjusted = []
    for t in trades:
        if t["pnl_pct"] is None:
            adjusted.append(dict(t))
            continue
        nt = dict(t)
        nt["pnl_pct"] = round(t["pnl_pct"] - cost_pct_roundtrip, 4)
        adjusted.append(nt)
    return aggregate(adjusted)


def pct(num, den):
    if not den:
        return None
    return round(100.0 * num / den, 2)


def main() -> int:
    REPORTS_OKX.mkdir(parents=True, exist_ok=True)
    print("loading zones ...", file=sys.stderr)
    zones = load_zones()
    decisions = apply_filter(zones)
    triggered = [z for z in zones if is_triggered(z) and z.get("triggerTs") is not None]
    triggered.sort(key=lambda z: z["triggerTs"])
    print(f"  {len(triggered)} triggered zones", file=sys.stderr)

    # build 1s buckets per date
    print("building 1s buckets per date ...", file=sys.stderr)
    buckets_by_date: dict[str, list] = {}
    feas_by_date: dict[str, dict] = {}
    for d in DATES:
        print(f"  {d} ...", file=sys.stderr)
        buckets_by_date[d] = trades_buckets_high_low(d)
        feas_by_date[d] = day_feasibility(buckets_by_date[d])

    # ---------- A. Telegram signal simulation (filtered only) ----------
    print("[A] Telegram signal simulation ...", file=sys.stderr)
    filtered_signals = [z for z in triggered if decisions.get(z["id"], {}).get("kept")]
    sim_rows: list[dict] = []
    for z in filtered_signals:
        sim = simulate_trade(z, buckets_by_date[z["_date"]])
        sim_rows.append({
            "date": z["_date"], "zone_id": z["id"],
            "triggerTs": z["triggerTs"], "triggerTs_iso": ms_to_iso(z["triggerTs"]),
            "direction": z["direction"], "engine_status": z["status"], "class_label": z["_class"],
            "entry_price": sim["entry_price"], "target_price": sim["target_price"],
            "zoneLow": z.get("zoneLow"), "zoneHigh": z.get("zoneHigh"),
            "reached_2pct": sim["exit_reason"] == "target_2pct",
            "exit_reason": sim["exit_reason"], "exit_iso": sim["exit_iso"],
            "exit_price": sim["exit_price"], "pnl_pct": sim["pnl_pct"],
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
    unique_2pct_moves_captured = sum(1 for r in sim_rows if r["engine_isPrimaryMoveZone"] and r["reached_2pct"])

    sim_json = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "scope": "Filtered triggered zones across OKX direct partial March 2026 (2026-03-02..2026-03-15), live-valid filter",
        "n_telegram_alerts": n_alerts,
        "alerts_per_day": round(n_alerts / len(DATES), 3),
        "long_alerts": n_long, "short_alerts": n_short,
        "reached_2pct_count": n_reached,
        "reached_2pct_rate_pct": reached_rate,
        "failed_or_timeout_count": n_failed,
        "unique_2pct_moves_captured": unique_2pct_moves_captured,
        "rows": sim_rows,
    }
    (REPORTS_OKX / "OKX_DIRECT_MARCH_TELEGRAM_SIGNAL_SIMULATION.json").write_text(
        json.dumps(sim_json, indent=2, default=str), encoding="utf-8")
    keys = ["date", "zone_id", "triggerTs_iso", "direction", "engine_status", "class_label",
            "entry_price", "target_price", "exit_reason", "exit_iso", "exit_price",
            "pnl_pct", "mfe_pct", "mae_pct", "time_in_trade_h", "reached_2pct",
            "engine_isPrimaryMoveZone"]
    with (REPORTS_OKX / "OKX_DIRECT_MARCH_TELEGRAM_SIGNAL_SIMULATION.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        for r in sim_rows:
            w.writerow(r)

    # ---------- B. Direction correctness ----------
    print("[B] direction correctness ...", file=sys.stderr)
    dir_rows = []
    days_up = 0; days_down = 0; days_both = 0; days_no = 0
    correct_dir_days = 0; missed_opp_days = 0
    wrong_dir_alert_days = 0; wrong_dir_alerts_total = 0
    signals_matching = 0; signals_against = 0
    reached_matching_dir = 0
    for d in DATES:
        fz = feas_by_date.get(d, {})
        up_feas = (fz.get("max_24h_up_pct") or 0) >= 2.0
        down_feas = (fz.get("max_24h_down_pct") or 0) >= 2.0
        if up_feas and down_feas: days_both += 1
        elif up_feas: days_up += 1
        elif down_feas: days_down += 1
        else: days_no += 1
        day_signals = [r for r in sim_rows if r["date"] == d]
        n_long_d = sum(1 for r in day_signals if r["direction"] == "LONG")
        n_short_d = sum(1 for r in day_signals if r["direction"] == "SHORT")
        n_reached_d = sum(1 for r in day_signals if r["reached_2pct"])
        any_feasible = up_feas or down_feas
        sent_long_when_up = up_feas and n_long_d > 0
        sent_short_when_down = down_feas and n_short_d > 0
        any_match = sent_long_when_up or sent_short_when_down
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
            if n_long_d + n_short_d > 0:
                wrong_dir_alert_days += 1
                wrong_alerts_today = n_long_d + n_short_d
        wrong_dir_alerts_total += wrong_alerts_today
        signals_against += wrong_alerts_today
        dir_rows.append({
            "date": d,
            "day_return_pct": fz.get("day_return_pct"),
            "day_range_pct": fz.get("day_range_pct"),
            "max_24h_up_pct": fz.get("max_24h_up_pct"),
            "max_24h_down_pct": fz.get("max_24h_down_pct"),
            "up_2pct_feasible": up_feas, "down_2pct_feasible": down_feas,
            "n_long_alerts": n_long_d, "n_short_alerts": n_short_d,
            "n_reached_2pct": n_reached_d,
            "verdict": (
                "BOTH_FEASIBLE" if up_feas and down_feas
                else "UP_ONLY" if up_feas
                else "DOWN_ONLY" if down_feas
                else "NEITHER"
            ),
            "direction_correct": (None if not any_feasible else ("YES" if any_match else "NO")),
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
    (REPORTS_OKX / "OKX_DIRECT_MARCH_DIRECTION_CORRECTNESS.json").write_text(
        json.dumps(dir_json, indent=2, default=str), encoding="utf-8")
    keys = ["date", "day_return_pct", "day_range_pct", "max_24h_up_pct", "max_24h_down_pct",
            "up_2pct_feasible", "down_2pct_feasible", "verdict",
            "n_long_alerts", "n_short_alerts", "n_reached_2pct",
            "direction_correct", "wrong_direction_alerts"]
    with (REPORTS_OKX / "OKX_DIRECT_MARCH_DIRECTION_CORRECTNESS.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in dir_rows:
            w.writerow(r)
    md_dir = [
        "# OKX direct partial March 2026 - direction correctness",
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
        "", "## Summary", "",
        f"- days with up 2 % feasible: **{dir_json['days_with_up_2pct']} / 14**",
        f"- days with down 2 % feasible: **{dir_json['days_with_down_2pct']} / 14**",
        f"- days with both 2 % feasible: **{dir_json['days_with_both_2pct']}**",
        f"- days with NO 2 % feasible: **{dir_json['days_with_no_2pct']}**",
        f"- correct-direction days: **{dir_json['correct_direction_days']}**",
        f"- missed-opportunity days: **{dir_json['missed_opportunity_days']}**",
        f"- wrong-direction-alert days: **{dir_json['wrong_direction_alert_days']}**",
        f"- filtered signals against only-feasible direction: **{dir_json['filtered_signals_against_only_feasible_direction']}**",
        f"- filtered signals matching feasible direction: **{dir_json['filtered_signals_matching_feasible_direction']}**",
        f"- reached 2 % matching direction: **{dir_json['reached_2pct_matching_direction']}**",
    ])
    (REPORTS_OKX / "OKX_DIRECT_MARCH_DIRECTION_CORRECTNESS.md").write_text("\n".join(md_dir), encoding="utf-8")

    # ---------- C. Trade ledger ----------
    print("[C] trade ledger ...", file=sys.stderr)
    mode1_trades = [{**r, "_mode": "mode1_alert_level"} for r in sim_rows]
    sorted_signals = sorted(sim_rows, key=lambda r: r["triggerTs"])
    mode2_trades = []
    skipped = []
    open_until_ts_sec = -1
    for r in sorted_signals:
        trig_sec = r["triggerTs"] // 1000
        if trig_sec < open_until_ts_sec:
            skipped.append({"zone_id": r["zone_id"], "reason": "position_open",
                            "open_until_iso": ms_to_iso(open_until_ts_sec * 1000)})
            continue
        mode2_trades.append({**r, "_mode": "mode2_strict_ledger"})
        time_h = r["time_in_trade_h"] or 0
        open_until_ts_sec = trig_sec + int(time_h * 3600)

    mode1_agg = aggregate(mode1_trades)
    mode2_agg = aggregate(mode2_trades)

    # cost-aware diagnostics
    cost_diag_mode2: dict[str, dict] = {}
    for slip in SLIPPAGE_SCENARIOS:
        cost_pct = FEE_ROUNDTRIP_PCT + slip
        cost_diag_mode2[f"fees{FEE_ROUNDTRIP_PCT}_slip{slip}"] = cost_aware_aggregate(mode2_trades, cost_pct)
    cost_diag_mode1: dict[str, dict] = {}
    for slip in SLIPPAGE_SCENARIOS:
        cost_pct = FEE_ROUNDTRIP_PCT + slip
        cost_diag_mode1[f"fees{FEE_ROUNDTRIP_PCT}_slip{slip}"] = cost_aware_aggregate(mode1_trades, cost_pct)

    ledger_json = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "scope": "OKX direct partial March 2026 (14 dates) pre-cost trade simulation; target 2 %, stop 1 %, timeout 24 h",
        "execution_model": {
            "target_pct": TARGET_PCT, "stop_pct": STOP_PCT, "timeout_hours": TIMEOUT_H,
            "tiebreak_target_and_stop_same_bucket": "stop_first_conservative",
            "PRE_COST_ONLY_MAIN": "YES",
            "FEES_SLIPPAGE_INCLUDED_MAIN": "NO",
        },
        "mode1_alert_level": {"trades": mode1_trades, "aggregate": mode1_agg,
                               "cost_aware_diagnostic": cost_diag_mode1},
        "mode2_strict_ledger": {
            "trades": mode2_trades, "aggregate": mode2_agg,
            "n_skipped_due_to_open_position": len(skipped),
            "skipped_examples": skipped[:20],
            "cost_aware_diagnostic": cost_diag_mode2,
        },
        "cost_assumptions": {
            "fee_roundtrip_pct": FEE_ROUNDTRIP_PCT,
            "slippage_scenarios_roundtrip_pct": SLIPPAGE_SCENARIOS,
            "note": "Cost = fee + slippage subtracted flat from each trade's pnl_pct.",
        },
    }
    (REPORTS_OKX / "OKX_DIRECT_MARCH_PRE_COST_TRADE_LEDGER.json").write_text(
        json.dumps(ledger_json, indent=2, default=str), encoding="utf-8")
    led_keys = ["mode", "date", "zone_id", "direction", "triggerTs_iso", "entry_price",
                "target_price", "exit_reason", "exit_iso", "exit_price",
                "pnl_pct", "mfe_pct", "mae_pct", "time_in_trade_h"]
    with (REPORTS_OKX / "OKX_DIRECT_MARCH_PRE_COST_TRADE_LEDGER.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=led_keys)
        w.writeheader()
        for set_name, lst in [("mode1", mode1_trades), ("mode2", mode2_trades)]:
            for t in lst:
                w.writerow({
                    "mode": set_name, "date": t["date"], "zone_id": t["zone_id"],
                    "direction": t["direction"], "triggerTs_iso": t["triggerTs_iso"],
                    "entry_price": t["entry_price"], "target_price": t["target_price"],
                    "exit_reason": t["exit_reason"], "exit_iso": t["exit_iso"],
                    "exit_price": t["exit_price"], "pnl_pct": t["pnl_pct"],
                    "mfe_pct": t["mfe_pct"], "mae_pct": t["mae_pct"],
                    "time_in_trade_h": t["time_in_trade_h"],
                })

    # ---------- D. Profitability sanity ----------
    print("[D] profitability sanity ...", file=sys.stderr)
    md_p = [
        "# OKX direct partial March 2026 - profitability sanity (pre-cost + cost diagnostic)",
        "",
        f"**Build:** {ledger_json['build_time_utc']}",
        "**Main metric: `PRE_COST_ONLY = YES`.**",
        "**Cost diagnostic: fee_roundtrip = 0.08 %, slippage scenarios {0.02, 0.06, 0.10} %.**",
        "**Target = 2 % strict. Stop = 1 % fixed. Timeout = 24h.**",
        "",
        "## MODE 1 (alert-level, pre-cost)",
        "",
        "| metric | value |",
        "|---|---:|",
    ]
    for k, v in mode1_agg.items():
        if isinstance(v, dict):
            if "date" in v:
                md_p.append(f"| {k} | {v.get('date')} ({v.get('sum_pnl_pct')}%) |")
            else:
                md_p.append(f"| {k} | _see exit_breakdown table below_ |")
        else:
            md_p.append(f"| {k} | {v} |")
    md_p.extend(["", "## MODE 1 exit-reason breakdown (pre-cost)", "",
                 "| metric | value |", "|---|---:|"])
    for k, v in (mode1_agg.get("exit_breakdown") or {}).items():
        md_p.append(f"| {k} | {v} |")
    md_p.extend(["", "## MODE 1 cost-aware diagnostic", "",
                 "| cost scenario (roundtrip %) | expectancy %/trade | profit factor | winrate % | total return % |",
                 "|---|---:|---:|---:|---:|"])
    for k, agg in cost_diag_mode1.items():
        cost_pct = FEE_ROUNDTRIP_PCT + float(k.split("_slip")[-1])
        md_p.append(f"| {cost_pct:.2f} ({k}) | {agg['expectancy_pct_per_trade']} | "
                    f"{agg['profit_factor']} | {agg['winrate_pct']} | {agg['total_return_pct_1unit']} |")

    md_p.extend(["", "## MODE 2 (strict ledger, pre-cost)", "",
                 f"- skipped due to open position: **{len(skipped)}**", "",
                 "| metric | value |", "|---|---:|"])
    for k, v in mode2_agg.items():
        if isinstance(v, dict):
            if "date" in v:
                md_p.append(f"| {k} | {v.get('date')} ({v.get('sum_pnl_pct')}%) |")
            else:
                md_p.append(f"| {k} | _see exit_breakdown table below_ |")
        else:
            md_p.append(f"| {k} | {v} |")
    md_p.extend(["", "## MODE 2 exit-reason breakdown (pre-cost)", "",
                 "| metric | value |", "|---|---:|"])
    for k, v in (mode2_agg.get("exit_breakdown") or {}).items():
        md_p.append(f"| {k} | {v} |")
    md_p.extend(["", "## MODE 2 cost-aware diagnostic", "",
                 "| cost scenario (roundtrip %) | expectancy %/trade | profit factor | winrate % | total return % |",
                 "|---|---:|---:|---:|---:|"])
    for k, agg in cost_diag_mode2.items():
        cost_pct = FEE_ROUNDTRIP_PCT + float(k.split("_slip")[-1])
        md_p.append(f"| {cost_pct:.2f} ({k}) | {agg['expectancy_pct_per_trade']} | "
                    f"{agg['profit_factor']} | {agg['winrate_pct']} | {agg['total_return_pct_1unit']} |")
    (REPORTS_OKX / "OKX_DIRECT_MARCH_PROFITABILITY_SANITY.md").write_text("\n".join(md_p), encoding="utf-8")
    (REPORTS_OKX / "OKX_DIRECT_MARCH_PROFITABILITY_SANITY.json").write_text(
        json.dumps({"mode1_pre_cost": mode1_agg, "mode2_pre_cost": mode2_agg,
                    "mode1_cost_aware": cost_diag_mode1,
                    "mode2_cost_aware": cost_diag_mode2,
                    "skipped_count_mode2": len(skipped)},
                   indent=2, default=str), encoding="utf-8")

    # ---------- E. Baseline vs filtered ----------
    print("[E] baseline vs filtered execution ...", file=sys.stderr)
    baseline_trades_raw = []
    for z in triggered:
        sim = simulate_trade(z, buckets_by_date[z["_date"]])
        baseline_trades_raw.append({**sim, "date": z["_date"], "zone_id": z["id"],
                                    "direction": z["direction"]})
    # Baseline strict ledger
    sorted_b = sorted(baseline_trades_raw, key=lambda r: r["entry_ts"])
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

    base1 = aggregate(to_pnl_trades(baseline_trades_raw))
    base2 = aggregate(to_pnl_trades(baseline_mode2))

    # wrong-direction baseline
    base_wrong_dir = 0
    for z in triggered:
        d = z["_date"]
        fz = feas_by_date.get(d, {})
        up_feas = (fz.get("max_24h_up_pct") or 0) >= 2.0
        down_feas = (fz.get("max_24h_down_pct") or 0) >= 2.0
        if up_feas and not down_feas and z["direction"] == "SHORT":
            base_wrong_dir += 1
        elif down_feas and not up_feas and z["direction"] == "LONG":
            base_wrong_dir += 1
        elif not up_feas and not down_feas:
            base_wrong_dir += 1

    bf_json = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "baseline": {
            "n_triggered": len(triggered), "wrong_direction_alerts": base_wrong_dir,
            "mode1_aggregate": base1, "mode2_aggregate": base2, "mode2_skipped": base_skipped,
        },
        "filtered": {
            "n_triggered": n_alerts, "wrong_direction_alerts": wrong_dir_alerts_total,
            "mode1_aggregate": mode1_agg, "mode2_aggregate": mode2_agg, "mode2_skipped": len(skipped),
        },
    }
    (REPORTS_OKX / "OKX_DIRECT_MARCH_BASELINE_VS_FILTERED_EXECUTION.json").write_text(
        json.dumps(bf_json, indent=2, default=str), encoding="utf-8")
    md_bf = [
        "# OKX direct partial March 2026 - baseline vs filtered execution (pre-cost)",
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
    (REPORTS_OKX / "OKX_DIRECT_MARCH_BASELINE_VS_FILTERED_EXECUTION.md").write_text("\n".join(md_bf), encoding="utf-8")

    # ---------- F. Primary unique audit ----------
    print("[F] primary unique moves audit ...", file=sys.stderr)
    primaries = [z for z in zones if z.get("isPrimaryMoveZone") and z.get("status") == "RESOLVED_REACHED"]
    audit = []
    for z in primaries:
        dec = decisions.get(z["id"], {})
        kept = dec.get("kept", False)
        lost_reason = dec.get("lost_reason")
        sim = simulate_trade(z, buckets_by_date[z["_date"]])
        fz = feas_by_date.get(z["_date"], {})
        was_in_ledger = any(t["zone_id"] == z["id"] for t in mode2_trades)
        was_skipped_in_ledger = any(s["zone_id"] == z["id"] for s in skipped)
        audit.append({
            "date": z["_date"], "zone_id": z["id"], "direction": z["direction"],
            "day_return_pct": fz.get("day_return_pct"),
            "max_24h_up_pct": fz.get("max_24h_up_pct"),
            "max_24h_down_pct": fz.get("max_24h_down_pct"),
            "confirm_to_trigger_min": dec.get("confirm_to_trigger_min"),
            "filter_kept": kept, "lost_reason": lost_reason or "kept_by_filter",
            "trade_target_reached_in_sim": sim["exit_reason"] == "target_2pct",
            "sim_exit_reason": sim["exit_reason"], "sim_pnl_pct": sim["pnl_pct"],
            "sim_time_in_trade_h": sim["time_in_trade_h"],
            "telegram_alert_would_have_been_sent": kept,
            "strict_ledger_took_this_trade": was_in_ledger,
            "strict_ledger_skipped_due_position_open": was_skipped_in_ledger,
        })
    (REPORTS_OKX / "OKX_DIRECT_MARCH_PRIMARY_UNIQUE_MOVES_AUDIT.json").write_text(
        json.dumps(audit, indent=2, default=str), encoding="utf-8")
    md_au = [
        "# OKX direct partial March 2026 - audit of primary unique moves",
        "",
        f"**Build:** {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}",
        "**Each row = engine-flagged primary_unique_reached_move zone; filter decision audit + sim-trade outcome at target 2 % / stop 1 % / timeout 24 h.**",
        "",
        "| date | day Δ % | 24h up % | 24h dn % | direction | conf->trig min | filter kept | lost reason | sim exit | sim pnl % | sim time (h) | telegram | strict ledger took |",
        "|---|---:|---:|---:|---|---:|:---:|---|---|---:|---:|:---:|:---:|",
    ]
    for r in audit:
        md_au.append(
            f"| {r['date']} | {r['day_return_pct']} | {r['max_24h_up_pct']} | "
            f"{r['max_24h_down_pct']} | {r['direction']} | {r['confirm_to_trigger_min']} | "
            f"{'YES' if r['filter_kept'] else 'NO'} | {r['lost_reason']} | "
            f"{r['sim_exit_reason']} | {r['sim_pnl_pct']} | {r['sim_time_in_trade_h']} | "
            f"{'YES' if r['telegram_alert_would_have_been_sent'] else 'NO'} | "
            f"{'YES' if r['strict_ledger_took_this_trade'] else 'NO'} |"
        )
    md_au.extend(["", "## Counts", "",
                  f"- total primary unique reached zones: **{len(audit)}**",
                  f"- kept by filter: **{sum(1 for r in audit if r['filter_kept'])}**",
                  f"- lost by filter: **{sum(1 for r in audit if not r['filter_kept'])}**",
                  f"- target reached in sim: **{sum(1 for r in audit if r['trade_target_reached_in_sim'])}**",
                  f"- strict-ledger took: **{sum(1 for r in audit if r['strict_ledger_took_this_trade'])}**",
                  f"- strict-ledger skipped due to open position: **{sum(1 for r in audit if r['strict_ledger_skipped_due_position_open'])}**"])
    (REPORTS_OKX / "OKX_DIRECT_MARCH_PRIMARY_UNIQUE_MOVES_AUDIT.md").write_text("\n".join(md_au), encoding="utf-8")

    # ---------- G. Compare with Binance Tardis 2025 ----------
    print("[G] vs Binance Tardis 2025 ...", file=sys.stderr)
    binance = {
        "scope": "Binance Tardis 2025 first-of-month (12 days)",
        "telegram_alerts": 58, "alerts_per_day": 4.833,
        "reached_2pct": 8, "reached_rate_pct": 13.79,
        "wrong_direction_alerts": 10,
        "correct_direction_days": 11, "missed_opp_days": 0,
        "primary_recall_pct": 71.43,
        "strict_ledger_trades": 19, "strict_ledger_wins": 5,
        "strict_ledger_losses": 3, "strict_ledger_timeouts": 11,
        "strict_ledger_winrate_pct": 26.32,
        "strict_ledger_expectancy_pre_cost": 0.6423,
        "strict_ledger_profit_factor_pre_cost": 3.68,
        "long_expectancy_pct": 0.7827, "short_expectancy_pct": 0.4864,
        "note": "bullish LONG weakness (2/4 primary lost: 2025-04-01, 2025-10-01)",
    }
    okx_strict = mode2_agg
    n_kept_primary = sum(1 for r in audit if r["filter_kept"])
    primary_recall = round(100.0 * n_kept_primary / len(audit), 2) if audit else None
    okx_block = {
        "scope": "OKX direct partial March 2026 (14 days)",
        "telegram_alerts": n_alerts, "alerts_per_day": round(n_alerts / 14, 3),
        "reached_2pct": n_reached, "reached_rate_pct": reached_rate,
        "wrong_direction_alerts": wrong_dir_alerts_total,
        "correct_direction_days": dir_json["correct_direction_days"],
        "missed_opp_days": dir_json["missed_opportunity_days"],
        "primary_recall_pct": primary_recall,
        "strict_ledger_trades": okx_strict["n_trades"], "strict_ledger_wins": okx_strict["wins"],
        "strict_ledger_losses": okx_strict["losses"], "strict_ledger_timeouts": okx_strict["timeouts"],
        "strict_ledger_winrate_pct": okx_strict["winrate_pct"],
        "strict_ledger_expectancy_pre_cost": okx_strict["expectancy_pct_per_trade"],
        "strict_ledger_profit_factor_pre_cost": okx_strict["profit_factor"],
        "long_expectancy_pct": okx_strict["long_expectancy_pct"],
        "short_expectancy_pct": okx_strict["short_expectancy_pct"],
    }
    compares_well = "UNKNOWN"
    if okx_strict["expectancy_pct_per_trade"] is not None and okx_strict["expectancy_pct_per_trade"] > 0 \
            and (okx_strict["profit_factor"] or 0) > 1.2:
        compares_well = "YES"
    elif (okx_strict["expectancy_pct_per_trade"] or 0) <= 0:
        compares_well = "NO"
    cmp_json = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "binance_tardis_2025": binance, "okx_direct_march_2026": okx_block,
        "compares_well": compares_well,
    }
    (REPORTS_OKX / "OKX_DIRECT_MARCH_VS_BINANCE_TARDIS_2025_COMPARISON.json").write_text(
        json.dumps(cmp_json, indent=2, default=str), encoding="utf-8")
    md_cmp = [
        "# Binance Tardis 2025 vs OKX direct March 2026 - cross-venue comparison",
        "",
        f"**Build:** {cmp_json['build_time_utc']}",
        "**Same passive filter (live-valid), same target=2 %, stop=1 %, timeout=24h.**",
        "",
        "| metric | Binance Tardis 2025 (12d) | OKX direct March 2026 (14d) |",
        "|---|---:|---:|",
    ]
    for k in ("telegram_alerts", "alerts_per_day", "reached_2pct", "reached_rate_pct",
              "wrong_direction_alerts", "correct_direction_days", "missed_opp_days",
              "primary_recall_pct",
              "strict_ledger_trades", "strict_ledger_wins", "strict_ledger_losses",
              "strict_ledger_timeouts", "strict_ledger_winrate_pct",
              "strict_ledger_expectancy_pre_cost", "strict_ledger_profit_factor_pre_cost",
              "long_expectancy_pct", "short_expectancy_pct"):
        md_cmp.append(f"| {k} | {binance.get(k)} | {okx_block.get(k)} |")
    md_cmp.extend(["", f"`COMPARES_WELL_WITH_BINANCE_TARDIS_2025` = **{compares_well}**", ""])
    (REPORTS_OKX / "OKX_DIRECT_MARCH_VS_BINANCE_TARDIS_2025_COMPARISON.md").write_text("\n".join(md_cmp), encoding="utf-8")

    # ---------- H. Final summary ----------
    print("[H] final summary ...", file=sys.stderr)
    expectancy_positive_mode2 = (okx_strict["expectancy_pct_per_trade"] or 0) > 0
    # After-basic-cost (use middle slippage 0.06% scenario)
    mid_key = f"fees{FEE_ROUNDTRIP_PCT}_slip0.06"
    after_cost_mid = cost_diag_mode2[mid_key]
    after_cost_expectancy_positive = (after_cost_mid["expectancy_pct_per_trade"] or 0) > 0

    filter_improves_expectancy = "UNKNOWN"
    if base2.get("expectancy_pct_per_trade") is not None and okx_strict.get("expectancy_pct_per_trade") is not None:
        if okx_strict["expectancy_pct_per_trade"] > base2["expectancy_pct_per_trade"] + 0.05:
            filter_improves_expectancy = "YES"
        elif okx_strict["expectancy_pct_per_trade"] < base2["expectancy_pct_per_trade"] - 0.05:
            filter_improves_expectancy = "NO"
        else:
            filter_improves_expectancy = "UNCLEAR"

    strategy_probably_profitable = "UNKNOWN"
    if okx_strict["n_trades"] is not None and okx_strict["n_trades"] >= 10:
        if expectancy_positive_mode2 and (okx_strict["profit_factor"] or 0) > 1.2:
            strategy_probably_profitable = "YES"
        elif (okx_strict["expectancy_pct_per_trade"] or 0) <= 0:
            strategy_probably_profitable = "NO"

    flags = {
        "OKX_DIRECT_PROFITABILITY_SANITY_DONE": "YES",
        "TARGET_USED_FOR_PROFITABILITY": "2.0%",
        "OKX_TELEGRAM_ALERTS_TOTAL": n_alerts,
        "OKX_TELEGRAM_ALERTS_PER_DAY": round(n_alerts / 14, 3),
        "OKX_TELEGRAM_ALERTS_REACHED_2PCT": n_reached,
        "OKX_TELEGRAM_ALERT_REACHED_2PCT_RATE_PCT": reached_rate,
        "OKX_DAYS_WITH_2PCT_OPPORTUNITY": dir_json["days_with_up_2pct"] + dir_json["days_with_down_2pct"] - dir_json["days_with_both_2pct"],
        "OKX_DAYS_WITH_CORRECT_DIRECTION_SIGNAL": dir_json["correct_direction_days"],
        "OKX_DAYS_WITH_MISSED_2PCT_OPPORTUNITY": dir_json["missed_opportunity_days"],
        "OKX_WRONG_DIRECTION_ALERTS_TOTAL": wrong_dir_alerts_total,
        "OKX_FILTERED_PRIMARY_UNIQUE_KEPT": n_kept_primary,
        "OKX_FILTERED_PRIMARY_UNIQUE_TOTAL": len(audit),
        "OKX_FILTERED_PRIMARY_RECALL_PCT": primary_recall,
        "OKX_STRICT_LEDGER_TRADES": okx_strict["n_trades"],
        "OKX_STRICT_LEDGER_WINS": okx_strict["wins"],
        "OKX_STRICT_LEDGER_LOSSES": okx_strict["losses"],
        "OKX_STRICT_LEDGER_TIMEOUTS": okx_strict["timeouts"],
        "OKX_STRICT_LEDGER_WINRATE_PCT": okx_strict["winrate_pct"],
        "OKX_STRICT_LEDGER_EXPECTANCY_PRE_COST_PCT": okx_strict["expectancy_pct_per_trade"],
        "OKX_STRICT_LEDGER_PROFIT_FACTOR_PRE_COST": okx_strict["profit_factor"],
        "OKX_STRICT_LEDGER_EXPECTANCY_AFTER_BASIC_COST_PCT": after_cost_mid["expectancy_pct_per_trade"],
        "OKX_STRICT_LEDGER_PROFIT_FACTOR_AFTER_BASIC_COST": after_cost_mid["profit_factor"],
        "OKX_FILTER_IMPROVES_EXPECTANCY": filter_improves_expectancy,
        "OKX_PRE_COST_EXPECTANCY_POSITIVE": "YES" if expectancy_positive_mode2 else ("NO" if okx_strict["expectancy_pct_per_trade"] is not None else "UNKNOWN"),
        "OKX_AFTER_COST_EXPECTANCY_POSITIVE": "YES" if after_cost_expectancy_positive else ("NO" if after_cost_mid["expectancy_pct_per_trade"] is not None else "UNKNOWN"),
        "OKX_STRATEGY_PROBABLY_PROFITABLE_ON_THIS_SAMPLE": strategy_probably_profitable,
        "COMPARES_WELL_WITH_BINANCE_TARDIS_2025": compares_well,
        "READY_FOR_PASSIVE_LIVE_OBSERVER": "YES" if (primary_recall or 0) >= 70 else "NO",
        "READY_TO_INTEGRATE_FILTER_IN_STRATEGY": "NO",
        "MORE_VALIDATION_REQUIRED": "YES",
    }
    sumr_json = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "scope": "OKX direct partial March 2026 (2026-03-02..2026-03-15) — pre-cost sanity at strict 2 % target",
        "PRE_COST_ONLY_MAIN": "YES",
        "FEES_SLIPPAGE_INCLUDED_MAIN": "NO",
        "PROFITABILITY_CLAIM": "NO",
        "execution_model": {"target_pct": TARGET_PCT, "stop_pct": STOP_PCT, "timeout_h": TIMEOUT_H},
        "answers": {
            "telegram_alerts_14d": n_alerts,
            "reached_2pct": n_reached,
            "correct_direction_days": dir_json["correct_direction_days"],
            "wrong_direction_alerts": wrong_dir_alerts_total,
            "missed_2pct_opportunity_days": dir_json["missed_opportunity_days"],
            "filter_vs_baseline_mode2_expectancy_delta_pp": (
                round((okx_strict["expectancy_pct_per_trade"] or 0) - (base2["expectancy_pct_per_trade"] or 0), 4)
                if okx_strict["expectancy_pct_per_trade"] is not None
                and base2["expectancy_pct_per_trade"] is not None else None
            ),
            "pre_cost_expectancy_positive_mode2": expectancy_positive_mode2,
            "after_basic_cost_expectancy_positive": after_cost_expectancy_positive,
            "probably_profitable_on_this_sample": strategy_probably_profitable,
        },
        "flags": flags,
    }
    (REPORTS_OKX / "OKX_DIRECT_MARCH_STRATEGY_PROFITABILITY_SANITY_SUMMARY.json").write_text(
        json.dumps(sumr_json, indent=2, default=str), encoding="utf-8")

    md_s = [
        "# OKX direct partial March 2026 — strategy profitability sanity summary",
        "",
        f"**Build:** {sumr_json['build_time_utc']}",
        "**Main metric: `PRE_COST_ONLY = YES`. Cost diagnostic separate. `PROFITABILITY_CLAIM = NO`.**",
        "**Target 2 % strict.**",
        "",
        "## Answers",
        "",
        f"1. Telegram alerts for 14 days: **{n_alerts}** (~{round(n_alerts/14, 2)}/day)",
        f"2. Reached 2 % strict: **{n_reached}** (= {reached_rate} %)",
        f"3. Correct-direction days: **{dir_json['correct_direction_days']}** / 14",
        f"4. Wrong-direction alerts total: **{wrong_dir_alerts_total}**",
        f"5. Missed 2 % opportunity days: **{dir_json['missed_opportunity_days']}**",
        f"6. Filter vs baseline MODE-2 expectancy delta: "
        f"**{sumr_json['answers']['filter_vs_baseline_mode2_expectancy_delta_pp']} pp**",
        f"7. Pre-cost positive expectancy (MODE 2): **{'YES' if expectancy_positive_mode2 else 'NO'}**",
        f"8. After-basic-cost positive expectancy (MODE 2, fees+slip~0.14 %): "
        f"**{'YES' if after_cost_expectancy_positive else 'NO'}**",
        f"9. STRATEGY_PROBABLY_PROFITABLE_ON_THIS_SAMPLE = **{strategy_probably_profitable}**",
        "",
        "## Cross-venue compare (vs Binance Tardis 2025)",
        "",
        "| metric | Binance Tardis 2025 (12d, 19 trades) | OKX direct March 2026 (14d) |",
        "|---|---:|---:|",
        f"| strict ledger trades | 19 | {okx_strict['n_trades']} |",
        f"| winrate % | 26.32 | {okx_strict['winrate_pct']} |",
        f"| expectancy %/trade | +0.6423 | {okx_strict['expectancy_pct_per_trade']} |",
        f"| profit factor | 3.68 | {okx_strict['profit_factor']} |",
        f"| primary recall % | 71.43 | {primary_recall} |",
        f"| wrong-direction alerts | 10 | {wrong_dir_alerts_total} |",
        "",
        "## Final flag matrix",
        "",
        "```",
    ]
    for k, v in flags.items():
        md_s.append(f"{k} = {v}")
    md_s.append("```")
    md_s.extend(["", "## Hard rules honored",
                 "- strategy / thresholds / `zoneDetector`: UNCHANGED",
                 "- NO new backtest; pure post-hoc simulation over existing zones + price path",
                 "- NO `uniqueMoveId` in filter decision; NO future-leak in suppress",
                 "- target STRICT 2 % (no 0.5/1/1.5 considered as 'win')",
                 "- no production integration; no profitability claim"])
    (REPORTS_OKX / "OKX_DIRECT_MARCH_STRATEGY_PROFITABILITY_SANITY_SUMMARY.md").write_text("\n".join(md_s), encoding="utf-8")

    print()
    print("FINAL FLAGS:")
    for k, v in flags.items():
        print(f"  {k:<52s} = {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
