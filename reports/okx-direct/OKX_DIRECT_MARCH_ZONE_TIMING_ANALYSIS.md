# OKX direct partial-March 2026 - zone timing analysis

**Scope:** 14 UTC days 2026-03-02..2026-03-15. No strategy / threshold change.

## A. Per-class timing distributions

### primary vs duplicate vs failed

| feature | primary mean / median | duplicate mean / median | failed mean / median |
|---|---|---|---|
| `candidate_to_confirm_min` | 9.7411 / 8.8167 | 11.1994 / 9.9333 | 11.9102 / 8.9833 |
| `confirm_to_trigger_min` | 21.4411 / 11.25 | 65.6861 / 40.9667 | 60.5433 / 23.1 |
| `total_pre_trigger_min` | 31.1822 / 25.9833 | 76.8855 / 52.2333 | 72.4536 / 37.3833 |
| `trigger_to_resolve_min` | 585.5535 / 502.8411 | 483.3677 / 432.15 | 1440.0 / 1440.0 |
| `trigger_to_target_min` | 585.5535 / 502.8411 | 483.3677 / 432.15 | None / None |
| `candidate_to_target_min` | 616.7357 / 521.5244 | 560.2533 / 530.6768 | None / None |
| `confirmed_to_target_min` | 606.9946 / 513.3578 | 549.0539 / 523.6601 | None / None |

## B. Cohen's d effects (pairwise)

| feature | primary vs duplicate | primary vs failed | duplicate vs failed |
|---|---:|---:|---:|
| `candidate_to_confirm_min` | -0.206 | -0.262 | -0.076 |
| `confirm_to_trigger_min` | -0.722 | -0.628 | 0.06 |
| `total_pre_trigger_min` | -0.738 | -0.65 | 0.051 |
| `trigger_to_resolve_min` | 0.289 | -3.245 | -4.049 |
| `trigger_to_target_min` | 0.289 | None | None |
| `candidate_to_target_min` | 0.157 | None | None |
| `confirmed_to_target_min` | 0.161 | None | None |

## C. Notes

- Negative d for `confirm_to_trigger_min` / `total_pre_trigger_min` (primary vs failed) means primaries trigger FASTER after confirmation.
- Positive d for `trigger_to_target_min` (primary vs duplicate) means primaries take longer to reach the move (because they enter EARLIER).
- Caveat: n=15 primary positives across 14 days; effects are suggestive only.