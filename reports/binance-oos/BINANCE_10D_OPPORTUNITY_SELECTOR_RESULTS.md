# D. Opportunity selector models — BINANCE_10D

**Build:** 2026-06-02T17:15:24+00:00
Causal first-eligible. OKX-frozen confluence floor = 3. Days=10.

| model | tr | wr% | exp% | PF | maxCL | wrongdir | alerts/d | no-trade | fake | GOOD cap/tot |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| ModelA_guard_only | 10 | 20.0 | -0.3035 | 0.612 | 4 | 6 | 1.0 | 0 | 0 | 2/31 |
| ModelB_guard_conf2 | 9 | 22.22 | -0.4254 | 0.51 | 5 | 6 | 0.9 | 1 | 0 | 2/31 |
| ModelC_guard_conf3 | 1 | 0.0 | -0.4912 | 0.0 | 1 | 1 | 0.1 | 9 | 0 | 0/31 |
| ModelD_guard_oppscore_OKXfloor | 1 | 0.0 | -1.64 | 0.0 | 1 | 1 | 0.1 | 9 | 0 | 0/31 |
| ModelE_max2_cooldown_oppscore | 2 | 0.0 | -0.0601 | 0.755 | 1 | 1 | 0.2 | 9 | 0 | 0/31 |
| ModelF_first_elig_oppscore_notrade | 1 | 0.0 | -1.64 | 0.0 | 1 | 1 | 0.1 | 9 | 0 | 0/31 |