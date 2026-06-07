"""Python mirror of src/research/canonicalLedger.ts.

Single source of truth for the canonical strict-ledger model used by all
post-hoc research scripts. The TypeScript module is the spec; this Python
module reproduces the same algorithm 1:1 for scripts that need direct
CSV.gz price-path I/O.

Hard rules:
  - One trade at a time.
  - Position closes at FIRST of: target hit, stop hit, timeout.
  - The "next signal allowed" timestamp is the ACTUAL exit timestamp,
    NOT triggerTs + 24h. This fixes the prior 41-vs-13 bug.
  - Max holding = 24h from entry.
  - If target and stop hit in same 1s bucket: conservative => STOP FIRST.
  - Target strict 2 %.
  - No strategy / threshold / engine change. NO future-leak.
"""
from __future__ import annotations
import csv
import gzip
import statistics as stats
from collections import defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable, Literal


Direction = Literal["LONG", "SHORT"]
EntryStrategy = Literal["trigger", "delay_5m", "delay_10m", "delay_15m", "delay_30m", "retest"]


@dataclass(frozen=True)
class Bucket:
    sec: int       # unix seconds
    high: float
    low: float
    last: float    # last trade price within that second


@dataclass(frozen=True)
class Signal:
    id: str
    date: str
    trigger_ts_ms: int
    direction: Direction
    zone_low: float | None = None
    zone_high: float | None = None


@dataclass(frozen=True)
class ExecutionConfig:
    entry_strategy: EntryStrategy = "trigger"
    stop_pct: float = 1.0
    zone_boundary_stop: bool = False
    max_zone_boundary_or_pct: float | None = None
    retest_max_min: int = 60
    target_pct: float = 2.0
    timeout_hours: int = 24


@dataclass
class TradeRecord:
    zone_id: str
    date: str
    direction: Direction
    trigger_ts_ms: int
    entry_sec: int
    exit_sec: int
    entry_price: float
    exit_price: float
    exit_reason: str   # "target_2pct" | "stop" | "timeout"
    pnl_pct: float
    mfe_pct: float
    mae_pct: float
    time_in_trade_h: float
    used_stop_pct: float


@dataclass
class LedgerResult:
    trades: list[TradeRecord]
    skipped_due_to_position: int
    skipped_no_data: int
    skipped_no_retest: int


# ---------- 1s bucket I/O ----------

def build_buckets_from_trades_csv(path: Path) -> list[Bucket]:
    """Build per-second (high, low, last) from a Tardis-compat trades.csv.gz."""
    high: dict[int, float] = {}
    low: dict[int, float] = {}
    last: dict[int, float] = {}
    with gzip.open(path, "rt", encoding="utf-8", newline="") as f:
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
                if price > high[sec]: high[sec] = price
                if price < low[sec]: low[sec] = price
            else:
                high[sec] = price; low[sec] = price
            last[sec] = price
    return [Bucket(s, high[s], low[s], last[s]) for s in sorted(high.keys())]


# ---------- single-trade sim ----------

def _bucket_idx_at_or_after(buckets: list[Bucket], target_sec: int) -> int:
    lo, hi = 0, len(buckets)
    while lo < hi:
        m = (lo + hi) // 2
        if buckets[m].sec < target_sec:
            lo = m + 1
        else:
            hi = m
    return lo


def simulate_canonical_trade(sig: Signal, buckets: list[Bucket], cfg: ExecutionConfig) -> dict:
    """Returns either {"exit_reason": "no_data" | "skip_no_retest"} or a full success dict."""
    if not buckets:
        return {"exit_reason": "no_data"}
    trig_sec = sig.trigger_ts_ms // 1000

    # 1. Determine entry
    enter_idx = _bucket_idx_at_or_after(buckets, trig_sec)
    if cfg.entry_strategy == "trigger":
        pass
    elif cfg.entry_strategy.startswith("delay_"):
        m = int(cfg.entry_strategy.split("_")[1].rstrip("m"))
        enter_idx = _bucket_idx_at_or_after(buckets, trig_sec + m * 60)
    elif cfg.entry_strategy == "retest":
        if sig.zone_low is None or sig.zone_high is None:
            return {"exit_reason": "no_data"}
        gate_end = trig_sec + cfg.retest_max_min * 60
        found = -1
        for idx in range(enter_idx, len(buckets)):
            b = buckets[idx]
            if b.sec < trig_sec:
                continue
            if b.sec > gate_end:
                break
            if b.high >= sig.zone_low and b.low <= sig.zone_high:
                found = idx; break
        if found < 0:
            return {"exit_reason": "skip_no_retest"}
        enter_idx = found
    else:
        return {"exit_reason": "no_data"}

    if enter_idx >= len(buckets):
        return {"exit_reason": "no_data"}
    eb = buckets[enter_idx]
    entry_sec = eb.sec
    entry_price = eb.last
    if entry_price <= 0:
        return {"exit_reason": "no_data"}

    # 2. Stop distance
    if cfg.zone_boundary_stop:
        if sig.direction == "LONG":
            if sig.zone_low is None: return {"exit_reason": "no_data"}
            used_stop_pct = (entry_price - sig.zone_low) / entry_price * 100.0
        else:
            if sig.zone_high is None: return {"exit_reason": "no_data"}
            used_stop_pct = (sig.zone_high - entry_price) / entry_price * 100.0
    elif cfg.max_zone_boundary_or_pct is not None:
        if sig.direction == "LONG" and sig.zone_low is not None:
            zb = (entry_price - sig.zone_low) / entry_price * 100.0
        elif sig.direction == "SHORT" and sig.zone_high is not None:
            zb = (sig.zone_high - entry_price) / entry_price * 100.0
        else:
            zb = cfg.max_zone_boundary_or_pct
        used_stop_pct = max(zb, cfg.max_zone_boundary_or_pct)
    else:
        used_stop_pct = cfg.stop_pct

    if sig.direction == "LONG":
        target = entry_price * (1.0 + cfg.target_pct / 100.0)
        stop = entry_price * (1.0 - used_stop_pct / 100.0)
    else:
        target = entry_price * (1.0 - cfg.target_pct / 100.0)
        stop = entry_price * (1.0 + used_stop_pct / 100.0)
    timeout_sec = entry_sec + cfg.timeout_hours * 3600

    # 3. Walk forward
    mfe = 0.0; mae = 0.0
    exit_reason = "timeout"; exit_sec = timeout_sec; exit_price = None
    for idx in range(enter_idx, len(buckets)):
        b = buckets[idx]
        if b.sec > timeout_sec:
            break
        if sig.direction == "LONG":
            up_pct = (b.high - entry_price) / entry_price * 100.0
            dn_pct = (entry_price - b.low) / entry_price * 100.0
            target_hit = b.high >= target
            stop_hit = b.low <= stop
        else:
            up_pct = (entry_price - b.low) / entry_price * 100.0
            dn_pct = (b.high - entry_price) / entry_price * 100.0
            target_hit = b.low <= target
            stop_hit = b.high >= stop
        if up_pct > mfe: mfe = up_pct
        if dn_pct > mae: mae = dn_pct
        if target_hit and stop_hit:
            exit_reason = "stop"; exit_sec = b.sec; exit_price = stop; break
        if target_hit:
            exit_reason = "target_2pct"; exit_sec = b.sec; exit_price = target; break
        if stop_hit:
            exit_reason = "stop"; exit_sec = b.sec; exit_price = stop; break

    if exit_reason == "timeout":
        last_idx = enter_idx
        for idx in range(enter_idx, len(buckets)):
            if buckets[idx].sec > timeout_sec: break
            last_idx = idx
        exit_price = buckets[last_idx].last
        exit_sec = buckets[last_idx].sec

    if exit_price is None:
        return {"exit_reason": "no_data"}

    sgn = 1.0 if sig.direction == "LONG" else -1.0
    pnl_pct = round(sgn * (exit_price - entry_price) / entry_price * 100.0, 6)
    return {
        "exit_reason": exit_reason,
        "entry_sec": entry_sec, "entry_price": entry_price,
        "exit_sec": exit_sec, "exit_price": exit_price,
        "pnl_pct": pnl_pct, "mfe_pct": round(mfe, 6), "mae_pct": round(mae, 6),
        "used_stop_pct": used_stop_pct,
    }


# ---------- ledger walk ----------

def canonical_ledger_walk(signals: Iterable[Signal],
                          buckets_by_date: dict[str, list[Bucket]],
                          cfg: ExecutionConfig) -> LedgerResult:
    """Chronological one-trade-at-a-time walk.
    CRITICAL: open_until_sec = ACTUAL exit timestamp (not trigSec + 24h).
    """
    sorted_sigs = sorted(signals, key=lambda s: s.trigger_ts_ms)
    trades: list[TradeRecord] = []
    open_until_sec = -1
    skipped_pos = 0; skipped_nd = 0; skipped_nr = 0
    for sig in sorted_sigs:
        trig_sec = sig.trigger_ts_ms // 1000
        if trig_sec < open_until_sec:
            skipped_pos += 1
            continue
        buckets = buckets_by_date.get(sig.date) or []
        if not buckets:
            skipped_nd += 1
            continue
        sim = simulate_canonical_trade(sig, buckets, cfg)
        if sim["exit_reason"] == "skip_no_retest":
            skipped_nr += 1; continue
        if sim["exit_reason"] == "no_data":
            skipped_nd += 1; continue
        time_in_trade_h = (sim["exit_sec"] - sim["entry_sec"]) / 3600.0
        trades.append(TradeRecord(
            zone_id=sig.id, date=sig.date, direction=sig.direction,
            trigger_ts_ms=sig.trigger_ts_ms,
            entry_sec=sim["entry_sec"], exit_sec=sim["exit_sec"],
            entry_price=sim["entry_price"], exit_price=sim["exit_price"],
            exit_reason=sim["exit_reason"], pnl_pct=sim["pnl_pct"],
            mfe_pct=sim["mfe_pct"], mae_pct=sim["mae_pct"],
            time_in_trade_h=round(time_in_trade_h, 4),
            used_stop_pct=sim["used_stop_pct"],
        ))
        # CRITICAL: actual exit, NOT trigSec + 24h.
        open_until_sec = sim["exit_sec"]
    return LedgerResult(trades=trades, skipped_due_to_position=skipped_pos,
                        skipped_no_data=skipped_nd, skipped_no_retest=skipped_nr)


# ---------- aggregate ----------

def aggregate(trades: list[TradeRecord]) -> dict:
    n = len(trades)
    wins = sum(1 for t in trades if t.exit_reason == "target_2pct")
    losses = sum(1 for t in trades if t.exit_reason == "stop")
    timeouts = sum(1 for t in trades if t.exit_reason == "timeout")
    pnls = [t.pnl_pct for t in trades]
    wp = [p for p in pnls if p > 0]
    lp = [p for p in pnls if p < 0]
    gw = sum(wp); gl = sum(-p for p in lp)
    max_cons = 0; cur = 0
    for t in trades:
        if t.pnl_pct < 0:
            cur += 1
            if cur > max_cons: max_cons = cur
        else:
            cur = 0
    longp = [t.pnl_pct for t in trades if t.direction == "LONG"]
    shortp = [t.pnl_pct for t in trades if t.direction == "SHORT"]
    by_day = defaultdict(list)
    for t in trades:
        by_day[t.date].append(t.pnl_pct)
    best_day = max(by_day.items(), key=lambda kv: sum(kv[1]), default=(None, []))
    worst_day = min(by_day.items(), key=lambda kv: sum(kv[1]), default=(None, []))
    return {
        "n_trades": n, "wins": wins, "losses": losses, "timeouts": timeouts,
        "winrate_pct": round(100.0 * wins / n, 2) if n else None,
        "avg_win_pct": round(stats.mean(wp), 4) if wp else None,
        "avg_loss_pct": round(stats.mean(lp), 4) if lp else None,
        "expectancy_pct_per_trade": round(stats.mean(pnls), 4) if pnls else None,
        "total_return_pct_1unit": round(sum(pnls), 4) if pnls else None,
        "profit_factor": round(gw / gl, 3) if gl > 0 else (None if gw == 0 else float("inf")),
        "max_consecutive_losses": max_cons,
        "long_n": len(longp),
        "long_expectancy_pct": round(stats.mean(longp), 4) if longp else None,
        "short_n": len(shortp),
        "short_expectancy_pct": round(stats.mean(shortp), 4) if shortp else None,
        "best_day": {"date": best_day[0], "sum_pnl_pct": round(sum(best_day[1]), 4) if best_day[0] else None},
        "worst_day": {"date": worst_day[0], "sum_pnl_pct": round(sum(worst_day[1]), 4) if worst_day[0] else None},
    }


def aggregate_after_cost(trades: list[TradeRecord], cost_pct_roundtrip: float) -> dict:
    """Apply flat roundtrip cost to each trade pnl_pct."""
    adjusted = [TradeRecord(**{**t.__dict__, "pnl_pct": round(t.pnl_pct - cost_pct_roundtrip, 6)})
                for t in trades]
    return aggregate(adjusted)
