# GATE RULES (rule-based, causal)

Build 2026-06-12T16:24:23+00:00 · research/calibration.

- **GATE_1_STRICT_DOWNTREND**: ret60<0 AND ret180<0 AND cvd60<0 AND not bounce_danger
- **GATE_2_SELLER_CONTROL**: net_taker_60m<0 AND ret60<0 AND not bounce_danger
- **GATE_3_NO_UPTREND**: allowed unless uptrend(ret60>0.3 OR ret180>0.5 OR >sma180 OR cvd60>0)
- **GATE_4_NO_CHOP**: allowed unless chop(|ret180|<0.5 AND range180>1.5)
- **GATE_5_COMBINED**: downside_background AND seller_control AND not uptrend AND not chop AND not bounce_danger
