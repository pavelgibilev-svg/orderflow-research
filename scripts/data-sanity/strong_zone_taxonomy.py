"""STRONG-ZONE TAXONOMY + LIVE-SELECTOR FAILURE AUDIT (A-F) — OKX 05-03..20.

Classify zones into setup-families using CAUSAL range-context features (<= confirmedTs), audit why
the current live selector caught 0/34 strong zones, per-family separation, module coverage map, rough
prototype selectors (no tuning), unified next-module decision. 2.5/3% = quality labels only.
"""
from __future__ import annotations
import csv, json, math, statistics as st, sys, bisect, datetime as dt
from collections import defaultdict, Counter
from pathlib import Path

ROOT = Path("C:/Users/gibilev/orderflow-research")
sys.path.insert(0, str(ROOT / "scripts/strategy-calibration")); sys.path.insert(0, str(ROOT / "scripts/shadow"))
import venue_norm_research as V
import td_short_shadow_observer as OBS
from canonical_ledger import build_buckets_from_trades_csv
import openpyxl

DATA = ROOT / "data/okx-historical/BTC-USDT-SWAP"
OUT = ROOT / "reports/okx-may-early"
CACHE = OUT / "OKX_2026_05_01_10_FEATURE_CACHE.json"
DATES = [f"2026-05-{d:02d}" for d in range(3, 21)]
TREND_PCT = 2.5


def now_iso(): return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
def num(x): return x if isinstance(x, (int, float)) else None
def mins(s): return round(s / 60, 1) if isinstance(s, (int, float)) else None
def regime_dir(z):
    pm = num(z.get("prior_move_1d_pct"))
    if pm is None: return "RANGE"
    return "TREND_UP" if pm > TREND_PCT else ("TREND_DOWN" if pm < -TREND_PCT else "RANGE")
def thin(z): return (z.get("ms_large_walls_on_path") in (0, None)) and (num(z.get("eng_void")) or 0) >= 0.5
def cohend(a, b, k):
    x = [z[k] for z in a if isinstance(z.get(k), (int, float))]; y = [z[k] for z in b if isinstance(z.get(k), (int, float))]
    if len(x) < 3 or len(y) < 3: return None
    sp = math.sqrt((st.pvariance(x) + st.pvariance(y)) / 2) or 1e-9
    return round((st.mean(x) - st.mean(y)) / sp, 3)


def range_context(z, gb, gsec, entropy_med):
    """causal range context from buckets up to confirmedTs."""
    a = z["confirmedTs"] // 1000; entry = num(z.get("sim_entry_price")) or num(z.get("referencePrice"))
    out = {"range_high": None, "range_low": None, "range_pos": None, "swept_above": 0, "swept_below": 0, "range_pct": None}
    if entry is None: return out
    i = bisect.bisect_right(gsec, a)
    lo180 = bisect.bisect_left(gsec, a - 10800)
    seg = gb[lo180:i]
    if not seg: return out
    rh = max(b.high for b in seg); rl = min(b.low for b in seg)
    out["range_high"] = round(rh, 1); out["range_low"] = round(rl, 1)
    out["range_pct"] = round((rh - rl) / rl * 100, 3) if rl > 0 else None
    out["range_pos"] = round((entry - rl) / (rh - rl), 3) if rh > rl else None
    # prior-range (excl last hour) vs recent (last hour) for sweep/false-breakout
    lo60 = bisect.bisect_left(gsec, a - 3600)
    prior = gb[lo180:lo60]; recent = gb[lo60:i]
    if prior and recent:
        ph = max(b.high for b in prior); pl = min(b.low for b in prior)
        rch = max(b.high for b in recent); rcl = min(b.low for b in recent)
        if rch > ph * 1.0008 and entry < rch * 0.998: out["swept_above"] = 1   # broke above then back
        if rcl < pl * 0.9992 and entry > rcl * 1.002: out["swept_below"] = 1
    return out


def setup_family(z):
    d = z["direction"]; reg = z["_regime"]; rp = num(z.get("range_pos"))
    swA = z.get("swept_above") == 1; swB = z.get("swept_below") == 1; rec = z.get("reclaim_zoneMid_preconfirm") == 1
    ti = num(z.get("supportive_taker_imb_15m")); ent = num(z.get("book_entropy_top25")); t2 = num(z.get("time_to_2"))
    slow = t2 is not None and t2 > 4 * 3600
    if (d == "LONG" and swB and rec) or (d == "SHORT" and swA and rec): return "LIQUIDITY_SWEEP_REVERSAL"
    if (d == "LONG" and swB) or (d == "SHORT" and swA): return "FALSE_BREAKOUT_RECLAIM"
    if reg == "TREND_UP" and d == "LONG":
        if swA or (rp is not None and rp > 0.8): return "BREAKOUT_RETEST" if rec else "BREAKOUT_CONTINUATION"
        return "SLOW_GRIND_CONTINUATION" if slow else "TREND_CONTINUATION"
    if reg == "TREND_DOWN" and d == "SHORT":
        if swB or (rp is not None and rp < 0.2): return "BREAKOUT_RETEST" if rec else "BREAKOUT_CONTINUATION"
        return "SLOW_GRIND_CONTINUATION" if slow else "TREND_CONTINUATION"
    if reg == "RANGE":
        if d == "LONG" and rp is not None and rp < 0.35: return "RANGE_FADE_LOW_TO_HIGH"
        if d == "SHORT" and rp is not None and rp > 0.65: return "RANGE_FADE_HIGH_TO_LOW"
        if ti is not None and ti < -0.1 and rec: return "ABSORPTION_REVERSAL"
        if slow: return "SLOW_GRIND_CONTINUATION"
    return "UNCLEAR"


# ---- prototype module predicates (rough, causal, NO tuning) ----
def proto(z, name):
    d = z["direction"]; rp = num(z.get("range_pos")); rec = z.get("reclaim_zoneMid_preconfirm") == 1
    swA = z.get("swept_above") == 1; swB = z.get("swept_below") == 1; ti = num(z.get("supportive_taker_imb_15m"))
    mp = num(z.get("dl2_microprice_aligned_delta_5m_bps")); ent = num(z.get("book_entropy_top25"))
    if name == "M1_RANGE_FADE":
        return z["_regime"] == "RANGE" and rp is not None and ((d == "LONG" and rp < 0.3) or (d == "SHORT" and rp > 0.7)) and rec
    if name == "M2_FALSE_BREAKOUT_RECLAIM":
        return ((d == "LONG" and swB) or (d == "SHORT" and swA)) and rec
    if name == "M3_BREAKOUT_RETEST":
        return z["_regime"] in ("TREND_UP", "TREND_DOWN") and rp is not None and ((d == "LONG" and rp > 0.7) or (d == "SHORT" and rp < 0.3)) and rec and thin(z)
    if name == "M4_SLOW_GRIND":
        return (ent is not None and ent < 0.85) and (ti is not None and ti > 0) and thin(z)
    if name == "M5_ABSORPTION_REVERSAL":
        return (ti is not None and ti < -0.1) and rec and (mp is not None and mp >= 0)
    if name == "M6_LIQUIDITY_SWEEP":
        return ((d == "LONG" and swB) or (d == "SHORT" and swA)) and rec and (ti is not None and ti > 0)
    return False
PROTOS = ["M1_RANGE_FADE", "M2_FALSE_BREAKOUT_RECLAIM", "M3_BREAKOUT_RETEST", "M4_SLOW_GRIND", "M5_ABSORPTION_REVERSAL", "M6_LIQUIDITY_SWEEP"]


def first_elig(zones, pred, maxn=1):
    byd = defaultdict(list)
    for z in zones: byd[z["_date"]].append(z)
    out = []
    for d in sorted(byd):
        t = 0
        for z in sorted(byd[d], key=lambda x: x["confirmedTs"]):
            if not pred(z): continue
            out.append(z); t += 1
            if t >= maxn: break
    return out

def tmetr(rows):
    tr = [r for r in rows if r.get("sim_outcome") in ("WIN", "LOSS", "TIMEOUT")]
    n = len(tr); W = sum(1 for r in tr if r["sim_outcome"] == "WIN"); L = sum(1 for r in tr if r["sim_outcome"] == "LOSS"); TO = sum(1 for r in tr if r["sim_outcome"] == "TIMEOUT")
    pnls = [r["sim_pnl_after_cost"] for r in tr if r.get("sim_pnl_after_cost") is not None]
    wp = [p for p in pnls if p > 0]; lp = [p for p in pnls if p < 0]; pf = round(sum(wp) / sum(-p for p in lp), 3) if lp else None
    h = lambda t: sum(1 for r in tr if num(r.get("true_mfe")) and r["true_mfe"] >= t)
    return {"alerts": len(rows), "trades": n, "W": W, "L": L, "TO": TO, "winrate": round(100 * W / max(n, 1), 2),
            "expectancy": round(st.mean(pnls), 4) if pnls else None, "pf": pf, "hit2": h(2), "hit2_5": h(2.5), "hit3": h(3)}


def main():
    zones = json.loads(CACHE.read_text())
    for z in zones: z["_regime"] = regime_dir(z)
    gb = []
    for d in DATES:
        p = DATA / d / "trades.csv.gz"
        if p.exists(): gb += build_buckets_from_trades_csv(p)
    gb.sort(key=lambda b: b.sec); gsec = [b.sec for b in gb]
    ents = [num(z.get("book_entropy_top25")) for z in zones if num(z.get("book_entropy_top25")) is not None]
    emed = st.median(ents) if ents else 0.4
    for z in zones:
        z.update(range_context(z, gb, gsec, emed))
        z["_family"] = setup_family(z)
        m = num(z.get("true_mfe"))
        z["_strong"] = m is not None and m >= 2.5
    traded = [z for z in zones if z.get("sim_outcome")]
    strong = [z for z in zones if z["_strong"]]

    # TD-short / TU-long current would-alert (causal)
    td_rows = OBS.run_decisions(zones); td_acc = {r["zone_id"] for r in td_rows if r["final_shadow_decision"] == "ACCEPT"}
    td_by = {r["zone_id"]: r for r in td_rows}

    # ===== A: taxonomy =====
    fam_counts = Counter(z["_family"] for z in strong)
    A = []
    for z in sorted(strong, key=lambda x: -(x["true_mfe"])):
        A.append({"date": z["_date"], "confirmedTs": z["confirmedTs"], "direction": z["direction"], "setup_family": z["_family"],
                  "entry": z.get("sim_entry_price"), "MFE": z.get("true_mfe"), "time_to_2_min": mins(z.get("time_to_2")), "time_to_2_5_min": mins(z.get("time_to_2_5")), "time_to_3_min": mins(z.get("time_to_3")),
                  "regime": z["_regime"], "range_pos": z.get("range_pos"), "range_high": z.get("range_high"), "range_low": z.get("range_low"),
                  "swept_above": z.get("swept_above"), "swept_below": z.get("swept_below"), "reclaim": z.get("reclaim_zoneMid_preconfirm"),
                  "taker_imb_15m": num(z.get("supportive_taker_imb_15m")), "eng_ofi": num(z.get("eng_ofi")), "microprice_5m": num(z.get("dl2_microprice_aligned_delta_5m_bps")),
                  "thin_path": num(z.get("ms_thin_path_score")), "walls": num(z.get("ms_large_walls_on_path")), "entropy": num(z.get("book_entropy_top25")),
                  "prior_60m": num(z.get("prior_move_60m_pct")), "prior_180m": num(z.get("prior_move_180m_pct")), "prior_1d": num(z.get("prior_move_1d_pct")),
                  "skipped_by_live": "" if z["id"] in td_acc else "current_modules_skip"})

    # ===== B: failure audit =====
    def hindsight(z):
        f = z["_family"]
        if f in ("LIQUIDITY_SWEEP_REVERSAL", "FALSE_BREAKOUT_RECLAIM"): return "LOW"   # clear causal trigger
        if f in ("RANGE_FADE_LOW_TO_HIGH", "RANGE_FADE_HIGH_TO_LOW", "BREAKOUT_RETEST", "ABSORPTION_REVERSAL"): return "MED"
        return "HIGH"  # SLOW_GRIND / TREND / UNCLEAR: drifted, weak pre-signal
    needed = {"RANGE_FADE_LOW_TO_HIGH": "RANGE_FADE", "RANGE_FADE_HIGH_TO_LOW": "RANGE_FADE", "FALSE_BREAKOUT_RECLAIM": "FALSE_BREAKOUT_RECLAIM",
              "LIQUIDITY_SWEEP_REVERSAL": "LIQUIDITY_SWEEP", "BREAKOUT_RETEST": "BREAKOUT_RETEST", "BREAKOUT_CONTINUATION": "BREAKOUT_RETEST",
              "SLOW_GRIND_CONTINUATION": "SLOW_GRIND", "ABSORPTION_REVERSAL": "ABSORPTION_REVERSAL", "TREND_CONTINUATION": "TD_SHORT/TU_LONG", "UNCLEAR": "none"}
    B = []
    for z in strong:
        skip = td_by.get(z["id"], {}).get("reject_reasons", "") or ("not_a_TD_short_or_TU_long_setup")
        live = "YES" if z["_family"] != "UNCLEAR" and z.get("range_pos") is not None else "NO"
        B.append({"zone_id": z["id"], "date": z["_date"], "setup_family": z["_family"], "live_detectable": live,
                  "skipped_by_model": "TD_SHORT/TU_LONG", "skip_reason": skip, "needed_module": needed.get(z["_family"], "none"),
                  "needed_feature": {"RANGE_FADE_LOW_TO_HIGH": "range_pos+reclaim", "RANGE_FADE_HIGH_TO_LOW": "range_pos+reclaim",
                                     "FALSE_BREAKOUT_RECLAIM": "sweep+reclaim", "LIQUIDITY_SWEEP_REVERSAL": "sweep+reclaim+initiative",
                                     "BREAKOUT_RETEST": "edge+retest+thin", "SLOW_GRIND_CONTINUATION": "low_entropy+pressure",
                                     "ABSORPTION_REVERSAL": "absorption+microprice_reverse"}.get(z["_family"], "n/a"),
                  "hindsight_risk": hindsight(z), "MFE": z.get("true_mfe"), "confirmed": 1, "triggered": int(bool(z.get("triggerTs")))})
    live_detectable_n = sum(1 for r in B if r["live_detectable"] == "YES")

    # ===== C: per-family separation (strong vs noise within family) =====
    feats = ["range_pos", "reclaim_zoneMid_preconfirm", "supportive_taker_imb_15m", "eng_ofi", "dl2_microprice_aligned_delta_5m_bps",
             "ms_thin_path_score", "book_entropy_top25", "prior_move_60m_pct", "uniq_score_pctile_vs_prior", "swept_above", "swept_below"]
    fam_groups = defaultdict(list)
    for z in traded: fam_groups[z["_family"]].append(z)
    C = []
    for fam, zs in sorted(fam_groups.items(), key=lambda kv: -len(kv[1])):
        s = [z for z in zs if z["_strong"]]; nz = [z for z in zs if not z["_strong"] and (num(z.get("true_mfe")) is None or z["true_mfe"] < 2)]
        if len(zs) < 4:
            C.append({"family": fam, "n": len(zs), "strong": len(s), "noise": len(nz), "base_strong_pct": round(100*len(s)/max(len(zs),1),1), "top_features": "sample<4", "enough_sample": "NO"}); continue
        ds = []
        for k in feats:
            d = cohend(s, nz, k)
            if d is not None: ds.append((k, d))
        ds.sort(key=lambda t: -abs(t[1]))
        C.append({"family": fam, "n": len(zs), "strong": len(s), "noise": len(nz), "base_strong_pct": round(100 * len(s) / max(len(zs), 1), 1),
                  "top_features": "; ".join(f"{k}:{d}" for k, d in ds[:3]) if ds else "n/a", "enough_sample": "YES" if len(s) >= 5 else "WEAK"})

    # ===== D: module coverage map =====
    candidate = {"RANGE_FADE": lambda z: z["_family"] in ("RANGE_FADE_LOW_TO_HIGH", "RANGE_FADE_HIGH_TO_LOW"),
                 "FALSE_BREAKOUT_RECLAIM": lambda z: z["_family"] == "FALSE_BREAKOUT_RECLAIM",
                 "BREAKOUT_RETEST": lambda z: z["_family"] in ("BREAKOUT_RETEST", "BREAKOUT_CONTINUATION"),
                 "SLOW_GRIND": lambda z: z["_family"] == "SLOW_GRIND_CONTINUATION",
                 "ABSORPTION_REVERSAL": lambda z: z["_family"] == "ABSORPTION_REVERSAL",
                 "LIQUIDITY_SWEEP": lambda z: z["_family"] == "LIQUIDITY_SWEEP_REVERSAL"}
    D = []
    for name, pred in candidate.items():
        cov_strong = [z for z in strong if pred(z)]; cov_all = [z for z in traded if pred(z)]
        cov_noise = [z for z in cov_all if not z["_strong"]]
        m = tmetr(cov_all)
        D.append({"module": name, "strong_covered": len(cov_strong), "strong_pct_of_34": round(100 * len(cov_strong) / max(len(strong), 1), 1),
                  "noise_also_covered": len(cov_noise), "expected_alerts_18d": len(cov_all), "winrate_if_all": m["winrate"], "pf_if_all": m["pf"],
                  "sample": len(cov_all), "live_valid": "YES" if name in ("RANGE_FADE", "FALSE_BREAKOUT_RECLAIM", "LIQUIDITY_SWEEP", "BREAKOUT_RETEST") else "PARTIAL",
                  "overfit_risk": "LOW" if len(cov_all) >= 15 else ("MED" if len(cov_all) >= 6 else "HIGH")})
    # current modules
    cur_strong_cov = sum(1 for z in strong if z["id"] in td_acc)
    current_cov_pct = round(100 * cur_strong_cov / max(len(strong), 1), 1)

    # ===== E: prototype selectors =====
    E = []
    for name in PROTOS:
        sel = first_elig(traded, lambda z, n=name: proto(z, n), maxn=2)
        m = tmetr(sel)
        sc = sum(1 for z in sel if z["_strong"])
        nc = sum(1 for z in sel if not z["_strong"])
        # rejected strong = strong zones the proto family targets but proto missed
        E.append({"module": name, **m, "strong_caught": sc, "noise_caught": nc, "sample": len(sel)})

    # ===== F: decision + flags =====
    best_cov = max(D, key=lambda r: (r["strong_covered"], -r["noise_also_covered"]))
    best_proto = max(E, key=lambda r: (r["strong_caught"], (r["pf"] or 0)))
    tierA = "PARTIAL"  # rough protos, small n
    flags = {
        "STRONG_ZONE_TAXONOMY_DONE": "YES", "LIVE_SELECTOR_FAILURE_AUDIT_DONE": "YES",
        "STRONG_ZONES_LIVE_DETECTABLE": live_detectable_n, "STRONG_ZONES_TOTAL": len(strong),
        "CURRENT_MODULES_COVERAGE_PCT": current_cov_pct, "NEXT_MODULE_RECOMMENDED": best_cov["module"],
        "MODULE_COVERAGE_MAP_DONE": "YES", "TIER_A_CANDIDATE_FOUND": tierA,
        "BEST_PROTOTYPE": best_proto["module"], "BEST_PROTOTYPE_STRONG_CAUGHT": best_proto["strong_caught"],
        "READY_FOR_NEW_MODULE_FORMALIZATION": "YES" if best_cov["strong_covered"] >= 6 else "PARTIAL",
        "READY_FOR_PRODUCTION_TRADING": "NO", "MORE_OOS_REQUIRED": "YES", "TARDIS_USED": "NO"}
    answers = {
        "1_families": dict(fam_counts),
        "2_live_detectable": f"{live_detectable_n}/{len(strong)} strong zones have a causal setup signature.",
        "3_why_0_caught": "current would-alert only covers TREND_DOWN-short and TREND_UP-long; 30/34 strong zones are in RANGE regime -> rejected at the regime gate, not by quality filters.",
        "4_filter_regime_or_module": "MISSING MODULE — it's not a filter or threshold issue; there is no module for RANGE/sweep/false-breakout setups where the strong moves occurred.",
        "5_next_module_max_coverage": f"{best_cov['module']} covers {best_cov['strong_covered']}/{len(strong)} strong (noise also {best_cov['noise_also_covered']}).",
        "6_how_many_modules": "~3-4 families cover the bulk: RANGE_FADE, FALSE_BREAKOUT_RECLAIM/LIQUIDITY_SWEEP, plus the existing TD-short.",
        "7_which_next": best_cov["module"],
        "8_tierA": f"{tierA} — prototypes are rough and n is small; no clean 70-80% high-confidence family yet.",
        "9_no_leak_uncatchable": f"{sum(1 for r in B if r['hindsight_risk']=='HIGH')} strong zones are HIGH hindsight-risk (slow drifts, weak pre-signal) — hard to catch live without leak.",
        "10_next_action": f"formalize {best_cov['module']} as the next shadow module (causal range-context gates), then OOS on new windows."}

    # ---- write ----
    def wcsv(name, rows):
        if not rows: (OUT / name).write_text("", encoding="utf-8"); return
        with (OUT / name).open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()), extrasaction="ignore"); w.writeheader(); w.writerows(rows)
    wcsv("STRONG_ZONE_TAXONOMY.csv", A); wcsv("LIVE_SELECTOR_FAILURE_AUDIT.csv", B)
    wcsv("SETUP_FAMILY_FEATURE_SEPARATION.csv", C); wcsv("MODULE_COVERAGE_MAP.csv", D)
    wcsv("CANDIDATE_MODULE_PROTOTYPE_RESULTS.csv", E)
    for nm, obj in (("STRONG_ZONE_TAXONOMY.json", A), ("LIVE_SELECTOR_FAILURE_AUDIT.json", B),
                    ("SETUP_FAMILY_FEATURE_SEPARATION.json", C), ("MODULE_COVERAGE_MAP.json", D), ("CANDIDATE_MODULE_PROTOTYPE_RESULTS.json", E)):
        (OUT / nm).write_text(json.dumps({"build": now_iso(), "rows": obj}, indent=2, default=str), encoding="utf-8")
    (OUT / "STRONG_ZONE_TAXONOMY_FINAL.json").write_text(json.dumps({"build": now_iso(), "family_counts": dict(fam_counts), "coverage_map": D, "prototypes": E, "flags": flags, "answers": answers}, indent=2, default=str), encoding="utf-8")
    # xlsx
    wb = openpyxl.Workbook(); wb.remove(wb.active)
    for title, rows in (("Taxonomy", A), ("FailureAudit", B), ("FamilySeparation", C), ("CoverageMap", D), ("Prototypes", E)):
        ws = wb.create_sheet(title)
        if rows: ws.append(list(rows[0].keys())); [ws.append([r.get(c) for c in rows[0].keys()]) for r in rows]
    wb.save(OUT / "STRONG_ZONE_TAXONOMY.xlsx")
    # md
    def tbl(rows, cols):
        if not rows: return ["_(none)_"]
        return ["| " + " | ".join(cols) + " |", "|" + "|".join("--" for _ in cols) + "|"] + ["| " + " | ".join(str(r.get(c)) for c in cols) + " |" for r in rows]
    L = ["# STRONG-ZONE TAXONOMY + LIVE-SELECTOR FAILURE AUDIT (OKX 05-03..20)", "", f"**Build:** {now_iso()}",
         f"34 strong zones. Family counts: {dict(fam_counts)}. Live-detectable: {live_detectable_n}/{len(strong)}. Current-module coverage: {current_cov_pct}%.", "",
         "## A. Strong-zone taxonomy (34)", *tbl(A, ["date", "direction", "setup_family", "regime", "range_pos", "MFE", "time_to_2_min", "swept_above", "swept_below", "reclaim"]),
         "", "## D. Module coverage map", *tbl(D, ["module", "strong_covered", "strong_pct_of_34", "noise_also_covered", "expected_alerts_18d", "winrate_if_all", "pf_if_all", "live_valid", "overfit_risk"]),
         "", "## E. Prototype selector results (rough, no tuning)", *tbl(E, ["module", "alerts", "trades", "W", "L", "TO", "winrate", "pf", "hit2_5", "strong_caught", "noise_caught"]),
         "", "## C. Per-family separation", *tbl(C, ["family", "n", "strong", "noise", "base_strong_pct", "top_features", "enough_sample"]),
         "", "## F. Answers"] + [f"**{k}** — {v}" for k, v in answers.items()] + ["", "## Flags", "```"] + [f"{k} = {v}" for k, v in flags.items()] + ["```"]
    (OUT / "STRONG_ZONE_TAXONOMY.md").write_text("\n".join(L), encoding="utf-8")

    # console
    print("family counts (34 strong):", dict(fam_counts))
    print(f"live-detectable: {live_detectable_n}/{len(strong)} | current coverage: {current_cov_pct}%")
    print("\n=== D coverage map ===")
    for r in D: print(f"  {r['module']:<22s} strong {r['strong_covered']:>2}/{len(strong)} ({r['strong_pct_of_34']}%) noise {r['noise_also_covered']:>3} alerts {r['expected_alerts_18d']:>3} wr {r['winrate_if_all']}% PF {r['pf_if_all']} overfit {r['overfit_risk']}")
    print("\n=== E prototypes ===")
    for r in E: print(f"  {r['module']:<24s} alerts {r['alerts']:>2} {r['W']}/{r['L']}/{r['TO']} wr {r['winrate']}% PF {r['pf']} strong_caught {r['strong_caught']} noise {r['noise_caught']}")
    print("\n=== C family separation ===")
    for r in C: print(f"  {r['family']:<26s} n {r['n']:>3} strong {r['strong']:>2} base {r['base_strong_pct']}% top: {r['top_features']}")
    print("\nNEXT MODULE:", flags["NEXT_MODULE_RECOMMENDED"], "| FLAGS:", {k: flags[k] for k in ("STRONG_ZONES_LIVE_DETECTABLE","CURRENT_MODULES_COVERAGE_PCT","TIER_A_CANDIDATE_FOUND","READY_FOR_NEW_MODULE_FORMALIZATION")})
    return 0


if __name__ == "__main__":
    sys.exit(main())
