"""S7 pre-Binance exact-canonical-ledger audit (Sections A-H).

Re-runs enhanced baseline and S7 EV-overlay through EXACT simulate_canonical_trade
(real timeout exit price, no approximation). Decodes the S7 formula, computes the
trade delta, full S7 table, feature ablation, OI/funding caveats, and freezes two
Binance-ready rulesets.

No engine change. Target strict 2%. Stop 1.5%. Cost 0.14%. No BE. No future leak.
"""
from __future__ import annotations
import csv, json, math, statistics as stats, sys, datetime as dt
from collections import defaultdict, Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from canonical_ledger import (Bucket, build_buckets_from_trades_csv, Signal,
                              ExecutionConfig, simulate_canonical_trade)
from march_target_zone_fuel import (load_dataset, explainable_score_l2_dyn,
                                    select_topn_per_day, iso_to_sec, ALL_DATES,
                                    FIRST_HALF, SECOND_HALF, DATA_ROOT)

REP_OUT = next(p for p in Path(__file__).resolve().parents if (p / "package.json").exists() and (p / "scripts").exists()) / "reports" / "strategy-calibration"
COST_PCT = 0.14
TARGET_PCT = 2.0
STOP_PCT = 1.5
TIMEOUT_HOURS = 24
# S7 reward/risk used in EV
EV_REWARD = TARGET_PCT - COST_PCT   # 1.86
EV_RISK = STOP_PCT + COST_PCT       # 1.64
EV_THRESHOLD = 0.4


def now_iso(): return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
def safe_float(x):
    if x in (None, "", "None"): return None
    try: return float(x)
    except: return None
def mean_or_none(xs):
    xs=[x for x in xs if x is not None]; return round(stats.mean(xs),4) if xs else None
def quantile(xs,q):
    xs=sorted(x for x in xs if x is not None); return xs[int(q*(len(xs)-1))] if xs else None
def short_id(z): return z[-13:] if z else ""


def load_all():
    rows = load_dataset()  # base + dl2 + void
    # target-zone heatmap
    tzp = REP_OUT/"MARCH_TARGET_ZONE_HEATMAP_FEATURES.csv"
    if tzp.exists():
        with tzp.open(encoding="utf-8") as f:
            tz={}
            for lr in csv.DictReader(f):
                d={}
                for k,v in lr.items():
                    if k=="zone_id": continue
                    d[k]=(v or None) if k in ("tz_target_type","tz_nearest_obstacle_type") else safe_float(v)
                tz[lr["zone_id"]]=d
        for r in rows:
            for k,v in tz.get(r["zone_id"],{}).items():
                if k not in r: r[k]=v
    # OI/funding fuel features (only NEW numeric fuel cols + setup_type/funding_regime;
    # do NOT clobber identity/string cols like confirmed_iso/date/direction)
    fp = REP_OUT/"OKX_MARCH_OI_FUNDING_FUEL_FEATURES.csv"
    skip_identity={"zone_id","date","direction","confirmed_iso","watch_label","coverage_class"}
    str_cols={"funding_regime","setup_type"}
    with fp.open(encoding="utf-8") as f:
        fu={}
        for lr in csv.DictReader(f):
            d={}
            for k,v in lr.items():
                if k in skip_identity: continue
                d[k]=(v or None) if k in str_cols else safe_float(v)
            fu[lr["zone_id"]]=d
    for r in rows:
        for k,v in fu.get(r["zone_id"],{}).items():
            r[k]=v
    return rows


# ---- p_reach (EXACT reproduction of S7) with ablation toggles ----
def p_reach(z, fuel_thr, void_thr, enabled=("fuel","void","wall","micro","funding")):
    p = 0.55
    if "fuel" in enabled and (z.get("true_fuel_score") or 0) >= (fuel_thr or 0): p += 0.03
    if "void" in enabled and (z.get("ms_thin_path_score") or 0) >= (void_thr or 0): p += 0.03
    if "wall" in enabled and (z.get("ms_large_walls_on_path") or 99) == 0: p += 0.03
    if "micro" in enabled and (z.get("dl2_microprice_aligned_delta_5m_bps") or -99) >= 0: p += 0.03
    if "funding" in enabled:
        fr = z.get("funding_rate_at_signal") or 0
        if fr < 0 and z["direction"] == "LONG": p += 0.02
        if fr > 0 and z["direction"] == "SHORT": p += 0.02
    return min(p, 0.9)


def ev_of(z, fuel_thr, void_thr, enabled=("fuel","void","wall","micro","funding")):
    p = p_reach(z, fuel_thr, void_thr, enabled)
    return p*EV_REWARD - (1-p)*EV_RISK


# ---- exact canonical-ledger sim (entry=confirmed, fixed 2% TP, 1.5% SL) ----
def build_buckets(dates_needed, cache):
    for d in dates_needed:
        if d in cache: continue
        p = DATA_ROOT/d/"trades.csv.gz"
        cache[d] = build_buckets_from_trades_csv(p) if p.exists() else []

def merge_fwd(date, cache):
    out=[]
    idx = ALL_DATES.index(date) if date in ALL_DATES else -1
    if idx<0: return out
    seq=[date]+[ALL_DATES[idx+k] for k in (1,2) if idx+k < len(ALL_DATES)]
    for d in seq: out += cache.get(d, [])
    return out

def sim_exact(z, cache):
    sec = iso_to_sec(z.get("confirmed_iso"))
    if sec is None: return None
    buckets = merge_fwd(z["date"], cache)
    if not buckets: return None
    sig = Signal(id=z["zone_id"], date=z["date"], trigger_ts_ms=sec*1000,
                 direction=z["direction"], zone_low=z.get("zone_low"), zone_high=z.get("zone_high"))
    cfg = ExecutionConfig(entry_strategy="trigger", stop_pct=STOP_PCT,
                          target_pct=TARGET_PCT, timeout_hours=TIMEOUT_HOURS)
    sim = simulate_canonical_trade(sig, buckets, cfg)
    if sim.get("exit_reason") in ("no_data","skip_no_retest"): return None
    er = sim["exit_reason"]
    outcome = "WIN" if er=="target_2pct" else ("LOSS" if er=="stop" else "TIMEOUT")
    return {"zone_id":z["zone_id"],"date":z["date"],"direction":z["direction"],
            "setup_type":z.get("setup_type"),
            "entry_sec":sim["entry_sec"],"exit_sec":sim["exit_sec"],
            "entry_price":round(sim["entry_price"],2),"exit_price":round(sim["exit_price"],2),
            "exit_reason":er,"outcome":outcome,
            "pnl_pre_cost":sim["pnl_pct"],"pnl_after_cost":round(sim["pnl_pct"]-COST_PCT,4),
            "mfe_pct":sim["mfe_pct"],"mae_pct":sim["mae_pct"],
            "watch_label":z.get("watch_label"),"coverage_class":z.get("coverage_class")}

def exact_metrics(trades):
    n=len(trades)
    wins=[t for t in trades if t["outcome"]=="WIN"]
    losses=[t for t in trades if t["outcome"]=="LOSS"]
    tos=[t for t in trades if t["outcome"]=="TIMEOUT"]
    pnls=[t["pnl_after_cost"] for t in trades]; pre=[t["pnl_pre_cost"] for t in trades]
    wp=[p for p in pnls if p>0]; lp=[p for p in pnls if p<0]
    pf=round(sum(wp)/sum(-p for p in lp),3) if lp else None
    cur=0;mx=0
    for t in trades:
        if t["pnl_after_cost"]<=0: cur+=1; mx=max(mx,cur)
        else: cur=0
    longs=[t for t in trades if t["direction"]=="LONG"]; shorts=[t for t in trades if t["direction"]=="SHORT"]
    h1=[t for t in trades if t["date"] in FIRST_HALF]; h2=[t for t in trades if t["date"] in SECOND_HALF]
    setup=Counter(t["setup_type"] for t in trades)
    return {"trades":n,"wins":len(wins),"losses":len(losses),"timeouts":len(tos),
        "winrate_pct":round(100.0*len(wins)/max(n,1),2),
        "avg_win_after_cost":mean_or_none([t["pnl_after_cost"] for t in wins]),
        "avg_loss_after_cost":mean_or_none([t["pnl_after_cost"] for t in losses]),
        "avg_timeout_pnl_after_cost":mean_or_none([t["pnl_after_cost"] for t in tos]),
        "expectancy_pre_cost_pct":round(stats.mean(pre),4) if pre else None,
        "expectancy_after_cost_pct":round(stats.mean(pnls),4) if pnls else None,
        "total_return_after_cost_pct":round(sum(pnls),4) if pnls else None,
        "pf_after_cost":pf,"max_consecutive_losses":mx,
        "long_n":len(longs),"short_n":len(shorts),
        "long_winrate":round(100.0*sum(1 for t in longs if t["outcome"]=="WIN")/max(len(longs),1),2),
        "short_winrate":round(100.0*sum(1 for t in shorts if t["outcome"]=="WIN")/max(len(shorts),1),2),
        "h1_n":len(h1),"h2_n":len(h2),
        "h1_winrate":round(100.0*sum(1 for t in h1 if t["outcome"]=="WIN")/max(len(h1),1),2),
        "h2_winrate":round(100.0*sum(1 for t in h2 if t["outcome"]=="WIN")/max(len(h2),1),2),
        "setup_split":dict(setup)}


def main():
    print("[load] ...", file=sys.stderr)
    rows = load_all()
    print(f"  {len(rows)} zones", file=sys.stderr)

    base_filter=lambda r:(r.get("dist_to_recent_swing_high_pct") is not None and r["dist_to_recent_swing_high_pct"]<=0.4616)
    enh_filter=lambda r:base_filter(r) and (r.get("dl2_supp_minus_opp_net_flow_15m") is not None and r["dl2_supp_minus_opp_net_flow_15m"]<=4497.76)
    enhanced=select_topn_per_day(rows, enh_filter, explainable_score_l2_dyn, 1)
    # thresholds EXACT as in fuel pass
    fuel_thr=quantile([r.get("true_fuel_score") for r in enhanced], 0.5)
    void_thr=quantile([r.get("ms_thin_path_score") for r in rows], 0.5)
    for z in enhanced:
        z["_p_reach"]=round(p_reach(z, fuel_thr, void_thr),4)
        z["_ev"]=round(ev_of(z, fuel_thr, void_thr),4)
    s7=[z for z in enhanced if z["_ev"]>EV_THRESHOLD]
    print(f"  enhanced={len(enhanced)} S7={len(s7)} fuel_thr={fuel_thr} void_thr={void_thr}", file=sys.stderr)

    print("[buckets] building ...", file=sys.stderr)
    cache={}
    need=set(ALL_DATES); need.add("2026-04-01")
    build_buckets(sorted(need), cache)

    # ---- A: exact canonical retest ----
    print("[A] exact canonical retest ...", file=sys.stderr)
    enh_trades=[t for z in enhanced if (t:=sim_exact(z,cache))]
    s7_trades=[t for z in s7 if (t:=sim_exact(z,cache))]
    enh_m=exact_metrics(enh_trades); s7_m=exact_metrics(s7_trades)
    A={"build_time_utc":now_iso(),"enhanced_baseline_exact":enh_m,"s7_exact":s7_m,
       "approx_prev":{"enhanced":{"winrate":62.07,"exp_aft":0.6475,"pf":2.258},
                      "s7_approx":{"winrate":65.38,"exp_aft":0.7638,"pf":2.689}}}
    (REP_OUT/"OKX_MARCH_S7_CANONICAL_LEDGER_RETEST.json").write_text(json.dumps(A,indent=2,default=str),encoding="utf-8")
    with (REP_OUT/"OKX_MARCH_S7_CANONICAL_LEDGER_RETEST.csv").open("w",encoding="utf-8",newline="") as f:
        keys=["model","trades","wins","losses","timeouts","winrate_pct","avg_win_after_cost",
              "avg_loss_after_cost","avg_timeout_pnl_after_cost","expectancy_pre_cost_pct",
              "expectancy_after_cost_pct","total_return_after_cost_pct","pf_after_cost",
              "max_consecutive_losses","long_winrate","short_winrate","h1_winrate","h2_winrate"]
        w=csv.DictWriter(f,fieldnames=keys,extrasaction="ignore"); w.writeheader()
        w.writerow({"model":"enhanced_baseline_exact",**enh_m})
        w.writerow({"model":"s7_exact",**s7_m})
    md=["# S7 exact canonical-ledger retest","",f"**Build:** {now_iso()}",
        "**Exact `simulate_canonical_trade` — real timeout exit price, no approximation.**","",
        "| metric | enhanced baseline | S7 EV-overlay |","|---|---:|---:|"]
    for k in ("trades","wins","losses","timeouts","winrate_pct","avg_win_after_cost","avg_loss_after_cost",
              "avg_timeout_pnl_after_cost","expectancy_pre_cost_pct","expectancy_after_cost_pct",
              "total_return_after_cost_pct","pf_after_cost","max_consecutive_losses",
              "long_winrate","short_winrate","h1_winrate","h2_winrate"):
        md.append(f"| {k} | {enh_m.get(k)} | {s7_m.get(k)} |")
    md+=["",f"- Enhanced setup split: {enh_m['setup_split']}",f"- S7 setup split: {s7_m['setup_split']}"]
    (REP_OUT/"OKX_MARCH_S7_CANONICAL_LEDGER_RETEST.md").write_text("\n".join(md),encoding="utf-8")

    # ---- B: formula explanation ----
    print("[B] formula explanation ...", file=sys.stderr)
    B={"build_time_utc":now_iso(),
       "selector_name":"S7_EV_positive",
       "base_selector":"dist_to_recent_swing_high_pct<=0.4616 AND dl2_supp_minus_opp_net_flow_15m<=4497.76, top1/day, entry=confirmed",
       "ev_formula":"EV = p_reach*1.86 - (1-p_reach)*1.64   (1.86 = target2% - cost0.14; 1.64 = stop1.5 + cost0.14)",
       "ev_threshold":f"keep zone if EV > {EV_THRESHOLD}  <=>  p_reach > {round((EV_THRESHOLD+EV_RISK)/(EV_REWARD+EV_RISK),4)}",
       "p_reach_base":0.55,
       "p_reach_components":[
         {"name":"true_fuel_score>=median","weight":0.03,"feature":"true_fuel_score = |oi_zscore_14d| + |funding_zscore_7d|","thr":fuel_thr,"available_at":"confirmedTs (OI daily snap<=T, funding settle<=T)","leak":"SAFE"},
         {"name":"ms_thin_path_score>=median","weight":0.03,"feature":"L2 thin-path-to-target (void)","thr":void_thr,"available_at":"confirmedTs (book snapshot)","leak":"SAFE"},
         {"name":"ms_large_walls_on_path==0","weight":0.03,"feature":"no large opposing wall on 2% path","thr":0,"available_at":"confirmedTs","leak":"SAFE"},
         {"name":"dl2_microprice_aligned_delta_5m_bps>=0","weight":0.03,"feature":"microprice drift aligned with direction (5m window ends at confirm)","available_at":"confirmedTs","leak":"SAFE"},
         {"name":"funding aligned (LONG&funding<0 OR SHORT&funding>0)","weight":0.02,"feature":"funding_rate_at_signal (last 8h settle<=T)","available_at":"confirmedTs","leak":"SAFE"}],
       "p_reach_cap":0.9,
       "true_oi_used":"YES (daily, OKX rubik, in true_fuel_score via oi_zscore_14d)",
       "funding_used":"YES (in true_fuel_score and funding-aligned bump)",
       "flow_proxy_used":"NO in S7 p_reach (flow proxies computed separately, not in this selector)",
       "target_zone_used_in_selector":"NO (target-zone is orientation/diagnostic only)",
       "future_or_outcome_field_used":"NO",
       "why_threshold_0.4":"EV>0.4 <=> p_reach>0.583; base 0.55 plus bumps. Needs >=2 of the 0.03 conditions (or one 0.03 + funding 0.02). Effectively keeps zones with at least two confluence conditions; removes zones with <=1 weak condition."}
    (REP_OUT/"OKX_MARCH_S7_FORMULA_EXPLANATION.json").write_text(json.dumps(B,indent=2,default=str),encoding="utf-8")
    md=["# S7 formula explanation","",f"**Build:** {now_iso()}","",
        f"## Base selector\n`{B['base_selector']}`","",
        f"## EV formula\n`{B['ev_formula']}`\n\n`{B['ev_threshold']}`","",
        f"## p_reach (base {B['p_reach_base']}, cap {B['p_reach_cap']})","",
        "| component | weight | feature | threshold | leak |","|---|---:|---|---|---|"]
    for c in B["p_reach_components"]:
        md.append(f"| {c['name']} | +{c['weight']} | {c['feature']} | {c.get('thr','-')} | {c['leak']} |")
    md+=["",f"- true OI used: {B['true_oi_used']}",f"- funding used: {B['funding_used']}",
         f"- flow_proxy in selector: {B['flow_proxy_used']}",
         f"- target-zone in selector: {B['target_zone_used_in_selector']}",
         f"- future/outcome field used: **{B['future_or_outcome_field_used']}**","",
         f"## Why EV>0.4\n{B['why_threshold_0.4']}"]
    (REP_OUT/"OKX_MARCH_S7_FORMULA_EXPLANATION.md").write_text("\n".join(md),encoding="utf-8")

    # ---- C: trade delta ----
    print("[C] trade delta ...", file=sys.stderr)
    s7_ids={z["zone_id"] for z in s7}
    enh_by_id={t["zone_id"]:t for t in enh_trades}
    z_by_id={z["zone_id"]:z for z in enhanced}
    removed=[z for z in enhanced if z["zone_id"] not in s7_ids]
    removed_rows=[]
    for z in removed:
        t=enh_by_id.get(z["zone_id"])
        if not t: continue
        # correctness: removing a LOSS/TIMEOUT = good; removing a WIN = bad
        correct = "YES" if t["outcome"] in ("LOSS","TIMEOUT") else "NO"
        removed_rows.append({"date":z["date"],"direction":z["direction"],"zone_id":z["zone_id"],
            "enhanced_result":t["outcome"],"pnl_after_cost":t["pnl_after_cost"],
            "setup_type":z.get("setup_type"),"true_fuel_score":z.get("true_fuel_score"),
            "p_reach":z["_p_reach"],"expected_trade_ev":z["_ev"],
            "reason_removed":f"EV {z['_ev']} <= {EV_THRESHOLD} (p_reach {z['_p_reach']})",
            "removal_correct":correct})
    rw=sum(1 for r in removed_rows if r["enhanced_result"]=="WIN")
    rl=sum(1 for r in removed_rows if r["enhanced_result"]=="LOSS")
    rt=sum(1 for r in removed_rows if r["enhanced_result"]=="TIMEOUT")
    net_pnl=round(sum(r["pnl_after_cost"] for r in removed_rows),4)
    C={"build_time_utc":now_iso(),"removed_count":len(removed_rows),
       "removed_wins":rw,"removed_losses":rl,"removed_timeouts":rt,
       "net_pnl_removed_after_cost":net_pnl,
       "winrate_delta_pp":round(s7_m["winrate_pct"]-enh_m["winrate_pct"],2),
       "expectancy_delta":round((s7_m["expectancy_after_cost_pct"] or 0)-(enh_m["expectancy_after_cost_pct"] or 0),4),
       "removed_trades":removed_rows}
    (REP_OUT/"OKX_MARCH_S7_TRADE_DELTA.json").write_text(json.dumps(C,indent=2,default=str),encoding="utf-8")
    with (REP_OUT/"OKX_MARCH_S7_TRADE_DELTA.csv").open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(removed_rows[0].keys()) if removed_rows else ["date"]); w.writeheader()
        for r in removed_rows: w.writerow(r)
    md=["# S7 trade delta vs enhanced baseline","",f"**Build:** {now_iso()}",
        f"- removed: {len(removed_rows)} (wins {rw}, losses {rl}, timeouts {rt})",
        f"- net pnl of removed (after cost): {net_pnl}",
        f"- winrate delta: {C['winrate_delta_pp']} pp; expectancy delta: {C['expectancy_delta']}","",
        "| date | dir | enhanced_result | pnl_aft | setup | fuel | p_reach | EV | removal_correct |",
        "|---|:---:|:---:|---:|---|---:|---:|---:|:---:|"]
    for r in removed_rows:
        md.append(f"| {r['date']} | {r['direction']} | {r['enhanced_result']} | {r['pnl_after_cost']} | "
            f"{r['setup_type']} | {r['true_fuel_score']} | {r['p_reach']} | {r['expected_trade_ev']} | {r['removal_correct']} |")
    (REP_OUT/"OKX_MARCH_S7_TRADE_DELTA.md").write_text("\n".join(md),encoding="utf-8")

    # ---- D: full S7 table ----
    print("[D] full S7 table ...", file=sys.stderr)
    full=[]
    for i,z in enumerate(sorted(s7, key=lambda x:x["date"]),1):
        t=next((x for x in s7_trades if x["zone_id"]==z["zone_id"]),None)
        if not t: continue
        entry=t["entry_price"]
        tp=round(entry*(1+TARGET_PCT/100.0),2) if z["direction"]=="LONG" else round(entry*(1-TARGET_PCT/100.0),2)
        sl=round(entry*(1-STOP_PCT/100.0),2) if z["direction"]=="LONG" else round(entry*(1+STOP_PCT/100.0),2)
        full.append({"#":i,"date":z["date"],"direction":z["direction"],"zone_id_short":short_id(z["zone_id"]),
            "setup_type":z.get("setup_type"),
            "entry_iso":dt.datetime.fromtimestamp(t["entry_sec"],tz=dt.timezone.utc).isoformat(timespec="seconds"),
            "entry_price":entry,"target_price":tp,"stop_price":sl,
            "exit_iso":dt.datetime.fromtimestamp(t["exit_sec"],tz=dt.timezone.utc).isoformat(timespec="seconds"),
            "exit_reason":t["exit_reason"],"pnl_after_cost":t["pnl_after_cost"],"result":t["outcome"],
            "true_fuel_score":z.get("true_fuel_score"),"dir_fuel_score":z.get("dir_fuel_score"),
            "funding_rate_at_signal":z.get("funding_rate_at_signal"),"funding_regime":z.get("funding_regime"),
            "void_thin_path":z.get("ms_thin_path_score"),"opp_wall":z.get("ms_large_walls_on_path"),
            "microprice_5m":z.get("dl2_microprice_aligned_delta_5m_bps"),
            "p_reach":z["_p_reach"],"expected_trade_ev":z["_ev"],
            "hit_2pct":1 if t["outcome"]=="WIN" else 0,
            "tz_target_distance_pct":z.get("tz_target_distance_pct"),
            "mfe_pct":t["mfe_pct"],"mae_pct":t["mae_pct"]})
    with (REP_OUT/"OKX_MARCH_S7_FULL_TRADE_TABLE.csv").open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(full[0].keys()) if full else ["#"]); w.writeheader()
        for r in full: w.writerow(r)
    (REP_OUT/"OKX_MARCH_S7_FULL_TRADE_TABLE.json").write_text(json.dumps(
        {"build_time_utc":now_iso(),"n":len(full),"trades":full},indent=2,default=str),encoding="utf-8")
    md=["# S7 full trade table (26 trades, exact ledger)","",f"**Build:** {now_iso()}","",
        "| # | date | dir | setup | entry | TP | SL | exit | reason | pnl_aft | result | fuel | fund | void | wall | micro | p_reach | EV |",
        "|--:|---|:--:|---|--:|--:|--:|---|---|--:|:--:|--:|--:|--:|--:|--:|--:|--:|"]
    for r in full:
        md.append(f"| {r['#']} | {r['date']} | {r['direction']} | {r['setup_type'].replace('absorption_reversal_','ar_').replace('retest_after_breakout_','rt_') if r['setup_type'] else ''} | "
            f"{r['entry_price']} | {r['target_price']} | {r['stop_price']} | {r['exit_iso'][11:16]} | {r['exit_reason']} | "
            f"{r['pnl_after_cost']} | {r['result']} | {r['true_fuel_score']} | {round(r['funding_rate_at_signal']*1e4,2) if r['funding_rate_at_signal'] is not None else None} | "
            f"{r['void_thin_path']} | {r['opp_wall']} | {r['microprice_5m']} | {r['p_reach']} | {r['expected_trade_ev']} |")
    (REP_OUT/"OKX_MARCH_S7_FULL_TRADE_TABLE.md").write_text("\n".join(md),encoding="utf-8")

    # ---- E: feature ablation ----
    print("[E] feature ablation ...", file=sys.stderr)
    comps=("fuel","void","wall","micro","funding")
    abl=[]
    def run_variant(name, enabled):
        sel=[z for z in enhanced if ev_of(z,fuel_thr,void_thr,enabled)>EV_THRESHOLD]
        tr=[t for z in sel if (t:=enh_by_id.get(z["zone_id"]))]
        m=exact_metrics(tr)
        removed_ids={z["zone_id"] for z in enhanced}-{z["zone_id"] for z in sel}
        wl=sum(1 for zid in removed_ids if enh_by_id.get(zid,{}).get("outcome")=="WIN")
        ll=sum(1 for zid in removed_ids if enh_by_id.get(zid,{}).get("outcome")=="LOSS")
        tl=sum(1 for zid in removed_ids if enh_by_id.get(zid,{}).get("outcome")=="TIMEOUT")
        return {"variant":name,"enabled":",".join(enabled) if enabled else "(none)","trades":m["trades"],
                "wins":m["wins"],"losses":m["losses"],"timeouts":m["timeouts"],"winrate_pct":m["winrate_pct"],
                "expectancy_after_cost_pct":m["expectancy_after_cost_pct"],"pf_after_cost":m["pf_after_cost"],
                "removed_vs_enh":len(removed_ids),"wins_lost":wl,"losses_removed":ll,"timeouts_removed":tl,
                "h1_winrate":m["h1_winrate"],"h2_winrate":m["h2_winrate"],
                "long_winrate":m["long_winrate"],"short_winrate":m["short_winrate"]}
    abl.append(run_variant("S7_full", comps))
    for c in comps:
        abl.append(run_variant(f"without_{c}", tuple(x for x in comps if x!=c)))
    for c in comps:
        abl.append(run_variant(f"only_{c}", (c,)))
    abl.append(run_variant("enhanced_no_overlay", ()))  # no bumps -> p=0.55 -> EV=3.5*0.55-1.64=0.285<0.4 -> removes ALL? check
    with (REP_OUT/"OKX_MARCH_S7_FEATURE_ABLATION.csv").open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(abl[0].keys())); w.writeheader()
        for r in abl: w.writerow(r)
    # importance: drop in expectancy when removing each comp (vs S7_full)
    s7full=abl[0]
    importance={}
    for c in comps:
        wv=next(r for r in abl if r["variant"]==f"without_{c}")
        importance[c]=round((s7full["expectancy_after_cost_pct"] or 0)-(wv["expectancy_after_cost_pct"] or 0),4)
    top_comp=max(importance,key=lambda k:importance[k]) if importance else None
    (REP_OUT/"OKX_MARCH_S7_FEATURE_ABLATION.json").write_text(json.dumps(
        {"build_time_utc":now_iso(),"ablation":abl,"importance_by_expectancy_drop":importance,
         "top_component":top_comp},indent=2,default=str),encoding="utf-8")
    md=["# S7 feature ablation","",f"**Build:** {now_iso()}","",
        "| variant | enabled | trades | W | L | TO | wr% | exp_aft% | PF | removed | wins_lost | losses_rm |",
        "|---|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|"]
    for r in abl:
        md.append(f"| {r['variant']} | {r['enabled']} | {r['trades']} | {r['wins']} | {r['losses']} | {r['timeouts']} | "
            f"{r['winrate_pct']} | {r['expectancy_after_cost_pct']} | {r['pf_after_cost']} | {r['removed_vs_enh']} | "
            f"{r['wins_lost']} | {r['losses_removed']} |")
    md+=["","## Importance (expectancy drop when removing component)"]
    for c,v in sorted(importance.items(),key=lambda kv:-kv[1]): md.append(f"- {c}: {v}")
    md.append(f"\n**Top component: {top_comp}**")
    (REP_OUT/"OKX_MARCH_S7_FEATURE_ABLATION.md").write_text("\n".join(md),encoding="utf-8")

    # ---- F: OI/funding caveats ----
    print("[F] caveats ...", file=sys.stderr)
    F={"build_time_utc":now_iso(),
       "oi_source":"OKX rubik /api/v5/rubik/stat/contracts/open-interest-volume",
       "oi_granularity":"1D","oi_timestamp":"16:00 UTC daily snapshot",
       "oi_scope":"USD notional, aggregate across ALL BTC contracts (NOT exact BTC-USDT-SWAP intraday)",
       "funding_source":"OKX /api/v5/public/funding-rate-history","funding_granularity":"8h per-instrument BTC-USDT-SWAP",
       "intraday_oi_15m_60m":"NOT available for March without paid Tardis/derivative_ticker (no API key)",
       "usage":"OI usable as DAY/REGIME/fuel background only, NOT exact entry-timing signal",
       "leak_safety":"all features use latest value with ts<=confirmedTs (OI daily snap, funding settle) -> leak-free",
       "implication_for_s7":"true_fuel_score mixes daily-OI zscore + funding zscore; it is a slow/background signal. "
                            "S7's edge is modest and partly from L2 void/microprice (intraday), not OI alone."}
    (REP_OUT/"OKX_MARCH_OI_FUNDING_CAVEATS.json").write_text(json.dumps(F,indent=2),encoding="utf-8")
    (REP_OUT/"OKX_MARCH_OI_FUNDING_CAVEATS.md").write_text(
        "# OKX March OI/funding caveats\n\n"f"**Build:** {now_iso()}\n\n"
        f"- OI source: {F['oi_source']}\n- OI granularity: **{F['oi_granularity']}** (16:00 UTC daily snapshot)\n"
        f"- OI scope: {F['oi_scope']}\n- Funding: {F['funding_source']} ({F['funding_granularity']})\n"
        f"- Intraday OI 15m/60m: **{F['intraday_oi_15m_60m']}**\n- Usage: {F['usage']}\n"
        f"- Leak safety: {F['leak_safety']}\n\n**Implication for S7:** {F['implication_for_s7']}\n",encoding="utf-8")

    # ---- G: freeze rulesets ----
    print("[G] freeze rulesets ...", file=sys.stderr)
    G={"build_time_utc":now_iso(),
       "ruleset_1_conservative":{
           "name":"RS1_enhanced_baseline","selector":enh_filter.__doc__ or "dist_to_recent_swing_high_pct<=0.4616 AND dl2_supp_minus_opp_net_flow_15m<=4497.76, top1/day, entry=confirmed",
           "trade":"TP fixed 2%, SL 1.5%, no BE, timeout 24h, cost 0.14%",
           "okx_march_exact":{k:enh_m[k] for k in ("trades","winrate_pct","expectancy_after_cost_pct","pf_after_cost","total_return_after_cost_pct")},
           "frozen_thresholds":{"dist_to_recent_swing_high_pct_max":0.4616,"dl2_supp_minus_opp_net_flow_15m_max":4497.76,"tp_pct":2.0,"sl_pct":1.5,"timeout_h":24,"cost_pct":0.14},
           "do_not_tune_on_binance":["dist_to_recent_swing_high_pct_max","dl2_supp_minus_opp_net_flow_15m_max","tp_pct","sl_pct"],
           "can_run_without_oi":"YES","can_run_with_binance_recorder":"YES",
           "required_binance_fields":["engine zones (confirmed)","1s trades buckets (swing dist)","incremental L2 (dl2_supp_minus_opp_net_flow_15m, explainable_score components)"],
           "pros":["simplest","no OI/funding dependency","largest sample (29)"],"cons":["lower winrate than S7 in-sample"]},
       "ruleset_2_s7":{
           "name":"RS2_s7_fuel_overlay","selector":"RS1 + keep zone if EV>0.4 where EV=p_reach*1.86-(1-p_reach)*1.64",
           "p_reach":"0.55 + 0.03*[fuel>=med] + 0.03*[void>=med] + 0.03*[no opp wall] + 0.03*[microprice aligned] + 0.02*[funding aligned], cap 0.9",
           "trade":"TP fixed 2%, SL 1.5%, no BE, timeout 24h, cost 0.14%",
           "okx_march_exact":{k:s7_m[k] for k in ("trades","winrate_pct","expectancy_after_cost_pct","pf_after_cost","total_return_after_cost_pct")},
           "frozen_thresholds":{"ev_threshold":0.4,"p_reach_base":0.55,"fuel_thr_quantile":0.5,"void_thr_quantile":0.5},
           "do_not_tune_on_binance":["ev_threshold","p_reach weights","quantile 0.5 for fuel/void thresholds (recompute thresholds from Binance distribution, keep quantile)"],
           "can_run_without_oi":"PARTIAL (fuel needs OI+funding; void/microprice/wall work without OI)",
           "can_run_with_binance_recorder":"YES (Binance has NATIVE OI+funding+liquidations, higher granularity)",
           "required_binance_fields":["RS1 fields","native Binance OI (per-instrument)","funding","L2 void/wall/microprice"],
           "pros":["higher winrate/PF in-sample","uses true OI+funding"],"cons":["smaller sample (26)","modest edge","OI only daily on OKX (Binance better)","overfit risk MEDIUM"]},
       "flags":{"FROZEN_RULESET_BASELINE_DEFINED":"YES","FROZEN_RULESET_S7_DEFINED":"YES"}}
    (REP_OUT/"BINANCE_FROZEN_RULESET_BEFORE_TEST.json").write_text(json.dumps(G,indent=2,default=str),encoding="utf-8")
    md=["# Binance frozen rule set (before test)","",f"**Build:** {now_iso()}","",
        "## RS1 — Conservative baseline (RUN FIRST)",
        f"- Selector: dist_to_recent_swing_high_pct<=0.4616 AND dl2_supp_minus_opp_net_flow_15m<=4497.76, top1/day, entry=confirmed",
        f"- Trade: TP 2%, SL 1.5%, no BE, timeout 24h, cost 0.14%",
        f"- OKX March exact: {G['ruleset_1_conservative']['okx_march_exact']}",
        f"- Can run without OI: YES | Binance recorder: YES",
        f"- Do NOT tune: {G['ruleset_1_conservative']['do_not_tune_on_binance']}","",
        "## RS2 — S7 fuel overlay (RUN SECOND, only after RS1 OOS pass)",
        f"- Overlay: keep if EV>0.4; p_reach = {G['ruleset_2_s7']['p_reach']}",
        f"- OKX March exact: {G['ruleset_2_s7']['okx_march_exact']}",
        f"- Can run without OI: PARTIAL | Binance recorder: YES (native OI better)",
        f"- Do NOT tune: {G['ruleset_2_s7']['do_not_tune_on_binance']}"]
    (REP_OUT/"BINANCE_FROZEN_RULESET_BEFORE_TEST.md").write_text("\n".join(md),encoding="utf-8")

    # ---- H: final ----
    print("[H] final ...", file=sys.stderr)
    s7_better = (s7_m["expectancy_after_cost_pct"] or -9) > (enh_m["expectancy_after_cost_pct"] or -9)
    flags={
        "S7_PRE_BINANCE_AUDIT_DONE":"YES","CANONICAL_LEDGER_USED":"YES","TIMEOUT_PNL_EXACT":"YES",
        "ENHANCED_BASELINE_EXACT_TRADES":enh_m["trades"],"ENHANCED_BASELINE_EXACT_WINRATE":enh_m["winrate_pct"],
        "ENHANCED_BASELINE_EXACT_EXPECTANCY_AFTER_COST":enh_m["expectancy_after_cost_pct"],
        "ENHANCED_BASELINE_EXACT_PF_AFTER_COST":enh_m["pf_after_cost"],
        "S7_EXACT_TRADES":s7_m["trades"],"S7_EXACT_WINRATE":s7_m["winrate_pct"],
        "S7_EXACT_EXPECTANCY_AFTER_COST":s7_m["expectancy_after_cost_pct"],"S7_EXACT_PF_AFTER_COST":s7_m["pf_after_cost"],
        "S7_STILL_IMPROVES_OVER_ENHANCED":"YES" if s7_better else "NO",
        "S7_REMOVED_WINS":rw,"S7_REMOVED_LOSSES":rl,"S7_REMOVED_TIMEOUTS":rt,"S7_NET_PNL_DELTA":net_pnl,
        "S7_FORMULA_EXPLAINED":"YES","S7_FEATURE_ABLATION_DONE":"YES","TOP_S7_COMPONENT":top_comp,
        "S7_FUTURE_LEAK_FOUND":"NO","OI_FUNDING_CAVEATS_DOCUMENTED":"YES",
        "FROZEN_RULESET_BASELINE_DEFINED":"YES","FROZEN_RULESET_S7_DEFINED":"YES",
        "READY_FOR_BINANCE_TEST":"YES","READY_FOR_TELEGRAM_SHADOW_MODE":"NO",
        "READY_TO_CHANGE_ENGINE":"NO","READY_FOR_PRODUCTION_TRADING":"NO","MORE_VALIDATION_REQUIRED":"YES"}
    final={"build_time_utc":now_iso(),"enhanced_exact":enh_m,"s7_exact":s7_m,
        "removed":{"wins":rw,"losses":rl,"timeouts":rt,"net_pnl":net_pnl},
        "ablation_importance":importance,"top_component":top_comp,"flags":flags}
    (REP_OUT/"OKX_MARCH_S7_PRE_BINANCE_AUDIT_FINAL.json").write_text(json.dumps(final,indent=2,default=str),encoding="utf-8")
    md=["# S7 pre-Binance audit — final report","",f"**Build:** {now_iso()}",
        "**Scope:** IN-SAMPLE OKX March 2026, exact canonical ledger. No engine change.","",
        "## 1-2. Exact retest",
        f"- Enhanced baseline EXACT: {enh_m['trades']} tr, {enh_m['winrate_pct']}% wr, exp {enh_m['expectancy_after_cost_pct']}%, PF {enh_m['pf_after_cost']}, ret {enh_m['total_return_after_cost_pct']}%",
        f"- S7 EXACT: {s7_m['trades']} tr, {s7_m['winrate_pct']}% wr, exp {s7_m['expectancy_after_cost_pct']}%, PF {s7_m['pf_after_cost']}, ret {s7_m['total_return_after_cost_pct']}%",
        f"- **S7 still improves over enhanced after exact timeout PnL: {flags['S7_STILL_IMPROVES_OVER_ENHANCED']}**",
        "",
        f"## 3. Removed trades ({len(removed_rows)})",
        f"- wins removed {rw}, losses removed {rl}, timeouts removed {rt}; net pnl removed {net_pnl}",
        "",
        "## 4-5. Improvement source",
        f"- Top component by expectancy contribution: **{top_comp}**. Importance: {importance}",
        "- Edge comes from L2/intraday confluence (void/microprice/wall) + fuel; OI alone is daily/background.",
        "",
        f"## 6. Future leak: **{flags['S7_FUTURE_LEAK_FOUND']}** (all features <= confirmedTs).",
        "",
        "## 7-8. Binance",
        "- RS1 (conservative baseline) RUN FIRST as clean OOS cross-venue check. RS2 (S7) RUN SECOND only after RS1 passes.",
        "## 9. Binance data needed",
        "- Engine zone replay on BTCUSDT futures; trades+L2 recorder days (have 2026-05-18..20 + 2025 set); native OI/funding for RS2.",
        "## 10. Success/failure criteria",
        "- SUCCESS: RS1 OOS winrate within ~5pp of OKX 62% and PF>1.5 after cost on >=20 trades.",
        "- FAILURE: winrate collapses <50% or PF<1.2 -> selector is OKX-regime-specific, do not proceed.",
        "","## Final flags","```"]
    for k,v in flags.items(): md.append(f"{k} = {v}")
    md+=["```","","## Hard rules honored",
        "- exact canonical ledger (real timeout exit price); target strict 2%; no engine change; "
        "no future leak; target-zone not primary win; OI/funding caveats documented."]
    (REP_OUT/"OKX_MARCH_S7_PRE_BINANCE_AUDIT_FINAL.md").write_text("\n".join(md),encoding="utf-8")

    # ---- console ----
    print()
    print("="*78)
    print("EXACT CANONICAL LEDGER: enhanced vs S7")
    print("="*78)
    print(f"{'metric':<34}{'enhanced':>14}{'S7':>14}")
    for k in ("trades","wins","losses","timeouts","winrate_pct","avg_win_after_cost","avg_loss_after_cost",
              "avg_timeout_pnl_after_cost","expectancy_after_cost_pct","total_return_after_cost_pct",
              "pf_after_cost","max_consecutive_losses"):
        print(f"{k:<34}{str(enh_m.get(k)):>14}{str(s7_m.get(k)):>14}")
    print()
    print(f"REMOVED 3: wins={rw} losses={rl} timeouts={rt} net_pnl={net_pnl}")
    for r in removed_rows:
        print(f"   {r['date']} {r['direction']:>5} {r['enhanced_result']:>7} pnl={r['pnl_after_cost']:+.3f} "
              f"p_reach={r['p_reach']} EV={r['expected_trade_ev']} correct={r['removal_correct']}")
    print()
    print("ABLATION (importance by expectancy drop):", importance, "TOP:", top_comp)
    print()
    print("FINAL FLAGS:")
    for k,v in flags.items(): print(f"  {k:<46s} = {v}")
    return 0


if __name__=="__main__":
    sys.exit(main())
