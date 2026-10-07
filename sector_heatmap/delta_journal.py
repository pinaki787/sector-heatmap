"""Event-time public indicator evidence; never a trading decision or backfill."""
import math
from copy import deepcopy
from .delta_signals import delta_rsi_series
from .delta_adx import series as adx_series
from .delta_trailing import atr_value


def snapshot(analysis, settings, observed_at, reason, signal_close=None):
    interval = settings['interval_seconds']
    rows = delta_rsi_series(analysis.get('candles', []), settings['rsi_length'], settings['ma_length'], settings['ma_type'])
    target = signal_close - interval if signal_close is not None else None
    row = next((r for r in rows if r['timestamp'] == target), None) if target is not None else (rows[-1] if rows else None)
    evidence = dict(version=1, observed_at=observed_at, symbol=analysis.get('symbol'), timeframe=settings['resolution'], reason=reason,
                    settings=deepcopy(settings), source='Delta India public REST', price_basis='Underlying completed candle close; traded-contract fills are separate',
                    capture_kind='RECOVERED_HISTORY_OBSERVED_LATER' if signal_close is not None and observed_at-signal_close>30 else 'EVENT_OBSERVATION',
                    candle=None, rsi=None, rsi_ma=None, bollinger=None, transition=None, reversal_price=None)
    if row is None:
        evidence['unavailable']='Requested completed signal candle not available in event observation'
        return evidence
    evidence['candle']={k:row.get(k) for k in ('timestamp','open','high','low','close','volume')}
    evidence['candle'].update(completed=True, is_forming=False, close_time=row['timestamp']+interval)
    evidence['adx']={'period':14,'value':adx_series(analysis.get('candles',[])).get(row['timestamp']),'filter_enabled':bool(settings.get('adx_enabled',False)),'threshold':settings.get('adx_threshold',25),'basis':'Wilder smoothing; completed underlying candles'}
    evidence['momentum']={'enabled':bool(settings.get('momentum_enabled',False)),'evidence':deepcopy(row.get('momentum'))}
    evidence.update(rsi=row.get('rsi'),rsi_ma=row.get('rsi_ma'),observed_cross=row.get('cross_direction'),touch_evidence=row.get('touch_evidence'))
    history=[r for r in rows if r['timestamp']<=row['timestamp']]
    evidence['recent_completed_candles']=[{k:r.get(k) for k in ('timestamp','open','high','low','close','volume','rsi','rsi_ma')} for r in history[-15:]]
    try:
        value,stamp=atr_value(history)
        prior=history[-2];tr=max(row['high']-row['low'],abs(row['high']-prior['close']),abs(row['low']-prior['close']))
        evidence['atr']={'period':14,'value':value,'true_range':tr,'candle_timestamp':stamp,'basis':'Wilder ATR of completed underlying candles'}
    except ValueError as error:evidence['atr']={'period':14,'value':None,'unavailable':str(error)}
    cross=row.get('cross_direction')
    evidence['transition']='MANUAL_NO_ENTRY_SIGNAL' if reason=='MANUAL_DISCRETIONARY' else ('BULLISH_TO_BEARISH' if cross=='BEARISH' else 'BEARISH_TO_BULLISH' if cross=='BULLISH' else None)
    evidence['reversal_price']=row['close'] if cross and reason!='MANUAL_DISCRETIONARY' else None
    evidence['signal_price']=row['close'] if signal_close is not None and reason!='MANUAL_DISCRETIONARY' else None
    bb=settings.get('journal_bb')
    if bb and isinstance(bb.get('length'),int) and not isinstance(bb['length'],bool) and 2<=bb['length']<=200 and isinstance(bb.get('deviation'),(int,float)) and math.isfinite(bb['deviation']) and 0<bb['deviation']<=10:
        closes=[r['close'] for r in rows if r['timestamp']<=row['timestamp']][-bb['length']:]
        band=dict(length=bb['length'],deviation=bb['deviation'],basis='Close SMA ± population standard deviation',upper=None,middle=None,lower=None)
        if len(closes)==bb['length']:
            mean=sum(closes)/len(closes);std=math.sqrt(sum((c-mean)**2 for c in closes)/len(closes));band.update(middle=mean,upper=mean+bb['deviation']*std,lower=mean-bb['deviation']*std,width_percent=100*2*bb['deviation']*std/mean if mean else None,percent_b=(row['close']-(mean-bb['deviation']*std))/(2*bb['deviation']*std) if std else None)
        evidence['bollinger']=band
    else:evidence['bollinger_unavailable']='Chart Bollinger settings not recorded; no assumed settings'
    forming=[c for c in analysis.get('candles',[]) if c.get('is_forming') or c['timestamp']+interval>observed_at]
    evidence['forming_candle_at_observation']={k:forming[-1].get(k) for k in ('timestamp','open','high','low','close','volume')}|dict(completed=False,is_forming=True) if forming else None
    return evidence
