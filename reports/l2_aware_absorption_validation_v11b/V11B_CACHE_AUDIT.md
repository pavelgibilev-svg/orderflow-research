# V11B CACHE AUDIT

Build 2026-06-14T08:25:30+00:00 · L2-aware absorption validation v11b · skeptical, not production.

v11 used the per-minute cache TRADES-ONLY (di/spread were None for okx-historical windows and unused even where populated).
L2 now integrated two ways: L2-LIGHT (cached di+spread, 3 v2okx down windows) and L2-FULL (reconstructed from incremental_book_L2, okx-native windows).

- DOWN_NOV [TREND_DOWN]: daily_L2 0/4 · di_min 5760 · L2full_cov 0.0% · L2light YES · L2full NO
- DOWN_JAN [TREND_DOWN]: daily_L2 0/4 · di_min 5760 · L2full_cov 0.0% · L2light YES · L2full NO
- DOWN_APR [TREND_DOWN]: daily_L2 0/6 · di_min 8600 · L2full_cov 0.0% · L2light YES · L2full NO
- DOWN_0327 [TREND_DOWN]: daily_L2 4/4 · di_min 0 · L2full_cov 100.0% · L2light NO · L2full YES
- UP_0310 [TREND_UP]: daily_L2 7/7 · di_min 0 · L2full_cov 0.0% · L2light NO · L2full PENDING_BUILD
- RANGE_0508 [RANGE_CHOP]: daily_L2 5/5 · di_min 0 · L2full_cov 0.0% · L2light NO · L2full PENDING_BUILD
- RANGE_0303 [RANGE_CHOP]: daily_L2 4/4 · di_min 0 · L2full_cov 100.0% · L2light NO · L2full YES
- BOUNCE_0512 [REVERSAL_BOUNCE]: daily_L2 5/5 · di_min 0 · L2full_cov 0.0% · L2light NO · L2full PENDING_BUILD
