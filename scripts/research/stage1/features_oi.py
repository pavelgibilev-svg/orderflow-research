#!/usr/bin/env python3
"""
features_oi.py  --  Stage 1 / Tier-2: 1-second open-interest feature dataset.

Reads raw Bybit open interest (5-min, from fetch_funding_oi.py), forward-fills it
onto a 1-second grid, and emits per-day feature CSVs with multi-window deltas:

  oi_current        forward-filled OI (BTC) at each second
  delta_oi_60s/5m/30m       oi_t - oi_{t-60/300/1800}
  delta_oi_60s/5m/30m_pct   (oi_t - oi_{t-N}) / oi_{t-N} * 100   (NaN if oi_{t-N}==0)

Each contiguous run of target dates is computed on a grid that starts BUFFER_DAYS
before the run, so the 30-min delta is defined at the day boundary (the raw CSV
already includes that buffer). NOT done this iteration: oi_intensity (trade-volume
normalisation).

Output: <DATA_BYBIT>/derived/features_oi/features_oi_<date>.csv
        (86400 rows per day, 00:00:00..23:59:59 UTC).

Deps: pandas, numpy.
Run:  python features_oi.py [--input PATH] [--output-dir DIR]
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
    "INPUT_PATH": str(DATA_BYBIT_ROOT / "derived" / "oi_history_BTCUSDT_5min.csv"),
    "OUTPUT_DIR": str(DATA_BYBIT_ROOT / "derived" / "features_oi"),
    "GRID_SECONDS": 1,
    "WINDOWS_SEC": [60, 300, 1800],       # 60s, 5m, 30m
    "BUFFER_DAYS": 1,
    "DATE_WINDOWS": ["2025-10-10", "2025-10-11", "2025-10-12",
                     "2026-06-02", "2026-06-03", "2026-06-04", "2026-06-05", "2026-06-06"],
}

REQUIRED_COLUMNS = ["timestamp_ms", "open_interest"]
WINDOW_LABEL = {60: "60s", 300: "5m", 1800: "30m"}


def date_to_ms_utc(date_str: str, hms: str) -> int:
    dt = datetime.strptime(f"{date_str} {hms}", "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def _shift_date(date_str: str, days: int) -> str:
    d = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc) + timedelta(days=days)
    return d.strftime("%Y-%m-%d")


def contiguous_runs(dates: list[str]) -> list[list[str]]:
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
        raise FileNotFoundError(f"Raw OI not found at {p}. Run fetch_funding_oi.py first.")
    df = pd.read_csv(p)
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Expected columns {REQUIRED_COLUMNS}, got {list(df.columns)}")
    df["timestamp_ms"] = df["timestamp_ms"].astype("int64")
    df["open_interest"] = df["open_interest"].astype("float64")
    return df.drop_duplicates("timestamp_ms").sort_values("timestamp_ms").reset_index(drop=True)


def build_run(raw: pd.DataFrame, run: list[str], cfg: dict) -> pd.DataFrame:
    gstart = date_to_ms_utc(_shift_date(run[0], -cfg["BUFFER_DAYS"]), "00:00:00")
    gend = date_to_ms_utc(run[-1], "23:59:59")
    grid = np.arange(gstart, gend + 1, 1000 * cfg["GRID_SECONDS"], dtype=np.int64)

    rw = raw[(raw["timestamp_ms"] >= gstart) & (raw["timestamp_ms"] <= gend)]
    if rw.empty:
        print(f"[oi]   WARNING: no raw OI inside {_shift_date(run[0], -cfg['BUFFER_DAYS'])}"
              f"..{run[-1]} -> features will be NaN", file=sys.stderr)
        oi = pd.Series(np.nan, index=grid)
    else:
        oi = rw.set_index("timestamp_ms")["open_interest"].reindex(grid, method="ffill")

    cols = {"timestamp_ms": grid, "oi_current": oi.to_numpy()}
    oiv = oi.to_numpy()
    for w in cfg["WINDOWS_SEC"]:
        k = w // cfg["GRID_SECONDS"]
        prev = np.concatenate([np.full(k, np.nan), oiv[:-k]]) if k < oiv.size else np.full(oiv.size, np.nan)
        delta = oiv - prev
        with np.errstate(divide="ignore", invalid="ignore"):
            pct = np.where((prev != 0) & np.isfinite(prev), (oiv - prev) / prev * 100.0, np.nan)
        cols[f"delta_oi_{WINDOW_LABEL[w]}"] = delta
        cols[f"delta_oi_{WINDOW_LABEL[w]}_pct"] = pct
    order = (["timestamp_ms", "oi_current"]
             + [f"delta_oi_{WINDOW_LABEL[w]}" for w in cfg["WINDOWS_SEC"]]
             + [f"delta_oi_{WINDOW_LABEL[w]}_pct" for w in cfg["WINDOWS_SEC"]])
    return pd.DataFrame(cols)[order]


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8"); sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Build 1s OI features from raw Bybit open interest.")
    ap.add_argument("--input", default=CONFIG["INPUT_PATH"])
    ap.add_argument("--output-dir", default=CONFIG["OUTPUT_DIR"])
    args = ap.parse_args(argv)
    cfg = dict(CONFIG)
    out = Path(args.output_dir); out.mkdir(parents=True, exist_ok=True)

    raw = load_raw(args.input)
    print(f"[oi] raw: {len(raw)} OI records", file=sys.stderr)

    written = []
    for run in contiguous_runs(cfg["DATE_WINDOWS"]):
        run_df = build_run(raw, run, cfg)
        for date in run:
            s, e = date_to_ms_utc(date, "00:00:00"), date_to_ms_utc(date, "23:59:59")
            day = run_df[(run_df["timestamp_ms"] >= s) & (run_df["timestamp_ms"] <= e)].reset_index(drop=True)
            path = out / f"features_oi_{date}.csv"
            day.to_csv(path, index=False)
            nan_oi = int(day["oi_current"].isna().sum())
            print(f"[oi] {date}: {len(day)} rows, {nan_oi} NaN oi_current -> {path.name}", file=sys.stderr)
            written.append(date)
    print(f"[oi] Done: {len(written)} day files in {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
