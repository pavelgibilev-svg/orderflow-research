# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTC-USDT-SWAP
- **Exchange:** okex-swap
- **Date (UTC):** 2026-03-20
- **Replay duration:** 5963.9s
- **Rows processed:** L2=127 569 777  trades=4 649 344  other=0

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 34 |
| LONG / SHORT | 14 / 20 |
| Triggered | 16 |
| Reached target | 0 |
| Failed by timeout | 16 |
| Invalidated before trigger | 17 |
| Expired (formation aged out) | 0 |
| No trigger by end of day | 1 |
| Hit rate among triggered | 0.00% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 0.00% | 0.00% | 1200 |
| 8h | 0.31% | 6.98% | 960 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTC-USDT-SWAP-LONG-1773988237000-17 | LONG | 2026-03-20T07:34:00.000Z | 70624.05 | 72036.53 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1773977273000-11 | SHORT | 2026-03-20T06:20:06.000Z | 70402.05 | 68994.01 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-LONG-1773967549000-4 | LONG | 2026-03-20T01:02:16.000Z | 70332.55 | 71739.20 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-LONG-1773967888000-5 | LONG | 2026-03-20T01:02:18.000Z | 70354.35 | 71761.44 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1773968838000-6 | SHORT | 2026-03-20T02:34:32.000Z | 70055.45 | 68654.34 | RESOLVED_FAILED | - |

## Move clustering accounting

Pure post-processing. Two RESOLVED_REACHED zones share a `uniqueMoveId` when they are the same direction and their `[triggerTs, reachedAt]` windows overlap or sit within `120` minutes of each other.

| Metric | Value |
|---|---|
| Move clustering enabled | yes |
| Reached zones (raw) | 0 |
| Unique reached moves | 0 |
| Duplicate move credits | 0 |
| Raw triggered hit rate | 0.00% |
| **Unique-move adjusted hit rate** | **0.00%** |

> The **unique-move-adjusted hit rate** is the honest headline number. The raw rate is kept only as a diagnostic — it counts every triggered zone that reached the target separately, even when several of them rode the same multi-hour directional move at progressively different price bands.

## Deduplication accounting

- Deduplication enabled: **yes**
- Cooldown after resolve: **30 min**
- Duplicate same-direction candidates suppressed during this run: **11484**
- Suppressions by reason:
  - `active_open`: 6727
  - `active_triggered`: 4757

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
