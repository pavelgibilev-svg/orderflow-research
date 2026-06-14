# TD-SHORT DAILY RUNNER — FINAL REPORT

**Build:** 2026-06-05T08:24:50+00:00
SHADOW/RESEARCH ONLY · rules FROZEN · Telegram DISABLED · production DISABLED · append-only OOS log · leak-free decisions

## OOS status: **OOS_FAIL**  (accepted 24 / need >=20)

## How to run daily
```
python scripts/shadow/td_short_daily_runner.py            # ingest new day(s) -> decisions
python scripts/shadow/td_short_daily_runner.py --update-outcomes   # after 24h -> outcomes
python scripts/shadow/td_short_daily_runner.py --dashboard  # refresh dashboard
```

## OOS logs
- decisions: `C:\Users\gibilev\orderflow-research\reports\shadow\oos\TD_SHORT_OOS_DECISIONS.jsonl`
- outcomes: `C:\Users\gibilev\orderflow-research\reports\shadow\oos\TD_SHORT_OOS_OUTCOMES.jsonl`
- dashboard: `C:\Users\gibilev\orderflow-research\reports\shadow\oos\TD_SHORT_OOS_DASHBOARD.md`

## Flags
```
TD_SHORT_DAILY_RUNNER_IMPLEMENTED = YES
TD_SHORT_RULES_FROZEN = YES
HYBRID_MAIN_MODEL = YES
M4_THIN_ONLY_BOOSTER_LOGGED = YES
DECISION_LOG_FUTURE_LEAK_FREE = YES
OUTCOME_UPDATER_SEPARATE = YES
DUPLICATE_ZONE_IDS = NO
TELEGRAM_DISABLED = YES
PRODUCTION_DISABLED = YES
APPEND_ONLY_OOS_LOG = YES
OOS_STATUS = OOS_FAIL
OOS_ACCEPTED_TRADES = 24
OOS_WINRATE = 50.0
OOS_PF = 1.993
NEW_OKX_BINANCE_OVERLAP_WINDOW_REQUIRED = YES
READY_FOR_LIVE_SHADOW_LOGGING = YES
READY_FOR_TELEGRAM_SHADOW_MODE = NO
READY_FOR_PRODUCTION_TRADING = NO
MORE_OOS_REQUIRED = YES
TARDIS_USED = NO
```

## Parallel requirement
Keep collecting a NEW OKX+Binance overlapping downtrend window (Binance v3 recorder + OKX open). Mandatory for a real OOS verdict; not a blocker for the runner.