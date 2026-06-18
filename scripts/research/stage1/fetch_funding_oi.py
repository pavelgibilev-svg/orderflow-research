#!/usr/bin/env python3
"""
fetch_funding_oi.py  --  Stage 1 / Tier-2: download Bybit funding + open interest.

Public Bybit V5 market REST (no API key, no secrets, read-only market data). Saves
raw funding-rate and open-interest history for the 8 geometry days
(2025-10-10..12 + 2026-06-02..06, BTCUSDT linear perpetual) to CSV.

A 1-DAY buffer is fetched BEFORE each window start so the 24h funding average
(features_funding.py) and the 30-min OI delta (features_oi.py) have history at
the day boundary (per the TZ §2 refinement).

Output (next to the existing ob200/trades data): <DATA_BYBIT>/derived/
  funding_history_BTCUSDT.csv   columns: timestamp_ms, funding_rate, symbol
  oi_history_BTCUSDT_5min.csv   columns: timestamp_ms, open_interest, symbol

<DATA_BYBIT> defaults to the external data dir and can be overridden with the
DATA_BYBIT_DIR env var or --output-dir. Output is NOT inside the git repo.

Deps: requests, pandas.

Run:  python fetch_funding_oi.py [--output-dir DIR]
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import unquote

import pandas as pd
import requests

DATA_BYBIT_ROOT = Path(os.environ.get("DATA_BYBIT_DIR", r"C:\orderflow-recoder module\data_bybit"))

CONFIG = {
    "SYMBOL": "BTCUSDT",
    "CATEGORY": "linear",                 # USDT perpetual
    "DATE_WINDOWS": [("2025-10-10", "2025-10-12"), ("2026-06-02", "2026-06-06")],
    "BUFFER_DAYS": 1,                     # fetch this many days before each window start
    "OI_INTERVAL": "5min",
    "REQUEST_DELAY_MS": 100,
    "MAX_RETRIES": 5,
    "RETRY_BACKOFF_BASE_S": 1.0,          # 1s -> 2s -> 4s -> 8s -> 16s
    "OUTPUT_DIR": str(DATA_BYBIT_ROOT / "derived"),
    "BYBIT_BASE_URL": "https://api.bybit.com",
    "PAGE_LIMIT": 200,
    "MAX_PAGES": 60,                      # safety cap on cursor pagination
}


def date_to_ms_utc(date_str: str, hms: str) -> int:
    dt = datetime.strptime(f"{date_str} {hms}", "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def _buffered_start(date_str: str, buffer_days: int) -> str:
    d = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc) - timedelta(days=buffer_days)
    return d.strftime("%Y-%m-%d")


def _request(url: str, params: dict, cfg: dict) -> dict:
    """One GET with retry/backoff on 429/5xx/network. Bybit retCode!=0 -> raise (not retried)."""
    for attempt in range(cfg["MAX_RETRIES"]):
        try:
            r = requests.get(url, params=params, timeout=20)
            if r.status_code == 429 or r.status_code >= 500:
                raise requests.HTTPError(f"HTTP {r.status_code}")
            try:
                data = r.json()
            except ValueError as e:
                print(f"[fetch] ERROR: invalid JSON from {url}: {e}", file=sys.stderr)
                raise
            if data.get("retCode") not in (0, "0", None):
                raise RuntimeError(f"Bybit retCode={data.get('retCode')} retMsg={data.get('retMsg')}")
            return data
        except RuntimeError:
            raise                                   # application error -> not recoverable
        except (requests.RequestException, ValueError) as e:
            wait = cfg["RETRY_BACKOFF_BASE_S"] * (2 ** attempt)
            print(f"[fetch]   retry {attempt + 1}/{cfg['MAX_RETRIES']} after "
                  f"{type(e).__name__} ({e}); sleep {wait:.0f}s", file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError(f"max retries exceeded: {url} params={params}")


def paginated_get(path: str, base_params: dict, cfg: dict):
    """GET with Bybit cursor pagination (OI) or single page (funding). Returns (list, n_calls)."""
    url = cfg["BYBIT_BASE_URL"] + path
    out, cursor, seen, calls = [], None, set(), 0
    for _ in range(cfg["MAX_PAGES"]):
        params = dict(base_params)
        if cursor:
            params["cursor"] = unquote(cursor)      # Bybit returns URL-encoded cursor; decode -> requests re-encodes once
        data = _request(url, params, cfg)
        calls += 1
        result = data.get("result") or {}
        page = result.get("list") or []
        out.extend(page)
        cursor = result.get("nextPageCursor")
        if not cursor or cursor in seen or not page:
            break
        seen.add(cursor)
        time.sleep(cfg["REQUEST_DELAY_MS"] / 1000.0)
    return out, calls


def fetch_funding(cfg: dict) -> pd.DataFrame:
    rows = []
    for start_date, end_date in cfg["DATE_WINDOWS"]:
        bstart = _buffered_start(start_date, cfg["BUFFER_DAYS"])
        s, e = date_to_ms_utc(bstart, "00:00:00"), date_to_ms_utc(end_date, "23:59:59")
        recs, calls = paginated_get("/v5/market/funding/history",
                                    {"category": cfg["CATEGORY"], "symbol": cfg["SYMBOL"],
                                     "startTime": s, "endTime": e, "limit": cfg["PAGE_LIMIT"]}, cfg)
        n = 0
        for r in recs:
            ts = int(r["fundingRateTimestamp"])
            if s <= ts <= e:
                rows.append({"timestamp_ms": ts, "funding_rate": float(r["fundingRate"]),
                             "symbol": r.get("symbol", cfg["SYMBOL"])})
                n += 1
        print(f"[fetch]   Window {bstart}..{end_date}: {n} records ({calls} API call(s))", file=sys.stderr)
        if not recs:
            print(f"[fetch]   WARNING: empty funding for window {bstart}..{end_date}", file=sys.stderr)
    return (pd.DataFrame(rows, columns=["timestamp_ms", "funding_rate", "symbol"])
            .drop_duplicates("timestamp_ms").sort_values("timestamp_ms").reset_index(drop=True))


def fetch_open_interest(cfg: dict) -> pd.DataFrame:
    rows = []
    for start_date, end_date in cfg["DATE_WINDOWS"]:
        bstart = _buffered_start(start_date, cfg["BUFFER_DAYS"])
        s, e = date_to_ms_utc(bstart, "00:00:00"), date_to_ms_utc(end_date, "23:59:59")
        recs, calls = paginated_get("/v5/market/open-interest",
                                    {"category": cfg["CATEGORY"], "symbol": cfg["SYMBOL"],
                                     "intervalTime": cfg["OI_INTERVAL"],
                                     "startTime": s, "endTime": e, "limit": cfg["PAGE_LIMIT"]}, cfg)
        n = 0
        for r in recs:
            ts = int(r["timestamp"])
            if s <= ts <= e:
                rows.append({"timestamp_ms": ts, "open_interest": float(r["openInterest"]),
                             "symbol": cfg["SYMBOL"]})
                n += 1
        print(f"[fetch]   Window {bstart}..{end_date}: {n} records ({calls} API call(s))", file=sys.stderr)
        if not recs:
            print(f"[fetch]   WARNING: empty OI for window {bstart}..{end_date} "
                  f"(Bybit OI history retention may not cover this range)", file=sys.stderr)
    return (pd.DataFrame(rows, columns=["timestamp_ms", "open_interest", "symbol"])
            .drop_duplicates("timestamp_ms").sort_values("timestamp_ms").reset_index(drop=True))


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Fetch Bybit funding + open interest (public REST).")
    ap.add_argument("--output-dir", default=CONFIG["OUTPUT_DIR"])
    args = ap.parse_args(argv)
    cfg = dict(CONFIG)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    print("[fetch] Fetching funding history for BTCUSDT...", file=sys.stderr)
    fdf = fetch_funding(cfg)
    fpath = out / "funding_history_BTCUSDT.csv"
    fdf.to_csv(fpath, index=False)
    print(f"[fetch] Total: {len(fdf)} funding records -> {fpath}", file=sys.stderr)

    print(f"\n[fetch] Fetching OI history ({cfg['OI_INTERVAL']}) for BTCUSDT...", file=sys.stderr)
    odf = fetch_open_interest(cfg)
    opath = out / f"oi_history_BTCUSDT_{cfg['OI_INTERVAL']}.csv"
    odf.to_csv(opath, index=False)
    print(f"[fetch] Total: {len(odf)} OI records -> {opath}", file=sys.stderr)

    # ---- sanity ----
    print(f"\n[fetch] Sanity: funding {len(fdf)} records, OI {len(odf)} records.", file=sys.stderr)
    if len(fdf):
        lo, hi = float(fdf["funding_rate"].min()), float(fdf["funding_rate"].max())
        flag = "  [!! outside +/-0.01]" if (lo < -0.01 or hi > 0.01) else ""
        print(f"[fetch]   funding_rate min/max: {lo:.6f} / {hi:.6f}{flag}", file=sys.stderr)
    if len(odf):
        lo, hi = float(odf["open_interest"].min()), float(odf["open_interest"].max())
        flag = "  [!! outside 50k-200k BTC]" if (lo < 50000 or hi > 200000) else ""
        print(f"[fetch]   open_interest min/max: {lo:.1f} / {hi:.1f} BTC{flag}", file=sys.stderr)
    print("[fetch] Done.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
