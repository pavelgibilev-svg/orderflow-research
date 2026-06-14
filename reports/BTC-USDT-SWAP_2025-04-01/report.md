# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTC-USDT-SWAP
- **Exchange:** okex-swap
- **Date (UTC):** 2025-04-01
- **Replay duration:** 5831.4s
- **Rows processed:** L2=144 815 592  trades=2 321 152  other=0

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 41 |
| LONG / SHORT | 24 / 17 |
| Triggered | 26 |
| Reached target | 10 |
| Failed by timeout | 16 |
| Invalidated before trigger | 12 |
| Expired (formation aged out) | 0 |
| No trigger by end of day | 3 |
| Hit rate among triggered | 38.46% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 10.75% | 3.00% | 1200 |
| 8h | 26.46% | 9.38% | 960 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTC-USDT-SWAP-LONG-1743526074000-37 | LONG | 2025-04-01T23:33:24.000Z | 85574.15 | 87285.63 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-LONG-1743498506000-20 | LONG | 2025-04-01T09:33:55.000Z | 84352.25 | 86039.29 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-LONG-1743485417000-11 | LONG | 2025-04-01T06:49:40.000Z | 83414.05 | 85082.33 | RESOLVED_REACHED | 24h |
| BTC-USDT-SWAP-SHORT-1743524448000-35 | SHORT | 2025-04-01T18:04:38.000Z | 84771.65 | 83076.22 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1743524508000-36 | SHORT | 2025-04-01T18:04:38.000Z | 84771.65 | 83076.22 | RESOLVED_FAILED | - |

## Move clustering accounting

Pure post-processing. Two RESOLVED_REACHED zones share a `uniqueMoveId` when they are the same direction and their `[triggerTs, reachedAt]` windows overlap or sit within `120` minutes of each other.

| Metric | Value |
|---|---|
| Move clustering enabled | yes |
| Reached zones (raw) | 10 |
| Unique reached moves | 2 |
| Duplicate move credits | 8 |
| Raw triggered hit rate | 38.46% |
| **Unique-move adjusted hit rate** | **7.69%** |

| Move | Dir | Size | Primary zone | Members |
|---|---|---|---|---|
| 1 | LONG | 9 | `BTC-USDT-SWAP-LONG-1743465757000-1` | BTC-USDT-SWAP-LONG-1743465757000-1, BTC-USDT-SWAP-LONG-1743465865000-2, BTC-USDT-SWAP-LONG-1743473552000-4, BTC-USDT-SWAP-LONG-1743474157000-5, BTC-USDT-SWAP-LONG-1743477032000-8, BTC-USDT-SWAP-LONG-1743477399000-9, BTC-USDT-SWAP-LONG-1743485417000-11, BTC-USDT-SWAP-LONG-1743490116000-12, BTC-USDT-SWAP-LONG-1743493767000-15 |
| 2 | SHORT | 1 | `BTC-USDT-SWAP-SHORT-1743501153000-22` | BTC-USDT-SWAP-SHORT-1743501153000-22 |

> The **unique-move-adjusted hit rate** is the honest headline number. The raw rate is kept only as a diagnostic — it counts every triggered zone that reached the target separately, even when several of them rode the same multi-hour directional move at progressively different price bands.

## Deduplication accounting

- Deduplication enabled: **yes**
- Cooldown after resolve: **30 min**
- Duplicate same-direction candidates suppressed during this run: **11992**
- Suppressions by reason:
  - `active_open`: 8664
  - `active_triggered`: 3328

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
