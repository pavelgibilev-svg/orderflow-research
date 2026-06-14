# L2 microstructure feature extraction

**Build:** 2026-05-26T14:32:07+00:00
**Source:** `incremental_book_L2.csv.gz` per day (29 days OKX direct)
**Zones with L2 features extracted:** 966 / 1043

## Extracted features

- `spread_bps`
- `top1_bid_amount`
- `top1_ask_amount`
- `top5_bid_sum`
- `top5_ask_sum`
- `top20_bid_sum`
- `top20_ask_sum`
- `top5_imbalance`
- `top20_imbalance`
- `microprice_dev_bps`
- `update_rate_30s`
- `l2_imb5_aligned`
- `l2_imb20_aligned`
- `l2_microprice_aligned`
- `depth_top1_ratio_aligned`

## Methodology
- Streamed incremental book updates chronologically per day.
- Maintained per-side dict `price → amount` (book has ~400 levels per side from Tardis snapshot).
- At each zone's `confirmed_iso` timestamp, snapshotted current book state and computed:
  - spread (bps), best bid/ask, mid
  - top-1, top-5, top-20 depth on each side
  - depth imbalance top-5 and top-20
  - microprice and its deviation from mid
  - update rate over last 30 s (events/sec)
- Direction-aligned variants: `l2_imb5_aligned` etc. — positive = supportive of trade direction.

## Features NOT extracted (and why)
- Refill speed after market hits: would require tracking aggressor trades and matching them to book deletions in real time. Out of scope for this pass.
- Wall persistence / lifetime: would require keeping per-level history; ~100 MB+ in RAM for full day. Out of scope.
- Cancel/replace ratio: deltas with amount==0 give cancels but no separation of cancel-and-replace vs pure cancel. Partial extraction possible.
- L2 sweep/reclaim: we have a trade-derived `sweep_reclaim_aligned` already.

## Honesty note
Even these basic L2 features (spread, depth, imbalance, microprice) are MORE than what trade-only features give. If they don't push precision past 50 %, the gap to 70 % is data/regime-bound, not feature-bound.