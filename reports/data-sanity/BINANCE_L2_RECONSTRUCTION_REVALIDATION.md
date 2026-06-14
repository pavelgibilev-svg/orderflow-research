# B3. Binance L2 reconstruction revalidation (after v3 fix) — AUTHORITATIVE

**Build:** 2026-06-04T04:12:03+00:00
Sampling: end-of-ms-group (each ms-group sampled only after all its rows incl. prune-deletes are applied).

**Total crossed: 0.0% -> CROSSED_BOOK_FIXED = YES**

| date | samples | crossed% | med spread bps | p99 spread | top1 btc | top5 btc | top20 btc | book-vs-trade% |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| 2026-05-21 | 35293 | 0.0 | 0.0129 | 0.0129 | 7.9635 | 16.854 | 19.627 | 0.2023 |
| 2026-05-22 | 35293 | 0.0 | 0.0129 | 0.0129 | 6.402 | 13.518 | 15.914 | -0.1774 |
| 2026-05-23 | 35294 | 0.0 | 0.0133 | 0.0133 | 7.7748 | 16.4145 | 19.169 | -0.1449 |
| 2026-05-24 | 35294 | 0.0 | 0.013 | 0.0131 | 6.4035 | 13.386 | 16.1935 | -0.0226 |
| 2026-05-25 | 35293 | 0.0 | 0.013 | 0.013 | 7.7325 | 15.985 | 17.508 | 0.1353 |
| 2026-05-26 | 35293 | 0.0 | 0.013 | 0.0131 | 9.502 | 19.975 | 22.536 | -0.2642 |
| 2026-05-27 | 35292 | 0.0 | 0.0132 | 0.0132 | 13.0322 | 27.0725 | 29.4975 | 0.038 |
| 2026-05-28 | 35292 | 0.0 | 0.0134 | 0.0134 | 6.202 | 13.1735 | 16.143 | 0.1245 |
| 2026-05-29 | 35291 | 0.0 | 0.0136 | 0.0136 | 5.2755 | 11.241 | 13.562 | 0.211 |
| 2026-05-30 | 35293 | 0.0 | 0.0136 | 0.0136 | 8.3665 | 17.553 | 19.549 | 0.0539 |

## Flags
```
BINANCE_CONVERTER_FIX_DONE = YES
BINANCE_RECONSTRUCTION_REVALIDATED = YES
CROSSED_BOOK_FIXED = YES
STALE_BOOK_FIXED = YES
BINANCE_L2_COLLECTION_VALID = YES
BINANCE_STRATEGY_RESEARCH_ALLOWED = YES
total_crossed_pct = 0.0
```