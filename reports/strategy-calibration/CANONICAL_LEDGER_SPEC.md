# Canonical strict-ledger spec (CANONICAL_STRICT_LEDGER_v1)

**Build:** 2026-05-23T10:09:35+00:00

## Definition

- **Input:** filtered triggered zones (`fast_trigger ≤ 60m`, `duplicate_60m`, `price_band ≤ 1.0%`); NO `uniqueMoveId` in decision; NO future-leak.
- **Sorting:** ascending by `triggerTs`.
- **Position rule:** one trade at a time. New signals ignored while position is open.
- **Position carry:** position carries across UTC day boundary until target/stop/timeout.
- **Max holding time:** 24h from entry.
- **Entry method:** next 1s bucket at or after entry timestamp; price = bucket.last.
- **Entry timestamp default:** `triggerTs` (alternative variants: `delay_{N}min`, `retest`).

## Direction semantics

- LONG: target = entry × 1.02, stop = entry × 0.99
- SHORT: target = entry × 0.98, stop = entry × 1.01
- target strict 2 %, stop default 1 %, timeout 24h

## Tie-breaks

- If target and stop occur in the SAME 1s bucket, conservative: stop first.

## Costs

- fees/slippage NOT included in primary result. Cost diagnostic is separate.

## Reproducibility

- Deterministic given inputs: (per-day 1s buckets, filtered zones JSON, filter params).
- `CANONICAL_LEDGER_DEFINED` = **YES**
- `CANONICAL_LEDGER_REPRODUCIBLE` = **YES**