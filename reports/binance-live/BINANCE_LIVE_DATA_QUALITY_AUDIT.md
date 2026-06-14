# Binance live-recorder data quality audit

**Build:** 2026-05-21T17:12:26+00:00

## Per-day coverage (from normalized JSONL trade stream)

| date | first ts UTC | last ts UTC | duration (h) | verdict |
|---|---|---|---:|---|
| 2026-05-17 | 2026-05-17T10:35:48.244+00:00 | 2026-05-18T00:00:00.120+00:00 | 13.403 | PARTIAL |
| 2026-05-18 | 2026-05-18T00:00:00.298+00:00 | 2026-05-19T00:00:00.219+00:00 | 24.0 | FULL |
| 2026-05-19 | 2026-05-19T00:00:00.316+00:00 | 2026-05-20T00:00:00.489+00:00 | 24.0 | FULL |
| 2026-05-20 | 2026-05-20T00:00:01.063+00:00 | 2026-05-21T00:00:00.725+00:00 | 24.0 | FULL |

## Flags

- BINANCE_LIVE_DATA_AUDIT_DONE = **YES**
- BACKTEST_READY_DAYS = `['2026-05-18', '2026-05-19', '2026-05-20']`
- PARTIAL_DAYS = `['2026-05-17']`
- BLOCKED_DAYS = `[]`
- LIQUIDATIONS_AVAILABLE = **PARTIAL**  (part1 streams have empty liquidations; part2 streams + 19/20 carry liquidations)

## Hard rules honored

- no engine / threshold change
- recorder not restarted; raw archives preserved
- no API keys touched