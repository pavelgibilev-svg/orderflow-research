# max2_total_per_day - missed market moves audit

**Build:** 2026-05-25T09:39:55+00:00
**Market 2 % moves total:** 20, covered by max2: **4**, missed: **16**

| date | dir | size % | move start | covered? | top2 dirs | best unselected correct | miss reason |
|---|---|---:|---|:---:|---|---|---|
| 2026-03-16 | UP | 3.0964 | 2026-03-16T03:34:00+00:00 | YES | ['LONG', 'LONG'] | `LONG-1773623888000-6` (rs=7.4) |  |
| 2026-03-16 | DOWN | 2.1772 | 2026-03-16T04:55:01+00:00 | NO | ['LONG', 'LONG'] | `HORT-1773626785000-7` (rs=7.5) | best correct-dir zone 1773626785000-7 with rank_score 7.5 (HIGH, ev=7) lost to top-2 (rank_scores [9.4, 9.4]) |
| 2026-03-16 | UP | 2.2946 | 2026-03-16T08:44:57+00:00 | NO | ['LONG', 'LONG'] | `ONG-1773647666000-19` (rs=8.5) | best correct-dir zone 773647666000-19 with rank_score 8.5 (HIGH, ev=8) lost to top-2 (rank_scores [9.4, 9.4]); base filter slow_trigger (no_trigger) |
| 2026-03-16 | DOWN | 2.0801 | 2026-03-16T13:41:49+00:00 | NO | ['LONG', 'LONG'] | `ORT-1773660536000-29` (rs=6.5) | best correct-dir zone 773660536000-29 with rank_score 6.5 (HIGH, ev=6) lost to top-2 (rank_scores [9.4, 9.4]) |
| 2026-03-19 | DOWN | 3.9505 | 2026-03-19T03:19:48+00:00 | NO | ['LONG', 'LONG'] | `HORT-1773879450000-2` (rs=7.5) | best correct-dir zone 1773879450000-2 with rank_score 7.5 (HIGH, ev=7) lost to top-2 (rank_scores [9.5, 9.5]) |
| 2026-03-20 | UP | 2.2116 | 2026-03-20T08:10:32+00:00 | NO | ['SHORT', 'SHORT'] | `ONG-1773988237000-17` (rs=8.5) | best correct-dir zone 773988237000-17 with rank_score 8.5 (HIGH, ev=8) lost to top-2 (rank_scores [8.5, 8.5]) |
| 2026-03-20 | DOWN | 2.7881 | 2026-03-20T08:12:09+00:00 | NO | ['SHORT', 'SHORT'] | `ORT-1773980106000-16` (rs=7.5) | best correct-dir zone 773980106000-16 with rank_score 7.5 (HIGH, ev=7) lost to top-2 (rank_scores [8.5, 8.5]) |
| 2026-03-22 | UP | 2.0367 | 2026-03-22T03:28:07+00:00 | NO | ['SHORT', 'SHORT'] | `LONG-1774139310000-1` (rs=7.4) | best correct-dir zone 1774139310000-1 with rank_score 7.4 (HIGH, ev=7) lost to top-2 (rank_scores [9.5, 9.5]); base filter slow_trigger ctm=108 |
| 2026-03-23 | UP | 2.1612 | 2026-03-23T05:03:36+00:00 | NO | ['SHORT', 'LONG'] | `LONG-1774230340000-9` (rs=8.5) | best correct-dir zone 1774230340000-9 with rank_score 8.5 (HIGH, ev=8) lost to top-2 (rank_scores [8.5, 8.5]) |
| 2026-03-23 | DOWN | 2.0389 | 2026-03-23T05:56:59+00:00 | NO | ['SHORT', 'LONG'] | `ORT-1774242344000-16` (rs=8.4) | best correct-dir zone 774242344000-16 with rank_score 8.4 (HIGH, ev=8) lost to top-2 (rank_scores [8.5, 8.5]); base filter dup_suppressed; base filter slow_trigger ctm=84 |
| 2026-03-23 | UP | 5.9542 | 2026-03-23T07:06:19+00:00 | NO | ['SHORT', 'LONG'] | `ONG-1774240874000-15` (rs=8.5) | best correct-dir zone 774240874000-15 with rank_score 8.5 (HIGH, ev=8) lost to top-2 (rank_scores [8.5, 8.5]); base filter dup_suppressed |
| 2026-03-23 | DOWN | 2.561 | 2026-03-23T11:13:08+00:00 | NO | ['SHORT', 'LONG'] | `—` (rs=None) | no correct-direction confirmed zone within the window |
| 2026-03-23 | UP | 3.0447 | 2026-03-23T12:03:12+00:00 | NO | ['SHORT', 'LONG'] | `—` (rs=None) | no correct-direction confirmed zone within the window |
| 2026-03-24 | DOWN | 3.5123 | 2026-03-24T07:59:03+00:00 | YES | ['SHORT', 'SHORT'] | `ORT-1774336685000-15` (rs=8.2) |  |
| 2026-03-29 | DOWN | 3.2533 | 2026-03-29T03:16:17+00:00 | NO | ['LONG', 'LONG'] | `HORT-1774752923000-8` (rs=8.2) | best correct-dir zone 1774752923000-8 with rank_score 8.2 (HIGH, ev=8) lost to top-2 (rank_scores [9.5, 9.5]); base filter slow_trigger ctm=610 |
| 2026-03-30 | UP | 3.7056 | 2026-03-30T00:20:06+00:00 | YES | ['LONG', 'LONG'] | `LONG-1774829318000-3` (rs=7.5) |  |
| 2026-03-31 | UP | 2.825 | 2026-03-31T01:25:35+00:00 | YES | ['LONG', 'LONG'] | `LONG-1774917842000-5` (rs=8.5) |  |
| 2026-03-31 | DOWN | 3.5721 | 2026-03-31T01:34:48+00:00 | NO | ['LONG', 'LONG'] | `HORT-1774916222000-2` (rs=7.5) | best correct-dir zone 1774916222000-2 with rank_score 7.5 (HIGH, ev=7) lost to top-2 (rank_scores [8.5, 8.5]); base filter slow_trigger (no_trigger) |
| 2026-03-31 | UP | 2.7664 | 2026-03-31T09:57:11+00:00 | NO | ['LONG', 'LONG'] | `ONG-1774948954000-21` (rs=7.5) | best correct-dir zone 774948954000-21 with rank_score 7.5 (HIGH, ev=7) lost to top-2 (rank_scores [8.5, 8.5]); base filter slow_trigger (no_trigger) |
| 2026-03-31 | DOWN | 2.0382 | 2026-03-31T14:18:55+00:00 | NO | ['LONG', 'LONG'] | `ORT-1774951968000-23` (rs=7.5) | best correct-dir zone 774951968000-23 with rank_score 7.5 (HIGH, ev=7) lost to top-2 (rank_scores [8.5, 8.5]); base filter dup_suppressed |