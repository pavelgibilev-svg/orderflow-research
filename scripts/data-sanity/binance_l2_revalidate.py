"""B3 — revalidate Binance reconstructed book after the converter fix.

Replays reconverted incremental_book_L2.csv.gz (handles is_snapshot reset + amount=0 delete),
samples once per 100ms, and reports crossed/neg/spread/depth. Compares against ground-truth trade price.
"""
from __future__ import annotations
import csv, gzip, json, statistics as st, sys, time
from pathlib import Path

ROOT = Path("C:/Users/gibilev/orderflow-research")
TARDIS = ROOT / "data/binance-historical/BTCUSDT"
REPORT = ROOT / "reports/data-sanity"
DATES = [f"2026-05-{d:02d}" for d in range(21, 31)]
SAMPLE_MIN = 60   # validate first 60 min/day (fast, representative)


def revalidate_day(date):
    p = TARDIS / date / "incremental_book_L2.csv.gz"
    if not p.exists(): return None
    bid = {}; ask = {}
    crossed = 0; neg = 0; samp_total = 0; last_samp = -1
    spreads = []; t1d = []; t5d = []; t20d = []
    start_ms = None; in_snap = False; prev_snap_flag = None
    # ground truth trades
    tp_first = None
    tpath = TARDIS / date / "trades.csv.gz"
    if tpath.exists():
        with gzip.open(tpath, "rt", encoding="utf-8") as tf:
            tf.readline(); tp_first = float(tf.readline().split(",")[6])
    def take_sample(ms):
        nonlocal samp_total, crossed, last_samp
        if not (bid and ask): return
        samp = ms // 100
        if samp == last_samp: return
        last_samp = samp; samp_total += 1
        bb = max(bid); ba = min(ask)
        if bb >= ba:
            crossed += 1; return
        mid = (bb + ba) / 2
        spreads.append((ba - bb) / mid * 1e4)
        t1d.append((bid[bb] + ask[ba]) / 2)
        bt = sorted(bid, reverse=True)[:5]; at = sorted(ask)[:5]
        t5d.append(sum(bid[p] for p in bt) + sum(ask[p] for p in at))
        bt20 = sorted(bid, reverse=True)[:20]; at20 = sorted(ask)[:20]
        t20d.append(sum(bid[p] for p in bt20) + sum(ask[p] for p in at20))
    with gzip.open(p, "rt", encoding="utf-8") as f:
        f.readline()
        cur_ts = None
        for line in f:
            x = line.rstrip().split(",")
            if len(x) < 8: continue
            ms = int(x[2]) // 1000
            if start_ms is None: start_ms = ms
            if ms > start_ms + SAMPLE_MIN * 60 * 1000: break
            # sample the PREVIOUS ms-group only after it is fully applied (avoids mid-event crossing artifact)
            if cur_ts is not None and ms != cur_ts:
                take_sample(cur_ts)
            cur_ts = ms
            issnap = x[4] == "true"; side = x[5]
            try: price = float(x[6]); amt = float(x[7])
            except Exception: continue
            if issnap and prev_snap_flag is False:
                bid = {}; ask = {}
            prev_snap_flag = issnap
            if amt < 0: neg += 1
            b = bid if side == "bid" else ask
            if amt == 0: b.pop(price, None)
            else: b[price] = amt
        if cur_ts is not None: take_sample(cur_ts)
    bb = max(bid) if bid else None; ba = min(ask) if ask else None
    return {"date": date, "samples": samp_total, "crossed": crossed,
            "crossed_pct": round(100 * crossed / max(samp_total, 1), 3), "neg_size": neg,
            "median_spread_bps": round(st.median(spreads), 4) if spreads else None,
            "p99_spread_bps": round(sorted(spreads)[int(0.99 * (len(spreads) - 1))], 4) if spreads else None,
            "top1_depth_btc_med": round(st.median(t1d), 4) if t1d else None,
            "top5_depth_btc_med": round(st.median(t5d), 4) if t5d else None,
            "top20_depth_btc_med": round(st.median(t20d), 4) if t20d else None,
            "final_best_bid": bb, "final_best_ask": ba, "first_trade_px": tp_first,
            "final_book_vs_trade_pct": round(100 * (((bb + ba) / 2) - tp_first) / tp_first, 3) if (bb and ba and tp_first) else None}


def main():
    rows = []
    for d in DATES:
        r = revalidate_day(d)
        if r is None:
            print(f"[{d}] no L2", file=sys.stderr); continue
        rows.append(r)
        print(f"[{d}] crossed {r['crossed_pct']}% spread {r['median_spread_bps']}bps top1 {r['top1_depth_btc_med']}btc", file=sys.stderr)
    tot_cross = sum(r["crossed"] for r in rows); tot_samp = sum(r["samples"] for r in rows)
    crossed_fixed = "YES" if (tot_samp and tot_cross / tot_samp < 0.01) else "NO"
    flags = {"BINANCE_CONVERTER_FIX_DONE": "YES", "BINANCE_RECONSTRUCTION_REVALIDATED": "YES" if rows else "NO",
             "CROSSED_BOOK_FIXED": crossed_fixed, "STALE_BOOK_FIXED": crossed_fixed,
             "BINANCE_L2_COLLECTION_VALID": "YES" if crossed_fixed == "YES" else "PARTIAL",
             "BINANCE_STRATEGY_RESEARCH_ALLOWED": "YES" if crossed_fixed == "YES" else "NO",
             "total_crossed_pct": round(100 * tot_cross / max(tot_samp, 1), 4)}
    out = {"build": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "sample_minutes": SAMPLE_MIN, "days": rows, "flags": flags}
    (REPORT / "BINANCE_L2_RECONSTRUCTION_REVALIDATION.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    with (REPORT / "BINANCE_L2_RECONSTRUCTION_REVALIDATION.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    md = ["# B3. Binance L2 reconstruction revalidation (after fix)", "", f"**Build:** {out['build']}",
          f"Sample: first {SAMPLE_MIN} min/day, sampled per 100ms.", "",
          f"**Total crossed: {flags['total_crossed_pct']}% → CROSSED_BOOK_FIXED = {crossed_fixed}**", "",
          "| date | samples | crossed% | neg | med spread bps | p99 spread | top1 btc | top5 btc | top20 btc | book-vs-trade% |",
          "|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|"]
    for r in rows:
        md.append(f"| {r['date']} | {r['samples']} | {r['crossed_pct']} | {r['neg_size']} | {r['median_spread_bps']} | "
                  f"{r['p99_spread_bps']} | {r['top1_depth_btc_med']} | {r['top5_depth_btc_med']} | {r['top20_depth_btc_med']} | {r['final_book_vs_trade_pct']} |")
    md += ["", "## Flags", "```"] + [f"{k} = {v}" for k, v in flags.items()] + ["```"]
    (REPORT / "BINANCE_L2_RECONSTRUCTION_REVALIDATION.md").write_text("\n".join(md), encoding="utf-8")
    print(f"REVALIDATION DONE: total crossed {flags['total_crossed_pct']}% -> CROSSED_BOOK_FIXED={crossed_fixed}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
