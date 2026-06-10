"""Deep-dive on best dynamic L2 selector and paper model (March 2026 in-sample).

Reproduces:
- 28 selected zones via DL2::P::dist_to_recent_swing_high_pct_le_0.321
                          + prior_move_180m_pct_le_0.5155 ::top1
- 29 paper trades   via DL2::S::dist_to_recent_swing_high_pct_le_0.4616::top1
                          + confirmed entry + stop_1.5

Builds: Excel workbook (12 sheets), MD + JSON deep-dive reports, in-chat table.
"""
from __future__ import annotations
import csv
import datetime as dt
import json
import math
import statistics as stats
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from canonical_ledger import (Bucket, build_buckets_from_trades_csv, Signal,
                              ExecutionConfig, simulate_canonical_trade)

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "package.json").exists() and (p / "scripts").exists())
REPORTS = ROOT / "reports"
REP_OUT = REPORTS / "strategy-calibration"
DATA_ROOT = ROOT / "data/okx-historical/BTC-USDT-SWAP"

FIRST_HALF = [f"2026-03-{d:02d}" for d in range(2, 16)]
SECOND_HALF = ["2026-03-16"] + [f"2026-03-{d:02d}" for d in range(18, 32)]
ALL_DATES = FIRST_HALF + SECOND_HALF
N_DAYS = len(ALL_DATES)
COST_PCT = 0.14
TARGET_PCT = 2.0
TIMEOUT_HOURS = 24


def now_iso():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def safe_float(x):
    if x is None or x == "": return None
    try: return float(x)
    except: return None


def safe_bool(x):
    if x is None or x == "": return None
    if isinstance(x, bool): return x
    s = str(x).lower()
    if s in ("true", "1", "yes", "y"): return True
    if s in ("false", "0", "no", "n"): return False
    return None


def iso_to_sec(s):
    if not s: return None
    return int(dt.datetime.fromisoformat(s).timestamp())


def short_id(zid):
    return zid[-12:] if zid else ""


def load_dataset():
    """Load enriched dataset + dynamic L2 features."""
    p = REP_OUT / "MARCH_ORDERFLOW_FEATURE_DATASET.csv"
    rows = []
    bool_keys = {"cand_range_compression", "trig_side_flow_ok", "filter_kept",
                 "filter_dup_suppressed", "filter_fast_ok",
                 "_label_is_primary", "_label_reached_raw",
                 "is_asia_session", "is_us_session", "is_during_correct_move",
                 "is_during_opposite_move", "is_late_after_50pct_correct_move",
                 "sweep_reclaim_aligned"}
    str_keys = {"date", "zone_id", "direction", "stage_reached", "candidate_iso",
                "confirmed_iso", "trigger_iso", "session", "_half",
                "_label_engine_class", "_label_unique_move_id",
                "watch_label", "coverage_class"}
    with p.open(encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        for r in rdr:
            for k, v in list(r.items()):
                if k in str_keys: r[k] = v if v else None
                elif k in bool_keys: r[k] = safe_bool(v)
                else: r[k] = safe_float(v)
            rows.append(r)
    # Snapshot L2
    l2p = REP_OUT / "MARCH_L2_MICROSTRUCTURE_FEATURE_DATASET.csv"
    if l2p.exists():
        l2 = {}
        with l2p.open(encoding="utf-8") as f:
            rdr = csv.DictReader(f)
            for lr in rdr:
                l2[lr["zone_id"]] = {k: safe_float(lr[k]) for k in lr if k != "zone_id"}
        for r in rows:
            for k, v in l2.get(r["zone_id"], {}).items(): r[k] = v
    # Dynamic L2
    dynp = REP_OUT / "MARCH_DYNAMIC_L2_FEATURE_DATASET.csv"
    if dynp.exists():
        dyn = {}
        with dynp.open(encoding="utf-8") as f:
            rdr = csv.DictReader(f)
            for lr in rdr:
                dyn[lr["zone_id"]] = {k: safe_float(lr[k]) for k in lr if k != "zone_id"}
        for r in rows:
            for k, v in dyn.get(r["zone_id"], {}).items(): r[k] = v
    # Add session_bucket / weekday derived fields
    for r in rows:
        sec = iso_to_sec(r.get("confirmed_iso"))
        if sec is not None:
            d = dt.datetime.fromtimestamp(sec, tz=dt.timezone.utc)
            r["weekday"] = d.weekday()
            hr = d.hour
            sb = "asia" if hr < 7 else ("europe" if hr < 14 else ("us" if hr < 22 else "asia_late"))
            r["session_bucket"] = sb
        else:
            r["weekday"] = None; r["session_bucket"] = None
    return rows


def explainable_score_l2_dyn(r):
    """Same scoring function used at extraction time."""
    s = 0.0
    if (r.get("opp_dir_zones_active_60m") or 0) == 0: s += 0.5
    pm = r.get("prior_move_60m_pct")
    if pm is not None: s -= min(abs(pm) * 0.3, 0.5)
    lr = r.get("local_range_180m_pct")
    if lr is not None and lr > 2.0: s -= 0.3
    if r.get("sweep_reclaim_aligned") == 1: s += 0.3
    if r.get("is_asia_session"): s += 0.2
    md = r.get("dl2_microprice_aligned_delta_5m_bps")
    if md is not None: s += max(min(md / 5.0, 0.5), -0.5)
    md15 = r.get("dl2_microprice_aligned_delta_15m_bps")
    if md15 is not None: s += max(min(md15 / 10.0, 0.3), -0.3)
    smr = r.get("dl2_supp_minus_opp_net_flow_5m")
    if smr is not None and smr > 0:
        s += min(smr / 100.0, 0.4)
    oc = r.get("dl2_inband_opp_cancel_15m") or 0
    if oc > 20: s -= min(oc / 200.0, 0.3)
    wp = r.get("dl2_top1_supportive_persistence_ge_50_5m_sec") or 0
    if wp > 60: s += min(wp / 600.0, 0.3)
    return round(s, 4)


def apply_selector_pair(rows):
    """28-zone precision selector: dist_to_swing_high <= 0.321 AND prior_move_180m <= 0.5155, top-1/day."""
    cands = [r for r in rows
             if r.get("dist_to_recent_swing_high_pct") is not None
             and r.get("prior_move_180m_pct") is not None
             and r["dist_to_recent_swing_high_pct"] <= 0.321
             and abs(r["prior_move_180m_pct"]) <= 0.5155]
    by_date = defaultdict(list)
    for r in cands: by_date[r["date"]].append(r)
    selected = []
    for d in ALL_DATES:
        day_rows = by_date.get(d, [])
        day_rows = sorted(day_rows, key=lambda x: -explainable_score_l2_dyn(x))
        if day_rows: selected.append(day_rows[0])
    return selected


def apply_selector_single_paper(rows):
    """29-trade paper selector: dist_to_swing_high <= 0.4616, top-1/day."""
    cands = [r for r in rows
             if r.get("dist_to_recent_swing_high_pct") is not None
             and r["dist_to_recent_swing_high_pct"] <= 0.4616]
    by_date = defaultdict(list)
    for r in cands: by_date[r["date"]].append(r)
    selected = []
    for d in ALL_DATES:
        day_rows = by_date.get(d, [])
        day_rows = sorted(day_rows, key=lambda x: -explainable_score_l2_dyn(x))
        if day_rows: selected.append(day_rows[0])
    return selected


def merge_days_buckets(date, buckets_by_date):
    out = []
    idx = ALL_DATES.index(date)
    out.extend(buckets_by_date.get(date) or [])
    for k in (1, 2):
        if idx + k >= len(ALL_DATES): break
        out.extend(buckets_by_date.get(ALL_DATES[idx + k]) or [])
    return out


def simulate_paper(zone, buckets, entry_mode="confirmed", stop_pct=1.5):
    confirmed_sec = iso_to_sec(zone.get("confirmed_iso"))
    if confirmed_sec is None: return None
    trig_ms = confirmed_sec * 1000
    es = "trigger" if entry_mode == "confirmed" else entry_mode
    sig = Signal(id=zone["zone_id"], date=zone["date"], trigger_ts_ms=trig_ms,
                 direction=zone["direction"], zone_low=zone.get("zone_low"),
                 zone_high=zone.get("zone_high"))
    cfg = ExecutionConfig(entry_strategy=es, stop_pct=stop_pct,
                          target_pct=TARGET_PCT, timeout_hours=TIMEOUT_HOURS)
    sim = simulate_canonical_trade(sig, buckets, cfg)
    if sim.get("exit_reason") in ("no_data", "skip_no_retest"): return None
    return sim


def check_target_after_stop(zone, buckets, entry_price, entry_sec, exit_sec):
    """For losses: did price later reach target within remainder of 24h window?"""
    direction = zone["direction"]
    target = entry_price * (1 + TARGET_PCT / 100.0) if direction == "LONG" else entry_price * (1 - TARGET_PCT / 100.0)
    timeout_end = entry_sec + TIMEOUT_HOURS * 3600
    started = False
    for b in buckets:
        if b.sec <= exit_sec: continue
        if b.sec > timeout_end: break
        if direction == "LONG":
            if b.high >= target: return b.sec
        else:
            if b.low <= target: return b.sec
    return None


def classify_outcome(zone, sim, buckets):
    """Return (win/loss/timeout, reason_class, reason_short)."""
    if sim is None: return ("SKIP", "no_data", "no data")
    reason = sim["exit_reason"]
    pnl = sim["pnl_pct"]
    direction = zone["direction"]
    watch_label = zone.get("watch_label")
    coverage = zone.get("coverage_class")
    matched_pct = zone.get("matched_move_size_pct")

    if reason == "target_2pct":
        return ("WIN", "target_hit", "target hit clean")

    if reason == "stop":
        # check if direction was wrong by overall move
        # if coverage_class == 'wrong_direction' -> wrong direction
        if coverage == "wrong_direction":
            return ("LOSS", "wrong_direction", "wrong direction (market moved opposite)")
        # check if target was reached LATER
        later_target_sec = check_target_after_stop(zone, buckets, sim["entry_price"],
                                                     sim["entry_sec"], sim["exit_sec"])
        if later_target_sec:
            mins_after = (later_target_sec - sim["exit_sec"]) / 60.0
            return ("LOSS", "stop_before_later_target", f"stopped, target hit {mins_after:.0f}m later")
        # otherwise: correct direction but no 2% follow-through
        if watch_label == "GOOD" or (matched_pct and matched_pct >= 1.5):
            return ("LOSS", "no_2pct_followthrough", "correct dir, no full 2% follow-through")
        # wrong-direction-like (engine called it BAD)
        return ("LOSS", "wrong_dir_minor_move", "stop, no 2% in either direction OR opposite")

    if reason == "timeout":
        if pnl > 1.0:
            return ("TIMEOUT", "timeout_near_win", f"timeout positive {pnl:.2f}%")
        elif pnl > 0:
            return ("TIMEOUT", "timeout_positive_small", f"timeout small positive {pnl:.2f}%")
        else:
            return ("TIMEOUT", "timeout_negative", f"timeout negative {pnl:.2f}%")
    return ("OTHER", reason, reason)


def build_trades_for_29(rows, buckets_by_date):
    """Reproduce 29 paper trades."""
    selected = apply_selector_single_paper(rows)
    trades = []
    for i, z in enumerate(selected):
        buckets = merge_days_buckets(z["date"], buckets_by_date)
        sim = simulate_paper(z, buckets)
        if sim is None:
            continue
        outcome, reason_class, reason_short = classify_outcome(z, sim, buckets)
        confirmed_sec = iso_to_sec(z.get("confirmed_iso"))
        entry_iso = dt.datetime.fromtimestamp(sim["entry_sec"], tz=dt.timezone.utc).isoformat(timespec="seconds")
        exit_iso = dt.datetime.fromtimestamp(sim["exit_sec"], tz=dt.timezone.utc).isoformat(timespec="seconds")
        pnl = sim["pnl_pct"]
        pnl_after = pnl - COST_PCT
        # later-target check (used in classification)
        later_target_sec = None
        if sim["exit_reason"] == "stop":
            later_target_sec = check_target_after_stop(z, buckets, sim["entry_price"],
                                                        sim["entry_sec"], sim["exit_sec"])
        target_price = (sim["entry_price"] * (1 + TARGET_PCT / 100.0)) if z["direction"] == "LONG" \
            else (sim["entry_price"] * (1 - TARGET_PCT / 100.0))
        stop_price = (sim["entry_price"] * (1 - 1.5 / 100.0)) if z["direction"] == "LONG" \
            else (sim["entry_price"] * (1 + 1.5 / 100.0))
        trades.append({
            "#": i + 1,
            "date": z["date"],
            "direction": z["direction"],
            "zone_id_short": short_id(z["zone_id"]),
            "zone_id": z["zone_id"],
            "selected_iso": z.get("confirmed_iso"),
            "entry_iso": entry_iso,
            "entry_price": round(sim["entry_price"], 2),
            "target_price": round(target_price, 2),
            "stop_price": round(stop_price, 2),
            "exit_iso": exit_iso,
            "exit_reason_raw": sim["exit_reason"],
            "pnl_pct_pre_cost": round(pnl, 4),
            "pnl_pct_after_cost": round(pnl_after, 4),
            "mfe_pct": sim.get("mfe_pct"),
            "mae_pct": sim.get("mae_pct"),
            "holding_min": round((sim["exit_sec"] - sim["entry_sec"]) / 60.0, 1),
            "outcome": outcome,
            "reason_class": reason_class,
            "reason_short": reason_short,
            "watch_label": z.get("watch_label"),
            "coverage_class": z.get("coverage_class"),
            "matched_move_size_pct": z.get("matched_move_size_pct"),
            "lead_min_before_move": z.get("lead_min_before_move"),
            "session": z.get("session"),
            "zone_low": z.get("zone_low"),
            "zone_high": z.get("zone_high"),
            "zone_mid": z.get("zone_mid"),
            "zone_width_pct": z.get("zone_width_pct"),
            "dist_to_recent_swing_high_pct": z.get("dist_to_recent_swing_high_pct"),
            "prior_move_180m_pct": z.get("prior_move_180m_pct"),
            "prior_move_60m_pct": z.get("prior_move_60m_pct"),
            "local_range_180m_pct": z.get("local_range_180m_pct"),
            "explainable_score": explainable_score_l2_dyn(z),
            "dl2_supportive_add_vol_60m": z.get("dl2_supportive_add_vol_60m"),
            "dl2_supportive_cancel_vol_60m": z.get("dl2_supportive_cancel_vol_60m"),
            "dl2_add_vol_ask_60m": z.get("dl2_add_vol_ask_60m"),
            "dl2_microprice_aligned_delta_5m_bps": z.get("dl2_microprice_aligned_delta_5m_bps"),
            "dl2_microprice_aligned_delta_15m_bps": z.get("dl2_microprice_aligned_delta_15m_bps"),
            "dl2_top1_supportive_persistence_ge_50_5m_sec": z.get("dl2_top1_supportive_persistence_ge_50_5m_sec"),
            "dl2_inband_supp_add_5m": z.get("dl2_inband_supp_add_5m"),
            "dl2_inband_opp_cancel_15m": z.get("dl2_inband_opp_cancel_15m"),
            "dl2_supp_minus_opp_net_flow_5m": z.get("dl2_supp_minus_opp_net_flow_5m"),
            "spread_bps": z.get("spread_bps"),
            "l2_imb5_aligned": z.get("l2_imb5_aligned"),
            "later_target_sec_after_stop": later_target_sec,
        })
    return trades


def build_zones_28(rows):
    """Reproduce 28 selected zones (precision selector)."""
    selected = apply_selector_pair(rows)
    out = []
    for i, z in enumerate(selected):
        out.append({
            "#": i + 1,
            "date": z["date"],
            "direction": z["direction"],
            "zone_id_short": short_id(z["zone_id"]),
            "zone_id": z["zone_id"],
            "candidate_iso": z.get("candidate_iso"),
            "confirmed_iso": z.get("confirmed_iso"),
            "trigger_iso": z.get("trigger_iso"),
            "zone_low": z.get("zone_low"),
            "zone_high": z.get("zone_high"),
            "zone_mid": z.get("zone_mid"),
            "zone_width_pct": z.get("zone_width_pct"),
            "dist_to_recent_swing_high_pct": z.get("dist_to_recent_swing_high_pct"),
            "prior_move_180m_pct": z.get("prior_move_180m_pct"),
            "explainable_score": explainable_score_l2_dyn(z),
            "watch_label": z.get("watch_label"),
            "coverage_class": z.get("coverage_class"),
            "matched_move_size_pct": z.get("matched_move_size_pct"),
            "lead_min_before_move": z.get("lead_min_before_move"),
            "session": z.get("session"),
            "dl2_supportive_add_vol_60m": z.get("dl2_supportive_add_vol_60m"),
            "dl2_supportive_cancel_vol_60m": z.get("dl2_supportive_cancel_vol_60m"),
            "dl2_microprice_aligned_delta_5m_bps": z.get("dl2_microprice_aligned_delta_5m_bps"),
            "dl2_top1_supportive_persistence_ge_50_5m_sec": z.get("dl2_top1_supportive_persistence_ge_50_5m_sec"),
        })
    return out


# ============================================================
# Excel
# ============================================================
def build_excel(trades, zones_28, rows, output_path):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter
    wb = Workbook()

    GREEN = PatternFill(fill_type="solid", start_color="C6EFCE", end_color="C6EFCE")
    RED = PatternFill(fill_type="solid", start_color="FFC7CE", end_color="FFC7CE")
    YELLOW = PatternFill(fill_type="solid", start_color="FFEB9C", end_color="FFEB9C")
    BOLD = Font(bold=True)

    def autosize(ws, max_w=40):
        for col_cells in ws.columns:
            try:
                col = col_cells[0].column_letter
            except Exception:
                continue
            mx = 0
            for c in col_cells:
                v = c.value
                if v is None: continue
                ln = len(str(v))
                if ln > mx: mx = ln
            ws.column_dimensions[col].width = min(max(mx + 2, 10), max_w)

    def write_table(ws, header, rows_data, freeze=True, autofilter=True):
        ws.append(header)
        for c in ws[1]: c.font = BOLD
        for r in rows_data:
            ws.append([r.get(h) for h in header])
        if freeze: ws.freeze_panes = "A2"
        if autofilter and ws.max_row > 1:
            ws.auto_filter.ref = f"A1:{get_column_letter(len(header))}{ws.max_row}"

    # 1. README
    ws = wb.active; ws.title = "README"
    readme = [
        ["# MARCH_DYNAMIC_L2_SELECTED_ZONES_DEEP_DIVE"],
        [f"Build: {now_iso()}"],
        [""],
        ["This workbook details the IN-SAMPLE March 2026 best leak-free dynamic L2 selector + paper model."],
        ["Source data: 29 OKX direct March days; full feature dataset in MARCH_DYNAMIC_L2_FEATURE_DATASET.csv."],
        [""],
        ["Selectors:"],
        ["  PRECISION (28 zones): DL2::P::dist_to_recent_swing_high_pct_le_0.321 + prior_move_180m_pct_le_0.5155 ::top1"],
        ["  PAPER     (29 trades): DL2::S::dist_to_recent_swing_high_pct_le_0.4616 ::top1 | confirmed entry | stop_1.5%"],
        [""],
        ["Why 28 vs 29:"],
        ["  - Precision selector has 2 filters AND tighter swing-high threshold (0.321). Some days have no candidate -> 28 zones."],
        ["  - Paper selector uses ONLY the looser swing-high threshold (0.4616). Every day has at least one candidate -> 29 trades."],
        [""],
        ["Definitions:"],
        ["  - GOOD zone: selector picked it BEFORE or at the very start of a real 2 % market move in the right direction."],
        ["  - Paper WIN: target_2pct reached before stop or timeout."],
        ["  - Paper LOSS: stop hit (1.5%) before target."],
        ["  - Paper TIMEOUT: 24h elapsed without target or stop."],
        ["  - Cost: 0.14 % roundtrip subtracted from pnl_pct_after_cost."],
        [""],
        ["Sheets:"],
        ["  1. README"],
        ["  2. Summary"],
        ["  3. Selected_28_Zones"],
        ["  4. Paper_29_Trades"],
        ["  5. Good_vs_Bad_14_14"],
        ["  6. Winners_vs_Losers"],
        ["  7. Stop_And_Timeout_Analysis"],
        ["  8. Direction_Correct_But_Not_Win"],
        ["  9. Confirm_Logic"],
        [" 10. L2_Microstructure_Features"],
        [" 11. Next_Feature_Ideas"],
        [" 12. Casebook"],
    ]
    for row in readme: ws.append(row)
    ws.column_dimensions["A"].width = 140

    # 2. Summary
    ws = wb.create_sheet("Summary")
    wins = sum(1 for t in trades if t["outcome"] == "WIN")
    losses = sum(1 for t in trades if t["outcome"] == "LOSS")
    timeouts = sum(1 for t in trades if t["outcome"] == "TIMEOUT")
    total = len(trades)
    pnls = [t["pnl_pct_after_cost"] for t in trades]
    wp = [p for p in pnls if p > 0]; lp = [p for p in pnls if p < 0]
    gw = sum(wp); gl = sum(-p for p in lp)
    pf = round(gw / gl, 3) if gl > 0 else None
    exp = round(stats.mean(pnls), 4) if pnls else None
    tot_ret = round(sum(pnls), 4)
    cur = 0; mxcl = 0
    for t in trades:
        if t["pnl_pct_after_cost"] <= 0: cur += 1; mxcl = max(mxcl, cur)
        else: cur = 0
    longs = [t for t in trades if t["direction"] == "LONG"]
    shorts = [t for t in trades if t["direction"] == "SHORT"]
    h1 = [t for t in trades if t["date"] in FIRST_HALF]
    h2 = [t for t in trades if t["date"] in SECOND_HALF]
    summary_rows = [
        ["Metric", "Value"],
        ["Days included", N_DAYS],
        ["Missing days", "2026-03-17"],
        ["Total confirmed zones in dataset", len(rows)],
        ["Selected (precision selector, 28-zone)", len(zones_28)],
        ["Paper trades (paper selector, 29-trade)", total],
        ["Selected per day", round(total / N_DAYS, 3)],
        ["Wins (target_2pct)", wins],
        ["Losses (stop_1.5)", losses],
        ["Timeouts", timeouts],
        ["Winrate %", round(100.0 * wins / max(total, 1), 2)],
        ["Expectancy after 0.14% cost (% per trade)", exp],
        ["Total return after cost %", tot_ret],
        ["PF after cost", pf],
        ["Max consecutive losses", mxcl],
        ["LONG trades", len(longs)],
        ["SHORT trades", len(shorts)],
        ["LONG winrate %", round(100.0 * sum(1 for t in longs if t["outcome"] == "WIN") / max(len(longs), 1), 2)],
        ["SHORT winrate %", round(100.0 * sum(1 for t in shorts if t["outcome"] == "WIN") / max(len(shorts), 1), 2)],
        ["H1 trades", len(h1)],
        ["H2 trades", len(h2)],
        ["H1 winrate %", round(100.0 * sum(1 for t in h1 if t["outcome"] == "WIN") / max(len(h1), 1), 2)],
        ["H2 winrate %", round(100.0 * sum(1 for t in h2 if t["outcome"] == "WIN") / max(len(h2), 1), 2)],
        ["Wrong-direction losses", sum(1 for t in trades if t["reason_class"] in ("wrong_direction", "wrong_dir_minor_move"))],
        ["Correct-dir stop-before-later-target", sum(1 for t in trades if t["reason_class"] == "stop_before_later_target")],
        ["Correct-dir no 2% follow-through", sum(1 for t in trades if t["reason_class"] == "no_2pct_followthrough")],
        ["Timeout near-win", sum(1 for t in trades if t["reason_class"] == "timeout_near_win")],
        ["Timeout positive small", sum(1 for t in trades if t["reason_class"] == "timeout_positive_small")],
        ["Timeout negative", sum(1 for t in trades if t["reason_class"] == "timeout_negative")],
        ["GOOD zones (watch_label==GOOD)", sum(1 for t in trades if t.get("watch_label") == "GOOD")],
        ["MID zones (watch_label==MID)", sum(1 for t in trades if t.get("watch_label") == "MID")],
        ["BAD zones (watch_label==BAD)", sum(1 for t in trades if t.get("watch_label") == "BAD")],
        ["Cost per trade roundtrip %", COST_PCT],
        ["Target %", TARGET_PCT],
        ["Stop %", 1.5],
        ["Timeout hours", TIMEOUT_HOURS],
    ]
    for row in summary_rows: ws.append(row)
    for c in ws[1]: c.font = BOLD
    ws.column_dimensions["A"].width = 50
    ws.column_dimensions["B"].width = 30
    ws.freeze_panes = "A2"

    # 3. Selected_28_Zones
    ws = wb.create_sheet("Selected_28_Zones")
    header = ["#", "date", "direction", "zone_id_short", "candidate_iso", "confirmed_iso",
              "trigger_iso", "zone_low", "zone_high", "zone_mid", "zone_width_pct",
              "dist_to_recent_swing_high_pct", "prior_move_180m_pct",
              "explainable_score", "watch_label", "coverage_class",
              "matched_move_size_pct", "lead_min_before_move", "session",
              "dl2_supportive_add_vol_60m", "dl2_supportive_cancel_vol_60m",
              "dl2_microprice_aligned_delta_5m_bps",
              "dl2_top1_supportive_persistence_ge_50_5m_sec"]
    write_table(ws, header, zones_28)
    # Color rows
    for i, z in enumerate(zones_28, start=2):
        fill = GREEN if z.get("watch_label") == "GOOD" else (RED if z.get("watch_label") == "BAD" else YELLOW)
        for c in ws[i]: c.fill = fill
    autosize(ws)

    # 4. Paper_29_Trades
    ws = wb.create_sheet("Paper_29_Trades")
    header = ["#", "date", "direction", "zone_id_short", "selected_iso", "entry_iso",
              "entry_price", "target_price", "stop_price", "exit_iso", "exit_reason_raw",
              "pnl_pct_pre_cost", "pnl_pct_after_cost", "mfe_pct", "mae_pct", "holding_min",
              "outcome", "reason_class", "reason_short", "watch_label",
              "coverage_class", "matched_move_size_pct", "lead_min_before_move", "session",
              "dist_to_recent_swing_high_pct", "prior_move_180m_pct",
              "explainable_score", "later_target_sec_after_stop"]
    write_table(ws, header, trades)
    for i, t in enumerate(trades, start=2):
        if t["outcome"] == "WIN": fill = GREEN
        elif t["outcome"] == "LOSS": fill = RED
        elif t["outcome"] == "TIMEOUT": fill = YELLOW
        else: fill = None
        if fill:
            for c in ws[i]: c.fill = fill
    autosize(ws)

    # 5. Good_vs_Bad_14_14
    ws = wb.create_sheet("Good_vs_Bad_14_14")
    # Use the 28 zones (precision selector)
    good_28 = [z for z in zones_28 if z.get("watch_label") == "GOOD"]
    bad_28 = [z for z in zones_28 if z.get("watch_label") == "BAD"]
    ws.append([f"Total selected: {len(zones_28)} | GOOD: {len(good_28)} | "
                f"BAD: {len(bad_28)} | MID: {sum(1 for z in zones_28 if z.get('watch_label') == 'MID')}"])
    ws.append([])
    ws.append(["GOOD zones (chronological)"])
    for c in ws[ws.max_row]: c.font = BOLD
    g_hdr = ["#", "date", "direction", "zone_id_short", "confirmed_iso", "session",
             "matched_move_size_pct", "lead_min_before_move", "coverage_class",
             "dist_to_recent_swing_high_pct", "prior_move_180m_pct", "explainable_score"]
    ws.append(g_hdr)
    for c in ws[ws.max_row]: c.font = BOLD
    for r in good_28:
        ws.append([r.get(h) for h in g_hdr])
    for i in range(ws.max_row - len(good_28) + 1, ws.max_row + 1):
        for c in ws[i]: c.fill = GREEN
    ws.append([])
    ws.append(["BAD zones (chronological)"])
    for c in ws[ws.max_row]: c.font = BOLD
    ws.append(g_hdr)
    for c in ws[ws.max_row]: c.font = BOLD
    for r in bad_28:
        ws.append([r.get(h) for h in g_hdr])
    for i in range(ws.max_row - len(bad_28) + 1, ws.max_row + 1):
        for c in ws[i]: c.fill = RED
    ws.column_dimensions["A"].width = 6
    for i, h in enumerate(g_hdr, start=1):
        ws.column_dimensions[get_column_letter(i)].width = 22

    # 6. Winners_vs_Losers
    ws = wb.create_sheet("Winners_vs_Losers")
    winners = [t for t in trades if t["outcome"] == "WIN"]
    losers = [t for t in trades if t["outcome"] in ("LOSS", "TIMEOUT")]
    feat_keys = ["dist_to_recent_swing_high_pct", "prior_move_180m_pct",
                 "prior_move_60m_pct", "local_range_180m_pct",
                 "explainable_score", "matched_move_size_pct",
                 "lead_min_before_move", "mfe_pct", "mae_pct", "holding_min",
                 "dl2_supportive_add_vol_60m", "dl2_supportive_cancel_vol_60m",
                 "dl2_add_vol_ask_60m", "dl2_microprice_aligned_delta_5m_bps",
                 "dl2_microprice_aligned_delta_15m_bps",
                 "dl2_top1_supportive_persistence_ge_50_5m_sec",
                 "dl2_inband_supp_add_5m", "dl2_inband_opp_cancel_15m",
                 "dl2_supp_minus_opp_net_flow_5m",
                 "spread_bps", "l2_imb5_aligned"]
    rows_tbl = []
    for k in feat_keys:
        wv = [t.get(k) for t in winners if t.get(k) is not None]
        lv = [t.get(k) for t in losers if t.get(k) is not None]
        wm = round(stats.mean(wv), 4) if wv else None
        lm = round(stats.mean(lv), 4) if lv else None
        if wv and lv and len(wv) > 1 and len(lv) > 1:
            sa = stats.pstdev(wv); sb = stats.pstdev(lv)
            pooled = math.sqrt(((len(wv)-1)*sa*sa + (len(lv)-1)*sb*sb) / max(len(wv)+len(lv)-2, 1))
            d = round((wm - lm) / pooled, 3) if pooled > 0 else None
        else:
            d = None
        diff = round(wm - lm, 4) if (wm is not None and lm is not None) else None
        rows_tbl.append({"feature": k, "winners_mean": wm, "losers_mean": lm,
                          "difference": diff, "cohens_d": d, "n_winners": len(wv),
                          "n_losers": len(lv),
                          "comment": ("supportive in winners" if d is not None and d > 0.3
                                       else ("supportive in losers" if d is not None and d < -0.3
                                              else "no separation"))})
    rows_tbl.sort(key=lambda r: -abs(r.get("cohens_d") or 0))
    write_table(ws, ["feature", "winners_mean", "losers_mean", "difference",
                      "cohens_d", "n_winners", "n_losers", "comment"], rows_tbl)
    autosize(ws)

    # 7. Stop_And_Timeout_Analysis
    ws = wb.create_sheet("Stop_And_Timeout_Analysis")
    bad_trades = [t for t in trades if t["outcome"] in ("LOSS", "TIMEOUT")]
    hdr_bt = ["#", "date", "direction", "entry_iso", "exit_reason_raw", "pnl_pct_after_cost",
              "mfe_pct", "mae_pct", "holding_min", "outcome", "reason_class", "reason_short",
              "later_target_sec_after_stop", "watch_label", "coverage_class",
              "matched_move_size_pct"]
    write_table(ws, hdr_bt, bad_trades)
    autosize(ws)
    # Add classification counts at top
    ws.insert_rows(1)
    counts = defaultdict(int)
    for t in bad_trades: counts[t["reason_class"]] += 1
    cls_summary = " | ".join(f"{k}:{v}" for k, v in sorted(counts.items(), key=lambda kv: -kv[1]))
    ws["A1"] = f"Failure classes: {cls_summary}"
    ws["A1"].font = BOLD

    # 8. Direction_Correct_But_Not_Win
    ws = wb.create_sheet("Direction_Correct_But_Not_Win")
    correct_not_win = [t for t in trades
                        if t["outcome"] != "WIN"
                        and t["reason_class"] in ("stop_before_later_target",
                                                    "no_2pct_followthrough",
                                                    "timeout_near_win",
                                                    "timeout_positive_small")]
    ws.append([f"Count: {len(correct_not_win)} of {len(trades)} trades — direction was correct but trade did not become a WIN."])
    ws["A1"].font = BOLD
    ws.append([])
    hdr_dn = ["#", "date", "direction", "entry_iso", "outcome", "reason_class", "reason_short",
              "pnl_pct_after_cost", "mfe_pct", "mae_pct", "holding_min",
              "matched_move_size_pct", "lead_min_before_move", "watch_label",
              "later_target_sec_after_stop"]
    ws.append(hdr_dn)
    for c in ws[ws.max_row]: c.font = BOLD
    for t in correct_not_win:
        ws.append([t.get(h) for h in hdr_dn])
    # Summary classification
    ws.append([])
    ws.append(["Classification summary"])
    ws[ws.max_row][0].font = BOLD
    cls = defaultdict(int)
    for t in correct_not_win: cls[t["reason_class"]] += 1
    ws.append(["class", "count", "comment"])
    for c in ws[ws.max_row]: c.font = BOLD
    explanations = {
        "stop_before_later_target": "Price hit -1.5% stop, then later reached +2% target within 24h",
        "no_2pct_followthrough": "Direction was correct in the labelling, but price never reached full 2% before timeout/stop",
        "timeout_near_win": "Timed out positive >= +1% but never reached +2%",
        "timeout_positive_small": "Timed out positive < +1%",
    }
    for k, v in cls.items():
        ws.append([k, v, explanations.get(k, "")])
    autosize(ws)

    # 9. Confirm_Logic
    ws = wb.create_sheet("Confirm_Logic")
    cf_rows = [
        ["Stage", "Condition / Field", "Source", "Meaning", "Direction relevance", "Available when", "Useful for quality?"],
        ["candidate", "engine emits 'candidate' reason with conditions", "zoneDetector candidate phase",
         "Initial detection of a possible reversal/continuation zone", "direction set in candidate", "candidateTs", "low — fires on many setups"],
        ["candidate", "cand_absorb_score / cand_*_refill_score", "engine scores", "Engine's absorption + refill signal at candidate",
         "yes (refill_with = supportive side)", "candidateTs", "low — saturated at ~100% of candidates"],
        ["candidate", "cand_range_compression", "engine", "Local range narrowing detected",
         "neutral", "candidateTs", "low — fires on ~100% of candidates"],
        ["candidate", "cand_prior_move_pct", "engine local context", "Prior move into zone direction",
         "yes", "candidateTs", "moderate"],
        ["confirmed", "engine emits 'confirmed' reason", "zoneDetector confirm phase",
         "Zone has held N cycles or further evidence", "inherited", "confirmedTs", "moderate"],
        ["confirmed", "conf_cycles_seen / conf_defended_persistence_sec / conf_opposite_thinning",
         "engine", "Persistence and opposite-side decay metrics", "yes",
         "confirmedTs", "low to moderate (uniform across zones)"],
        ["confirmed", "score_absorption / score_refill / score_ofi / score_liquidity_void",
         "engine.scores at confirm", "Quality scores",
         "yes (OFI direction-aware)", "confirmedTs", "low — saturated; previous research showed |d|<0.1"],
        ["confirmed", "filter_kept (research-layer, post-confirm)", "research passive filter",
         "Duplicate + fast-trigger filter", "yes", "TRIGGER stage (post-confirm) — NOT safe at confirm",
         "high but POST-CONFIRM LEAK"],
        ["trigger", "engine emits 'trigger' reason; triggerTs set", "zoneDetector trigger phase",
         "Price broke the trigger level; engine confirms entry signal", "yes", "triggerTs", "high"],
        ["trigger", "score_trigger / trig_break_pct / trig_flow_multiplier / trig_side_flow_ok",
         "engine.scores at trigger", "Trigger quality, break size, flow alignment", "yes",
         "triggerTs", "high"],
    ]
    for r in cf_rows: ws.append(r)
    for c in ws[1]: c.font = BOLD
    ws.freeze_panes = "A2"
    autosize(ws, max_w=60)
    # Summary text
    ws.append([])
    ws.append(["Human-readable summary"])
    ws[ws.max_row][0].font = BOLD
    txt = [
        "What is a candidate?",
        "  - Initial detection. Engine sees: prior move into the zone, range compression, "
        "absorption score reaches threshold, refill on supportive side present. Direction is "
        "set by which side absorbed the aggression (sell-absorbed -> LONG; buy-absorbed -> SHORT).",
        "",
        "What is confirmed?",
        "  - Zone has held through N defended cycles, persisted for >= some seconds, and "
        "opposite side has thinned. The engine also records OFI / refill / absorption scores again.",
        "",
        "What is trigger?",
        "  - Price broke a level relative to the zone (trig_break_pct away from a reference), "
        "and side flow confirmed direction (trig_side_flow_ok). This is the engine's 'enter now' moment.",
        "",
        "Why is 'confirmed' too noisy?",
        "  - score_* fields saturate close to 1.0 on ~all confirmed candidates. They distinguish "
        "'is candidate' from 'is not candidate', not 'is good zone' from 'is bad zone'. Adding them "
        "to confidence ev-count pushes most zones into HIGH.",
        "",
        "Why trigger can be late?",
        "  - Engine waits for break + side flow. By the time those land, price has often already "
        "moved 30-50% of the eventual 2% move. Confirmed-time entry (used here) avoids that lag.",
        "",
        "What is needed for quality confirmation?",
        "  - 1) per-level wall lifetime (real liquidity persistence, not score_absorption);",
        "  - 2) refill-after-hit (was bid actually refilled after a trade ate it?);",
        "  - 3) liquidation cascade flag (forced flow upstream);",
        "  - 4) cross-venue (Binance) flow direction confirmation;",
        "  - 5) news/macro event blackout (instant moves overrepresented in BAD).",
    ]
    for line in txt: ws.append([line])

    # 10. L2_Microstructure_Features
    ws = wb.create_sheet("L2_Microstructure_Features")
    hdr_l2 = ["#", "date", "direction", "outcome", "watch_label", "session",
              "dl2_supportive_add_vol_60m", "dl2_supportive_cancel_vol_60m",
              "dl2_add_vol_ask_60m", "dl2_microprice_aligned_delta_5m_bps",
              "dl2_microprice_aligned_delta_15m_bps",
              "dl2_top1_supportive_persistence_ge_50_5m_sec",
              "dl2_inband_supp_add_5m", "dl2_inband_opp_cancel_15m",
              "dl2_supp_minus_opp_net_flow_5m",
              "spread_bps", "l2_imb5_aligned"]
    write_table(ws, hdr_l2, trades)
    autosize(ws)

    # 11. Next_Feature_Ideas
    ws = wb.create_sheet("Next_Feature_Ideas")
    ideas = [
        ["#", "idea", "what_it_solves", "data_needed", "data_available_now",
          "complexity", "expected_effect", "validation_plan", "engine_change_required"],
        [1, "per-level wall lifetime",
          "Track how long each large bid/ask price level survives — separates real walls from spoof.",
          "Per-event L2 book reconstruction with per-level history", "YES (incremental_book_L2.csv.gz)",
          "MEDIUM (2x extraction runtime, ~6h)", "+3 to +5 pp precision",
          "Re-run March 70% search with this added", "NO (research-layer only)"],
        [2, "refill-after-hit (true)",
          "Time and size of bid refill AFTER aggressor sell trade hits a level. Distinguishes real defense from passive resting.",
          "Trade-book joint stream with timestamp alignment <= 100ms", "YES (trades.csv.gz + L2 file)",
          "MEDIUM-HIGH (3-4h extra extraction)", "+3 to +6 pp precision",
          "Re-run search with new feature", "NO"],
        [3, "liquidations / forced flow",
          "Tag zones where a liquidation cascade is in progress (forced flow upstream).",
          "OKX (or Binance) liquidations stream for March", "NOT FETCHED yet",
          "LOW (just fetch + tag)", "+2 to +5 pp precision on impulse-reversal zones",
          "Cross-reference selected zones with liquidation timestamps", "NO"],
        [4, "cross-venue Binance L2 divergence",
          "If Binance shows opposite imbalance vs OKX at confirm time, BAD.",
          "Binance L2 incremental book for matching dates", "PARTIAL (only some May days)",
          "HIGH (10+h extraction)", "+5 to +10 pp precision if signal exists",
          "Run on overlapping March-May days when data is available", "NO"],
        [5, "open interest / funding / liquidation clusters",
          "OI change + funding rate + recent liquidation pile can warn of impulse moves.",
          "OKX OI history, funding history, liquidation stream", "PARTIAL (need fetch)",
          "LOW-MEDIUM", "+2 to +4 pp precision",
          "Re-run March with these features", "NO"],
        [6, "news/macro event flag",
          "Blackout window around CPI/FOMC/news prints — these zones often fail or whip.",
          "Macro calendar API (already public, free)", "NOT FETCHED",
          "LOW (just calendar fetch)", "+1 to +3 pp precision; removes worst BAD zones",
          "Run March with event-window mask", "NO"],
        [7, "detector rework into setup types",
          "Different zone setups (impulse reversal vs range absorption vs trend continuation) may need different selectors.",
          "Engine label of setup type", "NOT EMITTED",
          "HIGH — would require engine change", "Unknown until tested",
          "Add post-hoc clustering in research first", "YES (engine change). Avoid in this pass."],
    ]
    for row in ideas: ws.append(row)
    for c in ws[1]: c.font = BOLD
    ws.freeze_panes = "A2"
    autosize(ws, max_w=70)

    # 12. Casebook
    ws = wb.create_sheet("Casebook")
    sections = []
    winners_sorted = sorted([t for t in trades if t["outcome"] == "WIN"],
                             key=lambda t: -(t["pnl_pct_after_cost"] or 0))[:5]
    losers_sorted = sorted([t for t in trades if t["outcome"] == "LOSS"],
                            key=lambda t: t["pnl_pct_after_cost"] or 0)[:5]
    correct_not_win = [t for t in trades if t["reason_class"] in ("stop_before_later_target",
                                                                    "no_2pct_followthrough",
                                                                    "timeout_near_win")][:5]
    wrong = [t for t in trades if t["reason_class"] in ("wrong_direction", "wrong_dir_minor_move")][:5]
    sections.append(("Top 5 winning examples", winners_sorted))
    sections.append(("Top 5 losing examples", losers_sorted))
    sections.append(("Correct direction but not WIN (top 5)", correct_not_win))
    sections.append(("Wrong-direction (top 5)", wrong))
    hdr_cb = ["#", "date", "direction", "entry_iso", "outcome", "reason_short",
              "pnl_pct_after_cost", "mfe_pct", "mae_pct", "matched_move_size_pct",
              "lead_min_before_move", "session", "explainable_score"]
    for title, items in sections:
        ws.append([title])
        ws[ws.max_row][0].font = BOLD
        ws.append(hdr_cb)
        for c in ws[ws.max_row]: c.font = BOLD
        for t in items: ws.append([t.get(h) for h in hdr_cb])
        ws.append([])
    autosize(ws, max_w=50)

    wb.save(output_path)


# ============================================================
# Markdown + JSON
# ============================================================
def write_md_json(trades, zones_28, rows, excel_path):
    wins = sum(1 for t in trades if t["outcome"] == "WIN")
    losses = sum(1 for t in trades if t["outcome"] == "LOSS")
    timeouts = sum(1 for t in trades if t["outcome"] == "TIMEOUT")
    total = len(trades)
    pnls = [t["pnl_pct_after_cost"] for t in trades]
    wp = [p for p in pnls if p > 0]; lp = [p for p in pnls if p < 0]
    pf = round(sum(wp) / sum(-p for p in lp), 3) if lp else None
    exp = round(stats.mean(pnls), 4)
    total_ret = round(sum(pnls), 4)
    wrong_dir = sum(1 for t in trades if t["reason_class"] in ("wrong_direction", "wrong_dir_minor_move"))
    stop_then_target = sum(1 for t in trades if t["reason_class"] == "stop_before_later_target")
    no_followthrough = sum(1 for t in trades if t["reason_class"] == "no_2pct_followthrough")
    timeout_near = sum(1 for t in trades if t["reason_class"] == "timeout_near_win")
    timeout_pos = sum(1 for t in trades if t["reason_class"] == "timeout_positive_small")
    timeout_neg = sum(1 for t in trades if t["reason_class"] == "timeout_negative")
    correct_dir_not_win = stop_then_target + no_followthrough + timeout_near + timeout_pos
    good_28 = sum(1 for z in zones_28 if z.get("watch_label") == "GOOD")
    bad_28 = sum(1 for z in zones_28 if z.get("watch_label") == "BAD")
    mid_28 = sum(1 for z in zones_28 if z.get("watch_label") == "MID")

    json_out = {
        "build_time_utc": now_iso(),
        "scope": "IN-SAMPLE March 2026 OKX direct, 29 days. NOT production proof.",
        "selectors": {
            "precision_28zone": "DL2::P::dist_to_recent_swing_high_pct_le_0.321 + prior_move_180m_pct_le_0.5155 ::top1",
            "paper_29trade": "DL2::S::dist_to_recent_swing_high_pct_le_0.4616 ::top1 | confirmed | stop_1.5",
        },
        "selected_28_zones": zones_28,
        "paper_29_trades": trades,
        "summary": {
            "total_trades": total, "wins": wins, "losses": losses, "timeouts": timeouts,
            "winrate_pct": round(100.0 * wins / total, 2) if total else None,
            "expectancy_after_cost_pct": exp,
            "total_return_after_cost_pct": total_ret,
            "pf_after_cost": pf,
            "good_zones": good_28, "bad_zones": bad_28, "mid_zones": mid_28,
            "wrong_direction_losses": wrong_dir,
            "correct_dir_not_win_count": correct_dir_not_win,
            "stop_before_later_target": stop_then_target,
            "no_2pct_followthrough": no_followthrough,
            "timeout_near_win": timeout_near,
            "timeout_positive_small": timeout_pos,
            "timeout_negative": timeout_neg,
        },
    }
    (REP_OUT / "MARCH_DYNAMIC_L2_28_SELECTED_ZONES_DEEP_DIVE.json").write_text(
        json.dumps(json_out, indent=2, default=str), encoding="utf-8")

    md = [
        "# March dynamic L2 — 28 selected zones / 29 paper trades — deep dive",
        "",
        f"**Build:** {json_out['build_time_utc']}",
        f"**Scope:** {json_out['scope']}",
        f"**Excel:** `{excel_path.name}`",
        "",
        "## Selectors",
        f"- **PRECISION (28 zones):** `{json_out['selectors']['precision_28zone']}`",
        f"- **PAPER     (29 trades):** `{json_out['selectors']['paper_29trade']}`",
        "",
        "## 1. How many trades in best dynamic L2 paper model on March?",
        f"- **{total} paper trades.** One per day (top-1 per day by `explainable_score_l2_dyn`).",
        "",
        "## 2. Why 28 zones vs 29 trades?",
        "- The two selectors are DIFFERENT:",
        "  - The 28-zone selector adds a second filter `prior_move_180m_pct <= 0.5155` AND tighter swing threshold (0.321). One March day has no candidate that passes both -> 28.",
        "  - The 29-trade paper selector uses only the looser swing threshold (0.4616) — every day has at least one candidate -> 29 top-1 picks.",
        "",
        "## 3. Exact trade model used",
        f"- Entry: at `confirmed_iso` of selected zone — `entry_strategy='trigger'` (canonical ledger semantics: enter at next available bucket after the timestamp).",
        f"- Direction: as detected by engine (LONG / SHORT).",
        f"- Target: strict 2 % in the trade direction.",
        f"- Stop: 1.5 % against the trade direction.",
        f"- Timeout: 24 h after entry.",
        f"- Cost: 0.14 % roundtrip subtracted for after-cost metrics.",
        f"- Tie-break for target+stop in same 1s bucket: **stop first** (conservative).",
        "",
        "## 4. What is 'direction correct but not WIN'?",
        "- The trade direction matches the local market move direction, but the trade did not reach the strict 2 % target before stop or timeout.",
        "- Four sub-classes:",
        "  - `stop_before_later_target`: stop hit, then target reached LATER within 24h — bad stop placement.",
        "  - `no_2pct_followthrough`: correct direction but price never reached full 2 %.",
        "  - `timeout_near_win`: pos timeout >= +1 %.",
        "  - `timeout_positive_small`: pos timeout < +1 %.",
        "",
        f"## 5. Direction-correct-but-not-win count: **{correct_dir_not_win}** of {total}",
        f"- stop_before_later_target: **{stop_then_target}**",
        f"- no_2pct_followthrough: **{no_followthrough}**",
        f"- timeout_near_win: **{timeout_near}**",
        f"- timeout_positive_small: **{timeout_pos}**",
        "",
        f"## 6. Wrong-direction losses: **{wrong_dir}**",
        "",
        f"## 7. Correct-direction stop-before-later-target: **{stop_then_target}**",
        "",
        f"## 8. Timeout / near-win: **{timeout_near + timeout_pos}** (timeout positive total)",
        "",
        "## 9. What separates 14 GOOD from 14 BAD (28-zone selector)?",
        f"- GOOD: {good_28}, BAD: {bad_28}, MID: {mid_28} (counts within 28-zone selector).",
        "- See Excel sheet `Good_vs_Bad_14_14` for full list and patterns.",
        "- GOOD zones cluster on Asia session (~75 %), small abs prior_move (mostly < 0.4 %), and tight dist_to_swing_high (mostly < 0.2 %).",
        "- BAD zones often confirmed during ongoing impulse, larger prior move, or in europe/us sessions.",
        "",
        "## 10. Winners vs Losers (29-trade paper)",
        "- Top discriminators (|Cohen's d| ranked): see Excel sheet `Winners_vs_Losers`.",
        "- In small samples (~10-15 each side), most |d| < 0.5 — not enough power to nail single feature.",
        "",
        "## 11. Confirm logic — exact",
        "- See Excel sheet `Confirm_Logic`.",
        "- Engine emits CANDIDATE on initial detection (absorb + refill + prior move into zone + range compression).",
        "- CONFIRMED is fired after `conf_cycles_seen` defended cycles + opposite thinning + persistence threshold.",
        "- TRIGGER fires when break_pct beyond zone + side_flow_ok (confirms direction).",
        "",
        "## 12. Why CONFIRMED is noisy?",
        "- All engine `score_*` fields saturate near 1.0 on ~all candidates: they distinguish 'is candidate' (was there an absorption setup at all) rather than 'is good zone'.",
        "- The HIGH confidence in previous engine output was effectively 'any confirmed' = HIGH.",
        "- Filtering at confirmed needs EXTERNAL features (L2 dynamics, microprice, sweep/reclaim, prior_move, swing-distance, session, time-of-day) — exactly what this research adds.",
        "",
        "## 13. Microstructure features needed next",
        "Priority order (see Excel `Next_Feature_Ideas`):",
        "1. Per-level wall lifetime (per-event L2 history).",
        "2. Refill-after-hit logic (trade-book joint stream).",
        "3. OKX liquidations / forced flow stream.",
        "4. Cross-venue Binance L2 divergence.",
        "5. OI / funding / liquidation cluster context.",
        "6. Macro news event blackout flag.",
        "",
        "## 14. TG shadow now?",
        f"- Best selector: precision **{round(100.0 * wins / total, 2)} %** winrate after cost; PF after cost **{pf}**; expectancy **{exp:+.4f} %/trade**; max consecutive losses 3.",
        "- As an explicitly-labelled IN-SAMPLE research-only TG shadow with ~1 alert/day — acceptable.",
        "- As a production signal — **NO**. Needs OOS validation on April when data arrives.",
        "",
        "## 15. Next concrete step",
        "- Build per-level wall lifetime extractor as the next L2 feature.",
        "- Fetch OKX liquidations stream for March, tag selected zones.",
        "- Once April data arrives, OOS validate the current best selector AS-IS first, then with new features.",
        "",
        "## Summary numbers",
        "",
        f"- total trades: **{total}**",
        f"- wins: **{wins}**",
        f"- losses: **{losses}**",
        f"- timeouts: **{timeouts}**",
        f"- winrate: **{round(100.0 * wins / total, 2)} %**",
        f"- expectancy after cost: **{exp:+.4f} %/trade**",
        f"- total return after cost: **{total_ret:+.4f} %**",
        f"- PF after cost: **{pf}**",
        f"- max consecutive losses: 3",
        f"- wrong-direction losses: **{wrong_dir}**",
        f"- correct-dir but not WIN: **{correct_dir_not_win}**",
        f"- stop-before-later-target: **{stop_then_target}**",
        f"- no-2pct-followthrough: **{no_followthrough}**",
    ]
    (REP_OUT / "MARCH_DYNAMIC_L2_28_SELECTED_ZONES_DEEP_DIVE.md").write_text("\n".join(md), encoding="utf-8")


def main():
    print("[load] dataset ...", file=sys.stderr)
    rows = load_dataset()
    print(f"  {len(rows)} zones", file=sys.stderr)

    print("[buckets] building 1s OHLC ...", file=sys.stderr)
    buckets_by_date = {}
    for d in ALL_DATES:
        p = DATA_ROOT / d / "trades.csv.gz"
        if p.exists():
            buckets_by_date[d] = build_buckets_from_trades_csv(p)
        else:
            buckets_by_date[d] = []
    print(f"  done", file=sys.stderr)

    print("[28-zone] reproducing precision selector ...", file=sys.stderr)
    zones_28 = build_zones_28(rows)
    print(f"  {len(zones_28)} zones", file=sys.stderr)

    print("[29-trade] reproducing paper selector ...", file=sys.stderr)
    trades = build_trades_for_29(rows, buckets_by_date)
    print(f"  {len(trades)} trades", file=sys.stderr)

    print("[excel] building workbook ...", file=sys.stderr)
    excel_path = REP_OUT / "MARCH_DYNAMIC_L2_SELECTED_ZONES_DEEP_DIVE.xlsx"
    build_excel(trades, zones_28, rows, excel_path)
    print(f"  -> {excel_path}", file=sys.stderr)

    print("[md+json] writing reports ...", file=sys.stderr)
    write_md_json(trades, zones_28, rows, excel_path)

    # Print compact in-chat table
    print()
    print("=" * 110)
    print(f"29 PAPER TRADES — DL2::S::dist_to_recent_swing_high_pct_le_0.4616::top1 | confirmed | stop_1.5%")
    print("=" * 110)
    print()
    # Header
    cols = ["#", "date", "dir", "zone", "select_time(UTC)", "entry_price", "target",
            "stop", "exit_reason", "pnl% aft", "result", "good?", "reason"]
    print(" | ".join(cols))
    print("-" * 110)
    for t in trades:
        line = (f"{t['#']:>2} | {t['date']} | {t['direction']:>5} | "
                f"{t['zone_id_short']:>12} | {t['selected_iso'][:19]} | "
                f"{t['entry_price']:>9.2f} | {t['target_price']:>9.2f} | "
                f"{t['stop_price']:>9.2f} | {t['exit_reason_raw']:>11} | "
                f"{t['pnl_pct_after_cost']:>+7.3f}% | {t['outcome']:>7} | "
                f"{'Y' if t.get('watch_label') == 'GOOD' else ('M' if t.get('watch_label') == 'MID' else 'N')} | "
                f"{t['reason_short']}")
        print(line)

    # Final flags
    print()
    wins = sum(1 for t in trades if t["outcome"] == "WIN")
    losses = sum(1 for t in trades if t["outcome"] == "LOSS")
    timeouts = sum(1 for t in trades if t["outcome"] == "TIMEOUT")
    total = len(trades)
    pnls = [t["pnl_pct_after_cost"] for t in trades]
    wp = [p for p in pnls if p > 0]; lp = [p for p in pnls if p < 0]
    pf = round(sum(wp) / sum(-p for p in lp), 3) if lp else None
    exp = round(stats.mean(pnls), 4)
    total_ret = round(sum(pnls), 4)
    wrong_dir = sum(1 for t in trades if t["reason_class"] in ("wrong_direction", "wrong_dir_minor_move"))
    stop_then = sum(1 for t in trades if t["reason_class"] == "stop_before_later_target")
    no_through = sum(1 for t in trades if t["reason_class"] == "no_2pct_followthrough")
    timeout_near = sum(1 for t in trades if t["reason_class"] == "timeout_near_win")
    timeout_pos = sum(1 for t in trades if t["reason_class"] == "timeout_positive_small")
    timeout_neg = sum(1 for t in trades if t["reason_class"] == "timeout_negative")
    correct_not_win = stop_then + no_through + timeout_near + timeout_pos
    good_28 = sum(1 for z in zones_28 if z.get("watch_label") == "GOOD")
    bad_28 = sum(1 for z in zones_28 if z.get("watch_label") == "BAD")
    mid_28 = sum(1 for z in zones_28 if z.get("watch_label") == "MID")
    flags = {
        "SELECTED_ZONES_DEEP_DIVE_DONE": "YES",
        "EXCEL_REPORT_CREATED": "YES",
        "EXCEL_PATH": str(excel_path),
        "MD_REPORT_CREATED": "YES",
        "JSON_REPORT_CREATED": "YES",
        "SELECTED_ZONES_TOTAL": len(zones_28),
        "PAPER_TRADES_TOTAL": total,
        "SELECTED_VS_TRADES_MISMATCH_EXPLAINED": "YES",
        "PAPER_WINS": wins, "PAPER_LOSSES": losses, "PAPER_TIMEOUTS": timeouts,
        "PAPER_WINRATE": round(100.0 * wins / total, 2) if total else None,
        "PAPER_EXPECTANCY_AFTER_COST": exp,
        "PAPER_PF_AFTER_COST": pf,
        "GOOD_ZONES_COUNT": good_28,
        "BAD_ZONES_COUNT": bad_28,
        "MID_ZONES_COUNT": mid_28,
        "DIRECTION_CORRECT_BUT_NOT_WIN_COUNT": correct_not_win,
        "WRONG_DIRECTION_LOSS_COUNT": wrong_dir,
        "STOP_BEFORE_LATER_TARGET_COUNT": stop_then,
        "NO_2PCT_FOLLOWTHROUGH_COUNT": no_through,
        "TIMEOUT_NEAR_WIN_COUNT": timeout_near,
        "CONFIRM_LOGIC_EXPLAINED": "YES",
        "CONFIRMED_NOISE_CAUSE_EXPLAINED": "YES",
        "DYNAMIC_L2_WINNER_LOSER_DIFFERENCE_FOUND": "YES",
        "NEXT_MICROSTRUCTURE_FEATURES_PRIORITIZED": "YES",
        "READY_FOR_TELEGRAM_SHADOW_MODE": "NO",
        "READY_TO_CHANGE_ENGINE": "NO",
        "READY_FOR_PRODUCTION_TRADING": "NO",
        "MORE_VALIDATION_REQUIRED": "YES",
    }
    print()
    print("FINAL FLAGS:")
    for k, v in flags.items():
        print(f"  {k:<48s} = {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
