# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTC-USDT-SWAP
- **Exchange:** okex-swap
- **Date (UTC):** 2026-03-10
- **Replay duration:** 5683.5s
- **Rows processed:** L2=148 801 978  trades=5 980 001  other=0

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 46 |
| LONG / SHORT | 24 / 22 |
| Triggered | 29 |
| Reached target | 14 |
| Failed by timeout | 15 |
| Invalidated before trigger | 15 |
| Expired (formation aged out) | 0 |
| No trigger by end of day | 2 |
| Hit rate among triggered | 48.28% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 18.33% | 17.08% | 1200 |
| 8h | 36.46% | 27.71% | 960 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTC-USDT-SWAP-LONG-1773115703000-16 | LONG | 2026-03-10T05:16:50.000Z | 70166.05 | 71569.37 | RESOLVED_REACHED | 24h |
| BTC-USDT-SWAP-LONG-1773130875000-28 | LONG | 2026-03-10T09:24:39.000Z | 71032.45 | 72453.10 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-LONG-1773119418000-20 | LONG | 2026-03-10T07:10:53.000Z | 70385.85 | 71793.57 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-LONG-1773127382000-24 | LONG | 2026-03-10T08:05:32.000Z | 70667.05 | 72080.39 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-LONG-1773127409000-25 | LONG | 2026-03-10T08:05:32.000Z | 70667.05 | 72080.39 | RESOLVED_FAILED | - |

## Move clustering accounting

Pure post-processing. Two RESOLVED_REACHED zones share a `uniqueMoveId` when they are the same direction and their `[triggerTs, reachedAt]` windows overlap or sit within `120` minutes of each other.

| Metric | Value |
|---|---|
| Move clustering enabled | yes |
| Reached zones (raw) | 14 |
| Unique reached moves | 3 |
| Duplicate move credits | 11 |
| Raw triggered hit rate | 48.28% |
| **Unique-move adjusted hit rate** | **10.34%** |

| Move | Dir | Size | Primary zone | Members |
|---|---|---|---|---|
| 1 | LONG | 12 | `BTC-USDT-SWAP-LONG-1773100831000-1` | BTC-USDT-SWAP-LONG-1773100831000-1, BTC-USDT-SWAP-LONG-1773104310000-6, BTC-USDT-SWAP-LONG-1773106071000-9, BTC-USDT-SWAP-LONG-1773104480000-7, BTC-USDT-SWAP-LONG-1773104532000-8, BTC-USDT-SWAP-LONG-1773106990000-10, BTC-USDT-SWAP-LONG-1773116500000-17, BTC-USDT-SWAP-LONG-1773118368000-19, BTC-USDT-SWAP-LONG-1773116566000-18, BTC-USDT-SWAP-LONG-1773115703000-16, BTC-USDT-SWAP-LONG-1773120716000-23, BTC-USDT-SWAP-LONG-1773114910000-14 |
| 2 | SHORT | 1 | `BTC-USDT-SWAP-SHORT-1773132250000-30` | BTC-USDT-SWAP-SHORT-1773132250000-30 |
| 3 | SHORT | 1 | `BTC-USDT-SWAP-SHORT-1773161500000-44` | BTC-USDT-SWAP-SHORT-1773161500000-44 |

> The **unique-move-adjusted hit rate** is the honest headline number. The raw rate is kept only as a diagnostic — it counts every triggered zone that reached the target separately, even when several of them rode the same multi-hour directional move at progressively different price bands.

## Deduplication accounting

- Deduplication enabled: **yes**
- Cooldown after resolve: **30 min**
- Duplicate same-direction candidates suppressed during this run: **10767**
- Suppressions by reason:
  - `active_open`: 6851
  - `active_triggered`: 3916

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
