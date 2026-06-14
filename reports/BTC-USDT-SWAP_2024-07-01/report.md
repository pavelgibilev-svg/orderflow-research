# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTC-USDT-SWAP
- **Exchange:** okex-swap
- **Date (UTC):** 2024-07-01
- **Replay duration:** 3548.6s
- **Rows processed:** L2=88 305 628  trades=959 411  other=0

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 17 |
| LONG / SHORT | 8 / 9 |
| Triggered | 9 |
| Reached target | 0 |
| Failed by timeout | 9 |
| Invalidated before trigger | 7 |
| Expired (formation aged out) | 0 |
| No trigger by end of day | 1 |
| Hit rate among triggered | 0.00% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 0.08% | 0.00% | 1200 |
| 8h | 0.42% | 0.00% | 960 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTC-USDT-SWAP-SHORT-1719795184000-6 | SHORT | 2024-07-01T13:48:09.000Z | 62664.15 | 61410.87 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-LONG-1719795494000-7 | LONG | 2024-07-01T01:06:15.000Z | 63198.35 | 64462.32 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-LONG-1719795523000-8 | LONG | 2024-07-01T01:06:16.000Z | 63330.65 | 64597.26 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-LONG-1719795069000-5 | LONG | 2024-07-01T01:00:01.000Z | 62951.65 | 64210.68 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-LONG-1719797912000-11 | LONG | 2024-07-01T01:57:09.000Z | 63712.75 | 64987.01 | RESOLVED_FAILED | - |

## Move clustering accounting

Pure post-processing. Two RESOLVED_REACHED zones share a `uniqueMoveId` when they are the same direction and their `[triggerTs, reachedAt]` windows overlap or sit within `120` minutes of each other.

| Metric | Value |
|---|---|
| Move clustering enabled | yes |
| Reached zones (raw) | 0 |
| Unique reached moves | 0 |
| Duplicate move credits | 0 |
| Raw triggered hit rate | 0.00% |
| **Unique-move adjusted hit rate** | **0.00%** |

> The **unique-move-adjusted hit rate** is the honest headline number. The raw rate is kept only as a diagnostic — it counts every triggered zone that reached the target separately, even when several of them rode the same multi-hour directional move at progressively different price bands.

## Deduplication accounting

- Deduplication enabled: **yes**
- Cooldown after resolve: **30 min**
- Duplicate same-direction candidates suppressed during this run: **15104**
- Suppressions by reason:
  - `active_open`: 7543
  - `active_triggered`: 7561

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
