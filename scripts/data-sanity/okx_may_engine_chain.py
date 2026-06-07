"""A2 — run frozen engine on OKX open May (no engine/detector change).

Invokes the existing CLI unchanged:
  npm run backtest:day -- --input data/okx-historical/BTC-USDT-SWAP/<date>
      --exchange okex-swap --symbol BTC-USDT-SWAP --date <date> --target-pct 2 --horizons 4h,8h,24h
Moves reports/BTC-USDT-SWAP_<date>/ -> reports/okx-may/BTC-USDT-SWAP_<date>/.
Gates each day on converted L2+trades presence.
"""
from __future__ import annotations
import json, shutil, subprocess, sys, time
from pathlib import Path

ROOT = Path("C:/Users/gibilev/orderflow-research")
DATA = ROOT / "data/okx-historical/BTC-USDT-SWAP"
OUT = ROOT / "reports/okx-may"; OUT.mkdir(parents=True, exist_ok=True)
DATES = [f"2026-05-{d:02d}" for d in range(21, 31)]


def run_day(d):
    l2 = DATA / d / "incremental_book_L2.csv.gz"; tr = DATA / d / "trades.csv.gz"
    if not (l2.exists() and l2.stat().st_size > 5e6 and tr.exists()):
        return {"date": d, "status": "SKIP_NO_DATA"}
    dst = OUT / f"BTC-USDT-SWAP_{d}"
    if (dst / "zones.json").exists():
        return {"date": d, "status": "EXISTS"}
    t0 = time.time()
    cmd = ["npm.cmd", "run", "backtest:day", "--",
           "--input", f"data/okx-historical/BTC-USDT-SWAP/{d}",
           "--exchange", "okex-swap", "--symbol", "BTC-USDT-SWAP", "--date", d,
           "--target-pct", "2", "--horizons", "4h,8h,24h"]
    per_log = OUT / f"_engine_{d}.log"
    with per_log.open("w", encoding="utf-8") as lf:
        r = subprocess.run(cmd, cwd=str(ROOT), stdout=lf, stderr=subprocess.STDOUT, shell=False)
    src = ROOT / "reports" / f"BTC-USDT-SWAP_{d}"
    if src.exists():
        if dst.exists(): shutil.rmtree(dst)
        shutil.move(str(src), str(dst))
    return {"date": d, "status": "OK" if r.returncode == 0 else "FAIL", "exit": r.returncode,
            "dur_s": round(time.time() - t0, 1)}


def main():
    res = []
    for i, d in enumerate(DATES, 1):
        print(f"--- {i}/10 {d}", file=sys.stderr)
        rec = run_day(d); res.append(rec)
        print(f"  {rec}", file=sys.stderr)
        (OUT / "OKX_MAY_ENGINE_CHAIN_RESULTS.json").write_text(
            json.dumps({"updated": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), "results": res}, indent=2), encoding="utf-8")
    ok = [r for r in res if r["status"] in ("OK", "EXISTS")]
    print(f"OKX ENGINE CHAIN DONE: {len(ok)}/10 ok", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
