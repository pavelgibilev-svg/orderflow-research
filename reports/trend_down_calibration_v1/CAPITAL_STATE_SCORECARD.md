# CAPITAL STATE SCORECARD

Build 2026-06-11T16:20:12+00:00 · research/calibration.

Baseline (all clusters): n=89 hit2=21.3% loss=30.3% PF=0.798

| capital_state | n | hit2% | loss% | TO% | PF | windows | interpretation |
|---|--:|--:|--:|--:|--:|---|---|
| ACTIVE_MARKDOWN | 13 | 7.7 | 38.5 | 53.8 | 0.227 | W1,W2,W3 | classifier direction-blind: labels LONG zones too -> flawed; SHORT subset tiny |
| DISTRIBUTION_INTO_BOUNCE | 16 | 12.5 | 43.8 | 43.8 | 0.324 | W1,W2,W3 | weak/losing (PF 0.324) |
| FORCED_UNWIND | 0 | - | - | - | - | - | not observed |
| ABSORPTION_AFTER_SELL_PRESSURE | 1 | 0.0 | 100.0 | 0.0 | 0.0 | W3 | too few to judge (NEED_MORE_DATA) |
| NO_CONTROL_CHOP | 12 | 33.3 | 8.3 | 58.3 | 4.537 | W1,W2,W3 | marginal (PF 4.537) |
| UNKNOWN | 47 | 25.5 | 27.7 | 46.8 | 1.047 | W1,W2,W3 | unclassifiable on L2-only (53%% of pool) -> NO TRADE |
