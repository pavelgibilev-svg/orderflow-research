"""TREND_DOWN cross-venue v2 — GOOD-ZONE forensic pass (analysis of existing artifacts; NO re-parse, NO tuning).

Reconstructs cross-venue categories from CROSS_VENUE_MATCHED_CLUSTERS.csv, joins each cluster to its full
decision features (ZONES_RAW.csv) + evidence scores + capital_state, then: A casebook of the 6 cross-confirmed
markdown shorts, B window map, C good-vs-bad feature comparison, D DNA/similarity, E soft template, F rough
stats, G final. RESEARCH ONLY — not production, not a winrate optimization.
"""
from __future__ import annotations
import csv, json, statistics as st, sys, datetime as dt
from collections import defaultdict, Counter
from pathlib import Path

D = Path("C:/Users/gibilev/orderflow-research/reports/trend_down_crossvenue_v2")
WINDOWS = {"W1_NOVEMBER": "2025-11-19..22", "W3_JANUARY": "2026-01-28..31", "W4_APRIL": "2024-04-12..17"}
MARKDOWN_STATES = ("ACTIVE_MARKDOWN", "FORCED_UNWIND", "DISTRIBUTION_INTO_BOUNCE")
FEATS = ["cvd_delta_60m", "taker_imb_30m", "net_taker_30m", "sell_frac_30m", "effort_vs_result_raw", "price_change_30m",
         "spread_bps", "depth_imbalance", "trade_count_spike", "dist_from_recent_low_pct", "dist_from_recent_high_pct",
         "bounce_into_pivot_pct", "vol_30m_btc", "local_vol_180m", "prior_move_60m"]
EV = ["effort_vs_result", "absorption_refill", "initiative_control", "background_alignment", "not_overextended", "liquidity_execution"]


def now(): return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
def fnum(x):
    try: return float(x)
    except (TypeError, ValueError): return None
def med(vals):
    v = [x for x in vals if x is not None]
    return round(st.median(v), 4) if v else None
def pf_of(W, L): return round((W * 1.86) / (L * 1.64), 3) if L else ("inf" if W else None)


def load():
    uc = list(csv.DictReader((D / "UNIQUE_CLUSTERS.csv").open(encoding="utf-8")))
    zr = list(csv.DictReader((D / "ZONES_RAW.csv").open(encoding="utf-8")))
    ev = {r["cluster_id"]: r for r in csv.DictReader((D / "EVIDENCE_BLOCK_SCORES.csv").open(encoding="utf-8"))}
    cb = {r["cluster_id"]: r for r in csv.DictReader((D / "CAPITAL_STATE_CASEBOOK.csv").open(encoding="utf-8"))}
    matched = list(csv.DictReader((D / "CROSS_VENUE_MATCHED_CLUSTERS.csv").open(encoding="utf-8")))
    # index ZONES_RAW by (exchange,window,direction,ts_iso,entry)
    zidx = {}
    for z in zr: zidx[(z["exchange"], z["window_id"], z["direction_candidate"], z["ts_iso"], z["entry_price"])] = z
    # cross-venue categories
    confirmed = set(); disagree = set(); pair_of = {}
    for m in matched:
        bc, oc = m["bybit_cluster"], m["okx_cluster"]
        (confirmed if m["agree_state"] == "1" else disagree).update([bc, oc])
        pair_of[bc] = oc; pair_of[oc] = bc
    clusters = {}
    for u in uc:
        cid = u["cluster_id"]
        z = zidx.get((u["exchange"], u["window_id"], u["direction_candidate"], u["ts_start"], u["entry_price"]), {})
        e = ev.get(cid, {}); b = cb.get(cid, {})
        cat = "CROSS_CONFIRMED" if cid in confirmed else ("CROSS_DISAGREEMENT" if cid in disagree else (u["exchange"].upper() + "_ONLY"))
        rec = {"cluster_id": cid, "exchange": u["exchange"], "window_id": u["window_id"], "date": u["date"], "ts_start": u["ts_start"],
               "direction": u["direction_candidate"], "entry_price": fnum(u["entry_price"]), "outcome": u["outcome"],
               "hit2": int(u["hit2"]), "hit2_5": int(u["hit2_5"]), "hit3": int(u["hit3"]), "loss": int(u["loss"]), "timeout": int(u["timeout"]),
               "mfe": fnum(u["future_mfe_pct"]), "mae": fnum(z.get("future_mae_pct")), "time_to_2": u["time_to_2"],
               "capital_state": b.get("capital_state_candidate", "UNKNOWN"), "cat": cat, "matched_with": pair_of.get(cid)}
        for f in FEATS: rec[f] = fnum(z.get(f))
        for k in EV: rec[k] = fnum(e.get(k))
        clusters[cid] = rec
    return clusters, matched


def grp_med(rows):
    out = {"n": len(rows), "hit2": sum(r["hit2"] for r in rows), "loss": sum(r["loss"] for r in rows), "timeout": sum(r["timeout"] for r in rows)}
    for f in FEATS + EV: out["med_" + f] = med([r.get(f) for r in rows])
    W = sum(1 for r in rows if r["outcome"] == "WIN"); L = sum(1 for r in rows if r["outcome"] == "LOSS")
    out["pf"] = pf_of(W, L); out["hit2_rate"] = round(100 * out["hit2"] / max(out["n"], 1), 1)
    return out


def explain(r):
    s = []
    if r["hit2"]: s.append("WIN: reached 2% down")
    elif r["loss"]: s.append("LOSS: +1.5% adverse first (bounce held / bid absorbed)")
    else: s.append("TIMEOUT: drifted, no 2% in horizon")
    if r.get("cvd_delta_60m") is not None: s.append(f"CVD60 {r['cvd_delta_60m']:+.0f} ({'net selling' if r['cvd_delta_60m']<0 else 'net buying'})")
    if r.get("taker_imb_30m") is not None: s.append(f"takerImb30 {r['taker_imb_30m']:+.2f}")
    if r.get("effort_vs_result_raw") is not None: s.append(f"effort_vs_result {r['effort_vs_result_raw']:+.2f} ({'down driven by selling' if r['effort_vs_result_raw']>0 else 'selling absorbed / no progress'})")
    if r.get("depth_imbalance") is not None: s.append(f"depthImb {r['depth_imbalance']:+.2f} ({'bid-heavy(absorption risk)' if r['depth_imbalance']>0.1 else 'ask-heavy(supply)' if r['depth_imbalance']<-0.1 else 'balanced'})")
    if r.get("dist_from_recent_low_pct") is not None: s.append(f"room_to_low {r['dist_from_recent_low_pct']:.2f}%")
    return "; ".join(s)


def main():
    clusters, matched = load()
    allc = list(clusters.values())
    good = [r for r in allc if r["cat"] == "CROSS_CONFIRMED" and r["direction"] == "SHORT" and r["capital_state"] in MARKDOWN_STATES]
    good.sort(key=lambda r: r["ts_start"])

    # ---- A: good-zone casebook ----
    acols = ["cluster_id", "matched_with", "window_id", "date", "ts_start", "exchange", "direction", "entry_price", "outcome",
             "hit2", "loss", "timeout", "mfe", "mae", "time_to_2", "capital_state"] + EV + ["cvd_delta_60m", "taker_imb_30m", "net_taker_30m",
             "effort_vs_result_raw", "depth_imbalance", "spread_bps", "dist_from_recent_low_pct", "bounce_into_pivot_pct", "explanation"]
    arows = []
    for r in good:
        rr = {k: r.get(k) for k in acols if k != "explanation"}; rr["explanation"] = explain(r); arows.append(rr)
    with (D / "GOOD_ZONE_CASEBOOK_CROSS_CONFIRMED.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=acols, extrasaction="ignore"); w.writeheader(); w.writerows(arows)
    amd = ["# GOOD ZONE CASEBOOK — cross-confirmed markdown shorts (n=%d)" % len(good), "", f"Build {now()} · RESEARCH (no tuning).",
           f"These are the clusters behind TD_CROSS_VENUE_CONFIRMED_MARKDOWN_SHORT (PF 1.13). They are **{len(good)} clusters = {len(good)//2} cross-venue moments** (each moment seen on Bybit AND OKX).", ""]
    for r in good:
        amd += [f"## {r['cluster_id']}  [{r['exchange']}]  {r['window_id']} {r['date']}",
                f"- ts {r['ts_start']} · matched_with {r['matched_with']} · {r['capital_state']} · outcome **{r['outcome']}** (hit2={r['hit2']})",
                f"- entry {r['entry_price']} · MFE {r['mfe']}% · MAE {r['mae']}% · time_to_2 {r['time_to_2']}",
                f"- evidence: " + ", ".join(f"{k}={r.get(k)}" for k in EV),
                f"- flow: CVD60 {r.get('cvd_delta_60m')} · takerImb30 {r.get('taker_imb_30m')} · effort_vs_result {r.get('effort_vs_result_raw')} · depthImb {r.get('depth_imbalance')} · spread {r.get('spread_bps')}bps",
                f"- **why:** {explain(r)}", ""]
    amd += ["> CVD before/during/after: only **before-entry** (cvd_delta_60m, causal) is available from saved artifacts; during/after would require re-parsing the per-minute series (not done in this analysis-only pass) -> N/A."]
    (D / "GOOD_ZONE_CASEBOOK_CROSS_CONFIRMED.md").write_text("\n".join(amd), encoding="utf-8")

    # ---- B: window map ----
    bm = []
    for wid in WINDOWS:
        g = [r for r in good if r["window_id"] == wid]
        conf = [r for r in allc if r["cat"] == "CROSS_CONFIRMED" and r["window_id"] == wid]
        bad_conf = [r for r in conf if r["hit2"] == 0]
        dis = [r for r in allc if r["cat"] == "CROSS_DISAGREEMENT" and r["window_id"] == wid]
        best = max(g, key=lambda r: (r["hit2"], r["mfe"] or 0)) if g else None
        states = Counter(r["capital_state"] for r in conf)
        bm.append({"window_id": wid, "dates": WINDOWS[wid], "good_zones": len(g), "bad_confirmed_zones": len(bad_conf),
                   "disagreement_zones": len(dis), "best_zone_ts": (best["ts_start"] if best else "-"),
                   "dominant_capital_state": (states.most_common(1)[0][0] if states else "-"),
                   "notes": f"good={len(g)} (hit2 {sum(r['hit2'] for r in g)})"})
    with (D / "GOOD_ZONE_WINDOW_MAP.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(bm[0].keys())); w.writeheader(); w.writerows(bm)
    (D / "GOOD_ZONE_WINDOW_MAP.md").write_text("# GOOD ZONE WINDOW MAP\n\nBuild %s\n\n| window | dates | good | bad_confirmed | disagreement | best_ts | dominant_state |\n|---|---|--:|--:|--:|---|---|\n" % now() +
        "\n".join(f"| {r['window_id']} | {r['dates']} | {r['good_zones']} | {r['bad_confirmed_zones']} | {r['disagreement_zones']} | {r['best_zone_ts']} | {r['dominant_capital_state']} |" for r in bm) + "\n", encoding="utf-8")

    # ---- C: good vs bad feature comparison ----
    confirmed_short = [r for r in allc if r["cat"] == "CROSS_CONFIRMED" and r["direction"] == "SHORT"]
    g_win = [r for r in confirmed_short if r["hit2"] == 1]
    g_lose = [r for r in confirmed_short if r["hit2"] == 0]
    dis_lose = [r for r in allc if r["cat"] == "CROSS_DISAGREEMENT" and r["direction"] == "SHORT" and r["outcome"] in ("LOSS", "TIMEOUT")]
    groups = {"GOOD_CONFIRMED_WINNERS": grp_med(g_win), "BAD_CONFIRMED_LOSERS": grp_med(g_lose), "DISAGREEMENT_LOSERS": grp_med(dis_lose)}
    with (D / "GOOD_VS_BAD_FEATURE_COMPARISON.csv").open("w", encoding="utf-8", newline="") as fh:
        cols = ["group", "n", "hit2", "loss", "timeout", "hit2_rate", "pf"] + ["med_" + f for f in FEATS + EV]
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore"); w.writeheader()
        for gname, gv in groups.items(): w.writerow({"group": gname, **gv})
    cmd = ["# GOOD vs BAD FEATURE COMPARISON (medians)", "", f"Build {now()} · cross-confirmed SHORT winners vs losers vs disagreement losers.",
           f"n: winners {groups['GOOD_CONFIRMED_WINNERS']['n']}, confirmed-losers {groups['BAD_CONFIRMED_LOSERS']['n']}, disagreement-losers {groups['DISAGREEMENT_LOSERS']['n']}.", "",
           "| feature | GOOD_winners | BAD_confirmed_losers | DISAGREEMENT_losers |", "|---|--:|--:|--:|"]
    for f in FEATS + EV:
        cmd.append(f"| {f} | {groups['GOOD_CONFIRMED_WINNERS'].get('med_'+f)} | {groups['BAD_CONFIRMED_LOSERS'].get('med_'+f)} | {groups['DISAGREEMENT_LOSERS'].get('med_'+f)} |")
    cmd += ["", "_CVD during/after, refill-after-hit, post-flow price response are N/A here (need re-parse). volume_burst≈trade_count_spike, late-entry≈dist_from_recent_low/room-to-TP2._"]
    (D / "GOOD_VS_BAD_FEATURE_COMPARISON.md").write_text("\n".join(cmd), encoding="utf-8")

    # ---- D: DNA analysis ----
    wins_in = sorted(set(r["window_id"] for r in good)); moments = len(good) // 2
    states = Counter(r["capital_state"] for r in good)
    # similarity heuristics
    cvd_all_neg = all((r.get("cvd_delta_60m") or 0) < 0 for r in good)
    init_all_pos = all((r.get("initiative_control") or 0) >= 1 for r in good)
    evr_all_pos = all((r.get("effort_vs_result_raw") or 0) > 0 for r in good)
    spread_var = med([r.get("spread_bps") for r in good])
    sim = "LOW"
    agree_cnt = sum([cvd_all_neg, init_all_pos, evr_all_pos, len(wins_in) >= 2])
    if agree_cnt >= 3 and len(wins_in) >= 2 and moments >= 4: sim = "MEDIUM"
    if agree_cnt >= 4 and moments >= 6: sim = "HIGH"
    g_win = [r for r in good if r["hit2"] == 1]; g_lose = [r for r in good if r["hit2"] == 0]
    dmd = ["# GOOD ZONE DNA ANALYSIS", "", f"Build {now()} · qualitative, no tuning.", "",
           f"- n={len(good)} clusters = **{moments} independent cross-venue moments** (each on Bybit+OKX).",
           f"- windows present: {wins_in} ({'distributed' if len(wins_in)>=2 else 'SINGLE WINDOW'})",
           f"- capital states: {dict(states)} (all DISTRIBUTION_INTO_BOUNCE by construction — markdown/unwind states never fired)",
           "",
           "## 1. Same window or distributed? -> " + (f"distributed across {len(wins_in)}" if len(wins_in) >= 2 else "ONE window (fragile)"),
           "## 2. Same move type? -> all DISTRIBUTION_INTO_BOUNCE shorts (shorting a bounce into a lower-high).",
           f"## 3. Similar CVD/taker flow? -> CVD60 all negative: {cvd_all_neg}; median takerImb30 {med([r.get('taker_imb_30m') for r in good])}.",
           f"## 4. Similar effort-vs-result? -> all positive (down driven by selling): {evr_all_pos}; median {med([r.get('effort_vs_result_raw') for r in good])}.",
           f"## 5. Similar cross-venue picture? -> yes by definition (both venues agreed state+direction within 30m).",
           "## 6. Same price reaction after aggressive sell? -> N/A from saved artifacts (post-flow response not stored).",
           f"## 7. 'Seller really controls' common? -> initiative_control>=1 on all: {init_all_pos}; this is the most consistent positive marker.",
           f"## 8. 'Not late entry' common? -> median room_to_low {med([r.get('dist_from_recent_low_pct') for r in good])}% (mixed; not a clean shared marker).",
           f"## 9. Same liquidity path? -> median spread {spread_var}bps; depthImb median {med([r.get('depth_imbalance') for r in good])} (not uniform).",
           "## 10. A veto that removes the bad ones? -> cross-venue DISAGREEMENT veto + NO_CONTROL_CHOP no-trade already separate the worst; within the good set, winners had stronger initiative_control/effort_vs_result but n is too small to set a threshold.",
           "",
           f"## Winners ({len(g_win)}) vs losers ({len(g_lose)}) inside the good set:",
           f"- winners median initiative_control {med([r.get('initiative_control') for r in g_win])} vs losers {med([r.get('initiative_control') for r in g_lose])}",
           f"- winners median effort_vs_result {med([r.get('effort_vs_result_raw') for r in g_win])} vs losers {med([r.get('effort_vs_result_raw') for r in g_lose])}",
           f"- winners median room_to_low {med([r.get('dist_from_recent_low_pct') for r in g_win])} vs losers {med([r.get('dist_from_recent_low_pct') for r in g_lose])}",
           "",
           f"GOOD_ZONE_SIMILARITY:\n{sim}", "",
           ("**Honest note:** PF 1.13 on n=%d (only %d independent moments) is almost certainly NOISE. The shared traits "
            "(net selling, positive initiative_control, effort_vs_result>0, cross-venue agreement) are directionally sensible "
            "but cannot be distinguished from chance at this sample size." % (len(good), moments)) if sim != "HIGH" else "Similarity high; still needs OOS."]
    (D / "GOOD_ZONE_DNA_ANALYSIS.md").write_text("\n".join(dmd), encoding="utf-8")

    # ---- E: soft template ----
    soft = {"template_id": "TD_CROSS_CONFIRMED_MARKDOWN_SOFT_TEMPLATE", "status_hint": "see SOFT_TEMPLATE_STATS",
            "level_1_background": "TREND_DOWN (window net<=-1% and prior move down)",
            "required_capital_state": "SHORT markdown-type (ACTIVE_MARKDOWN / FORCED_UNWIND / DISTRIBUTION_INTO_BOUNCE)",
            "required_cross_venue_behavior": "Bybit AND OKX agree on direction (SHORT) AND capital_state within <=30 min",
            "required_direction_consistency": "zone direction == SHORT; never apply a short-state to a LONG zone",
            "required_evidence_blocks": {"initiative_control": ">=1 (CVD60<0 & taker_imb_30<0)", "effort_vs_result": ">0 (down driven by net selling)", "background_alignment": ">=1 (prior 60m/180m down)"},
            "soft_confirmations": ["ask-heavy or balanced depth (not bid-heavy)", "non-trivial 30m volume / activity present", "room to recent low (not already at the low)"],
            "veto_conditions": ["cross-venue DISAGREEMENT -> no trade", "NO_CONTROL_CHOP -> no trade", "ABSORPTION_AFTER_SELL_PRESSURE / bid-heavy depth -> no short (reversal-watch)", "signal on one venue only -> quarantine"],
            "when_not_to_short": ["price already at recent low (no room to TP2)", "bid refill / CVD turning up", "venues disagree", "spread blown / chaotic book"],
            "manual_casebook_checks": ["was the bounce genuinely sold into on BOTH venues?", "did sellers keep initiative after the bounce (CVD continuing down)?", "is there room to 2% before the prior low?"],
            "still_uncertain": ["only ~3 independent moments", "all are DISTRIBUTION_INTO_BOUNCE (no true ACTIVE_MARKDOWN/FORCED_UNWIND samples)", "lower-high pivot trigger may be the wrong trigger for markdown continuation", "post-entry CVD/refill not yet measured"],
            "logic": "IF TREND_DOWN AND Bybit/OKX agree SHORT+state AND initiative_control>=1 AND effort_vs_result>0 AND no absorption-against-short AND not late -> SHORT_CANDIDATE_RESEARCH; ELSE veto per above."}
    (D / "TD_CROSS_CONFIRMED_MARKDOWN_SOFT_TEMPLATE.json").write_text(json.dumps({"build": now(), "research_only": True, "template": soft}, indent=2, default=str), encoding="utf-8")
    (D / "TD_CROSS_CONFIRMED_MARKDOWN_SOFT_TEMPLATE.md").write_text("# TD_CROSS_CONFIRMED_MARKDOWN_SOFT_TEMPLATE (research, soft)\n\nBuild %s · NOT production, NOT a hard 80%% filter.\n\n" % now() +
        "\n".join(f"- **{k}**: {v}" for k, v in soft.items()) + "\n", encoding="utf-8")

    # ---- F: rough stats (no extra fitting) = exactly the good set ----
    W = sum(1 for r in good if r["outcome"] == "WIN"); L = sum(1 for r in good if r["outcome"] == "LOSS"); TO = sum(1 for r in good if r["outcome"] == "TIMEOUT")
    exs = sorted(set(r["exchange"] for r in good)); wins = sorted(set(r["window_id"] for r in good)); moments = len(good) // 2
    if len(good) < 4: status = "NEED_MORE_DATA"
    elif len(wins) < 2: status = "QUARANTINE"
    elif pf_of(W, L) in (None,) or (isinstance(pf_of(W, L), float) and pf_of(W, L) < 0.9): status = "REJECT"
    else: status = "NEED_MORE_DATA"  # PF>1 but n=6/3 moments -> not a candidate
    stats = {"template_id": "TD_CROSS_CONFIRMED_MARKDOWN_SOFT_TEMPLATE", "n_clusters": len(good), "independent_moments": moments,
             "hit2": sum(r["hit2"] for r in good), "hit2_rate": round(100 * sum(r["hit2"] for r in good) / max(len(good), 1), 1),
             "W": W, "L": L, "TO": TO, "pf": pf_of(W, L), "expectancy": round(st.mean([1.86 if r["outcome"] == "WIN" else -1.64 if r["outcome"] == "LOSS" else 0 for r in good]), 3) if good else None,
             "windows": wins, "exchange_stability": ("BOTH" if len(exs) >= 2 else exs), "overfit_risk": "HIGH", "status": status}
    with (D / "SOFT_TEMPLATE_STATS.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(stats.keys()), extrasaction="ignore"); w.writeheader()
        w.writerow({k: (json.dumps(v) if isinstance(v, list) else v) for k, v in stats.items()})
    (D / "SOFT_TEMPLATE_STATS.md").write_text("# SOFT TEMPLATE STATS (no extra fitting)\n\nBuild %s\n\n" % now() +
        "\n".join(f"- {k}: {v}" for k, v in stats.items()) +
        f"\n\n**Verdict: {status}.** PF {stats['pf']} on n={len(good)} ({moments} independent moments) — promising direction, far too small to trust. Not REJECT (PF>=1, appears in {len(wins)} windows), not RESEARCH_CANDIDATE (n far too small).\n", encoding="utf-8")

    # console + final
    print(f"good cross-confirmed markdown shorts: n={len(good)} ({moments} moments), windows={wins}, exch={exs}")
    print(f"  outcomes: W{W}/L{L}/TO{TO} hit2 {stats['hit2_rate']}% PF {stats['pf']} -> {status}")
    print("window map:")
    for r in bm: print(f"  {r['window_id']}: good {r['good_zones']} bad_conf {r['bad_confirmed_zones']} disagree {r['disagreement_zones']}")
    print("good vs bad medians (key):")
    for f in ("initiative_control", "effort_vs_result", "cvd_delta_60m", "taker_imb_30m", "dist_from_recent_low_pct"):
        print(f"  {f}: win {groups['GOOD_CONFIRMED_WINNERS'].get('med_'+f)} | conf_lose {groups['BAD_CONFIRMED_LOSERS'].get('med_'+f)} | disagree_lose {groups['DISAGREEMENT_LOSERS'].get('med_'+f)}")
    print("GOOD_ZONE_SIMILARITY:", sim, "| SOFT_TEMPLATE_STATUS:", status)
    return 0


if __name__ == "__main__":
    sys.exit(main())
