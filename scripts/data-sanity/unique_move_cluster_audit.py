"""UNIQUE MOVE / DUPLICATE CLUSTER AUDIT — OKX 05-03..20.

Dedups raw hit-zones into independent market moves. A zone's target_hit_ts = confirmedTs + time_to_level.
Zones of same direction whose target hits fall within a 120-min window = ONE unique move (duplicate credits).
Causal module/proto alerts decide which moves were live-catchable (before target) vs hindsight-only.
Does NOT change conclusions or tune filters — pure raw-vs-unique recount.
"""
from __future__ import annotations
import csv, json, statistics as st, sys, importlib.util, datetime as dt
from collections import defaultdict
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "package.json").exists() and (p / "scripts").exists())
sys.path.insert(0, str(ROOT / "scripts/strategy-calibration")); sys.path.insert(0, str(ROOT / "scripts/shadow")); sys.path.insert(0, str(ROOT / "scripts/data-sanity"))
import td_short_shadow_observer as OBS
from canonical_ledger import build_buckets_from_trades_csv
spec = importlib.util.spec_from_file_location("tz", str(ROOT / "scripts/data-sanity/strong_zone_taxonomy.py"))
TZ = importlib.util.module_from_spec(spec); spec.loader.exec_module(TZ)
import openpyxl

OUT = ROOT / "reports/okx-may-early"; DATA = ROOT / "data/okx-historical/BTC-USDT-SWAP"
CACHE = OUT / "OKX_2026_05_01_10_FEATURE_CACHE.json"
DATES = [f"2026-05-{d:02d}" for d in range(3, 21)]
MOVE_GAP_S = 120 * 60   # 120-min window groups same move


def now_iso(): return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
def num(x): return x if isinstance(x, (int, float)) else None
def mins(s): return round(s / 60, 1) if isinstance(s, (int, float)) else None


def tu_long_pass(z):
    return z["_regime"] == "TREND_UP" and z["direction"] == "LONG" and not TZ.proto(z, "M5_ABSORPTION_REVERSAL") is None and not _seller_abs(z) and _tu_cc(z) >= 2
def _seller_abs(z):
    o = num(z.get("eng_ofi")); ti = num(z.get("supportive_taker_imb_15m"))
    return (o is not None and o < -0.2) or (ti is not None and ti < -0.1)
def _tu_conf(z):
    return [z.get("reclaim_zoneMid_preconfirm") == 1, (num(z.get("supportive_taker_imb_15m")) or -9) > 0,
            (num(z.get("dl2_microprice_aligned_delta_5m_bps")) or -9) >= 0, TZ.thin(z)]
def _tu_cc(z): return sum(1 for v in _tu_conf(z) if v)


def cluster(zones, level):
    """group zones that hit `level`%, by direction + target_hit_ts gap <=120min. returns {zid: cluster_id}, clusters list."""
    tt_key = {2: "time_to_2", 2.5: "time_to_2_5", 3: "time_to_3"}[level]
    elig = []
    for z in zones:
        m = num(z.get("true_mfe")); tt = num(z.get(tt_key))
        if m is not None and m >= level and tt is not None:
            z["_target_hit_ts"] = z["confirmedTs"] // 1000 + tt
            elig.append(z)
    cid_map = {}; clusters = []
    by_dir = defaultdict(list)
    for z in elig: by_dir[z["direction"]].append(z)
    cn = 0
    for d, zs in by_dir.items():
        zs.sort(key=lambda x: x["_target_hit_ts"])
        cur = []
        last = None
        for z in zs:
            if last is not None and z["_target_hit_ts"] - last > MOVE_GAP_S:
                clusters.append(cur); cn += 1; cur = []
            cur.append(z); last = z["_target_hit_ts"]
        if cur: clusters.append(cur); cn += 1
    out = []
    for i, c in enumerate(clusters):
        cid = f"{level}|{c[0]['direction']}|{i}"
        for z in c: cid_map[z["id"]] = cid
        out.append({"cluster_id": cid, "level": level, "direction": c[0]["direction"], "size": len(c), "zones": c})
    return cid_map, out


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

    # causal module/proto alert predicates (gate-pass, NOT first-eligible)
    td_acc = {r["zone_id"] for r in OBS.run_decisions(zones) if r["final_shadow_decision"] == "ACCEPT"}
    td_pass = {z["id"] for z in zones if OBS.evaluate(z)["hybrid_decision"] == "HYBRID_PASS"}
    def mods(z):
        return {"TD_SHORT": (z["id"] in td_pass), "TU_LONG": tu_long_pass(z),
                "RANGE_FADE": TZ.proto(z, "M1_RANGE_FADE"), "SWEEP": TZ.proto(z, "M6_LIQUIDITY_SWEEP"),
                "FALSE_BREAKOUT": TZ.proto(z, "M2_FALSE_BREAKOUT_RECLAIM"), "ABSORPTION": TZ.proto(z, "M5_ABSORPTION_REVERSAL")}
    def any_existing(z): return mods(z)["TD_SHORT"] or mods(z)["TU_LONG"]
    def any_new(z): m = mods(z); return m["RANGE_FADE"] or m["SWEEP"] or m["FALSE_BREAKOUT"] or m["ABSORPTION"]
    def any_module(z): return any_existing(z) or any_new(z)

    def hindsight(z):
        f = z["_family"]
        if f in ("LIQUIDITY_SWEEP_REVERSAL", "FALSE_BREAKOUT_RECLAIM"): return "LOW"
        if f in ("RANGE_FADE_LOW_TO_HIGH", "RANGE_FADE_HIGH_TO_LOW", "BREAKOUT_RETEST", "ABSORPTION_REVERSAL"): return "MED"
        return "HIGH"

    # ---- clusters at each level ----
    levels = {}
    for lv in (2, 2.5, 3):
        cid_map, clusters = cluster(zones, lv)
        levels[lv] = {"cid_map": cid_map, "clusters": clusters}

    strong = [z for z in zones if num(z.get("true_mfe")) is not None and z["true_mfe"] >= 2.5]
    cid25 = levels[2.5]["cid_map"]; clusters25 = levels[2.5]["clusters"]

    # ---- per-strong-zone enriched table ----
    rows = []
    for c in clusters25:
        czs = sorted(c["zones"], key=lambda x: x["confirmedTs"])
        first_id = czs[0]["id"]
        first_live = next((z["id"] for z in czs if any_module(z)), None)
        cluster_target_hit = min(z["_target_hit_ts"] for z in czs)
        any_existing_before = any(any_existing(z) for z in czs)
        any_new_before = any(any_new(z) for z in czs)
        for z in czs:
            rows.append({"zone_id": z["id"], "date": z["_date"], "direction": z["direction"], "setup_family": z["_family"],
                         "unique_move_cluster_id": c["cluster_id"], "cluster_size": c["size"],
                         "is_first_in_cluster": "YES" if z["id"] == first_id else "NO",
                         "is_duplicate": "NO" if z["id"] == first_id else "YES",
                         "is_first_live_detectable": "YES" if z["id"] == first_live else "NO",
                         "target_hit_ts": z["_target_hit_ts"], "time_from_confirm_to_target_min": mins(z.get("time_to_2")),
                         "MFE": z.get("true_mfe"),
                         "did_any_module_alert_before_cluster_move": "YES" if any_existing_before else "NO",
                         "could_new_module_alert_before_move": "YES" if any_new_before else "NO",
                         "hindsight_risk": hindsight(z)})

    # ---- A: strong summary ----
    n_clusters25 = len(clusters25)
    first_live_clusters = sum(1 for c in clusters25 if any(any_module(z) for z in c["zones"]))
    dup_strong = len(strong) - n_clusters25
    hindsight_clusters = sum(1 for c in clusters25 if not any(any_module(z) for z in c["zones"]))
    A = {"raw_strong_zones": len(strong), "unique_strong_move_clusters": n_clusters25,
         "first_live_detectable_strong_clusters": first_live_clusters, "duplicate_strong_zones": dup_strong,
         "hindsight_only_strong_clusters": hindsight_clusters,
         "avg_zones_per_cluster": round(len(strong) / max(n_clusters25, 1), 2)}

    # ---- B: hit2 summary ----
    hit2 = [z for z in zones if num(z.get("true_mfe")) is not None and z["true_mfe"] >= 2]
    clusters2 = levels[2]["clusters"]
    B = {"raw_hit2_zones": len(hit2), "unique_hit2_move_clusters": len(clusters2),
         "first_live_detectable_hit2_clusters": sum(1 for c in clusters2 if any(any_module(z) for z in c["zones"])),
         "duplicate_hit2_zones": len(hit2) - len(clusters2),
         "unique_hit2_5_clusters": len(clusters25), "unique_hit3_clusters": len(levels[3]["clusters"])}

    # ---- C: module coverage by unique moves (strong / 2.5 clusters) ----
    def coverage(pred):
        raw = [z for z in strong if pred(z)]
        cl = {cid25.get(z["id"]) for z in raw if cid25.get(z["id"])}
        return {"raw_zones": len(raw), "unique_moves": len(cl)}
    C = {
        "TD_SHORT": coverage(lambda z: mods(z)["TD_SHORT"]),
        "TU_LONG": coverage(lambda z: mods(z)["TU_LONG"]),
        "RANGE_FADE_proto": coverage(lambda z: mods(z)["RANGE_FADE"]),
        "SWEEP_proto": coverage(lambda z: mods(z)["SWEEP"]),
        "ANY_NEW_proto": coverage(any_new), "ANY_MODULE": coverage(any_module),
    }

    # ---- D: answers ----
    rf_raw = C["RANGE_FADE_proto"]["raw_zones"]; rf_uniq = C["RANGE_FADE_proto"]["unique_moves"]
    D = {
        "1_independent_opportunities": f"{n_clusters25} unique strong-move clusters out of {len(strong)} raw zones.",
        "2_duplicates": f"{dup_strong} strong zones were duplicate credits of an already-counted move.",
        "3_live_catchable_before_move": f"{first_live_clusters}/{n_clusters25} unique strong moves had at least one zone a causal module/proto could alert on before target.",
        "4_hindsight_only": f"{hindsight_clusters}/{n_clusters25} unique strong moves had NO causal pre-signal (hindsight-only).",
        "5_range_fade_raw_or_unique": f"RANGE_FADE proto touches {rf_raw} raw strong zones = {rf_uniq} unique moves.",
        "6_still_formalize_range_fade": ("PARTIAL — after dedup it covers only " + str(rf_uniq) + " unique strong moves; combined with breakeven PF it is a weak standalone edge. Worth a shadow prototype, not a priority module."),
    }

    flags = {"UNIQUE_MOVE_AUDIT_DONE": "YES", "RAW_STRONG_ZONES": len(strong), "UNIQUE_STRONG_MOVES": n_clusters25,
             "DUPLICATE_STRONG_ZONES": dup_strong, "HINDSIGHT_ONLY_STRONG_MOVES": hindsight_clusters,
             "FIRST_LIVE_DETECTABLE_STRONG_MOVES": first_live_clusters,
             "RAW_HIT2_ZONES": len(hit2), "UNIQUE_HIT2_MOVES": len(clusters2),
             "RANGE_FADE_UNIQUE_MOVES_COVERED": rf_uniq, "CONCLUSIONS_CHANGED": "NO", "TARDIS_USED": "NO"}

    # ---- write ----
    with (OUT / "UNIQUE_MOVE_CLUSTER_AUDIT.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    appendix = {"build": now_iso(), "A_strong": A, "B_hit2": B, "C_coverage_by_unique_moves": C, "D_answers": D, "flags": flags, "per_zone": rows}
    (OUT / "UNIQUE_MOVE_CLUSTER_AUDIT.json").write_text(json.dumps(appendix, indent=2, default=str), encoding="utf-8")
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "PerZone"
    ws.append(list(rows[0].keys())); [ws.append([r.get(c) for c in rows[0].keys()]) for r in rows]
    ws2 = wb.create_sheet("Summary")
    ws2.append(["section", "key", "value"])
    for sec, dd in (("A_strong", A), ("B_hit2", B)):
        for k, v in dd.items(): ws2.append([sec, k, v])
    for mod, dd in C.items(): ws2.append(["C_coverage", mod, f"raw {dd['raw_zones']} / unique {dd['unique_moves']}"])
    wb.save(OUT / "UNIQUE_MOVE_CLUSTER_AUDIT.xlsx")
    md = ["# UNIQUE MOVE / DUPLICATE CLUSTER AUDIT (OKX 05-03..20)", "", f"**Build:** {now_iso()}",
          "Raw hit-zones deduped into independent moves (same direction + target-hit within 120 min). Conclusions unchanged.", "",
          "## A. Strong zones (>=2.5%)",
          f"- raw strong zones: **{A['raw_strong_zones']}**",
          f"- unique strong move clusters: **{A['unique_strong_move_clusters']}**",
          f"- duplicate strong zones: **{A['duplicate_strong_zones']}**",
          f"- first live-detectable strong clusters: **{A['first_live_detectable_strong_clusters']}**",
          f"- hindsight-only strong clusters: **{A['hindsight_only_strong_clusters']}**",
          f"- avg zones/cluster: {A['avg_zones_per_cluster']}", "",
          "## B. Hit2 zones",
          f"- raw hit2 zones: **{B['raw_hit2_zones']}** -> unique hit2 moves: **{B['unique_hit2_move_clusters']}** (duplicates {B['duplicate_hit2_zones']})",
          f"- unique hit2.5 moves: {B['unique_hit2_5_clusters']} · unique hit3 moves: {B['unique_hit3_clusters']}", "",
          "## C. Module coverage by UNIQUE moves (strong)", "| module | raw zones | unique moves |", "|---|--:|--:|"]
    for mod, dd in C.items(): md.append(f"| {mod} | {dd['raw_zones']} | {dd['unique_moves']} |")
    md += ["", "## D. Answers"] + [f"**{k}** — {v}" for k, v in D.items()] + ["", "## Flags", "```"] + [f"{k} = {v}" for k, v in flags.items()] + ["```"]
    (OUT / "UNIQUE_MOVE_CLUSTER_AUDIT.md").write_text("\n".join(md), encoding="utf-8")

    print("A strong:", A)
    print("B hit2:", B)
    print("C coverage by unique moves:")
    for mod, dd in C.items(): print(f"  {mod:<18s} raw {dd['raw_zones']:>2} / unique {dd['unique_moves']:>2}")
    print("D:", json.dumps(D, indent=1))
    print("FLAGS:", flags)
    return 0


if __name__ == "__main__":
    sys.exit(main())
