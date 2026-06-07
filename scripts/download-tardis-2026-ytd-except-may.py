#!/usr/bin/env python3
"""Tardis YTD-2026 downloader (Jan-Apr only, May explicitly excluded).

Layout:
    data/tardis/binance-futures/BTCUSDT/{date}/{dataType}.csv.gz

200 -> OK, 404 -> SKIP, other failure -> ERROR.
Existing files (size > 1 KB) are kept and counted as EXISTS.
Summary at the end: downloaded / existing / skipped / failed.
"""
from __future__ import annotations

import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

EXCHANGE = os.environ.get("EXCHANGE", "binance-futures")
SYMBOL = os.environ.get("SYMBOL", "BTCUSDT")
OUT_ROOT = Path(os.environ.get("OUT_ROOT", "data/tardis"))
BASE_URL = "https://datasets.tardis.dev/v1"

# Only Jan-Apr 2026. May is current month and is intentionally excluded.
DATES = ["2026-01-01", "2026-02-01", "2026-03-01", "2026-04-01"]
DATA_TYPES = [
    "incremental_book_L2",
    "trades",
    "derivative_ticker",
    "book_ticker",
    "liquidations",
]

API_KEY = os.environ.get("TARDIS_API_KEY")
if API_KEY:
    print("Using TARDIS_API_KEY from environment.")
else:
    print("No TARDIS_API_KEY found. Using free first-day-of-month datasets.")

counts = {"downloaded": 0, "existing": 0, "skipped": 0, "failed": 0}


def download_one(url: str, outfile: Path) -> None:
    if outfile.exists() and outfile.stat().st_size > 1000:
        print(f"EXISTS {outfile} ({outfile.stat().st_size} bytes)")
        counts["existing"] += 1
        return

    outfile.parent.mkdir(parents=True, exist_ok=True)
    print(f"GET {url}")
    req = urllib.request.Request(url)
    if API_KEY:
        req.add_header("Authorization", f"Bearer {API_KEY}")

    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            with outfile.open("wb") as f:
                while True:
                    chunk = resp.read(1024 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
        size = outfile.stat().st_size
        print(f"OK {outfile} ({size} bytes)")
        counts["downloaded"] += 1
    except urllib.error.HTTPError as e:
        if outfile.exists():
            outfile.unlink()
        if e.code == 404:
            print(f"SKIP HTTP 404 {url}")
            counts["skipped"] += 1
        else:
            print(f"ERROR HTTP {e.code} {url}")
            counts["failed"] += 1
    except Exception as e:  # noqa: BLE001 - we want to surface every failure
        if outfile.exists():
            outfile.unlink()
        print(f"ERROR {url}: {e}")
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
    print(f"downloaded : {counts['downloaded']}")
    print(f"existing   : {counts['existing']}")
    print(f"skipped    : {counts['skipped']}   (404 - likely missing optional types)")
    print(f"failed     : {counts['failed']}    (other HTTP / network errors)")
    print()
    print(f"Output root: {OUT_ROOT}/{EXCHANGE}/{SYMBOL}/")
    print("Note: incremental_book_L2 and trades are mandatory; the others are optional.")
    return 0 if counts["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
