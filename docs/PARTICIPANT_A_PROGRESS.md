# Participant A (Production / Engine) — Progress Report

Дата: 2026-06-16
Status: IN PROGRESS

Symmetric counterpart to `docs/STAGE_1_PROGRESS.md` (Participant B, branch
`feat/stage1-book-geometry`). All statuses below are derived only from the repository
file tree, git state, and test runs verified on **2026-06-16**. Each item is tagged with
its real git status: **committed/pushed**, or **UNTRACKED (local-only)** — meaning it
exists on Participant A's working disk but has never been `git add`ed/committed/pushed,
so it is invisible to anyone working from GitHub or any clone.

> **⚠️ Honesty banner.** The biggest fact in this report: three working modules
> (`fast-l2-parser/`, `chrono-dispatcher/`, `orderbook-builder/`) are **untracked** in git
> (`git status` shows them as `??` as of 2026-06-16). They are NOT on any branch and NOT on
> the remote. This is the direct cause of Participant B not seeing `orderbook-builder/`.

## Git ground truth (verified 2026-06-16)

- `main` = `b2fafd9` ("Add AdShort research code and reports without raw market data"),
  in sync with `origin/main` (0 ahead / 0 behind).
- Participant B's branch `feat/stage1-book-geometry` (top `8833883`) forked from
  `a84cc8f` — **before** `b2fafd9`. Therefore B's branch does NOT contain the v9–v11b
  research arc or its reports.
- `git status` untracked, top-level: `chrono-dispatcher/`, `fast-l2-parser/`,
  `orderbook-builder/` (plus large data dirs, which are gitignored by design).

## Scope of "my side"

1. The **TypeScript backtest/engine** (`src/`) — data ingestion, L2 replay, feature
   engine, zone detector, target checker, reports, CLIs, and an optional Binance
   live-recorder. Pre-existing and committed; shared base with B's branch.
2. **Standalone infrastructure modules** built later (UNTRACKED, local-only): a fast
   gzip-CSV L2 parser, a deterministic event-replay dispatcher, and an L2 order-book
   builder.
3. A **short-permission / phase-separation research arc** (v4–v11b) — committed on `main`,
   not on B's branch.

---

## Actual state — by component

### TS backtest engine — data ingestion
- **Status: DONE (committed)**
- Evidence: `src/data/tardisCsvLoader.ts`, `src/data/fileResolver.ts`,
  `src/data/schema.ts`, `src/data/marketDataSource.ts`, `src/data/clickhouseDataSource.ts`.
- Commit: present since `0395f77`..`dbe564f`; on `main` and on B's branch base.
- Notes: streams Tardis CSV.gz without full load. NOTE the scope tension B flagged: the
  engine README targets **Tardis Binance-futures**, while B's research data is **Bybit
  `ob200`** — the engine has no Bybit ob200 loader yet (gap, see Divergences).

### TS engine — L2 order book replay
- **Status: DONE (committed)**
- Evidence: `src/replay/orderBook.ts`, `src/replay/marketReplayEngine.ts`,
  `src/replay/snapshotBuilder.ts`, `src/replay/dataQuality.ts`; tests `tests/orderBook.test.ts`.
- Notes: snapshot+delta reconstruction; the same `OrderBook` class backs the live recorder.

### TS engine — feature engine (LEGACY feature set)
- **Status: DONE (committed)** — but NOT the Stage-1 geometry features
- Evidence: `src/features/featureEngine.ts`, `orderflowImbalance.ts`, `absorption.ts`,
  `liquidityEvents.ts`, `liquidityVoid.ts`, `volatilityRegime.ts`; tests `tests/features.test.ts`.
- Notes: this is the **bucket-imbalance / absorption / void** feature set. The Stage-1 TZ
  §4.1 **geometric book moments** (mass / center-of-mass / variance) that B implemented in
  `scripts/research/stage1/features_geometry.py` are **NOT ported to TS**. Consequence:
  the §6 bit-exact TS↔Python cross-check (TZ §7.1) **has NOT been run** — there is nothing
  on the TS side to cross-check against yet. This resolves one of B's open questions: the
  cross-check is still pending on Participant A.

### TS engine — zone detector / strategy
- **Status: DONE (committed)**
- Evidence: `src/strategy/zoneDetector.ts`, `zoneStateMachine.ts`, `targetChecker.ts`,
  `zoneScoreV1.ts`, `probabilityBaseline.ts`, `uniqueMoveClustering.ts`; `tests/*`.
- Notes: Candidate→Confirmed→Triggered→Resolved state machine; 2% target checker. This is
  the substrate Stage 2 (zone calibration) will run on.

### TS engine — reports + CLIs
- **Status: DONE (committed)**
- Evidence: `src/reports/*`, `src/cli/*` (backtestDay, exportSnapshots, validateTardis,
  sampleBacktest2026, backtestDb, backtestOkxTechnical, liveRecorder, …).
- Notes: emits `zones.csv / zones.json / report.md` per run. There is **no dedicated
  `legacy_features_all_days.csv` exporter** in B's expected schema — see Blockers.

### TS engine — live recorder (Binance public)
- **Status: DONE (committed), NOT running**
- Evidence: `src/live-recorder/*` (binanceWsClient, binanceRestClient, localOrderBookLive,
  recorderService, batchWriter, spoolWriter, healthMonitor, schema).
- Notes: public WS/REST → ClickHouse; no API key, no trading endpoints (enforced by a test).
  Not currently collecting; it is the eventual source for the missing OI/funding/liquidations.

### Standalone module — `fast-l2-parser/` (gzip-CSV L2 parser + book builder, TS)
- **Status: DONE — but UNTRACKED (local-only)**
- Evidence: `fast-l2-parser/src/{l2-parser,fast-number,order-book,order-book-dispatcher,types}.ts`,
  `tests`/vitest. git: `?? fast-l2-parser/` (never committed).
- Verified 2026-06-16: vitest **14/14 green**; parser bench ~**2.78M rows/sec** (3M synthetic
  rows), order-book builder bench ~**2.0M updates/sec**.
- Notes: streaming Buffer-level CSV.gz parser (no readline/split) + an L2 OrderBookBuilder
  (mid-batch crossed-book deferral, snapshot reset). Specialized for `incremental_book_L2`.

### Standalone module — `chrono-dispatcher/` (deterministic EventDispatcher, Python)
- **Status: DONE — but UNTRACKED (local-only)**
- Evidence: `chrono-dispatcher/chrono_dispatcher/{events,sources,dispatcher,config,errors}.py`,
  `tests/test_dispatcher.py`. git: `?? chrono-dispatcher/`.
- Verified 2026-06-16: pytest **17/17 green**; bench ~**192k events/sec** (tuple heap key beats
  Event.__lt__ in a fair warm-cache run).
- Notes: K-way merge (min-heap), per-source jitter watermark + aggressive refill, frozen/slots
  events. This is a *reference* EventDispatcher; the canonical one is B/A's shared contract.

### Standalone module — `orderbook-builder/` (L2 OrderBookState, Python) ← B's open question
- **Status: DONE — but UNTRACKED (local-only)**
- Evidence: `orderbook-builder/orderbook/{types,config,state,manager}.py`,
  `tests/test_orderbook.py`, `benchmarks/bench_orderbook.py`. git: `?? orderbook-builder/`.
- Verified 2026-06-16: pytest **22/22 green**; bench Mode A (FULL SortedDict) ~**439k upd/s**
  apply-only, Mode B (top-N numpy cache) **5.51× faster on read-heavy** workloads.
- Notes: scaled-int core, SortedDict source-of-truth, optional numpy top-N cache with promote;
  per-symbol `BookManager`. **DIRECT ANSWER to B's open item:** yes, this component exists and
  works — but ONLY on Participant A's local disk; it was never pushed, so it is correctly
  "not present in the repo" from B's vantage point.

### Standalone module — Feature Pipeline (zero-alloc MIMO caркас)
- **Status: NOT STARTED**
- Evidence: none (no `features/` package on disk).
- Notes: spec received; **blocked on a stitch-contract decision** — the pipeline resets on
  `is_snapshot`, but the Task-1 `Event` has no `is_snapshot` field (it lives on the
  order-book payload, ORDER_BOOK only). A clarifying question on where `is_snapshot` comes
  from was raised and not yet resolved; coding is paused pending that answer.

### Research arc v4–v11b (short-permission / phase separation)
- **Status: DONE (committed on `main`, NOT on B's branch)**
- Evidence: `scripts/research/td_v4_regime.py` … `td_v11b_l2.py`;
  `reports/phase_separation_audit_v9/`, `absorption_accumulation_blocker_v10/`,
  `forward_validated_absorption_labels_v11/`, `l2_aware_absorption_validation_v11b/`.
- Commit: `b2fafd9`.
- Honest verdicts (from those reports): v9 phase model NEED_MORE_DATA; v10 absorption blocker
  NEED_MORE_DATA; v11 trades-only absorption REJECTED; v11b L2-aware absorption REJECTED at
  1-min resolution. This is a **different framing** from B's book-geometry research and is not
  yet reconciled with it.

---

## Divergences vs Participant B (the comparison)

1. **Branch fork point.** B's `feat/stage1-book-geometry` forked at `a84cc8f`, before my
   `b2fafd9`. ⇒ B does not have the v9–v11b research/reports; I do not have B's
   `scripts/research/stage1/` (it is on their branch, not merged to `main`).
2. **Three untracked modules.** `fast-l2-parser/`, `chrono-dispatcher/`, `orderbook-builder/`
   are local-only on A. ⇒ invisible to B until committed+pushed. (Resolves B's
   "orderbook-builder?" item.)
3. **Stage-1 geometry not in TS.** B's §4.1 geometry is Python-only; the TS engine has the
   legacy bucket/absorption features. ⇒ the §6 bit-exact 50k-row cross-check is **not run**.
4. **`legacy_features_all_days.csv` not produced.** B's §5.1 ablation is blocked on this dump
   from A; A has not produced it (the engine emits `zones.csv`, a different schema).
5. **Data backend mismatch.** Engine README/loaders target Tardis Binance-futures; B's data
   is Bybit `ob200`. No Bybit ob200 loader exists in the TS engine.

## Blockers (Participant A side)

- **§6 cross-check:** requires porting Stage-1 geometry (§4.1) into `src/features/` first;
  not started.
- **`legacy_features_all_days.csv`:** needs a small CLI to dump the engine's feature rows in
  B's documented schema (`scripts/research/stage1/ablation_prep.py` docstring); not built.
- **OI / funding / liquidations history:** same gap as B — no `derivative_ticker` /
  `liquidations` data on disk; the live-recorder could collect it going forward.
- **Feature Pipeline:** blocked on the `is_snapshot` stitch-contract decision (above).

## Open questions (need Partner B input)

- Should the three untracked modules be committed/pushed (and to which branch — `main`, a new
  `feat/...`, or merged toward B's branch) so they become verifiable on both sides?
- Is `orderbook-builder/` (scaled-int L2 builder) the component B expected as "Task 1 / book
  state", or is B expecting it inside the TS engine instead of a separate Python module?
- Do we reconcile the two research framings (A's short-permission gates vs B's book geometry)
  into one Stage-1 feature set, or keep them as parallel tracks?
- Confirm the responsibility split: is "Participant A = TS engine + infra" accurate, given
  that A has so far produced mostly Python research + Python standalone modules?

## What's NOT in this report (by design)

- Subjective progress percentages or timeline predictions.
- Any status not backed by a file + git state + (where claimed) a verified test/bench run.
- Claims about B's branch beyond what `git ls-tree` on `origin/feat/stage1-book-geometry`
  shows as of 2026-06-16.
