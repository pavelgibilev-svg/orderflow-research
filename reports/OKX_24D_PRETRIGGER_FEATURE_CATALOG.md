# OKX 24-date pre-trigger feature catalog

**Total features:** 24 (of which 12 are the v1-12)

All features are observable AT or BEFORE `zone.triggerTs`. Sources:
  - `zone.reasons[stage in {candidate, confirmed, trigger}].conditions`
  - `zone.scores.*` (frozen at trigger transition)
  - `zone.startTs / confirmedTs / triggerTs` (timing-only derivations)
  - `zone.zoneLow / zoneHigh / triggerPrice / targetPrice` (geometry only, no future price)

## A. Features available

| feature | stage | v1? | n present | missing % | min | max | mean |
|---|---|:---:|---:|---:|---:|---:|---:|
| `cand_pressure_against` | @candidate | yes | 784 | 0.0% | 0.5500181884321571 | 0.8543621013133209 | 0.5995602391379249 |
| `cand_absorb_score` | @candidate | yes | 784 | 0.0% | 0.6000195974387393 | 0.8793414626729801 | 0.6488613938330247 |
| `cand_refill_with` | @candidate | yes | 784 | 0.0% | 0.4863813524480623 | 0.5063282177809872 | 0.5001352987852624 |
| `conf_cycles_seen` | @confirmed | yes | 772 | 1.5% | 3.0 | 182.0 | 58.8419689119171 |
| `conf_age_min` | @confirmed | yes | 772 | 1.5% | 3.0 | 58.95 | 12.226964594127807 |
| `conf_defended_persistence_sec` | @confirmed | yes | 772 | 1.5% | 180.0 | 3537.0 | 733.6178756476684 |
| `candidate_to_confirm_min` | derived/geometry | yes | 772 | 1.5% | 3.0 | 58.95 | 12.226964594127807 |
| `confirm_to_trigger_min` | derived/geometry | yes | 469 | 40.2% | 0.4166666666666667 | 751.95 | 69.70870646766168 |
| `total_pre_trigger_min` | derived/geometry | yes | 469 | 40.2% | 4.116666666666666 | 775.0833333333334 | 80.56105188343994 |
| `trig_flow_multiplier` | @trigger | yes | 469 | 40.2% | 1.4000246472364286 | 16.335600375234545 | 1.9880680174016605 |
| `trig_break_pct` | @trigger | yes | 469 | 40.2% | 0.05017884567836016 | 1.5203888479174683 | 0.20395495740017408 |
| `score_absorption` | @score | yes | 784 | 0.0% | 0.6000299456699988 | 0.9029650329896494 | 0.649408296812247 |
| `cand_prior_move_pct` | @candidate | — | 784 | 0.0% | 0.0 | 0.008386456237807509 | 0.00033112964812692604 |
| `cand_range_compression` | @candidate | — | 784 | 0.0% | 1.0 | 1.0 | 1.0 |
| `conf_opposite_thinning` | @confirmed | — | 772 | 1.5% | 0.49103798545274213 | 0.5099533471810391 | 0.5001507517267927 |
| `conf_void_score` | @confirmed | — | 772 | 1.5% | 1.0 | 1.0 | 1.0 |
| `trig_side_flow_ok` | @trigger | — | 469 | 40.2% | 1.0 | 1.0 | 1.0 |
| `score_liquidity_void` | @score | — | 784 | 0.0% | 1.0 | 1.0 | 1.0 |
| `score_ofi` | @score | — | 784 | 0.0% | -0.5207061063887347 | 0.4940571596454855 | 0.0008341663996744577 |
| `score_refill` | @score | — | 784 | 0.0% | 0.4890337302485828 | 0.5095796170894332 | 0.5001520886300609 |
| `score_trigger` | @score | — | 469 | 40.2% | 0.9611784391778387 | 1.0 | 0.9877298382050557 |
| `zone_width_pct` | derived/geometry | — | 784 | 0.0% | 0.10005002501248952 | 4.903858200592772 | 0.3734170797223246 |
| `target_distance_pct` | derived/geometry | — | 469 | 40.2% | 1.9999999999999913 | 2.000000000000013 | 2.000000000000002 |
| `n_quality_flags` | derived/geometry | — | 784 | 0.0% | 0.0 | 0.0 | 0.0 |

## B. Forbidden as features (post-trigger / lookahead)

- targets.* (mfePct, maePct, outcome, reachedAt, timeToTargetMin, maxDrawdownBeforeTargetPct, endPrice, endTs)
- resolvedTs (used only as outcome timing, not as feature)
- status (final state — used only as outcome label)
- uniqueMoveId / isPrimaryMoveZone / duplicateMoveCredit / moveClusterSize (assigned by move-clustering AFTER resolve)
- future day_return / future max move / future regime label
- reasons[stage in {expire, invalidate}].conditions (post-trigger / post-resolve)
- qualityFlags entries added at resolution time
- regime_bucket as a per-zone feature (allowed only for stratified analysis)
