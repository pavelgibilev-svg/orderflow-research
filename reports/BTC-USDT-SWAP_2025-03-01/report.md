# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTC-USDT-SWAP
- **Exchange:** okex-swap
- **Date (UTC):** 2025-03-01
- **Replay duration:** 6367.0s
- **Rows processed:** L2=143 799 862  trades=1 910 203  other=0

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 32 |
| LONG / SHORT | 17 / 15 |
| Triggered | 19 |
| Reached target | 2 |
| Failed by timeout | 17 |
| Invalidated before trigger | 11 |
| Expired (formation aged out) | 0 |
| No trigger by end of day | 2 |
| Hit rate among triggered | 10.53% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 9.83% | 0.50% | 1200 |
| 8h | 16.56% | 3.23% | 960 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTC-USDT-SWAP-LONG-1740788654000-3 | LONG | 2025-03-01T01:46:49.000Z | 84544.25 | 86235.13 | RESOLVED_REACHED | 4h |
| BTC-USDT-SWAP-LONG-1740860259000-28 | LONG | 2025-03-01T21:57:42.000Z | 86121.95 | 87844.39 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1740807714000-19 | SHORT | 2025-03-01T05:51:23.000Z | 85677.05 | 83963.51 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1740794181000-7 | SHORT | 2025-03-01T02:02:21.000Z | 84380.05 | 82692.45 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-LONG-1740796707000-8 | LONG | 2025-03-01T04:12:27.000Z | 85905.55 | 87623.66 | RESOLVED_FAILED | - |

## Move clustering accounting

Pure post-processing. Two RESOLVED_REACHED zones share a `uniqueMoveId` when they are the same direction and their `[triggerTs, reachedAt]` windows overlap or sit within `120` minutes of each other.

| Metric | Value |
|---|---|
| Move clustering enabled | yes |
| Reached zones (raw) | 2 |
| Unique reached moves | 1 |
| Duplicate move credits | 1 |
| Raw triggered hit rate | 10.53% |
| **Unique-move adjusted hit rate** | **5.26%** |

| Move | Dir | Size | Primary zone | Members |
|---|---|---|---|---|
| 1 | LONG | 2 | `BTC-USDT-SWAP-LONG-1740789333000-4` | BTC-USDT-SWAP-LONG-1740789333000-4, BTC-USDT-SWAP-LONG-1740788654000-3 |

> The **unique-move-adjusted hit rate** is the honest headline number. The raw rate is kept only as a diagnostic — it counts every triggered zone that reached the target separately, even when several of them rode the same multi-hour directional move at progressively different price bands.

## Deduplication accounting

- Deduplication enabled: **yes**
- Cooldown after resolve: **30 min**
- Duplicate same-direction candidates suppressed during this run: **12739**
- Suppressions by reason:
  - `active_open`: 8240
  - `active_triggered`: 4499

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
