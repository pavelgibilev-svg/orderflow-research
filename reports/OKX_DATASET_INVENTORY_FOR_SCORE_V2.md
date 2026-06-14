# OKX dataset inventory — preparing for `zone_score_v2`

**Build time:** 2026-05-17T16:14:12Z UTC
**Venue:** OKX `okex-swap` BTC-USDT-SWAP
**Period considered:** 2024-01-01 .. 2026-05-01 (29 first-of-month dates that Tardis publishes free).

## A. Summary

- Dates with **full L2** on disk: **29** / 29
- Dates with **trades only** on disk: **0**
- Calibration set (v1 weight derivation, do not reuse for v2 selection): 2024-01-01, 2024-07-01, 2024-10-01, 2025-10-01, 2025-12-01, 2026-04-01
- OOS-v1 set (v1 OOS test, do not reuse for v2 selection): 2024-05-01, 2024-06-01, 2024-09-01, 2025-04-01, 2025-05-01, 2025-11-01
- Total OKX bytes on disk: **17.93 GiB**
- Missing L2 dates that ARE free on Tardis: **0** — 
- Missing L2 dates blocked by Tardis: **0** — (none)

## B. Per-date inventory

| date | role | L2 | trades | bk-tick | deriv-tick | liq | full-day report | bytes (MiB) |
|------|------|----|--------|---------|------------|-----|-----------------|------------:|
| 2024-01-01 | calibration   | ✓  |   ✓    |    ·    |     ·      |  ·  |        ✓        |      501.3 |
| 2024-02-01 | —             | ✓  |   ✓    |    ·    |     ·      |  ·  |        —        |      651.6 |
| 2024-03-01 | —             | ✓  |   ✓    |    ·    |     ·      |  ·  |        —        |      734.1 |
| 2024-04-01 | —             | ✓  |   ✓    |    ·    |     ·      |  ·  |        —        |      642.0 |
| 2024-05-01 | OOS_v1        | ✓  |   ✓    |    ·    |     ·      |  ·  |        ✓        |     1015.2 |
| 2024-06-01 | OOS_v1        | ✓  |   ✓    |    ·    |     ·      |  ·  |        ✓        |      270.4 |
| 2024-07-01 | calibration   | ✓  |   ✓    |    ·    |     ·      |  ·  |        ✓        |      494.0 |
| 2024-08-01 | —             | ✓  |   ✓    |    ·    |     ·      |  ·  |        —        |      720.9 |
| 2024-09-01 | OOS_v1        | ✓  |   ✓    |    ·    |     ·      |  ·  |        ✓        |      519.9 |
| 2024-10-01 | calibration   | ✓  |   ✓    |    ·    |     ·      |  ·  |        ✓        |      670.6 |
| 2024-11-01 | —             | ✓  |   ✓    |    ·    |     ·      |  ·  |        —        |      616.0 |
| 2024-12-01 | —             | ✓  |   ✓    |    ·    |     ·      |  ·  |        —        |      533.2 |
| 2025-01-01 | —             | ✓  |   ✓    |    ·    |     ·      |  ·  |        —        |      468.2 |
| 2025-02-01 | —             | ✓  |   ✓    |    ·    |     ·      |  ·  |        —        |      552.2 |
| 2025-03-01 | —             | ✓  |   ✓    |    ·    |     ·      |  ·  |        —        |      811.1 |
| 2025-04-01 | OOS_v1        | ✓  |   ✓    |    ·    |     ·      |  ·  |        ✓        |      822.9 |
| 2025-05-01 | OOS_v1        | ✓  |   ✓    |    ·    |     ·      |  ·  |        ✓        |      624.6 |
| 2025-06-01 | —             | ✓  |   ✓    |    ·    |     ·      |  ·  |        —        |      467.9 |
| 2025-07-01 | —             | ✓  |   ✓    |    ·    |     ·      |  ·  |        —        |      731.7 |
| 2025-08-01 | —             | ✓  |   ✓    |    ·    |     ·      |  ·  |        —        |      837.4 |
| 2025-09-01 | —             | ✓  |   ✓    |    ·    |     ·      |  ·  |        —        |      853.2 |
| 2025-10-01 | calibration   | ✓  |   ✓    |    ·    |     ·      |  ·  |        ✓        |      529.4 |
| 2025-11-01 | OOS_v1        | ✓  |   ✓    |    ·    |     ·      |  ·  |        ✓        |      335.1 |
| 2025-12-01 | calibration   | ✓  |   ✓    |    ·    |     ·      |  ·  |        ✓        |      926.7 |
| 2026-01-01 | —             | ✓  |   ✓    |    ·    |     ·      |  ·  |        —        |      298.1 |
| 2026-02-01 | —             | ✓  |   ✓    |    ·    |     ·      |  ·  |        —        |      879.1 |
| 2026-03-01 | —             | ✓  |   ✓    |    ·    |     ·      |  ·  |        —        |      749.8 |
| 2026-04-01 | calibration   | ✓  |   ✓    |    ✓    |     ✓      |  ✓  |        ✓        |      665.9 |
| 2026-05-01 | —             | ✓  |   ✓    |    ·    |     ·      |  ·  |        —        |      435.5 |

Legend: `✓` = present on disk; `·` = missing but free-downloadable from Tardis (or no probe needed for non-L2); `✗` = missing AND not free on Tardis.

## C. Action plan for v2 dataset expansion

1. Download the 0 L2 files marked free above (~0.0 GiB estimated).
2. Re-compute the regime table over all available dates → `OKX_EXPANDED_REGIME_TABLE_FOR_SCORE_V2.md`.
3. Select ≥12 candidate dates for v2 full-day replay → `OKX_SCORE_V2_CANDIDATE_DATES.json`.
4. Stop and ask for confirmation before launching the v2 full-day chain — estimated runtime is published in step 5 of the task brief.

## D. What this inventory does NOT do

- It does not score zones (v1 is archived).
- It does not start a backtest.
- It does not pay for any non-free Tardis dates.
- It does not change strategy thresholds.

Companion JSON: `reports/OKX_DATASET_INVENTORY_FOR_SCORE_V2.json`