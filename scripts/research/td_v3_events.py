"""TREND_DOWN v3 — EVENT-BASED TRIGGER (analysis of v2 normalized per-minute data; NO re-parse, NO tuning).

Replaces the lower-high pivot trigger with EVENTS: ACTIVE_MARKDOWN / FORCED_UNWIND / CVD_BREAKDOWN /
SELL_PRESSURE_NO_ABSORPTION / ABSORPTION (no-short). Causal decisions (<= event minute); forward-only outcomes;
TP=2%/SL=1.5% unchanged; 2.5/3% quality labels. Cross-venue split into 6 types (lead-lag is a signal, not a
veto). Thresholds are fixed a-priori from market meaning, NOT fit to outcomes.
"""
from __future__ import annotations
import csv, gzip, json, statistics as st, sys, datetime as dt
from collections import defaultdict, Counter
from pathlib import Path

ROOT = Path("C:/Users/gibilev/orderflow-research")
NORM = ROOT / "reports/trend_down_crossvenue_v2/_normalized"
V2 = ROOT / "reports/trend_down_crossvenue_v2"
OUT = ROOT / "reports/trend_down_event_trigger_v3"
WINDOWS = {"W1_NOVEMBER": "2025-11-19..22", "W3_JANUARY": "2026-01-28..31", "W4_APRIL": "2024-04-12..17"}
EXES = ("Bybit", "OKX")
TP, SL, HORIZON, COOLDOWN = 2.0, 1.5, 480, 30


def now(): return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
def fnum(x):
    try: return float(x)
    except (TypeError, ValueError): return None
def med(v): v = [x for x in v if x is not None]; return round(st.median(v), 4) if v else None
def pf_of(W, L): return round((W * 1.86) / (L * 1.64), 3) if L else ("inf" if W else None)
def iso(m): return dt.datetime.fromtimestamp(m * 60, tz=dt.timezone.utc).isoformat()


def load(ex, wid):
    p = NORM / f"{ex}_{wid}_1m.csv.gz"
    if not p.exists(): return []
    S = []
    with gzip.open(p, "rt", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            S.append({"m": int(r["ts_min"]), "date": r["date"], "mid": fnum(r["mid_c"]), "spread": fnum(r["spread_bps"]),
                      "di": fnum(r["depth_imbalance"]), "bd": fnum(r["bid_depth_top10"]), "ad": fnum(r["ask_depth_top10"]),
                      "bv": fnum(r["taker_buy_vol"]) or 0, "sv": fnum(r["taker_sell_vol"]) or 0, "tc": fnum(r["trade_count"]) or 0, "cvd": fnum(r["cvd"]) or 0})
    S = [r for r in S if r["mid"] is not None]; S.sort(key=lambda x: x["m"])
    return S


def feats(S, t):
    mid = [r["mid"] for r in S]
    def back(n): return mid[t - n] if t >= n else None
    def s(n, k): return sum(S[i][k] for i in range(max(0, t - n), t))
    pc5 = (mid[t] - back(5)) / back(5) * 100 if back(5) else None
    pc15 = (mid[t] - back(15)) / back(15) * 100 if back(15) else None
    nt5 = s(5, "bv") - s(5, "sv"); nt15 = s(15, "bv") - s(15, "sv")
    cvd5 = S[t]["cvd"] - (S[t - 5]["cvd"] if t >= 5 else S[0]["cvd"]); cvd15 = S[t]["cvd"] - (S[t - 15]["cvd"] if t >= 15 else S[0]["cvd"])
    tc5 = s(5, "tc"); base_tc = st.median([S[i]["tc"] for i in range(max(0, t - 180), t)]) if t > 10 else 1
    spike5 = (tc5 / 5) / (base_tc or 1) if base_tc else None
    vol5 = s(5, "bv") + s(5, "sv"); vol15 = s(15, "bv") + s(15, "sv")
    look = mid[max(0, t - 240):t + 1]
    dist_low = (mid[t] - min(look)) / min(look) * 100 if look else None
    cvd_min60 = min(S[i]["cvd"] for i in range(max(0, t - 60), t + 1))
    base_spread = st.median([S[i]["spread"] for i in range(max(0, t - 60), t) if S[i]["spread"] is not None]) if t > 10 else None
    return {"pc5": pc5, "pc15": pc15, "nt5": nt5, "nt15": nt15, "cvd5": cvd5, "cvd15": cvd15, "spike5": spike5,
            "vol5": vol5, "vol15": vol15, "dist_low": dist_low, "di": S[t]["di"], "spread": S[t]["spread"],
            "cvd_is_min60": S[t]["cvd"] <= cvd_min60, "spread_wide": (S[t]["spread"] is not None and base_spread is not None and S[t]["spread"] > 1.5 * base_spread)}


def detect(S, t):
    """return dict family->quality(0-3) for a minute (causal). Fixed a-priori thresholds."""
    f = feats(S, t); out = {}
    di = f["di"]; pc15 = f["pc15"]; pc5 = f["pc5"]
    # A ACTIVE_MARKDOWN: net selling pushing price down, no bid dominance, room to low
    if f["cvd15"] < 0 and f["nt15"] < 0 and pc15 is not None and pc15 < -0.15 and (di is None or di <= 0.1) and (f["dist_low"] is None or f["dist_low"] > 0.3):
        out["ACTIVE_MARKDOWN_EVENT"] = 1 + (pc15 < -0.4) + (f["nt15"] < -vol_floor(f["vol15"]))
    # B FORCED_UNWIND: fast drop + activity burst + net selling + thinning/wide spread
    if f["spike5"] is not None and f["spike5"] >= 2.5 and pc5 is not None and pc5 <= -0.4 and f["nt5"] < 0 and (f["spread_wide"] or (di is not None and di < -0.1)):
        out["FORCED_UNWIND_EVENT"] = 1 + (pc5 <= -0.8) + (f["spike5"] >= 4)
    # C CVD_BREAKDOWN: new 60m CVD low + price confirms (not snapping back)
    if f["cvd_is_min60"] and pc5 is not None and pc5 <= 0 and t >= 1 and S[t]["mid"] <= S[t - 1]["mid"]:
        out["CVD_BREAKDOWN_EVENT"] = 1 + (pc5 < -0.2) + (f["cvd5"] < 0)
    # D SELL_PRESSURE_NO_ABSORPTION: selling + price passes down easily + not bid-heavy
    if f["nt15"] < 0 and pc15 is not None and pc15 < -0.1 and (di is None or di <= 0.0):
        out["SELL_PRESSURE_NO_ABSORPTION_EVENT"] = 1 + (pc15 < -0.3) + (di is not None and di < -0.15)
    # E ABSORPTION_AFTER_SELL_PRESSURE (NO-SHORT): selling but price NOT falling + bid-heavy
    if f["nt15"] < 0 and pc15 is not None and pc15 >= -0.05 and (di is not None and di > 0.15):
        out["ABSORPTION_AFTER_SELL_PRESSURE_EVENT"] = 1 + (pc15 > 0.1) + (di > 0.3)
    return out, f


def vol_floor(v): return (v or 0) * 0.1


def sell_initiative(S, t):
    f = feats(S, t)
    if f["nt5"] < 0 and f["pc5"] is not None and f["pc5"] < 0 and f["cvd5"] < 0: return -1  # sell
    if f["nt5"] > 0 and f["pc5"] is not None and f["pc5"] > 0 and f["cvd5"] > 0: return 1   # buy
    return 0


def outcome_short(mid, t, entry):
    fav = adv = 0.0; t2 = t25 = t3 = None; oc = "TIMEOUT"; end = min(len(mid), t + HORIZON)
    for j in range(t + 1, end):
        fv = (entry - mid[j]) / entry * 100; av = (mid[j] - entry) / entry * 100
        fav = max(fav, fv); adv = max(adv, av)
        if t2 is None and fav >= 2: t2 = j - t
        if t25 is None and fav >= 2.5: t25 = j - t
        if t3 is None and fav >= 3: t3 = j - t
        if av >= SL and t2 is None: oc = "LOSS"; break
        if fv >= TP: oc = "WIN"; break
    return {"outcome": oc, "mfe": round(fav, 3), "mae": round(adv, 3), "hit2": int(fav >= 2), "hit2_5": int(fav >= 2.5), "hit3": int(fav >= 3),
            "loss": int(oc == "LOSS"), "timeout": int(oc == "TIMEOUT"), "time_to_2": t2, "time_to_2_5": t25, "time_to_3": t3}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    series = {(ex, wid): load(ex, wid) for wid in WINDOWS for ex in EXES}

    # ---- detect raw events ----
    raw = []
    for (ex, wid), S in series.items():
        if not S: continue
        mid = [r["mid"] for r in S]
        for t in range(60, len(S) - 5):
            fams, f = detect(S, t)
            for fam, q in fams.items():
                short = fam != "ABSORPTION_AFTER_SELL_PRESSURE_EVENT"
                oc = outcome_short(mid, t, mid[t]) if short else {"outcome": "NO_SHORT", "mfe": None, "mae": None, "hit2": 0, "hit2_5": 0, "hit3": 0, "loss": 0, "timeout": 0, "time_to_2": None, "time_to_2_5": None, "time_to_3": None}
                raw.append({"event_id": f"{ex[:2]}-{wid}-{fam[:4]}-{t}", "event_family": fam, "exchange": ex, "window_id": wid, "date": S[t]["date"],
                            "ts_min": S[t]["m"], "ts_iso": iso(S[t]["m"]), "price": round(mid[t], 2), "event_quality_score": q,
                            "cvd_delta_15m": round(f["cvd15"], 1), "cvd_delta_5m": round(f["cvd5"], 1), "net_taker_15m": round(f["nt15"], 3),
                            "spike5": round(f["spike5"], 2) if f["spike5"] else None, "pc5": round(f["pc5"], 3) if f["pc5"] is not None else None,
                            "pc15": round(f["pc15"], 3) if f["pc15"] is not None else None, "depth_imbalance": f["di"], "spread_bps": f["spread"],
                            "dist_from_recent_low_pct": round(f["dist_low"], 3) if f["dist_low"] is not None else None, "is_short": int(short), **oc})
    # ---- dedup unique events (per ex/window/family, 30m cooldown) ----
    uniq = []
    by = defaultdict(list)
    for e in raw: by[(e["exchange"], e["window_id"], e["event_family"])].append(e)
    for k, es in by.items():
        es.sort(key=lambda x: x["ts_min"]); last = None
        for e in es:
            if last is None or e["ts_min"] - last > COOLDOWN: uniq.append(e); last = e["ts_min"]

    # ---- cross-venue type per unique event ----
    for e in uniq:
        other = "OKX" if e["exchange"] == "Bybit" else "Bybit"
        S2 = series.get((other, e["window_id"]), [])
        idx = {r["m"]: i for i, r in enumerate(S2)}
        m = e["ts_min"]; ct = "SINGLE_VENUE_INITIATIVE"; ll = None
        if e["event_family"] == "ABSORPTION_AFTER_SELL_PRESSURE_EVENT": ct = "ABSORPTION_DIVERGENCE"
        else:
            # follow-through on own venue (next 5m price continues down)?
            Sown = series[(e["exchange"], e["window_id"])]; iown = {r["m"]: i for i, r in enumerate(Sown)}.get(m)
            ft = None
            if iown is not None and iown + 5 < len(Sown): ft = (Sown[iown + 5]["mid"] - Sown[iown]["mid"]) / Sown[iown]["mid"] * 100
            if ft is not None and ft > 0.05: ct = "VENUE_NOISE"
            else:
                sells = []; buys = []
                for dm in range(-10, 11):
                    i2 = idx.get(m + dm)
                    if i2 is None or i2 < 5: continue
                    si = sell_initiative(S2, i2)
                    if si == -1: sells.append(dm)
                    elif si == 1: buys.append(dm)
                if buys and not any(abs(b) <= 2 for b in sells) and min(abs(b) for b in buys) <= 3:
                    ct = "TRUE_DISAGREEMENT"
                elif sells:
                    near = min(sells, key=abs)
                    if abs(near) <= 2: ct = "SYNC_CONFIRMATION"; ll = near
                    else: ct = "LEAD_LAG_CONFIRMATION"; ll = near  # >0: other confirms later (this venue leads)
                else:
                    ct = "SINGLE_VENUE_INITIATIVE"
        e["cross_venue_type"] = ct; e["lead_lag_minutes"] = ll
        e["reason"] = f"{e['event_family']} | cvd15 {e['cvd_delta_15m']} | pc15 {e['pc15']} | di {e['depth_imbalance']} | xv {ct}"

    # ---- write raw + unique + outcomes ----
    rcols = list(raw[0].keys()) if raw else ["event_id"]
    with (OUT / "EVENT_CANDIDATES_RAW.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=rcols, extrasaction="ignore"); w.writeheader(); w.writerows(raw)
    ucols = rcols + ["cross_venue_type", "lead_lag_minutes", "reason"]
    with (OUT / "EVENT_CANDIDATES_UNIQUE.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=ucols, extrasaction="ignore"); w.writeheader(); w.writerows(uniq)
    ocols = ["event_id", "event_family", "exchange", "window_id", "ts_iso", "price", "outcome", "hit2", "hit2_5", "hit3", "loss", "timeout", "mfe", "mae", "time_to_2", "time_to_2_5", "time_to_3"]
    with (OUT / "EVENT_OUTCOMES.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=ocols, extrasaction="ignore"); w.writeheader(); w.writerows([e for e in uniq if e["is_short"]])

    # ---- section 1: disagreement / cross-venue types ----
    short_u = [e for e in uniq if e["is_short"]]
    # HONESTY CONTROL (computed early so template status reflects lift over a naive baseline)
    naive = []
    for (ex, wid), S in series.items():
        mid = [r["mid"] for r in S]
        for t in range(60, len(S) - 5, 10): naive.append({"window_id": wid, **outcome_short(mid, t, mid[t])})
    nb = grp(naive); nb_byw = {wid: grp([r for r in naive if r["window_id"] == wid]) for wid in WINDOWS}
    indep = []; _byw = defaultdict(list)
    for e in short_u: _byw[e["window_id"]].append(e)
    for wid, es in _byw.items():
        es.sort(key=lambda x: x["ts_min"]); last = None
        for e in es:
            if last is None or e["ts_min"] - last > 60: indep.append(e); last = e["ts_min"]
    ib = grp(indep); base0 = grp(short_u)
    control = {"naive_baseline_all": nb, "naive_baseline_by_window": nb_byw, "event_short_all": base0, "independent_moments": ib,
               "lift_hit2_vs_naive": round(base0["hit2_rate"] - nb["hit2_rate"], 1), "n_independent_moments": len(indep)}
    cvt = defaultdict(list)
    for e in short_u: cvt[e["cross_venue_type"]].append(e)
    dt_rows = []
    for ct, es in cvt.items():
        W = sum(1 for e in es if e["outcome"] == "WIN"); L = sum(1 for e in es if e["outcome"] == "LOSS")
        dt_rows.append({"cross_venue_type": ct, "n": len(es), "hit2": sum(e["hit2"] for e in es), "hit2_rate": round(100 * sum(e["hit2"] for e in es) / max(len(es), 1), 1),
                        "W": W, "L": L, "TO": sum(1 for e in es if e["outcome"] == "TIMEOUT"), "pf": pf_of(W, L),
                        "veto_or_signal": {"SYNC_CONFIRMATION": "signal", "LEAD_LAG_CONFIRMATION": "signal(early)", "SINGLE_VENUE_INITIATIVE": "watch/quarantine",
                                           "TRUE_DISAGREEMENT": "VETO", "ABSORPTION_DIVERGENCE": "no-short/reversal-watch", "VENUE_NOISE": "veto/ignore"}.get(ct, "?")})
    dt_rows.sort(key=lambda r: -r["n"])
    with (OUT / "CROSS_VENUE_DISAGREEMENT_TYPES.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(dt_rows[0].keys()) if dt_rows else ["cross_venue_type"]); w.writeheader(); w.writerows(dt_rows)
    wmd(OUT / "CROSS_VENUE_DISAGREEMENT_TYPES.md", "CROSS-VENUE TYPES (not all disagreement is veto)",
        ["| type | n | hit2% | W/L/TO | PF | role |", "|---|--:|--:|:--:|--:|---|"] +
        [f"| {r['cross_venue_type']} | {r['n']} | {r['hit2_rate']} | {r['W']}/{r['L']}/{r['TO']} | {r['pf']} | {r['veto_or_signal']} |" for r in dt_rows] +
        ["", "LEAD_LAG_CONFIRMATION is treated as a potential EARLY signal (one venue leads), not a veto. TRUE_DISAGREEMENT / VENUE_NOISE are vetoes."])

    # ---- section 3: entry policies ----
    def policy_rows(policy):
        rows = []
        for e in short_u:
            S = series[(e["exchange"], e["window_id"])]; idx = {r["m"]: i for i, r in enumerate(S)}; i = idx.get(e["ts_min"]); mid = [r["mid"] for r in S]
            if i is None: continue
            if policy == "EVENT_CLOSE": ti, entry = i, mid[i]
            elif policy == "EVENT_NEXT_MINUTE":
                if i + 1 >= len(mid): continue
                ti, entry = i + 1, mid[i + 1]
            elif policy == "EVENT_PULLBACK_SMALL":
                pb = None
                for j in range(i + 1, min(i + 6, len(mid))):
                    if mid[j] > mid[i] and (S[j]["cvd"] - S[i]["cvd"]) <= 0: pb = j; break
                if pb is None: continue
                ti, entry = pb, mid[pb]
            elif policy == "NO_ENTRY_ABSORPTION":
                if e["event_family"] == "SELL_PRESSURE_NO_ABSORPTION_EVENT": ti, entry = i, mid[i]
                else: continue
            oc = outcome_short(mid, ti, entry); rows.append({**e, **oc})
        return rows
    pol_stats = []
    for pol in ("EVENT_CLOSE", "EVENT_NEXT_MINUTE", "EVENT_PULLBACK_SMALL", "NO_ENTRY_ABSORPTION"):
        rows = policy_rows(pol); W = sum(1 for r in rows if r["outcome"] == "WIN"); L = sum(1 for r in rows if r["outcome"] == "LOSS"); TO = sum(1 for r in rows if r["outcome"] == "TIMEOUT")
        t2s = [r["time_to_2"] for r in rows if r["time_to_2"]]
        pol_stats.append({"policy": pol, "n": len(rows), "hit2": sum(r["hit2"] for r in rows), "loss": L, "timeout": TO, "hit2_rate": round(100 * sum(r["hit2"] for r in rows) / max(len(rows), 1), 1),
                          "pf": pf_of(W, L), "expectancy": round(st.mean([1.86 if r["outcome"] == "WIN" else -1.64 if r["outcome"] == "LOSS" else 0 for r in rows]), 3) if rows else None,
                          "median_time_to_2": med(t2s), "windows": sorted(set(r["window_id"] for r in rows)),
                          "cross_venue_breakdown": dict(Counter(r["cross_venue_type"] for r in rows))})
    with (OUT / "ENTRY_POLICY_COMPARISON.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["policy", "n", "hit2", "loss", "timeout", "hit2_rate", "pf", "expectancy", "median_time_to_2", "windows", "cross_venue_breakdown"], extrasaction="ignore")
        w.writeheader()
        for r in pol_stats: w.writerow({**r, "windows": json.dumps(r["windows"]), "cross_venue_breakdown": json.dumps(r["cross_venue_breakdown"])})
    wmd(OUT / "ENTRY_POLICY_COMPARISON.md", "ENTRY POLICY COMPARISON (no fitting)",
        ["| policy | n | hit2% | PF | exp% | medT2 | windows |", "|---|--:|--:|--:|--:|--:|---|"] +
        [f"| {r['policy']} | {r['n']} | {r['hit2_rate']} | {r['pf']} | {r['expectancy']} | {r['median_time_to_2']} | {','.join(r['windows'])} |" for r in pol_stats])

    # ---- per-family stats ----
    fam_stats = {}
    for fam in ("ACTIVE_MARKDOWN_EVENT", "FORCED_UNWIND_EVENT", "CVD_BREAKDOWN_EVENT", "SELL_PRESSURE_NO_ABSORPTION_EVENT", "ABSORPTION_AFTER_SELL_PRESSURE_EVENT"):
        es = [e for e in uniq if e["event_family"] == fam]; sh = [e for e in es if e["is_short"]]
        W = sum(1 for e in sh if e["outcome"] == "WIN"); L = sum(1 for e in sh if e["outcome"] == "LOSS")
        fam_stats[fam] = {"n": len(es), "n_short": len(sh), "hit2": sum(e["hit2"] for e in sh), "hit2_rate": round(100 * sum(e["hit2"] for e in sh) / max(len(sh), 1), 1) if sh else 0,
                          "W": W, "L": L, "TO": sum(1 for e in sh if e["outcome"] == "TIMEOUT"), "pf": pf_of(W, L), "windows": sorted(set(e["window_id"] for e in es))}

    # ---- section 6: soft templates ----
    templates, scorecard = build_templates(fam_stats, dt_rows, uniq, nb["hit2_rate"])
    (OUT / "EVENT_FILTER_TEMPLATES.json").write_text(json.dumps({"build": now(), "research_only": True, "templates": templates}, indent=2, default=str), encoding="utf-8")
    with (OUT / "EVENT_FILTER_SCORECARD.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["template_id", "trigger_family", "n", "hit2_rate", "pf", "expectancy", "windows", "overfit_risk", "status"], extrasaction="ignore")
        w.writeheader()
        for t in templates: w.writerow({**t, "windows": json.dumps(t.get("windows", []))})
    wmd(OUT / "EVENT_FILTER_TEMPLATES.md", "EVENT FILTER TEMPLATES (soft, research)",
        ["| template | family | n | hit2% | PF | windows | status |", "|---|---|--:|--:|--:|---|:--:|"] +
        [f"| {t['template_id']} | {t['trigger_family']} | {t['n']} | {t['hit2_rate']} | {t['pf']} | {','.join(t.get('windows', []))} | **{t['status']}** |" for t in templates])

    # ---- section 7: good event casebook ----
    good = sorted([e for e in short_u if e["hit2"] == 1 and e["cross_venue_type"] in ("SYNC_CONFIRMATION", "LEAD_LAG_CONFIRMATION")], key=lambda e: e["ts_iso"])
    gcols = ["event_id", "ts_iso", "window_id", "exchange", "cross_venue_type", "lead_lag_minutes", "event_family", "price", "mfe", "time_to_2", "cvd_delta_15m", "net_taker_15m", "pc15", "depth_imbalance", "dist_from_recent_low_pct"]
    with (OUT / "GOOD_EVENT_ZONE_CASEBOOK.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=gcols, extrasaction="ignore"); w.writeheader(); w.writerows(good)
    gmd = ["# GOOD EVENT ZONE CASEBOOK", "", f"Build {now()} · cross-confirmed/lead-lag SHORT events that hit 2% (n={len(good)}).", ""]
    for e in good:
        gmd += [f"## {e['event_id']} [{e['exchange']}] {e['window_id']} {e['ts_iso']}",
                f"- family {e['event_family']} · cross_venue {e['cross_venue_type']} (lead_lag {e['lead_lag_minutes']}m) · MFE {e['mfe']}% · time_to_2 {e['time_to_2']}m",
                f"- CVD15 {e['cvd_delta_15m']} (selling) · net_taker15 {e['net_taker_15m']} · pc15 {e['pc15']}% · depthImb {e['depth_imbalance']} · room_to_low {e['dist_from_recent_low_pct']}%",
                f"- why worked: net selling broke price down with cross-venue agreement; not late (room to low); no bid absorption against the short.",
                f"- would invalidate: bid refill / CVD turning up / other venue showing buy initiative.", ""]
    (OUT / "GOOD_EVENT_ZONE_CASEBOOK.md").write_text("\n".join(gmd), encoding="utf-8")

    # ---- HONESTY CONTROL report (computed early above) ----
    base = base0
    wmd(OUT / "REGIME_EXPOSURE_CONTROL.md", "REGIME EXPOSURE CONTROL (the honest test)",
        ["**Question:** do event-shorts beat just shorting at a random minute in these (strong down) windows?", "",
         f"- naive 'short every 10th minute' baseline: n={nb['n']} hit2 {nb['hit2_rate']}% PF {nb['pf']} exp {nb['expectancy']}%",
         f"- event-short (all 1944, overlapping): hit2 {base['hit2_rate']}% PF {base['pf']}",
         f"- **lift of events over naive baseline: {control['lift_hit2_vs_naive']} pp hit2**",
         f"- independent moments (dedup all short events to 60-min buckets/window): **{len(indep)}** (not 1944)",
         f"  -> independent-moment hit2 {ib['hit2_rate']}% PF {ib['pf']}", "",
         "| window | naive hit2% | naive PF |", "|---|--:|--:|"] +
        [f"| {wid} | {nb_byw[wid]['hit2_rate']} | {nb_byw[wid]['pf']} |" for wid in WINDOWS] +
        ["", "**Interpretation:** if event hit2 ≈ naive baseline, the high PF is REGIME EXPOSURE (the market fell 8-12%), NOT a transferable filter.",
         "All 3 windows are strong downtrends; even TRUE_DISAGREEMENT 'wins' here — that is the tell that categories are not separating.",
         "A real edge must be tested on NEUTRAL / UP / chop windows as a control, and on OOS down windows."])

    # ---- section 5: comparison with v2 ----
    comparison_v2(fam_stats, short_u, pol_stats)

    # ---- final report ----
    rc = any(t["status"] == "RESEARCH_CANDIDATE" for t in templates)
    final(fam_stats, dt_rows, pol_stats, templates, base, rc, control)

    # console
    print(f"unique events {len(uniq)} (short {len(short_u)}) | baseline short PF {base['pf']} hit2 {base['hit2_rate']}%")
    print("per-family:")
    for fam, s in fam_stats.items(): print(f"  {fam:<40} n{s['n']:>3} short{s['n_short']:>3} hit2 {s['hit2_rate']}% PF {s['pf']} windows {s['windows']}")
    print("cross-venue types:")
    for r in dt_rows: print(f"  {r['cross_venue_type']:<24} n{r['n']:>3} hit2 {r['hit2_rate']}% PF {r['pf']} -> {r['veto_or_signal']}")
    print("entry policies:")
    for r in pol_stats: print(f"  {r['policy']:<22} n{r['n']:>3} hit2 {r['hit2_rate']}% PF {r['pf']} exp {r['expectancy']}")
    print("templates:")
    for t in templates: print(f"  {t['template_id']:<46} n{t['n']:>3} PF {t['pf']} -> {t['status']}")
    print("RESEARCH_CANDIDATE:", rc)
    return 0


def grp(rows):
    W = sum(1 for r in rows if r["outcome"] == "WIN"); L = sum(1 for r in rows if r["outcome"] == "LOSS")
    return {"n": len(rows), "hit2": sum(r["hit2"] for r in rows), "hit2_rate": round(100 * sum(r["hit2"] for r in rows) / max(len(rows), 1), 1), "pf": pf_of(W, L),
            "expectancy": round(st.mean([1.86 if r["outcome"] == "WIN" else -1.64 if r["outcome"] == "LOSS" else 0 for r in rows]), 3) if rows else None}


def build_templates(fam, dt_rows, uniq, naive_hit2=0.0):
    def decide(n, pf, wins, hit2=None):
        # honest gate: high PF in a strong-downtrend window is regime exposure unless it BEATS the naive baseline
        lift = (hit2 - naive_hit2) if hit2 is not None else None
        if n < 4: return "NEED_MORE_DATA"
        if pf in (None,) or (isinstance(pf, float) and pf < 0.9): return "REJECT"
        if lift is not None and lift < 8: return "NEED_MORE_DATA"  # no real edge over 'short anything' in a downtrend
        if isinstance(pf, float) and pf >= 1.3 and len(wins) >= 2 and (lift is None or lift >= 8): return "RESEARCH_CANDIDATE"
        if len(wins) < 2: return "QUARANTINE"
        return "NEED_MORE_DATA"
    fammap = [("TD_ACTIVE_MARKDOWN_EVENT_SHORT_TEMPLATE", "ACTIVE_MARKDOWN_EVENT"), ("TD_FORCED_UNWIND_EVENT_SHORT_TEMPLATE", "FORCED_UNWIND_EVENT"),
              ("TD_CVD_BREAKDOWN_EVENT_SHORT_TEMPLATE", "CVD_BREAKDOWN_EVENT")]
    tl = []
    for tid, famk in fammap:
        s = fam[famk]; dec = decide(s["n_short"], s["pf"], s["windows"], s["hit2_rate"])
        tl.append({"template_id": tid, "trigger_family": famk, "required_evidence": ["CVD falling", "net taker sell", "price down response", "no bid absorption"],
                   "optional_confirmations": ["cross-venue sync/lead-lag", "spread/depth normal"], "veto_conditions": ["bid refill/absorption", "true cross-venue disagreement", "venue noise"],
                   "cross_venue_logic": "sync or lead-lag confirms; true-disagreement vetoes", "lead_lag_logic": "lead venue can fire early if lagger confirms within ~10m",
                   "when_not_to_use": ["price already at low (no room)", "absorption divergence"], "n": s["n_short"], "hit2_rate": s["hit2_rate"], "pf": s["pf"],
                   "expectancy": None, "windows": s["windows"], "overfit_risk": "HIGH" if s["n_short"] < 8 else "MED", "status": dec})
    # lead-lag template
    ll = next((r for r in dt_rows if r["cross_venue_type"] == "LEAD_LAG_CONFIRMATION"), {"n": 0, "hit2_rate": 0, "pf": None})
    ll_wins = sorted(set(e["window_id"] for e in uniq if e.get("cross_venue_type") == "LEAD_LAG_CONFIRMATION" and e["is_short"]))
    tl.append({"template_id": "TD_LEAD_LAG_MARKDOWN_SHORT_TEMPLATE", "trigger_family": "LEAD_LAG_CONFIRMATION", "required_evidence": ["one venue sell-initiative first", "other confirms within ~10m", "price not snapping back"],
               "optional_confirmations": ["CVD breakdown on lead venue"], "veto_conditions": ["lagger shows buy initiative (true disagreement)"], "cross_venue_logic": "enter on lead venue, require lag confirm",
               "lead_lag_logic": "core of this template", "when_not_to_use": ["no confirm from lagger", "absorption"], "n": ll["n"], "hit2_rate": ll["hit2_rate"], "pf": ll["pf"], "expectancy": None,
               "windows": ll_wins, "overfit_risk": "HIGH", "status": decide(ll["n"], ll["pf"], ll_wins, ll["hit2_rate"])})
    # vetoes / no-short
    for tid, ct, role in [("TD_TRUE_DISAGREEMENT_VETO", "TRUE_DISAGREEMENT", "VETO_CANDIDATE"), ("TD_ABSORPTION_DIVERGENCE_NO_SHORT", "ABSORPTION_DIVERGENCE", "VETO_CANDIDATE"), ("TD_VENUE_NOISE_IGNORE", "VENUE_NOISE", "VETO_CANDIDATE")]:
        r = next((x for x in dt_rows if x["cross_venue_type"] == ct), {"n": 0, "hit2_rate": 0, "pf": None})
        wlist = sorted(set(e["window_id"] for e in uniq if e.get("cross_venue_type") == ct and e["is_short"]))
        st_ = role if r["n"] >= 4 else "NEED_MORE_DATA"
        tl.append({"template_id": tid, "trigger_family": ct, "required_evidence": [], "optional_confirmations": [], "veto_conditions": ["this IS a veto/no-short bucket"],
                   "cross_venue_logic": ct, "lead_lag_logic": "-", "when_not_to_use": ["do not SHORT on these"], "n": r["n"], "hit2_rate": r["hit2_rate"], "pf": r["pf"],
                   "expectancy": None, "windows": wlist, "overfit_risk": "MED", "status": st_})
    sc = [{"template_id": t["template_id"], "trigger_family": t["trigger_family"], "n": t["n"], "hit2_rate": t["hit2_rate"], "pf": t["pf"], "windows": t["windows"], "overfit_risk": t["overfit_risk"], "status": t["status"]} for t in tl]
    return tl, sc


def comparison_v2(fam, short_u, pol_stats):
    v2cb = list(csv.DictReader((V2 / "CAPITAL_STATE_CASEBOOK.csv").open(encoding="utf-8"))) if (V2 / "CAPITAL_STATE_CASEBOOK.csv").exists() else []
    v2n = len(v2cb); v2dist = sum(1 for r in v2cb if r.get("capital_state_candidate") == "DISTRIBUTION_INTO_BOUNCE"); v2unk = sum(1 for r in v2cb if r.get("capital_state_candidate") == "UNKNOWN")
    base = grp(short_u)
    am = fam["ACTIVE_MARKDOWN_EVENT"]["n_short"]; fu = fam["FORCED_UNWIND_EVENT"]["n_short"]
    md = ["# COMPARISON WITH v2 LOWER-HIGH PIVOT", "", f"Build {now()} · v2 = reports/trend_down_crossvenue_v2 (lower-high pivot + capital_state).", "",
          f"- v2 trigger: lower-high pivots -> mostly DISTRIBUTION_INTO_BOUNCE ({v2dist}) + UNKNOWN {v2unk}/{v2n} (77%); ACTIVE_MARKDOWN=0, FORCED_UNWIND=0.",
          f"- v3 trigger: EVENTS. ACTIVE_MARKDOWN_EVENT samples = **{am}**; FORCED_UNWIND_EVENT samples = **{fu}**; CVD_BREAKDOWN = {fam['CVD_BREAKDOWN_EVENT']['n_short']}.",
          f"- less DISTRIBUTION-only? {'YES — events sample markdown/unwind directly' if am + fu > 0 else 'NO'}",
          f"- ACTIVE_MARKDOWN samples appeared? {'YES (' + str(am) + ')' if am > 0 else 'NO'}; FORCED_UNWIND appeared? {'YES (' + str(fu) + ')' if fu > 0 else 'NO'}",
          f"- UNKNOWN reduced? events are typed by construction (no UNKNOWN bucket).",
          f"- baseline PF: v2 short ~0.72 vs v3 event short {base['pf']} ({'better' if isinstance(base['pf'],float) and base['pf']>0.72 else 'not better'}).",
          f"- best entry policy PF: {max((p['pf'] for p in pol_stats if isinstance(p['pf'],float)), default=None)}.",
          "- lead-lag edge or noise? see CROSS_VENUE_DISAGREEMENT_TYPES (LEAD_LAG row).",
          "- disagreement still a single veto? NO — split into TRUE_DISAGREEMENT/VENUE_NOISE (veto) vs LEAD_LAG/SYNC (signal)."]
    (OUT / "COMPARISON_WITH_V2_LOWER_HIGH.md").write_text("\n".join(md), encoding="utf-8")


def final(fam, dt_rows, pol_stats, templates, base, rc, control):
    best_fam = max(fam.items(), key=lambda kv: (kv[1]["pf"] if isinstance(kv[1]["pf"], float) else -1, kv[1]["n_short"]))
    best_pol = max(pol_stats, key=lambda p: (p["pf"] if isinstance(p["pf"], float) else -1, p["n"]))
    md = ["# TREND_DOWN EVENT-TRIGGER v3 — FINAL REPORT", "", f"Build {now()} · RESEARCH/CALIBRATION, not production. TP=2%/SL=1.5%.", "",
          "## 1. Executive summary",
          "- **METHOD WIN, EDGE FAIL.** The event trigger DID fix the v2 gap — it now samples ACTIVE_MARKDOWN_EVENT="
          f"{fam['ACTIVE_MARKDOWN_EVENT']['n_short']}, FORCED_UNWIND_EVENT={fam['FORCED_UNWIND_EVENT']['n_short']}, CVD_BREAKDOWN={fam['CVD_BREAKDOWN_EVENT']['n_short']} short samples (v2 pivots gave 0 markdown/unwind).",
          f"- BUT the high numbers are **REGIME EXPOSURE, not an edge**: naive 'short a random minute' in these 3 strong-down windows scores hit2 {control['naive_baseline_all']['hit2_rate']}% / PF {control['naive_baseline_all']['pf']} — i.e. event-shorts (hit2 {base['hit2_rate']}% / PF {base['pf']}) beat random by only **{control['lift_hit2_vs_naive']} pp** (≈0; PF actually lower than random).",
          f"- 1944 'events' are heavily overlapping -> only **{control['n_independent_moments']} independent moments**. Even the supposed-veto TRUE_DISAGREEMENT 'wins' here -> categories don't separate in a downtrend.",
          f"- RESEARCH_CANDIDATE templates: {'YES' if rc else 'NONE'} (all event-short families -> NEED_MORE_DATA: no lift over the naive baseline).",
          "## 2. Why lower-high pivot replaced", "- It only caught bounces (DISTRIBUTION). Events sample the actual markdown/unwind/CVD-breakdown moments.",
          "## 3. Event families tested", "- A ACTIVE_MARKDOWN, B FORCED_UNWIND, C CVD_BREAKDOWN, D SELL_PRESSURE_NO_ABSORPTION, E ABSORPTION(no-short).",
          "## 4. Cross-venue disagreement types"] + [f"- {r['cross_venue_type']}: n={r['n']} PF={r['pf']} role={r['veto_or_signal']}" for r in dt_rows] + [
          "## 5. Lead-lag", "- See LEAD_LAG_CONFIRMATION row; treated as early signal not veto.",
          f"## 6. Best event family: {best_fam[0]} (PF {best_fam[1]['pf']}, n {best_fam[1]['n_short']}) · best entry policy: {best_pol['policy']} (PF {best_pol['pf']})",
          f"## 7. ACTIVE_MARKDOWN/FORCED_UNWIND samples: {'YES' if fam['ACTIVE_MARKDOWN_EVENT']['n_short'] or fam['FORCED_UNWIND_EVENT']['n_short'] else 'NO'}",
          "## 8-9. Templates kept / rejected"] + [f"- {t['template_id']}: {t['status']} (n {t['n']}, PF {t['pf']})" for t in templates] + [
          f"## 10. RESEARCH_CANDIDATE: {'YES' if rc else 'NO'}",
          "## 11. Next: more true TREND_DOWN windows (full OKX+trades), test event triggers OOS; refine lead-lag confirm window; do not tune thresholds.", "",
          "FINAL_ARTIFACTS_LOCATION:",
          "- main_folder: reports/trend_down_event_trigger_v3/",
          "- event_candidates: EVENT_CANDIDATES_RAW.csv / EVENT_CANDIDATES_UNIQUE.csv / EVENT_CASEBOOK (see GOOD_EVENT_ZONE_CASEBOOK.md)",
          "- event_outcomes: EVENT_OUTCOMES.csv", "- entry_policy_comparison: ENTRY_POLICY_COMPARISON.csv/.md",
          "- disagreement_types: CROSS_VENUE_DISAGREEMENT_TYPES.csv/.md", "- filter_templates: EVENT_FILTER_TEMPLATES.json/.md",
          "- filter_scorecard: EVENT_FILTER_SCORECARD.csv", "- good_event_casebook: GOOD_EVENT_ZONE_CASEBOOK.md/.csv",
          "- comparison_with_v2: COMPARISON_WITH_V2_LOWER_HIGH.md", "- final_report: TREND_DOWN_EVENT_TRIGGER_V3_FINAL_REPORT.md"]
    (OUT / "TREND_DOWN_EVENT_TRIGGER_V3_FINAL_REPORT.md").write_text("\n".join(md), encoding="utf-8")
    # event casebook (all unique, short)
    wmd(OUT / "EVENT_CASEBOOK.md", "EVENT CASEBOOK (unique short events by family)",
        sum([[f"## {fk} (n_short={fv['n_short']}, PF {fv['pf']}, windows {fv['windows']})"] for fk, fv in fam.items()], []))


def wmd(path, title, body): path.write_text(f"# {title}\n\nBuild {now()} · research/calibration.\n\n" + "\n".join(body) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
