"""OKX OPEN public-data converter (NO Tardis).

Input: OKX public 'L2orderbook-400lv' daily archives (tar.gz containing one .data NDJSON file),
       lines = {"instId","action":"snapshot|update","ts":"<ms>","asks":[[px,sz,nOrd]...],"bids":[...]}
       and OKX public 'trades' daily zips (CSV: instrument_name,trade_id,side,price,size,created_time).

OKX BTC-USDT-SWAP: ctVal=0.01 ctValCcy=BTC ctMult=1 (confirmed via /api/v5/public/instruments).
  => amount_base_btc = size_contracts * 0.01 ;  amount_usd = amount_base_btc * price

Common internal schema (matches Binance recorder converter output):
  incremental_book_L2: exchange,symbol,timestamp(us),local_timestamp(us),is_snapshot(true/false),side(bid/ask),price,amount
  trades:              exchange,symbol,timestamp(us),local_timestamp(us),id,side(buy/sell),price,amount
RAW UNITS PRESERVED: book/trade 'amount' stays in CONTRACTS (raw). Conversion to BTC/USD is explicit downstream.
"""
from __future__ import annotations
import csv, gzip, io, json, tarfile, zipfile
from pathlib import Path

OKX_CTVAL = 0.01          # BTC per contract (confirmed via OKX public instruments API)
OKX_CTVALCCY = "BTC"
EXCH = "okex-swap"


def _data_member(tf: tarfile.TarFile):
    for m in tf.getmembers():
        if m.name.endswith(".data") or m.name.endswith(".csv") or m.isfile():
            return m
    return None


def iter_book_objs(tar_path, max_ts_ms=None):
    """Yield parsed NDJSON book objects from an OKX L2 tar.gz, in file order."""
    with tarfile.open(tar_path, "r:gz") as tf:
        m = _data_member(tf)
        f = tf.extractfile(m)
        for raw in f:
            if not raw:
                continue
            try:
                obj = json.loads(raw)
            except Exception:
                continue
            ts = int(obj.get("ts", 0))
            if max_ts_ms is not None and ts > max_ts_ms:
                break
            yield obj


def normalized_book_rows(tar_path, symbol="BTC-USDT-SWAP", max_ts_ms=None):
    """Yield common-schema L2 rows. amount = RAW CONTRACTS (size 0 => delete row)."""
    for obj in iter_book_objs(tar_path, max_ts_ms=max_ts_ms):
        ts_us = int(obj["ts"]) * 1000
        snap = obj.get("action") == "snapshot"
        for side, key in (("ask", "asks"), ("bid", "bids")):
            for lvl in obj.get(key, []):
                try:
                    price = float(lvl[0]); amt = float(lvl[1])
                except Exception:
                    continue
                yield (EXCH, symbol, ts_us, ts_us, "true" if snap else "false", side, price, amt)


def iter_trades(zip_path, symbol="BTC-USDT-SWAP", max_ts_ms=None):
    """Yield common-schema trade rows. amount = RAW CONTRACTS."""
    with zipfile.ZipFile(zip_path) as z:
        name = z.namelist()[0]
        with z.open(name) as fh:
            text = io.TextIOWrapper(fh, encoding="utf-8")
            r = csv.reader(text)
            header = next(r, None)
            for row in r:
                if len(row) < 6:
                    continue
                try:
                    tid = row[1]; side = row[2]; price = float(row[3]); size = float(row[4]); ts = int(row[5])
                except Exception:
                    continue
                if max_ts_ms is not None and ts > max_ts_ms:
                    break
                yield (EXCH, symbol, ts * 1000, ts * 1000, tid, side, price, size)


def write_sample_l2(tar_path, out_path, minutes=60, symbol="BTC-USDT-SWAP"):
    """Write first `minutes` of normalized L2 to gz CSV. Returns row count + first/last ts."""
    rows = 0; first = None; last = None; start_ms = None
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(out_path, "wt", encoding="utf-8", newline="") as out:
        w = csv.writer(out)
        w.writerow(["exchange", "symbol", "timestamp", "local_timestamp", "is_snapshot", "side", "price", "amount"])
        for obj in iter_book_objs(tar_path):
            ts = int(obj["ts"])
            if start_ms is None:
                start_ms = ts
            if ts > start_ms + minutes * 60 * 1000:
                break
            snap = obj.get("action") == "snapshot"
            for side, key in (("ask", "asks"), ("bid", "bids")):
                for lvl in obj.get(key, []):
                    try:
                        price = float(lvl[0]); amt = float(lvl[1])
                    except Exception:
                        continue
                    w.writerow([EXCH, symbol, ts * 1000, ts * 1000, "true" if snap else "false", side, price, amt])
                    rows += 1
                    if first is None:
                        first = ts
                    last = ts
    return {"rows": rows, "first_ts_ms": first, "last_ts_ms": last}


def write_sample_trades(zip_path, out_path, minutes=60, symbol="BTC-USDT-SWAP"):
    rows = 0; first = None; last = None; start_ms = None
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(out_path, "wt", encoding="utf-8", newline="") as out:
        w = csv.writer(out)
        w.writerow(["exchange", "symbol", "timestamp", "local_timestamp", "id", "side", "price", "amount"])
        for (ex, sym, ts_us, lt, tid, side, price, size) in iter_trades(zip_path):
            ms = ts_us // 1000
            if start_ms is None:
                start_ms = ms
            if ms > start_ms + minutes * 60 * 1000:
                break
            w.writerow([ex, sym, ts_us, lt, tid, side, price, size]); rows += 1
            if first is None:
                first = ms
            last = ms
    return {"rows": rows, "first_ts_ms": first, "last_ts_ms": last}
