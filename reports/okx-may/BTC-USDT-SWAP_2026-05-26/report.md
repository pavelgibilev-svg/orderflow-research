# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTC-USDT-SWAP
- **Exchange:** okex-swap
- **Date (UTC):** 2026-05-26
- **Replay duration:** 2627.8s
- **Rows processed:** L2=83 510 098  trades=2 656 040  other=0

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 18 |
| LONG / SHORT | 7 / 11 |
| Triggered | 11 |
| Reached target | 0 |
| Failed by timeout | 11 |
| Invalidated before trigger | 4 |
| Expired (formation aged out) | 1 |
| No trigger by end of day | 2 |
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
| BTC-USDT-SWAP-SHORT-1779792782000-10 | SHORT | 2026-05-26T12:07:21.000Z | 76977.75 | 75438.19 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1779793605000-11 | SHORT | 2026-05-26T12:07:08.000Z | 77035.15 | 75494.45 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1779757505000-6 | SHORT | 2026-05-26T02:46:59.000Z | 76465.85 | 74936.53 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1779756601000-5 | SHORT | 2026-05-26T02:46:46.000Z | 76490.15 | 74960.35 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1779753601000-1 | SHORT | 2026-05-26T00:10:39.000Z | 77176.95 | 75633.41 | RESOLVED_FAILED | - |

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
- Duplicate same-direction candidates suppressed during this run: **8696**
- Suppressions by reason:
  - `active_open`: 5733
  - `active_triggered`: 2963

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Warnings

- Encountered 28800 feature ticks with quality flags.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
