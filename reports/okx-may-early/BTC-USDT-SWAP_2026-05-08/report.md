# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTC-USDT-SWAP
- **Exchange:** okex-swap
- **Date (UTC):** 2026-05-08
- **Replay duration:** 2180.1s
- **Rows processed:** L2=75 865 089  trades=2 723 442  other=0

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 24 |
| LONG / SHORT | 14 / 10 |
| Triggered | 16 |
| Reached target | 0 |
| Failed by timeout | 16 |
| Invalidated before trigger | 6 |
| Expired (formation aged out) | 0 |
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
| BTC-USDT-SWAP-SHORT-1778237718000-21 | SHORT | 2026-05-08T12:50:26.000Z | 79967.15 | 78367.81 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1778202302000-5 | SHORT | 2026-05-08T02:01:56.000Z | 79529.95 | 77939.35 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1778201933000-4 | SHORT | 2026-05-08T01:15:17.000Z | 79595.35 | 78003.44 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1778199225000-2 | SHORT | 2026-05-08T00:49:50.000Z | 79838.65 | 78241.88 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-LONG-1778198401000-1 | LONG | 2026-05-08T00:22:31.000Z | 80074.95 | 81676.45 | RESOLVED_FAILED | - |

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
- Duplicate same-direction candidates suppressed during this run: **8832**
- Suppressions by reason:
  - `active_open`: 5326
  - `active_triggered`: 3506

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Warnings

- Encountered 28800 feature ticks with quality flags.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
