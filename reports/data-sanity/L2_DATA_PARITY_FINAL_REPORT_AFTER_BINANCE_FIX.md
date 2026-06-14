# B4. L2 parity after Binance fix — OKX open May vs Binance CORRECTED

**Build:** 2026-06-04T04:01:59+00:00
Sample: first 60min on ['2026-05-23', '2026-05-26', '2026-05-29'], end-of-ms-group sampling.

| metric | OKX | Binance | note |
|---|--:|--:|---|
| crossed% (med) | 0.0 | 0.0 | both clean (<1%) |
| median spread bps | 0.0133 | 0.0133 | |
| updates/sec | 1158.0 | 1340.1 | |
| top1 depth BTC | 9.0162 | 7.7748 | comparable |
| top1 depth USD | 680007.0 | 586245.0 | ratio 1.16x |
| top20 depth USD | 1708203.0 | 1445414.0 | |

**OKX_BINANCE_NORMALIZED_L2_COMPARABLE = YES**

## Flags
```
L2_PARITY_AFTER_FIX_DONE = YES
BINANCE_RECONSTRUCTION_VALID_AFTER_FIX = YES
OKX_BINANCE_NORMALIZED_L2_COMPARABLE = YES
NEXT_RESEARCH_CAN_CONTINUE = YES
```