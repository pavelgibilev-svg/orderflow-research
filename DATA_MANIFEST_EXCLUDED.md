# DATA_MANIFEST_EXCLUDED.md

What is **deliberately NOT committed to GitHub**, why, where it lives locally, and which
scripts read it. The data itself is **not** attached here — only the manifest.

All raw market data is confined to `data/` (plus a few root archives) and excluded by
`.gitignore`. None of it is required to read the research conclusions (those are in
`reports/**/*.md`); it is only required to *re-run* the research scripts.

> Note on naming: research **scorecards** that contain the word `trades` in their
> filename (e.g. `..._RS1_BASELINE_TRADES.csv`) are simulated trade *ledgers* and ARE
> committed. The exclusions below are real venue market data only. We intentionally do
> not use bare `*trades*` / `*orderbook*` ignore globs so those scorecards survive.

---

## Excluded categories

### 1. OKX raw order book (L2) — `incremental_book_L2`
- **Why excluded:** 200–1100 MB **per day**, hundreds of files (multi-hundred-GB total).
- **Local location:** `data/okx-historical/BTC-USDT-SWAP/<YYYY-MM-DD>/incremental_book_L2.csv.gz`
  (full daily March + May 2026, plus first-of-month samples 2024–2026);
  raw tar form under `data/okx-direct/.../raw/orderbook/*.tar.gz`, `data/OKX 15-30.03.26/`,
  `data/okx may 2026/`, `data/trend_down_v2_okx/*.tar.gz`.
- **To reproduce:** place Tardis-schema `incremental_book_L2.csv.gz`
  (`exchange,symbol,timestamp,local_timestamp,is_snapshot,side,price,amount`) under
  `data/okx-historical/BTC-USDT-SWAP/<date>/`.
- **Read by:** `scripts/research/td_v11b_build_l2.py` (book reconstruction → per-minute cache).

### 2. OKX / Binance raw trades — `trades`
- **Why excluded:** 25–60 MB/day gzip; raw tick prints.
- **Local location:** `data/okx-historical/.../trades.csv.gz`,
  `data/tardis/binance-futures/BTCUSDT/<month>/trades.csv.gz`,
  `data/okx-direct/.../raw/trades/*.zip`, `data/binance-historical/.../trades.csv.gz`.
- **To reproduce:** Tardis-schema `trades.csv.gz` alongside the L2 files.
- **Read by:** the per-minute series builders behind `reports/short_permission_gate_v5/_series/`
  (loaded via `td_v5_gate.get_series`), and `td_v4_regime.load_series`.

### 3. Binance live recorder dumps — `book_ticker`, `raw_depth_events`, `orderbook_snapshots_1s`, `trades`
- **Why excluded:** 0.1–3.5 GB **per file** (`.jsonl`), the single largest items in the tree.
- **Local location:** `data/binance-live-normalized/...`, `data/binance-live-archives/staging/...`,
  `data/file-recordings-from-okx/...`.
- **To reproduce:** run the live recorder (`src/live-recorder/`) into ClickHouse / JSONL spool,
  or supply the `.jsonl` dumps.
- **Read by:** the Binance OOS pipeline (`scripts/binance-live/*`) and `backtest:db`.

### 4. Binance historical Tardis — `incremental_book_L2`, `book_ticker`, `trades`
- **Why excluded:** 0.4–0.9 GB/day gzip.
- **Local location:** `data/binance-historical/BTCUSDT/<date>/`,
  `data/tardis/binance-futures/BTCUSDT/<month>/`.
- **Read by:** `scripts/binance-live/*`, `scripts/data-sanity/l2_parity_audit.py`.

### 5. Reconstructed L2 per-minute caches
- **Why excluded:** derived caches (regenerable from raw L2); JSON, 0.5 MB+ each.
- **Local location:** `reports/**/_l2cache/`, `reports/**/_l2cache_10d/`, `reports/**/_l2cache_fixed/`,
  `reports/**/_series/`, `reports/**/_normalized/`.
- **To reproduce:** re-run `td_v11b_build_l2.py` (L2 cache) / the v5 series builder.
- **Read by:** `td_v11b_l2.py` (`_l2cache`), `td_v5_gate.get_series` (`_series`).

### 6. March / May 2026 windows and other large per-event report CSVs
- **Why excluded:** per-event / per-minute research dumps > 1 MB (not summary scorecards).
- **Local location (still in repo tree, gitignored):**
  `reports/event_trigger_regime_control_v4/EVENT_CANDIDATES_ALL_REGIMES.csv` (3.8 MB),
  `.../EVENT_OUTCOMES_ALL_REGIMES.csv` (2.0 MB),
  `reports/forward_validated_absorption_labels_v11/V11_FORWARD_LABELS.csv` (3.4 MB),
  `.../V11_SELL_PRESSURE_CANDIDATES.csv` (1.9 MB),
  `reports/strategy-calibration/MARCH_DYNAMIC_L2_FEATURE_DATASET.csv` (1.8 MB),
  `.../MARCH_DYNAMIC_L2_SELECTOR_SEARCH.csv` (1.5 MB),
  `.../MARCH_STAGE_SPECIFIC_SELECTOR_RESULTS.csv` (1.8 MB),
  `reports/trend_down_event_trigger_v3/EVENT_CANDIDATES_RAW.csv` (3.6 MB),
  `.../EVENT_CANDIDATES_UNIQUE.csv` (1.1 MB).
- **To reproduce:** re-run the corresponding `scripts/research/` / `scripts/strategy-calibration/` pass.

### 7. Root / misc archives
- **Why excluded:** multi-GB zips and venue archives.
- **Local location:** `OFFRW.zip` (4.9 GB, root), `Binance data archived/` (root),
  `data/11.06.2026/*.zip`, `data/kaggle/binance-btcusdt-l3/*.parquet`.

### 8. Secrets
- **Why excluded:** never commit credentials.
- **Status:** no real secret files exist in the tree (only `.env.example`, public-config template,
  empty password). `.gitignore` blocks `.env`, `.env.*`, `secrets.*`, `credentials.*`, `*.key`, `*.pem`.

---

## What you need locally to reproduce the research

1. Tardis-schema OKX `incremental_book_L2.csv.gz` + `trades.csv.gz` for the windows of
   interest under `data/okx-historical/BTC-USDT-SWAP/<date>/`.
2. The per-minute series caches under `reports/short_permission_gate_v5/_series/<window>.json`
   (or regenerate them from raw trades).
3. Python 3.10+ (standard library only — the research scripts have no third-party deps).

With those present, the `scripts/research/td_v*.py` passes run end-to-end and regenerate the
committed `reports/**/*.md` + small `*.csv` artifacts.
