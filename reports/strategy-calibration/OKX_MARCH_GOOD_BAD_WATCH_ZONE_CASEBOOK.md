# Good vs Bad watch-zone casebook (top 10 each)

**Build:** 2026-05-25T15:31:41+00:00

## Top 10 GOOD watch zones

| date | dir | confirmed_iso | match move % | lead min | v1 score | filter | engine class |
|---|---|---|---:|---:|---:|:---:|---|
| 2026-03-29 | SHORT | 2026-03-29T00:11:14+00:00 | 3.2533 | 185.05 | 1.4778 | N | invalidated_or_expired |
| 2026-03-29 | SHORT | 2026-03-29T00:06:41+00:00 | 3.2533 | 189.6 | 1.2877 | Y | failed_triggered |
| 2026-03-08 | LONG | 2026-03-08T05:30:31+00:00 | 2.4913 | 226.6 | 1.2733 | N | failed_triggered |
| 2026-03-10 | LONG | 2026-03-10T00:09:20+00:00 | 4.2595 | 140.95 | 1.2043 | Y | primary_unique_reached_move |
| 2026-03-29 | SHORT | 2026-03-29T02:28:15+00:00 | 3.2533 | 48.03 | 1.0896 | N | invalidated_or_expired |
| 2026-03-29 | SHORT | 2026-03-29T02:36:58+00:00 | 3.2533 | 39.32 | 1.0819 | N | invalidated_or_expired |
| 2026-03-30 | LONG | 2026-03-30T00:13:57+00:00 | 3.7056 | 6.15 | 1.0777 | Y | duplicate_reached_move |
| 2026-03-29 | SHORT | 2026-03-29T01:18:42+00:00 | 3.2533 | 117.58 | 1.0715 | N | invalidated_or_expired |
| 2026-03-02 | LONG | 2026-03-02T00:27:38+00:00 | 2.0434 | 43.65 | 1.0691 | N | duplicate_reached_move |
| 2026-03-23 | SHORT | 2026-03-23T05:18:54+00:00 | 2.0389 | 38.08 | 1.0395 | N | failed_triggered |

## Top 10 BAD zones with HIGH-LOOKING v1 score (false positives)

| date | dir | confirmed_iso | coverage class | v1 score | filter | engine class |
|---|---|---|---|---:|:---:|---|
| 2026-03-21 | SHORT | 2026-03-21T14:32:57+00:00 | missed_no_move_in_4h | 1.6763 | N | failed_triggered |
| 2026-03-14 | SHORT | 2026-03-14T03:29:54+00:00 | missed_no_move_in_4h | 1.6357 | N | failed_triggered |
| 2026-03-08 | SHORT | 2026-03-08T00:17:58+00:00 | missed_no_move_in_4h | 1.5708 | N | duplicate_reached_move |
| 2026-03-28 | SHORT | 2026-03-28T08:33:04+00:00 | missed_no_move_in_4h | 1.4659 | Y | failed_triggered |
| 2026-03-21 | SHORT | 2026-03-21T07:42:37+00:00 | missed_no_move_in_4h | 1.445 | N | duplicate_reached_move |
| 2026-03-14 | SHORT | 2026-03-14T03:44:42+00:00 | missed_no_move_in_4h | 1.4046 | N | failed_triggered |
| 2026-03-11 | SHORT | 2026-03-11T05:03:04+00:00 | wrong_direction | 1.3476 | N | failed_triggered |
| 2026-03-21 | LONG | 2026-03-21T00:08:08+00:00 | missed_no_move_in_4h | 1.3392 | Y | failed_triggered |
| 2026-03-07 | SHORT | 2026-03-07T00:53:36+00:00 | missed_no_move_in_4h | 1.3233 | N | failed_triggered |
| 2026-03-07 | LONG | 2026-03-07T00:24:57+00:00 | missed_no_move_in_4h | 1.3115 | Y | failed_triggered |

## Wrong-direction top10

| date | dir | confirmed_iso | matched move % | v1 score | engine class |
|---|---|---|---:|---:|---|
| 2026-03-11 | SHORT | 2026-03-11T05:03:04+00:00 | 3.0617 | 1.3476 | failed_triggered |
| 2026-03-24 | LONG | 2026-03-24T05:46:15+00:00 | 3.5123 | 1.1717 | failed_triggered |
| 2026-03-29 | LONG | 2026-03-29T00:46:44+00:00 | 3.2533 | 1.1332 | failed_triggered |
| 2026-03-29 | LONG | 2026-03-29T10:52:43+00:00 | 3.2533 | 0.9824 | failed_triggered |
| 2026-03-29 | LONG | 2026-03-29T00:26:39+00:00 | 3.2533 | 0.9347 | failed_triggered |
| 2026-03-12 | SHORT | 2026-03-12T07:42:02+00:00 | 2.3472 | 0.917 | invalidated_or_expired |
| 2026-03-08 | SHORT | 2026-03-08T09:00:13+00:00 | 2.4913 | 0.8884 | invalidated_or_expired |
| 2026-03-19 | LONG | 2026-03-19T00:15:09+00:00 | 3.9505 | 0.8861 | failed_triggered |
| 2026-03-29 | LONG | 2026-03-29T03:04:26+00:00 | 3.2533 | 0.8829 | failed_triggered |
| 2026-03-29 | LONG | 2026-03-29T11:23:51+00:00 | 3.2533 | 0.8779 | failed_triggered |

## Suppressed-by-filter but GOOD

| date | dir | confirmed_iso | matched move % | lead min | v1 score |
|---|---|---|---:|---:|---:|
| 2026-03-29 | SHORT | 2026-03-29T00:11:14+00:00 | 3.2533 | 185.05 | 1.4778 |
| 2026-03-08 | LONG | 2026-03-08T05:30:31+00:00 | 2.4913 | 226.6 | 1.2733 |
| 2026-03-29 | SHORT | 2026-03-29T02:28:15+00:00 | 3.2533 | 48.03 | 1.0896 |
| 2026-03-29 | SHORT | 2026-03-29T02:36:58+00:00 | 3.2533 | 39.32 | 1.0819 |
| 2026-03-29 | SHORT | 2026-03-29T01:18:42+00:00 | 3.2533 | 117.58 | 1.0715 |
| 2026-03-02 | LONG | 2026-03-02T00:27:38+00:00 | 2.0434 | 43.65 | 1.0691 |
| 2026-03-23 | SHORT | 2026-03-23T05:18:54+00:00 | 2.0389 | 38.08 | 1.0395 |
| 2026-03-24 | SHORT | 2026-03-24T06:07:43+00:00 | 3.5123 | 111.33 | 1.0342 |
| 2026-03-24 | SHORT | 2026-03-24T07:56:43+00:00 | 3.5123 | 2.33 | 1.0157 |
| 2026-03-16 | LONG | 2026-03-16T00:09:04+00:00 | 3.0964 | 204.93 | 1.0114 |