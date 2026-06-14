# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTC-USDT-SWAP
- **Exchange:** okex-swap
- **Date (UTC):** 2026-02-01
- **Replay duration:** 6748.8s
- **Rows processed:** L2=157 969 600  trades=5 085 587  other=0

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 28 |
| LONG / SHORT | 14 / 14 |
| Triggered | 17 |
| Reached target | 7 |
| Failed by timeout | 10 |
| Invalidated before trigger | 11 |
| Expired (formation aged out) | 0 |
| No trigger by end of day | 0 |
| Hit rate among triggered | 41.18% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 0.00% | 20.50% | 1200 |
| 8h | 0.00% | 46.98% | 960 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTC-USDT-SWAP-SHORT-1769906548000-5 | SHORT | 2026-02-01T01:46:53.000Z | 78275.65 | 76710.14 | RESOLVED_REACHED | 24h |
| BTC-USDT-SWAP-LONG-1769907455000-6 | LONG | 2026-02-01T04:20:01.000Z | 79072.55 | 80654.00 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1769954475000-14 | SHORT | 2026-02-01T14:25:30.000Z | 77912.45 | 76354.20 | RESOLVED_REACHED | 8h |
| BTC-USDT-SWAP-LONG-1769979515000-28 | LONG | 2026-02-01T22:09:48.000Z | 77166.65 | 78709.98 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-LONG-1769966313000-23 | LONG | 2026-02-01T18:02:04.000Z | 77874.95 | 79432.45 | RESOLVED_FAILED | - |

## Move clustering accounting

Pure post-processing. Two RESOLVED_REACHED zones share a `uniqueMoveId` when they are the same direction and their `[triggerTs, reachedAt]` windows overlap or sit within `120` minutes of each other.

| Metric | Value |
|---|---|
| Move clustering enabled | yes |
| Reached zones (raw) | 7 |
| Unique reached moves | 1 |
| Duplicate move credits | 6 |
| Raw triggered hit rate | 41.18% |
| **Unique-move adjusted hit rate** | **5.88%** |

| Move | Dir | Size | Primary zone | Members |
|---|---|---|---|---|
| 1 | SHORT | 7 | `BTC-USDT-SWAP-SHORT-1769905914000-2` | BTC-USDT-SWAP-SHORT-1769905914000-2, BTC-USDT-SWAP-SHORT-1769905954000-3, BTC-USDT-SWAP-SHORT-1769906512000-4, BTC-USDT-SWAP-SHORT-1769906548000-5, BTC-USDT-SWAP-SHORT-1769909589000-8, BTC-USDT-SWAP-SHORT-1769954475000-14, BTC-USDT-SWAP-SHORT-1769954256000-13 |

> The **unique-move-adjusted hit rate** is the honest headline number. The raw rate is kept only as a diagnostic — it counts every triggered zone that reached the target separately, even when several of them rode the same multi-hour directional move at progressively different price bands.

## Deduplication accounting

- Deduplication enabled: **yes**
- Cooldown after resolve: **30 min**
- Duplicate same-direction candidates suppressed during this run: **9469**
- Suppressions by reason:
  - `active_open`: 5052
  - `active_triggered`: 4415
  - `cooldown`: 2

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
