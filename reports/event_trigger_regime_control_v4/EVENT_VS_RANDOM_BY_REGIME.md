# EVENT vs RANDOM by regime (the v4 core test)

Build 2026-06-12T15:08:44+00:00 · research/calibration.

di-free detector, OKX single-venue. random = 500 random-minute shorts/window, same TP2/SL1.5/horizon.

| regime | event n | event hit2% | event PF | rand hit2% | rand PF | **lift hit2** | **lift PF** |
|---|--:|--:|--:|--:|--:|--:|--:|
| TREND_DOWN | 11867 | 36.8 | 1.812 | 34.7 | 2.491 | 2.1 | -0.679 |
| TREND_UP | 3558 | 6.5 | 0.178 | 5.0 | 0.157 | 1.5 | 0.021 |
| RANGE_CHOP | 3854 | 16.6 | 0.842 | 11.6 | 0.797 | 5.0 | 0.045 |
| REVERSAL_BOUNCE | 1621 | 9.6 | 1.238 | 9.6 | 1.555 | 0.0 | -0.317 |

**Read it like this:** a real edge shows POSITIVE lift over random in MULTIPLE regimes — especially staying out of trouble in TREND_UP/RANGE where random short loses. Lift ~0 in TREND_DOWN = regime exposure.
