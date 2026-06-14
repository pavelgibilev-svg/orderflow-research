# OKX direct March - INTERIM sanity check on 2026-03-16 + 2026-03-18

**Build:** 2026-05-24T14:01:53+00:00
**Scope:** ONLY 2 already-completed days; main chain still running for the other 13.
**Canonical model:** `scripts/strategy-calibration/canonical_ledger.py` (= `src/research/canonicalLedger.ts`).
**Target STRICT 2 %. Stop variants: 1.0 % (A) and 1.5 % (B). Timeout 24h.**

## 1. File presence

| date | wrapper report | full zones.json | trades.csv.gz |
|---|:---:|:---:|:---:|
| 2026-03-16 | YES | YES | YES |
| 2026-03-18 | YES | YES | YES |

## 2. Engine-level per-day metrics (already-produced backtest reports)

| date | zones | trig | reached | prim | dup | fail | no_trig | inval | LONG | SHORT | raw_hit % | unique_hit % | dedup_supp | runtime s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026-03-16 | 45 | 24 | 3 | 1 | 2 | 21 | 5 | 16 | 25 | 20 | 12.5 | 4.17 | 11140 | 4767.4 |
| 2026-03-18 | 57 | 33 | 12 | 1 | 11 | 21 | 4 | 20 | 21 | 36 | 36.36 | 3.03 | 12056 | 4474.5 |

## 3. Variant A - trigger_entry + stop 1.0 % (canonical baseline)

| metric | value |
|---|---:|
| n_trades | **6** |
| W / L / T | **1 / 3 / 2** |
| winrate % | 16.67 |
| avg win % | 1.0013 |
| avg loss % | -1.0 |
| **expectancy %/trade pre-cost** | **0.0007** |
| expectancy %/trade after basic cost (0.14 %) | -0.1393 |
| profit factor pre-cost | **1.001** |
| profit factor after cost | 0.756 |
| total return % (1 unit/trade) pre-cost | 0.004 |
| total return % after basic cost | -0.836 |
| max consecutive losses | 2 |
| LONG n / exp % | 1 / 0.2008 |
| SHORT n / exp % | 5 / -0.0394 |
| skipped due to open position | 15 |
| skipped no data | 0 |

### per-day result

| date | n trades | W/L/T | total pnl % (pre) | total pnl % (after cost) | expectancy %/trade |
|---|---:|---|---:|---:|---:|
| 2026-03-16 | 3 | 0/2/1 | -1.7992 | -2.2192 | -0.5997 |
| 2026-03-18 | 3 | 1/1/1 | 1.8032 | 1.3832 | 0.6011 |

### best / worst trade

- best trade: `BTC-USDT-SWAP-SHORT-1773806704000-17` on **2026-03-18** (SHORT) — pnl **2.0 %**, exit `target_2pct`
- worst trade: `BTC-USDT-SWAP-SHORT-1773620946000-4` on **2026-03-16** (SHORT) — pnl **-1.0 %**, exit `stop`

## 4. Variant B - delay 15 min entry + stop 1.5 % (diagnostic)

| metric | value |
|---|---:|
| n_trades | **4** |
| W / L / T | **1 / 1 / 2** |
| winrate % | 25.0 |
| avg win % | 1.1918 |
| avg loss % | -1.4634 |
| **expectancy %/trade pre-cost** | **-0.1358** |
| expectancy %/trade after basic cost (0.14 %) | -0.2758 |
| profit factor pre-cost | **0.814** |
| profit factor after cost | 0.656 |
| total return % (1 unit/trade) pre-cost | -0.5433 |
| total return % after basic cost | -1.1033 |
| max consecutive losses | 2 |
| LONG n / exp % | 0 / None |
| SHORT n / exp % | 4 / -0.1358 |
| skipped due to open position | 17 |
| skipped no data | 0 |

### per-day result

| date | n trades | W/L/T | total pnl % (pre) | total pnl % (after cost) | expectancy %/trade |
|---|---:|---|---:|---:|---:|
| 2026-03-16 | 2 | 0/1/1 | -2.9269 | -3.2069 | -1.4634 |
| 2026-03-18 | 2 | 1/0/1 | 2.3836 | 2.1036 | 1.1918 |

### best / worst trade

- best trade: `BTC-USDT-SWAP-SHORT-1773792030000-1` on **2026-03-18** (SHORT) — pnl **2.0 %**, exit `target_2pct`
- worst trade: `BTC-USDT-SWAP-SHORT-1773620946000-4` on **2026-03-16** (SHORT) — pnl **-1.5 %**, exit `stop`

## 5. Sanity check verdict

- No sanity issues detected. Canonical ledger appears applied correctly on both days.

## 6. Main chain status

- main chain still running: **YES**
- main chain current day: **2026-03-19**

## 7. Interim flag matrix

```
INTERIM_CHECK_DONE = YES
INTERIM_DAYS_CHECKED = ['2026-03-16', '2026-03-18']
INTERIM_BACKTEST_OUTPUTS_PRESENT = YES
INTERIM_CANONICAL_LEDGER_OK = YES
INTERIM_TRIGGER_ENTRY_STOP1_TRADES = 6
INTERIM_TRIGGER_ENTRY_STOP1_EXPECTANCY = 0.0007
INTERIM_TRIGGER_ENTRY_STOP1_PF = 1.001
INTERIM_TRIGGER_ENTRY_STOP1_TOTAL_RETURN_PRE_COST = 0.004
INTERIM_TRIGGER_ENTRY_STOP1_TOTAL_RETURN_AFTER_COST = -0.836
INTERIM_DELAY15_STOP15_TRADES = 4
INTERIM_DELAY15_STOP15_EXPECTANCY = -0.1358
INTERIM_DELAY15_STOP15_PF = 0.814
INTERIM_DELAY15_STOP15_TOTAL_RETURN_PRE_COST = -0.5433
INTERIM_DELAY15_STOP15_TOTAL_RETURN_AFTER_COST = -1.1033
INTERIM_DELAY15_STOP15_EXPECTANCY_AFTER_COST = -0.2758
INTERIM_DELAY15_STOP15_PROFITABLE_ON_2DAYS = NO
INTERIM_RESULT_LOOKS_NORMAL = YES
MAIN_CHAIN_STILL_RUNNING = YES
MAIN_CHAIN_CURRENT_DAY = 2026-03-19
INTERIM_PROFITABILITY_SAMPLE_TOO_SMALL = YES
```

## 8. Caveats

- This is only 2 days of OOS data. **`INTERIM_PROFITABILITY_SAMPLE_TOO_SMALL = YES`**.
- Final verdict requires all 15 days completed and a separate retest report.
- No engine / threshold change; no production integration.