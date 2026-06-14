# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTC-USDT-SWAP
- **Exchange:** okex-swap
- **Date (UTC):** 2024-10-01
- **Replay duration:** 5201.0s
- **Rows processed:** L2=124 227 505  trades=2 190 002  other=0

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 38 |
| LONG / SHORT | 19 / 19 |
| Triggered | 20 |
| Reached target | 13 |
| Failed by timeout | 7 |
| Invalidated before trigger | 17 |
| Expired (formation aged out) | 0 |
| No trigger by end of day | 1 |
| Hit rate among triggered | 65.00% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 0.08% | 49.00% | 1200 |
| 8h | 0.00% | 62.19% | 960 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTC-USDT-SWAP-SHORT-1727784411000-19 | SHORT | 2024-10-01T12:44:50.000Z | 63625.55 | 62353.04 | RESOLVED_REACHED | 4h |
| BTC-USDT-SWAP-SHORT-1727809459000-32 | SHORT | 2024-10-01T19:17:36.000Z | 61677.55 | 60444.00 | RESOLVED_REACHED | 4h |
| BTC-USDT-SWAP-SHORT-1727763869000-13 | SHORT | 2024-10-01T08:42:26.000Z | 63873.15 | 62595.69 | RESOLVED_REACHED | 8h |
| BTC-USDT-SWAP-SHORT-1727812179000-34 | SHORT | 2024-10-01T20:05:57.000Z | 61612.45 | 60380.20 | RESOLVED_REACHED | 4h |
| BTC-USDT-SWAP-SHORT-1727812759000-35 | SHORT | 2024-10-01T20:35:48.000Z | 60555.05 | 59343.95 | RESOLVED_FAILED | - |

## Move clustering accounting

Pure post-processing. Two RESOLVED_REACHED zones share a `uniqueMoveId` when they are the same direction and their `[triggerTs, reachedAt]` windows overlap or sit within `120` minutes of each other.

| Metric | Value |
|---|---|
| Move clustering enabled | yes |
| Reached zones (raw) | 13 |
| Unique reached moves | 1 |
| Duplicate move credits | 12 |
| Raw triggered hit rate | 65.00% |
| **Unique-move adjusted hit rate** | **5.00%** |

| Move | Dir | Size | Primary zone | Members |
|---|---|---|---|---|
| 1 | SHORT | 13 | `BTC-USDT-SWAP-SHORT-1727757424000-12` | BTC-USDT-SWAP-SHORT-1727757424000-12, BTC-USDT-SWAP-SHORT-1727763869000-13, BTC-USDT-SWAP-SHORT-1727768497000-16, BTC-USDT-SWAP-SHORT-1727768554000-17, BTC-USDT-SWAP-SHORT-1727784411000-19, BTC-USDT-SWAP-SHORT-1727787209000-20, BTC-USDT-SWAP-SHORT-1727789148000-23, BTC-USDT-SWAP-SHORT-1727789504000-24, BTC-USDT-SWAP-SHORT-1727796453000-26, BTC-USDT-SWAP-SHORT-1727799990000-28, BTC-USDT-SWAP-SHORT-1727809600000-33, BTC-USDT-SWAP-SHORT-1727809459000-32, BTC-USDT-SWAP-SHORT-1727812179000-34 |

> The **unique-move-adjusted hit rate** is the honest headline number. The raw rate is kept only as a diagnostic — it counts every triggered zone that reached the target separately, even when several of them rode the same multi-hour directional move at progressively different price bands.

## Deduplication accounting

- Deduplication enabled: **yes**
- Cooldown after resolve: **30 min**
- Duplicate same-direction candidates suppressed during this run: **10744**
- Suppressions by reason:
  - `active_open`: 8065
  - `active_triggered`: 2679

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
