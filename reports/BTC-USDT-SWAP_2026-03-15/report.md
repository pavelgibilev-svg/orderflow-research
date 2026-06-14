# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTC-USDT-SWAP
- **Exchange:** okex-swap
- **Date (UTC):** 2026-03-15
- **Replay duration:** 2003.4s
- **Rows processed:** L2=73 669 734  trades=2 452 703  other=0

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 36 |
| LONG / SHORT | 17 / 19 |
| Triggered | 16 |
| Reached target | 8 |
| Failed by timeout | 8 |
| Invalidated before trigger | 17 |
| Expired (formation aged out) | 0 |
| No trigger by end of day | 3 |
| Hit rate among triggered | 50.00% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 5.58% | 0.00% | 1200 |
| 8h | 6.98% | 0.00% | 960 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTC-USDT-SWAP-LONG-1773533193000-1 | LONG | 2026-03-15T02:01:43.000Z | 71179.95 | 72603.55 | RESOLVED_REACHED | 24h |
| BTC-USDT-SWAP-LONG-1773533645000-2 | LONG | 2026-03-15T00:28:20.000Z | 71119.75 | 72542.15 | RESOLVED_REACHED | 24h |
| BTC-USDT-SWAP-SHORT-1773567808000-19 | SHORT | 2026-03-15T12:41:56.000Z | 71585.45 | 70153.74 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-LONG-1773543685000-13 | LONG | 2026-03-15T04:06:43.000Z | 71559.95 | 72991.15 | RESOLVED_REACHED | 24h |
| BTC-USDT-SWAP-SHORT-1773535598000-4 | SHORT | 2026-03-15T01:10:38.000Z | 70888.05 | 69470.29 | RESOLVED_FAILED | - |

## Move clustering accounting

Pure post-processing. Two RESOLVED_REACHED zones share a `uniqueMoveId` when they are the same direction and their `[triggerTs, reachedAt]` windows overlap or sit within `120` minutes of each other.

| Metric | Value |
|---|---|
| Move clustering enabled | yes |
| Reached zones (raw) | 8 |
| Unique reached moves | 1 |
| Duplicate move credits | 7 |
| Raw triggered hit rate | 50.00% |
| **Unique-move adjusted hit rate** | **6.25%** |

| Move | Dir | Size | Primary zone | Members |
|---|---|---|---|---|
| 1 | LONG | 8 | `BTC-USDT-SWAP-LONG-1773533645000-2` | BTC-USDT-SWAP-LONG-1773533645000-2, BTC-USDT-SWAP-LONG-1773538526000-7, BTC-USDT-SWAP-LONG-1773537312000-5, BTC-USDT-SWAP-LONG-1773533193000-1, BTC-USDT-SWAP-LONG-1773540489000-9, BTC-USDT-SWAP-LONG-1773543685000-13, BTC-USDT-SWAP-LONG-1773542181000-11, BTC-USDT-SWAP-LONG-1773553188000-16 |

> The **unique-move-adjusted hit rate** is the honest headline number. The raw rate is kept only as a diagnostic — it counts every triggered zone that reached the target separately, even when several of them rode the same multi-hour directional move at progressively different price bands.

## Deduplication accounting

- Deduplication enabled: **yes**
- Cooldown after resolve: **30 min**
- Duplicate same-direction candidates suppressed during this run: **14315**
- Suppressions by reason:
  - `active_open`: 9769
  - `active_triggered`: 4546

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
