# TREND_DOWN CALIBRATION — TECHNICAL REPORT

Build 2026-06-11T16:16:37+00:00 · RESEARCH/CALIBRATION ONLY · TP=2% SL=1.5% unchanged · no production/Telegram.

## 1-2. Data found / missing
- Bybit ob200 (L2): COMPLETE 12/12 window days. OKX L2: only 3 last-days. Bybit trades: NONE. OKX trades: out-of-window only.
- See DATA_INVENTORY.md. In-window price/L2 from Bybit ob200 mid; trade-flow N/A (proxied).

## 3-4. Exchanges / windows processed
- Bybit, windows: ['W1', 'W2', 'W3'] (2025-11-19..2025-11-22, 2026-02-11..2026-02-14, 2026-01-28..2026-01-31).

## 5. Zones / clusters
- raw zones: 279; unique clusters: 89 (SIMPLIFIED L2-pivot builder, causal, forward-labeled).

## 6. Capital states observed
- {'UNKNOWN': 47, 'DISTRIBUTION_INTO_BOUNCE': 16, 'NO_CONTROL_CHOP': 12, 'ACTIVE_MARKDOWN': 13, 'ABSORPTION_AFTER_SELL_PRESSURE': 1}

## 7-8. Evidence reliability
- Reliable: background_alignment, not_overextended, liquidity_execution, depth-based absorption/initiative (PROXY).
- N/A (no in-window trades): effort_vs_result from executions, taker imbalance, CVD, true volume.

## 9. Candidate filters saved
| filter | state | n | hit2 | loss | winrate | PF | quality |
|---|---|--:|--:|--:|--:|--:|:--:|
| TD_ACTIVE_MARKDOWN_SHORT_CANDIDATE | ACTIVE_MARKDOWN | 1 | 0 | 0 | 0.0 | None | NEED_MORE_DATA |
| TD_DISTRIBUTION_INTO_BOUNCE_SHORT_CANDIDATE | DISTRIBUTION_INTO_BOUNCE | 16 | 2 | 7 | 12.5 | 0.324 | REJECT |
| TD_FORCED_UNWIND_CONTINUATION_CANDIDATE | FORCED_UNWIND | 0 | 0 | 0 | 0.0 | None | NEED_MORE_DATA |
| TD_ABSORPTION_AFTER_SELL_PRESSURE_NO_SHORT_OR_REVERSAL_WATCH | ABSORPTION_AFTER_SELL_PRESSURE | 1 | 0 | 1 | 0.0 | 0.0 | NEED_MORE_DATA |
| TD_NO_CONTROL_CHOP_NO_TRADE | NO_CONTROL_CHOP | 12 | 4 | 1 | 33.3 | 4.537 | WEAK |

## 10. Artifacts
(see ARTIFACTS_LOCATION below)

## 11. Next pass
- Add in-window TRADES (Bybit + OKX) to unlock effort_vs_result / taker imbalance / CVD.
- Re-run with full trade-flow evidence; compare capital_state separation with trades vs L2-proxy.
- Get OKX full 4-day L2 per window for cross-venue capital-state agreement.

ARTIFACTS_LOCATION:
- main_folder: reports/trend_down_calibration_v1/
- inventory: DATA_INVENTORY.csv / DATA_INVENTORY.md
- normalized_schema: NORMALIZED_SCHEMA.md (+ _normalized/*.csv.gz)
- windows_summary: TREND_DOWN_WINDOWS_SUMMARY.csv / .md
- raw_zones: TREND_DOWN_ZONES_RAW.csv
- unique_clusters: TREND_DOWN_UNIQUE_CLUSTERS.csv
- capital_state_casebook: CAPITAL_STATE_CASEBOOK.csv / .json / .md
- evidence_scores: EVIDENCE_BLOCK_SCORES.csv (+ EVIDENCE_BLOCK_DEFINITIONS.md)
- filter_candidates: FILTER_CANDIDATES_TREND_DOWN_V1.json / .csv
- filter_steps: FILTER_STEPS_TREND_DOWN_V1.md
- technical_report: TREND_DOWN_CALIBRATION_TECHNICAL_REPORT.md