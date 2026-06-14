# Filter failure audit (base passive filter)

**Build:** 2026-05-24T15:16:52+00:00
**Filter:** fast_trigger<=60m AND duplicate_60m_price_band<=1%

## Correct zones suppressed by filter: **11**

| date | zone | dir | class | primary? | filter reason | ctm min |
|---|---|---|---|:---:|---|---:|
| 2026-03-16 | `LONG-1773620182000-2` | LONG | primary_unique_reached_move | Y | slow_trigger (ctm=173.25) | 173.25 |
| 2026-03-16 | `LONG-1773620204000-3` | LONG | duplicate_reached_move | N | slow_trigger (ctm=173.25) | 173.25 |
| 2026-03-16 | `LONG-1773623888000-6` | LONG | duplicate_reached_move | N | slow_trigger (ctm=93.68333333333334) | 93.68333333333334 |
| 2026-03-18 | `ORT-1773808660000-19` | SHORT | duplicate_reached_move | N | duplicate_60m_price_band | 48.38333333333333 |
| 2026-03-18 | `ORT-1773802038000-13` | SHORT | duplicate_reached_move | N | duplicate_60m_price_band; slow_trigger (ctm=170.7) | 170.7 |
| 2026-03-18 | `ORT-1773804588000-14` | SHORT | duplicate_reached_move | N | slow_trigger (ctm=474.55) | 474.55 |
| 2026-03-18 | `ORT-1773835688000-27` | SHORT | duplicate_reached_move | N | duplicate_60m_price_band | 14.55 |
| 2026-03-18 | `ORT-1773836170000-28` | SHORT | duplicate_reached_move | N | duplicate_60m_price_band | 3.3833333333333333 |
| 2026-03-18 | `ORT-1773834370000-25` | SHORT | duplicate_reached_move | N | duplicate_60m_price_band | 43.083333333333336 |
| 2026-03-18 | `ORT-1773837926000-31` | SHORT | duplicate_reached_move | N | duplicate_60m_price_band | 12.95 |
| 2026-03-18 | `ORT-1773837656000-30` | SHORT | duplicate_reached_move | N | duplicate_60m_price_band | 16.683333333333334 |

## Deep dive: 03-16 LONG primary
- zone_id: BTC-USDT-SWAP-LONG-1773620182000-2
- direction: LONG
- candidate_iso: 2026-03-16T00:16:22+00:00
- confirmed_iso: 2026-03-16T00:37:27+00:00
- trigger_iso: 2026-03-16T03:30:42+00:00
- candidate_to_confirm_min: 21.083333333333332
- confirm_to_trigger_min: 173.25
- total_pre_trigger_min: 194.33333333333334
- filter_kept: False
- filter_reason: slow_trigger
- actual_2pct_up_move_on_day_start_iso: 2026-03-16T03:34:00+00:00
- actual_2pct_up_move_size_pct: 3.0964
- candidate_was_before_move_start: True
- trigger_was_before_move_start: True
- would_tg_alert_be_useful: YES (candidate before move start)