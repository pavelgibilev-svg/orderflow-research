# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTC-USDT-SWAP
- **Exchange:** okex-swap
- **Date (UTC):** 2024-05-01
- **Replay duration:** 8679.3s
- **Rows processed:** L2=192 068 268  trades=2 958 790  other=0

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 42 |
| LONG / SHORT | 23 / 19 |
| Triggered | 25 |
| Reached target | 14 |
| Failed by timeout | 11 |
| Invalidated before trigger | 13 |
| Expired (formation aged out) | 2 |
| No trigger by end of day | 2 |
| Hit rate among triggered | 56.00% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 26.00% | 34.83% | 1200 |
| 8h | 39.48% | 57.40% | 960 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTC-USDT-SWAP-SHORT-1714528701000-7 | SHORT | 2024-05-01T02:09:20.000Z | 59859.95 | 58662.75 | RESOLVED_REACHED | 8h |
| BTC-USDT-SWAP-SHORT-1714521953000-2 | SHORT | 2024-05-01T00:14:52.000Z | 60664.85 | 59451.55 | RESOLVED_REACHED | 8h |
| BTC-USDT-SWAP-SHORT-1714524563000-5 | SHORT | 2024-05-01T01:09:12.000Z | 59984.75 | 58785.06 | RESOLVED_REACHED | 8h |
| BTC-USDT-SWAP-LONG-1714559283000-23 | LONG | 2024-05-01T12:10:45.000Z | 58035.05 | 59195.75 | RESOLVED_REACHED | 8h |
| BTC-USDT-SWAP-LONG-1714601492000-40 | LONG | 2024-05-01T23:38:21.000Z | 58210.05 | 59374.25 | RESOLVED_FAILED | - |

## Move clustering accounting

Pure post-processing. Two RESOLVED_REACHED zones share a `uniqueMoveId` when they are the same direction and their `[triggerTs, reachedAt]` windows overlap or sit within `120` minutes of each other.

| Metric | Value |
|---|---|
| Move clustering enabled | yes |
| Reached zones (raw) | 14 |
| Unique reached moves | 3 |
| Duplicate move credits | 11 |
| Raw triggered hit rate | 56.00% |
| **Unique-move adjusted hit rate** | **12.00%** |

| Move | Dir | Size | Primary zone | Members |
|---|---|---|---|---|
| 1 | LONG | 7 | `BTC-USDT-SWAP-LONG-1714557145000-20` | BTC-USDT-SWAP-LONG-1714557145000-20, BTC-USDT-SWAP-LONG-1714557118000-19, BTC-USDT-SWAP-LONG-1714561962000-24, BTC-USDT-SWAP-LONG-1714559283000-23, BTC-USDT-SWAP-LONG-1714572596000-29, BTC-USDT-SWAP-LONG-1714583926000-34, BTC-USDT-SWAP-LONG-1714583857000-33 |
| 2 | SHORT | 6 | `BTC-USDT-SWAP-SHORT-1714521953000-2` | BTC-USDT-SWAP-SHORT-1714521953000-2, BTC-USDT-SWAP-SHORT-1714521774000-1, BTC-USDT-SWAP-SHORT-1714524563000-5, BTC-USDT-SWAP-SHORT-1714528276000-6, BTC-USDT-SWAP-SHORT-1714528701000-7, BTC-USDT-SWAP-SHORT-1714528989000-8 |
| 3 | SHORT | 1 | `BTC-USDT-SWAP-SHORT-1714567100000-27` | BTC-USDT-SWAP-SHORT-1714567100000-27 |

> The **unique-move-adjusted hit rate** is the honest headline number. The raw rate is kept only as a diagnostic — it counts every triggered zone that reached the target separately, even when several of them rode the same multi-hour directional move at progressively different price bands.

## Deduplication accounting

- Deduplication enabled: **yes**
- Cooldown after resolve: **30 min**
- Duplicate same-direction candidates suppressed during this run: **7599**
- Suppressions by reason:
  - `active_open`: 4397
  - `active_triggered`: 3130
  - `cooldown`: 72

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Warnings

- Encountered 1 feature ticks with quality flags.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
