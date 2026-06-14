# OKX March OI/funding download report

**Build:** 2026-05-30T07:25:55+00:00

- OI daily snapshots (rubik 1D, USD): total 180, March 31 (source: api)
- Funding settlements (8h): total 118, March 93 (source: api)
- Per-day funding.csv.gz written: 29 days
- OI daily cache: `_okx_oi_daily_rubik.csv`; funding cache: `_okx_funding_history.csv`

OI is DAILY granularity (16:00 UTC snapshot) and BTC-aggregate USD notional. Funding is 8h settlement rate. Both leak-free (use latest value with ts<=signal).
