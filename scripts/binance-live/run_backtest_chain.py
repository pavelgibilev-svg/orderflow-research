"""Sequential Binance-live backtest chain over converted Tardis-compat days.

Per spec: NO engine / threshold change. Invokes the existing
    npm run backtest:day -- --input data/binance-historical/BTCUSDT/<date> \
        --exchange binance-futures --symbol BTCUSDT --date <date> \
        --target-pct 2 --horizons 4h,8h,24h
Then renames the produced reports/BTCUSDT_<date>/report.* and the json
output into reports/binance-live/BINANCE_LIVE_TECHNICAL_REPLAY_<date>.{md,json,_ZONES.csv}.
"""
from __future__ import annotations
import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path("C:/Users/gibilev/orderflow-research")
REPORTS_LIVE = ROOT / "reports/binance-live"
REPORTS_LIVE.mkdir(parents=True, exist_ok=True)
LOG = ROOT / "data/binance-historical/_binance_live_chain.log"


def log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def run_backtest(date_iso: str) -> dict:
    started = time.time()
    log(f"=== backtest {date_iso} ===")
    per_log = LOG.with_suffix(f".{date_iso}.log")
    cmd = [
        "npm.cmd", "run", "backtest:day", "--",
        "--input", f"data/binance-historical/BTCUSDT/{date_iso}",
        "--exchange", "binance-futures",
        "--symbol", "BTCUSDT",
        "--date", date_iso,
        "--target-pct", "2",
        "--horizons", "4h,8h,24h",
    ]
    log(f"  cmd: {' '.join(cmd)}")
    with per_log.open("w", encoding="utf-8") as logf:
        r = subprocess.run(cmd, cwd=str(ROOT), stdout=logf, stderr=subprocess.STDOUT, shell=False)
    dur = time.time() - started
    log(f"  exit={r.returncode} dur={dur:.1f}s per-log={per_log}")
    # Move outputs (backtestDay writes to reports/<SYMBOL>_<DATE>/)
    src_dir = ROOT / "reports" / f"BTCUSDT_{date_iso}"
    moved = []
    if src_dir.exists():
        # rename whole folder to reports/binance-live/BTCUSDT_<date>/
        dst_dir = REPORTS_LIVE / f"BTCUSDT_{date_iso}"
        if dst_dir.exists():
            shutil.rmtree(dst_dir)
        shutil.move(str(src_dir), str(dst_dir))
        moved.append(str(dst_dir))
        # Also copy out the key files with our naming convention
        for src_name, dst_suffix in [
            ("zones.json", ".json"),
            ("zones.csv", "_ZONES.csv"),
            ("report.md", ".md"),
        ]:
            src_file = dst_dir / src_name
            if src_file.exists():
                dst_file = REPORTS_LIVE / f"BINANCE_LIVE_TECHNICAL_REPLAY_{date_iso}{dst_suffix}"
                shutil.copy2(src_file, dst_file)
                moved.append(str(dst_file))
    return {
        "date": date_iso,
        "exit_code": r.returncode,
        "duration_s": round(dur, 1),
        "moved": moved,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dates", required=True, help="comma-separated YYYY-MM-DD list")
    args = ap.parse_args()
    dates = [d.strip() for d in args.dates.split(",") if d.strip()]
    log(f"chain dates ({len(dates)}): {dates}")
    chain_started = time.time()
    out_json = REPORTS_LIVE / "BINANCE_LIVE_CHAIN_RESULTS.json"
    results = []
    for i, d in enumerate(dates, 1):
        log(f"--- {i}/{len(dates)}: {d}")
        rec = run_backtest(d)
        results.append(rec)
        out_json.write_text(json.dumps({
            "chain_started_unix": chain_started,
            "elapsed_s": round(time.time() - chain_started, 1),
            "completed_count": i,
            "total_count": len(dates),
            "results": results,
        }, indent=2), encoding="utf-8")
    log(f"chain DONE  elapsed={time.time()-chain_started:.1f}s  failures="
        f"{[r['date'] for r in results if r['exit_code'] != 0]}")
    return 0 if all(r["exit_code"] == 0 for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
