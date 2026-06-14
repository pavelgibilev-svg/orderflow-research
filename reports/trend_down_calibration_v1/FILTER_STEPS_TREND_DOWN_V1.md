# FILTER STEPS — TREND_DOWN V1 (candidate library, calibration)

Build 2026-06-11T16:16:37+00:00 · NOT a production rule. TP=2%, SL=1.5% unchanged.

## 1. Level 1 = TREND_DOWN
Confirm window net <= -1% (or PARTIAL <= +0.5%) on Bybit mid; prior 60m/180m move down.

## 2. Capital state
Classify each unique cluster into one of: ACTIVE_MARKDOWN / DISTRIBUTION_INTO_BOUNCE / FORCED_UNWIND /
ABSORPTION_AFTER_SELL_PRESSURE / NO_CONTROL_CHOP / UNKNOWN using prior move, bounce size, depth_imbalance, activity.

## 3. Evidence blocks (0-3 each, N/A if feature absent)
effort_vs_result (PROXY), absorption_refill (PROXY), initiative_control (PROXY), background_alignment, not_overextended, liquidity_execution.

## 4. Required conditions (per template)
- TD_ACTIVE_MARKDOWN_SHORT_CANDIDATE: ['background_alignment>=2', 'effort_vs_result>=1', 'initiative_control>=1']
- TD_DISTRIBUTION_INTO_BOUNCE_SHORT_CANDIDATE: ['bounce>=0.4%', 'ask-heavy depth', 'not_overextended>=1']
- TD_FORCED_UNWIND_CONTINUATION_CANDIDATE: ['acceleration pm60<=-1.5', 'activity spike', 'liquidity_execution>=1']
- TD_ABSORPTION_AFTER_SELL_PRESSURE_NO_SHORT_OR_REVERSAL_WATCH: ['bid-heavy depth_imb>0.15', 'near recent low', 'prior markdown']
- TD_NO_CONTROL_CHOP_NO_TRADE: ['depth_imb ~0', 'flow flips']

## 5. Veto conditions
- TD_ACTIVE_MARKDOWN_SHORT_CANDIDATE: ['bid-heavy depth_imb>0.15 (absorption)', 'spread>8bps']
- TD_DISTRIBUTION_INTO_BOUNCE_SHORT_CANDIDATE: ['bid refill (depth_imb>0.15)', 'low liquidity']
- TD_FORCED_UNWIND_CONTINUATION_CANDIDATE: ['already at recent low (dist_low<0.5)', 'spread blown out']
- TD_ABSORPTION_AFTER_SELL_PRESSURE_NO_SHORT_OR_REVERSAL_WATCH: ['fresh down acceleration', 'depth_imb flips negative']
- TD_NO_CONTROL_CHOP_NO_TRADE: ['—']

## 6. When entry is forbidden
- NO_CONTROL_CHOP -> no trade.
- ABSORPTION_AFTER_SELL_PRESSURE -> no fresh short (reversal watch only).
- low liquidity / blown spread -> no trade.

## 7. What counts as promising
PF>=1.2 AND winrate>=45% AND clusters>=4 across >=2 windows.

## 8. What NOT to use yet
- Any template with <4 clusters (NEED_MORE_DATA).
- Trade-flow confirmations (taker imbalance/CVD) until in-window trades exist.
- Anything tuned to a single window/day.