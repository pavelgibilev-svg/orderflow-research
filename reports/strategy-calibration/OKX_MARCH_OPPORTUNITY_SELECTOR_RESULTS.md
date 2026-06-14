# D. Opportunity selector models — OKX_MARCH

**Build:** 2026-06-02T17:15:24+00:00
Causal first-eligible. OKX-frozen confluence floor = 3. Days=29.

| model | tr | wr% | exp% | PF | maxCL | wrongdir | alerts/d | no-trade | fake | GOOD cap/tot |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| ModelA_guard_only | 29 | 55.17 | 0.5767 | 2.172 | 2 | 8 | 1.0 | 0 | 0 | 16/382 |
| ModelB_guard_conf2 | 29 | 55.17 | 0.5767 | 2.172 | 2 | 8 | 1.0 | 0 | 0 | 16/382 |
| ModelC_guard_conf3 | 29 | 51.72 | 0.456 | 1.831 | 2 | 8 | 1.0 | 0 | 0 | 15/382 |
| ModelD_guard_oppscore_OKXfloor | 24 | 45.83 | 0.2474 | 1.384 | 2 | 10 | 0.83 | 5 | 0 | 11/382 |
| ModelE_max2_cooldown_oppscore | 57 | 36.84 | -0.0884 | 0.891 | 5 | 28 | 1.97 | 0 | 0 | 21/382 |
| ModelF_first_elig_oppscore_notrade | 24 | 45.83 | 0.2474 | 1.384 | 2 | 10 | 0.83 | 5 | 0 | 11/382 |