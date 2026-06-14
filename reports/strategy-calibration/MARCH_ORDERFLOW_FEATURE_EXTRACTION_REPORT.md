# Orderflow feature extraction report

**Build:** 2026-05-26T11:40:11+00:00
**Source:** trades.csv.gz per day (29 days OKX direct)
**Zones in dataset:** 1043; with trade-derived features computed: 1043

## Extracted features (pre-confirm, no future leak)

- `taker_imb_5m`
- `taker_imb_15m`
- `taker_imb_30m`
- `taker_imb_60m`
- `taker_imb_180m`
- `taker_imb_aligned_5m`
- `taker_imb_aligned_15m`
- `taker_imb_aligned_30m`
- `taker_imb_aligned_60m`
- `taker_imb_aligned_180m`
- `taker_total_vol_15m`
- `taker_total_vol_60m`
- `vol_anomaly_15m_vs_bg`
- `ofi_shift_5m_vs_30m`
- `ofi_shift_aligned`
- `sweep_reclaim_aligned`
- `dist_to_recent_swing_high_pct`
- `dist_to_recent_swing_low_pct`
- `dist_to_4h_mean_pct`
- `pct_correct_move_already_done`
- `is_late_after_50pct_correct_move`
- `is_during_correct_move`
- `pct_opposite_move_already_done`
- `is_during_opposite_move`
- `utc_hour`
- `is_asia_session`
- `is_us_session`

## Features not extracted (with reason)

- `L2 refill speed / size / persistence` — requires book reconstruction across the day; engine cand_*_refill_score kept as proxy
- `L2 liquidity defense / wall persistence` — requires book reconstruction; conf_defended_persistence_sec kept as proxy
- `L2 book imbalance / microprice / spread` — requires per-snapshot book state; not extracted in this pass
- `L2 absorption efficiency (price progress per aggressive volume)` — needs book delta + trade match; we use trade-only vol_anomaly_15m_vs_bg instead
- `Cancel-cluster / quote flicker` — requires per-event book updates; not in scope

## Methodology
- Anchor time = `confirmed_iso` (confirmed-stage moment).
- All window aggregates use ONLY trades with timestamp ≤ anchor (no leak).
- 1-second cumulative sums on (buy_vol, sell_vol, n_trades) → O(1) window queries.
- Sweep/reclaim is computed on OHLC buckets from the same trades file.
- Late-move-completion uses real 2 % movement detection (independent of engine).
- All windows: 5 / 15 / 30 / 60 / 180 minutes ending at confirm time.

## What we did not extract (and why)
- L2 book features (refill speed, liquidity wall persistence, microprice, book imbalance) — would require full book reconstruction; we kept the engine's pre-computed `cand_*_refill_score` / `cand_absorb_score` / `conf_defended_persistence_sec` / `conf_opposite_thinning` instead, and previous research already flagged them as low-separation.
- Per-tick microprice / spread — same reason.
- Cancel-cluster / quote-flicker features — same.

## Honesty note
Trade-only orderflow features capture aggressor flow and price-level reactions. They are *coarser* than full L2 features but useful and leak-free. Treat the resulting separation as a lower bound on what richer book features could deliver.