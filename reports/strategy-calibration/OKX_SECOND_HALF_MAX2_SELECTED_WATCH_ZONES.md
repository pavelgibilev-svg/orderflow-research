# max2_total_per_day - selected watch zones (concrete list)

**Build:** 2026-05-25T09:39:55+00:00
**Scope:** max2_total_per_day selected zones across 15 ready days
**Ranking rule:** `rank_score = evidence_count + confidence_bonus(HIGH=0.5, MID=0.25) - slow_trigger_penalty`

**Counts:** covered=6, wrong_dir=2, noisy_1.5%=1, missed=21 / total=30

| date | rank | dir | conf-time | confidence | evidence | rank_score | filter | engine class | coverage | lead min | summary |
|---|---:|---|---|---|---:|---:|:---:|---|---|---:|---|
| 2026-03-16 | 1 | LONG | 2026-03-16T00:37:27+00:00 | HIGH | 9 | 9.4 | N | primary_unique_reached_move | **covered_2pct_move** | 176.55 | LONG because aggressive_sell_absorbed; bid_absorbed_sells; bid_refill_score_pres... |
| 2026-03-16 | 2 | LONG | 2026-03-16T00:37:27+00:00 | HIGH | 9 | 9.4 | N | duplicate_reached_move | **covered_2pct_move** | 176.55 | LONG because aggressive_sell_absorbed; bid_absorbed_sells; bid_refill_score_pres... |
| 2026-03-18 | 1 | SHORT | 2026-03-18T00:13:01+00:00 | HIGH | 8 | 8.5 | Y | primary_unique_reached_move | **missed_no_move_in_4h** | None | SHORT because aggressive_buy_absorbed; ask_absorbed_buys; ask_refill_score_prese... |
| 2026-03-18 | 2 | SHORT | 2026-03-18T00:54:55+00:00 | HIGH | 8 | 8.5 | N | invalidated_or_expired | **missed_no_move_in_4h** | None | SHORT because aggressive_buy_absorbed; ask_absorbed_buys; ask_refill_score_prese... |
| 2026-03-19 | 1 | LONG | 2026-03-19T09:18:04+00:00 | HIGH | 9 | 9.5 | N | failed_triggered | **noisy_partial_1_5pct** | None | LONG because aggressive_sell_absorbed; bid_absorbed_sells; bid_refill_score_pres... |
| 2026-03-19 | 2 | LONG | 2026-03-19T13:40:10+00:00 | HIGH | 9 | 9.5 | Y | failed_triggered | **missed_no_move_in_4h** | None | LONG because aggressive_sell_absorbed; bid_absorbed_sells; bid_refill_score_pres... |
| 2026-03-20 | 1 | SHORT | 2026-03-20T00:21:21+00:00 | HIGH | 8 | 8.5 | N | invalidated_or_expired | **missed_no_move_in_4h** | None | SHORT because aggressive_buy_absorbed; ask_absorbed_buys; ask_refill_score_prese... |
| 2026-03-20 | 2 | SHORT | 2026-03-20T00:44:27+00:00 | HIGH | 8 | 8.5 | N | invalidated_or_expired | **missed_no_move_in_4h** | None | SHORT because aggressive_buy_absorbed; ask_absorbed_buys; ask_refill_score_prese... |
| 2026-03-21 | 1 | SHORT | 2026-03-21T00:59:58+00:00 | HIGH | 8 | 8.5 | Y | primary_unique_reached_move | **missed_no_move_in_4h** | None | SHORT because ask_absorbed_buys; ask_refill_score_present; range_compression; vo... |
| 2026-03-21 | 2 | SHORT | 2026-03-21T07:42:37+00:00 | HIGH | 8 | 8.5 | N | duplicate_reached_move | **missed_no_move_in_4h** | None | SHORT because aggressive_buy_absorbed; ask_absorbed_buys; ask_refill_score_prese... |
| 2026-03-22 | 1 | SHORT | 2026-03-22T01:32:41+00:00 | HIGH | 9 | 9.5 | N | duplicate_reached_move | **wrong_direction** | None | SHORT because aggressive_buy_absorbed; ask_absorbed_buys; ask_refill_score_prese... |
| 2026-03-22 | 2 | SHORT | 2026-03-22T03:39:26+00:00 | HIGH | 9 | 9.5 | Y | duplicate_reached_move | **missed_no_move_in_4h** | None | SHORT because aggressive_buy_absorbed; ask_absorbed_buys; ask_refill_score_prese... |
| 2026-03-23 | 1 | SHORT | 2026-03-23T00:14:57+00:00 | HIGH | 8 | 8.5 | Y | failed_triggered | **missed_no_move_in_4h** | None | SHORT because aggressive_buy_absorbed; ask_absorbed_buys; ask_refill_score_prese... |
| 2026-03-23 | 2 | LONG | 2026-03-23T00:22:01+00:00 | HIGH | 8 | 8.5 | N | invalidated_or_expired | **missed_no_move_in_4h** | None | LONG because aggressive_sell_absorbed; bid_absorbed_sells; bid_refill_score_pres... |
| 2026-03-24 | 1 | SHORT | 2026-03-24T06:07:43+00:00 | HIGH | 8 | 8.5 | N | invalidated_or_expired | **covered_2pct_move** | 111.33 | SHORT because aggressive_buy_absorbed; ask_absorbed_buys; ask_refill_score_prese... |
| 2026-03-24 | 2 | SHORT | 2026-03-24T14:36:16+00:00 | HIGH | 8 | 8.5 | Y | failed_triggered | **missed_no_move_in_4h** | None | SHORT because aggressive_buy_absorbed; ask_absorbed_buys; ask_refill_score_prese... |
| 2026-03-25 | 1 | LONG | 2026-03-25T00:13:04+00:00 | HIGH | 8 | 8.5 | Y | failed_triggered | **missed_no_move_in_4h** | None | LONG because aggressive_sell_absorbed; bid_absorbed_sells; bid_refill_score_pres... |
| 2026-03-25 | 2 | SHORT | 2026-03-25T01:00:27+00:00 | HIGH | 8 | 8.5 | N | invalidated_or_expired | **missed_no_move_in_4h** | None | SHORT because aggressive_buy_absorbed; ask_absorbed_buys; ask_refill_score_prese... |
| 2026-03-26 | 1 | LONG | 2026-03-26T00:14:56+00:00 | HIGH | 8 | 8.5 | Y | failed_triggered | **missed_no_move_in_4h** | None | LONG because aggressive_sell_absorbed; bid_absorbed_sells; bid_refill_score_pres... |
| 2026-03-26 | 2 | LONG | 2026-03-26T00:24:34+00:00 | HIGH | 8 | 8.5 | Y | failed_triggered | **missed_no_move_in_4h** | None | LONG because aggressive_sell_absorbed; bid_absorbed_sells; bid_refill_score_pres... |
| 2026-03-27 | 1 | LONG | 2026-03-27T18:33:55+00:00 | HIGH | 9 | 9.4 | N | failed_triggered | **missed_no_move_in_4h** | None | LONG because aggressive_sell_absorbed; bid_absorbed_sells; bid_refill_score_pres... |
| 2026-03-27 | 2 | SHORT | 2026-03-27T14:38:37+00:00 | HIGH | 9 | 9.2 | N | failed_triggered | **missed_no_move_in_4h** | None | SHORT because aggressive_buy_absorbed; ask_absorbed_buys; ask_refill_score_prese... |
| 2026-03-28 | 1 | SHORT | 2026-03-28T00:40:41+00:00 | HIGH | 8 | 8.5 | N | failed_triggered | **missed_no_move_in_4h** | None | SHORT because aggressive_buy_absorbed; ask_absorbed_buys; ask_refill_score_prese... |
| 2026-03-28 | 2 | LONG | 2026-03-28T01:06:01+00:00 | HIGH | 8 | 8.5 | N | invalidated_or_expired | **missed_no_move_in_4h** | None | LONG because aggressive_sell_absorbed; bid_absorbed_sells; bid_refill_score_pres... |
| 2026-03-29 | 1 | LONG | 2026-03-29T00:46:44+00:00 | HIGH | 9 | 9.5 | N | failed_triggered | **wrong_direction** | None | LONG because aggressive_sell_absorbed; bid_absorbed_sells; bid_refill_score_pres... |
| 2026-03-29 | 2 | LONG | 2026-03-29T10:52:43+00:00 | HIGH | 9 | 9.5 | Y | failed_triggered | **missed_no_move_in_4h** | None | LONG because aggressive_sell_absorbed; bid_absorbed_sells; bid_refill_score_pres... |
| 2026-03-30 | 1 | LONG | 2026-03-30T02:25:03+00:00 | HIGH | 9 | 9.5 | Y | failed_triggered | **missed_no_move_in_4h** | None | LONG because aggressive_sell_absorbed; bid_absorbed_sells; bid_refill_score_pres... |
| 2026-03-30 | 2 | LONG | 2026-03-30T00:10:48+00:00 | HIGH | 8 | 8.5 | Y | duplicate_reached_move | **covered_2pct_move** | 9.3 | LONG because aggressive_sell_absorbed; bid_absorbed_sells; bid_refill_score_pres... |
| 2026-03-31 | 1 | LONG | 2026-03-31T00:05:34+00:00 | HIGH | 8 | 8.5 | Y | primary_unique_reached_move | **covered_2pct_move** | 80.02 | LONG because aggressive_sell_absorbed; bid_absorbed_sells; bid_refill_score_pres... |
| 2026-03-31 | 2 | LONG | 2026-03-31T00:44:02+00:00 | HIGH | 8 | 8.5 | N | duplicate_reached_move | **covered_2pct_move** | 41.55 | LONG because aggressive_sell_absorbed; bid_absorbed_sells; bid_refill_score_pres... |