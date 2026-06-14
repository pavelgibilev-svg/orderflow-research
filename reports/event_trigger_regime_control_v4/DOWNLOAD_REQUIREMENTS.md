# DOWNLOAD REQUIREMENTS (to complete v4 cross-venue + L2 regime control)

Build 2026-06-12T15:08:44+00:00
v4 control regimes are OKX-only, trades-only (no Bybit, no L2). To test cross-venue (sync/lead-lag/disagreement)
and depth-based families (ABSORPTION, full FORCED_UNWIND) across regimes, download Bybit+OKX L2+trades for:

| regime | dates | exchange | instrument | data_type | reason |
|---|---|---|---|---|---|
| TREND_UP | 2026-03-10..03-16 | Bybit | BTCUSDT | OrderBook + Public Trading History | cross-venue + L2 in an up regime |
| TREND_UP | 2026-03-10..03-16 | OKX | BTC-USDT-SWAP | OrderBook + Trade history (UTC+8) | depth for di-based families |
| RANGE_CHOP | 2026-05-08..05-11 | Bybit+OKX | BTCUSDT / BTC-USDT-SWAP | OrderBook + Trades | chop control with L2 |
| RANGE_CHOP | 2026-03-03..03-06 | Bybit+OKX | as above | OrderBook + Trades | high-intraday chop control |
| REVERSAL_BOUNCE | 2026-05-12..05-15 | Bybit+OKX | as above | OrderBook + Trades | late-short / bounce control |

Note: OKX trades use a UTC+8 day boundary — for UTC day D download labels D and D+1.