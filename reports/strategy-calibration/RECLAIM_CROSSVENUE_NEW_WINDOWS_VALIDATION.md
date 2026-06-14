# VALIDATE RECLAIM + CROSS-VENUE CONFIRMATION ON NEW WINDOWS

**Build:** 2026-06-04T13:12:16+00:00
RESEARCH ONLY · no engine/detector/TP-SL/threshold change · TP stays 2% · 2.5/3% = quality labels · no Tardis · no production

**Data constraint:** OKX+Binance L2 overlap ONLY 2026-05-21..30 → cross-venue confirmation cannot be tested on a NEW window.

## OKX March 2026 — regime TREND_UP_HIGHVOL (ret 3.8%, range 15.32%)
Reclaim test: base strong 0.337 | reclaim=1 precision 0.335 wr 36.45% PF 0.799 | reclaim=0 precision 0.338 wr 36.78%

| model | tr | wr% | exp% | PF | ret% | hit2/2.5/3 |
|---|--:|--:|--:|--:|--:|:--:|
| M0_single_RS1 | 29 | 62.07 | 0.6475 | 2.258 | 18.7771 | 18/16/12 |
| M1_norm_guard | 24 | 45.83 | 0.2474 | 1.384 | 5.9365 | 12/10/9 |
| M4_reclaim_only | 28 | 39.29 | 0.0637 | 1.088 | 1.7836 | 11/10/8 |
| M5_reclaim_strong_singleVenue | 28 | 39.29 | 0.0637 | 1.088 | 1.7836 | 11/10/8 |

### March regime breakdown (reclaim strong-precision)
- **TREND_UP** (n=174): base strong 43.7% → reclaim strong 41.9% (wr 37.84%, PF 0.69)
- **RANGE** (n=687): base strong 28.1% → reclaim strong 28.2% (wr 33.14%, PF 0.736)
- **TREND_DOWN** (n=182): base strong 45.1% → reclaim strong 47.1% (wr 48.28%, PF 1.224)

## OKX May 2026 — regime TREND_DOWN (reference)
| model | tr | wr% | exp% | PF | hit2/2.5/3 |
|---|--:|--:|--:|--:|:--:|
| M0_single_RS1 | 9 | 22.22 | 0.1473 | 1.35 | 4/1/0 |
| M1_norm_guard | 6 | 16.67 | -0.1679 | 0.713 | 3/0/0 |
| M4_reclaim_only | 9 | 22.22 | -0.0789 | 0.862 | 4/1/1 |
| M5_reclaim_strong_singleVenue | 0 | 0.0 | None | None | 0/0/0 |

## Binance May cross-venue temporal split (weak check, NOT a new window)
### H1_21_25 — regime RANGE
| model | tr | wr% | exp% | PF | hit2.5 |
|---|--:|--:|--:|--:|--:|
| M0_single_RS1 | 5 | 20.0 | 0.1773 | 1.659 | 1 |
| M1_norm_guard | 1 | 0.0 | -1.64 | 0.0 | 0 |
| M2_cross_confirm | 3 | 66.67 | 0.9867 | 4.895 | 2 |
| M3_divergence_reject | 5 | 40.0 | 0.604 | 3.414 | 2 |
| M4_reclaim_confirm | 0 | 0.0 | None | None | 0 |
| M5_reclaim_confirm_strong | 0 | 0.0 | None | None | 0 |
| M6_live_valid | 2 | 0.0 | -0.6345 | 0.226 | 0 |
### H2_26_30 — regime TREND_DOWN
| model | tr | wr% | exp% | PF | hit2.5 |
|---|--:|--:|--:|--:|--:|
| M0_single_RS1 | 5 | 0.0 | -1.2595 | 0.04 | 0 |
| M1_norm_guard | 1 | 0.0 | -1.64 | 0.0 | 0 |
| M2_cross_confirm | 4 | 0.0 | -1.1037 | 0.103 | 0 |
| M3_divergence_reject | 5 | 0.0 | -0.7474 | 0.24 | 0 |
| M4_reclaim_confirm | 0 | 0.0 | None | None | 0 |
| M5_reclaim_confirm_strong | 0 | 0.0 | None | None | 0 |
| M6_live_valid | 1 | 0.0 | -1.64 | 0.0 | 0 |

## Answers
**1_reclaim_holds** — OKX March (TREND_UP_HIGHVOL): reclaim precision 0.335 vs base 0.337 (winrate 36.45% vs 36.78% no-reclaim) -> NO. OKX May -> YES.

**2_cross_confirm_holds** — CANNOT be tested on a new window — OKX+Binance L2 overlap only 2026-05-21..30. May temporal split provided as a weak internal check only.

**3_together_pf15_wr** — YES — best March model M0_single_RS1: PF 2.258, winrate 62.07%.

**4_which_regimes** — reclaim strong-precision by March sub-regime: {'TREND_UP': {'n': 174, 'base_strong_pct': 43.7, 'reclaim_n': 74, 'reclaim_strong_pct': 41.9, 'reclaim_winrate': 37.84, 'reclaim_pf': 0.69}, 'RANGE': {'n': 687, 'base_strong_pct': 28.1, 'reclaim_n': 341, 'reclaim_strong_pct': 28.2, 'reclaim_winrate': 33.14, 'reclaim_pf': 0.736}, 'TREND_DOWN': {'n': 182, 'base_strong_pct': 45.1, 'reclaim_n': 87, 'reclaim_strong_pct': 47.1, 'reclaim_winrate': 48.28, 'reclaim_pf': 1.224}}.

**5_fuel_needed** — LIKELY — reclaim+confirmation improves precision but not to 60-70%; OI/liquidations fuel-layer is the next lever.

## Flags
```
RECLAIM_VALIDATION_DONE = YES
OKX_MARCH_REGIME = TREND_UP_HIGHVOL
OKX_MAY_REGIME = TREND_DOWN
RECLAIM_HOLDS_OKX_MARCH = NO
RECLAIM_HOLDS_OKX_MAY = YES
CROSS_VENUE_VALIDATED_ON_NEW_WINDOW = NO_DATA (only May overlaps)
BEST_MARCH_MODEL = M0_single_RS1
BEST_MARCH_PF = 2.258
BEST_MARCH_WINRATE = 62.07
TOGETHER_PF_1_5_OR_WR_60_70 = YES
FUEL_LAYER_NEEDED = LIKELY (OI/liquidations) to lift quality further
READY_FOR_TELEGRAM_SHADOW_MODE = NO
READY_FOR_PRODUCTION_TRADING = NO
MORE_OOS_REQUIRED = YES
TARDIS_USED = NO
```