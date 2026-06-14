# OKX direct Historical Market Data — access audit (no Tardis)

**Build date:** 2026-05-19
**Probed without auth from research workstation. No file downloads attempted past HEAD/short JSON probes.**

The user asked: can we, bypassing Tardis, pull arbitrary OKX days (e.g. BTC-USDT-SWAP order book L2 for 2025-03-15 / 16 / 17) directly from okx.com? The answer below is built from probing the live endpoints used by the `okx.com/en-us/historical-data` page UI, and from inspecting the public JS bundle that page loads.

## A. What the OKX page advertises (verbatim, < 15 words each)

From `https://www.okx.com/en-us/historical-data` (fetched 2026-05-19):

- "Tick-level trading history from September 2021 onwards"
- "OHLC chart history from July 2023 onwards"
- "Historical perpetual funding rates from March 2022 onwards"
- "High-resolution L2 data from March 2023 onwards"
- "Historical borrowing rates from December 2021 onwards"

So the *page text* claims L2 from March 2023 onward. No price / VIP / login label appears in plain text near the L2 row.

## B. Backend endpoints the page actually calls

The React bundle `cdn/assets/okfe/broker-center/brokerHistory/index.b786608a.js` references exactly four endpoints:

| endpoint | purpose | auth observed |
|---|---|---|
| `GET /priapi/v5/broker/public/trade-data/coins` | list of all CCY codes | works without auth, returns 1500+ codes |
| `GET /priapi/v5/broker/public/trade-data/instruments?instType=SWAP` | list of swap instruments | works without auth, returns 400+ pairs incl. `BTC-USDT`, `BTC-USD`, etc. |
| `GET /priapi/v5/broker/public/trade-data/download-link?...` | generate signed download URL | **rejects every call** with `{"code":"3","msg":"不支持操作"}` ("operation not supported") |
| `GET /priapi/v5/broker/user/isVip` | check VIP tier of current user | **403 Forbidden** without session cookie |

The `isVip` check + the fact that `download-link` returns `不支持操作` for EVERY parameter combination (valid instId, invalid instId, no params at all) together imply: the actual download URL is generated server-side **only for logged-in sessions**, and very likely only for accounts above a certain VIP / KYC tier.

## C. Probe matrix tried (all anonymous)

`download-link` GET, varying `dataType`:

| dataType tried | response |
|---|---|
| trades / TRADES / Trades / trade | `code:3 不支持操作` |
| book / BOOK / books / BOOKS / Books / books-l2 / booksL2 | `code:3 不支持操作` |
| orderbook / ORDERBOOK / orderBook / ob / OB | `code:3 不支持操作` |
| l2 / L2 / depth / DEPTH | `code:3 不支持操作` |
| funding / FUNDING / fundingRate / fr | `code:3 不支持操作` |
| kline / klines / candlestick / OHLC | `code:3 不支持操作` |
| borrow / BORROW / swap | `code:3 不支持操作` |

Same `code:3` is returned with no params, with bogus instId, with `date=2025-03`, `date=2025-03-15`, `date=20250315`, `date=202503`. POST with JSON body returns a different error (`51000 Parameter module error`), confirming the GET path is auth-gated rather than param-shape gated.

## D. Legacy `static.okx.com` CDN path (used in 2022 by `crypto-crawler/historical-data-downloader`)

The legacy public listing endpoint:

```
https://www.okx.com/priapi/v5/broker/public/orderRecord?t=<ms>&path=cdn/okex/traderecords/<msgType>/monthly/<YYYYMM>
```

now returns **404 Not Found** for every combination tried (trades / books / swaprate, 202503 / 202401 etc.). Direct CDN paths probed:

```
https://static.okx.com/cdn/okex/traderecords/{trades,books,orderbook,depth,swap}/{monthly,daily}/<YYYYMM[DD]>/BTC-USDT-SWAP{.csv.gz,.zip}
```

— all return 404. The legacy 2022-era public CDN structure is no longer reachable.

## E. Terms of Service (verbatim relevant fragments)

From `https://www.okx.com/en-us/help/historicaldata-terms-and-conditions`:

- License granted is "limited, revocable, non-exclusive, royalty-free, license to download and access"
- Permitted scope: "personal use" (incl. developing one's own trading strategies)
- "Commercial use" — defined to include "any re-distribution and/or sub-license of such Data to your end users or business partners" — is explicitly prohibited.
- No accuracy guarantees, no warranty.

ToS does not mention paid tier or VIP requirement explicitly — that gating is purely implemented at the API layer.

## F. Net verdict

- OKX *does* advertise L2 from March 2023 onwards on its public Historical Market Data page.
- The UI is **not anonymous** — generating a download link requires a logged-in OKX account, and the `isVip` pre-check next to every download button strongly suggests the L2 / high-resolution rows are gated to a minimum VIP / KYC tier (the exact threshold is not documented on the public page).
- No anonymous direct URL exists for arbitrary days. The legacy 2022 `static.okx.com/cdn/okex/traderecords/...` monthly path is no longer reachable.
- We did **not** attempt to log in, register, complete KYC, or pay anything — those steps are out of scope for this audit.
- Practical conclusion for our pipeline: the **free** way to get OKX BTC-USDT-SWAP L2 for arbitrary 2024–2026 days is still Tardis paid tier (not first-of-month free samples). OKX-direct *might* be cheaper if a user already has a VIP-tier OKX account, but we cannot verify file format / schema / granularity without that account.

## G. Schema-vs-Tardis comparison

Cannot be performed — no sample was downloadable through the public surface. We did NOT log in or pay to test. `OKX_DIRECT_SCHEMA_MATCHES_TARDIS = UNKNOWN`.

## H. Final flag matrix

```
OKX_DIRECT_ARBITRARY_DAYS_AVAILABLE  = YES (advertised on okx.com/historical-data,
                                             L2 since March 2023 — but ONLY for logged-in users)
OKX_DIRECT_LOGIN_REQUIRED            = YES (download-link rejects all anonymous calls;
                                             isVip pre-check is wired into the page bundle)
OKX_DIRECT_PAID_REQUIRED             = UNKNOWN (not stated on the public page;
                                                 VIP-tier gating is strongly implied by the
                                                 isVip pre-check, but the exact tier and price
                                                 cannot be determined without logging in)
OKX_DIRECT_SAMPLE_DOWNLOADED         = NO  (we explicitly did not log in / register / pay)
OKX_DIRECT_SCHEMA_MATCHES_TARDIS     = UNKNOWN (no sample available to compare)
```

## I. Hard rules honored

- No strategy / threshold / engine change.
- No large download attempted.
- No login, no KYC, no payment, no account creation on user's behalf.
- Probes were limited to HEAD / short JSON metadata calls against publicly-advertised endpoints (no auth, no cookies, no API key).
