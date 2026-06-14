# K. L2 DATA PARITY — FINAL SANITY REPORT (corrected verdict)

**Build:** 2026-06-03 · **TARDIS_USED = NO**
**Data sanity only. No engine/detector/TP-SL/selector/threshold change. No profitability claims.**

> This report supersedes the auto-generated optimistic flags after the Binance reconstruction bug was found.
> See **`BINANCE_L2_RECONSTRUCTION_BUG_FINDING.md`**.

## Headline verdict

1. **OKX open data is available and clean** for 2026-05-21..30 (no Tardis): L2 **10/10** days, trades **9/10**
   (05-21 trades missing). Both-sided snapshots/updates; reconstruction **0 crossed, 0 negative**.
2. **Amount unit mismatch CONFIRMED**: OKX = **contracts (ctVal 0.01 BTC)**, Binance = **BTC (base)**.
   Raw top1 depth differs **~132×**; after ×0.01 (BTC) the ratio collapses to **1.32×**, USD-notional **1.27×**.
   ⇒ raw L2 features are NOT cross-venue comparable; BTC/USD-notional or within-venue percentile are.
3. **Binance L2 reconstruction is BROKEN by a converter bug** (single stale 1s seed + depth-limited diffs →
   persistent crossed book, median **208 bps**, 100% of events after price drifts out of the seed window).
   This corrupts all Binance **top-of-book** features (microprice, spread, persistence, void, depth-imbalance).
4. **The earlier "feature unit shift" was only partially units.** Flow-scale gap = units; microprice/persistence/
   spread/void degeneration = the reconstruction bug. Recorder data itself is OK and the fix needs no re-recording.

## OKX vs Binance top1 depth by unit

| unit | OKX | Binance | ratio |
|---|--:|--:|--:|
| RAW | 1689.8 | 12.77 | **132×** |
| BTC | 16.90 | 12.77 | 1.32× |
| USD | 1,262,676 | 991,280 | 1.27× |

(Binance depth/spread medians reflect the brief clean window at day start before the book goes stale.)

## Reconstruction sanity

| venue | crossed | neg size | snapshots | verdict |
|---|--:|--:|--:|:--|
| OKX (open) | 0 | 0 | 45 (periodic) | CLEAN |
| Binance (recorder→converter) | 337,890 | 0 | 10 (single seed/day) | **BROKEN (stale seed)** |

## Update-rate / depth comparability

| metric | OKX | Binance |
|---|--:|--:|
| updates/sec (med) | 64 | 10 |
| top1 BTC | 16.90 | 12.77 |
| top1 USD | 1.26M | 0.99M |

OKX writes ~6× more book updates/sec and both-sided messages; Binance diffs are one-sided/limited-depth. Wall/
refill/persistence are **not** comparable until (a) the Binance book is reconstructed correctly and (b) sizes are
expressed in BTC/USD or within-venue percentile.

## Answers

**1. OKX open L2/trades 2026-05-21..30?** L2 10/10, trades 9/10 (missing 05-21). OKX public data, no Tardis.
**2. Binance L2 collected correctly?** Raw recorder YES (1s snapshots + diffs + trades present); **converted/reconstructed book NO** (stale-seed crossing).
**3. Binance converter/reconstruction errors?** **YES** — single stale 1s seed, never re-seeded; depth-limited diffs leave stale far levels → crossed book. Schema/timestamp/side/amount/delete fields are otherwise correct.
**4. OKX converter/reconstruction errors?** NO — NDJSON books map cleanly to common schema; 0 crossed, 0 negative.
**5. Units?** OKX amount = **contracts (ctVal 0.01 BTC)**; Binance amount = **BTC**. USD = base × price.
**6. Raw L2 comparable?** **NO** (~132× apart; units + the reconstruction bug).
**7. Normalized units to use?** Prices RAW; sizes/flows in **BTC or USD notional**; ranking via **within-venue percentile/z**. Never raw contract counts cross-venue.
**8. Shift cause?** **UNITS (flow scale) + CONVERTER reconstruction bug (top-of-book features).** Not a venue edge, not the recorder.
**9. Recompute old features?** **YES** — fix the converter, re-convert, recompute Binance L2 features; prior Binance top-of-book features are invalid.
**10. Same-date OKX/Binance research OK now?** **NOT YET** — only after the Binance converter is fixed and features recomputed. Data windows do align (same 2026-05-21..30).
**11. Raw vs normalized per feature?** RAW: price, count-of-orders. NORMALIZED-only: any size/flow/wall/persistence/void/depth (BTC or USD or percentile).
**12. Next actions?** (a) fix `convert_raw_depth_to_l2` to re-seed from `orderbook_snapshots_1s`; (b) re-convert 05-21..30; (c) recompute features in USD-notional + percentile; (d) re-run this parity on the corrected book; (e) THEN resume strategy research.

## Final flags

```
L2_DATA_PARITY_AUDIT_DONE              = YES
TARDIS_USED                           = NO
OKX_OPEN_DATA_AVAILABLE               = YES
OKX_OPEN_L2_AVAILABLE                 = YES
OKX_OPEN_TRADES_AVAILABLE             = YES (9/10 days; 05-21 missing)
BINANCE_L2_COLLECTION_VALID           = PARTIAL (raw OK, reconstruction broken)
BINANCE_CONVERTER_VALID               = NO (reconstruction: stale single seed)
OKX_OPEN_CONVERTER_VALID              = YES
OKX_BINANCE_RAW_L2_COMPARABLE         = NO
OKX_BINANCE_NORMALIZED_L2_COMPARABLE  = NO (until Binance reconstruction fixed)
AMOUNT_UNIT_MISMATCH_CONFIRMED        = YES (OKX contracts ctVal0.01 vs Binance BTC)
RECORDER_ISSUE_FOUND                  = NO
CONVERTER_ISSUE_FOUND                 = YES
RECONSTRUCTION_ISSUE_FOUND            = YES
FEATURE_UNIT_SHIFT_EXPLAINED          = PARTIAL (units = flow; converter bug = top-of-book)
NEXT_RESEARCH_CAN_CONTINUE            = NO (blocked on Binance converter fix + feature recompute)
READY_FOR_PRODUCTION_TRADING          = NO
```
