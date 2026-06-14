# NORMALIZED DATA STATUS

Build 2026-06-12T12:57:47+00:00 · RESEARCH/CALIBRATION (not production).

Per-minute combined (L2 + REAL trades) for Bybit + OKX. Bybit symbol BTCUSDT, OKX BTC-USDT-SWAP.
OKX trades bucketed by REAL UTC minute (UTC+8 label boundary handled). Old OKX quarantined.

| exchange | window | minutes | has_trades |
|---|---|--:|:--:|
| Bybit | W1_NOVEMBER | 5760 | YES |
| OKX | W1_NOVEMBER | 5760 | YES |
| Bybit | W3_JANUARY | 5760 | YES |
| OKX | W3_JANUARY | 5760 | YES |
| Bybit | W4_APRIL | 8640 | YES |
| OKX | W4_APRIL | 8600 | YES |

All 6 (exchange x window) series present.
