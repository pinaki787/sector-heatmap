"""Bounded, public-data-only Delta futures research. No execution dependencies."""
from bisect import bisect_left, insort
from collections import deque
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from itertools import product
from pathlib import Path
import hashlib, json, math, threading, time, uuid
from .delta_signals import delta_rsi_series, momentum_allows
from . import delta_adx

INTERVALS = {'1m':60, '5m':300, '15m':900, '30m':1800, '1h':3600, '6h':21600, '1d':86400}
MAX_COMBINATIONS = 96
MAX_BARS = 25000
MAX_WORK = 2000000
IST = timezone(timedelta(hours=5, minutes=30))
MODEL = {
    'instrument': 'Underlying perpetual futures research; not ATM-options P&L.',
    'signals': 'Completed underlying candles; existing Wilder RSI / SMA or EMA rules. Optional EMA candle-extreme touch is evaluated only at candle close.',
    'fills': 'Next contiguous candle open, adverse slippage plus half-spread allowance, rounded adversely to the current product tick. OHLC opens are a fill proxy, not historical executable bid/ask.',
    'exits': 'Opposite completed RSI crossover; no reversal on that signal. Force-close at last close of each train/test period with the same costs. Option-premium trailing is not simulated.',
    'capital': 'Fixed contract quantity, no compounding. Entry notional plus fees must fit available equity. Short exposure is modeled symmetrically; no broker margin or liquidation simulation.',
    'costs': 'Fee allowance charged on both fills; include taxes in your allowance. Funding is optional constant adverse notional drag per day, not historical signed funding rates.',
    'metadata': 'Current contract units/tick are used throughout; historical specification changes are not audited. USD quote-equivalent research, no INR conversion.',
    'split': 'Chronological time split; both periods start flat. Earlier candles warm held-out indicators causally. Grid ranked by training net return only; held-out results are not used for ranking.',
    'validation': 'Research only / unvalidated. Repeatedly inspecting held-out results can overfit them. No automatic strategy promotion.',
}


def number(value, name, low, high, integer=False):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or not low <= value <= high or integer and int(value) != value:
        raise ValueError(f'{name} must be {"a whole number" if integer else "a number"} from {low} to {high}.')
    return int(value) if integer else float(value)


def choices(payload, name, default, allowed=None, numeric=None):
    values = payload.get(name, default)
    if not isinstance(values, list) or not 1 <= len(values) <= 8:
        raise ValueError(f'{name}: choose 1–8 distinct values.')
    out = []
    for value in values:
        if numeric: value = number(value, name, *numeric, integer=True)
        elif value not in allowed: raise ValueError(f'Unsupported {name} value.')
        if value not in out: out.append(value)
    return out


def numeric_choices(payload,name,legacy,default,low,high,integer=False):
    values=payload.get(name,[payload.get(legacy,default)])
    if not isinstance(values,list) or not 1<=len(values)<=8:raise ValueError(f'{name}: choose 1–8 distinct values.')
    return list(dict.fromkeys(number(v,name,low,high,integer) for v in values))


def boolean_choices(payload,name,legacy):
    values=payload.get(name,[payload.get(legacy,False)])
    if not isinstance(values,list) or not 1<=len(values)<=2 or any(type(v) is not bool for v in values):raise ValueError(f'{name}: select off, on, or both.')
    return list(dict.fromkeys(values))


def plan(payload, now=None):
    if not isinstance(payload, dict): raise ValueError('Backtest settings must be an object.')
    now = time.time() if now is None else now
    symbol = payload.get('symbol', 'BTCUSD')
    if symbol not in ('BTCUSD', 'ETHUSD'): raise ValueError('Choose BTCUSD or ETHUSD perpetual futures.')
    try:
        start = datetime.strptime(payload['start_date'], '%Y-%m-%d').replace(tzinfo=IST).timestamp()
        end = (datetime.strptime(payload['end_date'], '%Y-%m-%d').replace(tzinfo=IST) + timedelta(days=1)).timestamp()
    except (KeyError, TypeError, ValueError): raise ValueError('Use valid start and end dates (YYYY-MM-DD, IST).') from None
    if start < datetime(2024,1,1,tzinfo=IST).timestamp() or start >= end or end > datetime.fromtimestamp(now,IST).replace(hour=0,minute=0,second=0,microsecond=0).timestamp():
        raise ValueError('Use dates from 2024 onward through yesterday; end date is inclusive in IST.')
    resolutions = choices(payload,'resolutions',['5m'], allowed=INTERVALS)
    rsi = choices(payload,'rsi_lengths',[14],numeric=(2,100))
    ma = choices(payload,'ma_lengths',[14],numeric=(2,100))
    types = choices(payload,'ma_types',['EMA'],allowed=('EMA','SMA'))
    filters = choices(payload,'filters',['BASELINE','EXPANDING','SQUEEZE_RELEASE'],allowed=('BASELINE','EXPANDING','SQUEEZE_RELEASE'))
    # Always include an unfiltered baseline for each RSI/MA/timeframe configuration.
    if 'BASELINE' not in filters: filters.insert(0,'BASELINE')
    lengths = choices(payload,'bb_lengths',[20],numeric=(5,100))
    deviations=numeric_choices(payload,'bb_deviations','bb_deviation',2,.5,4)
    lookbacks=numeric_choices(payload,'squeeze_lookbacks','squeeze_lookback',100,20,500,True)
    percentiles=numeric_choices(payload,'squeeze_percentiles','squeeze_percentile',20,1,50)
    releases=numeric_choices(payload,'release_windows','release_bars',3,1,10,True)
    for flag in ('adx_enabled','momentum_enabled'):
        if not isinstance(payload.get(flag,False),bool):raise ValueError(f'{flag} must be enabled or disabled.')
    adx_modes=boolean_choices(payload,'adx_modes','adx_enabled');momentum_modes=boolean_choices(payload,'momentum_modes','momentum_enabled')
    adx=choices(payload,'adx_thresholds',[25],numeric=(1,99)) if True in adx_modes else [25]
    entry_rules=choices(payload,'entry_rules',[payload.get('entry_rule','CURRENT')],allowed=('CURRENT','CROSS_ONLY'))
    base=dict(symbol=symbol,entry_rule=entry_rules[0],direction=payload.get('direction','BOTH'),adx_enabled=adx_modes[0],momentum_enabled=momentum_modes[0],bb_deviation=deviations[0],squeeze_lookback=lookbacks[0],squeeze_percentile=percentiles[0],release_bars=releases[0])
    if base['direction'] not in ('BOTH','LONG_ONLY','SHORT_ONLY'):raise ValueError('Choose supported entry and direction rules.')
    combinations=[]
    for resolution,rl,ml,mt,entry,adx_on,momentum_on in product(resolutions,rsi,ma,types,entry_rules,adx_modes,momentum_modes):
        for threshold in (adx if adx_on else [25]):
            for candidate in filters:
                variants=[(lengths[0],deviations[0],lookbacks[0],percentiles[0],releases[0])] if candidate=='BASELINE' else product(lengths,deviations,lookbacks if candidate=='SQUEEZE_RELEASE' else lookbacks[:1],percentiles if candidate=='SQUEEZE_RELEASE' else percentiles[:1],releases if candidate=='SQUEEZE_RELEASE' else releases[:1])
                for bl,dev,look,pct,release in variants:
                    combinations.append(dict(base,resolution=resolution,rsi_length=rl,ma_length=ml,ma_type=mt,entry_rule=entry,adx_enabled=adx_on,momentum_enabled=momentum_on,adx_threshold=threshold,filter=candidate,bb_length=bl,bb_deviation=dev,squeeze_lookback=look,squeeze_percentile=pct,release_bars=release))
                    if len(combinations)>MAX_COMBINATIONS:raise ValueError(f'Grid exceeds the {MAX_COMBINATIONS} cap; reduce selected values or filters.')
    if len(combinations)>MAX_COMBINATIONS: raise ValueError(f'{len(combinations)} combinations exceed the {MAX_COMBINATIONS} cap; reduce your grid.')
    warmup=max(300,6*max(rsi+ma),max(lengths)+max(lookbacks)+max(releases)+2)
    ranges={}
    for resolution in resolutions:
        interval=INTERVALS[resolution]
        # Only full bars inside the requested IST date range.
        lo=math.ceil(start/interval)*interval; hi=math.floor(end/interval)*interval
        count=(hi-lo)//interval
        if count < 40: raise ValueError(f'{resolution}: select a longer range (at least 40 full candles).')
        if count>MAX_BARS: raise ValueError(f'{resolution}: {count:,} candles exceed the {MAX_BARS:,} per-timeframe cap; shorten the dates or use a coarser timeframe.')
        ranges[resolution]=dict(start=lo,end=hi,fetch_start=lo-warmup*interval,expected=count,interval=interval)
    work=sum(ranges[c['resolution']]['expected']+warmup for c in combinations)
    if work>MAX_WORK: raise ValueError(f'Grid work {work:,} exceeds {MAX_WORK:,} candle-combinations; reduce dates or grid.')
    settings=dict(base,start_date=payload['start_date'],end_date=payload['end_date'],
        capital=number(payload.get('capital',10000),'Initial capital USD',10,10000000),
        contracts=number(payload.get('contracts',10),'Fixed contracts',1,100000,True),
        fee_bps=number(payload.get('fee_bps',6),'Fee allowance bps per fill',0,100),
        slippage_bps=number(payload.get('slippage_bps',2),'Slippage bps per fill',0,100),
        half_spread_bps=number(payload.get('half_spread_bps',1),'Half-spread bps per fill',0,100),
        funding_bps_day=number(payload.get('funding_bps_day',0),'Funding drag bps per day',0,100),
        holdout_percent=number(payload.get('holdout_percent',30),'Held-out percentage',10,50))
    requests=sum(math.ceil((v['expected']+warmup)/1500) for v in ranges.values())
    return dict(settings=settings,combinations=combinations,ranges=ranges,warmup=warmup,combination_count=len(combinations),max_combinations=MAX_COMBINATIONS,estimated_requests=requests,work=work,model=MODEL)


def audit(raw, interval, start, end, now):
    unique={};duplicates=0
    if not isinstance(raw,list): raise ValueError('Provider candle response is not an array.')
    for item in raw:
        try: row={k:float(item['time' if k=='timestamp' else k]) for k in ('timestamp','open','high','low','close','volume')}
        except (KeyError, TypeError, ValueError): raise ValueError('Provider candle contains missing/invalid OHLCV.') from None
        t=row['timestamp']
        if not all(math.isfinite(x) for x in row.values()) or t<=0 or t%interval or min(row[k] for k in ('open','high','low','close'))<=0 or row['high']<max(row['open'],row['close']) or row['low']>min(row['open'],row['close']) or row['volume']<0:
            raise ValueError('Provider candle OHLCV or timeframe alignment is invalid.')
        if not start<=t<end or t+interval>now: continue
        row['is_forming']=False
        if t in unique:
            if row!=unique[t]: raise ValueError('Conflicting duplicate provider candles; no results produced.')
            duplicates+=1
        unique[t]=row
    return sorted(unique.values(),key=lambda r:r['timestamp']),duplicates


def coverage(rows, bounds):
    stamps={int(r['timestamp']) for r in rows};missing=[];runs=[]
    for t in range(bounds['start'],bounds['end'],bounds['interval']):
        if t not in stamps: missing.append(t)
    for t in missing:
        if runs and t==runs[-1]['end']+bounds['interval']:runs[-1]['end']=t;runs[-1]['candles']+=1
        else:runs.append(dict(start=t,end=t,candles=1))
    actual=[r for r in rows if bounds['start']<=r['timestamp']<bounds['end']]
    return dict(expected=bounds['expected'],actual=len(actual),missing=len(missing),coverage_percent=100*len(actual)/bounds['expected'],gap_runs=len(runs),gaps=runs[:20],first=actual[0]['timestamp'] if actual else None,last=actual[-1]['timestamp'] if actual else None,warmup_bars=sum(r['timestamp']<bounds['start'] for r in rows))


def bollinger_features(rows,cfg):
    closes=deque();widths=[];prior_sorted=[];queue=deque();last_release=-100000;result=[]
    length=cfg['bb_length'];lookback=cfg['squeeze_lookback']
    for i,row in enumerate(rows):
        closes.append(row['close'])
        if len(closes)>length:closes.popleft()
        width=None;expanding=False;squeeze=False
        if len(closes)==length:
            mean=sum(closes)/length;variance=sum((x-mean)**2 for x in closes)/length
            width=200*cfg['bb_deviation']*math.sqrt(variance)/mean
            previous=widths[-1] if widths else None
            expanding=previous is not None and width>previous
            # Compare previous width against earlier widths only, excluding it and current.
            if previous is not None and len(prior_sorted)==lookback:
                threshold=prior_sorted[max(0,math.ceil(lookback*cfg['squeeze_percentile']/100)-1)]
                squeeze=previous<=threshold
            if squeeze and expanding:last_release=i
        result.append(dict(width_percent=width,expanding=expanding,release=expanding and i-last_release<cfg['release_bars']))
        previous=widths[-1] if widths else None
        if previous is not None:
            insort(prior_sorted,previous);queue.append(previous)
            if len(queue)>lookback:prior_sorted.pop(bisect_left(prior_sorted,queue.popleft()))
        widths.append(width)
    return result


def adverse_fill(price, side, settings, tick):
    adjustment=(settings['slippage_bps']+settings['half_spread_bps'])/10000
    adjusted=price*(1+side*adjustment)
    return (math.ceil(adjusted/tick-1e-9) if side>0 else math.floor(adjusted/tick+1e-9))*tick


def simulate(rows,features,adx,cfg,settings,units,tick,start,end):
    indices=[i for i,r in enumerate(rows) if start<=r['timestamp']<end]
    cash=settings['capital'];position=None;trades=[];equity=[];skipped=0;fees=0.;funding=0.;peak=cash;maxdd=0.;maxddpct=0.
    quantity=settings['contracts']*units;interval=INTERVALS[cfg['resolution']]
    def close(raw,stamp,reason,signal=None):
        nonlocal cash,position,fees,funding
        fill=adverse_fill(raw,-position['side'],settings,tick)
        fee=fill*quantity*settings['fee_bps']/10000
        drag=position['entry_price']*quantity*settings['funding_bps_day']/10000*max(0,stamp-position['entry_time'])/86400
        gross=(fill-position['entry_price'])*quantity*position['side']
        net=gross-position['entry_fee']-fee-drag
        cash+=gross-fee-drag;fees+=fee;funding+=drag
        trades.append(dict(side='LONG' if position['side']>0 else 'SHORT',contracts=settings['contracts'],units=quantity,entry_signal_time=position['signal_time'],entry_time=position['entry_time'],entry_price=position['entry_price'],entry_reason=position['reason'],exit_signal_time=signal,exit_time=stamp,exit_price=fill,exit_reason=reason,gross_pnl=gross,fees=position['entry_fee']+fee,funding_drag=drag,net_pnl=net,entry_bandwidth_percent=position['bandwidth']))
        position=None
    for offset,i in enumerate(indices):
        row=rows[i];stamp=row['timestamp'];cross=row['cross_direction'];was_held=position is not None
        if position and cross==('BEARISH' if position['side']>0 else 'BULLISH') and offset<len(indices)-1:
            nxt=rows[indices[offset+1]]
            if nxt['timestamp']!=stamp+interval:raise ValueError('Simulation refuses a missing next execution candle.')
            close(nxt['open'],nxt['timestamp'],'OPPOSITE_CROSSOVER',stamp+interval)
        if not was_held and offset<len(indices)-1:
            direction=row['entry_direction'] if cfg['entry_rule']=='CURRENT' else cross
            side=1 if direction=='BULLISH' else -1 if direction=='BEARISH' else 0
            candidate=cfg['filter'];gate=(candidate=='BASELINE' or features[i]['expanding']) if candidate in ('BASELINE','EXPANDING') else features[i]['release']
            eligible=side and (cfg['direction']=='BOTH' or cfg['direction']=='LONG_ONLY' and side>0 or cfg['direction']=='SHORT_ONLY' and side<0)
            if eligible and gate and delta_adx.allows(cfg,adx.get(stamp)) and momentum_allows(cfg,row,direction):
                nxt=rows[indices[offset+1]]
                if nxt['timestamp']!=stamp+interval:raise ValueError('Simulation refuses a missing next execution candle.')
                fill=adverse_fill(nxt['open'],side,settings,tick);fee=fill*quantity*settings['fee_bps']/10000
                if fill*quantity+fee>cash:skipped+=1
                else:
                    cash-=fee;fees+=fee
                    position=dict(side=side,entry_price=fill,entry_time=nxt['timestamp'],entry_fee=fee,signal_time=stamp+interval,reason=row['entry_reason'] if cfg['entry_rule']=='CURRENT' else 'CROSSOVER',bandwidth=features[i]['width_percent'])
        # Entry/exit at next open is timestamped there, never marked against this signal candle.
        valuation_time=stamp+interval
        marked=cash
        if position and position['entry_time']<valuation_time:
            drag=position['entry_price']*quantity*settings['funding_bps_day']/10000*(valuation_time-position['entry_time'])/86400
            marked+=(row['close']-position['entry_price'])*quantity*position['side']-drag
        if offset==len(indices)-1 and position:
            close(row['close'],valuation_time,'PERIOD_END');marked=cash
        peak=max(peak,marked);drawdown=peak-marked;ddpct=100*drawdown/peak if peak>0 else None
        maxdd=max(maxdd,drawdown);maxddpct=max(maxddpct,ddpct or 0)
        equity.append(dict(time=valuation_time,equity=marked,drawdown=drawdown,drawdown_percent=ddpct))
    wins=sum(t['net_pnl']>0 for t in trades);positive=sum(max(0,t['net_pnl']) for t in trades);negative=-sum(min(0,t['net_pnl']) for t in trades)
    metrics=dict(trades=len(trades),net_pnl=cash-settings['capital'],return_percent=100*(cash/settings['capital']-1),gross_pnl=sum(t['gross_pnl'] for t in trades),fees=fees,funding_drag=funding,win_rate=100*wins/len(trades) if trades else None,profit_factor=positive/negative if negative else None,profit_factor_basis='No losing trades' if not negative and trades else 'No trades' if not trades else 'Net winning / net losing P&L',max_drawdown=maxdd,max_drawdown_percent=maxddpct,skipped_capital=skipped,start=start,end=end,ending_equity=cash)
    return dict(metrics=metrics,trades=trades,equity=equity)


class BacktestCancelled(Exception): pass


class DeltaBacktest:
    """Injected public candle reader and contract metadata reader; never order routes."""
    def __init__(self,root,read,metadata,clock=time.time):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True);self.read=read;self.metadata=metadata;self.clock=clock
        self.lock=threading.RLock();self.job=None;self.cancel_event=threading.Event();self.details={}
        self.result_file=self.root/'last-result.json'
        if self.result_file.exists():
            try:
                saved=json.loads(self.result_file.read_text());self.job=saved['job'];self.details=saved['details']
            except (ValueError,KeyError,OSError):pass
    def inspect(self,payload):return plan(payload,self.clock())
    def status(self):
        with self.lock:return deepcopy(self.job or dict(state='IDLE',message='Choose a research grid and run a backtest.',model=MODEL))
    def detail(self,ident):
        with self.lock:
            if ident not in self.details:raise ValueError('Combination detail is unavailable; choose a completed result.')
            return deepcopy(self.details[ident])
    def start(self,payload):
        config=self.inspect(payload)
        with self.lock:
            if self.job and self.job['state'] in ('FETCHING','RUNNING'):raise ValueError('A research job is already running; cancel or wait for it.')
            self.cancel_event=threading.Event();self.details={}
            self.job=dict(id=uuid.uuid4().hex,state='FETCHING',message='Fetching and auditing public completed candles.',progress=0,completed=0,total=config['combination_count'],plan=config,coverage={},results=[],started_at=self.clock(),cached_windows=0,downloaded_windows=0,model=MODEL)
            threading.Thread(target=self._run,args=(config,self.cancel_event),daemon=True,name='delta-backtest-research').start()
            return self.status()
    def cancel(self,_=None):
        with self.lock:
            if self.job and self.job['state'] in ('FETCHING','RUNNING'):
                self.cancel_event.set();self.job['message']='Cancellation requested; finishing the current public read / combination.'
            return self.status()
    def _update(self,**values):
        with self.lock:self.job.update(values)
    def _fetch(self,symbol,resolution,bounds,cancel):
        raw=[];interval=bounds['interval'];start=bounds['fetch_start'];end=bounds['end'];windows=math.ceil((end-start)/(1500*interval))
        for n,lo in enumerate(range(start,end,1500*interval)):
            if cancel.is_set():raise BacktestCancelled()
            hi=min(end,lo+1500*interval)
            params=dict(symbol=symbol,resolution=resolution,start=lo,end=hi)
            digest=hashlib.sha256(json.dumps(params,sort_keys=True).encode()).hexdigest();path=self.root/(digest+'.json')
            record=None
            if path.exists():
                try:
                    stored=json.loads(path.read_text())
                    if stored['params']==params and self.clock()-stored['observed_at']<86400:record=stored['candles']
                except (OSError,KeyError,ValueError):pass
            if record is None:
                response=self.read('/v2/history/candles',params)
                record=response.get('result')
                audit(record,interval,lo,hi,self.clock())
                if len(record)>2000:raise ValueError('Provider exceeded historical candle response limit.')
                temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(dict(params=params,observed_at=self.clock(),candles=record)));temporary.chmod(0o600);temporary.replace(path)
                with self.lock:self.job['downloaded_windows']+=1
                # Bound sequential public requests; cancellation remains responsive.
                if cancel.wait(.12):raise BacktestCancelled()
            else:
                with self.lock:self.job['cached_windows']+=1
            raw.extend(record)
            self._update(message=f'{symbol} {resolution}: fetched window {n+1}/{windows}; auditing coverage.',progress=round(30*(self.job['downloaded_windows']+self.job['cached_windows'])/self.job['plan']['estimated_requests'],1))
        rows,duplicates=audit(raw,interval,start,end,self.clock())
        report=coverage(rows,bounds);report['duplicates_removed']=duplicates
        # Only the contiguous tail of warmup is used; never bridge gaps into indicators.
        cut=0
        for i in range(1,len(rows)):
            if rows[i]['timestamp']-rows[i-1]['timestamp']!=interval and rows[i]['timestamp']<=bounds['start']:cut=i
        rows=rows[cut:];report['contiguous_warmup_bars']=sum(r['timestamp']<bounds['start'] for r in rows)
        with self.lock:self.job['coverage'][resolution]=report
        if report['missing']:raise ValueError(f'{resolution}: {report["missing"]:,} requested candles missing in {report["gap_runs"]} gaps; backtest blocked rather than bridging gaps. Narrow the dates and retry.')
        required_warmup=(bounds['start']-bounds['fetch_start'])//interval
        if report['contiguous_warmup_bars']<required_warmup:raise ValueError(f'{resolution}: only {report["contiguous_warmup_bars"]}/{required_warmup} contiguous pre-range warmup candles; move the start date later.')
        return rows
    def _run(self,config,cancel):
        try:
            settings=config['settings'];metadata=self.metadata(settings['symbol'])
            if metadata.get('contract_type')!='perpetual_futures' or metadata.get('notional_type')!='vanilla' or metadata.get('is_quanto') is not False or metadata.get('quoting_currency')!='USD' or metadata.get('contract_unit_currency')!=metadata.get('underlying') or metadata.get('settlement_currency')!='USD':raise ValueError('Exact vanilla USD-quoted contract units could not be verified; no assumed P&L.')
            units=number(float(metadata['contract_value']),'Verified contract units',1e-8,10000)
            tick=number(float(metadata['tick_size']),'Verified tick size',1e-8,10000)
            self._update(product=metadata)
            datasets={res:self._fetch(settings['symbol'],res,bounds,cancel) for res,bounds in config['ranges'].items()}
            indicators={};bbs={};adxs={}
            self._update(state='RUNNING',message='Comparing fixed configurations; held-out period stays chronological.',progress=30)
            for n,cfg in enumerate(config['combinations']):
                if cancel.is_set():raise BacktestCancelled()
                res=cfg['resolution'];raw=datasets[res];bounds=config['ranges'][res];interval=bounds['interval']
                key=(res,cfg['rsi_length'],cfg['ma_length'],cfg['ma_type'])
                if key not in indicators:indicators[key]=delta_rsi_series(raw,cfg['rsi_length'],cfg['ma_length'],cfg['ma_type'])
                rows=indicators[key]
                first=next(r for r in rows if r['timestamp']>=bounds['start'])
                if first['rsi_ma'] is None:raise ValueError(f'{res}: selected RSI/MA needs more pre-range warmup; move the start date later.')
                bbkey=tuple([res]+[cfg[k] for k in ('bb_length','bb_deviation','squeeze_lookback','squeeze_percentile','release_bars')])
                if bbkey not in bbs:bbs[bbkey]=bollinger_features(raw,cfg)
                if res not in adxs:adxs[res]=delta_adx.series(raw)
                split=bounds['start']+int(bounds['expected']*(1-settings['holdout_percent']/100))*interval
                train=simulate(rows,bbs[bbkey],adxs[res],cfg,settings,units,tick,bounds['start'],split)
                held=simulate(rows,bbs[bbkey],adxs[res],cfg,settings,units,tick,split,bounds['end'])
                ident=str(n+1);result=dict(id=ident,config=cfg,train=train['metrics'],held_out=held['metrics'],split=split,unvalidated=True)
                # Downsample plotted close-equity only; every trade remains available.
                for segment in (train,held):
                    step=max(1,math.ceil(len(segment['equity'])/1200));curve=segment['equity'];segment['equity']=curve[::step]
                    if curve and segment['equity'][-1]!=curve[-1]:segment['equity'].append(curve[-1])
                with self.lock:
                    self.details[ident]=dict(result,train=train,held_out=held,model=MODEL)
                    self.job['results'].append(result);self.job['completed']=n+1
                self._update(progress=round(30+70*(n+1)/len(config['combinations']),1),message=f'Compared {n+1}/{len(config["combinations"])} combinations.')
            with self.lock:
                self.job['results'].sort(key=lambda r:(-r['train']['return_percent'],r['train']['max_drawdown_percent'],int(r['id'])))
                for rank,result in enumerate(self.job['results'],1):result['rank']=rank
            self._update(state='COMPLETE',progress=100,finished_at=self.clock(),message='Research complete. Ranked by training net return; held-out results remain unvalidated.')
            with self.lock:
                temp=self.result_file.with_suffix('.tmp');temp.write_text(json.dumps(dict(job=self.job,details=self.details),allow_nan=False));temp.chmod(0o600);temp.replace(self.result_file)
        except BacktestCancelled:self._update(state='CANCELLED',message='Research cancelled. Partial comparisons are not a completed ranking.',finished_at=self.clock())
        except Exception as error:self._update(state='ERROR',message=str(error),error=str(error),finished_at=self.clock())
