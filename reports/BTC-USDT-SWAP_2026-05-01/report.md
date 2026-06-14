# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTC-USDT-SWAP
- **Exchange:** okex-swap
- **Date (UTC):** 2026-05-01
- **Replay duration:** 2463.8s
- **Rows processed:** L2=75 247 692  trades=2 734 663  other=0

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 28 |
| LONG / SHORT | 15 / 13 |
| Triggered | 15 |
| Reached target | 4 |
| Failed by timeout | 11 |
| Invalidated before trigger | 9 |
| Expired (formation aged out) | 0 |
| No trigger by end of day | 4 |
| Hit rate among triggered | 26.67% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 7.75% | 0.00% | 1200 |
| 8h | 32.40% | 0.00% | 960 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTC-USDT-SWAP-LONG-1777624215000-16 | LONG | 2026-05-01T11:21:25.000Z | 77529.45 | 79080.04 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-LONG-1777601772000-4 | LONG | 2026-05-01T03:17:05.000Z | 76746.55 | 78281.48 | RESOLVED_REACHED | 24h |
| BTC-USDT-SWAP-LONG-1777607082000-8 | LONG | 2026-05-01T11:21:31.000Z | 77555.05 | 79106.15 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-LONG-1777619102000-13 | LONG | 2026-05-01T07:49:22.000Z | 77034.95 | 78575.65 | RESOLVED_REACHED | 8h |
| BTC-USDT-SWAP-LONG-1777606242000-7 | LONG | 2026-05-01T12:17:48.000Z | 77647.15 | 79200.09 | RESOLVED_FAILED | - |

## Move clustering accounting

Pure post-processing. Two RESOLVED_REACHED zones share a `uniqueMoveId` when they are the same direction and their `[triggerTs, reachedAt]` windows overlap or sit within `120` minutes of each other.

| Metric | Value |
|---|---|
| Move clustering enabled | yes |
| Reached zones (raw) | 4 |
| Unique reached moves | 1 |
| Duplicate move credits | 3 |
| Raw triggered hit rate | 26.67% |
| **Unique-move adjusted hit rate** | **6.67%** |

| Move | Dir | Size | Primary zone | Members |
|---|---|---|---|---|
| 1 | LONG | 4 | `BTC-USDT-SWAP-LONG-1777596087000-2` | BTC-USDT-SWAP-LONG-1777596087000-2, BTC-USDT-SWAP-LONG-1777598313000-3, BTC-USDT-SWAP-LONG-1777601772000-4, BTC-USDT-SWAP-LONG-1777619102000-13 |

> The **unique-move-adjusted hit rate** is the honest headline number. The raw rate is kept only as a diagnostic — it counts every triggered zone that reached the target separately, even when several of them rode the same multi-hour directional move at progressively different price bands.

## Deduplication accounting

- Deduplication enabled: **yes**
- Cooldown after resolve: **30 min**
- Duplicate same-direction candidates suppressed during this run: **13470**
- Suppressions by reason:
  - `active_open`: 11473
  - `active_triggered`: 1997

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
