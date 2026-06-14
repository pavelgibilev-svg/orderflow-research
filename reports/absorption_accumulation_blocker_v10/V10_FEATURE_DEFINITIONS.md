# V10 BLOCKER FEATURE DEFINITIONS (causal, fixed defaults)

Build 2026-06-13T10:18:13+00:00 · absorption/accumulation blocker v10 · skeptical, not production.

All features use minutes <= t only. Thresholds are interpretable defaults, NOT tuned to outcomes.
- F1 PRICE_RESPONSE_TO_SELL_PRESSURE: sell_frac_30m>=0.55 AND cvd_30<0 AND ret_30m>=-0.10% (heavy selling, weak downside).
- F2 FAILED_BREAKDOWN: intrabar low last 10m < prior 60m low, but mid[t] back above that low*1.0003 (breakdown reclaimed).
- F3 VWAP_RECLAIM_OR_HOLD: cvd_30<0 AND price_vs_vwap>=-0.05% AND was below VWAP in last 15m (holds/reclaims VWAP under selling).
- F4 LOW_DEFENSE: >=3 tests of prior 60m low in last 30m AND mid[t]>low*1.001 (defended low). [used inside combined]
- F5 CVD_PRICE_DIVERGENCE: cvd[t] new 60m low BUT mid[t] NOT new 60m low (seller effort, no bearish result).
- F6 LOW_VOL_CHOP: ATR/price<0.12% AND |price_vs_vwap|<0.10% AND range_180m<1.0% (no control). [used inside b10F]
Slippage model: WIN +1.86 / LOSS -1.64 base (incl ~14bps cost); each bps adds 2*bps/100 % to round-trip cost.
