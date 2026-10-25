"""Report-only price-basis schema. Never changes order or sizing inputs."""
import math
from datetime import datetime
from .premium_exit_mapping import premium_stop_from_greeks,premium_target_from_greeks
REVISION='handoff-horizon-levels-v2'
HORIZON_POLICY='COMPLETED_15M_DAILY_EMA20_ATR1_SELECTED_RR_IV_V1'
def positive(x):return isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x) and x>0
def horizon_levels(candidate,contract,proposal,horizon,entry,rr,now):
    frame='15m' if horizon=='intraday' else 'daily';state=(candidate.get('timeframe_states') or {}).get(frame) or {};label='completed 15-minute' if horizon=='intraday' else 'completed Daily'
    result=dict(status='UNAVAILABLE',timeframe=frame,policy=HORIZON_POLICY,basis=f'{label} EMA20 or close ± 1xATR; nearest valid adverse level to current chain spot. Target = spot ± selected R:R x its own stop distance.',source=dict(candle_at=state.get('last_updated'),data_quality=state.get('data_quality') or candidate.get('data_quality'),close=state.get('close'),ema20=state.get('ema20'),atr=state.get('atr')),underlying=dict(entry=entry if positive(entry) else None,target=None,stop_loss=None),premium=dict(entry=proposal.get('entry_points') if positive(proposal.get('entry_points')) else None,target=None,stop_loss=None),unavailable_reasons=[])
    if not positive(entry):result['reason']='Underlying chain spot is unavailable.';return result
    if result['source']['data_quality'] in ('UNAVAILABLE','STALE','INSUFFICIENT DATA'):
        result['reason']=f'{label} evidence quality is '+str(result['source']['data_quality'])+'.';return result
    close,atr,ema=state.get('close'),state.get('atr'),state.get('ema20')
    if not positive(close) or not positive(atr):result['reason']=f'{label} close and ATR evidence are required; no other horizon is substituted.';return result
    direction=candidate.get('direction');bull=direction=='BULLISH'
    if direction not in ('BULLISH','BEARISH'):result['reason']='Directional evidence is unavailable.';return result
    candidates=[('EMA20',ema),('close minus ATR' if bull else 'close plus ATR',close-atr if bull else close+atr)]
    valid=[(source,value) for source,value in candidates if positive(value) and (value<entry if bull else value>entry)]
    if not valid:result['reason']=f'{label} EMA20/ATR did not produce a valid adverse stop relative to chain spot.';return result
    chosen,stop=(max(valid,key=lambda v:v[1]) if bull else min(valid,key=lambda v:v[1]));result['underlying']['stop_loss']=stop;result['stop_component']=chosen;result['risk_distance']=abs(entry-stop);result['selected_reward_to_risk']=rr
    if positive(rr):
        target=entry+(1 if bull else -1)*rr*abs(entry-stop)
        if positive(target):result['underlying']['target']=target
        else:result['unavailable_reasons'].append('Underlying target is nonpositive under the selected R:R.')
    else:result['unavailable_reasons'].append('A positive selected reward-to-risk is required for targets.')
    common=dict(spot=entry,premium=proposal.get('entry_points'),strike=contract.get('strike'),expiry=proposal.get('expiry_iso'),option_type=contract.get('option_type'),tick=contract.get('tick_size'),greeks=contract.get('greeks') or {},now=now)
    estimates={}
    for kind,level in [('stop_loss',stop),('target',result['underlying']['target'])]:
        if level is None:continue
        try:
            if not proposal.get('expiry_iso'):raise ValueError('Exact ISO expiry evidence is missing.')
            estimate=premium_stop_from_greeks(stop=level,**common) if kind=='stop_loss' else premium_target_from_greeks(target=level,**common)
            result['premium'][kind]=estimate['stop_loss_price' if kind=='stop_loss' else 'target_price'];estimates[kind]=estimate
        except (ValueError,TypeError,KeyError,OverflowError) as error:result['unavailable_reasons'].append('Premium '+kind.replace('_',' ')+' unavailable: '+str(error))
    result['premium_estimates']=dict(model='QUOTE_ANCHORED_BLACK_SCHOLES_BROKER_IV_ZERO_RATE',levels=estimates,assumptions='Same exact contract and expiry for both horizon scenarios. Instantaneous underlying-level move at unchanged time and broker IV; zero interest/dividend assumptions. Premium levels are tick-aligned estimates, not time-to-target forecasts or guaranteed exits. Swing does not imply holding beyond this expiry.')
    result['status']='PROPOSED' if not result['unavailable_reasons'] else 'PARTIAL';result['reason']='; '.join(result['unavailable_reasons']) or None
    return result
def report_levels(card,policy,mode,now=None,broker=None,selected_lots=None,lots_supplied=False):
    a=card.get('analysis') or {};c=card.get('candidate') or {};p=a.get('proposal') or {};legs=p.get('legs') or []
    if a.get('kind')!='LONG_OPTION':return None
    contract=legs[0] if len(legs)==1 and legs[0].get('validated') is True else None
    if not contract:return dict(revision=REVISION,status='UNAVAILABLE',reason='A single validated exact option is required; rejected contracts are never selected.')
    if c.get('direction') not in ('BULLISH','BEARISH') or contract.get('option_type')!=('CE' if c['direction']=='BULLISH' else 'PE'):return dict(revision=REVISION,status='UNAVAILABLE',reason='Option side conflicts with the directional evidence; no levels selected.')
    current=a.get('active_invalidation') or {};stop=current.get('price') or p.get('underlying_invalidation') or (a.get('recommended_invalidation') or {}).get('price');entry=a.get('entry') or p.get('spot');rr=policy.get('minimum_reward_to_risk');sign=1 if c.get('direction')=='BULLISH' else -1
    target=entry+sign*rr*abs(entry-stop) if all(positive(x) for x in (entry,stop,rr)) else None
    shared=dict(mode=mode,basis='Existing shared completed Daily EMA20 / 1xATR structure; not a separately calculated intraday/swing plan',underlying=dict(entry=entry,target=target,stop_loss=stop),premium=dict(entry=p.get('entry_points'),target=p.get('target_exit_points'),stop_loss=(current.get('premium_stop_estimate') or p.get('premium_stop_estimate') or {}).get('stop_loss_price')))
    clock=now or datetime.now().astimezone()
    horizons={h:horizon_levels(c,contract,p,h,entry,rr,clock) for h in ('intraday','swing')}
    from .handoff_outcomes import outcomes
    lots=selected_lots if lots_supplied else (p.get('sizing') or {}).get('lots')
    sizing_contract=dict(contract,expiry=p.get('expiry_iso'))
    for values in horizons.values():values['outcomes']=outcomes(values,sizing_contract,lots,broker or c.get('broker') or p.get('broker'),clock,lots_source='Captured lots-per-stock input' if lots_supplied else 'Original validated proposal sizing')
    return dict(revision=REVISION,status='PROPOSED_REPORT_ONLY',policy=HORIZON_POLICY,contract=dict(symbol=contract.get('symbol'),strike=contract.get('strike'),option_type=contract.get('option_type'),expiry=p.get('expiry_iso') or p.get('expiry'),lot_size=contract.get('lot_size'),tick_size=contract.get('tick_size'),source='Selected broker exact-contract master and validated option chain'),source=dict(broker=broker or c.get('broker') or p.get('broker'),quality=c.get('data_quality'),timeframe_states=c.get('timeframe_states'),valuation_at=(now or datetime.now().astimezone()).isoformat()),shared_current_plan=shared,horizons=horizons,order_authority='NONE')
