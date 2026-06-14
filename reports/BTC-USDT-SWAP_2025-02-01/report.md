# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTC-USDT-SWAP
- **Exchange:** okex-swap
- **Date (UTC):** 2025-02-01
- **Replay duration:** 4143.7s
- **Rows processed:** L2=99 302 427  trades=1 156 904  other=0

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 34 |
| LONG / SHORT | 18 / 16 |
| Triggered | 20 |
| Reached target | 3 |
| Failed by timeout | 17 |
| Invalidated before trigger | 11 |
| Expired (formation aged out) | 0 |
| No trigger by end of day | 3 |
| Hit rate among triggered | 15.00% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 0.00% | 0.00% | 1200 |
| 8h | 0.00% | 0.00% | 960 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTC-USDT-SWAP-SHORT-1738401689000-13 | SHORT | 2025-02-01T09:36:44.000Z | 101709.15 | 99674.97 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-LONG-1738451924000-34 | LONG | 2025-02-01T23:32:06.000Z | 100663.85 | 102677.13 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1738369472000-4 | SHORT | 2025-02-01T04:09:26.000Z | 102136.15 | 100093.43 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1738449732000-29 | SHORT | 2025-02-01T22:54:58.000Z | 100555.05 | 98543.95 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1738442428000-25 | SHORT | 2025-02-01T20:47:11.000Z | 101045.95 | 99025.03 | RESOLVED_FAILED | - |

## Move clustering accounting

Pure post-processing. Two RESOLVED_REACHED zones share a `uniqueMoveId` when they are the same direction and their `[triggerTs, reachedAt]` windows overlap or sit within `120` minutes of each other.

| Metric | Value |
|---|---|
| Move clustering enabled | yes |
| Reached zones (raw) | 3 |
| Unique reached moves | 1 |
| Duplicate move credits | 2 |
| Raw triggered hit rate | 15.00% |
| **Unique-move adjusted hit rate** | **5.00%** |

| Move | Dir | Size | Primary zone | Members |
|---|---|---|---|---|
| 1 | SHORT | 3 | `BTC-USDT-SWAP-SHORT-1738373587000-8` | BTC-USDT-SWAP-SHORT-1738373587000-8, BTC-USDT-SWAP-SHORT-1738372513000-6, BTC-USDT-SWAP-SHORT-1738370485000-5 |

> The **unique-move-adjusted hit rate** is the honest headline number. The raw rate is kept only as a diagnostic — it counts every triggered zone that reached the target separately, even when several of them rode the same multi-hour directional move at progressively different price bands.

## Deduplication accounting

- Deduplication enabled: **yes**
- Cooldown after resolve: **30 min**
- Duplicate same-direction candidates suppressed during this run: **14091**
- Suppressions by reason:
  - `active_open`: 9122
  - `active_triggered`: 4952
  - `cooldown`: 17

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
