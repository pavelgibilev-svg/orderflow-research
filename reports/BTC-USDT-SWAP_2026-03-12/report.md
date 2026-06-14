# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTC-USDT-SWAP
- **Exchange:** okex-swap
- **Date (UTC):** 2026-03-12
- **Replay duration:** 4844.8s
- **Rows processed:** L2=131 908 822  trades=4 665 200  other=0

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 32 |
| LONG / SHORT | 15 / 17 |
| Triggered | 20 |
| Reached target | 0 |
| Failed by timeout | 20 |
| Invalidated before trigger | 11 |
| Expired (formation aged out) | 0 |
| No trigger by end of day | 1 |
| Hit rate among triggered | 0.00% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 0.00% | 0.00% | 1200 |
| 8h | 8.65% | 0.00% | 960 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTC-USDT-SWAP-SHORT-1773278670000-7 | SHORT | 2026-03-12T01:34:24.000Z | 69816.05 | 68419.73 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1773277918000-6 | SHORT | 2026-03-12T01:35:57.000Z | 69801.85 | 68405.81 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-LONG-1773303167000-19 | LONG | 2026-03-12T08:16:31.000Z | 69877.45 | 71275.00 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-LONG-1773306306000-20 | LONG | 2026-03-12T09:41:30.000Z | 69913.15 | 71311.41 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1773314627000-28 | SHORT | 2026-03-12T13:21:26.000Z | 69999.35 | 68599.36 | RESOLVED_FAILED | - |

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
- Duplicate same-direction candidates suppressed during this run: **11823**
- Suppressions by reason:
  - `active_open`: 8166
  - `active_triggered`: 3657

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
