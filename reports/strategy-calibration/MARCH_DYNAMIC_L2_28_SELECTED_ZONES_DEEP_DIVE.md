# March dynamic L2 — 28 selected zones / 29 paper trades — deep dive

**Build:** 2026-05-27T07:39:58+00:00
**Scope:** IN-SAMPLE March 2026 OKX direct, 29 days. NOT production proof.
**Excel:** `MARCH_DYNAMIC_L2_SELECTED_ZONES_DEEP_DIVE.xlsx`

## Selectors
- **PRECISION (28 zones):** `DL2::P::dist_to_recent_swing_high_pct_le_0.321 + prior_move_180m_pct_le_0.5155 ::top1`
- **PAPER     (29 trades):** `DL2::S::dist_to_recent_swing_high_pct_le_0.4616 ::top1 | confirmed | stop_1.5`

## 1. How many trades in best dynamic L2 paper model on March?
- **29 paper trades.** One per day (top-1 per day by `explainable_score_l2_dyn`).

## 2. Why 28 zones vs 29 trades?
- The two selectors are DIFFERENT:
  - The 28-zone selector adds a second filter `prior_move_180m_pct <= 0.5155` AND tighter swing threshold (0.321). One March day has no candidate that passes both -> 28.
  - The 29-trade paper selector uses only the looser swing threshold (0.4616) — every day has at least one candidate -> 29 top-1 picks.

## 3. Exact trade model used
- Entry: at `confirmed_iso` of selected zone — `entry_strategy='trigger'` (canonical ledger semantics: enter at next available bucket after the timestamp).
- Direction: as detected by engine (LONG / SHORT).
- Target: strict 2 % in the trade direction.
- Stop: 1.5 % against the trade direction.
- Timeout: 24 h after entry.
- Cost: 0.14 % roundtrip subtracted for after-cost metrics.
- Tie-break for target+stop in same 1s bucket: **stop first** (conservative).

## 4. What is 'direction correct but not WIN'?
- The trade direction matches the local market move direction, but the trade did not reach the strict 2 % target before stop or timeout.
- Four sub-classes:
  - `stop_before_later_target`: stop hit, then target reached LATER within 24h — bad stop placement.
  - `no_2pct_followthrough`: correct direction but price never reached full 2 %.
  - `timeout_near_win`: pos timeout >= +1 %.
  - `timeout_positive_small`: pos timeout < +1 %.

## 5. Direction-correct-but-not-win count: **4** of 29
- stop_before_later_target: **0**
- no_2pct_followthrough: **3**
- timeout_near_win: **0**
- timeout_positive_small: **1**

## 6. Wrong-direction losses: **6**

## 7. Correct-direction stop-before-later-target: **0**

## 8. Timeout / near-win: **1** (timeout positive total)

## 9. What separates 14 GOOD from 14 BAD (28-zone selector)?
- GOOD: 14, BAD: 13, MID: 1 (counts within 28-zone selector).
- See Excel sheet `Good_vs_Bad_14_14` for full list and patterns.
- GOOD zones cluster on Asia session (~75 %), small abs prior_move (mostly < 0.4 %), and tight dist_to_swing_high (mostly < 0.2 %).
- BAD zones often confirmed during ongoing impulse, larger prior move, or in europe/us sessions.

## 10. Winners vs Losers (29-trade paper)
- Top discriminators (|Cohen's d| ranked): see Excel sheet `Winners_vs_Losers`.
- In small samples (~10-15 each side), most |d| < 0.5 — not enough power to nail single feature.

## 11. Confirm logic — exact
- See Excel sheet `Confirm_Logic`.
- Engine emits CANDIDATE on initial detection (absorb + refill + prior move into zone + range compression).
- CONFIRMED is fired after `conf_cycles_seen` defended cycles + opposite thinning + persistence threshold.
- TRIGGER fires when break_pct beyond zone + side_flow_ok (confirms direction).

## 12. Why CONFIRMED is noisy?
- All engine `score_*` fields saturate near 1.0 on ~all candidates: they distinguish 'is candidate' (was there an absorption setup at all) rather than 'is good zone'.
- The HIGH confidence in previous engine output was effectively 'any confirmed' = HIGH.
- Filtering at confirmed needs EXTERNAL features (L2 dynamics, microprice, sweep/reclaim, prior_move, swing-distance, session, time-of-day) — exactly what this research adds.

## 13. Microstructure features needed next
Priority order (see Excel `Next_Feature_Ideas`):
1. Per-level wall lifetime (per-event L2 history).
2. Refill-after-hit logic (trade-book joint stream).
3. OKX liquidations / forced flow stream.
4. Cross-venue Binance L2 divergence.
5. OI / funding / liquidation cluster context.
6. Macro news event blackout flag.

## 14. TG shadow now?
- Best selector: precision **58.62 %** winrate after cost; PF after cost **1.922**; expectancy **+0.5268 %/trade**; max consecutive losses 3.
- As an explicitly-labelled IN-SAMPLE research-only TG shadow with ~1 alert/day — acceptable.
- As a production signal — **NO**. Needs OOS validation on April when data arrives.

## 15. Next concrete step
- Build per-level wall lifetime extractor as the next L2 feature.
- Fetch OKX liquidations stream for March, tag selected zones.
- Once April data arrives, OOS validate the current best selector AS-IS first, then with new features.

## Summary numbers

- total trades: **29**
- wins: **17**
- losses: **9**
- timeouts: **3**
- winrate: **58.62 %**
- expectancy after cost: **+0.5268 %/trade**
- total return after cost: **+15.2771 %**
- PF after cost: **1.922**
- max consecutive losses: 3
- wrong-direction losses: **6**
- correct-dir but not WIN: **4**
- stop-before-later-target: **0**
- no-2pct-followthrough: **3**