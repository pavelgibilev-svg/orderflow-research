# D. Setup-type router

**Build:** 2026-06-04T14:04:38+00:00

## TREND_DOWN
- **allowed**: ['SHORT continuation (DISTRIBUTION)']
- **rejected**: ['LONG accumulation without reversal proof']
- **required_filters**: ['trend-aligned OR reversal_proof', 'noise_ok (ofi/taker not conflicting)']

## TREND_UP
- **allowed**: ['LONG continuation (ACCUMULATION)']
- **rejected**: ['SHORT distribution without rejection proof']
- **required_filters**: ['trend-aligned OR rejection_proof', 'thin path preferred']

## RANGE
- **allowed**: ['mean-reversion from band with reclaim/rejection (both dirs)']
- **rejected**: ['no-reclaim entries']
- **required_filters**: ['reclaim_zoneMid', 'noise_ok', 'cross-confirm where available']

## LOW_VOL
- **allowed**: []
- **rejected**: ['all (range too small for 2% target)']
- **required_filters**: ['NO-TRADE unless exceptional strong-zone score']

## HIGH_VOL
- **note**: overlay — wider excursions; same direction rules, prefer continuation
