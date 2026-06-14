# S7 feature ablation

**Build:** 2026-05-30T10:46:08+00:00

| variant | enabled | trades | W | L | TO | wr% | exp_aft% | PF | removed | wins_lost | losses_rm |
|---|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| S7_full | fuel,void,wall,micro,funding | 26 | 17 | 7 | 2 | 65.38 | 0.7403 | 2.527 | 3 | 1 | 1 |
| without_fuel | void,wall,micro,funding | 21 | 15 | 4 | 2 | 71.43 | 0.9736 | 3.662 | 8 | 3 | 4 |
| without_void | fuel,wall,micro,funding | 24 | 16 | 7 | 1 | 66.67 | 0.7711 | 2.612 | 5 | 2 | 1 |
| without_wall | fuel,void,micro,funding | 26 | 17 | 7 | 2 | 65.38 | 0.7403 | 2.527 | 3 | 1 | 1 |
| without_micro | fuel,void,wall,funding | 14 | 11 | 3 | 0 | 78.57 | 1.11 | 4.159 | 15 | 7 | 5 |
| without_funding | fuel,void,wall,micro | 21 | 14 | 6 | 1 | 66.67 | 0.7181 | 2.376 | 8 | 4 | 2 |
| only_fuel | fuel | 0 | 0 | 0 | 0 | 0.0 | None | None | 29 | 18 | 8 |
| only_void | void | 0 | 0 | 0 | 0 | 0.0 | None | None | 29 | 18 | 8 |
| only_wall | wall | 0 | 0 | 0 | 0 | 0.0 | None | None | 29 | 18 | 8 |
| only_micro | micro | 0 | 0 | 0 | 0 | 0.0 | None | None | 29 | 18 | 8 |
| only_funding | funding | 0 | 0 | 0 | 0 | 0.0 | None | None | 29 | 18 | 8 |
| enhanced_no_overlay | (none) | 0 | 0 | 0 | 0 | 0.0 | None | None | 29 | 18 | 8 |

## Importance (expectancy drop when removing component)
- funding: 0.0222
- wall: 0.0
- void: -0.0308
- fuel: -0.2333
- micro: -0.3697

**Top component (only positive contributor): funding (+0.022), but UNSTABLE.**

## Honest interpretation (n=26)
- importance = S7_full_exp − without_component_exp. POSITIVE = component helps; NEGATIVE = it nominally hurts in-sample.
- Only **funding** has a positive (tiny, +0.022) contribution. **micro (−0.37)** and **fuel (−0.23)** nominally HURT in-sample.
- The `without_micro` (78.6% wr, n=14) and `without_fuel` (71.4%, n=21) variants look "better" but only by REMOVING MORE TRADES → smaller-sample overfit, not real signal.
- `only_X` variants = 0 trades (one +0.03 bump gives p=0.58 → EV 0.39 < 0.4; need ≥2 confluence conditions to pass).
- **S7_full is the LEAST aggressive EV overlay** (keeps 26/29). Its edge over baseline is REAL (exp 0.6475→0.7403, PF 2.258→2.527) but FRAGILE and NOT robustly attributable to any single fuel feature. With 26 trades and a 3-trade delta (one a wrongly-removed winner), flipping 1 trade changes the attribution.