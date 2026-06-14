# TREND_DOWN DECISION TREE V2

Build 2026-06-12T12:57:48+00:00 · RESEARCH/CALIBRATION (not production).

Research decision flow (NOT production). TP=2%/SL=1.5%.

```
IF Level1 != TREND_DOWN: do not use TREND_DOWN templates.
IF Level1 == TREND_DOWN:
  determine capital_state (direction-aware) from price + L2 + REAL trades (CVD/taker):

  ACTIVE_MARKDOWN + SHORT:        TD_ACTIVE_MARKDOWN_SHORT_TEMPLATE  [NEED_MORE_DATA]
  DISTRIBUTION_INTO_BOUNCE + SHORT: TD_DISTRIBUTION_INTO_BOUNCE_SHORT  [REJECT]
  FORCED_UNWIND + SHORT:          TD_FORCED_UNWIND_CONTINUATION       [NEED_MORE_DATA]
  ABSORPTION_AFTER_SELL_PRESSURE: NO short; reversal-watch / no-trade  [NEED_MORE_DATA]
  NO_CONTROL_CHOP:                NO TRADE                            [KEEP_AS_VETO]
  UNKNOWN:                        NO TRADE

  CHECK direction consistency: a SHORT-state never fires on a LONG zone (v1 bug fixed).
  CHECK cross-venue: CONFIRMED short markdown [QUARANTINE]; DISAGREEMENT -> VETO [KEEP_AS_VETO].
  THEN veto (dirty spread / at low / depth flip) -> no trade.
  DECISION: SHORT_CANDIDATE / NO_TRADE / REVERSAL_WATCH / NEED_MORE_DATA.
```
