# I. Binance recorder/converter audit

**Build:** 2026-06-03T11:51:54+00:00

> **CORRECTION:** Field-level schema/timestamp/side/amount/delete checks pass, BUT the **reconstruction is
> broken**: `convert_raw_depth_to_l2` seeds the book from only the FIRST 1s snapshot (`break # only first
> snapshot as seed`) and then applies depth-limited diffs → stale far levels → persistent crossed book.
> `BINANCE_CONVERTER_VALID = NO (reconstruction)`. Recorder DATA is fine (1s snapshots every second). Fix:
> re-seed from `orderbook_snapshots_1s`. See `BINANCE_L2_RECONSTRUCTION_BUG_FINDING.md`.

Converter: `scripts/binance-live/inventory_audit_normalize_convert.py` (raw_depth_events.jsonl → incremental_book_L2.csv.gz).

- BINANCE_CONVERTER_SCHEMA_OK = YES
- BINANCE_CONVERTER_TIMESTAMP_OK = YES
- BINANCE_CONVERTER_SIDE_OK = YES
- BINANCE_CONVERTER_AMOUNT_OK = YES
- BINANCE_CONVERTER_DELETE_OK = YES
- BINANCE_CONVERTER_SORT_OK = NO
- BINANCE_CONVERTER_DEDUP_OK = UNKNOWN

**Overall: PARTIAL**

Sample: {"raw_events_sampled": 201, "raw_keys": ["asks", "bids", "event_time", "exchange", "final_update_id", "first_update_id", "is_after_resync", "prev_final_update_id", "received_at", "resync_reason", "segment_id", "session_id", "symbol"], "norm_first_row": ["binance-futures", "BTCUSDT", "1779494401232000", "1779494401232000", "true", "ask", "77129.8", "16.232"]}
