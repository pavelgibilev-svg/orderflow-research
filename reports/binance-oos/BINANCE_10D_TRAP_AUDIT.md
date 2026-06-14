# B. Binance 10d — FAKE accumulation / distribution trap audit

**Build:** 2026-06-02T14:02:11+00:00
Classification from CAUSAL evidence (engine ofi/refill/absorption, taker imbalance, reclaim, structure, 1d regime). post_* = diagnostic only.

**Counts:** {'REAL_DISTRIBUTION': 1, 'FAKE_DISTRIBUTION_PULLBACK_NOISE': 3, 'FAKE_ACCUMULATION_BOUNCE_NOISE': 6}

| date | dir | label | pnl | eng_ofi | supp_taker15 | inband_sell% | reclaim | hi_low | regime1d | against | classification |
|---|:--:|:--:|--:|--:|--:|--:|:--:|:--:|:--:|:--:|:--|
| 2026-05-21 | SHORT | MID | 0.371 | -0.5332207126569236 | -0.1237 | 0.4501 | 1 | None | RANGE | 0 | REAL_DISTRIBUTION |
| 2026-05-22 | SHORT | GOOD | 1.86 | 0.5339892290334477 | -0.1741 | 0.5475 | 0 | 0 | RANGE | 0 | FAKE_DISTRIBUTION_PULLBACK_NOISE |
| 2026-05-23 | LONG | NOISE | -1.64 | -0.9793417233974 | -0.043 | None | 0 | 0 | BEAR | 1 | FAKE_ACCUMULATION_BOUNCE_NOISE |
| 2026-05-24 | SHORT | NOISE | -0.76 | 0.9942797230830904 | 0.1443 | None | 0 | 1 | BULL | 1 | FAKE_DISTRIBUTION_PULLBACK_NOISE |
| 2026-05-25 | SHORT | MID | 0.6451 | 0.4908616669232077 | -0.2697 | 0.541 | 0 | 1 | RANGE | 0 | FAKE_DISTRIBUTION_PULLBACK_NOISE |
| 2026-05-26 | LONG | NOISE | -1.64 | -0.4342596484179097 | -0.2975 | 0.6032 | 0 | 1 | RANGE | 0 | FAKE_ACCUMULATION_BOUNCE_NOISE |
| 2026-05-27 | LONG | NOISE | -1.64 | -0.9927162549765535 | -0.3033 | None | 0 | 0 | BEAR | 1 | FAKE_ACCUMULATION_BOUNCE_NOISE |
| 2026-05-28 | LONG | NOISE | -1.64 | -0.04115448570197201 | 0.05 | 0.4606 | 0 | 0 | BEAR | 1 | FAKE_ACCUMULATION_BOUNCE_NOISE |
| 2026-05-29 | LONG | NOISE | -1.64 | -0.9976031229355058 | -0.087 | None | 0 | 0 | BEAR | 1 | FAKE_ACCUMULATION_BOUNCE_NOISE |
| 2026-05-30 | LONG | MID | 0.2627 | -0.9966290971954136 | -0.0026 | None | 0 | 1 | RANGE | 0 | FAKE_ACCUMULATION_BOUNCE_NOISE |

### Evidence per trade
- **2026-05-21 SHORT** [REAL_DISTRIBUTION] (MID): ofi -0.53<0; supp_taker_imb -0.12<0; rejected mid
- **2026-05-22 SHORT** [FAKE_DISTRIBUTION_PULLBACK_NOISE] (GOOD): ofi 0.53>0 (buy flow under sell zone); supp_taker_imb -0.17<0; no rejection
- **2026-05-23 LONG** [FAKE_ACCUMULATION_BOUNCE_NOISE] (NOISE): ofi -0.98<0 (sell flow under buy zone); supp_taker_imb -0.04<0; no reclaim; lower-low pre; 1d regime BEAR vs LONG
- **2026-05-24 SHORT** [FAKE_DISTRIBUTION_PULLBACK_NOISE] (NOISE): ofi 0.99>0 (buy flow under sell zone); no rejection; 1d regime BULL vs SHORT
- **2026-05-25 SHORT** [FAKE_DISTRIBUTION_PULLBACK_NOISE] (MID): ofi 0.49>0 (buy flow under sell zone); supp_taker_imb -0.27<0; no rejection
- **2026-05-26 LONG** [FAKE_ACCUMULATION_BOUNCE_NOISE] (NOISE): ofi -0.43<0 (sell flow under buy zone); supp_taker_imb -0.30<0; no reclaim; higher-low; refill 0.51
- **2026-05-27 LONG** [FAKE_ACCUMULATION_BOUNCE_NOISE] (NOISE): ofi -0.99<0 (sell flow under buy zone); supp_taker_imb -0.30<0; no reclaim; lower-low pre; 1d regime BEAR vs LONG; refill 0.50
- **2026-05-28 LONG** [FAKE_ACCUMULATION_BOUNCE_NOISE] (NOISE): no reclaim; lower-low pre; 1d regime BEAR vs LONG; refill 0.51
- **2026-05-29 LONG** [FAKE_ACCUMULATION_BOUNCE_NOISE] (NOISE): ofi -1.00<0 (sell flow under buy zone); supp_taker_imb -0.09<0; no reclaim; lower-low pre; 1d regime BEAR vs LONG; refill 0.51
- **2026-05-30 LONG** [FAKE_ACCUMULATION_BOUNCE_NOISE] (MID): ofi -1.00<0 (sell flow under buy zone); supp_taker_imb -0.00<0; no reclaim; higher-low