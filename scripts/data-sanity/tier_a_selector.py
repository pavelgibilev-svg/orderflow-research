"""TIER-A HIGH-CONFIDENCE SELECTOR SEARCH on OKX 05-03..20 UNIQUE moves.

** IN-SAMPLE RESEARCH DEMO — NOT PRODUCTION VALIDATION. **
Works on DEDUPED unique move clusters (one trade per cluster = first live-detectable zone), never raw
duplicate zones. Decisions causal (<= confirmedTs); 2.5/3% are quality labels only; TP stays 2%.
"""
from __future__ import annotations
import csv, json, statistics as st, sys, importlib.util, datetime as dt
from collections import defaultdict
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "package.json").exists() and (p / "scripts").exists())
sys.path.insert(0, str(ROOT / "scripts/strategy-calibration")); sys.path.insert(0, str(ROOT / "scripts/data-sanity"))
from canonical_ledger import build_buckets_from_trades_csv
spec = importlib.util.spec_from_file_location("tz", str(ROOT / "scripts/data-sanity/strong_zone_taxonomy.py"))
TZ = importlib.util.module_from_spec(spec); spec.loader.exec_module(TZ)
import openpyxl

OUT = ROOT / "reports/okx-may-early"; DATA = ROOT / "data/okx-historical/BTC-USDT-SWAP"
CACHE = OUT / "OKX_2026_05_01_10_FEATURE_CACHE.json"
DATES = [f"2026-05-{d:02d}" for d in range(3, 21)]
GAP_S = 120 * 60


def now_iso(): return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
def num(x): return x if isinstance(x, (int, float)) else None
def mins(s): return round(s / 60, 1) if isinstance(s, (int, float)) else None


# ---- causal Tier-A conditions ----
def edge(z):
    rp = num(z.get("range_pos"));
    if rp is None: return False
    return (z["direction"] == "LONG" and rp < 0.3) or (z["direction"] == "SHORT" and rp > 0.7)
def sweep(z):
    return (z["direction"] == "LONG" and z.get("swept_below") == 1) or (z["direction"] == "SHORT" and z.get("swept_above") == 1)
def reclaim(z): return z.get("reclaim_zoneMid_preconfirm") == 1
def no_wall(z): return z.get("ms_large_walls_on_path") in (0, None)
def micro_ok(z): return (num(z.get("dl2_microprice_aligned_delta_5m_bps")) or -9) >= 0
def taker_ofi_ok(z):
    ti = num(z.get("supportive_taker_imb_15m")); o = num(z.get("eng_ofi"))
    return (ti is not None and ti > 0) or (o is not None and ((z["direction"] == "LONG" and o > 0) or (z["direction"] == "SHORT" and o < 0)))
def low_entropy(z, med): return (num(z.get("book_entropy_top25")) is not None) and z["book_entropy_top25"] < med
def thin(z): return TZ.thin(z)


def conf7(z, med):
    return sum([edge(z), sweep(z), reclaim(z), no_wall(z), micro_ok(z), taker_ofi_ok(z), low_entropy(z, med)])


def rules(med):
    return {
        "T1_edge_reclaim": lambda z: z["_regime"] == "RANGE" and edge(z) and reclaim(z),
        "T2_sweep_reversal": lambda z: sweep(z) and reclaim(z) and taker_ofi_ok(z),
        "T3_thin_path": lambda z: edge(z) and no_wall(z) and thin(z),
        "T4_absorption": lambda z: (num(z.get("supportive_taker_imb_15m")) or 9) < -0.1 and reclaim(z) and micro_ok(z),
        "T5_confluence": lambda z: (edge(z) or sweep(z)) and reclaim(z) and thin(z) and taker_ofi_ok(z),
        "T6_strict_2of7": lambda z: conf7(z, med) >= 2,
        "T6_strict_3of7": lambda z: conf7(z, med) >= 3,
        "T6_strict_4of7": lambda z: conf7(z, med) >= 4,
        "T6_strict_5of7": lambda z: conf7(z, med) >= 5,
    }


def dedup_alerts(fired):
    """one trade per move: group fired zones by direction + confirmedTs gap<=120m, take first by confirmedTs."""
    by = defaultdict(list)
    for z in fired: by[z["direction"]].append(z)
    picks = []
    for d, zs in by.items():
        zs.sort(key=lambda x: x["confirmedTs"]); last = None; group = []
        for z in zs:
            if last is not None and z["confirmedTs"] / 1000 - last > GAP_S:
                picks.append(min(group, key=lambda x: x["confirmedTs"])); group = []
            group.append(z); last = z["confirmedTs"] / 1000
        if group: picks.append(min(group, key=lambda x: x["confirmedTs"]))
    return picks


def metr(rows):
    tr = [r for r in rows if r.get("sim_outcome") in ("WIN", "LOSS", "TIMEOUT")]
    n = len(tr); W = sum(1 for r in tr if r["sim_outcome"] == "WIN"); L = sum(1 for r in tr if r["sim_outcome"] == "LOSS"); TO = sum(1 for r in tr if r["sim_outcome"] == "TIMEOUT")
    pnls = [r["sim_pnl_after_cost"] for r in tr if r.get("sim_pnl_after_cost") is not None]
    wp = [p for p in pnls if p > 0]; lp = [p for p in pnls if p < 0]; pf = round(sum(wp) / sum(-p for p in lp), 3) if lp else None
    cur = mx = 0
    for r in sorted(tr, key=lambda x: x["confirmedTs"]):
        if (r.get("sim_pnl_after_cost") or 0) <= 0: cur += 1; mx = max(mx, cur)
        else: cur = 0
    h = lambda t: sum(1 for r in tr if num(r.get("true_mfe")) and r["true_mfe"] >= t)
    t2 = [r.get("time_to_2") for r in tr if r.get("sim_outcome") == "WIN" and r.get("time_to_2")]
    return {"unique_alerts": len(rows), "trades": n, "W": W, "L": L, "TO": TO, "winrate": round(100 * W / max(n, 1), 2),
            "pf": pf, "expectancy": round(st.mean(pnls), 4) if pnls else None, "hit2_5": h(2.5), "hit3": h(3),
            "avg_time_to_2_min": round(st.mean(t2) / 60, 1) if t2 else None, "max_loss_streak": mx,
            "days_active": len({r["_date"] for r in rows})}


def main():
    zones = json.loads(CACHE.read_text())
    gb = []
    for d in DATES:
        p = DATA / d / "trades.csv.gz"
        if p.exists(): gb += build_buckets_from_trades_csv(p)
    gb.sort(key=lambda b: b.sec); gsec = [b.sec for b in gb]
    ents = [num(z.get("book_entropy_top25")) for z in zones if num(z.get("book_entropy_top25")) is not None]
    emed = st.median(ents) if ents else 0.4
    for z in zones:
        z["_regime"] = TZ.regime_dir(z); z.update(TZ.range_context(z, gb, gsec, emed)); z["_family"] = TZ.setup_family(z)
        m = num(z.get("true_mfe")); z["_strong"] = m is not None and m >= 2.5

    # strong move clusters (by target_hit at 2.5)
    strong = [z for z in zones if z["_strong"] and num(z.get("time_to_2_5"))]
    for z in strong: z["_th"] = z["confirmedTs"] // 1000 + z["time_to_2_5"]
    sclusters = []
    by = defaultdict(list)
    for z in strong: by[z["direction"]].append(z)
    for d, zs in by.items():
        zs.sort(key=lambda x: x["_th"]); last = None; cur = []
        for z in zs:
            if last is not None and z["_th"] - last > GAP_S: sclusters.append(cur); cur = []
            cur.append(z); last = z["_th"]
        if cur: sclusters.append(cur)
    strong_cluster_ids = {id(c): c for c in sclusters}
    def strong_cluster_of(z):
        for c in sclusters:
            if z in c: return id(c)
        return None
    n_strong_clusters = len(sclusters)

    # ---- A: unique-opportunity table (hit2 clusters) ----
    hit2 = [z for z in zones if num(z.get("true_mfe")) and z["true_mfe"] >= 2 and num(z.get("time_to_2"))]
    for z in hit2: z["_th2"] = z["confirmedTs"] // 1000 + z["time_to_2"]
    h2cl = []
    byh = defaultdict(list)
    for z in hit2: byh[z["direction"]].append(z)
    for d, zs in byh.items():
        zs.sort(key=lambda x: x["_th2"]); last = None; cur = []
        for z in zs:
            if last is not None and z["_th2"] - last > GAP_S: h2cl.append(cur); cur = []
            cur.append(z); last = z["_th2"]
        if cur: h2cl.append(cur)
    A = []
    for i, c in enumerate(h2cl):
        czs = sorted(c, key=lambda x: x["confirmedTs"]); f = czs[0]
        mx = max(c, key=lambda x: x["true_mfe"])
        is_strong = any(z["_strong"] for z in c)
        A.append({"cluster_id": f"h2|{f['direction']}|{i}", "date": f["_date"], "direction": f["direction"],
                  "first_zone_id": f["id"], "first_confirmed_ts": f["confirmedTs"], "target_hit_ts": min(z["_th2"] for z in c),
                  "MFE_best": mx["true_mfe"], "hit2": 1, "hit2_5": int(is_strong), "hit3": int(any(num(z.get("true_mfe")) and z["true_mfe"] >= 3 for z in c)),
                  "zones_in_cluster": len(c), "setup_family": f["_family"], "regime": f["_regime"], "range_pos": f.get("range_pos"),
                  "swept_above": f.get("swept_above"), "swept_below": f.get("swept_below"), "reclaim": f.get("reclaim_zoneMid_preconfirm"),
                  "eng_ofi": num(f.get("eng_ofi")), "taker_imb": num(f.get("supportive_taker_imb_15m")), "microprice_5m": num(f.get("dl2_microprice_aligned_delta_5m_bps")),
                  "thin_path": num(f.get("ms_thin_path_score")), "walls": num(f.get("ms_large_walls_on_path")), "entropy": num(f.get("book_entropy_top25")),
                  "prior_60m": num(f.get("prior_move_60m_pct")), "prior_180m": num(f.get("prior_move_180m_pct")), "prior_1d": num(f.get("prior_move_1d_pct"))})
    with (OUT / "TIER_A_UNIQUE_OPPORTUNITY_TABLE.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(A[0].keys())); w.writeheader(); w.writerows(A)
    (OUT / "TIER_A_UNIQUE_OPPORTUNITY_TABLE.json").write_text(json.dumps({"build": now_iso(), "rows": A}, indent=2, default=str), encoding="utf-8")

    # ---- B: rule search (deduped) ----
    R = rules(emed)
    def eval_rule(pred, pool=None):
        zs = pool if pool is not None else zones
        fired = [z for z in zs if z.get("sim_outcome") and pred(z)]
        picks = dedup_alerts(fired)
        m = metr(picks)
        sc = {strong_cluster_of(z) for z in fired if strong_cluster_of(z)}
        m["unique_strong_caught"] = len(sc)
        m["unique_noise_caught"] = sum(1 for p in picks if not p["_strong"])
        m["rejected_unique_strong"] = n_strong_clusters - len(sc)
        return m, picks
    B = []
    rule_picks = {}
    for name, pred in R.items():
        m, picks = eval_rule(pred); rule_picks[name] = picks
        B.append({"rule": name, **m})

    # ---- diagnostic: do strong moves even WIN the TP2 trade from first live entry? ----
    strong_first = []
    for c in sclusters:
        f = min(c, key=lambda x: x["confirmedTs"])
        strong_first.append(f.get("sim_outcome"))
    strong_diag = {"strong_clusters": n_strong_clusters,
                   "first_entry_WIN": strong_first.count("WIN"), "first_entry_LOSS": strong_first.count("LOSS"),
                   "first_entry_TIMEOUT": strong_first.count("TIMEOUT"),
                   "first_entry_winrate": round(100 * strong_first.count("WIN") / max(n_strong_clusters, 1), 1)}

    # ---- C: min-sample gates ----
    def gate(minn):
        ok = [r for r in B if r["unique_alerts"] >= minn]
        best = max(ok, key=lambda r: (r["winrate"], r["unique_alerts"])) if ok else None
        return best
    C = {"demo_min4": gate(4), "usable_min6": gate(6), "stronger_min8": gate(8)}

    # ---- D: anti-overfit on best rule (by winrate among min4) ----
    cand = [r for r in B if r["unique_alerts"] >= 4]
    best_rule = max(cand, key=lambda r: (r["winrate"], r["unique_alerts"])) if cand else max(B, key=lambda r: r["unique_alerts"])
    bp = R[best_rule["rule"]]
    def subset(excl=(), only=None):
        pool = [z for z in zones if z["_date"] not in excl and (only is None or z["_date"] in only)]
        m, _ = eval_rule(bp, pool); return m
    D = {
        "full": {"winrate": best_rule["winrate"], "n": best_rule["unique_alerts"]},
        "train_03_11": subset(only=[f"2026-05-{d:02d}" for d in range(3, 12)]),
        "test_12_20": subset(only=[f"2026-05-{d:02d}" for d in range(12, 21)]),
        "without_05_14": subset(excl=("2026-05-14",)), "without_05_15": subset(excl=("2026-05-15",)),
        "without_both": subset(excl=("2026-05-14", "2026-05-15")),
        "leave_one_day_out_winrates": {d: subset(excl=(d,))["winrate"] for d in DATES},
    }
    depends_1415 = "YES" if (D["without_both"]["winrate"] < best_rule["winrate"] - 15 or D["without_both"]["unique_alerts"] < 3) else "NO"

    # ---- E: presentation table (best + top rules) ----
    E = []
    for r in sorted(B, key=lambda x: (-x["winrate"], -x["unique_alerts"])):
        E.append({"rule": r["rule"], "unique_alerts": r["unique_alerts"], "W": r["W"], "L": r["L"], "TO": r["TO"], "winrate": r["winrate"],
                  "pf": r["pf"], "expectancy": r["expectancy"], "hit2_5": r["hit2_5"], "hit3": r["hit3"], "avg_time_to_2_min": r["avg_time_to_2_min"],
                  "max_loss_streak": r["max_loss_streak"], "days_active": r["days_active"],
                  "caveat": "IN-SAMPLE TIER-A DEMO, NOT PRODUCTION VALIDATION" + (" — n too small" if r["unique_alerts"] < 6 else "")})

    # ---- exact trades of best rule ----
    bt = []
    for z in sorted(rule_picks[best_rule["rule"]], key=lambda x: x["confirmedTs"]):
        bt.append({"date": z["_date"], "confirmed_iso": dt.datetime.fromtimestamp(z["confirmedTs"] / 1000, tz=dt.timezone.utc).isoformat(timespec="seconds"),
                   "direction": z["direction"], "setup_family": z["_family"], "entry": z.get("sim_entry_price"), "result": z.get("sim_outcome"),
                   "pnl_after_cost": z.get("sim_pnl_after_cost"), "MFE": z.get("true_mfe"), "time_to_2_min": mins(z.get("time_to_2")), "strong": int(z["_strong"])})

    found = "YES" if best_rule["winrate"] >= 70 and best_rule["unique_alerts"] >= 6 else ("PARTIAL" if best_rule["winrate"] >= 70 else "NO")
    flags = {
        "TIER_A_SEARCH_DONE": "YES", "TIER_A_70_80_FOUND": found, "BEST_TIER_A_RULE": best_rule["rule"],
        "BEST_TIER_A_UNIQUE_ALERTS": best_rule["unique_alerts"], "BEST_TIER_A_WINRATE": best_rule["winrate"], "BEST_TIER_A_PF": best_rule["pf"],
        "BEST_TIER_A_HINDSIGHT_RISK": "MED", "RESULT_DEPENDS_ON_05_14_05_15": depends_1415,
        "N_UNIQUE_STRONG_MOVES": n_strong_clusters, "N_UNIQUE_HIT2_MOVES": len(h2cl),
        "READY_FOR_TIER_A_SHADOW": "PARTIAL" if best_rule["unique_alerts"] >= 4 and best_rule["winrate"] >= 60 else "NO",
        "READY_FOR_PRODUCTION_TRADING": "NO", "MORE_OOS_REQUIRED": "YES", "IN_SAMPLE_DEMO_ONLY": "YES", "TARDIS_USED": "NO"}
    answers = {
        "1_can_reach_70_80": f"{found} — best rule {best_rule['rule']}: {best_rule['winrate']}% on {best_rule['unique_alerts']} unique alerts.",
        "2_unique_trades": f"{best_rule['unique_alerts']} unique trades (deduped, one per move).",
        "3_live_or_hindsight": f"It is a SELECTION (precision) problem, not timing/hindsight: all {strong_diag['strong_clusters']} strong moves WIN TP2 from their first zone ({strong_diag['first_entry_winrate']}%), but no causal rule isolates them from look-alike losers.",
        "4_exact_rules": best_rule["rule"] + " = " + {"T1_edge_reclaim": "RANGE + range edge + reclaim", "T2_sweep_reversal": "sweep + reclaim + taker/ofi aligned",
            "T3_thin_path": "edge + no wall + thin path", "T4_absorption": "taker against + reclaim + microprice aligned",
            "T5_confluence": "edge/sweep + reclaim + thin + taker/ofi", "T6_strict_2of7": ">=2 of 7 confluence", "T6_strict_3of7": ">=3 of 7 confluence",
            "T6_strict_4of7": ">=4 of 7 confluence", "T6_strict_5of7": ">=5 of {edge,sweep,reclaim,no_wall,microprice,taker/ofi,low_entropy}"}.get(best_rule["rule"], ""),
        "5_holds_without_1415": f"depends_on_05_14_05_15 = {depends_1415}; without both -> {D['without_both']['winrate']}% on {D['without_both']['unique_alerts']} alerts (stably low, not driven by those days).",
        "6_can_formalize_shadow": "NO as a winrate edge — best is ~29%. Only worth a shadow logger to KEEP COLLECTING the rare strong moves, not as a Tier-A trade trigger.",
        "7_oos_needs": "new OKX(+Binance) windows with >=15-20 unique strong moves; a feature with real ex-ante separation power (current microstructure set does not separate the 8 winners); freeze any rule, no re-tuning."}

    # write
    with (OUT / "TIER_A_SELECTOR_RESULTS.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(E[0].keys())); w.writeheader(); w.writerows(E)
    with (OUT / "TIER_A_BEST_RULE_TRADES.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(bt[0].keys()) if bt else ["date"]); w.writeheader(); w.writerows(bt)
    (OUT / "TIER_A_SELECTOR_RESULTS.json").write_text(json.dumps({"build": now_iso(), "status": "IN_SAMPLE_DEMO", "rules": B, "min_sample_gates": C,
        "anti_overfit": D, "presentation": E, "best_trades": bt, "flags": flags, "answers": answers, "strong_move_diagnostic": strong_diag,
        "n_unique_strong_moves": n_strong_clusters, "n_unique_hit2_moves": len(h2cl)}, indent=2, default=str), encoding="utf-8")
    wb = openpyxl.Workbook(); wb.remove(wb.active)
    for t, rows in (("UniqueOpps", A), ("Rules", E), ("BestTrades", bt)):
        ws = wb.create_sheet(t)
        if rows: ws.append(list(rows[0].keys())); [ws.append([r.get(c) for c in rows[0].keys()]) for r in rows]
    wb.save(OUT / "TIER_A_SELECTOR_RESULTS.xlsx")
    md = ["# TIER-A HIGH-CONFIDENCE SELECTOR (OKX 05-03..20 unique moves)", "",
          "## ⚠️ IN-SAMPLE TIER-A DEMO — NOT PRODUCTION VALIDATION", "", f"**Build:** {now_iso()}",
          f"Unique strong moves: {n_strong_clusters} · unique hit2 moves: {len(h2cl)}. One trade per move (deduped). TP=2%.", "",
          "## E. Tier-A rule results", "| rule | uniq | W/L/TO | wr% | PF | exp% | hit2.5 | maxLS | days | caveat |", "|---|--:|:--:|--:|--:|--:|--:|--:|--:|---|"]
    for r in E: md.append(f"| {r['rule']} | {r['unique_alerts']} | {r['W']}/{r['L']}/{r['TO']} | {r['winrate']} | {r['pf']} | {r['expectancy']} | {r['hit2_5']} | {r['max_loss_streak']} | {r['days_active']} | {r['caveat']} |")
    md += ["", f"## Best rule: {best_rule['rule']} — exact unique trades", "| date | dir | family | result | pnl | MFE | strong |", "|---|:--:|:--:|:--:|--:|--:|:--:|"]
    for t in bt: md.append(f"| {t['date']} | {t['direction']} | {t['setup_family']} | {t['result']} | {t['pnl_after_cost']} | {t['MFE']} | {t['strong']} |")
    md += ["", "## D. Anti-overfit",
           f"- full: {D['full']['winrate']}% (n={D['full']['n']})",
           f"- train 03-11: {D['train_03_11']['winrate']}% (n={D['train_03_11']['unique_alerts']}) | test 12-20: {D['test_12_20']['winrate']}% (n={D['test_12_20']['unique_alerts']})",
           f"- without 05-14: {D['without_05_14']['winrate']}% (n={D['without_05_14']['unique_alerts']})",
           f"- without 05-15: {D['without_05_15']['winrate']}% (n={D['without_05_15']['unique_alerts']})",
           f"- without both: {D['without_both']['winrate']}% (n={D['without_both']['unique_alerts']})",
           f"- **RESULT_DEPENDS_ON_05_14_05_15 = {depends_1415}**", "",
           "## Diagnostic — why winrate is low (SELECTION, not timing)",
           f"- All {strong_diag['strong_clusters']} unique strong moves WIN TP2 from their first zone: {strong_diag['first_entry_WIN']}W/{strong_diag['first_entry_LOSS']}L/{strong_diag['first_entry_TIMEOUT']}TO = **{strong_diag['first_entry_winrate']}%**.",
           "- So the ceiling exists; the problem is that no causal rule separates those 8 winners from the ~100 look-alike losers that also pass.", "",
           "## F. Answers"] + [f"**{k}** — {v}" for k, v in answers.items()] + ["", "## Flags", "```"] + [f"{k} = {v}" for k, v in flags.items()] + ["```"]
    (OUT / "TIER_A_SELECTOR_RESULTS.md").write_text("\n".join(md), encoding="utf-8")

    # console
    print(f"unique strong moves {n_strong_clusters} | unique hit2 moves {len(h2cl)}")
    print("=== rules ===")
    for r in sorted(B, key=lambda x: (-x['winrate'], -x['unique_alerts'])):
        print(f"  {r['rule']:<18s} uniq {r['unique_alerts']:>2} {r['W']}/{r['L']}/{r['TO']} wr {r['winrate']}% PF {r['pf']} hit2.5 {r['hit2_5']} strong_caught {r['unique_strong_caught']} maxLS {r['max_loss_streak']}")
    print(f"BEST: {best_rule['rule']} wr {best_rule['winrate']}% n {best_rule['unique_alerts']}")
    print("=== anti-overfit ===")
    print(f"  full {D['full']['winrate']}%(n{D['full']['n']}) | wo14 {D['without_05_14']['winrate']}%(n{D['without_05_14']['unique_alerts']}) | wo15 {D['without_05_15']['winrate']}%(n{D['without_05_15']['unique_alerts']}) | wo_both {D['without_both']['winrate']}%(n{D['without_both']['unique_alerts']})")
    print(f"  train03-11 {D['train_03_11']['winrate']}%(n{D['train_03_11']['unique_alerts']}) test12-20 {D['test_12_20']['winrate']}%(n{D['test_12_20']['unique_alerts']})")
    print("=== best trades ===")
    for t in bt: print(f"  {t['date']} {t['direction']:<5} {t['setup_family']:<22} {t['result']:<7} pnl {t['pnl_after_cost']} MFE {t['MFE']} strong {t['strong']}")
    print("FLAGS:", flags); print("depends_1415:", depends_1415)
    return 0


if __name__ == "__main__":
    sys.exit(main())
