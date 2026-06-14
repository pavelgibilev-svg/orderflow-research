# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTC-USDT-SWAP
- **Exchange:** okex-swap
- **Date (UTC):** 2025-12-01
- **Replay duration:** 6578.3s
- **Rows processed:** L2=164 161 088  trades=5 097 976  other=0

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 42 |
| LONG / SHORT | 21 / 21 |
| Triggered | 20 |
| Reached target | 11 |
| Failed by timeout | 9 |
| Invalidated before trigger | 20 |
| Expired (formation aged out) | 0 |
| No trigger by end of day | 2 |
| Hit rate among triggered | 55.00% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 7.58% | 37.75% | 1200 |
| 8h | 3.75% | 56.98% | 960 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTC-USDT-SWAP-SHORT-1764591504000-27 | SHORT | 2025-12-01T12:41:01.000Z | 85546.05 | 83835.13 | RESOLVED_REACHED | 4h |
| BTC-USDT-SWAP-LONG-1764622124000-40 | LONG | 2025-12-01T21:04:30.000Z | 85599.85 | 87311.85 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-LONG-1764563895000-19 | LONG | 2025-12-01T06:04:41.000Z | 86103.05 | 87825.11 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1764557654000-10 | SHORT | 2025-12-01T04:14:17.000Z | 86002.05 | 84282.01 | RESOLVED_REACHED | 24h |
| BTC-USDT-SWAP-LONG-1764571436000-22 | LONG | 2025-12-01T07:38:36.000Z | 86400.65 | 88128.66 | RESOLVED_FAILED | - |

## Move clustering accounting

Pure post-processing. Two RESOLVED_REACHED zones share a `uniqueMoveId` when they are the same direction and their `[triggerTs, reachedAt]` windows overlap or sit within `120` minutes of each other.

| Metric | Value |
|---|---|
| Move clustering enabled | yes |
| Reached zones (raw) | 11 |
| Unique reached moves | 1 |
| Duplicate move credits | 10 |
| Raw triggered hit rate | 55.00% |
| **Unique-move adjusted hit rate** | **5.00%** |

| Move | Dir | Size | Primary zone | Members |
|---|---|---|---|---|
| 1 | SHORT | 11 | `BTC-USDT-SWAP-SHORT-1764548802000-3` | BTC-USDT-SWAP-SHORT-1764548802000-3, BTC-USDT-SWAP-SHORT-1764554470000-8, BTC-USDT-SWAP-SHORT-1764552608000-7, BTC-USDT-SWAP-SHORT-1764551229000-4, BTC-USDT-SWAP-SHORT-1764557985000-11, BTC-USDT-SWAP-SHORT-1764558485000-12, BTC-USDT-SWAP-SHORT-1764558932000-13, BTC-USDT-SWAP-SHORT-1764560208000-14, BTC-USDT-SWAP-SHORT-1764557654000-10, BTC-USDT-SWAP-SHORT-1764591504000-27, BTC-USDT-SWAP-SHORT-1764598149000-31 |

> The **unique-move-adjusted hit rate** is the honest headline number. The raw rate is kept only as a diagnostic — it counts every triggered zone that reached the target separately, even when several of them rode the same multi-hour directional move at progressively different price bands.

## Deduplication accounting

- Deduplication enabled: **yes**
- Cooldown after resolve: **30 min**
- Duplicate same-direction candidates suppressed during this run: **10829**
- Suppressions by reason:
  - `active_open`: 8337
  - `active_triggered`: 2478
  - `cooldown`: 14

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
