# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTC-USDT-SWAP
- **Exchange:** okex-swap
- **Date (UTC):** 2026-03-14
- **Replay duration:** 1417.0s
- **Rows processed:** L2=59 890 293  trades=1 773 731  other=0

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 16 |
| LONG / SHORT | 8 / 8 |
| Triggered | 12 |
| Reached target | 0 |
| Failed by timeout | 12 |
| Invalidated before trigger | 4 |
| Expired (formation aged out) | 0 |
| No trigger by end of day | 0 |
| Hit rate among triggered | 0.00% |

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
| BTC-USDT-SWAP-SHORT-1773446937000-1 | SHORT | 2026-03-14T00:43:40.000Z | 70627.65 | 69215.10 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-LONG-1773484455000-16 | LONG | 2026-03-14T15:02:50.000Z | 70629.95 | 72042.55 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1773450492000-5 | SHORT | 2026-03-14T01:35:36.000Z | 70603.55 | 69191.48 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1773449958000-4 | SHORT | 2026-03-14T01:38:01.000Z | 70550.05 | 69139.05 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1773458412000-7 | SHORT | 2026-03-14T06:40:32.000Z | 70288.75 | 68882.98 | RESOLVED_FAILED | - |

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
- Duplicate same-direction candidates suppressed during this run: **17150**
- Suppressions by reason:
  - `active_open`: 7367
  - `active_triggered`: 9783

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
