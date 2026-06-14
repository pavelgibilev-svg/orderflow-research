# Binance live 2026-05-17..20 - MFE/MAE per zone, target sensitivity

**Build:** 2026-05-22T09:15:12+00:00

## A. Set sizes

- `baseline_triggered` = 41
- `filtered_kept` = 14
- `filter_suppressed` = 27

## B. `baseline_triggered` - per-horizon reached / hit-adverse rates

| horizon | n | median MFE % | median MAE % | reached 0.5 % | reached 1 % | reached 1.5 % | reached 2 % | hit adverse 0.5 % | hit adverse 1 % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1h | 41 | 0.1014 | 0.3902 | 7.32 | 4.88 | 0.0 | 0.0 | 31.71 | 4.88 |
| 4h | 41 | 0.2013 | 0.6265 | 24.39 | 9.76 | 2.44 | 0.0 | 56.1 | 24.39 |
| 8h | 41 | 0.3073 | 0.8082 | 39.02 | 17.07 | 2.44 | 0.0 | 68.29 | 41.46 |
| 24h | 41 | 0.6122 | 1.0888 | 60.98 | 26.83 | 9.76 | 0.0 | 73.17 | 53.66 |

## B. `filtered_kept` - per-horizon reached / hit-adverse rates

| horizon | n | median MFE % | median MAE % | reached 0.5 % | reached 1 % | reached 1.5 % | reached 2 % | hit adverse 0.5 % | hit adverse 1 % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1h | 14 | 0.1024 | 0.3185 | 7.14 | 0.0 | 0.0 | 0.0 | 28.57 | 0.0 |
| 4h | 14 | 0.3942 | 0.4759 | 35.71 | 7.14 | 7.14 | 0.0 | 50.0 | 0.0 |
| 8h | 14 | 0.5054 | 0.7141 | 57.14 | 14.29 | 7.14 | 0.0 | 71.43 | 21.43 |
| 24h | 14 | 0.7114 | 0.8669 | 78.57 | 28.57 | 14.29 | 0.0 | 85.71 | 42.86 |

## B. `filter_suppressed` - per-horizon reached / hit-adverse rates

| horizon | n | median MFE % | median MAE % | reached 0.5 % | reached 1 % | reached 1.5 % | reached 2 % | hit adverse 0.5 % | hit adverse 1 % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1h | 27 | 0.0955 | 0.4646 | 7.41 | 7.41 | 0.0 | 0.0 | 33.33 | 7.41 |
| 4h | 27 | 0.0955 | 0.7276 | 18.52 | 11.11 | 0.0 | 0.0 | 59.26 | 37.04 |
| 8h | 27 | 0.0955 | 1.0888 | 29.63 | 18.52 | 0.0 | 0.0 | 66.67 | 51.85 |
| 24h | 27 | 0.6061 | 1.1542 | 51.85 | 25.93 | 7.41 | 0.0 | 66.67 | 59.26 |
