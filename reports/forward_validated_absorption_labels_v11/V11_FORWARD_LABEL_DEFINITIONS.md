# V11 FORWARD LABEL DEFINITIONS (ex-post research labels — NOT live features)

Build 2026-06-13T10:39:27+00:00 · forward-validated absorption labels v11 · skeptical, not production.

Candidate = sell-pressure moment (cvd_30<0 AND (below VWAP OR sell_frac_30>=0.55 OR breakdown of 60m low)).
Primary horizon = 60m; also computed at 15/30/120m. cur=mid[t]; down=min future ret; up=max; ret=close ret; prog=-down.
- ACTIVE_MARKDOWN: prog>=0.6% AND ret<=-0.2% AND (new 60m low OR prog>=0.9%) — downside realized and held.
- SELL_PRESSURE_ABSORBED: ret>=0.2% with prog<0.9% (selling failed, net up) OR prog<0.4% with ret>-0.2% (couldn't push down).
- NO_CONTROL: |ret|<0.2% AND prog<0.6% AND up<0.6% (oscillation).
- UNKNOWN: ambiguous / insufficient future bars.
Thresholds are interpretable research defaults relative to TP2%/SL1.5%; not tuned to evidence scores.
