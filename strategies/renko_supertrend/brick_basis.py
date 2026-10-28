"""Confirmed close-based uniform Renko events. No invented intrabar ordering.
Host closes become known at host close; all bricks from that observation share
that availability time. Auto box freezes at first calibrated value per history
anchor so past bricks never resize as volatility changes.
"""
from copy import deepcopy
import math

REVISION='confirmed-brick-basis-v1'

def update(engine,candle):
    from .signals import Engine,completed,rma
    rows=completed([candle])
    if not rows:return None
    c=rows[0];s=engine.state;cfg=engine.config
    previous=s.get('previous')
    if previous and c['timestamp']<=previous['timestamp']:raise ValueError('Feed each completed host candle exactly once in chronological order.')
    tr=max(c['high']-c['low'],abs(c['high']-previous['close']),abs(c['low']-previous['close'])) if previous else c['high']-c['low']
    atr=rma(s,'brick_host_atr',tr,cfg['atr_length'])
    atr5=rma(s,'brick_host_atr5',tr,5)
    regime=rma(s,'brick_regime',tr,15);low=rma(s,'brick_low',tr,9)
    ratio=atr/regime if atr is not None and regime else 1
    auto=atr5/12 if str(engine.underlying).upper().startswith(('NSE:','BSE:')) and atr5 is not None else (atr*1.5 if ratio>1.2 and atr is not None else low*.7 if ratio<.8 and low is not None else atr)
    if cfg['brick_mode']=='Manual':s['brick_box']=cfg['manual_brick']
    elif s.get('brick_box') is None and auto is not None:s['brick_box']=max(engine.tick_size,auto)
    box=s.get('brick_box');events=[]
    if box is not None:
        if s.get('brick_level') is None:s['brick_level']=math.floor(c['close']/box);s['brick_direction']=0
        target=c['close']/box;level=s['brick_level'];direction=s.get('brick_direction',0)
        tolerance=1e-10
        while True:
            up=target-level>=1-tolerance;down=level-target>=1-tolerance
            if direction<0:up=target-level>=2-tolerance
            if direction>0:down=level-target>=2-tolerance
            if not up and not down:break
            sign=1 if up else -1
            opening=level+(sign if direction and sign!=direction else 0)
            level=opening+sign;direction=sign
            events.append(dict(open=opening*box,close=level*box,high=max(opening,level)*box,low=min(opening,level)*box,volume=None))
            if len(events)>50000:raise ValueError('Renko brick limit exceeded; choose a larger brick size.')
        s['brick_level']=level;s['brick_direction']=direction
    # Optional host-candle filters retain their original timeframe semantics;
    # the Renko indicator recurrence and trade triggers still run per brick.
    gates={}
    if cfg.get('anti_chop_enabled'):
        from . import anti_chop
        original=deepcopy(s)
        for side in ('BULLISH','BEARISH'):
            trial=deepcopy(original);gates[side]=anti_chop.observe(trial,c,{**engine.raw_config,**cfg},side,engine.host_seconds)
            if side=='BULLISH':committed=trial
        for key in committed:
            if key not in original or committed[key]!=original[key]:s[key]=committed[key]
    host_rows=(s.get('basis_host_filter_rows',[])+[c])[-1000:]
    if cfg.get('manual_trend_enabled') or cfg.get('calibrated_enabled'):s['basis_host_filter_rows']=host_rows
    inner_cfg={**engine.raw_config,'strategy_basis':'CANDLESTICK','brick_mode':'Manual','manual_brick':box or engine.tick_size,'chart_entry_guards':False,'_brick_input':True,'anti_chop_enabled':False,'manual_trend_enabled':False,'calibrated_enabled':False}
    inner=getattr(engine,'_brick_inner',None)
    if inner is None:
        inner=Engine(inner_cfg,engine.tick_size,s.get('brick_indicator_state'))
        engine._brick_inner=inner
    output=[];exit_consumed=False
    for i,event in enumerate(events):
        event['timestamp']=c['timestamp']+(i+1)/(len(events)+2)
        inner.raw_config['_external_anti_chop']=gates
        inner.raw_config['_external_anti_role']=cfg.get('anti_chop_role')
        if cfg.get('calibrated_enabled'):
            from . import calibrated
            inner.raw_config['_external_calibrated']=calibrated.check(host_rows,cfg,engine.host_seconds)
        if cfg.get('manual_trend_enabled'):
            from . import manual_trend
            inner.raw_config['_external_manual']={side:manual_trend.check(host_rows,cfg,side,engine.host_seconds) for side in ('BULLISH','BEARISH')}
        # Historical exits constrain projection only, never executable qualification.
        inner.raw_config['_suppress_projection_entry']=exit_consumed
        result=inner.update(event)
        if (result.get('lifecycle_event') or '').endswith('EXIT'):exit_consumed=True
        period=int(engine.raw_config.get('ema_exit_length',10));old=inner.state.get('brick_exit_ema')
        inner.state['brick_exit_ema']=event['close'] if old is None else 2/(period+1)*event['close']+(1-2/(period+1))*old
        bullish=event['close']>event['open'];aligned=(result['pine_direction']<0)==bullish
        if cfg['supertrend_enabled'] and not aligned:
            result.update(entry_qualified=False,entry_direction=None,entry_buy_signal=False,entry_sell_signal=False,entry_diagnostic='WAITING_BRICK_SUPERTREND_ALIGNMENT')
            inner.state['ema_qualified']=None
        result.update(source_timestamp=c['timestamp'],source_close=c['close'],box=box,brick_direction='BULLISH' if bullish else 'BEARISH',ema_exit=inner.state['brick_exit_ema'],ema_exit_enabled=engine.raw_config.get('ema_exit_enabled',False),strategy_basis='RENKO')
        output.append(result)
    s['brick_indicator_state']=deepcopy(inner.state)
    last=deepcopy(output[-1] if output else s.get('brick_last') or dict(ema10=None,ema30=None,ema100=None,supertrend=None,pine_direction=1,direction='NEUTRAL',entry_qualified=False,entry_diagnostic='WAITING_COMPLETED_RENKO_BRICK',entry_direction=None,cross_direction=None,buy_signal=False,sell_signal=False,raw_supertrend_cross_direction=None,synthetic_open=None,synthetic_close=None))
    if output:
        if last.get('entry_qualified') and any(r.get('entry_direction')==last.get('direction') for r in output):
            last.update(entry_direction=last['direction'],entry_buy_signal=last['direction']=='BULLISH',entry_sell_signal=last['direction']=='BEARISH')
        s['brick_last']=deepcopy(last)
    else:last.update(entry_qualified=False,entry_direction=None,entry_buy_signal=False,entry_sell_signal=False,cross_direction=None,raw_supertrend_cross_direction=None,buy_signal=False,sell_signal=False,lifecycle_event=None,lifecycle_reason=None,entry_diagnostic='WAITING_COMPLETED_RENKO_BRICK')
    for key in ('open','high','low','close'):
        if last.get(key) is None:last[key]=c[key]
    last.update(timestamp=c['timestamp'],host_open=c['open'],host_high=c['high'],host_low=c['low'],host_close=c['close'],host_atr=atr,box=box,auto_box=auto,brick_events=[{k:r.get(k) for k in ('timestamp','open','high','low','close','box','supertrend','pine_direction','direction','ema10','ema30','ema100','ema_exit','rsi14','rsi14_slope','entry_direction','entry_qualified','entry_diagnostic','supertrend_slope_filter','lifecycle_event','lifecycle_reason','lifecycle_event_at','brick_direction','source_timestamp','source_close')} for r in output],brick_count=len(output),strategy_basis='RENKO',has_completed_brick=bool(output))
    # Exits inspect every newly available brick, never an unchanged prior brick.
    last['brick_exit_events']=[{k:r.get(k) for k in ('close','ema_exit','brick_direction','raw_supertrend_cross_direction')} for r in output]
    s.update(previous=c,count=s.get('count',0)+1)
    for key in ('ema10','ema30','ema100'):s[key]=last.get(key)
    return last
