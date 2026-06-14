# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTC-USDT-SWAP
- **Exchange:** okex-swap
- **Date (UTC):** 2026-03-01
- **Replay duration:** 5622.5s
- **Rows processed:** L2=131 743 934  trades=5 299 982  other=0

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 43 |
| LONG / SHORT | 19 / 24 |
| Triggered | 26 |
| Reached target | 7 |
| Failed by timeout | 19 |
| Invalidated before trigger | 15 |
| Expired (formation aged out) | 0 |
| No trigger by end of day | 2 |
| Hit rate among triggered | 26.92% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 7.42% | 10.83% | 1200 |
| 8h | 9.27% | 27.08% | 960 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTC-USDT-SWAP-SHORT-1772324210000-3 | SHORT | 2026-03-01T00:35:29.000Z | 66713.75 | 65379.47 | RESOLVED_REACHED | 24h |
| BTC-USDT-SWAP-LONG-1772341233000-13 | LONG | 2026-03-01T05:20:16.000Z | 67444.75 | 68793.65 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-LONG-1772346194000-15 | LONG | 2026-03-01T07:36:29.000Z | 67172.35 | 68515.80 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1772395619000-31 | SHORT | 2026-03-01T20:29:59.000Z | 65266.05 | 63960.73 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1772396272000-32 | SHORT | 2026-03-01T20:34:51.000Z | 65185.25 | 63881.54 | RESOLVED_FAILED | - |

## Move clustering accounting

Pure post-processing. Two RESOLVED_REACHED zones share a `uniqueMoveId` when they are the same direction and their `[triggerTs, reachedAt]` windows overlap or sit within `120` minutes of each other.

| Metric | Value |
|---|---|
| Move clustering enabled | yes |
| Reached zones (raw) | 7 |
| Unique reached moves | 1 |
| Duplicate move credits | 6 |
| Raw triggered hit rate | 26.92% |
| **Unique-move adjusted hit rate** | **3.85%** |

| Move | Dir | Size | Primary zone | Members |
|---|---|---|---|---|
| 1 | SHORT | 7 | `BTC-USDT-SWAP-SHORT-1772323251000-1` | BTC-USDT-SWAP-SHORT-1772323251000-1, BTC-USDT-SWAP-SHORT-1772324210000-3, BTC-USDT-SWAP-SHORT-1772324876000-4, BTC-USDT-SWAP-SHORT-1772350918000-17, BTC-USDT-SWAP-SHORT-1772330247000-9, BTC-USDT-SWAP-SHORT-1772330889000-10, BTC-USDT-SWAP-SHORT-1772356497000-18 |

> The **unique-move-adjusted hit rate** is the honest headline number. The raw rate is kept only as a diagnostic — it counts every triggered zone that reached the target separately, even when several of them rode the same multi-hour directional move at progressively different price bands.

## Deduplication accounting

- Deduplication enabled: **yes**
- Cooldown after resolve: **30 min**
- Duplicate same-direction candidates suppressed during this run: **12402**
- Suppressions by reason:
  - `active_open`: 6393
  - `cooldown`: 1
  - `active_triggered`: 6008

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
