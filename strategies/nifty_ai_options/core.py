try:from . import sma_only
except ImportError:import sma_only
"""Deterministic strategy core; no broker imports or inherited entry filters."""
from collections import deque
import math
try:from .indicator import AIRenko, Traditional
except ImportError:from indicator import AIRenko, Traditional
try:from .hybrid_confirmation import HybridConfirmation,confirm_exit
except ImportError:from hybrid_confirmation import HybridConfirmation,confirm_exit

def positive(value,name):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<=0:raise ValueError(name+' must be finite and positive')
    return value

def sizes(reference,delta,market='NSE',asset=None,option_moneyness='OTM'):
    positive(reference,'Prior-session reference')
    if isinstance(delta,bool) or not math.isfinite(delta) or not 0<abs(delta)<=1:raise ValueError('Verified nonzero delta required')
    try:from .sizing_policy import scale_reference
    except ImportError:from sizing_policy import scale_reference
    sized=scale_reference(reference,market,asset,delta=delta,option_moneyness=option_moneyness)
    return sized['base_brick'],sized['premium_brick']

def select_contract(rows,side,expiry,target=40,*,option_moneyness='OTM',underlying_price=None):
    if option_moneyness not in ('OTM','ATM'):raise ValueError('Select OTM or ATM option classification')
    if option_moneyness=='OTM':positive(target,'Premium target')
    if side not in ('CE','PE'):raise ValueError('CE/PE required')
    candidates=[r for r in rows if r.get('option_type')==side and str(r.get('expiry'))==str(expiry) and isinstance(r.get('ltp'),(int,float)) and math.isfinite(r['ltp']) and r['ltp']>0]
    if option_moneyness=='ATM':
        positive(underlying_price,'Broker underlying price for ATM selection')
        candidates=[r for r in candidates if isinstance(r.get('strike_price'),(int,float)) and not isinstance(r.get('strike_price'),bool) and math.isfinite(r['strike_price']) and r['strike_price']>0]
        if not candidates:raise ValueError('Broker strike metadata unavailable for ATM selection')
        return min(candidates,key=lambda r:(abs(r['strike_price']-underlying_price),r['strike_price'],r['symbol']))
    if isinstance(underlying_price,(int,float)) and math.isfinite(underlying_price) and underlying_price>0:
        candidates=[r for r in candidates if isinstance(r.get('strike_price'),(int,float)) and (r['strike_price']>underlying_price if side=='CE' else r['strike_price']<underlying_price)]
    if not candidates:raise ValueError('No priced contracts for explicit expiry/side')
    return min(candidates,key=lambda r:(abs(r['ltp']-target),r['symbol']))

def chart_candle(event):
    values={key:positive(event.get(key),'Broker candle '+key) for key in ('open','high','low','close')}
    if not values['low']<=min(values['open'],values['close'])<=max(values['open'],values['close'])<=values['high']:raise ValueError('Real broker OHLC required for the selected Candles indicator')
    return values


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

try:from .sma_band import BandPolicy,observe_band
except ImportError:from sma_band import BandPolicy,observe_band

class Strategy:
    def __init__(self,config):
        sma_only.validate(config)
        self.config=dict(config,indicator_brick_mode=config.get('indicator_brick_mode','Manual'),entry_gate=config.get('entry_gate','underlying_flip_premium_bullish'),exit_supertrend=config.get('exit_supertrend','premium'))
        self.calculation_mode=config.get('calculation_mode','RENKO')
        if self.calculation_mode not in ('CANDLES','RENKO','HYBRID'):raise ValueError('Choose the strategy chart calculation mode')
        self.band=BandPolicy(self.config)
        if config.get('timeframe',1) not in (1,5,30):raise ValueError('Timeframe must be 1,5,30')
        if not sma_only.enabled(config) and config.get('entry_gate','underlying_flip_premium_bullish') not in ('underlying_flip','underlying_flip_premium_bullish','underlying_trend_premium_flip'):raise ValueError('Explicit entry_gate required')
        if not sma_only.enabled(config) and config.get('exit_supertrend','premium') not in ('underlying','premium','either'):raise ValueError('Explicit exit_supertrend required')
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
        self.entry_confirmation=HybridConfirmation(self.spot_size);self.hybrid_sequence=0;self.hybrid_price_at={};self.hybrid_exchange_at={};self.hybrid_last_sequence={};self.premium_confirmation=None;self.hybrid_active=False;self.premium_entry_confirmation=None
    def signal_side(self):return sma_only.side(self)
    def indicator(self,size):return AIRenko(length=self.config.get('indicator_length',5),factor=self.config.get('indicator_factor',3.0),manual_brick=size if self.config.get('indicator_brick_mode')=='Manual' else None,pine_series_precision=True,completed_bricks=self.config.get('supertrend_basis')=='COMPLETED_RENKO')
    def reset_contract(self,contract,delta=None):
        if self.position:raise ValueError('Cannot change open-trade contract/sizing')
        if not contract.get('symbol'):raise ValueError('Symbol required')
        if delta is None:
            binding=contract.get('verified_native_selection') or {}
            expected=dict(broker=self.config.get('broker'),account=self.config.get('account'),underlying=self.config.get('underlying'),symbol=contract.get('symbol'))
            if self.config.get('broker') not in ('DHAN','MOTILAL_OSWAL') or binding!=expected:raise ValueError('Verified native contract selection required when Greeks are unavailable')
            try:from .sizing_policy import scale_reference
            except ImportError:from sizing_policy import scale_reference
            geometry=scale_reference(self.config['reference_value'],self.config.get('market','NSE'),self.config.get('asset'),is_option=True,option_moneyness=self.config.get('option_moneyness','OTM'))
            spot,option=geometry['base_brick'],geometry['premium_brick']
        else:
            spot,option=sizes(self.config['reference_value'],delta,self.config.get('market','NSE'),self.config.get('asset'),self.config.get('option_moneyness','OTM'))
        self.contract=dict(contract,selection_delta=delta,spot_brick=spot,option_brick=option,option_moneyness=self.config.get('option_moneyness','OTM'),option_multiplier=option/spot,execution_route='OPTIONS',asset=self.config.get('asset'),parent_hours=self.sizing['parent_hours'])
        if self.config.get('band_price_basis')=='premium':
            self.config['band_symbol']=contract['symbol'];self.band=BandPolicy(self.config)
        self.premium_confirmation=None;self.premium_entry_confirmation=HybridConfirmation(option)
        if hasattr(self,'hybrid_hosts'):self.hybrid_hosts.pop('premium',None)
        if hasattr(self,'completed_signal_queue'):self.completed_signal_queue=[p for p in self.completed_signal_queue if p['symbol']==self.config['underlying']]
        if hasattr(self,'completed_signal_counts'):self.completed_signal_counts={k:v for k,v in self.completed_signal_counts.items() if k==self.config['underlying']}
        self.option_renko=Traditional(option);self.option_ai=self.indicator(option);self.premium_result=None
    def update(self,event):
        self.entry_observation_at=event.get('available_at',event.get('closed_at',event['timestamp']))
        if sma_only.enabled(self.config):return sma_only.update(self,event,True)
        kind=event['kind'];at=event['timestamp']
        if kind not in ('underlying','premium','sma'):raise ValueError('Unknown kind')
        if kind in self.last_time and at<=self.last_time[kind]:raise ValueError('Duplicate/out-of-order observation')
        self.last_time[kind]=at;close=positive(event['close'],'Close')
        if kind=='premium' and (not self.option_ai or event.get('symbol')!=self.contract['symbol']):raise ValueError('Selected/warmed contract required')
        if kind in ('underlying','premium'):
            band_actions=observe_band(self,event)
            if band_actions:return band_actions
        if kind=='sma':
            if not self.config.get('sma_exit_enabled',False):return []
            cross=self.sma.update(at,close)
            if self.position and ((self.position['side']=='CE' and cross=='BELOW') or (self.position['side']=='PE' and cross=='ABOVE')):return self.exit(at,'OPTIONAL_UNDERLYING_1M_SMA30')
            return []
        if kind=='premium' and (not self.option_ai or event.get('symbol')!=self.contract['symbol']):raise ValueError('Selected/warmed contract required')
        renko=self.under_renko if kind=='underlying' else self.option_renko
        ai=self.under_ai if kind=='underlying' else self.option_ai
        actions=[]
        if self.calculation_mode=='HYBRID':
            try:from .hybrid_basis import seed
            except ImportError:from hybrid_basis import seed
            warm_bricks=seed(self,event,kind)
        for bar in (warm_bricks if self.calculation_mode=='HYBRID' and self.config.get('supertrend_basis')=='COMPLETED_RENKO' else [chart_candle(event)] if self.calculation_mode in ('CANDLES','HYBRID') else renko.update(close)):
            result=ai.update(bar)
            if self.calculation_mode=='HYBRID' and self.config.get('supertrend_basis')=='COMPLETED_RENKO':
                try:from .hybrid_basis import record_signal
                except ImportError:from hybrid_basis import record_signal
                record_signal(self,event,kind,bar,result)
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
                if eligible and self.band.entry_ready(side,self.config,getattr(self,'entry_observation_at',at)):
                    if not hasattr(self,'contract') or self.contract.get('option_type')!=side:actions.append(dict(action='SELECT',side=side,timestamp=at));continue
                    self.pending_underlying_flip=None
                    self.band.consume_entry()
                    self.position=dict(self.contract,side=side,entry_timestamp=at)
                    actions.append(dict(action='BUY',timestamp=at,position=dict(self.position)))
        if self.config.get('sma_band_entry') and self.position is None:
            result=self.premium_result if self.config.get('band_price_basis')=='premium' else self.under_result
            confirmation=self.band.reentry(event,self.config,result,not_before=getattr(self,'entry_reset_at',0))
            if confirmation:
                self.pending_underlying_flip=event.get('available_at',event.get('closed_at',at+self.config['timeframe']*60))
                self.pending_underlying_flip_source_at=confirmation['closed_at'];self.entry_observation_at=self.pending_underlying_flip
                side='CE' if self.under_result and self.under_result['direction']<0 else 'PE'
                if not hasattr(self,'contract') or self.contract.get('option_type')!=side:actions.append(dict(action='SELECT',side=side,timestamp=self.pending_underlying_flip))
                else:
                    action=self.selected_gate_entry()
                    if action:action['confirmation']=confirmation;actions.append(action)
        return actions
    def update_hybrid(self,event):
        self.entry_observation_at=event.get('available_at',event.get('closed_at',event['timestamp']))
        if sma_only.enabled(self.config):return sma_only.update(self,event,True)
        self.hybrid_active=True
        if event['kind']=='sma':return self.update(event)
        kind=event.get('series') if event['kind']=='price' else event['kind']
        if kind not in ('underlying','premium'):raise ValueError('Exact underlying or premium series required')
        if kind=='premium' and (not self.option_ai or event.get('symbol')!=self.contract['symbol']):raise ValueError('Exact selected premium required')
        if kind=='premium' and self.config.get('signal_source')=='UNDERLYING':return []
        at=event.get('available_at',event['timestamp']);positive(at,'Observation availability')
        renko=self.under_renko if kind=='underlying' else self.option_renko
        ai=self.under_ai if kind=='underlying' else self.option_ai
        size=self.spot_size if kind=='underlying' else self.contract['option_brick']
        units=[]
        if event['kind']=='price':
            if self.calculation_mode=='CANDLES':return []
            exchange=positive(event['timestamp'],'Provider timestamp')
            if exchange<self.hybrid_exchange_at.get(kind,0):raise ValueError('Out-of-order provider price')
            sequence=event.get('sequence')
            if sequence is not None:
                if isinstance(sequence,bool) or not isinstance(sequence,int) or sequence<=self.hybrid_last_sequence.get(kind,0):raise ValueError('Duplicate live price sequence')
                self.hybrid_last_sequence[kind]=sequence
            self.hybrid_exchange_at[kind]=exchange
            previous_at=self.hybrid_price_at.get(kind)
            if previous_at is not None and at<previous_at:raise ValueError('Out-of-order live price')
            self.hybrid_price_at[kind]=at;self.hybrid_sequence+=1
            if self.calculation_mode=='HYBRID':
                try:from .hybrid_basis import price
                except ImportError:from hybrid_basis import price
                formed,result=price(self,event,kind)
            else:formed,result=renko.update(positive(event['close'],'Selected broker price')),None
            for index,bar in enumerate(formed):
                if self.calculation_mode!='HYBRID':result=ai.update(bar)
                elif self.config.get('supertrend_basis')=='COMPLETED_RENKO':result=bar['_signal_result']
                elif index:result=dict(result,flip=False)
                if kind=='underlying':
                    self.under_result=result
                    if result['flip']:self.entry_confirmation.arm('LONG' if result['direction']<0 else 'SHORT',at,(kind,self.hybrid_sequence,len(units)),source_at=exchange)
                else:
                    self.premium_result=result
                    if result['flip'] and result['direction']<0:
                        self.premium_entry_confirmation.arm('LONG',at,('premium-flip',self.hybrid_sequence,len(units)),source_at=exchange)
                units.append(dict(bar,kind='brick',closed=True,closed_at=event['timestamp'],available_at=at))
        else:
            if self.calculation_mode=='HYBRID' and (event.get('closed') is not True or event.get('source_basis')!='PROVIDER_CONFIRMED_CLOSE' or event.get('body_available') is not True):return []
            key='hybrid_candle_'+kind
            if at<=self.last_time.get(key,0):raise ValueError('Duplicate hybrid candle')
            self.last_time[key]=at;self.last_time[kind]=event['timestamp']
            if event.get('source_basis')!='PROVIDER_CONFIRMED_CLOSE' or event.get('body_available') is not True:return []
            if self.calculation_mode in ('CANDLES','HYBRID'):
                if self.calculation_mode=='HYBRID':
                    if event.get('closed') is not True:return []
                    try:from .hybrid_basis import confirmed
                    except ImportError:from hybrid_basis import confirmed
                    result=confirmed(self,event,kind)
                    if self.config.get('supertrend_basis')=='COMPLETED_RENKO':
                        try:from .hybrid_basis import store
                        except ImportError:from hybrid_basis import store
                        units.extend(dict(bar,kind='brick',closed=True,closed_at=event['closed_at'],available_at=at) for bar in store(self)[kind].pop('confirmed_bricks',[]))
                    if result is None:return observe_band(self,event)
                else:result=ai.update(chart_candle(event))
                if kind=='underlying':
                    self.under_result=result
                    if result['flip']:self.entry_confirmation.arm('LONG' if result['direction']<0 else 'SHORT',at,(kind,'candle',event['timestamp']),source_at=event.get('closed_at',event['timestamp']+self.config['timeframe']*60))
                else:
                    self.premium_result=result
                    if result['flip'] and result['direction']<0:self.premium_entry_confirmation.arm('LONG',at,('premium-candle',event['timestamp']),source_at=event.get('closed_at',event['timestamp']+self.config['timeframe']*60))
            if self.config.get('supertrend_basis')!='COMPLETED_RENKO' or abs(event['close']-event['open'])<size:
                units.append(dict(kind='host_candle' if self.calculation_mode=='CANDLES' else 'candle',open=event['open'],close=event['close'],closed=True,closed_at=event.get('closed_at',event['timestamp']+self.config['timeframe']*60),available_at=at))
        if self.config.get('exit_confirmation_mode')=='RENKO_BRICKS_ONLY':
            units=[unit for unit in units if unit.get('kind')=='brick']
        if self.calculation_mode=='HYBRID':
            try:from .hybrid_basis import brick_event
            except ImportError:from hybrid_basis import brick_event
            event=brick_event(event,units)
        band_actions=observe_band(self,event)
        if band_actions:self.band.retest=None;return band_actions
        reentry=self.band.reentry(event,self.config,self.premium_result if self.config.get('band_price_basis')=='premium' else self.under_result,flat=self.position is None,not_before=getattr(self,'entry_reset_at',0)) if event['kind']==self.config.get('band_price_basis','underlying') else None
        result=self.under_result if kind=='underlying' else self.premium_result
        if not units or not result:return []
        unit=units[-1];direction='LONG' if result['direction']<0 else 'SHORT'
        if self.position:
            if self.config['exit_supertrend'] not in (kind,'either'):return []
            confirmation=confirm_exit(unit,self.position,direction,result['st'],size,premium=kind=='premium')
            if not confirmation:return []
            entry_confirmation=None
            pending=self.entry_confirmation.pending if kind=='underlying' else None
            entered=self.position.get('entry_confirmed_at',self.position.get('entry_timestamp',0))
            if pending and pending['flip_at']>=entered:
                entry_confirmation=self.entry_confirmation.confirm(unit,direction,result['st'])
            actions=self.exit(at,'AI_RENKO_SUPERTREND_'+kind.upper());actions[0]['confirmation']=confirmation
            if self.config.get('signal_source')=='UNDERLYING' and kind=='underlying' and entry_confirmation:
                self.pending_underlying_flip=at;self.pending_underlying_flip_source_at=entry_confirmation['closed_at']
                actions[0]['entry_confirmation']=entry_confirmation
            return actions
        gate_mode=self.config['entry_gate']
        if kind=='underlying':
            confirmation=self.entry_confirmation.confirm(unit,direction,result['st'])
            if confirmation and gate_mode!='underlying_trend_premium_flip':
                self.pending_underlying_flip=at;self.pending_underlying_flip_source_at=confirmation['closed_at']
                if self.calculation_mode=='HYBRID':self.hybrid_entry_confirmation=confirmation
            elif self.entry_confirmation.pending is not None:self.pending_underlying_flip=None
            if reentry and gate_mode!='underlying_trend_premium_flip':
                self.pending_underlying_flip=at;self.pending_underlying_flip_source_at=reentry['closed_at'];self.entry_confirmation.clear()
                if self.calculation_mode=='HYBRID':self.hybrid_entry_confirmation=reentry
        else:
            gate=HybridConfirmation(size);gate.arm('LONG',at,('premium',self.hybrid_sequence,at),source_at=unit['closed_at'])
            self.premium_confirmation=gate.confirm(unit,direction,result['st'])
            if gate_mode=='underlying_trend_premium_flip':
                confirmation=self.premium_entry_confirmation.confirm(unit,direction,result['st']) or reentry
                if confirmation and self.under_result:
                    self.pending_underlying_flip=at;self.pending_underlying_flip_source_at=confirmation['closed_at']
                    if self.calculation_mode=='HYBRID':self.hybrid_entry_confirmation=confirmation
        if self.pending_underlying_flip is None:return []
        side='CE' if self.under_result['direction']<0 else 'PE'
        if not hasattr(self,'contract') or self.contract.get('option_type')!=side:return [dict(action='SELECT',side=side,timestamp=at)]
        if gate_mode!='underlying_flip' and (not self.premium_confirmation or self.premium_confirmation['available_at']<self.pending_underlying_flip):return []
        action=self.selected_gate_entry()
        return [action] if action else []

    def manual_entry(self,direction,at):
        self.band.consume_entry()
        if self.position:raise ValueError('An owned position already exists')
        if direction not in ('CE','PE') or not hasattr(self,'contract') or self.contract.get('option_type')!=direction:raise ValueError('Prepare the exact Call or Put before manual entry')
        positive(at,'Manual entry timestamp');self.entry_reset_at=at;self.pending_underlying_flip=None;self.band.retest=None
        self.position=dict(self.contract,side=direction,entry_timestamp=at,manual_override=True)
        return dict(action='BUY',timestamp=at,position=dict(self.position),manual_override=True)

    def selected_gate_entry(self):
        if sma_only.enabled(self.config):return sma_only.entry(self,True)
        at=self.pending_underlying_flip
        if not getattr(self,'entry_quotes_ready',True):return None
        mode=self.config['entry_gate']
        if self.position or at is None or not self.under_result or not hasattr(self,'contract'):return None
        if mode=='underlying_flip':
            premium_at=at
        elif not self.premium_result or self.premium_result['direction']>=0:return None
        elif self.hybrid_active:
            if not self.premium_confirmation or self.premium_confirmation['available_at']<at:return None
            if self.premium_confirmation.get('closed_at',self.premium_confirmation['available_at'])<getattr(self,'pending_underlying_flip_source_at',at):return None
            premium_at=self.premium_confirmation['available_at']
        else:
            premium_at=self.last_time.get('premium',-1)
            if premium_at<at:return None
        side='CE' if self.under_result['direction']<0 else 'PE'
        if self.contract['option_type']!=side:return None
        if not self.band.entry_ready(side,self.config,getattr(self,'entry_observation_at',at)):self.pending_underlying_flip=None;return None
        entry_at=max(at,premium_at)
        self.band.consume_entry()
        self.position=dict(self.contract,side=side,entry_timestamp=entry_at,signal_timestamp=at,underlying_flip_timestamp=at if mode!='underlying_trend_premium_flip' else None,entry_gate=mode)
        self.pending_underlying_flip=None
        return dict(action='BUY',timestamp=entry_at,position=dict(self.position),**(dict(confirmation=self.hybrid_entry_confirmation) if self.calculation_mode=='HYBRID' and getattr(self,'hybrid_entry_confirmation',None) else {}))
    def exit(self,at,reason):
        self.band.consume_entry()
        self.entry_reset_at=at
        self.sma_only_pending=None
        self.band.retest=None;self.entry_confirmation.clear();self.pending_underlying_flip=None;self.pending_underlying_flip_source_at=None;self.premium_confirmation=None
        if self.premium_entry_confirmation:self.premium_entry_confirmation.clear()
        position=self.position;self.position=None
        return [dict(action='SELL',timestamp=at,reason=reason,position=position)]
