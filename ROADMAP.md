# orderflow-research — Roadmap

Дата последнего обновления: 2026-06-16

## Goal

Build and validate an **Orderflow L2 Strategy**: reconstruct the L2 order book
from market data, engineer orderflow features (book geometry, continuous
imbalance, absorption/void, and — planned — OI/funding/liquidations), detect
accumulation/distribution zones, and backtest them. Framed by `README.md` as a
research / backtest module, then extended through the stages below.

> **note: existing docs frame the end-goal differently — confirm with Partner A.**
> - `README.md` states *"This is not a trading bot ... no live recorder, and no
>   exchange API — those are explicitly out of scope per the spec"*, yet the same
>   `README.md` later documents a Binance live-recorder, and this roadmap's
>   Stages 3–4 target live alerting and demo/micro trading. The README scope line
>   and the roadmap's live-trading direction are in tension.
> - `README.md` describes the engine reading **Tardis CSV (Binance-futures)**,
>   whereas current research data is **Bybit `ob200`** (see
>   `scripts/research/stage1/RESEARCH_LOG.md` and `tz_uchastnik_b_etap_1_1.md`).
> - The term "Stage 1" is overloaded: `README.md` calls the whole backtest module
>   a "Stage 1 deliverable", while this roadmap and the Participant-B TZ use
>   "Stage 1 / Этап 1" for data-enrichment & geometry features. This document
>   uses the latter meaning.

## Stage 1: Data enrichment & geometry features
**Plan:** 1.5–2 months
**Status:** IN PROGRESS

Goal: extend feature space (geometric book moments, OI, funding, liquidations,
basis), run ablation against legacy bucket-based features, produce a unified
feature dataset bit-exact validated between Python research code and TS engine.

See `docs/STAGE_1_PROGRESS.md` for detailed, evidence-backed status.

## Stage 2: Zone calibration & hard backtest
**Plan:** 1 month
**Status:** NOT STARTED (depends on Stage 1 closure)

Goal: run zoneDetector on 6–12 months of history, get thousands of candidate
zones, sift through feature filters in Python, derive a formal "passport" of a
working zone (e.g. "LONG zone valid only when: mass_bid rising AND OI rising AND
funding < X AND ...").

## Stage 3: Alert Engine
**Plan:** 2–3 weeks
**Status:** NOT STARTED

Goal: transform the backtest engine into a realtime scanner pushing prepared
trade decisions (entry, stop, target) to Telegram. Human still executes.

## Stage 4: Forward test (Incubator)
**Plan:** 1 month
**Status:** NOT STARTED

Goal: trade strictly by alerts on demo/micro positions; validate (a)
spread/slippage matches modelled, (b) human execution speed is sufficient, (c)
winrate from Stage 2 holds on live data.

## Cumulative timeline
Per plan: ~4.5–5 months from project start to live trading on small size.
Actual pace: see `docs/STAGE_1_PROGRESS.md` for current calibration (no
week-by-week estimates are recorded — only verifiable repo state).

## Responsibilities (current understanding — to confirm with Partner A)
- **Participant B (research):** Python research code, feature math, statistical
  validation. Verifiable in repo: `scripts/research/stage1/`.
- **Participant A (production):** TypeScript engine, realtime infrastructure,
  order book recorder. Verifiable in repo: `src/` (TS engine, `src/live-recorder/`).
- **Shared artifacts:** feature specifications, JSON test vectors
  (`scripts/research/stage1/feature_test_vectors.json`),
  `scripts/research/stage1/RESEARCH_LOG.md`, this roadmap.

This split needs explicit confirmation — see "Open coordination items" below.

## Open coordination items
- Confirm the responsibility split between Participant A and B in writing.
- Confirm the timeline of Participant A's `legacy_features_all_days.csv` dump
  (blocking §5.1 ablation; expected schema documented in
  `scripts/research/stage1/ablation_prep.py`).
- Confirm what Participant A is currently building (architecture sprint?
  imbalance portage? both?) — status unclear, requires coordination with partner.
- Resolve whether any `orderbook-builder/` or similar component exists on
  Partner A's side: it is **not present in this repo** (searched 2026-06-16) —
  if mentioned in AI logs, it needs verification with Partner A.
- Confirm whether the §6 bit-exact TS↔Python cross-check (≥50k rows, per the
  Stage-1 TZ §7.1) has been run on Partner A's TS engine, or is still pending.
