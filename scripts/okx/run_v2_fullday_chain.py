"""Strict-sequential v2 full-day chain for OKX zone_score_v2 data collection.

Reads the 12 candidate dates from
    reports/OKX_SCORE_V2_CANDIDATE_DATES.json
runs `npm run backtest:okx-technical -- --date <D> --window full-day` for
each one, sequentially, and renames the produced
    reports/OKX_TECHNICAL_REPLAY_<D>.{md,json,_ZONES.csv}
to
    reports/OKX_V2_TECHNICAL_REPLAY_<D>_fullday.{md,json,_ZONES.csv}

If a single date fails, the chain records the failure and continues with
the next date (so a transient hiccup does not nuke ~17 hours of compute).

NO strategy/threshold/score change. NO zone filtering. NO use of
zone_score_v1. This is a labeling/data-collection step only.
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
LOG = ROOT / "data" / "okx-historical" / "_v2_fullday_chain.log"


def log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def list_heavy_nodes() -> list[str]:
    try:
        out = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "Get-CimInstance Win32_Process | "
                "Where-Object { $_.Name -eq 'node.exe' -and $_.WorkingSetSize -gt 100MB } | "
                "Select-Object ProcessId,WorkingSetSize | ForEach-Object { \"$($_.ProcessId) $($_.WorkingSetSize)\" }",
            ],
            capture_output=True,
            text=True,
            timeout=20,
        )
        return [l for l in out.stdout.splitlines() if l.strip()]
    except Exception:
        return []


def run_one(date: str) -> dict:
    started = time.time()
    log(f"=== START v2 full-day {date} ===")
    pre_heavy = list_heavy_nodes()
    if pre_heavy:
        log(f"  WARN: heavy node processes already running: {pre_heavy}")

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
        log(f"  FAIL on {date}; continuing with next date")
        return {"date": date, "exit_code": result.returncode, "dur_s": round(dur, 1), "renamed": False, "error": "non-zero exit"}

    renamed: list[str] = []
    missing: list[str] = []
    for suffix in (".md", ".json", "_ZONES.csv"):
        src = REPORTS / f"OKX_TECHNICAL_REPLAY_{date}{suffix}"
        dst = REPORTS / f"OKX_V2_TECHNICAL_REPLAY_{date}_fullday{suffix}"
        if src.exists():
            shutil.move(str(src), str(dst))
            renamed.append(dst.name)
        else:
            missing.append(src.name)
            log(f"  WARN: expected output not produced: {src.name}")
    log(f"  renamed -> V2: {renamed}")
    return {
        "date": date,
        "exit_code": 0,
        "dur_s": round(dur, 1),
        "renamed": bool(renamed),
        "files": renamed,
        "missing": missing,
    }


def main() -> int:
    sel = json.loads((REPORTS / "OKX_SCORE_V2_CANDIDATE_DATES.json").read_text(encoding="utf-8"))
    dates = [c["date"] for c in sel["chosen"]]
    log(f"V2 chain dates ({len(dates)}): {dates}")
    log(f"V2 chain log -> {LOG}")
    log(f"Expected total runtime ~17 hours (~7676 sec/GB on the chain hardware).")
    chain_started = time.time()
    results: list[dict] = []
    for i, d in enumerate(dates, 1):
        log(f"--- date {i}/{len(dates)}: {d}")
        r = run_one(d)
        results.append(r)
        # Persist partial results after each date so a kill doesn't lose progress
        (REPORTS / "OKX_V2_FULLDAY_CHAIN_RESULTS.json").write_text(
            json.dumps({
                "chain_started_unix": chain_started,
                "elapsed_seconds": round(time.time() - chain_started, 1),
                "completed_count": i,
                "total_count": len(dates),
                "results": results,
            }, indent=2),
            encoding="utf-8",
        )
    total = time.time() - chain_started
    log(f"V2 chain DONE in {total:.1f}s ({total/3600:.2f} h)")
    log(f"failures: {[r['date'] for r in results if r['exit_code'] != 0]}")
    return 0 if all(r["exit_code"] == 0 for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
