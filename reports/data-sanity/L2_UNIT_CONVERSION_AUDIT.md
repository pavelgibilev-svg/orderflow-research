# E. Unit audit: contracts vs BTC vs USD

**Build:** 2026-06-03T11:51:54+00:00

OKX BTC-USDT-SWAP: **ctVal=0.01 BTC/contract** (confirmed via OKX public instruments API). amount_btc = contracts*0.01; amount_usd = amount_btc*price. Binance amount already BTC.

| venue | date | top1 raw | top1 BTC | top1 USD | top20 raw | top20 BTC | top20 USD |
|---|---|--:|--:|--:|--:|--:|--:|
| OKX | 2026-05-21 | 2511.91 | 25.1191 | 1947040.5 | 2998.92 | 29.9892 | 2324533.4 |
| OKX | 2026-05-22 | 1010.05 | 10.1005 | 783627.6 | 1315.72 | 13.1572 | 1020775.7 |
| OKX | 2026-05-23 | 1889.42 | 18.8942 | 1426675.5 | 2225.78 | 22.2578 | 1680656.4 |
| BINANCE | 2026-05-21 | 11.084 | 11.084 | 861244.0 | 13.22 | 13.22 | 1027214.5 |
| BINANCE | 2026-05-22 | 4.295 | 4.295 | 331272.3 | 15.692 | 15.692 | 1210320.0 |
| BINANCE | 2026-05-23 | 4.295 | 4.295 | 331272.3 | 15.692 | 15.692 | 1210320.0 |

Flags: amount units identified for both; BTC & USD conversion available; features can be notional-normalized.
