# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTC-USDT-SWAP
- **Exchange:** okex-swap
- **Date (UTC):** 2025-05-01
- **Replay duration:** 4134.9s
- **Rows processed:** L2=109 445 976  trades=2 334 321  other=0

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 44 |
| LONG / SHORT | 25 / 19 |
| Triggered | 28 |
| Reached target | 8 |
| Failed by timeout | 20 |
| Invalidated before trigger | 13 |
| Expired (formation aged out) | 2 |
| No trigger by end of day | 1 |
| Hit rate among triggered | 28.57% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 0.00% | 0.00% | 1200 |
| 8h | 18.85% | 0.00% | 960 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTC-USDT-SWAP-LONG-1746110557000-31 | LONG | 2025-05-01T14:58:50.000Z | 96702.95 | 98637.01 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-LONG-1746110911000-32 | LONG | 2025-05-01T15:10:06.000Z | 97130.60 | 99073.21 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-LONG-1746098604000-25 | LONG | 2025-05-01T12:45:41.000Z | 96360.05 | 98287.25 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-LONG-1746060889000-4 | LONG | 2025-05-01T01:06:41.000Z | 94457.85 | 96347.01 | RESOLVED_REACHED | 24h |
| BTC-USDT-SWAP-LONG-1746080742000-14 | LONG | 2025-05-01T08:17:42.000Z | 95089.95 | 96991.75 | RESOLVED_REACHED | 8h |

## Move clustering accounting

Pure post-processing. Two RESOLVED_REACHED zones share a `uniqueMoveId` when they are the same direction and their `[triggerTs, reachedAt]` windows overlap or sit within `120` minutes of each other.

| Metric | Value |
|---|---|
| Move clustering enabled | yes |
| Reached zones (raw) | 8 |
| Unique reached moves | 1 |
| Duplicate move credits | 7 |
| Raw triggered hit rate | 28.57% |
| **Unique-move adjusted hit rate** | **3.57%** |

| Move | Dir | Size | Primary zone | Members |
|---|---|---|---|---|
| 1 | LONG | 8 | `BTC-USDT-SWAP-LONG-1746058940000-3` | BTC-USDT-SWAP-LONG-1746058940000-3, BTC-USDT-SWAP-LONG-1746060889000-4, BTC-USDT-SWAP-LONG-1746065831000-8, BTC-USDT-SWAP-LONG-1746062484000-6, BTC-USDT-SWAP-LONG-1746066920000-10, BTC-USDT-SWAP-LONG-1746080742000-14, BTC-USDT-SWAP-LONG-1746078733000-13, BTC-USDT-SWAP-LONG-1746091632000-17 |

> The **unique-move-adjusted hit rate** is the honest headline number. The raw rate is kept only as a diagnostic — it counts every triggered zone that reached the target separately, even when several of them rode the same multi-hour directional move at progressively different price bands.

## Deduplication accounting

- Deduplication enabled: **yes**
- Cooldown after resolve: **30 min**
- Duplicate same-direction candidates suppressed during this run: **16053**
- Suppressions by reason:
  - `active_open`: 12816
  - `active_triggered`: 3237

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
