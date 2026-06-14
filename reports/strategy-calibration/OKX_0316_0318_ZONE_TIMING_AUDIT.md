# Candidate → Confirmed → Trigger timing audit

**Build:** 2026-05-24T15:16:51+00:00

## Slow-zone summary

- zones with confirm_to_trigger > 60 m: **9** (LONG=6, SHORT=3)
  - of which were eventually reached_raw: **5**
- zones with candidate_to_confirm > 60 m: **0**

## Per-zone (first 40, sorted by class)

| date | zone | dir | class | cand→conf min | conf→trig min | total pre-trig | trig→target min | trig→stop min | filter kept |
|---|---|---|---|---:|---:|---:|---:|---:|:---:|
| 2026-03-16 | `LONG-1773620204000-3` | LONG | duplicate_reached_move | 20.716666666666665 | 173.25 | 193.96666666666667 | 84.32 | None | N |
| 2026-03-16 | `LONG-1773623888000-6` | LONG | duplicate_reached_move | 38.88333333333333 | 93.68333333333334 | 132.56666666666666 | 84.32 | None | N |
| 2026-03-18 | `ORT-1773802038000-13` | SHORT | duplicate_reached_move | 17.733333333333334 | 170.7 | 188.43333333333334 | 396.9 | None | N |
| 2026-03-18 | `ORT-1773804588000-14` | SHORT | duplicate_reached_move | 5.316666666666666 | 474.55 | 479.8666666666667 | 92.1 | None | N |
| 2026-03-18 | `ORT-1773806704000-17` | SHORT | duplicate_reached_move | 32.6 | 49.45 | 82.05 | 423.52 | None | Y |
| 2026-03-18 | `ORT-1773808660000-19` | SHORT | duplicate_reached_move | 3.2 | 48.38333333333333 | 51.583333333333336 | 421.57 | None | N |
| 2026-03-18 | `ORT-1773814999000-20` | SHORT | duplicate_reached_move | 8.183333333333334 | 59.95 | 68.13333333333334 | 301.7 | None | Y |
| 2026-03-18 | `ORT-1773834370000-25` | SHORT | duplicate_reached_move | 3.0 | 43.083333333333336 | 46.083333333333336 | 148.47 | None | N |
| 2026-03-18 | `ORT-1773834431000-26` | SHORT | duplicate_reached_move | 5.366666666666666 | 18.933333333333334 | 24.3 | 166.62 | None | Y |
| 2026-03-18 | `ORT-1773835688000-27` | SHORT | duplicate_reached_move | 8.033333333333333 | 14.55 | 22.583333333333332 | 148.98 | None | N |
| 2026-03-18 | `ORT-1773836170000-28` | SHORT | duplicate_reached_move | 11.3 | 3.3833333333333333 | 14.683333333333334 | 148.85 | None | N |
| 2026-03-18 | `ORT-1773837656000-30` | SHORT | duplicate_reached_move | 4.5 | 16.683333333333334 | 21.183333333333334 | 426.38 | None | N |
| 2026-03-18 | `ORT-1773837926000-31` | SHORT | duplicate_reached_move | 3.0 | 12.95 | 15.95 | 424.52 | None | N |
| 2026-03-16 | `ONG-1773650421000-22` | LONG | failed_triggered | 6.15 | 129.73333333333332 | 135.88333333333333 | None | None | N |
| 2026-03-16 | `ONG-1773650790000-23` | LONG | failed_triggered | 15.566666666666666 | 273.3833333333333 | 288.95 | None | None | N |
| 2026-03-16 | `ONG-1773655882000-26` | LONG | failed_triggered | 4.85 | 34.083333333333336 | 38.93333333333333 | None | None | Y |
| 2026-03-16 | `ONG-1773656977000-27` | LONG | failed_triggered | 10.483333333333333 | 10.2 | 20.683333333333334 | None | None | Y |
| 2026-03-16 | `ONG-1773659225000-28` | LONG | failed_triggered | 3.6333333333333333 | 76.6 | 80.23333333333333 | None | None | N |
| 2026-03-16 | `ONG-1773660808000-30` | LONG | failed_triggered | 11.533333333333333 | 19.416666666666668 | 30.95 | None | None | Y |
| 2026-03-16 | `ONG-1773664875000-31` | LONG | failed_triggered | 3.35 | 47.55 | 50.9 | None | None | N |
| 2026-03-16 | `ONG-1773665169000-32` | LONG | failed_triggered | 3.933333333333333 | 41.56666666666667 | 45.5 | None | None | Y |
| 2026-03-16 | `ONG-1773666805000-33` | LONG | failed_triggered | 3.0 | 15.783333333333333 | 18.783333333333335 | None | None | N |
| 2026-03-16 | `ONG-1773684454000-38` | LONG | failed_triggered | 16.916666666666668 | 45.68333333333333 | 62.6 | None | None | Y |
| 2026-03-16 | `ONG-1773685469000-39` | LONG | failed_triggered | 37.71666666666667 | 8.0 | 45.71666666666667 | None | None | N |
| 2026-03-16 | `ONG-1773695990000-40` | LONG | failed_triggered | 10.55 | 5.85 | 16.4 | None | None | Y |
| 2026-03-16 | `HORT-1773620946000-4` | SHORT | failed_triggered | 18.516666666666666 | 17.416666666666668 | 35.93333333333333 | None | None | Y |
| 2026-03-16 | `HORT-1773626785000-7` | SHORT | failed_triggered | 3.0 | 18.433333333333334 | 21.433333333333334 | None | None | Y |
| 2026-03-16 | `ORT-1773638712000-12` | SHORT | failed_triggered | 3.8 | 38.333333333333336 | 42.13333333333333 | None | None | Y |
| 2026-03-16 | `ORT-1773639024000-13` | SHORT | failed_triggered | 3.1333333333333333 | 38.85 | 41.983333333333334 | None | None | N |
| 2026-03-16 | `ORT-1773640454000-15` | SHORT | failed_triggered | 7.2 | 11.1 | 18.3 | None | None | N |
| 2026-03-16 | `ORT-1773640886000-16` | SHORT | failed_triggered | 19.266666666666666 | 80.46666666666667 | 99.73333333333333 | None | None | N |
| 2026-03-16 | `ORT-1773647103000-18` | SHORT | failed_triggered | 14.416666666666666 | 32.0 | 46.416666666666664 | None | None | N |
| 2026-03-16 | `ORT-1773660536000-29` | SHORT | failed_triggered | 9.55 | 32.81666666666667 | 42.36666666666667 | None | None | Y |
| 2026-03-16 | `ORT-1773700604000-44` | SHORT | failed_triggered | 4.066666666666666 | 21.5 | 25.566666666666666 | None | None | Y |
| 2026-03-18 | `LONG-1773793270000-3` | LONG | failed_triggered | 8.066666666666666 | 59.766666666666666 | 67.83333333333333 | None | None | Y |
| 2026-03-18 | `LONG-1773793754000-4` | LONG | failed_triggered | 4.866666666666666 | 59.85 | 64.71666666666667 | None | None | N |
| 2026-03-18 | `LONG-1773794558000-5` | LONG | failed_triggered | 16.85 | 31.9 | 48.75 | None | None | N |
| 2026-03-18 | `LONG-1773796201000-7` | LONG | failed_triggered | 3.2666666666666666 | 17.216666666666665 | 20.483333333333334 | None | None | N |
| 2026-03-18 | `LONG-1773798977000-9` | LONG | failed_triggered | 3.75 | 16.433333333333334 | 20.183333333333334 | None | None | N |
| 2026-03-18 | `ONG-1773799629000-10` | LONG | failed_triggered | 7.85 | 19.25 | 27.1 | None | None | N |