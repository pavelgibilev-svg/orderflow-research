# Paper trade results — calibrated selectors (in-sample March)

**Build:** 2026-05-26T11:43:19+00:00
**Target:** strict 2 %  |  **Timeout:** 24 h  |  **Cost:** 0.14 % roundtrip
**Models tested:** 240 (top 12 selectors × 5 entries × 4 stops, minus skips)

## Top 30 by winrate (with ≥10 trades)

| selector | entry | stop | trades | wins | winrate % | exp pre % | exp aft % | PF pre | PF aft | total ret % | maxCL | LONG/SHORT |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `single::ctt_le30::top1_score` | delay_5m | stop_1.5 | 29 | 18 | 62.07 | 0.8863 | 0.7463 | 3.37 | 2.767 | 25.7024 | 2 | L14/S15 |
| `single::ctt_le30::top1_score` | delay_10m | stop_1.5 | 29 | 18 | 62.07 | 0.8737 | 0.7337 | 3.277 | 2.702 | 25.3383 | 2 | L14/S15 |
| `single::session_asia::top1_score` | delay_5m | stop_1.5 | 29 | 17 | 58.62 | 0.7515 | 0.6115 | 2.717 | 2.246 | 21.7947 | 3 | L15/S14 |
| `single::session_asia::top1_score` | delay_10m | stop_1.5 | 29 | 17 | 58.62 | 0.6491 | 0.5091 | 2.239 | 1.876 | 18.8241 | 3 | L15/S14 |
| `single::ctt_le30::top1_score` | confirmed | stop_1.25 | 29 | 17 | 58.62 | 0.8465 | 0.7065 | 3.347 | 2.728 | 24.5476 | 2 | L14/S15 |
| `single::ctt_le30::top1_score` | confirmed | stop_1.5 | 29 | 17 | 58.62 | 0.7775 | 0.6375 | 2.81 | 2.334 | 22.5476 | 2 | L14/S15 |
| `single::ctt_le30::top1_score` | delay_5m | stop_1.25 | 29 | 17 | 58.62 | 0.8346 | 0.6946 | 3.339 | 2.695 | 24.2024 | 2 | L14/S15 |
| `single::ctt_le30::top1_score` | delay_15m | stop_1.5 | 29 | 17 | 58.62 | 0.7529 | 0.6129 | 2.708 | 2.241 | 21.833 | 2 | L14/S15 |
| `dir::LONG+filter_kept+opp_eq0::top1_score` | confirmed | stop_1.5 | 25 | 14 | 56.0 | 0.5957 | 0.4557 | 2.103 | 1.772 | 14.8933 | 5 | L25/S0 |
| `dir::LONG+filter_kept+opp_eq0::top1_score` | delay_5m | stop_1.5 | 25 | 14 | 56.0 | 0.6758 | 0.5358 | 2.407 | 2.01 | 16.8953 | 3 | L25/S0 |
| `dir::LONG+filter_kept+opp_eq0::top1_score` | delay_10m | stop_1.5 | 25 | 14 | 56.0 | 0.6003 | 0.4603 | 2.112 | 1.774 | 15.0085 | 5 | L25/S0 |
| `dir::LONG+filter_kept+opp_eq0::top1_score` | delay_15m | stop_1.5 | 25 | 14 | 56.0 | 0.5983 | 0.4583 | 2.102 | 1.765 | 14.9586 | 5 | L25/S0 |
| `single::session_asia::top1_score` | confirmed | stop_1.25 | 29 | 16 | 55.17 | 0.6481 | 0.5081 | 2.405 | 1.979 | 18.7939 | 3 | L15/S14 |
| `single::session_asia::top1_score` | confirmed | stop_1.5 | 29 | 16 | 55.17 | 0.5681 | 0.4281 | 2.05 | 1.715 | 16.4759 | 3 | L15/S14 |
| `single::session_asia::top1_score` | delay_5m | stop_1.25 | 29 | 16 | 55.17 | 0.6446 | 0.5046 | 2.405 | 1.968 | 18.6944 | 3 | L15/S14 |
| `single::session_asia::top1_score` | delay_15m | stop_1.25 | 29 | 16 | 55.17 | 0.6242 | 0.4842 | 2.302 | 1.893 | 18.1006 | 3 | L15/S14 |
| `single::session_asia::top1_score` | delay_15m | stop_1.5 | 29 | 16 | 55.17 | 0.538 | 0.398 | 1.951 | 1.633 | 15.6006 | 3 | L15/S14 |
| `single::opp_eq0::top1_score` | delay_5m | stop_1.5 | 29 | 16 | 55.17 | 0.6689 | 0.5289 | 2.49 | 2.043 | 19.3973 | 3 | L14/S15 |
| `single::opp_eq0::top1_score` | delay_10m | stop_1.5 | 29 | 16 | 55.17 | 0.6338 | 0.4938 | 2.301 | 1.907 | 18.3808 | 3 | L14/S15 |
| `single::not_during_opp::top1_score` | delay_5m | stop_1.5 | 29 | 16 | 55.17 | 0.6689 | 0.5289 | 2.49 | 2.043 | 19.3973 | 3 | L16/S13 |
| `single::not_during_opp::top1_score` | delay_10m | stop_1.5 | 29 | 16 | 55.17 | 0.6338 | 0.4938 | 2.301 | 1.907 | 18.3808 | 3 | L16/S13 |
| `single::ctt_le30::top1_score` | delay_10m | stop_1.25 | 29 | 16 | 55.17 | 0.7099 | 0.5699 | 2.733 | 2.221 | 20.5883 | 2 | L14/S15 |
| `pair::filter_kept+not_during_opp::top1_score` | delay_5m | stop_1.5 | 29 | 16 | 55.17 | 0.6689 | 0.5289 | 2.49 | 2.043 | 19.3973 | 3 | L16/S13 |
| `pair::filter_kept+not_during_opp::top1_score` | delay_10m | stop_1.5 | 29 | 16 | 55.17 | 0.6338 | 0.4938 | 2.301 | 1.907 | 18.3808 | 3 | L16/S13 |
| `pair::opp_eq0+not_late::top1_score` | delay_5m | stop_1.5 | 29 | 16 | 55.17 | 0.6689 | 0.5289 | 2.49 | 2.043 | 19.3973 | 3 | L14/S15 |
| `pair::opp_eq0+not_late::top1_score` | delay_10m | stop_1.5 | 29 | 16 | 55.17 | 0.6338 | 0.4938 | 2.301 | 1.907 | 18.3808 | 3 | L14/S15 |
| `pair::opp_eq0+not_during_opp::top1_score` | delay_5m | stop_1.5 | 29 | 16 | 55.17 | 0.6689 | 0.5289 | 2.49 | 2.043 | 19.3973 | 3 | L14/S15 |
| `pair::opp_eq0+not_during_opp::top1_score` | delay_10m | stop_1.5 | 29 | 16 | 55.17 | 0.6338 | 0.4938 | 2.301 | 1.907 | 18.3808 | 3 | L14/S15 |
| `single::range180_very_low::top1_score` | delay_5m | stop_1.5 | 28 | 15 | 53.57 | 0.5779 | 0.4379 | 2.131 | 1.767 | 16.1799 | 3 | L13/S15 |
| `single::range180_very_low::top1_score` | delay_10m | stop_1.5 | 28 | 15 | 53.57 | 0.4687 | 0.3287 | 1.776 | 1.492 | 13.1224 | 3 | L13/S15 |

## Top 20 by winrate (any size, including small samples) — overfit prone
| selector | entry | stop | trades | winrate % | exp aft % | PF aft | overfit risk |
|---|---|---|---:|---:|---:|---:|---|
| `single::ctt_le30::top1_score` | delay_5m | stop_1.5 | 29 | 62.07 | 0.7463 | 2.767 | LOW |
| `single::ctt_le30::top1_score` | delay_10m | stop_1.5 | 29 | 62.07 | 0.7337 | 2.702 | LOW |
| `single::session_asia::top1_score` | delay_5m | stop_1.5 | 29 | 58.62 | 0.6115 | 2.246 | LOW |
| `single::session_asia::top1_score` | delay_10m | stop_1.5 | 29 | 58.62 | 0.5091 | 1.876 | LOW |
| `single::ctt_le30::top1_score` | confirmed | stop_1.25 | 29 | 58.62 | 0.7065 | 2.728 | LOW |
| `single::ctt_le30::top1_score` | confirmed | stop_1.5 | 29 | 58.62 | 0.6375 | 2.334 | LOW |
| `single::ctt_le30::top1_score` | delay_5m | stop_1.25 | 29 | 58.62 | 0.6946 | 2.695 | LOW |
| `single::ctt_le30::top1_score` | delay_15m | stop_1.5 | 29 | 58.62 | 0.6129 | 2.241 | LOW |
| `dir::LONG+filter_kept+opp_eq0::top1_score` | confirmed | stop_1.5 | 25 | 56.0 | 0.4557 | 1.772 | LOW |
| `dir::LONG+filter_kept+opp_eq0::top1_score` | delay_5m | stop_1.5 | 25 | 56.0 | 0.5358 | 2.01 | LOW |
| `dir::LONG+filter_kept+opp_eq0::top1_score` | delay_10m | stop_1.5 | 25 | 56.0 | 0.4603 | 1.774 | LOW |
| `dir::LONG+filter_kept+opp_eq0::top1_score` | delay_15m | stop_1.5 | 25 | 56.0 | 0.4583 | 1.765 | LOW |
| `single::session_asia::top1_score` | confirmed | stop_1.25 | 29 | 55.17 | 0.5081 | 1.979 | LOW |
| `single::session_asia::top1_score` | confirmed | stop_1.5 | 29 | 55.17 | 0.4281 | 1.715 | LOW |
| `single::session_asia::top1_score` | delay_5m | stop_1.25 | 29 | 55.17 | 0.5046 | 1.968 | LOW |
| `single::session_asia::top1_score` | delay_15m | stop_1.25 | 29 | 55.17 | 0.4842 | 1.893 | LOW |
| `single::session_asia::top1_score` | delay_15m | stop_1.5 | 29 | 55.17 | 0.398 | 1.633 | LOW |
| `single::opp_eq0::top1_score` | delay_5m | stop_1.5 | 29 | 55.17 | 0.5289 | 2.043 | LOW |
| `single::opp_eq0::top1_score` | delay_10m | stop_1.5 | 29 | 55.17 | 0.4938 | 1.907 | LOW |
| `single::not_during_opp::top1_score` | delay_5m | stop_1.5 | 29 | 55.17 | 0.5289 | 2.043 | LOW |