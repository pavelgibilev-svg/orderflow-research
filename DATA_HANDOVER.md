# Data handover

This repository contains TypeScript runtime modules, Python research scripts, and local OKX May 2026 report artifacts.

## Code included in Git

- package.json
- package-lock.json
- tsconfig.json
- config/strategy.default.json
- .env.example
- src/data/*
- src/reports/*
- scripts/**

## Local reports and caches

The large report artifacts are stored locally under reports/ and are ignored by Git.

Expected local handover folder:

- reports/okx-may-early/

Expected cache:

- reports/okx-may-early/FEATURE_CACHE.json

Expected daily zones:

- reports/okx-may*/BTC-USDT-SWAP_/zones.json

Expected OKX May 03-20 reports:

- OKX_2026_05_03_20_FULL_STATISTICS_APPENDIX.*
- UNIQUE_MOVE_CLUSTER_AUDIT.*
- STRONG_ZONE_TAXONOMY.*
- LIVE_SELECTOR_FAILURE_AUDIT.*
- MODULE_COVERAGE_MAP.*
- CANDIDATE_MODULE_PROTOTYPE_RESULTS.*
- TIER_A_SELECTOR_RESULTS.*
- TIER_A_BEST_RULE_TRADES.csv
- SUCCESSFUL_UNIQUE_MOVE_DATASET.*
- SUCCESSFUL_UNIQUE_MOVE_MINING.*
- POSITIVE_FEATURE_MINING.*
- SUCCESSFUL_RULE_MINING_RESULTS.*
- TIER_A_SUCCESSFUL_SELECTOR_RESULTS.*
- TIER_A_ANTI_OVERFIT_CHECK.*
- PER_DATE_PATTERN_CASEBOOK.*

Optional local reports if present:

- OKX_2026_05_03_20_ALL_ZONES.csv
- OKX_EARLY_MAY_STRONG_ZONES_CASEBOOK.csv
- OKX_EARLY_MAY_REJECTED_ZONES_ANALYSIS.csv
- OKX_EARLY_MAY_WOULD_ALERT_TRADES.csv

## Environment

Python scripts should not depend on a local hardcoded path. Use ORDERFLOW_ROOT or auto-root detection.

## Verification commands

npm install
npx tsc --noEmit
npm test
pip install -r requirements.txt
python -m compileall scripts -q
