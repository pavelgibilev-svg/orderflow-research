"""v11b builder — reconstruct causal per-minute L2 book features from incremental_book_L2 for the OKX-native windows.

Streams Tardis OKX incremental_book_L2 (exchange,symbol,timestamp,local_timestamp,is_snapshot,side,price,amount),
maintains the book, emits per-minute aggregates keyed by epoch-minute (== cached series 'm'). Caches per window so
reruns are instant and partial progress is usable. Causal: each minute's features use only book state up to that minute.
"""
from __future__ import annotations
import gzip, json, sys, time, datetime as dt
from pathlib import Path

ROOT = Path("C:/Users/gibilev/orderflow-research")
sys.path.insert(0, str(ROOT / "scripts/research"))
import td_v4_regime as V4
import td_v5_gate as V5
OKXH = ROOT / "data/okx-historical/BTC-USDT-SWAP"
CACHE = ROOT / "reports/l2_aware_absorption_validation_v11b/_l2cache"
# core within-background windows first; UP/BOUNCE last (completeness)
ORDER = ["DOWN_0327", "RANGE_0303", "RANGE_0508", "UP_0310", "BOUNCE_0512"]


def minute_feats(bids, asks):
    if not bids or not asks: return None
    bb = max(bids); ba = min(asks); mid = (bb + ba) / 2.0
    bsz = bids[bb]; asz = asks[ba]
    micro = (bb * asz + ba * bsz) / (bsz + asz)        # size-weighted top
    lo50 = mid * 0.995; lo25 = mid * 0.9975; hi50 = mid * 1.005; hi25 = mid * 1.0025
    bd50 = bd25 = ad50 = ad25 = 0.0
    for p, a in bids.items():
        if p >= lo50:
            bd50 += a
            if p >= lo25: bd25 += a
    for p, a in asks.items():
        if p <= hi50:
            ad50 += a
            if p <= hi25: ad25 += a
    return [round(mid, 2), round((ba - bb) / mid * 1e4, 3), round((micro - mid) / mid * 1e4, 3),
            round((bsz - asz) / (bsz + asz), 4), round(bd50, 2), round(ad50, 2), round(bd25, 2), round(ad25, 2)]
# feature index: 0 mid 1 spread_bps 2 micro_off_bps 3 top_imb 4 bid_d50 5 ask_d50 6 bid_d25 7 ask_d25
FEAT_KEYS = ["mid_l2", "spread_bps", "micro_off_bps", "top_imb", "bid_d50", "ask_d50", "bid_d25", "ask_d25"]


def utc_dates_for(wid):
    S = V5.get_series(wid)
    ms = [r["m"] for r in S]
    dates = sorted({dt.datetime.utcfromtimestamp(m * 60).strftime("%Y-%m-%d") for m in ms})
    return set(ms), dates


def build_window(wid):
    out = CACHE / f"{wid}.json"
    if out.exists():
        print(f"{wid}: cache exists, skip", flush=True); return
    want_min, dates = utc_dates_for(wid)
    feats = {}
    t0 = time.time(); total = 0
    for d in dates:
        f = OKXH / d / "incremental_book_L2.csv.gz"
        if not f.exists():
            print(f"{wid}: MISSING {f.name} for {d}", flush=True); continue
        bids = {}; asks = {}; last_min = None; rows = 0
        with gzip.open(f, "rt") as fh:
            next(fh)
            for line in fh:
                rows += 1
                c = line.split(",")
                # exchange,symbol,timestamp,local_timestamp,is_snapshot,side,price,amount
                ts = int(c[2]); side = c[5]; price = float(c[6]); amt = float(c[7])
                book = bids if side == "bid" else asks
                if amt == 0.0: book.pop(price, None)
                else: book[price] = amt
                m = ts // 60000000
                if m != last_min:
                    if last_min is not None and last_min in want_min:
                        ff = minute_feats(bids, asks)
                        if ff: feats[last_min] = ff
                    last_min = m
            if last_min in want_min:
                ff = minute_feats(bids, asks)
                if ff: feats[last_min] = ff
        total += rows
        print(f"{wid}: {d} rows {rows} cum_min {len(feats)} elapsed {round(time.time()-t0)}s", flush=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    json.dump({"keys": FEAT_KEYS, "feats": {str(k): v for k, v in feats.items()}}, out.open("w"))
    print(f"{wid}: DONE minutes {len(feats)} of {len(want_min)} total_rows {total} elapsed {round(time.time()-t0)}s", flush=True)


def main():
    CACHE.mkdir(parents=True, exist_ok=True)
    todo = sys.argv[1:] or ORDER
    for wid in todo:
        build_window(wid)
    print("ALL DONE", flush=True)


if __name__ == "__main__":
    main()
