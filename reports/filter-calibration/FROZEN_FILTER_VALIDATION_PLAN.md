# FROZEN FILTER VALIDATION PLAN

Build 2026-06-10T18:12:27+00:00 · RESEARCH ONLY — no production, no Telegram.

## Protocol
1. **March 2026 = calibration only.** Thresholds frozen in FROZEN_FILTER_SET_MARCH_V1.json. Do NOT change after seeing OOS.
2. **May 2026 existing artifacts = sanity-check, not proof** (overlaps the mining month; treat as in-sample-ish).
3. **Non-March windows = true OOS** (download per OOS_WINDOWS_TO_DOWNLOAD_BY_REGIME).
4. Apply each frozen filter **as-is**; one trade per unique move cluster; TP=2%; 2.5/3% labels only; decisions <= confirmedTs.
5. Per regime report: signals, hit2 rate, W/L/TO, PF, expectancy, coverage (active days), date stability, survive/die.
6. **If a filter fails OOS -> mark DEAD, do not tune it.**
7. **If a filter survives OOS -> mark SHADOW_CANDIDATE (not production).**

## Survive / die thresholds (declare before running OOS)
- SURVIVE: winrate within ~10 pts of March AND PF>=1.0 AND n>=8 AND date_stability>=0.5 across >=2 OOS windows.
- DEAD: winrate drops >15 pts OR PF<0.9 OR n<4 OR signals concentrate on a single day.
- INCONCLUSIVE: n in [4,8) -> keep frozen, gather more OOS, no verdict.

## Order of validation
1. **F1_TD_SHORT** first — only filter with a prior robust signal; validate on TREND_DOWN OOS months.
2. **F2_SWEEP_REVERSAL** + **F5_SIXBLOCK_4of6** on HIGH_VOL / mixed OOS.
3. **F3_ACCUMULATION / F4_DISTRIBUTION** on RANGE OOS month.

## What to ignore
- Any March winrate >70% at n<6 — overfit, not evidence.
- L2-dependent sub-features absent on March (book_entropy, thin-path, top-depth) until a full-schema cache is rebuilt.
- Single-day spikes; only cross-date stable behaviour counts.