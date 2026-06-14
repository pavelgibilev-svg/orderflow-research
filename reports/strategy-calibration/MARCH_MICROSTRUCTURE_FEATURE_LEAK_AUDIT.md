# Microstructure feature leak audit

**Build:** 2026-05-28T15:09:48+00:00

## Decision timestamps
- `candidateTs`: zone first detected by engine.
- `confirmedTs`: zone confirmed by engine (defended cycles + persistence).
- `triggerTs`: engine fired trigger (break + side flow).
- `first_touch_ts`: first bar where price touches zone band after confirmedTs.
- `micro_setup_validated_ts`: when microstructure setup is actually visible (hit detected + refill response observed). Always > confirmedTs in practice; if used as decision time, that becomes the alert timestamp.

## Field availability

| field | computed_window | cand_safe | confirm_safe | trigger_safe | micro_setup_safe | leak_status |
|---|---|---|---|---|---|---|
| per_level_wall_lifetime_60m_before_anchor | [anchor-60m, anchor] | N (anchor=candidate makes it candidate-safe IF window ends at candidateTs) | Y (window ends at confirmedTs) | Y | Y | SAFE if window ends at anchor |
| refill_after_hit (hits before anchor only) | [anchor-60m, anchor] | N for hits after candidate | Y (only count hits with ts <= confirmedTs) | Y | Y (but ts must be <= micro_setup_validated_ts) | SAFE if hit_ts <= anchor and refill_ts <= anchor |
| refill_after_hit (allowing post-anchor refill) | [anchor-60m, anchor+60s] | LEAK | LEAK | LEAK | Y (if anchor = micro_setup_validated_ts) | FUTURE LEAK at candidate / confirmed / trigger |
| liquidity_void_to_target (snapshot) | snapshot at anchor | Y (uses only book state at anchor) | Y | Y | Y | SAFE at anchor |
| microprice_evolution_* | rolling [anchor-Wsec, anchor] | Y | Y | Y | Y | SAFE if window ends at anchor |
| add_cancel_imbalance_* | rolling [anchor-Wsec, anchor] | Y | Y | Y | Y | SAFE |
| setup_type_classification (using only safe features) | computed from confirm-safe features only | Y | Y | Y | Y | SAFE iff inputs are leak-free |

## Rules followed in this research
- All new features in this pass are computed with windows ENDING at `confirmedTs`.
- No feature uses any tick at ts > confirmedTs.
- Outcome labels (`watch_label`, `coverage_class`, `matched_move_size_pct`) used ONLY in evaluation, never in selectors.