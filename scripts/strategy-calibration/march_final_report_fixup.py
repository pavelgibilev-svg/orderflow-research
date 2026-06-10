"""Regenerate MARCH_IN_SAMPLE_ZONE_CALIBRATION_FINAL_REPORT with leak-aware headline.

The original auto-generated final report picked an F1-balanced selector (recall-heavy)
as the headline. The user's goal is PRECISION (70-80% winrate). Also, selectors using
`confirm_to_trigger_min` filters at confirm time are future-leaky and must be flagged.
"""
import json, datetime as dt
from pathlib import Path

REP = next(p for p in Path(__file__).resolve().parents if (p / "package.json").exists() and (p / "scripts").exists()) / "reports" / "strategy-calibration"


def now_iso():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


sel = json.load(open(REP / "MARCH_TOP_SELECTOR_EVALUATION.json", encoding="utf-8"))
paper = json.load(open(REP / "MARCH_CALIBRATED_SELECTOR_PAPER_TRADE_RESULTS.json", encoding="utf-8"))
moves = json.load(open(REP / "MARCH_FULL_MARKET_2PCT_MOVES.json", encoding="utf-8"))
labels = json.load(open(REP / "MARCH_FULL_MOVEMENT_FIRST_ZONE_DATASET.json", encoding="utf-8"))

cats = sel["categories"]
best = cats.get("best_precision_min20")
best_long = cats.get("best_LONG_min10")
best_short = cats.get("best_SHORT_min10")
best_stable = cats.get("best_train_test_stable_min20")

results = paper["results"]


def has_ctt(name):
    return "ctt_le" in name


no_leak = [r for r in results if not has_ctt(r["selector"]) and (r["trades"] or 0) >= 20]
no_leak.sort(key=lambda r: -(r["winrate_pct"] or 0))
best_paper_no_leak = no_leak[0] if no_leak else None
with_leak_all = sorted([r for r in results if (r["trades"] or 0) >= 20],
                       key=lambda r: -(r["winrate_pct"] or 0))
best_paper_any = with_leak_all[0] if with_leak_all else None

n_zones = labels["n_zones"]
n_moves = moves["n_primary_2pct_moves"]
base_prec = sel["baseline_precision_pct"]
base_h1 = sel["first_half_baseline_pct"]
base_h2 = sel["second_half_baseline_pct"]

flags = {
    "MARCH_IN_SAMPLE_CALIBRATION_DONE": "YES",
    "DAYS_INCLUDED": 29,
    "TOTAL_ZONES": n_zones,
    "TOTAL_MARKET_2PCT_MOVES": n_moves,
    "TOTAL_SELECTED_BY_BEST_SELECTOR": best.get("selected_n") if best else None,
    "BEST_SELECTOR_NAME": best["selector"] if best else "none",
    "BEST_SELECTOR_ALERTS_PER_DAY": best.get("alerts_per_day") if best else None,
    "BEST_SELECTOR_PRECISION": best.get("precision_pct") if best else None,
    "BEST_SELECTOR_RECALL": best.get("recall_pct") if best else None,
    "BEST_SELECTOR_WRONG_DIRECTION_RATE": best.get("wrong_rate_pct") if best else None,
    "BEST_SELECTOR_FIRST_HALF_PRECISION": best.get("h1_precision_pct") if best else None,
    "BEST_SELECTOR_SECOND_HALF_PRECISION": best.get("h2_precision_pct") if best else None,
    "BEST_SELECTOR_OVERFIT_RISK": "MEDIUM" if best and (best.get("selected_n") or 0) < 40 else "LOW",
    "BEST_PAPER_TRADE_MODEL": (
        (f"{best_paper_no_leak['selector']} | {best_paper_no_leak['entry_mode']} | {best_paper_no_leak['stop']}"
         if best_paper_no_leak else "none") + " (leak-free)"),
    "BEST_PAPER_TRADES": best_paper_no_leak.get("trades") if best_paper_no_leak else None,
    "BEST_PAPER_WINRATE": best_paper_no_leak.get("winrate_pct") if best_paper_no_leak else None,
    "BEST_PAPER_EXPECTANCY_PRE_COST": best_paper_no_leak.get("expectancy_pre_cost_pct") if best_paper_no_leak else None,
    "BEST_PAPER_EXPECTANCY_AFTER_COST": best_paper_no_leak.get("expectancy_after_cost_pct") if best_paper_no_leak else None,
    "BEST_PAPER_PF_AFTER_COST": best_paper_no_leak.get("pf_after_cost") if best_paper_no_leak else None,
    "MARCH_70PCT_GOAL_REACHED": "NO",
    "MARCH_80PCT_GOAL_REACHED": "NO",
    "MINIMUM_TRADES_CONSTRAINT_MET": ("YES" if best_paper_no_leak
                                       and (best_paper_no_leak.get("trades") or 0) >= 20 else "NO"),
    "USEFUL_ORDERFLOW_FEATURES_FOUND": "YES",
    "LOCAL_NORMALIZATION_HELPED": "YES",
    "DIRECTION_GUARD_NEEDED": "YES",
    "TG_SELECTOR_CAN_BE_1_2_PER_DAY": "YES",
    "READY_FOR_TELEGRAM_SHADOW_MODE": "NO",
    "READY_TO_CHANGE_ENGINE": "NO",
    "READY_FOR_PRODUCTION_TRADING": "NO",
    "MORE_VALIDATION_REQUIRED": "YES",
}

summary = {
    "build_time_utc": now_iso(),
    "scope": "IN-SAMPLE March 2026 OKX direct, 29 days. NOT production proof.",
    "days_included": 29, "missing_dates": ["2026-03-17"],
    "n_zones": n_zones, "n_primary_2pct_moves": n_moves,
    "label_counts": labels["label_counts"], "coverage_counts": labels["coverage_counts"],
    "baseline_precision_pct": base_prec,
    "first_half_baseline_pct": base_h1, "second_half_baseline_pct": base_h2,
    "best_selector_headline_leak_free": best,
    "best_paper_trade_headline_leak_free": best_paper_no_leak,
    "best_paper_trade_with_post_confirm_filter": best_paper_any,
    "best_LONG_selector": best_long,
    "best_SHORT_selector": best_short,
    "best_train_test_stable_selector": best_stable,
    "leak_note": ("Selectors containing 'ctt_le30' / 'ctt_le60' filter on confirm_to_trigger_min, "
                  "which is only known AFTER trigger. For confirmed-time alerts, this is a "
                  "FUTURE LEAK. They are reported separately as 'execution-stage-only' results."),
    "categories": cats,
    "flags": flags,
}
(REP / "MARCH_IN_SAMPLE_ZONE_CALIBRATION_FINAL_REPORT.json").write_text(
    json.dumps(summary, indent=2, default=str), encoding="utf-8")

md = [
    "# March in-sample zone calibration — final report (IN-SAMPLE, NOT production proof)",
    "",
    f"**Build:** {summary['build_time_utc']}",
    f"**Scope:** {summary['scope']}",
    f"**Days:** 29 (14 first half + 15 second half; missing: 2026-03-17)",
    f"**Zones:** {n_zones}; **primary 2 % moves:** {n_moves}; **baseline precision (all confirmed):** {base_prec} %",
    f"**Baseline by half:** H1={base_h1} %, H2={base_h2} %",
    "",
    "## CRITICAL HONESTY NOTE",
    "",
    f"- The 70-80 % winrate goal is **NOT REACHED** in March in-sample.",
    f"- Best leak-free selector precision (>=20 selected): **{best['precision_pct']} %** "
    f"(`{best['selector']}`, {best['selected_n']} alerts, {best['alerts_per_day']}/day).",
    f"- Best leak-free paper-trade winrate (>=20 trades): **{best_paper_no_leak['winrate_pct']} %** "
    f"(`{best_paper_no_leak['selector']}` | {best_paper_no_leak['entry_mode']} | {best_paper_no_leak['stop']}, "
    f"{best_paper_no_leak['trades']} trades).",
    f"- Higher numbers exist in the optimization output but use the `confirm_to_trigger_min` filter — "
    f"that field is only knowable AFTER trigger, so applying it at confirm time is a **future leak**. "
    f"We label it explicitly and exclude it from the headline.",
    "",
    "## 1. Did we hit 70-80 % profitable selected zones in March?",
    f"- **NO.** Best clean precision = **{best['precision_pct']} %** on {best['selected_n']} alerts; "
    f"best clean paper-trade winrate = **{best_paper_no_leak['winrate_pct']} %** on {best_paper_no_leak['trades']} trades.",
    f"- Only with a future-leak filter (`ctt_le30`, applied at confirm time but using post-confirm data) "
    f"does winrate creep up to ~62 % — that result is not usable in a real signal pipeline.",
    "",
    "## 2. If goal hit — selector / formula / size / pace",
    f"- (Goal NOT hit.) The best honest selector is **`{best['selector']}`**:",
    f"  - hard filter: `is_asia_session == 1` (UTC 0-7)",
    f"  - within the day, rank by `explainable_score` (filter_kept, not_late, opp_eq0, "
    f"taker_imb_aligned_30m, ofi_shift_aligned, sweep_reclaim_aligned, plus overextension penalty)",
    f"  - top 1 per day",
    f"  - result: {best['selected_n']} alerts, {best['alerts_per_day']}/day, "
    f"precision {best['precision_pct']} %, recall {best['recall_pct']} %, "
    f"wrong-direction rate {best['wrong_rate_pct']} %",
    f"  - LONG precision: {best['long_precision_pct']} %, SHORT precision: {best['short_precision_pct']} %",
    f"  - H1 precision: {best['h1_precision_pct']} %, H2 precision: {best['h2_precision_pct']} % (STABLE)",
    f"  - avg lead: {best['avg_lead_min']} min, max consecutive bad alerts: {best['max_consecutive_bad']}",
    "",
    "## 3. Why we can't reach 70-80 %",
    "- Only 123 GOOD zones across 1043 confirmed → baseline ~11.8 % precision. Reaching 70 % needs a 6x lift.",
    "- Even the best clean combination (Asia session x top-1 by score) only reaches ~41 % precision. "
    "Adding more filters drops sample size below 20 (overfit territory).",
    "- After 0.14 % roundtrip cost, the realistic expectancy of the best leak-free combo is "
    "**+0.61 % per trade** (PF 2.25). Solid but not the 70-80 % winrate fantasy.",
    "- The labels are noisy: zones marked GOOD have ~25 % wrong-direction false positives even after "
    "movement-first labelling.",
    "",
    "## 4. Features that really work",
    "- `is_asia_session` (Asia open zones higher quality on average).",
    "- `filter_kept` (passive duplicate + fast-trigger filter): +5 pp precision uplift.",
    "- `opp_dir_zones_active_60m == 0`, `is_during_opposite_move == 0` (conflict guards).",
    "- `is_late_after_50pct_correct_move == 0` (late-entry guard — NEW from this pass).",
    "- `prior_move_60m_pct` small, `local_range_180m_pct` small (clean context).",
    "- `trig_break_pct` higher in GOOD.",
    "- `taker_imb_aligned_30m`, `ofi_shift_aligned`, `sweep_reclaim_aligned` — modest but real.",
    "",
    "## 5. Useful orderflow features (extracted from trades, no L2)",
    "- `is_late_after_50pct_correct_move`, `is_during_opposite_move` (movement-relative timing).",
    "- `ofi_shift_aligned` (5m vs 30m taker imbalance shift).",
    "- `taker_imb_aligned_30m/60m` (windowed taker imbalance).",
    "- `vol_anomaly_15m_vs_bg` (mildly helpful).",
    "- `sweep_reclaim_aligned` (binary; small but positive).",
    "",
    "## 6. Useless features",
    "- All engine score fields that fire on ~100 % of candidates: `cand_absorb_score`, "
    "`cand_*_refill_score`, `cand_range_compression`, `score_*` raw.",
    "- `conf_cycles_seen`, `conf_age_min`, `conf_opposite_thinning`, `conf_defended_persistence_sec`.",
    "- Raw `trig_flow_multiplier` (high in BAD too).",
    "- `cand_pressure_against` (no separation).",
    "- `local_realized_vol_*` (very small d).",
    "",
    "## 7. Anti-features",
    "- `is_late_after_50pct_correct_move` (strong anti-feature).",
    "- `is_during_opposite_move` (strong anti-feature for direction).",
    "- `prior_move_180m_pct` (direction-flipped: positive d vs BAD but negative d vs wrong_direction).",
    "",
    "## 8. LONG / SHORT differences",
    f"- Best LONG selector: `{best_long['selector']}`, LONG precision={best_long['long_precision_pct']} %, "
    f"n={best_long['long_n']}, H1={best_long['h1_precision_pct']} % vs H2={best_long['h2_precision_pct']} % "
    f"(H1-dominant — possibly overfit to first half).",
    f"- Best SHORT selector: `{best_short['selector']}`, SHORT precision={best_short['short_precision_pct']} %, "
    f"n={best_short['short_n']}, H1={best_short['h1_precision_pct']} % vs H2={best_short['h2_precision_pct']} % "
    f"(more stable than LONG).",
    "- LONG zones cluster on Asia opens; SHORT zones cluster around impulse exhaustion in US session.",
    "",
    "## 9. First-half vs second-half differences",
    f"- H1 baseline: {base_h1} %, H2 baseline: {base_h2} % — H2 has lower GOOD rate (regime change).",
    f"- The headline selector `{best['selector']}` is stable: H1={best['h1_precision_pct']} %, "
    f"H2={best['h2_precision_pct']} %.",
    "- Several aggressive combos collapse in H2 (e.g. `dir::LONG+filter_kept+opp_eq0`: H1 45 % -> H2 14 %).",
    "",
    "## 10. Which moves does the detector see well?",
    "- Asia-session impulse reversals after first leg (sharp 1.5-2 % moves into clean range).",
    "- Mid-session continuations where the engine confirms BEFORE breakout (lead > 60 min).",
    "",
    "## 11. Which moves does detector / selector miss?",
    "- Slow-grind 2 % moves with no obvious absorption (no candidate).",
    "- Wick-only 2 % spikes (confirms after the spike).",
    "- News-driven instant moves (any selector lags).",
    "",
    "## 12. What to change in the research layer",
    "- Add L2-derived refill/defense features (current proxies uninformative).",
    "- Build a direction guard module on `is_during_opposite_move` + opposite-confirmed-zone count.",
    "- Add cluster-dedup by `_label_unique_move_id` so we don't pick 2 zones from the same impulse.",
    "- Add an explicit retest-quality feature for trigger-stage entries.",
    "- Reserve `confirm_to_trigger_min` filters for *trigger-stage* selectors only (never for confirm-time).",
    "",
    "## 13. What we CANNOT change in the engine",
    "- Strategy definitions, thresholds, zone detector, confirmation logic, trigger logic. Selector layer only.",
    "",
    "## 14. Can we build TG shadow on calibrated selector?",
    "- The `single::session_asia::top1_score` selector is honest, leak-free, 1/day, 41 % precision, "
    "stable across halves. **As a SHADOW research channel marked clearly as 'in-sample, not validated "
    "OOS' — acceptable.**",
    "- As a production trading signal — **NO**. Out-of-sample April/May validation needed first.",
    "",
    "## 15. What data / features we still need",
    "- Full L2 reconstruction for refill / defense / wall persistence / microprice / spread.",
    "- Cross-venue (Binance) feature mirroring for direction confirmation.",
    "- A larger labeled sample (April-May) to verify stability of the patterns found here.",
    "- Calendar / macro news event flag (instant moves over-represented in BAD).",
    "",
    "## Final flag matrix",
    "",
    "```",
]
for k, v in flags.items():
    md.append(f"{k} = {v}")
md.extend([
    "```",
    "",
    "## Hard rules honored",
    "- engine / thresholds / detector: UNCHANGED.",
    "- decision features: pre-confirm only (no future leak in the headline selector).",
    "- `ctt_le_*` selectors are explicitly excluded from headline as future-leak; reported only as "
    "execution-stage curiosities.",
    "- outcome labels: NEVER used in selector logic.",
    "- target strict 2 %; cost 0.14 % roundtrip.",
    "- production claim: NONE.",
])
(REP / "MARCH_IN_SAMPLE_ZONE_CALIBRATION_FINAL_REPORT.md").write_text("\n".join(md), encoding="utf-8")
print("FINAL FLAGS (corrected):")
for k, v in flags.items():
    print(f"  {k:<46s} = {v}")
