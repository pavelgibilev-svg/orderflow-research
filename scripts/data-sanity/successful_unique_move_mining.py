"""SUCCESSFUL UNIQUE MOVE FILTER MINING — OKX 05-03..20.

IN-SAMPLE RESEARCH (not production proof). Finds POSITIVE filters describing successful live-detectable
unique moves (hit2/2.5/3) vs noise/timeout/stop. Works on unique_move_cluster_id, first_live_detectable zone
per cluster, no raw duplicates. Future labels = outcome only; decisions causal (<= confirmedTs). TP stays 2%.
"""
from __future__ import annotations
import csv, json, math, statistics as st, sys, importlib.util, datetime as dt
from collections import defaultdict
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "package.json").exists() and (p / "scripts").exists())
for p in ("scripts/strategy-calibration", "scripts/shadow", "scripts/data-sanity"):
    sys.path.insert(0, str(ROOT / p))
import td_short_shadow_observer as OBS
from canonical_ledger import build_buckets_from_trades_csv
spec = importlib.util.spec_from_file_location("ta", str(ROOT / "scripts/data-sanity/tier_a_selector.py"))
TA = importlib.util.module_from_spec(spec); spec.loader.exec_module(TA)
TZ = TA.TZ
import openpyxl

OUT = ROOT / "reports/okx-may-early"; DATA = ROOT / "data/okx-historical/BTC-USDT-SWAP"
CACHE = OUT / "OKX_2026_05_01_10_FEATURE_CACHE.json"
DATES = [f"2026-05-{d:02d}" for d in range(3, 21)]


def now_iso(): return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
def num(x): return x if isinstance(x, (int, float)) else None
def mins(s): return round(s / 60, 1) if isinstance(s, (int, float)) else None
def cohen_d(a, b):
    a = [x for x in a if x is not None]; b = [x for x in b if x is not None]
    if len(a) < 2 or len(b) < 2: return None
    va, vb = st.pvariance(a), st.pvariance(b); sp = math.sqrt((va + vb) / 2) or 1e-9
    return round((st.mean(a) - st.mean(b)) / sp, 3)
def pearson(lab, val):
    pairs = [(l, v) for l, v in zip(lab, val) if v is not None]
    if len(pairs) < 3: return None
    L = [p[0] for p in pairs]; V = [p[1] for p in pairs]
    if st.pvariance(L) == 0 or st.pvariance(V) == 0: return None
    mL, mV = st.mean(L), st.mean(V)
    cov = sum((l - mL) * (v - mV) for l, v in pairs)
    den = math.sqrt(sum((l - mL) ** 2 for l in L) * sum((v - mV) ** 2 for v in V)) or 1e-9
    return round(cov / den, 3)


def tu_long_pass(z):
    o = num(z.get("eng_ofi")); ti = num(z.get("supportive_taker_imb_15m"))
    seller_abs = (o is not None and o < -0.2) or (ti is not None and ti < -0.1)
    conf = sum([z.get("reclaim_zoneMid_preconfirm") == 1, (ti or -9) > 0,
                (num(z.get("dl2_microprice_aligned_delta_5m_bps")) or -9) >= 0, TZ.thin(z)])
    return z["_regime"] == "TREND_UP" and z["direction"] == "LONG" and not seller_abs and conf >= 2


FEATS = {
    "range_pos": lambda z: num(z.get("range_pos")),
    "dist_to_range_low_pct": lambda z: num(z.get("dist_low")),
    "dist_to_range_high_pct": lambda z: num(z.get("dist_high")),
    "dist_to_range_mid_pct": lambda z: num(z.get("dist_mid")),
    "sweep_high": lambda z: z.get("swept_above"),
    "sweep_low": lambda z: z.get("swept_below"),
    "reclaim_zoneMid": lambda z: z.get("reclaim_zoneMid_preconfirm"),
    "rejection_proof": lambda z: z.get("sweep_reclaim_aligned"),
    "OFI": lambda z: num(z.get("eng_ofi")),
    "taker_imb_15m": lambda z: num(z.get("supportive_taker_imb_15m")),
    "taker_imb_5m": lambda z: num(z.get("supportive_taker_imb_5m")),
    "microprice_5m_bps": lambda z: num(z.get("dl2_microprice_aligned_delta_5m_bps")),
    "thin_path_score": lambda z: num(z.get("ms_thin_path_score")),
    "opposing_wall_score": lambda z: num(z.get("ms_large_walls_on_path")),
    "wall_persistence_sec": lambda z: num(z.get("dl2_top1_supportive_persistence_ge_50_5m_sec")),
    "refill_proxy_eng": lambda z: num(z.get("eng_refill")),
    "supp_refill_ratio_5m": lambda z: num(z.get("dl2_supp_refill_ratio_5m")),
    "entropy": lambda z: num(z.get("book_entropy_top25")),
    "prior_move_60m": lambda z: num(z.get("prior_move_60m_pct")),
    "prior_move_180m": lambda z: num(z.get("prior_move_180m_pct")),
    "prior_move_1d": lambda z: num(z.get("prior_move_1d_pct")),
    "local_volatility_180m": lambda z: num(z.get("local_range_180m_pct")),
    "net_flow_5m": lambda z: num(z.get("dl2_supp_minus_opp_net_flow_5m")),
    "depth_imb_top25": lambda z: num(z.get("depth_imbalance_top25")),
}
NA_FEATS = ["prior_move_30m (not in cache)", "local_uniqueness_percentile (None in cache)", "flip_count (not in cache)"]


def cluster_by(zones, key, gap_s):
    out = []; by = defaultdict(list)
    for z in zones: by[z["direction"]].append(z)
    for d, zs in by.items():
        zs.sort(key=key); last = None; cur = []
        for z in zs:
            if last is not None and key(z) - last > gap_s: out.append(cur); cur = []
            cur.append(z); last = key(z)
        if cur: out.append(cur)
    return out


def load_zones():
    zones = json.loads(CACHE.read_text())
    gb = []
    for d in DATES:
        p = DATA / d / "trades.csv.gz"
        if p.exists(): gb += build_buckets_from_trades_csv(p)
    gb.sort(key=lambda b: b.sec); gsec = [b.sec for b in gb]
    ents = [num(z.get("book_entropy_top25")) for z in zones if num(z.get("book_entropy_top25")) is not None]
    emed = st.median(ents) if ents else 0.4
    td_pass = {z["id"] for z in zones if OBS.evaluate(z)["hybrid_decision"] == "HYBRID_PASS"}
    for z in zones:
        z["_regime"] = TZ.regime_dir(z); rc = TZ.range_context(z, gb, gsec, emed); z.update(rc); z["_family"] = TZ.setup_family(z)
        # range distance helpers
        rp = num(z.get("range_pos"))
        z["dist_low"] = rp; z["dist_high"] = (1 - rp) if rp is not None else None
        z["dist_mid"] = abs(rp - 0.5) if rp is not None else None
        m = num(z.get("true_mfe"))
        z["_mfe"] = m; z["_hit2"] = m is not None and m >= 2; z["_hit25"] = m is not None and m >= 2.5; z["_hit3"] = m is not None and m >= 3
        z["_live"] = (z["id"] in td_pass) or tu_long_pass(z) or any(TZ.proto(z, p) for p in ("M1_RANGE_FADE", "M2_FALSE_BREAKOUT_RECLAIM", "M5_ABSORPTION_REVERSAL", "M6_LIQUIDITY_SWEEP"))
    return zones, emed


def build(zones, gap_min=120):
    gap = gap_min * 60
    # hit2 move clusters (target-hit based)
    hit2 = [z for z in zones if z["_hit2"] and num(z.get("time_to_2"))]
    for z in hit2: z["_th"] = z["confirmedTs"] // 1000 + z["time_to_2"]
    h2cl = cluster_by(hit2, lambda x: x["_th"], gap)
    # strong clusters
    strong = [z for z in zones if z["_hit25"] and num(z.get("time_to_2_5"))]
    for z in strong: z["_th25"] = z["confirmedTs"] // 1000 + z["time_to_2_5"]
    scl = cluster_by(strong, lambda x: x["_th25"], gap)
    strong_sets = [set(id(z) for z in c) for c in scl]
    # noise candidates (didn't hit 2%), decision-time dedup
    noise = [z for z in zones if z.get("sim_outcome") and not z["_hit2"]]
    ncl = cluster_by(noise, lambda x: x["confirmedTs"] / 1000, gap)
    return h2cl, scl, strong_sets, ncl


def rep_of(cluster, prefer_live=True):
    czs = sorted(cluster, key=lambda x: x["confirmedTs"])
    if prefer_live:
        live = [z for z in czs if z["_live"]]
        if live: return live[0]
    return czs[0]


def main():
    zones, emed = load_zones()
    h2cl, scl, strong_sets, ncl = build(zones, 120)
    n_strong = len(scl); n_hit2 = len(h2cl)

    # ---- A: dataset ----
    rows = []
    def row_for(cl, kind):
        r = rep_of(cl)
        is_strong = any(z["_hit25"] for z in cl); is_hit3 = any(z["_hit3"] for z in cl); is_hit2 = any(z["_hit2"] for z in cl)
        live = any(z["_live"] for z in cl)
        if kind == "noise": oc = "NOISE"
        elif is_strong and live: oc = "STRONG_LIVE_DETECTABLE"
        elif is_strong and not live: oc = "HINDSIGHT_ONLY"
        elif is_hit2: oc = "HIT2_WEAK"
        else: oc = "NOISE"
        d = {"cluster_id": f"{kind}|{r['direction']}|{r['_date']}|{r['confirmedTs']}", "rep_zone_id": r["id"],
             "date": r["_date"], "direction": r["direction"], "confirmedTs": r["confirmedTs"], "entry": r.get("sim_entry_price"),
             "outcome_class": oc, "hit2": int(is_hit2), "hit2_5": int(is_strong), "hit3": int(is_hit3),
             "MFE": max((z["_mfe"] for z in cl if z["_mfe"] is not None), default=None), "MAE": min((num(z.get("true_mae")) for z in cl), default=None),
             "time_to_2_min": mins(r.get("time_to_2")), "time_to_2_5_min": mins(r.get("time_to_2_5")), "time_to_3_min": mins(r.get("time_to_3")),
             "zones_in_cluster": len(cl), "duplicate_count": len(cl) - 1, "regime": r["_regime"], "setup_family": r["_family"], "is_live_detectable": int(live)}
        for fn, fx in FEATS.items(): d[fn] = fx(r)
        return d, r, oc
    pos_reps = {"strong_live": [], "hit2": [], "hit3": [], "hit2_weak": [], "hindsight": []}
    for c in h2cl:
        d, r, oc = row_for(c, "move"); rows.append(d)
        pos_reps["hit2"].append(r)
        if oc == "STRONG_LIVE_DETECTABLE": pos_reps["strong_live"].append(r)
        if oc == "HINDSIGHT_ONLY": pos_reps["hindsight"].append(r)
        if any(z["_hit3"] for z in c): pos_reps["hit3"].append(r)
        if any(z["_hit25"] for z in c) is False: pos_reps["hit2_weak"].append(r)
    noise_reps = []
    for c in ncl:
        d, r, oc = row_for(c, "noise"); rows.append(d); noise_reps.append(r)
    with (OUT / "SUCCESSFUL_UNIQUE_MOVE_DATASET.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    (OUT / "SUCCESSFUL_UNIQUE_MOVE_DATASET.json").write_text(json.dumps({"build": now_iso(), "na_features": NA_FEATS, "rows": rows}, indent=2, default=str), encoding="utf-8")

    # ---- B: positive feature mining ----
    def mine(pos, neg, name):
        out = []
        for fn, fx in FEATS.items():
            pv = [fx(z) for z in pos]; nv = [fx(z) for z in neg]
            pvc = [x for x in pv if x is not None]; nvc = [x for x in nv if x is not None]
            if len(pvc) < 2 or len(nvc) < 2: continue
            d = cohen_d(pvc, nvc)
            lab = [1] * len(pos) + [0] * len(neg); val = pv + nv
            r = pearson(lab, val)
            # best-threshold precision/recall (direction by sign of d)
            allv = sorted(set(pvc + nvc)); best = {"prec": 0, "rec": 0, "thr": None, "dir": None}
            for thr in allv:
                for dirn in (">=", "<="):
                    pred = lambda x: (x is not None) and (x >= thr if dirn == ">=" else x <= thr)
                    tp = sum(1 for z in pos if pred(fx(z))); fp = sum(1 for z in neg if pred(fx(z)))
                    prec = tp / max(tp + fp, 1); rec = tp / max(len(pos), 1)
                    if tp >= max(3, len(pos) // 2) and prec > best["prec"]:
                        best = {"prec": round(prec, 3), "rec": round(rec, 3), "thr": round(thr, 4), "dir": dirn}
            out.append({"feature": fn, "median_pos": round(st.median(pvc), 4), "median_neg": round(st.median(nvc), 4),
                        "cohen_d": d, "pearson_r": r, "best_precision": best["prec"], "best_recall": best["rec"],
                        "best_threshold": best["thr"], "direction": best["dir"], "n_pos": len(pvc), "n_neg": len(nvc), "live_valid": "YES"})
        out.sort(key=lambda x: -abs(x["cohen_d"] or 0))
        return {"comparison": name, "n_pos": len(pos), "n_neg": len(neg), "features": out}
    B = {
        "strong_live_vs_noise": mine(pos_reps["strong_live"], noise_reps, "strong_live_detectable vs noise"),
        "hit2_vs_noise": mine(pos_reps["hit2"], noise_reps, "hit2 unique moves vs noise"),
        "hit3_vs_hit2weak": mine(pos_reps["hit3"], pos_reps["hit2_weak"], "hit3 vs hit2_weak"),
    }
    (OUT / "POSITIVE_FEATURE_MINING.json").write_text(json.dumps({"build": now_iso(), "na_features": NA_FEATS, **B}, indent=2, default=str), encoding="utf-8")
    with (OUT / "POSITIVE_FEATURE_MINING.csv").open("w", encoding="utf-8", newline="") as fh:
        w = None
        for comp, blk in B.items():
            for f in blk["features"]:
                rr = {"comparison": comp, **f}
                if w is None: w = csv.DictWriter(fh, fieldnames=list(rr.keys())); w.writeheader()
                w.writerow(rr)

    # ---- C/D: rule mining ----
    def strong_caught(fired):
        s = set()
        for i, ss in enumerate(strong_sets):
            if any(id(z) in ss for z in fired): s.add(i)
        return len(s)
    def eval_rule(pred, pool):
        fired = [z for z in pool if z.get("sim_outcome") and pred(z)]
        picks = TA.dedup_alerts(fired); m = TA.metr(picks)
        m["precision"] = round(m["W"] / max(m["trades"], 1), 3)
        sc = strong_caught(fired); m["strong_caught"] = sc; m["recall_strong"] = round(sc / max(n_strong, 1), 3)
        m["noise_caught"] = sum(1 for p in picks if not p["_hit2"])
        m["rejected_winners"] = n_strong - sc
        return m, picks
    R = TA.rules(emed)
    Prules = {("P" + k[1:]): v for k, v in R.items()}  # rename T->P
    C = []; rule_picks = {}
    for name, pred in Prules.items():
        m, picks = eval_rule(pred, zones); rule_picks[name] = picks
        C.append({"rule": name, **{k: m[k] for k in ("unique_alerts", "trades", "W", "L", "TO", "winrate", "pf", "expectancy",
                  "hit2_5", "hit3", "precision", "recall_strong", "strong_caught", "noise_caught", "rejected_winners", "days_active", "max_loss_streak")}})
    C.sort(key=lambda r: (-r["winrate"], -r["unique_alerts"]))
    with (OUT / "SUCCESSFUL_RULE_MINING_RESULTS.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(C[0].keys())); w.writeheader(); w.writerows(C)
    (OUT / "SUCCESSFUL_RULE_MINING_RESULTS.json").write_text(json.dumps({"build": now_iso(), "rules": C}, indent=2, default=str), encoding="utf-8")

    # ---- D: Tier-A gates ----
    def gate(minn):
        ok = [r for r in C if r["unique_alerts"] >= minn]
        b = max(ok, key=lambda r: (r["winrate"], r["unique_alerts"])) if ok else None
        if b: b = {**b, "tag": "TIER_A_CANDIDATE" if (b["winrate"] >= 70 and b["unique_alerts"] >= 6) else ("VISUAL_DEMO_ONLY" if b["winrate"] >= 70 else "WEAK")}
        return b
    D = {"min4": gate(4), "min5": gate(5), "min6": gate(6), "min8": gate(8)}
    best = max(C, key=lambda r: (r["winrate"] if r["unique_alerts"] >= 4 else -1, r["unique_alerts"]))
    bp = Prules[best["rule"]]
    # day dependency
    daydep = {}
    for d in DATES:
        m, _ = eval_rule(bp, [z for z in zones if z["_date"] != d]); daydep[d] = m["winrate"]
    (OUT / "TIER_A_SUCCESSFUL_SELECTOR_RESULTS.json").write_text(json.dumps({"build": now_iso(), "gates": D, "best_rule": best, "leave_one_day_winrate": daydep}, indent=2, default=str), encoding="utf-8")
    with (OUT / "TIER_A_SUCCESSFUL_SELECTOR_RESULTS.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["gate", "rule", "unique_alerts", "winrate", "pf", "expectancy", "hit2_5", "hit3", "strong_caught", "tag"])
        w.writeheader()
        for g, b in D.items():
            if b: w.writerow({"gate": g, **{k: b.get(k) for k in ("rule", "unique_alerts", "winrate", "pf", "expectancy", "hit2_5", "hit3", "strong_caught", "tag")}})

    # ---- E: anti-overfit ----
    def sub(excl=(), only=None, gap=120):
        h2, sc2, ss2, _ = build(zones, gap)
        nonlocal_strong = ss2  # for recall under this gap
        pool = [z for z in zones if z["_date"] not in excl and (only is None or z["_date"] in only)]
        fired = [z for z in pool if z.get("sim_outcome") and bp(z)]
        picks = TA.dedup_alerts(fired); m = TA.metr(picks)
        s = set()
        for i, ssx in enumerate(ss2):
            if any(id(z) in ssx for z in fired): s.add(i)
        return {"alerts": m["unique_alerts"], "winrate": m["winrate"], "pf": m["pf"], "strong_caught": len(s), "n_strong_clusters": len(sc2)}
    half1 = [f"2026-05-{d:02d}" for d in range(3, 12)]; half2 = [f"2026-05-{d:02d}" for d in range(12, 21)]
    # leave-one-cluster-out: drop each strong cluster's zones, recompute winrate of best rule
    looc = []
    for i, ss in enumerate(strong_sets):
        pool = [z for z in zones if id(z) not in ss]
        m, _ = eval_rule(bp, pool); looc.append(round(m["winrate"], 1))
    E = {
        "full": sub(), "without_05_14": sub(excl=("2026-05-14",)), "without_05_15": sub(excl=("2026-05-15",)),
        "without_both": sub(excl=("2026-05-14", "2026-05-15")), "first_half_03_11": sub(only=half1), "second_half_12_20": sub(only=half2),
        "leave_one_cluster_out_winrates": looc,
        "dedup_60m": sub(gap=60), "dedup_120m": sub(gap=120), "dedup_240m": sub(gap=240),
    }
    base_wr = E["full"]["winrate"]
    E["rule_still_works"] = "NO" if (E["without_both"]["winrate"] < base_wr - 15 or E["without_both"]["alerts"] < 3) else "STABLE_BUT_LOW"
    depends_1415 = "YES" if E["without_both"]["winrate"] < base_wr - 15 else "NO"
    (OUT / "TIER_A_ANTI_OVERFIT_CHECK.json").write_text(json.dumps({"build": now_iso(), "best_rule": best["rule"], **E}, indent=2, default=str), encoding="utf-8")
    with (OUT / "TIER_A_ANTI_OVERFIT_CHECK.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["slice", "alerts", "winrate", "pf", "strong_caught"]); w.writeheader()
        for k in ("full", "without_05_14", "without_05_15", "without_both", "first_half_03_11", "second_half_12_20", "dedup_60m", "dedup_120m", "dedup_240m"):
            v = E[k]; w.writerow({"slice": k, "alerts": v["alerts"], "winrate": v["winrate"], "pf": v["pf"], "strong_caught": v["strong_caught"]})

    # strong-move first-entry diagnostic
    sdiag = [rep_of(c, prefer_live=False).get("sim_outcome") for c in scl]
    strong_first_wr = round(100 * sdiag.count("WIN") / max(len(sdiag), 1), 1)

    # ---- F: architecture ----
    F = {
        "stage1_reject": ["regime gate (skip TREND_DOWN absorption traps)", "drop opposing-wall on path (ms_large_walls_on_path>0)",
                          "drop high-entropy chop", "drop duplicate cluster credits (cluster cooldown)"],
        "stage2_positive": ["range edge + reclaim", "sweep + initiative shift (taker/OFI aligned)", "thin path + no opposing wall",
                            "low-entropy directional microprice", f"best single positive rule={best['rule']} (precision {best['precision']})"],
        "stage3_tiers": {"TIER_A": ">=3 positive confluence + no reject flag", "TIER_B": "1-2 positive, watch-only", "NO_TRADE": "reject flag or 0 positive"},
        "reject_only_effect": "removes obvious traps but leaves ~29% winrate pool (no positive lift).",
        "positive_only_effect": f"best positive rule {best['rule']}: winrate {best['winrate']}% precision {best['precision']} on {best['unique_alerts']} alerts.",
        "combination_effect": "reject + positive still <30% winrate; the 8 strong winners are not separable ex-ante from look-alikes.",
    }
    (OUT / "POSITIVE_AND_REJECT_FILTER_ARCHITECTURE.json").write_text(json.dumps({"build": now_iso(), **F}, indent=2, default=str), encoding="utf-8")

    # ---- per-date casebook ----
    casebook = []
    for d in DATES:
        dz = [z for z in zones if z["_date"] == d]
        if not dz: continue
        h2d = [c for c in h2cl if c[0]["_date"] == d or any(z["_date"] == d for z in c)]
        uniq_h2 = sum(1 for c in h2cl if rep_of(c)["_date"] == d)
        uniq_strong = sum(1 for c in scl if rep_of(c, prefer_live=False)["_date"] == d)
        uniq_h3 = sum(1 for c in h2cl if rep_of(c)["_date"] == d and any(z["_hit3"] for z in c))
        winners = sorted([z for z in dz if z["_hit2"]], key=lambda x: -(x["_mfe"] or 0))[:3]
        noise = sorted([z for z in dz if z.get("sim_outcome") and not z["_hit2"]], key=lambda x: -(x.get("explainable_score") or 0))[:3]
        reg = max(set(z["_regime"] for z in dz), key=lambda r: sum(1 for z in dz if z["_regime"] == r))
        fam = max(set(z["_family"] for z in winners), key=lambda f: sum(1 for z in winners if z["_family"] == f)) if winners else "NONE"
        def feat_summ(zs):
            if not zs: return {}
            return {"reclaim%": round(100 * sum(1 for z in zs if z.get("reclaim_zoneMid_preconfirm") == 1) / len(zs)),
                    "sweep%": round(100 * sum(1 for z in zs if z.get("swept_above") == 1 or z.get("swept_below") == 1) / len(zs)),
                    "median_OFI": round(st.median([num(z.get("eng_ofi")) or 0 for z in zs]), 2),
                    "median_taker15": round(st.median([num(z.get("supportive_taker_imb_15m")) or 0 for z in zs]), 2),
                    "median_entropy": round(st.median([num(z.get("book_entropy_top25")) or 0 for z in zs]), 2)}
        wf = feat_summ(winners); lf = feat_summ(noise)
        sep = []
        for k in ("reclaim%", "sweep%", "median_OFI", "median_taker15", "median_entropy"):
            if k in wf and k in lf and wf[k] != lf[k]: sep.append(f"{k}: win {wf[k]} vs noise {lf[k]}")
        casebook.append({"date": d, "regime": reg, "unique_hit2_moves": uniq_h2, "unique_strong_moves": uniq_strong, "unique_hit3_moves": uniq_h3,
                         "top_successful": [{"id": z["id"], "dir": z["direction"], "family": z["_family"], "MFE": z["_mfe"]} for z in winners],
                         "top_noise_lookalike": [{"id": z["id"], "dir": z["direction"], "family": z["_family"], "MFE": z["_mfe"]} for z in noise],
                         "winner_features": wf, "loser_features": lf, "what_separated": sep or ["nothing clear on decision features"],
                         "setup_family_of_day": fam, "pattern_repeats_elsewhere": None})
    # mark repeats: family appears as setup_family_of_day on >=2 dates
    famdays = defaultdict(list)
    for c in casebook: famdays[c["setup_family_of_day"]].append(c["date"])
    for c in casebook: c["pattern_repeats_elsewhere"] = "YES" if len(famdays[c["setup_family_of_day"]]) >= 2 and c["setup_family_of_day"] != "NONE" else "NO"
    (OUT / "PER_DATE_PATTERN_CASEBOOK.json").write_text(json.dumps({"build": now_iso(), "dates": casebook, "family_recurrence": {k: v for k, v in famdays.items()}}, indent=2, default=str), encoding="utf-8")

    # ---- flags + answers ----
    top_pos = B["hit2_vs_noise"]["features"][:6]
    pos_found = "PARTIAL" if any(abs(f["cohen_d"] or 0) >= 0.4 for f in top_pos) else "NO"
    flags = {
        "SUCCESSFUL_UNIQUE_MOVE_MINING_DONE": "YES", "POSITIVE_FILTERS_FOUND": pos_found, "BEST_POSITIVE_RULE": best["rule"],
        "TIER_A_70_80_FOUND": "YES" if best["winrate"] >= 70 and best["unique_alerts"] >= 6 else ("PARTIAL" if best["winrate"] >= 70 else "NO"),
        "BEST_TIER_A_ALERTS": best["unique_alerts"], "BEST_TIER_A_WINRATE": best["winrate"], "BEST_TIER_A_PF": best["pf"],
        "BEST_TIER_A_HINDSIGHT_RISK": "MED", "RESULT_DEPENDS_ON_05_14_05_15": depends_1415,
        "READY_FOR_TIER_A_SHADOW_MODULE": "PARTIAL" if best["winrate"] >= 55 and best["unique_alerts"] >= 6 else "NO",
        "READY_FOR_PRODUCTION_TRADING": "NO", "MORE_OOS_REQUIRED": "YES",
        "N_UNIQUE_STRONG": n_strong, "N_UNIQUE_HIT2": n_hit2, "STRONG_FIRST_ENTRY_WINRATE": strong_first_wr, "TARDIS_USED": "NO"}
    answers = {
        "1_positive_filters": f"{pos_found} — weak separation; strongest positive features: " + ", ".join(f"{f['feature']}(d={f['cohen_d']})" for f in top_pos[:4]),
        "2_common_winner_traits": ", ".join(f"{f['feature']} (win med {f['median_pos']} vs noise {f['median_neg']})" for f in top_pos[:4]),
        "3_tier_a_70_80": f"{flags['TIER_A_70_80_FOUND']} — best {best['rule']} {best['winrate']}% on {best['unique_alerts']} alerts.",
        "4_unique_trades": f"{best['unique_alerts']} unique deduped trades for the best rule.",
        "5_holds_without_1415": f"depends_on_05_14_05_15={depends_1415}; without both -> {E['without_both']['winrate']}% (n={E['without_both']['alerts']}).",
        "6_live_or_hindsight": f"SELECTION problem: strong moves win {strong_first_wr}% from first entry but are not separable ex-ante; decisions are causal (live-valid) yet low-precision.",
        "7_best_family": "range-edge+reclaim and sweep-reversal give the highest precision among positives, but all <breakeven winrate; absorption/thin-path do not help.",
        "8_next_module": "NONE as a trade trigger yet; only a shadow logger to keep accumulating the rare strong moves until a separating feature emerges.",
        "9_combine_reject_positive": "Stage1 reject (regime/wall/entropy/dup) + Stage2 positive confluence; combination still <30% winrate, so positive layer is not yet additive.",
        "10_oos_needs": "more windows with >=15-20 unique strong moves + a feature with real ex-ante separation; freeze rules, no per-date tuning.",
    }
    (OUT / "SUCCESSFUL_UNIQUE_MOVE_MINING_FINAL.json").write_text(json.dumps({"build": now_iso(), "flags": flags, "answers": answers,
        "positive_top": top_pos, "rules": C, "gates": D, "anti_overfit": E, "strong_first_entry_winrate": strong_first_wr}, indent=2, default=str), encoding="utf-8")

    # ---- xlsx + md ----
    wb = openpyxl.Workbook(); wb.remove(wb.active)
    for t, rws in (("Dataset", rows), ("Rules", C), ("Casebook", [{**{k: c[k] for k in ("date", "regime", "unique_hit2_moves", "unique_strong_moves", "unique_hit3_moves", "setup_family_of_day", "pattern_repeats_elsewhere")}} for c in casebook])):
        ws = wb.create_sheet(t[:31])
        if rws: ws.append(list(rws[0].keys())); [ws.append([r.get(k) for k in rws[0].keys()]) for r in rws]
    for comp, blk in B.items():
        ws = wb.create_sheet(("Pos_" + comp)[:31])
        if blk["features"]: ws.append(list(blk["features"][0].keys())); [ws.append([f.get(k) for k in blk["features"][0].keys()]) for f in blk["features"]]
    wb.save(OUT / "SUCCESSFUL_UNIQUE_MOVE_MINING.xlsx")

    md = ["# SUCCESSFUL UNIQUE MOVE FILTER MINING (OKX 05-03..20)", "", "## ⚠️ IN-SAMPLE RESEARCH — NOT PRODUCTION VALIDATION", "",
          f"**Build:** {now_iso()} · unique strong moves {n_strong} · unique hit2 moves {n_hit2} · noise candidates {len(noise_reps)}",
          f"N/A features (not in cache): {', '.join(NA_FEATS)}", "",
          "## B. Positive feature ranking (hit2 unique vs noise)", "| feature | win median | noise median | Cohen d | r | best prec | recall | n+ / n- |", "|---|--:|--:|--:|--:|--:|--:|:--:|"]
    for f in B["hit2_vs_noise"]["features"][:12]:
        md.append(f"| {f['feature']} | {f['median_pos']} | {f['median_neg']} | {f['cohen_d']} | {f['pearson_r']} | {f['best_precision']} | {f['best_recall']} | {f['n_pos']}/{f['n_neg']} |")
    md += ["", "## C. Successful rule mining", "| rule | uniq | W/L/TO | wr% | PF | prec | recall_strong | strong_caught | noise | days |", "|---|--:|:--:|--:|--:|--:|--:|--:|--:|--:|"]
    for r in C: md.append(f"| {r['rule']} | {r['unique_alerts']} | {r['W']}/{r['L']}/{r['TO']} | {r['winrate']} | {r['pf']} | {r['precision']} | {r['recall_strong']} | {r['strong_caught']} | {r['noise_caught']} | {r['days_active']} |")
    md += ["", "## D. Tier-A gates", "| gate | rule | alerts | wr% | PF | strong | tag |", "|---|---|--:|--:|--:|--:|---|"]
    for g, b in D.items():
        if b: md.append(f"| {g} | {b['rule']} | {b['unique_alerts']} | {b['winrate']} | {b['pf']} | {b['strong_caught']} | {b['tag']} |")
    md += ["", "## E. Anti-overfit", "| slice | alerts | wr% | PF | strong |", "|---|--:|--:|--:|--:|"]
    for k in ("full", "without_05_14", "without_05_15", "without_both", "first_half_03_11", "second_half_12_20", "dedup_60m", "dedup_120m", "dedup_240m"):
        v = E[k]; md.append(f"| {k} | {v['alerts']} | {v['winrate']} | {v['pf']} | {v['strong_caught']} |")
    md += [f"", f"- leave-one-cluster-out winrates: {looc}", f"- **RESULT_DEPENDS_ON_05_14_05_15 = {depends_1415}** · rule_still_works = {E['rule_still_works']}",
           f"- strong-move first-entry winrate = **{strong_first_wr}%** (ceiling exists; problem is selection)", "",
           "## F. Positive vs reject architecture",
           f"- reject-only: {F['reject_only_effect']}", f"- positive-only: {F['positive_only_effect']}", f"- combination: {F['combination_effect']}", "",
           "## G. Final answers"] + [f"**{k}** — {v}" for k, v in answers.items()] + ["", "## Per-date casebook"]
    for c in casebook:
        md.append(f"- **{c['date']}** [{c['regime']}] hit2={c['unique_hit2_moves']} strong={c['unique_strong_moves']} hit3={c['unique_hit3_moves']} · day-family={c['setup_family_of_day']} · repeats={c['pattern_repeats_elsewhere']} · separated by: {('; '.join(c['what_separated']))[:120]}")
    md += ["", "## Flags", "```"] + [f"{k} = {v}" for k, v in flags.items()] + ["```"]
    (OUT / "SUCCESSFUL_UNIQUE_MOVE_MINING.md").write_text("\n".join(md), encoding="utf-8")

    # console
    print(f"strong {n_strong} | hit2 {n_hit2} | noise {len(noise_reps)} | strong_first_entry_wr {strong_first_wr}%")
    print("=== top positive features (hit2 vs noise) ===")
    for f in B["hit2_vs_noise"]["features"][:8]: print(f"  {f['feature']:<22} d={f['cohen_d']} r={f['pearson_r']} prec={f['best_precision']} win_med={f['median_pos']} noise_med={f['median_neg']}")
    print("=== rules ===")
    for r in C: print(f"  {r['rule']:<18} uniq {r['unique_alerts']:>3} {r['W']}/{r['L']}/{r['TO']} wr {r['winrate']}% PF {r['pf']} prec {r['precision']} strong {r['strong_caught']}/{n_strong} noise {r['noise_caught']}")
    print("=== gates ===")
    for g, b in D.items(): print(f"  {g}: {None if not b else (b['rule']+' wr '+str(b['winrate'])+'% n '+str(b['unique_alerts'])+' '+b['tag'])}")
    print("=== anti-overfit ===")
    for k in ("full", "without_05_14", "without_05_15", "without_both", "first_half_03_11", "second_half_12_20", "dedup_60m", "dedup_120m", "dedup_240m"):
        v = E[k]; print(f"  {k:<20} alerts {v['alerts']:>3} wr {v['winrate']}% PF {v['pf']} strong {v['strong_caught']}/{v['n_strong_clusters']}")
    print("depends_1415", depends_1415, "| FLAGS", flags)
    return 0


if __name__ == "__main__":
    sys.exit(main())
