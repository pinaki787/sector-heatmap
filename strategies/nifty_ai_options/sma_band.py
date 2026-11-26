"""SMA30 High/Low arithmetic over caller-confirmed broker candles.

No broker access or order logic. Consumers choose timeframe and series explicitly.
"""
from collections import deque
import math
ENTRY_POLICY_REVISION="sma-retest-required-v1"


class SMA30Band:
    PERIOD = 30

    def __init__(self):
        self.rows = deque(maxlen=self.PERIOD)
        self.timestamp = None
        self.value = None

    def update(self, timestamp, high, low, close):
        values = (timestamp, high, low, close)
        if any(isinstance(v, bool) or not isinstance(v, (int, float))
               or not math.isfinite(v) or v <= 0 for v in values):
            raise ValueError("Finite positive timestamp and broker High/Low/Close required")
        if low > close or close > high:
            raise ValueError("Broker candle Low <= Close <= High required")
        if self.timestamp is not None and timestamp <= self.timestamp:
            raise ValueError("Duplicate/out-of-order SMA30 band candle")
        self.rows.append((timestamp, high, low, close))
        self.timestamp = timestamp
        if len(self.rows) < self.PERIOD:
            return None
        # Re-sum the bounded 30-candle window to avoid long-running sum drift.
        # The cached value is reused between completed candles, including on LTPs.
        self.value = {
            "timestamp": timestamp,
            "upper": math.fsum(row[1] for row in self.rows) / self.PERIOD,
            "lower": math.fsum(row[2] for row in self.rows) / self.PERIOD,
            "close": close,
            "period": self.PERIOD,
        }
        return dict(self.value)

    def snapshot(self):
        return dict(self.value) if self.value is not None else None


class MovingBand:
    """SMA uses a rolling window; EMA seeds with that same period's simple mean."""
    def __init__(self,kind,period):
        if kind not in ('SMA','EMA') or isinstance(period,bool) or not isinstance(period,int) or not 1<=period<=500:
            raise ValueError('Band period must be a whole number from 1 to 500')
        self.kind=kind;self.period=period;self.rows=deque(maxlen=period)
        self.timestamp=None;self.value=None
    def update(self,at,high,low,close):
        if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<=0 for v in (at,high,low,close)) or not low<=close<=high:
            raise ValueError('Valid completed broker High/Low/Close required')
        if self.timestamp is not None and at<=self.timestamp:raise ValueError('Duplicate/out-of-order band candle')
        self.rows.append((high,low));self.timestamp=at
        if len(self.rows)<self.period:return None
        if self.kind=='EMA' and self.value:
            alpha=2/(self.period+1);upper=alpha*high+(1-alpha)*self.value['upper'];lower=alpha*low+(1-alpha)*self.value['lower']
        else:upper=math.fsum(r[0] for r in self.rows)/self.period;lower=math.fsum(r[1] for r in self.rows)/self.period
        self.value=dict(timestamp=at,upper=upper,lower=lower,close=close,period=self.period,kind=self.kind)
        return dict(self.value)

def retain_broker_ohlc(normalized,raw):
    """Attach only consistent real provider OHLC; never fabricate wick prices."""
    sources={}
    for r in raw:
        if isinstance(r,(tuple,list)) and len(r)>=5:sources.setdefault(r[0],[]).append(r)
    result=[]
    for row in normalized:
        matches=sources.get(row[0],[]);valid=[]
        for r in matches:
            if all(not isinstance(x,bool) and isinstance(x,(int,float)) and math.isfinite(x) and x>0 for x in r[1:5]) and r[3]<=min(r[1],r[4])<=max(r[1],r[4])<=r[2]:valid.append(tuple(r[1:5]))
        if matches and len(valid)==len(matches) and len(set(valid))==1:result.append([row[0],*valid[0],row[5] if len(row)>5 else None])
        else:result.append(row)
    return result

class BandPolicy:
    def __init__(self,config):
        self.signature=None;self.states={};self.history={};self.close=None;self.error=None;self.retest=None;self.retest_band=None;self.entry_retest=None;self.configure(config)
    def configure(self,config):
        specs=[]
        for kind in ('SMA','EMA'):
            key=kind.lower();period=config.get(key+'_band_period',30)
            if isinstance(period,bool) or not isinstance(period,int) or not 1<=period<=500:raise ValueError(kind+' band period must be a whole number from 1 to 500')
            if any(not isinstance(config.get(key+'_band_'+use,False),bool) for use in ('entry','exit')):raise ValueError('Band switches must be boolean')
            if config.get(key+'_band_entry') or config.get(key+'_band_exit'):specs.append((kind,period,config.get(key+'_band_entry',False),config.get(key+'_band_exit',False)))
        if not isinstance(config.get('sma_retest_required',True),bool):raise ValueError('SMA retest switch must be boolean')
        signature=(config.get('timeframe'),config.get('band_price_basis','underlying'),config.get('band_symbol'),tuple(specs),config.get('sma_retest_required',True))
        if signature!=self.signature:
            self.retest=None;self.retest_band=None;self.entry_retest=None;self.signature=signature;self.states={kind:MovingBand(kind,period) for kind,period,_,_ in specs};self.history={kind:[] for kind in self.states};self.error=None
        self.specs=specs
    def observe(self,event,config):
        self.configure(config)
        if not self.states:return False
        kind=event.get('series','underlying') if event['kind']=='price' else event['kind']
        if kind!=config.get('band_price_basis','underlying'):return False
        self.close=event['close']
        if event['kind']=='price':return False
        at=event['timestamp']
        if event.get('closed') is False:return False
        self.entry_retest=None
        self.retest_band=dict(self.states['SMA'].value) if 'SMA' in self.states and self.states['SMA'].value else None
        try:
            for name,state in self.states.items():
                value=state.update(at,event.get('high'),event.get('low'),event['close'])
                if value:self.history[name].append(dict(value,time=event.get('closed_at',at+config['timeframe']*60)))
                self.history[name]=self.history[name][-2000:]
            self.error=None
        except ValueError as error:
            self.error=str(error)
            self.states={name:MovingBand(name,period) for name,period,_,_ in self.specs};self.history={name:[] for name in self.states}
        return True
    def reentry(self,event,config,result,*,flat=True,not_before=0):
        """A retest needs the immediately following completed directional candle.
        Uses real OHLC and the previously completed SMA band; no proximity estimate.
        Price updates cannot supply the follow-up candle or repeat a consumed setup.
        """
        if not flat or not config.get('sma_band_entry') or not config.get('sma_retest_required',True):
            self.retest=None;return None
        if event.get('kind')!=config.get('band_price_basis','underlying'):return None
        prior=self.retest;self.retest=None
        sma_only=config.get('supertrend_enabled',True) is False
        if (not result and not sma_only) or event.get('closed') is False or event.get('source_basis')!='PROVIDER_CONFIRMED_CLOSE' or event.get('body_available') is not True or not self.retest_band:return None
        values=[event.get(k) for k in ('open','high','low','close','timestamp')]
        if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<=0 for v in values):return None
        opening,high,low,close,at=values
        if not low<=min(opening,close)<=max(opening,close)<=high:return None
        closed=event.get('closed_at',at+config['timeframe']*60);available=event.get('available_at',closed)
        if not at<closed<=available or at<not_before:return None
        if sma_only:
            if prior:side=prior['direction']
            elif config.get('band_price_basis')=='premium':side='LONG'
            elif opening>self.retest_band['upper'] and close<opening:side='LONG'
            elif opening<self.retest_band['lower'] and close>opening:side='SHORT'
            else:return None
        else:side='LONG' if result['direction']<0 else 'SHORT'
        current=self.states.get('SMA')
        value=current.value if current else None
        if not value:return None
        bullish=side=='LONG';line=None if sma_only else result['st']
        if prior and prior['direction']==side and at==prior['closed_at']:
            favorable=close>opening and close>value['upper'] if bullish else close<opening and close<value['lower']
            if favorable and (sma_only or (close>line if bullish else close<line)):
                self.entry_retest=dict(direction=side,timestamp=at,closed_at=closed,available_at=available,expires_at=closed+config['timeframe']*60,retest_at=prior['closed_at'])
                if self.allows(side,config,at=available):
                    return dict(direction=side,closed_at=closed,available_at=available,retest_at=prior['closed_at'],confirmation_basis='SMA_RETEST_FOLLOWUP_CANDLE')
                self.entry_retest=None
        band=self.retest_band
        touched=low<=band['upper'] and high>=band['lower']
        approach=opening>band['upper'] and close<opening if bullish else opening<band['lower'] and close>opening
        if touched and approach:self.retest=dict(direction=side,closed_at=closed)
        return None

    def entry_ready(self,side,config,at=None):
        if not self.allows(side,config):return False
        token=self.entry_retest
        return not config.get('sma_band_entry') or not config.get('sma_retest_required',True) or (at is not None and token['available_at']<=at<token['expires_at'])
    def consume_entry(self):
        self.entry_retest=None;self.retest=None
    def allows(self,side,config,*,at=None):
        self.configure(config)
        if config.get('band_price_basis')=='premium':side='LONG'
        if config.get('sma_band_entry') and config.get('sma_retest_required',True):
            token=self.entry_retest;normalized='LONG' if side in ('LONG','CE') else 'SHORT'
            value=self.states.get('SMA')
            if not token or token['direction']!=normalized or not value or not value.value or token['timestamp']!=value.value['timestamp']:return False
            if at is not None and not token['available_at']<=at<token['expires_at']:return False
        for name,_,entry,_ in self.specs:
            if not entry:continue
            value=self.states[name].value
            if not value or self.close is None:return False
            if side in ('LONG','CE') and not self.close>value['upper']:return False
            if side in ('SHORT','PE') and not self.close<value['lower']:return False
        return True
    def exit_reason(self,position,confirmed_close=None):
        if not position:return None
        for name,_,_,exit_enabled in self.specs:
            value=self.states[name].value
            if not exit_enabled or not value:continue
            side='LONG' if self.signature[1]=='premium' else position['side']
            # Completed closes must cross the far edge; equality and the cloud do not exit.
            # Premium-source bought options retain LONG premium semantics for both CE and PE.
            close=value['close'] if confirmed_close is None else confirmed_close
            adverse=close<value['lower'] if side in ('LONG','CE') else close>value['upper'] if side in ('SHORT','PE') else False
            if adverse:
                return 'OPTIONAL_'+('PREMIUM' if self.signature[1]=='premium' else 'UNDERLYING')+'_'+name+'_BAND'
        return None
    def snapshot(self,config,include_history=False):
        self.configure(config)
        return dict(retest_required=config.get('sma_retest_required',True),entry_policy_revision=ENTRY_POLICY_REVISION,timeframe=config.get('timeframe'),underlying=config.get('band_symbol') if config.get('band_price_basis')=='premium' else config.get('underlying'),price_basis=config.get('band_price_basis','underlying'),error=self.error,
            bands=[dict(kind=name,period=period,entry=entry,exit=exit_enabled,ready=self.states[name].value is not None,
                        value=self.states[name].value,**(dict(points=self.history[name]) if include_history else {})) for name,period,entry,exit_enabled in self.specs])

def observe_band(engine,event):
    completed=engine.band.observe(event,engine.config)
    if engine.config.get('calculation_mode')=='HYBRID' and event['kind'] in ('underlying','premium'):
        size=engine.spot_size if event['kind']=='underlying' else (getattr(engine,'contract',{}) or {}).get('option_brick')
        if not event.get('hybrid_completed_brick') and size and abs(event.get('close',0)-event.get('open',0))>=size:return []

    # An old candle delivered after a fill must not immediately exit that fill.
    unit=event.get('hybrid_completed_brick') if engine.config.get('calculation_mode')=='HYBRID' else None
    if unit and engine.position and unit.get('closed') is True and unit.get('closed_at',0)>engine.position.get('entry_confirmed_at',engine.position.get('entry_timestamp',0)):
        reason=engine.band.exit_reason(engine.position,unit['close'])
        if reason:
            actions=engine.exit(unit['available_at'],reason)
            actions[0]['confirmation']=dict(confirmation_basis='COMPLETED_RENKO_BRICK',closed_at=unit['closed_at'],available_at=unit['available_at'])
            return actions
    if engine.config.get('exit_confirmation_mode')=='RENKO_BRICKS_ONLY':return []
    pending=getattr(engine,'session_band_exit_pending',None)
    if engine.position and (completed and event.get('closed_at',event['timestamp']+engine.config['timeframe']*60)>=engine.position.get('entry_timestamp',0) or pending and event['kind']=='price'):
        reason=pending or engine.band.exit_reason(engine.position)
        if reason:
            engine.session_band_exit_pending=None
            if hasattr(engine,'pending_direction'):engine.pending_direction=None
            return engine.exit(event.get('available_at',event['timestamp']),reason)
    return []

def band_enabled(config):
    return any(config.get(kind+'_band_'+use,False) for kind in ('sma','ema') for use in ('entry','exit'))
