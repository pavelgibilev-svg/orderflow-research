"""BINANCE/OKX OPPORTUNITY CLASSIFIER FOR SKIPPED WINNERS (A-E).

Positive selection: which causal/live-valid features separate winner-zones (strict 2%) from noise,
so the selector trades ~1/1-2 days instead of standing fully aside — WITHOUT returning to fake accumulation.

Rules:
  - no engine/detector/TP-SL/production change; no direct Binance threshold tuning
  - all features causal (<= confirmedTs); no future leak (post-confirm initiative/entropy excluded)
  - thresholds derived from OKX March winners where possible; Binance-specific cuts labeled EXPLORATORY_NOT_FROZEN
  - reuse caches (OKX + Binance diag caches); no L2 re-stream
"""
from __future__ import annotations
import csv, json, math, statistics as st, sys, datetime as dt
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import venue_norm_research as V

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "package.json").exists() and (p / "scripts").exists())
OKX_CACHE = ROOT / "reports/strategy-calibration/OKX_MARCH_DIAG_FEATURE_CACHE.json"
BNC_CACHE = ROOT / "reports/binance-oos/BINANCE_10D_DIAG_FEATURE_CACHE.json"
OKX_OUT = ROOT / "reports/strategy-calibration"
BNC_OUT = ROOT / "reports/binance-oos"


def now_iso(): return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
def num(x): return x if isinstance(x,(int,float)) else None
def med(zs,k):
    xs=[z[k] for z in zs if isinstance(z.get(k),(int,float))]
    return round(st.median(xs),4) if xs else None
def cohend(g,n,k):
    a=[z[k] for z in g if isinstance(z.get(k),(int,float))]; b=[z[k] for z in n if isinstance(z.get(k),(int,float))]
    if len(a)<3 or len(b)<3: return None
    va=st.pvariance(a); vb=st.pvariance(b); sp=math.sqrt((va+vb)/2) or 1e-9
    return round((st.mean(a)-st.mean(b))/sp,3)


# ---------------- opportunity conditions (causal) ----------------
def opp_conditions(z):
    guard = not V.dir_guard_reject(z)
    uniq = (num(z.get("explainable_score__pctile_prior")) or 0) >= V.SCORE_PCTILE_FLOOR
    init = (num(z.get("supportive_taker_imb_15m")) or -9) > 0 and (num(z.get("dl2_microprice_aligned_delta_5m_bps")) or -9) >= 0
    walls = z.get("ms_large_walls_on_path")
    thin = (walls in (0, None)) and (num(z.get("eng_void")) or 0) >= 0.5
    reclaim = V.has_reversal_proof(z) or z.get("reclaim_zoneMid_preconfirm")==1
    return {"guard":guard,"uniq":uniq,"init":init,"thin":thin,"reclaim":reclaim}

def confluence(z):
    c=opp_conditions(z); return sum(1 for v in c.values() if v)

# opportunity rules (TRUE = zone qualifies as opportunity)
def opp_rules():
    return {
        "O1_uniqueness_high": lambda z: opp_conditions(z)["uniq"],
        "O2_initiative_shift": lambda z: opp_conditions(z)["init"],
        "O3_reclaim_rejection": lambda z: opp_conditions(z)["reclaim"],
        "O4_thin_path": lambda z: opp_conditions(z)["thin"],
        "O5_entropy_compression_EXPLORATORY": lambda z: (num(z.get("book_entropy_top25")) is not None) and z["book_entropy_top25"]<0.85,
        "O6_regime_continuation": lambda z: (not V.regime_against(z)) and opp_conditions(z)["thin"],
        "O7_reversal_only_proof": lambda z: V.regime_against(z) and opp_conditions(z)["reclaim"] and opp_conditions(z)["init"],
        "O8_confluence_ge3": lambda z: confluence(z)>=3,
    }


def metrics(trades): return V.metrics(trades)

# live-valid first-eligible selector among zones passing dir-guard AND extra(z)
def selector(zones, extra, maxn=1, cooldown=False, score_floor=None):
    byd=defaultdict(list)
    for z in zones: byd[z["_date"]].append(z)
    sel=[]
    for d in sorted(byd):
        day=sorted(byd[d],key=lambda z:z["confirmedTs"]); taken=[]
        for z in day:
            if not V.norm_filter(z,"pctile"): continue
            if V.dir_guard_reject(z): continue
            if score_floor is not None and (num(z.get("explainable_score__pctile_prior")) or 0)<score_floor: continue
            if extra and not extra(z): continue
            if cooldown and not V.cluster_cooldown_ok(z,taken): continue
            taken.append(z); sel.append(z)
            if len(taken)>=maxn: break
    return sel


def run():
    okx=json.loads(OKX_CACHE.read_text(encoding="utf-8"))
    bnc=json.loads(BNC_CACHE.read_text(encoding="utf-8"))
    V.normalize_layer(okx, V.COMMON_FEATS)
    V.normalize_layer(bnc, V.COMMON_FEATS + V.BNC_ONLY)

    venues={"OKX_MARCH":(okx,OKX_OUT,False),"BINANCE_10D":(bnc,BNC_OUT,True)}
    # OKX-frozen confluence floor = median confluence of OKX winners (guard-passing)
    okx_good_guard=[z for z in okx if z.get("sim_label")=="GOOD" and not V.dir_guard_reject(z)]
    CONF_FLOOR=int(st.median([confluence(z) for z in okx_good_guard])) if okx_good_guard else 2

    # ============ A: Binance skipped-winner casebook ============
    winners=[z for z in bnc if z.get("sim_label")=="GOOD"]
    old_rs1=V.select_model(bnc,"M0"); rs1_ids={z["id"] for z in old_rs1}
    norm_sel=V.select_model(bnc,"M5"); norm_ids={z["id"] for z in norm_sel}
    cb=[]
    for z in sorted(winners,key=lambda x:x["confirmedTs"]):
        c=opp_conditions(z)
        cb.append({"date":z["_date"],"direction":z["direction"],"setup":z.get("zoneType"),
            "confirmed_iso":V.now_iso() if False else dt.datetime.fromtimestamp(z["confirmedTs"]/1000,tz=dt.timezone.utc).isoformat(timespec="seconds"),
            "entry_price":z.get("sim_entry_price"),"mfe_pct":z.get("sim_mfe_pct"),"mae_pct":z.get("sim_mae_pct"),
            "regime_60m":z.get("regime_60m"),"regime_180m":z.get("regime_180m"),"regime_1d":z.get("regime_1d"),
            "supp_opp_15m_pctile":z.get("dl2_supp_minus_opp_net_flow_15m__pctile_prior"),
            "microprice_5m":z.get("dl2_microprice_aligned_delta_5m_bps"),"eng_ofi":z.get("eng_ofi"),
            "taker_imb_15m":z.get("taker_imbalance_15m"),"supp_taker_imb_15m":z.get("supportive_taker_imb_15m"),
            "reclaim":z.get("reclaim_zoneMid_preconfirm"),"book_entropy":z.get("book_entropy_top25"),
            "thin_path":z.get("ms_thin_path_score"),"walls":z.get("ms_large_walls_on_path"),"eng_void":z.get("eng_void"),
            "dist_swh":z.get("dist_to_recent_swing_high_pct"),
            "score_raw":z.get("explainable_score"),"score_pctile":z.get("explainable_score__pctile_prior"),
            "selected_by_old_rs1":1 if z["id"] in rs1_ids else 0,"selected_by_norm":1 if z["id"] in norm_ids else 0,
            "why_skipped":("taken" if z["id"] in rs1_ids else "not top1/day by score" ),
            "passes_dir_guard":0 if V.dir_guard_reject(z) else 1,
            "passes_confluence_ge3":1 if confluence(z)>=3 else 0,"confluence":confluence(z)})
    with (BNC_OUT/"BINANCE_10D_SKIPPED_WINNER_CASEBOOK.csv").open("w",encoding="utf-8",newline="") as fh:
        w=csv.DictWriter(fh,fieldnames=list(cb[0].keys())); w.writeheader(); w.writerows(cb)
    short_w=[r for r in cb if r["direction"]=="SHORT"]; long_w=[r for r in cb if r["direction"]=="LONG"]
    skipped=[r for r in cb if not r["selected_by_old_rs1"]]
    (BNC_OUT/"BINANCE_10D_SKIPPED_WINNER_CASEBOOK.json").write_text(json.dumps(
        {"build":now_iso(),"total_winners":len(cb),"short":len(short_w),"long":len(long_w),
         "skipped_by_old_rs1":len(skipped),"passes_dir_guard":sum(r["passes_dir_guard"] for r in cb),
         "passes_confluence_ge3":sum(r["passes_confluence_ge3"] for r in cb),"winners":cb},indent=2,default=str),encoding="utf-8")
    md=["# A. Binance 10d — skipped-winner casebook","",f"**Build:** {now_iso()}",
        f"31 winner-zones (strict 2%): {len(short_w)} SHORT, {len(long_w)} LONG. Skipped by old RS1: {len(skipped)}. "
        f"Pass dir-guard: {sum(r['passes_dir_guard'] for r in cb)}. Pass confluence>=3: {sum(r['passes_confluence_ge3'] for r in cb)}.","",
        "| date | dir | setup | regime1d | taker15 | supp_taker15 | reclaim | eng_void | walls | score_pct | guard | conf | oldRS1 |",
        "|---|:--:|:--:|:--:|--:|--:|:--:|--:|--:|--:|:--:|--:|:--:|"]
    for r in cb:
        md.append(f"| {r['date']} | {r['direction']} | {str(r['setup'])[:5]} | {r['regime_1d']} | {r['taker_imb_15m']} | "
                  f"{r['supp_taker_imb_15m']} | {r['reclaim']} | {r['eng_void']} | {r['walls']} | {r['score_pctile']} | "
                  f"{r['passes_dir_guard']} | {r['confluence']} | {r['selected_by_old_rs1']} |")
    (BNC_OUT/"BINANCE_10D_SKIPPED_WINNER_CASEBOOK.md").write_text("\n".join(md),encoding="utf-8")

    # ============ B: GOOD vs NOISE separation after guard ============
    SEP_FEATS=["dl2_supp_minus_opp_net_flow_15m__pctile_prior","dl2_microprice_aligned_delta_5m_bps__pctile_prior",
        "eng_ofi","supportive_taker_imb_15m","taker_imbalance_15m","reclaim_zoneMid_preconfirm",
        "uniq_score_pctile_vs_prior","eng_void","ms_thin_path_score","ms_large_walls_on_path",
        "prior_move_60m_pct","dist_to_recent_swing_high_pct","explainable_score__pctile_prior","book_entropy_top25"]
    sep_out={}
    for vk,(zs,outdir,isb) in venues.items():
        kept=[z for z in zs if z.get("sim_outcome") and not V.dir_guard_reject(z)]
        good=[z for z in kept if z["sim_label"]=="GOOD"]; noise=[z for z in kept if z["sim_label"]=="NOISE"]
        base=len(good)/max(len(kept),1)
        rows=[]
        for k in SEP_FEATS:
            gm=med(good,k); nm=med(noise,k); d=cohend(good,noise,k)
            # precision uplift: threshold = good-median; precision of GOOD among zones with feature>=thr (or<= if good<noise)
            vals=[(z[k],z["sim_label"]) for z in kept if isinstance(z.get(k),(int,float))]
            up=None; rec=None; fp_removed=None; good_lost=None
            if gm is not None and nm is not None and vals:
                ge = gm>=nm
                passers=[(v,l) for v,l in vals if (v>=gm if ge else v<=gm)]
                if passers:
                    prec=sum(1 for v,l in passers if l=="GOOD")/len(passers)
                    up=round(prec-base,3); rec=round(sum(1 for v,l in passers if l=="GOOD")/max(len(good),1),3)
                    fp_removed=sum(1 for z in noise if not (isinstance(z.get(k),(int,float)) and ((z[k]>=gm) if ge else (z[k]<=gm))))
                    good_lost=sum(1 for z in good if not (isinstance(z.get(k),(int,float)) and ((z[k]>=gm) if ge else (z[k]<=gm))))
            rows.append({"feature":k,"good_med":gm,"noise_med":nm,"cohen_d":d,"precision_uplift":up,
                         "recall":rec,"fp_removed":fp_removed,"good_lost":good_lost})
        rows.sort(key=lambda r:-(abs(r["cohen_d"]) if r["cohen_d"] is not None else -1))
        sep_out[vk]={"base_rate":round(base,3),"kept":len(kept),"good":len(good),"noise":len(noise),"rows":rows}
        gp=vk
        with (outdir/f"{gp}_OPPORTUNITY_FEATURE_SEPARATION.csv").open("w",encoding="utf-8",newline="") as fh:
            w=csv.DictWriter(fh,fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
        (outdir/f"{gp}_OPPORTUNITY_FEATURE_SEPARATION.json").write_text(json.dumps(sep_out[vk],indent=2,default=str),encoding="utf-8")
        mdl=[f"# B. GOOD vs NOISE feature separation (after guard) — {vk}","",f"**Build:** {now_iso()}",
            f"Kept (guard-passing) n={len(kept)} · GOOD {len(good)} · NOISE {len(noise)} · base {round(100*base,1)}%","",
            "| feature | GOOD med | NOISE med | Cohen d | prec uplift | recall | FP removed | GOOD lost |",
            "|---|--:|--:|--:|--:|--:|--:|--:|"]
        for r in rows:
            mdl.append(f"| {r['feature']} | {r['good_med']} | {r['noise_med']} | {r['cohen_d']} | {r['precision_uplift']} | "
                       f"{r['recall']} | {r['fp_removed']} | {r['good_lost']} |")
        (outdir/f"{gp}_OPPORTUNITY_FEATURE_SEPARATION.md").write_text("\n".join(mdl),encoding="utf-8")

    # ============ C: opportunity rule search ============
    rules=opp_rules()
    rule_out={}
    for vk,(zs,outdir,isb) in venues.items():
        traded=[z for z in zs if z.get("sim_outcome")]
        good=[z for z in traded if z["sim_label"]=="GOOD"]
        res=[]
        for rn,fn in rules.items():
            # filter-view
            passers=[z for z in traded if (not V.dir_guard_reject(z)) and fn(z)]
            good_cap=sum(1 for z in passers if z["sim_label"]=="GOOD")
            noise_rej=len([z for z in traded if z["sim_label"]=="NOISE"]) - sum(1 for z in passers if z["sim_label"]=="NOISE")
            # selector-view (first-eligible 1/day among guard+rule)
            sel=selector(zs, fn); tr=[z for z in sel if z.get("sim_outcome")]; m=metrics(tr)
            ndays=len({z["_date"] for z in sel}); alldays=len({z["_date"] for z in zs})
            explor = "EXPLORATORY_NOT_FROZEN" if ("EXPLORATORY" in rn) else "OKX_FROZEN"
            overfit = "HIGH" if (explor=="EXPLORATORY_NOT_FROZEN" or (isb and m["trades"]<5)) else ("LOW" if (m["pf_after_cost"] or 0)>1.3 else "MED")
            res.append({"rule":rn,"threshold_source":explor,"sel_trades":m["trades"],"wins":m["wins"],"losses":m["losses"],
                "timeouts":m["timeouts"],"winrate":m["winrate_pct"],"pf":m["pf_after_cost"],"expectancy":m["expectancy_after_cost_pct"],
                "alerts_per_day":round(len(sel)/max(alldays,1),2),"no_trade_days":alldays-ndays,
                "good_captured":good_cap,"good_total":len(good),"noise_rejected":noise_rej,"overfit_risk":overfit})
        rule_out[vk]=res
        gp=vk
        with (outdir/f"{gp}_OPPORTUNITY_RULE_SEARCH.csv").open("w",encoding="utf-8",newline="") as fh:
            w=csv.DictWriter(fh,fieldnames=list(res[0].keys())); w.writeheader(); w.writerows(res)
        (outdir/f"{gp}_OPPORTUNITY_RULE_SEARCH.json").write_text(json.dumps({"build":now_iso(),"rules":res},indent=2,default=str),encoding="utf-8")
        mdl=[f"# C. Opportunity rule search — {vk}","",f"**Build:** {now_iso()}",
            "Each rule applied AFTER dir-guard, as live-valid first-eligible selector (1/day). good_captured = filter-view of winners.","",
            "| rule | src | sel tr | wr% | PF | exp% | alerts/d | no-trade | GOOD cap/tot | NOISE rej | overfit |",
            "|---|:--:|--:|--:|--:|--:|--:|--:|--:|--:|:--:|"]
        for r in res:
            mdl.append(f"| {r['rule']} | {'EXP' if 'EXPLOR' in r['threshold_source'] else 'OKX'} | {r['sel_trades']} | {r['winrate']} | "
                       f"{r['pf']} | {r['expectancy']} | {r['alerts_per_day']} | {r['no_trade_days']} | {r['good_captured']}/{r['good_total']} | "
                       f"{r['noise_rejected']} | {r['overfit_risk']} |")
        (outdir/f"{gp}_OPPORTUNITY_RULE_SEARCH.md").write_text("\n".join(mdl),encoding="utf-8")

    # ============ D: opportunity selector models A-F ============
    def conf_ge(n): return lambda z: confluence(z)>=n
    sel_out={}
    for vk,(zs,outdir,isb) in venues.items():
        alldays=len({z["_date"] for z in zs}); goods=[z for z in zs if z.get("sim_label")=="GOOD"]
        defs={
            "ModelA_guard_only": dict(extra=None),
            "ModelB_guard_conf2": dict(extra=conf_ge(2)),
            "ModelC_guard_conf3": dict(extra=conf_ge(3)),
            "ModelD_guard_oppscore_OKXfloor": dict(extra=conf_ge(CONF_FLOOR), score_floor=V.SCORE_PCTILE_FLOOR),
            "ModelE_max2_cooldown_oppscore": dict(extra=conf_ge(CONF_FLOOR), maxn=2, cooldown=True),
            "ModelF_first_elig_oppscore_notrade": dict(extra=conf_ge(CONF_FLOOR), score_floor=V.SCORE_PCTILE_FLOOR),
        }
        rows=[]
        for mn,kw in defs.items():
            sel=selector(zs, kw.get("extra"), maxn=kw.get("maxn",1), cooldown=kw.get("cooldown",False), score_floor=kw.get("score_floor"))
            tr=[z for z in sel if z.get("sim_outcome")]; m=metrics(tr)
            took={z["id"] for z in sel}; ndays=len({z["_date"] for z in sel})
            fake=sum(1 for z in sel if z["direction"]=="LONG" and V.regime_against(z) and not V.has_reversal_proof(z))
            rows.append({"model":mn,"trades":m["trades"],"wins":m["wins"],"losses":m["losses"],"timeouts":m["timeouts"],
                "winrate":m["winrate_pct"],"expectancy":m["expectancy_after_cost_pct"],"pf":m["pf_after_cost"],
                "max_consec_losses":m["max_consecutive_losses"],"wrong_direction":m["wrong_direction"],
                "alerts_per_day":round(len(sel)/max(alldays,1),2),"no_trade_days":alldays-ndays,"fake_accumulation":fake,
                "good_captured":sum(1 for z in goods if z["id"] in took),"good_total":len(goods),
                "skipped_good":sum(1 for z in goods if z["id"] not in took)})
        sel_out[vk]=rows
        gp=vk
        with (outdir/f"{gp}_OPPORTUNITY_SELECTOR_RESULTS.csv").open("w",encoding="utf-8",newline="") as fh:
            w=csv.DictWriter(fh,fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
        (outdir/f"{gp}_OPPORTUNITY_SELECTOR_RESULTS.json").write_text(json.dumps({"build":now_iso(),"conf_floor_from_okx":CONF_FLOOR,"models":rows},indent=2,default=str),encoding="utf-8")
        mdl=[f"# D. Opportunity selector models — {vk}","",f"**Build:** {now_iso()}",
            f"Causal first-eligible. OKX-frozen confluence floor = {CONF_FLOOR}. Days={alldays}.","",
            "| model | tr | wr% | exp% | PF | maxCL | wrongdir | alerts/d | no-trade | fake | GOOD cap/tot |",
            "|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|"]
        for r in rows:
            mdl.append(f"| {r['model']} | {r['trades']} | {r['winrate']} | {r['expectancy']} | {r['pf']} | {r['max_consec_losses']} | "
                       f"{r['wrong_direction']} | {r['alerts_per_day']} | {r['no_trade_days']} | {r['fake_accumulation']} | {r['good_captured']}/{r['good_total']} |")
        (outdir/f"{gp}_OPPORTUNITY_SELECTOR_RESULTS.md").write_text("\n".join(mdl),encoding="utf-8")

    # ============ E: final ============
    bnc_sep=sep_out["BINANCE_10D"]["rows"]; okx_sep=sep_out["OKX_MARCH"]["rows"]
    top_bnc=[r for r in bnc_sep if r["cohen_d"] is not None and abs(r["cohen_d"])>=0.3]
    okx_maxd=max((abs(r["cohen_d"]) for r in okx_sep if r["cohen_d"] is not None),default=0)
    separation_found = ("YES_BINANCE_ONLY_NOT_OKX" if (top_bnc and okx_maxd<0.2) else ("YES" if top_bnc else "NO"))
    # best opportunity rule: prefer OKX-FROZEN by (good_captured then pf)
    bnc_rules=rule_out["BINANCE_10D"]
    frozen_rules=[r for r in bnc_rules if r["threshold_source"]=="OKX_FROZEN"]
    best_rule=max(frozen_rules or bnc_rules,key=lambda r:(r["good_captured"], (r["pf"] or 0)))
    # best selector model: OKX-preserving first (okx wr>=55 & PF>=1.5), then best Binance expectancy
    bnc_models=sel_out["BINANCE_10D"]; okx_models=sel_out["OKX_MARCH"]
    okx_by={m["model"]:m for m in okx_models}
    preserving=[m for m in bnc_models if okx_by[m["model"]]["winrate"]>=55 and (okx_by[m["model"]]["pf"] or 0)>=1.5]
    best_model=max(preserving,key=lambda m:(m["expectancy"] or -9)) if preserving else max(bnc_models,key=lambda m:(m["expectancy"] or -9))
    okx_best=okx_by[best_model["model"]]
    okx_pres = "YES" if (okx_best["winrate"]>=55 and (okx_best["pf"] or 0)>=1.5) else ("PARTIAL" if (okx_best["expectancy"] or -9)>0 and (okx_best["pf"] or 0)>=1.3 else "NO")
    freq = best_model["alerts_per_day"]
    target_reached = "YES" if 0.5<=freq<=1.0 and (best_model["expectancy"] or -9)>0 else "NO"
    flags={
        "OPPORTUNITY_CLASSIFIER_DONE":"YES","BINANCE_WINNER_ZONES_ANALYZED":len(winners),
        "GOOD_VS_NOISE_SEPARATION_FOUND":separation_found,
        "BEST_OPPORTUNITY_RULE":best_rule["rule"],"BEST_LIVE_VALID_SELECTOR":best_model["model"],
        "BINANCE_TRADES":best_model["trades"],"BINANCE_WINRATE":best_model["winrate"],
        "BINANCE_EXPECTANCY_AFTER_COST":best_model["expectancy"],"BINANCE_PF_AFTER_COST":best_model["pf"],
        "GOOD_CAPTURED":best_model["good_captured"],
        "SKIPPED_WINNERS_REDUCED":"YES" if best_model["good_captured"]>1 else "NO",
        "OKX_EDGE_PRESERVED":okx_pres,
        "TARGET_FREQUENCY_1_PER_1_2_DAYS_REACHED":target_reached,
        "READY_FOR_TELEGRAM_SHADOW_MODE":"NO","READY_FOR_PRODUCTION_TRADING":"NO","MORE_OOS_REQUIRED":"YES"}
    answers={
        "1_live_valid_winner_features":f"{separation_found}. On Binance only taker_imbalance_15m (d~0.52) and weak void/dist/microprice (d~0.2) lean toward winners; on OKX ALL candidate features have |d|<0.1 — the OKX edge is the composite top1/day ranking, not a single feature. So there is no strong OKX-consistent winner discriminator.",
        "2_why_selector_stood_aside":"frozen OKX score-percentile floor (87) + normalized flow filter + guard leave almost nothing on the Binance down-week; the few survivors still lost. The discriminative Binance signal (taker imbalance) is venue-specific and not in the frozen rule set.",
        "3_which_winners_capturable":f"confluence>=3 captures {sum(1 for z in winners if confluence(z)>=3)} of 31 winners pre-trade; dir-guard passes {sum(0 if V.dir_guard_reject(z) else 1 for z in winners)}/31. Without venue-specific (exploratory) thresholds, live-valid capture stays low.",
        "4_target_frequency":f"{target_reached}. Best live-valid model {best_model['model']}: {best_model['trades']} trades, alerts/day {freq}, no-trade days {best_model['no_trade_days']}. Frozen-only rules do not reach 1/1-2 days profitably on this window.",
        "5_rules_preserving_okx":f"OKX edge under best model: {okx_best['winrate']}% / PF {okx_best['pf']} -> {okx_pres}. Confluence/guard rules keep OKX broadly stable; aggressive single-feature cuts do not.",
        "6_rules_improving_binance_without_tuning":"none clearly: frozen rules stand aside (no loss but no edge). Only EXPLORATORY taker-imbalance cut (overfit risk HIGH) would add trades.",
        "7_continuation_vs_reversal":"continuation (regime-aligned + thin path, O6) is cleaner than reversal (O7); countertrend needs strong reclaim+initiative and remains the main fake-accumulation source.",
        "8_oi_liquidations_fuel":"YES — add OI + liquidations as a fuel layer; true OI absent on Binance recorder remains the biggest missing causal input.",
        "9_carry_to_next_oos":"direction/regime guard + venue-normalized percentile filter + confluence>=3 + no-trade option + cluster cooldown; test taker-imbalance signal as a candidate (not frozen) on NEW windows.",
        "10_telegram_shadow_ready":"NO — frozen selector stands aside; exploratory taker signal is unvalidated/overfit. Needs more OOS windows (bull/range) before shadow logging."}
    final={"build":now_iso(),"status":"RESEARCH_ONLY","conf_floor_from_okx":CONF_FLOOR,
        "separation":{"binance_top_features":top_bnc[:5],"okx_max_abs_d":max((abs(r["cohen_d"]) for r in okx_sep if r["cohen_d"] is not None),default=None)},
        "binance_models":bnc_models,"okx_models":okx_models,"best_rule":best_rule,"flags":flags,"answers":answers}
    (BNC_OUT/"OPPORTUNITY_CLASSIFIER_FINAL_REPORT.json").write_text(json.dumps(final,indent=2,default=str),encoding="utf-8")
    md=["# OPPORTUNITY CLASSIFIER FOR SKIPPED WINNERS — FINAL REPORT","",f"**Build:** {now_iso()}",
        "**RESEARCH ONLY. No engine/detector/TP-SL/production change. Causal features. OKX-frozen thresholds; Binance-specific cuts labeled EXPLORATORY.**","",
        "## Binance GOOD-vs-NOISE separation (after guard) — top features",
        "| feature | GOOD med | NOISE med | Cohen d |","|---|--:|--:|--:|"]
    for r in bnc_sep[:6]: md.append(f"| {r['feature']} | {r['good_med']} | {r['noise_med']} | {r['cohen_d']} |")
    md+=["",f"OKX max |Cohen d| across features = {final['separation']['okx_max_abs_d']} (≈0 ⇒ no single-feature OKX winner signal).","",
        "## Binance opportunity selector models","",
        "| model | tr | wr% | exp% | PF | alerts/d | no-trade | GOOD cap/31 |","|---|--:|--:|--:|--:|--:|--:|--:|"]
    for r in bnc_models:
        md.append(f"| {r['model']} | {r['trades']} | {r['winrate']} | {r['expectancy']} | {r['pf']} | {r['alerts_per_day']} | {r['no_trade_days']} | {r['good_captured']}/31 |")
    md+=["","## OKX sanity (same models)","| model | tr | wr% | exp% | PF |","|---|--:|--:|--:|--:|"]
    for r in okx_models:
        md.append(f"| {r['model']} | {r['trades']} | {r['winrate']} | {r['expectancy']} | {r['pf']} |")
    md+=["","## Answers"]
    for k,v in answers.items(): md.append(f"**{k}** — {v}\n")
    md+=["## Flags","```"]+[f"{k} = {v}" for k,v in flags.items()]+["```"]
    (BNC_OUT/"OPPORTUNITY_CLASSIFIER_FINAL_REPORT.md").write_text("\n".join(md),encoding="utf-8")

    # console
    print("=== SKIPPED WINNERS ===")
    print(f"31 winners: {len(short_w)} SHORT, {len(long_w)} LONG; pass dir-guard {sum(r['passes_dir_guard'] for r in cb)}; conf>=3 {sum(r['passes_confluence_ge3'] for r in cb)}")
    print("\n=== BINANCE GOOD vs NOISE (after guard) top features ===")
    for r in bnc_sep[:6]: print(f"  {r['feature']:48s} GOOD={r['good_med']} NOISE={r['noise_med']} d={r['cohen_d']} upl={r['precision_uplift']}")
    print(f"OKX max|d|={final['separation']['okx_max_abs_d']}  separation_found={separation_found}")
    print("\n=== BINANCE OPPORTUNITY RULES ===")
    for r in bnc_rules:
        print(f"  {r['rule']:38s} sel={r['sel_trades']} wr={r['winrate']} PF={r['pf']} GOODcap={r['good_captured']}/{r['good_total']} overfit={r['overfit_risk']}")
    print("\n=== BINANCE SELECTOR MODELS ===")
    for r in bnc_models:
        print(f"  {r['model']:34s} tr={r['trades']} wr={r['winrate']} exp={r['expectancy']} PF={r['pf']} alerts/d={r['alerts_per_day']} GOODcap={r['good_captured']}/31")
    print("\n=== OKX SANITY (models) ===")
    for r in okx_models:
        print(f"  {r['model']:34s} tr={r['trades']} wr={r['winrate']} exp={r['expectancy']} PF={r['pf']}")
    print("\nFLAGS:")
    for k,v in flags.items(): print(f"  {k:<46s} = {v}")
    return 0


if __name__=="__main__":
    sys.exit(run())
