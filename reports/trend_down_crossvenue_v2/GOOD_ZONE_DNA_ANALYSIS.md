# GOOD ZONE DNA ANALYSIS

Build 2026-06-12T13:42:04+00:00 · qualitative, no tuning.

- n=6 clusters = **3 independent cross-venue moments** (each on Bybit+OKX).
- windows present: ['W1_NOVEMBER', 'W3_JANUARY'] (distributed)
- capital states: {'DISTRIBUTION_INTO_BOUNCE': 6} (all DISTRIBUTION_INTO_BOUNCE by construction — markdown/unwind states never fired)

## 1. Same window or distributed? -> distributed across 2
## 2. Same move type? -> all DISTRIBUTION_INTO_BOUNCE shorts (shorting a bounce into a lower-high).
## 3. Similar CVD/taker flow? -> CVD60 all negative: True; median takerImb30 0.0648.
## 4. Similar effort-vs-result? -> all positive (down driven by selling): False; median 0.0084.
## 5. Similar cross-venue picture? -> yes by definition (both venues agreed state+direction within 30m).
## 6. Same price reaction after aggressive sell? -> N/A from saved artifacts (post-flow response not stored).
## 7. 'Seller really controls' common? -> initiative_control>=1 on all: True; this is the most consistent positive marker.
## 8. 'Not late entry' common? -> median room_to_low 0.7165% (mixed; not a clean shared marker).
## 9. Same liquidity path? -> median spread 0.012bps; depthImb median -0.1947 (not uniform).
## 10. A veto that removes the bad ones? -> cross-venue DISAGREEMENT veto + NO_CONTROL_CHOP no-trade already separate the worst; within the good set, winners had stronger initiative_control/effort_vs_result but n is too small to set a threshold.

## Winners (2) vs losers (4) inside the good set:
- winners median initiative_control 2.5 vs losers 2.0
- winners median effort_vs_result 0.0734 vs losers 0.0032
- winners median room_to_low 0.7165 vs losers 1.5795

GOOD_ZONE_SIMILARITY:
LOW

**Honest note:** PF 1.13 on n=6 (only 3 independent moments) is almost certainly NOISE. The shared traits (net selling, positive initiative_control, effort_vs_result>0, cross-venue agreement) are directionally sensible but cannot be distinguished from chance at this sample size.