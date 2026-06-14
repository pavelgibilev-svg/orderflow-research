# CALIBRATION WINDOW PLAN

**Status:** IN-SAMPLE RESEARCH — not a production plan. Built on the OKX 2026-05-03..20 deep audit
(8 unique strong moves, all RANGE-regime; no positive feature with AUC > ~0.67; no Tier-A at n>=6)
plus the data-driven NEXT_WINDOWS scanner. TP stays 2%; 2.5/3% are quality labels; Tardis not used.

## Why a new plan is needed
The 18-day pool is structurally biased: **16/18 days are RANGE** (median daily range ~1.2–2.8%).
Only 8 independent strong moves exist, and the microstructure features do not separate them from
look-alike noise (cross-cluster separation problem, not engine/TP/SL). Any rule that hits 70% here is
n<=4 curve-fit. Feature discovery therefore requires **regime diversity**, not more RANGE days.

## Minimum sample targets (per regime, before trusting any selector)
- **>= 15–20 unique strong moves per regime** (RANGE, TREND_UP, TREND_DOWN, HIGH_VOL).
  Rationale: 8 was not enough to separate; need ~2–3x for any signed-feature test to be stable across dates.
- **>= 5 contiguous days per window** so 3d/7d context and cluster cooldown behave like live.
- **>= 2 independent windows per regime** (different months) to test sign-stability across time, not one event.

## Window roles (assign every downloaded window to exactly one role)
1. **FEATURE DISCOVERY (train)** — mixed-regime pool used to *propose* positive features / rules.
   Target composition: 2 RANGE + 2 TREND (up/down) + 1 HIGH_VOL window. Never report winrate from here as evidence.
2. **VALIDATION (in-sample-but-held-out during search)** — a second, disjoint window per regime.
   A proposed feature/rule must keep its sign and >= comparable AUC here, or it is discarded.
3. **HOLDOUT (true OOS, opened once)** — the most recent window(s), frozen until the rule set is final.
   Open exactly once; if it fails, do not re-tune on it — go back to discovery on *other* windows.

## OKX+Binance overlap requirement
- Cross-venue claims (parity, venue-robust selectors) require **simultaneous OKX L2+trades and Binance
  recorder L2** for the same UTC days. The only overlap captured locally is **2026-05-21..30** (10 days).
- For new cross-venue windows: capture both venues for **>= 5 contiguous days** each. If only one venue is
  available, mark the window single-venue (usable for feature discovery, not for venue-robustness claims).

## Anti-overfit rules (carry forward from this audit)
- Work on **unique_move_cluster_id**, never raw duplicate zones (76% of strong zones here were duplicates).
- Decisions causal (<= confirmedTs); future labels (2/2.5/3%) only as outcome labels.
- Every candidate rule must report: leave-one-day-out, leave-one-cluster-out, and without-top-2-vol-days.
- A rule survives only if winrate holds within ~10 pts after removing the single best day AND best cluster.
- Max 3–5 live-valid features per rule; no same-day-only rules; no engine/TP/SL changes.

## Concrete next-download order (regimes missing or thin here)
Priority is set by the scanner's regime gaps; see NEXT_WINDOWS_TO_DOWNLOAD.{md,json,csv} for the exact dated
windows it selected from daily data. General order:
1. **TREND_DOWN** windows — validate the TD-short module OOS (its only robust edge so far).
2. **TREND_UP** windows — re-test TU-long, which failed on the thin May trend slice.
3. **HIGH_VOL** windows — densest source of 2%+ strong moves; best chance to get 15–20 unique strong moves fast.
4. **REVERSAL_SWEEP / BREAKOUT** windows — populate the LIQUIDITY_SWEEP / FALSE_BREAKOUT families that
   scored best causally but had n=1–2 here.
5. One **LOW_VOL** window as a negative/no-trade control.

## Definition of done for calibration
- >= 4 regimes each with >= 15 unique strong moves across >= 2 windows.
- At least one positive feature with AUC >= 0.70 that keeps its sign across train + validation.
- A rule that holds >= 60% winrate at n>=10 on validation AND survives the single holdout open.
Until then: keep the engine frozen, run shadow loggers only, make **no production claim**.
