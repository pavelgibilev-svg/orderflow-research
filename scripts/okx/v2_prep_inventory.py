"""Inventory OKX data on disk to prepare for zone_score_v2 dataset expansion.

For each first-of-month date 2024-01-01 .. 2026-05-01, record:
  - which data types are present locally
  - file sizes
  - whether the date has been used in calibration / OOS / not yet
  - whether full-day backtest output already exists

Also probe Tardis for which missing dates are available free (HEAD-via-Range
trick). Output a missing-dates list ready to feed the downloader.

Outputs:
  reports/OKX_DATASET_INVENTORY_FOR_SCORE_V2.md
  reports/OKX_DATASET_INVENTORY_FOR_SCORE_V2.json
"""
from __future__ import annotations
import json
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "package.json").exists() and (p / "scripts").exists())
DATA_ROOT = ROOT / "data" / "okx-historical" / "BTC-USDT-SWAP"
REPORTS = ROOT / "reports"

DATATYPES = ["incremental_book_L2", "trades", "book_ticker", "derivative_ticker", "liquidations"]

CALIB_DATES = {"2024-01-01", "2024-07-01", "2024-10-01", "2025-10-01", "2025-12-01", "2026-04-01"}
OOS_DATES = {"2025-04-01", "2025-05-01", "2024-05-01", "2024-09-01", "2024-06-01", "2025-11-01"}


def all_first_of_month_dates(start_y: int, end_y: int) -> list[str]:
    out: list[str] = []
    for y in range(start_y, end_y + 1):
        for m in range(1, 13):
            out.append(f"{y:04d}-{m:02d}-01")
    return out


def tardis_probe(date: str, dt: str) -> tuple[int | None, int]:
    """Return (size_bytes_or_None, http_status)."""
    yyyy, mm, dd = date.split("-")
    url = f"https://datasets.tardis.dev/v1/okex-swap/{dt}/{yyyy}/{mm}/{dd}/BTC-USDT-SWAP.csv.gz"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "orderflow-research-v2-inventory/1.0",
            "Range": "bytes=0-0",
            "Accept": "*/*",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            cr = r.headers.get("Content-Range", "")
            if cr:
                try:
                    total = int(cr.rsplit("/", 1)[-1])
                    return total, r.status
                except Exception:
                    pass
            cl = r.headers.get("Content-Length")
            if cl:
                try:
                    return int(cl), r.status
                except Exception:
                    pass
            return None, r.status
    except urllib.error.HTTPError as e:
        return None, e.code
    except Exception:
        return None, -1


def main() -> int:
    # Determine the range we care about: 2024-01-01 through the most recent
    # first-of-month that's published (cap at today's month, conservative).
    dates = all_first_of_month_dates(2024, 2026)
    # Cap at 2026-05-01 (last known available based on earlier probe)
    dates = [d for d in dates if d <= "2026-05-01"]

    rows: list[dict] = []
    on_disk_l2 = 0
    on_disk_trades = 0
    only_trades = 0
    full_l2 = 0
    total_bytes_on_disk = 0
    missing_l2_remote_free: list[str] = []
    missing_l2_remote_blocked: list[str] = []
    for d in dates:
        day = DATA_ROOT / d
        present: dict[str, dict] = {}
        bytes_here = 0
        for t in DATATYPES:
            p = day / f"{t}.csv.gz"
            if p.exists() and p.stat().st_size > 0:
                sz = p.stat().st_size
                present[t] = {"present": True, "size_bytes": sz}
                bytes_here += sz
            else:
                present[t] = {"present": False, "size_bytes": 0}
        total_bytes_on_disk += bytes_here
        has_l2 = present["incremental_book_L2"]["present"]
        has_trades = present["trades"]["present"]
        if has_l2:
            on_disk_l2 += 1
            full_l2 += 1
        if has_trades:
            on_disk_trades += 1
        if has_trades and not has_l2:
            only_trades += 1

        # If L2 missing, probe Tardis to see if it's free-available
        remote_l2: dict | None = None
        if not has_l2:
            size, status = tardis_probe(d, "incremental_book_L2")
            remote_l2 = {"status": status, "size_bytes": size}
            if status in (200, 206) and size is not None:
                missing_l2_remote_free.append(d)
            else:
                missing_l2_remote_blocked.append(d)

        # Replay status
        used_for = None
        if d in CALIB_DATES:
            used_for = "calibration"
        elif d in OOS_DATES:
            used_for = "OOS_v1"
        fullday_replay_exists = (REPORTS / f"OKX_TECHNICAL_REPLAY_{d}_fullday.json").exists() or \
                                (REPORTS / f"OKX_OOS_TECHNICAL_REPLAY_{d}_fullday.json").exists()

        rows.append({
            "date": d,
            "used_for": used_for,
            "fullday_replay_exists": fullday_replay_exists,
            "on_disk": {
                "incremental_book_L2_bytes": present["incremental_book_L2"]["size_bytes"],
                "trades_bytes": present["trades"]["size_bytes"],
                "book_ticker_bytes": present["book_ticker"]["size_bytes"],
                "derivative_ticker_bytes": present["derivative_ticker"]["size_bytes"],
                "liquidations_bytes": present["liquidations"]["size_bytes"],
                "total_bytes": bytes_here,
            },
            "has_full_l2_locally": has_l2,
            "has_trades_locally": has_trades,
            "only_trades_locally": (has_trades and not has_l2),
            "remote_l2_probe": remote_l2,
        })

    summary = {
        "dates_considered": len(dates),
        "dates_with_full_L2_on_disk": full_l2,
        "dates_with_trades_only": only_trades,
        "dates_with_trades_total": on_disk_trades,
        "calibration_dates": sorted(CALIB_DATES),
        "oos_v1_dates": sorted(OOS_DATES),
        "missing_L2_tardis_free": sorted(missing_l2_remote_free),
        "missing_L2_tardis_blocked": sorted(missing_l2_remote_blocked),
        "total_bytes_on_disk": total_bytes_on_disk,
        "total_gib_on_disk": round(total_bytes_on_disk / 1024**3, 2),
    }
    out = {
        "summary": summary,
        "datatypes_inventoried": DATATYPES,
        "per_date": rows,
    }
    (REPORTS / "OKX_DATASET_INVENTORY_FOR_SCORE_V2.json").write_text(
        json.dumps(out, indent=2), encoding="utf-8"
    )

    # --- Markdown ---
    md: list[str] = [
        "# OKX dataset inventory — preparing for `zone_score_v2`",
        "",
        f"**Build time:** {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} UTC",
        "**Venue:** OKX `okex-swap` BTC-USDT-SWAP",
        "**Period considered:** 2024-01-01 .. 2026-05-01 (29 first-of-month dates that Tardis publishes free).",
        "",
        "## A. Summary",
        "",
        f"- Dates with **full L2** on disk: **{summary['dates_with_full_L2_on_disk']}** / {summary['dates_considered']}",
        f"- Dates with **trades only** on disk: **{summary['dates_with_trades_only']}**",
        f"- Calibration set (v1 weight derivation, do not reuse for v2 selection): {', '.join(summary['calibration_dates'])}",
        f"- OOS-v1 set (v1 OOS test, do not reuse for v2 selection): {', '.join(summary['oos_v1_dates'])}",
        f"- Total OKX bytes on disk: **{summary['total_gib_on_disk']} GiB**",
        f"- Missing L2 dates that ARE free on Tardis: **{len(summary['missing_L2_tardis_free'])}** — {', '.join(summary['missing_L2_tardis_free'])}",
        f"- Missing L2 dates blocked by Tardis: **{len(summary['missing_L2_tardis_blocked'])}** — {', '.join(summary['missing_L2_tardis_blocked']) or '(none)'}",
        "",
        "## B. Per-date inventory",
        "",
        "| date | role | L2 | trades | bk-tick | deriv-tick | liq | full-day report | bytes (MiB) |",
        "|------|------|----|--------|---------|------------|-----|-----------------|------------:|",
    ]
    for r in rows:
        d = r["date"]
        role = r["used_for"] or "—"
        l2 = "✓" if r["has_full_l2_locally"] else ("·"
                                                  if (r["remote_l2_probe"] or {}).get("status") in (200, 206)
                                                  else "✗")
        tr = "✓" if r["has_trades_locally"] else "·"
        bk = "✓" if r["on_disk"]["book_ticker_bytes"] > 0 else "·"
        dv = "✓" if r["on_disk"]["derivative_ticker_bytes"] > 0 else "·"
        lq = "✓" if r["on_disk"]["liquidations_bytes"] > 0 else "·"
        rep = "✓" if r["fullday_replay_exists"] else "—"
        mib = r["on_disk"]["total_bytes"] / (1024 * 1024)
        md.append(f"| {d} | {role:<13s} | {l2:^2s} | {tr:^6s} | {bk:^7s} | {dv:^10s} | {lq:^3s} | {rep:^15s} | {mib:>10.1f} |")

    md.extend([
        "",
        "Legend: `✓` = present on disk; `·` = missing but free-downloadable from Tardis (or no probe needed for non-L2); `✗` = missing AND not free on Tardis.",
        "",
        "## C. Action plan for v2 dataset expansion",
        "",
        f"1. Download the {len(summary['missing_L2_tardis_free'])} L2 files marked free above (~{round(summary['total_gib_on_disk']/max(1,summary['dates_with_full_L2_on_disk'])*len(summary['missing_L2_tardis_free']), 1)} GiB estimated).",
        "2. Re-compute the regime table over all available dates → `OKX_EXPANDED_REGIME_TABLE_FOR_SCORE_V2.md`.",
        "3. Select ≥12 candidate dates for v2 full-day replay → `OKX_SCORE_V2_CANDIDATE_DATES.json`.",
        "4. Stop and ask for confirmation before launching the v2 full-day chain — estimated runtime is published in step 5 of the task brief.",
        "",
        "## D. What this inventory does NOT do",
        "",
        "- It does not score zones (v1 is archived).",
        "- It does not start a backtest.",
        "- It does not pay for any non-free Tardis dates.",
        "- It does not change strategy thresholds.",
        "",
        "Companion JSON: `reports/OKX_DATASET_INVENTORY_FOR_SCORE_V2.json`",
    ])
    (REPORTS / "OKX_DATASET_INVENTORY_FOR_SCORE_V2.md").write_text(
        "\n".join(md), encoding="utf-8"
    )

    print(f"wrote {REPORTS/'OKX_DATASET_INVENTORY_FOR_SCORE_V2.md'}")
    print(f"wrote {REPORTS/'OKX_DATASET_INVENTORY_FOR_SCORE_V2.json'}")
    print()
    print(f"  on-disk full L2: {summary['dates_with_full_L2_on_disk']} / {summary['dates_considered']}")
    print(f"  trades-only:     {summary['dates_with_trades_only']}")
    print(f"  total bytes:     {summary['total_gib_on_disk']} GiB")
    print(f"  missing L2 free: {summary['missing_L2_tardis_free']}")
    print(f"  missing L2 paid: {summary['missing_L2_tardis_blocked']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
