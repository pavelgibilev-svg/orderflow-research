# E. Binance 10d — live-valid selector audit

**Build:** 2026-06-02T14:02:11+00:00
Frozen OKX score threshold = **1.021** (weakest OKX winner; NOT tuned on Binance). Selection is causal first-eligible (no best-of-day hindsight).

| model | tr | W | L | TO | wr% | exp% | PF | maxCL | wrongdir | alerts/day | skipped GOOD |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| Model0_top1_day_RS1 | 10 | 1 | 5 | 4 | 10.0 | -0.5821 | 0.35 | 4 | 6 | 1.0 | 30 |
| Model1_first_elig_OKXthr | 1 | 0 | 0 | 1 | 0.0 | 0.371 | None | 0 | 0 | 0.1 | 31 |
| Model2_+noise | 1 | 0 | 0 | 1 | 0.0 | 0.371 | None | 0 | 0 | 0.1 | 31 |
| Model3_+dir_guard | 1 | 0 | 0 | 1 | 0.0 | 0.371 | None | 0 | 0 | 0.1 | 31 |
| Model4_max2_cooldown_noise | 1 | 0 | 0 | 1 | 0.0 | 0.371 | None | 0 | 0 | 0.1 | 31 |