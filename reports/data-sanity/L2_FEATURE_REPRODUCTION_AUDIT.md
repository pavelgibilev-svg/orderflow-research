# H. Feature reproduction / portability

**Build:** 2026-06-03T11:51:54+00:00

Top1 depth OKX/Binance ratio by unit system (≈1 ⇒ portable):

| unit | OKX | Binance | ratio |
|---|--:|--:|--:|
| RAW | 1689.805 | 12.767 | 132.36 |
| BTC | 16.8981 | 12.767 | 1.32 |
| USD | 1262676.0004 | 991280.3096 | 1.27 |

RAW ~132.36x apart (units). BTC/USD bring scales together; residual = real venue depth difference. Percentile/z within-venue is portable by construction.

Flags: {"RAW_FEATURES_NOT_PORTABLE": "YES", "BTC_NORMALIZED_FEATURES_PORTABLE": "YES", "USD_NOTIONAL_FEATURES_PORTABLE": "YES", "PERCENTILE_FEATURES_PORTABLE": "YES", "FEATURE_SHIFT_EXPLAINED_BY_UNITS": "YES", "FEATURE_SHIFT_EXPLAINED_BY_RECORDER": "NO", "FEATURE_SHIFT_EXPLAINED_BY_VENUE": "PARTIAL"}
