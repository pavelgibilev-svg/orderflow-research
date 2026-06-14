# J. OKX open-data converter audit

**Build:** 2026-06-03T11:52:06+00:00

Converter: `scripts/data-sanity/okx_open_converter.py` (NDJSON books → common schema; contracts preserved).

- OKX_OPEN_CONVERTER_SCHEMA_OK = YES
- OKX_OPEN_CONVERTER_TIMESTAMP_OK = YES
- OKX_OPEN_CONVERTER_SIDE_OK = YES
- OKX_OPEN_CONVERTER_AMOUNT_OK = YES
- OKX_OPEN_CONVERTER_DELETE_OK = YES
- OKX_OPEN_CONVERTER_SORT_OK = YES
- OKX_OPEN_CONVERTER_DEDUP_OK = YES

**Overall: YES**

Sample: {"first_obj_action": "snapshot", "first_obj_ts": "1779321600004", "n_objs_sampled": 51, "first_norm_row": ["okex-swap", "BTC-USDT-SWAP", 1779321600004000, 1779321600004000, "true", "ask", 77512.4, 37.17], "has_snapshot": true, "has_delete": true}
