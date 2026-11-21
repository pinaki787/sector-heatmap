"""Deterministic strategy core; no broker imports or inherited entry filters."""
from collections import deque
import math
try:from .indicator import AIRenko, Traditional
except ImportError:from indicator import AIRenko, Traditional

def positive(value,name):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<=0:raise ValueError(name+' must be finite and positive')
    return value

def sizes(reference,delta,market='NSE',asset=None):
    positive(reference,'Prior-session reference')
    if isinstance(delta,bool) or not math.isfinite(delta) or not 0<abs(delta)<=1:raise ValueError('Verified nonzero delta required')
    try:from .sizing_policy import scale_reference
    except ImportError:from sizing_policy import scale_reference
    sized=scale_reference(reference,market,asset,delta=delta)
    return sized['base_brick'],sized['premium_brick']

def select_contract(rows,side,expiry,target=40):
    positive(target,'Premium target')
    if side not in ('CE','PE'):raise ValueError('CE/PE required')
    candidates=[r for r in rows if r.get('option_type')==side and str(r.get('expiry'))==str(expiry) and isinstance(r.get('ltp'),(int,float)) and math.isfinite(r['ltp']) and r['ltp']>0]
    if not candidates:raise ValueError('No priced contracts for explicit expiry/side')
    return min(candidates,key=lambda r:(abs(r['ltp']-target),r['symbol']))

class SMAExit:
    def __init__(self):self.values=deque(maxlen=30);self.previous=None;self.timestamp=None
    def update(self,timestamp,close):
        if self.timestamp is not None and timestamp<=self.timestamp:raise ValueError('Duplicate/out-of-order SMA minute')
        self.timestamp=timestamp;self.values.append(positive(close,'Close'))
        if len(self.values)<30:return None
        diff=close-sum(self.values)/30
        cross=None if self.previous is None else 'BELOW' if self.previous>=0 and diff<0 else 'ABOVE' if self.previous<=0 and diff>0 else None
        self.previous=diff
        return cross

class Strategy:
    def __init__(self,config):
        self.config=dict(config,indicator_brick_mode=config.get('indicator_brick_mode','Manual'),entry_gate=config.get('entry_gate','underlying_flip_premium_bullish'),exit_supertrend=config.get('exit_supertrend','premium'))
        if config.get('timeframe',1) not in (1,5,30):raise ValueError('Timeframe must be 1,5,30')
        if config.get('entry_gate','underlying_flip_premium_bullish') not in ('underlying_flip','underlying_flip_premium_bullish','underlying_trend_premium_flip'):raise ValueError('Explicit entry_gate required')
        if config.get('exit_supertrend','premium') not in ('underlying','premium','either'):raise ValueError('Explicit exit_supertrend required')
        if config.get('sma_exit_enabled',False) and config.get('sma_price_basis')!='underlying':raise ValueError('Optional directional SMA requires explicit underlying basis')
        if config.get('indicator_brick_mode','Manual') not in ('Auto','Manual'):raise ValueError('Indicator mode Auto/Manual required')
        try:from .sizing_policy import scale_reference
        except ImportError:from sizing_policy import scale_reference
        self.sizing=scale_reference(config['reference_value'],config.get('market','NSE'),config.get('asset'));self.spot_size=self.sizing['base_brick']
        positive(self.spot_size,'Spot brick')
        self.under_renko=Traditional(self.spot_size)
        self.under_ai=self.indicator(self.spot_size)
        self.option_renko=self.option_ai=None
        self.position=self.under_result=self.premium_result=None
        self.sma=SMAExit();self.last_time={};self.pending_underlying_flip=None
    def indicator(self,size):return AIRenko(manual_brick=size if self.config.get('indicator_brick_mode')=='Manual' else None,pine_series_precision=True)
    def reset_contract(self,contract,delta):
        if self.position:raise ValueError('Cannot change open-trade contract/sizing')
        if not contract.get('symbol'):raise ValueError('Symbol required')
        spot,option=sizes(self.config['reference_value'],delta,self.config.get('market','NSE'),self.config.get('asset'))
        self.contract=dict(contract,selection_delta=delta,spot_brick=spot,option_brick=option,execution_route='OPTIONS',asset=self.config.get('asset'),parent_hours=self.sizing['parent_hours'])
        self.option_renko=Traditional(option);self.option_ai=self.indicator(option);self.premium_result=None
    def update(self,event):
        kind=event['kind'];at=event['timestamp']
        if kind not in ('underlying','premium','sma'):raise ValueError('Unknown kind')
        if kind in self.last_time and at<=self.last_time[kind]:raise ValueError('Duplicate/out-of-order observation')
        self.last_time[kind]=at;close=positive(event['close'],'Close')
        if kind=='sma':
            if not self.config.get('sma_exit_enabled',False):return []
            cross=self.sma.update(at,close)
            if self.position and ((self.position['side']=='CE' and cross=='BELOW') or (self.position['side']=='PE' and cross=='ABOVE')):return self.exit(at,'OPTIONAL_UNDERLYING_1M_SMA30')
            return []
        if kind=='premium' and (not self.option_ai or event.get('symbol')!=self.contract['symbol']):raise ValueError('Selected/warmed contract required')
        renko=self.under_renko if kind=='underlying' else self.option_renko
        ai=self.under_ai if kind=='underlying' else self.option_ai
        actions=[]
        for bar in renko.update(close):
            result=ai.update(bar)
            if kind=='underlying':self.under_result=result
            else:self.premium_result=result
            if self.position:
                adverse=result['flip'] and ((result['direction']>0 if self.position['side']=='CE' else result['direction']<0) if kind=='underlying' else result['direction']>0)
                if adverse and self.config['exit_supertrend'] in (kind,'either'):
                    actions+=self.exit(at,'AI_RENKO_SUPERTREND_'+kind.upper());break
            elif result['flip']:
                if kind=='underlying':self.pending_underlying_flip=at
                gate=self.config['entry_gate']
                side='CE' if self.under_result and self.under_result['direction']<0 else 'PE'
                if kind=='underlying' and (not hasattr(self,'contract') or self.contract.get('option_type')!=side):
                    actions.append(dict(action='SELECT',side=side,timestamp=at));continue
                eligible=(kind=='underlying' and gate=='underlying_flip') or (kind=='underlying' and gate=='underlying_flip_premium_bullish' and self.premium_result and self.premium_result['direction']<0 and self.last_time.get('premium',-1)>=at) or (kind=='premium' and gate=='underlying_trend_premium_flip' and result['direction']<0 and self.under_result is not None)
                if eligible:
                    if not hasattr(self,'contract') or self.contract.get('option_type')!=side:actions.append(dict(action='SELECT',side=side,timestamp=at));continue
                    self.pending_underlying_flip=None
                    self.position=dict(self.contract,side=side,entry_timestamp=at)
                    actions.append(dict(action='BUY',timestamp=at,position=dict(self.position)))
        return actions
    def selected_gate_entry(self):
        at=self.pending_underlying_flip
        if self.position or at is None or self.config['entry_gate']!='underlying_flip_premium_bullish' or not self.premium_result or self.premium_result['direction']>=0:return None
        if self.last_time.get('premium',-1)<at:return None
        side='CE' if self.under_result['direction']<0 else 'PE'
        if self.contract['option_type']!=side:return None
        entry_at=max(at,self.last_time['premium'])
        self.position=dict(self.contract,side=side,entry_timestamp=entry_at,underlying_flip_timestamp=at)
        self.pending_underlying_flip=None
        return dict(action='BUY',timestamp=entry_at,position=dict(self.position))
    def exit(self,at,reason):
        position=self.position;self.position=None
        return [dict(action='SELL',timestamp=at,reason=reason,position=position)]
