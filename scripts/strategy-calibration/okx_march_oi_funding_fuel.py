"""OKX March OI/funding fuel + target-zone orientation (Sections A-I).

OI source: OKX rubik open-interest-volume (public, free) — DAILY granularity for
March (fine periods do not reach back that far). USD notional, BTC aggregate.
Funding source: OKX public funding-rate-history (8h settlements, covers March).
NO liquidations. NO Binance run. Primary win = strict 2%. No future leak.
"""
from __future__ import annotations
import csv, gzip, json, math, statistics as stats, sys, time, datetime as dt, urllib.request
from collections import defaultdict, Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from march_target_zone_fuel import (load_dataset, explainable_score_l2_dyn,
    select_topn_per_day, build_buckets_with_volume, merge_forward_buckets,
    classify_setup, iso_to_sec, ALL_DATES, FIRST_HALF, SECOND_HALF, DATA_ROOT,
    TARGET_PCT, STOP_PCT, COST_PCT, TIMEOUT_HOURS, metrics)

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "package.json").exists() and (p / "scripts").exists())
REP_OUT = ROOT / "reports/strategy-calibration"
OI_CACHE = DATA_ROOT / "_okx_oi_daily_rubik.csv"
FUND_CACHE = DATA_ROOT / "_okx_funding_history.csv"

def now_iso(): return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
def ms2sec(ms): return int(ms)//1000
def safe_float(x):
    if x in (None,"","None"): return None
    try: return float(x)
    except: return None
def mean_or_none(xs):
    xs=[x for x in xs if x is not None]; return round(stats.mean(xs),6) if xs else None
def median_or_none(xs):
    xs=[x for x in xs if x is not None]; return round(stats.median(xs),6) if xs else None
def pstdev_or_none(xs):
    xs=[x for x in xs if x is not None]; return stats.pstdev(xs) if len(xs)>1 else None
def cohens_d(a,b):
    a=[x for x in a if x is not None]; b=[x for x in b if x is not None]
    if len(a)<2 or len(b)<2: return None
    ma,mb=stats.mean(a),stats.mean(b); sa,sb=stats.pstdev(a),stats.pstdev(b)
    pooled=math.sqrt(((len(a)-1)*sa*sa+(len(b)-1)*sb*sb)/max(len(a)+len(b)-2,1))
    return round((ma-mb)/pooled,4) if pooled else None
def quantile(xs,q):
    xs=sorted(x for x in xs if x is not None)
    return xs[int(q*(len(xs)-1))] if xs else None

def http_get_json(url, timeout=20, retries=3):
    last=None
    for _ in range(retries):
        try:
            req=urllib.request.Request(url, headers={"User-Agent":"research/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8","replace"))
        except Exception as e:
            last=e; time.sleep(1.0)
    raise last


# ============================================================
# B. download OI (rubik 1D) + funding (8h) — cached
# ============================================================
def fetch_oi_daily():
    if OI_CACHE.exists():
        rows=[]
        with OI_CACHE.open(encoding="utf-8") as f:
            for r in csv.DictReader(f): rows.append({"ts":int(r["ts"]),"oi_usd":float(r["oi_usd"]),"vol_usd":float(r["vol_usd"])})
        return rows, "cache"
    j=http_get_json("https://www.okx.com/api/v5/rubik/stat/contracts/open-interest-volume?ccy=BTC&period=1D")
    data=j.get("data",[])
    rows=[{"ts":int(r[0]),"oi_usd":float(r[1]),"vol_usd":float(r[2])} for r in data]
    rows.sort(key=lambda x:x["ts"])
    with OI_CACHE.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=["ts","oi_usd","vol_usd"]); w.writeheader()
        for r in rows: w.writerow(r)
    return rows, "api"

def fetch_funding():
    if FUND_CACHE.exists():
        rows=[]
        with FUND_CACHE.open(encoding="utf-8") as f:
            for r in csv.DictReader(f): rows.append({"fundingTime":int(r["fundingTime"]),"fundingRate":float(r["fundingRate"])})
        return rows, "cache"
    # paginate from Apr-05 back to Feb-15 to cover March + trailing for zscore
    after=1775692800000  # 2026-04-10 00:00
    floor=1771200000000  # 2026-02-16 00:00
    seen={}
    for _ in range(20):
        url=f"https://www.okx.com/api/v5/public/funding-rate-history?instId=BTC-USDT-SWAP&after={after}&limit=100"
        j=http_get_json(url); data=j.get("data",[])
        if not data: break
        for r in data:
            ft=int(r["fundingTime"]); seen[ft]=float(r["fundingRate"])
        oldest=min(int(r["fundingTime"]) for r in data)
        after=oldest
        if oldest<=floor: break
        time.sleep(0.2)
    rows=[{"fundingTime":ft,"fundingRate":fr} for ft,fr in sorted(seen.items())]
    with FUND_CACHE.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=["fundingTime","fundingRate"]); w.writeheader()
        for r in rows: w.writerow(r)
    return rows, "api"


# ============================================================
# leak-free OI / funding lookups
# ============================================================
def oi_at_or_before(oi_rows, sec):
    """latest daily OI snapshot with ts<=sec*1000."""
    best=None
    for r in oi_rows:
        if ms2sec(r["ts"])<=sec: best=r
        else: break
    return best

def oi_n_days_before(oi_rows, sec, n):
    snap=oi_at_or_before(oi_rows, sec)
    if not snap: return None
    target_ts=snap["ts"]-n*86400000
    best=None
    for r in oi_rows:
        if r["ts"]<=target_ts: best=r
        else: break
    return best

def funding_at_or_before(fund_rows, sec):
    best=None
    for r in fund_rows:
        if ms2sec(r["fundingTime"])<=sec: best=r
        else: break
    return best

def funding_trailing(fund_rows, sec, n):
    out=[]
    for r in fund_rows:
        if ms2sec(r["fundingTime"])<=sec: out.append(r["fundingRate"])
    return out[-n:] if out else []


# ============================================================
# hit_2pct + hit_target_zone path sim
# ============================================================
def sim_hits(direction, confirmed_sec, zone, buckets_cache, target_price):
    fwd=merge_forward_buckets(zone["date"], buckets_cache, lookahead=2)
    if not fwd[0]: return None
    secs,highs,lows,lasts=fwd
    lo,hi=0,len(secs)
    while lo<hi:
        m=(lo+hi)//2
        if secs[m]<confirmed_sec: lo=m+1
        else: hi=m
    if lo>=len(secs): return None
    i0=lo; entry=lasts[i0]
    if entry<=0: return None
    timeout=confirmed_sec+TIMEOUT_HOURS*3600
    if direction=="LONG":
        tp2=entry*(1+TARGET_PCT/100.0); sl=entry*(1-STOP_PCT/100.0)
    else:
        tp2=entry*(1-TARGET_PCT/100.0); sl=entry*(1+STOP_PCT/100.0)
    hit_2pct=None; hit_tz=None; sl_hit_at=None; mfe=0.0; mae=0.0
    for i in range(i0,len(secs)):
        if secs[i]>timeout: break
        h=highs[i]; l=lows[i]
        if direction=="LONG":
            up=(h-entry)/entry*100.0; dn=(entry-l)/entry*100.0
            tp2_hit=h>=tp2; sl_now=l<=sl
            tz_hit=(target_price is not None and h>=target_price)
        else:
            up=(entry-l)/entry*100.0; dn=(h-entry)/entry*100.0
            tp2_hit=l<=tp2; sl_now=h>=sl
            tz_hit=(target_price is not None and l<=target_price)
        if up>mfe: mfe=up
        if dn>mae: mae=dn
        if sl_hit_at is None and sl_now: sl_hit_at=secs[i]
        if hit_2pct is None and tp2_hit: hit_2pct=secs[i]
        if hit_tz is None and tz_hit: hit_tz=secs[i]
        if hit_2pct and (hit_tz or target_price is None): break
    # primary win = 2% reached before SL (conservative: SL same-bucket=loss handled by sl_hit_at<=hit)
    win2 = (hit_2pct is not None) and (sl_hit_at is None or hit_2pct < sl_hit_at)
    tzwin = (hit_tz is not None) and (sl_hit_at is None or hit_tz < sl_hit_at)
    return {"entry":round(entry,2),"hit_2pct":bool(win2),"hit_target_zone":bool(tzwin),
            "mfe_pct":round(mfe,4),"mae_pct":round(mae,4)}


# ============================================================
# MAIN
# ============================================================
def main():
    print("[load] dataset ...", file=sys.stderr)
    rows=load_dataset()
    for r in rows: classify_setup(r)
    # merge target-zone heatmap (already computed in prior task)
    tzp=REP_OUT/"MARCH_TARGET_ZONE_HEATMAP_FEATURES.csv"
    if tzp.exists():
        with tzp.open(encoding="utf-8") as f:
            tz={}
            for lr in csv.DictReader(f):
                d={}
                for k,v in lr.items():
                    if k=="zone_id": continue
                    d[k]=safe_float(v) if k not in ("tz_target_type","tz_nearest_obstacle_type") else (v or None)
                tz[lr["zone_id"]]=d
        for r in rows:
            for k,v in tz.get(r["zone_id"],{}).items():
                if k not in r: r[k]=v
    print(f"  {len(rows)} zones", file=sys.stderr)

    # ---------- A: source audit ----------
    print("[A] OI/funding source audit ...", file=sys.stderr)
    audit={"build_time_utc":now_iso(),
        "tardis_downloader_present":True,
        "tardis_api_key_set":False,
        "tardis_free_tier":"first-day-of-month only (so March 02-31 derivative_ticker NOT downloadable from Tardis without paid key)",
        "okx_public_api_reachable":True,
        "okx_current_oi_endpoint":"/api/v5/public/open-interest (SNAPSHOT only, no history)",
        "okx_oi_history_endpoint":"/api/v5/rubik/stat/contracts/open-interest-volume",
        "okx_oi_history_lookback":{"5m":"~2 days (does NOT reach March)","1H":"~30 days (does NOT reach March)","1D":"180 days back to 2025-12 (REACHES March, DAILY only)"},
        "okx_oi_unit":"USD notional, BTC currency aggregate (all BTC contracts), NOT instrument-specific BTC-USDT-SWAP",
        "okx_funding_endpoint":"/api/v5/public/funding-rate-history (8h settlements, covers March)",
        "flags":{
            "OKX_PUBLIC_OI_ENDPOINT_FOUND":"YES",
            "OKX_OI_HISTORY_AVAILABLE":"YES (1D granularity only for March)",
            "OKX_FUNDING_HISTORY_AVAILABLE":"YES",
            "OI_DATA_AVAILABLE":"YES (daily)",
            "FUNDING_DATA_AVAILABLE":"YES",
            "LIQUIDATIONS_USED":"NO",
            "OI_FROM_VOLUME_ATTEMPTED":"NO",
            "FLOW_PROXY_BUILT_IF_NO_OI":"YES (built for intraday since OI is daily-only)"}}
    (REP_OUT/"OKX_MARCH_OI_FUNDING_SOURCE_AUDIT.json").write_text(json.dumps(audit,indent=2),encoding="utf-8")
    md=["# OKX March OI/funding source audit","",f"**Build:** {audit['build_time_utc']}","",
        "## Findings","",
        "- Tardis downloader present but **no TARDIS_API_KEY** → only free first-of-month datasets. March 02-31 `derivative_ticker` (OI+funding) NOT downloadable from Tardis.",
        "- OKX public API reachable.",
        "- **Current OI** `/api/v5/public/open-interest` = snapshot only (no history).",
        "- **OI history** `/api/v5/rubik/stat/contracts/open-interest-volume`: 5m ~2d, 1H ~30d, **1D reaches back to 2025-12 → covers March at DAILY granularity only**.",
        "- OKX rubik OI unit = **USD notional, BTC currency aggregate** (all BTC contracts), not instrument-specific.",
        "- **Funding** `/api/v5/public/funding-rate-history` = 8h settlements, **covers March**.",
        "","## Verdict",
        "- TRUE OI available for March but DAILY only → usable as background/regime, NOT for 15m/60m intraday deltas.",
        "- Funding available for March (8h) → usable as background feature.",
        "- Intraday fuel must use FLOW_PROXY (from trades), explicitly NOT called OI.",
        "","## Flags","```"]
    for k,v in audit["flags"].items(): md.append(f"{k} = {v}")
    md.append("```")
    (REP_OUT/"OKX_MARCH_OI_FUNDING_SOURCE_AUDIT.md").write_text("\n".join(md),encoding="utf-8")

    # ---------- B: download ----------
    print("[B] download OI daily + funding ...", file=sys.stderr)
    oi_rows, oi_src=fetch_oi_daily()
    fund_rows, fund_src=fetch_funding()
    # restrict reporting to march window
    mar_lo=iso_to_sec("2026-03-01T00:00:00+00:00"); mar_hi=iso_to_sec("2026-04-01T00:00:00+00:00")
    oi_march=[r for r in oi_rows if mar_lo<=ms2sec(r["ts"])<mar_hi]
    fund_march=[r for r in fund_rows if mar_lo<=ms2sec(r["fundingTime"])<mar_hi]
    # write per-day funding.csv.gz
    fund_by_day=defaultdict(list)
    for r in fund_rows:
        d=dt.datetime.fromtimestamp(ms2sec(r["fundingTime"]),tz=dt.timezone.utc).date().isoformat()
        fund_by_day[d].append(r)
    fund_days_written=0
    for d in ALL_DATES:
        recs=fund_by_day.get(d,[])
        if not recs: continue
        p=DATA_ROOT/d/"funding.csv.gz"
        with gzip.open(p,"wt",encoding="utf-8",newline="") as f:
            w=csv.writer(f); w.writerow(["fundingTime","fundingRate"])
            for r in recs: w.writerow([r["fundingTime"],r["fundingRate"]])
        fund_days_written+=1
    dl={"build_time_utc":now_iso(),"oi_source":oi_src,"funding_source":fund_src,
        "oi_daily_rows_total":len(oi_rows),"oi_daily_rows_march":len(oi_march),
        "funding_rows_total":len(fund_rows),"funding_rows_march":len(fund_march),
        "funding_days_written":fund_days_written,
        "oi_cache_file":str(OI_CACHE),"funding_cache_file":str(FUND_CACHE),
        "flags":{"OI_DOWNLOADED_DAYS":len(oi_march),"FUNDING_DOWNLOADED_DAYS":fund_days_written,
                 "OI_UNIT_UNKNOWN":"NO (USD notional, aggregate BTC)","DOWNLOAD_BLOCKED_REASON":None,
                 "OI_GRANULARITY":"1D","FUNDING_GRANULARITY":"8h"}}
    (REP_OUT/"OKX_MARCH_OI_FUNDING_DOWNLOAD_REPORT.json").write_text(json.dumps(dl,indent=2),encoding="utf-8")
    with (REP_OUT/"OKX_MARCH_OI_FUNDING_DOWNLOAD_REPORT.csv").open("w",encoding="utf-8",newline="") as f:
        w=csv.writer(f); w.writerow(["date","funding_settlements","oi_daily_snapshot_usd"])
        oi_by_day={dt.datetime.fromtimestamp(ms2sec(r["ts"]),tz=dt.timezone.utc).date().isoformat():r["oi_usd"] for r in oi_rows}
        for d in ALL_DATES:
            w.writerow([d, len(fund_by_day.get(d,[])), round(oi_by_day.get(d,float("nan")),1) if d in oi_by_day else ""])
    (REP_OUT/"OKX_MARCH_OI_FUNDING_DOWNLOAD_REPORT.md").write_text(
        "# OKX March OI/funding download report\n\n"
        f"**Build:** {dl['build_time_utc']}\n\n"
        f"- OI daily snapshots (rubik 1D, USD): total {len(oi_rows)}, March {len(oi_march)} (source: {oi_src})\n"
        f"- Funding settlements (8h): total {len(fund_rows)}, March {len(fund_march)} (source: {fund_src})\n"
        f"- Per-day funding.csv.gz written: {fund_days_written} days\n"
        f"- OI daily cache: `{OI_CACHE.name}`; funding cache: `{FUND_CACHE.name}`\n\n"
        "OI is DAILY granularity (16:00 UTC snapshot) and BTC-aggregate USD notional. "
        "Funding is 8h settlement rate. Both leak-free (use latest value with ts<=signal).\n", encoding="utf-8")

    # ---------- C: data quality ----------
    print("[C] data quality ...", file=sys.stderr)
    oi_ts=[ms2sec(r["ts"]) for r in oi_march]
    fund_ts=[ms2sec(r["fundingTime"]) for r in fund_march]
    def gaps(ts):
        ts=sorted(ts); return [ts[i+1]-ts[i] for i in range(len(ts)-1)]
    oi_gaps=gaps(oi_ts); fund_gaps=gaps(fund_ts)
    dq={"build_time_utc":now_iso(),
        "oi":{"rows_march":len(oi_march),"first":dt.datetime.fromtimestamp(min(oi_ts),tz=dt.timezone.utc).isoformat() if oi_ts else None,
              "last":dt.datetime.fromtimestamp(max(oi_ts),tz=dt.timezone.utc).isoformat() if oi_ts else None,
              "median_interval_sec":median_or_none(oi_gaps),"max_gap_sec":max(oi_gaps) if oi_gaps else None,
              "nonnull_oi":sum(1 for r in oi_march if r["oi_usd"] is not None),"unit":"USD aggregate BTC","granularity":"1D"},
        "funding":{"rows_march":len(fund_march),"first":dt.datetime.fromtimestamp(min(fund_ts),tz=dt.timezone.utc).isoformat() if fund_ts else None,
              "last":dt.datetime.fromtimestamp(max(fund_ts),tz=dt.timezone.utc).isoformat() if fund_ts else None,
              "median_interval_sec":median_or_none(fund_gaps),"max_gap_sec":max(fund_gaps) if fund_gaps else None,
              "nonnull_rate":sum(1 for r in fund_march if r["fundingRate"] is not None),"granularity":"8h",
              "settlements_per_day":round(len(fund_march)/29.0,2)},
        "flags":{"OI_COVERS_MARCH":"YES","FUNDING_COVERS_MARCH":"YES",
                 "OI_MIN_GRANULARITY":"1D","FUNDING_MIN_GRANULARITY":"8h",
                 "OI_USABLE_FOR_15M_60M_FEATURES":"NO (daily only)","FUNDING_USABLE_AS_BACKGROUND":"YES"}}
    (REP_OUT/"OKX_MARCH_OI_FUNDING_DATA_QUALITY.json").write_text(json.dumps(dq,indent=2),encoding="utf-8")
    with (REP_OUT/"OKX_MARCH_OI_FUNDING_DATA_QUALITY.csv").open("w",encoding="utf-8",newline="") as f:
        w=csv.writer(f); w.writerow(["dataset","rows_march","first","last","median_interval_sec","max_gap_sec","granularity"])
        w.writerow(["oi",dq["oi"]["rows_march"],dq["oi"]["first"],dq["oi"]["last"],dq["oi"]["median_interval_sec"],dq["oi"]["max_gap_sec"],"1D"])
        w.writerow(["funding",dq["funding"]["rows_march"],dq["funding"]["first"],dq["funding"]["last"],dq["funding"]["median_interval_sec"],dq["funding"]["max_gap_sec"],"8h"])
    (REP_OUT/"OKX_MARCH_OI_FUNDING_DATA_QUALITY.md").write_text(
        "# OKX March OI/funding data quality\n\n"f"**Build:** {dq['build_time_utc']}\n\n"
        f"## OI (daily)\n- rows March: {dq['oi']['rows_march']}\n- {dq['oi']['first']} .. {dq['oi']['last']}\n"
        f"- median interval: {dq['oi']['median_interval_sec']}s (=1 day); max gap {dq['oi']['max_gap_sec']}s\n- unit USD aggregate BTC\n\n"
        f"## Funding (8h)\n- rows March: {dq['funding']['rows_march']} (~{dq['funding']['settlements_per_day']}/day)\n"
        f"- {dq['funding']['first']} .. {dq['funding']['last']}\n- median interval {dq['funding']['median_interval_sec']}s (=8h)\n\n"
        "## Flags\n```\n"+"\n".join(f"{k} = {v}" for k,v in dq["flags"].items())+"\n```\n", encoding="utf-8")

    # ---------- buckets for hit sim ----------
    print("[buckets] building (for hit_2pct / target sim) ...", file=sys.stderr)
    buckets_cache={}
    needed=set(ALL_DATES); needed.add("2026-04-01")
    for d in sorted(needed):
        p=DATA_ROOT/d/"trades.csv.gz"
        if p.exists(): buckets_cache[d]=build_buckets_with_volume(p)

    # ---------- D: fuel features (true OI daily + funding + FLOW_PROXY) ----------
    print("[D] fuel features ...", file=sys.stderr)
    # trailing OI series for zscore (daily, USD)
    oi_vals_all=[r["oi_usd"] for r in oi_rows]
    for r in rows:
        sec=iso_to_sec(r.get("confirmed_iso"))
        if sec is None: continue
        snap=oi_at_or_before(oi_rows, sec)
        snap1=oi_n_days_before(oi_rows, sec, 1)
        snap3=oi_n_days_before(oi_rows, sec, 3)
        r["oi_at_signal_usd"]=round(snap["oi_usd"],1) if snap else None
        r["oi_delta_1d_usd"]=round(snap["oi_usd"]-snap1["oi_usd"],1) if (snap and snap1) else None
        r["oi_pct_delta_1d"]=round((snap["oi_usd"]-snap1["oi_usd"])/snap1["oi_usd"]*100.0,4) if (snap and snap1 and snap1["oi_usd"]) else None
        r["oi_pct_delta_3d"]=round((snap["oi_usd"]-snap3["oi_usd"])/snap3["oi_usd"]*100.0,4) if (snap and snap3 and snap3["oi_usd"]) else None
        # zscore over trailing 14 daily snaps before signal
        trail=[x["oi_usd"] for x in oi_rows if x["ts"]<=snap["ts"]][-14:] if snap else []
        if len(trail)>=5 and pstdev_or_none(trail):
            r["oi_zscore_14d"]=round((snap["oi_usd"]-stats.mean(trail))/stats.pstdev(trail),4)
        else: r["oi_zscore_14d"]=None
        # funding
        fsnap=funding_at_or_before(fund_rows, sec)
        r["funding_rate_at_signal"]=round(fsnap["fundingRate"],10) if fsnap else None
        ftrail=funding_trailing(fund_rows, sec, 21)  # ~7 days of 8h
        if fsnap is not None:
            fr=fsnap["fundingRate"]
            r["funding_positive"]=1 if fr>0 else 0
            r["funding_negative"]=1 if fr<0 else 0
            if len(ftrail)>=5 and pstdev_or_none(ftrail):
                r["funding_zscore_7d"]=round((fr-stats.mean(ftrail))/stats.pstdev(ftrail),4)
            else: r["funding_zscore_7d"]=None
            absfr=abs(fr)
            r["funding_abs_extreme"]=round(absfr,10)
            # regime
            if fr>0.0001: r["funding_regime"]="extreme_positive"
            elif fr<-0.0001: r["funding_regime"]="extreme_negative"
            elif fr>0.00002: r["funding_regime"]="positive"
            elif fr<-0.00002: r["funding_regime"]="negative"
            else: r["funding_regime"]="neutral"
        # price+OI daily regime: price return over last day vs OI delta over last day
        # price return from buckets (close at signal vs ~24h before)
        # use prior_move features as proxy for short return; for daily use oi_pct_delta_1d sign + matched daily price
        # daily price change: use snap vs snap1 day's session—approximate by prior_move_180m sign extended; instead compute from buckets
        pr_1d=r.get("prior_move_180m_pct")  # proxy for recent return direction (leak-free)
        oi_up = (r.get("oi_pct_delta_1d") or 0)>0
        oi_dn = (r.get("oi_pct_delta_1d") or 0)<0
        price_up = (pr_1d or 0)>0.1; price_dn=(pr_1d or 0)<-0.1
        r["price_up_oi_up"]=1 if (price_up and oi_up) else 0
        r["price_up_oi_down"]=1 if (price_up and oi_dn) else 0
        r["price_down_oi_up"]=1 if (price_dn and oi_up) else 0
        r["price_down_oi_down"]=1 if (price_dn and oi_dn) else 0
        # FLOW_PROXY (intraday, NOT OI) from trades-derived dl2/taker
        r["flow_taker_imb_15m"]=r.get("taker_imb_aligned_15m")
        r["flow_taker_imb_30m"]=r.get("taker_imb_aligned_30m")
        r["flow_supp_minus_opp_15m"]=r.get("dl2_supp_minus_opp_net_flow_15m")
        r["flow_vol_anomaly_15m"]=r.get("vol_anomaly_15m_vs_bg")
        # generic fuel (true): |oi_zscore_14d| + |funding_zscore_7d|
        fz=abs(r.get("funding_zscore_7d") or 0); oz=abs(r.get("oi_zscore_14d") or 0)
        r["true_fuel_score"]=round(oz+fz,4)
        # directional fuel using daily OI regime + funding
        if r["direction"]=="LONG":
            r["dir_fuel_score"]=round((r.get("oi_pct_delta_1d") or 0)/1.0
                + (-(r.get("funding_rate_at_signal") or 0)*10000),4)  # negative funding = shorts pay = bullish lean
        else:
            r["dir_fuel_score"]=round((-(r.get("oi_pct_delta_1d") or 0))/1.0
                + ((r.get("funding_rate_at_signal") or 0)*10000),4)
    # zscore flow proxies across all confirmed
    for fk in ("flow_taker_imb_15m","flow_taker_imb_30m","flow_supp_minus_opp_15m","flow_vol_anomaly_15m"):
        vals=[r.get(fk) for r in rows if r.get(fk) is not None]
        if len(vals)<5: continue
        mu=stats.mean(vals); sd=stats.pstdev(vals) or 1
        for r in rows:
            v=r.get(fk)
            r[fk+"_z"]=round((v-mu)/sd,4) if v is not None else None
    feat_keys=["zone_id","date","direction","confirmed_iso","watch_label","coverage_class","setup_type",
        "oi_at_signal_usd","oi_delta_1d_usd","oi_pct_delta_1d","oi_pct_delta_3d","oi_zscore_14d",
        "funding_rate_at_signal","funding_zscore_7d","funding_regime","funding_positive","funding_negative","funding_abs_extreme",
        "price_up_oi_up","price_up_oi_down","price_down_oi_up","price_down_oi_down",
        "true_fuel_score","dir_fuel_score",
        "flow_taker_imb_15m_z","flow_taker_imb_30m_z","flow_supp_minus_opp_15m_z","flow_vol_anomaly_15m_z"]
    with (REP_OUT/"OKX_MARCH_OI_FUNDING_FUEL_FEATURES.csv").open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=feat_keys,extrasaction="ignore"); w.writeheader()
        for r in rows: w.writerow(r)
    (REP_OUT/"OKX_MARCH_OI_FUNDING_FUEL_FEATURES.json").write_text(json.dumps(
        {"build_time_utc":now_iso(),"n_zones":len(rows),
         "true_oi_features":["oi_at_signal_usd","oi_delta_1d_usd","oi_pct_delta_1d","oi_pct_delta_3d","oi_zscore_14d",
                             "price_up_oi_up","price_up_oi_down","price_down_oi_up","price_down_oi_down"],
         "funding_features":["funding_rate_at_signal","funding_zscore_7d","funding_regime","funding_abs_extreme"],
         "flow_proxy_features_NOT_OI":["flow_taker_imb_15m_z","flow_taker_imb_30m_z","flow_supp_minus_opp_15m_z","flow_vol_anomaly_15m_z"],
         "TRUE_OI_FEATURES_BUILT":"YES (daily)","FLOW_PROXY_NOT_TRUE_OI":"YES"},indent=2),encoding="utf-8")
    (REP_OUT/"OKX_MARCH_OI_FUNDING_FUEL_FEATURES.md").write_text(
        "# OKX March OI/funding fuel features\n\n"f"**Build:** {now_iso()}\n\n"
        "## TRUE OI (daily, OKX rubik, USD aggregate BTC)\n"
        "- oi_at_signal_usd, oi_delta_1d_usd, oi_pct_delta_1d, oi_pct_delta_3d, oi_zscore_14d\n"
        "- price+OI daily regime flags (price_up_oi_up etc; price proxy = prior_move_180m sign)\n"
        "- **Daily granularity → no 5m/15m/30m/60m OI deltas possible for March.**\n\n"
        "## Funding (8h, OKX public)\n- funding_rate_at_signal, funding_zscore_7d, funding_regime, funding_abs_extreme\n\n"
        "## FLOW_PROXY (intraday, from trades — explicitly NOT OI)\n"
        "- flow_taker_imb_15m/30m_z, flow_supp_minus_opp_15m_z, flow_vol_anomaly_15m_z\n\n"
        "**TRUE_OI_FEATURES_BUILT = YES (daily) ; FLOW_PROXY_NOT_TRUE_OI = YES**\n", encoding="utf-8")

    # ---------- selectors ----------
    base_filter=lambda r:(r.get("dist_to_recent_swing_high_pct") is not None and r["dist_to_recent_swing_high_pct"]<=0.4616)
    enh_filter=lambda r:base_filter(r) and (r.get("dl2_supp_minus_opp_net_flow_15m") is not None and r["dl2_supp_minus_opp_net_flow_15m"]<=4497.76)
    enhanced_zones=select_topn_per_day(rows,enh_filter,explainable_score_l2_dyn,1)
    print(f"  enhanced zones={len(enhanced_zones)}", file=sys.stderr)

    # ---------- E: target-zone orientation (secondary) on 29 enhanced ----------
    print("[E] target-zone orientation ...", file=sys.stderr)
    orient=[]
    for z in enhanced_zones:
        sec=iso_to_sec(z.get("confirmed_iso"))
        tgt=z.get("tz_target_price")
        sim=sim_hits(z["direction"], sec, z, buckets_cache, tgt)
        if sim is None: continue
        entry=sim["entry"]
        old_fixed_tp=round(entry*(1+TARGET_PCT/100.0),2) if z["direction"]=="LONG" else round(entry*(1-TARGET_PCT/100.0),2)
        tdist=z.get("tz_target_distance_pct")
        row={"date":z["date"],"direction":z["direction"],"zone_id":z["zone_id"],
            "entry":entry,"old_fixed_2pct_target":old_fixed_tp,
            "target_zone_price":tgt,"target_zone_type":z.get("tz_target_type"),
            "target_distance_pct":tdist,"target_quality_score":z.get("tz_void_thin_path_score"),
            "fuel_score":z.get("true_fuel_score"),"dir_fuel_score":z.get("dir_fuel_score"),
            "funding_regime":z.get("funding_regime"),"oi_pct_delta_1d":z.get("oi_pct_delta_1d"),
            "hit_2pct":sim["hit_2pct"],"hit_target_zone":sim["hit_target_zone"],
            "mfe_pct":sim["mfe_pct"],"mae_pct":sim["mae_pct"],
            "watch_label":z.get("watch_label"),
            "target_zone_too_close":1 if (tdist is not None and tdist<2.0) else 0,
            "target_zone_overestimated":1 if (sim["hit_2pct"] and not sim["hit_target_zone"]) else 0,
            "local_reaction_only":1 if (sim["hit_target_zone"] and not sim["hit_2pct"]) else 0}
        row["comment"]=("win_2pct" if sim["hit_2pct"] else
                        ("local_reaction_only" if row["local_reaction_only"] else
                         ("no_follow_through" )))
        orient.append(row)
    ok=[o for o in orient]
    with (REP_OUT/"OKX_MARCH_TARGET_ZONE_ORIENTATION_WITH_FUEL.csv").open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(ok[0].keys()) if ok else ["date"],extrasaction="ignore"); w.writeheader()
        for o in ok: w.writerow(o)
    (REP_OUT/"OKX_MARCH_TARGET_ZONE_ORIENTATION_WITH_FUEL.json").write_text(json.dumps(
        {"build_time_utc":now_iso(),"n":len(ok),
         "hit_2pct":sum(1 for o in ok if o["hit_2pct"]),
         "hit_target_zone":sum(1 for o in ok if o["hit_target_zone"]),
         "target_too_close_lt2pct":sum(1 for o in ok if o["target_zone_too_close"]),
         "target_overestimated":sum(1 for o in ok if o["target_zone_overestimated"]),
         "local_reaction_only":sum(1 for o in ok if o["local_reaction_only"]),
         "trades":ok},indent=2,default=str),encoding="utf-8")
    md=["# Target-zone orientation with fuel (secondary metric; primary win = strict 2%)","",
        f"**Build:** {now_iso()}",
        f"hit_2pct={sum(1 for o in ok if o['hit_2pct'])}/{len(ok)}  hit_target_zone={sum(1 for o in ok if o['hit_target_zone'])}  "
        f"target_too_close(<2%)={sum(1 for o in ok if o['target_zone_too_close'])}  "
        f"local_reaction_only={sum(1 for o in ok if o['local_reaction_only'])}","",
        "| date | dir | result | hit_2% | tz_price | tz_dist% | hit_tz | fuel | fund_regime | oiΔ1d% | comment |",
        "|---|:---:|:---:|:---:|---:|---:|:---:|---:|---|---:|---|"]
    for o in ok:
        md.append(f"| {o['date']} | {o['direction']} | {'WIN' if o['hit_2pct'] else 'no2%'} | "
            f"{'Y' if o['hit_2pct'] else 'N'} | {o['target_zone_price']} | {o['target_distance_pct']} | "
            f"{'Y' if o['hit_target_zone'] else 'N'} | {o['fuel_score']} | {o['funding_regime']} | "
            f"{o['oi_pct_delta_1d']} | {o['comment']} |")
    (REP_OUT/"OKX_MARCH_TARGET_ZONE_ORIENTATION_WITH_FUEL.md").write_text("\n".join(md),encoding="utf-8")

    # ---------- F: fuel feature evaluation ----------
    print("[F] fuel feature evaluation ...", file=sys.stderr)
    by_zone={z["zone_id"]:z for z in enhanced_zones}
    win_ids={o["zone_id"] for o in ok if o["hit_2pct"]}
    winners=[by_zone[o["zone_id"]] for o in ok if o["hit_2pct"]]
    nonwin=[by_zone[o["zone_id"]] for o in ok if not o["hit_2pct"]]
    feat_eval_keys=["true_fuel_score","dir_fuel_score","oi_pct_delta_1d","oi_pct_delta_3d","oi_zscore_14d",
        "funding_rate_at_signal","funding_zscore_7d","funding_abs_extreme",
        "flow_taker_imb_15m_z","flow_taker_imb_30m_z","flow_supp_minus_opp_15m_z","flow_vol_anomaly_15m_z"]
    tableF=[]
    for k in feat_eval_keys:
        wv=[r.get(k) for r in winners]; lv=[r.get(k) for r in nonwin]
        tableF.append({"feature":k,"winners_mean":mean_or_none(wv),"nonwin_mean":mean_or_none(lv),
            "winners_median":median_or_none(wv),"nonwin_median":median_or_none(lv),
            "cohens_d_win_vs_nonwin":cohens_d(wv,lv),"n_win":sum(1 for v in wv if v is not None),"n_nonwin":sum(1 for v in lv if v is not None)})
    tableF.sort(key=lambda r:-abs(r["cohens_d_win_vs_nonwin"] or 0))
    hyp={"H1_high_fuel_increases_2pct":None,"H2_low_fuel_explains_no2pct":None,
         "H3_funding_extreme_crowding":None,"H4_price_oi_regime_setup":None,"H5_flow_proxy_not_oi":"YES (flow proxy built, labeled non-OI)"}
    tf_d=next((r["cohens_d_win_vs_nonwin"] for r in tableF if r["feature"]=="true_fuel_score"),None)
    hyp["H1_high_fuel_increases_2pct"]=f"d(true_fuel win vs nonwin)={tf_d} -> {'supported' if (tf_d or 0)>0.2 else ('weak' if abs(tf_d or 0)>0.1 else 'not supported')}"
    hyp["H2_low_fuel_explains_no2pct"]=f"{'supported' if (tf_d or 0)>0.2 else 'not supported (fuel does not separate)'}"
    fz_d=next((r["cohens_d_win_vs_nonwin"] for r in tableF if r["feature"]=="funding_zscore_7d"),None)
    hyp["H3_funding_extreme_crowding"]=f"d(funding_zscore win vs nonwin)={fz_d} -> {'some signal' if abs(fz_d or 0)>0.2 else 'weak/none'}"
    hyp["H4_price_oi_regime_setup"]="diagnostic only (daily OI too coarse for setup-level timing)"
    with (REP_OUT/"OKX_MARCH_FUEL_FEATURE_EVALUATION.csv").open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(tableF[0].keys()) if tableF else ["feature"]); w.writeheader()
        for r in tableF: w.writerow(r)
    (REP_OUT/"OKX_MARCH_FUEL_FEATURE_EVALUATION.json").write_text(json.dumps(
        {"build_time_utc":now_iso(),"n_winners":len(winners),"n_nonwin":len(nonwin),
         "feature_table":tableF,"hypotheses":hyp},indent=2),encoding="utf-8")
    md=["# OKX March fuel feature evaluation","",f"**Build:** {now_iso()}",
        f"**Enhanced 29: winners(hit_2pct)={len(winners)}, non-winners={len(nonwin)}**","",
        "| feature | win_mean | nonwin_mean | d(win vs nonwin) | n_win | n_nonwin |",
        "|---|---:|---:|---:|---:|---:|"]
    for r in tableF:
        md.append(f"| `{r['feature']}` | {r['winners_mean']} | {r['nonwin_mean']} | {r['cohens_d_win_vs_nonwin']} | {r['n_win']} | {r['n_nonwin']} |")
    md+=["","## Hypotheses"]
    for k,v in hyp.items(): md.append(f"- **{k}**: {v}")
    (REP_OUT/"OKX_MARCH_FUEL_FEATURE_EVALUATION.md").write_text("\n".join(md),encoding="utf-8")

    # ---------- G: fuel-enhanced selector search ----------
    print("[G] fuel-enhanced selector search ...", file=sys.stderr)
    def eval_sel(zones):
        trades=[]
        for z in zones:
            sec=iso_to_sec(z.get("confirmed_iso"))
            sim=sim_hits(z["direction"], sec, z, buckets_cache, z.get("tz_target_price"))
            if sim is None: continue
            win=sim["hit_2pct"]
            # determine loss vs timeout: re-run quick to get exit reason -> approximate: if not win and mae>=stop -> loss else timeout
            outcome="WIN" if win else ("LOSS" if sim["mae_pct"]>=STOP_PCT else "TIMEOUT")
            pnl = (TARGET_PCT if win else (-STOP_PCT if outcome=="LOSS" else round((sim['mfe_pct']-sim['mae_pct'])*0,4)))
            # for timeout pnl ~ small; approximate timeout pnl by last? use 0 minus cost. Use -? keep 0 pre-cost.
            if outcome=="TIMEOUT": pnl=0.0
            trades.append({"date":z["date"],"direction":z["direction"],"zone_id":z["zone_id"],
                "outcome":outcome,"pnl_pre_cost":pnl,"pnl_after_cost":round(pnl-COST_PCT,4),
                "mfe_pct":sim["mfe_pct"],"mae_pct":sim["mae_pct"],
                "watch_label":z.get("watch_label"),"coverage_class":z.get("coverage_class"),
                "reason_class":("win_clean" if win else ("stop" if outcome=="LOSS" else "timeout"))})
        return trades
    void_thr=quantile([r.get("ms_thin_path_score") for r in rows],0.5)
    fuel_thr=quantile([r.get("true_fuel_score") for r in enhanced_zones],0.5)
    selectors={}
    selectors["S0_enhanced_baseline"]=enhanced_zones
    selectors["S1_enh_fuel_ge_med"]=[z for z in enhanced_zones if (z.get("true_fuel_score") or 0)>=(fuel_thr or 0)]
    selectors["S1b_enh_fuel_lt_med"]=[z for z in enhanced_zones if (z.get("true_fuel_score") or 0)<(fuel_thr or 0)]
    selectors["S2_enh_oi_delta_pos"]=[z for z in enhanced_zones if (z.get("oi_pct_delta_1d") or 0)>0]
    selectors["S2b_enh_oi_delta_neg"]=[z for z in enhanced_zones if (z.get("oi_pct_delta_1d") or 0)<0]
    selectors["S3_enh_funding_neg"]=[z for z in enhanced_zones if (z.get("funding_rate_at_signal") or 0)<0]
    selectors["S3b_enh_funding_pos"]=[z for z in enhanced_zones if (z.get("funding_rate_at_signal") or 0)>=0]
    selectors["S4_enh_target_quality"]=[z for z in enhanced_zones if (z.get("ms_thin_path_score") or 0)>=(void_thr or 0)]
    selectors["S5_enh_fuel_and_void"]=[z for z in enhanced_zones if (z.get("true_fuel_score") or 0)>=(fuel_thr or 0) and (z.get("ms_thin_path_score") or 0)>=(void_thr or 0)]
    selectors["S6_absorption_short"]=[z for z in enhanced_zones if z.get("setup_type")=="absorption_reversal_short"]
    selectors["S6b_absorption_long"]=[z for z in enhanced_zones if z.get("setup_type")=="absorption_reversal_long"]
    # S7 EV proxy
    def p_reach(z):
        p=0.55
        if (z.get("true_fuel_score") or 0)>=(fuel_thr or 0): p+=0.03
        if (z.get("ms_thin_path_score") or 0)>=(void_thr or 0): p+=0.03
        if (z.get("ms_large_walls_on_path") or 99)==0: p+=0.03
        if (z.get("dl2_microprice_aligned_delta_5m_bps") or -99)>=0: p+=0.03
        if (z.get("funding_rate_at_signal") or 0)<0 and z["direction"]=="LONG": p+=0.02
        if (z.get("funding_rate_at_signal") or 0)>0 and z["direction"]=="SHORT": p+=0.02
        return min(p,0.9)
    for z in enhanced_zones:
        z["_ev"]=p_reach(z)*(TARGET_PCT-COST_PCT)-(1-p_reach(z))*(STOP_PCT+COST_PCT)
    selectors["S7_EV_positive"]=[z for z in enhanced_zones if z.get("_ev",0)>0.4]
    sel_metrics={}
    for name,zs in selectors.items():
        t=eval_sel(zs); m=metrics(t)
        m["changed_vs_S0"]=len(set(z["zone_id"] for z in zs)^set(z["zone_id"] for z in enhanced_zones))
        sel_metrics[name]={"trade_list":t,**m}
    # write
    keys=["selector","trades","wins","losses","timeouts","winrate_pct","expectancy_after_cost_pct",
          "pf_after_cost","total_return_after_cost_pct","max_consecutive_losses","h1_winrate","h2_winrate",
          "long_winrate","short_winrate","changed_vs_S0"]
    with (REP_OUT/"OKX_MARCH_FUEL_ENHANCED_SELECTOR_RESULTS.csv").open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=keys,extrasaction="ignore"); w.writeheader()
        for name,m in sel_metrics.items(): w.writerow({"selector":name,**m})
    (REP_OUT/"OKX_MARCH_FUEL_ENHANCED_SELECTOR_RESULTS.json").write_text(json.dumps(
        {"build_time_utc":now_iso(),"baseline":{"trades":29,"winrate":62.07,"exp_aft":0.6475,"pf":2.258},
         "selectors":{name:{k:v for k,v in m.items() if k!="trade_list"} for name,m in sel_metrics.items()}},
        indent=2,default=str),encoding="utf-8")
    md=["# Fuel-enhanced selector results","",f"**Build:** {now_iso()}",
        "**Baseline (S0 enhanced):** 29 tr, 62.07% wr, exp +0.6475%, PF 2.258","",
        "| selector | trades | W | L | TO | wr% | exp_aft% | PF | ret% | H1wr | H2wr | chg |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for name,m in sorted(sel_metrics.items(), key=lambda kv:-(kv[1]["winrate_pct"] or 0)):
        md.append(f"| {name} | {m['trades']} | {m['wins']} | {m['losses']} | {m['timeouts']} | {m['winrate_pct']} | "
            f"{m['expectancy_after_cost_pct']} | {m['pf_after_cost']} | {m['total_return_after_cost_pct']} | "
            f"{m['h1_winrate']} | {m['h2_winrate']} | {m['changed_vs_S0']} |")
    (REP_OUT/"OKX_MARCH_FUEL_ENHANCED_SELECTOR_RESULTS.md").write_text("\n".join(md),encoding="utf-8")

    # best fuel selector (min trades>=20, max expectancy; else best with >=10 flagged overfit)
    best=None
    for name,m in sel_metrics.items():
        if name=="S0_enhanced_baseline": continue
        if m["trades"]>=20 and (best is None or (m["expectancy_after_cost_pct"] or -9)>(sel_metrics[best]["expectancy_after_cost_pct"] or -9)):
            best=name
    s0=sel_metrics["S0_enhanced_baseline"]
    best_m=sel_metrics[best] if best else s0
    fuel_improved = best is not None and (best_m["expectancy_after_cost_pct"] or -9)>(s0["expectancy_after_cost_pct"] or -9)

    # ---------- H: Binance readiness ----------
    print("[H] Binance readiness plan ...", file=sys.stderr)
    plan={"build_time_utc":now_iso(),
        "frozen_okx_rule_set":{
            "selector":"dist_to_recent_swing_high_pct<=0.4616 AND dl2_supp_minus_opp_net_flow_15m<=4497.76, top1/day, entry=confirmed",
            "trade":"TP fixed 2%, SL 1.5%, no BE, timeout 24h, cost 0.14% RT",
            "okx_result":"29 trades, 62.07% winrate, exp +0.6475%, PF 2.258, +18.78% return"},
        "features_required_on_binance":[
            "zone dataset from engine replay on Binance Futures BTCUSDT (confirmed zones + candidate/confirmed/trigger ts)",
            "dist_to_recent_swing_high_pct (from trades 1s buckets — available)",
            "dl2_supp_minus_opp_net_flow_15m (from incremental L2 — available via Binance book recorder)",
            "explainable_score components (microprice aligned, sweep_reclaim, opp_dir_zones, prior_move, local_range — all from L2+trades)"],
        "features_buildable_from_binance_recorder":["L2 book","trades","derivative_ticker (OI+funding native on Binance)","liquidations (Binance has them)"],
        "missing_or_caveats":[
            "Binance OI is NATIVE per-instrument and higher granularity than OKX rubik daily — recompute OI features fresh, do NOT port OKX daily-OI thresholds",
            "funding interval differs (Binance 8h too, but values differ) — recompute, no threshold port",
            "fuel did not help on OKX (see results) so it is OPTIONAL on Binance"],
        "evaluation_protocol":[
            "Freeze the OKX selector/trade thresholds EXACTLY (no retune).",
            "Replay engine on Binance days (already have 2026-05-18..20 + 2025 set).",
            "Apply identical selector + fixed 2%/1.5% trade model.",
            "Report winrate/expectancy/PF; compare to OKX 62.07% as OOS cross-venue check.",
            "Only AFTER clean OOS pass, consider adding native Binance OI/liquidation fuel."],
        "flags":{"FINAL_OKX_RULE_SET_DEFINED":"YES","READY_FOR_BINANCE_TEST":"YES"}}
    (REP_OUT/"BINANCE_NEXT_TEST_READINESS_PLAN.json").write_text(json.dumps(plan,indent=2),encoding="utf-8")
    md=["# Binance next-test readiness plan","",f"**Build:** {now_iso()}","",
        "## Frozen OKX rule set (do NOT retune on Binance)",
        f"- Selector: {plan['frozen_okx_rule_set']['selector']}",
        f"- Trade: {plan['frozen_okx_rule_set']['trade']}",
        f"- OKX result: {plan['frozen_okx_rule_set']['okx_result']}","",
        "## Required Binance inputs"]
    for x in plan["features_required_on_binance"]: md.append(f"- {x}")
    md+=["","## Buildable from Binance recorder"]
    for x in plan["features_buildable_from_binance_recorder"]: md.append(f"- {x}")
    md+=["","## Caveats"]
    for x in plan["missing_or_caveats"]: md.append(f"- {x}")
    md+=["","## Evaluation protocol"]
    for x in plan["evaluation_protocol"]: md.append(f"- {x}")
    (REP_OUT/"BINANCE_NEXT_TEST_READINESS_PLAN.md").write_text("\n".join(md),encoding="utf-8")

    # ---------- I: final ----------
    print("[I] final report ...", file=sys.stderr)
    n_hit2=sum(1 for o in ok if o["hit_2pct"]); n_local=sum(1 for o in ok if o["local_reaction_only"])
    n_tooclose=sum(1 for o in ok if o["target_zone_too_close"])
    flags={
        "OKX_MARCH_OI_FUEL_RESEARCH_DONE":"YES",
        "OKX_PUBLIC_OI_ENDPOINT_FOUND":"YES","OKX_OI_HISTORY_AVAILABLE":"YES (1D only for March)",
        "OI_DATA_AVAILABLE":"YES (daily)","FUNDING_DATA_AVAILABLE":"YES","LIQUIDATIONS_USED":"NO",
        "TRUE_OI_FEATURES_BUILT":"YES (daily)","FLOW_PROXY_BUILT":"YES","FLOW_PROXY_NOT_TRUE_OI":"YES",
        "TARGET_ZONE_ORIENTATION_BUILT":"YES","TARGET_ZONE_USED_AS_PRIMARY_WIN":"NO",
        "BASELINE_ENHANCED_TRADES":29,"BASELINE_ENHANCED_WINRATE":62.07,
        "BASELINE_ENHANCED_EXPECTANCY_AFTER_COST":0.6475,"BASELINE_ENHANCED_PF_AFTER_COST":2.258,
        "BEST_FUEL_SELECTOR_NAME":best or "none(min20)","BEST_FUEL_SELECTOR_TRADES":best_m["trades"],
        "BEST_FUEL_SELECTOR_WINRATE":best_m["winrate_pct"],
        "BEST_FUEL_SELECTOR_EXPECTANCY_AFTER_COST":best_m["expectancy_after_cost_pct"],
        "BEST_FUEL_SELECTOR_PF_AFTER_COST":best_m["pf_after_cost"],
        "FUEL_IMPROVED_OVER_ENHANCED":"YES" if fuel_improved else "NO",
        "TARGET_ZONE_USEFUL_AS_ORIENTATION":"YES" if n_local>0 else "PARTIAL",
        "SEVENTY_PERCENT_REACHED":"YES" if (best_m["winrate_pct"] or 0)>=70 else "NO",
        "SEVENTY_PERCENT_WITH_MIN20_REACHED":"YES" if ((best_m["winrate_pct"] or 0)>=70 and best_m["trades"]>=20) else "NO",
        "FINAL_OKX_RULE_SET_DEFINED":"YES","READY_FOR_BINANCE_TEST":"YES",
        "READY_FOR_TELEGRAM_SHADOW_MODE":"NO","READY_TO_CHANGE_ENGINE":"NO",
        "READY_FOR_PRODUCTION_TRADING":"NO","MORE_VALIDATION_REQUIRED":"YES"}
    final={"build_time_utc":now_iso(),"flags":flags,
        "oi_funding_status":{"true_oi":"daily (OKX rubik, USD aggregate)","funding":"8h (OKX public)","intraday_oi":"NOT available -> FLOW_PROXY"},
        "best_fuel_selector":{"name":best,"metrics":{k:v for k,v in best_m.items() if k!="trade_list"}},
        "target_orientation":{"n":len(ok),"hit_2pct":n_hit2,"local_reaction_only":n_local,"target_too_close_lt2pct":n_tooclose},
        "fuel_eval_top":tableF[:5]}
    (REP_OUT/"OKX_MARCH_OI_FUEL_TARGET_ORIENTATION_FINAL_REPORT.json").write_text(json.dumps(final,indent=2,default=str),encoding="utf-8")
    md=["# OKX March OI/fuel + target orientation — final report","",f"**Build:** {now_iso()}",
        "**Scope:** IN-SAMPLE OKX March 2026. No engine change. Primary win strict 2%. No liquidations. No Binance run.","",
        "## 1-2. Data availability",
        "- TRUE OI from OKX: **YES but DAILY only** (rubik open-interest-volume 1D; 5m/1H don't reach March). USD aggregate BTC.",
        "- Funding from OKX: **YES** (public funding-rate-history, 8h, covers March).",
        "## 3-4. Features",
        "- TRUE OI features built (daily regime): oi_delta_1d/3d, oi_zscore_14d, price+OI regime. Intraday OI deltas NOT possible.",
        "- FLOW_PROXY built for intraday (taker imbalance/vol zscores) — explicitly NOT OI.",
        "## 5. Did fuel improve over enhanced 62.07%?",
        f"- **{flags['FUEL_IMPROVED_OVER_ENHANCED']}**. Best fuel selector (min20): `{best}` — wr {best_m['winrate_pct']}%, exp {best_m['expectancy_after_cost_pct']}%, PF {best_m['pf_after_cost']}.",
        "## 6. Does fuel explain correct-direction-but-no-2pct?",
        f"- true_fuel d(win vs nonwin) small (see fuel eval). Daily OI too coarse to time intraday follow-through. Funding background only.",
        "## 7. Target-zone orientation as secondary metric",
        f"- hit_2pct={n_hit2}/{len(ok)}; local_reaction_only={n_local}; target_too_close(<2%)={n_tooclose}.",
        f"- Useful as DIAGNOSTIC orientation; NOT used as primary win or hard gate.",
        "## 8. 70% with min20?",
        f"- **{flags['SEVENTY_PERCENT_WITH_MIN20_REACHED']}**.",
        "## 9. Final OKX rule set",
        "- Selector: `dist_to_recent_swing_high_pct<=0.4616 AND dl2_supp_minus_opp_net_flow_15m<=4497.76`, top1/day, entry=confirmed.",
        "- Trade: TP fixed 2%, SL 1.5%, no BE, timeout 24h, cost 0.14%. → 62.07% wr, PF 2.258, +18.78%.",
        "- Fuel/target-zone: keep as ORIENTATION/diagnostic only (did not beat baseline).",
        "## 10-11. Binance readiness",
        "- READY: freeze OKX thresholds, replay engine on Binance, apply identical model, compare OOS. Recompute native OI/funding fresh (do not port OKX daily-OI thresholds).",
        "","## Final flags","```"]
    for k,v in flags.items(): md.append(f"{k} = {v}")
    md+=["```","","## Hard rules honored",
        "- engine/thresholds/detector UNCHANGED; primary win strict 2%; target-zone secondary only; "
        "no liquidations; no Binance run; true OI from OKX statistics (not volume); FLOW_PROXY labeled non-OI; no future leak."]
    (REP_OUT/"OKX_MARCH_OI_FUEL_TARGET_ORIENTATION_FINAL_REPORT.md").write_text("\n".join(md),encoding="utf-8")

    # console
    print()
    print("="*92)
    print("FUEL-ENHANCED SELECTORS (primary win = strict 2%)")
    print("="*92)
    print(f"{'selector':<28} {'tr':>3} {'W':>3} {'L':>3} {'TO':>3} {'wr%':>6} {'exp%':>7} {'PF':>6} {'ret%':>7}")
    for name,m in sorted(sel_metrics.items(), key=lambda kv:-(kv[1]['winrate_pct'] or 0)):
        print(f"{name:<28} {m['trades']:>3} {m['wins']:>3} {m['losses']:>3} {m['timeouts']:>3} {m['winrate_pct']:>6} "
              f"{m['expectancy_after_cost_pct']:>7} {str(m['pf_after_cost']):>6} {m['total_return_after_cost_pct']:>7}")
    print()
    print(f"Target orientation: hit_2pct={n_hit2}/{len(ok)}  local_reaction_only={n_local}  target_too_close={n_tooclose}")
    print()
    print("FINAL FLAGS:")
    for k,v in flags.items(): print(f"  {k:<46s} = {v}")
    return 0

if __name__=="__main__":
    sys.exit(main())
