# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTC-USDT-SWAP
- **Exchange:** okex-swap
- **Date (UTC):** 2026-03-06
- **Replay duration:** 6515.1s
- **Rows processed:** L2=153 629 812  trades=5 417 574  other=0

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 43 |
| LONG / SHORT | 24 / 19 |
| Triggered | 18 |
| Reached target | 8 |
| Failed by timeout | 10 |
| Invalidated before trigger | 22 |
| Expired (formation aged out) | 0 |
| No trigger by end of day | 3 |
| Hit rate among triggered | 44.44% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 0.00% | 20.25% | 1200 |
| 8h | 0.00% | 50.31% | 960 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTC-USDT-SWAP-SHORT-1772755231000-1 | SHORT | 2026-03-06T00:51:19.000Z | 70757.05 | 69341.91 | RESOLVED_REACHED | 24h |
| BTC-USDT-SWAP-SHORT-1772813847000-35 | SHORT | 2026-03-06T17:32:44.000Z | 68072.25 | 66710.80 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1772756173000-3 | SHORT | 2026-03-06T01:11:13.000Z | 70800.35 | 69384.34 | RESOLVED_REACHED | 24h |
| BTC-USDT-SWAP-SHORT-1772775022000-15 | SHORT | 2026-03-06T05:35:11.000Z | 70218.35 | 68813.98 | RESOLVED_REACHED | 24h |
| BTC-USDT-SWAP-LONG-1772776333000-19 | LONG | 2026-03-06T06:43:45.000Z | 70651.05 | 72064.07 | RESOLVED_FAILED | - |

## Move clustering accounting

Pure post-processing. Two RESOLVED_REACHED zones share a `uniqueMoveId` when they are the same direction and their `[triggerTs, reachedAt]` windows overlap or sit within `120` minutes of each other.

| Metric | Value |
|---|---|
| Move clustering enabled | yes |
| Reached zones (raw) | 8 |
| Unique reached moves | 1 |
| Duplicate move credits | 7 |
| Raw triggered hit rate | 44.44% |
| **Unique-move adjusted hit rate** | **5.56%** |

| Move | Dir | Size | Primary zone | Members |
|---|---|---|---|---|
| 1 | SHORT | 8 | `BTC-USDT-SWAP-SHORT-1772755231000-1` | BTC-USDT-SWAP-SHORT-1772755231000-1, BTC-USDT-SWAP-SHORT-1772756173000-3, BTC-USDT-SWAP-SHORT-1772755356000-2, BTC-USDT-SWAP-SHORT-1772762906000-9, BTC-USDT-SWAP-SHORT-1772761567000-8, BTC-USDT-SWAP-SHORT-1772760332000-7, BTC-USDT-SWAP-SHORT-1772775022000-15, BTC-USDT-SWAP-SHORT-1772798800000-24 |

> The **unique-move-adjusted hit rate** is the honest headline number. The raw rate is kept only as a diagnostic — it counts every triggered zone that reached the target separately, even when several of them rode the same multi-hour directional move at progressively different price bands.

## Deduplication accounting

- Deduplication enabled: **yes**
- Cooldown after resolve: **30 min**
- Duplicate same-direction candidates suppressed during this run: **12361**
- Suppressions by reason:
  - `active_open`: 8344
  - `active_triggered`: 4017

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
