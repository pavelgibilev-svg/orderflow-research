"""
Download OKX-swap BTC-USDT-SWAP 2026-04-01 sample via Tardis CDN.

The Tardis CDN distributes OKX historical data with the free-first-of-month
policy. 2026-04-01 is the 1st of April -> free without an API key. For
other days in the week, Tardis requires an API key (which we do not have),
and OKX's own download channel is gated behind login + paid tier.

The Range header is sent because a bare GET sometimes 404s on this CDN
(server-side cache quirk); Range gets a clean 200 with the full body.
"""
from __future__ import annotations
import sys
import urllib.request
from pathlib import Path

DEST = Path("data/okx-historical/BTC-USDT-SWAP/2026-04-01")
DATE = ("2026", "04", "01")
EXCHANGE = "okex-swap"
SYMBOL = "BTC-USDT-SWAP"

# Channels we want and their Tardis dataType slugs.
DATATYPES = [
    "incremental_book_L2",  # primary L2 delta stream
    "trades",
    "derivative_ticker",    # funding + mark price + open interest
    "book_ticker",          # best bid/ask updates
    "liquidations",
]

BASE = "https://datasets.tardis.dev/v1"


def main() -> int:
    DEST.mkdir(parents=True, exist_ok=True)
    yyyy, mm, dd = DATE
    summary = []
    for t in DATATYPES:
        url = f"{BASE}/{EXCHANGE}/{t}/{yyyy}/{mm}/{dd}/{SYMBOL}.csv.gz"
        out = DEST / f"{t}.csv.gz"
        if out.exists() and out.stat().st_size > 0:
            print(f"SKIP {t}: already exists ({out.stat().st_size:,} bytes)")
            summary.append((t, out.stat().st_size, "cached"))
            continue
        headers = {
            "User-Agent": "orderflow-research-okx-audit/1.0",
            # Range below kicks the CDN out of a cached 404 it sometimes returns.
            "Range": "bytes=0-",
        }
        req = urllib.request.Request(url, headers=headers)
        print(f"GET {url}")
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                cl = r.headers.get("Content-Length")
                ct = r.headers.get("Content-Type")
                print(f"  status={r.status} content_type={ct} content_length={cl}")
                bytes_written = 0
                with out.open("wb") as f:
                    while True:
                        chunk = r.read(1024 * 1024)
                        if not chunk:
                            break
                        f.write(chunk)
                        bytes_written += len(chunk)
                        if bytes_written % (32 * 1024 * 1024) == 0:
                            pct = (bytes_written / int(cl)) * 100 if cl else 0
                            print(f"    {bytes_written:,} bytes ({pct:.1f}%)")
                print(f"  saved -> {out}  ({bytes_written:,} bytes)")
                summary.append((t, bytes_written, "downloaded"))
        except Exception as e:
            print(f"  FAIL: {e!r}")
            summary.append((t, 0, f"error: {e!r}"))

    print("=" * 60)
    print(f"{'datatype':<24s} {'bytes':>14s}  status")
    for t, b, s in summary:
        print(f"{t:<24s} {b:>14,d}  {s}")
    return 0 if all(s == "downloaded" or s == "cached" for _, _, s in summary) else 1


if __name__ == "__main__":
    sys.exit(main())
