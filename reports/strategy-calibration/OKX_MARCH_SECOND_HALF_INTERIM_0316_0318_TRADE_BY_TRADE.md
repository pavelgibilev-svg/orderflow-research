# OKX direct March - INTERIM trade-by-trade diagnostic (2026-03-16 + 2026-03-18)

**Build:** 2026-05-24T14:26:10+00:00
**Scope:** detailed per-trade audit on 2 already-completed days; main chain still running for the other 13.
**Canonical ledger module:** `scripts/strategy-calibration/canonical_ledger.py` (= `src/research/canonicalLedger.ts`).
**Target strict 2 %. Variant A stop 1.0 %. Variant B delay 15min + stop 1.5 %. Timeout 24h.**

## 0. Funnel - how 102 zones become 6 (A) or 4 (B) trades

| stage | 2026-03-16 | 2026-03-18 | total |
|---|---:|---:|---:|
| zones | 45 | 57 | 102 |
| engine triggered | 24 | 33 | 57 |
| filtered alerts (base passive filter) | 11 | 10 | 21 |
| Variant A accepted by ledger | 3 | 3 | 6 |
| Variant A skipped open position | 8 | 7 | 15 |
| Variant B accepted by ledger | 2 | 2 | 4 |
| Variant B skipped open position | 9 | 8 | 17 |

## A. Variant A (trigger entry + stop 1.0 %) - trade list

### Variant A - 2026-03-16

| # | zone_id | dir | conf->trig min | trigger time | entry time | delay min | entry $ | target $ | stop $ | exit time | hold min | exit | pnl % | MFE | MAE | primary? | dup? | reach later (after stop) |
|--:|---|---|---:|---|---|---:|---:|---:|---:|---|---:|---|---:|---:|---:|:---:|:---:|---|
| 1 | `HORT-1773620946000-4` | SHORT | 17.416666666666668 | 2026-03-16T01:05:02+00:00 | 2026-03-16T01:05:02+00:00 | 0.0 | 72356.0 | 70908.9 | 73079.6 | 2026-03-16T03:30:44+00:00 | 145.7 | **stop** | **-1.000** | 0.197 | 1.028 | N | N | — |
| 2 | `ORT-1773638712000-12` | SHORT | 38.333333333333336 | 2026-03-16T06:07:20+00:00 | 2026-03-16T06:07:20+00:00 | 0.0 | 73811.5 | 72335.3 | 74549.6 | 2026-03-16T21:36:13+00:00 | 928.9 | **stop** | **-1.000** | 1.331 | 1.068 | N | N | — |
| 3 | `ONG-1773695990000-40` | LONG | 5.85 | 2026-03-16T21:36:14+00:00 | 2026-03-16T21:36:14+00:00 | 0.0 | 74692.3 | 76186.1 | 73945.4 | 2026-03-16T23:59:59+00:00 | 143.8 | **timeout** | **+0.201** | 0.251 | 0.650 | N | N | — |

### Variant A - 2026-03-18

| # | zone_id | dir | conf->trig min | trigger time | entry time | delay min | entry $ | target $ | stop $ | exit time | hold min | exit | pnl % | MFE | MAE | primary? | dup? | reach later (after stop) |
|--:|---|---|---:|---|---|---:|---:|---:|---:|---|---:|---|---:|---:|---:|:---:|:---:|---|
| 4 | `HORT-1773792030000-1` | SHORT | 10.833333333333334 | 2026-03-18T00:23:51+00:00 | 2026-03-18T00:23:51+00:00 | 0.0 | 73727.4 | 72252.9 | 74464.7 | 2026-03-18T03:24:37+00:00 | 180.8 | **stop** | **-1.000** | 0.328 | 1.005 | Y | N | 2026-03-18T12:33:09+00:00 |
| 5 | `ORT-1773806704000-17` | SHORT | 49.45 | 2026-03-18T05:27:07+00:00 | 2026-03-18T05:27:07+00:00 | 0.0 | 74092.2 | 72610.4 | 74833.1 | 2026-03-18T12:30:38+00:00 | 423.5 | **target_2pct** | **+2.000** | 2.002 | 0.211 | N | Y | — |
| 6 | `ORT-1773842088000-33` | SHORT | 16.483333333333334 | 2026-03-18T14:28:18+00:00 | 2026-03-18T14:28:18+00:00 | 0.0 | 71788.2 | 70352.4 | 72506.1 | 2026-03-18T23:59:59+00:00 | 571.7 | **timeout** | **+0.803** | 1.860 | 0.246 | N | N | — |

## B. Variant B (delay 15min + stop 1.5 %) - trade list

### Variant B - 2026-03-16

| # | zone_id | dir | conf->trig min | trigger time | entry time | delay min | entry $ | target $ | stop $ | exit time | hold min | exit | pnl % | MFE | MAE | primary? | dup? | reach later (after stop) |
|--:|---|---|---:|---|---|---:|---:|---:|---:|---|---:|---|---:|---:|---:|:---:|:---:|---|
| 1 | `HORT-1773620946000-4` | SHORT | 17.416666666666668 | 2026-03-16T01:05:02+00:00 | 2026-03-16T01:20:02+00:00 | 15.0 | 72421.1 | 70972.7 | 73507.4 | 2026-03-16T03:33:49+00:00 | 133.8 | **stop** | **-1.500** | 0.129 | 1.628 | N | N | — |
| 2 | `ORT-1773638712000-12` | SHORT | 38.333333333333336 | 2026-03-16T06:07:20+00:00 | 2026-03-16T06:22:20+00:00 | 15.0 | 73789.4 | 72313.6 | 74896.2 | 2026-03-16T23:59:59+00:00 | 1057.7 | **timeout** | **-1.427** | 1.302 | 1.478 | N | N | — |

### Variant B - 2026-03-18

| # | zone_id | dir | conf->trig min | trigger time | entry time | delay min | entry $ | target $ | stop $ | exit time | hold min | exit | pnl % | MFE | MAE | primary? | dup? | reach later (after stop) |
|--:|---|---|---:|---|---|---:|---:|---:|---:|---|---:|---|---:|---:|---:|:---:|:---:|---|
| 3 | `HORT-1773792030000-1` | SHORT | 10.833333333333334 | 2026-03-18T00:23:51+00:00 | 2026-03-18T00:38:51+00:00 | 15.0 | 73612.1 | 72139.9 | 74716.3 | 2026-03-18T13:01:22+00:00 | 742.5 | **target_2pct** | **+2.000** | 2.014 | 1.402 | Y | N | — |
| 4 | `ORT-1773842088000-33` | SHORT | 16.483333333333334 | 2026-03-18T14:28:18+00:00 | 2026-03-18T14:43:18+00:00 | 15.0 | 71485.8 | 70056.1 | 72558.1 | 2026-03-18T23:59:59+00:00 | 556.7 | **timeout** | **+0.384** | 1.445 | 0.670 | N | N | — |

## C. Skipped signals (open position blocked them)

### Variant A - skipped signals (had a position open at the time)

| date | skipped zone_id | dir | trigger time | blocked by | engine class | primary? | dup? | reached_raw? | would-exit if taken | would-pnl |
|---|---|---|---|---|---|:---:|:---:|:---:|---|---:|
| 2026-03-16 | `HORT-1773626785000-7` | SHORT | 2026-03-16T02:27:51+00:00 | `HORT-1773620946000-4` | failed_triggered | N | N | N | **stop** | -1.000% |
| 2026-03-16 | `ONG-1773655882000-26` | LONG | 2026-03-16T10:50:18+00:00 | `ORT-1773638712000-12` | failed_triggered | N | N | N | **timeout** | +1.874% |
| 2026-03-16 | `ONG-1773656977000-27` | LONG | 2026-03-16T10:50:18+00:00 | `ORT-1773638712000-12` | failed_triggered | N | N | N | **timeout** | +1.874% |
| 2026-03-16 | `ONG-1773660808000-30` | LONG | 2026-03-16T12:04:25+00:00 | `ORT-1773638712000-12` | failed_triggered | N | N | N | **stop** | -1.000% |
| 2026-03-16 | `ORT-1773660536000-29` | SHORT | 2026-03-16T12:11:18+00:00 | `ORT-1773638712000-12` | failed_triggered | N | N | N | **stop** | -1.000% |
| 2026-03-16 | `ONG-1773665169000-32` | LONG | 2026-03-16T13:31:39+00:00 | `ORT-1773638712000-12` | failed_triggered | N | N | N | **stop** | -1.000% |
| 2026-03-16 | `ONG-1773684454000-38` | LONG | 2026-03-16T19:10:10+00:00 | `ORT-1773638712000-12` | failed_triggered | N | N | N | **timeout** | +0.684% |
| 2026-03-16 | `ORT-1773700604000-44` | SHORT | 2026-03-16T23:02:18+00:00 | `ONG-1773695990000-40` | failed_triggered | N | N | N | **timeout** | -0.353% |
| 2026-03-18 | `LONG-1773793270000-3` | LONG | 2026-03-18T01:29:00+00:00 | `HORT-1773792030000-1` | failed_triggered | N | N | N | **stop** | -1.000% |
| 2026-03-18 | `ORT-1773814999000-20` | SHORT | 2026-03-18T07:31:27+00:00 | `ORT-1773806704000-17` | duplicate_reached_move | N | Y | Y | **target_2pct** | +2.000% |
| 2026-03-18 | `ORT-1773834431000-26` | SHORT | 2026-03-18T12:11:29+00:00 | `ORT-1773806704000-17` | duplicate_reached_move | N | Y | Y | **target_2pct** | +2.000% |
| 2026-03-18 | `ONG-1773848497000-43` | LONG | 2026-03-18T15:57:27+00:00 | `ORT-1773842088000-33` | failed_triggered | N | N | N | **stop** | -1.000% |
| 2026-03-18 | `ORT-1773849364000-44` | SHORT | 2026-03-18T16:06:02+00:00 | `ORT-1773842088000-33` | failed_triggered | N | N | N | **timeout** | +0.139% |
| 2026-03-18 | `ONG-1773854692000-45` | LONG | 2026-03-18T17:38:47+00:00 | `ORT-1773842088000-33` | failed_triggered | N | N | N | **stop** | -1.000% |
| 2026-03-18 | `ORT-1773857396000-47` | SHORT | 2026-03-18T18:54:48+00:00 | `ORT-1773842088000-33` | failed_triggered | N | N | N | **timeout** | -0.188% |

### Variant B - skipped signals (had a position open at the time)

| date | skipped zone_id | dir | trigger time | blocked by | engine class | primary? | dup? | reached_raw? | would-exit if taken | would-pnl |
|---|---|---|---|---|---|:---:|:---:|:---:|---|---:|
| 2026-03-16 | `HORT-1773626785000-7` | SHORT | 2026-03-16T02:27:51+00:00 | `HORT-1773620946000-4` | failed_triggered | N | N | N | **stop** | -1.500% |
| 2026-03-16 | `ONG-1773655882000-26` | LONG | 2026-03-16T10:50:18+00:00 | `ORT-1773638712000-12` | failed_triggered | N | N | N | **timeout** | +1.583% |
| 2026-03-16 | `ONG-1773656977000-27` | LONG | 2026-03-16T10:50:18+00:00 | `ORT-1773638712000-12` | failed_triggered | N | N | N | **timeout** | +1.583% |
| 2026-03-16 | `ONG-1773660808000-30` | LONG | 2026-03-16T12:04:25+00:00 | `ORT-1773638712000-12` | failed_triggered | N | N | N | **timeout** | +1.617% |
| 2026-03-16 | `ORT-1773660536000-29` | SHORT | 2026-03-16T12:11:18+00:00 | `ORT-1773638712000-12` | failed_triggered | N | N | N | **stop** | -1.500% |
| 2026-03-16 | `ONG-1773665169000-32` | LONG | 2026-03-16T13:31:39+00:00 | `ORT-1773638712000-12` | failed_triggered | N | N | N | **stop** | -1.500% |
| 2026-03-16 | `ONG-1773684454000-38` | LONG | 2026-03-16T19:10:10+00:00 | `ORT-1773638712000-12` | failed_triggered | N | N | N | **timeout** | +1.053% |
| 2026-03-16 | `ONG-1773695990000-40` | LONG | 2026-03-16T21:36:14+00:00 | `ORT-1773638712000-12` | failed_triggered | N | N | N | **timeout** | +0.460% |
| 2026-03-16 | `ORT-1773700604000-44` | SHORT | 2026-03-16T23:02:18+00:00 | `ORT-1773638712000-12` | failed_triggered | N | N | N | **timeout** | -0.582% |
| 2026-03-18 | `LONG-1773793270000-3` | LONG | 2026-03-18T01:29:00+00:00 | `HORT-1773792030000-1` | failed_triggered | N | N | N | **stop** | -1.500% |
| 2026-03-18 | `ORT-1773806704000-17` | SHORT | 2026-03-18T05:27:07+00:00 | `HORT-1773792030000-1` | duplicate_reached_move | N | Y | Y | **target_2pct** | +2.000% |
| 2026-03-18 | `ORT-1773814999000-20` | SHORT | 2026-03-18T07:31:27+00:00 | `HORT-1773792030000-1` | duplicate_reached_move | N | Y | Y | **target_2pct** | +2.000% |
| 2026-03-18 | `ORT-1773834431000-26` | SHORT | 2026-03-18T12:11:29+00:00 | `HORT-1773792030000-1` | duplicate_reached_move | N | Y | Y | **target_2pct** | +2.000% |
| 2026-03-18 | `ONG-1773848497000-43` | LONG | 2026-03-18T15:57:27+00:00 | `ORT-1773842088000-33` | failed_triggered | N | N | N | **timeout** | +0.013% |
| 2026-03-18 | `ORT-1773849364000-44` | SHORT | 2026-03-18T16:06:02+00:00 | `ORT-1773842088000-33` | failed_triggered | N | N | N | **timeout** | -0.028% |
| 2026-03-18 | `ONG-1773854692000-45` | LONG | 2026-03-18T17:38:47+00:00 | `ORT-1773842088000-33` | failed_triggered | N | N | N | **timeout** | -0.438% |
| 2026-03-18 | `ORT-1773857396000-47` | SHORT | 2026-03-18T18:54:48+00:00 | `ORT-1773842088000-33` | failed_triggered | N | N | N | **timeout** | +0.215% |

## D. Primary unique move lineage (2 primaries across these 2 days)

| date | uniqueMoveId | primary zone_id | dir | trigger time | in filtered alerts? | filter notes | Variant A | Variant B |
|---|---:|---|---|---|:---:|---|---|---|
| 2026-03-16 | 1 | `SWAP-LONG-1773620182000-2` | LONG | 2026-03-16T03:30:42+00:00 | NO | slow_trigger | filter_suppressed | filter_suppressed |
| 2026-03-18 | 1 | `WAP-SHORT-1773792030000-1` | SHORT | 2026-03-18T00:23:51+00:00 | YES | — | taken; exit=stop pnl=-1.0% | taken; exit=target_2pct pnl=2.0% |

## E. Per-day human explanation

**2026-03-16** (Variant A):
  - 24 triggered zones -> 11 pass base filter -> ledger takes **3** (skips 8 due to open position).
  - LOSSES: `1773620946000-4` SHORT @ 72356.0 -> stop in 145.7 min; `773638712000-12` SHORT @ 73811.5 -> stop in 928.9 min
  - TIMEOUTS: `773695990000-40` LONG (MFE 0.251% / MAE 0.650%)
  - **Day P&L (Variant A, pre-cost): -1.7992%**

**2026-03-16** (Variant B):
  - 24 triggered zones -> 11 pass base filter -> ledger takes **2** (skips 9 due to open position).
  - LOSSES: `1773620946000-4` SHORT @ 72421.1 -> stop in 133.8 min
  - TIMEOUTS: `773638712000-12` SHORT (MFE 1.302% / MAE 1.478%)
  - **Day P&L (Variant B, pre-cost): -2.9269%**

**2026-03-18** (Variant A):
  - 33 triggered zones -> 10 pass base filter -> ledger takes **3** (skips 7 due to open position).
  - WINS: `773806704000-17` SHORT @ 74092.2 -> target_2pct in 423.5 min
  - LOSSES: `1773792030000-1` SHORT @ 73727.4 -> stop in 180.8 min (would target_2pct after stop at 2026-03-18T12:33:09+00:00)
  - TIMEOUTS: `773842088000-33` SHORT (MFE 1.860% / MAE 0.246%)
  - SKIPPED but would have WON: **2** (this is where edge gets eaten by the one-trade-at-a-time rule).
  - **Day P&L (Variant A, pre-cost): 1.8032%**

**2026-03-18** (Variant B):
  - 33 triggered zones -> 10 pass base filter -> ledger takes **2** (skips 8 due to open position).
  - WINS: `1773792030000-1` SHORT @ 73612.1 -> target_2pct in 742.5 min
  - TIMEOUTS: `773842088000-33` SHORT (MFE 1.445% / MAE 0.670%)
  - SKIPPED but would have WON: **3** (this is where edge gets eaten by the one-trade-at-a-time rule).
  - **Day P&L (Variant B, pre-cost): 2.3836%**


## F. Final flag matrix

```
TRADE_BY_TRADE_INTERIM_DONE = YES
DAYS_EXPLAINED = ['2026-03-16', '2026-03-18']
VARIANT_A_TRADES_TOTAL = 6
VARIANT_A_WINS = 1
VARIANT_A_LOSSES = 3
VARIANT_A_TIMEOUTS = 2
VARIANT_B_TRADES_TOTAL = 4
VARIANT_B_WINS = 1
VARIANT_B_LOSSES = 1
VARIANT_B_TIMEOUTS = 2
FILTERED_ALERTS_TOTAL = 21
LEDGER_ACCEPTED_TOTAL = A=6, B=4
LEDGER_SKIPPED_OPEN_POSITION_TOTAL = A=15, B=17
PRIMARY_UNIQUE_TOTAL = 2
PRIMARY_UNIQUE_TAKEN_VARIANT_A = 1
PRIMARY_UNIQUE_TAKEN_VARIANT_B = 1
PRIMARY_UNIQUE_SKIPPED_OR_STOPPED_EXPLAINED = YES
ANY_UNEXPLAINED_TRADE_COUNT_MISMATCH = NO
```

## Notes
- All flags pre-cost. Strict 2 % target.
- 2 days, very thin sample; not a final verdict.
- No engine / threshold / detector change.