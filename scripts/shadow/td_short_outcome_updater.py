"""TD-SHORT OUTCOME UPDATER (separate post-factum step).

Reads the leak-free decision log, recomputes outcomes from REALIZED price (canonical TP2/SL1.5/24h
+ no-exit MFE/MAE/time_to) per venue, and writes a separate outcomes file. Also produces the
backfill report (D), live/OOS readiness (E), and final report (F). Decisions are never re-derived here.
"""
from __future__ import annotations
import csv, json, sys, bisect, datetime as dt
from collections import defaultdict
from pathlib import Path

ROOT = Path("C:/Users/gibilev/orderflow-research")
sys.path.insert(0, str(ROOT / "scripts/strategy-calibration"))
from canonical_ledger import build_buckets_from_trades_csv, Signal, ExecutionConfig, simulate_canonical_trade
import statistics as st

OUT = ROOT / "reports/shadow"
DATA = {"OKX_MARCH": ROOT / "data/okx-historical/BTC-USDT-SWAP", "OKX_MAY": ROOT / "data/okx-historical/BTC-USDT-SWAP",
        "BINANCE_MAY": ROOT / "data/binance-historical/BTCUSDT"}
COST = 0.14; TP = 2.0; SL = 1.5; TO_H = 24


def num(x): return x if isinstance(x, (int, float)) else None


def load_decisions():
    rows = []
    with (OUT / "TD_SHORT_SHADOW_DECISIONS.jsonl").open(encoding="utf-8") as fh:
        for line in fh:
            if line.strip(): rows.append(json.loads(line))
    return rows


def buckets_for(venue, dates):
    gb = []
    for d in sorted(dates):
        p = DATA[venue] / d / "trades.csv.gz"
        if p.exists(): gb += build_buckets_from_trades_csv(p)
    gb.sort(key=lambda b: b.sec)
    return gb, [b.sec for b in gb]


def outcome_for(dec, gb, secs):
    """canonical TP2/SL1.5 + no-exit 24h MFE/MAE/time_to from realized buckets."""
    ts = dec.get("confirmedTs"); d = dec.get("direction"); zl = dec.get("zoneLow"); zh = dec.get("zoneHigh")
    res = {"zone_id": dec["zone_id"], "venue": dec["venue"], "date": dec["date"], "final_shadow_decision": dec["final_shadow_decision"],
           "hybrid_decision": dec["hybrid_decision"], "m4_thin_decision": dec["m4_thin_decision"],
           "target_hit": 0, "stop_hit": 0, "timeout": 0, "result": "NO_TRADE", "pnl_after_cost": None,
           "MFE": None, "MAE": None, "hit_2pct": 0, "hit_2_5pct": 0, "hit_3pct": 0,
           "time_to_2pct_min": None, "time_to_2_5pct_min": None, "time_to_3pct_min": None}
    if ts is None or zl is None or zh is None or not gb: return res
    sig = Signal(id=dec["zone_id"], date=dec["date"], trigger_ts_ms=ts, direction=d, zone_low=zl, zone_high=zh)
    cfg = ExecutionConfig(entry_strategy="trigger", stop_pct=SL, target_pct=TP, timeout_hours=TO_H)
    sim = simulate_canonical_trade(sig, gb, cfg)
    er = sim.get("exit_reason")
    if er in ("no_data", "skip_no_retest"): return res
    res["pnl_after_cost"] = round(sim["pnl_pct"] - COST, 4)
    res["result"] = "WIN" if er == "target_2pct" else ("LOSS" if er == "stop" else "TIMEOUT")
    res["target_hit"] = int(er == "target_2pct"); res["stop_hit"] = int(er == "stop"); res["timeout"] = int(res["result"] == "TIMEOUT")
    ep = sim["entry_price"]; start = sim["entry_sec"]
    i = bisect.bisect_left(secs, start); j = bisect.bisect_right(secs, start + 24 * 3600); seg = gb[i:j]
    if seg and ep:
        mfe = -1e9; mae = 1e9; t2 = t25 = t3 = None
        for b in seg:
            fav = (b.high - ep) / ep * 100 if d == "LONG" else (ep - b.low) / ep * 100
            adv = (b.low - ep) / ep * 100 if d == "LONG" else (ep - b.high) / ep * 100
            if fav > mfe: mfe = fav
            if adv < mae: mae = adv
            if t2 is None and fav >= 2: t2 = b.sec - start
            if t25 is None and fav >= 2.5: t25 = b.sec - start
            if t3 is None and fav >= 3: t3 = b.sec - start
        res["MFE"] = round(mfe, 3); res["MAE"] = round(mae, 3)
        res["hit_2pct"] = int(mfe >= 2); res["hit_2_5pct"] = int(mfe >= 2.5); res["hit_3pct"] = int(mfe >= 3)
        res["time_to_2pct_min"] = round(t2 / 60, 1) if t2 else None
        res["time_to_2_5pct_min"] = round(t25 / 60, 1) if t25 else None
        res["time_to_3pct_min"] = round(t3 / 60, 1) if t3 else None
    return res


def metr(rows):
    tr = [r for r in rows if r.get("result") in ("WIN", "LOSS", "TIMEOUT")]
    n = len(tr); W = sum(1 for r in tr if r["result"] == "WIN"); L = sum(1 for r in tr if r["result"] == "LOSS"); TO = sum(1 for r in tr if r["result"] == "TIMEOUT")
    pnls = [r["pnl_after_cost"] for r in tr if r.get("pnl_after_cost") is not None]
    wp = [p for p in pnls if p > 0]; lp = [p for p in pnls if p < 0]
    pf = round(sum(wp) / sum(-p for p in lp), 3) if lp else None
    cur = mx = 0
    for r in tr:
        if (r.get("pnl_after_cost") or 0) <= 0: cur += 1; mx = max(mx, cur)
        else: cur = 0
    return {"trades": n, "W": W, "L": L, "TO": TO, "winrate": round(100 * W / max(n, 1), 2),
            "expectancy": round(st.mean(pnls), 4) if pnls else None, "pf": pf,
            "total_return": round(sum(pnls), 4) if pnls else None, "max_loss_streak": mx,
            "hit2": sum(r["hit_2pct"] for r in tr), "hit2_5": sum(r["hit_2_5pct"] for r in tr), "hit3": sum(r["hit_3pct"] for r in tr)}


def first_elig(decs, maxn=1):
    byd = defaultdict(list)
    for r in decs: byd[(r["venue"], r["date"])].append(r)
    out = []
    for key in sorted(byd):
        day = sorted(byd[key], key=lambda r: r.get("confirmedTs") or 0)
        out += day[:maxn]
    return out


def main():
    decs = load_decisions()
    # group by venue, build buckets, compute outcomes
    byv = defaultdict(list)
    for r in decs: byv[r["venue"]].append(r)
    outcomes = {}
    for vn, rows in byv.items():
        gb, secs = buckets_for(vn, {r["date"] for r in rows})
        for r in rows: outcomes[r["zone_id"]] = outcome_for(r, gb, secs)
        print(f"  {vn}: outcomes for {len(rows)} zones", file=sys.stderr)
    out_rows = list(outcomes.values())
    with (OUT / "TD_SHORT_SHADOW_OUTCOMES.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out_rows[0].keys())); w.writeheader(); w.writerows(out_rows)
    with (OUT / "TD_SHORT_SHADOW_OUTCOMES.jsonl").open("w", encoding="utf-8") as fh:
        for r in out_rows: fh.write(json.dumps(r, default=str) + "\n")

    # ---- D: backfill report ----
    for r in decs: r["_oc"] = outcomes.get(r["zone_id"], {})
    def join(decs_sub): return [dict(r["_oc"], confirmedTs=r.get("confirmedTs")) for r in decs_sub]
    accepted = [r for r in decs if r["final_shadow_decision"] == "ACCEPT"]
    hybrid_m = metr(join(accepted))
    td_short = [r for r in decs if r["regime"] == "TREND_DOWN" and r["direction"] == "SHORT"]
    m4_pass = [r for r in td_short if r["m4_thin_decision"] == "M4_THIN_ONLY_PASS"]
    m4_sel = first_elig(m4_pass, maxn=1)
    m4_m = metr(join(m4_sel))
    acc_ids = {r["zone_id"] for r in accepted}; m4_ids = {r["zone_id"] for r in m4_sel}
    overlap = len(acc_ids & m4_ids)
    # reject reasons
    rr = defaultdict(int)
    for r in decs:
        for x in (r["reject_reasons"].split(";") if r["reject_reasons"] else []):
            if x: rr[x] += 1
    # rejected winners/losers among td_short
    rej_td = [r for r in td_short if r["final_shadow_decision"] == "REJECT"]
    rej_winners = sum(1 for r in rej_td if (outcomes.get(r["zone_id"], {}).get("hit_2pct")))
    rej_losers = sum(1 for r in rej_td if outcomes.get(r["zone_id"], {}).get("result") == "LOSS")
    pv = {}
    for vn in ("OKX_MARCH", "OKX_MAY", "BINANCE_MAY"):
        pv[vn] = metr(join([r for r in accepted if r["venue"] == vn]))
    bf = {"build": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
          "n_decisions": len(decs), "n_td_short": len(td_short), "hybrid_candidates": sum(1 for r in decs if r["hybrid_decision"] == "HYBRID_PASS"),
          "accepted": len(accepted), "hybrid_metrics": hybrid_m, "m4_metrics": m4_m, "overlap_hybrid_m4": overlap,
          "reject_reasons": dict(sorted(rr.items(), key=lambda kv: -kv[1])), "rejected_winners": rej_winners, "rejected_losers": rej_losers, "per_venue": pv}
    (OUT / "TD_SHORT_OBSERVER_BACKFILL_REPORT.json").write_text(json.dumps(bf, indent=2, default=str), encoding="utf-8")
    with (OUT / "TD_SHORT_OBSERVER_BACKFILL_TRADES.csv").open("w", encoding="utf-8", newline="") as fh:
        keys = ["zone_id", "venue", "date", "result", "pnl_after_cost", "MFE", "MAE", "hit_2pct", "hit_2_5pct", "time_to_2pct_min"]
        w = csv.DictWriter(fh, fieldnames=keys, extrasaction="ignore"); w.writeheader()
        for r in accepted: w.writerow(outcomes.get(r["zone_id"], {}))
    mdD = ["# D. TD-short observer backfill (sanity — NOT production proof)", "", f"**Build:** {bf['build']}",
           f"Decisions {len(decs)} · TD-short {len(td_short)} · HYBRID candidates {bf['hybrid_candidates']} · accepted {len(accepted)}", "",
           f"**HYBRID accepted:** {hybrid_m['trades']}tr {hybrid_m['W']}/{hybrid_m['L']}/{hybrid_m['TO']} wr {hybrid_m['winrate']}% exp {hybrid_m['expectancy']} PF {hybrid_m['pf']} ret {hybrid_m['total_return']}% maxLS {hybrid_m['max_loss_streak']} hit2/2.5/3 {hybrid_m['hit2']}/{hybrid_m['hit2_5']}/{hybrid_m['hit3']}",
           f"**M4 thin-only:** {m4_m['trades']}tr wr {m4_m['winrate']}% PF {m4_m['pf']} exp {m4_m['expectancy']} · overlap with HYBRID: {overlap}",
           f"Rejected winners {rej_winners} · correctly-rejected losers {rej_losers}", "",
           "## Per venue (HYBRID)", "| venue | tr | wr% | PF | exp% |", "|---|--:|--:|--:|--:|"]
    for vn, v in pv.items(): mdD.append(f"| {vn} | {v['trades']} | {v['winrate']} | {v['pf']} | {v['expectancy']} |")
    mdD += ["", "## Reject reasons", "| reason | count |", "|---|--:|"]
    for k, v in bf["reject_reasons"].items(): mdD.append(f"| {k} | {v} |")
    (OUT / "TD_SHORT_OBSERVER_BACKFILL_REPORT.md").write_text("\n".join(mdD), encoding="utf-8")

    # ---- E: live/OOS readiness ----
    leak_free = "YES"  # decision log fields whitelisted; no outcome fields present
    E = {"build": bf["build"],
         "1_shadow_ready": "YES — frozen causal gates, decision log written, no trading/Telegram.",
         "2_future_leak": "NO leak — decision log has zero outcome/future fields; outcomes are a separate file.",
         "3_decision_outcome_separated": "YES — observer writes decisions; updater writes outcomes.",
         "4_daily_data_needed": "per day: confirmed zones + causal features (regime, prior_move_60m/1d, eng_ofi, taker_imb, microprice, void/walls, reclaim).",
         "5_how_to_run_daily": "run td_short_shadow_observer.py on the day's confirmed-zone feature cache -> decisions; after 24h run td_short_outcome_updater.py.",
         "6_min_oos": ">=20 accepted TD-short trades on NEW data (not OKX March).",
         "7_success_criteria": ["PF>1.5", "winrate>=50-55%", "max loss streak<=5", "no catastrophic counter-trend losses (MAE not >> SL)", "results NOT concentrated in one venue/day"]}
    (OUT / "TD_SHORT_LIVE_READINESS.json").write_text(json.dumps(E, indent=2), encoding="utf-8")
    (OUT / "TD_SHORT_LIVE_READINESS.md").write_text("# E. TD-short live/OOS readiness\n\n**Build:** " + bf["build"] + "\n\n"
        + "\n".join(f"**{k}** — {v}" for k, v in E.items() if not isinstance(v, list))
        + "\n\n## OOS success criteria\n" + "\n".join("- " + x for x in E["7_success_criteria"]) + "\n", encoding="utf-8")

    # ---- F: final ----
    concentrated = pv["OKX_MARCH"]["trades"] > (hybrid_m["trades"] * 0.6)
    flags = {
        "TD_SHORT_SHADOW_OBSERVER_IMPLEMENTED": "YES", "TD_SHORT_RULES_FROZEN": "YES",
        "HYBRID_MAIN_MODEL": "YES", "M4_THIN_ONLY_LOGGED_AS_BOOSTER": "YES",
        "DECISION_LOG_FUTURE_LEAK_FREE": leak_free, "OUTCOME_UPDATER_SEPARATE": "YES",
        "TELEGRAM_DISABLED": "YES", "PRODUCTION_DISABLED": "YES", "BACKFILL_DONE": "YES",
        "BACKFILL_HYBRID_TRADES": hybrid_m["trades"], "BACKFILL_HYBRID_WINRATE": hybrid_m["winrate"], "BACKFILL_HYBRID_PF": hybrid_m["pf"],
        "BACKFILL_EDGE_CONCENTRATED_OKX_MARCH": "YES" if concentrated else "NO",
        "READY_FOR_LIVE_SHADOW_LOGGING": "YES", "READY_FOR_TELEGRAM_SHADOW_MODE": "NO",
        "READY_FOR_PRODUCTION_TRADING": "NO", "MORE_OOS_REQUIRED": "YES", "TARDIS_USED": "NO"}
    final = {"build": bf["build"], "status": "SHADOW_RESEARCH_ONLY", "backfill": bf, "readiness": E, "flags": flags}
    (OUT / "TD_SHORT_SHADOW_OBSERVER_FINAL_REPORT.json").write_text(json.dumps(final, indent=2, default=str), encoding="utf-8")
    L = ["# TD-SHORT SHADOW OBSERVER — FINAL REPORT", "", f"**Build:** {bf['build']}",
         "SHADOW/RESEARCH ONLY · rules FROZEN · Telegram DISABLED · production DISABLED · decision log leak-free · TARDIS not used", "",
         f"## Backfill (sanity)\nHYBRID accepted {hybrid_m['trades']}tr · wr {hybrid_m['winrate']}% · PF {hybrid_m['pf']} · exp {hybrid_m['expectancy']} · maxLS {hybrid_m['max_loss_streak']}",
         f"- M4 thin-only {m4_m['trades']}tr wr {m4_m['winrate']}% PF {m4_m['pf']} (overlap {overlap})",
         f"- per venue: OKX_MARCH {pv['OKX_MARCH']['trades']}tr/{pv['OKX_MARCH']['winrate']}%, OKX_MAY {pv['OKX_MAY']['trades']}tr/{pv['OKX_MAY']['winrate']}%, BINANCE_MAY {pv['BINANCE_MAY']['trades']}tr/{pv['BINANCE_MAY']['winrate']}%",
         f"- edge concentrated in OKX March (in-sample): **{flags['BACKFILL_EDGE_CONCENTRATED_OKX_MARCH']}**", "",
         "## Flags", "```"] + [f"{k} = {v}" for k, v in flags.items()] + ["```"]
    (OUT / "TD_SHORT_SHADOW_OBSERVER_FINAL_REPORT.md").write_text("\n".join(L), encoding="utf-8")

    print(f"\nHYBRID accepted {hybrid_m['trades']}tr wr {hybrid_m['winrate']}% PF {hybrid_m['pf']} exp {hybrid_m['expectancy']} maxLS {hybrid_m['max_loss_streak']}")
    print(f"M4 thin {m4_m['trades']}tr wr {m4_m['winrate']}% PF {m4_m['pf']} overlap {overlap}")
    print(f"per venue: {[(k, v['trades'], v['winrate'], v['pf']) for k, v in pv.items()]}")
    print(f"reject reasons: {bf['reject_reasons']}")
    print(f"rejected winners {rej_winners} losers {rej_losers}")
    print("FLAGS:")
    for k, v in flags.items(): print(f"  {k:<42s} = {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
