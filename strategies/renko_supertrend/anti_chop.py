"""Optional, completed-host-candle, entry-only anti-chop checklist.
Independent ATR14 / SMA20 and EMA20/50 state; never alters exit decisions.
"""
import math
REVISION='host-timeframe-anti-chop-v4-combination'
DEFAULTS=dict(anti_chop_enabled=False,anti_chop_combination="All",anti_chop_role="Filter",anti_chop_mode="Adaptive",anti_chop_atr_length=14,anti_chop_atr_average_length=20,anti_chop_ema_fast_length=20,anti_chop_ema_slow_length=50,anti_chop_adaptive_window=200,anti_chop_slope_percentile=60.,anti_chop_gap_percentile=60.,anti_chop_overlap_percentile=40.,anti_chop_slope_bars=3,anti_chop_slope_atr=.15,
              anti_chop_gap_atr=.20,anti_chop_cross_bars=6,
              anti_chop_structure_bars=3,anti_chop_overlap_percent=50.)

def settings(payload):
    c={k:payload.get(k,v) for k,v in DEFAULTS.items()}
    if not isinstance(c['anti_chop_enabled'],bool):raise ValueError('Anti-chop switch must be boolean.')
    if c['anti_chop_combination'] not in ('All','Trend'):raise ValueError('Choose All or Trend anti-chop confirmation.')
    if c['anti_chop_role'] not in ('Filter','Entry'):raise ValueError('Choose Filter or Entry anti-chop role.')
    if c['anti_chop_mode'] not in ('Adaptive','Manual'):raise ValueError('Choose Adaptive or Manual anti-chop mode.')
    for k,low,high in [('anti_chop_atr_length',1,100),('anti_chop_atr_average_length',1,200),('anti_chop_ema_fast_length',1,500),('anti_chop_ema_slow_length',2,1000),('anti_chop_adaptive_window',20,2000),('anti_chop_slope_bars',1,50),('anti_chop_cross_bars',1,100),('anti_chop_structure_bars',2,20)]:
        v=c[k]
        try:
            n=int(v)
            if isinstance(v,bool) or float(v)!=n or not low<=n<=high:raise ValueError
        except (TypeError,ValueError,OverflowError):raise ValueError('Anti-chop candle counts are outside their allowed ranges.') from None
        c[k]=n
    for k,low,high in [('anti_chop_slope_percentile',1,99),('anti_chop_gap_percentile',1,99),('anti_chop_overlap_percentile',1,99),('anti_chop_slope_atr',0,10),('anti_chop_gap_atr',0,10),('anti_chop_overlap_percent',0,100)]:
        v=c[k]
        try:n=float(v)
        except (TypeError,ValueError,OverflowError):raise ValueError('Anti-chop thresholds must be finite numbers.') from None
        if isinstance(v,bool) or not math.isfinite(n) or not low<=n<=high:raise ValueError('Anti-chop threshold is outside its allowed range.')
        c[k]=n
    if c['anti_chop_ema_fast_length']>=c['anti_chop_ema_slow_length']:raise ValueError('Anti-chop fast EMA period must be below its slow EMA period.')
    return c

def standalone_rules(payload):
    if payload.get('anti_chop_enabled') and payload.get('anti_chop_role')=='Entry':
        from . import indicator_families
        c=indicator_families.apply(payload)
        keys=('supertrend_enabled','ema_fast_enabled','ema_slow_enabled','ema_third_enabled','ema_widening_enabled','rsi_slope_enabled','rsi_level_enabled','retest_enabled','manual_trend_enabled','calibrated_enabled','higher_timeframe_enabled','market_structure_enabled','rsi_htf_1_enabled','rsi_htf_2_enabled','rsi_htf_3_enabled','zone_entry_enabled','ema_proximity_enabled','ema_momentum_enabled','use_adx')
        if any(c.get(k,False) for k in keys):raise ValueError('Standalone anti-chop entries require other entry rules off; EMA exits may remain enabled.')

def compatible(payload):
    if payload.get('anti_chop_enabled') and payload.get('intrabar_entries'):
        raise ValueError('Anti-chop uses completed candles; turn off intrabar entries before enabling it.')

def observe(state,candle,config,direction,seconds=300):
    cfg=settings(config)
    if not cfg['anti_chop_enabled']:return dict(enabled=False,allowed=True,revision=REVISION)
    compatible({**config,'timeframe':config.get('timeframe','5 minutes')})
    if not isinstance(seconds,(int,float)) or seconds<=0:raise ValueError('A verified host candle interval is required.')
    if candle.get('is_forming') or candle.get('provisional'):
        return dict(enabled=True,allowed=False,ready=False,checks=[],reason='Waiting for a completed host candle.',revision=REVISION)
    s=state.setdefault('anti_chop',{})
    t=candle['timestamp'];last=s.get('previous')
    if last and t<=last['timestamp']:raise ValueError('Anti-chop candles must be strictly chronological.')
    close=candle['close'];high=candle['high'];low=candle['low']
    if not all(isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x) and x>0 for x in (close,high,low)) or high<max(close,low):raise ValueError('Invalid anti-chop OHLC.')
    for key,period in [('ema20',cfg['anti_chop_ema_fast_length']),('ema50',cfg['anti_chop_ema_slow_length'])]:
        old=s.get(key);s[key]=close if old is None else old+2/(period+1)*(close-old)
    tr=high-low if last is None else max(high-low,abs(high-last['close']),abs(low-last['close']))
    seed=s.setdefault('tr_seed',[])
    if s.get('atr14') is None:
        seed.append(tr)
        if len(seed)==cfg['anti_chop_atr_length']:s['atr14']=sum(seed)/cfg['anti_chop_atr_length']
    else:s['atr14']+=(tr-s['atr14'])/cfg['anti_chop_atr_length']
    atr=s.get('atr14');av=s.setdefault('atr_values',[])
    if atr is not None:av.append(atr);del av[:-cfg['anti_chop_atr_average_length']]
    mean=sum(av)/cfg['anti_chop_atr_average_length'] if len(av)==cfg['anti_chop_atr_average_length'] else None
    e=s.setdefault('ema20_values',[]);e.append(s['ema20']);del e[:-(cfg['anti_chop_slope_bars']+1)]
    sign=1 if s['ema20']>s['ema50'] else -1
    crosses=s.setdefault('crosses',[]);crosses.append(s.get('sign') is None or sign!=s.get('sign'));del crosses[:-cfg['anti_chop_cross_bars']];s['sign']=sign
    rows=s.setdefault('structure_rows',[])
    if last and t-last['timestamp']!=seconds:rows.clear()
    rows.append({k:candle[k] for k in ('timestamp','high','low','close')});del rows[:-cfg['anti_chop_structure_bars']]
    s['previous']={k:candle[k] for k in ('timestamp','close')};s['count']=s.get('count',0)+1
    ready=s['count']>=max(cfg['anti_chop_ema_slow_length'],cfg['anti_chop_atr_length']+cfg['anti_chop_atr_average_length']-1,cfg['anti_chop_cross_bars'],cfg['anti_chop_slope_bars']+1) and atr is not None and atr>0 and mean is not None
    slope=(e[-1]-e[0])/atr if ready and len(e)==cfg['anti_chop_slope_bars']+1 else None
    gap=abs(s['ema20']-s['ema50'])/atr if ready else None
    if cfg['anti_chop_role']=='Entry':direction='BULLISH' if s['ema20']>s['ema50'] else 'BEARISH' if s['ema20']<s['ema50'] else 'NEUTRAL'
    bull=direction=='BULLISH';bear=direction=='BEARISH'
    overlaps=[];structure=len(rows)==cfg['anti_chop_structure_bars'] and (bull or bear)
    for a,b in zip(rows,rows[1:]):
        width=min(a['high']-a['low'],b['high']-b['low'])
        overlaps.append(max(0,min(a['high'],b['high'])-max(a['low'],b['low']))/width if width>0 else math.inf)
        structure=structure and ((bull and b['high']>a['high'] and b['low']>a['low']) or (bear and b['high']<a['high'] and b['low']<a['low']))
    overlap=sum(overlaps)/len(overlaps) if overlaps and all(math.isfinite(x) for x in overlaps) else None
    history=s.setdefault('adaptive_history',[]);window=cfg['anti_chop_adaptive_window']
    prior=history[-window:];adaptive=cfg['anti_chop_mode']=='Adaptive'
    calibration_ready=len(prior)>=window
    def percentile(values,p):
        ordered=sorted(values);index=(len(ordered)-1)*p/100;lower=int(index);upper=min(lower+1,len(ordered)-1)
        return ordered[lower]+(ordered[upper]-ordered[lower])*(index-lower)
    slope_limit=percentile([x[0] for x in prior],cfg['anti_chop_slope_percentile']) if adaptive and calibration_ready else cfg['anti_chop_slope_atr'] if not adaptive else None
    gap_limit=percentile([x[1] for x in prior],cfg['anti_chop_gap_percentile']) if adaptive and calibration_ready else cfg['anti_chop_gap_atr'] if not adaptive else None
    overlap_limit=percentile([x[2] for x in prior],cfg['anti_chop_overlap_percentile']) if adaptive and calibration_ready else cfg['anti_chop_overlap_percent'] if not adaptive else None
    base_ready=ready;ready=bool(ready and (not adaptive or calibration_ready))
    slope_ok=ready and ((bull and slope>=slope_limit and slope>0) or (bear and slope<=-slope_limit and slope<0))
    gap_ok=ready and gap>=gap_limit and not any(crosses) and ((bull and sign==1) or (bear and sign==-1))
    fast=cfg['anti_chop_ema_fast_length'];slow=cfg['anti_chop_ema_slow_length'];period=cfg['anti_chop_atr_length'];average=cfg['anti_chop_atr_average_length']
    checks=[dict(key='atr',label=f'ATR{period} above its {average}-bar average',passed=bool(ready and atr>mean),observed=atr,reference=mean),
            dict(key='slope',label=f'EMA{fast} directional slope',passed=bool(slope_ok),observed=slope,required=slope_limit),
            dict(key='separation',label=f'EMA{fast}/{slow} separation; no recent cross',passed=bool(gap_ok),observed=gap,required=gap_limit,no_cross=not any(crosses)),
            dict(key='structure',label='Directional candles and limited overlap',passed=bool(ready and structure and overlap is not None and overlap*100<=overlap_limit),observed=None if overlap is None else overlap*100,required=overlap_limit)]
    # Current candle may inform the NEXT candle's calibration, never its own thresholds.
    if base_ready and slope is not None and gap is not None and overlap is not None:
        history.append([abs(slope),gap,overlap*100]);del history[:-window]
    allowed,checks=combine(checks,ready,cfg['anti_chop_combination'])
    failed=[x['key'] for x in checks if not x['passed'] and x.get('mandatory',True)]
    return dict(enabled=True,allowed=allowed,ready=ready,checks=checks,combination=cfg['anti_chop_combination'],role=cfg['anti_chop_role'],mode=cfg['anti_chop_mode'],calibration=dict(samples=len(prior),required=window,ready=calibration_ready),thresholds=dict(slope_atr=slope_limit,gap_atr=gap_limit,overlap_percent=overlap_limit),periods=dict(atr=period,atr_average=average,ema_fast=fast,ema_slow=slow),direction=direction,ema20=s['ema20'],ema50=s['ema50'],atr14=atr,atr_average=mean,last_completed_at=t,revision=REVISION,reason=('Trend checks pass: slope, separation and either ATR or structure.' if cfg['anti_chop_combination']=='Trend' else 'All four anti-chop checks pass.') if allowed else ('Adaptive calibration warming up: '+str(len(prior))+'/'+str(window)+' prior observations.') if adaptive and not calibration_ready else 'Anti-chop warmup incomplete.' if not ready else 'Waiting for anti-chop: '+', '.join(failed)+'.')

def apply(entry,gate):
    entry['anti_chop']=gate
    if not gate['allowed']:
        entry.update(entry_qualified=False,entry_direction=None,entry_buy_signal=False,entry_sell_signal=False,entry_diagnostic='WAITING_ANTI_CHOP')


def generate_entry(entry,gate,state):
    """Emit once per qualifying episode; exits remain independently configured."""
    direction=gate.get('direction')
    qualified=bool(gate.get('ready') and gate.get('allowed') and direction in ('BULLISH','BEARISH'))
    event=direction if qualified and state.get('anti_chop_qualified')!=direction else None
    state['anti_chop_qualified']=direction if qualified else None
    entry.update(selected_direction=direction,entry_qualified=qualified,entry_direction=event,
                 entry_buy_signal=event=='BULLISH',entry_sell_signal=event=='BEARISH',
                 entry_diagnostic='ANTI_CHOP_ENTRY' if event else 'ANTI_CHOP_HOLD' if qualified else 'WAITING_ANTI_CHOP')
    entry['anti_chop']=gate


def combine(checks,ready,combination):
    """Keep actual observations; explicitly mark the two alternative supports."""
    rows=[dict(x) for x in checks]
    by_key={x['key']:x for x in rows}
    if combination=='Trend':
        for key in ('atr','structure'):by_key[key]['mandatory']=False
        support=bool(by_key['atr']['passed'] or by_key['structure']['passed'])
        rows.append(dict(key='confirmation',label='Either ATR or candle structure',passed=bool(ready and support),mandatory=True))
    return bool(ready and all(x['passed'] for x in rows if x.get('mandatory',True))),rows
