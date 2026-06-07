"""B — frozen engine on OKX early-May (05-03..10). Output reports/okx-may-early/BTC-USDT-SWAP_<date>."""
from __future__ import annotations
import json, shutil, subprocess, sys, time
from pathlib import Path
ROOT = Path("C:/Users/gibilev/orderflow-research")
DATA = ROOT / "data/okx-historical/BTC-USDT-SWAP"
OUT = ROOT / "reports/okx-may-early"; OUT.mkdir(parents=True, exist_ok=True)
DATES = [f"2026-05-{d:02d}" for d in range(3, 21)]
def run_day(d):
    l2 = DATA/d/"incremental_book_L2.csv.gz"; tr = DATA/d/"trades.csv.gz"
    if not (l2.exists() and l2.stat().st_size > 5e6 and tr.exists()): return {"date": d, "status": "SKIP_NO_DATA"}
    dst = OUT/f"BTC-USDT-SWAP_{d}"
    if (dst/"zones.json").exists(): return {"date": d, "status": "EXISTS"}
    t0=time.time()
    cmd=["npm.cmd","run","backtest:day","--","--input",f"data/okx-historical/BTC-USDT-SWAP/{d}",
         "--exchange","okex-swap","--symbol","BTC-USDT-SWAP","--date",d,"--target-pct","2","--horizons","4h,8h,24h"]
    with (OUT/f"_engine_{d}.log").open("w",encoding="utf-8") as lf:
        r=subprocess.run(cmd,cwd=str(ROOT),stdout=lf,stderr=subprocess.STDOUT,shell=False)
    src=ROOT/"reports"/f"BTC-USDT-SWAP_{d}"
    if src.exists():
        if dst.exists(): shutil.rmtree(dst)
        shutil.move(str(src),str(dst))
    return {"date": d,"status":"OK" if r.returncode==0 else "FAIL","dur_s":round(time.time()-t0,1)}
def main():
    res=[]
    for i,d in enumerate(DATES,1):
        rec=run_day(d); res.append(rec); print(f"--- {i}/{len(DATES)} {rec}",file=sys.stderr)
        (OUT/"OKX_EARLY_ENGINE_CHAIN_RESULTS.json").write_text(json.dumps({"results":res},indent=2),encoding="utf-8")
    print(f"OKX EARLY ENGINE DONE: {sum(1 for r in res if r['status'] in ('OK','EXISTS'))}/{len(DATES)}",file=sys.stderr)
    return 0
if __name__=="__main__": sys.exit(main())
