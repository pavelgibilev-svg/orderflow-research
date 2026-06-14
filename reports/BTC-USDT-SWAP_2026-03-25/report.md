# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTC-USDT-SWAP
- **Exchange:** okex-swap
- **Date (UTC):** 2026-03-25
- **Replay duration:** 3577.6s
- **Rows processed:** L2=109 850 927  trades=4 176 506  other=0

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 33 |
| LONG / SHORT | 18 / 15 |
| Triggered | 23 |
| Reached target | 0 |
| Failed by timeout | 23 |
| Invalidated before trigger | 8 |
| Expired (formation aged out) | 1 |
| No trigger by end of day | 1 |
| Hit rate among triggered | 0.00% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 0.00% | 0.00% | 1200 |
| 8h | 0.10% | 0.00% | 960 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTC-USDT-SWAP-LONG-1774432966000-18 | LONG | 2026-03-25T10:47:53.000Z | 71535.45 | 72966.16 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-LONG-1774437718000-22 | LONG | 2026-03-25T11:29:43.000Z | 71904.35 | 73342.44 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1774439561000-25 | SHORT | 2026-03-25T15:09:18.000Z | 70904.75 | 69486.65 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-LONG-1774397404000-3 | LONG | 2026-03-25T00:34:01.000Z | 70781.45 | 72197.08 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1774460558000-31 | SHORT | 2026-03-25T17:53:24.000Z | 70757.45 | 69342.30 | RESOLVED_FAILED | - |

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
- Duplicate same-direction candidates suppressed during this run: **11008**
- Suppressions by reason:
  - `active_open`: 6374
  - `active_triggered`: 4634

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
