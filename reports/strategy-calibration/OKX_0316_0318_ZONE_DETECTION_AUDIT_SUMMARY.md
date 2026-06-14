# Zone detection audit - master summary (2026-03-16 + 2026-03-18)

**Build:** 2026-05-24T15:16:56+00:00
**Movement-first audit: market 2 % moves vs engine zones. Read-only. No engine change.**

## Human answers

**1. Правда ли zones детектятся поздно?**  
   Из 4 market 2 % moves: **early=1**, **late+mid=2**, **missed=0**. 
   Late problem flag: **YES**.

**2. Где задержка: candidate, confirmation или trigger?**  
   - candidate late problem: **NO**  
   - confirmation too slow: **NO**  
   - trigger too slow: **YES**  

**3. Правда ли filter убивает правильные зоны?**  
   Correct zones suppressed by filter: **11** — flag `FILTER_SUPPRESSED_CORRECT_ZONES = YES`.

**4. Почему 03-16 primary LONG был suppressed?**
   - candidate at: `2026-03-16T00:16:22+00:00`
   - confirmed at: `2026-03-16T00:37:27+00:00`
   - trigger at: `2026-03-16T03:30:42+00:00`
   - candidate_to_confirm_min: 21.083333333333332
   - confirm_to_trigger_min: **173.25** (>60m -> slow_trigger flag)
   - candidate was before move start: True
   - trigger was before move start: True
   - would TG alert at candidate be useful? YES (candidate before move start)

**5. Был ли 03-18 SHORT primary найден вовремя или late?**  
   See section B per-move row; classified by move-completion-at-trigger.

**6. Были ли wrong-direction сигналы?**  Yes — **2** triggers had no 2 % move in their direction within next 4h. flag `YES`.

**7. Почему всего 2 primary unique moves?**  Market had 4 2 % moves; engine labeled 2 as primary. Unmatched market moves: 3. flag `UNIQUE_MOVE_LABELING_PROBLEM = YES`.

**8. Есть ли проблема с unique-move labeling?**  `YES`.

**9. Нужна ли локальная нормализация признаков?**  `NO` (proxy via 60-m range by class).

**10. Что является главным больным местом?**  `MAIN_ROOT_CAUSE = mixed`.

**11. Какие 2-3 решения выглядят самыми перспективными?**  
   1. Earlier TG watch-zone mode  
   2. Local-normalized features (percentile/z-score)  
   3. Movement-coverage metric in CI  

**12. Что НЕ надо менять прямо сейчас?**  
   - `zoneDetector` / thresholds / production engine — NO changes.  
   - filter parameters in production — no changes; only research-layer rules.  
   - target/stop/timeout — diagnostic only.

## Final flag matrix

```
ZONE_DETECTION_AUDIT_DONE = YES
DAYS_AUDITED = ['2026-03-16', '2026-03-18']
MARKET_2PCT_MOVES_FOUND = 4
ENGINE_PRIMARY_UNIQUE_MOVES = 2
MARKET_MOVES_MISSED_BY_ENGINE = 3
MARKET_MOVES_COVERED_EARLY = 1
MARKET_MOVES_COVERED_LATE = 2
ZONE_DETECTION_LATE_PROBLEM = YES
CANDIDATE_LATE_PROBLEM = NO
CONFIRMATION_TOO_SLOW = NO
TRIGGER_TOO_SLOW = YES
FILTER_SUPPRESSED_CORRECT_ZONES = YES
SLOW_TRIGGER_FILTER_TOO_AGGRESSIVE = YES
WRONG_DIRECTION_PROBLEM = YES
LOCAL_NORMALIZATION_NEEDED = NO
UNIQUE_MOVE_LABELING_PROBLEM = YES
MAIN_ROOT_CAUSE = mixed
TOP_FIX_CANDIDATE_1 = Earlier TG watch-zone mode
TOP_FIX_CANDIDATE_2 = Local-normalized features (percentile/z-score)
TOP_FIX_CANDIDATE_3 = Movement-coverage metric in CI
READY_TO_CHANGE_ENGINE = NO
READY_TO_BUILD_TG_WATCH_ZONE_MODE = YES
MORE_VALIDATION_REQUIRED = YES
```

## Hard rules honored
- strategy / thresholds / `zoneDetector`: UNCHANGED
- NO new backtest spawned; pure post-hoc
- post-trigger labels used only as evaluation, not as features
- target STRICT 2 %
- READY_TO_CHANGE_ENGINE = NO