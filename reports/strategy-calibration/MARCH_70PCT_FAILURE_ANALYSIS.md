# 70 % failure analysis (why leak-free can't reach 70 % on March)

**Build:** 2026-05-26T12:38:35+00:00

## Headline reasons
- Reaching 70 % precision needs a 6x lift over baseline ~12 %.
- Existing leak-free features give at most ~35-45 % precision at ≥20 selected.
- Reason: GOOD and BAD zones overlap heavily on every leak-free feature individually.
- Per-feature overlap: BAD zones land inside the GOOD's p10-p90 range >80 % of the time on most features.
- Even multi-feature confluence cannot push BAD out — features correlate, so adding 3-4 filters collapses sample size without big precision gain.
- After 0.14 % cost, ~30 % winrate with 2:1 risk/reward is the realistic ceiling unless we add: (a) L2 features, (b) external (Binance / liquidations) features, (c) macro/news flag.

## Per-feature overlap (BAD inside GOOD's p10-p90)

| feature | good range p10-p90 | BAD in range % | good n | bad n |
|---|---|---:|---:|---:|
| `conf_void_score` | [1.0, 1.0] | 100.0 | 123 | 774 |
| `score_liquidity_void` | [1.0, 1.0] | 100.0 | 123 | 774 |
| `same_dir_zones_active_60m` | [0.0, 2.0] | 93.41 | 123 | 774 |
| `cand_prior_move_pct` | [0.0, 0.001057368590231606] | 93.02 | 123 | 774 |
| `conf_age_min` | [3.0, 27.583333333333332] | 91.34 | 123 | 774 |
| `conf_defended_persistence_sec` | [180.0, 1655.0] | 91.34 | 123 | 774 |
| `opp_dir_zones_active_60m` | [0.0, 2.0] | 90.57 | 123 | 774 |
| `score_trigger` | [0.9675551203725601, 1.0] | 90.18 | 71 | 438 |
| `conf_opposite_thinning` | [0.4985962894444347, 0.501959908661141] | 85.53 | 123 | 774 |
| `score_absorption` | [0.6013128985751718, 0.7154133045604815] | 82.3 | 123 | 774 |

## Top false positives — BAD zones with HIGH explainable_score

| date | dir | confirmed | coverage | score | filter | late | during_opp | taker30 | ofi_aligned | sweep |
|---|---|---|---|---:|:---:|:---:|:---:|---:|---:|:---:|
| 2026-03-08 | SHORT | 2026-03-08T04:05:17+00:00 | missed_no_move_in_4h | 3.8838 | Y | N | N | -0.1383 | 0.0592 | Y |
| 2026-03-18 | SHORT | 2026-03-18T06:31:30+00:00 | missed_no_move_in_4h | 3.8687 | Y | N | N | -0.1514 | 0.0526 | Y |
| 2026-03-26 | LONG | 2026-03-26T00:24:34+00:00 | missed_no_move_in_4h | 3.8407 | Y | N | N | -0.1564 | 0.0124 | Y |
| 2026-03-27 | SHORT | 2026-03-27T00:20:17+00:00 | missed_no_move_in_4h | 3.836 | Y | N | N | -0.0316 | -0.1073 | Y |
| 2026-03-25 | LONG | 2026-03-25T03:13:50+00:00 | missed_no_move_in_4h | 3.8304 | Y | N | N | -0.1142 | -0.0156 | Y |
| 2026-03-21 | LONG | 2026-03-21T00:08:08+00:00 | missed_no_move_in_4h | 3.7964 | Y | N | N | 0.1234 | -0.8702 | Y |
| 2026-03-09 | SHORT | 2026-03-09T00:13:27+00:00 | missed_no_move_in_4h | 3.7846 | Y | N | N | -0.2213 | 0.1353 | Y |
| 2026-03-28 | LONG | 2026-03-28T00:20:17+00:00 | missed_no_move_in_4h | 3.7757 | Y | N | N | 0.1038 | -0.3946 | Y |
| 2026-03-07 | LONG | 2026-03-07T00:24:57+00:00 | missed_no_move_in_4h | 3.7631 | Y | N | N | 0.1177 | -0.5548 | Y |
| 2026-03-14 | SHORT | 2026-03-14T00:18:25+00:00 | missed_no_move_in_4h | 3.7461 | Y | N | N | 0.0791 | -0.5282 | Y |
| 2026-03-18 | SHORT | 2026-03-18T00:13:01+00:00 | missed_no_move_in_4h | 3.7032 | Y | N | N | -0.166 | -0.0843 | Y |
| 2026-03-25 | LONG | 2026-03-25T00:12:01+00:00 | missed_no_move_in_4h | 3.6627 | Y | N | N | -0.0444 | -0.2283 | Y |
| 2026-03-26 | LONG | 2026-03-26T00:14:56+00:00 | missed_no_move_in_4h | 3.6379 | Y | N | N | -0.3372 | 0.0148 | Y |
| 2026-03-19 | SHORT | 2026-03-19T22:55:51+00:00 | missed_no_move_in_4h | 3.6309 | Y | N | N | 0.3036 | -0.494 | Y |
| 2026-03-27 | LONG | 2026-03-27T06:56:39+00:00 | missed_no_move_in_4h | 3.6168 | Y | N | N | -0.0439 | -0.3592 | Y |

## Top false negatives — GOOD zones with LOW explainable_score

| date | dir | confirmed | matched % | lead min | score | filter | late | taker30 | ofi_aligned | sweep |
|---|---|---|---:|---:|---:|:---:|:---:|---:|---:|:---:|
| 2026-03-11 | SHORT | 2026-03-11T10:23:49+00:00 | 2.0228 | 196.37 | 0.1505 | N | Y | 0.0528 | -0.237 | Y |
| 2026-03-31 | SHORT | 2026-03-31T01:29:06+00:00 | 3.5721 | 5.7 | 0.6564 | N | N | -0.1654 | 0.0427 | Y |
| 2026-03-31 | SHORT | 2026-03-31T10:19:46+00:00 | 2.0382 | 239.15 | 0.7148 | N | N | 0.098 | -0.297 | Y |
| 2026-03-10 | SHORT | 2026-03-10T08:06:20+00:00 | 2.8238 | 86.42 | 0.7668 | N | N | -0.1874 | -0.2473 | Y |
| 2026-03-10 | SHORT | 2026-03-10T08:44:10+00:00 | 2.8238 | 48.58 | 0.8435 | N | N | 0.0016 | -0.3078 | Y |
| 2026-03-31 | LONG | 2026-03-31T09:52:43+00:00 | 2.7664 | 4.47 | 0.8623 | N | N | -0.0092 | -0.2969 | Y |
| 2026-03-11 | SHORT | 2026-03-11T12:02:38+00:00 | 2.0228 | 97.55 | 0.9014 | N | Y | 0.2635 | -0.4995 | Y |
| 2026-03-16 | LONG | 2026-03-16T06:16:04+00:00 | 2.2946 | 148.88 | 0.9925 | N | N | -0.0584 | -0.1103 | Y |
| 2026-03-12 | SHORT | 2026-03-12T11:23:47+00:00 | 2.0832 | 21.78 | 1.0639 | N | N | 0.0182 | -0.1974 | Y |
| 2026-03-23 | SHORT | 2026-03-23T05:18:54+00:00 | 2.0389 | 38.08 | 1.0664 | N | N | -0.2992 | 0.0456 | Y |
| 2026-03-03 | SHORT | 2026-03-03T15:44:52+00:00 | 2.204 | 41.32 | 1.1325 | N | N | -0.0589 | -0.0543 | Y |
| 2026-03-16 | LONG | 2026-03-16T08:20:09+00:00 | 2.2946 | 24.8 | 1.173 | N | N | -0.0127 | -0.0972 | Y |
| 2026-03-16 | LONG | 2026-03-16T08:20:09+00:00 | 2.2946 | 24.8 | 1.173 | N | N | -0.0127 | -0.0972 | Y |
| 2026-03-03 | SHORT | 2026-03-03T09:44:01+00:00 | 2.7375 | 148.58 | 1.1894 | N | N | 0.0678 | -0.2119 | Y |
| 2026-03-16 | SHORT | 2026-03-16T10:27:56+00:00 | 2.0801 | 193.88 | 1.1896 | N | N | -0.1076 | -0.0322 | Y |

## Missing data (would help most)
- L2 book state (refill, defense, microprice, void) — strongest candidate for next pass.
- Cross-venue feed (Binance order book + liquidations) for direction confirmation.
- On-chain liquidation cascade flag.
- Calendar / macro news event tag.