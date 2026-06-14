# OKX March OI/funding data quality

**Build:** 2026-05-30T07:25:55+00:00

## OI (daily)
- rows March: 31
- 2026-03-01T16:00:00+00:00 .. 2026-03-31T16:00:00+00:00
- median interval: 86400.0s (=1 day); max gap 86400s
- unit USD aggregate BTC

## Funding (8h)
- rows March: 93 (~3.21/day)
- 2026-03-01T00:00:00+00:00 .. 2026-03-31T16:00:00+00:00
- median interval 28800.0s (=8h)

## Flags
```
OI_COVERS_MARCH = YES
FUNDING_COVERS_MARCH = YES
OI_MIN_GRANULARITY = 1D
FUNDING_MIN_GRANULARITY = 8h
OI_USABLE_FOR_15M_60M_FEATURES = NO (daily only)
FUNDING_USABLE_AS_BACKGROUND = YES
```
