# C. Opportunity rule search — OKX_MARCH

**Build:** 2026-06-02T17:15:24+00:00
Each rule applied AFTER dir-guard, as live-valid first-eligible selector (1/day). good_captured = filter-view of winners.

| rule | src | sel tr | wr% | PF | exp% | alerts/d | no-trade | GOOD cap/tot | NOISE rej | overfit |
|---|:--:|--:|--:|--:|--:|--:|--:|--:|--:|:--:|
| O1_uniqueness_high | OKX | 24 | 45.83 | 1.384 | 0.2474 | 0.83 | 5 | 55/382 | 479 | LOW |
| O2_initiative_shift | OKX | 26 | 38.46 | 0.905 | -0.0782 | 0.9 | 3 | 119/382 | 387 | MED |
| O3_reclaim_rejection | OKX | 29 | 51.72 | 1.831 | 0.456 | 1.0 | 0 | 315/382 | 92 | LOW |
| O4_thin_path | OKX | 29 | 55.17 | 2.172 | 0.5767 | 1.0 | 0 | 354/382 | 52 | LOW |
| O5_entropy_compression_EXPLORATORY | EXP | 0 | 0.0 | None | None | 0.0 | 29 | 0/382 | 570 | HIGH |
| O6_regime_continuation | OKX | 29 | 51.72 | 1.761 | 0.4349 | 1.0 | 0 | 224/382 | 266 | LOW |
| O7_reversal_only_proof | OKX | 18 | 38.89 | 0.916 | -0.0686 | 0.62 | 11 | 44/382 | 478 | MED |
| O8_confluence_ge3 | OKX | 29 | 51.72 | 1.831 | 0.456 | 1.0 | 0 | 318/382 | 90 | LOW |