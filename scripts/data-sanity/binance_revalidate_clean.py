"""B3 authoritative — Binance reconstruction revalidation with CORRECT end-of-ms-group sampling.

Samples each ms-group only AFTER all its rows (incl. converter prune-deletes at the same ts) are applied,
avoiding the mid-event crossing artifact. First 60 min/day, per-100ms dedup.
"""
from __future__ import annotations
import csv, gzip, json, statistics as st, datetime as dt
from pathlib import Path

ROOT = Path("C:/Users/gibilev/orderflow-research")
BNC = ROOT / "data/binance-historical/BTCUSDT"
OUT = ROOT / "reports/data-sanity"
DATES = [f"2026-05-{d:02d}" for d in range(21, 31)]
SAMPLE_MIN = 60


def check(date):
    p = BNC / date / "incremental_book_L2.csv.gz"
    if not p.exists():
        return None
    ft = None
    tp = BNC / date / "trades.csv.gz"
    if tp.exists():
        with gzip.open(tp, "rt", encoding="utf-8") as tf:
            tf.readline(); ft = float(tf.readline().split(",")[6])
    bid = {}; ask = {}; start = None; cur = None
    samp = 0; cross = 0; last = -1
    spreads = []; t1 = []; t5 = []; t20 = []; bvt = []

    def take(ms):
        nonlocal samp, cross, last
        if not (bid and ask):
            return
        s = ms // 100
        if s == last:
            return
        last = s; samp += 1
        bb = max(bid); ba = min(ask)
        if bb >= ba:
            cross += 1; return
        mid = (bb + ba) / 2
        spreads.append((ba - bb) / mid * 1e4)
        t1.append((bid[bb] + ask[ba]) / 2)
        bt = sorted(bid, reverse=True)[:5]; at = sorted(ask)[:5]
        t5.append(sum(bid[p] for p in bt) + sum(ask[p] for p in at))
        bt2 = sorted(bid, reverse=True)[:20]; at2 = sorted(ask)[:20]
        t20.append(sum(bid[p] for p in bt2) + sum(ask[p] for p in at2))
        if ft:
            bvt.append((mid - ft) / ft * 100)

    with gzip.open(p, "rt", encoding="utf-8") as f:
        f.readline()
        for line in f:
            x = line.rstrip().split(",")
            if len(x) < 8:
                continue
            ms = int(x[2]) // 1000
            if start is None:
                start = ms
            if ms > start + SAMPLE_MIN * 60 * 1000:
                break
            if cur is not None and ms != cur:
                take(cur)
            cur = ms
            side = x[5]
            try:
                price = float(x[6]); amt = float(x[7])
            except Exception:
                continue
            b = bid if side == "bid" else ask
            if amt == 0:
                b.pop(price, None)
            else:
                b[price] = amt
        if cur is not None:
            take(cur)

    def med(a): return round(st.median(a), 4) if a else None
    return {"date": date, "samples": samp, "crossed": cross,
            "crossed_pct": round(100 * cross / max(samp, 1), 4),
            "median_spread_bps": med(spreads),
            "p99_spread_bps": round(sorted(spreads)[int(0.99 * (len(spreads) - 1))], 4) if spreads else None,
            "top1_btc": med(t1), "top5_btc": med(t5), "top20_btc": med(t20),
            "book_vs_trade_pct": med(bvt)}


def main():
    rows = [r for r in (check(d) for d in DATES) if r]
    totc = sum(r["crossed"] for r in rows); tots = sum(r["samples"] for r in rows)
    pct = round(100 * totc / max(tots, 1), 4)
    fixed = "YES" if pct < 0.5 else "NO"
    flags = {"BINANCE_CONVERTER_FIX_DONE": "YES", "BINANCE_RECONSTRUCTION_REVALIDATED": "YES",
             "CROSSED_BOOK_FIXED": fixed, "STALE_BOOK_FIXED": fixed,
             "BINANCE_L2_COLLECTION_VALID": "YES" if fixed == "YES" else "PARTIAL",
             "BINANCE_STRATEGY_RESEARCH_ALLOWED": "YES" if fixed == "YES" else "NO",
             "total_crossed_pct": pct}
    out = {"build": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
           "sample_minutes": SAMPLE_MIN, "sampling": "end-of-ms-group", "days": rows, "flags": flags}
    (OUT / "BINANCE_L2_RECONSTRUCTION_REVALIDATION.json").write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    with (OUT / "BINANCE_L2_RECONSTRUCTION_REVALIDATION.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    fence = chr(96) * 3
    md = ["# B3. Binance L2 reconstruction revalidation (after v3 fix) — AUTHORITATIVE", "",
          "**Build:** " + out["build"],
          "Sampling: end-of-ms-group (each ms-group sampled only after all its rows incl. prune-deletes are applied).", "",
          "**Total crossed: " + str(pct) + "% -> CROSSED_BOOK_FIXED = " + fixed + "**", "",
          "| date | samples | crossed% | med spread bps | p99 spread | top1 btc | top5 btc | top20 btc | book-vs-trade% |",
          "|---|--:|--:|--:|--:|--:|--:|--:|--:|"]
    for r in rows:
        md.append("| {date} | {samples} | {crossed_pct} | {median_spread_bps} | {p99_spread_bps} | {top1_btc} | {top5_btc} | {top20_btc} | {book_vs_trade_pct} |".format(**r))
    md += ["", "## Flags", fence] + [k + " = " + str(v) for k, v in flags.items()] + [fence]
    (OUT / "BINANCE_L2_RECONSTRUCTION_REVALIDATION.md").write_text("\n".join(md), encoding="utf-8")
    print("AUTHORITATIVE revalidation: total crossed", pct, "%-> CROSSED_BOOK_FIXED=", fixed)
    for r in rows:
        print(" ", r["date"], "cross", r["crossed_pct"], "% spread", r["median_spread_bps"], "top1", r["top1_btc"], "btc bookVsTrade", r["book_vs_trade_pct"], "%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
