"""A — recompute Binance L2 features on the FIXED v3 book (old caches invalid). No Tardis.

Mirrors okx_may_feature_build but for Binance: BTC units, reports/binance-live zones, funding present.
Fresh L2 cache dir so the corrected pure-diff book is re-streamed. Adds no-exit 24h MFE/MAE (strong labels).
"""
from __future__ import annotations
import json, sys, time, importlib.util, bisect
from collections import defaultdict
from pathlib import Path

ROOT = Path("C:/Users/gibilev/orderflow-research")
BLIVE = ROOT / "scripts/binance-live"
SCAL = ROOT / "scripts/strategy-calibration"
sys.path.insert(0, str(BLIVE)); sys.path.insert(0, str(SCAL))
import binance_oos_features_rs as B
from canonical_ledger import build_buckets_from_trades_csv
spec = importlib.util.spec_from_file_location("b10d", str(BLIVE / "binance_10d_diag.py"))
b10d = importlib.util.module_from_spec(spec); spec.loader.exec_module(b10d)

DATA = ROOT / "data/binance-historical/BTCUSDT"
ZONES = ROOT / "reports/binance-live"
OUT = ROOT / "reports/binance-oos"
CACHE = OUT / "BINANCE_10D_FIXED_L2_FEATURE_CACHE.json"
DATES = [f"2026-05-{d:02d}" for d in range(21, 31)]

B.TARDIS = DATA; B.DATES = DATES
b10d.TARDIS = DATA
b10d.L2CACHE_DIR = OUT / "_l2cache_fixed"; b10d.L2CACHE_DIR.mkdir(parents=True, exist_ok=True)


def load_zones():
    zs = []
    for d in DATES:
        p = ZONES / f"BTCUSDT_{d}" / "zones.json"
        if not p.exists(): continue
        obj = json.loads(p.read_text(encoding="utf-8"))
        arr = obj if isinstance(obj, list) else obj.get("zones", [])
        for z in arr:
            if z.get("confirmedTs") is None: continue
            z["_date"] = d
            sc = z.get("scores") or {}
            z["eng_absorption"] = sc.get("absorptionScore"); z["eng_void"] = sc.get("liquidityVoidScore")
            z["eng_ofi"] = sc.get("ofiScore"); z["eng_refill"] = sc.get("refillScore"); z["eng_trigger"] = sc.get("triggerScore")
            zs.append(z)
    return zs


def main():
    if CACHE.exists():
        print("fixed cache exists; delete to rebuild", file=sys.stderr); return 0
    zones = load_zones()
    print(f"Binance confirmed zones: {len(zones)}", file=sys.stderr)
    opp = B.opp_dir_counts(zones)
    bcache = {}
    for d in DATES:
        p = DATA / d / "trades.csv.gz"
        if p.exists(): bcache[d] = build_buckets_from_trades_csv(p)
    gb = []
    for d in DATES: gb += bcache.get(d, [])
    gb.sort(key=lambda b: b.sec); gsec = [b.sec for b in gb]
    print(f"global buckets {len(gb)}", file=sys.stderr)
    for z in zones:
        z.update(B.trades_features(z, bcache.get(z["_date"], [])))
        hr = (z["confirmedTs"] // 1000 % 86400) // 3600; z["is_asia_session"] = 1 if hr < 7 else 0
        z["opp_dir_zones_active_60m"] = opp.get(z["id"], 0)
        z.update(b10d.regime_struct(z, gb, gsec))
    by_date = defaultdict(list)
    for z in zones:
        by_date[z["_date"]].append((z["confirmedTs"] // 1000, z["id"], z["direction"], z.get("zoneLow"), z.get("zoneHigh")))
    print("[trades aggression]", file=sys.stderr)
    for d in DATES:
        agg = b10d.trades_aggression_for_day(d, by_date.get(d, []))
        for z in zones:
            if z["_date"] == d: z.update(agg.get(z["id"], {}))
    print("[L2 extended on FIXED book]", file=sys.stderr)
    for d in DATES:
        t0 = time.time(); l2 = b10d.l2_extended_for_day(d, by_date.get(d, []))
        for z in zones:
            if z["_date"] == d: z.update(l2.get(z["id"], {}))
        print(f"  {d}: L2 {time.time()-t0:.0f}s", file=sys.stderr)
    for z in zones:
        z["funding_rate_at_signal"] = B.funding_at(z["_date"], z["confirmedTs"] // 1000)
        z["explainable_score"] = B.explainable_score(z)
        sf = z.get("dl2_supp_minus_opp_net_flow_15m")
        ref = z.get("referencePrice") or (z.get("zoneLow") and z.get("zoneHigh") and (z["zoneLow"] + z["zoneHigh"]) / 2)
        z["supp_opp_15m_usd"] = round(sf * ref, 1) if (isinstance(sf, (int, float)) and ref) else None  # Binance amount already BTC
    # canonical sim + labels
    for z in zones:
        sim = B.sim_trade(z, bcache)
        if sim is None:
            z.update({"sim_label": "NO_TRADE", "sim_outcome": None, "sim_pnl_after_cost": None,
                      "sim_pnl_pre_cost": None, "sim_mfe_pct": None, "sim_mae_pct": None,
                      "sim_exit_reason": None, "sim_entry_price": None, "sim_correct_direction": None}); continue
        z["sim_outcome"] = sim["outcome"]; z["sim_pnl_after_cost"] = sim["pnl_after_cost"]
        z["sim_pnl_pre_cost"] = sim["pnl_pre_cost"]; z["sim_mfe_pct"] = sim["mfe_pct"]; z["sim_mae_pct"] = sim["mae_pct"]
        z["sim_exit_reason"] = sim["exit_reason"]; z["sim_entry_price"] = sim["entry_price"]
        z["sim_correct_direction"] = 1 if (sim["mfe_pct"] or 0) >= (sim["mae_pct"] or 0) else 0
        z["sim_label"] = "GOOD" if sim["outcome"] == "WIN" else ("NOISE" if sim["outcome"] == "LOSS" else
                         ("MID" if (sim["pnl_pre_cost"] or 0) > 0 else "NOISE"))
    # no-exit 24h forward MFE/MAE (strong-zone labels)
    secs = [b.sec for b in gb]
    for z in zones:
        if not z.get("sim_entry_price"):
            z["true_mfe"] = None; z["true_mae"] = None; continue
        entry = z["sim_entry_price"]; start = z["confirmedTs"] // 1000; dirn = z["direction"]
        i = bisect.bisect_left(secs, start); j = bisect.bisect_right(secs, start + 24 * 3600); seg = gb[i:j]
        if not seg:
            z["true_mfe"] = None; z["true_mae"] = None; continue
        if dirn == "LONG":
            z["true_mfe"] = round(max((b.high - entry) / entry * 100 for b in seg), 3)
            z["true_mae"] = round(min((b.low - entry) / entry * 100 for b in seg), 3)
        else:
            z["true_mfe"] = round(max((entry - b.low) / entry * 100 for b in seg), 3)
            z["true_mae"] = round(min((entry - b.high) / entry * 100 for b in seg), 3)
    zs = sorted(zones, key=lambda z: z["confirmedTs"]); psc = []
    for z in zs:
        z["uniq_score_pctile_vs_prior"] = b10d.pctile(sorted(psc), z["explainable_score"]) if psc else None
        psc.append(z["explainable_score"])
    for z in zones:
        for k in ("reasons", "targets", "scores"): z.pop(k, None)
    CACHE.write_text(json.dumps(zones, default=str, indent=0), encoding="utf-8")
    import csv
    keys = ["id", "_date", "direction", "zoneType", "sim_label", "sim_outcome", "sim_pnl_after_cost",
            "true_mfe", "true_mae", "explainable_score", "dist_to_recent_swing_high_pct",
            "dl2_supp_minus_opp_net_flow_15m", "dl2_microprice_aligned_delta_5m_bps",
            "ms_thin_path_score", "ms_large_walls_on_path", "eng_ofi", "eng_void", "eng_refill",
            "supportive_taker_imb_15m", "taker_imbalance_15m", "spread_now_bps", "book_entropy_top25",
            "reclaim_zoneMid_preconfirm", "regime_1d", "uniq_score_pctile_vs_prior", "funding_rate_at_signal"]
    with (OUT / "BINANCE_10D_FIXED_L2_FEATURE_TABLE.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys, extrasaction="ignore"); w.writeheader()
        for z in zones: w.writerow(z)
    traded = sum(1 for z in zones if z.get("sim_outcome")); good = sum(1 for z in zones if z.get("sim_label") == "GOOD")
    h2 = sum(1 for z in zones if isinstance(z.get("true_mfe"), (int, float)) and z["true_mfe"] >= 2)
    h25 = sum(1 for z in zones if isinstance(z.get("true_mfe"), (int, float)) and z["true_mfe"] >= 2.5)
    h3 = sum(1 for z in zones if isinstance(z.get("true_mfe"), (int, float)) and z["true_mfe"] >= 3)
    print(f"[done] {len(zones)} zones, traded {traded}, GOOD {good}; true MFE hit2={h2} hit2.5={h25} hit3={h3} -> {CACHE.name}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
