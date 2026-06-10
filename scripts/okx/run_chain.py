"""Strictly-sequential runner for OKX technical replays.

Spawns `npm run backtest:okx-technical -- --date <D> --window <W>` for each
date in the given list, waits for each child to FULLY exit before launching
the next. Avoids the orphan/parallel mess that a Bash-killed for-loop can
create on Windows.

Usage:
    python scripts/okx/run_chain.py --window 3h --dates 2024-07-01,2024-10-01,2025-10-01,2025-12-01
"""
from __future__ import annotations
import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "package.json").exists() and (p / "scripts").exists())


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dates", required=True)
    p.add_argument("--window", default="3h")
    args = p.parse_args()
    dates = [d.strip() for d in args.dates.split(",") if d.strip()]
    log_path = ROOT / "data" / "okx-historical" / f"_chain_{args.window}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    overall_start = time.time()
    print(f"[chain] dates={dates} window={args.window}")
    print(f"[chain] log -> {log_path}")
    for i, d in enumerate(dates, 1):
        started = time.time()
        marker = f"=== [{i}/{len(dates)}] {d} START {time.strftime('%H:%M:%S')} ==="
        print(marker, flush=True)
        with log_path.open("a", encoding="utf-8") as logf:
            logf.write(marker + "\n")
        cmd = [
            "npm.cmd",
            "run",
            "backtest:okx-technical",
            "--",
            "--date",
            d,
            "--window",
            args.window,
        ]
        # Stream output to both stdout and the log
        with log_path.open("a", encoding="utf-8") as logf:
            r = subprocess.run(
                cmd, cwd=str(ROOT), stdout=logf, stderr=subprocess.STDOUT, shell=False
            )
        dur = time.time() - started
        marker = f"=== [{i}/{len(dates)}] {d} END exit={r.returncode} dur={dur:.1f}s ==="
        print(marker, flush=True)
        with log_path.open("a", encoding="utf-8") as logf:
            logf.write(marker + "\n")
        if r.returncode != 0:
            print(f"[chain] FAIL on {d}; continuing with next")
    print(f"[chain] all done in {(time.time()-overall_start):.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
