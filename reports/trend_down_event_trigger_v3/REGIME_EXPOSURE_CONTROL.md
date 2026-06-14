# REGIME EXPOSURE CONTROL (the honest test)

Build 2026-06-12T14:32:51+00:00 · research/calibration.

**Question:** do event-shorts beat just shorting at a random minute in these (strong down) windows?

- naive 'short every 10th minute' baseline: n=3992 hit2 39.5% PF 2.268 exp 0.411%
- event-short (all 1944, overlapping): hit2 41.0% PF 1.991
- **lift of events over naive baseline: 1.5 pp hit2**
- independent moments (dedup all short events to 60-min buckets/window): **255** (not 1944)
  -> independent-moment hit2 40.4% PF 2.204

| window | naive hit2% | naive PF |
|---|--:|--:|
| W1_NOVEMBER | 37.5 | 2.181 |
| W3_JANUARY | 31.5 | 2.77 |
| W4_APRIL | 46.1 | 2.138 |

**Interpretation:** if event hit2 ≈ naive baseline, the high PF is REGIME EXPOSURE (the market fell 8-12%), NOT a transferable filter.
All 3 windows are strong downtrends; even TRUE_DISAGREEMENT 'wins' here — that is the tell that categories are not separating.
A real edge must be tested on NEUTRAL / UP / chop windows as a control, and on OOS down windows.
