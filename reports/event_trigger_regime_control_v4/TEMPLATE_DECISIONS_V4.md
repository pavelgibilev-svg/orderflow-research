# TEMPLATE DECISIONS v4 (status = lift over random across regimes)

Build 2026-06-12T15:08:44+00:00

- **TD_ACTIVE_MARKDOWN_EVENT_SHORT_TEMPLATE** [ACTIVE_MARKDOWN_EVENT] -> **REJECT** · per-regime (n / event_PF / pf_lift_vs_random): TREND_DOWN:n3164/PF1.384/dPF-1.107, TREND_UP:n981/PF0.25/dPF0.093, RANGE_CHOP:n933/PF0.667/dPF-0.13, REVERSAL_BOUNCE:n180/PF0.284/dPF-1.271
- **TD_FORCED_UNWIND_EVENT_SHORT_TEMPLATE** [FORCED_UNWIND_EVENT] -> **REJECT** · per-regime (n / event_PF / pf_lift_vs_random): TREND_DOWN:n317/PF1.588/dPF-0.903, TREND_UP:n44/PF0.087/dPF-0.07, RANGE_CHOP:n65/PF0.548/dPF-0.249, REVERSAL_BOUNCE:n11/PFNone/dPFNone
- **TD_CVD_BREAKDOWN_EVENT_SHORT_TEMPLATE** [CVD_BREAKDOWN_EVENT] -> **REJECT** · per-regime (n / event_PF / pf_lift_vs_random): TREND_DOWN:n1331/PF1.677/dPF-0.814, TREND_UP:n320/PF0.118/dPF-0.039, RANGE_CHOP:n490/PF0.998/dPF0.201, REVERSAL_BOUNCE:n318/PF1.183/dPF-0.372
- **TD_SELL_PRESSURE_NO_ABSORPTION_SHORT_TEMPLATE** [SELL_PRESSURE_NO_ABSORPTION_EVENT] -> **REJECT** · per-regime (n / event_PF / pf_lift_vs_random): TREND_DOWN:n7055/PF2.104/dPF-0.387, TREND_UP:n2213/PF0.152/dPF-0.005, RANGE_CHOP:n2366/PF0.924/dPF0.127, REVERSAL_BOUNCE:n1112/PF1.492/dPF-0.063
- **TD_TRUE_DISAGREEMENT_VETO** [cross_venue] -> **NEED_MORE_DATA** · per-regime (n / event_PF / pf_lift_vs_random): cross-venue/L2 not testable in OKX-only control regimes -> needs Bybit+OKX+L2 control data (see DOWNLOAD_REQUIREMENTS)
- **TD_ABSORPTION_DIVERGENCE_NO_SHORT** [absorption(L2)] -> **NEED_MORE_DATA** · per-regime (n / event_PF / pf_lift_vs_random): cross-venue/L2 not testable in OKX-only control regimes -> needs Bybit+OKX+L2 control data (see DOWNLOAD_REQUIREMENTS)
- **TD_VENUE_NOISE_IGNORE** [cross_venue] -> **NEED_MORE_DATA** · per-regime (n / event_PF / pf_lift_vs_random): cross-venue/L2 not testable in OKX-only control regimes -> needs Bybit+OKX+L2 control data (see DOWNLOAD_REQUIREMENTS)
- **TD_LEAD_LAG_MARKDOWN_SHORT_TEMPLATE** [cross_venue] -> **NEED_MORE_DATA** · per-regime (n / event_PF / pf_lift_vs_random): cross-venue/L2 not testable in OKX-only control regimes -> needs Bybit+OKX+L2 control data (see DOWNLOAD_REQUIREMENTS)

_Rule: event must beat RANDOM on PF in TREND_DOWN to avoid REJECT. hit2-lift alone is not enough (FORCED_UNWIND had +16pp hit2 but PF 1.59 < random 2.49)._
