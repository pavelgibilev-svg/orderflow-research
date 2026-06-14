# BE isolation addendum (full enhanced 29-trade set, fixed 2% TP)

**Build:** 2026-05-29T17:45:02+00:00
**Why:** main Model C gated by target-zone>=2% collapsed to n=4. This isolates BE on the real n=29.

| model | trades | W | L | TO | BE | winrate% | exp_aft% | PF_aft | totRet% | maxCL | saved | killed |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A_enhanced_fixed2pct_noBE | 29 | 18 | 8 | 3 | 0 | 62.07 | 0.6475 | 2.258 | 18.7771 | 3 | - | - |
| A_enhanced_fixed2pct_BE_C1 | 29 | 15 | 7 | 0 | 7 | 51.72 | 0.5324 | 2.239 | 15.44 | 4 | 1 | 3 |
| A_enhanced_fixed2pct_BE_C2 | 29 | 15 | 7 | 0 | 7 | 51.72 | 0.5324 | 2.239 | 15.44 | 4 | 1 | 3 |
| A_enhanced_fixed2pct_BE_C3 | 29 | 18 | 8 | 3 | 0 | 62.07 | 0.6475 | 2.258 | 18.7771 | 3 | 0 | 0 |
| A_enhanced_fixed2pct_BE_C4 | 29 | 2 | 0 | 0 | 27 | 6.9 | -0.0021 | 0.984 | -0.06 | 16 | 8 | 16 |

**Reference (no BE):** winrate 62.07%, exp_aft 0.6475%, PF 2.258, totRet 18.7771%
**Best BE variant:** A_enhanced_fixed2pct_BE_C3 (exp_aft 0.6475%)
**BE improves expectancy over no-BE on full 29:** NO

Each BE variant moves stop to entry after its arm condition; BE exit ≈ -0.14% (cost). losses_saved = trades that were a full -1.64% loss in no-BE but exited ≈breakeven with BE. winners_killed = trades that were +1.86% wins in no-BE but got stopped at breakeven first.