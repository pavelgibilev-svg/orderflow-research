# FILTER DEFINITIONS — MARCH V1 (frozen)

Build 2026-06-10T18:22:40+00:00 · RESEARCH ONLY · TP=2% · 2.5/3% labels only.
N/A on March cache: book_entropy_top25, ms_thin_path_score, ms_large_walls_on_path, depth_top_of_book, liquidity_void_to_target, L2_update_rate, basis

## Pool
{
  "march_zones": 1043,
  "raw_hit2": 430,
  "raw_strong": 351,
  "unique_hit2_clusters": 74,
  "unique_strong_clusters": 55,
  "unique_hit3_clusters": 48,
  "noise_clusters": 146,
  "missing_data_days": [
    "2026-03-17"
  ],
  "cache_starts": "2026-03-02 (03-01 zones not in cache)"
}

## Filters
### F1_TD_SHORT — TREND_DOWN/SHORT (phase TREND_CONTINUATION)
- features: ['regime=TREND_DOWN', 'prior_move_60m<0', 'no buyer absorption', 'conf>=2 of {reclaim,taker-sell,microprice-down,void-bid-path}']
- thresholds: {'prior_move_60m': '<0', 'confluence': '>=2'}
- vetoes: ['buyer_absorption']
- n=50 W/L/TO 19/22/9 winrate 38.0% PF 0.979 hit2 38.0% stab 0.33 overfit LOW

### F2_SWEEP_REVERSAL — ANY/BOTH (phase SWEEP_REVERSAL)
- features: ['swept_high/low', 'reclaim', 'taker aligned']
- thresholds: {'reclaim_or_sweep_aligned': 1}
- vetoes: ['dirty_exec']
- n=83 W/L/TO 30/43/10 winrate 36.1% PF 0.791 hit2 36.1% stab 0.34 overfit LOW

### F3_ACCUMULATION — RANGE/LONG (phase ACCUMULATION_CANDIDATE)
- features: ['RANGE', 'range_pos<0.4', 'sell pressure', 'absorption/refill/reclaim']
- thresholds: {'range_pos': '<0.4'}
- vetoes: ['overextended']
- n=14 W/L/TO 7/6/1 winrate 50.0% PF 1.323 hit2 50.0% stab 0.58 overfit LOW

### F4_DISTRIBUTION — RANGE/SHORT (phase DISTRIBUTION_CANDIDATE)
- features: ['RANGE', 'range_pos>0.6', 'buy pressure', 'absorption']
- thresholds: {'range_pos': '>0.6'}
- vetoes: ['overextended']
- n=0 W/L/TO 0/0/0 winrate 0.0% PF None hit2 0.0% stab 0.0 overfit HIGH

### F5_SIXBLOCK_4of6 — ANY/BOTH (phase None)
- features: ['6-block confluence>=4', 'no veto']
- thresholds: {'confluence': '>=4/6'}
- vetoes: ['dirty_exec', 'overextended', 'low_liquidity']
- n=192 W/L/TO 70/101/21 winrate 36.5% PF 0.786 hit2 36.5% stab 0.29 overfit LOW
