# TG_watch_score_v1 proposal (research only; NOT integrated)

**Build:** 2026-05-25T15:31:41+00:00
**Components: 8 (from feature separation top + anti-features)**

| component | weight | kind | meaning |
|---|---:|---|---|
| `local_range_180m_pct_neg` | -0.37 | numeric_scaled | feature scaled by Cohen's d -0.3731 |
| `prior_move_60m_pct_pos` | 0.26 | numeric_scaled | feature scaled by Cohen's d 0.2629 |
| `trig_break_pct_pos` | 0.26 | numeric_scaled | feature scaled by Cohen's d 0.2575 |
| `local_range_60m_pct_neg` | -0.26 | numeric_scaled | feature scaled by Cohen's d -0.2565 |
| `prior_move_30m_pct_pos` | 0.24 | numeric_scaled | feature scaled by Cohen's d 0.2377 |
| `local_range_30m_pct_neg` | -0.21 | numeric_scaled | feature scaled by Cohen's d -0.2131 |
| `local_realized_vol_15m_neg` | -0.2 | numeric_scaled | feature scaled by Cohen's d -0.2003 |
| `prior_move_180m_pct_antifeature_penalty` | -1.0 | anti_feature | positive d vs bad (0.1251) BUT negative d vs wrong (-0.3032) — direction-flipped |

**Ranking rule:** rank confirmed zones by sum of component contributions; pick top-1 or top-2 per day

Each component is observable AT confirmation; no future leak. v1 derived from full-March separation analysis; train/test validation showed which patterns are stable.