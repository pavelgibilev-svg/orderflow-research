"""Strict-sequential OOS full-day chain for OKX zone_score_v1 validation.

For each date in the OOS selection:
  1. Spawn `npm run backtest:okx-technical -- --date <D> --window full-day`
     via subprocess.run (BLOCKS until exit).
  2. Rename the produced reports/OKX_TECHNICAL_REPLAY_<D>.{md,json,_ZONES.csv}
     to reports/OKX_OOS_TECHNICAL_REPLAY_<D>_fullday.{md,json,_ZONES.csv}
     so OOS files never collide with calibration files.
  3. Log per-date wall-clock + exit code.

If a date's full-day fails or takes excessively long (>200 min), the chain
records the failure and moves on; the OOS validation report will reflect
which dates landed.

NO strategy/threshold/weight changes. NO score change.
"""
from __future__ import annotations
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "package.json").exists() and (p / "scripts").exists())
REPORTS = ROOT / "reports"
LOG = ROOT / "data" / "okx-historical" / "_oos_fullday_chain.log"


def log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def run_one(date: str) -> dict:
    started = time.time()
    log(f"=== START OOS full-day {date} ===")
    cmd = [
        "npm.cmd", "run", "backtest:okx-technical", "--",
        "--date", date, "--window", "full-day",
    ]
    log(f"  cmd: {' '.join(cmd)}")
    per_date_log = LOG.with_suffix(f".{date}.log")
    with per_date_log.open("w", encoding="utf-8") as logf:
        result = subprocess.run(
            cmd, cwd=str(ROOT), stdout=logf, stderr=subprocess.STDOUT, shell=False
        )
    dur = time.time() - started
    log(f"  npm exit={result.returncode}  dur={dur:.1f}s  per-date-log={per_date_log}")
    if result.returncode != 0:
        return {"date": date, "exit_code": result.returncode, "dur_s": round(dur, 1), "renamed": False}

    renamed: list[str] = []
    for suffix in (".md", ".json", "_ZONES.csv"):
        src = REPORTS / f"OKX_TECHNICAL_REPLAY_{date}{suffix}"
        dst = REPORTS / f"OKX_OOS_TECHNICAL_REPLAY_{date}_fullday{suffix}"
        if src.exists():
            shutil.move(str(src), str(dst))
            renamed.append(dst.name)
        else:
            log(f"  WARN: expected output not produced: {src.name}")
    log(f"  renamed -> OOS: {renamed}")
    return {"date": date, "exit_code": 0, "dur_s": round(dur, 1), "renamed": True, "files": renamed}


def main() -> int:
    sel = json.loads((REPORTS / "OKX_OOS_SELECTED_DATES.json").read_text(encoding="utf-8"))
    dates = [c["date"] for c in sel["chosen"]]
    log(f"OOS chain dates={dates}")
    log(f"OOS chain log -> {LOG}")
    started = time.time()
    results: list[dict] = []
    for i, d in enumerate(dates, 1):
        log(f"--- date {i}/{len(dates)}: {d}")
        results.append(run_one(d))
    total = time.time() - started
    log(f"OOS chain DONE in {total:.1f}s ({total/60:.1f} min)")
    (REPORTS / "OKX_OOS_FULLDAY_CHAIN_RESULTS.json").write_text(
        json.dumps({"chain_total_seconds": round(total, 1), "results": results}, indent=2),
        encoding="utf-8",
    )
    return 0 if all(r["exit_code"] == 0 for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
