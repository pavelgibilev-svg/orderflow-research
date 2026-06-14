# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTC-USDT-SWAP
- **Exchange:** okex-swap
- **Date (UTC):** 2026-03-09
- **Replay duration:** 7468.8s
- **Rows processed:** L2=147 707 596  trades=5 956 994  other=0

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 48 |
| LONG / SHORT | 23 / 25 |
| Triggered | 30 |
| Reached target | 9 |
| Failed by timeout | 21 |
| Invalidated before trigger | 15 |
| Expired (formation aged out) | 1 |
| No trigger by end of day | 2 |
| Hit rate among triggered | 30.00% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 24.50% | 0.00% | 1200 |
| 8h | 66.04% | 0.00% | 960 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTC-USDT-SWAP-LONG-1773063517000-30 | LONG | 2026-03-09T13:46:12.000Z | 69173.45 | 70556.92 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-LONG-1773017505000-4 | LONG | 2026-03-09T01:35:31.000Z | 66583.75 | 67915.43 | RESOLVED_REACHED | 8h |
| BTC-USDT-SWAP-LONG-1773063532000-31 | LONG | 2026-03-09T13:46:17.000Z | 69064.15 | 70445.43 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-LONG-1773026901000-6 | LONG | 2026-03-09T05:34:12.000Z | 67589.95 | 68941.75 | RESOLVED_REACHED | 24h |
| BTC-USDT-SWAP-LONG-1773027138000-7 | LONG | 2026-03-09T05:34:30.000Z | 67589.45 | 68941.24 | RESOLVED_REACHED | 24h |

## Move clustering accounting

Pure post-processing. Two RESOLVED_REACHED zones share a `uniqueMoveId` when they are the same direction and their `[triggerTs, reachedAt]` windows overlap or sit within `120` minutes of each other.

| Metric | Value |
|---|---|
| Move clustering enabled | yes |
| Reached zones (raw) | 9 |
| Unique reached moves | 1 |
| Duplicate move credits | 8 |
| Raw triggered hit rate | 30.00% |
| **Unique-move adjusted hit rate** | **3.33%** |

| Move | Dir | Size | Primary zone | Members |
|---|---|---|---|---|
| 1 | LONG | 9 | `BTC-USDT-SWAP-LONG-1773017505000-4` | BTC-USDT-SWAP-LONG-1773017505000-4, BTC-USDT-SWAP-LONG-1773016156000-3, BTC-USDT-SWAP-LONG-1773028538000-9, BTC-USDT-SWAP-LONG-1773031454000-10, BTC-USDT-SWAP-LONG-1773027249000-8, BTC-USDT-SWAP-LONG-1773026901000-6, BTC-USDT-SWAP-LONG-1773027138000-7, BTC-USDT-SWAP-LONG-1773045274000-22, BTC-USDT-SWAP-LONG-1773053059000-25 |

> The **unique-move-adjusted hit rate** is the honest headline number. The raw rate is kept only as a diagnostic — it counts every triggered zone that reached the target separately, even when several of them rode the same multi-hour directional move at progressively different price bands.

## Deduplication accounting

- Deduplication enabled: **yes**
- Cooldown after resolve: **30 min**
- Duplicate same-direction candidates suppressed during this run: **9263**
- Suppressions by reason:
  - `active_open`: 6261
  - `active_triggered`: 2878
  - `cooldown`: 124

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
