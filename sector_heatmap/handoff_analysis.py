"""Read-only Handoff analysis engine, reusable without starting dashboard runners.

The owned provider supplies all market data, positions, orders and option chains.
Analysis and sizing never call an execution method.
"""
from datetime import datetime
import secrets
from .handoff import (validate_risk_policy, build_equity_opportunity,
    apply_invalidation_choice, evidence_conviction)
def join_unique_reasons(items):
    reasons = [str(item.get('reason') or '').strip() for item in items]
    return '; '.join(dict.fromkeys((reason for reason in reasons if reason)))

def instrument_route(payload):
    """Return the one explicitly selected, non-mixed handoff instrument route."""
    route = str((payload or {}).get('instrument_route') or '').strip().lower()
    if route not in {'cash_equity', 'stock_options'}:
        raise ValueError('Choose Cash equity or Stock options before collecting matches.')
    return route

def opportunities(payload, provider, analysis_runs):
    """Analyze fresh full-alignment candidates without creating order authority."""
    recipient = str(payload.get('recipient') or '').lower()
    if recipient not in {'chatgpt', 'codex'}:
        raise ValueError('Choose ChatGPT or Codex before collecting AI analysis.')
    policy = validate_risk_policy(payload.get('risk_policy'))
    route = instrument_route(payload)
    mode = payload.get('mode') if payload.get('mode') in {'intraday', 'swing'} else 'intraday'
    collection = provider.candidates(mode)
    if provider.broker=='FYERS':
        from .handoff_screener import merge
        collection=merge(collection,getattr(provider,'sectors',None),getattr(provider,'folder',None),auto=payload.get('handoff_schedule_mode')=='AUTO',master=getattr(provider,'cash_master',None))
    candidates = [candidate for candidate in collection.get('candidates', []) if candidate.get('kind') == 'stock']
    cards, exclusions = ([], [])
    exclusions.extend((collection.get("scope") or {}).get("screener",{}).get("exclusions",[]))
    exclusions.extend(dict(kind='SCREENER_SOURCE',name=x.get('label'),reason=x.get('reason')) for x in (collection.get('scope') or {}).get('screener',{}).get('source_failures',[]))
    broker = provider.broker
    token = 'provider:owned'
    positions_response = {'netPositions': provider.positions()}
    client = None
    from .exposure_guard import exclude_exposure
    orders = provider.orders()
    candidates, duplicate_candidates = exclude_exposure(candidates, positions_response.get('netPositions') or (positions_response.get('data') or {}).get('netPositions') or [], orders)
    exclusions.extend(({'candidate_key': candidate['key'], 'name': candidate.get('name'), 'kind': 'OPEN_POSITION', 'reason': 'An open selected-broker position or pending order already exists for this underlying; duplicate exposure is excluded.'} for candidate in duplicate_candidates))
    level_plans = {}
    for candidate in candidates:
        from .persistent_jobs import checkpoint
        checkpoint('Building Handoff evidence for ' + str(candidate.get('symbol') or candidate.get('name')) + '.')
        plan = build_equity_opportunity(candidate, policy)
        level_plans[candidate['key']] = plan
        recommended = plan.get('recommended_invalidation') or {}
        if isinstance(recommended.get('price'), (int, float)) and recommended['price'] > 0:
            candidate['derived_invalidation'] = {'status': 'READY', 'method': recommended.get('method', 'structure'), 'price': recommended['price'], 'basis': 'Exact price from completed-candle structure', 'rationale': recommended.get('rationale')}
        else:
            candidate['derived_invalidation'] = {'status': 'UNAVAILABLE', 'reason': plan.get('reason') or 'Completed-candle structure did not produce a valid directional invalidation.'}
        if route == 'cash_equity':
            if plan.get('status') == 'REQUIRES_INVALIDATION':
                try:
                    proposed = apply_invalidation_choice(candidate, plan, policy, {'method': 'structure'})
                    plan['proposed_sizing'] = proposed
                    plan['target'] = proposed['target']
                    plan['quantity'] = proposed['quantity']
                    plan['estimated_max_loss'] = proposed['estimated_max_loss']
                    plan['estimated_notional'] = proposed['estimated_notional']
                except ValueError as error:
                    plan['proposal_warning'] = str(error)
                plan['conviction'] = evidence_conviction(candidate, plan)
                cards.append({'candidate_key': candidate['key'], 'candidate': candidate, 'analysis': plan})
            else:
                exclusions.append({'candidate_key': candidate['key'], 'name': candidate.get('name'), 'kind': 'EQUITY', 'reason': plan.get('reason')})
    if route == 'stock_options':
        if not token or ':' not in token:
            exclusions.append({'kind': 'OPTIONS', 'reason': 'FYERS authentication is required for fresh option analysis.'})
        else:
            option_candidates = list(candidates)
            from .handoff_priority import priority_key
            option_candidates.sort(key=lambda item:priority_key(dict(candidate=item,conviction=evidence_conviction(item,level_plans.get(item['key'],{})))))
            option_scan_limit = 12
            for omitted in option_candidates[option_scan_limit:]:
                exclusions.append({'candidate_key': omitted['key'], 'name': omitted.get('name'), 'kind': 'OPTIONS', 'reason': 'Option refresh deferred by the bounded selected-broker request budget; no contract was inferred.'})
            for candidate in option_candidates[:option_scan_limit]:
                plan = level_plans.get(candidate['key'], {})
                invalidation = (plan.get('recommended_invalidation') or {}).get('price')
                if not isinstance(invalidation, (int, float)) or invalidation <= 0:
                    exclusions.append({'candidate_key': candidate['key'], 'name': candidate.get('name'), 'kind': 'OPTIONS', 'reason': 'Completed-candle structure did not produce a valid underlying invalidation; option construction was blocked.'})
                    continue
                risk = {'planning_capital': policy['planning_capital'], 'max_loss_value': policy['idea_risk_limit'], 'max_loss_unit': 'rupees', 'invalidation': invalidation, 'stop_basis': 'price', 'max_simultaneous_positions': policy['max_simultaneous_positions'], 'minimum_reward_to_risk': policy['minimum_reward_to_risk'], 'enforce_risk_controls': policy['enforce_risk_controls'], 'enforce_minimum_reward_to_risk': policy['enforce_minimum_reward_to_risk']}
                try:
                    options = provider.options(candidate['symbol'], candidate['direction'], risk)
                    ready = []
                    for proposal in options.get('proposals') or []:
                        sizing = proposal.get('sizing') or {}
                        if sizing.get('status') not in {'SIZED', 'USER_SIZED'} or not sizing.get('lots'):
                            exclusions.append({'candidate_key': candidate['key'], 'name': candidate.get('name'), 'kind': 'OPTIONS', 'reason': 'A validated long option exists but the configured risk/capital does not support one lot.'})
                            continue
                        minimum_rr = policy.get('minimum_reward_to_risk')
                        target_profit_per_lot = proposal['max_loss_per_lot'] * minimum_rr if minimum_rr is not None else None
                        target_points = (proposal['entry_points'] + target_profit_per_lot / proposal['lot_size'] if proposal['structure'] in {'DEBIT', 'LONG_OPTION'} else max(0, proposal['entry_points'] - target_profit_per_lot / proposal['lot_size'])) if target_profit_per_lot is not None else None
                        ready.append({**proposal, 'underlying': candidate['symbol'], 'expiry': options.get('expiry'), 'expiry_iso': options.get('expiry_iso'), 'spot': options.get('spot'), 'target_exit_points': round(target_points, 2) if target_points is not None else None, 'underlying_invalidation': invalidation, 'exit_conditions': [f'Exit if the underlying reaches invalidation ₹{invalidation:.2f}.' if invalidation else 'No valid underlying invalidation; do not trade.', f'Target option premium {target_points:.2f} points from your selected 1:{minimum_rr:g} reward:risk preference.' if target_points is not None else 'No reward:risk target was imposed; choose an exit objective when you prepare the ticket.', 'Exit/stand aside if any leg quote, liquidity, Greeks/OI/volume, expiry, or completed-candle alignment becomes stale or invalid.'], 'liquidity_evidence': {'rules': options.get('liquidity_rules'), 'legs': [{'symbol': leg.get('symbol'), 'bid': leg.get('bid'), 'ask': leg.get('ask'), 'spread_pct': leg.get('spread_pct'), 'open_interest': leg.get('open_interest'), 'volume': leg.get('volume'), 'greeks': leg.get('greeks'), 'lot_size': leg.get('lot_size'), 'tick_size': leg.get('tick_size')} for leg in proposal.get('legs', [])]}, 'decision_support_only': True})
                    if ready:
                        proposal = max(ready, key=lambda item: (item.get('reward_to_risk') or 0, -(item.get('max_loss_per_lot') or float('inf'))))
                        option_analysis = {'status': 'REQUIRES_INVALIDATION_ACCEPTANCE', 'kind': 'LONG_OPTION', 'direction': candidate['direction'], 'entry': options.get('spot'), 'invalidation_choices': plan.get('invalidation_choices'), 'recommended_invalidation': plan.get('recommended_invalidation'), 'active_invalidation': None, 'thesis': plan.get('thesis'), 'entry_trigger': plan.get('entry_trigger'), 'entry_condition': plan.get('entry_condition'), 'proposal': proposal}
                        option_analysis['conviction'] = evidence_conviction(candidate, option_analysis, proposal)
                        cards.append({'candidate_key': candidate['key'], 'candidate': candidate, 'analysis': option_analysis})
                    if not ready:
                        reason = join_unique_reasons(options.get('rejected_proposals') or [])
                        exclusions.append({'candidate_key': candidate['key'], 'name': candidate.get('name'), 'kind': 'OPTIONS', 'reason': reason or options.get('reason') or 'No exact long-option entry passed the configured gates.', 'rejected_contracts': options.get('rejected_contracts') or [], 'liquidity_rules': options.get('liquidity_rules')})
                except Exception as error:
                    exclusions.append({'candidate_key': candidate['key'], 'name': candidate.get('name'), 'kind': 'OPTIONS', 'reason': str(error)})
    from .persistent_jobs import checkpoint
    from .exposure_guard import exclude_handoff_cards
    checkpoint('Rechecking selected-broker exposure before saving Handoff cards.')
    final_positions, final_orders = (provider.positions(), provider.orders())
    candidates, cards, newly_exposed = exclude_handoff_cards(candidates, cards, final_positions, final_orders)
    exclusions.extend(({'candidate_key': candidate['key'], 'name': candidate.get('name'), 'kind': 'OPEN_POSITION', 'reason': 'An open position or pending order appeared during analysis; this underlying is excluded.'} for candidate in newly_exposed))
    analysis_id = secrets.token_urlsafe(12)
    from .handoff_levels import report_levels
    for report_card in cards:
        levels=report_levels(report_card,policy,mode,broker=broker,selected_lots=payload.get('report_lots'),lots_supplied='report_lots' in payload)
        if levels is not None:report_card['analysis']['report_levels']=levels
    from .handoff_priority import priority_key
    cards.sort(key=priority_key)
    candidate_order={c['candidate_key']:i for i,c in enumerate(cards)}
    candidates.sort(key=lambda c:candidate_order.get(c['key'],10**9))
    for index, card in enumerate(cards):
        card['card_id'] = f'card-{index + 1}'
    result = {'schema': 'sector-pulse-auto-analysis/v1', 'generated_at': datetime.now().astimezone().isoformat(), 'analysis_id': analysis_id, 'status': 'READY', 'decision_support_only': True, 'order_authority': 'NONE', 'analysis_recipient': recipient, 'instrument_route': route, 'ai_review': {'status': 'UNAVAILABLE', 'recipient': recipient, 'transmitted': False, 'message': f'{recipient.title()} is not connected to this local dashboard. The cards below are transparent rule-engine proposals, not {recipient.title()} output.', 'recommendation_source': 'LOCAL_EVIDENCE_RULE_ENGINE'}, 'risk_policy': policy, 'source': {'broker': broker, 'mode': mode, 'analysis_updated_at': collection.get('updated_at'), 'market_session': collection.get('market_session')}, 'scope': {**(collection.get('scope') or {}), 'option_scan_limit': 12}, 'candidates': candidates, 'cards': cards, 'exclusions': exclusions}
    analysis_runs[analysis_id] = {'created_at': datetime.now().timestamp(), 'cards': {card['card_id']: card for card in cards}, 'policy': policy, 'provider': provider, 'account_id': provider.execution.account['id']}
    for old_id, run in list(analysis_runs.items()):
        if datetime.now().timestamp() - run['created_at'] > 900:
            analysis_runs.pop(old_id, None)
    return result

def size(payload, analysis_runs):
    """Accept/edit one proposed stop and recompute dependent values from a fresh FYERS quote."""
    run = analysis_runs.get(str(payload.get('analysis_id') or ''))
    if not run:
        raise ValueError('This analysis expired. Collect fresh matches again.')
    card = run['cards'].get(str(payload.get('card_id') or ''))
    if not card:
        raise ValueError('The selected analysis card is no longer available.')
    candidate, opportunity = (card['candidate'], card['analysis'])
    policy = validate_risk_policy(payload.get('risk_policy'))
    provider = run.get('provider')
    fresh_price, received = provider.quote(candidate['symbol'])
    quote_values = {'tt': received}
    refreshed = {**opportunity, 'entry': float(fresh_price), 'current_price': float(fresh_price)}
    if opportunity.get('kind') in {'OPTION_SPREAD', 'LONG_OPTION'}:
        option_proposal = opportunity.get('proposal')
        tick_size = 0.05
    else:
        master = {'tick_size': provider.tick(candidate['symbol'])}
        if not master:
            raise RuntimeError("The exact equity contract is absent from today's FYERS cash-market master.")
        tick_size = master['tick_size']
        option_proposal = None
    sizing = apply_invalidation_choice(candidate, refreshed, policy, payload.get('selection'), tick_size=tick_size, option_proposal=option_proposal)
    return {'analysis_id': payload.get('analysis_id'), 'card_id': payload.get('card_id'), 'status': 'ACCEPTED_AND_SIZED', 'fresh_quote': {'symbol': candidate['symbol'], 'price': fresh_price, 'provider_timestamp': quote_values.get('tt')}, 'active_invalidation': sizing, 'ticket_confirmation_invalidated': True, 'message': 'Stop selection accepted and recomputed from fresh selected-broker evidence. Any earlier ticket preview or confirmation is invalid.'}
