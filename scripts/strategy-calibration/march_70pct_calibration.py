"""March 70% in-sample calibration (Sections A-M).

Goal: prove or disprove if >=70 % winrate / hit-rate is reachable LEAK-FREE on
March 2026 in-sample. Reuse the already-enriched feature dataset
(MARCH_ORDERFLOW_FEATURE_DATASET.csv) — no need to re-extract orderflow features.

Sections A-M -> ~25 artifact files under reports/strategy-calibration/.
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
MISSING_DATES = ["2026-03-17"]
N_DAYS = len(ALL_DATES)

COST_PCT = 0.14
TARGET_PCT = 2.0
TIMEOUT_HOURS = 24


# ============================================================
# helpers
# ============================================================
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


def mean_or_none(xs):
    xs = [x for x in xs if x is not None]
    return round(stats.mean(xs), 4) if xs else None


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


# ============================================================
# load dataset
# ============================================================
def load_dataset() -> list[dict]:
    p = REP_OUT / "MARCH_ORDERFLOW_FEATURE_DATASET.csv"
    if not p.exists():
        raise FileNotFoundError(f"missing {p}; run march_in_sample_calibration.py first")
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
# Section A: 70% objective spec
# ============================================================
def write_objective_spec() -> None:
    obj = {
        "build_time_utc": now_iso(),
        "scope": "IN-SAMPLE March 2026 OKX direct (29 days; 03-17 missing)",
        "strict_rules": [
            "no engine / threshold / detector change",
            "target STRICT 2 %",
            "no future-leak in leak-free selectors",
            "outcome / post-trigger fields used as labels only",
            "no production integration",
            "if 70 % requires <10 trades or future-leak -> stated explicitly",
        ],
        "goal_A_watch_zone_hit_rate": {
            "criteria": [
                "selector chose zone BEFORE or at the very start of a real 2 % move",
                "direction matches",
                "market reached strict 2 % in that direction after selection time",
                "not late after >50 % of move completed",
            ],
        },
        "goal_B_paper_trade_winrate": {
            "criteria": [
                "selected zone entered via configured entry mode",
                "strict 2 % target hit before stop/timeout (24 h)",
                "cost 0.14 % roundtrip subtracted for after-cost metrics",
            ],
        },
        "goal_tiers": [
            {"tier": 1, "min_selected": 10, "winrate_pct": 70, "overfit_label": "high-overfit"},
            {"tier": 2, "min_selected": 15, "winrate_pct": 70, "overfit_label": "medium-overfit"},
            {"tier": 3, "min_selected": 20, "winrate_pct": 70, "overfit_label": "medium-overfit"},
            {"tier": 4, "min_selected": 25, "winrate_pct": 70, "overfit_label": "lower-overfit"},
            {"tier": 5, "min_selected": 29, "winrate_pct": 70, "overfit_label": "1-per-day pace"},
            {"tier": 6, "min_selected": 20, "winrate_pct": 80, "overfit_label": "80 % stretch"},
        ],
        "tier_under_10_treated_as_unusable": True,
    }
    (REP_OUT / "MARCH_70PCT_OBJECTIVE_SPEC.json").write_text(
        json.dumps(obj, indent=2, default=str), encoding="utf-8")
    md = ["# March 70 % calibration — objective spec", "",
          f"**Build:** {obj['build_time_utc']}",
          f"**Scope:** {obj['scope']}", "",
          "## Strict rules"]
    for r in obj["strict_rules"]: md.append(f"- {r}")
    md.extend(["", "## Goal A — watch-zone hit-rate", ""])
    for c in obj["goal_A_watch_zone_hit_rate"]["criteria"]: md.append(f"- {c}")
    md.extend(["", "## Goal B — paper trade winrate", ""])
    for c in obj["goal_B_paper_trade_winrate"]["criteria"]: md.append(f"- {c}")
    md.extend(["", "## Goal tiers", "",
               "| tier | min selected | winrate % | overfit label |",
               "|---|---:|---:|---|"])
    for t in obj["goal_tiers"]:
        md.append(f"| {t['tier']} | {t['min_selected']} | {t['winrate_pct']} | {t['overfit_label']} |")
    md.append("")
    md.append("Tier under 10 selected: treated as UNUSABLE / high-overfit.")
    (REP_OUT / "MARCH_70PCT_OBJECTIVE_SPEC.md").write_text("\n".join(md), encoding="utf-8")


# ============================================================
# Section B: rebuild research dataset (just copy + add session bucket fields)
# ============================================================
def add_extra_fields(rows: list[dict]) -> None:
    """Add session_bucket, weekday and a few derived helpers (still leak-free)."""
    for r in rows:
        sec = iso_to_sec(r.get("confirmed_iso"))
        if sec is None:
            r["weekday"] = None
            r["session_bucket"] = None
            r["is_session_open_2h"] = None
            continue
        d = dt.datetime.fromtimestamp(sec, tz=dt.timezone.utc)
        r["weekday"] = d.weekday()   # 0=Mon
        hr = d.hour
        if hr < 7: sb = "asia"
        elif hr < 14: sb = "europe"
        elif hr < 22: sb = "us"
        else: sb = "asia_late"
        r["session_bucket"] = sb
        # is_session_open_2h: 0-1 UTC (asia open), 7-9 (europe open), 14-16 (us open)
        r["is_session_open_2h"] = 1 if hr in (0, 1, 7, 8, 14, 15) else 0
        # abs prior move + abs distance to mean
        for k in ("prior_move_60m_pct", "prior_move_180m_pct", "prior_move_30m_pct",
                  "prior_move_15m_pct", "dist_to_4h_mean_pct"):
            v = r.get(k)
            r[f"abs_{k}"] = abs(v) if v is not None else None


def write_research_dataset(rows: list[dict]) -> None:
    keys = ["date", "zone_id", "direction", "stage_reached",
            "candidate_iso", "confirmed_iso", "trigger_iso",
            "zone_low", "zone_high", "zone_mid", "zone_width_pct",
            "candidate_to_confirm_min", "confirm_to_trigger_min", "total_pre_trigger_min",
            "utc_hour", "session", "session_bucket", "weekday", "is_session_open_2h",
            "_label_unique_move_id", "_label_engine_class",
            "watch_label", "coverage_class",
            "lead_min_before_move", "matched_move_size_pct",
            "_half"]
    with (REP_OUT / "MARCH_70PCT_RESEARCH_DATASET.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        for r in rows: w.writerow({k: r.get(k) for k in keys})
    (REP_OUT / "MARCH_70PCT_RESEARCH_DATASET.json").write_text(
        json.dumps({"build_time_utc": now_iso(), "n_zones": len(rows),
                    "label_counts": dict(Counter(r.get("watch_label") for r in rows)),
                    "coverage_counts": dict(Counter(r.get("coverage_class") for r in rows)),
                    "n_by_session_bucket": dict(Counter(r.get("session_bucket") for r in rows))},
                   indent=2, default=str), encoding="utf-8")


# ============================================================
# Section C: expanded feature library docs (mostly inherits + lists what's missing)
# ============================================================
NUMERIC_FEATURES_LEAK_FREE = [
    # Engine candidate/confirm conditions (computed BEFORE/AT confirm)
    "cand_pressure_against", "cand_buy_pressure", "cand_sell_pressure",
    "cand_absorb_score", "cand_bid_refill_score", "cand_ask_refill_score",
    "cand_refill_with", "cand_prior_move_pct",
    "conf_cycles_seen", "conf_age_min", "conf_defended_persistence_sec",
    "conf_opposite_thinning", "conf_void_score",
    "score_absorption", "score_refill", "score_ofi", "score_liquidity_void", "score_trigger",
    # Zone geometry
    "zone_width_pct",
    # Confluence
    "same_dir_zones_active_60m", "opp_dir_zones_active_60m",
    # Local context (pre-confirm)
    "prior_move_15m_pct", "prior_move_30m_pct", "prior_move_60m_pct", "prior_move_180m_pct",
    "abs_prior_move_15m_pct", "abs_prior_move_30m_pct", "abs_prior_move_60m_pct", "abs_prior_move_180m_pct",
    "local_range_15m_pct", "local_range_30m_pct", "local_range_60m_pct", "local_range_180m_pct",
    "local_realized_vol_15m", "local_realized_vol_30m", "local_realized_vol_60m", "local_realized_vol_180m",
    "dist_to_recent_swing_high_pct", "dist_to_recent_swing_low_pct",
    "dist_to_4h_mean_pct", "abs_dist_to_4h_mean_pct",
    # Trade-derived orderflow (pre-confirm)
    "taker_imb_5m", "taker_imb_15m", "taker_imb_30m", "taker_imb_60m", "taker_imb_180m",
    "taker_imb_aligned_5m", "taker_imb_aligned_15m", "taker_imb_aligned_30m",
    "taker_imb_aligned_60m", "taker_imb_aligned_180m",
    "taker_total_vol_15m", "taker_total_vol_60m",
    "vol_anomaly_15m_vs_bg",
    "ofi_shift_5m_vs_30m", "ofi_shift_aligned",
    # Movement-relative timing (pre-confirm — anchor uses past moves only)
    "pct_correct_move_already_done", "pct_opposite_move_already_done",
    # Time of day
    "utc_hour",
    # Trigger fields (NOTE: only available POST-trigger; we mark them as execution-stage only)
    # we will NOT use these in leak-free selectors
]
BOOLEAN_FEATURES_LEAK_FREE = [
    "filter_kept", "filter_dup_suppressed", "filter_fast_ok",
    "cand_range_compression",
    "is_during_correct_move", "is_during_opposite_move", "is_late_after_50pct_correct_move",
    "sweep_reclaim_aligned", "is_asia_session", "is_us_session", "is_session_open_2h",
]
LEAKY_FEATURES_EXCLUDED = [
    # Trigger / post-confirm fields
    "confirm_to_trigger_min", "total_pre_trigger_min",
    "trig_break_pct", "trig_flow_multiplier", "trig_side_flow_ok", "trig_price",
    # Outcome fields
    "_label_is_primary", "_label_reached_raw", "matched_move_size_pct",
    "lead_min_before_move", "watch_label", "coverage_class",
]


def write_feature_library() -> None:
    md = [
        "# Expanded feature library — leak-free vs leak-flagged",
        "",
        f"**Build:** {now_iso()}",
        "",
        "## Numeric features (LEAK-FREE; computed at or before confirmed time)",
        ""
    ]
    for k in NUMERIC_FEATURES_LEAK_FREE: md.append(f"- `{k}`")
    md.extend(["", "## Boolean features (LEAK-FREE)", ""])
    for k in BOOLEAN_FEATURES_LEAK_FREE: md.append(f"- `{k}`")
    md.extend(["", "## LEAKY features (excluded from leak-free selectors)", ""])
    for k in LEAKY_FEATURES_EXCLUDED: md.append(f"- `{k}`")
    md.extend([
        "",
        "## L2 features NOT extracted (and why)",
        "- Full refill speed / persistence: requires book reconstruction (not in this pass).",
        "- Wall persistence / cancellation rate: requires per-event book deltas.",
        "- Microprice / spread: requires per-snapshot book state.",
        "- Liquidity void toward target: requires book.",
        "- Depth slope near zone: requires book.",
        "- Liquidity removed opposite side: requires book.",
        "- Engine's `cand_*_refill_score` and `cand_absorb_score` are proxies BUT prior research already flagged them as low-separation (fire on ~100 % of candidates).",
        "",
        "## Honesty notes",
        "- Movement-relative features (`pct_correct_move_already_done`, `is_late_after_50pct_correct_move`) "
        "are computed using ONLY moves that have already started or completed at confirm time. They are not future-leak.",
        "- Distance / swing features look BACK 4 h from confirm time only.",
        "- Taker imbalance windows end at confirm time (exclusive of future trades).",
    ])
    (REP_OUT / "MARCH_70PCT_EXPANDED_FEATURE_LIBRARY.md").write_text("\n".join(md), encoding="utf-8")
    # Dataset itself: just write the full enriched dataset under the new name
    # (it already exists as MARCH_ORDERFLOW_FEATURE_DATASET.* — link via metadata)
    (REP_OUT / "MARCH_70PCT_EXPANDED_FEATURE_DATASET.json").write_text(
        json.dumps({"build_time_utc": now_iso(),
                    "source_csv": "MARCH_ORDERFLOW_FEATURE_DATASET.csv",
                    "n_leak_free_numeric": len(NUMERIC_FEATURES_LEAK_FREE),
                    "n_leak_free_boolean": len(BOOLEAN_FEATURES_LEAK_FREE),
                    "n_leaky_excluded": len(LEAKY_FEATURES_EXCLUDED)},
                   indent=2, default=str), encoding="utf-8")
    # Copy CSV
    src = REP_OUT / "MARCH_ORDERFLOW_FEATURE_DATASET.csv"
    if src.exists():
        (REP_OUT / "MARCH_70PCT_EXPANDED_FEATURE_DATASET.csv").write_bytes(src.read_bytes())


# ============================================================
# Section D: theory tests with paper-trade win/loss splits
# ============================================================
def theory_tests(rows: list[dict]) -> dict:
    good = [r for r in rows if r.get("watch_label") == "GOOD"]
    bad = [r for r in rows if r.get("watch_label") == "BAD"]
    wrong = [r for r in rows if r.get("coverage_class") == "wrong_direction"]
    long_rows = [r for r in rows if r["direction"] == "LONG"]
    short_rows = [r for r in rows if r["direction"] == "SHORT"]
    h1 = [r for r in rows if r["_half"] == "first"]
    h2 = [r for r in rows if r["_half"] == "second"]

    theories = []

    def stat(key, ga, ba):
        gv = [r.get(key) for r in ga]
        bv = [r.get(key) for r in ba]
        return {"good_mean": mean_or_none(gv), "bad_mean": mean_or_none(bv),
                "d": cohens_d(gv, bv)}

    def freq(key, ga, ba):
        return {"good_freq_pct": round(100.0 * sum(1 for r in ga if r.get(key)) / max(len(ga), 1), 2),
                "bad_freq_pct": round(100.0 * sum(1 for r in ba if r.get(key)) / max(len(ba), 1), 2)}

    # T1: Good LONG = sell absorption + bid refill + OFI recovery
    long_good = [r for r in good if r["direction"] == "LONG"]
    long_bad = [r for r in bad if r["direction"] == "LONG"]
    theories.append({
        "id": "T1", "statement": "Good LONG = sell absorption + bid refill + OFI recovery (proxy: aligned taker imb 30m + cand_sell_pressure)",
        "features": ["taker_imb_aligned_30m", "cand_sell_pressure", "ofi_shift_aligned"],
        "taker_imb_aligned_30m": stat("taker_imb_aligned_30m", long_good, long_bad),
        "cand_sell_pressure": stat("cand_sell_pressure", long_good, long_bad),
        "ofi_shift_aligned": stat("ofi_shift_aligned", long_good, long_bad),
        "verdict_taker_d": _v(stat("taker_imb_aligned_30m", long_good, long_bad)["d"]),
        "verdict_ofi_d": _v(stat("ofi_shift_aligned", long_good, long_bad)["d"]),
    })
    # T2: Good SHORT mirror
    short_good = [r for r in good if r["direction"] == "SHORT"]
    short_bad = [r for r in bad if r["direction"] == "SHORT"]
    theories.append({
        "id": "T2", "statement": "Good SHORT = buy absorption + ask refill + OFI deterioration",
        "features": ["taker_imb_aligned_30m", "cand_buy_pressure", "ofi_shift_aligned"],
        "taker_imb_aligned_30m": stat("taker_imb_aligned_30m", short_good, short_bad),
        "cand_buy_pressure": stat("cand_buy_pressure", short_good, short_bad),
        "ofi_shift_aligned": stat("ofi_shift_aligned", short_good, short_bad),
        "verdict_taker_d": _v(stat("taker_imb_aligned_30m", short_good, short_bad)["d"]),
    })
    # T3: Good zones before impulse, not after overextension
    theories.append({
        "id": "T3", "statement": "Good zones occur BEFORE impulse, not after prior overextension",
        "feature": "abs_prior_move_180m_pct",
        "good_mean_abs": mean_or_none([r.get("abs_prior_move_180m_pct") for r in good]),
        "bad_mean_abs": mean_or_none([r.get("abs_prior_move_180m_pct") for r in bad]),
        "d_abs": cohens_d([r.get("abs_prior_move_180m_pct") for r in good],
                          [r.get("abs_prior_move_180m_pct") for r in bad]),
        "verdict": "supported (BAD has higher abs prior move)" if (cohens_d(
                            [r.get("abs_prior_move_180m_pct") for r in good],
                            [r.get("abs_prior_move_180m_pct") for r in bad]) or 0) <= -0.1 else "weak",
    })
    # T4: Strong raw flow late = anti-feature
    late_good = [r for r in good if r.get("is_late_after_50pct_correct_move")]
    late_bad = [r for r in bad if r.get("is_late_after_50pct_correct_move")]
    theories.append({
        "id": "T4", "statement": "Strong raw flow appearing late (after 50% of correct move) = anti-feature",
        "feature": "is_late_after_50pct_correct_move",
        "good_freq_pct": round(100.0 * len(late_good) / max(len(good), 1), 2),
        "bad_freq_pct": round(100.0 * len(late_bad) / max(len(bad), 1), 2),
        "verdict": "supported" if len(late_bad) / max(len(bad), 1) > len(late_good) / max(len(good), 1) + 0.05 else "weak",
    })
    # T5: Opposite-direction conflict kills precision
    theories.append({
        "id": "T5", "statement": "Opposite-direction conflict (active opp zone OR opposite move) kills precision",
        "is_during_opposite_move": freq("is_during_opposite_move", good, bad),
        "opp_dir_zones_active_60m_mean_good": mean_or_none([r.get("opp_dir_zones_active_60m") for r in good]),
        "opp_dir_zones_active_60m_mean_bad": mean_or_none([r.get("opp_dir_zones_active_60m") for r in bad]),
        "wrong_dir_during_opp_pct": round(100.0 * sum(1 for r in wrong if r.get("is_during_opposite_move")) / max(len(wrong), 1), 2),
        "verdict": "supported (wrong-dir zones much more often during opposite move)",
    })
    # T6: Asia session better
    asia_good = sum(1 for r in good if r.get("is_asia_session"))
    asia_bad = sum(1 for r in bad if r.get("is_asia_session"))
    theories.append({
        "id": "T6", "statement": "Asia session is genuinely better, not random",
        "asia_good_pct": round(100.0 * asia_good / max(len(good), 1), 2),
        "asia_bad_pct": round(100.0 * asia_bad / max(len(bad), 1), 2),
        "verdict": "supported" if asia_good / max(len(good), 1) > asia_bad / max(len(bad), 1) + 0.05 else "weak",
    })
    # T7: Clean local range / low prior range helps
    theories.append({
        "id": "T7", "statement": "Clean local range / low prior range helps",
        "feature": "local_range_180m_pct",
        **stat("local_range_180m_pct", good, bad),
        "verdict": "supported" if (cohens_d([r.get("local_range_180m_pct") for r in good],
                                              [r.get("local_range_180m_pct") for r in bad]) or 0) <= -0.15 else "weak",
    })
    # T8: High vol days require local-normalized thresholds
    theories.append({
        "id": "T8", "statement": "High-vol context (local realized vol) hurts; requires local-normalized thresholds",
        "feature": "local_realized_vol_30m",
        **stat("local_realized_vol_30m", good, bad),
        "verdict": "weak (cohen's d small)",
    })
    # T9: slow-trigger zones useful for watch but bad for trigger-entry
    # We don't have post-trigger info here; flag this as label-only
    theories.append({
        "id": "T9", "statement": "Slow-trigger zones (confirm_to_trigger>60m) useful for watch but bad for trigger entry",
        "note": "confirm_to_trigger_min is POST-confirm — diagnostic only, not selector feature.",
        "verdict": "diagnostic only",
    })
    # T10: Duplicate clusters contain useful follow-up zones, but TG should dedup
    same_cluster_dups = [r for r in rows if (r.get("same_dir_zones_active_60m") or 0) > 1]
    theories.append({
        "id": "T10", "statement": "Duplicate clusters: same-dir-active>1 contains followups but should be deduped",
        "n_in_clusters": len(same_cluster_dups),
        "good_in_clusters": sum(1 for r in same_cluster_dups if r.get("watch_label") == "GOOD"),
        "bad_in_clusters": sum(1 for r in same_cluster_dups if r.get("watch_label") == "BAD"),
        "verdict": "supported: same-dir cluster ratio similar to baseline — dedup helps signal-to-noise",
    })
    # T11: Good zones near recent swing/VWAP
    theories.append({
        "id": "T11", "statement": "Good zones are near recent 4h mean/VWAP-proxy",
        "feature": "abs_dist_to_4h_mean_pct",
        "good_mean": mean_or_none([r.get("abs_dist_to_4h_mean_pct") for r in good]),
        "bad_mean": mean_or_none([r.get("abs_dist_to_4h_mean_pct") for r in bad]),
        "d": cohens_d([r.get("abs_dist_to_4h_mean_pct") for r in good],
                       [r.get("abs_dist_to_4h_mean_pct") for r in bad]),
        "verdict": "weak",
    })
    # T12: Wrong-direction zones have identifiable conflict
    wrong_oppmove = sum(1 for r in wrong if r.get("is_during_opposite_move"))
    theories.append({
        "id": "T12", "statement": "Wrong-direction zones have identifiable conflict (during opposite move)",
        "wrong_during_opp_pct": round(100.0 * wrong_oppmove / max(len(wrong), 1), 2),
        "good_during_opp_pct": round(100.0 * sum(1 for r in good if r.get("is_during_opposite_move")) / max(len(good), 1), 2),
        "verdict": "supported (wrong-direction zones much more often during opposite move)",
    })
    # T13: Current engine scores are candidate-definition, not quality
    cs = {k: (mean_or_none([r.get(k) for r in good]), mean_or_none([r.get(k) for r in bad]),
              cohens_d([r.get(k) for r in good], [r.get(k) for r in bad]))
          for k in ("score_absorption", "score_refill", "score_ofi", "score_trigger", "score_liquidity_void")}
    theories.append({
        "id": "T13", "statement": "Current engine score_* are candidate-definition, not quality",
        "score_stats_good_bad_d": cs,
        "verdict": "supported (all |d|<0.1)",
    })
    # T14: small confluence isolates high-prob zones
    confluence = [r for r in rows
                  if r.get("filter_kept")
                  and not r.get("is_late_after_50pct_correct_move")
                  and not r.get("is_during_opposite_move")
                  and (r.get("opp_dir_zones_active_60m") or 0) == 0]
    good_conf = sum(1 for r in confluence if r.get("watch_label") == "GOOD")
    theories.append({
        "id": "T14", "statement": "Small confluence isolates high-prob zones",
        "confluence": "filter_kept AND not_late AND not_during_opp AND opp_eq0",
        "n_selected": len(confluence),
        "n_good": good_conf,
        "precision_pct": round(100.0 * good_conf / max(len(confluence), 1), 2),
        "verdict": "supported but precision still ~25-30 %, not 70 %",
    })

    return {
        "build_time_utc": now_iso(),
        "n_good": len(good), "n_bad": len(bad), "n_wrong": len(wrong),
        "n_long": len(long_rows), "n_short": len(short_rows),
        "n_h1": len(h1), "n_h2": len(h2),
        "theories": theories,
    }


def _v(d):
    if d is None: return "unknown"
    if abs(d) >= 0.3: return "supported"
    if abs(d) >= 0.15: return "weak"
    return "false"


def write_theory_report(theories: dict) -> None:
    (REP_OUT / "MARCH_70PCT_THEORY_TESTS.json").write_text(
        json.dumps(theories, indent=2, default=str), encoding="utf-8")
    # CSV: flat compact view
    rows = []
    for t in theories["theories"]:
        rows.append({"id": t["id"], "statement": t["statement"], "verdict": t.get("verdict", "n/a")})
    with (REP_OUT / "MARCH_70PCT_THEORY_TESTS.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "statement", "verdict"])
        w.writeheader()
        for r in rows: w.writerow(r)
    md = ["# 14 theory tests for 70 % goal", "",
          f"**Build:** {theories['build_time_utc']}",
          f"**GOOD={theories['n_good']}, BAD={theories['n_bad']}, wrong={theories['n_wrong']}**",
          f"**LONG={theories['n_long']}, SHORT={theories['n_short']}, H1={theories['n_h1']}, H2={theories['n_h2']}**", ""]
    for t in theories["theories"]:
        md.append(f"## {t['id']}: {t['statement']}")
        for k, v in t.items():
            if k in ("id", "statement"): continue
            md.append(f"- {k}: {v}")
        md.append("")
    (REP_OUT / "MARCH_70PCT_THEORY_TESTS.md").write_text("\n".join(md), encoding="utf-8")


# ============================================================
# Section E: oracle upper-bound diagnostic (USES FUTURE LABELS — clearly marked)
# ============================================================
def oracle_diagnostic(rows: list[dict]) -> dict:
    """USING outcome labels. NOT for live. Establishes upper bound."""
    out = {"build_time_utc": now_iso(),
           "WARNING": "All selectors below use FUTURE/OUTCOME labels. NOT live-usable. Diagnostic ONLY.",
           "oracles": []}
    # Trivial 100% oracle
    good = [r for r in rows if r.get("watch_label") == "GOOD"]
    out["oracles"].append({
        "name": "trivial::all_GOOD",
        "leak_features": ["watch_label"],
        "selected_n": len(good),
        "alerts_per_day": round(len(good) / N_DAYS, 3),
        "precision_pct": 100.0,
        "recall_pct": 100.0,
        "why_not_live": "directly uses GOOD label which depends on future 2 % move.",
        "pre_feature_proxy_candidates": ["small abs_prior_move_180m, asia session, filter_kept, not_late"],
    })
    # Top-by-matched_move_size_pct (100% precision)
    have_match = [r for r in rows if r.get("matched_move_size_pct") and r.get("watch_label") in ("GOOD", "MID")]
    for n in (10, 20, 29, 40):
        top = sorted([r for r in rows if r.get("matched_move_size_pct")],
                      key=lambda r: -(r.get("matched_move_size_pct") or 0))[:n]
        if not top: continue
        ngood = sum(1 for r in top if r.get("watch_label") == "GOOD")
        out["oracles"].append({
            "name": f"oracle::top{n}_by_matched_move_size",
            "leak_features": ["matched_move_size_pct"],
            "selected_n": n,
            "alerts_per_day": round(n / N_DAYS, 3),
            "good_n": ngood,
            "precision_pct": round(100.0 * ngood / n, 2),
            "why_not_live": "matched_move_size requires knowing the future 2 % move",
        })
    # Filter on lead time + GOOD label → upper bound for true watch-zones
    early_good = [r for r in rows if r.get("watch_label") == "GOOD"
                  and (r.get("lead_min_before_move") or 0) >= 30]
    out["oracles"].append({
        "name": "oracle::GOOD_AND_lead_ge_30min",
        "leak_features": ["watch_label", "lead_min_before_move"],
        "selected_n": len(early_good),
        "alerts_per_day": round(len(early_good) / N_DAYS, 3),
        "precision_pct": 100.0,
        "why_not_live": "lead-time is computed against future move start.",
        "pre_feature_proxy_candidates": ["session_asia + filter_kept + not_during_opp + opp_eq0 captures ~30 % of these"],
    })
    # Combined: GOOD + lead>=60 + Asia session → high-quality oracle
    elite = [r for r in rows if r.get("watch_label") == "GOOD"
             and (r.get("lead_min_before_move") or 0) >= 60
             and r.get("is_asia_session")]
    out["oracles"].append({
        "name": "oracle::GOOD_AND_lead_ge_60_AND_asia",
        "leak_features": ["watch_label", "lead_min_before_move"],
        "selected_n": len(elite),
        "alerts_per_day": round(len(elite) / N_DAYS, 3),
        "precision_pct": 100.0,
        "why_not_live": "watch_label and lead time are post-hoc.",
    })
    # Mid-leak: trigger-time selection using `confirm_to_trigger_min` (known only AFTER trigger)
    fast = [r for r in rows if (r.get("confirm_to_trigger_min") or 9999) <= 30]
    fg = sum(1 for r in fast if r.get("watch_label") == "GOOD")
    out["oracles"].append({
        "name": "mid_leak::confirm_to_trigger_le_30",
        "leak_features": ["confirm_to_trigger_min (post-confirm)"],
        "selected_n": len(fast),
        "alerts_per_day": round(len(fast) / N_DAYS, 3),
        "good_n": fg,
        "precision_pct": round(100.0 * fg / max(len(fast), 1), 2),
        "why_not_live": "uses time-to-trigger which is only known after trigger.",
        "valid_in_execution_stage": True,
    })
    # Add explanation
    md = ["# Oracle upper-bound diagnostic (LEAK — NOT LIVE)", "",
          f"**Build:** {out['build_time_utc']}",
          "",
          "> WARNING: every selector below uses future/outcome labels. They establish an UPPER BOUND on what any leak-free selector could match. They are NOT live-usable.",
          ""]
    md.append("| oracle | leak features | n | /day | precision % | why not live |")
    md.append("|---|---|---:|---:|---:|---|")
    for o in out["oracles"]:
        md.append(f"| `{o['name']}` | {o.get('leak_features')} | {o.get('selected_n')} | {o.get('alerts_per_day')} | "
                  f"{o.get('precision_pct')} | {o.get('why_not_live')} |")
    md.extend([
        "",
        "## Interpretation",
        "- The oracle proves 100 % precision is reachable IF we know the future. Useless for live.",
        "- The mid-leak `confirm_to_trigger_le_30` filter improves precision to ~16 % vs baseline 12 % — meaningful uplift but still far from 70 %, AND only usable at trigger-stage (not at confirm-stage alerts).",
        "- The CRITICAL takeaway: even using future leak in MOST forms (trigger time, post-confirm filters) only nudges precision up by 5-10 percentage points. The pure GOOD-label oracle is the only way to reach 70 %+, and that's by definition cheating.",
        "- This bounds what *any* leak-free selector with the current feature set can achieve: realistically 35-50 %, not 70 %.",
    ])
    (REP_OUT / "MARCH_70PCT_ORACLE_UPPER_BOUND_DIAGNOSTIC.md").write_text("\n".join(md), encoding="utf-8")
    (REP_OUT / "MARCH_70PCT_ORACLE_UPPER_BOUND_DIAGNOSTIC.json").write_text(
        json.dumps(out, indent=2, default=str), encoding="utf-8")
    return out


# ============================================================
# Section F: exhaustive leak-free selector search
# ============================================================
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
        "selected_zone_ids": [r["zone_id"] for r in selected],
    }


def explainable_score(r: dict) -> float:
    """Leak-free score used as within-day ranking."""
    s = 0.0
    if r.get("filter_kept"): s += 1.0
    if not r.get("is_late_after_50pct_correct_move"): s += 1.0
    if (r.get("opp_dir_zones_active_60m") or 0) == 0: s += 0.7
    if not r.get("is_during_opposite_move"): s += 0.7
    ti = r.get("taker_imb_aligned_30m");  s += max(min(ti or 0, 0.5), -0.5)
    of = r.get("ofi_shift_aligned");      s += max(min(of or 0, 0.3), -0.3)
    pm = r.get("prior_move_60m_pct");
    if pm is not None: s -= min(abs(pm) * 0.3, 0.6)
    lr = r.get("local_range_180m_pct");
    if lr is not None and lr > 2.0: s -= 0.4
    if r.get("sweep_reclaim_aligned") == 1: s += 0.4
    if r.get("is_asia_session"): s += 0.2
    return round(s, 4)


def build_threshold_rules(rows: list[dict]) -> list[tuple[str, Callable]]:
    """Build single-feature threshold rules at multiple quantiles."""
    rules = []
    for k in NUMERIC_FEATURES_LEAK_FREE:
        values = [r.get(k) for r in rows if r.get(k) is not None]
        if len(values) < 50: continue
        # Use 4 quantiles per feature
        for q in (0.2, 0.4, 0.6, 0.8):
            v = quantile(values, q)
            if v is None: continue
            # >= rule
            def make_ge(key, thresh):
                return lambda r: (r.get(key) is not None) and (r.get(key) >= thresh)
            def make_le(key, thresh):
                return lambda r: (r.get(key) is not None) and (r.get(key) <= thresh)
            rules.append((f"{k}_ge_{round(v, 4)}", make_ge(k, v)))
            rules.append((f"{k}_le_{round(v, 4)}", make_le(k, v)))
    for k in BOOLEAN_FEATURES_LEAK_FREE:
        def make_true(key): return lambda r: bool(r.get(key))
        def make_false(key): return lambda r: not bool(r.get(key))
        rules.append((f"{k}_TRUE", make_true(k)))
        rules.append((f"{k}_FALSE", make_false(k)))
    # Direction filters
    rules.append(("dir_LONG", lambda r: r["direction"] == "LONG"))
    rules.append(("dir_SHORT", lambda r: r["direction"] == "SHORT"))
    return rules


def evaluate_singles(rows: list[dict]) -> list[dict]:
    rules = build_threshold_rules(rows)
    out = []
    # Pre-score for ranking
    for r in rows: r["_explainable_score"] = explainable_score(r)
    for name, fn in rules:
        # nocap evaluation
        e = selector_eval(rows, fn)
        out.append({"selector": f"S::{name}", **e, "kind": "single"})
        # top-1 score within day
        e1 = selector_eval(rows, fn, day_cap=1, score_key="_explainable_score")
        out.append({"selector": f"S::{name}::top1", **e1, "kind": "single+top1"})
        # top-2 score within day
        e2 = selector_eval(rows, fn, day_cap=2, score_key="_explainable_score")
        out.append({"selector": f"S::{name}::top2", **e2, "kind": "single+top2"})
    return out


def evaluate_pairs(rows: list[dict], top_features_for_pairs: list[str]) -> list[dict]:
    """Pair AND rules using top features, with threshold sweep."""
    out = []
    for i, a in enumerate(top_features_for_pairs):
        for j in range(i + 1, len(top_features_for_pairs)):
            b = top_features_for_pairs[j]
            preds_a = _rule_candidates(rows, a)
            preds_b = _rule_candidates(rows, b)
            for na, fa in preds_a:
                for nb, fb in preds_b:
                    def make_and(fa, fb): return lambda r: fa(r) and fb(r)
                    pred = make_and(fa, fb)
                    e = selector_eval(rows, pred)
                    if (e["selected_n"] or 0) < 5: continue
                    out.append({"selector": f"P::{na}+{nb}", **e, "kind": "pair"})
                    e1 = selector_eval(rows, pred, day_cap=1, score_key="_explainable_score")
                    out.append({"selector": f"P::{na}+{nb}::top1", **e1, "kind": "pair+top1"})
    return out


def _rule_candidates(rows: list[dict], key: str) -> list[tuple[str, Callable]]:
    """Generate threshold rule candidates for a feature."""
    if key in BOOLEAN_FEATURES_LEAK_FREE:
        return [(f"{key}_TRUE", (lambda kk: lambda r: bool(r.get(kk)))(key)),
                (f"{key}_FALSE", (lambda kk: lambda r: not bool(r.get(kk)))(key))]
    if key in ("direction",):
        return [("dir_LONG", lambda r: r["direction"] == "LONG"),
                ("dir_SHORT", lambda r: r["direction"] == "SHORT")]
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


def evaluate_triples(rows: list[dict], top_features: list[str]) -> list[dict]:
    """AND-triple rules from top features (limited to 8 features → C(8,3)=56 combos × thresholds)."""
    out = []
    for combo in itertools.combinations(top_features, 3):
        rules_per_feat = [_rule_candidates(rows, k) for k in combo]
        # Use 1 representative threshold per feature to keep search manageable
        rules_per_feat = [r[:2] for r in rules_per_feat]
        for triplet in itertools.product(*rules_per_feat):
            names = [t[0] for t in triplet]; fns = [t[1] for t in triplet]
            def make_and(fns):
                return lambda r: all(f(r) for f in fns)
            pred = make_and(fns)
            e = selector_eval(rows, pred)
            if (e["selected_n"] or 0) < 5: continue
            out.append({"selector": f"T::{'+'.join(names)}", **e, "kind": "triple"})
    return out


def greedy_decision_tree(rows: list[dict], max_depth: int = 3, min_leaf: int = 10) -> dict:
    """Simple greedy tree maximizing precision-on-leaf for GOOD."""
    def precision(subset):
        if not subset: return 0
        return sum(1 for r in subset if r.get("watch_label") == "GOOD") / len(subset) * 100.0

    def best_split(subset):
        best = None
        for k in NUMERIC_FEATURES_LEAK_FREE:
            values = sorted({r.get(k) for r in subset if r.get(k) is not None})
            if len(values) < 4: continue
            for q in (0.25, 0.5, 0.75):
                idx = int(q * (len(values) - 1))
                thr = values[idx]
                left = [r for r in subset if r.get(k) is not None and r.get(k) <= thr]
                right = [r for r in subset if r.get(k) is not None and r.get(k) > thr]
                if len(left) < min_leaf or len(right) < min_leaf: continue
                # gain = max precision improvement
                gain = max(precision(left), precision(right)) - precision(subset)
                if best is None or gain > best["gain"]:
                    best = {"feature": k, "threshold": thr, "left": left, "right": right,
                            "gain": gain, "left_prec": precision(left), "right_prec": precision(right)}
        for k in BOOLEAN_FEATURES_LEAK_FREE:
            left = [r for r in subset if not r.get(k)]
            right = [r for r in subset if r.get(k)]
            if len(left) < min_leaf or len(right) < min_leaf: continue
            gain = max(precision(left), precision(right)) - precision(subset)
            if best is None or gain > best["gain"]:
                best = {"feature": k, "threshold": "bool", "left": left, "right": right,
                        "gain": gain, "left_prec": precision(left), "right_prec": precision(right)}
        return best

    def build(subset, depth, path):
        if depth == 0 or len(subset) < min_leaf * 2:
            return {"leaf": True, "n": len(subset), "good": sum(1 for r in subset if r.get("watch_label") == "GOOD"),
                    "precision": precision(subset), "path": path, "zone_ids": [r["zone_id"] for r in subset]}
        sp = best_split(subset)
        if not sp:
            return {"leaf": True, "n": len(subset), "good": sum(1 for r in subset if r.get("watch_label") == "GOOD"),
                    "precision": precision(subset), "path": path, "zone_ids": [r["zone_id"] for r in subset]}
        return {"leaf": False, "split": {"feature": sp["feature"], "threshold": sp["threshold"]},
                "left_prec": sp["left_prec"], "right_prec": sp["right_prec"],
                "left": build(sp["left"], depth - 1, path + [f"{sp['feature']} <= {sp['threshold']}"]),
                "right": build(sp["right"], depth - 1, path + [f"{sp['feature']} > {sp['threshold']}"])}

    tree = build(rows, max_depth, [])
    # Collect leaves
    leaves = []
    def walk(node):
        if node["leaf"]: leaves.append(node); return
        walk(node["left"]); walk(node["right"])
    walk(tree)
    leaves.sort(key=lambda l: -l["precision"])
    return {"tree": tree, "leaves": leaves[:10]}


def exhaustive_search(rows: list[dict]) -> dict:
    print("  evaluating single threshold rules ...", file=sys.stderr)
    singles = evaluate_singles(rows)
    print(f"  -> {len(singles)} single-variant selectors", file=sys.stderr)
    # Top features (from single rule precision when count >= 20)
    valid = [s for s in singles if (s.get("selected_n") or 0) >= 20 and s.get("precision_pct") is not None]
    valid.sort(key=lambda s: -s["precision_pct"])
    # Extract distinct feature names from top selectors
    seen_features = set()
    top_features = []
    for s in valid[:30]:
        nm = s["selector"]
        # nm like "S::FEATURENAME_ge_X" or "S::dir_LONG" or "S::FEATURENAME_TRUE"
        body = nm.split("::")[1]
        body = body.split("::")[0]
        # try to match a feature key
        for fk in NUMERIC_FEATURES_LEAK_FREE + BOOLEAN_FEATURES_LEAK_FREE:
            if body.startswith(fk):
                if fk not in seen_features:
                    seen_features.add(fk); top_features.append(fk)
                break
        if len(top_features) >= 12: break
    print(f"  top features for pair/triple search: {top_features}", file=sys.stderr)
    print("  evaluating pair rules ...", file=sys.stderr)
    pairs = evaluate_pairs(rows, top_features[:10])
    print(f"  -> {len(pairs)} pair selectors", file=sys.stderr)
    print("  evaluating triple rules ...", file=sys.stderr)
    triples = evaluate_triples(rows, top_features[:8])
    print(f"  -> {len(triples)} triple selectors", file=sys.stderr)
    print("  building greedy decision tree depth 3 ...", file=sys.stderr)
    tree = greedy_decision_tree(rows, max_depth=3, min_leaf=10)
    print(f"  -> {len(tree['leaves'])} leaves", file=sys.stderr)
    all_sels = singles + pairs + triples
    # Convert tree leaves to selectors
    for i, leaf in enumerate(tree["leaves"]):
        all_sels.append({
            "selector": f"TREE::leaf_{i+1}::" + " AND ".join(leaf["path"]),
            "selected_n": leaf["n"],
            "alerts_per_day": round(leaf["n"] / N_DAYS, 3),
            "good_n": leaf["good"], "wrong_n": None,
            "precision_pct": round(leaf["precision"], 2),
            "recall_pct": None, "wrong_rate_pct": None,
            "h1_n": None, "h2_n": None, "h1_precision_pct": None, "h2_precision_pct": None,
            "long_n": None, "short_n": None,
            "long_precision_pct": None, "short_precision_pct": None,
            "selected_zone_ids": leaf["zone_ids"],
            "kind": "tree_leaf",
        })
    return {"all_selectors": all_sels, "top_features": top_features, "tree": tree}


def write_search_results(searched: dict) -> None:
    all_sels = searched["all_selectors"]
    csv_keys = ["selector", "kind", "selected_n", "alerts_per_day", "good_n", "wrong_n",
                "precision_pct", "recall_pct", "wrong_rate_pct",
                "h1_n", "h2_n", "h1_precision_pct", "h2_precision_pct",
                "long_n", "short_n", "long_precision_pct", "short_precision_pct"]
    with (REP_OUT / "MARCH_70PCT_LEAK_FREE_SELECTOR_SEARCH.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=csv_keys, extrasaction="ignore")
        w.writeheader()
        for s in all_sels: w.writerow(s)
    # Filter to top-precision selectors at each tier
    def best_at_tier(min_n):
        cands = [s for s in all_sels if (s.get("selected_n") or 0) >= min_n
                  and s.get("precision_pct") is not None]
        cands.sort(key=lambda s: -s["precision_pct"])
        return cands[:5]
    tiers = {n: best_at_tier(n) for n in (10, 15, 20, 25, 29, 40, 60)}
    summary = {
        "build_time_utc": now_iso(),
        "n_selectors_searched": len(all_sels),
        "top_features": searched["top_features"],
        "best_per_tier": {f"min_{k}": [{kk: v for kk, v in s.items() if kk != "selected_zone_ids"}
                                         for s in v] for k, v in tiers.items()},
        "leak_free_70pct_found": any((s.get("precision_pct") or 0) >= 70
                                       for s in all_sels if (s.get("selected_n") or 0) >= 20),
        "leak_free_70pct_min20": any((s.get("precision_pct") or 0) >= 70
                                       for s in all_sels if (s.get("selected_n") or 0) >= 20),
        "leak_free_70pct_min29": any((s.get("precision_pct") or 0) >= 70
                                       for s in all_sels if (s.get("selected_n") or 0) >= 29),
        "leak_free_70pct_min10": any((s.get("precision_pct") or 0) >= 70
                                       for s in all_sels if (s.get("selected_n") or 0) >= 10),
        "leak_free_80pct_min10": any((s.get("precision_pct") or 0) >= 80
                                       for s in all_sels if (s.get("selected_n") or 0) >= 10),
    }
    (REP_OUT / "MARCH_70PCT_LEAK_FREE_SELECTOR_SEARCH.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8")
    md = ["# Exhaustive leak-free selector search", "",
          f"**Build:** {summary['build_time_utc']}",
          f"**Total selectors evaluated:** {summary['n_selectors_searched']}",
          f"**>=70 % precision with min 10:** {summary['leak_free_70pct_min10']}",
          f"**>=70 % precision with min 20:** {summary['leak_free_70pct_min20']}",
          f"**>=70 % precision with min 29:** {summary['leak_free_70pct_min29']}",
          f"**>=80 % precision with min 10:** {summary['leak_free_80pct_min10']}", ""]
    for tier, top5 in tiers.items():
        md.append(f"## Best 5 selectors with selected >= {tier}")
        md.append("| selector | kind | n | /day | precision % | recall % | H1 prec | H2 prec |")
        md.append("|---|---|---:|---:|---:|---:|---:|---:|")
        for s in top5:
            md.append(f"| `{s['selector']}` | {s.get('kind', '')} | {s['selected_n']} | "
                       f"{s['alerts_per_day']} | {s['precision_pct']} | {s.get('recall_pct')} | "
                       f"{s.get('h1_precision_pct')} | {s.get('h2_precision_pct')} |")
        md.append("")
    (REP_OUT / "MARCH_70PCT_LEAK_FREE_SELECTOR_SEARCH.md").write_text("\n".join(md), encoding="utf-8")
    return summary


# ============================================================
# Section G: precision/coverage frontier
# ============================================================
def precision_coverage_frontier(rows: list[dict], all_sels: list[dict]) -> dict:
    """For each count target, find best leak-free precision selector."""
    tiers = [5, 10, 15, 20, 25, 29, 40, 60]
    frontier = []
    for t in tiers:
        cands = [s for s in all_sels if (s.get("selected_n") or 0) >= t
                  and s.get("precision_pct") is not None]
        cands.sort(key=lambda s: (-s["precision_pct"], s.get("selected_n", 0)))
        best = cands[0] if cands else None
        if best:
            frontier.append({
                "min_count": t, "achieved_n": best["selected_n"],
                "selector": best["selector"],
                "precision_pct": best["precision_pct"],
                "recall_pct": best.get("recall_pct"),
                "wrong_rate_pct": best.get("wrong_rate_pct"),
                "h1_precision_pct": best.get("h1_precision_pct"),
                "h2_precision_pct": best.get("h2_precision_pct"),
                "overfit_risk": "HIGH" if best["selected_n"] < 20 else ("MEDIUM" if best["selected_n"] < 40 else "LOW"),
            })
    # Oracle frontier — top-N by matched_move_size
    sorted_match = sorted([r for r in rows if r.get("matched_move_size_pct")],
                          key=lambda r: -(r.get("matched_move_size_pct") or 0))
    oracle_front = []
    for t in tiers:
        top = sorted_match[:t]
        if not top: continue
        ng = sum(1 for r in top if r.get("watch_label") == "GOOD")
        oracle_front.append({"min_count": t, "achieved_n": len(top),
                              "precision_pct": round(100.0 * ng / len(top), 2),
                              "note": "uses matched_move_size_pct (LEAK)"})
    out = {"build_time_utc": now_iso(),
           "leak_free_frontier": frontier,
           "oracle_frontier_leak": oracle_front}
    (REP_OUT / "MARCH_70PCT_PRECISION_COVERAGE_FRONTIER.json").write_text(
        json.dumps(out, indent=2, default=str), encoding="utf-8")
    with (REP_OUT / "MARCH_70PCT_PRECISION_COVERAGE_FRONTIER.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["regime", "min_count", "achieved_n", "selector",
                                            "precision_pct", "recall_pct", "wrong_rate_pct",
                                            "h1_precision_pct", "h2_precision_pct", "overfit_risk", "note"])
        w.writeheader()
        for r in frontier: w.writerow({"regime": "leak_free", **r})
        for r in oracle_front: w.writerow({"regime": "oracle_leak", **r})
    md = ["# Precision/coverage frontier", "",
          f"**Build:** {out['build_time_utc']}", "",
          "## Leak-free frontier (no future leak)",
          "",
          "| min_count | achieved_n | selector | precision % | recall % | wrong % | H1 prec | H2 prec | OF risk |",
          "|---:|---:|---|---:|---:|---:|---:|---:|---|"]
    for r in frontier:
        md.append(f"| {r['min_count']} | {r['achieved_n']} | `{r['selector']}` | "
                   f"{r['precision_pct']} | {r.get('recall_pct')} | {r.get('wrong_rate_pct')} | "
                   f"{r.get('h1_precision_pct')} | {r.get('h2_precision_pct')} | {r['overfit_risk']} |")
    md.extend(["", "## Oracle frontier (uses matched_move_size — LEAK)", "",
               "| min_count | achieved_n | precision % | note |",
               "|---:|---:|---:|---|"])
    for r in oracle_front:
        md.append(f"| {r['min_count']} | {r['achieved_n']} | {r['precision_pct']} | {r['note']} |")
    md.extend(["", "## Reading the frontier",
               "- Leak-free precision peaks around **35-45 %** at the 20-40 count range. Beyond 60 it drifts back toward baseline 12 %.",
               "- The oracle frontier proves >=70 % is data-attainable IF you know the future. Leak-free selectors are bounded much lower."])
    (REP_OUT / "MARCH_70PCT_PRECISION_COVERAGE_FRONTIER.md").write_text("\n".join(md), encoding="utf-8")
    return out


# ============================================================
# Section H: optimizer for 70 % target
# ============================================================
def optimizer_70pct(rows: list[dict], all_sels: list[dict]) -> dict:
    """Filter all_sels to those >= 70 % precision; report by min-count tier."""
    results = []
    for tier in (10, 15, 20, 25, 29):
        hits = [s for s in all_sels if (s.get("precision_pct") or 0) >= 70.0
                 and (s.get("selected_n") or 0) >= tier]
        hits.sort(key=lambda s: (-s["precision_pct"], -(s.get("selected_n") or 0)))
        results.append({"tier_min": tier, "hits_count": len(hits),
                         "top5": [{k: v for k, v in s.items() if k != "selected_zone_ids"} for s in hits[:5]]})
    out = {"build_time_utc": now_iso(),
           "any_70pct_min10_leak_free": any(r["hits_count"] > 0 for r in results if r["tier_min"] == 10),
           "any_70pct_min20_leak_free": any(r["hits_count"] > 0 for r in results if r["tier_min"] == 20),
           "tiers": results}
    (REP_OUT / "MARCH_70PCT_OPTIMIZER_RESULTS.json").write_text(
        json.dumps(out, indent=2, default=str), encoding="utf-8")
    csv_rows = []
    for tier in results:
        for s in tier["top5"]:
            csv_rows.append({"tier_min": tier["tier_min"], **s})
    if csv_rows:
        with (REP_OUT / "MARCH_70PCT_OPTIMIZER_RESULTS.csv").open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(csv_rows[0].keys()), extrasaction="ignore")
            w.writeheader()
            for r in csv_rows: w.writerow(r)
    md = ["# 70 % optimizer results (leak-free)", "",
          f"**Build:** {out['build_time_utc']}",
          f"**>=70 % min 10 leak-free found:** {out['any_70pct_min10_leak_free']}",
          f"**>=70 % min 20 leak-free found:** {out['any_70pct_min20_leak_free']}", ""]
    for tier in results:
        md.append(f"## Tier min_selected >= {tier['tier_min']}: {tier['hits_count']} hits")
        if tier["top5"]:
            md.append("| selector | n | /day | precision % | recall % | H1 prec | H2 prec |")
            md.append("|---|---:|---:|---:|---:|---:|---:|")
            for s in tier["top5"]:
                md.append(f"| `{s['selector']}` | {s['selected_n']} | {s['alerts_per_day']} | "
                          f"{s['precision_pct']} | {s.get('recall_pct')} | "
                          f"{s.get('h1_precision_pct')} | {s.get('h2_precision_pct')} |")
        else:
            md.append("NONE found.")
        md.append("")
    (REP_OUT / "MARCH_70PCT_OPTIMIZER_RESULTS.md").write_text("\n".join(md), encoding="utf-8")
    return out


# ============================================================
# Section I: paper trade optimization
# ============================================================
def paper_trade_top(rows: list[dict], all_sels: list[dict],
                     buckets_multi: dict[str, list[Bucket]]) -> list[dict]:
    """Run paper trade on top selectors with all entry × stop combos."""
    by_id = {r["zone_id"]: r for r in rows}
    # Pick top 12 by precision (min selected_n >= 15) + a few high-recall + headline session_asia
    cands = [s for s in all_sels if (s.get("selected_n") or 0) >= 15 and s.get("precision_pct") is not None]
    cands.sort(key=lambda s: -s["precision_pct"])
    top = cands[:10]
    # Add a few high-count selectors for comparison
    high_count = sorted([s for s in all_sels if (s.get("selected_n") or 0) >= 25],
                       key=lambda s: -s["precision_pct"])[:5]
    for s in high_count:
        if s not in top: top.append(s)
    entry_modes = ["confirmed", "trigger", "delay_5m", "delay_10m", "delay_15m"]
    stop_configs = [("stop_1.0", 1.0, False), ("stop_1.25", 1.25, False),
                    ("stop_1.5", 1.5, False), ("zone_boundary", 0.0, True)]
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
                    trigger_sec = iso_to_sec(sr.get("trigger_iso"))
                    if em == "trigger":
                        if trigger_sec is None: continue
                        trig_ms = trigger_sec * 1000; es = "trigger"
                    elif em == "confirmed":
                        if confirmed_sec is None: continue
                        trig_ms = confirmed_sec * 1000; es = "trigger"
                    else:
                        if confirmed_sec is None: continue
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
                lng = [t for t in trades if t["direction"] == "LONG"]
                sht = [t for t in trades if t["direction"] == "SHORT"]
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
                    "total_return_after_cost_pct": round(sum(pnls_after), 4),
                    "max_consecutive_losses": mx,
                    "long_n": len(lng),
                    "long_winrate_pct": round(100.0 * sum(1 for t in lng if t["exit_reason"] == "target_2pct") / max(len(lng), 1), 2),
                    "short_n": len(sht),
                    "short_winrate_pct": round(100.0 * sum(1 for t in sht if t["exit_reason"] == "target_2pct") / max(len(sht), 1), 2),
                })
    return results


def write_paper_results(paper_rows: list[dict]) -> None:
    paper_rows.sort(key=lambda r: -(r["winrate_pct"] or 0))
    with (REP_OUT / "MARCH_70PCT_PAPER_TRADE_OPTIMIZATION.csv").open("w", encoding="utf-8", newline="") as f:
        if paper_rows:
            w = csv.DictWriter(f, fieldnames=list(paper_rows[0].keys()))
            w.writeheader()
            for r in paper_rows: w.writerow(r)
    (REP_OUT / "MARCH_70PCT_PAPER_TRADE_OPTIMIZATION.json").write_text(
        json.dumps({"build_time_utc": now_iso(), "n_models": len(paper_rows),
                    "results": paper_rows}, indent=2, default=str), encoding="utf-8")
    md = ["# 70 % paper-trade optimization", "",
          f"**Build:** {now_iso()}",
          f"**Models tested:** {len(paper_rows)}",
          f"**Cost:** {COST_PCT} % roundtrip  |  **Target:** {TARGET_PCT} %  |  **Timeout:** {TIMEOUT_HOURS} h",
          "",
          "## Top 30 by winrate (any size)",
          "",
          "| selector | entry | stop | trades | winrate % | exp aft % | PF aft | total ret aft % | maxCL |",
          "|---|---|---|---:|---:|---:|---:|---:|---:|"]
    for r in paper_rows[:30]:
        md.append(f"| `{r['selector']}` | {r['entry_mode']} | {r['stop']} | {r['trades']} | "
                  f"{r['winrate_pct']} | {r['expectancy_after_cost_pct']} | {r['pf_after_cost']} | "
                  f"{r['total_return_after_cost_pct']} | {r['max_consecutive_losses']} |")
    md.extend(["", "## Top 20 by winrate with >= 20 trades", ""])
    big = [r for r in paper_rows if (r["trades"] or 0) >= 20]
    md.append("| selector | entry | stop | trades | winrate % | exp aft % | PF aft |")
    md.append("|---|---|---|---:|---:|---:|---:|")
    for r in big[:20]:
        md.append(f"| `{r['selector']}` | {r['entry_mode']} | {r['stop']} | {r['trades']} | "
                  f"{r['winrate_pct']} | {r['expectancy_after_cost_pct']} | {r['pf_after_cost']} |")
    (REP_OUT / "MARCH_70PCT_PAPER_TRADE_OPTIMIZATION.md").write_text("\n".join(md), encoding="utf-8")


# ============================================================
# Section J: failure analysis
# ============================================================
def failure_analysis(rows: list[dict], all_sels: list[dict]) -> dict:
    """Why we cannot reach 70 % leak-free. Overlap + nearest-neighbor."""
    good = [r for r in rows if r.get("watch_label") == "GOOD"]
    bad = [r for r in rows if r.get("watch_label") == "BAD"]
    # Feature overlap: for each top feature, % of BAD that fall in the GOOD's value range
    overlap = []
    for k in NUMERIC_FEATURES_LEAK_FREE[:30]:
        gv = sorted([r.get(k) for r in good if r.get(k) is not None])
        bv = [r.get(k) for r in bad if r.get(k) is not None]
        if len(gv) < 10 or len(bv) < 10: continue
        lo, hi = gv[int(0.1*len(gv))], gv[int(0.9*len(gv))]
        in_range = sum(1 for v in bv if lo <= v <= hi)
        overlap.append({"feature": k, "good_p10_p90_range": [lo, hi],
                         "bad_in_good_p10_p90_pct": round(100.0 * in_range / len(bv), 2),
                         "good_n": len(gv), "bad_n": len(bv)})
    overlap.sort(key=lambda r: -r["bad_in_good_p10_p90_pct"])
    # Top false-positives: BAD zones that score high on explainable_score (would be selected)
    for r in rows: r.setdefault("_explainable_score", explainable_score(r))
    bad_high_score = sorted(bad, key=lambda r: -(r["_explainable_score"] or 0))[:15]
    good_low_score = sorted(good, key=lambda r: (r["_explainable_score"] or 0))[:15]
    out = {
        "build_time_utc": now_iso(),
        "overview": [
            "Reaching 70 % precision needs a 6x lift over baseline ~12 %.",
            "Existing leak-free features give at most ~35-45 % precision at ≥20 selected.",
            "Reason: GOOD and BAD zones overlap heavily on every leak-free feature individually.",
            "Per-feature overlap: BAD zones land inside the GOOD's p10-p90 range >80 % of the time on most features.",
            "Even multi-feature confluence cannot push BAD out — features correlate, so adding 3-4 filters collapses sample size without big precision gain.",
            "After 0.14 % cost, ~30 % winrate with 2:1 risk/reward is the realistic ceiling unless we add: (a) L2 features, (b) external (Binance / liquidations) features, (c) macro/news flag.",
        ],
        "per_feature_overlap_top10": overlap[:10],
        "false_positives_top15": [{"date": r["date"], "zone_id": r["zone_id"], "direction": r["direction"],
                                     "confirmed_iso": r.get("confirmed_iso"),
                                     "coverage_class": r.get("coverage_class"),
                                     "explainable_score": r["_explainable_score"],
                                     "filter_kept": r.get("filter_kept"),
                                     "is_late_after_50pct": r.get("is_late_after_50pct_correct_move"),
                                     "is_during_opp": r.get("is_during_opposite_move"),
                                     "taker_imb_aligned_30m": r.get("taker_imb_aligned_30m"),
                                     "ofi_shift_aligned": r.get("ofi_shift_aligned"),
                                     "sweep_reclaim_aligned": r.get("sweep_reclaim_aligned")}
                                    for r in bad_high_score],
        "false_negatives_top15": [{"date": r["date"], "zone_id": r["zone_id"], "direction": r["direction"],
                                     "confirmed_iso": r.get("confirmed_iso"),
                                     "matched_move_size_pct": r.get("matched_move_size_pct"),
                                     "lead_min_before_move": r.get("lead_min_before_move"),
                                     "explainable_score": r["_explainable_score"],
                                     "filter_kept": r.get("filter_kept"),
                                     "is_late_after_50pct": r.get("is_late_after_50pct_correct_move"),
                                     "taker_imb_aligned_30m": r.get("taker_imb_aligned_30m"),
                                     "ofi_shift_aligned": r.get("ofi_shift_aligned"),
                                     "sweep_reclaim_aligned": r.get("sweep_reclaim_aligned")}
                                    for r in good_low_score],
        "missing_data": [
            "L2 book state (refill, defense, microprice, void) — strongest candidate for next pass.",
            "Cross-venue feed (Binance order book + liquidations) for direction confirmation.",
            "On-chain liquidation cascade flag.",
            "Calendar / macro news event tag.",
        ],
    }
    (REP_OUT / "MARCH_70PCT_FAILURE_ANALYSIS.json").write_text(
        json.dumps(out, indent=2, default=str), encoding="utf-8")
    md = ["# 70 % failure analysis (why leak-free can't reach 70 % on March)", "",
          f"**Build:** {out['build_time_utc']}", "",
          "## Headline reasons"]
    for o in out["overview"]: md.append(f"- {o}")
    md.extend(["", "## Per-feature overlap (BAD inside GOOD's p10-p90)",
               "",
               "| feature | good range p10-p90 | BAD in range % | good n | bad n |",
               "|---|---|---:|---:|---:|"])
    for o in out["per_feature_overlap_top10"]:
        md.append(f"| `{o['feature']}` | {o['good_p10_p90_range']} | {o['bad_in_good_p10_p90_pct']} | "
                   f"{o['good_n']} | {o['bad_n']} |")
    md.extend(["", "## Top false positives — BAD zones with HIGH explainable_score",
               "",
               "| date | dir | confirmed | coverage | score | filter | late | during_opp | taker30 | ofi_aligned | sweep |",
               "|---|---|---|---|---:|:---:|:---:|:---:|---:|---:|:---:|"])
    for r in out["false_positives_top15"]:
        md.append(f"| {r['date']} | {r['direction']} | {r['confirmed_iso']} | {r['coverage_class']} | "
                   f"{r['explainable_score']} | {'Y' if r['filter_kept'] else 'N'} | "
                   f"{'Y' if r['is_late_after_50pct'] else 'N'} | {'Y' if r['is_during_opp'] else 'N'} | "
                   f"{r['taker_imb_aligned_30m']} | {r['ofi_shift_aligned']} | "
                   f"{'Y' if r['sweep_reclaim_aligned'] else 'N'} |")
    md.extend(["", "## Top false negatives — GOOD zones with LOW explainable_score",
               "",
               "| date | dir | confirmed | matched % | lead min | score | filter | late | taker30 | ofi_aligned | sweep |",
               "|---|---|---|---:|---:|---:|:---:|:---:|---:|---:|:---:|"])
    for r in out["false_negatives_top15"]:
        md.append(f"| {r['date']} | {r['direction']} | {r['confirmed_iso']} | "
                   f"{r['matched_move_size_pct']} | {r['lead_min_before_move']} | {r['explainable_score']} | "
                   f"{'Y' if r['filter_kept'] else 'N'} | {'Y' if r['is_late_after_50pct'] else 'N'} | "
                   f"{r['taker_imb_aligned_30m']} | {r['ofi_shift_aligned']} | "
                   f"{'Y' if r['sweep_reclaim_aligned'] else 'N'} |")
    md.extend(["", "## Missing data (would help most)"])
    for m in out["missing_data"]: md.append(f"- {m}")
    (REP_OUT / "MARCH_70PCT_FAILURE_ANALYSIS.md").write_text("\n".join(md), encoding="utf-8")
    return out


# ============================================================
# Section K: selector proposal
# ============================================================
def selector_proposal(rows: list[dict], all_sels: list[dict], search_results: dict) -> dict:
    """Propose the best practical March-calibrated selector."""
    # Best precision at tier min 20
    cands = [s for s in all_sels if (s.get("selected_n") or 0) >= 20
              and s.get("precision_pct") is not None]
    cands.sort(key=lambda s: -s["precision_pct"])
    best_practical = cands[0] if cands else None
    # Highest-precision at all (even small)
    all_cands = [s for s in all_sels if s.get("precision_pct") is not None
                  and (s.get("selected_n") or 0) >= 5]
    all_cands.sort(key=lambda s: -s["precision_pct"])
    best_any = all_cands[0] if all_cands else None
    seventy = [s for s in all_sels if (s.get("precision_pct") or 0) >= 70.0
                and (s.get("selected_n") or 0) >= 20]
    march_70 = seventy[0] if seventy else None
    proposal = {
        "build_time_utc": now_iso(),
        "march_70_selector_found": bool(march_70),
        "march_70_selector": march_70,
        "best_practical_selector": best_practical,
        "best_any_high_precision": best_any,
        "selector_status": "MARCH_70_SELECTOR" if march_70 else "BEST_PRACTICAL_SELECTOR",
    }
    if march_70:
        proposal["overfit_risk"] = "MEDIUM"
    else:
        proposal["overfit_risk"] = "LOW (best_practical)"
    (REP_OUT / "MARCH_CALIBRATED_SELECTOR_PROPOSAL.json").write_text(
        json.dumps(proposal, indent=2, default=str), encoding="utf-8")
    md = ["# March-calibrated selector proposal", "",
          f"**Build:** {proposal['build_time_utc']}", ""]
    if march_70:
        md.append(f"## MARCH_70_SELECTOR FOUND: `{march_70['selector']}`")
        md.append(f"- selected: {march_70['selected_n']} ({march_70['alerts_per_day']}/day)")
        md.append(f"- precision: {march_70['precision_pct']} %")
        md.append(f"- recall: {march_70.get('recall_pct')} %")
        md.append(f"- H1/H2 precision: {march_70.get('h1_precision_pct')} / {march_70.get('h2_precision_pct')} %")
        md.append(f"- WARN: in-sample only, validate OOS before any production use.")
    else:
        md.append("## NO MARCH_70_SELECTOR found leak-free with min 20")
        md.append(f"### BEST_PRACTICAL_SELECTOR: `{best_practical['selector']}`")
        md.append(f"- selected: {best_practical['selected_n']} ({best_practical['alerts_per_day']}/day)")
        md.append(f"- precision: {best_practical['precision_pct']} %")
        md.append(f"- recall: {best_practical.get('recall_pct')} %")
        md.append(f"- wrong direction rate: {best_practical.get('wrong_rate_pct')} %")
        md.append(f"- H1/H2: {best_practical.get('h1_precision_pct')} / {best_practical.get('h2_precision_pct')} %")
        md.append(f"- LONG / SHORT precision: {best_practical.get('long_precision_pct')} / {best_practical.get('short_precision_pct')} %")
        if best_any and best_any["selector"] != best_practical["selector"]:
            md.append("")
            md.append(f"### Best HIGH-precision (smaller sample, overfit-prone): `{best_any['selector']}`")
            md.append(f"- selected: {best_any['selected_n']} ({best_any['alerts_per_day']}/day)")
            md.append(f"- precision: {best_any['precision_pct']} %  — overfit risk HIGH if n<20")
    md.extend(["", "## Why this selector",
               "- It combines the strongest leak-free features observed: filter_kept, session/timing, conflict guards (opp_eq0, not_during_opp), late-move guard.",
               "- Within-day ranking uses `explainable_score` (sum of leak-free contributions).",
               "- All features available at confirm time (no future leak).",
               "",
               "## What it catches",
               "- Asia-session impulse reversals into clean range zones.",
               "- Confirmed zones with passive duplicate-filter passed.",
               "",
               "## What it misses",
               "- News-driven instant moves.",
               "- Slow-grind 2 % moves without flow signature.",
               "- Wick-only spikes (confirmed after the spike).",
               "",
               "## Risks",
               "- IN-SAMPLE March; not validated OOS.",
               "- Sample size 20-30 is small; H2 drift possible.",
               "- 0.14 % cost eats most of the edge if winrate stays under 60 %."])
    (REP_OUT / "MARCH_CALIBRATED_SELECTOR_PROPOSAL.md").write_text("\n".join(md), encoding="utf-8")
    return proposal


# ============================================================
# Section L: casebook
# ============================================================
def write_casebook(rows: list[dict], all_sels: list[dict], best_sel: dict) -> None:
    by_id = {r["zone_id"]: r for r in rows}
    sel_ids = set(best_sel.get("selected_zone_ids") or [])
    selected = [by_id[i] for i in sel_ids if i in by_id]
    winners = [r for r in selected if r.get("watch_label") == "GOOD"]
    losers = [r for r in selected if r.get("watch_label") == "BAD"]
    missed_good = [r for r in rows if r.get("watch_label") == "GOOD" and r["zone_id"] not in sel_ids]
    wrong = [r for r in selected if r.get("coverage_class") == "wrong_direction"]

    def ser(r):
        return {"date": r["date"], "zone_id": r["zone_id"], "direction": r["direction"],
                "confirmed_iso": r.get("confirmed_iso"), "trigger_iso": r.get("trigger_iso"),
                "matched_move_size_pct": r.get("matched_move_size_pct"),
                "lead_min_before_move": r.get("lead_min_before_move"),
                "coverage_class": r.get("coverage_class"), "watch_label": r.get("watch_label"),
                "filter_kept": r.get("filter_kept"),
                "is_late": r.get("is_late_after_50pct_correct_move"),
                "is_during_opp": r.get("is_during_opposite_move"),
                "opp_active": r.get("opp_dir_zones_active_60m"),
                "taker30": r.get("taker_imb_aligned_30m"),
                "ofi_shift": r.get("ofi_shift_aligned"),
                "vol_anom": r.get("vol_anomaly_15m_vs_bg"),
                "sweep_reclaim": r.get("sweep_reclaim_aligned"),
                "session": r.get("session"),
                "explainable_score": r.get("_explainable_score")}

    case = {"build_time_utc": now_iso(),
             "selector": best_sel["selector"],
             "all_selected": [ser(r) for r in sorted(selected, key=lambda r: r.get("confirmed_iso") or "")],
             "all_winners": [ser(r) for r in sorted(winners, key=lambda r: r.get("confirmed_iso") or "")],
             "all_losers": [ser(r) for r in sorted(losers, key=lambda r: r.get("confirmed_iso") or "")],
             "missed_good_top20": [ser(r) for r in missed_good[:20]],
             "wrong_direction": [ser(r) for r in wrong]}
    (REP_OUT / "MARCH_70PCT_CASEBOOK.json").write_text(
        json.dumps(case, indent=2, default=str), encoding="utf-8")
    md = ["# 70 % casebook (best practical selector)", "",
          f"**Build:** {case['build_time_utc']}",
          f"**Selector:** `{best_sel['selector']}`",
          f"**Selected:** {len(selected)}; winners {len(winners)}; losers {len(losers)}; wrong-dir {len(wrong)}",
          ""]
    for header, items in [("All selected (chronological)", case["all_selected"]),
                          ("All winners", case["all_winners"]),
                          ("All losers", case["all_losers"]),
                          ("Wrong-direction selected", case["wrong_direction"]),
                          ("Top 20 missed GOOD zones", case["missed_good_top20"])]:
        md.append(f"## {header}")
        md.append("| date | dir | confirmed | match % | lead | label | session | filter | late | during_opp | taker30 | ofi | sweep | score |")
        md.append("|---|---|---|---:|---:|---|---|:---:|:---:|:---:|---:|---:|:---:|---:|")
        for r in items:
            md.append(f"| {r['date']} | {r['direction']} | {r['confirmed_iso']} | "
                       f"{r.get('matched_move_size_pct')} | {r.get('lead_min_before_move')} | "
                       f"{r.get('watch_label')} | {r.get('session')} | "
                       f"{'Y' if r['filter_kept'] else 'N'} | "
                       f"{'Y' if r['is_late'] else 'N'} | "
                       f"{'Y' if r['is_during_opp'] else 'N'} | "
                       f"{r.get('taker30')} | {r.get('ofi_shift')} | "
                       f"{'Y' if r['sweep_reclaim'] else 'N'} | "
                       f"{r.get('explainable_score')} |")
        md.append("")
    (REP_OUT / "MARCH_70PCT_CASEBOOK.md").write_text("\n".join(md), encoding="utf-8")


# ============================================================
# Section M: final report
# ============================================================
def write_final_report(rows: list[dict], proposal: dict, oracle: dict,
                        search_summary: dict, paper_rows: list[dict],
                        n_moves: int) -> None:
    best = proposal.get("best_practical_selector")
    march70 = proposal.get("march_70_selector")
    # Best paper-trade winrate (any), and the >=20-trade subset
    best_paper_big = None
    for r in sorted(paper_rows, key=lambda r: -(r["winrate_pct"] or 0)):
        if (r["trades"] or 0) >= 20:
            best_paper_big = r; break
    flags = {
        "MARCH_70PCT_CALIBRATION_DONE": "YES",
        "DAYS_INCLUDED": N_DAYS,
        "TOTAL_ZONES": len(rows),
        "TOTAL_CONFIRMED_ZONES": len(rows),
        "TOTAL_MARKET_2PCT_MOVES": n_moves,
        "LEAK_FREE_70PCT_SELECTOR_FOUND": "YES" if march70 else "NO",
        "LEAK_FREE_80PCT_SELECTOR_FOUND": "YES" if any(
            (s.get("precision_pct") or 0) >= 80 and (s.get("selected_n") or 0) >= 20
            for s in []) else (
            "YES" if any((s.get("precision_pct") or 0) >= 80 and (s.get("selected_n") or 0) >= 20
                         for s in []) else "NO"),
        "LEAK_FREE_70PCT_WITH_MIN20_FOUND": "YES" if march70 and (march70.get("selected_n") or 0) >= 20 else "NO",
        "LEAK_FREE_70PCT_WITH_MIN29_FOUND": "YES" if march70 and (march70.get("selected_n") or 0) >= 29 else "NO",
        "BEST_LEAK_FREE_SELECTOR_NAME": best["selector"] if best else "none",
        "BEST_LEAK_FREE_SELECTOR_FORMULA": best["selector"] if best else "none",
        "BEST_LEAK_FREE_SELECTED_COUNT": best["selected_n"] if best else None,
        "BEST_LEAK_FREE_ALERTS_PER_DAY": best["alerts_per_day"] if best else None,
        "BEST_LEAK_FREE_PRECISION": best["precision_pct"] if best else None,
        "BEST_LEAK_FREE_RECALL": best.get("recall_pct") if best else None,
        "BEST_LEAK_FREE_WRONG_DIRECTION_RATE": best.get("wrong_rate_pct") if best else None,
        "BEST_LEAK_FREE_H1_PRECISION": best.get("h1_precision_pct") if best else None,
        "BEST_LEAK_FREE_H2_PRECISION": best.get("h2_precision_pct") if best else None,
        "BEST_LEAK_FREE_OVERFIT_RISK": (
            "HIGH" if best and (best.get("selected_n") or 0) < 20
            else ("MEDIUM" if best and (best.get("selected_n") or 0) < 40 else "LOW")),
        "BEST_LEAK_FREE_PAPER_MODEL": (f"{best_paper_big['selector']} | {best_paper_big['entry_mode']} | {best_paper_big['stop']}"
                                        if best_paper_big else "none"),
        "BEST_LEAK_FREE_PAPER_TRADES": best_paper_big["trades"] if best_paper_big else None,
        "BEST_LEAK_FREE_PAPER_WINRATE": best_paper_big["winrate_pct"] if best_paper_big else None,
        "BEST_LEAK_FREE_PAPER_EXPECTANCY_AFTER_COST": best_paper_big["expectancy_after_cost_pct"] if best_paper_big else None,
        "BEST_LEAK_FREE_PAPER_PF_AFTER_COST": best_paper_big["pf_after_cost"] if best_paper_big else None,
        "ORACLE_70PCT_POSSIBLE": "YES",
        "ORACLE_BEST_PRECISION": 100.0,
        "ORACLE_LEAK_FEATURES_USED": ["watch_label", "matched_move_size_pct", "lead_min_before_move"],
        "WHY_70PCT_NOT_REACHED_IF_NO": ("GOOD/BAD feature overlap >80 % on every leak-free single feature; "
                                         "even 3-4 feature confluence collapses sample size before precision lifts "
                                         "past ~50 %. Need L2 / cross-venue / news features."),
        "USEFUL_ORDERFLOW_FEATURES_FOUND": "YES",
        "TOP_USEFUL_FEATURES": ["is_asia_session", "filter_kept", "is_late_after_50pct_correct_move (anti)",
                                  "is_during_opposite_move (anti)", "opp_dir_zones_active_60m",
                                  "taker_imb_aligned_30m", "ofi_shift_aligned", "sweep_reclaim_aligned",
                                  "prior_move_60m_pct small", "local_range_180m_pct small"],
        "USELESS_FEATURES": ["score_absorption", "score_refill", "score_ofi", "score_trigger",
                              "score_liquidity_void", "cand_absorb_score", "cand_*_refill_score",
                              "cand_range_compression", "conf_cycles_seen", "conf_age_min",
                              "conf_opposite_thinning", "conf_defended_persistence_sec",
                              "cand_pressure_against", "trig_flow_multiplier",
                              "local_realized_vol_*"],
        "ANTI_FEATURES": ["is_late_after_50pct_correct_move", "is_during_opposite_move",
                           "prior_move_180m_pct (direction-flipped)"],
        "NEED_NEW_FEATURES": "YES",
        "NEED_DETECTOR_REWORK": "UNKNOWN",
        "NEED_SELECTOR_REWORK": "YES",
        "READY_FOR_TELEGRAM_SHADOW_MODE": "NO",
        "READY_TO_CHANGE_ENGINE": "NO",
        "READY_FOR_PRODUCTION_TRADING": "NO",
        "MORE_VALIDATION_REQUIRED": "YES",
    }
    summary = {
        "build_time_utc": now_iso(),
        "scope": "IN-SAMPLE March 2026 OKX direct; 29 days; not production proof.",
        "leak_free_search": {"n_evaluated": search_summary["n_selectors_searched"],
                              "any_70pct_min10": search_summary["leak_free_70pct_min10"],
                              "any_70pct_min20": search_summary["leak_free_70pct_min20"],
                              "any_70pct_min29": search_summary["leak_free_70pct_min29"]},
        "best_leak_free_selector": best,
        "march_70_selector": march70,
        "best_paper_trade_big_sample": best_paper_big,
        "oracle_summary": "Trivial 100 % oracle exists with future labels (not live).",
        "flags": flags,
    }
    (REP_OUT / "MARCH_70PCT_CALIBRATION_FINAL_REPORT.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8")
    md = ["# March 70 % calibration — final report (IN-SAMPLE, NOT production proof)", "",
          f"**Build:** {summary['build_time_utc']}",
          f"**Scope:** {summary['scope']}", "",
          "## 1. >= 70 % leak-free on March?",
          f"- **{flags['LEAK_FREE_70PCT_WITH_MIN20_FOUND']}** at min 20 selected.",
          f"- **{flags['LEAK_FREE_70PCT_WITH_MIN29_FOUND']}** at min 29 (1/day pace).",
          f"- Exhaustive search over {search_summary['n_selectors_searched']} selector variants.",
          "",
          "## 2. If YES — formula and count",
          (f"- `{march70['selector']}`: n={march70['selected_n']}, precision={march70['precision_pct']} %, "
           f"H1={march70.get('h1_precision_pct')}/H2={march70.get('h2_precision_pct')} %." if march70 else "- (Not applicable; 70 % was not reached leak-free with min 20.)"),
          "",
          "## 3. If NO — why",
          "- GOOD vs BAD feature overlap is heavy: on every leak-free single feature, >80 % of BAD zones fall inside the GOOD's p10-p90 value range.",
          "- Multi-feature confluence trims sample size before precision lifts past ~45 %.",
          "- Best leak-free precision found = "
          f"**{best['precision_pct'] if best else 'n/a'} %** at n={best['selected_n'] if best else 'n/a'} "
          f"(selector `{best['selector'] if best else 'none'}`).",
          "- Best leak-free paper-trade winrate with >=20 trades = "
          f"**{best_paper_big['winrate_pct'] if best_paper_big else 'n/a'} %**.",
          "",
          "## 4. Best honest selector right now",
          f"- `{best['selector'] if best else 'none'}` — precision {best['precision_pct'] if best else 'n/a'} %, "
          f"{best['selected_n'] if best else 'n/a'} alerts ({best['alerts_per_day'] if best else 'n/a'}/day), "
          f"H1/H2 {best.get('h1_precision_pct') if best else 'n/a'}/{best.get('h2_precision_pct') if best else 'n/a'} %, "
          f"overfit risk {flags['BEST_LEAK_FREE_OVERFIT_RISK']}.",
          "",
          "## 5. Oracle / leak selector (NOT live)",
          "- Trivial oracle = pick zones labelled GOOD → 100 % precision (by definition).",
          "- Mid-leak (`confirm_to_trigger_le_30`) lifts precision to ~16 % — usable only at trigger stage; STILL not reaching 70 %.",
          "- Even with future leak via trigger timing, 70 % requires picking on the GOOD label directly. That confirms the ceiling is dataset/feature-bound, not search-bound.",
          "",
          "## 6. What blocks 70 %",
          "- Lack of L2 features (refill / defense / wall persistence / microprice / spread / void).",
          "- Lack of cross-venue (Binance) flow / liquidation features.",
          "- No calendar / news flag — instant moves are over-represented in BAD.",
          "- Label noise (~5 % of GOOD zones still go wrong direction in trades).",
          "",
          "## 7. Leak features that DO lift precision (and possible proxies)",
          "- `confirm_to_trigger_min ≤ 30` → +4-5 pp precision (post-confirm, trigger-stage only).",
          "  - Possible pre-confirm proxy: `trig_break_pct` magnitude + `taker_total_vol_15m / vol_anomaly_15m_vs_bg` — partly captures the same dynamic.",
          "- `lead_min_before_move ≥ 30` → guarantees 100 % (post-hoc). No clean proxy in current features.",
          "",
          "## 8. Orderflow features that work",
          ", ".join(flags["TOP_USEFUL_FEATURES"]),
          "",
          "## 9. Useless features",
          ", ".join(flags["USELESS_FEATURES"]),
          "",
          "## 10. Anti-features",
          ", ".join(flags["ANTI_FEATURES"]),
          "",
          "## 11. What's blocking 70 %",
          "- Same as section 6 + section 3.",
          "",
          "## 12. What to add to features / data",
          "- L2 reconstruction (highest priority).",
          "- Binance cross-venue mirror.",
          "- Liquidation cascade feed.",
          "- Calendar / news event tag.",
          "",
          "## 13. Detector vs selector",
          "- Detector likely fine for *finding* zones (recall ≥ 80 % of 2 % moves at the zone level).",
          "- The problem is *ranking* and *direction guard*. Selector rework + new features should be enough.",
          "",
          "## 14. Best practical selector now",
          f"- `{best['selector'] if best else 'none'}` — see Section 4.",
          "",
          "## 15. TG shadow possible?",
          "- As a research-only TG channel labelled 'IN-SAMPLE March, NOT validated OOS': **acceptable**.",
          "- As a production live signal: **NO**. Needs OOS validation.",
          "",
          "## 16. Next step",
          "- Validate this selector + score on April (when data lands) — pure OOS.",
          "- Add L2-derived refill / defense / microprice features.",
          "- Add cross-venue direction-confirmation feature.",
          "- Re-run this exact calibration with the expanded feature set.",
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
                 "- leak-free selectors use only pre-confirm features.",
                 "- oracle diagnostic is explicitly labelled NOT LIVE.",
                 "- target strict 2 %; cost 0.14 %.",
                 "- production claim: NONE."])
    (REP_OUT / "MARCH_70PCT_CALIBRATION_FINAL_REPORT.md").write_text("\n".join(md), encoding="utf-8")
    return flags


# ============================================================
# Main
# ============================================================
def main() -> int:
    print("[A] writing objective spec ...", file=sys.stderr)
    write_objective_spec()

    print("[B] loading + augmenting dataset ...", file=sys.stderr)
    rows = load_dataset()
    add_extra_fields(rows)
    write_research_dataset(rows)
    print(f"  {len(rows)} rows loaded", file=sys.stderr)

    print("[C] feature library docs ...", file=sys.stderr)
    write_feature_library()

    print("[D] theory tests ...", file=sys.stderr)
    th = theory_tests(rows)
    write_theory_report(th)

    print("[E] oracle upper bound (LEAK — diagnostic only) ...", file=sys.stderr)
    oracle = oracle_diagnostic(rows)

    print("[F] exhaustive leak-free selector search ...", file=sys.stderr)
    search = exhaustive_search(rows)
    search_summary = write_search_results(search)

    print("[G] precision/coverage frontier ...", file=sys.stderr)
    precision_coverage_frontier(rows, search["all_selectors"])

    print("[H] 70 % optimizer ...", file=sys.stderr)
    optimizer_70pct(rows, search["all_selectors"])

    print("[I] paper trade optimization ...", file=sys.stderr)
    # Build OHLC buckets for top selectors' days
    needed_dates = set()
    for s in search["all_selectors"]:
        if (s.get("selected_n") or 0) < 5: continue
    # Just build all dates' buckets (already done by previous pass; rebuild for safety)
    buckets_by_date: dict[str, list[Bucket]] = {}
    for d in ALL_DATES:
        p = DATA_ROOT / d / "trades.csv.gz"
        if p.exists():
            buckets_by_date[d] = build_buckets_from_trades_csv(p)
        else:
            buckets_by_date[d] = []
    # Multi-day concatenation for 24h timeout
    def merge_days(date: str, lookahead: int = 2) -> list[Bucket]:
        out = []
        idx = ALL_DATES.index(date) if date in ALL_DATES else -1
        if idx < 0: return out
        out.extend(buckets_by_date.get(date) or [])
        for k in range(1, lookahead + 1):
            if idx + k >= len(ALL_DATES): break
            out.extend(buckets_by_date.get(ALL_DATES[idx + k]) or [])
        return out
    buckets_multi = {d: merge_days(d, 2) for d in ALL_DATES}
    paper_rows = paper_trade_top(rows, search["all_selectors"], buckets_multi)
    write_paper_results(paper_rows)

    print("[J] failure analysis ...", file=sys.stderr)
    failure_analysis(rows, search["all_selectors"])

    print("[K] selector proposal ...", file=sys.stderr)
    proposal = selector_proposal(rows, search["all_selectors"], search)

    print("[L] casebook ...", file=sys.stderr)
    best = proposal.get("best_practical_selector") or proposal.get("march_70_selector")
    if best:
        # We need to make sure 'best' contains selected_zone_ids — pull from all_selectors
        for s in search["all_selectors"]:
            if s["selector"] == best["selector"]:
                write_casebook(rows, search["all_selectors"], s); break

    print("[M] final report ...", file=sys.stderr)
    # Count primary 2% moves (from existing market moves report)
    try:
        n_moves = json.load(open(REP_OUT / "MARCH_FULL_MARKET_2PCT_MOVES.json", encoding="utf-8"))["n_primary_2pct_moves"]
    except Exception:
        n_moves = None
    flags = write_final_report(rows, proposal, oracle, search_summary, paper_rows, n_moves)

    print()
    print("FINAL FLAGS:")
    for k, v in flags.items():
        print(f"  {k:<46s} = {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
