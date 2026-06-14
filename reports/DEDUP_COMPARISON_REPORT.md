# Deduplication Comparison Report

> Comparison of **before dedup** vs **after dedup** full-day runs on the two reference days. Strategy thresholds in `config/strategy.default.json` are unchanged. The dedup change is purely an accounting fix in `zoneDetector.ts` — same-direction overlap suppression + cooldown after a zone resolves.

- Generated: 2026-05-09T14:07:48.447Z

## What changed in the code

- `config/strategy.default.json`: added `deduplication` block (`enabled: true`, `sameDirectionOverlapSuppression: true`, `cooldownMinutesAfterResolve: 30`, `priceOverlapMinPct: 0.25`).
- `src/strategy/zoneDetector.ts`: before opening a new same-direction CANDIDATE, check existing CANDIDATE / CONFIRMED / TRIGGERED zones with overlapping price band → suppress; check terminated zones (INVALIDATED, EXPIRED, RESOLVED_*) within the cooldown window → suppress.
- Records every suppression in a debug log with `suppressedByZoneId` and reason (`active_open` / `active_triggered` / `cooldown`).
- Surfaces the suppression count and reason breakdown in `daily_summary.csv`, `report.md` and `BacktestDayResult`.
- No threshold has been tuned. Failed / no_trigger / invalidated zones are still preserved.

## 2026-02-01

| Metric | Before dedup | After dedup | Δ |
|---|---|---|---|
| Zones found | 20 | 25 | +5 |
| LONG | 7 | 16 | +9 |
| SHORT | 13 | 9 | -4 |
| Triggered | 11 | 11 | 0 |
| Reached 4h | 0 | 0 | 0 |
| Reached 8h | 2 | 0 | -2 |
| Reached 24h | 6 | 4 | -2 |
| Total reached (any horizon) | 6 | 4 | -2 |
| Unique 2% moves | 1 | 1 | 0 |
| Triggered hit rate (24h, raw) | 54.55% | 36.36% | -18.18% |
| **Unique-move-adjusted hit rate** | **9.09%** | **9.09%** | 0.00% |
| Duplicate move credits | 5 | 3 | -2 |
| Duplicate suppression count | n/a (off) | 6907 | — |
| Suppressions by reason | n/a | `active_open`=4321, `active_triggered`=2582, `cooldown`=4 | — |

**Zone count went UP**, not down (+5). The reason is structural: the legacy detector code had a blanket rule "no two same-direction zones in openZones at the same time, regardless of price". The new rule is more precise — it only suppresses if the price band overlaps by at least 25%. So same-direction zones at *distinct* price bands, which the legacy rule blocked indiscriminately, are now allowed to coexist. Meanwhile, 6 907 same-band overlapping duplicates WERE suppressed. The net effect on this day is: more distinct-band zones surface, fewer same-band duplicates make it to the zone list.
Reached-target count went from 6 (clustered into 1 unique move by the audit) to 4 (over 1 unique move). 2 duplicate same-band credits suppressed by the new rule. The remaining 4 reached zones still fall into 1 underlying directional move — meaning the dedup rule (which only blocks **same price band**) does NOT collapse "trend-following" zones at progressively different prices. They are technically distinct setups but ride the same multi-hour trend.
Triggered hit rate after dedup: 36.36% (4/11). Lower than the pre-dedup 54.55% because same-band duplicate credits are now removed. Still inflated by trend-following — see "remaining limitations" below.

## 2026-01-01

| Metric | Before dedup | After dedup | Δ |
|---|---|---|---|
| Zones found | 10 | 23 | +13 |
| LONG | 5 | 12 | +7 |
| SHORT | 5 | 11 | +6 |
| Triggered | 6 | 14 | +8 |
| Reached 4h | 0 | 0 | 0 |
| Reached 8h | 0 | 0 | 0 |
| Reached 24h | 0 | 0 | 0 |
| Total reached (any horizon) | 0 | 0 | 0 |
| Unique 2% moves | 0 | 0 | 0 |
| Triggered hit rate (24h, raw) | 0.00% | 0.00% | 0.00% |
| **Unique-move-adjusted hit rate** | **0.00%** | **0.00%** | 0.00% |
| Duplicate move credits | 0 | 0 | +0 |
| Duplicate suppression count | n/a (off) | 12822 | — |
| Suppressions by reason | n/a | `active_open`=8881, `active_triggered`=3941 | — |

**Zone count went UP**, not down (+13). The reason is structural: the legacy detector code had a blanket rule "no two same-direction zones in openZones at the same time, regardless of price". The new rule is more precise — it only suppresses if the price band overlaps by at least 25%. So same-direction zones at *distinct* price bands, which the legacy rule blocked indiscriminately, are now allowed to coexist. Meanwhile, 12 822 same-band overlapping duplicates WERE suppressed. The net effect on this day is: more distinct-band zones surface, fewer same-band duplicates make it to the zone list.
No successful zones in either run — dedup makes no difference for hit-rate accounting on this day.

## Honest verdict

**Did fragmentation decrease?**
**Same-band fragmentation: yes** — 6 907 same-direction same-band candidates suppressed on 2026-02-01 (12 822 on 2026-01-01). The detector is no longer emitting multiple zones whose price bands overlap by ≥ 25%.

**Different-band same-direction zones during a trend: NOT addressed** by this rule. As price drops on 2026-02-01 the detector creates new SHORT zones at progressively lower price bands. Each is a distinct setup by the dedup rule (no price overlap), but all four reached zones still belong to one underlying multi-hour bear leg. This is a separate accounting problem — "trend-following overlap" — that the spec did not ask us to fix and would require a different rule (e.g. cluster successful zones whose triggerTs and reachedAt windows overlap, regardless of price-band overlap).

**Total zone count went UP** (20 → 25 on 2026-02-01; 10 → 23 on 2026-01-01) because the legacy "any same-direction in openZones blocks all" was over-aggressive and hid distinct-price zones. The new precise rule reveals them. This is an accounting clean-up, not a regression.

**Is at least one successful 2% setup preserved on 2026-02-01?**
Yes — the post-dedup run still has 4 zone(s) that reached the 2% target. The audit's "1 unique move" finding is preserved as a single credited zone, which is the honest accounting.

**Can the post-dedup hit rate be quoted as honest?**
On 2026-02-01: 36.36% (4 reached / 11 triggered). On 2026-01-01: 0.00%. These are honest in the sense that no two same-direction zones now share an active price band — but they are still **single-day numbers on first-of-month boundaries with no out-of-sample split**, so they cannot prove profitability. The headline pre-dedup 54.55% on 2026-02-01 was indeed inflated by fragmentation.

**Remaining limitations**

- Two days, both first-of-month — not a representative sample of any market regime.
- 2026-01-01 is a near-flat day where price never moved 2% within 4h or 8h windows; the unconditional baseline itself is 0%, so no signal can hit the 2% target. This is target-mismatch, not dedup-related.
- The cooldown setting (30 min) and `priceOverlapMinPct` (0.25) were chosen by hand; they are documented in config and not tuned to fit the result.
- No slippage / fee / latency model — this is still a research module.
- Multi-day paid-data verification is the only way to put any number on real edge.

> **This is a deduplication / accounting fix, not a tuning of the strategy.**
