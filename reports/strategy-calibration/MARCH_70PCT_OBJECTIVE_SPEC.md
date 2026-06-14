# March 70 % calibration — objective spec

**Build:** 2026-05-26T12:33:22+00:00
**Scope:** IN-SAMPLE March 2026 OKX direct (29 days; 03-17 missing)

## Strict rules
- no engine / threshold / detector change
- target STRICT 2 %
- no future-leak in leak-free selectors
- outcome / post-trigger fields used as labels only
- no production integration
- if 70 % requires <10 trades or future-leak -> stated explicitly

## Goal A — watch-zone hit-rate

- selector chose zone BEFORE or at the very start of a real 2 % move
- direction matches
- market reached strict 2 % in that direction after selection time
- not late after >50 % of move completed

## Goal B — paper trade winrate

- selected zone entered via configured entry mode
- strict 2 % target hit before stop/timeout (24 h)
- cost 0.14 % roundtrip subtracted for after-cost metrics

## Goal tiers

| tier | min selected | winrate % | overfit label |
|---|---:|---:|---|
| 1 | 10 | 70 | high-overfit |
| 2 | 15 | 70 | medium-overfit |
| 3 | 20 | 70 | medium-overfit |
| 4 | 25 | 70 | lower-overfit |
| 5 | 29 | 70 | 1-per-day pace |
| 6 | 20 | 80 | 80 % stretch |

Tier under 10 selected: treated as UNUSABLE / high-overfit.