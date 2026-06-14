# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTC-USDT-SWAP
- **Exchange:** okex-swap
- **Date (UTC):** 2026-04-01
- **Replay duration:** 3513.1s
- **Rows processed:** L2=110 176 675  trades=3 920 423  other=567

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 30 |
| LONG / SHORT | 17 / 13 |
| Triggered | 21 |
| Reached target | 1 |
| Failed by timeout | 20 |
| Invalidated before trigger | 9 |
| Expired (formation aged out) | 0 |
| No trigger by end of day | 0 |
| Hit rate among triggered | 4.76% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 4.50% | 0.00% | 1200 |
| 8h | 13.65% | 0.00% | 960 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTC-USDT-SWAP-SHORT-1775025586000-18 | SHORT | 2026-04-01T13:44:28.000Z | 68057.95 | 66696.79 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1775024985000-16 | SHORT | 2026-04-01T09:10:14.000Z | 68438.15 | 67069.39 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-LONG-1775001967000-1 | LONG | 2026-04-01T00:51:04.000Z | 68268.95 | 69634.33 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-LONG-1775021507000-13 | LONG | 2026-04-01T06:20:02.000Z | 68768.15 | 70143.51 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-LONG-1775035482000-24 | LONG | 2026-04-01T12:44:58.000Z | 68674.15 | 70047.63 | RESOLVED_FAILED | - |

## Move clustering accounting

Pure post-processing. Two RESOLVED_REACHED zones share a `uniqueMoveId` when they are the same direction and their `[triggerTs, reachedAt]` windows overlap or sit within `120` minutes of each other.

| Metric | Value |
|---|---|
| Move clustering enabled | yes |
| Reached zones (raw) | 1 |
| Unique reached moves | 1 |
| Duplicate move credits | 0 |
| Raw triggered hit rate | 4.76% |
| **Unique-move adjusted hit rate** | **4.76%** |

| Move | Dir | Size | Primary zone | Members |
|---|---|---|---|---|
| 1 | LONG | 1 | `BTC-USDT-SWAP-LONG-1775009554000-9` | BTC-USDT-SWAP-LONG-1775009554000-9 |

> The **unique-move-adjusted hit rate** is the honest headline number. The raw rate is kept only as a diagnostic — it counts every triggered zone that reached the target separately, even when several of them rode the same multi-hour directional move at progressively different price bands.

## Deduplication accounting

- Deduplication enabled: **yes**
- Cooldown after resolve: **30 min**
- Duplicate same-direction candidates suppressed during this run: **12987**
- Suppressions by reason:
  - `active_open`: 4322
  - `active_triggered`: 8665

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
