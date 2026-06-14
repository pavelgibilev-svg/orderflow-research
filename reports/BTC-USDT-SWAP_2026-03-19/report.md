# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTC-USDT-SWAP
- **Exchange:** okex-swap
- **Date (UTC):** 2026-03-19
- **Replay duration:** 5911.0s
- **Rows processed:** L2=133 909 759  trades=5 071 685  other=0

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 51 |
| LONG / SHORT | 25 / 26 |
| Triggered | 27 |
| Reached target | 7 |
| Failed by timeout | 20 |
| Invalidated before trigger | 20 |
| Expired (formation aged out) | 1 |
| No trigger by end of day | 3 |
| Hit rate among triggered | 25.93% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 1.92% | 5.92% | 1200 |
| 8h | 5.94% | 51.46% | 960 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTC-USDT-SWAP-SHORT-1773893807000-13 | SHORT | 2026-03-19T04:27:07.000Z | 70688.85 | 69275.07 | RESOLVED_REACHED | 24h |
| BTC-USDT-SWAP-SHORT-1773894114000-14 | SHORT | 2026-03-19T06:37:36.000Z | 70564.45 | 69153.16 | RESOLVED_REACHED | 8h |
| BTC-USDT-SWAP-LONG-1773878683000-1 | LONG | 2026-03-19T03:17:57.000Z | 71349.95 | 72776.95 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1773891608000-11 | SHORT | 2026-03-19T04:07:16.000Z | 70901.35 | 69483.32 | RESOLVED_REACHED | 4h |
| BTC-USDT-SWAP-LONG-1773932261000-35 | LONG | 2026-03-19T15:05:45.000Z | 69799.95 | 71195.95 | RESOLVED_FAILED | - |

## Move clustering accounting

Pure post-processing. Two RESOLVED_REACHED zones share a `uniqueMoveId` when they are the same direction and their `[triggerTs, reachedAt]` windows overlap or sit within `120` minutes of each other.

| Metric | Value |
|---|---|
| Move clustering enabled | yes |
| Reached zones (raw) | 7 |
| Unique reached moves | 1 |
| Duplicate move credits | 6 |
| Raw triggered hit rate | 25.93% |
| **Unique-move adjusted hit rate** | **3.70%** |

| Move | Dir | Size | Primary zone | Members |
|---|---|---|---|---|
| 1 | SHORT | 7 | `BTC-USDT-SWAP-SHORT-1773879450000-2` | BTC-USDT-SWAP-SHORT-1773879450000-2, BTC-USDT-SWAP-SHORT-1773886593000-7, BTC-USDT-SWAP-SHORT-1773891608000-11, BTC-USDT-SWAP-SHORT-1773891003000-9, BTC-USDT-SWAP-SHORT-1773891095000-10, BTC-USDT-SWAP-SHORT-1773893807000-13, BTC-USDT-SWAP-SHORT-1773894114000-14 |

> The **unique-move-adjusted hit rate** is the honest headline number. The raw rate is kept only as a diagnostic — it counts every triggered zone that reached the target separately, even when several of them rode the same multi-hour directional move at progressively different price bands.

## Deduplication accounting

- Deduplication enabled: **yes**
- Cooldown after resolve: **30 min**
- Duplicate same-direction candidates suppressed during this run: **11913**
- Suppressions by reason:
  - `active_open`: 10042
  - `active_triggered`: 1621
  - `cooldown`: 250

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
