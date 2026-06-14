# Binance frozen rule set (before test)

**Build:** 2026-05-30T10:46:08+00:00

## RS1 — Conservative baseline (RUN FIRST)
- Selector: dist_to_recent_swing_high_pct<=0.4616 AND dl2_supp_minus_opp_net_flow_15m<=4497.76, top1/day, entry=confirmed
- Trade: TP 2%, SL 1.5%, no BE, timeout 24h, cost 0.14%
- OKX March exact: {'trades': 29, 'winrate_pct': 62.07, 'expectancy_after_cost_pct': 0.6475, 'pf_after_cost': 2.258, 'total_return_after_cost_pct': 18.7771}
- Can run without OI: YES | Binance recorder: YES
- Do NOT tune: ['dist_to_recent_swing_high_pct_max', 'dl2_supp_minus_opp_net_flow_15m_max', 'tp_pct', 'sl_pct']

## RS2 — S7 fuel overlay (RUN SECOND, only after RS1 OOS pass)
- Overlay: keep if EV>0.4; p_reach = 0.55 + 0.03*[fuel>=med] + 0.03*[void>=med] + 0.03*[no opp wall] + 0.03*[microprice aligned] + 0.02*[funding aligned], cap 0.9
- OKX March exact: {'trades': 26, 'winrate_pct': 65.38, 'expectancy_after_cost_pct': 0.7403, 'pf_after_cost': 2.527, 'total_return_after_cost_pct': 19.2466}
- Can run without OI: PARTIAL | Binance recorder: YES (native OI better)
- Do NOT tune: ['ev_threshold', 'p_reach weights', 'quantile 0.5 for fuel/void thresholds (recompute thresholds from Binance distribution, keep quantile)']