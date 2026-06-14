# OKX direct second-half March 2026 - FULL retest MASTER SUMMARY

**Build:** 2026-05-25T09:40:34+00:00
**Scope:** OKX direct second-half March 2026 full retest master summary
**No engine / threshold / detector change. Read-only post-hoc audit. Target strict 2 %.**

## 1. Data status

- Days processed: **15/15**
- Missing: ['2026-03-17 (no source data)']
- Backtest failures: 0
- All 15 ready-day reports present in `reports/okx-direct/OKX_DIRECT_TECHNICAL_REPLAY_2026-03-{16,18..31}.{md,json,_ZONES.csv}`

## 2. Engine-level result

| metric | total | per day |
|---|---:|---:|
| zones | 543 | 36.2 |
| triggered | 330 | 22.0 |
| reached_raw | 89 | 5.93 |
| primary unique | **15** | 1.0 |
| duplicate credits | 74 | — |
| failed triggered | 241 | — |
| LONG / SHORT (all classes) | 264 / 279 | — |
| mute days (0 reached) | 3 | — |

## 3. Execution result (canonical strict ledger)

| variant | trades | W/L/T | winrate | exp pre-cost | PF pre-cost | exp after cost | PF after cost | total return after cost |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| A trigger_entry+stop_1pct | 43 | 9/25/9 | 20.93 | **-0.1341** | **0.777** | -0.2741 | 0.607 | -11.7868 |
| B delay_15m+stop_1.5pct | 33 | 8/12/13 | 24.24 | **-0.0845** | **0.867** | -0.2245 | 0.689 | -7.4087 |

**`DELAY15_STOP15_HOLDS_ON_SECOND_HALF` = NO**

## 4. Detection-quality result

- Market 2 % moves (ZigZag detector): **20** primary
- Engine coverage:
  - covered_watch_early: 7
  - covered_trigger_early: 3
  - covered_mid: 0
  - covered_late: 2
  - filtered_correct_zone (correct zone existed but base filter killed it): 7
  - missed_move (no engine zone at all): 1
- Correct zones suppressed by base filter: **61**
- Slow-trigger correct zones (confirm→trigger > 60 m, direction matches market move): **44**
  - of those, could have alerted at confirmed stage: 44
- Wrong-direction triggered zones (no 2 % in engine direction within 4 h): **8**

## 5. Confirmation logic result

- Confirmed zones per day: **35.8**
- Coverage distribution among confirmed:
  - missed_no_move_in_4h: **409** (76.2%)
  - covered_2pct_move: **60** (11.2%)
  - wrong_direction: **41** (7.6%)
  - noisy_partial_1_5pct: **27** (5.0%)

- HIGH confidence count: **533** of 537 confirmed (= 99.3%)
- `CONFIRMED_HIGH_FILTER_USEFUL` = **NO** (if HIGH catches > 90 % of confirmed, the bar is too permissive)
- `CONFIRM_STAGE_USEFUL_FOR_TG_WATCH` = **UNKNOWN**

## 6. TG-watch result

| mode | alerts/day | covered | wrong | missed | avg lead min |
|---|---:|---:|---:|---:|---:|
| `confirmed_only` | 35.8 | 60 | 83 | 394 | 109.15 |
| `candidate_MID+` | 35.8 | 60 | 83 | 394 | 109.15 |
| `confirmed_MID+` | 35.8 | 60 | 83 | 394 | 109.15 |
| `confirmed_HIGH_only` | 34.333 | 55 | 79 | 381 | 107.53 |
| `max1_per_direction_per_day` | 2.0 | 7 | 5 | 18 | 127.51 |
| `max2_total_per_day` | 2.0 | 10 | 2 | 18 | 126.24 |

## 7. Top selected max2_total_per_day zones

| date | rank | direction | confirmedTs | confidence | rank_score | coverage | lead min |
|---|---:|---|---|---|---:|---|---:|
| 2026-03-16 | 1 | LONG | 2026-03-16T00:37:27+00:00 | HIGH | 9.4 | **covered_2pct_move** | 176.55 |
| 2026-03-16 | 2 | LONG | 2026-03-16T00:37:27+00:00 | HIGH | 9.4 | **covered_2pct_move** | 176.55 |
| 2026-03-18 | 1 | SHORT | 2026-03-18T00:13:01+00:00 | HIGH | 8.5 | **missed_no_move_in_4h** | None |
| 2026-03-18 | 2 | SHORT | 2026-03-18T00:54:55+00:00 | HIGH | 8.5 | **missed_no_move_in_4h** | None |
| 2026-03-19 | 1 | LONG | 2026-03-19T09:18:04+00:00 | HIGH | 9.5 | **noisy_partial_1_5pct** | None |
| 2026-03-19 | 2 | LONG | 2026-03-19T13:40:10+00:00 | HIGH | 9.5 | **missed_no_move_in_4h** | None |
| 2026-03-20 | 1 | SHORT | 2026-03-20T00:21:21+00:00 | HIGH | 8.5 | **missed_no_move_in_4h** | None |
| 2026-03-20 | 2 | SHORT | 2026-03-20T00:44:27+00:00 | HIGH | 8.5 | **missed_no_move_in_4h** | None |
| 2026-03-21 | 1 | SHORT | 2026-03-21T00:59:58+00:00 | HIGH | 8.5 | **missed_no_move_in_4h** | None |
| 2026-03-21 | 2 | SHORT | 2026-03-21T07:42:37+00:00 | HIGH | 8.5 | **missed_no_move_in_4h** | None |
| 2026-03-22 | 1 | SHORT | 2026-03-22T01:32:41+00:00 | HIGH | 9.5 | **wrong_direction** | None |
| 2026-03-22 | 2 | SHORT | 2026-03-22T03:39:26+00:00 | HIGH | 9.5 | **missed_no_move_in_4h** | None |
| 2026-03-23 | 1 | SHORT | 2026-03-23T00:14:57+00:00 | HIGH | 8.5 | **missed_no_move_in_4h** | None |
| 2026-03-23 | 2 | LONG | 2026-03-23T00:22:01+00:00 | HIGH | 8.5 | **missed_no_move_in_4h** | None |
| 2026-03-24 | 1 | SHORT | 2026-03-24T06:07:43+00:00 | HIGH | 8.5 | **covered_2pct_move** | 111.33 |
| 2026-03-24 | 2 | SHORT | 2026-03-24T14:36:16+00:00 | HIGH | 8.5 | **missed_no_move_in_4h** | None |
| 2026-03-25 | 1 | LONG | 2026-03-25T00:13:04+00:00 | HIGH | 8.5 | **missed_no_move_in_4h** | None |
| 2026-03-25 | 2 | SHORT | 2026-03-25T01:00:27+00:00 | HIGH | 8.5 | **missed_no_move_in_4h** | None |
| 2026-03-26 | 1 | LONG | 2026-03-26T00:14:56+00:00 | HIGH | 8.5 | **missed_no_move_in_4h** | None |
| 2026-03-26 | 2 | LONG | 2026-03-26T00:24:34+00:00 | HIGH | 8.5 | **missed_no_move_in_4h** | None |
| 2026-03-27 | 1 | LONG | 2026-03-27T18:33:55+00:00 | HIGH | 9.4 | **missed_no_move_in_4h** | None |
| 2026-03-27 | 2 | SHORT | 2026-03-27T14:38:37+00:00 | HIGH | 9.2 | **missed_no_move_in_4h** | None |
| 2026-03-28 | 1 | SHORT | 2026-03-28T00:40:41+00:00 | HIGH | 8.5 | **missed_no_move_in_4h** | None |
| 2026-03-28 | 2 | LONG | 2026-03-28T01:06:01+00:00 | HIGH | 8.5 | **missed_no_move_in_4h** | None |
| 2026-03-29 | 1 | LONG | 2026-03-29T00:46:44+00:00 | HIGH | 9.5 | **wrong_direction** | None |
| 2026-03-29 | 2 | LONG | 2026-03-29T10:52:43+00:00 | HIGH | 9.5 | **missed_no_move_in_4h** | None |
| 2026-03-30 | 1 | LONG | 2026-03-30T02:25:03+00:00 | HIGH | 9.5 | **missed_no_move_in_4h** | None |
| 2026-03-30 | 2 | LONG | 2026-03-30T00:10:48+00:00 | HIGH | 8.5 | **covered_2pct_move** | 9.3 |
| 2026-03-31 | 1 | LONG | 2026-03-31T00:05:34+00:00 | HIGH | 8.5 | **covered_2pct_move** | 80.02 |
| 2026-03-31 | 2 | LONG | 2026-03-31T00:44:02+00:00 | HIGH | 8.5 | **covered_2pct_move** | 41.55 |

- max2 totals: **30** alerts (2.0/day) over 15 days
- covered_2pct_move: **6** (20.0%)
- noisy_partial_1.5%: 1
- wrong_direction: 2
- missed_no_move_in_4h: 21
- avg lead min before move: 99.2
- max2 missed market 2 % moves: **16 / 20**

## 7b. Pattern search (good-watch patterns)

| pattern | per day | precision % | recall % | covered | wrong |
|---|---:|---:|---:|---:|---:|
| `baseline_all_confirmed` | 35.8 | 11.17 | 100.0 | 60 | 41 |
| `confidence_HIGH` | 35.533 | 11.26 | 100.0 | 60 | 40 |
| `absorb+refill` | 35.8 | 11.17 | 100.0 | 60 | 41 |
| `OFI_aligned` | 20.933 | 12.1 | 63.33 | 38 | 21 |
| `trigger_flow_strong` | 11.667 | 11.43 | 33.33 | 20 | 25 |
| `zone_defended_long` | 15.2 | 9.21 | 35.0 | 21 | 24 |
| `cycles_seen_ge_5` | 33.8 | 11.64 | 98.33 | 59 | 38 |
| `filter_kept_only` | 8.067 | 13.22 | 26.67 | 16 | 14 |

**Best pattern:** none meets criteria (alerts/day ≤ 3.5 AND precision > 0 AND recall > 0)

## 8. Root cause

- **trigger_too_slow** — many correct-direction zones have confirm→trigger > 60 m
- **filter_suppressed_correct_zones** — base filter kills correct-direction zones (10+)
- **confirmation_too_noisy** — ~50 confirmed/day, only ~13 % cover a 2 % move within 4 h
- **confidence_broken** — HIGH catches ~all confirmed; current evidence features lack discrimination
- **wrong_direction_problem** — engine sometimes picks the wrong side on chop
- **execution_variant_didnt_hold** — delay_15m+stop_1.5% degraded on second half vs first half

## 9. Concrete next actions

### A. What you can do now (research / shadow only)
- Continue passive live observer: log engine triggers + canonical ledger simulation in shadow mode.
- Build `TG_watch_score_v1` based on feature-separation findings (see `OKX_SECOND_HALF_CONFIRMATION_NOISE_AUDIT.md`). v0 confidence is broken — needs rewrite.
- Implement movement-coverage metric in CI: per backtest, report `covered_early / covered_late / missed` alongside trade counts.
- Generate direction-explanation strings for every confirmed zone in tooling (already prototyped).

### B. What you CANNOT do
- ❌ Change engine / zoneDetector / thresholds
- ❌ Send real Telegram alerts to users
- ❌ Open real trades on this data
- ❌ Claim profitability — delay_15m+stop_1.5% did NOT hold on second-half

### C. What needs more research
- `TG_watch_score_v1` design: drop features with 0 separation (absorb/refill/range_compression saturate), add `filter_kept` weight, invert sign on `trigger_flow_strong` if confirmed as anti-feature, add opposite-direction conflict penalty + late-entry guard.
- Local-normalized features (percentile/z-score vs last 30/60/180 m).
- Direction guard rule: drop signals against strong local impulse without reversal evidence.
- Confirmed-stage ranking experiment: rank by feature combinations; cap 1-2 per day; validate on next independent period.

## Final flag matrix

```
OKX_SECOND_HALF_FULL_REPORT_DONE = YES
DAYS_PROCESSED = 15
MISSING_DAYS = ['2026-03-17 (no source data)']
BACKTEST_FAILURES = 0
ENGINE_ZONES_TOTAL = 543
ENGINE_TRIGGERED_TOTAL = 330
ENGINE_PRIMARY_UNIQUE_TOTAL = 15
ENGINE_FAILED_TRIGGERED_TOTAL = 241
MARKET_2PCT_MOVES_TOTAL = 20
ENGINE_COVERED_WATCH_EARLY = 7
ENGINE_COVERED_TRIGGER_EARLY = 3
ENGINE_COVERED_MID = 0
ENGINE_COVERED_LATE = 2
ENGINE_MISSED_MOVES = 8
TRIGGER_ENTRY_STOP1_TRADES = 43
TRIGGER_ENTRY_STOP1_EXPECTANCY_PRE_COST = -0.1341
TRIGGER_ENTRY_STOP1_PF_PRE_COST = 0.777
TRIGGER_ENTRY_STOP1_EXPECTANCY_AFTER_COST = -0.2741
DELAY15_STOP15_TRADES = 33
DELAY15_STOP15_EXPECTANCY_PRE_COST = -0.0845
DELAY15_STOP15_PF_PRE_COST = 0.867
DELAY15_STOP15_EXPECTANCY_AFTER_COST = -0.2245
DELAY15_STOP15_HOLDS_ON_SECOND_HALF = NO
CONFIRMED_ZONES_PER_DAY = 35.8
CONFIRMED_HIGH_FILTER_USEFUL = NO
CONFIRM_STAGE_USEFUL_FOR_TG_WATCH = UNKNOWN
MAX2_ALERTS_PER_DAY = 2.0
MAX2_COVERED_2PCT_MOVES = 6
MAX2_MISSED_MOVES = 21
MAX2_WRONG_OR_NOISY_ALERTS = 3
MAX2_AVG_LEAD_MIN = 99.2
GOOD_WATCH_ZONE_PATTERN_FOUND = NO
TG_WATCH_CONFIDENCE_SCORE_V1_NEEDED = YES
READY_TO_BUILD_TG_WATCH_SELECTOR = NO
READY_FOR_TELEGRAM_SHADOW_MODE = NO
READY_FOR_PASSIVE_LIVE_OBSERVER = NO
READY_TO_CHANGE_ENGINE = NO
READY_FOR_PRODUCTION_TRADING = NO
MORE_VALIDATION_REQUIRED = YES
```

## Hard rules honored
- strategy / thresholds / `zoneDetector`: UNCHANGED
- NO new backtest spawned; all post-hoc
- target STRICT 2 %
- diagnostic-only; no production integration; READY_FOR_PRODUCTION_TRADING = NO