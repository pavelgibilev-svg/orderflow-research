"""Interim Binance OOS report on COMPLETED days only (partial; clearly labeled).
Reuses functions from binance_oos_features_rs. NOT the final 10-day verdict.
"""
from __future__ import annotations
import csv, json, sys, time, datetime as dt
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import binance_oos_features_rs as B
from canonical_ledger import build_buckets_from_trades_csv

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "package.json").exists() and (p / "scripts").exists())
OUT = ROOT / "reports/binance-oos"
TARDIS = ROOT / "data/binance-historical/BTCUSDT"
ALL10 = [f"2026-05-{d:02d}" for d in range(21,31)]

def now_iso(): return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

def main():
    done=[d for d in ALL10 if (ROOT/f"reports/binance-live/BTCUSDT_{d}"/"zones.json").exists()]
    print(f"completed days: {done}", file=sys.stderr)
    # keep module DATES = all 10 so forward-24h buckets can span into later converted days
    B.DATES = ALL10
    B.H1 = done[:len(done)//2] if len(done)>=2 else done
    B.H2 = done[len(done)//2:] if len(done)>=2 else []
    # load zones from done days
    all_zones=[]
    for d in done:
        for z in B.load_zones(d):
            z["_date"]=d; all_zones.append(z)
    print(f"confirmed zones: {len(all_zones)}", file=sys.stderr)
    opp=B.opp_dir_counts(all_zones)
    # buckets for all converted days (forward sim)
    bcache={}
    for d in ALL10:
        p=TARDIS/d/"trades.csv.gz"
        if p.exists(): bcache[d]=build_buckets_from_trades_csv(p)
    for z in all_zones:
        z.update(B.trades_features(z, bcache[z["_date"]]))
        hr=(z["confirmedTs"]//1000 % 86400)//3600
        z["is_asia_session"]=1 if hr<7 else 0
        z["opp_dir_zones_active_60m"]=opp.get(z["id"],0)
    # L2 features per done day
    by_date=defaultdict(list)
    for z in all_zones:
        by_date[z["_date"]].append((z["confirmedTs"]//1000,z["id"],z["direction"],z.get("zoneLow"),z.get("zoneHigh")))
    l2map={}
    for d in done:
        t0=time.time(); l2map.update(B.l2_features_for_day(d, by_date.get(d,[])))
        print(f"  {d}: L2 {time.time()-t0:.0f}s", file=sys.stderr)
    for z in all_zones:
        z.update(l2map.get(z["id"],{}))
        z["funding_rate_at_signal"]=B.funding_at(z["_date"], z["confirmedTs"]//1000)
        z["_score"]=B.explainable_score(z)
    # RS1
    rs1_pass=[z for z in all_zones
              if z.get("dist_to_recent_swing_high_pct") is not None and z["dist_to_recent_swing_high_pct"]<=B.SWING_MAX
              and z.get("dl2_supp_minus_opp_net_flow_15m") is not None and z["dl2_supp_minus_opp_net_flow_15m"]<=B.SUPP_OPP_15M_MAX]
    by_d=defaultdict(list)
    for z in rs1_pass: by_d[z["_date"]].append(z)
    rs1_sel=[]
    for d in done:
        day=sorted(by_d.get(d,[]),key=lambda x:-x["_score"])
        if day: rs1_sel.append(day[0])
    rs1_trades=[t for z in rs1_sel if (t:=B.sim_trade(z,bcache))]
    m=B.metrics(rs1_trades)
    zmap={z["id"]:z for z in all_zones}

    # engine counts
    eng_rows=[]
    for d in done:
        allz=json.loads((ROOT/f"reports/binance-live/BTCUSDT_{d}"/"zones.json").read_text(encoding="utf-8"))
        allz=allz if isinstance(allz,list) else allz.get("zones",[])
        conf=[z for z in allz if z.get("confirmedTs")]
        eng_rows.append({"date":d,"zones":len(allz),"confirmed":len(conf),
                         "triggered":sum(1 for z in allz if z.get("triggerTs"))})

    interim={"build_time_utc":now_iso(),"status":"INTERIM_PARTIAL","completed_days":done,
             "pending_days":[d for d in ALL10 if d not in done],
             "engine_per_day":eng_rows,"rs1_metrics":m,
             "rs1_candidate_pass":len(rs1_pass),"rs1_selected":len(rs1_sel),
             "rs1_trades":rs1_trades,
             "caveat":"PARTIAL interim on completed days only. NOT the final 10-day OOS verdict. "
                      "Small n; do not treat as conclusive."}
    (OUT/"BINANCE_2026_05_21_30_INTERIM_REPORT.json").write_text(json.dumps(interim,indent=2,default=str),encoding="utf-8")
    md=[f"# Binance OOS INTERIM report ({len(done)} of 10 days)","",f"**Build:** {now_iso()}",
        "**STATUS: PARTIAL / INTERIM — not the final 10-day verdict. Small sample.**","",
        f"Completed: {done}",f"Pending: {interim['pending_days']}","",
        "## Engine per day","","| date | zones | confirmed | triggered |","|---|---:|---:|---:|"]
    for r in eng_rows: md.append(f"| {r['date']} | {r['zones']} | {r['confirmed']} | {r['triggered']} |")
    md+=["","## RS1 (frozen OKX rules) on completed days","",
        "| metric | value | OKX IS ref |","|---|---:|---:|",
        f"| trades | {m['trades']} | 29 |",
        f"| wins | {m['wins']} | 18 |",
        f"| losses | {m['losses']} | 8 |",
        f"| timeouts | {m['timeouts']} | 3 |",
        f"| winrate % | {m['winrate_pct']} | 62.07 |",
        f"| avg win aft | {m['avg_win_after_cost']} | - |",
        f"| avg loss aft | {m['avg_loss_after_cost']} | - |",
        f"| avg timeout aft | {m['avg_timeout_pnl_after_cost']} | - |",
        f"| expectancy aft % | {m['expectancy_after_cost_pct']} | 0.6475 |",
        f"| total return aft % | {m['total_return_after_cost_pct']} | 18.78 |",
        f"| PF aft | {m['pf_after_cost']} | 2.258 |",
        f"| max consec losses | {m['max_consecutive_losses']} | 3 |",
        f"| LONG/SHORT winrate | {m['long_winrate']}/{m['short_winrate']} | - |",
        "",
        "## RS1 selected trades (interim)","",
        "| date | dir | result | pnl_aft% | dist_swh% | supp_opp_15m | thin_path | microprice5m | funding |",
        "|---|:--:|:--:|--:|--:|--:|--:|--:|--:|"]
    for t in rs1_trades:
        z=zmap[t["zone_id"]]
        md.append(f"| {t['date']} | {t['direction']} | {t['outcome']} | {t['pnl_after_cost']} | "
            f"{z.get('dist_to_recent_swing_high_pct')} | {z.get('dl2_supp_minus_opp_net_flow_15m')} | "
            f"{z.get('ms_thin_path_score')} | {z.get('dl2_microprice_aligned_delta_5m_bps')} | "
            f"{round((z.get('funding_rate_at_signal') or 0)*1e4,2)} |")
    md+=["","**Caveat:** "+interim["caveat"]]
    (OUT/"BINANCE_2026_05_21_30_INTERIM_REPORT.md").write_text("\n".join(md),encoding="utf-8")
    with (OUT/"BINANCE_2026_05_21_30_INTERIM_RS1_TRADES.csv").open("w",encoding="utf-8",newline="") as f:
        keys=["date","direction","zone_id","confirmed_iso","entry_price","exit_reason","outcome","pnl_after_cost",
              "mfe_pct","mae_pct"]
        w=csv.DictWriter(f,fieldnames=keys,extrasaction="ignore"); w.writeheader()
        for t in rs1_trades: w.writerow(t)

    print("\n=== INTERIM RS1 ({} days) ===".format(len(done)))
    print(f"confirmed zones {len(all_zones)}; RS1 pass {len(rs1_pass)}; selected {len(rs1_sel)}")
    print(f"RS1: {m['trades']}tr {m['wins']}W/{m['losses']}L/{m['timeouts']}TO wr={m['winrate_pct']}% "
          f"exp={m['expectancy_after_cost_pct']} PF={m['pf_after_cost']} ret={m['total_return_after_cost_pct']}")
    for t in rs1_trades:
        z=zmap[t["zone_id"]]
        print(f"  {t['date']} {t['direction']:>5} {t['outcome']:>7} pnl={t['pnl_after_cost']:+.3f} "
              f"dist={z.get('dist_to_recent_swing_high_pct')} supp_opp15={z.get('dl2_supp_minus_opp_net_flow_15m')}")
    return 0

if __name__=="__main__":
    sys.exit(main())
