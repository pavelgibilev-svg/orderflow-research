# Local normalization audit (proxy: local price range by zone class)

**Build:** 2026-05-24T15:16:56+00:00

## Median local 60-min price range by zone class

| class | median 60m range % |
|---|---:|
| failed_triggered | 0.8282 |
| primary_unique_reached_move | 0.6673 |
| duplicate_reached_move | 0.9143 |

`LOCAL_NORMALIZATION_NEEDED` = **NO**

If primary-unique zones tend to fire in materially different local volatility than failed_triggered,
then absolute thresholds may be biased and local normalization could help.