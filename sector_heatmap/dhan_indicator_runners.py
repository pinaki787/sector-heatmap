"""Dhan runners reuse the application's completed-candle signal functions."""
from datetime import datetime
import math
from .dhan_strategy_service import DhanRsiRunner,rsi_config
from .dhan_execution import IST
from strategies.ema_crossover.runner import TIMEFRAMES
from .kama_strategy import kama_v6_signal

KAMA_KEYS=('kama_length','fast_length','slow_length','minimum_efficiency','slope_lookback','minimum_slope_atr','breakout_bars','cooldown_bars','allow_reclaims','entry_session','squareoff_session')


def configuration(payload):
    strategy=payload.get('strategy')
    if strategy not in ('EMA_BAND_V1','KAMA_V6'):raise ValueError('Explicit EMA Band or KAMA strategy required.')
    if payload.get('execution_route')!='OPTIONS':raise ValueError('This Dhan strategy route supports explicitly selected bought options.')
    result=rsi_config(dict(payload,strategy='RSI_BASED_EMA_V1',rsi_length=14,ma_length=14,ma_type='SMA'))
    result.update(strategy=strategy,execution_route='OPTIONS',entry_session='0915-1510',squareoff_session='1515-1530')
    defaults=dict(ema_length=21,slope_lookback=8,minimum_slope_atr=.10,kama_length=10,fast_length=2,slow_length=30,minimum_efficiency=.35,breakout_bars=5,cooldown_bars=2,allow_reclaims=True)
    for key,default in defaults.items():
        raw=payload.get(key,default)
        if isinstance(default,bool):
            if not isinstance(raw,bool):raise ValueError('KAMA reclaim setting must be boolean.')
            result[key]=raw
        elif isinstance(default,int):
            value=int(raw)
            if isinstance(raw,bool) or str(raw)!=str(value) or not (0 if key=='cooldown_bars' else 1)<=value<=500:
                raise ValueError('Invalid whole-number '+key)
            result[key]=value
        else:
            value=float(raw)
            if not math.isfinite(value) or value<0 or key=='minimum_efficiency' and value>1:raise ValueError('Invalid '+key)
            result[key]=value
    kama_v6_signal([],**{k:result[k] for k in KAMA_KEYS})
    for key in ('invalidation','idea_risk_limit','stop_loss_pct','target_profit_pct','profit_protection_pct'):
        raw=payload.get(key)
        value=None if raw in (None,'',0) else float(raw)
        if value is not None and (not math.isfinite(value) or value<=0 or key in ('stop_loss_pct','profit_protection_pct') and value>=100):
            raise ValueError('Invalid '+key)
        result[key]=value
    raw=payload.get('resistance_volume_exit',False)
    if not isinstance(raw,bool):raise ValueError('Resistance volume exit must be boolean.')
    result['resistance_volume_exit']=raw
    result['resistance_volume_lookback']=int(payload.get('resistance_volume_lookback') or 20)
    result['resistance_volume_multiple']=float(payload.get('resistance_volume_multiple') or 1.5)
    if not 2<=result['resistance_volume_lookback']<=500 or not math.isfinite(result['resistance_volume_multiple']) or result['resistance_volume_multiple']<=0:
        raise ValueError('Invalid resistance volume parameters.')
    if result.get('idea_risk_limit'):
        result['max_premium']=min(result['max_premium'],result['idea_risk_limit']) if result.get('max_premium') else result['idea_risk_limit']
    result['label']='EMA Band' if strategy=='EMA_BAND_V1' else 'KAMA V6'
    return result


class IndicatorRunner(DhanRsiRunner):
    configure=staticmethod(configuration)
    runtime_revision='dhan-band-kama-completed-v1'

    def signal_key(self,sig):
        c=self.state['config']
        return c['strategy']+':'+c['underlying']+':'+c['timeframe']+':'+str(sig['timestamp'])

    def signal(self):
        c=self.state['config'];seconds=TIMEFRAMES[c['timeframe']]
        rows=[r for r in self.adapter.candles(c) if not r.get('is_forming') and r['timestamp']+seconds<=self.clock()]
        if not rows:raise ValueError('Completed Dhan candles unavailable.')
        position=self.state.get('position')
        if c['strategy']=='EMA_BAND_V1':
            from .web import ema_band_strategy_signal,ema_band_exit_signal,ema_band_resistance_volume_exit
            value=ema_band_strategy_signal(rows,c['ema_length'],c['entry_session'],c['slope_lookback'],c['minimum_slope_atr'])
            exit_value=ema_band_exit_signal(rows,c['ema_length'])
            resistance=ema_band_resistance_volume_exit(rows,c['resistance_volume_lookback'],c['resistance_volume_multiple']) if c.get('resistance_volume_exit') and position and position['direction']=='BULLISH' else {'exit':False}
            sig=dict(value,cross_direction=value.get('direction'),exit_signal=exit_value['exit'] or resistance['exit'],resistance_volume_exit=resistance['exit'])
        else:
            sign=1 if position and position['direction']=='BULLISH' else -1 if position else 0
            exits=self.state.get('kama_exit_times',{})
            def prior(direction):
                indices=[i for i,r in enumerate(rows) if r['timestamp']<=exits.get(direction,-1)]
                return indices[-1] if indices else None
            value=kama_v6_signal(rows,position=sign,last_long_exit_bar=prior('BULLISH'),
                                last_short_exit_bar=prior('BEARISH'),**{k:c[k] for k in KAMA_KEYS})
            action=value['action'];direction={'ENTER_LONG':'BULLISH','ENTER_SHORT':'BEARISH'}.get(action)
            sig=dict(value,cross_direction=direction,direction=direction,exit_signal=action in ('EXIT_LONG','EXIT_SHORT','SQUARE_OFF'))
        sig.update(timestamp=rows[-1]['timestamp'],close=rows[-1]['close'])
        self.state['last_signal']=sig
        return sig

    def fresh_cross(self,sig):
        interval=TIMEFRAMES[self.state['config']['timeframe']]
        closed=sig['timestamp']+interval;previous=self.state.get('last_processed_bar')
        if previous is not None and sig['timestamp']<=previous:return False
        self.state['last_processed_bar']=sig['timestamp'];self.save()
        fresh=self.state.get('eligible_since',self.state.get('started_at',self.clock()))<closed<=self.clock() and self.clock()-closed<=interval
        return fresh and bool(self.state.get('position') or sig.get('cross_direction'))

    def exit_signal(self,sig,direction):return bool(sig.get('exit_signal'))
    def exit_reason_for(self,sig,position):
        invalidation=self.state['config'].get('invalidation')
        if invalidation and (sig['close']<=invalidation if position['direction']=='BULLISH' else sig['close']>=invalidation):
            return 'UNDERLYING_INVALIDATION'
        if sig.get('resistance_volume_exit'):return 'RESISTANCE_VOLUME_EXIT'
        return self.state['config']['strategy']+'_CLOSE_EXIT' if self.exit_signal(sig,position['direction']) else None

    def validate_entry_authorization(self, position):
        super().validate_entry_authorization(position)
        stop=self.state['config'].get('invalidation')
        spot=self.state['last_signal']['close']
        if stop and not (stop<spot if position['direction']=='BULLISH' else stop>spot):
            raise ValueError('Underlying invalidation must be on the loss side of the signal.')


    def complete_pending(self,filled,price):
        before=self.state.get('position')
        super().complete_pending(filled,price)
        if before and not self.state.get('position') and self.state['config']['strategy']=='KAMA_V6':
            self.state.setdefault('kama_exit_times',{})[before['direction']]=(self.state.get('last_signal') or {}).get('timestamp',self.clock())
            self.save()

    def step(self):
        with self.lock:
            c=self.state.get('config') or {}
            position=self.state.get('position')
            if self.state.get('running') and c and position and not self.state.get('pending') and not position.get('exit_requested') and any(c.get(k) for k in ('stop_loss_pct','target_profit_pct','profit_protection_pct')):
                quote=self.adapter.quote(position['symbol'])
                bid=float(quote['bid']);entry=position['entry_price']
                stop=c.get('stop_loss_pct');target=c.get('target_profit_pct');protect=c.get('profit_protection_pct')
                protection=None
                if protect:
                    from .web import ema_profit_protection
                    protection=ema_profit_protection(entry,bid,protect,position.get('profit_peak_price'),position.get('profit_protection_stop'))
                    position.update(profit_peak_price=protection['peak_price'],profit_protection_stop=protection['stop_price'],profit_protection_stage=protection['stage'])
                reason=('PREMIUM_STOP' if stop and bid<=entry*(1-stop/100) else
                        'PREMIUM_TARGET' if target and bid>=entry*(1+target/100) else
                        'PREMIUM_PROFIT_PROTECTION' if protection and protection['exit'] else None)
                if reason:position.update(exit_requested=True,exit_reason=reason)
                self.save()
            if self.state.get('running') and c:
                now=datetime.fromtimestamp(self.clock(),IST)
                if now.hour*60+now.minute>=15*60+15:
                    self.state['accepting_entries']=False
                    if self.state.get('position'):
                        self.state['position'].update(exit_requested=True,exit_reason='INDIAN_SESSION_SQUARE_OFF')
                        self.save()
        return super().step()


class BandRunner(IndicatorRunner):
    strategy_id='EMA_BAND_V1'
    entry_reason='EMA_BAND_CLOSE_ENTRY'
    exit_reason='EMA_BAND_CLOSE_EXIT'
    activation_name='EMA BAND'
    signal_policy='COMPLETED_EMA_BAND_BODY_AND_MIDPOINT_ENTRY__INSIDE_BAND_EXIT'

class KamaRunner(IndicatorRunner):
    strategy_id='KAMA_V6'
    entry_reason='KAMA_CLOSE_ENTRY'
    exit_reason='KAMA_CLOSE_EXIT'
    activation_name='KAMA V6'
    signal_policy='COMPLETED_KAMA_V6_ONLY'
