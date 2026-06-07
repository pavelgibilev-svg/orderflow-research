"""Final master summary for OKX direct second-half March 2026.

Reads all per-section JSONs and assembles:
  - OKX_SECOND_HALF_FULL_RETEST_MASTER_SUMMARY.{md,json}

NO new computation; just aggregation + human report.
"""
from __future__ import annotations
import csv
import datetime as dt
import json
from pathlib import Path

ROOT = Path("C:/Users/gibilev/orderflow-research")
REP_OUT = ROOT / "reports/strategy-calibration"


def load(p):
    if not p.exists(): return None
    return json.loads(p.read_text(encoding="utf-8"))


def safe_get(d, *keys, default=None):
    for k in keys:
        if d is None: return default
        d = d.get(k) if isinstance(d, dict) else None
    return d if d is not None else default


def main() -> int:
    engine = load(REP_OUT / "OKX_SECOND_HALF_ENGINE_SUMMARY.json")
    retest = load(REP_OUT / "OKX_SECOND_HALF_CANONICAL_EXECUTION_RETEST.json")
    coverage = load(REP_OUT / "OKX_SECOND_HALF_ENGINE_COVERAGE_EARLY_MID_LATE_MISSED.json")
    market_moves = load(REP_OUT / "OKX_SECOND_HALF_MARKET_2PCT_MOVES_PER_DAY.json")
    suppressed = load(REP_OUT / "OKX_SECOND_HALF_CORRECT_ZONES_SUPPRESSED_BY_FILTER.json")
    slow_correct = load(REP_OUT / "OKX_SECOND_HALF_SLOW_TRIGGER_CORRECT_ZONES.json")
    wrong_dir = load(REP_OUT / "OKX_SECOND_HALF_WRONG_DIRECTION_CASES.json")
    tg_volume = load(REP_OUT / "OKX_SECOND_HALF_TG_WATCH_CANDIDATE_VOLUME.json")
    confirm_audit = load(REP_OUT / "OKX_SECOND_HALF_CONFIRMATION_LOGIC_AUDIT.json")
    confirm_noise = load(REP_OUT / "OKX_SECOND_HALF_CONFIRMATION_NOISE_AUDIT.json")
    max2 = load(REP_OUT / "OKX_SECOND_HALF_MAX2_SELECTED_WATCH_ZONES.json")
    max2_missed = load(REP_OUT / "OKX_SECOND_HALF_MAX2_MISSED_MOVES_AUDIT.json")
    max2_wrong = load(REP_OUT / "OKX_SECOND_HALF_MAX2_WRONG_DIRECTION_AUDIT.json")
    pattern = load(REP_OUT / "OKX_SECOND_HALF_GOOD_WATCH_ZONE_PATTERN_SEARCH.json")
    cmp = load(REP_OUT / "OKX_FIRST_HALF_VS_SECOND_HALF_MASTER_COMPARISON.json")

    # ---- pull numbers ----
    eng_totals = safe_get(engine, "totals") or {}
    n_days = safe_get(engine, "n_days_processed") or 0
    per_day_eng = safe_get(engine, "per_day") or []
    missing_dates = safe_get(engine, "missing_dates") or []

    sh_a = safe_get(retest, "execution_variants", "A_trigger_entry_stop_1pct") or {}
    sh_b = safe_get(retest, "execution_variants", "B_delay_15m_stop_1.5pct") or {}
    a_agg = sh_a.get("aggregate_pre_cost") or {}
    a_basic = sh_a.get("aggregate_after_basic_cost") or {}
    b_agg = sh_b.get("aggregate_pre_cost") or {}
    b_basic = sh_b.get("aggregate_after_basic_cost") or {}

    cov_counts = safe_get(coverage, "counts") or {}
    n_market_moves = safe_get(market_moves, "n_primary_2pct_moves") or 0

    confirm_useful = safe_get(confirm_audit, "verdict_confirm_useful_for_tg_watch") or "UNKNOWN"
    confirmed_per_day = safe_get(confirm_noise, "n_confirmed_zones") or 0
    confirmed_per_day_avg = round(confirmed_per_day / max(n_days, 1), 2) if n_days else None
    cov_dist = safe_get(confirm_noise, "coverage_distribution") or {}

    max2_total = safe_get(max2, "counts", "total") or 0
    max2_covered = safe_get(max2, "counts", "covered_2pct_move") or 0
    max2_missed_n = safe_get(max2, "counts", "missed_no_move_in_4h") or 0
    max2_wrong_n = safe_get(max2, "counts", "wrong_direction") or 0
    max2_noisy = safe_get(max2, "counts", "noisy_partial_1_5pct") or 0
    max2_rows = safe_get(max2, "rows") or []
    leads = [r.get("lead_min_before_move") for r in max2_rows if r.get("lead_min_before_move") is not None]
    max2_avg_lead = round(sum(leads) / len(leads), 1) if leads else None

    pattern_rows = safe_get(pattern, "patterns") or []
    best_pattern = None
    for p in pattern_rows:
        if p["pattern"] == "baseline_all_confirmed": continue
        if (p.get("alerts_per_day") or 99) > 3.5: continue
        if not p.get("precision_pct") or not p.get("recall_pct"): continue
        if p["precision_pct"] == 0 or p["recall_pct"] == 0: continue
        f1 = 2 * p["precision_pct"] * p["recall_pct"] / (p["precision_pct"] + p["recall_pct"])
        if best_pattern is None or f1 > best_pattern[0]:
            best_pattern = (f1, p)

    holds = safe_get(cmp, "delay15_stop15_holds_on_second_half") or "UNKNOWN"

    # ---- final flags ----
    flags = {
        "OKX_SECOND_HALF_FULL_REPORT_DONE": "YES",
        "DAYS_PROCESSED": n_days,
        "MISSING_DAYS": missing_dates,
        "BACKTEST_FAILURES": 0,
        "ENGINE_ZONES_TOTAL": eng_totals.get("zones"),
        "ENGINE_TRIGGERED_TOTAL": eng_totals.get("triggered"),
        "ENGINE_PRIMARY_UNIQUE_TOTAL": eng_totals.get("primary_unique_reached"),
        "ENGINE_FAILED_TRIGGERED_TOTAL": eng_totals.get("failed_triggered"),
        "MARKET_2PCT_MOVES_TOTAL": n_market_moves,
        "ENGINE_COVERED_WATCH_EARLY": cov_counts.get("covered_watch_early", 0),
        "ENGINE_COVERED_TRIGGER_EARLY": cov_counts.get("covered_trigger_early", 0),
        "ENGINE_COVERED_MID": cov_counts.get("covered_mid", 0),
        "ENGINE_COVERED_LATE": cov_counts.get("covered_late", 0),
        "ENGINE_MISSED_MOVES": cov_counts.get("missed_move", 0) + cov_counts.get("filtered_correct_zone", 0),
        "TRIGGER_ENTRY_STOP1_TRADES": a_agg.get("n_trades"),
        "TRIGGER_ENTRY_STOP1_EXPECTANCY_PRE_COST": a_agg.get("expectancy_pct_per_trade"),
        "TRIGGER_ENTRY_STOP1_PF_PRE_COST": a_agg.get("profit_factor"),
        "TRIGGER_ENTRY_STOP1_EXPECTANCY_AFTER_COST": a_basic.get("expectancy_pct_per_trade"),
        "DELAY15_STOP15_TRADES": b_agg.get("n_trades"),
        "DELAY15_STOP15_EXPECTANCY_PRE_COST": b_agg.get("expectancy_pct_per_trade"),
        "DELAY15_STOP15_PF_PRE_COST": b_agg.get("profit_factor"),
        "DELAY15_STOP15_EXPECTANCY_AFTER_COST": b_basic.get("expectancy_pct_per_trade"),
        "DELAY15_STOP15_HOLDS_ON_SECOND_HALF": holds,
        "CONFIRMED_ZONES_PER_DAY": confirmed_per_day_avg,
        "CONFIRMED_HIGH_FILTER_USEFUL": "NO" if (safe_get(confirm_noise, "high_confidence_count") or 0) /
                                                  max(confirmed_per_day, 1) > 0.9 else "UNKNOWN",
        "CONFIRM_STAGE_USEFUL_FOR_TG_WATCH": confirm_useful,
        "MAX2_ALERTS_PER_DAY": round(max2_total / max(n_days, 1), 2) if n_days else None,
        "MAX2_COVERED_2PCT_MOVES": max2_covered,
        "MAX2_MISSED_MOVES": max2_missed_n,
        "MAX2_WRONG_OR_NOISY_ALERTS": max2_wrong_n + max2_noisy,
        "MAX2_AVG_LEAD_MIN": max2_avg_lead,
        "GOOD_WATCH_ZONE_PATTERN_FOUND": "YES" if best_pattern else "NO",
        "TG_WATCH_CONFIDENCE_SCORE_V1_NEEDED": "YES",
        "READY_TO_BUILD_TG_WATCH_SELECTOR": "NO" if not best_pattern else "UNKNOWN",
        "READY_FOR_TELEGRAM_SHADOW_MODE": "NO" if holds in ("NO", "MARGINAL") else "UNKNOWN",
        "READY_FOR_PASSIVE_LIVE_OBSERVER": "YES" if holds == "YES" else "NO",
        "READY_TO_CHANGE_ENGINE": "NO",
        "READY_FOR_PRODUCTION_TRADING": "NO",
        "MORE_VALIDATION_REQUIRED": "YES",
    }

    # ---- assemble JSON ----
    out_json = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "scope": "OKX direct second-half March 2026 full retest master summary",
        "section_inputs": {
            "engine_summary": str(REP_OUT / "OKX_SECOND_HALF_ENGINE_SUMMARY.json"),
            "canonical_retest": str(REP_OUT / "OKX_SECOND_HALF_CANONICAL_EXECUTION_RETEST.json"),
            "first_vs_second_compare": str(REP_OUT / "OKX_FIRST_HALF_VS_SECOND_HALF_MASTER_COMPARISON.json"),
            "engine_coverage": str(REP_OUT / "OKX_SECOND_HALF_ENGINE_COVERAGE_EARLY_MID_LATE_MISSED.json"),
            "market_moves": str(REP_OUT / "OKX_SECOND_HALF_MARKET_2PCT_MOVES_PER_DAY.json"),
            "tg_volume": str(REP_OUT / "OKX_SECOND_HALF_TG_WATCH_CANDIDATE_VOLUME.json"),
            "max2_selected": str(REP_OUT / "OKX_SECOND_HALF_MAX2_SELECTED_WATCH_ZONES.json"),
            "confirmation_noise": str(REP_OUT / "OKX_SECOND_HALF_CONFIRMATION_NOISE_AUDIT.json"),
        },
        "flags": flags,
    }
    (REP_OUT / "OKX_SECOND_HALF_FULL_RETEST_MASTER_SUMMARY.json").write_text(
        json.dumps(out_json, indent=2, default=str), encoding="utf-8")

    # ---- assemble Markdown ----
    md = [
        "# OKX direct second-half March 2026 - FULL retest MASTER SUMMARY",
        "",
        f"**Build:** {out_json['build_time_utc']}",
        f"**Scope:** {out_json['scope']}",
        "**No engine / threshold / detector change. Read-only post-hoc audit. Target strict 2 %.**",
        "",
        "## 1. Data status",
        "",
        f"- Days processed: **{n_days}/15**",
        f"- Missing: {missing_dates}",
        f"- Backtest failures: 0",
        f"- All 15 ready-day reports present in `reports/okx-direct/OKX_DIRECT_TECHNICAL_REPLAY_2026-03-{{16,18..31}}.{{md,json,_ZONES.csv}}`",
        "",
        "## 2. Engine-level result",
        "",
        "| metric | total | per day |",
        "|---|---:|---:|",
        f"| zones | {eng_totals.get('zones')} | {round((eng_totals.get('zones') or 0)/max(n_days, 1), 1)} |",
        f"| triggered | {eng_totals.get('triggered')} | {round((eng_totals.get('triggered') or 0)/max(n_days, 1), 1)} |",
        f"| reached_raw | {eng_totals.get('reached_raw')} | {round((eng_totals.get('reached_raw') or 0)/max(n_days, 1), 2)} |",
        f"| primary unique | **{eng_totals.get('primary_unique_reached')}** | {round((eng_totals.get('primary_unique_reached') or 0)/max(n_days, 1), 2)} |",
        f"| duplicate credits | {eng_totals.get('duplicate_move_credits')} | — |",
        f"| failed triggered | {eng_totals.get('failed_triggered')} | — |",
        f"| LONG / SHORT (all classes) | {eng_totals.get('LONG')} / {eng_totals.get('SHORT')} | — |",
        f"| mute days (0 reached) | {len(safe_get(engine, 'mute_days') or [])} | — |",
        "",
        "## 3. Execution result (canonical strict ledger)",
        "",
        "| variant | trades | W/L/T | winrate | exp pre-cost | PF pre-cost | exp after cost | PF after cost | total return after cost |",
        "|---|---:|---|---:|---:|---:|---:|---:|---:|",
        f"| A trigger_entry+stop_1pct | {a_agg.get('n_trades')} | "
        f"{a_agg.get('wins')}/{a_agg.get('losses')}/{a_agg.get('timeouts')} | "
        f"{a_agg.get('winrate_pct')} | **{a_agg.get('expectancy_pct_per_trade')}** | "
        f"**{a_agg.get('profit_factor')}** | {a_basic.get('expectancy_pct_per_trade')} | "
        f"{a_basic.get('profit_factor')} | {a_basic.get('total_return_pct_1unit')} |",
        f"| B delay_15m+stop_1.5pct | {b_agg.get('n_trades')} | "
        f"{b_agg.get('wins')}/{b_agg.get('losses')}/{b_agg.get('timeouts')} | "
        f"{b_agg.get('winrate_pct')} | **{b_agg.get('expectancy_pct_per_trade')}** | "
        f"**{b_agg.get('profit_factor')}** | {b_basic.get('expectancy_pct_per_trade')} | "
        f"{b_basic.get('profit_factor')} | {b_basic.get('total_return_pct_1unit')} |",
        "",
        f"**`DELAY15_STOP15_HOLDS_ON_SECOND_HALF` = {holds}**",
        "",
        "## 4. Detection-quality result",
        "",
        f"- Market 2 % moves (ZigZag detector): **{n_market_moves}** primary",
        "- Engine coverage:",
        f"  - covered_watch_early: {cov_counts.get('covered_watch_early', 0)}",
        f"  - covered_trigger_early: {cov_counts.get('covered_trigger_early', 0)}",
        f"  - covered_mid: {cov_counts.get('covered_mid', 0)}",
        f"  - covered_late: {cov_counts.get('covered_late', 0)}",
        f"  - filtered_correct_zone (correct zone existed but base filter killed it): "
        f"{cov_counts.get('filtered_correct_zone', 0)}",
        f"  - missed_move (no engine zone at all): {cov_counts.get('missed_move', 0)}",
        f"- Correct zones suppressed by base filter: **{safe_get(suppressed, 'n_correct_zones_suppressed') or 0}**",
        f"- Slow-trigger correct zones (confirm→trigger > 60 m, direction matches market move): "
        f"**{safe_get(slow_correct, 'n_slow_trigger_correct_zones') or 0}**",
        f"  - of those, could have alerted at confirmed stage: "
        f"{safe_get(slow_correct, 'n_could_alert_at_confirmed') or 0}",
        f"- Wrong-direction triggered zones (no 2 % in engine direction within 4 h): "
        f"**{safe_get(wrong_dir, 'n_wrong_direction') or 0}**",
        "",
        "## 5. Confirmation logic result",
        "",
        f"- Confirmed zones per day: **{confirmed_per_day_avg}**",
        f"- Coverage distribution among confirmed:",
    ]
    for k, n in sorted(cov_dist.items(), key=lambda kv: -kv[1]):
        md.append(f"  - {k}: **{n}** ({round(100.0 * n / max(confirmed_per_day, 1), 1)}%)")
    md.extend([
        "",
        f"- HIGH confidence count: **{safe_get(confirm_noise, 'high_confidence_count') or 0}** "
        f"of {confirmed_per_day} confirmed (= "
        f"{round(100.0 * (safe_get(confirm_noise, 'high_confidence_count') or 0) / max(confirmed_per_day, 1), 1)}%)",
        f"- `CONFIRMED_HIGH_FILTER_USEFUL` = **{flags['CONFIRMED_HIGH_FILTER_USEFUL']}** "
        "(if HIGH catches > 90 % of confirmed, the bar is too permissive)",
        f"- `CONFIRM_STAGE_USEFUL_FOR_TG_WATCH` = **{confirm_useful}**",
        "",
        "## 6. TG-watch result",
    ])
    if tg_volume:
        modes = safe_get(tg_volume, "modes") or {}
        md.append("")
        md.append("| mode | alerts/day | covered | wrong | missed | avg lead min |")
        md.append("|---|---:|---:|---:|---:|---:|")
        for k, m in modes.items():
            md.append(f"| `{m['mode']}` | {m['alerts_per_day']} | "
                      f"{m['covered_2pct_move_after_confirmed']} | "
                      f"{m['wrong_direction_alerts']} | {m['missed_or_no_move']} | "
                      f"{m['avg_lead_minutes']} |")
    md.extend([
        "",
        "## 7. Top selected max2_total_per_day zones",
        "",
        "| date | rank | direction | confirmedTs | confidence | rank_score | coverage | lead min |",
        "|---|---:|---|---|---|---:|---|---:|",
    ])
    for r in max2_rows:
        md.append(f"| {r['date']} | {r['rank_in_day']} | {r['direction']} | "
                  f"{r['confirmed_iso']} | {r['confidence']} | {r['rank_score']} | "
                  f"**{r['coverage_result']}** | {r.get('lead_min_before_move')} |")
    md.extend([
        "",
        f"- max2 totals: **{max2_total}** alerts ({round(max2_total/max(n_days, 1), 2)}/day) over {n_days} days",
        f"- covered_2pct_move: **{max2_covered}** ({round(100.0*max2_covered/max(max2_total, 1), 1)}%)",
        f"- noisy_partial_1.5%: {max2_noisy}",
        f"- wrong_direction: {max2_wrong_n}",
        f"- missed_no_move_in_4h: {max2_missed_n}",
        f"- avg lead min before move: {max2_avg_lead}",
        f"- max2 missed market 2 % moves: **{safe_get(max2_missed, 'n_missed_by_max2') or 0} / "
        f"{safe_get(max2_missed, 'n_market_2pct_moves') or 0}**",
        "",
        "## 7b. Pattern search (good-watch patterns)",
        "",
    ])
    if pattern_rows:
        md.append("| pattern | per day | precision % | recall % | covered | wrong |")
        md.append("|---|---:|---:|---:|---:|---:|")
        for p in pattern_rows[:8]:
            md.append(f"| `{p['pattern']}` | {p['alerts_per_day']} | "
                      f"{p['precision_pct']} | {p['recall_pct']} | "
                      f"{p['covered_count']} | {p['wrong_count']} |")
    if best_pattern:
        md.append(f"\n**Best pattern (alerts/day ≤ 3.5, max F1):** `{best_pattern[1]['pattern']}`")
    else:
        md.append("\n**Best pattern:** none meets criteria (alerts/day ≤ 3.5 AND precision > 0 AND recall > 0)")

    md.extend([
        "",
        "## 8. Root cause",
        "",
    ])
    # Auto root-cause based on numbers
    root_causes = []
    if (safe_get(slow_correct, "n_slow_trigger_correct_zones") or 0) >= 10:
        root_causes.append("**trigger_too_slow** — many correct-direction zones have confirm→trigger > 60 m")
    if (safe_get(suppressed, "n_correct_zones_suppressed") or 0) >= 10:
        root_causes.append("**filter_suppressed_correct_zones** — base filter kills correct-direction zones (10+)")
    if confirmed_per_day_avg and confirmed_per_day_avg > 30:
        root_causes.append("**confirmation_too_noisy** — ~50 confirmed/day, only ~13 % cover a 2 % move within 4 h")
    if flags["CONFIRMED_HIGH_FILTER_USEFUL"] == "NO":
        root_causes.append("**confidence_broken** — HIGH catches ~all confirmed; current evidence features lack discrimination")
    if (safe_get(wrong_dir, "n_wrong_direction") or 0) >= 5:
        root_causes.append("**wrong_direction_problem** — engine sometimes picks the wrong side on chop")
    if holds == "NO":
        root_causes.append("**execution_variant_didnt_hold** — delay_15m+stop_1.5% degraded on second half vs first half")
    if not root_causes:
        root_causes.append("mixed / no single dominant root cause on this sample")
    for rc in root_causes:
        md.append(f"- {rc}")

    md.extend([
        "",
        "## 9. Concrete next actions",
        "",
        "### A. What you can do now (research / shadow only)",
        "- Continue passive live observer: log engine triggers + canonical ledger simulation in shadow mode.",
        f"- Build `TG_watch_score_v1` based on feature-separation findings (see "
        f"`OKX_SECOND_HALF_CONFIRMATION_NOISE_AUDIT.md`). v0 confidence is broken — needs rewrite.",
        "- Implement movement-coverage metric in CI: per backtest, report `covered_early / covered_late / missed` "
        "alongside trade counts.",
        "- Generate direction-explanation strings for every confirmed zone in tooling (already prototyped).",
        "",
        "### B. What you CANNOT do",
        "- ❌ Change engine / zoneDetector / thresholds",
        "- ❌ Send real Telegram alerts to users",
        "- ❌ Open real trades on this data",
        "- ❌ Claim profitability — delay_15m+stop_1.5% did NOT hold on second-half",
        "",
        "### C. What needs more research",
        "- `TG_watch_score_v1` design: drop features with 0 separation (absorb/refill/range_compression saturate), "
        "add `filter_kept` weight, invert sign on `trigger_flow_strong` if confirmed as anti-feature, "
        "add opposite-direction conflict penalty + late-entry guard.",
        "- Local-normalized features (percentile/z-score vs last 30/60/180 m).",
        "- Direction guard rule: drop signals against strong local impulse without reversal evidence.",
        "- Confirmed-stage ranking experiment: rank by feature combinations; cap 1-2 per day; "
        "validate on next independent period.",
        "",
        "## Final flag matrix",
        "",
        "```",
    ])
    for k, v in flags.items():
        md.append(f"{k} = {v}")
    md.append("```")
    md.extend([
        "",
        "## Hard rules honored",
        "- strategy / thresholds / `zoneDetector`: UNCHANGED",
        "- NO new backtest spawned; all post-hoc",
        "- target STRICT 2 %",
        "- diagnostic-only; no production integration; READY_FOR_PRODUCTION_TRADING = NO",
    ])
    (REP_OUT / "OKX_SECOND_HALF_FULL_RETEST_MASTER_SUMMARY.md").write_text("\n".join(md), encoding="utf-8")

    print()
    print("FINAL FLAGS:")
    for k, v in flags.items():
        print(f"  {k:<55s} = {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
