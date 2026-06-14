# A. OKX open data availability audit

**Build:** 2026-06-03T11:39:19+00:00  ·  TARDIS_USED=NO

Source: `data/okx may 2026` (OKX public L2orderbook-400lv + trades).

- **L2 available dates:** ['2026-05-21', '2026-05-22', '2026-05-23', '2026-05-24', '2026-05-25', '2026-05-26', '2026-05-27', '2026-05-28', '2026-05-29', '2026-05-30', '2026-05-31']
- **Trades available dates:** ['2026-05-22', '2026-05-23', '2026-05-24', '2026-05-25', '2026-05-26', '2026-05-27', '2026-05-28', '2026-05-29', '2026-05-30', '2026-05-31', '2026-06-01']
- Target window 2026-05-21..30: L2 10/10 days, trades 9/10 days (missing trades: ['2026-05-21'])

Format: 400-level NDJSON books (snapshot/update), ~10ms; trades CSV. Units = **contracts (ctVal 0.01 BTC)**.

Flags: OKX_OPEN_DATA_AVAILABLE=YES · OKX_OPEN_L2_AVAILABLE=YES · OKX_OPEN_TRADES_AVAILABLE=YES
