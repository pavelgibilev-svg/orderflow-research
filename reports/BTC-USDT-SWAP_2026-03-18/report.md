# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTC-USDT-SWAP
- **Exchange:** okex-swap
- **Date (UTC):** 2026-03-18
- **Replay duration:** 4472.6s
- **Rows processed:** L2=117 784 810  trades=4 695 585  other=0

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 57 |
| LONG / SHORT | 21 / 36 |
| Triggered | 33 |
| Reached target | 12 |
| Failed by timeout | 21 |
| Invalidated before trigger | 20 |
| Expired (formation aged out) | 0 |
| No trigger by end of day | 4 |
| Hit rate among triggered | 36.36% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 0.00% | 25.92% | 1200 |
| 8h | 0.00% | 67.40% | 960 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTC-USDT-SWAP-LONG-1773793754000-4 | LONG | 2026-03-18T01:33:57.000Z | 74073.45 | 75554.92 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1773861038000-49 | SHORT | 2026-03-18T19:33:09.000Z | 71189.65 | 69765.86 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1773861090000-50 | SHORT | 2026-03-18T19:33:32.000Z | 71156.15 | 69733.03 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1773837926000-31 | SHORT | 2026-03-18T13:01:23.000Z | 72164.65 | 70721.36 | RESOLVED_REACHED | 8h |
| BTC-USDT-SWAP-SHORT-1773792030000-1 | SHORT | 2026-03-18T00:23:51.000Z | 73719.95 | 72245.55 | RESOLVED_REACHED | 24h |

## Move clustering accounting

Pure post-processing. Two RESOLVED_REACHED zones share a `uniqueMoveId` when they are the same direction and their `[triggerTs, reachedAt]` windows overlap or sit within `120` minutes of each other.

| Metric | Value |
|---|---|
| Move clustering enabled | yes |
| Reached zones (raw) | 12 |
| Unique reached moves | 1 |
| Duplicate move credits | 11 |
| Raw triggered hit rate | 36.36% |
| **Unique-move adjusted hit rate** | **3.03%** |

| Move | Dir | Size | Primary zone | Members |
|---|---|---|---|---|
| 1 | SHORT | 12 | `BTC-USDT-SWAP-SHORT-1773792030000-1` | BTC-USDT-SWAP-SHORT-1773792030000-1, BTC-USDT-SWAP-SHORT-1773806704000-17, BTC-USDT-SWAP-SHORT-1773808660000-19, BTC-USDT-SWAP-SHORT-1773802038000-13, BTC-USDT-SWAP-SHORT-1773814999000-20, BTC-USDT-SWAP-SHORT-1773804588000-14, BTC-USDT-SWAP-SHORT-1773834431000-26, BTC-USDT-SWAP-SHORT-1773835688000-27, BTC-USDT-SWAP-SHORT-1773836170000-28, BTC-USDT-SWAP-SHORT-1773834370000-25, BTC-USDT-SWAP-SHORT-1773837926000-31, BTC-USDT-SWAP-SHORT-1773837656000-30 |

> The **unique-move-adjusted hit rate** is the honest headline number. The raw rate is kept only as a diagnostic — it counts every triggered zone that reached the target separately, even when several of them rode the same multi-hour directional move at progressively different price bands.

## Deduplication accounting

- Deduplication enabled: **yes**
- Cooldown after resolve: **30 min**
- Duplicate same-direction candidates suppressed during this run: **12056**
- Suppressions by reason:
  - `active_open`: 6637
  - `active_triggered`: 5419

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Warnings

- Encountered 1 feature ticks with quality flags.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
