# In-sample selector optimization (full search results)

**Build:** 2026-05-26T11:40:12+00:00
**Selectors evaluated:** 368
**Baseline confirmed precision:** 11.79 %

## Top 30 by precision (with ≥20 selected for usability)

| selector | n | /day | good | wrong | precision % | recall % | wrong rate % | H1 prec | H2 prec |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `single::session_asia::top1_score` | 29 | 1.0 | 12 | 1 | 41.38 | 9.76 | 3.45 | 42.86 | 40.0 |
| `single::range180_very_low::top1_score` | 28 | 0.966 | 11 | 2 | 39.29 | 8.94 | 7.14 | 38.46 | 40.0 |
| `single::opp_eq0::top1_score` | 29 | 1.0 | 10 | 1 | 34.48 | 8.13 | 3.45 | 42.86 | 26.67 |
| `single::not_during_opp::top1_score` | 29 | 1.0 | 10 | 1 | 34.48 | 8.13 | 3.45 | 42.86 | 26.67 |
| `single::ctt_le30::top1_score` | 29 | 1.0 | 10 | 2 | 34.48 | 8.13 | 6.9 | 42.86 | 26.67 |
| `pair::filter_kept+not_during_opp::top1_score` | 29 | 1.0 | 10 | 1 | 34.48 | 8.13 | 3.45 | 42.86 | 26.67 |
| `pair::opp_eq0+not_late::top1_score` | 29 | 1.0 | 10 | 1 | 34.48 | 8.13 | 3.45 | 42.86 | 26.67 |
| `pair::opp_eq0+not_during_opp::top1_score` | 29 | 1.0 | 10 | 0 | 34.48 | 8.13 | 0.0 | 42.86 | 26.67 |
| `pair::not_late+not_during_opp::top1_score` | 29 | 1.0 | 10 | 1 | 34.48 | 8.13 | 3.45 | 42.86 | 26.67 |
| `pair::sweep_reclaim+not_during_opp::top1_score` | 29 | 1.0 | 10 | 1 | 34.48 | 8.13 | 3.45 | 42.86 | 26.67 |
| `triple::filter_kept+not_late+not_during_opp::top1_score` | 29 | 1.0 | 10 | 1 | 34.48 | 8.13 | 3.45 | 42.86 | 26.67 |
| `triple::filter_kept+ctt_le60+not_during_opp::top1_score` | 29 | 1.0 | 10 | 1 | 34.48 | 8.13 | 3.45 | 42.86 | 26.67 |
| `triple::filter_kept+sweep_reclaim+not_during_opp::top1_score` | 29 | 1.0 | 10 | 1 | 34.48 | 8.13 | 3.45 | 42.86 | 26.67 |
| `triple::not_late+not_during_opp+sweep_reclaim::top1_score` | 29 | 1.0 | 10 | 1 | 34.48 | 8.13 | 3.45 | 42.86 | 26.67 |
| `quad::filter_kept+not_late+not_during_opp+sweep_reclaim::top1_score` | 29 | 1.0 | 10 | 1 | 34.48 | 8.13 | 3.45 | 42.86 | 26.67 |
| `triple::filter_kept+range180_low+not_late::top2_score` | 56 | 1.931 | 18 | 4 | 32.14 | 14.63 | 7.14 | 34.62 | 30.0 |
| `pair::filter_kept+opp_eq0::top1_score` | 28 | 0.966 | 9 | 1 | 32.14 | 7.32 | 3.57 | 38.46 | 26.67 |
| `triple::filter_kept+opp_eq0+not_late::top1_score` | 28 | 0.966 | 9 | 1 | 32.14 | 7.32 | 3.57 | 38.46 | 26.67 |
| `triple::filter_kept+opp_eq0+not_during_opp::top1_score` | 28 | 0.966 | 9 | 0 | 32.14 | 7.32 | 0.0 | 38.46 | 26.67 |
| `triple::filter_kept+range180_low+not_late::top1_score` | 28 | 0.966 | 9 | 2 | 32.14 | 7.32 | 7.14 | 30.77 | 33.33 |
| `quad::filter_kept+not_late+not_during_opp+prior60_le1::top1_score` | 28 | 0.966 | 9 | 1 | 32.14 | 7.32 | 3.57 | 38.46 | 26.67 |
| `pair::range180_low+not_late::top2_score` | 58 | 2.0 | 18 | 5 | 31.03 | 14.63 | 8.62 | 32.14 | 30.0 |
| `baseline_all_confirmed::top1_score` | 29 | 1.0 | 9 | 2 | 31.03 | 7.32 | 6.9 | 35.71 | 26.67 |
| `single::filter_kept::top1_score` | 29 | 1.0 | 9 | 2 | 31.03 | 7.32 | 6.9 | 35.71 | 26.67 |
| `single::opp_le1::top1_score` | 29 | 1.0 | 9 | 2 | 31.03 | 7.32 | 6.9 | 35.71 | 26.67 |
| `single::not_late::top1_score` | 29 | 1.0 | 9 | 2 | 31.03 | 7.32 | 6.9 | 35.71 | 26.67 |
| `single::sweep_reclaim::top1_score` | 29 | 1.0 | 9 | 2 | 31.03 | 7.32 | 6.9 | 35.71 | 26.67 |
| `single::range180_low::top1_score` | 29 | 1.0 | 9 | 2 | 31.03 | 7.32 | 6.9 | 28.57 | 33.33 |
| `single::ctt_le60::top1_score` | 29 | 1.0 | 9 | 2 | 31.03 | 7.32 | 6.9 | 35.71 | 26.67 |
| `pair::filter_kept+not_late::top1_score` | 29 | 1.0 | 9 | 2 | 31.03 | 7.32 | 6.9 | 35.71 | 26.67 |

## Top 30 by precision (any selected count, including small samples)

| selector | n | /day | good | precision % | recall % | H1 prec | H2 prec | overfit risk |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `dir::LONG+filter_kept+not_late+ofi_pos::nocap` | 2 | 0.069 | 2 | 100.0 | 1.63 | None | 100.0 | HIGH |
| `dir::LONG+filter_kept+not_late+ofi_pos::top1_score` | 2 | 0.069 | 2 | 100.0 | 1.63 | None | 100.0 | HIGH |
| `dir::LONG+filter_kept+not_late+ofi_pos::top2_score` | 2 | 0.069 | 2 | 100.0 | 1.63 | None | 100.0 | HIGH |
| `dir::LONG+filter_kept+not_late+ofi_pos::top1perdir_score` | 2 | 0.069 | 2 | 100.0 | 1.63 | None | 100.0 | HIGH |
| `single::session_asia::top1_score` | 29 | 1.0 | 12 | 41.38 | 9.76 | 42.86 | 40.0 | MEDIUM |
| `single::range180_very_low::top1_score` | 28 | 0.966 | 11 | 39.29 | 8.94 | 38.46 | 40.0 | MEDIUM |
| `quad::filter_kept+opp_eq0+not_late+ofi_aligned_pos::top1_score` | 8 | 0.276 | 3 | 37.5 | 2.44 | 0.0 | 75.0 | HIGH |
| `quad::filter_kept+opp_eq0+not_late+ofi_aligned_pos::top1perdir_score` | 8 | 0.276 | 3 | 37.5 | 2.44 | 0.0 | 75.0 | HIGH |
| `quad::filter_kept+not_late+zone_width_le04+ofi_aligned_pos::top1_score` | 8 | 0.276 | 3 | 37.5 | 2.44 | 0.0 | 60.0 | HIGH |
| `quad::filter_kept+not_late+zone_width_le04+ofi_aligned_pos::top1perdir_score` | 8 | 0.276 | 3 | 37.5 | 2.44 | 0.0 | 60.0 | HIGH |
| `single::opp_eq0::top1_score` | 29 | 1.0 | 10 | 34.48 | 8.13 | 42.86 | 26.67 | MEDIUM |
| `single::not_during_opp::top1_score` | 29 | 1.0 | 10 | 34.48 | 8.13 | 42.86 | 26.67 | MEDIUM |
| `single::ctt_le30::top1_score` | 29 | 1.0 | 10 | 34.48 | 8.13 | 42.86 | 26.67 | MEDIUM |
| `pair::filter_kept+not_during_opp::top1_score` | 29 | 1.0 | 10 | 34.48 | 8.13 | 42.86 | 26.67 | MEDIUM |
| `pair::opp_eq0+not_late::top1_score` | 29 | 1.0 | 10 | 34.48 | 8.13 | 42.86 | 26.67 | MEDIUM |
| `pair::opp_eq0+not_during_opp::top1_score` | 29 | 1.0 | 10 | 34.48 | 8.13 | 42.86 | 26.67 | MEDIUM |
| `pair::not_late+not_during_opp::top1_score` | 29 | 1.0 | 10 | 34.48 | 8.13 | 42.86 | 26.67 | MEDIUM |
| `pair::sweep_reclaim+not_during_opp::top1_score` | 29 | 1.0 | 10 | 34.48 | 8.13 | 42.86 | 26.67 | MEDIUM |
| `triple::filter_kept+not_late+not_during_opp::top1_score` | 29 | 1.0 | 10 | 34.48 | 8.13 | 42.86 | 26.67 | MEDIUM |
| `triple::filter_kept+ctt_le60+not_during_opp::top1_score` | 29 | 1.0 | 10 | 34.48 | 8.13 | 42.86 | 26.67 | MEDIUM |
| `triple::filter_kept+sweep_reclaim+not_during_opp::top1_score` | 29 | 1.0 | 10 | 34.48 | 8.13 | 42.86 | 26.67 | MEDIUM |
| `triple::not_late+not_during_opp+sweep_reclaim::top1_score` | 29 | 1.0 | 10 | 34.48 | 8.13 | 42.86 | 26.67 | MEDIUM |
| `quad::filter_kept+not_late+not_during_opp+sweep_reclaim::top1_score` | 29 | 1.0 | 10 | 34.48 | 8.13 | 42.86 | 26.67 | MEDIUM |
| `quad::filter_kept+opp_eq0+not_late+ofi_aligned_pos::nocap` | 9 | 0.31 | 3 | 33.33 | 2.44 | 0.0 | 75.0 | HIGH |
| `quad::filter_kept+opp_eq0+not_late+ofi_aligned_pos::top2_score` | 9 | 0.31 | 3 | 33.33 | 2.44 | 0.0 | 75.0 | HIGH |
| `quad::filter_kept+not_late+zone_width_le04+ofi_aligned_pos::nocap` | 9 | 0.31 | 3 | 33.33 | 2.44 | 0.0 | 60.0 | HIGH |
| `quad::filter_kept+not_late+zone_width_le04+ofi_aligned_pos::top2_score` | 9 | 0.31 | 3 | 33.33 | 2.44 | 0.0 | 60.0 | HIGH |
| `triple::filter_kept+range180_low+not_late::top2_score` | 56 | 1.931 | 18 | 32.14 | 14.63 | 34.62 | 30.0 | LOW |
| `pair::filter_kept+opp_eq0::top1_score` | 28 | 0.966 | 9 | 32.14 | 7.32 | 38.46 | 26.67 | MEDIUM |
| `triple::filter_kept+opp_eq0+not_late::top1_score` | 28 | 0.966 | 9 | 32.14 | 7.32 | 38.46 | 26.67 | MEDIUM |