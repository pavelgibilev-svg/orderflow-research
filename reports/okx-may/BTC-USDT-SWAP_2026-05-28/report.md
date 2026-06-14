# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTC-USDT-SWAP
- **Exchange:** okex-swap
- **Date (UTC):** 2026-05-28
- **Replay duration:** 3021.4s
- **Rows processed:** L2=91 797 826  trades=3 446 177  other=0

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 27 |
| LONG / SHORT | 11 / 16 |
| Triggered | 18 |
| Reached target | 5 |
| Failed by timeout | 13 |
| Invalidated before trigger | 9 |
| Expired (formation aged out) | 0 |
| No trigger by end of day | 0 |
| Hit rate among triggered | 27.78% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 0.00% | 15.25% | 1200 |
| 8h | 0.00% | 48.65% | 960 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTC-USDT-SWAP-SHORT-1779943598000-15 | SHORT | 2026-05-28T05:18:42.000Z | 72898.05 | 71440.09 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1779933152000-7 | SHORT | 2026-05-28T02:21:51.000Z | 74160.05 | 72676.85 | RESOLVED_REACHED | 24h |
| BTC-USDT-SWAP-SHORT-1779935203000-8 | SHORT | 2026-05-28T03:16:38.000Z | 74062.15 | 72580.91 | RESOLVED_REACHED | 24h |
| BTC-USDT-SWAP-SHORT-1779978734000-27 | SHORT | 2026-05-28T14:44:46.000Z | 72799.25 | 71343.26 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1779926787000-2 | SHORT | 2026-05-28T01:17:54.000Z | 74146.85 | 72663.91 | RESOLVED_REACHED | 24h |

## Move clustering accounting

Pure post-processing. Two RESOLVED_REACHED zones share a `uniqueMoveId` when they are the same direction and their `[triggerTs, reachedAt]` windows overlap or sit within `120` minutes of each other.

| Metric | Value |
|---|---|
| Move clustering enabled | yes |
| Reached zones (raw) | 5 |
| Unique reached moves | 1 |
| Duplicate move credits | 4 |
| Raw triggered hit rate | 27.78% |
| **Unique-move adjusted hit rate** | **5.56%** |

| Move | Dir | Size | Primary zone | Members |
|---|---|---|---|---|
| 1 | SHORT | 5 | `BTC-USDT-SWAP-SHORT-1779926422000-1` | BTC-USDT-SWAP-SHORT-1779926422000-1, BTC-USDT-SWAP-SHORT-1779926787000-2, BTC-USDT-SWAP-SHORT-1779933054000-6, BTC-USDT-SWAP-SHORT-1779933152000-7, BTC-USDT-SWAP-SHORT-1779935203000-8 |

> The **unique-move-adjusted hit rate** is the honest headline number. The raw rate is kept only as a diagnostic — it counts every triggered zone that reached the target separately, even when several of them rode the same multi-hour directional move at progressively different price bands.

## Deduplication accounting

- Deduplication enabled: **yes**
- Cooldown after resolve: **30 min**
- Duplicate same-direction candidates suppressed during this run: **9019**
- Suppressions by reason:
  - `active_open`: 7562
  - `active_triggered`: 1457

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Warnings

- Encountered 28800 feature ticks with quality flags.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
