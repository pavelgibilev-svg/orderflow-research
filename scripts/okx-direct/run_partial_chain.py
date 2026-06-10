"""Strictly-sequential chain for OKX direct partial-March 2026:
  1. convert <date> via convert_okx_direct_to_tardis.py
  2. invoke `npm run backtest:okx-technical -- --date <date> --window full-day`
  3. rename the produced reports/OKX_TECHNICAL_REPLAY_<date>.{md,json,_ZONES.csv}
     to reports/okx-direct/OKX_DIRECT_TECHNICAL_REPLAY_<date>.{md,json,_ZONES.csv}
  4. persist a per-day result row into the chain log JSON.

Per user spec: do not parallelise. If a single date fails, record the failure and continue.

No strategy / threshold change. The engine is invoked exactly as-is.
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
REPORTS_OKX_DIRECT = ROOT / "reports/okx-direct"
REPORTS_OKX_DIRECT.mkdir(parents=True, exist_ok=True)
LOG = ROOT / "data/okx-historical/_okx_direct_partial_chain.log"
PY = "python"


def log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def convert(date_iso: str) -> dict:
    started = time.time()
    log(f"  [convert] {date_iso} ...")
    r = subprocess.run(
        [PY, "-u", "scripts/okx-direct/convert_okx_direct_to_tardis.py", "--date", date_iso],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    dur = time.time() - started
    if r.returncode != 0:
        log(f"  [convert] FAIL {date_iso} exit={r.returncode}: {r.stderr[-400:]}")
    else:
        log(f"  [convert] OK {date_iso} in {dur:.1f}s")
    return {"exit_code": r.returncode, "duration_s": round(dur, 1)}


def backtest(date_iso: str) -> dict:
    started = time.time()
    log(f"  [backtest] {date_iso} ...")
    per_log = LOG.with_suffix(f".{date_iso}.log")
    with per_log.open("w", encoding="utf-8") as logf:
        r = subprocess.run(
            ["npm.cmd", "run", "backtest:okx-technical", "--",
             "--date", date_iso, "--window", "full-day"],
            cwd=str(ROOT),
            stdout=logf,
            stderr=subprocess.STDOUT,
            shell=False,
        )
    dur = time.time() - started
    log(f"  [backtest] exit={r.returncode} dur={dur:.1f}s per-day-log={per_log}")
    return {"exit_code": r.returncode, "duration_s": round(dur, 1), "per_day_log": str(per_log)}


def rename_outputs(date_iso: str) -> dict:
    """Rename reports/OKX_TECHNICAL_REPLAY_<date>.* -> reports/okx-direct/OKX_DIRECT_TECHNICAL_REPLAY_<date>.*"""
    REPORTS = ROOT / "reports"
    moved: list[str] = []
    missing: list[str] = []
    for suffix in (".md", ".json", "_ZONES.csv"):
        src = REPORTS / f"OKX_TECHNICAL_REPLAY_{date_iso}{suffix}"
        dst = REPORTS_OKX_DIRECT / f"OKX_DIRECT_TECHNICAL_REPLAY_{date_iso}{suffix}"
        if src.exists():
            shutil.move(str(src), str(dst))
            moved.append(dst.name)
        else:
            missing.append(src.name)
    return {"moved": moved, "missing": missing}


def run_one(date_iso: str) -> dict:
    started = time.time()
    log(f"=== {date_iso} ===")
    rec = {"date": date_iso, "started_unix": started}
    rec["convert"] = convert(date_iso)
    if rec["convert"]["exit_code"] != 0:
        rec["status"] = "convert_failed"
        rec["duration_s"] = round(time.time() - started, 1)
        return rec
    rec["backtest"] = backtest(date_iso)
    rec["rename"] = rename_outputs(date_iso)
    rec["status"] = "ok" if rec["backtest"]["exit_code"] == 0 and rec["rename"]["moved"] else "backtest_failed_or_no_output"
    rec["duration_s"] = round(time.time() - started, 1)
    return rec


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dates", required=True, help="comma-separated YYYY-MM-DD list")
    args = ap.parse_args()
    dates = [d.strip() for d in args.dates.split(",") if d.strip()]
    log(f"chain dates ({len(dates)}): {dates}")
    chain_started = time.time()
    results: list[dict] = []
    out_json = REPORTS_OKX_DIRECT / "OKX_DIRECT_MARCH_PARTIAL_CHAIN_RESULTS.json"
    for i, d in enumerate(dates, 1):
        log(f"--- {i}/{len(dates)}: {d}")
        results.append(run_one(d))
        out_json.write_text(json.dumps({
            "chain_started_unix": chain_started,
            "elapsed_s": round(time.time() - chain_started, 1),
            "completed_count": i,
            "total_count": len(dates),
            "results": results,
        }, indent=2), encoding="utf-8")
    total = time.time() - chain_started
    log(f"chain DONE in {total:.1f}s ({total/3600:.2f} h)")
    log(f"failures: {[r['date'] for r in results if r.get('status') != 'ok']}")
    return 0 if all(r.get("status") == "ok" for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
