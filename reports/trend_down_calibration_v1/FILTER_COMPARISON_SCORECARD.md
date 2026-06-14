# FILTER COMPARISON SCORECARD

Build 2026-06-11T16:20:12+00:00 · research/calibration.

| filter | state | n | windows | hit2% | PF | decision | why |
|---|---|--:|--:|--:|--:|:--:|---|
| TD_ACTIVE_MARKDOWN_SHORT_CANDIDATE | ACTIVE_MARKDOWN | 1 | 1 | 0.0 | None | **NEED_MORE_DATA** | sample too small |
| TD_DISTRIBUTION_INTO_BOUNCE_SHORT_CANDIDATE | DISTRIBUTION_INTO_BOUNCE | 16 | 3 | 12.5 | 0.324 | **REJECT** | shorting the bounce LOST (PF 0.324, hit2 12.5%) |
| TD_FORCED_UNWIND_CONTINUATION_CANDIDATE | FORCED_UNWIND | 0 | 0 | 0.0 | None | **NEED_MORE_DATA** | sample too small |
| TD_ABSORPTION_AFTER_SELL_PRESSURE_NO_SHORT_OR_REVERSAL_WATCH | ABSORPTION_AFTER_SELL_PRESSURE | 1 | 1 | 0.0 | 0.0 | **NEED_MORE_DATA** | sample too small |
| TD_NO_CONTROL_CHOP_NO_TRADE | NO_CONTROL_CHOP | 12 | 3 | 33.3 | 4.537 | **KEEP_AS_VETO** | chop-state; default veto (PF 4.537 on tiny n is noise) |
