"""A/B/C/D/E — OKX early-May (05-03..10) analysis: audit, engine summary, TD-short sanity,
strong-move labels, TU-long module research. Binance absent -> CROSS_VENUE_NOT_AVAILABLE.
No engine/detector/TP-SL change. TP=2%. 2.5/3% = quality labels. Causal. No Tardis/production.
"""
from __future__ import annotations
import csv, gzip, json, statistics as st, sys, datetime as dt
from collections import defaultdict
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "package.json").exists() and (p / "scripts").exists())
sys.path.insert(0, str(ROOT / "scripts/strategy-calibration")); sys.path.insert(0, str(ROOT / "scripts/shadow"))
import venue_norm_research as V
import td_short_shadow_observer as OBS

DATA = ROOT / "data/okx-historical/BTC-USDT-SWAP"
OUT = ROOT / "reports/okx-may-early"
CACHE = OUT / "OKX_2026_05_01_10_FEATURE_CACHE.json"
DATES = [f"2026-05-{d:02d}" for d in range(3, 21)]
TREND_PCT = 2.5


def now_iso(): return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
def num(x): return x if isinstance(x, (int, float)) else None
def regime_dir(z):
    pm = num(z.get("prior_move_1d_pct"))
    if pm is None: return "RANGE"
    return "TREND_UP" if pm > TREND_PCT else ("TREND_DOWN" if pm < -TREND_PCT else "RANGE")
def is_strong(z): return num(z.get("true_mfe")) is not None and z["true_mfe"] >= 2.5
def thin(z): return (z.get("ms_large_walls_on_path") in (0, None)) and (num(z.get("eng_void")) or 0) >= 0.5


# ---- TU-long gates (research-only; symmetric to TD-short) ----
def seller_absorption(z):
    o = num(z.get("eng_ofi")); ti = num(z.get("supportive_taker_imb_15m"))
    return (o is not None and o < -0.2) or (ti is not None and ti < -0.1)   # sell flow / sell-dominant under a LONG
def tu_mandatory(z):
    r = []
    if regime_dir(z) != "TREND_UP": r.append("not_TREND_UP")
    if z["direction"] != "LONG": r.append("not_LONG")
    pm60 = num(z.get("prior_move_60m_pct"))
    if pm60 is None or pm60 <= 0: r.append("prior_60m_not_positive")
    if seller_absorption(z): r.append("seller_absorption")
    return r
def tu_conf(z):
    return {"reclaim": z.get("reclaim_zoneMid_preconfirm") == 1, "taker_buy": (num(z.get("supportive_taker_imb_15m")) or -9) > 0,
            "microprice_up": (num(z.get("dl2_microprice_aligned_delta_5m_bps")) or -9) >= 0, "thin_ask_path": thin(z)}
def tu_conf_count(z): return sum(1 for v in tu_conf(z).values() if v)


def first_elig(zones, extra, maxn=1, cooldown=False):
    byd = defaultdict(list)
    for z in zones: byd[z["_date"]].append(z)
    out = []
    for d in sorted(byd):
        day = sorted(byd[d], key=lambda z: z["confirmedTs"]); taken = []
        for z in day:
            if extra and not extra(z): continue
            if cooldown and not V.cluster_cooldown_ok(z, taken): continue
            taken.append(z); out.append(z)
            if len(taken) >= maxn: break
    return out
def sel_metrics(zones, sel):
    tr = [z for z in sel if z.get("sim_outcome")]; m = V.metrics(tr)
    days = len({z["_date"] for z in zones}); sd = len({z["_date"] for z in sel})
    m["no_trade_days"] = days - sd; m["alerts_per_day"] = round(len(sel) / max(days, 1), 2)
    for thr, k in ((2, "hit_2"), (2.5, "hit_2_5"), (3, "hit_3")):
        m[k] = sum(1 for z in tr if num(z.get("true_mfe")) and z["true_mfe"] >= thr)
    return m


def crossing(d, minutes=10):
    p = DATA / d / "incremental_book_L2.csv.gz"
    if not p.exists(): return None
    bid = {}; ask = {}; start = None; cur = None; samp = 0; cross = 0; last = -1; spr = []
    with gzip.open(p, "rt") as f:
        f.readline()
        for line in f:
            x = line.rstrip().split(",")
            ms = int(x[2]) // 1000
            if start is None: start = ms
            if ms > start + minutes * 60000: break
            if cur is not None and ms != cur:
                if bid and ask:
                    bb = max(bid); ba = min(ask); s = ms // 100
                    if s != last:
                        last = s; samp += 1
                        if bb >= ba: cross += 1
                        else: spr.append((ba - bb) / ((bb + ba) / 2) * 1e4)
            cur = ms; side = x[5]; price = float(x[6]); amt = float(x[7])
            b = bid if side == "bid" else ask
            if amt == 0: b.pop(price, None)
            else: b[price] = amt
    return {"crossed_pct": round(100 * cross / max(samp, 1), 3), "median_spread_bps": round(st.median(spr), 4) if spr else None}


def window_regime():
    gb_low = None; gb_high = None; first = None; last = None
    for d in DATES:
        p = DATA / d / "trades.csv.gz"
        if not p.exists(): continue
        with gzip.open(p, "rt") as f:
            f.readline()
            for line in f:
                x = line.rstrip().split(",")
                try: px = float(x[6])
                except Exception: continue
                if first is None: first = px
                last = px
                gb_low = px if gb_low is None else min(gb_low, px); gb_high = px if gb_high is None else max(gb_high, px)
    if first is None: return {"return_pct": None, "range_pct": None, "regime": "UNKNOWN"}
    ret = (last - first) / first * 100; rng = (gb_high - gb_low) / gb_low * 100
    reg = "TREND_UP" if ret > 3 else "TREND_DOWN" if ret < -3 else "RANGE"
    return {"return_pct": round(ret, 2), "range_pct": round(rng, 2), "regime": reg}


def main():
    binance_avail = "NO"  # Binance live recorder only 05-17..30
    # ---- A: data audit ----
    conv = json.loads((OUT / "OKX_EARLY_CONVERSION_REPORT.json").read_text()) if (OUT / "OKX_EARLY_CONVERSION_REPORT.json").exists() else {"days": []}
    audit_rows = []
    for x in conv.get("days", []):
        d = x["date"]; cs = crossing(d) if x.get("l2_status") in ("CONVERTED", "EXISTS") else None
        audit_rows.append({"date": d, "l2_status": x.get("l2_status"), "l2_rows": x.get("l2_rows"), "trades_status": x.get("tr_status"),
                           "trades_rows": x.get("tr_rows"), "crossed_pct": cs["crossed_pct"] if cs else None, "median_spread_bps": cs["median_spread_bps"] if cs else None,
                           "quality": "FULL" if (x.get("l2_status") in ("CONVERTED", "EXISTS") and x.get("tr_status") in ("CONVERTED", "EXISTS")) else ("L2_ONLY" if x.get("l2_status") in ("CONVERTED", "EXISTS") else "BAD")})
    wreg = window_regime()
    nfull = sum(1 for r in audit_rows if r["quality"] == "FULL")
    a_flags = {"OKX_MAY_EARLY_DATA_READY": "YES" if nfull >= 6 else ("PARTIAL" if nfull >= 3 else "NO"), "TARDIS_USED": "NO",
               "WINDOW_REGIME": wreg["regime"], "WINDOW_RETURN_PCT": wreg["return_pct"], "CROSS_VENUE_NOT_AVAILABLE": "YES"}
    (OUT / "OKX_2026_05_01_10_DATA_AUDIT.json").write_text(json.dumps({"build": now_iso(), "days": audit_rows, "window_regime": wreg, "flags": a_flags, "units": "OKX contracts ctVal 0.01 BTC"}, indent=2, default=str), encoding="utf-8")
    with (OUT / "OKX_2026_05_01_10_DATA_AUDIT.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(audit_rows[0].keys())); w.writeheader(); w.writerows(audit_rows)
    (OUT / "OKX_2026_05_01_10_DATA_AUDIT.md").write_text("# A. OKX early-May data audit\n\n**Build:** " + now_iso() +
        f"\n\nWindow regime: **{wreg['regime']}** (ret {wreg['return_pct']}%, range {wreg['range_pct']}%). Units: contracts (ctVal 0.01). Cross-venue: NOT AVAILABLE (no Binance early-May).\n\n"
        "| date | L2 | rows | trades | rows | crossed% | spread bps | quality |\n|---|:--:|--:|:--:|--:|--:|--:|:--:|\n" +
        "\n".join(f"| {r['date']} | {r['l2_status']} | {r['l2_rows']} | {r['trades_status']} | {r['trades_rows']} | {r['crossed_pct']} | {r['median_spread_bps']} | {r['quality']} |" for r in audit_rows) +
        f"\n\nFlags: {a_flags}\n", encoding="utf-8")

    if not CACHE.exists():
        print("feature cache not ready; A audit written only", file=sys.stderr); return 2
    zones = json.loads(CACHE.read_text())
    V.normalize_layer(zones, V.COMMON_FEATS)
    for z in zones: z["_regime_dir"] = regime_dir(z); z["_venue"] = "OKX_MAY_EARLY"; z["symbol"] = "BTC-USDT-SWAP"
    traded = [z for z in zones if z.get("sim_outcome")]

    # ---- B: engine summary ----
    eng_rows = []
    for d in DATES:
        p = OUT / f"BTC-USDT-SWAP_{d}" / "daily_summary.csv"; s = {}
        if p.exists():
            for line in p.read_text().splitlines()[1:]:
                if "," in line:
                    k, v = line.split(",", 1)
                    try: s[k] = int(v) if v.lstrip("-").isdigit() else float(v)
                    except Exception: s[k] = v
        dz = [z for z in zones if z["_date"] == d]
        reg = st.median([z["prior_move_1d_pct"] for z in dz if num(z.get("prior_move_1d_pct")) is not None]) if dz else None
        eng_rows.append({"date": d, "zones": int(s.get("zones_total", 0)), "confirmed": len(dz), "triggered": int(s.get("zones_triggered", 0)),
                         "reached_raw": int(s.get("reached_zones_raw", 0)), "primary_unique": int(s.get("unique_reached_moves", 0)),
                         "duplicate": int(s.get("duplicate_move_credits", 0)), "failed": int(s.get("status_RESOLVED_FAILED", 0)),
                         "long": sum(1 for z in dz if z["direction"] == "LONG"), "short": sum(1 for z in dz if z["direction"] == "SHORT"),
                         "median_1d_move": round(reg, 2) if reg is not None else None})
    (OUT / "OKX_2026_05_01_10_ENGINE_SUMMARY.json").write_text(json.dumps({"build": now_iso(), "days": eng_rows}, indent=2, default=str), encoding="utf-8")
    with (OUT / "OKX_2026_05_01_10_ENGINE_SUMMARY.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(eng_rows[0].keys())); w.writeheader(); w.writerows(eng_rows)
    (OUT / "OKX_2026_05_01_10_ENGINE_SUMMARY.md").write_text("# B. OKX early-May engine summary\n\n**Build:** " + now_iso() +
        "\n\n| date | zones | conf | trig | reached | uniq | failed | L/S | med_1d% |\n|---|--:|--:|--:|--:|--:|--:|:--:|--:|\n" +
        "\n".join(f"| {r['date']} | {r['zones']} | {r['confirmed']} | {r['triggered']} | {r['reached_raw']} | {r['primary_unique']} | {r['failed']} | {r['long']}/{r['short']} | {r['median_1d_move']} |" for r in eng_rows) + "\n", encoding="utf-8")

    # ---- C: TD-short observer sanity ----
    td_rows = []
    for z in zones:
        ev = OBS.evaluate(z)
        td_rows.append({"date": z["_date"], "dir": z["direction"], "regime": ev["regime"], "hybrid": ev["hybrid_decision"], "reject": ev["reject_reasons"]})
    td_cands = [r for r in td_rows if r["hybrid"] == "HYBRID_PASS"]
    accepted_shorts = first_elig([z for z in zones if OBS.evaluate(z)["hybrid_decision"] == "HYBRID_PASS"], None)
    false_shorts_tu = sum(1 for z in accepted_shorts if regime_dir(z) == "TREND_UP")
    rr = defaultdict(int)
    for r in td_rows:
        for x in (r["reject"].split(";") if r["reject"] else []):
            if x: rr[x] += 1
    stands_aside = "YES" if len(td_cands) == 0 else ("PARTIAL" if len(td_cands) <= 2 else "NO")
    c_flags = {"TD_SHORT_STANDS_ASIDE_IN_TREND_UP": stands_aside, "TD_SHORT_FALSE_SHORTS_IN_TREND_UP": false_shorts_tu,
               "TD_SHORT_HYBRID_CANDIDATES": len(td_cands)}
    (OUT / "TD_SHORT_ON_OKX_MAY_EARLY_SANITY.json").write_text(json.dumps({"build": now_iso(), "n_zones": len(zones), "hybrid_candidates": len(td_cands), "accepted_shorts": len(accepted_shorts), "false_shorts_in_trend_up": false_shorts_tu, "reject_reasons": dict(rr), "flags": c_flags}, indent=2, default=str), encoding="utf-8")
    with (OUT / "TD_SHORT_ON_OKX_MAY_EARLY_SANITY.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(td_rows[0].keys())); w.writeheader(); w.writerows(td_rows)
    (OUT / "TD_SHORT_ON_OKX_MAY_EARLY_SANITY.md").write_text("# C. TD-short observer sanity on OKX early-May (expect stand-aside in TREND_UP)\n\n**Build:** " + now_iso() +
        f"\n\nzones {len(zones)} · HYBRID candidates {len(td_cands)} · accepted shorts {len(accepted_shorts)} · false shorts in TREND_UP {false_shorts_tu}\n\n"
        f"**TD_SHORT_STANDS_ASIDE_IN_TREND_UP = {stands_aside}**\n\nReject reasons: {dict(sorted(rr.items(), key=lambda kv:-kv[1]))}\n", encoding="utf-8")

    # ---- D: strong-move labels ----
    def slabel(z):
        m = num(z.get("true_mfe"))
        if m is None: return z.get("sim_label", "NO_TRADE")
        if m >= 3: return "STRONG_3"
        if m >= 2.5: return "STRONG_2_5"
        if m >= 2: return "WEAK_WIN_2"
        if m >= 0: return "MID"
        return "NOISE"
    cc = defaultdict(int)
    for z in traded: cc[slabel(z)] += 1
    def cnt(thr): return sum(1 for z in traded if num(z.get("true_mfe")) and z["true_mfe"] >= thr)
    (OUT / "OKX_2026_05_01_10_STRONG_MOVE_LABELS.json").write_text(json.dumps({"build": now_iso(), "traded": len(traded), "hit_2": cnt(2), "hit_2_5": cnt(2.5), "hit_3": cnt(3), "classes": dict(cc)}, indent=2), encoding="utf-8")
    with (OUT / "OKX_2026_05_01_10_STRONG_MOVE_LABELS.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh); w.writerow(["zone_id", "date", "dir", "regime", "class", "true_mfe", "true_mae", "time_to_2_min", "time_to_2_5_min"])
        for z in traded: w.writerow([z["id"], z["_date"], z["direction"], z["_regime_dir"], slabel(z), z.get("true_mfe"), z.get("true_mae"), round(z["time_to_2"] / 60, 1) if z.get("time_to_2") else None, round(z["time_to_2_5"] / 60, 1) if z.get("time_to_2_5") else None])
    (OUT / "OKX_2026_05_01_10_STRONG_MOVE_LABELS.md").write_text("# D. OKX early-May strong-move labels (no-exit 24h MFE)\n\n**Build:** " + now_iso() +
        f"\n\ntraded {len(traded)} · hit2 {cnt(2)} · hit2.5 {cnt(2.5)} · hit3 {cnt(3)}\n\nClasses: {dict(cc)}\n", encoding="utf-8")

    # ---- E: TU-long module research ----
    tu_long = [z for z in zones if regime_dir(z) == "TREND_UP" and z["direction"] == "LONG" and z.get("sim_outcome")]
    def run(name, extra, maxn=1, cooldown=False):
        sel = first_elig(tu_long, extra, maxn=maxn, cooldown=cooldown); m = sel_metrics(tu_long, sel)
        rej = [z for z in tu_long if not (extra(z) if extra else True)]
        fp = sum(1 for z in rej if z.get("sim_outcome") == "LOSS")
        rw = sum(1 for z in rej if z.get("sim_outcome") == "WIN" or (num(z.get("true_mfe")) and z["true_mfe"] >= 2))
        return {"model": name, "trades": m["trades"], "wins": m["wins"], "losses": m["losses"], "timeouts": m["timeouts"], "winrate_pct": m["winrate_pct"],
                "expectancy_after_cost_pct": m["expectancy_after_cost_pct"], "pf_after_cost": m["pf_after_cost"], "total_return_after_cost_pct": m["total_return_after_cost_pct"],
                "max_consecutive_losses": m["max_consecutive_losses"], "no_trade_days": m["no_trade_days"], "alerts_per_day": m["alerts_per_day"],
                "hit_2": m["hit_2"], "hit_2_5": m["hit_2_5"], "hit_3": m["hit_3"], "correctly_rejected_losers": fp, "rejected_winners": rw}
    cf = tu_conf
    E = [run("M0_baseline_RS1", lambda z: True),  # baseline = all TU-long (no extra)
         run("M1_TU_LONG_only", lambda z: True),
         run("M2_no_seller_absorption", lambda z: not seller_absorption(z)),
         run("M3_plus_reclaim", lambda z: (not seller_absorption(z)) and z.get("reclaim_zoneMid_preconfirm") == 1),
         run("M4_plus_taker_microprice", lambda z: (not seller_absorption(z)) and (cf(z)["taker_buy"] or cf(z)["microprice_up"])),
         run("M5_plus_thin_ask", lambda z: (not seller_absorption(z)) and cf(z)["thin_ask_path"]),
         run("M6_confluence_2of4", lambda z: (not seller_absorption(z)) and tu_conf_count(z) >= 2),
         run("M7_live_valid_2of4_cooldown", lambda z: (not seller_absorption(z)) and tu_conf_count(z) >= 2, maxn=2, cooldown=True)]
    best = max([r for r in E if r["trades"] >= 5], key=lambda r: (r["pf_after_cost"] or 0), default=E[0])
    e_flags = {"TU_LONG_RESEARCH_DONE": "YES", "TU_LONG_ZONES": len(tu_long), "BEST_TU_LONG_MODEL": best["model"],
               "BEST_TU_LONG_WINRATE": best["winrate_pct"], "BEST_TU_LONG_PF": best["pf_after_cost"], "CROSS_VENUE_NOT_AVAILABLE": "YES",
               "READY_FOR_PRODUCTION_TRADING": "NO", "TARDIS_USED": "NO"}
    (OUT / "TU_LONG_MODULE_RESEARCH.json").write_text(json.dumps({"build": now_iso(), "window_regime": wreg, "tu_long_zones": len(tu_long), "models": E, "flags": e_flags}, indent=2, default=str), encoding="utf-8")
    with (OUT / "TU_LONG_MODULE_RESEARCH.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(E[0].keys())); w.writeheader(); w.writerows(E)
    mdE = ["# E. TU-long (TREND_UP LONG-continuation) module research", "", f"**Build:** {now_iso()}",
           f"Window regime {wreg['regime']} (ret {wreg['return_pct']}%). TU-long zones: {len(tu_long)}. Cross-venue NOT AVAILABLE.", "",
           "| model | tr | W/L/TO | wr% | exp% | PF | ret% | hit2/2.5/3 | FP removed | rej winners |",
           "|---|--:|:--:|--:|--:|--:|--:|:--:|--:|--:|"]
    for r in E:
        mdE.append(f"| {r['model']} | {r['trades']} | {r['wins']}/{r['losses']}/{r['timeouts']} | {r['winrate_pct']} | {r['expectancy_after_cost_pct']} | {r['pf_after_cost']} | {r['total_return_after_cost_pct']} | {r['hit_2']}/{r['hit_2_5']}/{r['hit_3']} | {r['correctly_rejected_losers']} | {r['rejected_winners']} |")
    (OUT / "TU_LONG_MODULE_RESEARCH.md").write_text("\n".join(mdE), encoding="utf-8")

    print("=== A window regime:", wreg)
    print("=== B engine: zones", sum(r["zones"] for r in eng_rows), "confirmed", len(zones), "reached", sum(r["reached_raw"] for r in eng_rows))
    print(f"=== C TD-short sanity: HYBRID candidates {len(td_cands)} accepted {len(accepted_shorts)} false-shorts-in-TU {false_shorts_tu} -> stands_aside={stands_aside}")
    print(f"=== D strong: traded {len(traded)} hit2 {cnt(2)} hit2.5 {cnt(2.5)} hit3 {cnt(3)} classes {dict(cc)}")
    print(f"=== E TU-long ({len(tu_long)} zones):")
    for r in E: print(f"  {r['model']:<28s} tr {r['trades']:>2} wr {r['winrate_pct']}% exp {r['expectancy_after_cost_pct']} PF {r['pf_after_cost']} hit2.5 {r['hit_2_5']}")
    print("FLAGS C:", c_flags, "| E:", e_flags)
    return 0


if __name__ == "__main__":
    sys.exit(main())
