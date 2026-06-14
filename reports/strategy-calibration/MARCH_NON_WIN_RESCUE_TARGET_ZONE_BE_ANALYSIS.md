# Non-win rescue analysis (target-zone + BE)

**Build:** 2026-05-29T17:37:33+00:00
**Enhanced model non-wins:** 11
**Would be SKIPPED by target-zone filter (no >=2% room):** 9
**Losses where MFE>=1% (BE C1 would cut to ~breakeven):** 1

| date | dir | outcome | reason | pnl% | MFE% | MAE% | room% | has_tgt>=2% | B_skips | BE_C1_saves |
|---|:---:|:---:|---|---:|---:|---:|---:|:---:|:---:|:---:|
| 2026-03-06 | LONG | LOSS | stop_no_2pct_either_dir | -1.64 | 0.3053 | 1.5755 | 0.1227 | Y | N | N |
| 2026-03-07 | LONG | LOSS | stop_no_2pct_either_dir | -1.64 | 0.2766 | 1.6037 | 0.0793 | N | Y | N |
| 2026-03-11 | SHORT | LOSS | stop_no_2pct_either_dir | -1.64 | 1.4376 | 1.5282 | 0.0688 | N | Y | Y |
| 2026-03-12 | SHORT | TIMEOUT | timeout_negative | -0.6895 | 1.3731 | 0.9418 | 6.0 | Y | N | Y |
| 2026-03-16 | SHORT | LOSS | correct_direction_but_no_2pct | -1.64 | 0.5466 | 1.5274 | 0.1031 | N | Y | N |
| 2026-03-20 | LONG | LOSS | correct_direction_but_no_2pct | -1.64 | 0.6772 | 1.5009 | 0.0934 | N | Y | N |
| 2026-03-21 | LONG | LOSS | stop_no_2pct_either_dir | -1.64 | 0.5286 | 1.5737 | 0.1175 | N | Y | N |
| 2026-03-25 | LONG | TIMEOUT | timeout_negative | -1.1207 | 1.0992 | 1.0718 | 0.1527 | N | Y | Y |
| 2026-03-26 | LONG | LOSS | stop_no_2pct_either_dir | -1.64 | 0.2088 | 1.5054 | 0.1152 | N | Y | N |
| 2026-03-27 | LONG | LOSS | stop_no_2pct_either_dir | -1.64 | 0.1123 | 1.8038 | 0.0921 | N | Y | N |
| 2026-03-28 | LONG | TIMEOUT | timeout_negative | 0.2273 | 1.3281 | 0.4855 | 0.0504 | N | Y | Y |