# OI / funding / liquidation data audit (OKX March 2026)

**Build:** 2026-05-29T17:30:39+00:00

## Verdict

| dataset | available for March | covers March |
|---|:---:|:---:|
| open interest | NO | NO |
| funding | NO | NO |
| liquidations | NO | NO |

March OKX per-day directories contain ONLY `incremental_book_L2.csv.gz` and `trades.csv.gz`.
No `derivative_ticker.csv.gz` (OI+funding) and no `liquidations.csv.gz` for any of the 29 March days.

## Reference schema (from 2026-04-01 OKX, NOT March)
`derivative_ticker.csv.gz`: exchange, symbol, timestamp, local_timestamp, funding_timestamp, funding_rate, predicted_funding_rate, open_interest, last_price, index_price, mark_price

`liquidations.csv.gz`: exchange, symbol, timestamp, local_timestamp, id, side, price, amount

## What is needed to enable OI/fuel research
- Fetch OKX derivative_ticker.csv.gz (OI + funding) for 2026-03-02..03-31 in Tardis-compat layout, placed at data/okx-historical/BTC-USDT-SWAP/<date>/derivative_ticker.csv.gz
- Fetch OKX liquidations.csv.gz for the same dates at .../<date>/liquidations.csv.gz
- Timestamps must be microsecond unix, covering full UTC day, same as April reference

**Decision:** Proceed with target-zone + 3 trade models WITHOUT OI/fuel. OI/funding/liquidation feature + evaluation sections produce NOT_AVAILABLE placeholders.