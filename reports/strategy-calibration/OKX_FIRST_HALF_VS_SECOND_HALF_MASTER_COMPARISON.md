# OKX direct March - FIRST HALF vs SECOND HALF master comparison

**Build:** 2026-05-25T09:40:33+00:00
**First half:** 2026-03-02..2026-03-15 (14 days)
**Second half:** 2026-03-16, 03-18..03-31 (15 days; 03-17 missing)

## Engine-level

| metric | first half | second half | comment |
|---|---:|---:|---|
| days | 14 | 15 | |
| zones | 510 | 543 | |
| triggered | 295 | 330 | |
| reached_raw | 98 | 89 | |
| primary unique | **15** | **15** | |
| duplicate credits | 83 | 74 | |

## Execution Variant A - trigger_entry + stop 1.0 %

| metric | first half | second half | delta | comment |
|---|---:|---:|---:|---|
| trades | 44 | 43 | -1 | |
| wins | 10 | 9 | -1 | |
| losses | 27 | 25 | -2 | |
| timeouts | 7 | 9 | 2 | |
| winrate % | 22.73 | 20.93 | -1.8 | |
| expectancy pre-cost | -0.1782 | -0.1341 | 0.0441 | |
| PF pre-cost | 0.732 | 0.777 | 0.045 | |
| total return pre-cost | -7.8408 | -5.7668 | 2.074 | |
| expectancy after cost | None | -0.2741 | None | |
| PF after cost | None | 0.607 | None | |
| total return after cost | None | -11.7868 | None | |
| max consec losses | 6 | 8 | 2 | |
| LONG n / exp | 25 / 0.0117 | 18 / -0.338 | — | |
| SHORT n / exp | 19 / -0.4281 | 25 / 0.0127 | — | |

## Execution Variant B - delay 15 min + stop 1.5 % (diagnostic)

| metric | first half | second half | delta | comment |
|---|---:|---:|---:|---|
| trades | 30 | 33 | 3 | |
| wins | 12 | 8 | -4 | |
| losses | 7 | 12 | 5 | |
| timeouts | 11 | 13 | 2 | |
| winrate % | 40.0 | 24.24 | -15.76 | |
| expectancy pre-cost | 0.471 | -0.0845 | -0.5555 | |
| PF pre-cost | 2.053 | 0.867 | -1.186 | |
| total return pre-cost | 14.1312 | -2.7887 | -16.9199 | |
| expectancy after cost | None | -0.2245 | None | |
| PF after cost | None | 0.689 | None | |
| total return after cost | None | -7.4087 | None | |
| max consec losses | 2 | 6 | 4 | |
| LONG n / exp | 15 / 0.5626 | 16 / -0.4244 | — | |
| SHORT n / exp | 15 / 0.3795 | 17 / 0.2354 | — | |

## `DELAY15_STOP15_HOLDS_ON_SECOND_HALF` = **NO**

Decision rule:
- YES if expectancy_pre_cost >= 0 AND PF_pre_cost > 1.0
- NO if expectancy_pre_cost < -0.05 OR PF_pre_cost < 0.9
- MARGINAL otherwise