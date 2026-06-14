# Zone Quality Audit — BTCUSDT 2026-02-01

> Audit of the full-day backtest output for 2026-02-01: are 20 zones in one day independent signals, or is the detector fragmenting the same market structure?

- Generated: 2026-05-09T05:36:43.682Z
- Source zones: `reports/full_day_2026-02-01/zones.json`
- Strategy thresholds NOT modified.
- Detector logic NOT modified.

## 1. Temporal overlaps

Active interval per zone is defined as **`[startTs … min(resolvedTs, triggerTs, confirmedTs, startTs)]`** — the period where the zone was actively forming or being tracked. Two zones overlap temporally when these intervals intersect.

Temporally overlapping pairs (any direction): **82**.
Of those, same-direction: **45**.

Same-direction temporal overlaps (the suspicious ones for fragmentation):

| A id | B id | Dir | A active | B active | Overlap |
|---|---|---|---|---|---|
| BTCUSDT-SHORT-1769904037000-1 | BTCUSDT-SHORT-1769911034000-3 | SHORT | 00:00:37–15:26:10 | 01:57:14–20:28:31 | 01:57:14–15:26:10 |
| BTCUSDT-SHORT-1769904037000-1 | BTCUSDT-SHORT-1769929070000-4 | SHORT | 00:00:37–15:26:10 | 06:57:50–21:09:27 | 06:57:50–15:26:10 |
| BTCUSDT-SHORT-1769904037000-1 | BTCUSDT-SHORT-1769931922000-6 | SHORT | 00:00:37–15:26:10 | 07:45:22–09:58:07 | 07:45:22–09:58:07 |
| BTCUSDT-SHORT-1769904037000-1 | BTCUSDT-SHORT-1769940184000-7 | SHORT | 00:00:37–15:26:10 | 10:03:04–15:27:02 | 10:03:04–15:26:10 |
| BTCUSDT-SHORT-1769904037000-1 | BTCUSDT-SHORT-1769942488000-8 | SHORT | 00:00:37–15:26:10 | 10:41:28–23:06:38 | 10:41:28–15:26:10 |
| BTCUSDT-SHORT-1769904037000-1 | BTCUSDT-SHORT-1769958085000-9 | SHORT | 00:00:37–15:26:10 | 15:01:25–23:09:32 | 15:01:25–15:26:10 |
| BTCUSDT-SHORT-1769911034000-3 | BTCUSDT-SHORT-1769929070000-4 | SHORT | 01:57:14–20:28:31 | 06:57:50–21:09:27 | 06:57:50–20:28:31 |
| BTCUSDT-SHORT-1769911034000-3 | BTCUSDT-SHORT-1769931922000-6 | SHORT | 01:57:14–20:28:31 | 07:45:22–09:58:07 | 07:45:22–09:58:07 |
| BTCUSDT-SHORT-1769911034000-3 | BTCUSDT-SHORT-1769940184000-7 | SHORT | 01:57:14–20:28:31 | 10:03:04–15:27:02 | 10:03:04–15:27:02 |
| BTCUSDT-SHORT-1769911034000-3 | BTCUSDT-SHORT-1769942488000-8 | SHORT | 01:57:14–20:28:31 | 10:41:28–23:06:38 | 10:41:28–20:28:31 |
| BTCUSDT-SHORT-1769911034000-3 | BTCUSDT-SHORT-1769958085000-9 | SHORT | 01:57:14–20:28:31 | 15:01:25–23:09:32 | 15:01:25–20:28:31 |
| BTCUSDT-SHORT-1769911034000-3 | BTCUSDT-SHORT-1769962684000-11 | SHORT | 01:57:14–20:28:31 | 16:18:04–18:08:40 | 16:18:04–18:08:40 |
| BTCUSDT-SHORT-1769911034000-3 | BTCUSDT-SHORT-1769969766000-12 | SHORT | 01:57:14–20:28:31 | 18:16:06–19:57:09 | 18:16:06–20:28:31 |
| BTCUSDT-SHORT-1769911034000-3 | BTCUSDT-SHORT-1769977518000-13 | SHORT | 01:57:14–20:28:31 | 20:25:18–21:09:28 | 20:25:18–20:28:31 |
| BTCUSDT-SHORT-1769929070000-4 | BTCUSDT-SHORT-1769931922000-6 | SHORT | 06:57:50–21:09:27 | 07:45:22–09:58:07 | 07:45:22–09:58:07 |
| BTCUSDT-SHORT-1769929070000-4 | BTCUSDT-SHORT-1769940184000-7 | SHORT | 06:57:50–21:09:27 | 10:03:04–15:27:02 | 10:03:04–15:27:02 |
| BTCUSDT-SHORT-1769929070000-4 | BTCUSDT-SHORT-1769942488000-8 | SHORT | 06:57:50–21:09:27 | 10:41:28–23:06:38 | 10:41:28–21:09:27 |
| BTCUSDT-SHORT-1769929070000-4 | BTCUSDT-SHORT-1769958085000-9 | SHORT | 06:57:50–21:09:27 | 15:01:25–23:09:32 | 15:01:25–21:09:27 |
| BTCUSDT-SHORT-1769929070000-4 | BTCUSDT-SHORT-1769962684000-11 | SHORT | 06:57:50–21:09:27 | 16:18:04–18:08:40 | 16:18:04–18:08:40 |
| BTCUSDT-SHORT-1769929070000-4 | BTCUSDT-SHORT-1769969766000-12 | SHORT | 06:57:50–21:09:27 | 18:16:06–19:57:09 | 18:16:06–21:09:27 |
| BTCUSDT-SHORT-1769929070000-4 | BTCUSDT-SHORT-1769977518000-13 | SHORT | 06:57:50–21:09:27 | 20:25:18–21:09:28 | 20:25:18–21:09:27 |
| BTCUSDT-SHORT-1769940184000-7 | BTCUSDT-SHORT-1769942488000-8 | SHORT | 10:03:04–15:27:02 | 10:41:28–23:06:38 | 10:41:28–15:27:02 |
| BTCUSDT-SHORT-1769940184000-7 | BTCUSDT-SHORT-1769958085000-9 | SHORT | 10:03:04–15:27:02 | 15:01:25–23:09:32 | 15:01:25–15:27:02 |
| BTCUSDT-SHORT-1769942488000-8 | BTCUSDT-SHORT-1769958085000-9 | SHORT | 10:41:28–23:06:38 | 15:01:25–23:09:32 | 15:01:25–23:06:38 |
| BTCUSDT-SHORT-1769942488000-8 | BTCUSDT-SHORT-1769962684000-11 | SHORT | 10:41:28–23:06:38 | 16:18:04–18:08:40 | 16:18:04–18:08:40 |
| BTCUSDT-SHORT-1769942488000-8 | BTCUSDT-SHORT-1769969766000-12 | SHORT | 10:41:28–23:06:38 | 18:16:06–19:57:09 | 18:16:06–23:06:38 |
| BTCUSDT-SHORT-1769942488000-8 | BTCUSDT-SHORT-1769977518000-13 | SHORT | 10:41:28–23:06:38 | 20:25:18–21:09:28 | 20:25:18–23:06:38 |
| BTCUSDT-SHORT-1769942488000-8 | BTCUSDT-SHORT-1769980511000-15 | SHORT | 10:41:28–23:06:38 | 21:15:11–22:12:21 | 21:15:11–22:12:21 |
| BTCUSDT-SHORT-1769942488000-8 | BTCUSDT-SHORT-1769986285000-18 | SHORT | 10:41:28–23:06:38 | 22:51:25–23:05:47 | 22:51:25–23:06:38 |
| BTCUSDT-SHORT-1769958085000-9 | BTCUSDT-SHORT-1769962684000-11 | SHORT | 15:01:25–23:09:32 | 16:18:04–18:08:40 | 16:18:04–18:08:40 |

## 2. Price overlaps

Two zones price-overlap when their [zoneLow, zoneHigh] intervals intersect.

Price-overlapping pairs (any direction): **63**.
Of those, same-direction: **32**.
Pairs that overlap in BOTH time AND price: **34**.

## 3. Overlap groups (same direction + temporal + price)

A zone group merges zones that are pairwise (same direction) ∧ (temporal overlap) ∧ (price overlap). If group size > 1, the detector is producing several zones over the same market structure.

Total groups: **8** (3 with ≥ 2 zones, 5 singletons).

| Group | Dir | Zones | Active window | Price band | Zone IDs |
|---|---|---|---|---|---|
| 1 | SHORT | 8 | 00:00:37–19:57:09 | 77841.65–79375.45 | BTCUSDT-SHORT-1769904037000-1, BTCUSDT-SHORT-1769911034000-3, BTCUSDT-SHORT-1769929070000-4, BTCUSDT-SHORT-1769931922000-6, BTCUSDT-SHORT-1769940184000-7, BTCUSDT-SHORT-1769942488000-8, BTCUSDT-SHORT-1769958085000-9, BTCUSDT-SHORT-1769969766000-12 |
| 2 | LONG | 1 | 01:12:33–07:04:52 | 78512.55–78683.45 | BTCUSDT-LONG-1769908353000-2 |
| 3 | LONG | 1 | 07:09:41–14:31:19 | 78158.25–78327.95 | BTCUSDT-LONG-1769929781000-5 |
| 4 | LONG | 1 | 15:42:21–20:28:32 | 77113.45–77299.95 | BTCUSDT-LONG-1769960541000-10 |
| 5 | SHORT | 1 | 16:18:04–18:08:40 | 77100.65–77810.85 | BTCUSDT-SHORT-1769962684000-11 |
| 6 | SHORT | 4 | 20:25:18–23:05:47 | 76507.15–77707.95 | BTCUSDT-SHORT-1769977518000-13, BTCUSDT-SHORT-1769980511000-15, BTCUSDT-SHORT-1769986285000-18, BTCUSDT-SHORT-1769990315000-20 |
| 7 | LONG | 1 | 20:32:24–21:09:38 | 76850.91–77707.95 | BTCUSDT-LONG-1769977944000-14 |
| 8 | LONG | 3 | 21:21:56–23:36:10 | 75668.95–77516.25 | BTCUSDT-LONG-1769980916000-16, BTCUSDT-LONG-1769985661000-17, BTCUSDT-LONG-1769989443000-19 |

Successful zones per group: group 1: 6

## 4. Direction clustering

| Metric | LONG | SHORT |
|---|---|---|
| Zones found | 7 | 13 |
| Triggered | 2 | 9 |
| RESOLVED_REACHED | 0 | 6 |
| RESOLVED_FAILED | 2 | 3 |
| INVALIDATED | 4 | 3 |
| NO_TRIGGER | 1 | 1 |
| EXPIRED | 0 | 0 |

**All 6 successful zones are SHORT**. They are part of one or more downward moves on this day. The day's net return was directional, so this matches a directional-tailwind explanation.

## 5. Target duplication — how many unique 2% moves are there?

Two successful zones are considered to have caught the **same** 2% move when:
- they are the same direction, AND
- their `[triggerTs … reachedAt]` time windows overlap, OR
- their target prices are within 0.5% AND their trigger times are within 6 hours.

Successful zones: **6**
Unique 2% moves: **1**

| Move | Dir | Trigger window | Trigger px range | Target px range | Reached window | Zones in this move |
|---|---|---|---|---|---|---|
| 1 | SHORT | 01:07:10–15:17:03 | 77288.35–78566.05 | 75742.58–76994.73 | 15:26:10–23:09:32 | 6 (BTCUSDT-SHORT-1769904037000-1, BTCUSDT-SHORT-1769911034000-3, BTCUSDT-SHORT-1769929070000-4, BTCUSDT-SHORT-1769940184000-7, BTCUSDT-SHORT-1769942488000-8, BTCUSDT-SHORT-1769958085000-9) |

**All 6 "successful" zones share a single 2% move.** The hit-rate of 54.55% reflects 6 zone-credits for what is fundamentally **1 directional event**.

## 6. Cooldown / duplicate detection

For each consecutive pair of same-direction zones, we measure the gap between when the previous zone's active window closed and the next zone's start. Negative gaps mean the new zone started while the previous one was still active.

| Direction | Pair count | Gap min (median, min, max) | Pairs where prev was still active |
|---|---|---|---|
| LONG | 6 | 4.8 / -1432.1 / 71.0 | 2 |
| SHORT | 12 | -485.2 / -1434.3 / 39.1 | 9 |

### Same-direction zones started while a previous one was still active

| Prev id | Next id | Dir | Prev active | Next start | Gap (min) |
|---|---|---|---|---|---|
| BTCUSDT-SHORT-1769977518000-13 | BTCUSDT-SHORT-1769980511000-15 | SHORT | 20:25:18–21:09:28 | 21:15:11 | -1434.3 |
| BTCUSDT-LONG-1769985661000-17 | BTCUSDT-LONG-1769989443000-19 | LONG | 22:41:01–23:36:10 | 23:44:03 | -1432.1 |
| BTCUSDT-SHORT-1769969766000-12 | BTCUSDT-SHORT-1769977518000-13 | SHORT | 18:16:06–19:57:09 | 20:25:18 | -1411.8 |
| BTCUSDT-LONG-1769980916000-16 | BTCUSDT-LONG-1769985661000-17 | LONG | 21:21:56–22:11:01 | 22:41:01 | -1410.0 |
| BTCUSDT-SHORT-1769986285000-18 | BTCUSDT-SHORT-1769990315000-20 | SHORT | 22:51:25–23:05:47 | 23:58:35 | -1387.2 |
| BTCUSDT-SHORT-1769911034000-3 | BTCUSDT-SHORT-1769929070000-4 | SHORT | 01:57:14–20:28:31 | 06:57:50 | -810.7 |
| BTCUSDT-SHORT-1769904037000-1 | BTCUSDT-SHORT-1769911034000-3 | SHORT | 00:00:37–15:26:10 | 01:57:14 | -808.9 |
| BTCUSDT-SHORT-1769929070000-4 | BTCUSDT-SHORT-1769931922000-6 | SHORT | 06:57:50–21:09:27 | 07:45:22 | -804.1 |
| BTCUSDT-SHORT-1769942488000-8 | BTCUSDT-SHORT-1769958085000-9 | SHORT | 10:41:28–23:06:38 | 15:01:25 | -485.2 |
| BTCUSDT-SHORT-1769958085000-9 | BTCUSDT-SHORT-1769962684000-11 | SHORT | 15:01:25–23:09:32 | 16:18:04 | -411.5 |
| BTCUSDT-SHORT-1769940184000-7 | BTCUSDT-SHORT-1769942488000-8 | SHORT | 10:03:04–15:27:02 | 10:41:28 | -285.6 |

### Proposed deduplication rule

The detector is producing multiple same-direction zones over the same active window and price band. A simple, conservative rule that does **not** require touching strategy thresholds:

```text
Before opening a new candidate of direction D at time T, price band [L, H]:
  if there exists an existing zone Z' of direction D with:
    Z'.status in {CANDIDATE, CONFIRMED, TRIGGERED}
    AND Z'.startTs <= T <= max(Z'.resolvedTs, Z'.triggerTs, Z'.confirmedTs, Z'.startTs)
    AND price band [L, H] intersects [Z'.zoneLow, Z'.zoneHigh]
  then DO NOT open the new candidate.

Optional cooldown: even after Z' resolves, suppress new same-direction
candidates within Z's price band for `cooldownMin` minutes.
```

This is a deduplication rule, not a threshold tune. It belongs in `zoneDetector.ts` — the change is in detector logic but the **strategy thresholds in `config/strategy.default.json` stay identical**.

## 7. Triggered-zone quality (per zone)

| Zone id | Dir | Trigger | MFE % | MAE % | Reached 2 %? | t→target min | overlap_group | unique_move |
|---|---|---|---|---|---|---|---|---|
| BTCUSDT-SHORT-1769904037000-1 | SHORT | 01:07:10 | 3.72 | 0.80 | **yes** | 859.0 | 1 | 1 |
| BTCUSDT-SHORT-1769911034000-3 | SHORT | 06:48:08 | 3.36 | 1.18 | **yes** | 820.4 | 1 | 1 |
| BTCUSDT-SHORT-1769929070000-4 | SHORT | 07:04:52 | 3.12 | 1.42 | **yes** | 844.6 | 1 | 1 |
| BTCUSDT-SHORT-1769940184000-7 | SHORT | 10:36:21 | 3.64 | 0.43 | **yes** | 290.7 | 1 | 1 |
| BTCUSDT-SHORT-1769942488000-8 | SHORT | 14:28:51 | 2.79 | 0.88 | **yes** | 517.8 | 1 | 1 |
| BTCUSDT-SHORT-1769958085000-9 | SHORT | 15:17:03 | 2.13 | 1.47 | **yes** | 472.5 | 1 | 1 |
| BTCUSDT-SHORT-1769969766000-12 | SHORT | 19:57:09 | 1.73 | 1.01 | no | - | 1 | - |
| BTCUSDT-SHORT-1769977518000-13 | SHORT | 21:09:28 | 1.13 | 1.63 | no | - | 6 | - |
| BTCUSDT-LONG-1769980916000-16 | LONG | 22:11:01 | 0.62 | 2.11 | no | - | 8 | - |
| BTCUSDT-LONG-1769985661000-17 | LONG | 23:36:10 | 0.03 | 0.92 | no | - | 8 | - |
| BTCUSDT-SHORT-1769986285000-18 | SHORT | 23:05:47 | 1.43 | 1.10 | no | - | 6 | - |

## 8. Honest verdict

**Are 20 zones really 20 independent zones?**

No. The 20 zones cluster into **8 overlap groups**, of which **3 contain more than one zone**. 11 same-direction zones started while a previous zone of the same direction was still active. The detector is fragmenting the same market structure into multiple zones.

**Are the 6 successful zones 6 independent successes, or 1–2 large moves?**

**1 move.** All 6 successful zones cluster into a single unique 2% move (move 1 in the table above). The 54.55% triggered hit rate on 2026-02-01 reflects 6 zone-credits for fundamentally **one directional event** — not 6 independent edge instances.

**Should we add cooldown / deduplication?**

Yes. The "no same-direction zone may open inside an active same-direction zone's price band" rule above should be added to `zoneDetector.ts` before the next full-day run. It is a behaviour fix, not a threshold tune.

**Can today's 54.55% hit rate be quoted as an honest hit rate?**

**No.** The denominator (11 triggered) is inflated by fragmentation; the numerator (6 reached) is inflated by multiple zones being credited for the same 2% move. After collapsing to unique moves, the honest "events that hit 2%" count for 2026-02-01 is **1**, not 6. Reporting 54.55% without that caveat overstates the strategy's real edge.

**What needs to change before the next full-day run?**

1. Add the same-direction overlap deduplication rule in `zoneDetector.ts` (no threshold change).
2. After the rule lands, re-run 2026-02-01 full-day and report:
   - new zone count (expected to drop materially);
   - new triggered count;
   - new hit rate (likely lower, but more honest);
   - confirm that group sizes are all 1.
3. Then repeat the regime-comparison run on 2026-01-01.
4. Only after dedup, with multiple paid days, consider any threshold tuning.
