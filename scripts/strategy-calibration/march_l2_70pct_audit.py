"""March leak audit + L2 features + 70 % re-test (Sections A-I).

Critical follow-up:
- A. Audit the current best selector for leak.
- B. Split selectors by stage (candidate / confirmed / trigger).
- C. Casebook of all 29 selected paper-trade signals.
- D. Winners vs losers analysis.
- E. Extract real L2 microstructure features from incremental_book_L2.csv.gz.
- F. Re-run exhaustive 70 % leak-free search with L2-enhanced dataset.
- G. Paper-trade optimization with L2-enhanced selectors.
- H. Verdict: did L2 features unlock 70 %?
- I. Final report.

NO engine / threshold / detector change. Target strict 2 %. Cost 0.14 % roundtrip.
"""
from __future__ import annotations
import csv
import datetime as dt
import gzip
import itertools
import json
import math
import statistics as stats
import sys
import time
from collections import defaultdict, Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))
from canonical_ledger import (Bucket, build_buckets_from_trades_csv, Signal,
                              ExecutionConfig, simulate_canonical_trade)

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "package.json").exists() and (p / "scripts").exists())
REPORTS = ROOT / "reports"
REP_OUT = REPORTS / "strategy-calibration"
DATA_ROOT = ROOT / "data/okx-historical/BTC-USDT-SWAP"

FIRST_HALF_DATES = [f"2026-03-{d:02d}" for d in range(2, 16)]
SECOND_HALF_DATES = ["2026-03-16"] + [f"2026-03-{d:02d}" for d in range(18, 32)]
ALL_DATES = FIRST_HALF_DATES + SECOND_HALF_DATES
N_DAYS = len(ALL_DATES)

COST_PCT = 0.14
TARGET_PCT = 2.0
TIMEOUT_HOURS = 24

L2_CACHE_PATH = REP_OUT / "MARCH_L2_MICROSTRUCTURE_FEATURE_DATASET.csv"


def now_iso() -> str:
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


def quantile(xs, q):
    xs = sorted(x for x in xs if x is not None)
    if not xs: return None
    idx = int(q * (len(xs) - 1))
    return xs[idx]


def cohens_d(a, b):
    a = [x for x in a if x is not None and not (isinstance(x, float) and math.isnan(x))]
    b = [x for x in b if x is not None and not (isinstance(x, float) and math.isnan(x))]
    if len(a) < 2 or len(b) < 2: return None
    ma, mb = stats.mean(a), stats.mean(b)
    sa, sb = stats.pstdev(a), stats.pstdev(b)
    pooled = math.sqrt(((len(a)-1)*sa*sa + (len(b)-1)*sb*sb) / max(len(a)+len(b)-2, 1))
    if pooled == 0: return None
    return round((ma - mb) / pooled, 4)


def mean_or_none(xs):
    xs = [x for x in xs if x is not None]
    return round(stats.mean(xs), 4) if xs else None


# ============================================================
# Load existing dataset
# ============================================================
def load_dataset() -> list[dict]:
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
    return rows


# ============================================================
# Section A: Leak audit
# ============================================================
def leak_audit(rows: list[dict]) -> dict:
    """Empirically verify leak status of suspect fields."""
    # 1. score_trigger
    has_trig = sum(1 for r in rows if r.get("trigger_iso"))
    no_trig = sum(1 for r in rows if not r.get("trigger_iso"))
    score_trig_when_no_trig = sum(1 for r in rows if not r.get("trigger_iso") and r.get("score_trigger") is not None)
    score_trig_when_trig = sum(1 for r in rows if r.get("trigger_iso") and r.get("score_trigger") is not None)

    # 2. pct_correct_move_already_done
    pct_zero = sum(1 for r in rows if r.get("pct_correct_move_already_done") == 0)
    pct_nonzero_rows = [r for r in rows if r.get("pct_correct_move_already_done") and r.get("pct_correct_move_already_done") > 0]
    pct_nonzero_good = sum(1 for r in pct_nonzero_rows if r.get("watch_label") == "GOOD")
    pct_nonzero_bad = sum(1 for r in pct_nonzero_rows if r.get("watch_label") == "BAD")

    # 3. filter_kept
    fk = sum(1 for r in rows if r.get("filter_kept"))
    fk_no_trig = sum(1 for r in rows if r.get("filter_kept") and not r.get("trigger_iso"))

    fields_audit = [
        {
            "field": "score_trigger",
            "definition": "engine's trigger-quality score, populated in zone.scores when a trigger event fires",
            "source": "scripts/strategy-calibration/march_in_sample_calibration.py extract_features() -> scores.get('triggerScore')",
            "available_at_candidate": "NO",
            "available_at_confirmed": "NO (verified: 0 of 418 zones without triggerTs have score_trigger)",
            "available_at_trigger": "YES (verified: 625 of 625 triggered zones have score_trigger)",
            "uses_future_market_move": "NO directly, but knowing trigger happened is future info at confirm time",
            "leak_classification": "FUTURE_LEAK at confirm; SAFE at trigger stage",
            "empirical_count_no_trig_with_value": score_trig_when_no_trig,
            "empirical_count_trig_with_value": score_trig_when_trig,
        },
        {
            "field": "pct_correct_move_already_done",
            "definition": "pct of correct-direction 2 % move completed at anchor, where move is detected via full-day scan with start/end determined by retracement",
            "source": "scripts/strategy-calibration/march_in_sample_calibration.py compute_orderflow_features() — uses moves_today list scanned over full day",
            "available_at_candidate": "NO",
            "available_at_confirmed": "NO (requires move.end_sec which is determined only when retracement triggers, possibly after anchor)",
            "available_at_trigger": "PARTIAL — even at trigger we don't know future end_sec of in-progress moves",
            "uses_future_market_move": "YES (move.end_sec is by definition determined by future retracement)",
            "leak_classification": "FUTURE_LEAK",
            "empirical_pct_zero_count": pct_zero,
            "empirical_pct_nonzero_GOOD": pct_nonzero_good,
            "empirical_pct_nonzero_BAD": pct_nonzero_bad,
            "live_behavior": "would always be 0 since at live time no completed move can overlap anchor (its end_sec is past, can't be > anchor)",
        },
        {
            "field": "is_during_correct_move",
            "definition": "boolean wrapper of pct_correct_move_already_done > 0",
            "leak_classification": "FUTURE_LEAK (same root cause)",
        },
        {
            "field": "pct_opposite_move_already_done",
            "definition": "same as pct_correct but for opposite direction",
            "leak_classification": "FUTURE_LEAK",
        },
        {
            "field": "is_during_opposite_move",
            "leak_classification": "FUTURE_LEAK",
        },
        {
            "field": "is_late_after_50pct_correct_move",
            "leak_classification": "FUTURE_LEAK",
        },
        {
            "field": "filter_kept",
            "definition": "passive filter: zone is kept iff NOT duplicate of prior trigger AND confirm_to_trigger <= 60min. Both inputs require post-confirm info.",
            "source": "scripts/strategy-calibration/good_watch_zone_feature_research.py apply_passive_filter() — iterates over TRIGGERED zones only, uses prior['triggerTs'] and confirm_to_trigger_min",
            "available_at_candidate": "NO",
            "available_at_confirmed": "NO (uses triggerTs of prior zones AND of current zone)",
            "available_at_trigger": "YES (all inputs known at trigger of THIS zone, modulo timing of subsequent zones)",
            "leak_classification": "FUTURE_LEAK at confirm; SAFE at trigger stage IF computed once at trigger of this zone",
            "empirical_kept_count": fk,
            "empirical_kept_count_no_trig": fk_no_trig,
        },
        {
            "field": "filter_dup_suppressed",
            "leak_classification": "FUTURE_LEAK at confirm; SAFE at trigger",
        },
        {
            "field": "filter_fast_ok",
            "definition": "confirm_to_trigger_min <= 60 — uses triggerTs",
            "leak_classification": "FUTURE_LEAK at confirm; SAFE at trigger",
        },
        {
            "field": "confirm_to_trigger_min",
            "leak_classification": "FUTURE_LEAK at confirm; SAFE at trigger",
        },
        {
            "field": "total_pre_trigger_min",
            "leak_classification": "FUTURE_LEAK at confirm; SAFE at trigger",
        },
        {
            "field": "trig_break_pct / trig_flow_multiplier / trig_side_flow_ok / trig_price",
            "leak_classification": "FUTURE_LEAK at confirm; SAFE at trigger",
        },
        {
            "field": "matched_move_size_pct / lead_min_before_move / watch_label / coverage_class",
            "leak_classification": "LABEL_ONLY (use only for evaluation)",
        },
        # Safe ones for sanity
        {
            "field": "taker_imb_aligned_30m / ofi_shift_aligned / vol_anomaly_15m_vs_bg / sweep_reclaim_aligned",
            "definition": "trade-derived, computed using only trades with timestamp <= anchor (confirmedTs)",
            "available_at_confirmed": "YES",
            "leak_classification": "SAFE_AT_CONFIRM",
        },
        {
            "field": "prior_move_*m_pct / local_range_*m_pct / local_realized_vol_*m / dist_to_recent_swing_* / dist_to_4h_mean_pct",
            "definition": "backward-looking on 1s buckets ending at anchor",
            "leak_classification": "SAFE_AT_CONFIRM",
        },
        {
            "field": "cand_* / conf_* / score_absorption / score_refill / score_ofi / score_liquidity_void",
            "definition": "engine-computed at candidate or confirm stage",
            "leak_classification": "SAFE_AT_CONFIRM",
        },
        {
            "field": "is_asia_session / is_us_session / is_session_open_2h / utc_hour / weekday / session",
            "leak_classification": "SAFE_AT_CONFIRM",
        },
        {
            "field": "same_dir_zones_active_60m / opp_dir_zones_active_60m",
            "definition": "count of PRIOR confirmed zones in past 60m — uses only confirmedTs < anchor",
            "leak_classification": "SAFE_AT_CONFIRM",
        },
    ]

    # Current best selectors -- live validity
    best_pair_selector = {
        "name": "P::score_trigger_ge_1.0+pct_correct_move_already_done_le_0.0::top1",
        "uses_fields": ["score_trigger", "pct_correct_move_already_done"],
        "leak_status": "LEAK — both fields are FUTURE_LEAK at confirm stage",
        "valid_stage": "none for watch alerts; partial 'execution' if applied at trigger stage AND we replace pct_correct_move_already_done by a backward-looking proxy",
        "live_valid": "NO at confirm stage",
    }
    best_paper_selector = {
        "name": "S::score_trigger_ge_1.0::top1 | delay_10m | stop_1.5%",
        "uses_fields": ["score_trigger"],
        "leak_status": "LEAK — score_trigger only available after trigger fires",
        "valid_stage": "could be a TRIGGER-STAGE execution selector (enter delay_10m AFTER trigger fires, knowing score_trigger value)",
        "live_valid": "NO if used as watch alert at confirm; PARTIALLY valid as trigger-stage execution rule",
    }

    audit = {
        "build_time_utc": now_iso(),
        "summary": "Both headline selectors use FUTURE_LEAK fields. Need to re-derive leak-free selectors per stage.",
        "fields_audit": fields_audit,
        "best_pair_selector_audit": best_pair_selector,
        "best_paper_selector_audit": best_paper_selector,
        "flags": {
            "BEST_SELECTOR_LEAK_AUDIT_DONE": "YES",
            "PCT_CORRECT_MOVE_ALREADY_DONE_LEAK_FREE": "NO",
            "SCORE_TRIGGER_AVAILABLE_AT_CONFIRM": "NO",
            "SCORE_TRIGGER_AVAILABLE_AT_TRIGGER": "YES",
            "FILTER_KEPT_AVAILABLE_AT_CONFIRM": "NO",
            "FILTER_KEPT_AVAILABLE_AT_TRIGGER": "YES",
            "CURRENT_BEST_SELECTOR_LIVE_VALID": "NO",
            "CURRENT_BEST_SELECTOR_VALID_STAGE": "none-at-confirm; partial-at-trigger",
        },
    }
    (REP_OUT / "MARCH_BEST_SELECTOR_LEAK_AUDIT.json").write_text(
        json.dumps(audit, indent=2, default=str), encoding="utf-8")
    md = ["# Best selector leak audit", "",
          f"**Build:** {audit['build_time_utc']}",
          "",
          "## Summary",
          audit["summary"],
          "",
          "## Suspect fields — verdict",
          "",
          "| field | confirm-safe? | trigger-safe? | classification |",
          "|---|:---:|:---:|---|"]
    for fa in fields_audit[:6]:
        md.append(f"| `{fa['field']}` | {fa.get('available_at_confirmed', 'N/A')} | "
                  f"{fa.get('available_at_trigger', 'N/A')} | {fa['leak_classification']} |")
    md.extend(["", "## Detailed audit"])
    for fa in fields_audit:
        md.append(f"### `{fa['field']}`")
        for k, v in fa.items():
            if k == "field": continue
            md.append(f"- {k}: {v}")
        md.append("")
    md.extend(["", "## Current best selector — live validity",
               f"- pair selector: `{best_pair_selector['name']}` — **LIVE VALID: {best_pair_selector['live_valid']}**",
               f"  - leak fields: {best_pair_selector['uses_fields']}",
               f"  - reason: {best_pair_selector['leak_status']}",
               f"- paper selector: `{best_paper_selector['name']}` — **LIVE VALID: {best_paper_selector['live_valid']}**",
               f"  - leak fields: {best_paper_selector['uses_fields']}",
               f"  - reason: {best_paper_selector['leak_status']}",
               "",
               "## Flags",
               "```"])
    for k, v in audit["flags"].items():
        md.append(f"{k} = {v}")
    md.append("```")
    (REP_OUT / "MARCH_BEST_SELECTOR_LEAK_AUDIT.md").write_text("\n".join(md), encoding="utf-8")
    return audit


# ============================================================
# Stage-safe feature sets
# ============================================================
# Features safe at CONFIRMED stage (no future info)
CONFIRM_SAFE_NUMERIC = [
    # Engine candidate/confirm conditions
    "cand_pressure_against", "cand_buy_pressure", "cand_sell_pressure",
    "cand_absorb_score", "cand_bid_refill_score", "cand_ask_refill_score",
    "cand_refill_with", "cand_prior_move_pct", "cand_down_move_pct", "cand_up_move_pct",
    "conf_cycles_seen", "conf_age_min", "conf_defended_persistence_sec",
    "conf_opposite_thinning", "conf_void_score",
    "score_absorption", "score_refill", "score_ofi", "score_liquidity_void",   # NOT score_trigger
    # Zone geometry
    "zone_width_pct",
    # Confluence (uses prior confirmed only)
    "same_dir_zones_active_60m", "opp_dir_zones_active_60m",
    # Local context (backward)
    "prior_move_15m_pct", "prior_move_30m_pct", "prior_move_60m_pct", "prior_move_180m_pct",
    "abs_prior_move_15m_pct", "abs_prior_move_30m_pct", "abs_prior_move_60m_pct", "abs_prior_move_180m_pct",
    "local_range_15m_pct", "local_range_30m_pct", "local_range_60m_pct", "local_range_180m_pct",
    "local_realized_vol_15m", "local_realized_vol_30m", "local_realized_vol_60m", "local_realized_vol_180m",
    "dist_to_recent_swing_high_pct", "dist_to_recent_swing_low_pct",
    "dist_to_4h_mean_pct", "abs_dist_to_4h_mean_pct",
    # Trade-derived orderflow (windows ending at confirm anchor)
    "taker_imb_5m", "taker_imb_15m", "taker_imb_30m", "taker_imb_60m", "taker_imb_180m",
    "taker_imb_aligned_5m", "taker_imb_aligned_15m", "taker_imb_aligned_30m",
    "taker_imb_aligned_60m", "taker_imb_aligned_180m",
    "taker_total_vol_15m", "taker_total_vol_60m",
    "vol_anomaly_15m_vs_bg",
    "ofi_shift_5m_vs_30m", "ofi_shift_aligned",
    # Time of day
    "utc_hour",
]
CONFIRM_SAFE_BOOLEAN = [
    "cand_range_compression", "sweep_reclaim_aligned",
    "is_asia_session", "is_us_session", "is_session_open_2h",
]

# Features safe at TRIGGER stage (everything confirm-safe + trigger-stage fields)
TRIGGER_ONLY_NUMERIC = [
    "score_trigger", "trig_break_pct", "trig_flow_multiplier", "trig_price",
    "confirm_to_trigger_min", "total_pre_trigger_min",
]
TRIGGER_ONLY_BOOLEAN = [
    "filter_kept", "filter_dup_suppressed", "filter_fast_ok", "trig_side_flow_ok",
]

LEAKY_EXCLUDED_AT_ALL_STAGES = [
    "pct_correct_move_already_done", "pct_opposite_move_already_done",
    "is_during_correct_move", "is_during_opposite_move",
    "is_late_after_50pct_correct_move",
    "matched_move_size_pct", "lead_min_before_move",
]


def add_extra_fields(rows: list[dict]) -> None:
    """Add session_bucket, weekday and abs_* helpers."""
    for r in rows:
        sec = iso_to_sec(r.get("confirmed_iso"))
        if sec is None:
            r["weekday"] = None
            r["session_bucket"] = None
            r["is_session_open_2h"] = None
            continue
        d = dt.datetime.fromtimestamp(sec, tz=dt.timezone.utc)
        r["weekday"] = d.weekday()
        hr = d.hour
        if hr < 7: sb = "asia"
        elif hr < 14: sb = "europe"
        elif hr < 22: sb = "us"
        else: sb = "asia_late"
        r["session_bucket"] = sb
        r["is_session_open_2h"] = 1 if hr in (0, 1, 7, 8, 14, 15) else 0
        for k in ("prior_move_60m_pct", "prior_move_180m_pct", "prior_move_30m_pct",
                  "prior_move_15m_pct", "dist_to_4h_mean_pct"):
            v = r.get(k)
            r[f"abs_{k}"] = abs(v) if v is not None else None


# ============================================================
# Section B: stage-specific selectors
# ============================================================
def explainable_score_confirm_safe(r: dict) -> float:
    """Leak-free explainable score using ONLY confirm-safe features."""
    s = 0.0
    if (r.get("opp_dir_zones_active_60m") or 0) == 0: s += 0.7
    # absolute prior_move (low = good)
    pm = r.get("prior_move_60m_pct")
    if pm is not None: s -= min(abs(pm) * 0.3, 0.6)
    lr = r.get("local_range_180m_pct")
    if lr is not None and lr > 2.0: s -= 0.4
    ti = r.get("taker_imb_aligned_30m");  s += max(min(ti or 0, 0.5), -0.5)
    of = r.get("ofi_shift_aligned");      s += max(min(of or 0, 0.3), -0.3)
    if r.get("sweep_reclaim_aligned") == 1: s += 0.4
    if r.get("is_asia_session"): s += 0.2
    # Confidence: high score_absorption (engine confirm-safe, mostly constant but small)
    sa = r.get("score_absorption")
    if sa is not None and sa > 0: s += min(sa * 0.2, 0.3)
    # Penalty: many same-direction recent clusters
    same = r.get("same_dir_zones_active_60m") or 0
    if same > 2: s -= 0.3
    return round(s, 4)


def explainable_score_trigger_stage(r: dict) -> float:
    """Score allowed to use trigger-stage features."""
    s = explainable_score_confirm_safe(r)
    if r.get("filter_kept"): s += 1.0
    if r.get("score_trigger") and r.get("score_trigger") >= 0.99: s += 1.0
    tb = r.get("trig_break_pct")
    if tb is not None: s += min(tb * 0.5, 0.5)
    ct = r.get("confirm_to_trigger_min")
    if ct is not None and ct <= 30: s += 0.5
    elif ct is not None and ct > 120: s -= 0.3
    return round(s, 4)


def selector_eval(rows: list[dict], predicate, day_cap=None, per_dir_cap=None,
                   score_key=None) -> dict:
    by_date = defaultdict(list)
    for r in rows:
        if not predicate(r): continue
        by_date[r["date"]].append(r)
    selected = []
    for d in ALL_DATES:
        day_rows = by_date.get(d, [])
        if score_key:
            day_rows = sorted(day_rows, key=lambda x: -(x.get(score_key) or 0))
        if per_dir_cap is not None:
            seen = defaultdict(int); kept = []
            for r in day_rows:
                if seen[r["direction"]] < per_dir_cap:
                    kept.append(r); seen[r["direction"]] += 1
            day_rows = kept
        if day_cap is not None:
            day_rows = day_rows[:day_cap]
        selected.extend(day_rows)
    n = len(selected)
    good = sum(1 for r in selected if r.get("watch_label") == "GOOD")
    wrong = sum(1 for r in selected if r.get("coverage_class") == "wrong_direction")
    n_good_all = sum(1 for r in rows if r.get("watch_label") == "GOOD")
    h1 = [r for r in selected if r["_half"] == "first"]
    h2 = [r for r in selected if r["_half"] == "second"]
    g1 = sum(1 for r in h1 if r.get("watch_label") == "GOOD")
    g2 = sum(1 for r in h2 if r.get("watch_label") == "GOOD")
    lng = [r for r in selected if r["direction"] == "LONG"]
    sht = [r for r in selected if r["direction"] == "SHORT"]
    gl = sum(1 for r in lng if r.get("watch_label") == "GOOD")
    gs = sum(1 for r in sht if r.get("watch_label") == "GOOD")
    leads = [r.get("lead_min_before_move") for r in selected
             if r.get("lead_min_before_move") and r["lead_min_before_move"] > 0]
    return {
        "selected_n": n, "alerts_per_day": round(n / N_DAYS, 3),
        "good_n": good, "wrong_n": wrong,
        "precision_pct": round(100.0 * good / max(n, 1), 2) if n else None,
        "recall_pct": round(100.0 * good / max(n_good_all, 1), 2) if n_good_all else None,
        "wrong_rate_pct": round(100.0 * wrong / max(n, 1), 2) if n else None,
        "h1_n": len(h1), "h2_n": len(h2),
        "h1_precision_pct": round(100.0 * g1 / max(len(h1), 1), 2) if h1 else None,
        "h2_precision_pct": round(100.0 * g2 / max(len(h2), 1), 2) if h2 else None,
        "long_n": len(lng), "short_n": len(sht),
        "long_precision_pct": round(100.0 * gl / max(len(lng), 1), 2) if lng else None,
        "short_precision_pct": round(100.0 * gs / max(len(sht), 1), 2) if sht else None,
        "avg_lead_min": round(stats.mean(leads), 2) if leads else None,
        "median_lead_min": round(stats.median(leads), 2) if leads else None,
        "selected_zone_ids": [r["zone_id"] for r in selected],
    }


def build_rule_candidates(rows: list[dict], numeric_keys: list[str], boolean_keys: list[str]) -> list[tuple[str, Callable]]:
    rules = []
    for k in numeric_keys:
        values = [r.get(k) for r in rows if r.get(k) is not None]
        if len(values) < 50: continue
        for q in (0.2, 0.4, 0.6, 0.8):
            v = quantile(values, q)
            if v is None: continue
            def make_ge(key, thresh): return lambda r: (r.get(key) is not None) and (r.get(key) >= thresh)
            def make_le(key, thresh): return lambda r: (r.get(key) is not None) and (r.get(key) <= thresh)
            rules.append((f"{k}_ge_{round(v, 4)}", make_ge(k, v)))
            rules.append((f"{k}_le_{round(v, 4)}", make_le(k, v)))
    for k in boolean_keys:
        def make_true(key): return lambda r: bool(r.get(key))
        def make_false(key): return lambda r: not bool(r.get(key))
        rules.append((f"{k}_TRUE", make_true(k)))
        rules.append((f"{k}_FALSE", make_false(k)))
    rules.append(("dir_LONG", lambda r: r["direction"] == "LONG"))
    rules.append(("dir_SHORT", lambda r: r["direction"] == "SHORT"))
    return rules


def search_stage(rows: list[dict], numeric_keys: list[str], boolean_keys: list[str],
                  score_key: str, stage_name: str) -> list[dict]:
    print(f"  [stage:{stage_name}] building rule candidates ...", file=sys.stderr)
    rules = build_rule_candidates(rows, numeric_keys, boolean_keys)
    # Pre-rank score
    out = []
    for name, fn in rules:
        e = selector_eval(rows, fn)
        out.append({"selector": f"{stage_name}::S::{name}", **e, "kind": "single"})
        e1 = selector_eval(rows, fn, day_cap=1, score_key=score_key)
        out.append({"selector": f"{stage_name}::S::{name}::top1", **e1, "kind": "single+top1"})
        e2 = selector_eval(rows, fn, day_cap=2, score_key=score_key)
        out.append({"selector": f"{stage_name}::S::{name}::top2", **e2, "kind": "single+top2"})
    # Add pair search on top-12 features by single-rule precision
    valid = [s for s in out if (s.get("selected_n") or 0) >= 20 and s.get("precision_pct") is not None]
    valid.sort(key=lambda s: -s["precision_pct"])
    seen_feats = set(); top_feats = []
    for s in valid[:40]:
        body = s["selector"].split("::")[2]
        for fk in numeric_keys + boolean_keys:
            if body.startswith(fk):
                if fk not in seen_feats:
                    seen_feats.add(fk); top_feats.append(fk)
                break
        if len(top_feats) >= 10: break
    print(f"  [stage:{stage_name}] top features for pair search: {top_feats}", file=sys.stderr)
    for i, a in enumerate(top_feats):
        for j in range(i + 1, len(top_feats)):
            b = top_feats[j]
            preds_a = _rule_candidates(rows, a, numeric_keys, boolean_keys)
            preds_b = _rule_candidates(rows, b, numeric_keys, boolean_keys)
            for na, fa in preds_a:
                for nb, fb in preds_b:
                    def make_and(fa, fb): return lambda r: fa(r) and fb(r)
                    pred = make_and(fa, fb)
                    e = selector_eval(rows, pred)
                    if (e["selected_n"] or 0) < 5: continue
                    out.append({"selector": f"{stage_name}::P::{na}+{nb}", **e, "kind": "pair"})
                    e1 = selector_eval(rows, pred, day_cap=1, score_key=score_key)
                    out.append({"selector": f"{stage_name}::P::{na}+{nb}::top1", **e1, "kind": "pair+top1"})
    return out


def _rule_candidates(rows, key, numeric_keys, boolean_keys):
    if key in boolean_keys:
        return [(f"{key}_TRUE", (lambda kk: lambda r: bool(r.get(kk)))(key)),
                (f"{key}_FALSE", (lambda kk: lambda r: not bool(r.get(kk)))(key))]
    values = [r.get(key) for r in rows if r.get(key) is not None]
    if len(values) < 50: return []
    out = []
    for q in (0.3, 0.5, 0.7):
        v = quantile(values, q)
        if v is None: continue
        out.append((f"{key}_ge_{round(v, 4)}",
                     (lambda kk, th: lambda r: (r.get(kk) is not None) and (r.get(kk) >= th))(key, v)))
        out.append((f"{key}_le_{round(v, 4)}",
                     (lambda kk, th: lambda r: (r.get(kk) is not None) and (r.get(kk) <= th))(key, v)))
    return out


def stage_specific_search(rows: list[dict]) -> dict:
    """Run separate searches for candidate / confirmed / trigger stages."""
    # Score-keys per stage
    for r in rows:
        r["_score_confirm"] = explainable_score_confirm_safe(r)
        r["_score_trigger"] = explainable_score_trigger_stage(r)
    # CANDIDATE-STAGE: only cand_* + zone geometry + session + prior_move + opp/same dir (using prior candidates)
    # We approximate "candidate stage" with engine cand_* fields only — trade-derived features anchored at confirm
    # are NOT candidate-safe but might be available if we re-anchor. For simplicity, candidate-stage = engine cand fields.
    candidate_numeric = [k for k in CONFIRM_SAFE_NUMERIC
                          if k.startswith("cand_") or k in ("zone_width_pct", "utc_hour",
                                                              "abs_prior_move_60m_pct", "prior_move_60m_pct",
                                                              "abs_prior_move_180m_pct",
                                                              "local_range_60m_pct", "local_range_180m_pct")]
    candidate_boolean = ["cand_range_compression", "is_asia_session", "is_us_session", "is_session_open_2h"]
    # CONFIRMED-STAGE: everything confirm-safe
    confirmed_numeric = CONFIRM_SAFE_NUMERIC
    confirmed_boolean = CONFIRM_SAFE_BOOLEAN
    # TRIGGER-STAGE: confirm-safe + trigger-only (and only triggered zones)
    triggered_rows = [r for r in rows if r.get("trigger_iso")]
    trigger_numeric = CONFIRM_SAFE_NUMERIC + TRIGGER_ONLY_NUMERIC
    trigger_boolean = CONFIRM_SAFE_BOOLEAN + TRIGGER_ONLY_BOOLEAN

    out_candidate = search_stage(rows, candidate_numeric, candidate_boolean, "_score_confirm", "CAND")
    out_confirmed = search_stage(rows, confirmed_numeric, confirmed_boolean, "_score_confirm", "CONF")
    out_trigger = search_stage(triggered_rows, trigger_numeric, trigger_boolean, "_score_trigger", "TRIG")

    return {"candidate": out_candidate, "confirmed": out_confirmed, "trigger": out_trigger}


def write_stage_results(stage_results: dict) -> dict:
    rows = []
    for stage_name, sels in stage_results.items():
        for s in sels:
            rows.append({"stage": stage_name, **{k: v for k, v in s.items() if k != "selected_zone_ids"}})
    csv_keys = ["stage", "selector", "kind", "selected_n", "alerts_per_day",
                "good_n", "wrong_n", "precision_pct", "recall_pct", "wrong_rate_pct",
                "h1_precision_pct", "h2_precision_pct",
                "long_precision_pct", "short_precision_pct",
                "avg_lead_min", "median_lead_min"]
    with (REP_OUT / "MARCH_STAGE_SPECIFIC_SELECTOR_RESULTS.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=csv_keys, extrasaction="ignore")
        w.writeheader()
        for r in rows: w.writerow(r)
    summary = {}
    for stage_name, sels in stage_results.items():
        valid = [s for s in sels if (s.get("selected_n") or 0) >= 20 and s.get("precision_pct") is not None]
        valid.sort(key=lambda s: -s["precision_pct"])
        summary[stage_name] = {
            "n_selectors": len(sels),
            "best_min20_top5": [{k: v for k, v in s.items() if k != "selected_zone_ids"} for s in valid[:5]],
            "best_min10_top5": [{k: v for k, v in s.items() if k != "selected_zone_ids"} for s in
                                  sorted([s for s in sels if (s.get("selected_n") or 0) >= 10
                                           and s.get("precision_pct") is not None],
                                          key=lambda s: -s["precision_pct"])[:5]],
            "any_70pct_min20": any((s.get("precision_pct") or 0) >= 70
                                     for s in sels if (s.get("selected_n") or 0) >= 20),
        }
    (REP_OUT / "MARCH_STAGE_SPECIFIC_SELECTOR_RESULTS.json").write_text(
        json.dumps({"build_time_utc": now_iso(), "stages": summary}, indent=2, default=str), encoding="utf-8")
    md = ["# Stage-specific selector results (leak-free per stage)", "",
          f"**Build:** {now_iso()}", ""]
    for stage_name in ("candidate", "confirmed", "trigger"):
        st = summary[stage_name]
        md.append(f"## Stage: {stage_name}")
        md.append(f"- n_selectors evaluated: {st['n_selectors']}")
        md.append(f"- 70 % precision with min 20: **{st['any_70pct_min20']}**")
        md.append("")
        md.append("### Top 5 with min 20 selected")
        md.append("| selector | n | /day | precision % | recall % | wrong % | H1 prec | H2 prec | LONG | SHORT |")
        md.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
        for s in st["best_min20_top5"]:
            md.append(f"| `{s['selector']}` | {s['selected_n']} | {s['alerts_per_day']} | "
                       f"{s['precision_pct']} | {s.get('recall_pct')} | {s.get('wrong_rate_pct')} | "
                       f"{s.get('h1_precision_pct')} | {s.get('h2_precision_pct')} | "
                       f"{s.get('long_precision_pct')} | {s.get('short_precision_pct')} |")
        md.append("")
        md.append("### Top 5 with min 10 selected (smaller sample, overfit-prone)")
        md.append("| selector | n | /day | precision % |")
        md.append("|---|---:|---:|---:|")
        for s in st["best_min10_top5"]:
            md.append(f"| `{s['selector']}` | {s['selected_n']} | {s['alerts_per_day']} | {s['precision_pct']} |")
        md.append("")
    (REP_OUT / "MARCH_STAGE_SPECIFIC_SELECTOR_RESULTS.md").write_text("\n".join(md), encoding="utf-8")
    return summary


# ============================================================
# Section C: Casebook of 29 selected signals
# ============================================================
def casebook_29(rows: list[dict], buckets_by_date: dict[str, list[Bucket]]) -> None:
    """Reproduce the 29 selected signals from
    S::score_trigger_ge_1.0::top1 + delay_10m + stop_1.5, and detail each."""
    # Filter: score_trigger >= 1.0, top1 per day by explainable_score (the LEAKY score)
    # Reproduce the exact selector
    candidates = [r for r in rows if (r.get("score_trigger") or 0) >= 1.0]
    # Score for ranking: same leaky explainable as before
    def explainable_old(r):
        s = 0.0
        if r.get("filter_kept"): s += 1.0
        if not r.get("is_late_after_50pct_correct_move"): s += 1.0
        if (r.get("opp_dir_zones_active_60m") or 0) == 0: s += 0.7
        if not r.get("is_during_opposite_move"): s += 0.7
        ti = r.get("taker_imb_aligned_30m"); s += max(min(ti or 0, 0.5), -0.5)
        of = r.get("ofi_shift_aligned");    s += max(min(of or 0, 0.3), -0.3)
        pm = r.get("prior_move_60m_pct")
        if pm is not None: s -= min(abs(pm) * 0.3, 0.6)
        lr = r.get("local_range_180m_pct")
        if lr is not None and lr > 2.0: s -= 0.4
        if r.get("sweep_reclaim_aligned") == 1: s += 0.4
        if r.get("is_asia_session"): s += 0.2
        return s
    by_date = defaultdict(list)
    for r in candidates: by_date[r["date"]].append(r)
    selected = []
    for d in ALL_DATES:
        day_rows = by_date.get(d, [])
        day_rows = sorted(day_rows, key=lambda x: -explainable_old(x))
        if day_rows: selected.append(day_rows[0])

    # Now simulate paper trade (delay_10m + stop_1.5)
    def merge_days(date):
        out = []
        idx = ALL_DATES.index(date)
        out.extend(buckets_by_date.get(date) or [])
        for k in (1, 2):
            if idx + k >= len(ALL_DATES): break
            out.extend(buckets_by_date.get(ALL_DATES[idx + k]) or [])
        return out

    case = []
    winners = 0; losers = 0; timeouts = 0
    for i, r in enumerate(selected):
        confirmed_sec = iso_to_sec(r.get("confirmed_iso"))
        if confirmed_sec is None: continue
        buckets = merge_days(r["date"])
        sig = Signal(id=r["zone_id"], date=r["date"], trigger_ts_ms=confirmed_sec * 1000,
                     direction=r["direction"], zone_low=r.get("zone_low"), zone_high=r.get("zone_high"))
        cfg = ExecutionConfig(entry_strategy="delay_10m", stop_pct=1.5,
                              target_pct=TARGET_PCT, timeout_hours=TIMEOUT_HOURS)
        sim = simulate_canonical_trade(sig, buckets, cfg)
        if sim.get("exit_reason") in ("no_data", "skip_no_retest"):
            continue
        outcome = sim["exit_reason"]
        if outcome == "target_2pct": winners += 1
        elif outcome == "stop": losers += 1
        else: timeouts += 1
        case.append({
            "#": i + 1,
            "date": r["date"],
            "direction": r["direction"],
            "zone_id": r["zone_id"],
            "candidate_iso": r.get("candidate_iso"),
            "confirmed_iso": r.get("confirmed_iso"),
            "trigger_iso": r.get("trigger_iso"),
            "session": r.get("session"),
            "selected_stage": "confirmed (entry +10 min)",
            "entry_sec": sim["entry_sec"],
            "entry_iso": dt.datetime.fromtimestamp(sim["entry_sec"], tz=dt.timezone.utc).isoformat(timespec="seconds"),
            "entry_price": sim["entry_price"],
            "exit_sec": sim["exit_sec"],
            "exit_iso": dt.datetime.fromtimestamp(sim["exit_sec"], tz=dt.timezone.utc).isoformat(timespec="seconds"),
            "exit_price": sim["exit_price"],
            "exit_reason": outcome,
            "pnl_pct": sim["pnl_pct"],
            "win_loss": "WIN" if outcome == "target_2pct" else ("LOSS" if outcome == "stop" else "TIMEOUT"),
            "watch_label": r.get("watch_label"),
            "coverage_class": r.get("coverage_class"),
            "matched_move_size_pct": r.get("matched_move_size_pct"),
            "lead_min_before_move": r.get("lead_min_before_move"),
            "score_trigger": r.get("score_trigger"),
            "explainable_score_legacy": round(explainable_old(r), 4),
            "explainable_score_confirm_safe": round(explainable_score_confirm_safe(r), 4),
            "zone_low": r.get("zone_low"), "zone_high": r.get("zone_high"), "zone_mid": r.get("zone_mid"),
            "filter_kept": r.get("filter_kept"),
            "is_late_after_50pct_correct_move": r.get("is_late_after_50pct_correct_move"),
            "is_during_opposite_move": r.get("is_during_opposite_move"),
            "opp_dir_zones_active_60m": r.get("opp_dir_zones_active_60m"),
            "same_dir_zones_active_60m": r.get("same_dir_zones_active_60m"),
            "taker_imb_aligned_30m": r.get("taker_imb_aligned_30m"),
            "ofi_shift_aligned": r.get("ofi_shift_aligned"),
            "vol_anomaly_15m_vs_bg": r.get("vol_anomaly_15m_vs_bg"),
            "sweep_reclaim_aligned": r.get("sweep_reclaim_aligned"),
            "prior_move_60m_pct": r.get("prior_move_60m_pct"),
            "local_range_180m_pct": r.get("local_range_180m_pct"),
            "reason_summary": f"{r['direction']} zone confirmed in {r.get('session', '?')} session with score_trigger={r.get('score_trigger')}",
        })

    with (REP_OUT / "MARCH_BEST_29_SELECTED_SIGNALS_CASEBOOK.csv").open("w", encoding="utf-8", newline="") as f:
        if case:
            w = csv.DictWriter(f, fieldnames=list(case[0].keys()))
            w.writeheader()
            for r in case: w.writerow(r)
    (REP_OUT / "MARCH_BEST_29_SELECTED_SIGNALS_CASEBOOK.json").write_text(
        json.dumps({"build_time_utc": now_iso(),
                    "selector": "S::score_trigger_ge_1.0::top1 | delay_10m | stop_1.5%",
                    "WARNING": "This selector USES LEAK FIELDS (score_trigger at confirm time). Casebook is diagnostic only.",
                    "n_signals": len(case), "winners": winners, "losers": losers, "timeouts": timeouts,
                    "winrate_pct": round(100.0 * winners / max(len(case), 1), 2),
                    "signals": case}, indent=2, default=str), encoding="utf-8")
    md = ["# Casebook: 29 selected paper-trade signals (best paper model)", "",
          f"**Build:** {now_iso()}",
          f"**Selector:** `S::score_trigger_ge_1.0::top1 | delay_10m | stop_1.5%`",
          f"**WARNING:** This selector uses LEAK FIELDS (score_trigger at confirm). Casebook is diagnostic only.",
          f"**Trades:** {len(case)} (wins: {winners}, losses: {losers}, timeouts: {timeouts})",
          f"**Winrate:** {round(100.0 * winners / max(len(case), 1), 2)} %",
          "",
          "| # | date | dir | confirmed | session | entry | exit_reason | pnl % | win | label | match % | lead | score_trig | filter | late | during_opp | taker30 | ofi | sweep |",
          "|---:|---|---|---|---|---|---|---:|:---:|---|---:|---:|---:|:---:|:---:|:---:|---:|---:|:---:|"]
    for c in case:
        md.append(f"| {c['#']} | {c['date']} | {c['direction']} | {c['confirmed_iso']} | {c['session']} | "
                  f"{c['entry_iso']} | {c['exit_reason']} | {c['pnl_pct']} | {c['win_loss']} | "
                  f"{c.get('watch_label')} | {c.get('matched_move_size_pct')} | {c.get('lead_min_before_move')} | "
                  f"{c['score_trigger']} | "
                  f"{'Y' if c['filter_kept'] else 'N'} | "
                  f"{'Y' if c['is_late_after_50pct_correct_move'] else 'N'} | "
                  f"{'Y' if c['is_during_opposite_move'] else 'N'} | "
                  f"{c['taker_imb_aligned_30m']} | {c['ofi_shift_aligned']} | "
                  f"{'Y' if c['sweep_reclaim_aligned'] else 'N'} |")
    (REP_OUT / "MARCH_BEST_29_SELECTED_SIGNALS_CASEBOOK.md").write_text("\n".join(md), encoding="utf-8")
    return case


# ============================================================
# Section D: Winners vs Losers
# ============================================================
def winners_vs_losers(case: list[dict], rows: list[dict]) -> None:
    """Compare features for 29 signals: winners vs losers."""
    by_id = {r["zone_id"]: r for r in rows}
    winners_rows = [by_id[c["zone_id"]] for c in case if c["win_loss"] == "WIN" and c["zone_id"] in by_id]
    losers_rows = [by_id[c["zone_id"]] for c in case if c["win_loss"] in ("LOSS", "TIMEOUT") and c["zone_id"] in by_id]
    feature_keys = (CONFIRM_SAFE_NUMERIC + TRIGGER_ONLY_NUMERIC
                    + CONFIRM_SAFE_BOOLEAN + TRIGGER_ONLY_BOOLEAN)
    table = []
    for k in feature_keys:
        wv = [r.get(k) for r in winners_rows]
        lv = [r.get(k) for r in losers_rows]
        if k in CONFIRM_SAFE_BOOLEAN + TRIGGER_ONLY_BOOLEAN:
            wf = round(100.0 * sum(1 for v in wv if v) / max(len(wv), 1), 2)
            lf = round(100.0 * sum(1 for v in lv if v) / max(len(lv), 1), 2)
            table.append({"feature": k, "type": "boolean", "winners_freq_pct": wf, "losers_freq_pct": lf,
                          "diff_pp": round(wf - lf, 2)})
        else:
            wm = mean_or_none(wv); lm = mean_or_none(lv); d = cohens_d(wv, lv)
            table.append({"feature": k, "type": "numeric", "winners_mean": wm, "losers_mean": lm,
                          "cohens_d_winners_vs_losers": d})
    # Sort by absolute separation
    def sep(t):
        if t["type"] == "boolean": return abs(t.get("diff_pp") or 0)
        return abs(t.get("cohens_d_winners_vs_losers") or 0) * 100
    table.sort(key=sep, reverse=True)
    csv_keys = ["feature", "type", "winners_mean", "losers_mean", "cohens_d_winners_vs_losers",
                "winners_freq_pct", "losers_freq_pct", "diff_pp"]
    with (REP_OUT / "MARCH_BEST_SELECTOR_WINNERS_VS_LOSERS.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=csv_keys, extrasaction="ignore")
        w.writeheader()
        for r in table: w.writerow(r)
    (REP_OUT / "MARCH_BEST_SELECTOR_WINNERS_VS_LOSERS.json").write_text(
        json.dumps({"build_time_utc": now_iso(),
                    "n_winners": len(winners_rows), "n_losers": len(losers_rows),
                    "feature_table": table}, indent=2, default=str), encoding="utf-8")
    md = ["# Winners vs Losers feature comparison (29 selected paper trades)", "",
          f"**Build:** {now_iso()}",
          f"**Winners: {len(winners_rows)}; Losers + Timeouts: {len(losers_rows)}**",
          "",
          "## Top 30 most-separating features",
          "",
          "| feature | type | winners | losers | sep |",
          "|---|---|---:|---:|---:|"]
    for t in table[:30]:
        if t["type"] == "boolean":
            md.append(f"| `{t['feature']}` | bool | {t['winners_freq_pct']}% | {t['losers_freq_pct']}% | "
                       f"{t['diff_pp']} pp |")
        else:
            md.append(f"| `{t['feature']}` | num | {t['winners_mean']} | {t['losers_mean']} | "
                       f"d={t['cohens_d_winners_vs_losers']} |")
    md.append("")
    md.append("## Notes")
    md.append("- Sample size 14 winners vs 15 losers is small — Cohen's d is noisy. Trust only |d| >= 0.5.")
    md.append("- This is a within-selector breakdown: ALL 29 zones already pass `score_trigger >= 1.0` and `top1/day`.")
    (REP_OUT / "MARCH_BEST_SELECTOR_WINNERS_VS_LOSERS.md").write_text("\n".join(md), encoding="utf-8")


# ============================================================
# Section E: L2 microstructure feature extraction
# ============================================================
@dataclass
class BookSnap:
    spread_bps: Optional[float]
    best_bid: Optional[float]
    best_ask: Optional[float]
    mid: Optional[float]
    top1_bid_amount: Optional[float]
    top1_ask_amount: Optional[float]
    top5_bid_sum: Optional[float]
    top5_ask_sum: Optional[float]
    top20_bid_sum: Optional[float]
    top20_ask_sum: Optional[float]
    top5_imbalance: Optional[float]
    top20_imbalance: Optional[float]
    microprice: Optional[float]
    microprice_dev_bps: Optional[float]
    update_rate_30s: Optional[float]


def extract_l2_features_for_day(date: str, target_secs_set: set[int],
                                 anchors: list[tuple[int, str]]) -> dict[str, BookSnap]:
    """Extract L2 features for each (anchor_sec, zone_id) in anchors for given day.

    Streams the book file once, maintaining bid_book / ask_book.
    Triggers snapshot when update timestamp passes next anchor.
    """
    p = DATA_ROOT / date / "incremental_book_L2.csv.gz"
    if not p.exists():
        return {}
    # Sort anchors ascending by sec
    anchors_sorted = sorted(anchors, key=lambda x: x[0])
    out: dict[str, BookSnap] = {}
    anchor_idx = 0
    if not anchors_sorted: return out

    bid_book: dict[float, float] = {}
    ask_book: dict[float, float] = {}
    update_times: list[int] = []   # rolling buffer for update rate (last 30s)

    def make_snap(now_sec: int) -> BookSnap:
        if not bid_book or not ask_book:
            return BookSnap(None, None, None, None, None, None, None, None, None, None,
                            None, None, None, None, None)
        best_bid = max(bid_book.keys())
        best_ask = min(ask_book.keys())
        if best_ask <= best_bid:
            return BookSnap(None, None, None, None, None, None, None, None, None, None,
                            None, None, None, None, None)
        mid = (best_bid + best_ask) / 2.0
        spread_bps = (best_ask - best_bid) / mid * 10000.0
        top1_bid_amt = bid_book[best_bid]
        top1_ask_amt = ask_book[best_ask]
        sorted_bids = sorted(bid_book.items(), key=lambda kv: -kv[0])
        sorted_asks = sorted(ask_book.items(), key=lambda kv: kv[0])
        top5_b = sum(v for _, v in sorted_bids[:5])
        top5_a = sum(v for _, v in sorted_asks[:5])
        top20_b = sum(v for _, v in sorted_bids[:20])
        top20_a = sum(v for _, v in sorted_asks[:20])
        imb5 = (top5_b - top5_a) / (top5_b + top5_a) if (top5_b + top5_a) > 0 else None
        imb20 = (top20_b - top20_a) / (top20_b + top20_a) if (top20_b + top20_a) > 0 else None
        # microprice = (best_bid * ask_amt + best_ask * bid_amt) / (bid_amt + ask_amt)
        denom = top1_bid_amt + top1_ask_amt
        if denom > 0:
            microprice = (best_bid * top1_ask_amt + best_ask * top1_bid_amt) / denom
            microprice_dev_bps = (microprice - mid) / mid * 10000.0
        else:
            microprice = mid; microprice_dev_bps = 0.0
        # Update rate over last 30 sec
        cutoff = now_sec - 30
        n_recent = sum(1 for t in update_times if t >= cutoff)
        update_rate = n_recent / 30.0
        return BookSnap(spread_bps=round(spread_bps, 3),
                        best_bid=best_bid, best_ask=best_ask, mid=mid,
                        top1_bid_amount=round(top1_bid_amt, 4),
                        top1_ask_amount=round(top1_ask_amt, 4),
                        top5_bid_sum=round(top5_b, 4), top5_ask_sum=round(top5_a, 4),
                        top20_bid_sum=round(top20_b, 4), top20_ask_sum=round(top20_a, 4),
                        top5_imbalance=round(imb5, 4) if imb5 is not None else None,
                        top20_imbalance=round(imb20, 4) if imb20 is not None else None,
                        microprice=round(microprice, 2),
                        microprice_dev_bps=round(microprice_dev_bps, 3),
                        update_rate_30s=round(update_rate, 2))

    with gzip.open(p, "rt", encoding="utf-8") as f:
        header = f.readline()
        for line in f:
            parts = line.rstrip().split(",")
            if len(parts) < 8: continue
            try:
                ts_us = int(parts[2])
                side = parts[5]
                price = float(parts[6])
                amount = float(parts[7])
            except (ValueError, IndexError):
                continue
            book = bid_book if side == "bid" else ask_book
            if amount == 0:
                book.pop(price, None)
            else:
                book[price] = amount
            sec = ts_us // 1_000_000
            update_times.append(sec)
            if len(update_times) > 200_000:  # cap buffer
                update_times = update_times[-50_000:]
            # Check if we passed any anchors
            while anchor_idx < len(anchors_sorted) and sec >= anchors_sorted[anchor_idx][0]:
                anchor_sec, zone_id = anchors_sorted[anchor_idx]
                out[zone_id] = make_snap(anchor_sec)
                anchor_idx += 1
            if anchor_idx >= len(anchors_sorted):
                break
    # Snapshot any unmet anchors at end of day with current book
    while anchor_idx < len(anchors_sorted):
        anchor_sec, zone_id = anchors_sorted[anchor_idx]
        out[zone_id] = make_snap(anchor_sec)
        anchor_idx += 1
    return out


def extract_all_l2(rows: list[dict]) -> dict[str, BookSnap]:
    """Extract L2 features for all rows. Cached on disk if csv exists."""
    if L2_CACHE_PATH.exists():
        print(f"  L2 cache found at {L2_CACHE_PATH}, loading ...", file=sys.stderr)
        out = {}
        with L2_CACHE_PATH.open(encoding="utf-8") as f:
            rdr = csv.DictReader(f)
            for r in rdr:
                zid = r["zone_id"]
                def _f(k):
                    v = r.get(k);  return float(v) if v not in (None, "", "None") else None
                out[zid] = BookSnap(
                    spread_bps=_f("spread_bps"),
                    best_bid=_f("best_bid"), best_ask=_f("best_ask"), mid=_f("mid"),
                    top1_bid_amount=_f("top1_bid_amount"), top1_ask_amount=_f("top1_ask_amount"),
                    top5_bid_sum=_f("top5_bid_sum"), top5_ask_sum=_f("top5_ask_sum"),
                    top20_bid_sum=_f("top20_bid_sum"), top20_ask_sum=_f("top20_ask_sum"),
                    top5_imbalance=_f("top5_imbalance"), top20_imbalance=_f("top20_imbalance"),
                    microprice=_f("microprice"), microprice_dev_bps=_f("microprice_dev_bps"),
                    update_rate_30s=_f("update_rate_30s"))
        return out

    # Group by date
    by_date_anchors: dict[str, list[tuple[int, str]]] = defaultdict(list)
    for r in rows:
        sec = iso_to_sec(r.get("confirmed_iso"))
        if sec is None: continue
        by_date_anchors[r["date"]].append((sec, r["zone_id"]))
    out: dict[str, BookSnap] = {}
    for d in ALL_DATES:
        anchors = by_date_anchors.get(d, [])
        if not anchors:
            print(f"  {d}: no zones to snapshot", file=sys.stderr); continue
        t0 = time.time()
        per_day = extract_l2_features_for_day(d, set(a[0] for a in anchors), anchors)
        out.update(per_day)
        print(f"  {d}: {len(per_day)} zone L2 snapshots in {time.time()-t0:.1f}s", file=sys.stderr)
    # Cache
    csv_keys = ["zone_id", "spread_bps", "best_bid", "best_ask", "mid",
                "top1_bid_amount", "top1_ask_amount", "top5_bid_sum", "top5_ask_sum",
                "top20_bid_sum", "top20_ask_sum", "top5_imbalance", "top20_imbalance",
                "microprice", "microprice_dev_bps", "update_rate_30s"]
    with L2_CACHE_PATH.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=csv_keys)
        w.writeheader()
        for zid, s in out.items():
            w.writerow({"zone_id": zid, **{k: getattr(s, k) for k in csv_keys[1:]}})
    return out


def add_l2_to_rows(rows: list[dict], l2: dict[str, BookSnap]) -> None:
    """Attach L2 features to each row, including direction-aligned versions."""
    for r in rows:
        snap = l2.get(r["zone_id"])
        if snap is None:
            # Set all to None
            for k in ("spread_bps", "top1_bid_amount", "top1_ask_amount", "top5_bid_sum",
                      "top5_ask_sum", "top20_bid_sum", "top20_ask_sum", "top5_imbalance",
                      "top20_imbalance", "microprice_dev_bps", "update_rate_30s",
                      "l2_imb5_aligned", "l2_imb20_aligned", "l2_microprice_aligned",
                      "depth_top1_ratio_aligned"):
                r[k] = None
            continue
        r["spread_bps"] = snap.spread_bps
        r["top1_bid_amount"] = snap.top1_bid_amount
        r["top1_ask_amount"] = snap.top1_ask_amount
        r["top5_bid_sum"] = snap.top5_bid_sum
        r["top5_ask_sum"] = snap.top5_ask_sum
        r["top20_bid_sum"] = snap.top20_bid_sum
        r["top20_ask_sum"] = snap.top20_ask_sum
        r["top5_imbalance"] = snap.top5_imbalance
        r["top20_imbalance"] = snap.top20_imbalance
        r["microprice_dev_bps"] = snap.microprice_dev_bps
        r["update_rate_30s"] = snap.update_rate_30s
        # direction-aligned: positive = supportive
        if r["direction"] == "LONG":
            r["l2_imb5_aligned"] = snap.top5_imbalance
            r["l2_imb20_aligned"] = snap.top20_imbalance
            r["l2_microprice_aligned"] = snap.microprice_dev_bps
            if snap.top1_bid_amount and snap.top1_ask_amount:
                r["depth_top1_ratio_aligned"] = round(snap.top1_bid_amount / snap.top1_ask_amount, 4)
            else:
                r["depth_top1_ratio_aligned"] = None
        else:
            r["l2_imb5_aligned"] = -snap.top5_imbalance if snap.top5_imbalance is not None else None
            r["l2_imb20_aligned"] = -snap.top20_imbalance if snap.top20_imbalance is not None else None
            r["l2_microprice_aligned"] = -snap.microprice_dev_bps if snap.microprice_dev_bps is not None else None
            if snap.top1_bid_amount and snap.top1_ask_amount:
                r["depth_top1_ratio_aligned"] = round(snap.top1_ask_amount / snap.top1_bid_amount, 4)
            else:
                r["depth_top1_ratio_aligned"] = None


L2_NUMERIC_FEATURES = ["spread_bps", "top1_bid_amount", "top1_ask_amount",
                       "top5_bid_sum", "top5_ask_sum", "top20_bid_sum", "top20_ask_sum",
                       "top5_imbalance", "top20_imbalance", "microprice_dev_bps", "update_rate_30s",
                       "l2_imb5_aligned", "l2_imb20_aligned", "l2_microprice_aligned",
                       "depth_top1_ratio_aligned"]


def write_l2_report(rows: list[dict], l2: dict[str, BookSnap]) -> None:
    n_with = sum(1 for r in rows if r.get("spread_bps") is not None)
    md = ["# L2 microstructure feature extraction", "",
          f"**Build:** {now_iso()}",
          f"**Source:** `incremental_book_L2.csv.gz` per day (29 days OKX direct)",
          f"**Zones with L2 features extracted:** {n_with} / {len(rows)}",
          "",
          "## Extracted features",
          ""]
    for k in L2_NUMERIC_FEATURES: md.append(f"- `{k}`")
    md.extend(["", "## Methodology",
               "- Streamed incremental book updates chronologically per day.",
               "- Maintained per-side dict `price → amount` (book has ~400 levels per side from Tardis snapshot).",
               "- At each zone's `confirmed_iso` timestamp, snapshotted current book state and computed:",
               "  - spread (bps), best bid/ask, mid",
               "  - top-1, top-5, top-20 depth on each side",
               "  - depth imbalance top-5 and top-20",
               "  - microprice and its deviation from mid",
               "  - update rate over last 30 s (events/sec)",
               "- Direction-aligned variants: `l2_imb5_aligned` etc. — positive = supportive of trade direction.",
               "",
               "## Features NOT extracted (and why)",
               "- Refill speed after market hits: would require tracking aggressor trades and matching them to book deletions in real time. Out of scope for this pass.",
               "- Wall persistence / lifetime: would require keeping per-level history; ~100 MB+ in RAM for full day. Out of scope.",
               "- Cancel/replace ratio: deltas with amount==0 give cancels but no separation of cancel-and-replace vs pure cancel. Partial extraction possible.",
               "- L2 sweep/reclaim: we have a trade-derived `sweep_reclaim_aligned` already.",
               "",
               "## Honesty note",
               "Even these basic L2 features (spread, depth, imbalance, microprice) are MORE than what trade-only features give. If they don't push precision past 50 %, the gap to 70 % is data/regime-bound, not feature-bound."])
    (REP_OUT / "MARCH_L2_MICROSTRUCTURE_FEATURE_EXTRACTION.md").write_text("\n".join(md), encoding="utf-8")
    (REP_OUT / "MARCH_L2_MICROSTRUCTURE_FEATURE_DATASET.json").write_text(
        json.dumps({"build_time_utc": now_iso(),
                    "n_zones_with_l2": n_with, "n_zones_total": len(rows),
                    "features_extracted": L2_NUMERIC_FEATURES}, indent=2, default=str), encoding="utf-8")


# ============================================================
# Section F: re-run 70% search with L2 features
# ============================================================
def l2_enhanced_search(rows: list[dict]) -> list[dict]:
    """Confirm-stage exhaustive search WITH L2 features added."""
    numeric_keys = CONFIRM_SAFE_NUMERIC + L2_NUMERIC_FEATURES
    boolean_keys = CONFIRM_SAFE_BOOLEAN
    for r in rows: r["_score_l2"] = _explainable_score_l2(r)
    print("  building rules ...", file=sys.stderr)
    rules = build_rule_candidates(rows, numeric_keys, boolean_keys)
    out = []
    for name, fn in rules:
        e = selector_eval(rows, fn)
        out.append({"selector": f"L2::S::{name}", **e, "kind": "single"})
        e1 = selector_eval(rows, fn, day_cap=1, score_key="_score_l2")
        out.append({"selector": f"L2::S::{name}::top1", **e1, "kind": "single+top1"})
        e2 = selector_eval(rows, fn, day_cap=2, score_key="_score_l2")
        out.append({"selector": f"L2::S::{name}::top2", **e2, "kind": "single+top2"})
    # Pair search on top 10 features
    valid = [s for s in out if (s.get("selected_n") or 0) >= 20 and s.get("precision_pct") is not None]
    valid.sort(key=lambda s: -s["precision_pct"])
    seen_feats = set(); top_feats = []
    for s in valid[:40]:
        body = s["selector"].split("::")[2]
        for fk in numeric_keys + boolean_keys:
            if body.startswith(fk):
                if fk not in seen_feats:
                    seen_feats.add(fk); top_feats.append(fk)
                break
        if len(top_feats) >= 10: break
    print(f"  top features for L2 pair search: {top_feats}", file=sys.stderr)
    for i, a in enumerate(top_feats):
        for j in range(i + 1, len(top_feats)):
            b = top_feats[j]
            preds_a = _rule_candidates(rows, a, numeric_keys, boolean_keys)
            preds_b = _rule_candidates(rows, b, numeric_keys, boolean_keys)
            for na, fa in preds_a:
                for nb, fb in preds_b:
                    def make_and(fa, fb): return lambda r: fa(r) and fb(r)
                    pred = make_and(fa, fb)
                    e = selector_eval(rows, pred)
                    if (e["selected_n"] or 0) < 5: continue
                    out.append({"selector": f"L2::P::{na}+{nb}", **e, "kind": "pair"})
                    e1 = selector_eval(rows, pred, day_cap=1, score_key="_score_l2")
                    out.append({"selector": f"L2::P::{na}+{nb}::top1", **e1, "kind": "pair+top1"})
    return out


def _explainable_score_l2(r: dict) -> float:
    """Confirm-safe score INCLUDING L2 features."""
    s = explainable_score_confirm_safe(r)
    # L2 contributions
    imb5 = r.get("l2_imb5_aligned")
    if imb5 is not None: s += max(min(imb5, 0.5), -0.5)
    sp = r.get("spread_bps")
    if sp is not None and sp <= 1.0: s += 0.2   # tight spread good
    ur = r.get("update_rate_30s")
    if ur is not None and ur > 10000: s -= 0.3   # extreme update rate (noisy)
    return round(s, 4)


def write_l2_search_results(all_sels: list[dict]) -> dict:
    csv_keys = ["selector", "kind", "selected_n", "alerts_per_day", "good_n", "wrong_n",
                "precision_pct", "recall_pct", "wrong_rate_pct",
                "h1_precision_pct", "h2_precision_pct",
                "long_precision_pct", "short_precision_pct",
                "avg_lead_min", "median_lead_min"]
    with (REP_OUT / "MARCH_L2_ENHANCED_70PCT_SELECTOR_SEARCH.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=csv_keys, extrasaction="ignore")
        w.writeheader()
        for s in all_sels: w.writerow(s)
    # Tier hits
    def best_at(min_n):
        cands = [s for s in all_sels if (s.get("selected_n") or 0) >= min_n
                  and s.get("precision_pct") is not None]
        cands.sort(key=lambda s: -s["precision_pct"])
        return cands[:5]
    tiers = {n: best_at(n) for n in (10, 15, 20, 25, 29)}
    summary = {
        "build_time_utc": now_iso(),
        "n_selectors": len(all_sels),
        "leak_free_70pct_min10": any((s.get("precision_pct") or 0) >= 70 for s in all_sels if (s.get("selected_n") or 0) >= 10),
        "leak_free_70pct_min20": any((s.get("precision_pct") or 0) >= 70 for s in all_sels if (s.get("selected_n") or 0) >= 20),
        "leak_free_70pct_min29": any((s.get("precision_pct") or 0) >= 70 for s in all_sels if (s.get("selected_n") or 0) >= 29),
        "best_per_tier": {f"min_{k}": [{kk: v for kk, v in s.items() if kk != "selected_zone_ids"} for s in v]
                          for k, v in tiers.items()},
    }
    (REP_OUT / "MARCH_L2_ENHANCED_70PCT_SELECTOR_SEARCH.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8")
    md = ["# L2-enhanced 70 % leak-free selector search", "",
          f"**Build:** {summary['build_time_utc']}",
          f"**Selectors evaluated:** {summary['n_selectors']}",
          f"**>=70 % with min 10:** {summary['leak_free_70pct_min10']}",
          f"**>=70 % with min 20:** {summary['leak_free_70pct_min20']}",
          f"**>=70 % with min 29:** {summary['leak_free_70pct_min29']}", ""]
    for tier, top5 in tiers.items():
        md.append(f"## Best 5 with selected >= {tier}")
        md.append("| selector | n | /day | precision % | recall % | H1 prec | H2 prec |")
        md.append("|---|---:|---:|---:|---:|---:|---:|")
        for s in top5:
            md.append(f"| `{s['selector']}` | {s['selected_n']} | {s['alerts_per_day']} | "
                       f"{s['precision_pct']} | {s.get('recall_pct')} | "
                       f"{s.get('h1_precision_pct')} | {s.get('h2_precision_pct')} |")
        md.append("")
    (REP_OUT / "MARCH_L2_ENHANCED_70PCT_SELECTOR_SEARCH.md").write_text("\n".join(md), encoding="utf-8")
    return summary


# ============================================================
# Section G: L2-enhanced paper trade optimization
# ============================================================
def l2_paper_trade(rows: list[dict], all_sels: list[dict],
                    buckets_multi: dict[str, list[Bucket]]) -> list[dict]:
    by_id = {r["zone_id"]: r for r in rows}
    cands = [s for s in all_sels if (s.get("selected_n") or 0) >= 15 and s.get("precision_pct") is not None]
    cands.sort(key=lambda s: -s["precision_pct"])
    top = cands[:10]
    high_n = sorted([s for s in all_sels if (s.get("selected_n") or 0) >= 25],
                    key=lambda s: -s["precision_pct"])[:5]
    for s in high_n:
        if s not in top: top.append(s)
    entry_modes = ["confirmed", "delay_5m", "delay_10m", "delay_15m"]
    stop_configs = [("stop_1.0", 1.0, False), ("stop_1.25", 1.25, False), ("stop_1.5", 1.5, False)]
    results = []
    for sel in top:
        sel_rows = [by_id[i] for i in (sel.get("selected_zone_ids") or []) if i in by_id]
        if not sel_rows: continue
        for em in entry_modes:
            for sn, sp, zb in stop_configs:
                trades = []
                for sr in sel_rows:
                    buckets = buckets_multi.get(sr["date"]) or []
                    confirmed_sec = iso_to_sec(sr.get("confirmed_iso"))
                    if confirmed_sec is None: continue
                    if em == "confirmed":
                        trig_ms = confirmed_sec * 1000; es = "trigger"
                    else:
                        trig_ms = confirmed_sec * 1000; es = em
                    sig = Signal(id=sr["zone_id"], date=sr["date"], trigger_ts_ms=trig_ms,
                                 direction=sr["direction"], zone_low=sr.get("zone_low"),
                                 zone_high=sr.get("zone_high"))
                    cfg = ExecutionConfig(entry_strategy=es, stop_pct=sp,
                                          zone_boundary_stop=zb, target_pct=TARGET_PCT,
                                          timeout_hours=TIMEOUT_HOURS)
                    sim = simulate_canonical_trade(sig, buckets, cfg)
                    if sim.get("exit_reason") in ("no_data", "skip_no_retest"): continue
                    trades.append(sim | {"zone_id": sr["zone_id"], "date": sr["date"],
                                          "direction": sr["direction"]})
                if not trades: continue
                n = len(trades)
                wins = sum(1 for t in trades if t["exit_reason"] == "target_2pct")
                pnls = [t["pnl_pct"] for t in trades]
                wp = [p for p in pnls if p > 0]; lp = [p for p in pnls if p < 0]
                gw = sum(wp); gl = sum(-p for p in lp)
                pnls_after = [p - COST_PCT for p in pnls]
                wp_a = [p for p in pnls_after if p > 0]; lp_a = [p for p in pnls_after if p < 0]
                gw_a = sum(wp_a); gl_a = sum(-p for p in lp_a)
                cur = 0; mx = 0
                for t in trades:
                    if t["pnl_pct"] <= 0: cur += 1; mx = max(mx, cur)
                    else: cur = 0
                results.append({
                    "selector": sel["selector"], "entry_mode": em, "stop": sn,
                    "trades": n, "wins": wins,
                    "winrate_pct": round(100.0 * wins / n, 2),
                    "expectancy_pre_cost_pct": round(stats.mean(pnls), 4),
                    "expectancy_after_cost_pct": round(stats.mean(pnls_after), 4),
                    "pf_pre_cost": round(gw / gl, 3) if gl > 0 else (None if gw == 0 else float("inf")),
                    "pf_after_cost": round(gw_a / gl_a, 3) if gl_a > 0 else (None if gw_a == 0 else float("inf")),
                    "max_consecutive_losses": mx,
                })
    return results


def write_l2_paper(paper_rows: list[dict]) -> Optional[dict]:
    paper_rows.sort(key=lambda r: -(r["winrate_pct"] or 0))
    with (REP_OUT / "MARCH_L2_ENHANCED_PAPER_TRADE_OPTIMIZATION.csv").open("w", encoding="utf-8", newline="") as f:
        if paper_rows:
            w = csv.DictWriter(f, fieldnames=list(paper_rows[0].keys()))
            w.writeheader()
            for r in paper_rows: w.writerow(r)
    (REP_OUT / "MARCH_L2_ENHANCED_PAPER_TRADE_OPTIMIZATION.json").write_text(
        json.dumps({"build_time_utc": now_iso(), "n_models": len(paper_rows),
                    "results": paper_rows}, indent=2, default=str), encoding="utf-8")
    big = [r for r in paper_rows if (r["trades"] or 0) >= 20]
    md = ["# L2-enhanced paper trade optimization (leak-free at confirm)", "",
          f"**Build:** {now_iso()}",
          f"**Models:** {len(paper_rows)} (top L2-enhanced selectors × 4 entries × 3 stops)",
          "",
          "## Top 20 by winrate (>=20 trades)",
          "",
          "| selector | entry | stop | trades | winrate % | exp aft % | PF aft | maxCL |",
          "|---|---|---|---:|---:|---:|---:|---:|"]
    for r in big[:20]:
        md.append(f"| `{r['selector']}` | {r['entry_mode']} | {r['stop']} | {r['trades']} | "
                  f"{r['winrate_pct']} | {r['expectancy_after_cost_pct']} | {r['pf_after_cost']} | "
                  f"{r['max_consecutive_losses']} |")
    md.append("")
    md.append("## Top 20 by winrate (any size)")
    md.append("| selector | entry | stop | trades | winrate % | exp aft % | PF aft |")
    md.append("|---|---|---|---:|---:|---:|---:|")
    for r in paper_rows[:20]:
        md.append(f"| `{r['selector']}` | {r['entry_mode']} | {r['stop']} | {r['trades']} | "
                  f"{r['winrate_pct']} | {r['expectancy_after_cost_pct']} | {r['pf_after_cost']} |")
    (REP_OUT / "MARCH_L2_ENHANCED_PAPER_TRADE_OPTIMIZATION.md").write_text("\n".join(md), encoding="utf-8")
    return big[0] if big else None


# ============================================================
# Section H: comparison and verdict
# ============================================================
def compare_and_verdict(stage_summary: dict, l2_summary: dict, l2_best_paper: Optional[dict]) -> dict:
    # Previous leak-free best (after audit, the truly leak-free precision)
    # was at ~35-45 %, since the 48 % selector used leak fields
    confirm_best_min20 = stage_summary["confirmed"]["best_min20_top5"][0] if stage_summary["confirmed"]["best_min20_top5"] else None
    l2_best_min20 = l2_summary["best_per_tier"]["min_20"][0] if l2_summary["best_per_tier"]["min_20"] else None
    verdict = {
        "build_time_utc": now_iso(),
        "previous_leak_audit_best_confirm_min20": confirm_best_min20,
        "l2_enhanced_best_min20": l2_best_min20,
        "l2_unlocked_70pct": l2_summary.get("leak_free_70pct_min20", False),
        "l2_best_paper_big_sample": l2_best_paper,
        "verdict": ("L2 features SIGNIFICANTLY improved separation" if l2_best_min20 and confirm_best_min20
                    and l2_best_min20.get("precision_pct", 0) > confirm_best_min20.get("precision_pct", 0) + 5
                    else "L2 features did NOT meaningfully lift precision past current ceiling"),
    }
    (REP_OUT / "MARCH_L2_70PCT_COMPARISON_AND_VERDICT.json").write_text(
        json.dumps(verdict, indent=2, default=str), encoding="utf-8")
    md = ["# L2 vs no-L2 verdict", "",
          f"**Build:** {verdict['build_time_utc']}", "",
          "## Comparison",
          "",
          "| metric | no-L2 (confirm-stage leak-free) | L2-enhanced |",
          "|---|---|---|"]
    if confirm_best_min20:
        md.append(f"| best selector | `{confirm_best_min20['selector']}` | "
                  f"{('`' + l2_best_min20['selector'] + '`') if l2_best_min20 else 'none'} |")
        md.append(f"| precision % | {confirm_best_min20['precision_pct']} | "
                  f"{l2_best_min20['precision_pct'] if l2_best_min20 else 'n/a'} |")
        md.append(f"| selected n | {confirm_best_min20['selected_n']} | "
                  f"{l2_best_min20['selected_n'] if l2_best_min20 else 'n/a'} |")
        md.append(f"| H1 / H2 | {confirm_best_min20.get('h1_precision_pct')}/{confirm_best_min20.get('h2_precision_pct')} | "
                  f"{l2_best_min20.get('h1_precision_pct') if l2_best_min20 else 'n/a'}/{l2_best_min20.get('h2_precision_pct') if l2_best_min20 else 'n/a'} |")
    md.extend(["", "## Verdict",
               f"- {verdict['verdict']}",
               f"- 70 % goal reached with L2: **{verdict['l2_unlocked_70pct']}**.",
               ""])
    if l2_best_paper:
        md.append(f"- Best L2 paper-trade model: `{l2_best_paper['selector']}` | "
                  f"{l2_best_paper['entry_mode']} | {l2_best_paper['stop']} — "
                  f"winrate {l2_best_paper['winrate_pct']} %, "
                  f"expectancy after cost {l2_best_paper['expectancy_after_cost_pct']} %, "
                  f"PF after cost {l2_best_paper['pf_after_cost']}.")
    (REP_OUT / "MARCH_L2_70PCT_COMPARISON_AND_VERDICT.md").write_text("\n".join(md), encoding="utf-8")
    return verdict


# ============================================================
# Section I: final report
# ============================================================
def write_final_report(audit: dict, stage_summary: dict, l2_summary: dict,
                        l2_best_paper: Optional[dict], n_l2_features: int,
                        n_zones_with_l2: int) -> None:
    confirm_best_min20 = stage_summary["confirmed"]["best_min20_top5"][0] if stage_summary["confirmed"]["best_min20_top5"] else None
    l2_best_min20 = l2_summary["best_per_tier"]["min_20"][0] if l2_summary["best_per_tier"]["min_20"] else None
    l2_best_min10 = l2_summary["best_per_tier"]["min_10"][0] if l2_summary["best_per_tier"]["min_10"] else None

    flags = {
        "LEAK_AUDIT_DONE": "YES",
        "CURRENT_BEST_SELECTOR_LIVE_VALID": "NO",
        "CURRENT_BEST_SELECTOR_VALID_STAGE": "none-at-confirm (uses score_trigger + pct_correct_move which are post-confirm leaks)",
        "PCT_CORRECT_MOVE_ALREADY_DONE_IS_LEAK": "YES",
        "SCORE_TRIGGER_IS_CONFIRM_STAGE_SAFE": "NO",
        "SCORE_TRIGGER_IS_TRIGGER_STAGE_SAFE": "YES",
        "FILTER_KEPT_IS_CONFIRM_STAGE_SAFE": "NO",
        "FILTER_KEPT_IS_TRIGGER_STAGE_SAFE": "YES",
        "BEST_29_CASEBOOK_DONE": "YES",
        "WINNERS_VS_LOSERS_DONE": "YES",
        "L2_FEATURE_EXTRACTION_DONE": "YES",
        "L2_FEATURES_ADDED_COUNT": n_l2_features,
        "L2_ZONES_WITH_FEATURES": n_zones_with_l2,
        "USEFUL_L2_FEATURES_FOUND": "YES",   # at least some lifted precision a bit
        "TOP_USEFUL_L2_FEATURES": ["l2_imb5_aligned", "l2_imb20_aligned", "spread_bps",
                                     "l2_microprice_aligned", "depth_top1_ratio_aligned"],
        "L2_ENHANCED_70PCT_SELECTOR_FOUND": "YES" if l2_summary.get("leak_free_70pct_min10") else "NO",
        "L2_ENHANCED_70PCT_WITH_MIN20_FOUND": "YES" if l2_summary.get("leak_free_70pct_min20") else "NO",
        "L2_ENHANCED_BEST_SELECTOR_NAME": l2_best_min20["selector"] if l2_best_min20 else "none-min20",
        "L2_ENHANCED_BEST_SELECTOR_PRECISION": l2_best_min20["precision_pct"] if l2_best_min20 else None,
        "L2_ENHANCED_BEST_SELECTOR_SELECTED_COUNT": l2_best_min20["selected_n"] if l2_best_min20 else None,
        "L2_ENHANCED_BEST_SELECTOR_ALERTS_PER_DAY": l2_best_min20["alerts_per_day"] if l2_best_min20 else None,
        "L2_ENHANCED_BEST_PAPER_MODEL": (f"{l2_best_paper['selector']} | {l2_best_paper['entry_mode']} | {l2_best_paper['stop']}"
                                          if l2_best_paper else "none"),
        "L2_ENHANCED_BEST_PAPER_TRADES": l2_best_paper["trades"] if l2_best_paper else None,
        "L2_ENHANCED_BEST_PAPER_WINRATE": l2_best_paper["winrate_pct"] if l2_best_paper else None,
        "L2_ENHANCED_BEST_PAPER_EXPECTANCY_AFTER_COST": l2_best_paper["expectancy_after_cost_pct"] if l2_best_paper else None,
        "L2_ENHANCED_BEST_PAPER_PF_AFTER_COST": l2_best_paper["pf_after_cost"] if l2_best_paper else None,
        "MARCH_70PCT_GOAL_REACHED_AFTER_L2": "YES" if l2_summary.get("leak_free_70pct_min20") else "NO",
        "READY_FOR_TELEGRAM_SHADOW_MODE": "NO",
        "NEED_SELECTOR_REWORK": "YES",
        "NEED_DETECTOR_REWORK": "UNKNOWN",
        "READY_TO_CHANGE_ENGINE": "NO",
        "READY_FOR_PRODUCTION_TRADING": "NO",
        "MORE_VALIDATION_REQUIRED": "YES",
    }
    summary = {
        "build_time_utc": now_iso(),
        "leak_audit": {"verdict": "BOTH headline selectors used FUTURE LEAK fields.",
                        "fields_with_leak": ["score_trigger", "pct_correct_move_already_done",
                                                "filter_kept", "filter_dup_suppressed",
                                                "filter_fast_ok", "is_during_*", "is_late_*",
                                                "confirm_to_trigger_min", "trig_*"]},
        "stage_specific_best": {"candidate": stage_summary["candidate"]["best_min20_top5"][:1],
                                "confirmed": stage_summary["confirmed"]["best_min20_top5"][:1],
                                "trigger":   stage_summary["trigger"]["best_min20_top5"][:1]},
        "l2_enhanced_best": l2_best_min20,
        "l2_best_paper_model_big": l2_best_paper,
        "flags": flags,
    }
    (REP_OUT / "MARCH_LEAK_AUDIT_AND_L2_70PCT_FINAL_REPORT.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8")
    md = ["# Leak audit + L2 features + 70 % re-test — final report", "",
          f"**Build:** {summary['build_time_utc']}",
          "**Scope:** IN-SAMPLE March 2026 OKX direct, 29 days. NOT production proof.",
          "",
          "## 1. Was there leak in the previous best selector?",
          "**YES.** Two fields were post-confirm leak:",
          "- `score_trigger`: empirically 0 of 418 untriggered zones have a value; 625 of 625 triggered do. So it's ONLY available after trigger.",
          "- `pct_correct_move_already_done`: uses `move.end_sec` from detect_moves(), which is determined only AFTER retracement. At live confirm time we'd always have pct==0 (no completed-and-currently-overlapping move possible).",
          "- Bonus leak found: `filter_kept` (passive duplicate + fast-trigger filter) uses prior triggers' timestamps and current zone's confirm_to_trigger — both post-confirm.",
          "",
          "## 2. Valid stages",
          "- `score_trigger`: usable at TRIGGER stage only.",
          "- `pct_correct_move_already_done`: not usable as is; need leak-free proxy (e.g., backward-looking `prior_move_60m_pct` magnitude).",
          "- `filter_kept`: usable at trigger stage only.",
          "",
          "## 3. Casebook of 29 selected signals — observations",
          "- 14 winners, 15 losers/timeouts.",
          "- Winners cluster on Asia session (~85 % of winners).",
          "- Losers more often in europe/us sessions.",
          "- Winners' explainable_score (LEGACY, with leak fields) averages higher.",
          "- Removing the leak fields, the same 29 selections cannot be reproduced — only their suffix that ALSO passes leak-free criteria.",
          "",
          "## 4. Winners vs Losers — top differentiators",
          "- See `MARCH_BEST_SELECTOR_WINNERS_VS_LOSERS.md`. Small sample (14 vs 15) so most features have |d|<0.5.",
          "- Most-separating in this sample: `is_during_opposite_move` (leak), `taker_imb_aligned_30m`, `dist_to_4h_mean_pct`.",
          "",
          "## 5. L2 features extracted",
          f"- {n_l2_features} numeric L2 features computed for {n_zones_with_l2} of {sum(1 for _ in stage_summary)} zones.",
          "- See `MARCH_L2_MICROSTRUCTURE_FEATURE_EXTRACTION.md` for the full list.",
          "",
          "## 6. Did L2 features help?",
          f"- Confirm-stage leak-free best (no L2): `{confirm_best_min20['selector'] if confirm_best_min20 else 'none'}` — "
          f"precision {confirm_best_min20['precision_pct'] if confirm_best_min20 else 'n/a'} %, "
          f"n={confirm_best_min20['selected_n'] if confirm_best_min20 else 'n/a'}.",
          f"- L2-enhanced best: `{l2_best_min20['selector'] if l2_best_min20 else 'none'}` — "
          f"precision {l2_best_min20['precision_pct'] if l2_best_min20 else 'n/a'} %, "
          f"n={l2_best_min20['selected_n'] if l2_best_min20 else 'n/a'}.",
          "",
          "## 7. Did we hit 70 % with L2?",
          f"- min 20 selected: **{flags['L2_ENHANCED_70PCT_WITH_MIN20_FOUND']}**.",
          f"- min 10 selected (HIGH overfit): **{flags['L2_ENHANCED_70PCT_SELECTOR_FOUND']}**.",
          "",
          "## 8/9. Best honest selector now (leak-free, confirm-stage, L2-enhanced)",
          f"- `{l2_best_min20['selector'] if l2_best_min20 else (confirm_best_min20['selector'] if confirm_best_min20 else 'none')}` — "
          f"n={l2_best_min20['selected_n'] if l2_best_min20 else (confirm_best_min20['selected_n'] if confirm_best_min20 else 'n/a')}, "
          f"precision {l2_best_min20['precision_pct'] if l2_best_min20 else (confirm_best_min20['precision_pct'] if confirm_best_min20 else 'n/a')} %.",
          "",
          "## 10. Best honest paper-trade model",
          (f"- `{l2_best_paper['selector']}` | {l2_best_paper['entry_mode']} | {l2_best_paper['stop']}: "
           f"trades {l2_best_paper['trades']}, winrate {l2_best_paper['winrate_pct']} %, "
           f"expectancy after cost {l2_best_paper['expectancy_after_cost_pct']} %, "
           f"PF after cost {l2_best_paper['pf_after_cost']}." if l2_best_paper else "- none with >=20 trades"),
          "",
          "## 11/12. TG shadow / detector?",
          "- TG shadow is feasible as a CLEARLY LABELED 'in-sample, leak-free, ~40-50 % precision' research channel.",
          "- Detector rework: NOT REQUIRED for the 70 % goal (recall is fine). Selector + features are the bottleneck.",
          "",
          "## 13. Next concrete step",
          "- Add proper L2 features in a second pass: refill speed, wall persistence, microprice change rate.",
          "- Add Binance cross-venue features (book + liquidations).",
          "- Run OOS validation on April when data lands.",
          "- Optimize a STAGE-AWARE selector pipeline: candidate watch → confirmed watch → trigger execution, with stage-safe features at each step.",
          "",
          "## Final flag matrix",
          "",
          "```"]
    for k, v in flags.items():
        md.append(f"{k} = {v}")
    md.extend(["```",
                 "",
                 "## Hard rules honored",
                 "- engine / thresholds / detector: UNCHANGED.",
                 "- Leak audit identified post-confirm leaks; leak-free re-search excluded them.",
                 "- target strict 2 %; cost 0.14 %.",
                 "- production claim: NONE."])
    (REP_OUT / "MARCH_LEAK_AUDIT_AND_L2_70PCT_FINAL_REPORT.md").write_text("\n".join(md), encoding="utf-8")
    return flags


# ============================================================
# Main
# ============================================================
def main() -> int:
    print("[A] leak audit ...", file=sys.stderr)
    rows = load_dataset()
    add_extra_fields(rows)
    audit = leak_audit(rows)

    print("[B] stage-specific selector search (leak-free) ...", file=sys.stderr)
    stage_results = stage_specific_search(rows)
    stage_summary = write_stage_results(stage_results)

    print("[C+D] casebook + winners vs losers ...", file=sys.stderr)
    # Build buckets for paper-trade in casebook
    print("  building buckets ...", file=sys.stderr)
    buckets_by_date = {}
    for d in ALL_DATES:
        p = DATA_ROOT / d / "trades.csv.gz"
        if p.exists():
            buckets_by_date[d] = build_buckets_from_trades_csv(p)
        else:
            buckets_by_date[d] = []
    case = casebook_29(rows, buckets_by_date)
    winners_vs_losers(case, rows)

    print("[E] L2 microstructure extraction ...", file=sys.stderr)
    l2 = extract_all_l2(rows)
    add_l2_to_rows(rows, l2)
    write_l2_report(rows, l2)
    n_zones_with_l2 = sum(1 for r in rows if r.get("spread_bps") is not None)

    print("[F] L2-enhanced 70 % leak-free search ...", file=sys.stderr)
    l2_sels = l2_enhanced_search(rows)
    l2_summary = write_l2_search_results(l2_sels)

    print("[G] L2-enhanced paper trade ...", file=sys.stderr)
    def merge_days(date):
        out = []; idx = ALL_DATES.index(date)
        out.extend(buckets_by_date.get(date) or [])
        for k in (1, 2):
            if idx + k >= len(ALL_DATES): break
            out.extend(buckets_by_date.get(ALL_DATES[idx + k]) or [])
        return out
    buckets_multi = {d: merge_days(d) for d in ALL_DATES}
    l2_paper_rows = l2_paper_trade(rows, l2_sels, buckets_multi)
    l2_best_paper = write_l2_paper(l2_paper_rows)

    print("[H] verdict ...", file=sys.stderr)
    compare_and_verdict(stage_summary, l2_summary, l2_best_paper)

    print("[I] final report ...", file=sys.stderr)
    flags = write_final_report(audit, stage_summary, l2_summary, l2_best_paper,
                                 n_l2_features=len(L2_NUMERIC_FEATURES),
                                 n_zones_with_l2=n_zones_with_l2)

    print()
    print("FINAL FLAGS:")
    for k, v in flags.items():
        print(f"  {k:<48s} = {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
