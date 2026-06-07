"""
Probe + optionally download Tardis "first day of month" OKX-swap samples
for BTC-USDT-SWAP.

Tardis serves the 1st day of every calendar month FREE without an API key
on the URL pattern
    https://datasets.tardis.dev/v1/okex-swap/{datatype}/{YYYY}/{MM}/01/BTC-USDT-SWAP.csv.gz
The rest of the month requires Tardis paid credentials (we do not have any).

Modes:
    --mode probe                : HEAD-check every (date, datatype) and print a
                                 size table. No disk write. Safe to run blindly.
    --mode download --dates D,D : Download specific dates' files into
                                 data/okx-historical/BTC-USDT-SWAP/<date>/

Dates accepted: YYYY-MM-01 only (other days return 404 without credentials).

Example:
    python scripts/okx/download_okx_tardis_first_day_samples.py --mode probe
    python scripts/okx/download_okx_tardis_first_day_samples.py --mode download \
        --dates 2025-01-01,2025-07-01 --types incremental_book_L2,trades
"""

from __future__ import annotations
import argparse
import sys
import urllib.request
import urllib.error
from pathlib import Path

BASE = "https://datasets.tardis.dev/v1"
EXCHANGE = "okex-swap"
SYMBOL = "BTC-USDT-SWAP"
DEFAULT_TYPES = [
    "incremental_book_L2",
    "trades",
    "book_ticker",
    "derivative_ticker",
    "liquidations",
]
DEFAULT_DEST_ROOT = Path("data/okx-historical") / SYMBOL


def all_first_of_month_dates(start_year: int, end_year: int) -> list[str]:
    out: list[str] = []
    for y in range(start_year, end_year + 1):
        for m in range(1, 13):
            out.append(f"{y:04d}-{m:02d}-01")
    return out


def url_for(date: str, dt: str) -> str:
    yyyy, mm, dd = date.split("-")
    return f"{BASE}/{EXCHANGE}/{dt}/{yyyy}/{mm}/{dd}/{SYMBOL}.csv.gz"


def head_size(url: str) -> tuple[int | None, int]:
    """Return (size_bytes_or_None, http_status). Uses GET+Range because the
    Tardis CDN sometimes serves stale 404 to bare HEAD requests."""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "orderflow-research-okx-probe/1.0",
            "Range": "bytes=0-0",
            "Accept": "*/*",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            # When Range is honored, Content-Range tells full size:
            cr = r.headers.get("Content-Range", "")
            if cr:
                # form: "bytes 0-0/<TOTAL>"
                try:
                    total = int(cr.rsplit("/", 1)[-1])
                    return total, r.status
                except Exception:
                    pass
            cl = r.headers.get("Content-Length")
            if cl:
                return int(cl), r.status
            return None, r.status
    except urllib.error.HTTPError as e:
        return None, e.code
    except Exception:
        return None, -1


def cmd_probe(args: argparse.Namespace) -> int:
    dates = args.dates.split(",") if args.dates else all_first_of_month_dates(args.start_year, args.end_year)
    types = args.types.split(",") if args.types else DEFAULT_TYPES
    print(f"{'date':<12s}  " + "  ".join(f"{t:>22s}" for t in types))
    print("-" * (14 + (24 * len(types))))
    grand = {t: 0 for t in types}
    available_dates = 0
    for d in dates:
        row = [d]
        any_ok = False
        for t in types:
            size, status = head_size(url_for(d, t))
            if status == 200 and size is not None:
                row.append(f"{size/1e6:>20.1f}MB")
                grand[t] += size
                any_ok = True
            elif status == 200:
                row.append(f"{'200 ?MB':>22s}")
            else:
                row.append(f"{status:>22d}")
        if any_ok:
            available_dates += 1
        print(f"{d:<12s}  " + "  ".join(row[1:]))
    print("-" * (14 + (24 * len(types))))
    print(f"{'TOTAL':<12s}  " + "  ".join(f"{grand[t]/1e9:>20.2f}GB" for t in types))
    print()
    print(f"available dates (any datatype 200): {available_dates}/{len(dates)}")
    return 0


def cmd_download(args: argparse.Namespace) -> int:
    if not args.dates:
        print("--mode download requires --dates")
        return 2
    dates = args.dates.split(",")
    types = args.types.split(",") if args.types else DEFAULT_TYPES
    DEFAULT_DEST_ROOT.mkdir(parents=True, exist_ok=True)
    ok = True
    for d in dates:
        if not d.endswith("-01"):
            print(f"WARN: {d} is not a first-of-month date; Tardis paid tier required, skipping.")
            continue
        day_dir = DEFAULT_DEST_ROOT / d
        day_dir.mkdir(parents=True, exist_ok=True)
        for t in types:
            url = url_for(d, t)
            out = day_dir / f"{t}.csv.gz"
            if out.exists() and out.stat().st_size > 0:
                print(f"  skip (cached): {out}")
                continue
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "orderflow-research-okx-download/1.0",
                    "Range": "bytes=0-",
                    "Accept": "*/*",
                },
            )
            try:
                with urllib.request.urlopen(req, timeout=600) as r:
                    cl = r.headers.get("Content-Length")
                    print(f"GET {url}  ->  {out}  (~{int(cl)/1e6:.1f}MB)" if cl else f"GET {url}  ->  {out}")
                    with out.open("wb") as f:
                        while True:
                            chunk = r.read(1024 * 1024)
                            if not chunk:
                                break
                            f.write(chunk)
            except Exception as e:
                print(f"  FAIL {url}: {e!r}")
                ok = False
    return 0 if ok else 1


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=["probe", "download"], default="probe")
    p.add_argument("--dates", help="CSV YYYY-MM-DD list (only YYYY-MM-01 dates are free on Tardis)")
    p.add_argument("--types", help=f"CSV data types (default: {','.join(DEFAULT_TYPES)})")
    p.add_argument("--start-year", type=int, default=2024)
    p.add_argument("--end-year", type=int, default=2026)
    args = p.parse_args()
    if args.mode == "probe":
        return cmd_probe(args)
    return cmd_download(args)


if __name__ == "__main__":
    sys.exit(main())
