# Stage-specific selector results (leak-free per stage)

**Build:** 2026-05-26T12:58:57+00:00

## Stage: candidate
- n_selectors evaluated: 3240
- 70 % precision with min 20: **False**

### Top 5 with min 20 selected
| selector | n | /day | precision % | recall % | wrong % | H1 prec | H2 prec | LONG | SHORT |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `CAND::P::utc_hour_le_4.0+cand_refill_with_ge_0.4998::top1` | 29 | 1.0 | 41.38 | 9.76 | 0.0 | 42.86 | 40.0 | 42.86 | 40.0 |
| `CAND::P::utc_hour_le_4.0+cand_absorb_score_le_0.6176::top1` | 28 | 0.966 | 39.29 | 8.94 | 7.14 | 30.77 | 46.67 | 38.46 | 40.0 |
| `CAND::S::utc_hour_le_2.0::top1` | 29 | 1.0 | 37.93 | 8.94 | 0.0 | 42.86 | 33.33 | 40.0 | 35.71 |
| `CAND::S::is_session_open_2h_TRUE::top1` | 29 | 1.0 | 37.93 | 8.94 | 3.45 | 42.86 | 33.33 | 43.75 | 30.77 |
| `CAND::P::utc_hour_le_4.0+is_session_open_2h_TRUE::top1` | 29 | 1.0 | 37.93 | 8.94 | 3.45 | 42.86 | 33.33 | 43.75 | 30.77 |

### Top 5 with min 10 selected (smaller sample, overfit-prone)
| selector | n | /day | precision % |
|---|---:|---:|---:|
| `CAND::P::utc_hour_le_4.0+cand_refill_with_ge_0.4998::top1` | 29 | 1.0 | 41.38 |
| `CAND::P::utc_hour_le_4.0+cand_absorb_score_le_0.6176::top1` | 28 | 0.966 | 39.29 |
| `CAND::S::utc_hour_le_2.0::top1` | 29 | 1.0 | 37.93 |
| `CAND::S::is_session_open_2h_TRUE::top1` | 29 | 1.0 | 37.93 |
| `CAND::P::utc_hour_le_4.0+is_session_open_2h_TRUE::top1` | 29 | 1.0 | 37.93 |

## Stage: confirmed
- n_selectors evaluated: 4236
- 70 % precision with min 20: **False**

### Top 5 with min 20 selected
| selector | n | /day | precision % | recall % | wrong % | H1 prec | H2 prec | LONG | SHORT |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `CONF::P::taker_total_vol_15m_le_69071.8+utc_hour_le_4.0::top1` | 28 | 0.966 | 42.86 | 9.76 | 0.0 | 38.46 | 46.67 | 36.36 | 47.06 |
| `CONF::S::taker_total_vol_15m_le_55572.16::top1` | 29 | 1.0 | 41.38 | 9.76 | 3.45 | 35.71 | 46.67 | 36.36 | 44.44 |
| `CONF::P::dist_to_recent_swing_high_pct_le_0.321+utc_hour_le_4.0::top1` | 29 | 1.0 | 41.38 | 9.76 | 0.0 | 42.86 | 40.0 | 46.15 | 37.5 |
| `CONF::P::dist_to_recent_swing_high_pct_le_0.321+utc_hour_le_8.0::top1` | 29 | 1.0 | 41.38 | 9.76 | 0.0 | 42.86 | 40.0 | 50.0 | 35.29 |
| `CONF::P::taker_total_vol_15m_le_105386.84+dist_to_recent_swing_high_pct_le_0.321::top1` | 27 | 0.931 | 40.74 | 8.94 | 0.0 | 41.67 | 40.0 | 45.45 | 37.5 |

### Top 5 with min 10 selected (smaller sample, overfit-prone)
| selector | n | /day | precision % |
|---|---:|---:|---:|
| `CONF::P::taker_total_vol_15m_le_69071.8+utc_hour_le_4.0::top1` | 28 | 0.966 | 42.86 |
| `CONF::S::taker_total_vol_15m_le_55572.16::top1` | 29 | 1.0 | 41.38 |
| `CONF::P::dist_to_recent_swing_high_pct_le_0.321+utc_hour_le_4.0::top1` | 29 | 1.0 | 41.38 |
| `CONF::P::dist_to_recent_swing_high_pct_le_0.321+utc_hour_le_8.0::top1` | 29 | 1.0 | 41.38 |
| `CONF::P::taker_total_vol_15m_le_105386.84+dist_to_recent_swing_high_pct_le_0.321::top1` | 27 | 0.931 | 40.74 |

## Stage: trigger
- n_selectors evaluated: 4832
- 70 % precision with min 20: **False**

### Top 5 with min 20 selected
| selector | n | /day | precision % | recall % | wrong % | H1 prec | H2 prec | LONG | SHORT |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `TRIG::P::opp_dir_zones_active_60m_le_0.0+dist_to_recent_swing_high_pct_le_0.9593::top1` | 29 | 1.0 | 48.28 | 19.72 | 0.0 | 50.0 | 46.67 | 47.06 | 50.0 |
| `TRIG::P::opp_dir_zones_active_60m_le_1.0+dist_to_recent_swing_high_pct_le_0.9593::top1` | 29 | 1.0 | 44.83 | 18.31 | 3.45 | 42.86 | 46.67 | 43.75 | 46.15 |
| `TRIG::P::opp_dir_zones_active_60m_le_1.0+dist_to_recent_swing_high_pct_le_0.9593::top1` | 29 | 1.0 | 44.83 | 18.31 | 3.45 | 42.86 | 46.67 | 43.75 | 46.15 |
| `TRIG::P::opp_dir_zones_active_60m_le_0.0+utc_hour_le_3.0::top1` | 29 | 1.0 | 44.83 | 18.31 | 3.45 | 42.86 | 46.67 | 53.33 | 35.71 |
| `TRIG::P::opp_dir_zones_active_60m_le_0.0+utc_hour_le_7.0::top1` | 29 | 1.0 | 44.83 | 18.31 | 6.9 | 42.86 | 46.67 | 53.33 | 35.71 |

### Top 5 with min 10 selected (smaller sample, overfit-prone)
| selector | n | /day | precision % |
|---|---:|---:|---:|
| `TRIG::P::opp_dir_zones_active_60m_le_0.0+dist_to_recent_swing_high_pct_le_0.9593::top1` | 29 | 1.0 | 48.28 |
| `TRIG::P::opp_dir_zones_active_60m_le_1.0+dist_to_recent_swing_high_pct_le_0.9593::top1` | 29 | 1.0 | 44.83 |
| `TRIG::P::opp_dir_zones_active_60m_le_1.0+dist_to_recent_swing_high_pct_le_0.9593::top1` | 29 | 1.0 | 44.83 |
| `TRIG::P::opp_dir_zones_active_60m_le_0.0+utc_hour_le_3.0::top1` | 29 | 1.0 | 44.83 |
| `TRIG::P::opp_dir_zones_active_60m_le_0.0+utc_hour_le_7.0::top1` | 29 | 1.0 | 44.83 |
