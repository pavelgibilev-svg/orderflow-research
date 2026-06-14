# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTC-USDT-SWAP
- **Exchange:** okex-swap
- **Date (UTC):** 2026-03-23
- **Replay duration:** 6249.0s
- **Rows processed:** L2=159 830 400  trades=7 320 153  other=0

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 37 |
| LONG / SHORT | 19 / 18 |
| Triggered | 24 |
| Reached target | 8 |
| Failed by timeout | 16 |
| Invalidated before trigger | 13 |
| Expired (formation aged out) | 0 |
| No trigger by end of day | 0 |
| Hit rate among triggered | 33.33% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 24.08% | 2.42% | 1200 |
| 8h | 55.21% | 3.02% | 960 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTC-USDT-SWAP-SHORT-1774224201000-1 | SHORT | 2026-03-23T00:36:11.000Z | 67676.35 | 66322.82 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1774224316000-2 | SHORT | 2026-03-23T00:36:11.000Z | 67676.35 | 66322.82 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-LONG-1774230340000-9 | LONG | 2026-03-23T02:26:25.000Z | 68138.85 | 69501.63 | RESOLVED_REACHED | 24h |
| BTC-USDT-SWAP-LONG-1774228797000-8 | LONG | 2026-03-23T02:31:01.000Z | 68198.35 | 69562.32 | RESOLVED_REACHED | 24h |
| BTC-USDT-SWAP-SHORT-1774236610000-13 | SHORT | 2026-03-23T04:02:50.000Z | 68029.45 | 66668.86 | RESOLVED_FAILED | - |

## Move clustering accounting

Pure post-processing. Two RESOLVED_REACHED zones share a `uniqueMoveId` when they are the same direction and their `[triggerTs, reachedAt]` windows overlap or sit within `120` minutes of each other.

| Metric | Value |
|---|---|
| Move clustering enabled | yes |
| Reached zones (raw) | 8 |
| Unique reached moves | 1 |
| Duplicate move credits | 7 |
| Raw triggered hit rate | 33.33% |
| **Unique-move adjusted hit rate** | **4.17%** |

| Move | Dir | Size | Primary zone | Members |
|---|---|---|---|---|
| 1 | LONG | 8 | `BTC-USDT-SWAP-LONG-1774228686000-7` | BTC-USDT-SWAP-LONG-1774228686000-7, BTC-USDT-SWAP-LONG-1774230340000-9, BTC-USDT-SWAP-LONG-1774228797000-8, BTC-USDT-SWAP-LONG-1774233261000-11, BTC-USDT-SWAP-LONG-1774237251000-14, BTC-USDT-SWAP-LONG-1774226586000-5, BTC-USDT-SWAP-LONG-1774226641000-6, BTC-USDT-SWAP-LONG-1774240874000-15 |

> The **unique-move-adjusted hit rate** is the honest headline number. The raw rate is kept only as a diagnostic — it counts every triggered zone that reached the target separately, even when several of them rode the same multi-hour directional move at progressively different price bands.

## Deduplication accounting

- Deduplication enabled: **yes**
- Cooldown after resolve: **30 min**
- Duplicate same-direction candidates suppressed during this run: **11431**
- Suppressions by reason:
  - `active_open`: 4998
  - `active_triggered`: 6433

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
