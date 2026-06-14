# NEXT RESEARCH BRANCH

Build 2026-06-12T17:12:23+00:00 · research closure · skeptical, not production.

1. **Keep the strict short-permission gate (GATE_6E / GATE_6A) as a research object** — it cleanly captures regime exposure (blocks 71-85% of uptrend shorts; random+gate PF >> random_all).
2. **Validate the gate on MORE regime windows** — the binding limit is ONE local TREND_UP window. Get >=2-3 more UP/RANGE/BOUNCE windows (Bybit+OKX, L2+trades) before promoting from PASS_CLOSED_NEED_MORE_DATA.
3. **Replace the entry.** Inside the bearish gate, test a DIFFERENT entry mechanism (the event detector is rejected). Even scheduled/random-in-gate is the baseline to beat.
4. **Or pivot** to a different strategy idea — the orderflow short-entry thesis on this dataset is not supported.
5. Do NOT tune thresholds or invent gates on this dataset further (overfit risk; in-sample exhausted).
