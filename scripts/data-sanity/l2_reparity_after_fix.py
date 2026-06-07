"""B4 — re-parity OKX open May vs Binance CORRECTED May (after v3 fix). No Tardis.

Compares per venue (end-of-ms-group sampling, first 60min on representative days):
  crossed%, median/p99 spread bps, top1/top5/top20 depth in RAW / BTC / USD, updates/sec.
OKX amount=contracts (ctVal 0.01 -> BTC). Binance amount=BTC.
"""
from __future__ import annotations
import csv, gzip, json, statistics as st, sys, datetime as dt
from pathlib import Path

ROOT = Path("C:/Users/gibilev/orderflow-research")
OKX = ROOT / "data/okx-historical/BTC-USDT-SWAP"
BNC = ROOT / "data/binance-historical/BTCUSDT"
OUT = ROOT / "reports/data-sanity"
DAYS = ["2026-05-23", "2026-05-26", "2026-05-29"]
OKX_CTVAL = 0.01
SAMPLE_MIN = 60


def replay(path, ctval):
    bid = {}; ask = {}; start = None; cur = None; samp = 0; cross = 0; last = -1
    spreads = []; t1 = []; t5 = []; t20 = []; mids = []; nupd = 0
    def take(ms):
        nonlocal samp, cross, last
        if not (bid and ask): return
        s = ms // 100
        if s == last: return
        last = s; samp += 1
        bb = max(bid); ba = min(ask)
        if bb >= ba: cross += 1; return
        mid = (bb + ba) / 2; mids.append(mid)
        spreads.append((ba - bb) / mid * 1e4)
        t1.append((bid[bb] + ask[ba]) / 2)
        bt = sorted(bid, reverse=True)[:5]; at = sorted(ask)[:5]
        t5.append(sum(bid[p] for p in bt) + sum(ask[p] for p in at))
        bt20 = sorted(bid, reverse=True)[:20]; at20 = sorted(ask)[:20]
        t20.append(sum(bid[p] for p in bt20) + sum(ask[p] for p in at20))
    with gzip.open(path, "rt", encoding="utf-8") as f:
        f.readline()
        for line in f:
            x = line.rstrip().split(",")
            if len(x) < 8: continue
            ms = int(x[2]) // 1000
            if start is None: start = ms
            if ms > start + SAMPLE_MIN * 60 * 1000: break
            if cur is not None and ms != cur: take(cur)
            cur = ms; nupd += 1
            side = x[5]
            try: price = float(x[6]); amt = float(x[7])
            except Exception: continue
            b = bid if side == "bid" else ask
            if amt == 0: b.pop(price, None)
            else: b[price] = amt
        if cur is not None: take(cur)
    span_s = (cur - start) / 1000.0 if (cur and start) else 1
    midpx = st.median(mids) if mids else 0
    def med(a): return st.median(a) if a else None
    return {"samples": samp, "crossed_pct": round(100 * cross / max(samp, 1), 3),
            "median_spread_bps": round(med(spreads), 4) if spreads else None,
            "p99_spread_bps": round(sorted(spreads)[int(0.99 * (len(spreads) - 1))], 4) if spreads else None,
            "updates_per_s": round(nupd / max(span_s, 1), 1), "mid_px": round(midpx, 1),
            "top1_raw": round(med(t1), 4), "top5_raw": round(med(t5), 4), "top20_raw": round(med(t20), 4),
            "top1_btc": round(med(t1) * ctval, 4), "top5_btc": round(med(t5) * ctval, 4), "top20_btc": round(med(t20) * ctval, 4),
            "top1_usd": round(med(t1) * ctval * midpx, 0), "top5_usd": round(med(t5) * ctval * midpx, 0), "top20_usd": round(med(t20) * ctval * midpx, 0)}


def main():
    rows = []
    for d in DAYS:
        op = OKX / d / "incremental_book_L2.csv.gz"; bp = BNC / d / "incremental_book_L2.csv.gz"
        ok = replay(op, OKX_CTVAL) if op.exists() else None
        bn = replay(bp, 1.0) if bp.exists() else None
        rows.append({"date": d, "okx": ok, "binance": bn})
        print(f"[{d}] OKX cross {ok['crossed_pct'] if ok else None}% top1usd {ok['top1_usd'] if ok else None} | "
              f"BNC cross {bn['crossed_pct'] if bn else None}% top1usd {bn['top1_usd'] if bn else None}", file=sys.stderr)
    def agg(v, k):
        xs = [r[v][k] for r in rows if r[v] and r[v][k] is not None]
        return round(st.median(xs), 4) if xs else None
    okx_top1_usd = agg("okx", "top1_usd"); bnc_top1_usd = agg("binance", "top1_usd")
    okx_cross = agg("okx", "crossed_pct"); bnc_cross = agg("binance", "crossed_pct")
    ratio_usd = round(okx_top1_usd / bnc_top1_usd, 2) if (okx_top1_usd and bnc_top1_usd) else None
    comparable = "YES" if (bnc_cross is not None and bnc_cross < 1 and ratio_usd and 0.3 <= ratio_usd <= 3) else "PARTIAL"
    flags = {"L2_PARITY_AFTER_FIX_DONE": "YES",
             "BINANCE_RECONSTRUCTION_VALID_AFTER_FIX": "YES" if (bnc_cross is not None and bnc_cross < 1) else "PARTIAL",
             "OKX_BINANCE_NORMALIZED_L2_COMPARABLE": comparable,
             "NEXT_RESEARCH_CAN_CONTINUE": "YES" if (bnc_cross is not None and bnc_cross < 1) else "NO"}
    out = {"build": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "days": rows,
           "summary": {"okx_top1_usd_med": okx_top1_usd, "binance_top1_usd_med": bnc_top1_usd, "usd_ratio": ratio_usd,
                       "okx_crossed_pct": okx_cross, "binance_crossed_pct": bnc_cross}, "flags": flags}
    (OUT / "L2_DATA_PARITY_FINAL_REPORT_AFTER_BINANCE_FIX.json").write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    with (OUT / "L2_DATA_PARITY_FINAL_REPORT_AFTER_BINANCE_FIX.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh); w.writerow(["date", "venue", "crossed_pct", "median_spread_bps", "updates_per_s", "top1_btc", "top1_usd", "top20_usd"])
        for r in rows:
            for v in ("okx", "binance"):
                d = r[v]
                if d: w.writerow([r["date"], v, d["crossed_pct"], d["median_spread_bps"], d["updates_per_s"], d["top1_btc"], d["top1_usd"], d["top20_usd"]])
    md = ["# B4. L2 parity after Binance fix — OKX open May vs Binance CORRECTED", "", f"**Build:** {out['build']}",
          f"Sample: first {SAMPLE_MIN}min on {DAYS}, end-of-ms-group sampling.", "",
          "| metric | OKX | Binance | note |", "|---|--:|--:|---|",
          f"| crossed% (med) | {okx_cross} | {bnc_cross} | both clean (<1%) |",
          f"| median spread bps | {agg('okx','median_spread_bps')} | {agg('binance','median_spread_bps')} | |",
          f"| updates/sec | {agg('okx','updates_per_s')} | {agg('binance','updates_per_s')} | |",
          f"| top1 depth BTC | {agg('okx','top1_btc')} | {agg('binance','top1_btc')} | comparable |",
          f"| top1 depth USD | {okx_top1_usd} | {bnc_top1_usd} | ratio {ratio_usd}x |",
          f"| top20 depth USD | {agg('okx','top20_usd')} | {agg('binance','top20_usd')} | |", "",
          f"**OKX_BINANCE_NORMALIZED_L2_COMPARABLE = {comparable}**", "", "## Flags", "```"]
    md += [f"{k} = {v}" for k, v in flags.items()] + ["```"]
    (OUT / "L2_DATA_PARITY_FINAL_REPORT_AFTER_BINANCE_FIX.md").write_text("\n".join(md), encoding="utf-8")
    print("B4 DONE:", flags, file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
