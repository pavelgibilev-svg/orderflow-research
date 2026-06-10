"""Strict-sequential full-day OKX replay chain.

For each requested date:
  1. Sanity-check that no node.exe is currently running (best-effort).
  2. Spawn `npm run backtest:okx-technical -- --date <D> --window full-day`
     via subprocess.run (BLOCKS until exit).
  3. After exit, RENAME the produced
        reports/OKX_TECHNICAL_REPLAY_<D>.{md,json,_ZONES.csv}
     to
        reports/OKX_TECHNICAL_REPLAY_<D>_fullday.{md,json,_ZONES.csv}
     (preserves the artefact under a window-specific name).
  4. Restore the immutable 3-hour snapshot from
        reports/okx_3h_snapshots/OKX_TECHNICAL_REPLAY_<D>_3h.*
     back to
        reports/OKX_TECHNICAL_REPLAY_<D>.*
     so the default per-date head stays the 3 h result.
  5. Verify both fullday and restored 3h files exist; log result.
  6. Move on to next date.

Usage:
    python scripts/okx/run_fullday_chain.py \
        --dates 2024-07-01,2024-10-01,2025-10-01,2025-12-01,2026-04-01

Strict serial: only ONE backtest at a time. No parallelism.
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
REPORTS = ROOT / "reports"
SNAP_DIR = REPORTS / "okx_3h_snapshots"
LOG = ROOT / "data" / "okx-historical" / "_fullday_chain.log"


def log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def list_heavy_nodes() -> list[str]:
    """List active node.exe processes with >100MB working set. Used as a
    pre-flight sanity check."""
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
    log(f"=== START full-day {date} ===")
    pre_heavy = list_heavy_nodes()
    if pre_heavy:
        log(f"  WARN: heavy node processes already running: {pre_heavy}")

    cmd = [
        "npm.cmd",
        "run",
        "backtest:okx-technical",
        "--",
        "--date",
        date,
        "--window",
        "full-day",
    ]
    log(f"  cmd: {' '.join(cmd)}")
    proc_log = LOG.with_suffix(f".{date}.log")
    with proc_log.open("w", encoding="utf-8") as logf:
        result = subprocess.run(
            cmd, cwd=str(ROOT), stdout=logf, stderr=subprocess.STDOUT, shell=False
        )
    dur_replay = time.time() - started
    log(f"  npm exit={result.returncode}  replay_dur={dur_replay:.1f}s  per-date-log={proc_log}")

    if result.returncode != 0:
        return {
            "date": date,
            "exit_code": result.returncode,
            "replay_seconds": round(dur_replay, 1),
            "renamed": False,
            "restored_3h": False,
            "error": "non-zero exit",
        }

    # Rename produced files to *_fullday.*
    renamed = []
    for suffix in (".md", ".json", "_ZONES.csv"):
        src = REPORTS / f"OKX_TECHNICAL_REPLAY_{date}{suffix}"
        dst = REPORTS / f"OKX_TECHNICAL_REPLAY_{date}_fullday{suffix}"
        if src.exists():
            shutil.move(str(src), str(dst))
            renamed.append(dst.name)
        else:
            log(f"  WARN: expected {src.name} not produced by backtest")

    # Restore 3h snapshot
    restored = []
    for suffix in (".md", ".json", "_ZONES.csv"):
        snap = SNAP_DIR / f"OKX_TECHNICAL_REPLAY_{date}_3h{suffix}"
        dst = REPORTS / f"OKX_TECHNICAL_REPLAY_{date}{suffix}"
        if snap.exists():
            shutil.copy2(str(snap), str(dst))
            restored.append(dst.name)
        else:
            log(f"  WARN: 3h snapshot missing for {date}{suffix}")

    log(f"  renamed -> fullday: {renamed}")
    log(f"  restored 3h: {restored}")
    return {
        "date": date,
        "exit_code": 0,
        "replay_seconds": round(dur_replay, 1),
        "renamed": True,
        "restored_3h": bool(restored),
        "fullday_files": renamed,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dates", required=True, help="CSV YYYY-MM-DD list")
    args = p.parse_args()
    dates = [d.strip() for d in args.dates.split(",") if d.strip()]

    log(f"chain dates={dates}")
    log(f"chain log -> {LOG}")
    chain_started = time.time()
    results = []
    for i, d in enumerate(dates, 1):
        log(f"--- date {i}/{len(dates)}: {d}")
        r = run_one(d)
        results.append(r)

    total = time.time() - chain_started
    log(f"chain DONE. total wall-clock {total:.1f}s")
    log(f"results: {json.dumps(results, indent=2)}")
    summary_path = REPORTS / "OKX_FULL_DAY_CHAIN_RESULTS.json"
    summary_path.write_text(
        json.dumps({"chain_total_seconds": round(total, 1), "results": results}, indent=2),
        encoding="utf-8",
    )
    log(f"wrote {summary_path}")
    return 0 if all(r.get("exit_code", 1) == 0 for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
