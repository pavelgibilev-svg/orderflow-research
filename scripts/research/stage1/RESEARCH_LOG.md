# Stage 1 Research Log — Imbalance Duel & Multi-Day Validation

> Location note: the Stage-1 TZ suggested `reports/stage1/`, but `/reports/` is
> gitignored in this repo, so this log lives next to the Stage-1 code
> (`scripts/research/stage1/`) to remain version-controlled and accessible to
> future stages. Raw run artifacts stay under `reports/stage1/multiday/`
> (gitignored). Numbers below are verified against
> `reports/stage1/multiday/aggregate_summary.json`.

## Summary

Stage 1 §5.2 (imbalance duel) is formally closed with verdict **BORDERLINE**.
No engine code changes. Imbalance feature is documented as a Stage 2 validation
candidate, gated by a hypothesis to be revalidated when more diverse market
data is available.

## Multi-Day Results (8 days, 2 regimes)

| Metric                              | imbalance_inv | imbalance_exp |
|-------------------------------------|---------------|---------------|
| Pooled d (Reversals vs Controls)    | -0.44 [-0.50, -0.37] | -0.39 [-0.46, -0.33] |
| Pooled d (Reversals vs Tautology)   | -0.27 [-0.36, -0.19] | -0.25 [-0.33, -0.16] |
| Pooled d (Tautology vs Controls)    | -0.17 [-0.24, -0.10] | -0.16 [-0.23, -0.09] |
| Inter-day std (R-vs-C)              | 0.10          | 0.08          |

### Per-day breakdown (imbalance_inv, R-vs-T)

| Date       | Regime                  | N_reversals | d (R-vs-T) |
|------------|-------------------------|-------------|------------|
| 2025-10-10 | post-ATH distribution   | 112         | -0.13      |
| 2025-10-11 | post-ATH distribution   | 72          | -0.03      |
| 2025-10-12 | post-ATH distribution   | 87          | -0.30      |
| 2026-06-02 | bear continuation       | 80          | -0.38      |
| 2026-06-03 | bear continuation       | 109         | -0.33      |
| 2026-06-04 | bear continuation       | 182         | -0.38      |
| 2026-06-05 | bear continuation       | 228         | -0.31      |
| 2026-06-06 | bear continuation       | 97          | -0.26      |

## Findings

### F1. imbalance_inv chosen, imbalance_exp deprecated

`imbalance_exp` underflows to NaN at high prices (BTC ~$120k, λ=10 ticks) due
to `exp(-d/λ)` collapsing for distant levels in the maxDepthPct=0.5% window.
Statistically, the two versions are indistinguishable (overlapping CIs across
all comparisons).

**Operational decision:** use `imbalance_inv` only. Archive `imbalance_exp`.

**Action item for Participant A:** if `imbalance_exp` is implemented in the
TS engine with similar exponential weighting, it will silently produce NaN
on high-price regimes. Either remove it or add explicit numerical guard.

### F2. Robust contrarian sign — established fact

Reversals show systematic OPPOSITE-sign imbalance to the original "absorption
zone" hypothesis. The feature reflects directional flow leading INTO the
extremum, not passive absorption protecting it.

Sign holds on all 8/8 days across both regimes (post-ATH distribution and
bear continuation), pooled effect strong (|d| = 0.44), low inter-day std.
This is no longer a hypothesis — it is a stable empirical finding.

### F3. Extremum-specificity is regime-dependent

Decomposition of the pooled effect:
```
R-vs-C (-0.44)  ≈  R-vs-T (-0.27)  +  T-vs-C (-0.17)
                      ↑                    ↑
              extremum-specific      directional flow
                  (~60%)                  (~40%)
```

Split by regime (mean d, R-vs-T):
- Bear continuation (June 2026): -0.33 (above specificity threshold 0.30)
- Post-ATH distribution (October 2025): -0.15 (below tautology threshold 0.20)

The integral `inter_day_std` (0.10) did NOT flag this because the *total*
counter-trend effect is stable across regimes — what varies is its
*tautological share*, which is only visible in the R-vs-T split.

### F4. Borderline verdict — feature NOT integrated into TS engine

Per `research_validation.py` v2 verdict logic: |d(R-vs-T) pooled| = 0.27,
in [0.20, 0.30] borderline zone. Engine code remains untouched. No heuristic
gates are added at this stage to avoid premature commitment.

## Hypothesis for Stage 2 Validation

> The contrarian/exhaustion signal in imbalance_inv is operationally usable
> in trend-continuation regimes (e.g. `|prior_move_30d_pct| > 15%` with
> direction aligned to the reversal side), and degenerates toward tautology
> in topping/distribution regimes near ATH.
>
> Status: hypothesis, NOT validated classifier. Subject to revalidation when
> 20+ additional days across varied regimes are available.
>
> Backlog item: collect data, repeat multi-day analysis, confirm or refute
> before any TS engine integration.

## Next Steps

1. Await Participant A's dump of legacy bucket-based features
   (`orderflowImbalance`, `buyAbsorption`, `sellAbsorption`, `refillScore`,
   `thinningScore`, `liquidityVoid`) for the 8-day window.
2. Run §5.1 ablation (see `scripts/research/stage1/ablation_prep.py`).
3. If ablation shows `imbalance_inv` carries independent information
   over existing features: keep as candidate, await more data for regime
   revalidation. If redundant: archive.
4. Open as parallel task: build `features_oi.py`, `features_funding.py`,
   `features_liquidations.py` per original Stage 1 TZ §4.3–4.6.

## Status Flags

```
STAGE_1_GEOMETRY_FEATURES                = DONE  (mass, CoM, variance, imbalance_inv)
STAGE_1_IMBALANCE_DUEL                   = DONE  (verdict: BORDERLINE)
STAGE_1_TAUTOLOGY_TEST                   = DONE  (verdict: regime-dependent)
STAGE_1_ABLATION_AGAINST_LEGACY          = BLOCKED (waiting for Participant A dump)
STAGE_1_OI_FUNDING_LIQ_FEATURES          = NOT_STARTED (parallel task available)
TS_ENGINE_INTEGRATION                    = NOT_STARTED (pending §5.1 outcome)
```
