"""TREND_DOWN cross-venue v2 — NORMALIZE (L2 + REAL trades) per minute, per (exchange, window).

Bybit + OKX. L2 book reconstruction -> per-second mid/depth -> per-minute OHLC + L2 aggregates.
Trades -> per-minute taker_buy/sell volume, trade_count, taker_imbalance, running CVD.
OKX trades use a UTC+8 day boundary: a UTC day's trades are read from labels D and D+1 and bucketed by REAL
UTC minute. Bybit Nov/Jan L2 is reused from the v1 per-second cache (quarantined OKX is NOT touched).
Outputs: reports/trend_down_crossvenue_v2/_normalized/<EX>_<window>_1m.csv.gz  (+ per-day L2 caches for resume).
"""
from __future__ import annotations
import csv, gzip, io, json, statistics as st, sys, datetime as dt
from collections import defaultdict
from pathlib import Path

ROOT = Path("C:/Users/gibilev/orderflow-research")
sys.path.insert(0, str(ROOT / "scripts/research"))
import td_calib_parse_l2 as TP  # reuse book reconstruction (parse -> per-second rows)

TG = Path("C:/Users/gibilev/Downloads/Telegram Desktop")
OLD = ROOT / "data/11.06.2026"
OKX_WS = ROOT / "data/trend_down_v2_okx"
V1NORM = ROOT / "reports/trend_down_calibration_v1/_normalized"
OUT = ROOT / "reports/trend_down_crossvenue_v2/_normalized"
L2CACHE = OUT / "_l2min"

WINDOWS = {
    "W1_NOVEMBER": ["2025-11-19", "2025-11-20", "2025-11-21", "2025-11-22"],
    "W3_JANUARY": ["2026-01-28", "2026-01-29", "2026-01-30", "2026-01-31"],
    "W4_APRIL": ["2024-04-12", "2024-04-13", "2024-04-14", "2024-04-15", "2024-04-16", "2024-04-17"],
}
OKX_TRADE_LABELS = {
    "W1_NOVEMBER": ["2025-11-19", "2025-11-20", "2025-11-21", "2025-11-22", "2025-11-23"],
    "W3_JANUARY": ["2026-01-28", "2026-01-29", "2026-01-30", "2026-01-31", "2026-02-01"],
    "W4_APRIL": ["2024-04-12", "2024-04-13", "2024-04-14", "2024-04-15", "2024-04-16", "2024-04-17", "2024-04-18"],
}


def log(m): print(f"[{dt.datetime.now().strftime('%H:%M:%S')}] {m}", flush=True)


def bybit_ob_path(d):
    p = OLD / f"{d}_BTCUSDT_ob200.data.zip"
    if p.exists(): return p
    return TG / f"{d}_BTCUSDT_ob500.data.zip"  # April


def persec_to_min(rows):
    """rows: per-second [ex,sec,bb,ba,mid,spread,tbs,tas,bd,ad,di,upd] -> per-minute dict."""
    bym = defaultdict(list)
    for r in rows: bym[int(r[1]) // 60].append(r)
    out = {}
    for m, g in bym.items():
        mids = [float(x[4]) for x in g if x[4] not in (None, "")]
        if not mids: continue
        out[m] = {"mid_o": mids[0], "mid_h": max(mids), "mid_l": min(mids), "mid_c": mids[-1],
                  "spread_bps": round(st.mean([float(x[5]) for x in g if x[5] not in (None, "")]), 3),
                  "depth_imb": round(st.mean([float(x[10]) for x in g if x[10] not in (None, "")]), 4),
                  "bid_depth": round(st.mean([float(x[8]) for x in g if x[8] not in (None, "")]), 3),
                  "ask_depth": round(st.mean([float(x[9]) for x in g if x[9] not in (None, "")]), 3),
                  "update_count": sum(int(float(x[11])) for x in g if x[11] not in (None, ""))}
    return out


def l2_min_for_day(ex, d):
    """per-minute L2 dict for one UTC day, cached. Reuse v1 per-second cache for Bybit Nov/Jan."""
    cache = L2CACHE / f"{ex}_{d}.csv.gz"
    if cache.exists():
        out = {}
        with gzip.open(cache, "rt") as fh:
            for r in csv.DictReader(fh):
                out[int(r["ts_min"])] = {k: (float(r[k]) if k != "update_count" else int(float(r[k]))) for k in ("mid_o", "mid_h", "mid_l", "mid_c", "spread_bps", "depth_imb", "bid_depth", "ask_depth", "update_count")}
        return out
    # build
    v1 = V1NORM / f"{ex}_{'BTCUSDT' if ex=='Bybit' else 'BTC-USDT-SWAP'}_{d}_l2_1s.csv.gz"
    if ex == "Bybit" and v1.exists():
        rows = []
        with gzip.open(v1, "rt") as fh:
            for r in csv.DictReader(fh):
                rows.append([r["exchange"], r["ts_sec"], r["best_bid"], r["best_ask"], r["mid"], r["spread_bps"], r["top_bid_size"], r["top_ask_size"], r["bid_depth_top10"], r["ask_depth_top10"], r["depth_imbalance"], r["update_count"]])
        log(f"  L2 {ex} {d}: reused v1 per-second ({len(rows)} rows)")
    else:
        path = bybit_ob_path(d) if ex == "Bybit" else (OKX_WS / f"BTC-USDT-SWAP-L2orderbook-400lv-{d}.tar.gz")
        if not path.exists(): log(f"  L2 {ex} {d}: MISSING {path.name}"); return {}
        t0 = dt.datetime.now(); rows = TP.parse(path, ex)
        log(f"  L2 {ex} {d}: parsed raw {path.name} ({len(rows)} sec-rows, {(dt.datetime.now()-t0).total_seconds():.0f}s)")
    mins = persec_to_min(rows)
    L2CACHE.mkdir(parents=True, exist_ok=True)
    with gzip.open(cache, "wt", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh); w.writerow(["ts_min", "mid_o", "mid_h", "mid_l", "mid_c", "spread_bps", "depth_imb", "bid_depth", "ask_depth", "update_count"])
        for m in sorted(mins): r = mins[m]; w.writerow([m] + [r[k] for k in ("mid_o", "mid_h", "mid_l", "mid_c", "spread_bps", "depth_imb", "bid_depth", "ask_depth", "update_count")])
    return mins


def trades_min_bybit(d):
    """one UTC day Bybit trades -> per-minute taker buy/sell vol + count."""
    p = TG / f"BTCUSDT{d}.csv.gz"
    out = defaultdict(lambda: [0.0, 0.0, 0])  # buy_vol, sell_vol, count
    if not p.exists(): return out
    with gzip.open(p, "rt", encoding="utf-8") as fh:
        rd = csv.reader(fh); next(rd, None)
        for row in rd:
            try: ts = float(row[0]); side = row[2]; size = float(row[3])
            except (IndexError, ValueError): continue
            m = int(ts) // 60
            rec = out[m]
            if side == "Buy": rec[0] += size
            else: rec[1] += size
            rec[2] += 1
    return out


def trades_min_okx(labels):
    """OKX trades from label files (UTC+8) -> per-minute by REAL UTC minute."""
    out = defaultdict(lambda: [0.0, 0.0, 0])
    import zipfile
    for lab in labels:
        p = OKX_WS / f"BTC-USDT-SWAP-trades-{lab}.zip"
        if not p.exists(): continue
        with zipfile.ZipFile(p) as z:
            with z.open(z.namelist()[0]) as fh:
                rd = csv.reader(io.TextIOWrapper(fh, encoding="utf-8")); next(rd, None)
                for row in rd:
                    try: side = row[2]; price = float(row[3]); size = float(row[4]); ct = int(row[5])
                    except (IndexError, ValueError): continue
                    m = ct // 60000
                    rec = out[m]
                    if side == "buy": rec[0] += size
                    else: rec[1] += size
                    rec[2] += 1
    return out


def build_window(ex, wid):
    outp = OUT / f"{ex}_{wid}_1m.csv.gz"
    if outp.exists(): log(f"{ex} {wid}: exists, skip"); return
    days = WINDOWS[wid]
    l2 = {}
    for d in days: l2.update(l2_min_for_day(ex, d))
    if ex == "Bybit":
        tr = defaultdict(lambda: [0.0, 0.0, 0])
        for d in days:
            for m, v in trades_min_bybit(d).items(): tr[m][0] += v[0]; tr[m][1] += v[1]; tr[m][2] += v[2]
    else:
        tr = trades_min_okx(OKX_TRADE_LABELS[wid])
    # restrict to window UTC day range
    lo = int(dt.datetime.strptime(days[0], "%Y-%m-%d").replace(tzinfo=dt.timezone.utc).timestamp()) // 60
    hi = int(dt.datetime.strptime(days[-1], "%Y-%m-%d").replace(tzinfo=dt.timezone.utc).timestamp()) // 60 + 1440
    mins = sorted(m for m in set(l2) | set(tr) if lo <= m < hi)
    cvd = 0.0
    OUT.mkdir(parents=True, exist_ok=True)
    with gzip.open(outp, "wt", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["exchange", "ts_min", "date", "mid_o", "mid_h", "mid_l", "mid_c", "spread_bps", "depth_imbalance",
                    "bid_depth_top10", "ask_depth_top10", "update_count", "taker_buy_vol", "taker_sell_vol", "trade_count", "taker_imbalance", "cvd"])
        for m in mins:
            L = l2.get(m); T = tr.get(m, [0.0, 0.0, 0])
            bv, sv, tc = T; cvd += (bv - sv)
            ti = round((bv - sv) / (bv + sv), 4) if (bv + sv) else None
            date = dt.datetime.fromtimestamp(m * 60, tz=dt.timezone.utc).strftime("%Y-%m-%d")
            if L:
                w.writerow([ex, m, date, L["mid_o"], L["mid_h"], L["mid_l"], L["mid_c"], L["spread_bps"], L["depth_imb"],
                            L["bid_depth"], L["ask_depth"], L["update_count"], round(bv, 4), round(sv, 4), tc, ti, round(cvd, 4)])
            else:  # trade-only minute (rare; L2 gap)
                w.writerow([ex, m, date, "", "", "", "", "", "", "", "", "", round(bv, 4), round(sv, 4), tc, ti, round(cvd, 4)])
    log(f"{ex} {wid}: wrote {len(mins)} minutes -> {outp.name}")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for wid in WINDOWS:
        for ex in ("Bybit", "OKX"):
            build_window(ex, wid)
    log("V2 NORMALIZE DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
