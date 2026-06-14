# D. TD-short shadow observer backtest

**Build:** 2026-06-04T17:35:04+00:00
All confirmed zones: 1383 · TD-short population: 133 · candidates: 61 · accepted: 24

**Accepted module:** 24tr 12/7/5 wr 50.0% exp 0.5118 PF 1.993 ret 12.282% maxCL 4 hit2/2.5/3 12/12/9
Rejected winners (missed): 36 · rejected losers (correctly): 21

## Per venue
| venue | tr | wr% | PF | exp% | hit2.5 |
|---|--:|--:|--:|--:|--:|
| OKX_MARCH | 18 | 61.11 | 3.461 | 0.9004 | 11 |
| OKX_MAY | 5 | 20.0 | 0.449 | -0.4569 | 1 |
| BINANCE_MAY | 1 | 0.0 | 0.0 | -1.64 | 0 |

## Model comparison (HYBRID vs M4 vs M7)
| model | tr | wr% | PF | exp% | maxCL |
|---|--:|--:|--:|--:|--:|
| HYBRID_module | 24 | 50.0 | 1.993 | 0.5118 | 4 |
| M4_thin_only | 20 | 60.0 | 3.697 | 0.8992 | 3 |
| M7_2of4_no_mandatory | 26 | 50.0 | 2.129 | 0.5407 | 4 |