# March in-sample calibration — objectives

**Build:** 2026-05-26T11:31:21+00:00
**Scope:** IN-SAMPLE March 2026 OKX direct calibration (29 days; 03-17 missing)

## Hard rules
- no engine / threshold / detector change
- target STRICT 2% (1% / 1.5% are diagnostic only)
- no future-leak in decision features
- outcome / post-trigger fields used as labels only
- no production integration

## Mode 1 — TG watch-zone objective

Successful when:
- selector picked it BEFORE or at the very start of a real 2% market move
- direction matches
- after alert/confirm/selected time a 2% move was reached in that direction
- not late after >50% of move completed

Metrics: selected alerts total, alerts/day, successful selected zones, precision, recall of market 2% moves, wrong-direction rate, missed market moves, avg lead time, median lead time.

## Mode 2 — paper trade objective

- entries: ['confirmed', 'trigger', 'delay_5m', 'delay_10m', 'delay_15m']
- stops: [1.0, 1.25, 1.5, 'zone_boundary']
- target: 2.0 %
- timeout: 24 h
- cost: 0.14 % roundtrip

Metrics: trades, wins, losses, timeouts, winrate %, expectancy pre-cost %, expectancy after cost %, PF pre-cost, PF after cost, total return %, max consecutive losses, LONG/SHORT separately

## Headline target
- ideal winrate: 70-80 %
- alerts/day: around 1-2
- minimum signals: 20 / month
- selecting 3-5 trades for the entire month even at >=80% winrate