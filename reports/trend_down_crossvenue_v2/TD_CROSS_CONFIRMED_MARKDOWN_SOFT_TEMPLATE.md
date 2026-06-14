# TD_CROSS_CONFIRMED_MARKDOWN_SOFT_TEMPLATE (research, soft)

Build 2026-06-12T13:42:04+00:00 · NOT production, NOT a hard 80% filter.

- **template_id**: TD_CROSS_CONFIRMED_MARKDOWN_SOFT_TEMPLATE
- **status_hint**: see SOFT_TEMPLATE_STATS
- **level_1_background**: TREND_DOWN (window net<=-1% and prior move down)
- **required_capital_state**: SHORT markdown-type (ACTIVE_MARKDOWN / FORCED_UNWIND / DISTRIBUTION_INTO_BOUNCE)
- **required_cross_venue_behavior**: Bybit AND OKX agree on direction (SHORT) AND capital_state within <=30 min
- **required_direction_consistency**: zone direction == SHORT; never apply a short-state to a LONG zone
- **required_evidence_blocks**: {'initiative_control': '>=1 (CVD60<0 & taker_imb_30<0)', 'effort_vs_result': '>0 (down driven by net selling)', 'background_alignment': '>=1 (prior 60m/180m down)'}
- **soft_confirmations**: ['ask-heavy or balanced depth (not bid-heavy)', 'non-trivial 30m volume / activity present', 'room to recent low (not already at the low)']
- **veto_conditions**: ['cross-venue DISAGREEMENT -> no trade', 'NO_CONTROL_CHOP -> no trade', 'ABSORPTION_AFTER_SELL_PRESSURE / bid-heavy depth -> no short (reversal-watch)', 'signal on one venue only -> quarantine']
- **when_not_to_short**: ['price already at recent low (no room to TP2)', 'bid refill / CVD turning up', 'venues disagree', 'spread blown / chaotic book']
- **manual_casebook_checks**: ['was the bounce genuinely sold into on BOTH venues?', 'did sellers keep initiative after the bounce (CVD continuing down)?', 'is there room to 2% before the prior low?']
- **still_uncertain**: ['only ~3 independent moments', 'all are DISTRIBUTION_INTO_BOUNCE (no true ACTIVE_MARKDOWN/FORCED_UNWIND samples)', 'lower-high pivot trigger may be the wrong trigger for markdown continuation', 'post-entry CVD/refill not yet measured']
- **logic**: IF TREND_DOWN AND Bybit/OKX agree SHORT+state AND initiative_control>=1 AND effort_vs_result>0 AND no absorption-against-short AND not late -> SHORT_CANDIDATE_RESEARCH; ELSE veto per above.
