#!/usr/bin/env python3
"""Tardis Binance Futures BTCUSDT 2025 first-of-month downloader.

Layout:
    data/tardis/binance-futures/BTCUSDT/{date}/{dataType}.csv.gz

NO API key required for first-of-month dates. Existing files (>1 KB) kept.
"""
from __future__ import annotations
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

EXCHANGE = "binance-futures"
SYMBOL = "BTCUSDT"
OUT_ROOT = Path(os.environ.get("OUT_ROOT", "data/tardis"))
BASE_URL = "https://datasets.tardis.dev/v1"

DATES = [f"2025-{m:02d}-01" for m in range(1, 13)]   # 12 first-of-month 2025
DATA_TYPES = [
    "incremental_book_L2",
    "trades",
    "derivative_ticker",
    "book_ticker",
    "liquidations",
]

API_KEY = os.environ.get("TARDIS_API_KEY")
counts = {"downloaded": 0, "existing": 0, "skipped": 0, "failed": 0}


def download_one(url: str, outfile: Path) -> None:
    if outfile.exists() and outfile.stat().st_size > 1000:
        print(f"EXISTS {outfile} ({outfile.stat().st_size} bytes)", flush=True)
        counts["existing"] += 1
        return
    outfile.parent.mkdir(parents=True, exist_ok=True)
    print(f"GET {url}", flush=True)
    req = urllib.request.Request(url)
    if API_KEY:
        req.add_header("Authorization", f"Bearer {API_KEY}")
    started = time.time()
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            with outfile.open("wb") as f:
                while True:
                    chunk = resp.read(2 * 1024 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
        size = outfile.stat().st_size
        print(f"OK {outfile} ({size:,} bytes, {time.time()-started:.1f}s)", flush=True)
        counts["downloaded"] += 1
    except urllib.error.HTTPError as e:
        if outfile.exists():
            outfile.unlink()
        if e.code == 404:
            print(f"SKIP HTTP 404 {url}", flush=True)
            counts["skipped"] += 1
        else:
            print(f"ERROR HTTP {e.code} {url}", flush=True)
            counts["failed"] += 1
    except Exception as e:
        if outfile.exists():
            outfile.unlink()
        print(f"ERROR {url}: {e}", flush=True)
        counts["failed"] += 1


def main() -> int:
    for date in DATES:
        yyyy, mm, dd = date.split("-")
        date_dir = OUT_ROOT / EXCHANGE / SYMBOL / date
        for data_type in DATA_TYPES:
            url = f"{BASE_URL}/{EXCHANGE}/{data_type}/{yyyy}/{mm}/{dd}/{SYMBOL}.csv.gz"
            outfile = date_dir / f"{data_type}.csv.gz"
            download_one(url, outfile)
    print()
    print("==== SUMMARY ====")
    for k, v in counts.items():
        print(f"{k:10s}: {v}")
    return 0 if counts["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
