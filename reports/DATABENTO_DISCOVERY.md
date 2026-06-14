# Databento discovery for orderflow-research

**Audit date:** 2026-05-11 (UTC)
**Working directory:** `C:\Users\gibilev\orderflow-research`
**API key path:** `data/databento/access_token.txt` (never printed, never committed)
**databento-py version:** 0.77.0

---

## 0. Headline

| Question                                                  | Answer |
|-----------------------------------------------------------|--------|
| Is Binance Futures BTCUSDT on Databento?                  | ❌ **NO** — Databento does not carry any Binance / Bybit / OKX / centralized-crypto-exchange data. The provider catalog is regulated US/EU venues only. |
| Closest equivalent for BTC orderflow research?            | ✅ **CME Globex (`GLBX.MDP3`)** — Bitcoin futures (`BTC.FUT`) and Micro Bitcoin futures (`MBT.FUT`) |
| Is CME BTC futures directly equivalent to Binance USDS-M Futures? | ❌ **NO** — different venue, different contract spec, different liquidity, different participant mix. Useful only as a **supplementary microstructure test**, not as a strategy backtest replacement. |
| Schemas available on GLBX.MDP3?                           | mbo, mbp-1, mbp-10, tbbo, trades, bbo-1s/1m, ohlcv-*, definition, status, statistics, imbalance |
| Selected instrument for the week                          | **`MBT.FUT`** (Micro Bitcoin futures), parent symbol, with **MBO + trades** schemas |
| Selected window                                           | 2026-04-01T00:00:00Z → 2026-04-08T00:00:00Z (1 week) |
| Estimated cost                                            | $3.65 (MBT MBO $3.50 + MBT trades $0.15). Plus optional BTC.FUT trades $0.04 for cross-reference. |

---

## 1. Datasets available on this API key

Databento exposed **29** historical datasets. All are regulated US / EU
trading venues:

| dataset          | mbo | mbp-10 | trades | data range                |
|------------------|-----|--------|--------|---------------------------|
| ARCX.PILLAR      | ✅  | ✅     | ✅     | 2018-05-01 → 2026-05-11   |
| BATS.PITCH       | ✅  | ✅     | ✅     | 2018-05-01 → 2026-05-11   |
| BATY.PITCH       | ✅  | ✅     | ✅     | 2018-05-01 → 2026-05-11   |
| DBEQ.BASIC       | ✅  | ✅     | ✅     | 2023-03-28 → 2026-05-09   |
| EDGA.PITCH       | ✅  | ✅     | ✅     | 2018-05-01 → 2026-05-11   |
| EDGX.PITCH       | ✅  | ✅     | ✅     | 2018-05-01 → 2026-05-11   |
| EPRL.DOM         | ✅  | ✅     | ✅     | 2023-03-28 → 2026-05-11   |
| EQUS.MINI        | ❌  | ❌     | ✅     | 2023-03-28 → 2026-05-11   |
| EQUS.SUMMARY     | ❌  | ❌     | ❌     | 2024-07-01 → 2026-05-11   |
| **GLBX.MDP3**    | ✅  | ✅     | ✅     | **2010-06-06 → 2026-05-11** |
| IEXG.TOPS        | ❌  | ❌     | ✅     | 2023-03-28 → 2026-05-11   |
| IFEU.IMPACT      | ✅  | ✅     | ✅     | 2018-12-23 → 2026-05-10   |
| IFLL.IMPACT      | ✅  | ✅     | ✅     | 2018-12-23 → 2026-05-10   |
| IFUS.IMPACT      | ✅  | ✅     | ✅     | 2018-12-23 → 2026-05-10   |
| MEMX.MEMOIR      | ✅  | ✅     | ✅     | 2023-03-28 → 2026-05-11   |
| NDEX.IMPACT      | ✅  | ✅     | ✅     | 2018-12-23 → 2026-05-11   |
| OCEA.MEMOIR      | ✅  | ✅     | ✅     | 2025-08-24 → 2026-05-11   |
| OPRA.PILLAR      | ❌  | ❌     | ✅     | 2013-04-01 → 2026-05-11   |
| XASE.PILLAR      | ✅  | ✅     | ✅     | 2018-05-01 → 2026-05-11   |
| XBOS.ITCH        | ✅  | ✅     | ✅     | 2018-05-01 → 2026-05-11   |
| XCBF.PITCH       | ✅  | ✅     | ✅     | 2018-11-04 → 2026-05-10   |
| XCHI.PILLAR      | ✅  | ✅     | ✅     | 2023-03-28 → 2026-05-11   |
| XCIS.TRADESBBO   | ❌  | ❌     | ✅     | 2023-03-28 → 2026-05-11   |
| XEEE.EOBI        | ✅  | ✅     | ✅     | 2026-04-09 → 2026-05-11   |
| XEUR.EOBI        | ✅  | ✅     | ✅     | 2025-03-10 → 2026-05-10   |
| XNAS.BASIC       | ❌  | ❌     | ✅     | 2024-07-01 → 2026-05-11   |
| XNAS.ITCH        | ✅  | ✅     | ✅     | 2018-05-01 → 2026-05-11   |
| XNYS.PILLAR      | ✅  | ✅     | ✅     | 2018-05-01 → 2026-05-11   |
| XPSX.ITCH        | ✅  | ✅     | ✅     | 2018-05-01 → 2026-05-11   |

Of these, **only GLBX.MDP3** carries crypto-related derivatives — the CME
Group cryptocurrency futures (BTC, MBT, ETH, MET and a handful of options).

> **No Binance, no Bybit, no OKX, no DEX data.** Databento focuses on
> regulated equity / futures / options exchanges. Crypto-native venues are
> outside their coverage.

---

## 2. BTC instruments on GLBX.MDP3

| parent symbol | description                            | contract size | currency | trading hours (CME Globex) |
|---------------|----------------------------------------|---------------|----------|-----------------------------|
| `BTC.FUT`     | Bitcoin futures (regular)              | 5 BTC         | USD cash-settled to BRR | Sun 18:00 → Fri 17:00 ET, daily 17:00–18:00 break |
| `MBT.FUT`     | **Micro Bitcoin futures**              | 0.1 BTC       | USD cash-settled to BRR | same as above |
| `ETH.FUT`     | Ether futures                          | 50 ETH        | USD cash-settled to ETHUSD_RR | same |
| `MET.FUT`     | Micro Ether futures                    | 0.1 ETH       | USD cash-settled to ETHUSD_RR | same |

CME also lists Bitcoin options, Bitcoin Friday futures (BFF), Bitcoin
Euro futures, etc., but those are out of scope for our spot/perp-style
orderflow strategy.

### Symbology

Databento uses **parent symbology**: `BTC.FUT` means "all live
expirations of the Bitcoin futures product on CME Globex". When a data
query is submitted with `stype_in='parent'`, Databento automatically
expands it into the set of `raw_symbol` instrument-ids active in the
date window. For week 2026-04-01 → 2026-04-08 the expansion will include
the front-month and a handful of nearer expirations.

(The Symbology REST endpoint refused `stype_out=raw_symbol` for parent
on GLBX, but **data queries accept it**, as confirmed by
`metadata.get_record_count` / `get_cost` returning non-zero results
below.)

---

## 3. Cost and size for the target week

`metadata.get_record_count` / `get_billable_size` / `get_cost` for
`start = 2026-04-01T00:00:00`, `end = 2026-04-08T00:00:00`,
`dataset = GLBX.MDP3`, `stype_in = parent`:

| symbol    | schema  | record count   | billable bytes      | cost (USD) |
|-----------|---------|----------------|---------------------|-----------:|
| BTC.FUT   | mbo     | 35 034 382     | 1 961 925 392 (~1.83 GiB) | **$3.29** |
| BTC.FUT   | mbp-10  | 31 682 711     | 11 659 237 648 (~10.86 GiB) | **$5.43** |
| BTC.FUT   | trades  | 35 265         | 1 692 720 (~1.62 MiB)       | **$0.04** |
| MBT.FUT   | mbo     | 37 229 659     | 2 084 860 904 (~1.94 GiB)   | **$3.50** |
| MBT.FUT   | mbp-10  | 31 725 663     | 11 675 043 984 (~10.88 GiB) | **$5.44** |
| MBT.FUT   | trades  | 122 975        | 5 902 800 (~5.63 MiB)       | **$0.15** |

Observations:

- **MBO is cheaper than MBP-10** on this dataset (≈ 60 % of the cost) and
  carries strictly more information. MBO records every order add /
  modify / cancel; MBP-10 collapses to per-level aggregates and is fatter
  on the wire.
- **Trades** are tiny (a few MB at most) — always include them.
- **MBT.FUT has ~3.5× more trades** than BTC.FUT (122 975 vs 35 265 for
  the week) because the micro contract attracts the retail flow that
  generates many small executions. For orderflow research this is
  desirable.

---

## 4. Selected download

| field            | value |
|------------------|-------|
| dataset          | `GLBX.MDP3` |
| primary symbol   | `MBT.FUT` (parent → all live Micro Bitcoin futures expirations) |
| supplementary    | `BTC.FUT` trades only (cross-reference, $0.04) |
| schemas          | **mbo** + **trades** |
| stype_in         | `parent` |
| start            | 2026-04-01T00:00:00Z |
| end              | 2026-04-08T00:00:00Z (exclusive) |
| approx cost      | $3.50 (MBT MBO) + $0.15 (MBT trades) + $0.04 (BTC trades) ≈ **$3.69** |
| approx on-disk   | ~0.4–0.6 GiB after zstd compression |
| local layout     | `data/databento/GLBX.MDP3/MBT.FUT/20260401_20260408/*.dbn.zst` |

**Why MBT.FUT and not BTC.FUT?**
- More trade events ⇒ richer orderflow stream (the strategy's
  `taker-buy / taker-sell` features benefit from higher trade density).
- Slightly larger MBO too (because order events follow trades);
  reconstruction quality is the same.
- The MBO+trades cost ratio favors MBT a hair, but the deciding factor
  is trade density.

**Why MBO and not MBP-10?**
- Cheaper.
- More granular (per-order, not per-level aggregates).
- Our existing strategy reads only L2 price-level state — we will
  aggregate the L3 MBO stream into L2 levels in the converter (Section 8
  of the week-audit report), so we get L2 "for free" out of L3 anyway.

---

## 5. Hard reality check: Binance vs CME

| dimension              | Binance USDS-M Futures BTCUSDT-perp | CME `BTC.FUT` / `MBT.FUT` |
|------------------------|-------------------------------------|----------------------------|
| venue                  | Binance (offshore, unregulated)     | CME Group (Chicago, CFTC-regulated) |
| settlement             | USDT (perpetual, funding rate)      | USD cash to BRR (monthly expiration) |
| contract size          | configurable; smallest 0.001 BTC    | BTC: 5 BTC fixed; MBT: 0.1 BTC fixed |
| tick size              | $0.10                               | BTC: $5 ($25 per tick value); MBT: $5 ($0.50 per tick value) |
| trading hours          | 24 / 7                              | Sun 18:00 ET → Fri 17:00 ET, with daily 17:00–18:00 ET maintenance break |
| typical daily volume   | tens of billions USD notional       | hundreds of millions to ~1 B USD notional (BTC + MBT combined) |
| participant mix        | retail-dominant; large prop / market-maker tier | institutional / commodity-trading-advisor heavy; less retail |
| order types            | limit, market, conditional, no funding-driven liquidations on US-regulated tier | limit, market, stop, with CME-specific session/auction order types |
| funding rate           | yes, 8-hour funding                 | no — basis instead |
| liquidations           | yes, public via `forceOrder` stream | no equivalent public stream |

**Conclusion:** treating CME futures as a drop-in replacement for Binance
perp would invalidate any backtest. The orderflow microstructure overlaps
in shape (book → trades → impact) but **price levels, depth profile,
session structure, and reflexive funding-flow dynamics are fundamentally
different**. CME data is appropriate for:

- ✅ Building / validating a `DatabentoDataSource` adapter and the L2
  reconstruction pipeline.
- ✅ Studying institutional-flow microstructure (large block patterns,
  open / close auction effects, settlement-driven activity).
- ❌ Backtesting a Binance-tuned strategy as-is.
- ❌ Claiming any winrate on this venue and porting that claim to
  Binance.

This conforms to the user's directive:
> "Если доступен только CME BTC futures, использовать его только как
> дополнительный микроструктурный тест, не как замену Binance Futures."

---

## 6. Next steps

1. **Download** the selected slice (Section 4) — covered in
   `reports/DATABENTO_WEEK_AUDIT.md`.
2. **Audit** the downloaded DBN files: row counts, time coverage,
   reconstructability of the book, gaps, sample rows. Same companion
   report.
3. **Adapter** (`src/data/databentoDataSource.ts`?) — only if Step 2
   gives green light. This adapter would map MBO → L2 internal model and
   trades → `TradeEvent`. To be decided after the audit, since the
   investment is real and the venue-mismatch is unrecoverable for
   strategy purposes.
4. **Parser-correctness replay** — 1–3 hours of book reconstruction +
   trade processing, no strategy-engine invocation (same rule as for the
   Kaggle audit: don't conflate parser correctness with venue mismatch).
5. **Verdict** at the bottom of the week-audit report.
