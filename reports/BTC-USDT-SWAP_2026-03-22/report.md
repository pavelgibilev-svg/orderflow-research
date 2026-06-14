# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTC-USDT-SWAP
- **Exchange:** okex-swap
- **Date (UTC):** 2026-03-22
- **Replay duration:** 3055.4s
- **Rows processed:** L2=96 944 642  trades=3 706 135  other=0

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 33 |
| LONG / SHORT | 14 / 19 |
| Triggered | 24 |
| Reached target | 7 |
| Failed by timeout | 17 |
| Invalidated before trigger | 8 |
| Expired (formation aged out) | 0 |
| No trigger by end of day | 1 |
| Hit rate among triggered | 29.17% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 0.00% | 2.08% | 1200 |
| 8h | 0.00% | 13.33% | 960 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTC-USDT-SWAP-SHORT-1774208087000-28 | SHORT | 2026-03-22T21:05:13.000Z | 67882.15 | 66524.51 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1774179056000-18 | SHORT | 2026-03-22T11:52:19.000Z | 68058.55 | 66697.38 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-LONG-1774179961000-19 | LONG | 2026-03-22T13:04:06.000Z | 68881.45 | 70259.08 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1774207344000-27 | SHORT | 2026-03-22T19:31:56.000Z | 68227.15 | 66862.61 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1774140972000-4 | SHORT | 2026-03-22T01:37:54.000Z | 68725.45 | 67350.94 | RESOLVED_REACHED | 24h |

## Move clustering accounting

Pure post-processing. Two RESOLVED_REACHED zones share a `uniqueMoveId` when they are the same direction and their `[triggerTs, reachedAt]` windows overlap or sit within `120` minutes of each other.

| Metric | Value |
|---|---|
| Move clustering enabled | yes |
| Reached zones (raw) | 7 |
| Unique reached moves | 1 |
| Duplicate move credits | 6 |
| Raw triggered hit rate | 29.17% |
| **Unique-move adjusted hit rate** | **4.17%** |

| Move | Dir | Size | Primary zone | Members |
|---|---|---|---|---|
| 1 | SHORT | 7 | `BTC-USDT-SWAP-SHORT-1774139842000-3` | BTC-USDT-SWAP-SHORT-1774139842000-3, BTC-USDT-SWAP-SHORT-1774139822000-2, BTC-USDT-SWAP-SHORT-1774142237000-5, BTC-USDT-SWAP-SHORT-1774140972000-4, BTC-USDT-SWAP-SHORT-1774149904000-8, BTC-USDT-SWAP-SHORT-1774158125000-11, BTC-USDT-SWAP-SHORT-1774146977000-6 |

> The **unique-move-adjusted hit rate** is the honest headline number. The raw rate is kept only as a diagnostic — it counts every triggered zone that reached the target separately, even when several of them rode the same multi-hour directional move at progressively different price bands.

## Deduplication accounting

- Deduplication enabled: **yes**
- Cooldown after resolve: **30 min**
- Duplicate same-direction candidates suppressed during this run: **14899**
- Suppressions by reason:
  - `active_open`: 7818
  - `active_triggered`: 7081

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
