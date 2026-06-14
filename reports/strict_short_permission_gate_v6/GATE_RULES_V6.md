# GATE RULES v6 (rule-based, stricter)

Build 2026-06-12T16:45:47+00:00 · research/calibration.

- **GATE_6A_STRICT_NO_UPTREND**: FORBID if ret60>0 OR ret180>0 OR ret360>0 OR price>vwap OR cvd60>0 OR buy_recovery
- **GATE_6B_DOWNTREND_ONLY**: ALLOW only if ret60<0 AND ret180<0 AND cvd180<0 AND price<vwap AND downside_progress
- **GATE_6C_SELLER_CONTROL_STRICT**: ALLOW only if net_taker60<0 AND cvd60<0 AND pc15<0 AND weak_bounce AND not bounce_danger
- **GATE_6D_NO_BOUNCE_NO_CHOP**: FORBID if bounce_danger OR chop
- **GATE_6E_COMBINED_STRICT**: ALLOW only if downtrend_perm AND seller_ctrl_strict AND not uptrend_danger AND not chop AND not bounce_danger
