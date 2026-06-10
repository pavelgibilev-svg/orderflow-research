"""Build OKX March feature table comparable to the Binance 10d diag cache — WITHOUT L2 re-streaming.

Sources (all already on disk):
  - reports/BTC-USDT-SWAP_2026-03-DD/zones.json  (engine zones + scores + reasons)
  - reports/strategy-calibration/MARCH_DYNAMIC_L2_FEATURE_DATASET.csv (1043 zones: L2 features, join by zone_id)
  - data/okx-historical/BTC-USDT-SWAP/2026-03-DD/trades.csv.gz (cheap buckets: canonical sim, regime, dist_swh, taker imbalance)

Output cache: reports/strategy-calibration/OKX_MARCH_DIAG_FEATURE_CACHE.json
Causal only (<= confirmedTs). No engine/detector change.
"""
from __future__ import annotations
import csv, gzip, json, sys, time, bisect, datetime as dt
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "scripts" / "binance-live"))
import binance_oos_features_rs as B
from canonical_ledger import build_buckets_from_trades_csv
# reuse venue-agnostic regime/structure from the binance diag module
sys.path.insert(0, str(HERE.parents[0] / "binance-live"))
import importlib.util
_spec = importlib.util.spec_from_file_location("b10d", str(HERE.parents[0] / "binance-live" / "binance_10d_diag.py"))
b10d = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(b10d)

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "package.json").exists() and (p / "scripts").exists())
OKX_TRADES = ROOT / "data/okx-historical/BTC-USDT-SWAP"
FEAT_CSV = ROOT / "reports/strategy-calibration/MARCH_DYNAMIC_L2_FEATURE_DATASET.csv"
CACHE = ROOT / "reports/strategy-calibration/OKX_MARCH_DIAG_FEATURE_CACHE.json"
ZONE_BAND_PCT = 0.002

# L2 feature columns to pull from the precomputed dataset (no streaming)
L2_COLS = ["dl2_supp_minus_opp_net_flow_15m","dl2_supp_minus_opp_net_flow_5m",
           "dl2_microprice_aligned_delta_5m_bps","dl2_microprice_aligned_delta_15m_bps",
           "dl2_top1_supportive_persistence_ge_50_5m_sec","dl2_inband_opp_cancel_15m",
           "dl2_inband_supp_add_5m","dl2_spread_now_bps","dl2_spread_mean_5m_bps","dl2_spread_max_5m_bps",
           "dl2_supportive_add_vol_5m","dl2_supportive_cancel_vol_5m"]


def f(x):
    try: return float(x)
    except: return None


def load_feat_csv():
    out={}
    for r in csv.DictReader(open(FEAT_CSV,encoding="utf-8")):
        zid=r["zone_id"]; d={}
        for c in L2_COLS:
            if c in r: d[c]=f(r[c])
        # derive refill ratio proxy
        sa=f(r.get("dl2_supportive_add_vol_5m")); sc=f(r.get("dl2_supportive_cancel_vol_5m"))
        d["dl2_supp_refill_ratio_5m"]=round(sa/(sc+1.0),4) if (sa is not None and sc is not None) else None
        out[zid]=d
    return out


def aggression_okx(date, anchors):
    """taker imbalance + inband sell share from OKX trades (ratios => unit-agnostic). cheap."""
    p=OKX_TRADES/date/"trades.csv.gz"
    if not p.exists() or not anchors: return {}
    anchors=sorted(anchors,key=lambda x:x[0])
    bands={zid:(zlo*(1-ZONE_BAND_PCT),zhi*(1+ZONE_BAND_PCT)) for _,zid,_,zlo,zhi in anchors}
    per_sec=defaultdict(lambda:[0.0,0.0]); inband=defaultdict(lambda:[0.0,0.0]); nxt=0
    with gzip.open(p,"rt",encoding="utf-8") as fh:
        fh.readline()
        for line in fh:
            parts=line.rstrip().split(",")
            if len(parts)<8: continue
            try:
                ts=int(parts[2]); side=parts[5]; price=float(parts[6]); amt=float(parts[7])
            except: continue
            sec=ts//1_000_000; ps=per_sec[sec]
            if side=="buy": ps[0]+=amt
            else: ps[1]+=amt
            for idx in range(nxt,len(anchors)):
                asec,zid,_,zlo,zhi=anchors[idx]
                if asec-sec>1800: break
                blo,bhi=bands[zid]
                if blo<=price<=bhi:
                    ib=inband[zid]
                    if side=="buy": ib[0]+=amt
                    else: ib[1]+=amt
            while nxt<len(anchors) and anchors[nxt][0]<=sec: nxt+=1
    secs=sorted(per_sec); cb=[0.0]; cs=[0.0]
    for s in secs: cb.append(cb[-1]+per_sec[s][0]); cs.append(cs[-1]+per_sec[s][1])
    def wsum(a,w):
        lo=bisect.bisect_left(secs,a-w); hi=bisect.bisect_right(secs,a)
        return cb[hi]-cb[lo], cs[hi]-cs[lo]
    out={}
    for asec,zid,direction,zlo,zhi in anchors:
        d={}
        for w,lab in ((300,"5m"),(900,"15m"),(1800,"30m")):
            bv,sv=wsum(asec,w); tot=bv+sv
            d[f"taker_imbalance_{lab}"]=round((bv-sv)/tot,4) if tot>0 else 0.0
            supp=bv if direction=="LONG" else sv; opp=sv if direction=="LONG" else bv
            d[f"supportive_taker_imb_{lab}"]=round((supp-opp)/tot,4) if tot>0 else 0.0
        ib=inband.get(zid,[0.0,0.0]); tot=ib[0]+ib[1]
        d["inband_sell_share_30m"]=round(ib[1]/tot,4) if tot>0 else None
        out[zid]=d
    return out


def main():
    if CACHE.exists():
        print("cache exists; delete to rebuild", file=sys.stderr); return 0
    feat=load_feat_csv()
    print(f"feat csv zones: {len(feat)}", file=sys.stderr)
    # collect OKX March zone reports
    dirs=sorted(ROOT.glob("reports/BTC-USDT-SWAP_2026-03-*"))
    zones=[]
    for dd in dirs:
        zp=dd/"zones.json"
        if not zp.exists(): continue
        date=dd.name.replace("BTC-USDT-SWAP_","")
        obj=json.loads(zp.read_text(encoding="utf-8"))
        arr=obj if isinstance(obj,list) else obj.get("zones",[])
        for z in arr:
            if z.get("confirmedTs") is None: continue
            if z["id"] not in feat: continue   # need L2 features
            z["_date"]=date
            sc=z.get("scores") or {}
            z["eng_absorption"]=sc.get("absorptionScore"); z["eng_void"]=sc.get("liquidityVoidScore")
            z["eng_ofi"]=sc.get("ofiScore"); z["eng_refill"]=sc.get("refillScore"); z["eng_trigger"]=sc.get("triggerScore")
            z.update(feat[z["id"]])
            zones.append(z)
    print(f"matched OKX confirmed zones: {len(zones)}", file=sys.stderr)
    dates=sorted({z["_date"] for z in zones})
    B.DATES=dates
    print(f"dates: {dates[0]}..{dates[-1]} ({len(dates)})", file=sys.stderr)
    # buckets
    bcache={}; t0=time.time()
    for d in dates:
        p=OKX_TRADES/d/"trades.csv.gz"
        if p.exists(): bcache[d]=build_buckets_from_trades_csv(p)
    print(f"buckets built {time.time()-t0:.0f}s", file=sys.stderr)
    gb=[]
    for d in dates: gb+=bcache.get(d,[])
    gb.sort(key=lambda b:b.sec); gsec=[b.sec for b in gb]
    # opp dir
    opp=B.opp_dir_counts(zones)
    # trades features + regime + struct + aggression
    by_date=defaultdict(list)
    for z in zones:
        by_date[z["_date"]].append((z["confirmedTs"]//1000, z["id"], z["direction"], z.get("zoneLow"), z.get("zoneHigh")))
    for z in zones:
        z.update(B.trades_features(z, bcache.get(z["_date"],[])))
        hr=(z["confirmedTs"]//1000 % 86400)//3600; z["is_asia_session"]=1 if hr<7 else 0
        z["opp_dir_zones_active_60m"]=opp.get(z["id"],0)
        z.update(b10d.regime_struct(z, gb, gsec))
    t0=time.time()
    for d in dates:
        agg=aggression_okx(d, by_date.get(d,[]))
        for z in zones:
            if z["_date"]==d: z.update(agg.get(z["id"],{}))
    print(f"aggression {time.time()-t0:.0f}s", file=sys.stderr)
    # explainable score + sim
    for z in zones:
        z["explainable_score"]=B.explainable_score(z)
    for z in zones:
        sim=B.sim_trade(z, bcache)
        if sim is None:
            z["sim_label"]="NO_TRADE"; z["sim_outcome"]=None; z["sim_pnl_after_cost"]=None
            z["sim_pnl_pre_cost"]=None; z["sim_mfe_pct"]=None; z["sim_mae_pct"]=None
            z["sim_exit_reason"]=None; z["sim_entry_price"]=None; z["sim_correct_direction"]=None
            continue
        z["sim_outcome"]=sim["outcome"]; z["sim_pnl_after_cost"]=sim["pnl_after_cost"]
        z["sim_pnl_pre_cost"]=sim["pnl_pre_cost"]; z["sim_mfe_pct"]=sim["mfe_pct"]; z["sim_mae_pct"]=sim["mae_pct"]
        z["sim_exit_reason"]=sim["exit_reason"]; z["sim_entry_price"]=sim["entry_price"]
        z["sim_correct_direction"]=1 if (sim["mfe_pct"] or 0)>=(sim["mae_pct"] or 0) else 0
        if sim["outcome"]=="WIN": z["sim_label"]="GOOD"
        elif sim["outcome"]=="LOSS": z["sim_label"]="NOISE"
        elif sim["outcome"]=="TIMEOUT" and (sim["pnl_pre_cost"] or 0)>0: z["sim_label"]="MID"
        else: z["sim_label"]="NOISE"
    # uniqueness vs prior
    zs=sorted(zones,key=lambda z:z["confirmedTs"]); psc=[]
    for z in zs:
        z["uniq_score_pctile_vs_prior"]=b10d.pctile(sorted(psc), z["explainable_score"]) if psc else None
        psc.append(z["explainable_score"])
    for z in zones:
        for k in ("reasons","targets","scores"): z.pop(k,None)
    CACHE.write_text(json.dumps(zones,default=str,indent=0),encoding="utf-8")
    traded=sum(1 for z in zones if z.get("sim_outcome"))
    good=sum(1 for z in zones if z.get("sim_label")=="GOOD")
    print(f"[done] {len(zones)} zones, traded {traded}, GOOD {good} -> {CACHE.name}", file=sys.stderr)
    return 0


if __name__=="__main__":
    sys.exit(main())
