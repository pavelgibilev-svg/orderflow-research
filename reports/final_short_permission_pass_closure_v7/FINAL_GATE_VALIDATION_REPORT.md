# FINAL GATE VALIDATION (frozen, with slippage)

Build 2026-06-12T17:12:23+00:00 · research closure · skeptical, not production.

**Data:** Bybit+OKX (NOT Binance). Gate validation = OKX single-venue, trades-only, di-free. Windows: 4 TREND_DOWN, 1 TREND_UP (only one!), 2 RANGE, 1 BOUNCE.

## Scorecard (PF by slippage)
| evaluation | 0bps PF | 5bps PF | 10bps PF | n | winrate | maxDD% | expR(0bps) |
|---|--:|--:|--:|--:|--:|--:|--:|
| random_all | 1.416 | 1.055 | 0.82 | 4000 | 21.9 | -384.24 | 0.073 |
| random+GATE_6A | 1.777 | 1.38 | 1.104 | 617 | 30.5 | -71.6 | 0.151 |
| random+GATE_6E | 2.16 | 1.628 | 1.276 | 256 | 31.2 | -25.14 | 0.19 |
| event+GATE_6A | 1.506 | 1.214 | 0.997 | 4766 | 31.8 | -551.56 | 0.121 |
| event+GATE_6E | 2.1 | 1.607 | 1.272 | 2405 | 32.3 | -175.5 | 0.192 |

## Gate block / retention (events)
- TREND_UP blocked: GATE_6A 71.7% (n 2200->623), GATE_6E 85.1% (n 2200->328).
- TREND_DOWN retained: GATE_6A 40.3%, GATE_6E 18.1%.
- RANGE blocked: 6A 68.3%, 6E 82.2% · BOUNCE blocked: 6A 50.6%, 6E 66.3%.

## Honest reads
- gate_helps (random+gate > random_all @0bps): 6A=True, 6E=True.
- survives 5bps (random+gate > random_all @5bps): 6A=True, 6E=True.
- event_adds (event+gate > random+gate): 6A=False, 6E=False.
- regime diversity: only **1 TREND_UP window** -> the uptrend-blocking claim is single-window.
- slippage note: these are 2%-target swing trades; 5-10bps round-trip is small vs the 200bps target, so PF erodes only modestly (not a scalper).
