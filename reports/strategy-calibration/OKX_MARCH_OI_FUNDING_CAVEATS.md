# OKX March OI/funding caveats

**Build:** 2026-05-30T10:46:08+00:00

- OI source: OKX rubik /api/v5/rubik/stat/contracts/open-interest-volume
- OI granularity: **1D** (16:00 UTC daily snapshot)
- OI scope: USD notional, aggregate across ALL BTC contracts (NOT exact BTC-USDT-SWAP intraday)
- Funding: OKX /api/v5/public/funding-rate-history (8h per-instrument BTC-USDT-SWAP)
- Intraday OI 15m/60m: **NOT available for March without paid Tardis/derivative_ticker (no API key)**
- Usage: OI usable as DAY/REGIME/fuel background only, NOT exact entry-timing signal
- Leak safety: all features use latest value with ts<=confirmedTs (OI daily snap, funding settle) -> leak-free

**Implication for S7:** true_fuel_score mixes daily-OI zscore + funding zscore; it is a slow/background signal. S7's edge is modest and partly from L2 void/microprice (intraday), not OI alone.
