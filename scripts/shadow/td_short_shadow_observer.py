"""TD-SHORT SHADOW OBSERVER (frozen, causal, no Telegram, no trading, no production).

Decision uses ONLY features available at/before confirmedTs. Writes a decision log with NO
outcome/future fields. Outcomes are added later by the SEPARATE td_short_outcome_updater.py.

Rules are FROZEN (do not tune):
  MANDATORY: regime==TREND_DOWN, direction==SHORT, prior_move_60m_pct<0, no buyer_absorption.
  CONFLUENCE (>=2 of): rejection_proof, taker_sell, microprice_down, thin_bid_path.
  SELECTION: first-eligible, max 2/day/venue, cluster cooldown 120m / 0.5% band.
  HYBRID = main decision. M4_THIN_ONLY (thin_bid_path alone) logged as booster/alternative.
"""
from __future__ import annotations
import csv, json, sys, datetime as dt
from collections import defaultdict
from pathlib import Path

ROOT = Path("C:/Users/gibilev/orderflow-research")
sys.path.insert(0, str(ROOT / "scripts/strategy-calibration"))
import venue_norm_research as V

OUT = ROOT / "reports/shadow"; OUT.mkdir(parents=True, exist_ok=True)

# ---- FROZEN thresholds ----
TREND_PCT = 2.5          # |prior_move_1d| > 2.5% => trend
OFI_MAX = 0.2            # buyer absorption if eng_ofi > 0.2
TAKER_MIN = -0.1        # buyer absorption if supportive_taker_imb_15m < -0.1
VOID_MIN = 0.5          # thin path if eng_void >= 0.5 and no large walls
CONF_MIN = 2
COOLDOWN_MIN = 120
BAND_PCT = 0.5
TP_PCT = 2.0; SL_PCT = 1.5


def num(x): return x if isinstance(x, (int, float)) else None
def iso(ms): return dt.datetime.fromtimestamp(ms / 1000, tz=dt.timezone.utc).isoformat(timespec="seconds") if ms else None


def regime(z):
    pm = num(z.get("prior_move_1d_pct"))
    if pm is None: return "RANGE"
    return "TREND_UP" if pm > TREND_PCT else ("TREND_DOWN" if pm < -TREND_PCT else "RANGE")


def buyer_absorption(z):
    o = num(z.get("eng_ofi")); ti = num(z.get("supportive_taker_imb_15m"))
    return (o is not None and o > OFI_MAX) or (ti is not None and ti < TAKER_MIN)


def conf_flags(z):
    return {
        "rejection_proof": z.get("reclaim_zoneMid_preconfirm") == 1,
        "taker_sell": (num(z.get("supportive_taker_imb_15m")) or -9) > 0,
        "microprice_down": (num(z.get("dl2_microprice_aligned_delta_5m_bps")) or -9) >= 0,
        "thin_bid_path": (z.get("ms_large_walls_on_path") in (0, None)) and (num(z.get("eng_void")) or 0) >= VOID_MIN,
    }


def hypo_entry(z):
    e = num(z.get("referencePrice"))
    if e: return e
    lo, hi = num(z.get("zoneLow")), num(z.get("zoneHigh"))
    return (lo + hi) / 2 if (lo and hi) else None


def evaluate(z):
    """Pure-causal evaluation (no cooldown). Returns dict of logged fields + mandatory/confluence + decisions."""
    reg = regime(z); d = z["direction"]; ba = buyer_absorption(z)
    cf = conf_flags(z); cc = sum(1 for v in cf.values() if v)
    pm60 = num(z.get("prior_move_60m_pct"))
    reasons = []
    if reg != "TREND_DOWN": reasons.append("not_TREND_DOWN")
    if d != "SHORT": reasons.append("not_SHORT")
    if pm60 is None or pm60 >= 0: reasons.append("prior_60m_not_negative")
    if ba: reasons.append("buyer_absorption")
    mandatory_pass = len(reasons) == 0
    if mandatory_pass and cc < CONF_MIN: reasons.append(f"confluence_lt_2({cc})")
    if mandatory_pass and not cf["thin_bid_path"] and num(z.get("ms_large_walls_on_path")) and z["ms_large_walls_on_path"] > 0:
        pass  # thick bid path is implicit via thin_bid_path flag; not a hard reject by itself
    hybrid = "HYBRID_PASS" if (mandatory_pass and cc >= CONF_MIN) else "HYBRID_REJECT"
    m4 = "M4_THIN_ONLY_PASS" if cf["thin_bid_path"] else "M4_THIN_ONLY_REJECT"
    e = hypo_entry(z)
    return {
        "zone_id": z.get("id"), "venue": z.get("_venue"), "symbol": z.get("symbol"), "date": z.get("_date"),
        "confirmedTs": z.get("confirmedTs"), "confirmed_iso": iso(z.get("confirmedTs")), "direction": d,
        "setup_type": z.get("zoneType"), "regime": reg, "prior_move_1d": num(z.get("prior_move_1d_pct")),
        "prior_move_60m_pct": pm60, "eng_ofi": num(z.get("eng_ofi")),
        "supportive_taker_imb_15m": num(z.get("supportive_taker_imb_15m")),
        "microprice_aligned_5m": num(z.get("dl2_microprice_aligned_delta_5m_bps")),
        "eng_void": num(z.get("eng_void")), "thin_path_score": num(z.get("ms_thin_path_score")),
        "large_walls": num(z.get("ms_large_walls_on_path")), "reclaim_zoneMid": z.get("reclaim_zoneMid_preconfirm"),
        "buyer_absorption": int(ba), "conf_rejection": int(cf["rejection_proof"]), "conf_taker_sell": int(cf["taker_sell"]),
        "conf_microprice": int(cf["microprice_down"]), "conf_thin": int(cf["thin_bid_path"]), "confluence_count": cc,
        "zoneLow": num(z.get("zoneLow")), "zoneHigh": num(z.get("zoneHigh")), "hypo_entry": round(e, 2) if e else None,
        "tp_2pct": round(e * (1 - TP_PCT / 100), 2) if e else None, "sl_1_5pct": round(e * (1 + SL_PCT / 100), 2) if e else None,
        "mandatory_pass": int(mandatory_pass), "reject_reasons": ";".join(reasons),
        "hybrid_decision": hybrid, "m4_thin_decision": m4,
    }


def run_decisions(zones):
    """Process zones with stateful cluster cooldown (per venue/day, chronological). Adds cluster/cooldown/final."""
    rows = []
    bykey = defaultdict(list)
    for z in zones: bykey[(z.get("_venue"), z.get("_date"))].append(z)
    for key in sorted(bykey, key=lambda k: (str(k[0]), str(k[1]))):
        taken = []
        for z in sorted(bykey[key], key=lambda x: x.get("confirmedTs") or 0):
            r = evaluate(z)
            e = r["hypo_entry"]
            r["cluster_id"] = f"{r['venue']}_{r['direction']}_{int(e // 100)}" if e else None
            # cooldown only matters if it would otherwise PASS
            cooldown_active = False
            if r["hybrid_decision"] == "HYBRID_PASS":
                if not V.cluster_cooldown_ok(z, taken, cooldown_min=COOLDOWN_MIN, band_pct=BAND_PCT):
                    cooldown_active = True
                elif sum(1 for t in taken if t["_date"] == z["_date"]) >= 2:
                    cooldown_active = True
            r["cooldown_state"] = "ACTIVE" if cooldown_active else "CLEAR"
            if r["hybrid_decision"] == "HYBRID_PASS" and not cooldown_active:
                r["final_shadow_decision"] = "ACCEPT"
                taken.append(z)
            else:
                if r["hybrid_decision"] == "HYBRID_PASS" and cooldown_active:
                    r["reject_reasons"] = (r["reject_reasons"] + ";duplicate_cluster_or_cooldown").strip(";")
                r["final_shadow_decision"] = "REJECT"
            rows.append(r)
    return rows


DECISION_FIELDS = ["zone_id", "venue", "symbol", "date", "confirmedTs", "confirmed_iso", "direction", "setup_type",
    "regime", "prior_move_1d", "prior_move_60m_pct", "eng_ofi", "supportive_taker_imb_15m", "microprice_aligned_5m",
    "eng_void", "thin_path_score", "large_walls", "reclaim_zoneMid", "buyer_absorption", "conf_rejection",
    "conf_taker_sell", "conf_microprice", "conf_thin", "confluence_count", "cluster_id", "cooldown_state",
    "zoneLow", "zoneHigh", "hypo_entry", "tp_2pct", "sl_1_5pct", "mandatory_pass", "reject_reasons",
    "hybrid_decision", "m4_thin_decision", "final_shadow_decision"]
# NOTE: no sim_outcome / true_mfe / pnl / hit_* here — outcomes are added by the separate updater.


def write_logs(rows):
    with (OUT / "TD_SHORT_SHADOW_DECISIONS.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=DECISION_FIELDS, extrasaction="ignore"); w.writeheader(); w.writerows(rows)
    with (OUT / "TD_SHORT_SHADOW_DECISIONS.jsonl").open("w", encoding="utf-8") as fh:
        for r in rows: fh.write(json.dumps({k: r.get(k) for k in DECISION_FIELDS}, default=str) + "\n")
    # daily summary
    byday = defaultdict(lambda: {"zones": 0, "candidates": 0, "accepted": 0, "rejects": defaultdict(int)})
    for r in rows:
        s = byday[(r["venue"], r["date"])]; s["zones"] += 1
        if r["hybrid_decision"] == "HYBRID_PASS": s["candidates"] += 1
        if r["final_shadow_decision"] == "ACCEPT": s["accepted"] += 1
        for rr in (r["reject_reasons"].split(";") if r["reject_reasons"] else []):
            if rr: s["rejects"][rr] += 1
    ds = []
    for (v, d), s in sorted(byday.items()):
        ds.append({"venue": v, "date": d, "zones": s["zones"], "candidates": s["candidates"], "accepted": s["accepted"], "top_rejects": dict(sorted(s["rejects"].items(), key=lambda kv: -kv[1])[:3])})
    (OUT / "TD_SHORT_DAILY_SUMMARY.json").write_text(json.dumps({"build": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "days": ds}, indent=2, default=str), encoding="utf-8")
    md = ["# TD-short shadow observer — daily summary", "", "| venue | date | zones | candidates | accepted | top rejects |", "|---|---|--:|--:|--:|---|"]
    for r in ds: md.append(f"| {r['venue']} | {r['date']} | {r['zones']} | {r['candidates']} | {r['accepted']} | {r['top_rejects']} |")
    (OUT / "TD_SHORT_DAILY_SUMMARY.md").write_text("\n".join(md), encoding="utf-8")


def load_caches():
    caches = {"OKX_MARCH": ROOT / "reports/strategy-calibration/OKX_MARCH_DIAG_FEATURE_CACHE.json",
              "OKX_MAY": ROOT / "reports/okx-may/OKX_2026_05_21_30_FEATURE_CACHE.json",
              "BINANCE_MAY": ROOT / "reports/binance-oos/BINANCE_10D_FIXED_L2_FEATURE_CACHE.json"}
    zones = []
    for vn, p in caches.items():
        for z in json.loads(p.read_text(encoding="utf-8")):
            if z.get("confirmedTs") is None: continue
            z["_venue"] = vn
            if not z.get("symbol"): z["symbol"] = "BTC-USDT-SWAP" if vn.startswith("OKX") else "BTCUSDT"
            zones.append(z)
    return zones


def main():
    zones = load_caches()
    rows = run_decisions(zones)
    write_logs(rows)
    acc = sum(1 for r in rows if r["final_shadow_decision"] == "ACCEPT")
    cand = sum(1 for r in rows if r["hybrid_decision"] == "HYBRID_PASS")
    leak_free = all(not any(k in DECISION_FIELDS for k in ("sim_outcome", "true_mfe", "pnl_after_cost", "hit_2", "result")) for _ in [0])
    print(f"decisions: {len(rows)} zones · HYBRID candidates {cand} · accepted {acc}", file=sys.stderr)
    print(f"DECISION_LOG_FUTURE_LEAK_FREE = {'YES' if leak_free else 'NO'}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
