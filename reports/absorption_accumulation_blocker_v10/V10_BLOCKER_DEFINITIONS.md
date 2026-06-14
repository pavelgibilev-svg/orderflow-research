# V10 BLOCKER VARIANTS

Build 2026-06-13T10:18:13+00:00 · absorption/accumulation blocker v10 · skeptical, not production.

Blocker is an ADDITIONAL layer: short_allowed = gate_allow AND NOT blocker_fires. Frozen gates/8A unchanged.
- BLOCKER_10A_ABSORPTION_BASIC = F1.
- BLOCKER_10B_FAILED_BREAKDOWN = F2.
- BLOCKER_10C_VWAP_RECLAIM = F3.
- BLOCKER_10D_CVD_PRICE_DIVERGENCE = F5.
- BLOCKER_10E_COMBINED_CONSERVATIVE = (F1+F2+F3+F4+F5 count) >= 2 absorption signs.
- BLOCKER_10F_COMBINED_AGGRESSIVE = any of F1..F5 OR F6 chop.

⚠️ CIRCULARITY NOTE: the v9 phase labels for ABSORPTION/ACCUMULATION were themselves defined with similar 'selling-but-no-new-low' logic, so a blocker built from absorption features will mechanically fire in those phases. The non-circular evidence is (a) markdown retention staying HIGH and (b) the ex-post forward-downside diagnostic (the gate has no absorption knowledge).
