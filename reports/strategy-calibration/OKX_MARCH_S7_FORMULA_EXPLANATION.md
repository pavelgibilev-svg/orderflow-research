# S7 formula explanation

**Build:** 2026-05-30T10:46:08+00:00

## Base selector
`dist_to_recent_swing_high_pct<=0.4616 AND dl2_supp_minus_opp_net_flow_15m<=4497.76, top1/day, entry=confirmed`

## EV formula
`EV = p_reach*1.86 - (1-p_reach)*1.64   (1.86 = target2% - cost0.14; 1.64 = stop1.5 + cost0.14)`

`keep zone if EV > 0.4  <=>  p_reach > 0.5829`

## p_reach (base 0.55, cap 0.9)

| component | weight | feature | threshold | leak |
|---|---:|---|---|---|
| true_fuel_score>=median | +0.03 | true_fuel_score = |oi_zscore_14d| + |funding_zscore_7d| | 1.5373 | SAFE |
| ms_thin_path_score>=median | +0.03 | L2 thin-path-to-target (void) | 0.0982 | SAFE |
| ms_large_walls_on_path==0 | +0.03 | no large opposing wall on 2% path | 0 | SAFE |
| dl2_microprice_aligned_delta_5m_bps>=0 | +0.03 | microprice drift aligned with direction (5m window ends at confirm) | - | SAFE |
| funding aligned (LONG&funding<0 OR SHORT&funding>0) | +0.02 | funding_rate_at_signal (last 8h settle<=T) | - | SAFE |

- true OI used: YES (daily, OKX rubik, in true_fuel_score via oi_zscore_14d)
- funding used: YES (in true_fuel_score and funding-aligned bump)
- flow_proxy in selector: NO in S7 p_reach (flow proxies computed separately, not in this selector)
- target-zone in selector: NO (target-zone is orientation/diagnostic only)
- future/outcome field used: **NO**

## Why EV>0.4
EV>0.4 <=> p_reach>0.583; base 0.55 plus bumps. Needs >=2 of the 0.03 conditions (or one 0.03 + funding 0.02). Effectively keeps zones with at least two confluence conditions; removes zones with <=1 weak condition.