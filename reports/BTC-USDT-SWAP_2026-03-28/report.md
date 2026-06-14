# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTC-USDT-SWAP
- **Exchange:** okex-swap
- **Date (UTC):** 2026-03-28
- **Replay duration:** 1857.2s
- **Rows processed:** L2=67 176 397  trades=1 960 621  other=0

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 23 |
| LONG / SHORT | 15 / 8 |
| Triggered | 15 |
| Reached target | 0 |
| Failed by timeout | 15 |
| Invalidated before trigger | 6 |
| Expired (formation aged out) | 0 |
| No trigger by end of day | 2 |
| Hit rate among triggered | 0.00% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 0.00% | 0.00% | 1200 |
| 8h | 0.00% | 0.00% | 960 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTC-USDT-SWAP-SHORT-1774656577000-2 | SHORT | 2026-03-28T01:11:48.000Z | 66159.85 | 64836.65 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1774656525000-1 | SHORT | 2026-03-28T01:13:31.000Z | 66081.85 | 64760.21 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1774662687000-8 | SHORT | 2026-03-28T02:19:06.000Z | 66018.35 | 64697.98 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-LONG-1774657037000-3 | LONG | 2026-03-28T00:31:12.000Z | 66398.55 | 67726.52 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1774686604000-15 | SHORT | 2026-03-28T09:03:54.000Z | 66316.75 | 64990.42 | RESOLVED_FAILED | - |

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
- Duplicate same-direction candidates suppressed during this run: **14387**
- Suppressions by reason:
  - `active_open`: 10063
  - `active_triggered`: 4324

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
