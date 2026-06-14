# Trade model comparison (A / B / C+BE)

**Build:** 2026-05-29T17:37:33+00:00
**Selector basis:** enhanced microstructure (dist_to_recent_swing_high<=0.4616 AND dl2_supp_minus_opp_net_flow_15m<=4497.76, top1/day).
**A_baseline shown for reference (baseline selector).**

| model | trades | skip | W | L | TO | BE | winrate% | exp_aft% | PF_aft | totRet% | maxCL | saved | killed |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A_baseline_fixed2pct | 29 | 0 | 17 | 9 | 3 | 0 | 58.62 | 0.5268 | 1.922 | 15.2771 | 3 | - | - |
| A_enhanced_fixed2pct | 29 | 0 | 18 | 8 | 3 | 0 | 62.07 | 0.6475 | 2.258 | 18.7771 | 3 | - | - |
| B_enhanced_targetzone_filter | 4 | 25 | 2 | 1 | 1 | 0 | 50.0 | 0.3476 | 1.597 | 1.3905 | 1 | - | - |
| C_enhanced_targetTP_BE_C1 | 4 | 25 | 1 | 1 | 0 | 2 | 25.0 | -0.0132 | 0.973 | -0.0528 | 2 | 0 | 1 |
| C_enhanced_targetTP_BE_C2 | 4 | 25 | 1 | 1 | 0 | 2 | 25.0 | -0.0132 | 0.973 | -0.0528 | 2 | 0 | 1 |
| C_enhanced_targetTP_BE_C3 | 4 | 25 | 1 | 1 | 2 | 0 | 25.0 | 0.2752 | 1.473 | 1.1009 | 1 | 0 | 0 |
| C_enhanced_targetTP_BE_C4 | 4 | 25 | 1 | 0 | 0 | 3 | 25.0 | 0.3618 | 4.446 | 1.4472 | 2 | 1 | 1 |
| C_enhanced_targetTP_noBE | 4 | 25 | 1 | 1 | 2 | 0 | 25.0 | 0.2752 | 1.473 | 1.1009 | 1 | - | - |