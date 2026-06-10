"""Sequential Binance-Tardis 2025 backtest chain (12 first-of-month dates).

Uses existing `npm run backtest:day --exchange binance-futures` unchanged.
Outputs renamed to reports/binance-tardis/BINANCE_TARDIS_TECHNICAL_REPLAY_<date>.{md,json,_ZONES.csv}.
"""
from __future__ import annotations
import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "package.json").exists() and (p / "scripts").exists())
REPORTS_TARDIS = ROOT / "reports/binance-tardis"
REPORTS_TARDIS.mkdir(parents=True, exist_ok=True)
LOG = ROOT / "data/tardis/_binance_tardis_2025_chain.log"


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
        "--input", f"data/tardis/binance-futures/BTCUSDT/{date_iso}",
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
    src_dir = ROOT / "reports" / f"BTCUSDT_{date_iso}"
    moved = []
    if src_dir.exists():
        dst_dir = REPORTS_TARDIS / f"BTCUSDT_{date_iso}"
        if dst_dir.exists():
            shutil.rmtree(dst_dir)
        shutil.move(str(src_dir), str(dst_dir))
        moved.append(str(dst_dir))
        for src_name, dst_suffix in [("zones.json", ".json"), ("zones.csv", "_ZONES.csv"),
                                      ("report.md", ".md")]:
            sf = dst_dir / src_name
            if sf.exists():
                df = REPORTS_TARDIS / f"BINANCE_TARDIS_TECHNICAL_REPLAY_{date_iso}{dst_suffix}"
                shutil.copy2(sf, df)
                moved.append(str(df))
    return {"date": date_iso, "exit_code": r.returncode,
            "duration_s": round(dur, 1), "moved": moved}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dates", required=True)
    args = ap.parse_args()
    dates = [d.strip() for d in args.dates.split(",") if d.strip()]
    log(f"chain dates ({len(dates)}): {dates}")
    chain_started = time.time()
    out_json = REPORTS_TARDIS / "BINANCE_TARDIS_2025_CHAIN_RESULTS.json"
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
    log(f"chain DONE elapsed={time.time()-chain_started:.1f}s  failures="
        f"{[r['date'] for r in results if r['exit_code'] != 0]}")
    return 0 if all(r["exit_code"] == 0 for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
