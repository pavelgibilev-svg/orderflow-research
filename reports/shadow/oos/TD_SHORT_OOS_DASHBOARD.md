# TD-short OOS dashboard

**Build:** 2026-06-05T08:24:50+00:00
**STATUS: OOS_FAIL**

- days observed: 48 · TD-short candidates: 61 · HYBRID accepted: 24 · M4 accepted: 112 (overlap 18)
- completed outcomes: 24 · pending (<24h or unmatured): 0

**HYBRID accepted (matured):** 24tr 12/7/5 · wr 50.0% · PF 1.993 · exp 0.5118 · maxLS 4 · hit2/2.5/3 12/12/9

## By venue
| venue | tr | wr% | PF |
|---|--:|--:|--:|
| BINANCE_MAY | 1 | 0.0 | 0.0 |
| OKX_MARCH | 18 | 61.11 | 3.461 |
| OKX_MAY | 5 | 20.0 | 0.449 |

## By regime
| regime | tr | wr% | PF |
|---|--:|--:|--:|
| TREND_DOWN | 24 | 50.0 | 1.993 |

## Safety
```
DECISION_LOG_FUTURE_LEAK_FREE = YES
OUTCOME_UPDATER_SEPARATE = YES
DUPLICATE_ZONE_IDS = NO
TELEGRAM_DISABLED = YES
PRODUCTION_DISABLED = YES
```

## Success criteria (gate)
```
status = OOS_FAIL
min_trades = 20
pf>1.5 = True
winrate>=50 = True
max_loss_streak<=5 = True
not_concentrated = False
no_catastrophic = False
```

_Note: if accepted trades < 20, status = INSUFFICIENT_SAMPLE even if numbers look good._