# OKX cross-venue first-day summary

**Venue:** OKX `okex-swap` BTC-USDT-SWAP — perpetual
**Source:** Tardis CDN, first-day-of-month free samples only
**Replay window per date:** 3 hours from UTC midnight (compute-budget cap)
**Strategy thresholds:** Binance USDS-M Futures defaults, **UNCHANGED**

## HARD DISCLAIMER

  • OKX is NOT Binance.
  • Strategy thresholds are calibrated for Binance USDS-M Futures BTCUSDT-perp.
  • Numbers below are the engine's reaction to OKX microstructure with Binance-tuned thresholds left UNCHANGED.
  • Do NOT quote any of these numbers as a strategy edge or winrate.
  • Purpose: check whether the engine can detect plausible zones on a different L2 venue, not whether they pay.

## A. Per-date summary (3h window)

| date       | regime hint        | zones | confirmed | triggered | reached | LONG | SHORT | unique moves | dedup suppr. | raw hit | unique-move hit |
|------------|--------------------|------:|----------:|----------:|--------:|-----:|------:|-------------:|-------------:|--------:|----------------:|
| 2026-01-01 | up +1.38 %         |     6 |         6 |         3 |       0 |    3 |     3 |            0 |         2043 |   0.00% |           0.00% |
| 2026-04-01 | flat -0.24 %       |    11 |        11 |         6 |       0 |    7 |     4 |            0 |         1365 |   0.00% |           0.00% |
| 2026-05-01 | up +2.47 %         |     5 |         5 |         3 |       2 |    3 |     2 |            1 |         1284 |  66.67% |          33.33% |

## B. Status breakdown

| date       | RESOLVED_FAILED | INVALIDATED | NO_TRIGGER | EXPIRED |
|------------|----------------:|------------:|-----------:|--------:|
| 2026-01-01 |               3 |           0 |          3 |       0 |
| 2026-04-01 |               6 |           2 |          3 |       0 |
| 2026-05-01 |               1 |           0 |          2 |       0 |

## C. Interpretation notes

- **Hit-rate is computed within the 3-hour replay window;** the strategy's target horizons are 4 / 8 / 24 h, so triggered zones are evaluated against the full 24 h of trades but only those whose trigger fell inside the 3 h L2 window are counted. This is the same compute-budget arrangement we use for Binance day-runs.
- **Hit-rates vary by date and are inseparable from intraday regime** — e.g. 2026-05-01 shows a +2.47 % up day, which mechanically helps LONG zones reach a 2 % target; 2026-01-01 and 2026-04-01 sit closer to flat and produce 0 reaches. None of this is a profitability claim: 3 days is not a sample. It does NOT imply the strategy is profitable on OKX. It does NOT imply it is unprofitable on OKX. It does NOT carry over to Binance. A real verdict needs a multi-day matched-window study under a venue-calibrated config.
- **High duplicate-suppression counts** (~1 000+ candidates absorbed per day) indicate the engine produces many same-direction signals on OKX. Whether that's noise or stacking depends on calibration — out of scope here.
- **LONG / SHORT imbalance** mirrors the intraday regime hint; expected.

## D. What's missing for a real cross-venue conclusion

- Full-day replay on each date (3 h cap drops the latter 21 h of L2 events).
- More than three first-of-month days — Tardis paid tier OR OKX VIP premium needed to extend.
- A venue-calibrated thresholds config — explicitly out of scope per the user's hard rules.
- A matched-window Binance backtest on the same UTC days for direct comparison.