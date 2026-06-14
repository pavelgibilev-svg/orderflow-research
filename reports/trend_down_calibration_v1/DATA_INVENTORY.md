# DATA INVENTORY — TREND_DOWN calibration v1

Build 2026-06-11T15:57:59+00:00 · source `data/11.06.2026` · RESEARCH/CALIBRATION ONLY.

## Files found (by stream)
- **Bybit OrderBook (ob200)**: 12 files — 2025-11-19_BTCUSDT_ob200.data.zip, 2025-11-20_BTCUSDT_ob200.data.zip, 2025-11-21_BTCUSDT_ob200.data.zip, 2025-11-22_BTCUSDT_ob200.data.zip, 2026-01-28_BTCUSDT_ob200.data.zip, 2026-01-29_BTCUSDT_ob200.data.zip, 2026-01-30_BTCUSDT_ob200.data.zip, 2026-01-31_BTCUSDT_ob200.data.zip, 2026-02-11_BTCUSDT_ob200.data.zip, 2026-02-12_BTCUSDT_ob200.data.zip, 2026-02-13_BTCUSDT_ob200.data.zip, 2026-02-14_BTCUSDT_ob200.data.zip
- **Bybit Trades**: 0 files — NONE
- **OKX OrderBook (400lv)**: 3 files — BTC-USDT-SWAP-L2orderbook-400lv-2025-11-22.tar.gz, BTC-USDT-SWAP-L2orderbook-400lv-2026-01-31.tar.gz, BTC-USDT-SWAP-L2orderbook-400lv-2026-02-14.tar.gz
- **OKX Trades**: 3 files — BTC-USDT-SWAP-trades-2025-11-23.zip, BTC-USDT-SWAP-trades-2026-02-01.zip, BTC-USDT-SWAP-trades-2026-02-15.zip

## Coverage per window (got / missing days)
### W1: 2025-11-19..2025-11-22
- Bybit orderbook_L2_200: got ['2025-11-19', '2025-11-20', '2025-11-21', '2025-11-22'] · **missing []**
- Bybit trades: got [] · **missing ['2025-11-19', '2025-11-20', '2025-11-21', '2025-11-22']**
- OKX orderbook_L2_400: got ['2025-11-22'] · **missing ['2025-11-19', '2025-11-20', '2025-11-21']**
- OKX trades: got [] · **missing ['2025-11-19', '2025-11-20', '2025-11-21', '2025-11-22']**
### W2: 2026-02-11..2026-02-14
- Bybit orderbook_L2_200: got ['2026-02-11', '2026-02-12', '2026-02-13', '2026-02-14'] · **missing []**
- Bybit trades: got [] · **missing ['2026-02-11', '2026-02-12', '2026-02-13', '2026-02-14']**
- OKX orderbook_L2_400: got ['2026-02-14'] · **missing ['2026-02-11', '2026-02-12', '2026-02-13']**
- OKX trades: got [] · **missing ['2026-02-11', '2026-02-12', '2026-02-13', '2026-02-14']**
### W3: 2026-01-28..2026-01-31
- Bybit orderbook_L2_200: got ['2026-01-28', '2026-01-29', '2026-01-30', '2026-01-31'] · **missing []**
- Bybit trades: got [] · **missing ['2026-01-28', '2026-01-29', '2026-01-30', '2026-01-31']**
- OKX orderbook_L2_400: got ['2026-01-31'] · **missing ['2026-01-28', '2026-01-29', '2026-01-30']**
- OKX trades: got [] · **missing ['2026-01-28', '2026-01-29', '2026-01-30', '2026-01-31']**

## Explicit summary
- **Dates found (any stream):** ['2025-11-19', '2025-11-20', '2025-11-21', '2025-11-22', '2025-11-23', '2026-01-28', '2026-01-29', '2026-01-30', '2026-01-31', '2026-02-01', '2026-02-11', '2026-02-12', '2026-02-13', '2026-02-14', '2026-02-15']
- **Dates MISSING by stream:**
  - Bybit orderbook_L2_200: none
  - Bybit trades: ['2025-11-19', '2025-11-20', '2025-11-21', '2025-11-22', '2026-01-28', '2026-01-29', '2026-01-30', '2026-01-31', '2026-02-11', '2026-02-12', '2026-02-13', '2026-02-14']
  - OKX orderbook_L2_400: ['2025-11-19', '2025-11-20', '2025-11-21', '2026-01-28', '2026-01-29', '2026-01-30', '2026-02-11', '2026-02-12', '2026-02-13']
  - OKX trades: ['2025-11-19', '2025-11-20', '2025-11-21', '2025-11-22', '2026-01-28', '2026-01-29', '2026-01-30', '2026-01-31', '2026-02-11', '2026-02-12', '2026-02-13', '2026-02-14']

- **Where is Bybit OrderBook:** `data/11.06.2026/*_BTCUSDT_ob200.data.zip` — COMPLETE for all 12 window days.
- **Where is Bybit Trades:** NOT PROVIDED (0 files) — trade-flow features from Bybit are N/A.
- **Where is OKX OrderBook:** `data/11.06.2026/BTC-USDT-SWAP-L2orderbook-400lv-*.tar.gz` — only the LAST day of each window (2025-11-22, 2026-01-31, 2026-02-14).
- **Where is OKX Trades:** only out-of-window days (2025-11-23, 2026-02-01, 2026-02-15) — NONE inside the 3 windows.

## Can we continue calibration?
**YES — with Bybit ob200 as the primary in-window price + L2 source (full coverage).** Outcome labels
(MFE/hit2/2.5/3) and L2 features (spread, depth, depth_imbalance, best sizes) are computable for all 3
windows from Bybit ob200 mid-price reconstruction. **Trade-flow evidence** (real taker imbalance / CVD /
aggressor side / effort_vs_result from executions) is **N/A in-window** (no in-window trades on either
venue) and will be **L2-proxied or N/A**, never fabricated. OKX serves only as a 1-day-per-window L2
cross-check. This is a CALIBRATION pass, not production.
