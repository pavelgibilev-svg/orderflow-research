# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTC-USDT-SWAP
- **Exchange:** okex-swap
- **Date (UTC):** 2024-09-01
- **Replay duration:** 3574.8s
- **Rows processed:** L2=96 313 567  trades=1 331 285  other=0

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 42 |
| LONG / SHORT | 25 / 17 |
| Triggered | 20 |
| Reached target | 7 |
| Failed by timeout | 13 |
| Invalidated before trigger | 19 |
| Expired (formation aged out) | 0 |
| No trigger by end of day | 3 |
| Hit rate among triggered | 35.00% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 0.00% | 6.42% | 1200 |
| 8h | 0.10% | 12.81% | 960 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTC-USDT-SWAP-SHORT-1725196077000-27 | SHORT | 2024-09-01T13:38:23.000Z | 57875.65 | 56718.14 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1725167457000-14 | SHORT | 2024-09-01T05:22:54.000Z | 58180.85 | 57017.23 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-LONG-1725159745000-12 | LONG | 2024-09-01T03:14:06.000Z | 58580.45 | 59752.06 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1725156126000-6 | SHORT | 2024-09-01T02:07:47.000Z | 58623.15 | 57450.69 | RESOLVED_REACHED | 24h |
| BTC-USDT-SWAP-LONG-1725148831000-1 | LONG | 2024-09-01T00:07:59.000Z | 59032.95 | 60213.61 | RESOLVED_FAILED | - |

## Move clustering accounting

Pure post-processing. Two RESOLVED_REACHED zones share a `uniqueMoveId` when they are the same direction and their `[triggerTs, reachedAt]` windows overlap or sit within `120` minutes of each other.

| Metric | Value |
|---|---|
| Move clustering enabled | yes |
| Reached zones (raw) | 7 |
| Unique reached moves | 1 |
| Duplicate move credits | 6 |
| Raw triggered hit rate | 35.00% |
| **Unique-move adjusted hit rate** | **5.00%** |

| Move | Dir | Size | Primary zone | Members |
|---|---|---|---|---|
| 1 | SHORT | 7 | `BTC-USDT-SWAP-SHORT-1725149573000-2` | BTC-USDT-SWAP-SHORT-1725149573000-2, BTC-USDT-SWAP-SHORT-1725151467000-3, BTC-USDT-SWAP-SHORT-1725151509000-4, BTC-USDT-SWAP-SHORT-1725156126000-6, BTC-USDT-SWAP-SHORT-1725156384000-7, BTC-USDT-SWAP-SHORT-1725156873000-9, BTC-USDT-SWAP-SHORT-1725158438000-11 |

> The **unique-move-adjusted hit rate** is the honest headline number. The raw rate is kept only as a diagnostic — it counts every triggered zone that reached the target separately, even when several of them rode the same multi-hour directional move at progressively different price bands.

## Deduplication accounting

- Deduplication enabled: **yes**
- Cooldown after resolve: **30 min**
- Duplicate same-direction candidates suppressed during this run: **10705**
- Suppressions by reason:
  - `active_open`: 7110
  - `active_triggered`: 3595

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
