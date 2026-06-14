# Microstructure casebook (Option B)

**Build:** 2026-05-28T19:34:10+00:00
**Baseline:** 29 trades, wr 58.62%, exp +0.5268, PF 1.922
**Best enhanced:** `ENH::baseline+dl2_supp_minus_opp_net_flow_15m_le_4497.76::top1` — 29 trades, wr 62.07%, exp +0.6475, PF 2.258

## Baseline LOSSES that enhanced REMOVES
| date | dir | zone_id | reason | pnl % |
|---|:---:|---|---|---:|
| 2026-03-07 | LONG | 1772877219000-19 | stop_no_2pct_either_dir | -1.64 |
| 2026-03-21 | LONG | -1774051508000-1 | stop_no_2pct_either_dir | -1.64 |
| 2026-03-22 | LONG | -1774139310000-1 | correct_direction_but_no_2pct | -1.64 |
| 2026-03-24 | LONG | 1774337368000-16 | wrong_direction | -1.64 |
| 2026-03-26 | LONG | -1774483234000-1 | stop_no_2pct_either_dir | -1.64 |

Removed 5 loss-likes.

## Baseline WINS that enhanced INCORRECTLY removes
| date | dir | zone_id |
|---|:---:|---|
| 2026-03-13 | LONG | 1773396407000-11 |
| 2026-03-27 | SHORT | -1774577539000-8 |

Removed 2 WINs.

## Baseline WINS that enhanced KEEPS
| date | dir | zone_id |
|---|:---:|---|
| 2026-03-02 | LONG | -1772409634000-1 |
| 2026-03-03 | SHORT | -1772496525000-2 |
| 2026-03-04 | LONG | 1772606412000-18 |
| 2026-03-05 | SHORT | -1772670314000-2 |
| 2026-03-08 | SHORT | 1772966351000-24 |
| 2026-03-09 | LONG | 1773066205000-36 |
| 2026-03-10 | SHORT | 1773132250000-30 |
| 2026-03-14 | LONG | 1773484455000-16 |
| 2026-03-15 | LONG | 1773607034000-26 |
| 2026-03-18 | SHORT | -1773792030000-1 |
| 2026-03-19 | SHORT | -1773879450000-2 |
| 2026-03-23 | LONG | -1774228797000-8 |
| 2026-03-29 | SHORT | -1774752923000-8 |
| 2026-03-30 | LONG | -1774829268000-2 |
| 2026-03-31 | LONG | -1774915354000-1 |