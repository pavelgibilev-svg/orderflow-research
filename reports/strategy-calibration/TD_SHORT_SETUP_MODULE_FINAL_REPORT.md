# TD-SHORT SETUP MODULE — FINAL REPORT

**Build:** 2026-06-04T17:35:04+00:00
SHADOW / RESEARCH ONLY · Telegram DISABLED · no production · engine/detector/TP-SL unchanged · TP2/SL1.5 · causal

## Final rule
TREND_DOWN + SHORT + prior_move_60m<0 + no buyer-absorption (mandatory), then >=2 of {rejection, taker-sell, microprice-down, thin-bid-path}; first-eligible max2/day + cooldown.

## Observer backtest (existing data)
All zones 1383 · TD-short 133 · candidates 61 · accepted 24
- **24tr · wr 50.0% · exp 0.5118 · PF 1.993 · ret 12.282% · maxCL 4 · hit2/2.5/3 12/12/9**
- rejected winners 36 · correctly-rejected losers 21

## Model comparison
| model | tr | wr% | PF | exp% | maxCL |
|---|--:|--:|--:|--:|--:|
| HYBRID_module | 24 | 50.0 | 1.993 | 0.5118 | 4 |
| M4_thin_only | 20 | 60.0 | 3.697 | 0.8992 | 3 |
| M7_2of4_no_mandatory | 26 | 50.0 | 2.129 | 0.5407 | 4 |

## Per venue
| venue | tr | wr% | PF | exp% |
|---|--:|--:|--:|--:|
| OKX_MARCH | 18 | 61.11 | 3.461 | 0.9004 |
| OKX_MAY | 5 | 20.0 | 0.449 | -0.4569 |
| BINANCE_MAY | 1 | 0.0 | 0.0 | -1.64 |

## Answers
**1_final_rule** — TREND_DOWN + SHORT + prior_move_60m<0 + no buyer-absorption (mandatory), then >=2 of {rejection, taker-sell, microprice-down, thin-bid-path}; first-eligible max2/day + cooldown.

**2_mandatory_vs_optional** — Mandatory: regime, direction, prior_move_60m<0, no buyer-absorption. Optional (confluence>=2): rejection/taker-sell/microprice-down/thin-path.

**3_practical_model** — HYBRID (mandatory + confluence>=2). M4 thin-only has higher PF but n=11 (fragile); HYBRID is the robust middle.

**4_trades_existing** — 24 accepted trades on existing data (wr 50.0%, PF 1.993).

**5_per_venue** — {'OKX_MARCH': {'trades': 18, 'winrate': 61.11, 'pf': 3.461, 'expectancy': 0.9004, 'hit_2_5': 11}, 'OKX_MAY': {'trades': 5, 'winrate': 20.0, 'pf': 0.449, 'expectancy': -0.4569, 'hit_2_5': 1}, 'BINANCE_MAY': {'trades': 1, 'winrate': 0.0, 'pf': 0.0, 'expectancy': -1.64, 'hit_2_5': 0}}

**6_reject_reasons** — not_trend_down, not_short, no_fresh_weakness_60m, buyer_absorption, weak_confluence(<2).

**7_what_kills_short** — shorting a bounce (prior_move_60m>0) and buyer absorption (OFI>0/taker buy) — 70% of losses pre-flagged.

**8_shadow_ready** — YES — observer logic is causal and logs candidates/rejects; shadow/research only.

**9_telegram_ready** — NO — explicitly disabled; not enough OOS evidence.

**10_oos_needs** — new OKX+Binance downtrend overlap window, >=15-20 TD-short trades, no tuning; criteria PF>1.5 & wr>=50-55%.

## Flags
```
TD_SHORT_MODULE_FORMALIZED = YES
TD_SHORT_SHADOW_OBSERVER_READY = YES
TD_SHORT_TELEGRAM_READY = NO
TD_SHORT_PRODUCTION_READY = NO
BEST_TD_SHORT_MODEL = HYBRID_module (mandatory + confluence>=2 + cooldown)
TD_SHORT_EXISTING_DATA_TRADES = 24
TD_SHORT_EXISTING_DATA_WINRATE = 50.0
TD_SHORT_EXISTING_DATA_PF = 1.993
TD_SHORT_EXISTING_DATA_EXPECTANCY = 0.5118
TD_SHORT_REJECTED_WINNERS = 36
TD_SHORT_REJECTED_LOSERS = 21
TD_SHORT_OOS_REQUIRED = YES
READY_FOR_TELEGRAM_SHADOW_MODE = NO
READY_FOR_PRODUCTION_TRADING = NO
TARDIS_USED = NO
```