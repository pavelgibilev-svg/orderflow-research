# TREND_UP SHORT BLOCK TEST (2026-03-10..16, +9.4%)

Build 2026-06-12T16:24:23+00:00 · research/calibration.

- v3 short-events in the uptrend (after 6h warmup): **2200** · PF 0.172 (loses).
- event families fired: {'CVD_BREAKDOWN_EVENT': 309, 'SELL_PRESSURE_NO_ABSORPTION_EVENT': 2114, 'ACTIVE_MARKDOWN_EVENT': 898, 'FORCED_UNWIND_EVENT': 42}
- why false: pure downward-momentum events fire on every pullback inside an uptrend; price reverts up -> stopped.

| gate | up before | up after | blocked% | PF after |
|---|--:|--:|--:|--:|
| GATE_1_STRICT_DOWNTREND | 2200 | 869 | 60.5 | 0.02 |
| GATE_2_SELLER_CONTROL | 2200 | 1210 | 45.0 | 0.118 |
| GATE_3_NO_UPTREND | 2200 | 1135 | 48.4 | 0.065 |
| GATE_4_NO_CHOP | 2200 | 2108 | 4.2 | 0.151 |
| GATE_5_COMBINED | 2200 | 828 | 62.4 | 0.0 |

- best uptrend blocker: **GATE_5_COMBINED** (62.4% blocked).
- remaining shorts after the best gate are pullback events the gate still permits; tighter ret/cvd thresholds would remove them but that is tuning (not done).
