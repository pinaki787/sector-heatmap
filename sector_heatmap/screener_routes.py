"""Three execution choices for verified screener underlyings; advisory only."""
from .persistent_jobs import checkpoint
import csv
import io
import math
import time
from .handoff import build_defined_risk_spreads, build_long_option_proposals, evidence_conviction


def join_unique_reasons(items):
    reasons=[]
    for item in items:
        values=item.get('reasons') or [item.get('reason')] if isinstance(item,dict) else [item]
        reasons.extend(str(value) for value in values if value)
    return '; '.join(dict.fromkeys(reasons))


def option_underlyings(content, now=None):
    now=time.time() if now is None else now
    result=set()
    for row in csv.reader(io.StringIO(content)):
        if len(row)<18 or row[16] not in {'CE','PE'}:
            continue
        try:
            if float(row[8])<=now or int(float(row[3]))<=0:continue
        except (ValueError,TypeError):continue
        result.add(row[13].strip().upper())
    return result


def analyze(candidates, client, master, fetch_chain, risk):
    plans=[];excluded=[];classifications=[]
    try:
        eligible=option_underlyings(master._content())
    except Exception:
        eligible=None  # Unknown eligibility must not be labeled equity-only.
    for item in candidates:
        checkpoint("Checking stock-option evidence.")
        ticker=str(item.get('symbol') or '').strip().upper()
        if not ticker or any(c not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789&-' for c in ticker):
            excluded.append(dict(symbol=ticker,reason='Invalid stock ticker.'));continue
        underlying=f'NSE:{ticker}-EQ'
        available=None if eligible is None else ticker in eligible
        classification=dict(symbol=ticker,classification='Stock Options' if available else 'Equity' if available is False else 'Eligibility unavailable',options_available=available,routes={})
        classifications.append(classification)
        if available is not True:
            reason='No active listed option contracts in the current broker master.' if available is False else 'Current option master could not be verified.'
            for route in ['LONG_OPTION','OPTION_SPREAD']:classification['routes'][route]=dict(eligible=False,reason=reason)
            continue
        direction=item.get('direction');stop=item.get('stop')
        if direction not in {'BULLISH','BEARISH'} or isinstance(stop,bool) or not isinstance(stop,(float,int)) or not math.isfinite(stop) or stop<=0:
            excluded.append(dict(symbol=ticker,reason='Valid direction and structural invalidation are required.'));continue
        try:
            chain,expiry=fetch_chain(client,underlying)
            symbols=[r.get('symbol') for r in chain.get('data',{}).get('optionsChain',[]) if r.get('symbol')]
            records=master.lookup(symbols)
            candidate=dict(direction=direction,data_quality='READY',timeframe_states=item.get('timeframe_states') or {})
            for route,builder in [('LONG_OPTION',build_long_option_proposals),('OPTION_SPREAD',build_defined_risk_spreads)]:
                try:
                    options=builder(chain,expiry,records,direction,{**risk,'invalidation':stop})
                    ready=[]
                    for proposal in options.get('proposals') or []:
                        if route=='OPTION_SPREAD' and proposal.get('structure')!='DEBIT':
                            continue  # Existing execution supports protection-first debit spreads.
                        grade=evidence_conviction(candidate,item,proposal)
                        sizing=proposal.get('sizing') or {}
                        if sizing.get('status') in {'SIZED','USER_SIZED'} and sizing.get('lots') and grade.get('rating')=='High':ready.append((proposal,grade))
                    if not ready:
                        reason=join_unique_reasons(options.get('rejected_proposals') or []) or options.get('reason') or 'Contract, liquidity, risk or conviction checks did not pass.'
                        classification['routes'][route]=dict(eligible=False,reason=reason);excluded.append(dict(symbol=ticker,route=route,reason=reason));continue
                    proposal,grade=max(ready,key=lambda pair:(pair[1].get('score',0),pair[0].get('reward_to_risk') or 0,-(pair[0].get('max_loss_per_lot') or float('inf'))))
                    classification['routes'][route]=dict(eligible=True)
                    plans.append(dict(symbol=ticker,underlying=underlying,direction=direction,route=route,classification='Stock Options',alignment=item.get('alignment'),timeframe_states=item.get('timeframe_states') or {},expiry=options.get('expiry'),expiry_iso=options.get('expiry_iso'),spot=options.get('spot'),proposal={**proposal,'kind':route},conviction=grade,decision_support_only=True))
                except Exception:
                    reason='Option proposal could not be validated; refresh broker evidence.'
                    classification['routes'][route]=dict(eligible=False,reason=reason);excluded.append(dict(symbol=ticker,route=route,reason=reason))
        except Exception:
            reason='Fresh option chain or exact contract metadata is unavailable.'
            for route in ['LONG_OPTION','OPTION_SPREAD']:classification['routes'][route]=dict(eligible=False,reason=reason)
            excluded.append(dict(symbol=ticker,reason=reason))
    plans.sort(key=lambda item:(-float(item['conviction'].get('score',0)),item['symbol'],item['route']))
    return dict(status='READY',plans=plans,excluded=excluded,classifications=classifications,message=f'{len(plans)} naked-buy or spread proposals passed fresh broker checks. Choose an execution route per stock.')


def budget_slices(items, budget):
    """Explicit score-weighted budget shares; sum never exceeds entered budget."""
    weights=[]
    for item in items:
        value=item.get('allocation_weight',1)
        if isinstance(value,bool):raise ValueError('Allocation weights must be positive finite numbers.')
        weight=float(value)
        if not math.isfinite(weight) or weight<=0:raise ValueError('Allocation weights must be positive finite numbers.')
        weights.append(weight)
    if not weights or not math.isfinite(budget) or budget<=0:raise ValueError('A positive budget and selected candidates are required.')
    total=sum(weights)
    if not math.isfinite(total):raise ValueError('Total allocation weight is not finite.')
    budget=math.floor(budget*100)/100
    result=[];remaining=budget
    for weight in weights[:-1]:
        share=math.floor(budget*weight/total*100)/100
        result.append(share);remaining-=share
    result.append(round(remaining,2))
    return result
