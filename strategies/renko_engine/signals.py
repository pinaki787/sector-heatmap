"""Confirmed host-candle port of reference.pine, independent of Supertrend."""
from copy import deepcopy
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json
import math
import re

STRATEGY='RENKO_ENGINE_V1'
IST=ZoneInfo('Asia/Kolkata')
DEFAULTS=dict(engine_brick_mode='Percentage',engine_percent=.66,engine_fixed_box=50.,engine_basis='Current close',engine_stepping='Whole bricks',engine_reversal_bricks=1,engine_round_brick=False,engine_anchor_time='2026-09-01T09:15',engine_seed_level=0.,engine_seed_trend=0,engine_rule='EMA cross + Renko direction',engine_direction='Both',engine_session_only=True,engine_session='0915-1505',engine_flat_hour=15,engine_flat_minute=10,engine_end_time='2026-12-31T23:59',engine_show_cpr=True,engine_show_range=True,engine_range_session='1245-1300',engine_show_fr=True)

def epoch(value):
    d=datetime.fromisoformat(value)
    if d.tzinfo is None:d=d.replace(tzinfo=IST)
    return d.timestamp()

def settings(payload):
    c={k:payload.get(k,v) for k,v in DEFAULTS.items()}
    for k,choices in dict(engine_brick_mode=('Percentage','Fixed'),engine_basis=('Current close','Previous close','Previous daily close'),engine_stepping=('Whole bricks','One brick per bar','Price minus brick'),engine_rule=('EMA cross + Renko direction','EMA crossing Renko','Aligned state transition','Renko reversal'),engine_direction=('Both','Long only','Short only')).items():
        if c[k] not in choices:raise ValueError('Invalid '+k)
    for k,low,high in [('engine_percent',.000001,float('inf')),('engine_fixed_box',.000001,float('inf')),('engine_seed_level',0,float('inf'))]:
        if isinstance(c[k],bool):raise ValueError('Invalid '+k)
        c[k]=float(c[k])
        if not math.isfinite(c[k]) or not low<=c[k]<=high:raise ValueError('Invalid '+k)
    for k,low,high in [('engine_reversal_bricks',1,3),('engine_seed_trend',-1,1),('engine_flat_hour',0,23),('engine_flat_minute',0,59)]:
        if isinstance(c[k],bool) or float(c[k])!=int(c[k]) or not low<=int(c[k])<=high:raise ValueError('Invalid '+k)
        c[k]=int(c[k])
    for k in ('engine_round_brick','engine_session_only','engine_show_cpr','engine_show_range','engine_show_fr'):
        if not isinstance(c[k],bool):raise ValueError('Boolean required for '+k)
    for k in ('engine_session','engine_range_session'):
        if not isinstance(c[k],str) or not re.fullmatch(r'(?:[01]\d|2[0-3])[0-5]\d-(?:[01]\d|2[0-3])[0-5]\d',c[k]):raise ValueError('Use HHMM-HHMM for '+k)
    if epoch(c['engine_anchor_time'])>=epoch(c['engine_end_time']):raise ValueError('Research end must follow anchor')
    return c

def minute(t):
    d=datetime.fromtimestamp(t,IST);return d.hour*60+d.minute

def in_session(t,window):
    a,b=(int(v[:2])*60+int(v[2:]) for v in window.split('-'));m=minute(t)
    return a<=m<b if a<=b else m>=a or m<b

class Engine:
    def __init__(self,config,tick_size,state=None):
        self.config=settings(config);self.seconds={'1 minute':60,'2 minutes':120,'3 minutes':180,'5 minutes':300,'10 minutes':600,'15 minutes':900,'30 minutes':1800,'1 hour':3600}[config.get('timeframe','5 minutes')]
        self.tick=float(tick_size)
        if not math.isfinite(self.tick) or self.tick<=0:raise ValueError('Verified tick size required')
        self.state=deepcopy(state) if state else dict(level=None,trend=0,previous=None,count=0,ema10=None,ema30=None,aligned_long=False,aligned_short=False,daily=None,prior_day=None,range=None,first=None,red=None)
    def update(self,b):
        from strategies.renko_supertrend.signals import completed
        b=completed([b])[0];s=self.state;c=self.config;t=b['timestamp'];old=s['previous']
        if old and t<=old['timestamp']:raise ValueError('Completed candles must be chronological')
        key=datetime.fromtimestamp(t,IST).date().isoformat();daily=s['daily'];new_day=daily is None or daily['date']!=key
        if new_day:
            s['prior_day']=daily;s['daily']=dict(date=key,high=b['high'],low=b['low'],close=b['close']);s.update(range=None,first=None,red=None)
        else:s['daily'].update(high=max(daily['high'],b['high']),low=min(daily['low'],b['low']),close=b['close'])
        prev=s['prior_day'];prev_close=prev['close'] if prev else None
        base=prev_close if c['engine_basis']=='Previous daily close' else old['close'] if c['engine_basis']=='Previous close' and old else None if c['engine_basis']=='Previous close' else b['close']
        raw=c['engine_fixed_box'] if c['engine_brick_mode']=='Fixed' else base*c['engine_percent']/100 if base is not None else None
        brick=max(self.tick,math.floor(raw/self.tick+.5)*self.tick if c['engine_round_brick'] else raw) if raw is not None else None
        old_level=s['level'];old_trend=s['trend'];old_fast=s['ema10'];old_slow=s['ema30']
        for name,length in [('ema10',10),('ema30',30)]:s[name]=b['close'] if s[name] is None else s[name]+2/(length+1)*(b['close']-s[name])
        fast,slow=s['ema10'],s['ema30']
        if t>=epoch(c['engine_anchor_time']) and brick is not None:
            if s['level'] is None:s.update(level=c['engine_seed_level'] or b['close'],trend=c['engine_seed_trend'])
            else:
                delta=b['close']-s['level'];candidate=1 if delta>0 else -1 if delta<0 else 0
                if abs(delta)>=brick*(c['engine_reversal_bricks'] if s['trend'] and candidate!=s['trend'] else 1):
                    advance=brick if c['engine_stepping']=='One brick per bar' else math.floor(abs(delta)/brick)*brick
                    s['level']=b['close']-candidate*brick if c['engine_stepping']=='Price minus brick' else s['level']+candidate*advance;s['trend']=candidate
        level,trend=s['level'],s['trend'];al=trend==1 and fast>slow and level is not None and b['close']>level;ash=trend==-1 and fast<slow and level is not None and b['close']<level
        rule=c['engine_rule']
        if rule=='EMA cross + Renko direction':long=old_fast is not None and old_fast<=old_slow and fast>slow and trend==1;short=old_fast is not None and old_fast>=old_slow and fast<slow and trend==-1
        elif rule=='EMA crossing Renko':long=old_level is not None and old_fast is not None and old_fast<=old_level and level is not None and fast>level and fast>slow;short=old_level is not None and old_fast is not None and old_fast>=old_level and level is not None and fast<level and fast<slow
        elif rule=='Aligned state transition':long=al and not s['aligned_long'];short=ash and not s['aligned_short']
        else:long=trend==1 and old_trend!=1;short=trend==-1 and old_trend!=-1
        active=epoch(c['engine_anchor_time'])<=t<=epoch(c['engine_end_time']);square=c['engine_session_only'] and minute(t+self.seconds)>=c['engine_flat_hour']*60+c['engine_flat_minute'];eligible=active and (not c['engine_session_only'] or in_session(t,c['engine_session'])) and not square
        raw_direction='BULLISH' if long else 'BEARISH' if short else None
        allowed=eligible and raw_direction is not None and not (raw_direction=='BULLISH' and c['engine_direction']=='Short only' or raw_direction=='BEARISH' and c['engine_direction']=='Long only')
        if in_session(t,c['engine_range_session']):s['range']=dict(high=max((s['range'] or {}).get('high',b['high']),b['high']),low=min((s['range'] or {}).get('low',b['low']),b['low']))
        opening=minute(t)==555
        if opening:s['first']=dict(high=b['high'],low=b['low'])
        elif s['first'] and s['red'] is None and b['close']<b['open']:s['red']=dict(high=b['high'],low=b['low'])
        band=lambda r,f:r['low']+(r['high']-r['low'])*f if r else None
        pivot=(prev['high']+prev['low']+prev['close'])/3 if prev else None;bc=(prev['high']+prev['low'])/2 if prev else None;tc=2*pivot-bc if prev else None
        context=dict(pivot=pivot if not new_day else None,tc=max(tc,bc) if prev and not new_day else None,bc=min(tc,bc) if prev and not new_day else None,range_high=(s['range'] or {}).get('high'),range_low=(s['range'] or {}).get('low'),range44=band(s['range'],.44),range56=band(s['range'],.56),f44=band(s['first'],.44) if not opening else None,f56=band(s['first'],.56) if not opening else None,r44=band(s['red'],.44),r56=band(s['red'],.56))
        # Historical Pine projection is separate from broker executions. Orders
        # generated at the prior close fill at this host candle's open.
        event=None;event_at=None;reason=None
        projected=s.get('projected_position');pending=s.pop('projected_pending',None)
        if pending:
            if pending['direction'] is None:
                event='BUY EXIT' if projected=='BULLISH' else 'SELL EXIT' if projected else None
            else:event='BUY' if pending['direction']=='BULLISH' else 'SELL'
            projected=pending['direction'];s['projected_entry_at']=t;event_at=t;reason=pending['reason']
        if (square or t>epoch(c['engine_end_time'])) and projected:
            event='BUY EXIT' if projected=='BULLISH' else 'SELL EXIT';projected=None;event_at=t+self.seconds;reason='SESSION_OR_END_CLOSE'
        elif active:
            if allowed and raw_direction!=projected:
                s['projected_pending']=dict(direction=raw_direction,reason='PINE_ENTRY_OR_REVERSAL')
            elif projected and raw_direction and raw_direction!=projected:
                s['projected_pending']=dict(direction=None,reason='OPPOSITE_SIGNAL')
        s['projected_position']=projected
        s.update(previous=b,count=s['count']+1,aligned_long=al,aligned_short=ash)
        return dict(**b,**context,lifecycle_event=event,lifecycle_event_at=event_at,lifecycle_reason=reason,projected_position=dict(direction=projected,entry_timestamp=s.get('projected_entry_at',t)) if projected else None,renko_close=level,renko_open=old_level or level,supertrend=level,box=brick,auto_box=brick,direction='BULLISH' if trend==1 else 'BEARISH' if trend==-1 else 'NEUTRAL',pine_direction=trend,ema10=fast,ema30=slow,ema_gap=fast-slow,ema_exit_enabled=False,entry_direction=raw_direction if allowed else None,cross_direction=raw_direction if allowed else None,supertrend_cross_direction=raw_direction if active else None,engine_opposite_signal=raw_direction if active else None,entry_qualified=bool(allowed),entry_diagnostic='QUALIFIED' if allowed else 'OUTSIDE_ENGINE_SESSION' if not eligible else 'DIRECTION_RESTRICTED' if raw_direction else 'WAITING_ENGINE_SIGNAL',signal_allowed=True,engine_squareoff=square or t>epoch(c['engine_end_time']),engine_active=active,engine_context_source='Previous loaded intraday session HLC; exchange daily parity unverified',is_forming=False)

def analysis(candles,config,tick_size,saved=None,retain=500):
    from strategies.renko_supertrend.signals import completed
    from strategies.renko_supertrend.runner import price_fingerprint,HistoryRevision
    rows=completed(candles)
    if not rows:raise ValueError('No completed host candles')
    identity=dict(engine_version='pro-renko-engine-v1',config=settings(config),symbol=config['underlying'],timeframe=config['timeframe'],tick_size=tick_size)
    if saved and saved['identity']!=identity:raise ValueError('Engine configuration changed; explicit stopped restart required')
    if saved and saved['last']['timestamp'] not in {r['timestamp'] for r in rows}:raise ValueError('Engine history continuity lost; no reseed or entry')
    fingerprints=dict(saved.get('price_fingerprints',{})) if saved else {};outputs=list(saved.get('rows',[])) if saved else [];engine=Engine(config,tick_size,saved['state'] if saved else None);last=saved.get('last') if saved else None
    for b in rows:
        key=str(b['timestamp']);digest=price_fingerprint(b)
        if key in fingerprints and fingerprints[key]!=digest:raise HistoryRevision('Completed engine OHLC changed; same-anchor recovery required')
        if last and b['timestamp']<=last['timestamp']:continue
        last=engine.update(b);outputs.append(last);fingerprints[key]=digest
    return dict(identity=identity,state=deepcopy(engine.state),last=last,rows=outputs[-retain:] if retain else outputs,price_fingerprints=dict(list(fingerprints.items())[-1000:]),fingerprints={},anchor=saved['anchor'] if saved else rows[0]['timestamp'])
