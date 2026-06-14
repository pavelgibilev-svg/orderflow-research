# TG_watch_score_v0 proposal (research only, NOT integrated)

**Build:** 2026-05-25T09:39:55+00:00
**Name:** `TG_watch_score_v0`
**Scope:** research-only, NOT integrated into engine, NOT changing thresholds
**Intended use:** rank confirmed zones; pick top-1 or top-2 per day; explainable

## Components

| name | weight | meaning | field | why helps | overfit risk |
|---|---:|---|---|---|---|
| `absorb_score_high` | 1.5 | candidate.absorbScore >= 0.6 — aggressive sells (LONG) / buys (SHORT) absorbed | `reasons[stage=candidate].conditions.absorbScore` | highest separation in audit | LOW (orthogonal to direction) |
| `refill_present` | 1.0 | candidate refill score present in direction-appropriate side | `reasons[stage=candidate].conditions.bidRefillScore / askRefillScore` | indicates passive liquidity defending the zone | LOW |
| `ofi_aligned` | 1.5 | score.ofiScore > +0.05 for LONG / < -0.05 for SHORT | `scores.ofiScore` | directional orderflow agreement | MEDIUM (already in engine) |
| `flow_multiplier_strong` | 1.0 | reasons[trigger].conditions.flowMultiplier >= 1.5 | `reasons[stage=trigger].conditions.flowMultiplier` | trigger break supported by strong flow | LOW (only adds when trigger happens) |
| `defended_long` | 1.0 | reasons[confirmed].conditions.defendedPersistenceSec >= 600 | `reasons[stage=confirmed].conditions.defendedPersistenceSec` | zone has held for >= 10 minutes — more reliable than just one bounce | LOW |
| `early_timing_bonus` | 0.5 | confirmation time within first 1h of zone candidate | `(confirmedTs - startTs) / 60000.0` | earlier zones tend to have more move ahead | LOW |
| `slow_trigger_penalty` | -1.0 | confirm_to_trigger > 180m — penalize | `(triggerTs - confirmedTs) / 60000.0` | very-slow triggers usually mean the move started without us | LOW |
| `wrong_direction_risk` | -1.5 | opposite-direction confirmed candidate within last 60m with equal/higher score | `scan opposite-direction zones in same time window` | engine confused by chop — likely wrong direction | MEDIUM (need to define 'equal/higher' carefully) |
| `late_after_move_risk` | -1.5 | prior-move (downMovePct/upMovePct) >= 1.0% before candidate | `reasons[candidate].conditions.downMovePct / upMovePct` | if direction already moved 1%+, R/R to 2% target is bad | LOW |
| `weak_evidence_penalty` | -1.0 | evidence_count < 3 — likely noise | `internal count of features triggered` | noise filter | LOW |

**Ranking rule:** pick zones with score >= 3.0; rank by score desc; cap at 2/day; cap at 1/direction/day to prevent same-side spam

**DO NOT integrate this into engine; do NOT change zoneDetector thresholds. This is a research-layer score for shadow Telegram observer.**