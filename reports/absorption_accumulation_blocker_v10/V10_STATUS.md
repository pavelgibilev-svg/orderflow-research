# V10 STATUS

Build 2026-06-13 · absorption/accumulation blocker v10 · skeptical, not production.

- STATUS (auto): BLOCKER_PROMISING (b10F) → **CORRECTED (manual): BLOCKER_NEED_MORE_DATA (headline b10E on GATE_6A)** — see V10_BLOCKER_DECISION.md.
- Why corrected: b10F only hits absorption<20% by gutting markdown (retention 40.9%) and distribution (47.4%) — "blocks almost everything". The ex-post test also failed.
- **ACCUMULATION: partial success** — b10E cuts false-perm 28.9% -> 13.7% while keeping markdown 71.0% / distribution 80.9% (real separation).
- **ABSORPTION: NOT solved** — b10E only 40.6% -> 33.8% (goal <20%); only b10F reaches <20% but destroys markdown.
- **Ex-post absorption ordering: FALSE** — blocker-fire minutes do NOT fall less; in absorption they fell more (−0.94% vs −0.84%). Reduction is mechanical/circular, not forward-validated.
- Interpretable single features (F1/F3/F5) barely fire; work is carried by F2 (failed-breakdown, halves markdown) + F6 (chop).
- one-window dominance 0.21 (not a single-window artifact).
- Causal blocker (no future features); future used ONLY in ex-post diagnostic.
- in-sample, single-venue OKX, 1 uptrend window, partly-circular phase labels. PRODUCTION: NO.
- Next: better forward-validated absorption feature + OOS — NOT td_l calibration yet.
