# OKX direct SECOND HALF March 2026 - canonical execution retest (15 days)

**Build:** 2026-05-25T09:33:39+00:00
**Days processed:** 15 (2026-03-16, 03-18..03-31); 03-17 missing in source
**Canonical model:** `scripts/strategy-calibration/canonical_ledger.py (mirror of src/research/canonicalLedger.ts)`
**Target STRICT 2 %. Timeout 24h. NO engine change. Read-only post-hoc.**

- filtered triggered signals: **121**

## Variant A - trigger_entry + stop 1.0 % (canonical baseline)

| metric | pre-cost | after basic cost (0.14 %) |
|---|---:|---:|
| n_trades | 43 | 43 |
| W / L / T | 9 / 25 / 9 | (same) |
| winrate % | 20.93 | (same) |
| avg win % | 1.5433 | (cost reduces each) |
| avg loss % | -0.861 | (cost worsens each) |
| **expectancy %/trade** | **-0.1341** | **-0.2741** |
| total return % | -5.7668 | -11.7868 |
| **profit factor** | **0.777** | **0.607** |
| max consecutive losses | 8 | — |
| LONG n / exp % | 18 / -0.338 | — |
| SHORT n / exp % | 25 / 0.0127 | — |
| skipped due to open position | 78 | — |

### Cost-aware diagnostic (Variant A)
| roundtrip cost % | expectancy %/trade | PF | total return % |
|---|---:|---:|---:|
| 0.10 | -0.2341 | 0.651 | -10.0668 |
| 0.14 | -0.2741 | 0.607 | -11.7868 |
| 0.18 | -0.3141 | 0.568 | -13.5068 |

## Variant B - delay 15min + stop 1.5 % (diagnostic)

| metric | pre-cost | after basic cost (0.14 %) |
|---|---:|---:|
| n_trades | 33 | 33 |
| W / L / T | 8 / 12 / 13 | (same) |
| winrate % | 24.24 | (same) |
| avg win % | 1.4043 | — |
| avg loss % | -1.0522 | — |
| **expectancy %/trade** | **-0.0845** | **-0.2245** |
| total return % | -2.7887 | -7.4087 |
| **profit factor** | **0.867** | **0.689** |
| max consecutive losses | 6 | — |
| LONG n / exp % | 16 / -0.4244 | — |
| SHORT n / exp % | 17 / 0.2354 | — |
| skipped due to open position | 88 | — |

### Cost-aware diagnostic (Variant B)
| roundtrip cost % | expectancy %/trade | PF | total return % |
|---|---:|---:|---:|
| 0.10 | -0.1845 | 0.736 | -6.0887 |
| 0.14 | -0.2245 | 0.689 | -7.4087 |
| 0.18 | -0.2645 | 0.646 | -8.7287 |