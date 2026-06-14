# BINANCE L2 RECONSTRUCTION BUG — critical finding

**Build date:** 2026-06-03 · Data-sanity audit (no Tardis). **Recorder DATA is OK; the CONVERTER reconstruction is broken.**

## What was found

Reconstructing the Binance order book from `data/binance-historical/BTCUSDT/<date>/incremental_book_L2.csv.gz`
produces a **persistently crossed book** (best_bid ≥ best_ask) for almost the entire day after the first few seconds.

- Per-event crossed rate (05-23, first 10 min): **100%** of events crossed, **median magnitude 208 bps (~2.1%)**, both sides present.
- Across the 10-day 60-min sample: **337,890** crossed events on Binance vs **0** on OKX.

## Root cause (converter, not recorder)

`scripts/binance-live/inventory_audit_normalize_convert.py :: convert_raw_depth_to_l2`:

```
# 1) Seed snapshot from the first 1s book snapshot ...
            ...
            n_snapshots_emitted += 1
            break  # only first snapshot as seed   <-- only ONE seed for the whole day
# 2) Stream raw_depth_events as deltas (depth-limited @depth diffs)
```

- The seed is a **single 50-level 1-second snapshot** (~$14 wide window).
- `raw_depth_events` are **depth-limited diffs** around the current price.
- As price drifts away from the seed window, the diff stream **never touches the stale far levels**, so they are
  never deleted. The stale side stays put while the live side moves → the reconstructed top-of-book crosses by
  roughly the distance price has drifted from the seed.

**Evidence — seed vs first trade staleness (varies with drift):**

| date | seed mid | first trade | staleness |
|---|--:|--:|--:|
| 2026-05-21 | 77701.6 | 77515.0 | +0.24% |
| 2026-05-25 | 76600.1 | 77030.3 | −0.56% |
| 2026-05-29 | 74649.1 | 73591.5 | +1.44% |
| 2026-05-23 | 77129.7 | 75513.2 | +2.14% |

The staleness magnitude == the eventual crossed magnitude → confirms the mechanism.

## Impact on prior research

All **top-of-book-dependent** Binance L2 features (`max(bid)`/`min(ask)`-based) are **corrupted** beyond the first
seconds of each day:
- `microprice_aligned_delta_*` (≈0 / degenerate — now explained: stale bid never moves),
- `spread_*`, `top1_supportive_persistence`, `ms_thin_path_score` / liquidity-void (mid is wrong → ±2% window wrong),
- `depth_imbalance`, top1/top5/top20 depth.

**Whole-book flow** features (`dl2_supp_minus_opp_net_flow_*`) are *less* affected (add/cancel deltas occur near the
live price), but their **absolute scale is a separate unit issue** (OKX contracts vs Binance BTC — see unit audit).

⇒ The earlier "feature unit shift" addendum was **only partially correct**: the flow-scale gap is units, but the
microprice/persistence/spread/void degeneration is **this reconstruction bug**, not units and not a venue edge.

## The recorder data is sufficient to fix it

`orderbook_snapshots_1s.jsonl` contains a fresh **snapshot every second** (the converter currently uses only the
first). The book can be reconstructed correctly by **re-seeding from the 1s snapshots** (periodically, or using them
as the primary book with diffs only between seconds). No re-recording needed.

## Required actions before further strategy research

1. Fix `convert_raw_depth_to_l2` to re-seed from the per-second snapshots (remove the single-seed `break`).
2. Re-convert Binance 2026-05-21..30.
3. Recompute all Binance L2 features; treat prior Binance top-of-book features as **invalid**.
4. Re-run cross-venue parity on the corrected book before resuming selector/opportunity research.

## Flags

```
RECONSTRUCTION_ISSUE_FOUND            = YES
CONVERTER_ISSUE_FOUND                 = YES (single stale seed; no re-seed)
RECORDER_ISSUE_FOUND                  = NO  (1s snapshots + diffs + trades all present)
BINANCE_TOPOFBOOK_FEATURES_CORRUPTED  = YES
BINANCE_FLOW_FEATURES_CORRUPTED       = NO (but unit-scaled)
FIX_AVAILABLE_FROM_EXISTING_DATA      = YES (re-seed from orderbook_snapshots_1s)
NEXT_RESEARCH_CAN_CONTINUE            = NO (blocked on converter fix + feature recompute)
```
