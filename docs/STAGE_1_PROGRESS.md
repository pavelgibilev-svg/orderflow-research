# Stage 1 Progress Report

Дата: 2026-06-16
Status: IN PROGRESS

All statuses below are derived only from the repository file tree and git
history (branch `feat/stage1-book-geometry`, evidence verified 2026-06-16).
Components with no corresponding file are marked NOT STARTED. Data that lives
outside the repo is called out explicitly.

## Originally planned scope (per initial Stage 1 TZ)

Reference: `scripts/research/stage1/tz_uchastnik_b_etap_1_1.md`
("ТЗ для Участника Б — Этап 1: Геометрия стакана + контекстные слои") — the
original Stage-1 TZ IS in the repo.

Planned features and infrastructure (TZ section in parentheses):
1. Geometric book moments — mass, center of mass, variance per side (§4.1)
2. Continuous imbalance — two versions: inv, exp (§4.2)
3. OI dynamics — multi-window deltas + intensity normalization (§4.3)
4. Liquidations — flag + multi-window volume (§4.4)
5. Funding rate + basis (§4.5, §4.6)
6. Multi-day reconstruction pipeline (§3.x / book_reconstruction)
7. Tautology test infrastructure (added in research_validation v2)
8. Ablation against legacy bucket-based features (§5.1)
9. TS↔Python bit-exact validation via JSON test vectors (§6, acceptance §7.1)
10. Alpha report — visual audit (§5.3)
11. Stage 1 feature dataset on 6+ months of history (§7 acceptance)

## Actual state — by component

### Geometric book moments
- **Status: DONE**
- Evidence: `scripts/research/stage1/features_geometry.py`
- Last commit: `24743f9` (2026-06-15)
- Notes: `book_geometry_snapshot` (single-snapshot reference), `book_geometry_batch`
  (vectorized via `np.add.reduceat`), `book_deformation` (#4). Pure NumPy.

### Continuous imbalance (inv + exp)
- **Status: DONE** (computed); `imbalance_exp` deprecated
- Evidence: `scripts/research/stage1/features_geometry.py` (`imbalance_inv`,
  `imbalance_exp` fields)
- Last commit: `24743f9` (2026-06-15)
- Notes: `imbalance_exp` deprecated due to NaN underflow at high prices
  (`exp(-d/λ)` collapses, BTC ~$120k). Decision documented in
  `scripts/research/stage1/RESEARCH_LOG.md` finding F1 (commit `a20a73b`).

### Multi-day pipeline & tautology test
- **Status: DONE**
- Evidence: `scripts/research/stage1/book_reconstruction.py` (Bybit ob200
  snapshot+delta replay → 1s snapshots → vectorized geometry) and
  `scripts/research/stage1/research_validation.py` (multi-day runner + tautology
  test t* vs t*-90s, three comparisons)
- Last commit: `531d840` (reconstruction, 2026-06-15); `159c40e`
  (research_validation v2, 2026-06-15)
- Notes: Ran on 8 days (2025-10-10..12 + 2026-06-02..06). Verdict BORDERLINE
  (see RESEARCH_LOG F3/F4). Reconstruction has an internal Python parity guard
  (batch vs reference = 2.18e-11). Per-day run outputs live in
  `reports/stage1/` which is **gitignored — outputs are NOT in the repo**.

### OI dynamics
- **Status: NOT STARTED**
- Evidence: not found in current repo state (no `features_oi.py`)
- Notes: BLOCKED — no `derivative_ticker` (OI) data on disk; cannot compute.

### Liquidations
- **Status: NOT STARTED**
- Evidence: not found in current repo state (no `features_liquidations.py`)
- Notes: BLOCKED — no historical liquidations data on disk; cannot compute.

### Funding rate + basis
- **Status: NOT STARTED**
- Evidence: not found in current repo state (no `features_funding.py`)
- Notes: BLOCKED — no `derivative_ticker` (funding/mark/index) data on disk.

### Ablation infrastructure
- **Status: DONE (stub)**; ablation RUN is BLOCKED
- Evidence: `scripts/research/stage1/ablation_prep.py`
- Last commit: `6d42681` (2026-06-15)
- Notes: Conditional Cohen's d + Pearson/Spearman correlation, with stub mode
  that prints the expected schema and exits 0 until the legacy-feature dump
  arrives. Full ablation is BLOCKED on Participant A's
  `data/participant_a/legacy_features_all_days.csv` (schema documented in the
  script docstring). Smoke-verified end-to-end on a synthetic dump.

### Bit-exact TS↔Python validation
- **Status: PARTIAL** — test-vector contract DONE; the ≥50k-row cross-check NOT done
- Evidence: `scripts/research/stage1/feature_test_vectors.json` +
  `scripts/research/stage1/test_vectors_gen.py`
- Last commit: `7de91e0` (2026-06-15)
- Notes: The §6 contract (17 synthetic cases, 6-decimal expected geometry) is
  produced for Participant A. The actual TS↔Python numerical match on ≥50k rows
  (Stage-1 TZ acceptance §7.1) has NOT been run here — it requires Participant A's
  TS implementation. **status unclear, requires coordination with partner.** (The
  2.18e-11 parity above is Python-internal batch-vs-reference, not cross-language.)

### Alpha report (visual audit)
- **Status: NOT STARTED**
- Evidence: not found in current repo state (no `alpha_report.py`)
- Notes: matplotlib is not installed in this environment; plot generation is
  skipped throughout (`research_validation.py` prints
  "matplotlib unavailable — PNG plots skipped").

### Multi-month feature dataset
- **Status: NOT STARTED**
- Evidence: not found in current repo state
- Notes: 8 days reconstructed (3 × Oct-2025, 5 × Jun-2026), but outputs are
  gitignored (`reports/stage1/`) and far short of the "6+ months" target.

## Data assets present in repo

- **In-repo data: NONE.** The repo's `/data/` and `/reports/` are gitignored, so
  no market data or run artifacts are version-controlled.
- **External data directory** (read by absolute path, not in repo):
  `C:\orderflow-recoder module\data_bybit\`
  - Date coverage: 2025-10-10, 2025-10-11, 2025-10-12, 2026-06-02, 2026-06-03,
    2026-06-04, 2026-06-05, 2026-06-06 (8 days).
  - File types present: order book (`ob200`, perp + spot) and trades (perp + spot).
  - Missing per Stage 1 requirements (confirmed by direct `ls`/`find`, 2026-06-16):
    **`derivative_ticker` (OI/funding/mark/index) and `liquidations` are absent.**

## Findings & documented decisions

Source: `scripts/research/stage1/RESEARCH_LOG.md` (commit `a20a73b`).
- **F1.** `imbalance_inv` chosen; `imbalance_exp` deprecated (NaN underflow at high price).
- **F2.** Robust contrarian sign — established fact (pooled d −0.44, inter-day std
  0.10, 8/8 days, both regimes; imbalance reflects flow INTO the extremum, not absorption).
- **F3.** Extremum-specificity is regime-dependent (June bear-continuation specific
  d≈−0.33; October post-ATH tautological d≈−0.15).
- **F4.** Borderline verdict — feature NOT integrated into TS engine.
- **Decision:** `imbalance_inv` chosen, `imbalance_exp` archived.
- **Stage-2 hypothesis (recorded):** the contrarian/exhaustion signal is usable in
  trend-continuation regimes and degenerates toward tautology near ATH; not a
  validated classifier — needs 20+ more days to confirm/refute.

## Blockers

- **§5.1 ablation:** waiting on Participant A's `legacy_features_all_days.csv`
  (expected schema documented in `scripts/research/stage1/ablation_prep.py`).
- **§4.3 OI / §4.4 liquidations / §4.5 funding / §4.6 basis:** historical
  `derivative_ticker` and `liquidations` data not on disk — requires Tardis
  purchase, a Coinglass/Bybit API pull, or future collection via the live-recorder.
- **§6 bit-exact 50k-row cross-check:** pending Participant A's TS geometry
  implementation; not runnable from the Python side alone.

## Open questions (need Partner A input)

- What is Participant A currently building — TS engine architecture sprint,
  imbalance portage, both, or something else? (status unclear)
- Does an `orderbook-builder/` or equivalent component exist on Partner A's side?
  It is **not present in this repo** (searched 2026-06-16); if mentioned in AI
  logs, it is not verified here.
- ETA for the `legacy_features_all_days.csv` dump (blocking §5.1)?
- Has Partner A implemented the §6 geometry in TS and run the bit-exact
  cross-check on ≥50k rows (TZ §7.1), or is that still in the plan?
- Who sources the missing `derivative_ticker` / `liquidations` history needed for
  §4.3–4.6, and by when?

## What's NOT in this report (by design)

- Subjective progress estimates ("we're 30% done") — left to humans.
- Predictions about future work timing.
- Anything not directly verifiable in the repo file tree.
