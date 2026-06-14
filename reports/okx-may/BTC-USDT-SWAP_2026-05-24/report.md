# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTC-USDT-SWAP
- **Exchange:** okex-swap
- **Date (UTC):** 2026-05-24
- **Replay duration:** 1721.1s
- **Rows processed:** L2=59 854 620  trades=2 182 860  other=0

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 25 |
| LONG / SHORT | 12 / 13 |
| Triggered | 11 |
| Reached target | 0 |
| Failed by timeout | 11 |
| Invalidated before trigger | 10 |
| Expired (formation aged out) | 0 |
| No trigger by end of day | 4 |
| Hit rate among triggered | 0.00% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 11.50% | 0.00% | 1200 |
| 8h | 20.21% | 0.00% | 960 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTC-USDT-SWAP-LONG-1779584281000-5 | LONG | 2026-05-24T03:11:24.000Z | 76955.55 | 78494.66 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1779630050000-19 | SHORT | 2026-05-24T13:54:36.000Z | 76811.25 | 75275.02 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1779620871000-15 | SHORT | 2026-05-24T12:11:46.000Z | 77139.65 | 75596.86 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1779631417000-20 | SHORT | 2026-05-24T14:12:17.000Z | 76528.15 | 74997.59 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1779629292000-18 | SHORT | 2026-05-24T13:54:09.000Z | 76768.65 | 75233.28 | RESOLVED_FAILED | - |

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
- Duplicate same-direction candidates suppressed during this run: **11446**
- Suppressions by reason:
  - `active_open`: 8725
  - `active_triggered`: 2721

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Warnings

- Encountered 28800 feature ticks with quality flags.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
