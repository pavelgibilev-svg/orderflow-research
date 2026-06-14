# Target-Feasibility Diagnostic — 2 % target on Jan-Apr 2026

> Pure analysis. Does NOT change `config/strategy.default.json`, the detector, or the target checker. Answers a single question: on these four days, is a 2 % target reachable in the first place?

- Generated: 2026-05-09T19:08:40.322Z
- Source: `data/tardis/binance-futures/BTCUSDT/<date>/trades.csv.gz`
- Method: minute-by-minute close prices, sliding-window max upward and max downward % move within 4h / 8h / 24h windows.

## 1. Day-level metrics

| Date | Return % | Range % | First | Last | High | Low | Trades | Regime |
|---|---|---|---|---|---|---|---|---|
| 2026-01-01 | +1.36% | 1.57% | 87608.30 | 88800.00 | 88881.40 | 87508.40 | 1 056 983 | choppy |
| 2026-02-01 | -2.26% | 4.96% | 78706.70 | 76931.50 | 79396.80 | 75644.00 | 6 759 515 | bearish |
| 2026-03-01 | -1.77% | 4.89% | 66937.00 | 65750.00 | 68189.00 | 65011.00 | 5 961 363 | bearish |
| 2026-04-01 | -0.23% | 2.60% | 68241.40 | 68086.50 | 69288.00 | 67534.90 | 4 104 211 | choppy |

## 2. Max windowed moves

Maximum upward and downward price movement (in % of the window's starting price) reachable from any starting minute of the day.

| Date | Max 4h up | Max 4h down | Max 8h up | Max 8h down | Max 24h up | Max 24h down |
|---|---|---|---|---|---|---|
| 2026-01-01 | 0.76% | 0.61% | 1.19% | 0.61% | 1.55% | 0.61% |
| 2026-02-01 | 2.20% | 2.67% | 2.20% | 3.26% | 2.20% | 4.46% |
| 2026-03-01 | 3.17% | 2.92% | 3.17% | 3.28% | 3.17% | 4.54% |
| 2026-04-01 | 2.37% | 1.62% | 2.42% | 1.81% | 2.42% | 1.83% |

## 3. 2 % target feasibility

A 2 % target is "feasible" on horizon X if there exists at least one starting minute in the day from which the price moves 2 % up OR 2 % down within X hours. **If feasibility is "no", no signal — however good — can hit the 2 % target on that horizon.**

| Date | 2 % feasible 4h | 2 % feasible 8h | 2 % feasible intraday (24h) | Recommended target % | Regime |
|---|---|---|---|---|---|
| 2026-01-01 | **no** | **no** | **no** | 0.5 | choppy |
| 2026-02-01 | yes | yes | yes | 2.0 | bearish |
| 2026-03-01 | yes | yes | yes | 2.0 | bearish |
| 2026-04-01 | yes | yes | yes | 1.5 | choppy |

## 4. Which days can be used to evaluate a 2 % strategy?

- **Days where 2 % is reachable on intraday (24h) horizon:** 3 of 4 → 2026-02-01, 2026-03-01, 2026-04-01.
- **Days where 2 % is reachable on 8h horizon:** 3 of 4 → 2026-02-01, 2026-03-01, 2026-04-01.
- **Days where 2 % is reachable on 4h horizon:** 3 of 4 → 2026-02-01, 2026-03-01, 2026-04-01.
- **Days where 2 % is unreachable on any horizon (the target is structurally wrong for the day):** 1 of 4 → 2026-01-01.

## 5. Days where 2 % is the wrong target

### 2026-01-01 (choppy)

- Day return: +1.36%, range 1.57 %.
- Max 24h move from any single minute: 1.55 % up / 0.61 % down — both **below 2 %**.
- A 2 % target is structurally unreachable on this day. The strategy's 0 % hit rate on 2026-01-01 is **not evidence that the strategy is bad**; it's evidence that 2 % is the wrong target for this regime.
- A more honest target for this day would be ≈ 0.5 %.


## 6. Can 2026-01-01 be used to evaluate a 2 % strategy?

**No.** Max 24h move from any minute is 1.55 % up / 0.61 % down — both below 2 %. Every triggered zone on this day has a 100 % failure rate **by definition of the day's price walk**, regardless of how good or bad the detector is. Any "0 % hit rate on 2026-01-01" should be reported with this caveat.

## 7. Recommended target by day

The recommended target is chosen as the largest standard target (2.0 %, 1.5 %, 1.0 %, 0.5 %) that is BOTH (a) ≤ 0.6 × intraday range, and (b) ≤ max 8h move. This is a heuristic, not a tuned parameter — it just keeps the target inside what the day's price action actually delivered.

| Date | Range % | Max 8h up | Max 8h down | Recommended target % |
|---|---|---|---|---|
| 2026-01-01 | 1.57% | 1.19% | 0.61% | 0.5 |
| 2026-02-01 | 4.96% | 2.20% | 3.26% | 2.0 |
| 2026-03-01 | 4.89% | 3.17% | 3.28% | 2.0 |
| 2026-04-01 | 2.60% | 2.42% | 1.81% | 1.5 |

Days where 2 % is unreachable would yield more meaningful signal-vs-baseline numbers if evaluated against the recommended target instead. **This requires changing the `targetPct` parameter in a future run; it does not change the strategy, the detector, or the existing thresholds.**

## 8. Honest verdict

Only **3 of 4** days are suitable for evaluating a 2 % strategy on the intraday horizon. The remaining 1 day(s) (2026-01-01) physically cannot deliver a 2 % move from any starting point — the strategy's hit rate on those days is **mechanically bounded at 0 %** regardless of detector quality.

Of the suitable days, only **3** have 2 % reachable on the 4h horizon — meaning the 4h hit rate is the most discriminating; the 24h hit rate has the most permissive feasibility.

When reporting hit rates on a single day, the honest framing is:
- include "2 % feasible on this horizon: yes/no" for that day;
- treat 0 % hit rate on infeasible days as a NULL result, not a strategy failure;
- compute "wins per feasible day" alongside "wins per day" when aggregating multiple days.

> The strategy thresholds in `config/strategy.default.json` are unchanged. The detector and target checker are unchanged. This is purely a feasibility audit of the chosen 2 % target on the available 4 days.
