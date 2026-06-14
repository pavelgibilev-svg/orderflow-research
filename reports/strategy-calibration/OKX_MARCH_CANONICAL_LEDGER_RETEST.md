# OKX direct March 2026 - canonical strict-ledger retest

**Build:** 2026-05-23T15:00:16+00:00
**Canonical model:** `scripts/strategy-calibration/canonical_ledger.py (mirror of src/research/canonicalLedger.ts)`
**Target STRICT 2 %. Timeout 24h. No engine change. Read-only post-hoc.**

## A. Inputs

- Dates: 2026-03-02 .. 2026-03-15 (14 days)
- Base filter: fast_trigger≤60m, duplicate_60m, price_band≤1.0% (live-valid; no uniqueMoveId)
- Filtered triggered zones (input to ledger): **103**

## B. Variant 1 - baseline (trigger entry + stop 1.0 %)

- n_trades: **44**
- W / L / T: **10 / 27 / 7**
- skipped due to open position: 59
- winrate %: **22.73**
- avg win %: 1.6474  |  avg loss %: -0.9438
- **expectancy %/trade pre-cost: -0.1782**
- total return % (1 unit/trade): -7.8408
- **profit factor pre-cost: 0.732**
- max consecutive losses: 6
- LONG n / exp %: 25 / 0.0117
- SHORT n / exp %: 19 / -0.4281
- best day: {'date': '2026-03-06', 'sum_pnl_pct': 2.701}
- worst day: {'date': '2026-03-02', 'sum_pnl_pct': -2.8773}

### Cost-aware diagnostic (baseline)

| roundtrip cost % | expectancy %/trade | PF | total return % |
|---|---:|---:|---:|
| 0.10 (fee_0.08_slip_0.02) | -0.2782 | 0.622 | -12.2408 |
| 0.14 (fee_0.08_slip_0.06) | -0.3182 | 0.583 | -14.0008 |
| 0.18 (fee_0.08_slip_0.1) | -0.3582 | 0.548 | -15.7608 |

## C. Variant 2 - diagnostic (delay 15 min entry + stop 1.5 %)

- n_trades: **30**
- W / L / T: **12 / 7 / 11**
- skipped due to open position: 73
- winrate %: **40.0**
- avg win %: 1.5309  |  avg loss %: -1.1188
- **expectancy %/trade pre-cost: 0.471**
- total return % (1 unit/trade): 14.1312
- **profit factor pre-cost: 2.053**
- max consecutive losses: 2
- LONG n / exp %: 15 / 0.5626
- SHORT n / exp %: 15 / 0.3795
- best day: {'date': '2026-03-13', 'sum_pnl_pct': 4.9161}
- worst day: {'date': '2026-03-05', 'sum_pnl_pct': -1.5}

### Cost-aware diagnostic (delay 15m / stop 1.5 %)

| roundtrip cost % | expectancy %/trade | PF | total return % |
|---|---:|---:|---:|
| 0.10 (fee_0.08_slip_0.02) | 0.371 | 1.756 | 11.1312 |
| 0.14 (fee_0.08_slip_0.06) | 0.331 | 1.652 | 9.9312 |
| 0.18 (fee_0.08_slip_0.1) | 0.291 | 1.554 | 8.7312 |

## D. Notes

- `canonical_ledger.py` and `src/research/canonicalLedger.ts` enforce the SAME rule: `open_until_sec = ACTUAL exit timestamp`, NOT `triggerTs + 24h`.
- Stop-first conservative tie-break inside a 1s bucket.
- Cost diagnostic = flat roundtrip subtraction; not a full execution model.
- Diagnostic only — no engine or threshold change.