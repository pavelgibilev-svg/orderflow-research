# Binance live 2026-05-17..20 - day-level 2 % feasibility

**Build:** 2026-05-22T09:14:50+00:00
**Scope:** computes day open/high/low/close + forward-max-moves up/down 4h/8h/24h from trades.csv.gz (no future-leak into filter; this is diagnostic).

| date | return % | range % | intraday up % | intraday dn % | 4h up | 4h dn | 8h up | 8h dn | 24h up | 24h dn | 2 % feas |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|:---:|
| 2026-05-17 | -1.3079 | 2.2232 | 0.0756 | 2.1009 | 0.9194 | 2.0929 | 0.9194 | 2.0929 | 0.9194 | 2.1725 | YES |
| 2026-05-18 | -0.6014 | 2.2934 | 0.4224 | 1.829 | 1.468 | 2.2312 | 1.5905 | 2.2312 | 1.5905 | 2.2312 | YES |
| 2026-05-19 | -0.2191 | 1.6786 | 0.5454 | 1.1144 | 1.1583 | 1.2371 | 1.2235 | 1.5256 | 1.2235 | 1.64 | NO |
| 2026-05-20 | 0.9361 | 1.6351 | 1.2234 | 0.4051 | 1.1817 | 1.1091 | 1.4464 | 1.1091 | 1.6344 | 1.1091 | NO |

**`BINANCE_LIVE_2PCT_FEASIBLE_DAYS` = 2 / 4**

Reading:
- `intraday up/dn` = high-from-open / open-from-low (absolute intraday excursion).
- `4h/8h/24h up/dn` = max forward move within that horizon, measured from ANY 1-second anchor in the day.
  If this is < 2 %, no zone triggered any time during the day could have reached a +2 % target within the horizon.