#!/usr/bin/env python3
"""
features_funding.py  --  Stage 1 / Tier-2: 1-second funding feature dataset.

Reads raw Bybit funding history (from fetch_funding_oi.py), forward-fills the
8-hourly settlement onto a 1-second grid, and emits per-day feature CSVs:

  funding_current      forward-filled funding rate at each second
  funding_24h_avg      rolling mean of funding_current over the last 86400 s
  funding_sign_flip    1 if sign(funding_current) changed vs the previous second

The 24h average needs the prior day, so each contiguous run of target dates is
computed on a grid that starts BUFFER_DAYS before the run (the raw CSV already
includes that buffer, fetched by fetch_funding_oi.py).

Output: <DATA_BYBIT>/derived/features_funding/features_funding_<date>.csv
        (86400 rows per day, 00:00:00..23:59:59 UTC).

Deps: pandas, numpy.
Run:  python features_funding.py [--input PATH] [--output-dir DIR]
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

DATA_BYBIT_ROOT = Path(os.environ.get("DATA_BYBIT_DIR", r"C:\orderflow-recoder module\data_bybit"))

CONFIG = {
    "INPUT_PATH": str(DATA_BYBIT_ROOT / "derived" / "funding_history_BTCUSDT.csv"),
    "OUTPUT_DIR": str(DATA_BYBIT_ROOT / "derived" / "features_funding"),
    "GRID_SECONDS": 1,
    "FUNDING_AVG_WINDOW_SEC": 86400,
    "BUFFER_DAYS": 1,
    "DATE_WINDOWS": ["2025-10-10", "2025-10-11", "2025-10-12",
                     "2026-06-02", "2026-06-03", "2026-06-04", "2026-06-05", "2026-06-06"],
}

REQUIRED_COLUMNS = ["timestamp_ms", "funding_rate"]


def date_to_ms_utc(date_str: str, hms: str) -> int:
    dt = datetime.strptime(f"{date_str} {hms}", "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def _shift_date(date_str: str, days: int) -> str:
    d = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc) + timedelta(days=days)
    return d.strftime("%Y-%m-%d")


def contiguous_runs(dates: list[str]) -> list[list[str]]:
    """Group sorted dates into runs of consecutive calendar days."""
    ds = sorted(dates)
    runs, cur = [], [ds[0]]
    for d in ds[1:]:
        if d == _shift_date(cur[-1], 1):
            cur.append(d)
        else:
            runs.append(cur); cur = [d]
    runs.append(cur)
    return runs


def load_raw(path: str) -> pd.DataFrame:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Raw funding not found at {p}. Run fetch_funding_oi.py first.")
    df = pd.read_csv(p)
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Expected columns {REQUIRED_COLUMNS}, got {list(df.columns)}")
    df["timestamp_ms"] = df["timestamp_ms"].astype("int64")
    df["funding_rate"] = df["funding_rate"].astype("float64")
    return df.drop_duplicates("timestamp_ms").sort_values("timestamp_ms").reset_index(drop=True)


def build_run(raw: pd.DataFrame, run: list[str], cfg: dict) -> pd.DataFrame:
    gstart = date_to_ms_utc(_shift_date(run[0], -cfg["BUFFER_DAYS"]), "00:00:00")
    gend = date_to_ms_utc(run[-1], "23:59:59")
    grid = np.arange(gstart, gend + 1, 1000 * cfg["GRID_SECONDS"], dtype=np.int64)

    rw = raw[(raw["timestamp_ms"] >= gstart) & (raw["timestamp_ms"] <= gend)]
    if rw.empty:
        print(f"[funding]   WARNING: no raw funding inside {_shift_date(run[0], -cfg['BUFFER_DAYS'])}"
              f"..{run[-1]} -> features will be NaN", file=sys.stderr)
        fc = pd.Series(np.nan, index=grid)
    else:
        # gap check (norm 8h settlement; warn if > 9h)
        gaps = np.diff(rw["timestamp_ms"].to_numpy())
        if (gaps > 9 * 3600 * 1000).any():
            print(f"[funding]   WARNING: funding gap > 9h in run {run[0]}..{run[-1]} "
                  f"(max {gaps.max()/3600000:.1f}h)", file=sys.stderr)
        ser = rw.set_index("timestamp_ms")["funding_rate"]
        fc = ser.reindex(grid, method="ffill")          # forward-fill onto 1s grid

    win = cfg["FUNDING_AVG_WINDOW_SEC"] // cfg["GRID_SECONDS"]
    avg = fc.rolling(window=win, min_periods=win).mean()

    sgn = np.sign(fc.to_numpy())
    prev_sgn = np.concatenate([[np.nan], sgn[:-1]])
    fcv = fc.to_numpy()
    nanmask = np.isnan(fcv) | np.concatenate([[True], np.isnan(fcv[:-1])])
    flip = (sgn != prev_sgn).astype(np.int64)
    flip[nanmask] = 0

    return pd.DataFrame({
        "timestamp_ms": grid,
        "funding_current": fc.to_numpy(),
        "funding_24h_avg": avg.to_numpy(),
        "funding_sign_flip": flip,
    })


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8"); sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Build 1s funding features from raw Bybit funding.")
    ap.add_argument("--input", default=CONFIG["INPUT_PATH"])
    ap.add_argument("--output-dir", default=CONFIG["OUTPUT_DIR"])
    args = ap.parse_args(argv)
    cfg = dict(CONFIG)
    out = Path(args.output_dir); out.mkdir(parents=True, exist_ok=True)

    raw = load_raw(args.input)
    print(f"[funding] raw: {len(raw)} funding records", file=sys.stderr)

    written = []
    for run in contiguous_runs(cfg["DATE_WINDOWS"]):
        run_df = build_run(raw, run, cfg)
        for date in run:
            s, e = date_to_ms_utc(date, "00:00:00"), date_to_ms_utc(date, "23:59:59")
            day = run_df[(run_df["timestamp_ms"] >= s) & (run_df["timestamp_ms"] <= e)].reset_index(drop=True)
            path = out / f"features_funding_{date}.csv"
            day.to_csv(path, index=False)
            nan_avg = int(day["funding_24h_avg"].isna().sum())
            print(f"[funding] {date}: {len(day)} rows, {nan_avg} NaN 24h_avg -> {path.name}", file=sys.stderr)
            written.append(date)
    print(f"[funding] Done: {len(written)} day files in {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
