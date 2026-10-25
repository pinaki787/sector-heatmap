"""Isolated Renko research using fixed historical contracts and actual premiums.

No execution adapter, runner instance, login or order endpoint is imported here.
"""
import bisect,calendar,contextlib,io,json,math,warnings
from datetime import date,datetime,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from sector_heatmap.persistent_jobs import checkpoint
from .signals import Engine
from . import exit_indicators,market_structure,mtf_rsi,ema_proximity,trailing_stop,sideways,risk,zone_target
from .backtest_data import IST,in_session,session
from .runner import configuration
from .historical_lots import checked_lot
REVISION='exchange-contract-master-backtest-v3'
FRAMES={'1 minute':1,'2 minutes':2,'3 minutes':3,'5 minutes':5,'10 minutes':10,'15 minutes':15,'30 minutes':30,'1 hour':60}

def period(request,today=None):
    today=today or datetime.now(IST).date();last=today-timedelta(days=1)
    preset=str(request.get('period','1m'))
    if preset=='custom':first=date.fromisoformat(str(request.get('from_date')));last=date.fromisoformat(str(request.get('to_date')))
    else:
        months={'1m':1,'3m':3,'6m':6,'1y':12}.get(preset)
        if not months:raise ValueError('Choose 1, 3, 6 months, 1 year or custom dates.')
        month=(last.year*12+last.month-1)-months;year,m=divmod(month,12);m+=1
        first=date(year,m,min(last.day,calendar.monthrange(year,m)[1]))+timedelta(days=1)
    if not first<=last<today or (last-first).days>366:raise ValueError('Choose an ordered completed-date window of at most 366 days, ending before today.')
    return first,last

def framework_trade(rows,entry_at,exit_at,quantity,direction='BULLISH'):
    """Backtesting.py executes next-bar-open orders; no hand-built P&L proxy."""
    import pandas as pd
    from backtesting import Backtest,Strategy
    selected=[r for r in rows if r['timestamp']<=exit_at]
    times=[r['timestamp'] for r in selected];entry=bisect.bisect_left(times,entry_at);end=bisect.bisect_left(times,exit_at)
    if entry>=len(times) or end>=len(times) or times[entry]!=entry_at or times[end]!=exit_at or entry<2 or end<=entry:raise ValueError('Exact contract entry/exit bars and two preceding real candles are required.')
    selected=selected[entry-2:end+1];frame=pd.DataFrame(selected).rename(columns={k:k.title() for k in ('open','high','low','close','volume')});frame.index=pd.to_datetime(frame.pop('timestamp'),unit='s',utc=True)
    entry_i=2;exit_i=len(frame)-1;sign=1 if direction=='BULLISH' else -1
    class FixedContract(Strategy):
        def init(self):pass
        def next(self):
            i=len(self.data)-1
            if i==entry_i-1:(self.buy if sign>0 else self.sell)(size=quantity)
            if i==exit_i-1 and self.position:self.position.close()
    initial=max(1_000_000,float(frame['High'].max())*quantity*4)
    with warnings.catch_warnings(),contextlib.redirect_stderr(io.StringIO()),contextlib.redirect_stdout(io.StringIO()):
        warnings.simplefilter('ignore');stats=Backtest(frame,FixedContract,cash=initial,commission=0,trade_on_close=False,exclusive_orders=True,finalize_trades=False).run()
    trades=stats['_trades']
    if len(trades)!=1 or int(trades.iloc[0]['EntryBar'])!=entry_i or int(trades.iloc[0]['ExitBar'])!=exit_i:raise ValueError('Historical execution framework did not match the exact requested contract bars.')
    trade=trades.iloc[0]
    return dict(gross_pnl=float(trade['PnL']),entry_premium=float(trade['EntryPrice']),exit_premium=float(trade['ExitPrice']),engine='backtesting.py 0.6.6',curve=[dict(timestamp=int(t.timestamp()),gross_equity=float(row['Equity'])-initial) for t,row in stats['_equity_curve'].iterrows() if int(t.timestamp())>=entry_at])

def metrics(trades,capital):
    priced=[t for t in trades if t.get('net_pnl') is not None];values=[t['net_pnl'] for t in priced];wins=[v for v in values if v>0];losses=[v for v in values if v<0]
    equity=capital;peak=capital;drawdown=0;win=loss=best=worst=0;curve=[]
    for t in priced:
        v=t['net_pnl'];equity+=v;peak=max(peak,equity);drawdown=max(drawdown,peak-equity)
        win=win+1 if v>0 else 0;loss=loss+1 if v<0 else 0;best=max(best,win);worst=max(worst,loss)
        curve.append(dict(timestamp=t['exit_at'],equity=round(equity,2),drawdown=round(peak-equity,2)))
    return dict(closed_trades=len(trades),priced_trades=len(priced),wins=len(wins),losses=len(losses),breakeven=sum(v==0 for v in values),win_rate=100*len(wins)/len(values) if values else None,gross_pnl=round(sum(t['gross_pnl'] for t in trades if t.get('gross_pnl') is not None),2) if any(t.get('gross_pnl') is not None for t in trades) else None,estimated_charges=round(sum(t['charges'] for t in priced),2) if priced else None,net_pnl=round(sum(values),2) if values else (0.0 if not trades else None),profit_factor=sum(wins)/-sum(losses) if losses else None,profit_factor_note='No losing priced trades' if wins and not losses else 'No priced trades' if not values else '',max_drawdown=round(drawdown,2) if priced else None,drawdown_basis='Closed-trade net equity; not intratrade premium drawdown',max_winning_streak=best,max_losing_streak=worst,initial_capital=capital,ending_capital=round(equity,2),equity_curve=curve)

def run(request,source,now=None):
    first,last=period(request,now);submitted=dict(request.get('settings') or {})
    if submitted.get('strategy')!='RENKO_SUPERTREND_V1':raise ValueError('Backtest requires a captured Renko Supertrend configuration.')
    c=configuration(dict(submitted,mode='PAPER'));c['mode']='BACKTEST'
    symbol=c['underlying'];minutes=FRAMES[c['timeframe']];seconds=minutes*60;policy=session(symbol)
    if symbol.startswith(('NSE:','BSE:')):c['session_deadline']='15:10'
    elif symbol.startswith('MCX:'):c['session_deadline']='23:30'
    else:c['session_deadline']=None
    capital=float(submitted.get('paper_capital_inr') or 100000)
    if not math.isfinite(capital) or capital<=0:raise ValueError('Research capital must be positive.')
    if request.get('historical_units_per_lot') not in (None,''):raise ValueError('Manual/default lot-size substitutions are not allowed. Historical quantity requires exact-contract dated broker-master evidence.')
    warmup=max(c.get(k,1) for k in ('atr_length','ema_fast_length','ema_slow_length','rsi_slope_length','adx_length'))
    if c.get('ema_third_enabled'):warmup=max(warmup,c['ema_third_length'])
    warm_first=first-timedelta(days=max(14,math.ceil(warmup*minutes/375*7/5)+10))
    checkpoint('Loading staged historical underlying candles.')
    rows,coverage=source.underlying(symbol,warm_first,last,minutes)
    visible=[r for r in rows if str(first)<=datetime.fromtimestamp(r['timestamp'],IST).date().isoformat()<=str(last)]
    if not visible:raise ValueError('No staged/provider underlying data covers this instrument and requested period.')
    execution_rows,execution_coverage=source.underlying(symbol,warm_first,last,1)
    execution_visible=[r for r in execution_rows if str(first)<=datetime.fromtimestamp(r['timestamp'],IST).date().isoformat()<=str(last)]
    if not execution_visible:raise ValueError('One-minute underlying history is required for session exits and synchronized premium execution.')
    config=dict(c,chart_entry_guards=True,chart_zone_target_enabled=False)
    if c.get('higher_timeframe_enabled'):config['_chart_higher_rows']=source.underlying(symbol,warm_first,last,FRAMES[c['supertrend_timeframe']])[0]
    if mtf_rsi.enabled(c):config['_chart_rsi_rows']={slot:source.underlying(symbol,warm_first,last,FRAMES[c[f'rsi_htf_{slot}_timeframe']])[0] for slot in mtf_rsi.SLOTS if c.get(f'rsi_htf_{slot}_enabled')}
    zones=[];timeline=[];zone_times=[]
    if c.get('zone_target_enabled'):
        zones=source.underlying(symbol,warm_first,last,5)[0];zone_target.zones(zones,timeline);zone_times=[r['timestamp']+300 for r in zones]
    issues=[];audit=[];trades=[];position=None;pending=None;used=0;losses={};lock=None;exposure=None;engine=Engine(config,tick_size=float(request.get('host_tick_size') or .05));exit_ema=None;prior_gap=None
    limitations=['Historical candle-price simulation, not executable bid/ask or confirmed fills.','Completed signal at bar close; entry and selected-indicator exit at the next exact host-bar open.','ATM means nearest strike in the nearest broker-reported unexpired expiry; lower strike breaks ties.','Lot size requires exact-contract broker-master evidence for the trade date; snapshots are never projected across dates.','The exact entry contract is retained until exit. No rolling ATM, synthetic option valuation or underlying P&L substitute.','Captured trade limit applies across this backtest run, matching the runner.','NSE/BSE regular sessions and the 15:10 strategy cutoff are enforced; nonregular sessions are excluded.','Only the 2026 NSE holiday calendar is currently verified; earlier years use broker-returned weekdays.']
    if c.get('intrabar_entries'):issues.append(dict(type='UNSUPPORTED_TICK_TIMING',message='Intrabar entries require synchronized tick evidence; historical candles cannot reproduce this selected setting. Disable intrabar mode for a completed-candle backtest.'))
    if c.get('supertrend_continuation_enabled'):issues.append(dict(type='UNSUPPORTED_CONTINUATION',message='The selected runtime continuation policy is not available to this historical replay.'))
    if not symbol.startswith(('NSE:','BSE:')):issues.append(dict(type='UNVERIFIED_HISTORICAL_SESSION',message='This research adapter currently verifies NSE/BSE regular intraday sessions only. MCX seasonal sessions and continuous-market execution require a verified historical calendar before performance can be reported.'))
    if c.get('execution_route')=='CASH_EQUITY' and c.get('cash_product')=='CNC':issues.append(dict(type='UNVERIFIED_CARRY_FORWARD',message='Cash carry-forward requires a verified overnight corporate-action and cost policy. This replay supports regular intraday exposure only; the selected holding policy was not silently changed.'))
    blocked=bool(issues)
    if c.get('trailing_enabled') or c.get('spot_target') is not None or c.get('spot_stop') is not None:limitations.append('Hard boundaries and trailing are sampled at historical one-minute opens using synchronized real premiums; intervening tick paths and slippage are unknown.')
    def problem(kind,at,message,**kw):
        issues.append(dict(type=kind,at=at,message=str(message),**kw))
    def finish(bar,why):
        nonlocal position,lock,exposure,exit_ema
        p=position;at=bar['timestamp'];q=p['quotes'].get(at)
        if q is None or q.get('volume',0)<=0:problem('MISSING_HELD_CONTRACT',at,'Exact held-contract exit premium is missing.',contract=p['contract']['symbol']);return False
        trade=dict(entry_at=p['entry_at'],exit_at=at,direction=p['direction'],underlying=symbol,underlying_entry=p['spot'],underlying_exit=bar['open'],contract=p['contract']['symbol'],strike=p['contract'].get('strike'),expiry=p['contract'].get('expiry'),option_type=p['contract'].get('option_type'),quantity=p['quantity'],lot_size=p['lot_size'],lot_size_source=p['lot_size_source'],lot_size_provenance=p.get('lot_size_provenance'),lot_size_gap=p.get('lot_size_gap'),entry_premium=p['entry_premium'],exit_premium=q['open'],gross_pnl=None,charges=None,net_pnl=None,exit_reason=why,entry_indicators=p['signal'],holding_minutes=(at-p['entry_at'])/60)
        if p['quantity'] is not None:
            try:
                simulated=framework_trade(p['history'],p['entry_at'],at,p['quantity'],p['direction'] if c['execution_route']=='CASH_EQUITY' else 'BULLISH');trade.update({k:v for k,v in simulated.items() if k!='curve'})
                # The verified fee model does not cover earlier dates, cash or MCX.
                if c['execution_route']=='OPTIONS' and symbol.startswith(('NSE:','BSE:')) and datetime.fromtimestamp(at,IST).date()>=date(2026,4,1):
                    from .costs import fee,MODEL
                    rate=.000355299 if symbol.startswith('NSE:') else .000325
                    slip=float(c.get('additional_slippage_points',0) or 0)*p['quantity']*2
                    trade['charges']=round(fee(p['entry_premium']*p['quantity'],'BUY',exchange_rate=rate)['total']+fee(q['open']*p['quantity'],'SELL',exchange_rate=rate)['total']+slip,2)
                    trade['net_pnl']=round(trade['gross_pnl']-trade['charges'],2);trade['cost_model']=MODEL['id'];trade['cost_basis']='Estimated historical option charges plus selected additional-slippage sensitivity; contract-note costs unavailable.'
                else:problem('UNVERIFIED_HISTORICAL_COSTS',at,'Selected asset/date has no verified cost schedule; gross premium P&L only.')
            except ValueError as error:problem('PRICING_FRAMEWORK_GAP',at,error,contract=p['contract']['symbol'])
        else:problem('MISSING_HISTORICAL_QUANTITY',at,'Date-applicable exact-contract broker/exchange master lot metadata is missing or invalid. Quantity, costs and P&L are withheld; manual/default substitution is prohibited.',contract=p['contract']['symbol'],coverage=p.get('lot_size_gap'))
        trades.append(trade)
        if trade['net_pnl'] is not None:
            day=datetime.fromtimestamp(at,IST).date().isoformat();losses[day]=losses.get(day,0)+max(0,-trade['net_pnl'])
        lock=sideways.freeze(exposure,at,trade['net_pnl'],seconds,c,str(len(trades)),symbol) if c.get('sideways_enabled') else None
        position=None;exposure=None;engine.state['ema_qualified']=None;return True
    def closed_host(host,index):
        nonlocal pending,exit_ema,prior_gap
        at=host['timestamp'];sig=engine.update(host);alpha=2/(c.get('ema_exit_length',10)+1);exit_ema=host['close'] if exit_ema is None else alpha*host['close']+(1-alpha)*exit_ema
        selected=str(first)<=datetime.fromtimestamp(at,IST).date().isoformat()<=str(last)
        if selected and position:
            probe=dict(sig,supertrend_cross_direction=sig.get('raw_supertrend_cross_direction'),exit_previous_ema_gap=prior_gap)
            if c.get('market_structure_exit_enabled'):probe['exit_market_structure']=market_structure.check(rows[:index+1],position['direction'],seconds,at+seconds)
            why=exit_indicators.reason(c,probe,position['direction'])
            if c.get('ema_exit_enabled') and (host['close']<exit_ema if position['direction']=='BULLISH' else host['close']>exit_ema):why=why or f'EMA{c.get("ema_exit_length",10)}_CONFIRMED_BREACH'
            if c.get('zone_target_enabled'):
                j=bisect.bisect_right(zone_times,at+seconds)-1
                if j>=1:why=why or zone_target.assess_known(zones[j],zones[j-1],timeline[j-1],dict(direction=position['direction'],opened_at=position['entry_at']),at+seconds).get('reason')
            if why:pending=dict(action='EXIT',reason=why)
        elif selected and not lock and sig.get('entry_direction') and index>=warmup and used<c['max_trades']:
            pending=dict(action='ENTRY',expected=at+seconds,signal=sig)
        prior_gap=sig.get('ema_gap')
    host_index=0;previous_execution=None;observed_minutes=0
    for index,bar in enumerate(execution_rows):
        at=bar['timestamp'];clock=datetime.fromtimestamp(at,IST);day=clock.date().isoformat();selected=str(first)<=day<=str(last);minute=clock.hour*60+clock.minute
        if selected:observed_minutes+=1
        while host_index<len(rows) and rows[host_index]['timestamp']+seconds<=at:
            closed_host(rows[host_index],host_index);host_index+=1
        if index%100==0:checkpoint(f'Replaying historical candle {index+1} of {len(execution_rows)}.',dict(revision=REVISION,status='PARTIAL',phase='REPLAY',processed=index,total=len(execution_rows),requested=dict(from_date=str(first),to_date=str(last)),underlying=symbol,timeframe=c['timeframe'],settings=submitted,metrics=None,priced_subset_metrics=metrics(trades,capital),coverage=dict(observed_trading_hours=round(observed_minutes/60,2)),trades=list(trades),issues=list(issues)+[dict(type='PARTIAL_JOB',message='Saved progress only. Replay has not completed; full-period performance is withheld.')],assumptions=limitations))
        exited=False
        if selected and position:
            q=position['quotes'].get(at)
            if q is None:problem('MISSING_HELD_CONTRACT',at,'Held option premium missing; simulation stopped instead of marking or rolling it.',contract=position['contract']['symbol']);break
            deadline=int(c['session_deadline'][:2])*60+int(c['session_deadline'][3:]) if c.get('session_deadline') else None
            overnight=c.get('commodity_holding')=='CARRY_FORWARD' or c.get('cash_product')=='CNC' or policy['timezone']=='UTC'
            if position['day']!=day and not overnight:
                problem('MISSING_SESSION_EXIT',at,'Prior session cutoff premium/underlying evidence is missing; no next-day exit was invented.');break
            if previous_execution is not None and position['day']==day and at-previous_execution!=60:
                problem('MISSING_EXPOSURE_HISTORY',at,'Missing one-minute underlying data during held exposure; replay stopped.');break
            forced=deadline is not None and minute>=deadline
            why='SESSION_CUTOFF' if forced else risk.hard_exit(bar['open'],position['direction'],c)
            if not why and c.get('trailing_enabled'):
                price=q['open'] if c.get('trailing_basis')=='OPTION_PREMIUM_PERCENT' else bar['open']
                position['trail'],hit=trailing_stop.advance(position.get('trail'),c,position['direction'],price,at,at,at,position['entry_at'])
                if hit:why='SAMPLED_TRAILING_STOP'
            if why or pending and pending.get('action')=='EXIT':
                if not finish(bar,why or pending['reason']):break
                pending=None;exited=True
        if selected and lock and sideways.breakout(lock,bar['open'],at,at):lock=None;engine.state['ema_qualified']=None
        if selected and pending and pending.get('action')=='ENTRY' and not position and not exited:
            plan=pending;pending=None
            deadline=int(c['session_deadline'][:2])*60+int(c['session_deadline'][3:]) if c.get('session_deadline') else 1440
            if at==plan['expected'] and minute<deadline and not lock and used<c['max_trades'] and not blocked:
                try:
                    sig=plan['signal'];fast=sig['ema10']+2/(c['ema_fast_length']+1)*(bar['open']-sig['ema10']);slow=sig['ema30']+2/(c['ema_slow_length']+1)*(bar['open']-sig['ema30'])
                    ema_proximity.check(c,bar['open'],fast,sig['host_atr'],dict(sig,preflight_ema30=slow),sig['direction'])
                    why=risk.hard_exit(bar['open'],sig['direction'],c)
                    if why:raise ValueError('Entry already breaches selected hard boundary.')
                    if c['execution_route']=='CASH_EQUITY':
                        if c.get('cash_product')=='CNC' and sig['direction']=='BEARISH':raise ValueError('CNC delivery does not open a new short position.')
                        contract=dict(symbol=symbol,strike=None,expiry=None,option_type=None);history=execution_rows;qty=c['quantity'];lot=1;lot_source='Captured share quantity'
                    else:
                        contract=source.select(symbol,at,sig['direction'],bar['open']);history=source.premiums(contract,clock.date()-timedelta(days=7),min(last,date.fromisoformat(contract['expiry'])),1)
                        lot=checked_lot(contract,at);qty=int(c['lots'])*lot if lot else None;lot_source=contract.get('lot_size_source') or 'Missing authoritative dated master';
                        if lot is None:contract['lot_size']=None
                    quotes={r['timestamp']:r for r in history};q=quotes.get(at)
                    if q is None or q.get('volume',0)<=0:raise ValueError('Exact selected ATM contract entry premium is missing; no substitute contract is used.')
                    cost=q['open']*qty if qty else None
                    realized=sum(t['net_pnl'] or 0 for t in trades)
                    if cost is not None and (cost>capital+realized or c.get('max_premium') is not None and cost>c['max_premium'] or c.get('daily_budget') is not None and cost+losses.get(day,0)>c['daily_budget']):raise ValueError('Captured capital/premium/daily budget blocks this research entry.')
                    position=dict(contract=contract,history=history,quotes=quotes,quantity=qty,lot_size=lot,lot_size_source=lot_source,lot_size_provenance=contract.get('lot_size_provenance'),lot_size_gap=contract.get('lot_size_gap'),entry_at=at,spot=bar['open'],entry_premium=q['open'],direction=sig['direction'],signal={k:sig.get(k) for k in ('timestamp','direction','close','ema10','ema30','ema100','rsi14','rsi14_slope','adx','entry_diagnostic')},day=day);used+=1
                except ValueError as error:
                    text=str(error);kind='ENTRY_FILTER' if any(x in text for x in ('proximity','too far','Momentum','capital/','boundary','CNC')) else 'MISSING_OPTION_EVIDENCE'
                    audit.append(dict(at=at,type=kind,reason=text,underlying_price=bar['open'],direction=plan['signal']['direction']))
                    if kind!='ENTRY_FILTER':problem(kind,at,text)
        if selected and position:
            for value in (bar['open'],bar['high'],bar['low'],bar['close']):exposure=sideways.observe(exposure,position['entry_at'],value,at,at)
        previous_execution=at
    if position:problem('UNRESOLVED_POSITION',position['entry_at'],'Held contract has no evidenced exit within the requested data; it is excluded from closed-trade P&L.',contract=position['contract']['symbol'])
    def expected_day(start,step):
        while start<=last and start>=first:
            h,m=map(int,policy['open'].split(':'));stamp=datetime.combine(start,datetime.min.time(),ZoneInfo(policy['timezone'])).replace(hour=h,minute=m).timestamp()
            if in_session(stamp,policy):return start
            start+=timedelta(days=step)
        return None
    expected_first=expected_day(first,1);expected_last=expected_day(last,-1)
    if expected_first and datetime.fromtimestamp(execution_visible[0]['timestamp'],IST).date()>expected_first:problem('UNDERLYING_COVERAGE_START',execution_visible[0]['timestamp'],'Actual data starts after the requested first trading session.')
    if expected_last and datetime.fromtimestamp(execution_visible[-1]['timestamp'],IST).date()<expected_last:problem('UNDERLYING_COVERAGE_END',execution_visible[-1]['timestamp'],'Actual data ends before the requested last trading session.')
    # Never label a quiet or partially missing underlying period as complete.
    expected=set();cursor=first
    while cursor<=last:
        opening=epoch_open=datetime.combine(cursor,datetime.min.time(),ZoneInfo(policy['timezone']))
        h,m=map(int,policy['open'].split(':'));opening=opening.replace(hour=h,minute=m)
        if in_session(opening.timestamp(),policy):
            end_h,end_m=map(int,policy['close'].split(':'));count=(end_h-h)*60+end_m-m
            expected.update(int(opening.timestamp())+i*60 for i in range(count))
        cursor+=timedelta(days=1)
    missing=expected-{r['timestamp'] for r in execution_visible}
    if missing:problem('UNDERLYING_MINUTE_GAPS',min(missing),f'{len(missing)} expected regular-session underlying minutes are absent; complete-period metrics are withheld.',missing_minutes=len(missing))
    warm_count=sum(datetime.fromtimestamp(r['timestamp'],IST).date()<first for r in rows)
    if warm_count<warmup:problem('INSUFFICIENT_WARMUP',execution_visible[0]['timestamp'],f'{warm_count} preceding host bars available; selected periods require at least {warmup}.')
    subset=metrics(trades,capital);complete=not issues and all(t.get('net_pnl') is not None for t in trades)
    result=dict(revision=REVISION,status='COMPLETE' if complete else 'INCOMPLETE',mode='BACKTEST',broker=submitted.get('broker','FYERS'),currency='INR',underlying=symbol,timeframe=c['timeframe'],requested=dict(from_date=str(first),to_date=str(last)),settings=submitted,effective_settings=c,coverage=dict(coverage,visible_bars=len(visible),execution_minutes=len(execution_visible),actual_first=execution_visible[0]['timestamp'],actual_last=execution_visible[-1]['timestamp'],observed_trading_hours=round(len(execution_visible)/60,2),observed_sessions=len({datetime.fromtimestamp(r['timestamp'],IST).date() for r in visible}),warmup_bars=sum(datetime.fromtimestamp(r['timestamp'],IST).date()<first for r in rows),network_requests=getattr(source,'calls',0)),metrics=subset if complete else None,priced_subset_metrics=subset,trades=trades,skipped=audit,issues=issues,assumptions=limitations,data_evidence=source.evidence,execution_safety='Research only. No execution adapter, runner activation or broker orders.',quantity_policy='Exact-contract dated broker/exchange master only; no manual/default lot substitution')
    checkpoint('Historical report calculated and saved.',result);return result
