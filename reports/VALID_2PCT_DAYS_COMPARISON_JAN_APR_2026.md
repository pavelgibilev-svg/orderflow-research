# Valid 2 % Days Comparison — Jan-Apr 2026

> Honest cross-day evaluation of the strategy on **only the days where the 2 % target is structurally reachable** per the target-feasibility analyser. 2026-01-01 is excluded by design because its 24h max move is < 2 % in both directions, so any hit-rate from that day is mechanically zero and not informative about strategy quality. Strategy thresholds are unchanged. Detector and target checker are unchanged.

- Generated: 2026-05-10T10:45:21.326Z
- Days included: 2026-02-01, 2026-03-01, 2026-04-01

## 1. Headline metrics — only feasible days

| Date | Feasibility | Regime | Range | Triggered | Reached raw | **Unique moves** | Adj hit rate | Raw hit rate | LONG / SHORT moves | Days notes |
|---|---|---|---|---|---|---|---|---|---|---|
| 2026-02-01 | fully feasible (both directions) | bearish | 4.96% | 11 | 4 | **1** | **9.09%** | 36.36% | 0 / 1 |  |
| 2026-03-01 | fully feasible (both directions) | bearish | 4.89% | 24 | 8 | **1** | **4.17%** | 33.33% | 0 / 1 |  |
| 2026-04-01 | partial feasible (one direction only) | choppy | 2.60% | 18 | 0 | **0** | **0.00%** | 0.00% | 0 / 0 |  |
| **TOTAL (feasible days only)** | — | — | — | **53** | **12** | **2** | **3.77%** | 22.64% | **0 / 2** | — |

## 2. Per-day detail

### 2026-02-01 (fully feasible (both directions))

Day price action:
- Return: -2.25%, Range: 4.96%, Regime: bearish
- Max 4h up/down: 2.20% / 2.67%
- Max 8h up/down: 2.20% / 3.27%
- Max 24h up/down: 2.20% / 4.46%
- 2% feasible: 4h=yes, 8h=yes, 24h=yes

Strategy result:
- L2 events processed: 165 962 192, trades scanned: 6 759 515
- Zones found: 25 (LONG=16, SHORT=9)
- Triggered: 11
- Reached zones (raw): 4 (LONG=0, SHORT=4)
- Reached by horizon: 4h=0, 8h=0, 24h=4
- Unique reached moves: **1** (LONG=0, SHORT=1)
- Duplicate move credits collapsed: 3
- Raw triggered hit rate: 36.36%
- **Unique-move-adjusted hit rate: 9.09%**

**Conclusion:** SHORT-only success on this day. Consistent with bearish-bias hypothesis but does NOT confirm it (this day's regime is bearish, return -2.25%).

### 2026-03-01 (fully feasible (both directions))

Day price action:
- Return: -1.77%, Range: 4.89%, Regime: bearish
- Max 4h up/down: 3.17% / 2.92%
- Max 8h up/down: 3.17% / 3.28%
- Max 24h up/down: 3.17% / 4.54%
- 2% feasible: 4h=yes, 8h=yes, 24h=yes

Strategy result:
- L2 events processed: 139 795 935, trades scanned: 5 961 363
- Zones found: 46 (LONG=25, SHORT=21)
- Triggered: 24
- Reached zones (raw): 8 (LONG=0, SHORT=8)
- Reached by horizon: 4h=0, 8h=0, 24h=8
- Unique reached moves: **1** (LONG=0, SHORT=1)
- Duplicate move credits collapsed: 7
- Raw triggered hit rate: 33.33%
- **Unique-move-adjusted hit rate: 4.17%**

**Conclusion:** SHORT-only success on this day. Consistent with bearish-bias hypothesis but does NOT confirm it (this day's regime is bearish, return -1.77%).

### 2026-04-01 (partial feasible (one direction only))

Day price action:
- Return: -0.23%, Range: 2.60%, Regime: choppy
- Max 4h up/down: 2.37% / 1.62%
- Max 8h up/down: 2.42% / 1.81%
- Max 24h up/down: 2.42% / 1.83%
- 2% feasible: 4h=yes, 8h=yes, 24h=yes

Strategy result:
- L2 events processed: 124 963 429, trades scanned: 4 104 211
- Zones found: 30 (LONG=16, SHORT=14)
- Triggered: 18
- Reached zones (raw): 0 (LONG=0, SHORT=0)
- Reached by horizon: 4h=0, 8h=0, 24h=0
- Unique reached moves: **0** (LONG=0, SHORT=0)
- Duplicate move credits collapsed: 0
- Raw triggered hit rate: 0.00%
- **Unique-move-adjusted hit rate: 0.00%**

**Conclusion:** no 2% target reached, despite the day being structurally feasible. Negative signal for the strategy on this regime.

## 3. Honest verdict across feasible days

Days successfully evaluated: 3 of 3.

### Q1. Is the 2026-02-01 result confirmed on a second feasible day?

**Partially yes.** 2026-03-01 produced 1 unique reached move (LONG=0, SHORT=1). The strategy is not zero on a second feasible day — it matches or exceeds the 2026-02-01 result of 1 unique move.

### Q2. Is success regime-dependent (only bearish days)?

**Likely yes.** Across all feasible days the strategy ONLY succeeded on the SHORT side (2026-02-01, 2026-03-01). LONG never reached its 2 % target — even on days where LONG was structurally feasible. This is consistent with regime-dependent / bearish-bias behaviour, though 2-3 days is too few to be conclusive.

### Q3. How many unique 2 % moves were caught in total?

**2** unique 2 % moves across 3 feasible days (0 LONG + 2 SHORT). Aggregate triggered hit rate (raw): 22.64%. Aggregate unique-move-adjusted: 3.77%.

### Q4. Can we already speak about an edge?

**No.** Even with 2 unique moves over 3 feasible days, this is far below any sample size that supports a profitability claim:
- All 3 days are first-of-month boundaries — atypical liquidity / funding-reset behaviour.
- No out-of-sample split.
- No fees / slippage / latency model.
- The hit rate is not horizon-matched against an unconditional baseline at 24h (the per-day baseline only has enough samples at 4h / 8h).
- 2-3 days does not bound directional bias well — a single regime tilt can swamp the result.

### Q5. What to test next?

1. **Paid Tardis subscription, ≥ 1 calendar month** at full-day resolution; this is the only way to escape first-of-month sample bias.
2. Per-direction-per-day hit rate against a horizon-matched baseline (P(±2 % within 24h) computed on the same days the detector ran on).
3. A symmetric per-day target ladder (0.5 / 1.0 / 1.5 / 2.0 %) — see TARGET_FEASIBILITY_2PCT_JAN_APR_2026.md. This separates "the strategy works" from "the day moved enough".
4. Once the live recorder has a few weeks of data, replay through `backtest:db` and compare with the Tardis-CSV runs to detect any source-specific bias.
5. Do **not** retune `config/strategy.default.json` based on this 2-3 day sample.

> **This is a feasibility-aware, post-dedup, post-clustering verification.** Strategy thresholds are unchanged. Detector logic is unchanged. Failed / no_trigger / invalidated zones are preserved in every per-day report.
