# Top selectors — categorized evaluation

**Build:** 2026-05-26T11:40:12+00:00
**Baseline precision: full=11.79 %, H1=13.24 %, H2=10.43 %**

## best_precision_min20: `single::session_asia::top1_score`
- selected: **29** (1.0/day)
- good: 12; bad: 14; wrong: 1; noisy: 1
- **precision: 41.38 %**; recall: 9.76 %; wrong rate: 3.45 %
- LONG: n=15, precision=46.67 %
- SHORT: n=14, precision=35.71 %
- H1: n=14, precision=42.86 %
- H2: n=15, precision=40.0 %
- avg lead: 102.55 min; median: 84.0 min
- max consecutive bad alerts: 5
- **overfit risk: MEDIUM**

## best_precision_min10: `single::session_asia::top1_score`
- selected: **29** (1.0/day)
- good: 12; bad: 14; wrong: 1; noisy: 1
- **precision: 41.38 %**; recall: 9.76 %; wrong rate: 3.45 %
- LONG: n=15, precision=46.67 %
- SHORT: n=14, precision=35.71 %
- H1: n=14, precision=42.86 %
- H2: n=15, precision=40.0 %
- avg lead: 102.55 min; median: 84.0 min
- max consecutive bad alerts: 5
- **overfit risk: MEDIUM**

## best_1_2_alerts_day: `single::session_asia::top1_score`
- selected: **29** (1.0/day)
- good: 12; bad: 14; wrong: 1; noisy: 1
- **precision: 41.38 %**; recall: 9.76 %; wrong rate: 3.45 %
- LONG: n=15, precision=46.67 %
- SHORT: n=14, precision=35.71 %
- H1: n=14, precision=42.86 %
- H2: n=15, precision=40.0 %
- avg lead: 102.55 min; median: 84.0 min
- max consecutive bad alerts: 5
- **overfit risk: MEDIUM**

## best_recall_min15pct: `single::not_late::nocap`
- selected: **925** (31.897/day)
- good: 121; bad: 665; wrong: 126; noisy: 49
- **precision: 13.08 %**; recall: 98.37 %; wrong rate: 13.62 %
- LONG: n=455, precision=13.85 %
- SHORT: n=470, precision=12.34 %
- H1: n=433, precision=15.01 %
- H2: n=492, precision=11.38 %
- avg lead: 95.58 min; median: 85.95 min
- max consecutive bad alerts: 149
- **overfit risk: LOW**

## best_balanced_f1_min20: `single::session_asia::nocap`
- selected: **443** (15.276/day)
- good: 81; bad: 281; wrong: 70; noisy: 24
- **precision: 18.28 %**; recall: 65.85 %; wrong rate: 15.8 %
- LONG: n=211, precision=19.43 %
- SHORT: n=232, precision=17.24 %
- H1: n=218, precision=15.6 %
- H2: n=225, precision=20.89 %
- avg lead: 102.03 min; median: 88.78 min
- max consecutive bad alerts: 56
- **overfit risk: LOW**

## best_LONG_min10: `dir::LONG+filter_kept+opp_eq0::top1_score`
- selected: **25** (0.862/day)
- good: 7; bad: 14; wrong: 1; noisy: 1
- **precision: 28.0 %**; recall: 5.69 %; wrong rate: 4.0 %
- LONG: n=25, precision=28.0 %
- SHORT: n=0, precision=None %
- H1: n=11, precision=45.45 %
- H2: n=14, precision=14.29 %
- avg lead: 106.95 min; median: 117.75 min
- max consecutive bad alerts: 7
- **overfit risk: MEDIUM**

## best_SHORT_min10: `dir::SHORT+filter_kept+not_late::top1_score`
- selected: **27** (0.931/day)
- good: 6; bad: 16; wrong: 1; noisy: 1
- **precision: 22.22 %**; recall: 4.88 %; wrong rate: 3.7 %
- LONG: n=0, precision=None %
- SHORT: n=27, precision=22.22 %
- H1: n=13, precision=23.08 %
- H2: n=14, precision=21.43 %
- avg lead: 102.81 min; median: 75.92 min
- max consecutive bad alerts: 11
- **overfit risk: MEDIUM**

## best_explainable: `single::session_asia::top1_score`
- selected: **29** (1.0/day)
- good: 12; bad: 14; wrong: 1; noisy: 1
- **precision: 41.38 %**; recall: 9.76 %; wrong rate: 3.45 %
- LONG: n=15, precision=46.67 %
- SHORT: n=14, precision=35.71 %
- H1: n=14, precision=42.86 %
- H2: n=15, precision=40.0 %
- avg lead: 102.55 min; median: 84.0 min
- max consecutive bad alerts: 5
- **overfit risk: MEDIUM**

## best_train_test_stable_min20: `single::session_asia::top1_score`
- selected: **29** (1.0/day)
- good: 12; bad: 14; wrong: 1; noisy: 1
- **precision: 41.38 %**; recall: 9.76 %; wrong rate: 3.45 %
- LONG: n=15, precision=46.67 %
- SHORT: n=14, precision=35.71 %
- H1: n=14, precision=42.86 %
- H2: n=15, precision=40.0 %
- avg lead: 102.55 min; median: 84.0 min
- max consecutive bad alerts: 5
- **overfit risk: MEDIUM**

## Top 20 raw (sorted by precision)
| selector | n | /day | precision % | recall % | wrong rate % | H1 prec | H2 prec | OF risk |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `dir::LONG+filter_kept+not_late+ofi_pos::nocap` | 2 | 0.069 | 100.0 | 1.63 | 0.0 | None | 100.0 | HIGH |
| `dir::LONG+filter_kept+not_late+ofi_pos::top1_score` | 2 | 0.069 | 100.0 | 1.63 | 0.0 | None | 100.0 | HIGH |
| `dir::LONG+filter_kept+not_late+ofi_pos::top2_score` | 2 | 0.069 | 100.0 | 1.63 | 0.0 | None | 100.0 | HIGH |
| `dir::LONG+filter_kept+not_late+ofi_pos::top1perdir_score` | 2 | 0.069 | 100.0 | 1.63 | 0.0 | None | 100.0 | HIGH |
| `single::session_asia::top1_score` | 29 | 1.0 | 41.38 | 9.76 | 3.45 | 42.86 | 40.0 | MEDIUM |
| `single::range180_very_low::top1_score` | 28 | 0.966 | 39.29 | 8.94 | 7.14 | 38.46 | 40.0 | MEDIUM |
| `quad::filter_kept+opp_eq0+not_late+ofi_aligned_pos::top1_score` | 8 | 0.276 | 37.5 | 2.44 | 0.0 | 0.0 | 75.0 | HIGH |
| `quad::filter_kept+opp_eq0+not_late+ofi_aligned_pos::top1perdir_score` | 8 | 0.276 | 37.5 | 2.44 | 0.0 | 0.0 | 75.0 | HIGH |
| `quad::filter_kept+not_late+zone_width_le04+ofi_aligned_pos::top1_score` | 8 | 0.276 | 37.5 | 2.44 | 0.0 | 0.0 | 60.0 | HIGH |
| `quad::filter_kept+not_late+zone_width_le04+ofi_aligned_pos::top1perdir_score` | 8 | 0.276 | 37.5 | 2.44 | 0.0 | 0.0 | 60.0 | HIGH |
| `single::opp_eq0::top1_score` | 29 | 1.0 | 34.48 | 8.13 | 3.45 | 42.86 | 26.67 | MEDIUM |
| `single::not_during_opp::top1_score` | 29 | 1.0 | 34.48 | 8.13 | 3.45 | 42.86 | 26.67 | MEDIUM |
| `single::ctt_le30::top1_score` | 29 | 1.0 | 34.48 | 8.13 | 6.9 | 42.86 | 26.67 | MEDIUM |
| `pair::filter_kept+not_during_opp::top1_score` | 29 | 1.0 | 34.48 | 8.13 | 3.45 | 42.86 | 26.67 | MEDIUM |
| `pair::opp_eq0+not_late::top1_score` | 29 | 1.0 | 34.48 | 8.13 | 3.45 | 42.86 | 26.67 | MEDIUM |
| `pair::opp_eq0+not_during_opp::top1_score` | 29 | 1.0 | 34.48 | 8.13 | 0.0 | 42.86 | 26.67 | MEDIUM |
| `pair::not_late+not_during_opp::top1_score` | 29 | 1.0 | 34.48 | 8.13 | 3.45 | 42.86 | 26.67 | MEDIUM |
| `pair::sweep_reclaim+not_during_opp::top1_score` | 29 | 1.0 | 34.48 | 8.13 | 3.45 | 42.86 | 26.67 | MEDIUM |
| `triple::filter_kept+not_late+not_during_opp::top1_score` | 29 | 1.0 | 34.48 | 8.13 | 3.45 | 42.86 | 26.67 | MEDIUM |
| `triple::filter_kept+ctt_le60+not_during_opp::top1_score` | 29 | 1.0 | 34.48 | 8.13 | 3.45 | 42.86 | 26.67 | MEDIUM |