"""A3 — build OKX May feature table (engine scores + L2 + regime + sim + normalized), no Tardis.

Reuses the proven pipeline (binance_10d_diag + binance_oos_features_rs) repointed to OKX May paths.
OKX amount = CONTRACTS (March-compatible) so absolute March thresholds apply directly.
Also emits amount_btc (=*0.01) and usd-notional context fields where useful.
Gates on engine zones present in reports/okx-may/BTC-USDT-SWAP_<date>/zones.json.
"""
from __future__ import annotations
import json, sys, time, importlib.util
from collections import defaultdict
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "package.json").exists() and (p / "scripts").exists())
BLIVE = ROOT / "scripts/binance-live"
SCAL = ROOT / "scripts/strategy-calibration"
sys.path.insert(0, str(BLIVE)); sys.path.insert(0, str(SCAL))
import binance_oos_features_rs as B
from canonical_ledger import build_buckets_from_trades_csv
spec = importlib.util.spec_from_file_location("b10d", str(BLIVE / "binance_10d_diag.py"))
b10d = importlib.util.module_from_spec(spec); spec.loader.exec_module(b10d)

DATA = ROOT / "data/okx-historical/BTC-USDT-SWAP"
ZONES = ROOT / "reports/okx-may"
OUT = ROOT / "reports/okx-may"
CACHE = OUT / "OKX_2026_05_21_30_FEATURE_CACHE.json"
DATES = [f"2026-05-{d:02d}" for d in range(21, 31)]
OKX_CTVAL = 0.01

# repoint shared modules to OKX May
B.TARDIS = DATA; B.DATES = DATES
b10d.TARDIS = DATA
b10d.L2CACHE_DIR = OUT / "_l2cache_okxmay"; b10d.L2CACHE_DIR.mkdir(parents=True, exist_ok=True)


def load_zones():
    zs = []
    for d in DATES:
        p = ZONES / f"BTC-USDT-SWAP_{d}" / "zones.json"
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
        print("cache exists; delete to rebuild", file=sys.stderr); return 0
    have = [d for d in DATES if (ZONES / f"BTC-USDT-SWAP_{d}" / "zones.json").exists()]
    print(f"zone days present: {have}", file=sys.stderr)
    if len(have) < 5:
        print("WAITING: <5 engine days present", file=sys.stderr); return 2
    zones = load_zones()
    print(f"confirmed zones: {len(zones)}", file=sys.stderr)
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
    print("[L2 extended]", file=sys.stderr)
    for d in DATES:
        t0 = time.time(); l2 = b10d.l2_extended_for_day(d, by_date.get(d, []))
        for z in zones:
            if z["_date"] == d: z.update(l2.get(z["id"], {}))
        print(f"  {d}: L2 {time.time()-t0:.0f}s", file=sys.stderr)
    for z in zones:
        z["funding_rate_at_signal"] = None  # OKX May open data: no funding stream
        z["explainable_score"] = B.explainable_score(z)
        # USD-notional context for the supp/opp net flow (contracts -> BTC -> USD)
        ref = z.get("referencePrice") or (z.get("zoneLow") and z.get("zoneHigh") and (z["zoneLow"]+z["zoneHigh"])/2)
        sf = z.get("dl2_supp_minus_opp_net_flow_15m")
        z["supp_opp_15m_btc"] = round(sf * OKX_CTVAL, 4) if isinstance(sf, (int, float)) else None
        z["supp_opp_15m_usd"] = round(sf * OKX_CTVAL * ref, 1) if (isinstance(sf, (int, float)) and ref) else None
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
    zs = sorted(zones, key=lambda z: z["confirmedTs"]); psc = []
    for z in zs:
        z["uniq_score_pctile_vs_prior"] = b10d.pctile(sorted(psc), z["explainable_score"]) if psc else None
        psc.append(z["explainable_score"])
    for z in zones:
        for k in ("reasons", "targets", "scores"): z.pop(k, None)
    CACHE.write_text(json.dumps(zones, default=str, indent=0), encoding="utf-8")
    traded = sum(1 for z in zones if z.get("sim_outcome")); good = sum(1 for z in zones if z.get("sim_label") == "GOOD")
    print(f"[done] {len(zones)} zones, traded {traded}, GOOD {good} -> {CACHE.name}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
