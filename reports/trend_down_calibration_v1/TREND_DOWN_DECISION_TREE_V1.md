# TREND_DOWN DECISION TREE V1

Build 2026-06-11T16:20:12+00:00 · research/calibration.

Research decision flow (NOT production). TP=2%/SL=1.5% unchanged.

```
IF Level1 != TREND_DOWN:            -> do not use TREND_DOWN templates.
IF Level1 == TREND_DOWN:
  determine capital_state from L2 (prior move, bounce size, depth_imbalance, activity):

  ACTIVE_MARKDOWN (SHORT):          -> TD_ACTIVE_MARKDOWN_SHORT_TEMPLATE  [QUARANTINE: n too small]
  DISTRIBUTION_INTO_BOUNCE (SHORT): -> shorting the bounce LOST here (PF<0.5) -> DO NOT short yet [REJECTED on L2-only]
  FORCED_UNWIND:                    -> not observed -> NEED_MORE_DATA
  ABSORPTION_AFTER_SELL_PRESSURE:   -> DO NOT short; reversal-watch / no-trade
  NO_CONTROL_CHOP:                  -> NO TRADE (default veto)
  UNKNOWN (53% of clusters):        -> NO TRADE (cannot classify on L2-only)

  THEN check veto: dirty spread / at recent low / depth_imbalance flip -> no trade.
  THEN optional confirmations (taker/CVD/cross-venue) -> N/A until trades exist.
  THEN: trade / no-trade / reversal-watch.
```

Bottom line: on L2-only data the tree mostly routes to **NO-TRADE / reversal-watch**; no state yet gives a
tradeable short edge across both true down windows.
