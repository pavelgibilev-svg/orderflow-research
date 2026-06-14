# OKX March OI/funding source audit

**Build:** 2026-05-30T07:25:52+00:00

## Findings

- Tardis downloader present but **no TARDIS_API_KEY** → only free first-of-month datasets. March 02-31 `derivative_ticker` (OI+funding) NOT downloadable from Tardis.
- OKX public API reachable.
- **Current OI** `/api/v5/public/open-interest` = snapshot only (no history).
- **OI history** `/api/v5/rubik/stat/contracts/open-interest-volume`: 5m ~2d, 1H ~30d, **1D reaches back to 2025-12 → covers March at DAILY granularity only**.
- OKX rubik OI unit = **USD notional, BTC currency aggregate** (all BTC contracts), not instrument-specific.
- **Funding** `/api/v5/public/funding-rate-history` = 8h settlements, **covers March**.

## Verdict
- TRUE OI available for March but DAILY only → usable as background/regime, NOT for 15m/60m intraday deltas.
- Funding available for March (8h) → usable as background feature.
- Intraday fuel must use FLOW_PROXY (from trades), explicitly NOT called OI.

## Flags
```
OKX_PUBLIC_OI_ENDPOINT_FOUND = YES
OKX_OI_HISTORY_AVAILABLE = YES (1D granularity only for March)
OKX_FUNDING_HISTORY_AVAILABLE = YES
OI_DATA_AVAILABLE = YES (daily)
FUNDING_DATA_AVAILABLE = YES
LIQUIDATIONS_USED = NO
OI_FROM_VOLUME_ATTEMPTED = NO
FLOW_PROXY_BUILT_IF_NO_OI = YES (built for intraday since OI is daily-only)
```