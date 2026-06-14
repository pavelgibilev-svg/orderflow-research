# Move Clustering Audit — BTCUSDT 2026-02-01

> Pure post-processing accounting fix. Strategy thresholds in `config/strategy.default.json` are unchanged. Detector logic untouched. Failed / no_trigger / invalidated zones remain in the zones list and never receive a `uniqueMoveId`.

- Generated: 2026-05-09T14:07:43.266Z
- Source zones: `reports/full_day_2026-02-01_dedup/zones.json`
- Total zones in source: 25
- Triggered: 11

## 1. Algorithm

Two RESOLVED_REACHED zones share a `uniqueMoveId` when they meet ALL of:
- same direction (LONG / LONG or SHORT / SHORT);
- their `[triggerTs, reachedAt]` time windows overlap, OR the next zone's `triggerTs` falls within `moveClusterGapMinutes = 120` minutes of the cluster's max `reachedAt`.

Within a cluster, the zone with the earliest `triggerTs` is marked `isPrimaryMoveZone = true`. Ties are broken by composite score (absorption × void × trigger). Other reached zones in the same cluster get `duplicateMoveCredit = true`.

## 2. Headline metrics

| Metric | Value |
|---|---|
| Triggered zones | 11 |
| Reached zones (raw) | 4 |
| Unique reached moves | 1 |
| Duplicate move credits | 3 |
| Raw triggered hit rate | 36.36% |
| **Unique-move-adjusted hit rate** | **9.09%** |

## 3. All reached zones

| # | Zone id | Dir | Trigger | Reached | TrigPx | TargetPx | Move id | Cluster size | Primary? | Dup credit | MFE % | MAE % | t→tgt min |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `BTCUSDT-SHORT-1769904037000-1` | SHORT | 01:07:10 | 15:26:10 | 78566.05 | 76994.73 | 1 | 4 | **yes** | no | 3.72 | 0.80 | 859.0 |
| 2 | `BTCUSDT-SHORT-1769904101000-2` | SHORT | 01:11:00 | 15:26:10 | 78538.75 | 76967.98 | 1 | 4 | no | yes | 3.69 | 0.83 | 855.2 |
| 3 | `BTCUSDT-SHORT-1769911034000-5` | SHORT | 06:48:08 | 20:28:31 | 78273.45 | 76707.98 | 1 | 4 | no | yes | 3.36 | 1.18 | 820.4 |
| 4 | `BTCUSDT-SHORT-1769929081000-9` | SHORT | 07:04:55 | 20:28:41 | 78109.65 | 76547.46 | 1 | 4 | no | yes | 3.16 | 1.39 | 803.8 |

## 4. Unique moves

Each row is one underlying directional move. The reached-zones inside it all caught the same continuing trend (overlapping or near-adjacent in time, same direction).

| Move id | Dir | # Zones | Trigger window | Reached window | Primary zone | Members |
|---|---|---|---|---|---|---|
| 1 | SHORT | 4 | 01:07:10–07:04:55 | 15:26:10–20:28:41 | `BTCUSDT-SHORT-1769904037000-1` | BTCUSDT-SHORT-1769904037000-1, BTCUSDT-SHORT-1769904101000-2, BTCUSDT-SHORT-1769911034000-5, BTCUSDT-SHORT-1769929081000-9 |

## 5. Why 4 reached zones = 1 unique move

### Move 1 (SHORT)

Cluster size: 4 reached zones.

Trigger times within this move: 01:07:10 → 01:11:00 → 06:48:08 → 07:04:55.
Reached times: 15:26:10 / 15:26:10 / 20:28:31 / 20:28:41.
Target prices: 76994.73 / 76967.98 / 76707.98 / 76547.46.

These 4 zones have **mutually overlapping trigger→reached windows** (min reachedAt = 15:26:10, max triggerTs = 07:04:55, overlap of 501 min). They all rode the same continuing downward leg of the day. Crediting all 4 of them to the day's hit-rate would inflate the count: only 3 of them are duplicate credits for one underlying directional event.


## 6. Honest verdict for 2026-02-01

**Raw triggered hit rate:** 36.36% (4/11).
**Unique-move-adjusted hit rate:** 9.09% (1/11).

The headline number that should be quoted is **9.09%**, not 36.36%. The 3 duplicate-credit zones rode the same multi-hour downward leg as the primary zone in their cluster — they are technically distinct setups but caught the same underlying directional event.

> The strategy thresholds in `config/strategy.default.json` are unchanged. The detector and target checker are unchanged. Failed / no_trigger / invalidated zones are still preserved in the zones list (they simply never enter clustering).
