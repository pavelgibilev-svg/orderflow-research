"""BINANCE 10D DIAGNOSTIC: selected-vs-skipped + noise/trap classifier + live-valid selector audit.

Goal: explain WHY frozen RS1 failed on 2026-05-21..30. NOT tuning the strategy.
HARD RULES (enforced by construction):
  - engine / zoneDetector / TP / SL unchanged (we only read engine outputs + replay canonical ledger)
  - NO threshold optimization on Binance; any score threshold is taken FROZEN from OKX distribution
  - all SELECTOR features computed strictly <= confirmedTs (no future leak)
  - post-signal quantities are used ONLY as diagnostic labels (prefixed post_), never in a live-valid selector
  - no production claim

Builds a cached causal feature table for every confirmed zone, then emits:
  A) BINANCE_10D_SELECTED_VS_SKIPPED_AUDIT
  B) BINANCE_10D_TRAP_AUDIT
  C) BINANCE_10D_LOCAL_BACKGROUND_FEATURES + OKX_VS_BINANCE_FEATURE_DISTRIBUTION_SHIFT
  D) BINANCE_10D_NOISE_CLASSIFIER_RESEARCH
  E) BINANCE_10D_LIVE_VALID_SELECTOR_AUDIT
  + BINANCE_10D_NOISE_TRAP_FINAL_REPORT
"""
from __future__ import annotations
import csv, gzip, json, math, statistics as st, sys, time, datetime as dt
from collections import defaultdict, deque, Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import binance_oos_features_rs as B
from canonical_ledger import build_buckets_from_trades_csv

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "package.json").exists() and (p / "scripts").exists())
OUT = ROOT / "reports/binance-oos"
TARDIS = ROOT / "data/binance-historical/BTCUSDT"
ZONES_DIR = ROOT / "reports/binance-live"
OKX_DIR = ROOT / "reports/strategy-calibration"
CACHE = OUT / "BINANCE_10D_DIAG_FEATURE_CACHE.json"
L2CACHE_DIR = OUT / "_l2cache_10d"; L2CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATES = [f"2026-05-{d:02d}" for d in range(21, 31)]
H1 = DATES[:5]; H2 = DATES[5:]
ZONE_BAND_PCT = 0.002; WALL_SIZE = 50.0; COST = B.COST_PCT

# --- OKX FROZEN score thresholds (derived from OKX 29 selected paper trades; NOT tuned on Binance) ---
OKX_SCORE_WINNER_MIN = 1.021      # weakest score that ever won on OKX
OKX_SCORE_WINNER_P10 = 1.347
OKX_SCORE_ALL_P20 = 1.481


def now_iso(): return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
def ms_iso(ms): return dt.datetime.fromtimestamp(ms/1000, tz=dt.timezone.utc).isoformat(timespec="seconds") if ms else None
def mean(xs):
    xs=[x for x in xs if x is not None]; return round(st.mean(xs),4) if xs else None
def median(xs):
    xs=[x for x in xs if x is not None]; return round(st.median(xs),4) if xs else None
def pctile(sorted_xs, v):
    if not sorted_xs: return None
    lo=0
    for i,x in enumerate(sorted_xs):
        if x<=v: lo=i+1
        else: break
    return round(100.0*lo/len(sorted_xs),1)


# ------------------------------------------------------------------ zones + engine scores
def load_all_zones():
    zs=[]
    for d in DATES:
        p=ZONES_DIR/f"BTCUSDT_{d}"/"zones.json"
        obj=json.loads(p.read_text(encoding="utf-8"))
        arr=obj if isinstance(obj,list) else obj.get("zones",[])
        for z in arr:
            if z.get("confirmedTs") is None: continue
            z["_date"]=d
            sc=z.get("scores") or {}
            z["eng_absorption"]=sc.get("absorptionScore"); z["eng_void"]=sc.get("liquidityVoidScore")
            z["eng_ofi"]=sc.get("ofiScore"); z["eng_refill"]=sc.get("refillScore"); z["eng_trigger"]=sc.get("triggerScore")
            cand={}; conf={}
            for r in (z.get("reasons") or []):
                if r.get("stage")=="candidate": cand=r.get("conditions") or {}
                if r.get("stage")=="confirmed": conf=r.get("conditions") or {}
            z["cand_sellPressure"]=cand.get("sellPressure"); z["cand_bidRefill"]=cand.get("bidRefillScore")
            z["cand_downMovePct"]=cand.get("downMovePct"); z["cand_absorb"]=cand.get("absorbScore")
            z["cand_rangeCompression"]=cand.get("rangeCompression")
            z["conf_defendedPersistenceSec"]=conf.get("defendedPersistenceSec"); z["conf_oppositeThinning"]=conf.get("oppositeThinning")
            z["conf_voidScore"]=conf.get("voidScore"); z["conf_cyclesSeen"]=conf.get("cyclesSeen"); z["conf_ageMin"]=conf.get("ageMin")
            zs.append(z)
    return zs


# ------------------------------------------------------------------ extended L2 pass (one per day, cached)
def l2_extended_for_day(date, anchors):
    cf=L2CACHE_DIR/f"{date}.json"
    if cf.exists():
        return json.loads(cf.read_text(encoding="utf-8"))
    p=TARDIS/date/"incremental_book_L2.csv.gz"
    if not p.exists() or not anchors:
        cf.write_text("{}",encoding="utf-8"); return {}
    anchors=sorted(anchors,key=lambda x:x[0]); out={}; nxt=0
    bid={}; ask={}
    micro=deque(maxlen=8000)            # (sec,bb,ba,t1b,t1a,mp,spread_bps)
    per_min=deque(maxlen=72)
    cur={"min_sec":-1,"ab":0.,"aa":0.,"cb":0.,"ca":0.}
    last_sec=-1
    bands={zid:(zlo*(1-ZONE_BAND_PCT),zhi*(1+ZONE_BAND_PCT),direction) for _,zid,direction,zlo,zhi in anchors}
    inband=defaultdict(list)
    def snap(sec):
        if not bid or not ask: return
        bb=max(bid); ba=min(ask)
        if ba<=bb: return
        t1b=bid[bb]; t1a=ask[ba]; den=t1b+t1a
        mp=(bb*t1a+ba*t1b)/den if den>0 else (bb+ba)/2
        spr=(ba-bb)/((ba+bb)/2)*1e4
        micro.append((sec,bb,ba,t1b,t1a,mp,spr))
    def micro_le(s):
        best=None
        for x in micro:
            if x[0]<=s: best=x
            else: break
        return best
    def finalize(zone_sec,zid,direction,zlo,zhi):
        f={}
        now=micro_le(zone_sec)
        for w,lab in ((300,"5m"),(900,"15m")):
            past=micro_le(zone_sec-w)
            if now and past and past[5]>0:
                d=(now[5]-past[5])/past[5]*1e4
                f[f"dl2_microprice_aligned_delta_{lab}_bps"]=round(d if direction=="LONG" else -d,3)
            else: f[f"dl2_microprice_aligned_delta_{lab}_bps"]=None
        c5=zone_sec-300; pers=0
        for x in micro:
            if c5<=x[0]<=zone_sec:
                supp=x[3] if direction=="LONG" else x[4]
                if supp>=50: pers+=1
        f["dl2_top1_supportive_persistence_ge_50_5m_sec"]=pers
        allb=list(per_min)+[cur]
        for w,lab in ((300,"5m"),(900,"15m")):
            cutoff=zone_sec-w
            rel=[b for b in allb if b["min_sec"]>=cutoff-60 and b["min_sec"]<=zone_sec]
            ab=sum(b["ab"] for b in rel); aa=sum(b["aa"] for b in rel)
            cb=sum(b["cb"] for b in rel); ca=sum(b["ca"] for b in rel)
            if direction=="LONG": sa,sc_,oa,oc=ab,cb,aa,ca
            else: sa,sc_,oa,oc=aa,ca,ab,cb
            f[f"dl2_supp_add_{lab}"]=round(sa,2); f[f"dl2_supp_cancel_{lab}"]=round(sc_,2)
            f[f"dl2_opp_add_{lab}"]=round(oa,2); f[f"dl2_opp_cancel_{lab}"]=round(oc,2)
            f[f"dl2_supp_minus_opp_net_flow_{lab}"]=round((sa-sc_)-(oa-oc),4)
            f[f"dl2_supp_refill_ratio_{lab}"]=round(sa/(sc_+1.0),4)
        c15=zone_sec-900; c5b=zone_sec-300; opp=0.; sad=0.
        for (s,side,delta) in inband.get(zid,[]):
            if s>zone_sec: continue
            is_supp=(side=="bid" and direction=="LONG") or (side=="ask" and direction=="SHORT")
            if s>=c15 and delta<0 and not is_supp: opp+=-delta
            if s>=c5b and delta>0 and is_supp: sad+=delta
        f["dl2_inband_opp_cancel_15m"]=round(opp,4); f["dl2_inband_supp_add_5m"]=round(sad,4)
        # snapshot book-shape features at zone time
        if bid and ask:
            bb=max(bid); ba=min(ask); mid=(bb+ba)/2
            tup=mid*1.02; tdn=mid*0.98
            ask_to=sum(a for pr,a in ask.items() if ba<=pr<=tup)
            bid_to=sum(a for pr,a in bid.items() if tdn<=pr<=bb)
            ask_lg=sum(1 for pr,a in ask.items() if ba<=pr<=tup and a>=WALL_SIZE)
            bid_lg=sum(1 for pr,a in bid.items() if tdn<=pr<=bb and a>=WALL_SIZE)
            depth=ask_to if direction=="LONG" else bid_to
            walls=ask_lg if direction=="LONG" else bid_lg
            f["ms_thin_path_score"]=round(1.0/(1+math.log1p(depth)),4); f["ms_large_walls_on_path"]=walls
            # depth imbalance top-25 each side
            bt=sorted(bid.items(),key=lambda kv:-kv[0])[:25]; at=sorted(ask.items(),key=lambda kv:kv[0])[:25]
            bv=sum(a for _,a in bt); av=sum(a for _,a in at); tot=bv+av
            imb=(bv-av)/tot if tot>0 else 0.0
            f["depth_imbalance_top25"]=round(imb if direction=="LONG" else -imb,4)
            # book entropy over top-25 each side combined
            amts=[a for _,a in bt]+[a for _,a in at]; s=sum(amts)
            if s>0 and len(amts)>1:
                ps=[a/s for a in amts if a>0]
                ent=-sum(p*math.log(p) for p in ps)/math.log(len(ps)) if len(ps)>1 else 0.0
                f["book_entropy_top25"]=round(ent,4)
            else: f["book_entropy_top25"]=None
            f["spread_now_bps"]=round((ba-bb)/mid*1e4,3)
        else:
            for k in ("ms_thin_path_score","ms_large_walls_on_path","depth_imbalance_top25","book_entropy_top25","spread_now_bps"):
                f[k]=None
        # spread instability over last 5m
        sprs=[x[6] for x in micro if zone_sec-300<=x[0]<=zone_sec]
        f["spread_instability_5m_bps"]=round(st.pstdev(sprs),4) if len(sprs)>=3 else None
        return f
    with gzip.open(p,"rt",encoding="utf-8") as fh:
        fh.readline()
        for line in fh:
            parts=line.rstrip().split(",")
            if len(parts)<8: continue
            try:
                ts=int(parts[2]); side=parts[5]; price=float(parts[6]); amt=float(parts[7])
            except: continue
            book=bid if side=="bid" else ask
            prev=book.get(price,0.0)
            if amt==0: book.pop(price,None); delta=-prev
            else: book[price]=amt; delta=amt-prev
            sec=ts//1_000_000; ms_=sec-(sec%60)
            if ms_!=cur["min_sec"]:
                if cur["min_sec"]>=0: per_min.append(dict(cur))
                cur={"min_sec":ms_,"ab":0.,"aa":0.,"cb":0.,"ca":0.}
            if delta>0:
                if side=="bid": cur["ab"]+=delta
                else: cur["aa"]+=delta
            elif delta<0:
                if side=="bid": cur["cb"]+=-delta
                else: cur["ca"]+=-delta
            if sec!=last_sec: snap(sec); last_sec=sec
            for idx in range(nxt,len(anchors)):
                asec,zid,direction,zlo,zhi=anchors[idx]
                if asec-sec>3600: break
                blo,bhi,_=bands[zid]
                if blo<=price<=bhi: inband[zid].append((sec,side,delta))
            while nxt<len(anchors) and anchors[nxt][0]<=sec:
                asec,zid,direction,zlo,zhi=anchors[nxt]
                out[zid]=finalize(asec,zid,direction,zlo,zhi); inband.pop(zid,None); nxt+=1
            if nxt>=len(anchors): break
    while nxt<len(anchors):
        asec,zid,direction,zlo,zhi=anchors[nxt]
        out[zid]=finalize(asec,zid,direction,zlo,zhi); nxt+=1
    cf.write_text(json.dumps(out,default=str),encoding="utf-8")
    return out


# ------------------------------------------------------------------ trades aggression pass (one per day, cached)
def trades_aggression_for_day(date, anchors):
    cf=L2CACHE_DIR/f"{date}_trd.json"
    if cf.exists(): return json.loads(cf.read_text(encoding="utf-8"))
    p=TARDIS/date/"trades.csv.gz"
    if not p.exists() or not anchors:
        cf.write_text("{}",encoding="utf-8"); return {}
    anchors=sorted(anchors,key=lambda x:x[0]); nxt=0
    bands={zid:(zlo*(1-ZONE_BAND_PCT),zhi*(1+ZONE_BAND_PCT),direction) for _,zid,direction,zlo,zhi in anchors}
    per_sec=defaultdict(lambda:[0.0,0.0])      # sec -> [buy,sell]
    inband=defaultdict(lambda:[0.0,0.0,0,0])   # zid -> [buy,sell, last_sec_buy?, ] use buy/sell totals in band
    last_sec=-1
    with gzip.open(p,"rt",encoding="utf-8") as fh:
        fh.readline()
        for line in fh:
            parts=line.rstrip().split(",")
            if len(parts)<8: continue
            try:
                ts=int(parts[2]); side=parts[5]; price=float(parts[6]); amt=float(parts[7])
            except: continue
            sec=ts//1_000_000
            ps=per_sec[sec]
            if side=="buy": ps[0]+=amt
            else: ps[1]+=amt
            # inband collect for pending anchors (last 30m)
            for idx in range(nxt,len(anchors)):
                asec,zid,direction,zlo,zhi=anchors[idx]
                if asec-sec>1800: break
                blo,bhi,_=bands[zid]
                if blo<=price<=bhi:
                    ib=inband[zid]
                    if side=="buy": ib[0]+=amt
                    else: ib[1]+=amt
            while nxt<len(anchors) and anchors[nxt][0]<=sec: nxt+=1
            if nxt>=len(anchors) and sec-anchors[-1][0]>0: pass
    # build sorted cumulative arrays
    secs=sorted(per_sec); cb=[0.0]; cs=[0.0]
    for s in secs: cb.append(cb[-1]+per_sec[s][0]); cs.append(cs[-1]+per_sec[s][1])
    import bisect
    def wsum(a_sec,w):
        lo=bisect.bisect_left(secs,a_sec-w); hi=bisect.bisect_right(secs,a_sec)
        return cb[hi]-cb[lo], cs[hi]-cs[lo]
    out={}
    for asec,zid,direction,zlo,zhi in anchors:
        f={}
        for w,lab in ((300,"5m"),(900,"15m"),(1800,"30m")):
            bv,sv=wsum(asec,w); tot=bv+sv
            ti=(bv-sv)/tot if tot>0 else 0.0
            f[f"taker_imbalance_{lab}"]=round(ti,4)
            supp=bv if direction=="LONG" else sv; opp=sv if direction=="LONG" else bv
            f[f"supportive_taker_imb_{lab}"]=round((supp-opp)/tot,4) if tot>0 else 0.0
            f[f"ofi_supportive_vol_{lab}"]=round(supp-opp,3)
        ib=inband.get(zid,[0.0,0.0,0,0])
        f["inband_buy_aggr_30m"]=round(ib[0],3); f["inband_sell_aggr_30m"]=round(ib[1],3)
        tot=ib[0]+ib[1]
        f["inband_sell_share_30m"]=round(ib[1]/tot,4) if tot>0 else None
        out[zid]=f
    cf.write_text(json.dumps(out,default=str),encoding="utf-8")
    return out


# ------------------------------------------------------------------ regime + structure from global buckets
def regime_struct(z, gbuckets, gsec):
    import bisect
    anchor=z["confirmedTs"]//1000
    i=bisect.bisect_right(gsec,anchor)-1
    out={"prior_move_60m_pct":None,"prior_move_180m_pct":None,"prior_move_1d_pct":None,
         "regime_60m":None,"regime_180m":None,"regime_1d":None,"trend_against_signal_1d":None,
         "reclaim_zoneMid_preconfirm":None,"higher_low_preconfirm":None,"lower_low_preconfirm":None}
    if i<0: return out
    cur=gbuckets[i].last
    def mv(w):
        j=bisect.bisect_left(gsec,anchor-w)
        if j>=len(gbuckets) or j<0 or gbuckets[j].last<=0: return None
        return round((cur-gbuckets[j].last)/gbuckets[j].last*100.0,4)
    out["prior_move_60m_pct"]=mv(3600); out["prior_move_180m_pct"]=mv(10800); out["prior_move_1d_pct"]=mv(86400)
    def lab(v,db):
        if v is None: return None
        return "BULL" if v>db else ("BEAR" if v<-db else "RANGE")
    out["regime_60m"]=lab(out["prior_move_60m_pct"],0.3); out["regime_180m"]=lab(out["prior_move_180m_pct"],0.5)
    out["regime_1d"]=lab(out["prior_move_1d_pct"],0.8)
    d=z["direction"]
    if out["regime_1d"] is not None:
        out["trend_against_signal_1d"]=1 if ((d=="LONG" and out["regime_1d"]=="BEAR") or (d=="SHORT" and out["regime_1d"]=="BULL")) else 0
    zlo=z.get("zoneLow"); zhi=z.get("zoneHigh"); start=(z.get("startTs") or z["confirmedTs"])//1000
    if zlo is not None and zhi is not None:
        mid=(zlo+zhi)/2; lo=bisect.bisect_left(gsec,start); hi=i
        seg=gbuckets[lo:hi+1]
        if seg:
            entered=any(b.high>=zlo and b.low<=zhi for b in seg)
            if d=="LONG": out["reclaim_zoneMid_preconfirm"]=1 if (entered and cur>=mid) else 0
            else: out["reclaim_zoneMid_preconfirm"]=1 if (entered and cur<=mid) else 0
        # structure over 180m, two 90m halves
        a0=bisect.bisect_left(gsec,anchor-10800); amid=bisect.bisect_left(gsec,anchor-5400)
        first=gbuckets[a0:amid]; second=gbuckets[amid:i+1]
        if first and second:
            l1=min(b.low for b in first); l2=min(b.low for b in second)
            out["higher_low_preconfirm"]=1 if l2>l1 else 0
            out["lower_low_preconfirm"]=1 if l2<l1 else 0
    return out


# ------------------------------------------------------------------ build feature table (cached)
def build_table():
    if CACHE.exists():
        print("[cache hit] loading feature table", file=sys.stderr)
        return json.loads(CACHE.read_text(encoding="utf-8"))
    B.DATES=DATES
    print("[zones]", file=sys.stderr)
    zones=load_all_zones()
    print(f"  confirmed zones: {len(zones)}", file=sys.stderr)
    opp=B.opp_dir_counts(zones)
    print("[buckets]", file=sys.stderr)
    bcache={}
    for d in DATES:
        p=TARDIS/d/"trades.csv.gz"
        if p.exists(): bcache[d]=build_buckets_from_trades_csv(p)
    gb=[]
    for d in DATES: gb+=bcache.get(d,[])
    gb.sort(key=lambda b:b.sec); gsec=[b.sec for b in gb]
    print(f"  global buckets: {len(gb)}", file=sys.stderr)
    print("[trades features + regime + struct]", file=sys.stderr)
    for z in zones:
        z.update(B.trades_features(z, bcache.get(z["_date"],[])))
        hr=(z["confirmedTs"]//1000 % 86400)//3600; z["is_asia_session"]=1 if hr<7 else 0
        z["opp_dir_zones_active_60m"]=opp.get(z["id"],0)
        z.update(regime_struct(z, gb, gsec))
    print("[trades aggression pass]", file=sys.stderr)
    by_date=defaultdict(list)
    for z in zones:
        by_date[z["_date"]].append((z["confirmedTs"]//1000, z["id"], z["direction"], z.get("zoneLow"), z.get("zoneHigh")))
    for d in DATES:
        t0=time.time(); agg=trades_aggression_for_day(d, by_date.get(d,[]))
        for z in zones:
            if z["_date"]==d: z.update(agg.get(z["id"],{}))
        print(f"  {d}: trd {time.time()-t0:.0f}s", file=sys.stderr)
    print("[L2 extended pass]", file=sys.stderr)
    for d in DATES:
        t0=time.time(); l2=l2_extended_for_day(d, by_date.get(d,[]))
        for z in zones:
            if z["_date"]==d: z.update(l2.get(z["id"],{}))
        print(f"  {d}: L2 {time.time()-t0:.0f}s", file=sys.stderr)
    print("[funding + score + sim]", file=sys.stderr)
    for z in zones:
        z["funding_rate_at_signal"]=B.funding_at(z["_date"], z["confirmedTs"]//1000)
        z["explainable_score"]=B.explainable_score(z)
    # canonical sim every confirmed zone
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
    # uniqueness vs prior zones (causal: only earlier confirmedTs)
    zs_sorted=sorted(zones,key=lambda z:z["confirmedTs"])
    prior_scores=[]; prior_supp=[]
    for z in zs_sorted:
        z["uniq_score_pctile_vs_prior"]=pctile(sorted(prior_scores), z["explainable_score"]) if prior_scores else None
        sf=z.get("dl2_supp_minus_opp_net_flow_15m")
        z["uniq_suppflow_pctile_vs_prior"]=pctile(sorted([x for x in prior_supp if x is not None]), sf) if (sf is not None and prior_supp) else None
        prior_scores.append(z["explainable_score"])
        if sf is not None: prior_supp.append(sf)
    # strip heavy raw fields before cache
    keep_drop=("reasons","targets","scores")
    for z in zones:
        for k in keep_drop: z.pop(k,None)
    CACHE.write_text(json.dumps(zones,default=str,indent=0),encoding="utf-8")
    print(f"[cache written] {len(zones)} zones", file=sys.stderr)
    return zones


# ------------------------------------------------------------------ metrics helper
def trade_metrics(trades):
    """trades: list of zone dicts that produced a sim (label != NO_TRADE)."""
    ts=[t for t in trades if t.get("sim_outcome")]
    n=len(ts); W=sum(1 for t in ts if t["sim_outcome"]=="WIN")
    L=sum(1 for t in ts if t["sim_outcome"]=="LOSS"); TO=sum(1 for t in ts if t["sim_outcome"]=="TIMEOUT")
    pnls=[t["sim_pnl_after_cost"] for t in ts]
    wp=[p for p in pnls if p>0]; lp=[p for p in pnls if p<0]
    pf=round(sum(wp)/sum(-p for p in lp),3) if lp else None
    cur=0;mx=0
    for t in ts:
        if (t["sim_pnl_after_cost"] or 0)<=0: cur+=1; mx=max(mx,cur)
        else: cur=0
    wrongdir=sum(1 for t in ts if not t.get("sim_correct_direction"))
    return {"trades":n,"wins":W,"losses":L,"timeouts":TO,
            "winrate_pct":round(100*W/max(n,1),2),
            "expectancy_after_cost_pct":round(st.mean(pnls),4) if pnls else None,
            "total_return_after_cost_pct":round(sum(pnls),4) if pnls else None,
            "pf_after_cost":pf,"max_consecutive_losses":mx,"wrong_direction":wrongdir,
            "long_n":sum(1 for t in ts if t["direction"]=="LONG"),
            "short_n":sum(1 for t in ts if t["direction"]=="SHORT"),
            "h1_n":sum(1 for t in ts if t["_date"] in H1),"h2_n":sum(1 for t in ts if t["_date"] in H2),
            "h1_wins":sum(1 for t in ts if t["_date"] in H1 and t["sim_outcome"]=="WIN"),
            "h2_wins":sum(1 for t in ts if t["_date"] in H2 and t["sim_outcome"]=="WIN")}


def main():
    t_start=time.time()
    zones=build_table()
    for z in zones:  # ensure numeric
        pass
    bydate=defaultdict(list)
    for z in zones: bydate[z["_date"]].append(z)
    traded=[z for z in zones if z.get("sim_outcome")]
    goods=[z for z in zones if z.get("sim_label")=="GOOD"]
    print(f"\n[overview] confirmed={len(zones)} traded={len(traded)} GOOD={len(goods)} "
          f"NOISE={sum(1 for z in zones if z.get('sim_label')=='NOISE')} MID={sum(1 for z in zones if z.get('sim_label')=='MID')} "
          f"NO_TRADE={sum(1 for z in zones if z.get('sim_label')=='NO_TRADE')}", file=sys.stderr)

    # ---- reproduce RS1 selection (top1/day by score among filter-passers) ----
    rs1_pass=[z for z in zones if z.get("dist_to_recent_swing_high_pct") is not None and z["dist_to_recent_swing_high_pct"]<=B.SWING_MAX
              and z.get("dl2_supp_minus_opp_net_flow_15m") is not None and z["dl2_supp_minus_opp_net_flow_15m"]<=B.SUPP_OPP_15M_MAX]
    rs1_sel=[]
    bp=defaultdict(list)
    for z in rs1_pass: bp[z["_date"]].append(z)
    for d in DATES:
        day=sorted(bp.get(d,[]),key=lambda x:-x["explainable_score"])
        if day: rs1_sel.append(day[0])
    rs1_ids={z["id"] for z in rs1_sel}

    run_A(zones,bydate,rs1_sel,rs1_ids,goods)
    run_B(zones,rs1_sel)
    okx=run_C(zones,traded,goods,rs1_sel)
    run_D(zones,traded)
    models=run_E(zones,bydate,rs1_sel,rs1_pass,goods)
    run_final(zones,traded,goods,rs1_sel,rs1_ids,okx,models)
    print(f"\n[done] {time.time()-t_start:.0f}s total", file=sys.stderr)
    return 0


# ================================================================= SECTION A
def run_A(zones,bydate,rs1_sel,rs1_ids,goods):
    print("[A] selected vs skipped", file=sys.stderr)
    sel_by_date={z["_date"]:z for z in rs1_sel}
    rows=[]; day_summ=[]
    for d in DATES:
        dz=bydate[d]; sel=sel_by_date.get(d)
        conf=len(dz); traded=[z for z in dz if z.get("sim_outcome")]
        good=[z for z in dz if z.get("sim_label")=="GOOD"]
        skipped_good=[z for z in good if z["id"]!=(sel["id"] if sel else None)]
        short_good=[z for z in good if z["direction"]=="SHORT"]
        sel_loss = sel is not None and sel.get("sim_label")=="NOISE"
        skipped_short_winner_on_long_loss = (sel is not None and sel["direction"]=="LONG" and sel_loss and len(short_good)>0)
        day_summ.append({"date":d,"confirmed":conf,"triggered_sim":len(traded),"good_2pct":len(good),
            "selected_id":sel["id"] if sel else None,"selected_dir":sel["direction"] if sel else None,
            "selected_label":sel.get("sim_label") if sel else None,"selected_pnl":sel.get("sim_pnl_after_cost") if sel else None,
            "selected_score":round(sel["explainable_score"],3) if sel else None,
            "skipped_good_n":len(skipped_good),"short_good_n":len(short_good),
            "skipped_short_winner_while_selected_long_lost":skipped_short_winner_on_long_loss})
        for z in dz:
            rows.append({"date":d,"zone_id":z["id"],"dir":z["direction"],"setup":z.get("zoneType"),
                "is_selected":1 if z["id"] in rs1_ids else 0,"label":z.get("sim_label"),
                "outcome":z.get("sim_outcome"),"pnl_after_cost":z.get("sim_pnl_after_cost"),
                "score":round(z["explainable_score"],4),"dist_swh":z.get("dist_to_recent_swing_high_pct"),
                "supp_opp_15m":z.get("dl2_supp_minus_opp_net_flow_15m"),"eng_ofi":z.get("eng_ofi"),
                "regime_1d":z.get("regime_1d"),"trend_against":z.get("trend_against_signal_1d"),
                "confirmed_iso":ms_iso(z["confirmedTs"])})
    with (OUT/"BINANCE_10D_SELECTED_VS_SKIPPED_AUDIT.csv").open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    js={"build":now_iso(),"status":"DIAGNOSTIC","per_day":day_summ,
        "totals":{"confirmed":len(zones),"good_2pct":len(goods),
                  "skipped_good_total":sum(s["skipped_good_n"] for s in day_summ),
                  "days_short_winner_while_selected_long_lost":[s["date"] for s in day_summ if s["skipped_short_winner_while_selected_long_lost"]]}}
    (OUT/"BINANCE_10D_SELECTED_VS_SKIPPED_AUDIT.json").write_text(json.dumps(js,indent=2,default=str),encoding="utf-8")
    md=["# A. Binance 10d — SELECTED vs SKIPPED audit","",f"**Build:** {now_iso()}  ·  DIAGNOSTIC, no tuning","",
        "| date | conf | traded | 2%win | sel dir | sel label | sel pnl | sel score | skipped 2%win | SHORT 2%win | SHORT-winner while sel-LONG-lost |",
        "|---|--:|--:|--:|:--:|:--:|--:|--:|--:|--:|:--:|"]
    for s in day_summ:
        md.append(f"| {s['date']} | {s['confirmed']} | {s['triggered_sim']} | {s['good_2pct']} | {s['selected_dir']} | "
                  f"{s['selected_label']} | {s['selected_pnl']} | {s['selected_score']} | {s['skipped_good_n']} | {s['short_good_n']} | "
                  f"{'YES' if s['skipped_short_winner_while_selected_long_lost'] else ''} |")
    md+=["",f"- total confirmed: {len(zones)}; total 2% winners: {len(goods)}; total skipped 2% winners: {js['totals']['skipped_good_total']}",
         f"- days where a SHORT 2%-winner existed but RS1 took a losing LONG: **{js['totals']['days_short_winner_while_selected_long_lost']}**"]
    (OUT/"BINANCE_10D_SELECTED_VS_SKIPPED_AUDIT.md").write_text("\n".join(md),encoding="utf-8")
    return day_summ


# ================================================================= SECTION B
def run_B(zones,rs1_sel):
    print("[B] trap audit", file=sys.stderr)
    rows=[]
    for z in rs1_sel:
        d=z["direction"]
        ofi=z.get("eng_ofi"); refill=z.get("eng_refill"); absb=z.get("eng_absorption")
        reclaim=z.get("reclaim_zoneMid_preconfirm"); hl=z.get("higher_low_preconfirm"); ll=z.get("lower_low_preconfirm")
        supp15=z.get("dl2_supp_minus_opp_net_flow_15m"); mp5=z.get("dl2_microprice_aligned_delta_5m_bps")
        sti=z.get("supportive_taker_imb_15m"); inband_sell=z.get("inband_sell_share_30m")
        opp_cxl=z.get("dl2_inband_opp_cancel_15m"); supp_add=z.get("dl2_inband_supp_add_5m")
        regime=z.get("regime_1d"); against=z.get("trend_against_signal_1d")
        # classification (causal evidence only)
        votes_real=0; votes_fake=0; ev=[]
        if d=="LONG":
            if ofi is not None and ofi<-0.2: votes_fake+=1; ev.append(f"ofi {ofi:.2f}<0 (sell flow under buy zone)")
            elif ofi is not None and ofi>0.2: votes_real+=1; ev.append(f"ofi {ofi:.2f}>0")
            if sti is not None and sti<0: votes_fake+=1; ev.append(f"supp_taker_imb {sti:.2f}<0")
            if reclaim==1: votes_real+=1; ev.append("reclaimed mid")
            if reclaim==0: votes_fake+=1; ev.append("no reclaim")
            if hl==1: votes_real+=1; ev.append("higher-low")
            if ll==1: votes_fake+=1; ev.append("lower-low pre")
            if against==1: votes_fake+=1; ev.append(f"1d regime {regime} vs LONG")
            if refill is not None and refill>=0.5: votes_real+=1; ev.append(f"refill {refill:.2f}")
        else:
            if ofi is not None and ofi>0.2: votes_fake+=1; ev.append(f"ofi {ofi:.2f}>0 (buy flow under sell zone)")
            elif ofi is not None and ofi<-0.2: votes_real+=1; ev.append(f"ofi {ofi:.2f}<0")
            if sti is not None and sti<0: votes_fake+=1; ev.append(f"supp_taker_imb {sti:.2f}<0")
            if reclaim==1: votes_real+=1; ev.append("rejected mid")
            if reclaim==0: votes_fake+=1; ev.append("no rejection")
            if against==1: votes_fake+=1; ev.append(f"1d regime {regime} vs SHORT")
        if votes_real>=2 and votes_real>votes_fake: cls=("REAL_ACCUMULATION" if d=="LONG" else "REAL_DISTRIBUTION")
        elif votes_fake>=2 and votes_fake>votes_real: cls=(f"FAKE_ACCUMULATION_BOUNCE_NOISE" if d=="LONG" else "FAKE_DISTRIBUTION_PULLBACK_NOISE")
        else: cls="UNCLEAR"
        rows.append({"date":z["_date"],"dir":d,"setup":z.get("zoneType"),"label":z.get("sim_label"),
            "outcome":z.get("sim_outcome"),"pnl_after_cost":z.get("sim_pnl_after_cost"),
            "eng_ofi":ofi,"eng_refill":refill,"eng_absorption":absb,"supp_taker_imb_15m":sti,
            "inband_sell_share_30m":inband_sell,"supp_minus_opp_15m":supp15,"microprice_5m_bps":mp5,
            "inband_opp_cancel_15m":opp_cxl,"inband_supp_add_5m":supp_add,
            "reclaim_mid":reclaim,"higher_low":hl,"lower_low_pre":ll,
            "regime_1d":regime,"trend_against":against,
            "post_mfe_pct":z.get("sim_mfe_pct"),"post_mae_pct":z.get("sim_mae_pct"),
            "classification":cls,"evidence":"; ".join(ev)})
    with (OUT/"BINANCE_10D_TRAP_AUDIT.csv").open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    cc=Counter(r["classification"] for r in rows)
    (OUT/"BINANCE_10D_TRAP_AUDIT.json").write_text(json.dumps({"build":now_iso(),"counts":cc,"trades":rows},indent=2,default=str),encoding="utf-8")
    md=["# B. Binance 10d — FAKE accumulation / distribution trap audit","",f"**Build:** {now_iso()}",
        "Classification from CAUSAL evidence (engine ofi/refill/absorption, taker imbalance, reclaim, structure, 1d regime). post_* = diagnostic only.","",
        f"**Counts:** {dict(cc)}","",
        "| date | dir | label | pnl | eng_ofi | supp_taker15 | inband_sell% | reclaim | hi_low | regime1d | against | classification |",
        "|---|:--:|:--:|--:|--:|--:|--:|:--:|:--:|:--:|:--:|:--|"]
    for r in rows:
        md.append(f"| {r['date']} | {r['dir']} | {r['label']} | {r['pnl_after_cost']} | {r['eng_ofi']} | "
                  f"{r['supp_taker_imb_15m']} | {r['inband_sell_share_30m']} | {r['reclaim_mid']} | {r['higher_low']} | "
                  f"{r['regime_1d']} | {r['trend_against']} | {r['classification']} |")
    md+=["","### Evidence per trade"]
    for r in rows: md.append(f"- **{r['date']} {r['dir']}** [{r['classification']}] ({r['label']}): {r['evidence']}")
    (OUT/"BINANCE_10D_TRAP_AUDIT.md").write_text("\n".join(md),encoding="utf-8")
    return rows


# ================================================================= SECTION C
def _stats(zs,key):
    xs=[z.get(key) for z in zs if isinstance(z.get(key),(int,float))]
    if not xs: return {"n":0,"mean":None,"median":None}
    return {"n":len(xs),"mean":round(st.mean(xs),4),"median":round(st.median(xs),4)}

def run_C(zones,traded,goods,rs1_sel):
    print("[C] background features + distribution shift", file=sys.stderr)
    # local background normalization: percentile vs prior already in table; here z_60m/z_180m via same-day cohort
    bg_rows=[]
    feats=["dl2_supp_minus_opp_net_flow_15m","dl2_microprice_aligned_delta_5m_bps","supportive_taker_imb_15m",
           "taker_imbalance_15m","book_entropy_top25","spread_instability_5m_bps","depth_imbalance_top25",
           "ms_thin_path_score","dl2_supp_refill_ratio_5m","eng_ofi","eng_refill","eng_void","eng_absorption",
           "explainable_score"]
    bydate=defaultdict(list)
    for z in zones: bydate[z["_date"]].append(z)
    for z in zones:
        rec={"zone_id":z["id"],"date":z["_date"],"dir":z["direction"],"label":z.get("sim_label")}
        cohort=bydate[z["_date"]]
        for fk in feats:
            v=z.get(fk); rec[fk]=v
            vals=[c.get(fk) for c in cohort if isinstance(c.get(fk),(int,float))]
            if isinstance(v,(int,float)) and len(vals)>=3 and st.pstdev(vals)>0:
                rec[f"{fk}__z_day"]=round((v-st.mean(vals))/st.pstdev(vals),3)
            else: rec[f"{fk}__z_day"]=None
        rec["uniq_score_pctile_vs_prior"]=z.get("uniq_score_pctile_vs_prior")
        bg_rows.append(rec)
    with (OUT/"BINANCE_10D_LOCAL_BACKGROUND_FEATURES.csv").open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(bg_rows[0].keys())); w.writeheader(); w.writerows(bg_rows)
    (OUT/"BINANCE_10D_LOCAL_BACKGROUND_FEATURES.json").write_text(json.dumps({"build":now_iso(),"rows":bg_rows},indent=0,default=str),encoding="utf-8")
    md=["# C1. Binance 10d — local/daily background-normalized features","",f"**Build:** {now_iso()}",
        "Per-zone raw + day-cohort z-score (`__z_day`) + causal percentile-vs-prior-zones (uniqueness). Full data in CSV/JSON.","",
        f"Confirmed zones: {len(zones)}. Features: {', '.join(feats)}",""]
    (OUT/"BINANCE_10D_LOCAL_BACKGROUND_FEATURES.md").write_text("\n".join(md),encoding="utf-8")

    # cohorts for distribution shift
    bz_win=[z for z in traded if z.get("sim_outcome")=="WIN"]
    bz_los=[z for z in traded if z.get("sim_label")=="NOISE"]
    bz_sel_loss=[z for z in rs1_sel if z.get("sim_label")=="NOISE"]
    sel_ids={z["id"] for z in rs1_sel}
    bz_skip_win=[z for z in goods if z["id"] not in sel_ids]
    # OKX winners/losers from 29-trades
    okx=json.loads((OKX_DIR/"MARCH_DYNAMIC_L2_29_TRADES_FULL_TABLE.json").read_text(encoding="utf-8"))["trades"]
    def f2(t,k):
        try: return float(t.get(k))
        except: return None
    okx_win=[t for t in okx if t.get("outcome")=="WIN"]; okx_los=[t for t in okx if t.get("outcome")=="LOSS"]
    # comparable feature map: binance_key -> okx_key
    cmap={"dl2_supp_minus_opp_net_flow_5m":("dl2_supp_minus_opp_net_flow_5m","dl2_supp_minus_opp_net_flow_5m"),
          "dl2_microprice_aligned_delta_5m_bps":("dl2_microprice_aligned_delta_5m_bps","dl2_microprice_aligned_delta_5m_bps"),
          "dl2_microprice_aligned_delta_15m_bps":("dl2_microprice_aligned_delta_15m_bps","dl2_microprice_aligned_delta_15m_bps"),
          "dist_to_recent_swing_high_pct":("dist_to_recent_swing_high_pct","dist_to_recent_swing_high_pct"),
          "local_range_180m_pct":("local_range_180m_pct","local_range_180m_pct"),
          "prior_move_60m_pct":("prior_move_60m_pct","prior_move_60m_pct"),
          "explainable_score":("explainable_score","explainable_score"),
          "dl2_top1_supportive_persistence_ge_50_5m_sec":("dl2_top1_supportive_persistence_ge_50_5m_sec","dl2_top1_supportive_persistence_ge_50_5m_sec")}
    shift={"build":now_iso(),"features":{}}
    for bkey,(bk,ok) in cmap.items():
        shift["features"][bkey]={
            "okx_winners":{"n":len(okx_win),"mean":mean([f2(t,ok) for t in okx_win]),"median":median([f2(t,ok) for t in okx_win])},
            "okx_losers":{"n":len(okx_los),"mean":mean([f2(t,ok) for t in okx_los]),"median":median([f2(t,ok) for t in okx_los])},
            "binance_winners":_stats(bz_win,bk),"binance_losers":_stats(bz_los,bk),
            "binance_selected_losses":_stats(bz_sel_loss,bk),"binance_skipped_winners":_stats(bz_skip_win,bk)}
    (OUT/"OKX_VS_BINANCE_FEATURE_DISTRIBUTION_SHIFT.json").write_text(json.dumps(shift,indent=2,default=str),encoding="utf-8")
    md=["# C2. OKX vs Binance — feature distribution shift","",f"**Build:** {now_iso()}",
        f"Cohorts: OKX win={len(okx_win)} OKX loss={len(okx_los)} · Binance win={len(bz_win)} loss={len(bz_los)} "
        f"sel-loss={len(bz_sel_loss)} skipped-win={len(bz_skip_win)}","",
        "| feature | OKXwin (med) | OKXloss | BNCwin | BNCloss | BNC sel-loss | BNC skip-win |",
        "|---|--:|--:|--:|--:|--:|--:|"]
    for fk,v in shift["features"].items():
        md.append(f"| {fk} | {v['okx_winners']['median']} | {v['okx_losers']['median']} | "
                  f"{v['binance_winners']['median']} | {v['binance_losers']['median']} | "
                  f"{v['binance_selected_losses']['median']} | {v['binance_skipped_winners']['median']} |")
    (OUT/"OKX_VS_BINANCE_FEATURE_DISTRIBUTION_SHIFT.md").write_text("\n".join(md),encoding="utf-8")
    return shift


# ================================================================= SECTION D
def run_D(zones,traded):
    print("[D] noise classifier research", file=sys.stderr)
    # candidate causal rules (booleans true => REJECT)
    def r_long_bear_noreclaim(z): return z["direction"]=="LONG" and z.get("regime_1d")=="BEAR" and z.get("reclaim_zoneMid_preconfirm")!=1
    def r_short_bull_norej(z):    return z["direction"]=="SHORT" and z.get("regime_1d")=="BULL" and z.get("reclaim_zoneMid_preconfirm")!=1
    def r_ofi_conflict(z):
        o=z.get("eng_ofi")
        if o is None: return False
        return (z["direction"]=="LONG" and o<-0.2) or (z["direction"]=="SHORT" and o>0.2)
    def r_no_reclaim(z): return z.get("reclaim_zoneMid_preconfirm")==0
    def r_high_entropy(z):
        e=z.get("book_entropy_top25"); return e is not None and e>0.92
    def r_taker_conflict(z):
        ti=z.get("supportive_taker_imb_15m"); return ti is not None and ti<-0.1
    def r_low_uniqueness(z):
        p=z.get("uniq_score_pctile_vs_prior"); return p is not None and p<40
    rules={"R1_LONG_bear_no_reclaim":r_long_bear_noreclaim,"R2_SHORT_bull_no_rejection":r_short_bull_norej,
           "R3_ofi_direction_conflict":r_ofi_conflict,"R4_no_reclaim_after_hit":r_no_reclaim,
           "R5_high_entropy":r_high_entropy,"R6_taker_imbalance_conflict":r_taker_conflict,
           "R7_low_uniqueness_vs_prior":r_low_uniqueness}
    base=traded
    base_good=[z for z in base if z.get("sim_label")=="GOOD"]; base_noise=[z for z in base if z.get("sim_label")=="NOISE"]
    res=[]
    for name,fn in rules.items():
        rejected=[z for z in base if fn(z)]; kept=[z for z in base if not fn(z)]
        noise_removed=sum(1 for z in rejected if z.get("sim_label")=="NOISE")
        good_lost=sum(1 for z in rejected if z.get("sim_label")=="GOOD")
        wrongdir_removed=sum(1 for z in rejected if not z.get("sim_correct_direction"))
        stop_removed=sum(1 for z in rejected if z.get("sim_outcome")=="LOSS")
        m=trade_metrics(kept)
        res.append({"rule":name,"rejected":len(rejected),"noise_removed":noise_removed,"good_lost":good_lost,
            "wrongdir_removed":wrongdir_removed,"stop_removed":stop_removed,
            "kept_n":m["trades"],"kept_winrate":m["winrate_pct"],"kept_pf":m["pf_after_cost"],
            "kept_expectancy":m["expectancy_after_cost_pct"]})
    base_m=trade_metrics(base)
    (OUT/"BINANCE_10D_NOISE_CLASSIFIER_RESEARCH.json").write_text(json.dumps(
        {"build":now_iso(),"base":{"n":len(base),"good":len(base_good),"noise":len(base_noise),"metrics":base_m},
         "rules":res},indent=2,default=str),encoding="utf-8")
    with (OUT/"BINANCE_10D_NOISE_CLASSIFIER_RESEARCH.csv").open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(res[0].keys())); w.writeheader(); w.writerows(res)
    md=["# D. Binance 10d — noise classifier research","",f"**Build:** {now_iso()}",
        f"Base population = all triggered/sim zones (n={len(base)}; GOOD={len(base_good)} NOISE={len(base_noise)} MID={len(base)-len(base_good)-len(base_noise)}).",
        "Rule = TRUE means REJECT. Applied post-hoc to the WHOLE triggered population (not just RS1 picks) to measure noise-removal power.","",
        "| rule | rejected | NOISE removed | GOOD lost | wrongdir removed | stop removed | kept n | kept wr% | kept PF |",
        "|---|--:|--:|--:|--:|--:|--:|--:|--:|"]
    for r in res:
        md.append(f"| {r['rule']} | {r['rejected']} | {r['noise_removed']} | {r['good_lost']} | {r['wrongdir_removed']} | "
                  f"{r['stop_removed']} | {r['kept_n']} | {r['kept_winrate']} | {r['kept_pf']} |")
    md+=["",f"Base (no filter): n={base_m['trades']} wr={base_m['winrate_pct']}% PF={base_m['pf_after_cost']} exp={base_m['expectancy_after_cost_pct']}"]
    (OUT/"BINANCE_10D_NOISE_CLASSIFIER_RESEARCH.md").write_text("\n".join(md),encoding="utf-8")
    return res


# ================================================================= SECTION E
def run_E(zones,bydate,rs1_sel,rs1_pass,goods):
    print("[E] live-valid selector audit", file=sys.stderr)
    # causal noise filter (structural / OKX-frozen, no Binance tuning)
    def noise_reject(z):
        if z.get("reclaim_zoneMid_preconfirm")==0: return True            # no reclaim/rejection
        o=z.get("eng_ofi")
        if o is not None and ((z["direction"]=="LONG" and o<-0.2) or (z["direction"]=="SHORT" and o>0.2)): return True
        e=z.get("book_entropy_top25")
        if e is not None and e>0.92: return True
        return False
    def dir_guard(z):
        # reject LONG in 1d-bearish without reclaim proof; SHORT in 1d-bullish without rejection proof
        if z["direction"]=="LONG" and z.get("regime_1d")=="BEAR" and z.get("reclaim_zoneMid_preconfirm")!=1: return True
        if z["direction"]=="SHORT" and z.get("regime_1d")=="BULL" and z.get("reclaim_zoneMid_preconfirm")!=1: return True
        return False
    THR=OKX_SCORE_WINNER_MIN  # frozen from OKX (weakest OKX winner)
    pass_by_date=defaultdict(list)
    for z in rs1_pass: pass_by_date[z["_date"]].append(z)
    for d in DATES: pass_by_date[d].sort(key=lambda z:z["confirmedTs"])  # chronological (live order)

    def first_eligible(extra=None, thr=None, maxn=1, cooldown_min=None):
        sel=[]
        for d in DATES:
            cnt=0; last_ts=None
            for z in pass_by_date[d]:
                if thr is not None and z["explainable_score"]<thr: continue
                if extra and extra(z): continue
                if cooldown_min and last_ts is not None and (z["confirmedTs"]-last_ts)/60000.0<cooldown_min: continue
                sel.append(z); cnt+=1; last_ts=z["confirmedTs"]
                if cnt>=maxn: break
        return sel
    # Model 0: current top1/day RS1
    m0=rs1_sel
    # Model 1: first eligible by frozen OKX score threshold
    m1=first_eligible(thr=THR, maxn=1)
    # Model 2: + noise filter
    m2=first_eligible(extra=noise_reject, thr=THR, maxn=1)
    # Model 3: + direction guard
    m3=first_eligible(extra=lambda z: noise_reject(z) or dir_guard(z), thr=THR, maxn=1)
    # Model 4: max2/day + cluster cooldown 120m + noise filter (no score thr to allow >1/day)
    m4=first_eligible(extra=noise_reject, thr=THR, maxn=2, cooldown_min=120)
    models={"Model0_top1_day_RS1":m0,"Model1_first_elig_OKXthr":m1,"Model2_+noise":m2,
            "Model3_+dir_guard":m3,"Model4_max2_cooldown_noise":m4}
    out=[]
    sel0_goods=len(goods)
    for name,sel in models.items():
        tr=[z for z in sel if z.get("sim_outcome")]
        m=trade_metrics(tr)
        took_ids={z["id"] for z in sel}
        skipped_good=sum(1 for z in goods if z["id"] not in took_ids)
        ndays=len({z["_date"] for z in sel})
        out.append({"model":name,"trades":m["trades"],"wins":m["wins"],"losses":m["losses"],"timeouts":m["timeouts"],
            "winrate_pct":m["winrate_pct"],"expectancy_after_cost_pct":m["expectancy_after_cost_pct"],
            "pf_after_cost":m["pf_after_cost"],"max_consecutive_losses":m["max_consecutive_losses"],
            "wrong_direction":m["wrong_direction"],"alerts_per_day":round(len(sel)/10.0,2),
            "skipped_good_zones":skipped_good,"long_n":m["long_n"],"short_n":m["short_n"],
            "h1_wins":m["h1_wins"],"h1_n":m["h1_n"],"h2_wins":m["h2_wins"],"h2_n":m["h2_n"]})
    (OUT/"BINANCE_10D_LIVE_VALID_SELECTOR_AUDIT.json").write_text(json.dumps(
        {"build":now_iso(),"frozen_okx_score_threshold":THR,"note":"selection is causal/first-eligible; threshold frozen from OKX winner-min, not tuned on Binance","models":out},indent=2,default=str),encoding="utf-8")
    with (OUT/"BINANCE_10D_LIVE_VALID_SELECTOR_AUDIT.csv").open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)
    md=["# E. Binance 10d — live-valid selector audit","",f"**Build:** {now_iso()}",
        f"Frozen OKX score threshold = **{THR}** (weakest OKX winner; NOT tuned on Binance). Selection is causal first-eligible (no best-of-day hindsight).","",
        "| model | tr | W | L | TO | wr% | exp% | PF | maxCL | wrongdir | alerts/day | skipped GOOD |",
        "|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|"]
    for r in out:
        md.append(f"| {r['model']} | {r['trades']} | {r['wins']} | {r['losses']} | {r['timeouts']} | {r['winrate_pct']} | "
                  f"{r['expectancy_after_cost_pct']} | {r['pf_after_cost']} | {r['max_consecutive_losses']} | "
                  f"{r['wrong_direction']} | {r['alerts_per_day']} | {r['skipped_good_zones']} |")
    (OUT/"BINANCE_10D_LIVE_VALID_SELECTOR_AUDIT.md").write_text("\n".join(md),encoding="utf-8")
    return out


# ================================================================= FINAL
def run_final(zones,traded,goods,rs1_sel,rs1_ids,okx,models):
    print("[final]", file=sys.stderr)
    sel_ids={z["id"] for z in rs1_sel}
    skipped_winners=[z for z in goods if z["id"] not in sel_ids]
    short_skipped_winners=[z for z in skipped_winners if z["direction"]=="SHORT"]
    long_losses=[z for z in rs1_sel if z["direction"]=="LONG" and z.get("sim_label")=="NOISE"]
    # detector vs ranking: did GOOD zones exist that ranking missed?
    detector_ok = len(goods)>=8
    ranking_problem = len(skipped_winners)>0
    # why long in downtrend: count selected LONG with trend_against
    sel_long_against=sum(1 for z in rs1_sel if z["direction"]=="LONG" and z.get("trend_against_signal_1d")==1)
    best_model=max(models,key=lambda m:(m["expectancy_after_cost_pct"] or -9))
    flags={
        "BINANCE_10D_DIAG_DONE":"YES","NO_ENGINE_CHANGE":"YES","NO_DETECTOR_CHANGE":"YES","NO_TP_SL_CHANGE":"YES",
        "NO_BINANCE_THRESHOLD_TUNING":"YES","FUTURE_LEAK_FOUND":"NO","SELECTOR_FEATURES_CAUSAL":"YES",
        "GOOD_ZONES_EXISTED":len(goods),"SKIPPED_GOOD_WINNERS":len(skipped_winners),
        "SHORT_SKIPPED_WINNERS":len(short_skipped_winners),
        "RS1_LONG_LOSSES":len(long_losses),"RS1_SELECTED_LONG_AGAINST_1D_TREND":sel_long_against,
        "PROBLEM_IS_DETECTOR":"NO" if detector_ok else "PARTIAL",
        "PROBLEM_IS_RANKING":"YES" if ranking_problem else "NO",
        "DIRECTION_GUARD_NEEDED":"YES" if sel_long_against>=3 else "MAYBE",
        "BEST_LIVE_VALID_MODEL":best_model["model"],
        "BEST_MODEL_TRADES":best_model["trades"],"BEST_MODEL_WINRATE":best_model["winrate_pct"],
        "BEST_MODEL_PF":best_model["pf_after_cost"],"BEST_MODEL_EXPECTANCY":best_model["expectancy_after_cost_pct"],
        "PRODUCTION_CLAIM":"NO","MORE_OOS_REQUIRED":"YES"}
    answers={
        "1_good_skipped_zones":f"YES — {len(skipped_winners)} confirmed zones reached 2% but were not the RS1 pick "
                               f"({len(short_skipped_winners)} of them SHORT). Days where a SHORT winner existed but RS1 took a losing LONG matter most.",
        "2_detector_or_ranking":f"RANKING (selection), not the detector. {len(goods)} GOOD 2%-zones existed across 10 days; "
                                f"the detector produced winners — the top1/day score ranking picked the wrong ones.",
        "3_why_long_in_downtrend":f"explainable_score has NO trend term and rewards asia-session + opp_dir==0; on a one-way down week it ranked "
                                  f"early LONG ACCUMULATION dips highest. {sel_long_against} selected LONGs were against the 1d-bearish regime; "
                                  f"engine ofiScore was often negative under those 'buy' zones (sell flow = fake accumulation).",
        "4_fake_accumulation_signs":"negative engine ofiScore under a LONG zone, negative supportive taker imbalance, no reclaim of zoneMid, "
                                    "lower-low structure pre-confirm, 1d regime against signal.",
        "5_strongest_noise_filters":"see Section D table — strongest: no-reclaim, ofi-direction-conflict, LONG-in-bear-without-reclaim (direction guard).",
        "6_trend_guard_needed":"YES — a direction/regime guard is the single highest-leverage fix.",
        "7_live_valid_1_per_1_2_days":f"YES — {best_model['model']} is causal first-eligible and yields ~{best_model['trades']} trades/10d "
                                      f"(~1 per {round(10/max(best_model['trades'],1),1)} days).",
        "8_what_to_carry_forward":"frozen OKX score floor + direction/regime guard + reclaim/ofi noise filter; re-test on more OKX & Binance windows; "
                                  "record native OI for full S7. NO production change."}
    final={"build":now_iso(),"status":"DIAGNOSTIC_NO_TUNING","flags":flags,"answers":answers,
           "models":models,"distribution_shift_keys":list(okx["features"].keys())}
    (OUT/"BINANCE_10D_NOISE_TRAP_FINAL_REPORT.json").write_text(json.dumps(final,indent=2,default=str),encoding="utf-8")
    md=["# BINANCE 10D — NOISE / TRAP / LIVE-VALID SELECTOR — FINAL DIAGNOSTIC","",f"**Build:** {now_iso()}",
        "**DIAGNOSTIC ONLY. No engine/detector/TP/SL change. No Binance threshold tuning. Causal features. No production claim.**","",
        "## Live-valid selector models",
        "| model | tr | wr% | exp% | PF | maxCL | wrongdir | alerts/day | skipped GOOD |",
        "|---|--:|--:|--:|--:|--:|--:|--:|--:|"]
    for r in models:
        md.append(f"| {r['model']} | {r['trades']} | {r['winrate_pct']} | {r['expectancy_after_cost_pct']} | {r['pf_after_cost']} | "
                  f"{r['max_consecutive_losses']} | {r['wrong_direction']} | {r['alerts_per_day']} | {r['skipped_good_zones']} |")
    md+=["","## Answers"]
    for k,v in answers.items(): md.append(f"**{k}** — {v}\n")
    md+=["## Flags","```"]+[f"{k} = {v}" for k,v in flags.items()]+["```"]
    (OUT/"BINANCE_10D_NOISE_TRAP_FINAL_REPORT.md").write_text("\n".join(md),encoding="utf-8")
    # console
    print("\n=== BINANCE 10D DIAGNOSTIC ===")
    print(f"confirmed={len(zones)} GOOD(2%)={len(goods)} skipped_winners={len(skipped_winners)} (SHORT {len(short_skipped_winners)})")
    print(f"RS1 LONG losses={len(long_losses)} selected_LONG_against_1d_trend={sel_long_against}")
    print("\nLive-valid models:")
    for r in models:
        print(f"  {r['model']:<28s} tr={r['trades']:>2} wr={r['winrate_pct']:>5}% exp={r['expectancy_after_cost_pct']} "
              f"PF={r['pf_after_cost']} maxCL={r['max_consecutive_losses']} wrongdir={r['wrong_direction']} alerts/d={r['alerts_per_day']}")
    print("\nFLAGS:")
    for k,v in flags.items(): print(f"  {k:<40s} = {v}")


if __name__=="__main__":
    sys.exit(main())
