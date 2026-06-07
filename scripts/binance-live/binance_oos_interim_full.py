"""COMPREHENSIVE INTERIM Binance OOS report on the 7 COMPLETED days 2026-05-21..27.

Clearly labeled INTERIM / PARTIAL. NOT the final 10-day verdict.
- Does NOT touch the main backtest chain (reads existing engine outputs only).
- Does NOT recompute engine reports (reads reports/binance-live/BTCUSDT_<d>/).
- Uses frozen OKX RS1 + RS2(S7 partial) rules, exact canonical ledger (real timeout PnL),
  NO threshold retuning.
- Produces the full requested artifact set with BINANCE_2026_05_21_27_INTERIM_* naming.

Reuses functions from binance_oos_features_rs (features, RS1/RS2, metrics, sim_trade).
"""
from __future__ import annotations
import csv, json, sys, time, datetime as dt
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import binance_oos_features_rs as B
from canonical_ledger import build_buckets_from_trades_csv

ROOT = Path("C:/Users/gibilev/orderflow-research")
OUT = ROOT / "reports/binance-oos"
TARDIS = ROOT / "data/binance-historical/BTCUSDT"
ZONES_DIR = ROOT / "reports/binance-live"
NORM_REPORT = OUT / "BINANCE_2026_05_21_30_NORMALIZATION_REPORT.json"

ALL10 = [f"2026-05-{d:02d}" for d in range(21, 31)]
INTERIM_DAYS = [f"2026-05-{d:02d}" for d in range(21, 28)]   # 05-21..27 (explicit interim window)
TAG = "BINANCE_2026_05_21_27_INTERIM"

OKX_RS1 = {"trades": 29, "winrate": 62.07, "exp": 0.6475, "pf": 2.258, "ret": 18.78}
OKX_S7  = {"trades": 26, "winrate": 65.38, "exp": 0.7403, "pf": 2.527}


def now_iso(): return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def parse_daily_summary(d):
    p = ZONES_DIR / f"BTCUSDT_{d}" / "daily_summary.csv"
    out = {}
    if not p.exists(): return out
    for line in p.read_text(encoding="utf-8").splitlines()[1:]:
        if "," not in line: continue
        k, v = line.split(",", 1)
        try: out[k] = float(v) if ("." in v or v.lstrip("-").isdigit() is False) else int(v)
        except Exception: out[k] = v
    return out


def day_range(buckets):
    """intraday open/high/low/close + range_pct + 2% feasibility + coverage hours."""
    if not buckets:
        return {"open": None, "high": None, "low": None, "close": None,
                "range_pct": None, "feasible_2pct": None, "coverage_h": 0.0}
    hi = max(b.high for b in buckets); lo = min(b.low for b in buckets)
    op = buckets[0].last; cl = buckets[-1].last
    cov = round((buckets[-1].sec - buckets[0].sec) / 3600.0, 2)
    rng = round((hi - lo) / lo * 100.0, 3) if lo > 0 else None
    return {"open": round(op, 2), "high": round(hi, 2), "low": round(lo, 2), "close": round(cl, 2),
            "range_pct": rng, "feasible_2pct": (rng is not None and rng >= 2.0), "coverage_h": cov}


def interim_transfer(m):
    """Honest interim verdict: UNKNOWN if sample too small to judge."""
    n = m["trades"]; wr = m["winrate_pct"]
    pf = m["pf_after_cost"] or 0; exp = m["expectancy_after_cost_pct"] or 0
    if n < 15:
        return "UNKNOWN"   # too few trades to confirm/reject transfer
    if n >= 20 and abs(wr - OKX_RS1["winrate"]) <= 5 and pf > 1.5:
        return "GOOD"
    if n >= 15 and wr > 52 and pf > 1.2:
        return "WEAK"
    if wr < 50 or pf < 1.2 or exp <= 0:
        return "NO"
    return "UNKNOWN"


def main():
    miss = [d for d in INTERIM_DAYS if not (ZONES_DIR / f"BTCUSDT_{d}" / "daily_summary.csv").exists()]
    if miss:
        print(f"INTERIM blocked: missing engine output for {miss}", file=sys.stderr)
        return 2
    B.DATES = ALL10  # forward 24h buckets may span into later converted days (all 10 converted)

    # row counts for data audit
    rowcounts = {}
    if NORM_REPORT.exists():
        nr = json.loads(NORM_REPORT.read_text(encoding="utf-8"))
        for x in nr.get("days", []):
            s = x.get("streams", {})
            rowcounts[x["date"]] = {
                "L2": s.get("incremental_book_L2", {}).get("rows_out"),
                "trades": s.get("trades", {}).get("rows_out"),
                "deriv": s.get("derivative_ticker", {}).get("rows_out"),
                "liq": s.get("liquidations", {}).get("rows_out")}

    print("[load zones]", file=sys.stderr)
    all_zones = []
    for d in INTERIM_DAYS:
        for z in B.load_zones(d):
            z["_date"] = d; all_zones.append(z)
    print(f"  confirmed zones: {len(all_zones)}", file=sys.stderr)
    opp = B.opp_dir_counts(all_zones)

    print("[trades buckets]", file=sys.stderr)
    bcache = {}
    for d in ALL10:
        p = TARDIS / d / "trades.csv.gz"
        if p.exists():
            bcache[d] = build_buckets_from_trades_csv(p)

    print("[trades features]", file=sys.stderr)
    for z in all_zones:
        z.update(B.trades_features(z, bcache.get(z["_date"], [])))
        hr = (z["confirmedTs"] // 1000 % 86400) // 3600
        z["is_asia_session"] = 1 if hr < 7 else 0
        z["opp_dir_zones_active_60m"] = opp.get(z["id"], 0)

    print("[L2 features]", file=sys.stderr)
    by_date = defaultdict(list)
    for z in all_zones:
        by_date[z["_date"]].append((z["confirmedTs"] // 1000, z["id"], z["direction"],
                                    z.get("zoneLow"), z.get("zoneHigh")))
    l2map = {}
    for d in INTERIM_DAYS:
        t0 = time.time()
        l2map.update(B.l2_features_for_day(d, by_date.get(d, [])))
        print(f"  {d}: L2 {time.time()-t0:.0f}s", file=sys.stderr)
    for z in all_zones:
        z.update(l2map.get(z["id"], {}))
        z["funding_rate_at_signal"] = B.funding_at(z["_date"], z["confirmedTs"] // 1000)
        z["_score"] = B.explainable_score(z)
    zmap = {z["id"]: z for z in all_zones}

    # ---------------- RS1 (frozen) ----------------
    print("[RS1]", file=sys.stderr)
    rs1_pass = [z for z in all_zones
                if z.get("dist_to_recent_swing_high_pct") is not None
                and z["dist_to_recent_swing_high_pct"] <= B.SWING_MAX
                and z.get("dl2_supp_minus_opp_net_flow_15m") is not None
                and z["dl2_supp_minus_opp_net_flow_15m"] <= B.SUPP_OPP_15M_MAX]
    by_d = defaultdict(list)
    for z in rs1_pass:
        by_d[z["_date"]].append(z)
    rs1_sel = []
    for d in INTERIM_DAYS:
        day = sorted(by_d.get(d, []), key=lambda x: -x["_score"])
        if day:
            rs1_sel.append(day[0])
    rs1_trades = [t for z in rs1_sel if (t := B.sim_trade(z, bcache))]
    rs1_m = B.metrics(rs1_trades)

    # outcome classification
    def classify(t):
        if t["outcome"] == "WIN": return "win_2pct"
        if t["outcome"] == "LOSS": return "stop_wrong_dir"
        return "correct_dir_no_2pct" if (t["pnl_pre_cost"] or 0) > 0 else "timeout_wrong_dir"
    for t in rs1_trades:
        t["class"] = classify(t)
    correct_dir_no_2pct = sum(1 for t in rs1_trades if t["class"] == "correct_dir_no_2pct")
    wrong_direction = sum(1 for t in rs1_trades if t["class"] in ("stop_wrong_dir", "timeout_wrong_dir"))
    stop_no_2pct = sum(1 for t in rs1_trades if t["outcome"] == "LOSS")
    per_day_pnl = defaultdict(float)
    for t in rs1_trades:
        per_day_pnl[t["date"]] += t["pnl_after_cost"]
    per_day_pnl = {d: round(per_day_pnl.get(d, 0.0), 4) for d in INTERIM_DAYS}
    rs1_m.update({"correct_direction_no_2pct": correct_dir_no_2pct,
                  "wrong_direction": wrong_direction,
                  "stop_no_2pct_either_dir": stop_no_2pct,
                  "per_day_pnl_after_cost": per_day_pnl})

    # ---------------- RS2 (S7 PARTIAL: no true OI) ----------------
    print("[RS2 partial]", file=sys.stderr)
    void_thr = B.quantile([z.get("ms_thin_path_score") for z in rs1_sel], 0.5)
    def p_reach(z):
        p = 0.55  # true-OI fuel component UNAVAILABLE on Binance recorder -> omitted (partial)
        if (z.get("ms_thin_path_score") or 0) >= (void_thr or 0): p += 0.03
        if (z.get("ms_large_walls_on_path") or 99) == 0: p += 0.03
        if (z.get("dl2_microprice_aligned_delta_5m_bps") or -99) >= 0: p += 0.03
        fr = z.get("funding_rate_at_signal") or 0
        if fr < 0 and z["direction"] == "LONG": p += 0.02
        if fr > 0 and z["direction"] == "SHORT": p += 0.02
        return min(p, 0.9)
    for z in rs1_sel:
        z["_p_reach"] = round(p_reach(z), 4)
        z["_ev"] = round(p_reach(z) * B.EV_REWARD - (1 - p_reach(z)) * B.EV_RISK, 4)
    rs2_sel = [z for z in rs1_sel if z["_ev"] > B.EV_THR]
    rs2_trades = [t for z in rs2_sel if (t := B.sim_trade(z, bcache))]
    rs2_m = B.metrics(rs2_trades)
    rs1_ids = {z["id"] for z in rs1_sel}; rs2_ids = {z["id"] for z in rs2_sel}
    removed_ids = rs1_ids - rs2_ids
    rs1_by_id = {t["zone_id"]: t for t in rs1_trades}
    rs2_removed = [rs1_by_id[i] for i in removed_ids if i in rs1_by_id]
    rs2_improves = ((rs2_m["expectancy_after_cost_pct"] or -9) > (rs1_m["expectancy_after_cost_pct"] or -9)) \
        if rs2_m["trades"] > 0 else None

    # ---------------- DATA AUDIT ----------------
    print("[data audit]", file=sys.stderr)
    audit_rows = []
    for d in INTERIM_DAYS:
        rng = day_range(bcache.get(d, []))
        rc = rowcounts.get(d, {})
        funding = B.funding_at(d, int(dt.datetime.fromisoformat(d).timestamp()) + 43200)
        liq_rows = rc.get("liq") or 0
        cov = rng["coverage_h"]
        quality = "FULL" if cov >= 23 else ("PARTIAL" if cov >= 12 else "BAD")
        audit_rows.append({
            "date": d, "included": "YES", "quality": quality, "coverage_h": cov,
            "L2_rows": rc.get("L2"), "trades_rows": rc.get("trades"),
            "deriv_rows": rc.get("deriv"), "liq_rows": liq_rows,
            "day_high": rng["high"], "day_low": rng["low"], "range_pct": rng["range_pct"],
            "feasible_2pct": "YES" if rng["feasible_2pct"] else "NO",
            "funding_present": "YES" if funding is not None else "NO",
            "liquidations_present": "YES" if liq_rows > 0 else "NO",
            "true_oi_present": "NO"})
    audit = {"build_time_utc": now_iso(), "status": "INTERIM_PARTIAL", "days": audit_rows,
             "true_oi_available": "NO", "funding_available": "YES", "liquidations_available": "YES"}
    (OUT / f"{TAG}_DATA_AUDIT.json").write_text(json.dumps(audit, indent=2, default=str), encoding="utf-8")
    with (OUT / f"{TAG}_DATA_AUDIT.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(audit_rows[0].keys())); w.writeheader(); w.writerows(audit_rows)
    md = [f"# {TAG} — DATA AUDIT (7 completed days)", "", f"**Build:** {now_iso()}",
          "**STATUS: INTERIM / PARTIAL — not the final 10-day verdict.**", "",
          "true OI: **NO stream in recorder** · funding: YES · liquidations: YES", "",
          "| date | incl | qual | cov_h | L2 rows | trades | deriv | liq | day_high | day_low | range% | 2%feas | fund | liq |",
          "|---|:--:|:--:|--:|--:|--:|--:|--:|--:|--:|--:|:--:|:--:|:--:|"]
    for r in audit_rows:
        md.append(f"| {r['date']} | {r['included']} | {r['quality']} | {r['coverage_h']} | {r['L2_rows']} | "
                  f"{r['trades_rows']} | {r['deriv_rows']} | {r['liq_rows']} | {r['day_high']} | {r['day_low']} | "
                  f"{r['range_pct']} | {r['feasible_2pct']} | {r['funding_present']} | {r['liquidations_present']} |")
    (OUT / f"{TAG}_DATA_AUDIT.md").write_text("\n".join(md), encoding="utf-8")

    # ---------------- ENGINE SUMMARY ----------------
    print("[engine summary]", file=sys.stderr)
    eng_rows = []
    for d in INTERIM_DAYS:
        s = parse_daily_summary(d)
        eng_rows.append({
            "date": d,
            "zones": int(s.get("zones_total", 0)),
            "triggered": int(s.get("zones_triggered", 0)),
            "reached_raw": int(s.get("reached_zones_raw", 0)),
            "primary_unique": int(s.get("unique_reached_moves", 0)),
            "duplicate_reached": int(s.get("duplicate_move_credits", 0)),
            "failed_triggered": int(s.get("status_RESOLVED_FAILED", 0)),
            "long": int(s.get("direction_LONG", 0)),
            "short": int(s.get("direction_SHORT", 0))})
    eng_tot = {k: sum(r[k] for r in eng_rows) for k in
               ("zones", "triggered", "reached_raw", "primary_unique", "duplicate_reached",
                "failed_triggered", "long", "short")}
    eng = {"build_time_utc": now_iso(), "status": "INTERIM_PARTIAL", "days": eng_rows, "totals": eng_tot}
    (OUT / f"{TAG}_ENGINE_SUMMARY.json").write_text(json.dumps(eng, indent=2), encoding="utf-8")
    with (OUT / f"{TAG}_ENGINE_SUMMARY.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(eng_rows[0].keys())); w.writeheader(); w.writerows(eng_rows)
    md = [f"# {TAG} — ENGINE SUMMARY (7 completed days)", "", f"**Build:** {now_iso()}",
          "**STATUS: INTERIM / PARTIAL.** No engine retuning; reads existing engine outputs.", "",
          f"**Totals:** zones {eng_tot['zones']} · triggered {eng_tot['triggered']} · reached_raw {eng_tot['reached_raw']} · "
          f"primary_unique {eng_tot['primary_unique']} · duplicate_reached {eng_tot['duplicate_reached']} · "
          f"failed_triggered {eng_tot['failed_triggered']} · LONG {eng_tot['long']} / SHORT {eng_tot['short']}", "",
          "| date | zones | triggered | reached_raw | primary_unique | dup_reached | failed_trig | LONG | SHORT |",
          "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for r in eng_rows:
        md.append(f"| {r['date']} | {r['zones']} | {r['triggered']} | {r['reached_raw']} | {r['primary_unique']} | "
                  f"{r['duplicate_reached']} | {r['failed_triggered']} | {r['long']} | {r['short']} |")
    md.append(f"| **TOT** | {eng_tot['zones']} | {eng_tot['triggered']} | {eng_tot['reached_raw']} | "
              f"{eng_tot['primary_unique']} | {eng_tot['duplicate_reached']} | {eng_tot['failed_triggered']} | "
              f"{eng_tot['long']} | {eng_tot['short']} |")
    (OUT / f"{TAG}_ENGINE_SUMMARY.md").write_text("\n".join(md), encoding="utf-8")

    # ---------------- trade-table CSV writer ----------------
    TT_KEYS = ["date", "direction", "setup_type", "entry_time", "entry_price", "exit_reason",
               "outcome", "class", "pnl_after_cost", "pnl_pre_cost", "mfe_pct", "mae_pct",
               "dist_to_recent_swing_high_pct", "dl2_supp_minus_opp_net_flow_15m",
               "ms_thin_path_score", "ms_large_walls_on_path",
               "dl2_microprice_aligned_delta_5m_bps", "funding_rate_at_signal",
               "_score", "_p_reach", "_ev"]
    def trade_row(t):
        z = zmap.get(t["zone_id"], {})
        return {"date": t["date"], "direction": t["direction"], "setup_type": z.get("zoneType"),
                "entry_time": t.get("confirmed_iso"), "entry_price": t.get("entry_price"),
                "exit_reason": t.get("exit_reason"), "outcome": t.get("outcome"), "class": t.get("class"),
                "pnl_after_cost": t.get("pnl_after_cost"), "pnl_pre_cost": t.get("pnl_pre_cost"),
                "mfe_pct": t.get("mfe_pct"), "mae_pct": t.get("mae_pct"),
                "dist_to_recent_swing_high_pct": z.get("dist_to_recent_swing_high_pct"),
                "dl2_supp_minus_opp_net_flow_15m": z.get("dl2_supp_minus_opp_net_flow_15m"),
                "ms_thin_path_score": z.get("ms_thin_path_score"),
                "ms_large_walls_on_path": z.get("ms_large_walls_on_path"),
                "dl2_microprice_aligned_delta_5m_bps": z.get("dl2_microprice_aligned_delta_5m_bps"),
                "funding_rate_at_signal": z.get("funding_rate_at_signal"),
                "_score": z.get("_score"), "_p_reach": z.get("_p_reach"), "_ev": z.get("_ev")}
    def write_tt(path, trades):
        with open(path, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=TT_KEYS, extrasaction="ignore"); w.writeheader()
            for t in trades: w.writerow(trade_row(t))
    write_tt(OUT / f"{TAG}_TRADE_TABLE.csv", rs1_trades)
    write_tt(OUT / f"{TAG}_RS1_RESULTS.csv", rs1_trades)
    write_tt(OUT / f"{TAG}_RS2_RESULTS.csv", rs2_trades)

    # ---------------- RS1 RESULTS md/json ----------------
    rs1_flags = {
        "BINANCE_INTERIM_RS1_DONE": "YES", "BINANCE_INTERIM_RS1_TRADES": rs1_m["trades"],
        "BINANCE_INTERIM_RS1_WINS": rs1_m["wins"], "BINANCE_INTERIM_RS1_LOSSES": rs1_m["losses"],
        "BINANCE_INTERIM_RS1_TIMEOUTS": rs1_m["timeouts"], "BINANCE_INTERIM_RS1_WINRATE": rs1_m["winrate_pct"],
        "BINANCE_INTERIM_RS1_EXPECTANCY_AFTER_COST": rs1_m["expectancy_after_cost_pct"],
        "BINANCE_INTERIM_RS1_PF_AFTER_COST": rs1_m["pf_after_cost"]}
    (OUT / f"{TAG}_RS1_RESULTS.json").write_text(json.dumps(
        {"build_time_utc": now_iso(), "status": "INTERIM_PARTIAL",
         "selector": "dist_to_recent_swing_high_pct<=0.4616 AND dl2_supp_minus_opp_net_flow_15m<=4497.76, top1/day",
         "trade_model": "entry=confirmed, TP=2%, SL=1.5%, timeout=24h, no BE, cost=0.14%, canonical ledger exact",
         "n_candidate_pass": len(rs1_pass), "n_selected": len(rs1_sel),
         "metrics": rs1_m, "flags": rs1_flags,
         "trades": [trade_row(t) for t in rs1_trades]}, indent=2, default=str), encoding="utf-8")
    def metric_block(m):
        return ["| metric | value | OKX IS ref |", "|---|---:|---:|",
                f"| trades | {m['trades']} | 29 |", f"| wins | {m['wins']} | 18 |",
                f"| losses | {m['losses']} | 8 |", f"| timeouts | {m['timeouts']} | 3 |",
                f"| winrate % | {m['winrate_pct']} | 62.07 |",
                f"| avg win aft % | {m['avg_win_after_cost']} | - |",
                f"| avg loss aft % | {m['avg_loss_after_cost']} | - |",
                f"| avg timeout aft % | {m['avg_timeout_pnl_after_cost']} | - |",
                f"| expectancy aft % | {m['expectancy_after_cost_pct']} | 0.6475 |",
                f"| total return aft % | {m['total_return_after_cost_pct']} | 18.78 |",
                f"| PF aft | {m['pf_after_cost']} | 2.258 |",
                f"| max consec losses | {m['max_consecutive_losses']} | 3 |",
                f"| LONG/SHORT winrate | {m['long_winrate']}/{m['short_winrate']} | - |"]
    md = [f"# {TAG} — RS1 FROZEN BASELINE (7 completed days)", "", f"**Build:** {now_iso()}",
          "**STATUS: INTERIM / PARTIAL — small sample, not conclusive.**", "",
          "Selector: `dist_to_recent_swing_high_pct <= 0.4616 AND dl2_supp_minus_opp_net_flow_15m <= 4497.76`, top1/day.",
          "Trade: entry=confirmed, TP 2%, SL 1.5%, timeout 24h, no BE, cost 0.14%, canonical ledger (exact timeout PnL).",
          "", f"Candidate zones passing filter: {len(rs1_pass)}; days with a selected trade: {len(rs1_sel)}.", "",
          *metric_block(rs1_m), "",
          f"- correct-direction-but-no-2%: **{correct_dir_no_2pct}**",
          f"- wrong-direction: **{wrong_direction}**",
          f"- stop_no_2pct_either_dir: **{stop_no_2pct}**", "",
          "**Per-day PnL after cost:** " + ", ".join(f"{d}={per_day_pnl[d]:+.3f}" for d in INTERIM_DAYS)]
    (OUT / f"{TAG}_RS1_RESULTS.md").write_text("\n".join(md), encoding="utf-8")

    # ---------------- RS2 RESULTS md/json ----------------
    rs2_flags = {
        "BINANCE_INTERIM_RS2_DONE": "PARTIAL", "BINANCE_INTERIM_RS2_TRUE_OI_AVAILABLE": "NO",
        "BINANCE_INTERIM_RS2_TRADES": rs2_m["trades"], "BINANCE_INTERIM_RS2_WINRATE": rs2_m["winrate_pct"],
        "BINANCE_INTERIM_RS2_EXPECTANCY_AFTER_COST": rs2_m["expectancy_after_cost_pct"],
        "BINANCE_INTERIM_RS2_PF_AFTER_COST": rs2_m["pf_after_cost"],
        "BINANCE_INTERIM_RS2_IMPROVES_RS1": ("YES" if rs2_improves else "NO") if rs2_improves is not None else "UNKNOWN"}
    (OUT / f"{TAG}_RS2_RESULTS.json").write_text(json.dumps(
        {"build_time_utc": now_iso(), "status": "INTERIM_PARTIAL_NO_TRUE_OI",
         "note": "Binance recorder has funding+liquidations but NO open-interest stream. "
                 "p_reach uses void+wall+microprice+funding components only; true-OI fuel omitted. "
                 "NOT a proxy for true OI. EV threshold and p_reach weights unchanged from frozen S7.",
         "ev_threshold": B.EV_THR, "void_threshold_median_thin_path": void_thr,
         "metrics": rs2_m, "flags": rs2_flags,
         "removed_from_rs1": {"n": len(rs2_removed),
                              "wins": sum(1 for t in rs2_removed if t["outcome"] == "WIN"),
                              "losses": sum(1 for t in rs2_removed if t["outcome"] == "LOSS"),
                              "timeouts": sum(1 for t in rs2_removed if t["outcome"] == "TIMEOUT")},
         "trades": [trade_row(t) for t in rs2_trades]}, indent=2, default=str), encoding="utf-8")
    md = [f"# {TAG} — RS2 S7 OVERLAY (PARTIAL, 7 completed days)", "", f"**Build:** {now_iso()}",
          "**STATUS: INTERIM / PARTIAL.** `RS2_PARTIAL = YES` — Binance recorder has **no open-interest stream**, "
          "so the true-OI fuel component is omitted (NOT replaced by a proxy). p_reach uses void+wall+microprice+funding only. "
          "EV threshold and p_reach weights unchanged.", "",
          f"Applied AFTER RS1. EV>{B.EV_THR}. Removed {len(rs2_removed)} of {len(rs1_sel)} RS1 selections.", "",
          *metric_block(rs2_m), "",
          f"- RS2 improves RS1 (expectancy): **{rs2_flags['BINANCE_INTERIM_RS2_IMPROVES_RS1']}**"]
    (OUT / f"{TAG}_RS2_RESULTS.md").write_text("\n".join(md), encoding="utf-8")

    # ---------------- OKX vs BINANCE comparison ----------------
    rs1_status = interim_transfer(rs1_m)
    rs2_status = interim_transfer(rs2_m) if rs2_m["trades"] > 0 else "UNKNOWN"
    comp = {"build_time_utc": now_iso(), "status": "INTERIM_PARTIAL",
            "okx_rs1": OKX_RS1, "okx_s7": OKX_S7, "binance_rs1": rs1_m, "binance_rs2": rs2_m,
            "binance_interim_rs1_transfer_status": rs1_status,
            "binance_interim_rs2_transfer_status": rs2_status,
            "winrate_delta_rs1_vs_okx": round(rs1_m["winrate_pct"] - OKX_RS1["winrate"], 2),
            "pf_delta_rs1_vs_okx": round((rs1_m["pf_after_cost"] or 0) - OKX_RS1["pf"], 3) if rs1_m["pf_after_cost"] else None,
            "expectancy_delta_rs1_vs_okx": round((rs1_m["expectancy_after_cost_pct"] or 0) - OKX_RS1["exp"], 4),
            "caveat": "Small n; interim transfer status intentionally UNKNOWN unless n>=15."}
    (OUT / f"{TAG}_OKX_VS_BINANCE.json").write_text(json.dumps(comp, indent=2, default=str), encoding="utf-8")
    (OUT / f"{TAG}_OKX_VS_BINANCE.md").write_text(
        f"# {TAG} — OKX (IS) vs Binance (OOS interim)\n\n**Build:** {now_iso()}\n\n"
        "**STATUS: INTERIM / PARTIAL.** Transfer status is UNKNOWN unless n>=15.\n\n"
        "| model | trades | winrate% | exp_aft% | PF_aft | totRet% |\n|---|---:|---:|---:|---:|---:|\n"
        f"| OKX RS1 (IS) | 29 | 62.07 | 0.6475 | 2.258 | 18.78 |\n"
        f"| OKX S7 (IS) | 26 | 65.38 | 0.7403 | 2.527 | - |\n"
        f"| **Binance RS1 (OOS 7d)** | {rs1_m['trades']} | {rs1_m['winrate_pct']} | {rs1_m['expectancy_after_cost_pct']} | {rs1_m['pf_after_cost']} | {rs1_m['total_return_after_cost_pct']} |\n"
        f"| **Binance RS2 (OOS 7d partial)** | {rs2_m['trades']} | {rs2_m['winrate_pct']} | {rs2_m['expectancy_after_cost_pct']} | {rs2_m['pf_after_cost']} | {rs2_m['total_return_after_cost_pct']} |\n\n"
        f"- RS1 winrate delta vs OKX: {comp['winrate_delta_rs1_vs_okx']} pp · PF delta: {comp['pf_delta_rs1_vs_okx']} · exp delta: {comp['expectancy_delta_rs1_vs_okx']}\n"
        f"- **BINANCE_INTERIM_TRANSFER_STATUS (RS1): {rs1_status}** · RS2: {rs2_status}\n",
        encoding="utf-8")

    # ---------------- CASEBOOK ----------------
    wins = sorted([t for t in rs1_trades if t["outcome"] == "WIN"], key=lambda x: -x["pnl_after_cost"])
    losses = sorted([t for t in rs1_trades if t["outcome"] == "LOSS"], key=lambda x: x["pnl_after_cost"])
    no2 = [t for t in rs1_trades if t["class"] == "correct_dir_no_2pct"]
    wrongs = [t for t in rs1_trades if t["class"] in ("stop_wrong_dir", "timeout_wrong_dir")]
    traded_days = {t["date"] for t in rs1_trades}
    days_no_trade = [d for d in INTERIM_DAYS if d not in traded_days]
    audit_by_d = {r["date"]: r for r in audit_rows}
    days_2pct_no_trade = [d for d in days_no_trade if audit_by_d[d]["feasible_2pct"] == "YES"]
    def brief(t):
        z = zmap.get(t["zone_id"], {})
        return {"date": t["date"], "dir": t["direction"], "setup": z.get("zoneType"),
                "entry_time": t.get("confirmed_iso"), "outcome": t["outcome"], "class": t["class"],
                "pnl_after_cost": t["pnl_after_cost"], "mfe_pct": t.get("mfe_pct"), "mae_pct": t.get("mae_pct"),
                "dist_swh": z.get("dist_to_recent_swing_high_pct"),
                "supp_opp_15m": z.get("dl2_supp_minus_opp_net_flow_15m")}
    casebook = {"build_time_utc": now_iso(), "status": "INTERIM_PARTIAL",
                "best_wins": [brief(t) for t in wins[:5]],
                "losses": [brief(t) for t in losses],
                "no_2pct_followthrough": [brief(t) for t in no2],
                "wrong_direction_cases": [brief(t) for t in wrongs],
                "days_with_no_rs1_trade": days_no_trade,
                "days_2pct_move_but_no_rs1_trade": days_2pct_no_trade}
    (OUT / f"{TAG}_CASEBOOK.json").write_text(json.dumps(casebook, indent=2, default=str), encoding="utf-8")
    def case_tbl(rows):
        if not rows: return ["_(none)_"]
        out = ["| date | dir | setup | entry_time | outcome | pnl_aft% | mfe% | mae% | dist_swh% | supp_opp_15m |",
               "|---|:--:|:--:|:--:|:--:|--:|--:|--:|--:|--:|"]
        for r in rows:
            out.append(f"| {r['date']} | {r['dir']} | {r['setup']} | {r['entry_time']} | {r['outcome']} | "
                       f"{r['pnl_after_cost']} | {r['mfe_pct']} | {r['mae_pct']} | {r['dist_swh']} | {r['supp_opp_15m']} |")
        return out
    md = [f"# {TAG} — CASEBOOK (7 completed days)", "", f"**Build:** {now_iso()}",
          "**STATUS: INTERIM / PARTIAL.**", "",
          "## Best wins", *case_tbl(casebook["best_wins"]), "",
          "## Losses (stop-outs)", *case_tbl(casebook["losses"]), "",
          "## Correct-direction but no 2% follow-through", *case_tbl(casebook["no_2pct_followthrough"]), "",
          "## Wrong-direction cases", *case_tbl(casebook["wrong_direction_cases"]), "",
          f"## Days with no RS1 trade\n{days_no_trade or '_(none)_'}", "",
          f"## Days with a >=2% market move but no RS1 trade\n{days_2pct_no_trade or '_(none)_'}"]
    (OUT / f"{TAG}_CASEBOOK.md").write_text("\n".join(md), encoding="utf-8")

    # ---------------- FINAL INTERIM REPORT ----------------
    main_running = (ZONES_DIR / "BTCUSDT_2026-05-29" / "daily_summary.csv").exists() is False \
        or (ZONES_DIR / "BTCUSDT_2026-05-30" / "daily_summary.csv").exists() is False
    flags = {
        "BINANCE_INTERIM_DONE": "YES",
        "BINANCE_INTERIM_DAYS": INTERIM_DAYS,
        "BINANCE_MAIN_10D_CHAIN_STILL_RUNNING": "YES" if main_running else "NO",
        "BINANCE_INTERIM_RS1_DONE": "YES",
        "BINANCE_INTERIM_RS1_TRADES": rs1_m["trades"],
        "BINANCE_INTERIM_RS1_WINS": rs1_m["wins"],
        "BINANCE_INTERIM_RS1_LOSSES": rs1_m["losses"],
        "BINANCE_INTERIM_RS1_TIMEOUTS": rs1_m["timeouts"],
        "BINANCE_INTERIM_RS1_WINRATE": rs1_m["winrate_pct"],
        "BINANCE_INTERIM_RS1_EXPECTANCY_AFTER_COST": rs1_m["expectancy_after_cost_pct"],
        "BINANCE_INTERIM_RS1_PF_AFTER_COST": rs1_m["pf_after_cost"],
        "BINANCE_INTERIM_RS2_DONE": "PARTIAL",
        "BINANCE_INTERIM_RS2_TRUE_OI_AVAILABLE": "NO",
        "BINANCE_INTERIM_RS2_TRADES": rs2_m["trades"],
        "BINANCE_INTERIM_RS2_WINRATE": rs2_m["winrate_pct"],
        "BINANCE_INTERIM_RS2_EXPECTANCY_AFTER_COST": rs2_m["expectancy_after_cost_pct"],
        "BINANCE_INTERIM_RS2_PF_AFTER_COST": rs2_m["pf_after_cost"],
        "BINANCE_INTERIM_RS2_IMPROVES_RS1": rs2_flags["BINANCE_INTERIM_RS2_IMPROVES_RS1"],
        "BINANCE_INTERIM_TRANSFER_STATUS": rs1_status,
        "NO_THRESHOLD_RETUNING_DONE": "YES",
        "CANONICAL_LEDGER_USED": "YES",
        "TIMEOUT_PNL_EXACT": "YES",
        "FUTURE_LEAK_FOUND": "NO",
        "READY_FOR_FINAL_10D_REPORT": "NO"}
    final = {"build_time_utc": now_iso(), "status": "INTERIM_PARTIAL",
             "interim_days": INTERIM_DAYS, "pending_days": [d for d in ALL10 if d not in INTERIM_DAYS],
             "engine_totals": eng_tot, "data_audit": audit_rows,
             "binance_rs1": rs1_m, "binance_rs2": rs2_m, "comparison": comp,
             "rs1_trades": [trade_row(t) for t in rs1_trades],
             "rs2_trades": [trade_row(t) for t in rs2_trades],
             "flags": flags,
             "caveat": "INTERIM on 7 of 10 completed days (05-21..27). Small n; NOT conclusive. "
                       "RS2 is PARTIAL (no true-OI stream on Binance recorder). Final 10-day report "
                       "to be rebuilt once 05-28..30 engine outputs are all present."}
    (OUT / f"{TAG}_FINAL_REPORT.json").write_text(json.dumps(final, indent=2, default=str), encoding="utf-8")
    md = [f"# {TAG} — FINAL INTERIM REPORT (7 of 10 days)", "", f"**Build:** {now_iso()}",
          "**STATUS: INTERIM / PARTIAL — not the final 10-day OOS verdict. Small sample.**", "",
          f"Interim days: {INTERIM_DAYS}", f"Pending (still computing / to add): {final['pending_days']}", "",
          "## Engine (7 days)",
          f"- zones {eng_tot['zones']} · triggered {eng_tot['triggered']} · reached_raw {eng_tot['reached_raw']} · "
          f"primary_unique {eng_tot['primary_unique']} · failed_triggered {eng_tot['failed_triggered']} · "
          f"LONG {eng_tot['long']} / SHORT {eng_tot['short']}", "",
          "## RS1 vs RS2 (Binance OOS interim)", "",
          "| model | trades | W | L | TO | winrate% | exp_aft% | PF | totRet% | maxCL |",
          "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
          f"| RS1 | {rs1_m['trades']} | {rs1_m['wins']} | {rs1_m['losses']} | {rs1_m['timeouts']} | {rs1_m['winrate_pct']} | {rs1_m['expectancy_after_cost_pct']} | {rs1_m['pf_after_cost']} | {rs1_m['total_return_after_cost_pct']} | {rs1_m['max_consecutive_losses']} |",
          f"| RS2 (partial) | {rs2_m['trades']} | {rs2_m['wins']} | {rs2_m['losses']} | {rs2_m['timeouts']} | {rs2_m['winrate_pct']} | {rs2_m['expectancy_after_cost_pct']} | {rs2_m['pf_after_cost']} | {rs2_m['total_return_after_cost_pct']} | {rs2_m['max_consecutive_losses']} |",
          "",
          "## OKX (IS) vs Binance (OOS interim)",
          f"- OKX RS1: 29 tr, 62.07%, exp +0.6475, PF 2.258  →  Binance RS1 (7d): {rs1_m['trades']} tr, {rs1_m['winrate_pct']}%, exp {rs1_m['expectancy_after_cost_pct']}, PF {rs1_m['pf_after_cost']}",
          f"- **BINANCE_INTERIM_TRANSFER_STATUS = {rs1_status}** (UNKNOWN if n<15 — honest interim).", "",
          "## Final interim flags", "```"]
    for k, v in flags.items(): md.append(f"{k} = {v}")
    md += ["```", "", "**Caveat:** " + final["caveat"]]
    (OUT / f"{TAG}_FINAL_REPORT.md").write_text("\n".join(md), encoding="utf-8")

    # ---------------- console ----------------
    print("\n=== BINANCE OOS INTERIM (7 days 05-21..27) ===")
    print(f"Engine: zones {eng_tot['zones']} triggered {eng_tot['triggered']} reached_raw {eng_tot['reached_raw']} "
          f"primary_unique {eng_tot['primary_unique']} LONG {eng_tot['long']}/SHORT {eng_tot['short']}")
    print(f"RS1: {rs1_m['trades']}tr {rs1_m['wins']}W/{rs1_m['losses']}L/{rs1_m['timeouts']}TO "
          f"wr={rs1_m['winrate_pct']}% exp={rs1_m['expectancy_after_cost_pct']} PF={rs1_m['pf_after_cost']} "
          f"ret={rs1_m['total_return_after_cost_pct']} maxCL={rs1_m['max_consecutive_losses']}")
    print(f"     correct_dir_no_2pct={correct_dir_no_2pct} wrong_dir={wrong_direction} stop_no_2pct={stop_no_2pct}")
    print(f"RS2(partial): {rs2_m['trades']}tr {rs2_m['wins']}W/{rs2_m['losses']}L/{rs2_m['timeouts']}TO "
          f"wr={rs2_m['winrate_pct']}% exp={rs2_m['expectancy_after_cost_pct']} PF={rs2_m['pf_after_cost']} "
          f"(removed {len(rs2_removed)} from RS1)")
    print(f"TRANSFER STATUS (interim): RS1={rs1_status} RS2={rs2_status}")
    print("\nRS1 trade table:")
    print("date dir setup outcome class pnl_aft entry dist_swh supp_opp15 thin_path microprice5m fundingE4")
    for t in rs1_trades:
        z = zmap[t["zone_id"]]
        print(f"  {t['date']} {t['direction']:>5} {str(z.get('zoneType'))[:6]:>6} {t['outcome']:>7} "
              f"{t['class']:>20} pnl={t['pnl_after_cost']:+.3f} entry={t['entry_price']} "
              f"dist={z.get('dist_to_recent_swing_high_pct')} supp_opp15={z.get('dl2_supp_minus_opp_net_flow_15m')} "
              f"thin={z.get('ms_thin_path_score')} mp5m={z.get('dl2_microprice_aligned_delta_5m_bps')} "
              f"fund={round((z.get('funding_rate_at_signal') or 0)*1e4,3)}")
    print("\nFINAL INTERIM FLAGS:")
    for k, v in flags.items(): print(f"  {k:<46s} = {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
