# Dynamic L2 reconstruction report

**Build:** 2026-05-26T21:57:39+00:00
**Source:** `incremental_book_L2.csv.gz` per day (29 days)
**Zones with dynamic L2 features:** 1043 / 1043

## Method
- Stream incremental book updates chronologically per day (~130M events/day).
- Maintain bid_book / ask_book dicts (price -> amount).
- Per-second microprice samples (deque, last 80 min).
- Per-minute event bins (last 72 min): add_vol, cancel_vol, n_events, n_large_*.
- Per-zone in-band event tracking: for each pending zone, collect events whose price is within zone_low * 0.998 to zone_high * 1.002.
- At each zone's confirmedTs (anchor), snapshot all rolling buffers and compute window aggregates over 30s/1m/5m/15m/30m/60m.

## Quality
- All windows END at anchor — no future-leak.
- Microprice sampled exactly once per UTC second.
- Event bins quantized to 1-minute granularity (acceptable for 5m-60m windows; ~5 % aliasing for 1m window).

## Memory / runtime
- ~440K updates/sec processing throughput.
- ~5 min per day × 29 days = ~2.5 hours total streaming.
- Per-zone in-band buffer: up to ~50K events.

## Limitations
- 'Wall persistence' is approximated via top-1 supportive size >= 50 lots persistence (sec count in 5m).
- Full per-price-level history NOT tracked (would cost ~200 MB extra RAM per day).
- Cancel-replace disambiguation not done; cancel_vol includes BOTH pure cancels AND cancel-leg of replace.
