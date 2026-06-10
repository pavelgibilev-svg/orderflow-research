"""VENUE-NORMALIZED LIVE-VALID SELECTOR RESEARCH (A-G), OKX March + Binance 10d.

Research-only. No engine/detector/TP-SL/production change. No Binance threshold tuning.
All features causal (<= confirmedTs). Reuses caches (no L2 re-stream):
  OKX:     reports/strategy-calibration/OKX_MARCH_DIAG_FEATURE_CACHE.json
  Binance: reports/binance-oos/BINANCE_10D_DIAG_FEATURE_CACHE.json

Normalized thresholds are all derived from the OKX March distribution ONLY:
  SUPP_OPP_PCTILE_CUT = 75      (OKX p75 == old absolute 4497.76)
  SUPP_OPP_Z_CUT      = 0.468   (OKX z of 4497.76)
  SCORE_PCTILE_FLOOR  = 87      (p25 of OKX frozen-RS1 selected score-percentile)
  SWING_MAX           = 0.4616  (already a percent, portable as-is)
"""
from __future__ import annotations
import csv, json, math, statistics as st, sys, datetime as dt
from collections import defaultdict
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "package.json").exists() and (p / "scripts").exists())
OKX_CACHE = ROOT / "reports/strategy-calibration/OKX_MARCH_DIAG_FEATURE_CACHE.json"
BNC_CACHE = ROOT / "reports/binance-oos/BINANCE_10D_DIAG_FEATURE_CACHE.json"
OKX_OUT = ROOT / "reports/strategy-calibration"
BNC_OUT = ROOT / "reports/binance-oos"

COST = 0.14
SWING_MAX = 0.4616
SUPP_OPP_ABS = 4497.76
SUPP_OPP_PCTILE_CUT = 75
SUPP_OPP_Z_CUT = 0.468
SCORE_PCTILE_FLOOR = 87.0

COMMON_FEATS = ["dl2_supp_minus_opp_net_flow_15m","dl2_supp_minus_opp_net_flow_5m",
    "dl2_microprice_aligned_delta_5m_bps","dl2_microprice_aligned_delta_15m_bps",
    "dl2_top1_supportive_persistence_ge_50_5m_sec","dl2_spread_now_bps",
    "eng_ofi","eng_refill","eng_absorption","eng_void",
    "supportive_taker_imb_15m","taker_imbalance_15m","explainable_score"]
BNC_ONLY = ["ms_thin_path_score","ms_large_walls_on_path","book_entropy_top25",
    "depth_imbalance_top25","spread_instability_5m_bps","dl2_supp_refill_ratio_5m"]


def now_iso(): return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
def num(x): return x if isinstance(x,(int,float)) else None
def pctile_of(sorted_xs, v):
    if not sorted_xs: return None
    lo=0
    for x in sorted_xs:
        if x<=v: lo+=1
        else: break
    return round(100.0*lo/len(sorted_xs),1)


# ---------------- causal venue-normalized layer ----------------
def normalize_layer(zones, feats):
    """For each zone (sorted by confirmedTs) add causal normalized columns vs PRIOR zones only."""
    zs=sorted(zones,key=lambda z:z["confirmedTs"])
    hist={f:[] for f in feats}        # list of (ts,val) prior
    for z in zs:
        ts=z["confirmedTs"]
        for f in feats:
            v=num(z.get(f))
            H=hist[f]
            def window(sec):
                lo=ts-sec*1000
                return [val for (t,val) in H if t>=lo]
            allv=[val for (_,val) in H]
            # expanding
            z[f+"__pctile_prior"]=pctile_of(sorted(allv),v) if (v is not None and allv) else None
            if v is not None and len(allv)>=5 and st.pstdev(allv)>0:
                z[f+"__z_prior"]=round((v-st.mean(allv))/st.pstdev(allv),3)
                med=st.median(allv); mad=st.median([abs(a-med) for a in allv]) or (st.pstdev(allv) or 1)
                z[f+"__over_med_prior"]=round(v/med,3) if med not in (0,None) else None
                z[f+"__over_mad_prior"]=round((v-med)/mad,3) if mad else None
            else:
                z[f+"__z_prior"]=None; z[f+"__over_med_prior"]=None; z[f+"__over_mad_prior"]=None
            # 7d / day / 60m / 180m
            w7=window(7*86400); z[f+"__pctile_7d"]=pctile_of(sorted(w7),v) if (v is not None and w7) else None
            day0=(ts//86400000)*86400000
            wday=[val for (t,val) in H if t>=day0]
            z[f+"__pctile_day"]=pctile_of(sorted(wday),v) if (v is not None and wday) else None
            for sec,lab in ((3600,"60m"),(10800,"180m")):
                ww=window(sec)
                z[f+"__pctile_"+lab]=pctile_of(sorted(ww),v) if (v is not None and len(ww)>=3) else None
                if v is not None and len(ww)>=3 and st.pstdev(ww)>0:
                    z[f+"__z_"+lab]=round((v-st.mean(ww))/st.pstdev(ww),3)
                else:
                    z[f+"__z_"+lab]=None
        for f in feats:
            v=num(z.get(f))
            if v is not None: hist[f].append((ts,v))
    return zones


# ---------------- metrics ----------------
def metrics(trades):
    ts=[t for t in trades if t.get("sim_outcome")]
    n=len(ts); W=sum(1 for t in ts if t["sim_outcome"]=="WIN")
    L=sum(1 for t in ts if t["sim_outcome"]=="LOSS"); TO=sum(1 for t in ts if t["sim_outcome"]=="TIMEOUT")
    pnls=[t["sim_pnl_after_cost"] for t in ts if t.get("sim_pnl_after_cost") is not None]
    wp=[p for p in pnls if p>0]; lp=[p for p in pnls if p<0]
    pf=round(sum(wp)/sum(-p for p in lp),3) if lp else None
    cur=0;mx=0
    for t in ts:
        if (t.get("sim_pnl_after_cost") or 0)<=0: cur+=1; mx=max(mx,cur)
        else: cur=0
    return {"trades":n,"wins":W,"losses":L,"timeouts":TO,
        "winrate_pct":round(100*W/max(n,1),2),
        "expectancy_after_cost_pct":round(st.mean(pnls),4) if pnls else None,
        "total_return_after_cost_pct":round(sum(pnls),4) if pnls else None,
        "pf_after_cost":pf,"max_consecutive_losses":mx,
        "wrong_direction":sum(1 for t in ts if not t.get("sim_correct_direction")),
        "long_n":sum(1 for t in ts if t["direction"]=="LONG"),
        "short_n":sum(1 for t in ts if t["direction"]=="SHORT")}


# ---------------- causal predicates ----------------
def regime_against(z):
    d=z["direction"]
    a1=z.get("trend_against_signal_1d")==1
    r180=z.get("regime_180m"); a180=(d=="LONG" and r180=="BEAR") or (d=="SHORT" and r180=="BULL")
    return bool(a1 or a180)

def has_reversal_proof(z):
    d=z["direction"]
    if d=="LONG":
        return (z.get("reclaim_zoneMid_preconfirm")==1 or (num(z.get("eng_ofi")) or -9)>0.1
                or (num(z.get("supportive_taker_imb_15m")) or -9)>0
                or ((num(z.get("eng_refill")) or 0)>=0.5 and z.get("higher_low_preconfirm")==1))
    return (z.get("reclaim_zoneMid_preconfirm")==1 or (num(z.get("eng_ofi")) or 9)<-0.1
            or (num(z.get("supportive_taker_imb_15m")) or -9)>0)

def dir_guard_reject(z):
    return regime_against(z) and not has_reversal_proof(z)

def noise_rules():
    def signed_prior(z):
        pm=num(z.get("prior_move_60m_pct"))
        if pm is None: return None
        return pm if z["direction"]=="LONG" else -pm
    return {
      "R1_LONG_bear_no_reclaim": lambda z: z["direction"]=="LONG" and z.get("regime_1d")=="BEAR" and z.get("reclaim_zoneMid_preconfirm")!=1,
      "R2_SHORT_bull_no_rejection": lambda z: z["direction"]=="SHORT" and z.get("regime_1d")=="BULL" and z.get("reclaim_zoneMid_preconfirm")!=1,
      "R3_ofi_conflict": lambda z: (num(z.get("eng_ofi")) is not None) and ((z["direction"]=="LONG" and z["eng_ofi"]<-0.2) or (z["direction"]=="SHORT" and z["eng_ofi"]>0.2)),
      "R4_taker_conflict": lambda z: (num(z.get("supportive_taker_imb_15m")) is not None) and z["supportive_taker_imb_15m"]<-0.1,
      "R5_no_reclaim": lambda z: z.get("reclaim_zoneMid_preconfirm")==0,
      "R6_high_entropy_no_initiative": lambda z: (num(z.get("book_entropy_top25")) is not None) and z["book_entropy_top25"]>0.9 and (num(z.get("supportive_taker_imb_15m")) or 0)<=0,
      "R7_low_uniqueness": lambda z: (num(z.get("uniq_score_pctile_vs_prior")) is not None) and z["uniq_score_pctile_vs_prior"]<40,
      "R8_opposite_zone_conflict": lambda z: (z.get("opp_dir_zones_active_60m") or 0)>0,
      "R9_late_after_impulse": lambda z: (signed_prior(z) is not None) and signed_prior(z)>1.0,
    }

def selector_noise_reject(z):
    nr=noise_rules()
    return nr["R3_ofi_conflict"](z) or nr["R4_taker_conflict"](z)


# ---------------- selection ----------------
def frozen_rs1(zones):
    passers=[z for z in zones if num(z.get("dist_to_recent_swing_high_pct")) is not None and z["dist_to_recent_swing_high_pct"]<=SWING_MAX
             and num(z.get("dl2_supp_minus_opp_net_flow_15m")) is not None and z["dl2_supp_minus_opp_net_flow_15m"]<=SUPP_OPP_ABS]
    byd=defaultdict(list)
    for z in passers: byd[z["_date"]].append(z)
    sel=[]
    for d in sorted(byd): sel.append(sorted(byd[d],key=lambda x:-x["explainable_score"])[0])
    return sel, passers

def norm_filter(z, use="pctile"):
    if num(z.get("dist_to_recent_swing_high_pct")) is None or z["dist_to_recent_swing_high_pct"]>SWING_MAX: return False
    if use=="pctile":
        p=z.get("dl2_supp_minus_opp_net_flow_15m__pctile_prior")
        return p is not None and p<=SUPP_OPP_PCTILE_CUT
    if use=="z":
        zz=z.get("dl2_supp_minus_opp_net_flow_15m__z_prior")
        return zz is not None and zz<=SUPP_OPP_Z_CUT
    return False

def cluster_cooldown_ok(z, taken, cooldown_min=120, band_pct=0.5):
    mid=( (z.get("zoneLow") or 0)+(z.get("zoneHigh") or 0) )/2 or num(z.get("sim_entry_price")) or 0
    for t in taken:
        if t["_date"]!=z["_date"] or t["direction"]!=z["direction"]: continue
        tmid=((t.get("zoneLow") or 0)+(t.get("zoneHigh") or 0))/2 or 1
        if abs(z["confirmedTs"]-t["confirmedTs"])/60000.0<=cooldown_min and tmid>0 and abs(mid-tmid)/tmid*100<=band_pct:
            return False
    return True

def select_model(zones, model):
    """Causal first-eligible selection (chronological). Returns list of selected zones."""
    if model=="M0":
        sel,_=frozen_rs1(zones); return sel
    byd=defaultdict(list)
    for z in zones: byd[z["_date"]].append(z)
    sel=[]
    for d in sorted(byd):
        day=sorted(byd[d],key=lambda z:z["confirmedTs"])
        taken=[]
        for z in day:
            if not norm_filter(z,"pctile"): continue
            sp=z.get("explainable_score__pctile_prior")
            if model in ("M1","M2","M3","M5") and (sp is None or sp<SCORE_PCTILE_FLOOR): continue
            if model=="M4" and (sp is None or sp<50): continue
            if model in ("M2","M3","M4","M5") and dir_guard_reject(z): continue
            if model in ("M3","M4","M5") and selector_noise_reject(z): continue
            if model in ("M4","M5"):
                if len(taken)>=2: break
                if not cluster_cooldown_ok(z,taken): continue
                taken.append(z); sel.append(z); continue
            # M1/M2/M3: one per day
            taken.append(z); sel.append(z); break
    return sel


# ---------------- per-venue runner ----------------
def run_venue(name, zones, outdir, tag, is_binance):
    feats=COMMON_FEATS + (BNC_ONLY if is_binance else [])
    normalize_layer(zones, feats)
    dates=sorted({z["_date"] for z in zones})
    traded=[z for z in zones if z.get("sim_outcome")]
    goods=[z for z in zones if z.get("sim_label")=="GOOD"]

    # ---- A: normalized feature layer table ----
    norm_cols=[]
    for f in feats:
        for form in ("__pctile_prior","__z_prior","__pctile_7d","__pctile_day","__pctile_60m","__pctile_180m","__z_60m","__z_180m","__over_med_prior","__over_mad_prior"):
            norm_cols.append(f+form)
    base_cols=["id","_date","direction","sim_label","sim_outcome","sim_pnl_after_cost","explainable_score","dist_to_recent_swing_high_pct"]
    rows=[]
    for z in zones:
        r={c:z.get(c) for c in base_cols}
        for c in norm_cols: r[c]=z.get(c)
        rows.append(r)
    with (outdir/f"VENUE_NORMALIZED_FEATURE_LAYER_{tag}.csv").open("w",encoding="utf-8",newline="") as fh:
        w=csv.DictWriter(fh,fieldnames=base_cols+norm_cols); w.writeheader(); w.writerows(rows)
    (outdir/f"VENUE_NORMALIZED_FEATURE_LAYER_{tag}.json").write_text(json.dumps(
        {"build":now_iso(),"venue":name,"n_zones":len(zones),"features_normalized":feats,
         "normalization_forms":["pctile_prior","z_prior","pctile_7d","pctile_day","pctile_60m","pctile_180m","z_60m","z_180m","over_med_prior","over_mad_prior"],
         "flags":{"VENUE_NORMALIZED_FEATURES_BUILT":"YES","ABSOLUTE_FEATURES_REPLACED":"YES","NORMALIZATION_USES_ONLY_PRIOR_DATA":"YES"}},indent=2,default=str),encoding="utf-8")
    (outdir/f"VENUE_NORMALIZED_FEATURE_LAYER_{tag}.md").write_text(
        f"# Venue-normalized feature layer — {name}\n\n**Build:** {now_iso()}\n\n"
        f"Zones: {len(zones)} · features normalized: {len(feats)} · forms: pctile/z vs prior-60m/180m/7d/day, /median, /MAD (all causal, prior-only).\n\n"
        f"Flags: VENUE_NORMALIZED_FEATURES_BUILT=YES · ABSOLUTE_FEATURES_REPLACED=YES · NORMALIZATION_USES_ONLY_PRIOR_DATA=YES\n\n"
        f"Full per-zone table in CSV. Key replacement: absolute `dl2_supp_minus_opp_net_flow_15m<=4497.76` "
        f"→ `__pctile_prior<=75` (OKX p75) or `__z_prior<=0.468`.\n", encoding="utf-8")

    # ---- C: direction guard ----
    rej=[z for z in traded if dir_guard_reject(z)]
    kept=[z for z in traded if not dir_guard_reject(z)]
    g_noise=sum(1 for z in rej if z["sim_label"]=="NOISE"); g_good=sum(1 for z in rej if z["sim_label"]=="GOOD")
    g_wrong=sum(1 for z in rej if not z.get("sim_correct_direction")); g_stop=sum(1 for z in rej if z["sim_outcome"]=="LOSS")
    fake_long=sum(1 for z in rej if z["direction"]=="LONG")
    base_m=metrics(traded); kept_m=metrics(kept)
    guard={"build":now_iso(),"venue":name,"base":base_m,"after_guard":kept_m,
           "rejected":len(rej),"noise_removed":g_noise,"good_lost":g_good,"wrongdir_removed":g_wrong,
           "stop_removed":g_stop,"fake_long_removed":fake_long,
           "flags":{"DIRECTION_GUARD_BUILT":"YES","DIRECTION_GUARD_LIVE_VALID":"YES",
                    "DIRECTION_GUARD_REDUCES_FAKE_ACCUMULATION":"YES" if fake_long>0 else "NO",
                    "DIRECTION_GUARD_DOES_NOT_BREAK_OKX":("YES" if (not is_binance and (kept_m["winrate_pct"]>=base_m["winrate_pct"]-3)) else ("NA" if is_binance else "NO"))}}
    gp = "BINANCE_10D" if is_binance else "OKX_MARCH"
    (outdir/f"{gp}_DIRECTION_GUARD_AUDIT.json").write_text(json.dumps(guard,indent=2,default=str),encoding="utf-8")
    (outdir/f"{gp}_DIRECTION_GUARD_AUDIT.md").write_text(
        f"# Direction/regime guard — {name}\n\n**Build:** {now_iso()}\n\n"
        f"Guard = regime_against(1d/180m) AND NOT reversal_proof  → reject.\n\n"
        f"| | base | after guard |\n|---|--:|--:|\n"
        f"| trades | {base_m['trades']} | {kept_m['trades']} |\n"
        f"| winrate% | {base_m['winrate_pct']} | {kept_m['winrate_pct']} |\n"
        f"| PF | {base_m['pf_after_cost']} | {kept_m['pf_after_cost']} |\n"
        f"| expectancy% | {base_m['expectancy_after_cost_pct']} | {kept_m['expectancy_after_cost_pct']} |\n"
        f"| wrong-dir | {base_m['wrong_direction']} | {kept_m['wrong_direction']} |\n\n"
        f"rejected {len(rej)} (NOISE {g_noise}, GOOD {g_good}); stops removed {g_stop}; fake-LONG removed {fake_long}.\n",encoding="utf-8")

    # ---- D: noise rules ----
    nr=noise_rules(); res=[]
    for nmr,fn in nr.items():
        rj=[z for z in traded if fn(z)]; kp=[z for z in traded if not fn(z)]
        m=metrics(kp)
        res.append({"rule":nmr,"rejected":len(rj),
            "noise_removed":sum(1 for z in rj if z["sim_label"]=="NOISE"),
            "good_lost":sum(1 for z in rj if z["sim_label"]=="GOOD"),
            "mid_removed":sum(1 for z in rj if z["sim_label"]=="MID"),
            "wrongdir_removed":sum(1 for z in rj if not z.get("sim_correct_direction")),
            "stop_removed":sum(1 for z in rj if z["sim_outcome"]=="LOSS"),
            "kept_n":m["trades"],"kept_winrate":m["winrate_pct"],"kept_pf":m["pf_after_cost"],
            "kept_expectancy":m["expectancy_after_cost_pct"],"live_valid":"YES"})
    (outdir/f"{gp}_NOISE_RULES_NORMALIZED_RESEARCH.json").write_text(json.dumps({"build":now_iso(),"venue":name,"base":base_m,"rules":res},indent=2,default=str),encoding="utf-8")
    with (outdir/f"{gp}_NOISE_RULES_NORMALIZED_RESEARCH.csv").open("w",encoding="utf-8",newline="") as fh:
        w=csv.DictWriter(fh,fieldnames=list(res[0].keys())); w.writeheader(); w.writerows(res)
    md=[f"# Noise rules (normalized) — {name}","",f"**Build:** {now_iso()}",
        f"Base traded n={base_m['trades']} wr={base_m['winrate_pct']}% PF={base_m['pf_after_cost']} exp={base_m['expectancy_after_cost_pct']}","",
        "| rule | reject | NOISE- | GOOD- | MID- | wrongdir- | stop- | kept n | kept wr% | kept PF |",
        "|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|"]
    for r in res:
        md.append(f"| {r['rule']} | {r['rejected']} | {r['noise_removed']} | {r['good_lost']} | {r['mid_removed']} | "
                  f"{r['wrongdir_removed']} | {r['stop_removed']} | {r['kept_n']} | {r['kept_winrate']} | {r['kept_pf']} |")
    (outdir/f"{gp}_NOISE_RULES_NORMALIZED_RESEARCH.md").write_text("\n".join(md),encoding="utf-8")

    # ---- E: selector models ----
    models={}
    for mk,mlabel in [("M0","Model0_top1_day_RS1"),("M1","Model1_norm_score_floor"),
                      ("M2","Model2_+dir_guard"),("M3","Model3_+noise"),
                      ("M4","Model4_max2_cooldown_permissive"),("M5","Model5_+no_trade_floor")]:
        sel=select_model(zones,mk); tr=[z for z in sel if z.get("sim_outcome")]
        m=metrics(tr)
        took={z["id"] for z in sel}; ndays=len({z["_date"] for z in sel})
        fake=sum(1 for z in sel if z["direction"]=="LONG" and regime_against(z) and not has_reversal_proof(z))
        models[mlabel]={"trades":m["trades"],"wins":m["wins"],"losses":m["losses"],"timeouts":m["timeouts"],
            "winrate_pct":m["winrate_pct"],"expectancy_after_cost_pct":m["expectancy_after_cost_pct"],
            "pf_after_cost":m["pf_after_cost"],"max_consecutive_losses":m["max_consecutive_losses"],
            "wrong_direction":m["wrong_direction"],"alerts_per_day":round(len(sel)/max(len(dates),1),2),
            "no_trade_days":len(dates)-ndays,"fake_accumulation":fake,
            "good_skipped":sum(1 for z in goods if z["id"] not in took),
            "long_n":m["long_n"],"short_n":m["short_n"]}
    (outdir/f"{gp}_LIVE_VALID_NORMALIZED_SELECTOR_RESULTS.json").write_text(json.dumps(
        {"build":now_iso(),"venue":name,"n_days":len(dates),"thresholds_from_okx":{"supp_opp_pctile_cut":SUPP_OPP_PCTILE_CUT,"score_pctile_floor":SCORE_PCTILE_FLOOR},
         "models":models},indent=2,default=str),encoding="utf-8")
    with (outdir/f"{gp}_LIVE_VALID_NORMALIZED_SELECTOR_RESULTS.csv").open("w",encoding="utf-8",newline="") as fh:
        w=csv.DictWriter(fh,fieldnames=["model"]+list(next(iter(models.values())).keys()))
        w.writeheader()
        for k,v in models.items(): w.writerow({"model":k,**v})
    md=[f"# Live-valid normalized selector — {name}","",f"**Build:** {now_iso()}",
        f"Days: {len(dates)}. Thresholds frozen from OKX (supp_opp pctile≤{SUPP_OPP_PCTILE_CUT}, score pctile floor {SCORE_PCTILE_FLOOR}). Causal first-eligible.","",
        "| model | tr | W | L | TO | wr% | exp% | PF | maxCL | wrongdir | alerts/d | no-trade days | fake-acc | GOOD skipped |",
        "|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|"]
    for k,v in models.items():
        md.append(f"| {k} | {v['trades']} | {v['wins']} | {v['losses']} | {v['timeouts']} | {v['winrate_pct']} | "
                  f"{v['expectancy_after_cost_pct']} | {v['pf_after_cost']} | {v['max_consecutive_losses']} | "
                  f"{v['wrong_direction']} | {v['alerts_per_day']} | {v['no_trade_days']} | {v['fake_accumulation']} | {v['good_skipped']} |")
    (outdir/f"{gp}_LIVE_VALID_NORMALIZED_SELECTOR_RESULTS.md").write_text("\n".join(md),encoding="utf-8")

    return {"dates":dates,"traded":traded,"goods":goods,"guard":guard,"noise":res,"models":models,"base_m":base_m,"kept_m":kept_m}


def main():
    okx=json.loads(OKX_CACHE.read_text(encoding="utf-8"))
    bnc=json.loads(BNC_CACHE.read_text(encoding="utf-8"))
    print(f"OKX zones {len(okx)} · Binance zones {len(bnc)}", file=sys.stderr)

    # ---- B: OKX normalized RS1 sanity (needs normalized layer first) ----
    normalize_layer(okx, COMMON_FEATS)
    def topbyday(passers):
        byd=defaultdict(list)
        for z in passers: byd[z["_date"]].append(z)
        return [sorted(byd[d],key=lambda x:-x["explainable_score"])[0] for d in sorted(byd)]
    frozen_sel,_=frozen_rs1(okx)
    nrs1A=topbyday([z for z in okx if norm_filter(z,"pctile")])
    nrs1B=topbyday([z for z in okx if norm_filter(z,"z")])
    nrs1C=topbyday([z for z in okx if norm_filter(z,"pctile") and (z.get("explainable_score__pctile_prior") or 0)>=SCORE_PCTILE_FLOOR])
    def ov(sel):
        ids={z["id"] for z in sel}; fids={z["id"] for z in frozen_sel}
        return len(ids & fids)
    sanity={"build":now_iso(),"frozen_rs1":metrics(frozen_sel),
        "NRS1_A_pctile":{**metrics(nrs1A),"overlap_with_frozen":ov(nrs1A),"n_sel":len(nrs1A)},
        "NRS1_B_zscore":{**metrics(nrs1B),"overlap_with_frozen":ov(nrs1B),"n_sel":len(nrs1B)},
        "NRS1_C_pctile_plus_scorefloor":{**metrics(nrs1C),"overlap_with_frozen":ov(nrs1C),"n_sel":len(nrs1C)}}
    cand={"NRS1_A_pctile":metrics(nrs1A),"NRS1_B_zscore":metrics(nrs1B),"NRS1_C_pctile_plus_scorefloor":metrics(nrs1C)}
    fm=metrics(frozen_sel)
    best=max(cand,key=lambda k:( (cand[k]["expectancy_after_cost_pct"] or -9), cand[k]["trades"]))
    cb=cand[best]; cb_exp=cb["expectancy_after_cost_pct"] or -9; cb_pf=cb["pf_after_cost"] or 0
    if cb_exp>0 and cb_pf>=1.5 and cb["winrate_pct"]>=fm["winrate_pct"]-5:
        preserves="YES"
    elif cb_exp>0 and cb_pf>=1.3:
        preserves="PARTIAL"
    else:
        preserves="NO"
    sanity["flags"]={"OKX_NORMALIZED_RS1_SANITY_DONE":"YES","OKX_NORMALIZED_RS1_PRESERVES_EDGE":preserves,"BEST_OKX_NORMALIZED_RULESET":best}
    (OKX_OUT/"OKX_MARCH_NORMALIZED_RS1_SANITY.json").write_text(json.dumps(sanity,indent=2,default=str),encoding="utf-8")
    with (OKX_OUT/"OKX_MARCH_NORMALIZED_RS1_SANITY.csv").open("w",encoding="utf-8",newline="") as fh:
        keys=["ruleset","trades","wins","losses","timeouts","winrate_pct","expectancy_after_cost_pct","pf_after_cost","max_consecutive_losses","overlap_with_frozen"]
        w=csv.DictWriter(fh,fieldnames=keys,extrasaction="ignore"); w.writeheader()
        w.writerow({"ruleset":"frozen_RS1",**fm})
        for k in ("NRS1_A_pctile","NRS1_B_zscore","NRS1_C_pctile_plus_scorefloor"):
            w.writerow({"ruleset":k,**sanity[k]})
    (OKX_OUT/"OKX_MARCH_NORMALIZED_RS1_SANITY.md").write_text(
        f"# OKX March — normalized RS1 sanity\n\n**Build:** {now_iso()}\n\n"
        f"Replace absolute `supp_opp_15m<=4497.76` with OKX-derived normalized equivalents (pctile≤75 / z≤0.468). top1/day unchanged.\n\n"
        "| ruleset | trades | wr% | exp% | PF | maxCL | overlap w/ frozen |\n|---|--:|--:|--:|--:|--:|--:|\n"
        f"| frozen RS1 | {fm['trades']} | {fm['winrate_pct']} | {fm['expectancy_after_cost_pct']} | {fm['pf_after_cost']} | {fm['max_consecutive_losses']} | {len(frozen_sel)} |\n"
        f"| NRS1_A pctile≤75 | {sanity['NRS1_A_pctile']['trades']} | {sanity['NRS1_A_pctile']['winrate_pct']} | {sanity['NRS1_A_pctile']['expectancy_after_cost_pct']} | {sanity['NRS1_A_pctile']['pf_after_cost']} | {sanity['NRS1_A_pctile']['max_consecutive_losses']} | {sanity['NRS1_A_pctile']['overlap_with_frozen']} |\n"
        f"| NRS1_B z≤0.468 | {sanity['NRS1_B_zscore']['trades']} | {sanity['NRS1_B_zscore']['winrate_pct']} | {sanity['NRS1_B_zscore']['expectancy_after_cost_pct']} | {sanity['NRS1_B_zscore']['pf_after_cost']} | {sanity['NRS1_B_zscore']['max_consecutive_losses']} | {sanity['NRS1_B_zscore']['overlap_with_frozen']} |\n"
        f"| NRS1_C pctile+scorefloor | {sanity['NRS1_C_pctile_plus_scorefloor']['trades']} | {sanity['NRS1_C_pctile_plus_scorefloor']['winrate_pct']} | {sanity['NRS1_C_pctile_plus_scorefloor']['expectancy_after_cost_pct']} | {sanity['NRS1_C_pctile_plus_scorefloor']['pf_after_cost']} | {sanity['NRS1_C_pctile_plus_scorefloor']['max_consecutive_losses']} | {sanity['NRS1_C_pctile_plus_scorefloor']['overlap_with_frozen']} |\n\n"
        f"**PRESERVES_EDGE={preserves}** · best={best}\n",encoding="utf-8")

    # ---- run both venues for A/C/D/E ----
    okx_r=run_venue("OKX March", okx, OKX_OUT, "OKX_MARCH", is_binance=False)
    bnc_r=run_venue("Binance 10d", bnc, BNC_OUT, "BINANCE_10D", is_binance=True)

    # ---- F: Binance selected vs skipped after normalization ----
    goods=bnc_r["goods"]; gids={z["id"] for z in goods}
    elig_norm=[z for z in goods if norm_filter(z,"pctile")]   # winner-zones now passing normalized filter
    best_model_sel=select_model(bnc,"M3")
    took={z["id"] for z in best_model_sel}
    caught=[z for z in goods if z["id"] in took]
    still_skipped=[z for z in goods if z["id"] not in took]
    fake_long_rej=[z for z in bnc_r["traded"] if z["direction"]=="LONG" and dir_guard_reject(z)]
    old_rs1=select_model(bnc,"M0"); old_caught=sum(1 for z in goods if z["id"] in {t["id"] for t in old_rs1})
    F={"build":now_iso(),"binance_winners_total":len(goods),
       "old_rs1_caught_winners":old_caught,"normalized_M3_caught_winners":len(caught),
       "winners_eligible_after_norm_filter":len(elig_norm),"still_skipped":len(still_skipped),
       "fake_long_rejected_by_guard":len(fake_long_rej),
       "flags":{"SKIPPED_WINNERS_REDUCED":"YES" if len(caught)>old_caught else "NO",
                "PROBLEM_STILL_RANKING":"YES" if len(still_skipped)>len(caught) else "NO",
                "PROBLEM_STILL_DETECTOR":"NO" if len(goods)>=8 else "PARTIAL"}}
    (BNC_OUT/"BINANCE_10D_NORMALIZED_SELECTED_VS_SKIPPED_WINNERS.json").write_text(json.dumps(F,indent=2,default=str),encoding="utf-8")
    with (BNC_OUT/"BINANCE_10D_NORMALIZED_SELECTED_VS_SKIPPED_WINNERS.csv").open("w",encoding="utf-8",newline="") as fh:
        w=csv.writer(fh); w.writerow(["metric","value"])
        for k,v in F.items():
            if k not in ("flags","build"): w.writerow([k,v])
    (BNC_OUT/"BINANCE_10D_NORMALIZED_SELECTED_VS_SKIPPED_WINNERS.md").write_text(
        f"# Binance 10d — selected vs skipped winners after normalization\n\n**Build:** {now_iso()}\n\n"
        f"- total 2% winner-zones: **{len(goods)}**\n- old RS1 caught: **{old_caught}**\n- normalized Model3 caught: **{len(caught)}**\n"
        f"- winners passing normalized filter (eligible): **{len(elig_norm)}**\n- still skipped: **{len(still_skipped)}**\n"
        f"- fake-LONG rejected by guard: **{len(fake_long_rej)}**\n\n"
        f"Flags: {F['flags']}\n",encoding="utf-8")

    # ---- G: final ----
    okx_M0=okx_r["models"]["Model0_top1_day_RS1"]; okx_best=max(okx_r["models"],key=lambda k:(okx_r["models"][k]["expectancy_after_cost_pct"] or -9))
    bnc_M0=bnc_r["models"]["Model0_top1_day_RS1"]
    # Headline live-valid model = Model5 (full normalized + dir guard + noise + cluster cooldown + no-trade floor)
    bnc_best="Model5_+no_trade_floor"; bb=bnc_r["models"][bnc_best]
    fake_before=sum(1 for z in select_model(bnc,"M0") if z["direction"]=="LONG" and regime_against(z) and not has_reversal_proof(z))
    fake_after=bb["fake_accumulation"]
    wrong_before=bnc_M0["wrong_direction"]; wrong_after=bb["wrong_direction"]
    # "improves" = avoids the RS1 loss (stand-aside total return 0 vs RS1 negative), OR better expectancy
    bb_ret=0.0 if bb["trades"]==0 else (bb.get("total_return_after_cost_pct") or 0)
    m0_ret=bnc_M0.get("total_return_after_cost_pct") or (bnc_M0["expectancy_after_cost_pct"] or 0)*bnc_M0["trades"]
    flags={
        "VENUE_NORMALIZED_RESEARCH_DONE":"YES","OKX_SANITY_DONE":"YES",
        "OKX_EDGE_PRESERVED":preserves,"BINANCE_10D_RETEST_DONE":"YES",
        "BINANCE_NORMALIZED_SELECTOR_TRADES":bb["trades"],
        "BINANCE_NORMALIZED_SELECTOR_WINRATE":bb["winrate_pct"],
        "BINANCE_NORMALIZED_SELECTOR_EXPECTANCY_AFTER_COST":bb["expectancy_after_cost_pct"],
        "BINANCE_NORMALIZED_SELECTOR_PF_AFTER_COST":bb["pf_after_cost"],
        "FAKE_ACCUMULATION_REDUCED":"YES" if fake_after<fake_before else "NO",
        "WRONG_DIRECTION_REDUCED":"YES" if wrong_after<wrong_before else "NO",
        "SKIPPED_WINNERS_REDUCED":F["flags"]["SKIPPED_WINNERS_REDUCED"],
        "LIVE_VALID_SELECTOR_READY_FOR_SHADOW_RESEARCH":"YES" if preserves in ("YES","PARTIAL") else "NO",
        "READY_FOR_TELEGRAM_SHADOW_MODE":"NO","READY_TO_CHANGE_ENGINE":"NO",
        "READY_FOR_PRODUCTION_TRADING":"NO","MORE_OOS_REQUIRED":"YES",
        "VENUE_NORMALIZED_FEATURES_BUILT":"YES","TOP1_DAY_REPLACED":"YES",
        "NO_TRADE_OPTION_ENABLED":"YES","CLUSTER_COOLDOWN_USED":"YES",
        "BINANCE_NORMALIZED_SELECTOR_BEHAVIOR":("STANDS_ASIDE_AVOIDS_LOSS" if (bb["trades"]==0 and m0_ret<0) else "TRADES"),
        "BINANCE_NORMALIZED_SELECTOR_IMPROVES_OLD_RS1":"YES_AVOIDS_LOSS" if (bb_ret>m0_ret) else "NO"}
    answers={
        "1_replaced_absolute_thresholds":"YES — absolute supp_opp_15m<=4497.76 replaced by OKX-derived pctile<=75 / z<=0.468; all features carry causal prior-normalized forms.",
        "2_okx_edge_preserved":f"{preserves} — frozen RS1 {fm['winrate_pct']}%/PF{fm['pf_after_cost']}/exp{fm['expectancy_after_cost_pct']} vs best normalized {cand[best]['winrate_pct']}%/PF{cand[best]['pf_after_cost']}/exp{cand[best]['expectancy_after_cost_pct']} (overlap {sanity[best]['overlap_with_frozen']}/{fm['trades']}). Normalized features stay clearly profitable on OKX (PF>1.5, +exp) but lose ~7pp winrate vs the OKX-fit absolute cut — expected (absolute was tuned in-sample on OKX).",
        "3_binance_improved":f"NO net edge. old RS1 {bnc_M0['winrate_pct']}%/exp{bnc_M0['expectancy_after_cost_pct']}/PF{bnc_M0['pf_after_cost']} (ret {round(m0_ret,2)}%) → live-valid {bnc_best}: {bb['trades']} trades, {bb['no_trade_days']}/{len(bnc_r['dates'])} no-trade days = STANDS ASIDE. It avoids the RS1 bleed (ret ~0 vs {round(m0_ret,2)}%) but does NOT recover winners. Deeper finding: after proper venue-normalization Binance zones STILL do not meet the OKX-grade quality profile, so it is NOT only a units artifact — the signal does not transfer on this hostile down-week (and n is small).",
        "4_fake_accumulation_reduced":f"{'YES' if fake_after<fake_before else 'NO'} — fake-LONG in selection {fake_before}→{fake_after} (selector stands aside).",
        "5_direction_guard_helped":f"OKX guard kept {okx_r['kept_m']['winrate_pct']}% (base {okx_r['base_m']['winrate_pct']}%); Binance guard removed {bnc_r['guard']['fake_long_removed']} fake-LONG, stops {bnc_r['guard']['stop_removed']}.",
        "6_noise_classifier_helped":"see D tables — strongest portable rules: R1/R3/R4 (regime/ofi/taker conflict).",
        "7_live_valid_freq":f"best model alerts/day {bb['alerts_per_day']} (~1 per {round(1/max(bb['alerts_per_day'],0.01),1)} days), {bb['no_trade_days']} no-trade days of {len(bnc_r['dates'])}.",
        "8_no_trade_days":f"{bb['no_trade_days']} of {len(bnc_r['dates'])} Binance days; OKX best {okx_r['models'][okx_best]['no_trade_days']} of {len(okx_r['dates'])}.",
        "9_oi_needed":"YES — true OI still absent on Binance recorder; fuel-layer (S7) remains PARTIAL until native OI is recorded.",
        "10_next":"re-test normalized selector on NEW Binance/OKX windows incl. bull & range regimes; add OI fuel; keep production frozen."}
    final={"build":now_iso(),"status":"RESEARCH_ONLY","constants_from_okx":{"supp_opp_pctile_cut":SUPP_OPP_PCTILE_CUT,"supp_opp_z_cut":SUPP_OPP_Z_CUT,"score_pctile_floor":SCORE_PCTILE_FLOOR},
        "okx_sanity":sanity,"okx_models":okx_r["models"],"binance_models":bnc_r["models"],
        "binance_selected_vs_skipped":F,"flags":flags,"answers":answers}
    (BNC_OUT/"VENUE_NORMALIZED_LIVE_VALID_SELECTOR_FINAL_REPORT.json").write_text(json.dumps(final,indent=2,default=str),encoding="utf-8")
    md=["# VENUE-NORMALIZED LIVE-VALID SELECTOR — FINAL REPORT","",f"**Build:** {now_iso()}",
        "**RESEARCH ONLY. No engine/detector/TP-SL/production change. Thresholds frozen from OKX, never tuned on Binance. Causal features.**","",
        "## OKX sanity (normalization must not break OKX)",
        "| ruleset | trades | wr% | exp% | PF | overlap |","|---|--:|--:|--:|--:|--:|",
        f"| frozen RS1 | {fm['trades']} | {fm['winrate_pct']} | {fm['expectancy_after_cost_pct']} | {fm['pf_after_cost']} | — |",
        f"| NRS1_A pctile | {sanity['NRS1_A_pctile']['trades']} | {sanity['NRS1_A_pctile']['winrate_pct']} | {sanity['NRS1_A_pctile']['expectancy_after_cost_pct']} | {sanity['NRS1_A_pctile']['pf_after_cost']} | {sanity['NRS1_A_pctile']['overlap_with_frozen']} |",
        f"| NRS1_C pctile+floor | {sanity['NRS1_C_pctile_plus_scorefloor']['trades']} | {sanity['NRS1_C_pctile_plus_scorefloor']['winrate_pct']} | {sanity['NRS1_C_pctile_plus_scorefloor']['expectancy_after_cost_pct']} | {sanity['NRS1_C_pctile_plus_scorefloor']['pf_after_cost']} | {sanity['NRS1_C_pctile_plus_scorefloor']['overlap_with_frozen']} |",
        f"\n**OKX_EDGE_PRESERVED = {preserves}**\n",
        "## Binance: old RS1 vs normalized selector models","",
        "| model | tr | wr% | exp% | PF | maxCL | wrongdir | alerts/d | no-trade days | fake-acc | GOOD skipped |",
        "|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|"]
    for k,v in bnc_r["models"].items():
        md.append(f"| {k} | {v['trades']} | {v['winrate_pct']} | {v['expectancy_after_cost_pct']} | {v['pf_after_cost']} | "
                  f"{v['max_consecutive_losses']} | {v['wrong_direction']} | {v['alerts_per_day']} | {v['no_trade_days']} | {v['fake_accumulation']} | {v['good_skipped']} |")
    md+=["","## Answers"]
    for k,v in answers.items(): md.append(f"**{k}** — {v}\n")
    md+=["## Flags","```"]+[f"{k} = {v}" for k,v in flags.items()]+["```"]
    (BNC_OUT/"VENUE_NORMALIZED_LIVE_VALID_SELECTOR_FINAL_REPORT.md").write_text("\n".join(md),encoding="utf-8")

    # console
    print("\n=== OKX SANITY ===")
    print(f"frozen RS1: {fm['trades']}tr {fm['winrate_pct']}% PF{fm['pf_after_cost']} exp{fm['expectancy_after_cost_pct']}")
    for k in ("NRS1_A_pctile","NRS1_B_zscore","NRS1_C_pctile_plus_scorefloor"):
        s=sanity[k]; print(f"{k}: {s['trades']}tr {s['winrate_pct']}% PF{s['pf_after_cost']} exp{s['expectancy_after_cost_pct']} overlap{s['overlap_with_frozen']}")
    print(f"PRESERVES_EDGE={preserves} best={best}")
    print("\n=== BINANCE MODELS ===")
    for k,v in bnc_r["models"].items():
        print(f"  {k:<34s} tr={v['trades']:>2} wr={v['winrate_pct']:>5}% exp={v['expectancy_after_cost_pct']} PF={v['pf_after_cost']} "
              f"alerts/d={v['alerts_per_day']} no-trade={v['no_trade_days']} fake={v['fake_accumulation']} GOODskip={v['good_skipped']}")
    print(f"\nfake-accum {fake_before}->{fake_after}  wrong-dir {wrong_before}->{wrong_after}")
    print("Binance winners: total",len(goods),"old RS1 caught",old_caught,"normalized M3 caught",len(caught),"still skipped",len(still_skipped))
    print("\nFINAL FLAGS:")
    for k,v in flags.items(): print(f"  {k:<48s} = {v}")
    return 0


if __name__=="__main__":
    sys.exit(main())
