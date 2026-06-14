# Binance next-test readiness plan

**Build:** 2026-05-30T07:31:47+00:00

## Frozen OKX rule set (do NOT retune on Binance)
- Selector: dist_to_recent_swing_high_pct<=0.4616 AND dl2_supp_minus_opp_net_flow_15m<=4497.76, top1/day, entry=confirmed
- Trade: TP fixed 2%, SL 1.5%, no BE, timeout 24h, cost 0.14% RT
- OKX result: 29 trades, 62.07% winrate, exp +0.6475%, PF 2.258, +18.78% return

## Required Binance inputs
- zone dataset from engine replay on Binance Futures BTCUSDT (confirmed zones + candidate/confirmed/trigger ts)
- dist_to_recent_swing_high_pct (from trades 1s buckets — available)
- dl2_supp_minus_opp_net_flow_15m (from incremental L2 — available via Binance book recorder)
- explainable_score components (microprice aligned, sweep_reclaim, opp_dir_zones, prior_move, local_range — all from L2+trades)

## Buildable from Binance recorder
- L2 book
- trades
- derivative_ticker (OI+funding native on Binance)
- liquidations (Binance has them)

## Caveats
- Binance OI is NATIVE per-instrument and higher granularity than OKX rubik daily — recompute OI features fresh, do NOT port OKX daily-OI thresholds
- funding interval differs (Binance 8h too, but values differ) — recompute, no threshold port
- fuel did not help on OKX (see results) so it is OPTIONAL on Binance

## Evaluation protocol
- Freeze the OKX selector/trade thresholds EXACTLY (no retune).
- Replay engine on Binance days (already have 2026-05-18..20 + 2025 set).
- Apply identical selector + fixed 2%/1.5% trade model.
- Report winrate/expectancy/PF; compare to OKX 62.07% as OOS cross-venue check.
- Only AFTER clean OOS pass, consider adding native Binance OI/liquidation fuel.