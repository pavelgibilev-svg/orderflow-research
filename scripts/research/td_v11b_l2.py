"""v11b — L2-AWARE ABSORPTION VALIDATION (diagnostic, not optimization, not production).

Same v11 forward labels (unchanged). Rebuild causal evidence from L2: (A) L2-LIGHT = cached di+spread (3 v2okx down
windows); (B) L2-FULL = reconstructed book depth/refill/microprice (5 okx windows, see td_v11b_build_l2). Test whether
L2 evidence separates ACTIVE_MARKDOWN vs SELL_PRESSURE_ABSORBED WITHIN background (no Simpson's hiding). Compare
trades-only vs L2 vs combined. No PnL, no tuning, no td_l.
"""
from __future__ import annotations
import csv, json, sys, datetime as dt
from collections import defaultdict
from pathlib import Path

ROOT = Path("C:/Users/gibilev/orderflow-research")
sys.path.insert(0, str(ROOT / "scripts/research"))
import td_v4_regime as V4
import td_v5_gate as V5
import td_v8_entry as V8
import td_v9_phase as V9
import td_v11_absorption as V11          # reuse forward_label, background, evidence(trades), auc, clip01
OKXH = ROOT / "data/okx-historical/BTC-USDT-SWAP"
CACHE = ROOT / "reports/l2_aware_absorption_validation_v11b/_l2cache"
OUT = ROOT / "reports/l2_aware_absorption_validation_v11b"
PRIMARY = 60
clip01 = V11.clip01; auc = V11.auc


def now(): return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
def mean(xs): return round(sum(xs) / len(xs), 4) if xs else None


def load_l2(wid):
    f = CACHE / f"{wid}.json"
    if not f.exists(): return None
    d = json.load(f.open()); keys = d["keys"]
    return {int(k): dict(zip(keys, v)) for k, v in d["feats"].items()}


def l2_full_scores(l2arr, cvd, t):
    """causal L2-FULL markdown-likelihood blocks from reconstructed book (higher=continuation; absorption=low). None if no coverage."""
    cur = l2arr[t]
    if cur is None: return None
    base = [l2arr[i] for i in range(t - 8, t - 2) if l2arr[i] is not None]
    if len(base) < 3: return None
    bd50_base = sum(b["bid_d50"] for b in base) / len(base)
    bd25_base = sum(b["bid_d25"] for b in base) / len(base)
    cvd15 = cvd[t] - cvd[t - 15]
    refill = cur["bid_d50"] / bd50_base if bd50_base else 1.0
    defense = cur["bid_d25"] / bd25_base if bd25_base else 1.0
    band_imb = (cur["bid_d50"] - cur["ask_d50"]) / (cur["bid_d50"] + cur["ask_d50"]) if (cur["bid_d50"] + cur["ask_d50"]) else 0.0
    recent = [l2arr[i] for i in range(t - 5, t + 1) if l2arr[i] is not None]
    mi = sum(r["top_imb"] for r in recent) / len(recent)
    mo = sum(r["micro_off_bps"] for r in recent) / len(recent)
    spr_base = sorted(b["spread_bps"] for b in base)[len(base) // 2]
    widen = cur["spread_bps"] / spr_base if spr_base else 1.0
    s1 = clip01((1.1 - refill) / 0.4)                       # BID_REFILL: refilled -> absorbed -> low
    s2 = clip01((1.1 - defense) / 0.4)                      # BID_DEFENSE_NEAR_LOW
    s3 = clip01(0.5 - band_imb)                             # BOOK_THINNESS_BELOW: bids thin vs asks -> markdown
    s4 = clip01(0.5 - mi + (0.05 if mo < 0 else -0.05))     # MICROPRICE_AND_IMBALANCE_CONTROL
    s5 = clip01((widen - 1) / 1.0) * 0.5 + clip01(1 - refill) * 0.5   # SPREAD_AND_BOOK_STABILITY (risk)
    s6 = s1 if cvd15 < 0 else 0.5                           # PRICE_RESPONSE_TO_L2_PRESSURE (refill gated by selling)
    combined = round((s1 + s2 + s3 + s4 + s6) / 5.0, 4)
    return {"BID_REFILL": round(s1, 4), "BID_DEFENSE_NEAR_LOW": round(s2, 4), "BOOK_THINNESS_BELOW": round(s3, 4),
            "MICROPRICE_IMBALANCE": round(s4, 4), "SPREAD_STABILITY": round(s5, 4), "PRICE_RESPONSE_L2": round(s6, 4),
            "L2FULL_COMBINED": combined}


def l2_light_scores(di, spread, t):
    """causal L2-LIGHT blocks from cached di (top-of-book depth imbalance) + spread. None if missing."""
    if di[t] is None: return None
    win = [di[i] for i in range(t - 10, t + 1) if di[i] is not None]
    if len(win) < 6: return None
    lvl = di[t]; persist = sum(win) / len(win); trend = di[t] - win[0]
    spr = spread[t] if spread[t] is not None else None
    spr_base = [spread[i] for i in range(t - 10, t) if spread[i] is not None]
    widen = (spr / (sorted(spr_base)[len(spr_base) // 2])) if (spr and spr_base) else 1.0
    # orientation: di<0 (ask-heavy) assumed downward lean -> markdown-like high. (AUC magnitude is what matters.)
    s1 = clip01(0.5 - lvl)                                  # L2L_IMBALANCE_LEVEL
    s2 = clip01(0.5 - persist)                              # L2L_IMBALANCE_PERSIST
    s3 = clip01(0.5 - trend * 2.0)                          # L2L_IMBALANCE_TREND (falling di -> more sell lean)
    s4 = clip01((widen - 1) / 1.0)                          # L2L_SPREAD widening
    combined = round((s1 + s2 + s3) / 3.0, 4)
    return {"L2L_IMBALANCE_LEVEL": round(s1, 4), "L2L_IMBALANCE_PERSIST": round(s2, 4),
            "L2L_IMBALANCE_TREND": round(s3, 4), "L2L_SPREAD": round(s4, 4), "L2LIGHT_COMBINED": combined}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    series = {wid: V5.get_series(wid) for wid in V4.WINDOWS}
    P = {wid: V8.prep(S) for wid, S in series.items()}
    l2full = {wid: load_l2(wid) for wid in series}
    for wid in series: print(f"{wid}: prep ok, L2full={'Y' if l2full[wid] else 'N'}", flush=True)

    # ---- Step 1 data audit + cache audit ----
    audit = []
    for wid in series:
        reg, src, days = V4.WINDOWS[wid]
        S = series[wid]
        ms = [r["m"] for r in S]; dates = sorted({dt.datetime.utcfromtimestamp(m * 60).strftime("%Y-%m-%d") for m in ms})
        have_daily = [d for d in dates if (OKXH / d / "incremental_book_L2.csv.gz").exists()]
        di_n = sum(1 for r in S if r.get("di") is not None)
        l2 = l2full[wid]; cov = round(100 * len(l2) / len(S), 1) if l2 else 0.0
        audit.append({"window": wid, "venue": "OKX", "symbol": "BTC-USDT-SWAP", "background": reg,
                      "date_range": f"{dates[0]}..{dates[-1]}", "src": src,
                      "daily_incremental_book_L2_days": f"{len(have_daily)}/{len(dates)}",
                      "cached_di_minutes": di_n, "l2full_cache_minutes": (len(l2) if l2 else 0), "l2full_coverage_pct": cov,
                      "v11_used_L2": "NO (trades-only)",
                      "usable_L2_light": "YES" if di_n > 0 else "NO",
                      "usable_L2_full": "YES" if (l2 and cov > 50) else ("PENDING_BUILD" if len(have_daily) > 0 else "NO")})
    _wcsv(OUT / "V11B_L2_DATA_AUDIT.csv", audit)

    # ---- Steps 2-4: candidates + forward labels + trades/L2 evidence ----
    cands = []
    for wid, S in series.items():
        Pi = P[wid]; mid = Pi["mid"]; cvd = Pi["cvd"]; vwap = Pi["vwap"]; lo = Pi["lo"]; n = Pi["n"]
        di = [r.get("di") for r in S]; spread = [r.get("spread") for r in S]
        l2 = l2full[wid]
        l2arr = [l2.get(S[i]["m"]) if l2 else None for i in range(n)]
        for t in range(360, n - (PRIMARY + 5)):
            cvd30 = cvd[t] - cvd[t - 30]; pv = (mid[t] - vwap[t]) / vwap[t] * 100
            sv30 = sum(S[i]["sv"] for i in range(t - 30, t)); bv30 = sum(S[i]["bv"] for i in range(t - 30, t))
            sell_frac = sv30 / (sv30 + bv30) if (sv30 + bv30) > 0 else 0.5
            breakdown = min(lo[t - 5:t + 1]) < min(mid[t - 60:t])
            if not (cvd30 < 0 and (pv < 0.10 or sell_frac >= 0.55 or breakdown)):
                continue
            lab = V11.forward_label(Pi, t, PRIMARY)
            tr = V11.evidence(S, Pi, t)["COMBINED"]
            lf = l2_full_scores(l2arr, cvd, t) if l2 else None
            ll = l2_light_scores(di, spread, t)
            row = {"wid": wid, "background": V11.background(Pi, t), "label": lab, "TRADES_COMBINED": tr}
            if lf: row.update(lf)
            if ll: row.update(ll)
            cands.append(row)
    mk = [c for c in cands if c["label"] == "ACTIVE_MARKDOWN"]; ab = [c for c in cands if c["label"] == "SELL_PRESSURE_ABSORBED"]
    print(f"candidates {len(cands)} | markdown {len(mk)} absorbed {len(ab)}", flush=True)

    FULL_BLOCKS = ["BID_REFILL", "BID_DEFENSE_NEAR_LOW", "BOOK_THINNESS_BELOW", "MICROPRICE_IMBALANCE", "SPREAD_STABILITY", "PRICE_RESPONSE_L2", "L2FULL_COMBINED"]
    LIGHT_BLOCKS = ["L2L_IMBALANCE_LEVEL", "L2L_IMBALANCE_PERSIST", "L2L_IMBALANCE_TREND", "L2L_SPREAD", "L2LIGHT_COMBINED"]

    def auc_for(block, subset=None):
        m = [c[block] for c in mk if block in c and (subset is None or c["background"] in subset)]
        a = [c[block] for c in ab if block in c and (subset is None or c["background"] in subset)]
        return auc(m, a), len(m), len(a)

    # ---- Step 5: evidence scorecard (overall) + trades vs L2 comparison ----
    ev_rows = []
    for fam, blocks in (("TRADES", ["TRADES_COMBINED"]), ("L2_FULL", FULL_BLOCKS), ("L2_LIGHT", LIGHT_BLOCKS)):
        for blk in blocks:
            a, nm, na = auc_for(blk)
            ev_rows.append({"family": fam, "block": blk, "auc_overall": a, "n_markdown": nm, "n_absorbed": na,
                            "mean_md": mean([c[blk] for c in mk if blk in c]), "mean_ab": mean([c[blk] for c in ab if blk in c])})
    _wcsv(OUT / "V11B_L2_EVIDENCE_SCORECARD.csv", ev_rows)

    # ---- within-background separation (the decisive test) ----
    wb_rows = []
    for bg in ("TREND_DOWN", "RANGE", "TREND_UP", "LOW_VOL"):
        for blk in ("TRADES_COMBINED", "L2FULL_COMBINED", "L2LIGHT_COMBINED"):
            a, nm, na = auc_for(blk, {bg})
            wb_rows.append({"background": bg, "block": blk, "auc": a, "n_markdown": nm, "n_absorbed": na})
    _wcsv(OUT / "V11B_WITHIN_BACKGROUND_SEPARATION.csv", wb_rows)

    # combined trades+L2 (where both present)
    cmp_rows = []
    for label, blkpair in (("TRADES_only", ("TRADES_COMBINED", None)),
                           ("L2FULL_only", ("L2FULL_COMBINED", None)),
                           ("L2LIGHT_only", ("L2LIGHT_COMBINED", None)),
                           ("TRADES+L2FULL", ("TRADES_COMBINED", "L2FULL_COMBINED")),
                           ("TRADES+L2LIGHT", ("TRADES_COMBINED", "L2LIGHT_COMBINED"))):
        b1, b2 = blkpair
        def comp(c):
            if b2 is None: return c.get(b1)
            if b1 in c and b2 in c: return (c[b1] + c[b2]) / 2.0
            return None
        for bg in ("ALL", "TREND_DOWN", "RANGE"):
            sub = None if bg == "ALL" else {bg}
            m = [comp(c) for c in mk if (sub is None or c["background"] in sub) and comp(c) is not None]
            a = [comp(c) for c in ab if (sub is None or c["background"] in sub) and comp(c) is not None]
            cmp_rows.append({"model": label, "scope": bg, "auc": auc(m, a), "n_markdown": len(m), "n_absorbed": len(a)})
    _wcsv(OUT / "V11B_TRADES_VS_L2_COMPARISON.csv", cmp_rows)

    # ---- per-window breakdown ----
    pw = defaultdict(lambda: defaultdict(int))
    for c in cands: pw[c["wid"]][c["label"]] += 1
    pw_rows = []
    for wid in series:
        for blk in ("TRADES_COMBINED", "L2FULL_COMBINED", "L2LIGHT_COMBINED"):
            m = [c[blk] for c in mk if c["wid"] == wid and blk in c]; a = [c[blk] for c in ab if c["wid"] == wid and blk in c]
            if m and a:
                pw_rows.append({"window": wid, "background": V4.WINDOWS[wid][0], "block": blk, "auc": auc(m, a), "n_markdown": len(m), "n_absorbed": len(a)})
    _wcsv(OUT / "V11B_PER_WINDOW_BREAKDOWN.csv", pw_rows)

    # ---- decision ----
    def wb(blk, bg):
        r = next((x for x in wb_rows if x["block"] == blk and x["background"] == bg), None)
        return (r["auc"], r["n_markdown"], r["n_absorbed"]) if r else (None, 0, 0)
    td_full = wb("L2FULL_COMBINED", "TREND_DOWN"); td_light = wb("L2LIGHT_COMBINED", "TREND_DOWN")
    rg_full = wb("L2FULL_COMBINED", "RANGE"); td_trades = wb("TRADES_COMBINED", "TREND_DOWN")
    def sep(x): return x[0] is not None and abs(x[0] - 0.5) >= 0.10 and min(x[1], x[2]) >= 80
    def weak(x): return x[0] is not None and abs(x[0] - 0.5) >= 0.06 and min(x[1], x[2]) >= 50
    any_full_built = any(l2full[w] for w in series)
    if not any_full_built and not any((series[w] and any(r.get("di") is not None for r in series[w])) for w in series):
        status = "DATA_INTEGRATION_BLOCKED"
    elif sep(td_full) or sep(rg_full) or sep(td_light):
        status = "L2_ABSORPTION_EVIDENCE_PROMISING"
    elif weak(td_full) or weak(rg_full) or weak(td_light):
        status = "L2_ABSORPTION_EVIDENCE_NEED_MORE_DATA"
    else:
        status = "L2_ABSORPTION_EVIDENCE_REJECTED"

    _wmd(OUT / "V11B_L2_FEATURE_DEFINITIONS.md", "V11B L2 FEATURE DEFINITIONS (causal, <=t; higher=markdown-like)",
         ["L2-FULL (reconstructed book, per-minute, within +-0.5%/0.25% bands):",
          "- BID_REFILL: bid_d50[t] vs mean(bid_d50[t-8..t-3]); refilled bids under selling -> absorption -> low.",
          "- BID_DEFENSE_NEAR_LOW: bid_d25 (close-in) recovery vs baseline.",
          "- BOOK_THINNESS_BELOW: band imbalance (bid_d50-ask_d50)/sum; bids thin vs asks -> markdown.",
          "- MICROPRICE_IMBALANCE: 5m mean top imbalance + microprice offset sign -> seller control.",
          "- SPREAD_STABILITY: spread widening + depth collapse (risk/instability).",
          "- PRICE_RESPONSE_L2: refill score gated by actual selling (cvd_15<0).",
          "- L2FULL_COMBINED = mean(REFILL,DEFENSE,THINNESS,MICROPRICE,PRICE_RESPONSE).", "",
          "L2-LIGHT (cached di top-of-book depth imbalance + spread; the only L2 the 3 v2okx down windows have):",
          "- L2L_IMBALANCE_LEVEL / _PERSIST(10m mean) / _TREND(10m change) / _SPREAD(widening).",
          "- L2LIGHT_COMBINED = mean(LEVEL,PERSIST,TREND). Orientation assumed di<0=down-lean; AUC MAGNITUDE (|AUC-0.5|) is the separation, sign is orientation.", "",
          "All causal: book state and trades up to minute t only. Forward labels UNCHANGED from v11."])
    cov_lines = [f"- {a['window']} [{a['background']}]: daily_L2 {a['daily_incremental_book_L2_days']} · di_min {a['cached_di_minutes']} · L2full_cov {a['l2full_coverage_pct']}% · L2light {a['usable_L2_light']} · L2full {a['usable_L2_full']}" for a in audit]
    _wmd(OUT / "V11B_CACHE_AUDIT.md", "V11B CACHE AUDIT",
         ["v11 used the per-minute cache TRADES-ONLY (di/spread were None for okx-historical windows and unused even where populated).",
          "L2 now integrated two ways: L2-LIGHT (cached di+spread, 3 v2okx down windows) and L2-FULL (reconstructed from incremental_book_L2, okx-native windows).", ""] + cov_lines)
    _wmd(OUT / "V11B_SIMSPON_PARADOX_CHECK.md", "V11B SIMPSON'S-PARADOX CHECK (within-background only)",
         ["Always report conditioned-by-background AUC. Overall AUC is NOT used for the verdict.", "",
          f"- TREND_DOWN: TRADES {td_trades[0]} (n {td_trades[1]}/{td_trades[2]}) · L2_FULL {td_full[0]} (n {td_full[1]}/{td_full[2]}) · L2_LIGHT {td_light[0]} (n {td_light[1]}/{td_light[2]}).",
          f"- RANGE: L2_FULL {rg_full[0]} (n {rg_full[1]}/{rg_full[2]}).", "",
          "Reminder: v11's overall 0.624 collapsed to 0.500/0.508 within TREND_DOWN/RANGE. L2 must beat THAT to matter."])
    _wmd(OUT / "V11B_FINAL_DECISION.md", "V11B FINAL DECISION (skeptical)",
         [f"**STATUS: {status}**", "",
          "## v11 scope correction",
          "- v11's REJECT applies to TRADES-ONLY features. v11 never used L2 (di/spread None for okx windows; book never reconstructed).", "",
          "## Within-background L2 separation (the only test that counts)",
          f"- TREND_DOWN: trades {td_trades[0]} | **L2_FULL {td_full[0]}** (n {td_full[1]}/{td_full[2]}, DOWN_0327 only) | **L2_LIGHT {td_light[0]}** (n {td_light[1]}/{td_light[2]}, 3 down windows).",
          f"- RANGE: **L2_FULL {rg_full[0]}** (n {rg_full[1]}/{rg_full[2]}).", "",
          "## Reading",
          "- L2 'matters' only if within-TREND_DOWN/RANGE |AUC-0.5| is materially above the trades-only ~0.50 floor.",
          "- L2_FULL within-TREND_DOWN rests on ONE window (DOWN_0327) — single-window caveat applies; not freezable.",
          "- In-sample, OKX-only. No PnL, no tuning, no td_l. Absorption blocker is alive ONLY if a block clears the bar above."])
    nb = {"L2_ABSORPTION_EVIDENCE_PROMISING": "extend L2-FULL to more down/range windows (build remaining caches) + OOS, THEN propose v12 L2 blocker",
          "L2_ABSORPTION_EVIDENCE_NEED_MORE_DATA": "more L2-FULL window diversity (esp. >1 TREND_DOWN with book) before any blocker",
          "L2_ABSORPTION_EVIDENCE_REJECTED": "L2 evidence also fails within-background; absorption not separable here — collect liquidations/OI or accept td_s stays phase-gated",
          "DATA_INTEGRATION_BLOCKED": "fix L2 integration"}[status]
    _wmd(OUT / "V11B_NEXT_BRANCH_RECOMMENDATION.md", "V11B NEXT BRANCH RECOMMENDATION",
         [f"**Recommended next: {nb}.**", "",
          "- Still NO td_l: a long module needs the absorption boundary validated within-background AND OOS.",
          "- L2-FULL within-TREND_DOWN currently = one window (DOWN_0327). Priority: reconstruct book for >=2 more TREND_DOWN windows (Nov/Jan/Apr have no daily book; need OKX-native down days with incremental_book_L2, e.g. other March/May down stretches).",
          "- Liquidations + OI remain unintegrated and are the natural next microstructure layer for seller-exhaustion.",
          "- Keep GATE_6A/6E/8A frozen; forward labels unchanged."])
    _wmd(OUT / "V11B_STATUS.md", "V11B STATUS",
         [f"- STATUS: **{status}**",
          "- v11 corrected scope: TRADES_ONLY_FEATURES_REJECTED (v11 never used L2).",
          f"- within-TREND_DOWN AUC: trades {td_trades[0]} | L2_FULL {td_full[0]} (n {td_full[1]}/{td_full[2]}) | L2_LIGHT {td_light[0]} (n {td_light[1]}/{td_light[2]})",
          f"- within-RANGE AUC: L2_FULL {rg_full[0]} (n {rg_full[1]}/{rg_full[2]})",
          f"- L2-FULL caches built: {[w for w in series if l2full[w]]}",
          "- in-sample, OKX-only, L2-FULL within-down = single window. PRODUCTION: NO. No td_l."])

    print(f"candidates {len(cands)} mk {len(mk)} ab {len(ab)}")
    print("within-background AUC:")
    for r in wb_rows:
        if r["auc"] is not None: print(f"  {r['background']:<11} {r['block']:<18} AUC {r['auc']} (n {r['n_markdown']}/{r['n_absorbed']})")
    print("trades vs L2 (scope):")
    for r in cmp_rows:
        if r["auc"] is not None: print(f"  {r['model']:<16} {r['scope']:<10} AUC {r['auc']} (n {r['n_markdown']}/{r['n_absorbed']})")
    print(f"STATUS {status}")
    return 0


def _wcsv(path, rows):
    if not rows: path.write_text("", encoding="utf-8"); return
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys, extrasaction="ignore"); w.writeheader()
        for r in rows: w.writerow(r)
def _wmd(path, title, body):
    path.write_text(f"# {title}\n\nBuild {now()} · L2-aware absorption validation v11b · skeptical, not production.\n\n" + "\n".join(body) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
