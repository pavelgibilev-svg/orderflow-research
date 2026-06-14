# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTC-USDT-SWAP
- **Exchange:** okex-swap
- **Date (UTC):** 2024-01-01
- **Replay duration:** 3800.5s
- **Rows processed:** L2=102 515 341  trades=323 856  other=0

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 43 |
| LONG / SHORT | 21 / 22 |
| Triggered | 23 |
| Reached target | 13 |
| Failed by timeout | 10 |
| Invalidated before trigger | 17 |
| Expired (formation aged out) | 0 |
| No trigger by end of day | 3 |
| Hit rate among triggered | 56.52% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 10.58% | 0.00% | 1200 |
| 8h | 26.25% | 0.00% | 960 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTC-USDT-SWAP-LONG-1704109801000-24 | LONG | 2024-01-01T12:22:13.000Z | 42715.05 | 43569.35 | RESOLVED_REACHED | 8h |
| BTC-USDT-SWAP-SHORT-1704073733000-7 | SHORT | 2024-01-01T03:43:59.000Z | 42256.90 | 41411.76 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1704097253000-18 | SHORT | 2024-01-01T08:34:23.000Z | 42485.45 | 41635.74 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-LONG-1704133299000-29 | LONG | 2024-01-01T19:29:12.000Z | 43306.65 | 44172.78 | RESOLVED_REACHED | 8h |
| BTC-USDT-SWAP-LONG-1704138960000-34 | LONG | 2024-01-01T20:01:19.000Z | 43666.05 | 44539.37 | RESOLVED_FAILED | - |

## Move clustering accounting

Pure post-processing. Two RESOLVED_REACHED zones share a `uniqueMoveId` when they are the same direction and their `[triggerTs, reachedAt]` windows overlap or sit within `120` minutes of each other.

| Metric | Value |
|---|---|
| Move clustering enabled | yes |
| Reached zones (raw) | 13 |
| Unique reached moves | 1 |
| Duplicate move credits | 12 |
| Raw triggered hit rate | 56.52% |
| **Unique-move adjusted hit rate** | **4.35%** |

| Move | Dir | Size | Primary zone | Members |
|---|---|---|---|---|
| 1 | LONG | 13 | `BTC-USDT-SWAP-LONG-1704067235000-1` | BTC-USDT-SWAP-LONG-1704067235000-1, BTC-USDT-SWAP-LONG-1704072481000-5, BTC-USDT-SWAP-LONG-1704068597000-3, BTC-USDT-SWAP-LONG-1704075260000-9, BTC-USDT-SWAP-LONG-1704088839000-16, BTC-USDT-SWAP-LONG-1704102374000-20, BTC-USDT-SWAP-LONG-1704102458000-21, BTC-USDT-SWAP-LONG-1704109801000-24, BTC-USDT-SWAP-LONG-1704107882000-23, BTC-USDT-SWAP-LONG-1704124400000-25, BTC-USDT-SWAP-LONG-1704135089000-31, BTC-USDT-SWAP-LONG-1704133343000-30, BTC-USDT-SWAP-LONG-1704133299000-29 |

> The **unique-move-adjusted hit rate** is the honest headline number. The raw rate is kept only as a diagnostic — it counts every triggered zone that reached the target separately, even when several of them rode the same multi-hour directional move at progressively different price bands.

## Deduplication accounting

- Deduplication enabled: **yes**
- Cooldown after resolve: **30 min**
- Duplicate same-direction candidates suppressed during this run: **15210**
- Suppressions by reason:
  - `active_open`: 10857
  - `active_triggered`: 4353

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
