# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTC-USDT-SWAP
- **Exchange:** okex-swap
- **Date (UTC):** 2026-05-23
- **Replay duration:** 2191.2s
- **Rows processed:** L2=67 987 778  trades=2 412 532  other=0

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 19 |
| LONG / SHORT | 13 / 6 |
| Triggered | 11 |
| Reached target | 0 |
| Failed by timeout | 11 |
| Invalidated before trigger | 5 |
| Expired (formation aged out) | 1 |
| No trigger by end of day | 2 |
| Hit rate among triggered | 0.00% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 0.00% | 0.00% | 1200 |
| 8h | 0.00% | 14.06% | 960 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTC-USDT-SWAP-LONG-1779537311000-14 | LONG | 2026-05-23T13:01:02.000Z | 74865.95 | 76363.27 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-LONG-1779544826000-16 | LONG | 2026-05-23T14:36:48.000Z | 75409.20 | 76917.38 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-LONG-1779542109000-15 | LONG | 2026-05-23T13:48:29.000Z | 75043.35 | 76544.22 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1779507906000-9 | SHORT | 2026-05-23T04:19:36.000Z | 75541.05 | 74030.23 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1779494401000-1 | SHORT | 2026-05-23T00:14:11.000Z | 75425.05 | 73916.55 | RESOLVED_FAILED | - |

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
- Duplicate same-direction candidates suppressed during this run: **12160**
- Suppressions by reason:
  - `active_open`: 8844
  - `active_triggered`: 2935
  - `cooldown`: 381

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Warnings

- Encountered 28800 feature ticks with quality flags.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
