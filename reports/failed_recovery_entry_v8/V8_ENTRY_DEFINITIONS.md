# V8 ENTRY DEFINITIONS (causal, inside frozen gate)

Build 2026-06-13T03:13:21+00:00 · research branch v8 · skeptical, not production.

- **8A FAILED_VWAP_RECLAIM**: below VWAP180, touched/exceeded VWAP in last 5m, then closes back below VWAP.
- **8B FAILED_LOCAL_HIGH**: a swing high formed in [t-15,t-3]; price now below it and turning down.
- **8C WEAK_BUY_RECOVERY**: buy flow up last 10m (net taker / CVD) but price barely reclaimed (<0.1%) and now stalls.
- **8D PULLBACK_TO_RESISTANCE**: price pulls into resistance (max of VWAP, recent breakdown high) then rejects (closes below).
All require the FROZEN gate (6A or 6E) active at the entry minute. Causal; no future data.
