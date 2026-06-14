# max2_total_per_day - wrong-direction selected zones audit

**Build:** 2026-05-25T09:39:55+00:00
**Wrong-direction selected count:** 2

## 2026-03-22 `WAP-SHORT-1774142237000-5` — engine SELECTED SHORT, market went UP

- confirmed at: 2026-03-22T01:32:41+00:00
- confidence: **HIGH** (evidence count 9)
- evidence: ['aggressive_buy_absorbed', 'ask_absorbed_buys', 'ask_refill_score_present', 'range_compression', 'void_score_present', '24_defense_cycles', 'zone_defended_long', 'OFI_sell_side', 'trigger_flow_strong']
- 4h forward in selected dir: max fav 0.3166%, max adv 0.9233%
- opposite-direction candidate present: {'opposite_candidate_zone_id': 'BTC-USDT-SWAP-LONG-1774139310000-1', 'opposite_confidence': 'HIGH', 'opposite_evidence_count': 7, 'opposite_filter_kept': False, 'opposite_in_top2': False}
- why engine chose this side: sufficient evidence (9); HIGH confidence
- prevention rule candidate: **opposite-direction candidate with equal/better confidence was available — direction-balance check would skip this; selected direction had max favorable 0.32% in 4h — late-context guard**
- classification: **wrong_direction_noise**

## 2026-03-29 `SWAP-LONG-1774743999000-4` — engine SELECTED LONG, market went DOWN

- confirmed at: 2026-03-29T00:46:44+00:00
- confidence: **HIGH** (evidence count 9)
- evidence: ['aggressive_sell_absorbed', 'bid_absorbed_sells', 'bid_refill_score_present', 'range_compression', 'void_score_present', '114_defense_cycles', 'zone_defended_long', 'OFI_buy_side', 'trigger_flow_strong']
- 4h forward in selected dir: max fav 1.1398%, max adv 0.0254%
- opposite-direction candidate present: {'opposite_candidate_zone_id': 'BTC-USDT-SWAP-SHORT-1774742430000-1', 'opposite_confidence': 'HIGH', 'opposite_evidence_count': 7, 'opposite_filter_kept': True, 'opposite_in_top2': False}
- why engine chose this side: sufficient evidence (9); HIGH confidence
- prevention rule candidate: **opposite-direction candidate with equal/better confidence was available — direction-balance check would skip this**
- classification: **ambiguous_local_setup**
