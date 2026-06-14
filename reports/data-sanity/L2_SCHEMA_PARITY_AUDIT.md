# D. Schema parity audit

**Build:** 2026-06-03T11:51:54+00:00

| field | OKX (open) | Binance (recorder) | match |
|---|---|---|:--:|
| timestamp | us (ms*1000) | us | YES |
| is_snapshot | true/false | true/false | YES |
| side | bid/ask | bid/ask | YES |
| delete | size 0 | amount 0 | YES |
| snapshot reset | action=snapshot | is_snapshot=true | YES |
| **amount unit** | **contracts (0.01 BTC)** | **BTC** | **NO** |

Schema/semantics match; only the amount UNIT differs (the core parity issue).
