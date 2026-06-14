# CROSS-VENUE COMPARISON (Bybit vs OKX, real data)

Build 2026-06-12T12:57:48+00:00 · RESEARCH/CALIBRATION (not production).

## Category scorecard (one trade per cluster)
| category | n | hit2 | W/L/TO | hit2% | PF | exp% |
|---|--:|--:|:--:|--:|--:|--:|
| CROSS_CONFIRMED | 144 | 38 | 38/48/58 | 26.4 | 0.898 | -0.056 |
| BYBIT_ONLY | 5 | 0 | 0/3/2 | 0.0 | 0.0 | -0.984 |
| OKX_ONLY | 6 | 1 | 1/2/3 | 16.7 | 0.567 | -0.237 |
| CROSS_DISAGREEMENT | 64 | 16 | 16/34/14 | 25.0 | 0.534 | -0.406 |

- matched pairs: 104 · mean lead-lag (OKX-Bybit, min): -0.04 (negative => OKX leads)
- price action agreement was already confirmed <1bps in v1; here we test whether cross-venue zone/state agreement improves hit2/PF.
- CROSS_CONFIRMED vs BYBIT_ONLY hit2/PF delta is the key cross-venue value test.
