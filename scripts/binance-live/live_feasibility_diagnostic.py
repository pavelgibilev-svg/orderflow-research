"""PART 1 - Feasibility diagnostic over Binance live 2026-05-17..20.

Inputs (READ-ONLY):
  data/binance-historical/BTCUSDT/<date>/trades.csv.gz
  reports/binance-live/BTCUSDT_<date>/zones.json

Outputs:
  reports/binance-live/BINANCE_LIVE_2026_05_17_20_DAY_FEASIBILITY.{md,json}
  reports/binance-live/BINANCE_LIVE_2026_05_17_20_MFE_MAE_TARGET_SENSITIVITY.{md,json,csv}

NO new backtest. NO engine / threshold change.
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
TARDIS_ROOT = ROOT / "data/binance-historical/BTCUSDT"
REPORTS_LIVE = ROOT / "reports/binance-live"
DATES = ["2026-05-17", "2026-05-18", "2026-05-19", "2026-05-20"]
TARGETS_PCT = [0.5, 1.0, 1.5, 2.0]
STOPS_PCT = [0.5, 1.0]
HORIZONS_S = {"1h": 3600, "4h": 4 * 3600, "8h": 8 * 3600, "24h": 24 * 3600}


def ms_to_iso(ms: int) -> str:
    return dt.datetime.fromtimestamp(ms / 1000, tz=dt.timezone.utc).isoformat(timespec="milliseconds")


# ---------- A1: day-level feasibility ----------

def stream_trades(date: str):
    """Yield (ts_ms, price, side, qty) from trades.csv.gz; ts in microseconds in source."""
    p = TARDIS_ROOT / date / "trades.csv.gz"
    if not p.exists():
        return
    with gzip.open(p, "rt", encoding="utf-8", newline="") as f:
        rdr = csv.reader(f)
        header = next(rdr)
        idx_ts = header.index("timestamp")
        idx_side = header.index("side")
        idx_price = header.index("price")
        idx_amount = header.index("amount")
        for row in rdr:
            try:
                ts_us = int(row[idx_ts])
                price = float(row[idx_price])
                amt = float(row[idx_amount])
                side = row[idx_side]
            except Exception:
                continue
            yield ts_us // 1000, price, side, amt  # convert to ms


def day_feasibility(date: str) -> dict:
    open_p = None
    close_p = None
    high = -float("inf")
    low = float("inf")
    # forward-move calc: for each trade (price, ts) compute, BUT we need max future move
    # within 4h/8h/24h. Need O(n) running max with sliding window — use deque.
    # Simpler approach: do one pass to load all (ts, price) (lightweight: n~1e6 floats).
    pts: list[tuple[int, float]] = []
    n = 0
    for ts_ms, price, side, qty in stream_trades(date):
        if open_p is None:
            open_p = price
        close_p = price
        if price > high:
            high = price
        if price < low:
            low = price
        pts.append((ts_ms, price))
        n += 1
    if n == 0:
        return {"date": date, "n_trades": 0}

    day_range_pct = round((high - low) / low * 100.0, 4) if low > 0 else None
    day_return_pct = round((close_p - open_p) / open_p * 100.0, 4) if open_p else None
    max_intraday_up_pct = round((high - open_p) / open_p * 100.0, 4) if open_p else None
    max_intraday_down_pct = round((open_p - low) / open_p * 100.0, 4) if open_p else None

    # Forward 4h / 8h / 24h: max(up,down) from each point, then take the GLOBAL max
    # (i.e., somewhere in the day, was there a 4h window that moved 2%?)
    forward = {h: {"max_up": 0.0, "max_down": 0.0} for h in HORIZONS_S}
    # For efficiency, since pts are ts-sorted, for each anchor look ahead up to horizon
    times = [p[0] for p in pts]
    prices = [p[1] for p in pts]
    N = len(pts)
    for h_label, h_s in HORIZONS_S.items():
        h_ms = h_s * 1000
        # Two-pointer: for each anchor i, advance j while times[j]-times[i] <= h_ms
        j = 0
        cur_max = -float("inf")
        cur_min = float("inf")
        # window-max needs proper sliding; this is O(n^2) worst-case — but with ~3M
        # trades it would be slow. Use a different approach: bucket by 1-second.
        # 1s buckets reduce to ~86400 points; we then scan with a true O(n) sliding window.
        pass

    # Reduce to 1-second buckets (use last price each second) for speed
    last_price_by_sec: dict[int, float] = {}
    for ts_ms, price in pts:
        sec = ts_ms // 1000
        last_price_by_sec[sec] = price
    secs = sorted(last_price_by_sec.keys())
    prices_sec = [last_price_by_sec[s] for s in secs]
    N1 = len(secs)

    for h_label, h_s in HORIZONS_S.items():
        # For each anchor i, find max j s.t. secs[j] - secs[i] <= h_s
        max_up = 0.0
        max_down = 0.0
        j = 0
        cur_max = -float("inf")
        cur_min = float("inf")
        # We want, for each i: max_{i<=k<=j} prices[k] - prices[i], for j with secs[j]-secs[i]<=h_s.
        # Use a monotonic queue for max/min over sliding window.
        from collections import deque
        dq_max = deque()  # holds indices with decreasing prices
        dq_min = deque()  # holds indices with increasing prices
        j = 0
        for i in range(N1):
            # Advance j to max j with secs[j] - secs[i] <= h_s
            while j < N1 and secs[j] - secs[i] <= h_s:
                while dq_max and prices_sec[dq_max[-1]] <= prices_sec[j]:
                    dq_max.pop()
                dq_max.append(j)
                while dq_min and prices_sec[dq_min[-1]] >= prices_sec[j]:
                    dq_min.pop()
                dq_min.append(j)
                j += 1
            # Now window is [i, j-1]
            # Drop elements < i from deques
            while dq_max and dq_max[0] < i:
                dq_max.popleft()
            while dq_min and dq_min[0] < i:
                dq_min.popleft()
            if dq_max and dq_min:
                w_max = prices_sec[dq_max[0]]
                w_min = prices_sec[dq_min[0]]
                p0 = prices_sec[i]
                up = (w_max - p0) / p0 * 100.0
                dn = (p0 - w_min) / p0 * 100.0
                if up > max_up:
                    max_up = up
                if dn > max_down:
                    max_down = dn
        forward[h_label]["max_up"] = round(max_up, 4)
        forward[h_label]["max_down"] = round(max_down, 4)

    # Day-level 2% feasibility: did EITHER direction reach 2% from ANY 1-second anchor within 24h?
    feasible = {}
    for tgt in TARGETS_PCT:
        feasible[f"{tgt}pct"] = (
            forward["24h"]["max_up"] >= tgt or forward["24h"]["max_down"] >= tgt
        )

    return {
        "date": date,
        "n_trades": n,
        "open": open_p,
        "high": high,
        "low": low,
        "close": close_p,
        "day_return_pct": day_return_pct,
        "day_range_pct": day_range_pct,
        "max_intraday_up_pct": max_intraday_up_pct,
        "max_intraday_down_pct": max_intraday_down_pct,
        "forward_max_moves": forward,
        "feasibility": feasible,
    }


# ---------- A2: MFE/MAE after triggered zones ----------

def load_zones(date: str) -> list[dict]:
    p = REPORTS_LIVE / f"BTCUSDT_{date}" / "zones.json"
    if not p.exists():
        return []
    obj = json.loads(p.read_text(encoding="utf-8"))
    zones = obj if isinstance(obj, list) else obj.get("zones", [])
    for z in zones:
        z["_date"] = date
    return zones


def mid_price(z: dict) -> float | None:
    lo, hi = z.get("zoneLow"), z.get("zoneHigh")
    if lo is None or hi is None:
        return None
    return (lo + hi) / 2.0


def confirm_to_trigger_min(z: dict) -> float | None:
    c, t = z.get("confirmedTs"), z.get("triggerTs")
    if c is None or t is None:
        return None
    return (t - c) / 60000.0


def is_triggered(z: dict) -> bool:
    return z.get("status") in ("RESOLVED_REACHED", "RESOLVED_FAILED")


def apply_live_valid_filter(zones: list[dict]) -> dict[str, dict]:
    """Live-valid filter: duplicate_60m (price band <= 1%) AND fast_trigger <= 60m."""
    by_date = defaultdict(list)
    for z in zones:
        by_date[z["_date"]].append(z)
    decisions = {}
    for date, lst in by_date.items():
        triggered = [z for z in lst if is_triggered(z) and z.get("triggerTs") is not None]
        triggered.sort(key=lambda z: z["triggerTs"])
        for i, z in enumerate(triggered):
            T = z["triggerTs"]
            D = z["direction"]
            z_mid = mid_price(z)
            dup = False
            for prior in triggered[:i]:
                if prior["triggerTs"] >= T:
                    continue
                if prior["direction"] != D:
                    continue
                dt_min = (T - prior["triggerTs"]) / 60000.0
                if dt_min <= 0 or dt_min > 60:
                    continue
                p_mid = mid_price(prior)
                if z_mid is None or p_mid is None:
                    continue
                if abs(z_mid - p_mid) / z_mid * 100.0 <= 1.0:
                    dup = True
                    break
            ctm = confirm_to_trigger_min(z)
            fast_ok = (ctm is None) or (ctm <= 60)
            decisions[z["id"]] = {"kept": (not dup) and fast_ok, "dup": dup, "fast_ok": fast_ok}
    return decisions


def trigger_price(z: dict) -> float | None:
    for r in z.get("reasons") or []:
        if r.get("stage") == "trigger":
            tp = (r.get("conditions") or {}).get("triggerPrice")
            if tp is not None:
                return float(tp)
    return mid_price(z)


def mfe_mae_for_zone(z: dict, trades_by_date: dict[str, list[tuple[int, float]]]) -> dict:
    """Forward MFE / MAE at 1h/4h/8h/24h for one triggered zone.
    Use 1-second buckets of last_price (already built per date)."""
    date = z["_date"]
    pts = trades_by_date.get(date, [])
    if not pts:
        return {}
    direction = z["direction"]
    triggerTs = z.get("triggerTs")
    if triggerTs is None:
        return {}
    entry = trigger_price(z) or mid_price(z)
    if entry is None or entry <= 0:
        return {}
    # find first index with sec >= triggerTs // 1000
    trigger_sec = triggerTs // 1000
    # binary search
    lo, hi = 0, len(pts)
    while lo < hi:
        m = (lo + hi) // 2
        if pts[m][0] < trigger_sec:
            lo = m + 1
        else:
            hi = m
    start = lo
    if start >= len(pts):
        return {}
    out = {}
    for h_label, h_s in HORIZONS_S.items():
        end_ts = trigger_sec + h_s
        # find end index (exclusive)
        lo2, hi2 = start, len(pts)
        while lo2 < hi2:
            m = (lo2 + hi2) // 2
            if pts[m][0] <= end_ts:
                lo2 = m + 1
            else:
                hi2 = m
        if lo2 == start:
            out[h_label] = {"n_points": 0}
            continue
        window = pts[start:lo2]
        prices = [p for _, p in window]
        if direction == "LONG":
            mfe_pct = (max(prices) - entry) / entry * 100.0
            mae_pct = (entry - min(prices)) / entry * 100.0
        else:
            mfe_pct = (entry - min(prices)) / entry * 100.0
            mae_pct = (max(prices) - entry) / entry * 100.0
        reached = {f"{t}pct": (mfe_pct >= t) for t in TARGETS_PCT}
        stopped = {f"{s}pct": (mae_pct >= s) for s in STOPS_PCT}
        out[h_label] = {
            "n_points": len(window),
            "mfe_pct": round(mfe_pct, 4),
            "mae_pct": round(mae_pct, 4),
            "reached": reached,
            "stopped_adverse": stopped,
        }
    return out


def build_trades_sec_buckets(date: str) -> list[tuple[int, float]]:
    last_price_by_sec: dict[int, float] = {}
    for ts_ms, price, side, qty in stream_trades(date):
        last_price_by_sec[ts_ms // 1000] = price
    return sorted(last_price_by_sec.items())


# ---------- writers ----------

def aggregate_target_pct(per_zone: list[dict], horizon: str, target_pct: float) -> dict:
    """Across given zones at given horizon: how many reached, hit adverse, etc."""
    n = 0
    reached = 0
    stop05 = 0
    stop10 = 0
    mfes = []
    maes = []
    for r in per_zone:
        rec = r.get("forward_outcome", {}).get(horizon)
        if not rec or not rec.get("n_points"):
            continue
        n += 1
        if rec["reached"].get(f"{target_pct}pct"):
            reached += 1
        if rec["stopped_adverse"].get("0.5pct"):
            stop05 += 1
        if rec["stopped_adverse"].get("1.0pct"):
            stop10 += 1
        mfes.append(rec["mfe_pct"])
        maes.append(rec["mae_pct"])
    return {
        "n": n,
        "reached_count": reached,
        "reached_pct": round(100.0 * reached / n, 2) if n else None,
        "hit_adverse_0_5_pct_count": stop05,
        "hit_adverse_0_5_pct_pct": round(100.0 * stop05 / n, 2) if n else None,
        "hit_adverse_1_0_pct_count": stop10,
        "hit_adverse_1_0_pct_pct": round(100.0 * stop10 / n, 2) if n else None,
        "median_mfe_pct": round(stats.median(mfes), 4) if mfes else None,
        "median_mae_pct": round(stats.median(maes), 4) if maes else None,
        "max_mfe_pct": round(max(mfes), 4) if mfes else None,
        "worst_mae_pct": round(max(maes), 4) if maes else None,
    }


# ---------- main ----------

def main() -> int:
    REPORTS_LIVE.mkdir(parents=True, exist_ok=True)
    print("[A1] day-level feasibility ...", file=sys.stderr)
    day_rows = []
    for d in DATES:
        print(f"  scanning {d}", file=sys.stderr)
        r = day_feasibility(d)
        day_rows.append(r)
        if r.get("n_trades"):
            print(f"    return={r['day_return_pct']}%  range={r['day_range_pct']}%  "
                  f"4h up/dn={r['forward_max_moves']['4h']}", file=sys.stderr)

    # 2% feasibility count
    feas_2pct_days = sum(1 for r in day_rows if r.get("feasibility", {}).get("2.0pct"))

    feas_out = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "scope": "Binance live-recorder 2026-05-17..2026-05-20",
        "per_day": day_rows,
        "BINANCE_LIVE_2PCT_FEASIBLE_DAYS": feas_2pct_days,
    }
    (REPORTS_LIVE / "BINANCE_LIVE_2026_05_17_20_DAY_FEASIBILITY.json").write_text(
        json.dumps(feas_out, indent=2, default=str), encoding="utf-8")

    md = [
        "# Binance live 2026-05-17..20 - day-level 2 % feasibility",
        "",
        f"**Build:** {feas_out['build_time_utc']}",
        "**Scope:** computes day open/high/low/close + forward-max-moves up/down 4h/8h/24h"
        " from trades.csv.gz (no future-leak into filter; this is diagnostic).",
        "",
        "| date | return % | range % | intraday up % | intraday dn % | 4h up | 4h dn | 8h up | 8h dn | 24h up | 24h dn | 2 % feas |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|:---:|",
    ]
    for r in day_rows:
        if not r.get("n_trades"):
            md.append(f"| {r['date']} | no data |")
            continue
        f = r["forward_max_moves"]
        feas = "YES" if r["feasibility"].get("2.0pct") else "NO"
        md.append(
            f"| {r['date']} | {r['day_return_pct']} | {r['day_range_pct']} | "
            f"{r['max_intraday_up_pct']} | {r['max_intraday_down_pct']} | "
            f"{f['4h']['max_up']} | {f['4h']['max_down']} | "
            f"{f['8h']['max_up']} | {f['8h']['max_down']} | "
            f"{f['24h']['max_up']} | {f['24h']['max_down']} | {feas} |"
        )
    md.extend([
        "",
        f"**`BINANCE_LIVE_2PCT_FEASIBLE_DAYS` = {feas_2pct_days} / 4**",
        "",
        "Reading:",
        "- `intraday up/dn` = high-from-open / open-from-low (absolute intraday excursion).",
        "- `4h/8h/24h up/dn` = max forward move within that horizon, measured from ANY 1-second anchor in the day.",
        "  If this is < 2 %, no zone triggered any time during the day could have reached a +2 % target within the horizon.",
    ])
    (REPORTS_LIVE / "BINANCE_LIVE_2026_05_17_20_DAY_FEASIBILITY.md").write_text("\n".join(md), encoding="utf-8")

    print("[A2] MFE/MAE per zone ...", file=sys.stderr)
    zones_all: list[dict] = []
    for d in DATES:
        zones_all.extend(load_zones(d))
    print(f"  loaded {len(zones_all)} zones", file=sys.stderr)
    decisions = apply_live_valid_filter(zones_all)

    # Build 1-second price buckets once per date (shared)
    print("  building 1s price buckets per date ...", file=sys.stderr)
    trades_by_date = {d: build_trades_sec_buckets(d) for d in DATES}
    for d in DATES:
        print(f"    {d}: {len(trades_by_date[d])} unique seconds", file=sys.stderr)

    triggered_zones = [z for z in zones_all if is_triggered(z)]
    print(f"  computing MFE/MAE for {len(triggered_zones)} triggered zones ...", file=sys.stderr)
    per_zone = []
    for z in triggered_zones:
        rec = {
            "zone_id": z["id"],
            "date": z["_date"],
            "direction": z["direction"],
            "triggerTs": z.get("triggerTs"),
            "triggerTs_iso": ms_to_iso(z["triggerTs"]) if z.get("triggerTs") else None,
            "trigger_price": trigger_price(z),
            "engine_status": z.get("status"),
            "filter_kept": decisions.get(z["id"], {}).get("kept"),
            "forward_outcome": mfe_mae_for_zone(z, trades_by_date),
        }
        per_zone.append(rec)

    # Aggregate per (set, horizon, target)
    sets = {
        "baseline_triggered": per_zone,
        "filtered_kept": [r for r in per_zone if r["filter_kept"]],
        "filter_suppressed": [r for r in per_zone if r["filter_kept"] is False],
    }
    agg = {}
    for sname, lst in sets.items():
        agg[sname] = {}
        for h in HORIZONS_S:
            agg[sname][h] = {}
            for tgt in TARGETS_PCT:
                agg[sname][h][f"{tgt}pct"] = aggregate_target_pct(lst, h, tgt)

    mfe_mae_out = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "scope": "Binance live 2026-05-17..2026-05-20 — MFE/MAE on triggered zones (diagnostic; uses post-trigger price path, NOT inside filter decision).",
        "set_sizes": {k: len(v) for k, v in sets.items()},
        "aggregates": agg,
        "per_zone": per_zone,
    }
    (REPORTS_LIVE / "BINANCE_LIVE_2026_05_17_20_MFE_MAE_TARGET_SENSITIVITY.json").write_text(
        json.dumps(mfe_mae_out, indent=2, default=str), encoding="utf-8")

    # CSV
    keys = ["zone_id", "date", "direction", "triggerTs_iso", "engine_status", "filter_kept",
            "mfe_1h", "mae_1h", "mfe_4h", "mae_4h", "mfe_8h", "mae_8h",
            "mfe_24h", "mae_24h",
            "reached_0_5pct_24h", "reached_1pct_24h", "reached_1_5pct_24h", "reached_2pct_24h",
            "stopped_0_5pct_24h", "stopped_1pct_24h"]
    with (REPORTS_LIVE / "BINANCE_LIVE_2026_05_17_20_MFE_MAE_TARGET_SENSITIVITY.csv").open("w", encoding="utf-8", newline="") as fp:
        w = csv.DictWriter(fp, fieldnames=keys)
        w.writeheader()
        for r in per_zone:
            fo = r.get("forward_outcome", {})
            row = {
                "zone_id": r["zone_id"], "date": r["date"], "direction": r["direction"],
                "triggerTs_iso": r["triggerTs_iso"], "engine_status": r["engine_status"],
                "filter_kept": r["filter_kept"],
            }
            for h in ("1h", "4h", "8h", "24h"):
                rec = fo.get(h) or {}
                row[f"mfe_{h}"] = rec.get("mfe_pct")
                row[f"mae_{h}"] = rec.get("mae_pct")
            r24 = fo.get("24h") or {}
            reached24 = r24.get("reached", {}) or {}
            stopped24 = r24.get("stopped_adverse", {}) or {}
            row["reached_0_5pct_24h"] = reached24.get("0.5pct")
            row["reached_1pct_24h"] = reached24.get("1.0pct")
            row["reached_1_5pct_24h"] = reached24.get("1.5pct")
            row["reached_2pct_24h"] = reached24.get("2.0pct")
            row["stopped_0_5pct_24h"] = stopped24.get("0.5pct")
            row["stopped_1pct_24h"] = stopped24.get("1.0pct")
            w.writerow(row)

    # MD
    md2 = [
        "# Binance live 2026-05-17..20 - MFE/MAE per zone, target sensitivity",
        "",
        f"**Build:** {mfe_mae_out['build_time_utc']}",
        "",
        "## A. Set sizes",
        "",
    ]
    for k, v in mfe_mae_out["set_sizes"].items():
        md2.append(f"- `{k}` = {v}")
    md2.append("")
    for sname in ("baseline_triggered", "filtered_kept", "filter_suppressed"):
        md2.append(f"## B. `{sname}` - per-horizon reached / hit-adverse rates")
        md2.append("")
        md2.append("| horizon | n | median MFE % | median MAE % | reached 0.5 % | reached 1 % | reached 1.5 % | reached 2 % | hit adverse 0.5 % | hit adverse 1 % |")
        md2.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
        for h in HORIZONS_S:
            tgt2 = agg[sname][h]["2.0pct"]
            tgt1 = agg[sname][h]["1.0pct"]
            tgt05 = agg[sname][h]["0.5pct"]
            tgt15 = agg[sname][h]["1.5pct"]
            md2.append(
                f"| {h} | {tgt2['n']} | {tgt2['median_mfe_pct']} | {tgt2['median_mae_pct']} | "
                f"{tgt05['reached_pct']} | {tgt1['reached_pct']} | {tgt15['reached_pct']} | "
                f"{tgt2['reached_pct']} | {tgt2['hit_adverse_0_5_pct_pct']} | "
                f"{tgt2['hit_adverse_1_0_pct_pct']} |"
            )
        md2.append("")
    (REPORTS_LIVE / "BINANCE_LIVE_2026_05_17_20_MFE_MAE_TARGET_SENSITIVITY.md").write_text("\n".join(md2), encoding="utf-8")

    # ---------- A3: interpretation + final flags ----------
    filt = sets["filtered_kept"]
    n_filt = len(filt)
    agg_filt_24 = {tgt: aggregate_target_pct(filt, "24h", tgt) for tgt in TARGETS_PCT}
    reached_05 = agg_filt_24[0.5]["reached_pct"]
    reached_10 = agg_filt_24[1.0]["reached_pct"]
    reached_15 = agg_filt_24[1.5]["reached_pct"]
    reached_20 = agg_filt_24[2.0]["reached_pct"]
    median_mfe_24 = agg_filt_24[2.0]["median_mfe_pct"]
    median_mae_24 = agg_filt_24[2.0]["median_mae_pct"]

    target_too_high = "UNKNOWN"
    sub_2pct_edge = "UNKNOWN"
    # Heuristics:
    if reached_05 is not None and reached_05 >= 60:
        sub_2pct_edge = "YES"
    elif reached_05 is not None and reached_05 < 40:
        sub_2pct_edge = "NO"
    if reached_05 is not None and reached_20 is not None:
        if reached_20 == 0 and reached_05 >= 50:
            target_too_high = "YES"
        elif reached_20 > 0:
            target_too_high = "NO"

    primary_present_anywhere = any(z.get("isPrimaryMoveZone") for z in zones_all)
    live_informative = "YES" if primary_present_anywhere else "NO"

    final_flags = {
        "BINANCE_LIVE_FEASIBILITY_DIAGNOSTIC_DONE": "YES",
        "BINANCE_LIVE_2PCT_FEASIBLE_DAYS": feas_2pct_days,
        "BINANCE_LIVE_FILTERED_SIGNALS_COUNT": n_filt,
        "BINANCE_LIVE_FILTERED_REACHED_0_5_PCT": reached_05,
        "BINANCE_LIVE_FILTERED_REACHED_1_0_PCT": reached_10,
        "BINANCE_LIVE_FILTERED_REACHED_1_5_PCT": reached_15,
        "BINANCE_LIVE_FILTERED_REACHED_2_0_PCT": reached_20,
        "BINANCE_LIVE_FILTERED_MEDIAN_MFE_24H": median_mfe_24,
        "BINANCE_LIVE_FILTERED_MEDIAN_MAE_24H": median_mae_24,
        "TARGET_2PCT_TOO_HIGH_FOR_LIVE_SAMPLE": target_too_high,
        "ZONES_SHOW_SUB_2PCT_EDGE": sub_2pct_edge,
        "LIVE_SAMPLE_INFORMATIVE_FOR_PRIMARY_RECALL": live_informative,
    }
    (REPORTS_LIVE / "BINANCE_LIVE_FEASIBILITY_DIAGNOSTIC_FLAGS.json").write_text(
        json.dumps(final_flags, indent=2), encoding="utf-8")
    print()
    print("PART 1 FLAGS:")
    for k, v in final_flags.items():
        print(f"  {k:<48s} = {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
