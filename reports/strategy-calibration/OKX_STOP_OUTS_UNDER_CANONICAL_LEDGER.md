# OKX stop-outs under canonical ledger (counterfactual audit)

**Build:** 2026-05-23T10:13:09+00:00
**Scope:** all OKX baseline stop-outs (n = 27); for each, check whether variants would have won.

| date | dir | entry | mae % | mfe % | stop time | target hit after stop (h) | delay 30m | stop 1.5 % | zone-bdy | retest |
|---|---|---:|---:|---:|---|---:|---|---|---|---|
| 2026-03-02 | LONG | 66252.3 | 1.0077 | 1.2149 | 2026-03-02T07:10:26+00:00 | 7.97 | stop | stop | stop | skip_no_retest |
| 2026-03-02 | SHORT | 65698.1 | 1.014 | 0.1111 | 2026-03-02T09:01:56+00:00 | None | stop | stop | stop | stop |
| 2026-03-02 | SHORT | 65856.1 | 1.0054 | 0.9818 | 2026-03-02T14:42:20+00:00 | None | stop | stop | stop | stop |
| 2026-03-03 | LONG | 67037.8 | 1.0123 | 1.3361 | 2026-03-03T14:44:30+00:00 | 1.41 | stop | target_2pct | stop | stop |
| 2026-03-04 | SHORT | 68008.4 | 1.0891 | 0.2854 | 2026-03-04T01:42:10+00:00 | None | stop | stop | stop | stop |
| 2026-03-04 | SHORT | 68439.0 | 1.0462 | 1.5794 | 2026-03-04T07:47:03+00:00 | None | stop | stop | stop | stop |
| 2026-03-04 | LONG | 71434.6 | 1.0106 | 0.6206 | 2026-03-04T12:18:29+00:00 | 3.184 | stop | target_2pct | target_2pct | target_2pct |
| 2026-03-04 | SHORT | 72545.4 | 1.0064 | 0.0624 | 2026-03-04T16:53:51+00:00 | None | stop | stop | stop | stop |
| 2026-03-04 | LONG | 73643.1 | 1.0074 | 0.0989 | 2026-03-04T17:22:19+00:00 | None | stop | stop | stop | stop |
| 2026-03-04 | LONG | 73461.2 | 1.0362 | 0.7743 | 2026-03-04T22:45:42+00:00 | None | stop | stop | stop | stop |
| 2026-03-05 | LONG | 72920.9 | 1.016 | 0.4937 | 2026-03-05T05:58:17+00:00 | None | stop | stop | stop | stop |
| 2026-03-05 | SHORT | 72244.9 | 1.008 | 0.7284 | 2026-03-05T10:23:48+00:00 | 5.773 | stop | stop | stop | stop |
| 2026-03-07 | LONG | 68276.7 | 1.0569 | 0.3634 | 2026-03-07T06:53:11+00:00 | None | stop | stop | stop | stop |
| 2026-03-07 | LONG | 67867.2 | 1.0288 | 0.5493 | 2026-03-07T19:27:47+00:00 | None | stop | timeout | stop | stop |
| 2026-03-08 | SHORT | 67168.5 | 1.0127 | 0.9795 | 2026-03-08T09:17:09+00:00 | 12.785 | stop | target_2pct | stop | stop |
| 2026-03-08 | LONG | 68068.7 | 1.0263 | 0.1453 | 2026-03-08T11:41:45+00:00 | None | stop | stop | stop | stop |
| 2026-03-09 | SHORT | 65804.9 | 1.0318 | 0.0353 | 2026-03-09T00:33:40+00:00 | None | stop | stop | stop | stop |
| 2026-03-09 | SHORT | 67236.3 | 1.021 | 0.5995 | 2026-03-09T09:16:03+00:00 | None | stop | stop | stop | skip_no_retest |
| 2026-03-09 | LONG | 67992.9 | 1.0001 | 0.6364 | 2026-03-09T11:21:02+00:00 | 3.26 | target_2pct | target_2pct | stop | target_2pct |
| 2026-03-10 | SHORT | 69852.9 | 1.0329 | 0.7343 | 2026-03-10T08:05:30+00:00 | None | stop | stop | stop | stop |
| 2026-03-10 | SHORT | 70642.7 | 1.0685 | 1.9715 | 2026-03-10T14:56:07+00:00 | None | target_2pct | stop | stop | target_2pct |
| 2026-03-11 | LONG | 69650.6 | 1.0139 | 0.8691 | 2026-03-11T12:08:56+00:00 | 1.521 | stop | target_2pct | stop | target_2pct |
| 2026-03-11 | SHORT | 69699.6 | 1.0508 | 0.0736 | 2026-03-11T16:07:02+00:00 | None | stop | stop | stop | stop |
| 2026-03-12 | SHORT | 70045.8 | 1.0011 | 1.2703 | 2026-03-12T11:45:33+00:00 | None | stop | timeout | stop | skip_no_retest |
| 2026-03-13 | LONG | 71847.5 | 1.0198 | 0.1956 | 2026-03-13T02:43:20+00:00 | 10.817 | target_2pct | target_2pct | target_2pct | stop |
| 2026-03-13 | LONG | 73717.9 | 1.0498 | 0.2019 | 2026-03-13T14:43:58+00:00 | None | stop | stop | stop | stop |
| 2026-03-13 | SHORT | 71473.6 | 1.0155 | 0.488 | 2026-03-13T17:16:21+00:00 | None | timeout | timeout | stop | timeout |

## Counterfactual counts

- target eventually hit AFTER stop (within 24h timeout): **8 / 27**
- delay_30m would have won (target_2pct): **3 / 27**
- stop_1.5 % would have won: **6 / 27**
- zone-boundary stop would have won: **2 / 27**
- retest entry would have won: **4 / 27**

## Verdict: `OKX_STOP_OUT_CAUSE = mixed`