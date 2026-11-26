"""Confirmed Renko from ordered live price observations, independent of host close."""
from copy import deepcopy
import math
from .signals import Engine
REVISION='ordered-price-renko-v1'

def observe(export, config, tick_size, tick, received, generation):
    """Mutate owned recurrence only; return immutable full-brick observations.

    Historical OHLC is warmup only. First price after Start is a baseline.
    Later fresh prices fill complete bricks from the same run’s last brick close. Equal/out-of-order exchange stamps
    are ignored: arrival order is not invented when the source cannot prove it.
    """
    stamp=tick.get('exch_feed_time',tick.get('last_traded_time'))
    price=tick.get('ltp')
    if isinstance(stamp,bool) or isinstance(price,bool):return []
    try:stamp=float(stamp);price=float(price)
    except (TypeError,ValueError):return []
    if not all(math.isfinite(v) for v in (stamp,price,received)) or price<=0 or not 0<=received-stamp<=15:return []
    state=export['state']
    from . import session_auto
    session_reference=None
    previous_session=(state.get('session_auto') or {}).get('session_start')
    live=state.setdefault('price_renko',{})
    sequence=tick.get('observation_sequence')
    if live.get('last_exchange_at') is not None:
        if stamp<live['last_exchange_at']:return []
        if stamp==live['last_exchange_at'] and (sequence is None or live.get('last_sequence') is None or sequence<=live['last_sequence']):return []
    if session_auto.selected(config):
        session_reference=session_auto.apply_observation(state,config,stamp,tick_size)
        if session_reference is None:return []
        live=state.setdefault('price_renko',{})
    box=state.get('brick_box') or export['last'].get('box')
    if not box or box<=0:raise ValueError('Confirmed Auto/Manual brick sizing is not initialized.')
    session_gap=(previous_session is not None and session_reference is not None
                 and previous_session != session_reference['session_start']
                 and live.get('run_id') == config.get('_run_id'))
    baseline=(not live or live.get('run_id')!=config.get('_run_id')
              or (not session_gap and (live.get('stream_session')!=config.get('_stream_session')
              )))
    live.update(last_exchange_at=stamp,received_at=received,last_sequence=sequence,
                stream_session=config.get('_stream_session'),generation=generation)
    if baseline:
        live.update(run_id=config.get('_run_id'),stream_session=config.get('_stream_session'),generation=generation,level=math.floor(price/box),
                    direction=0,baseline_at=stamp,baseline_price=price,
                    reason='Fresh stream baseline; unobserved price path excluded, no replay.')
        return []
    level=live['level'];direction=live['direction'];events=[]
    while True:
        up=price/box-level >= (2 if direction<0 else 1)-1e-10
        down=level-price/box >= (2 if direction>0 else 1)-1e-10
        if not up and not down:break
        side=1 if up else -1
        opening=level+(side if direction and side!=direction else 0)
        level=opening+side;direction=side
        events.append((opening*box,level*box))
    live.update(level=level,direction=direction)
    if not events:return []
    raw={**config,'strategy_basis':'CANDLESTICK','brick_mode':'Manual','manual_brick':box,
         '_brick_input':True,'chart_entry_guards':False,
         'anti_chop_enabled':False,'manual_trend_enabled':False,'calibrated_enabled':False}
    inner=Engine(raw,tick_size,state.get('brick_indicator_state'))
    results=[]
    for index,(opening,closing) in enumerate(events):
        logical=max(stamp, (inner.state.get('previous') or {}).get('timestamp',0)+.000001)
        candle=dict(timestamp=logical,open=opening,close=closing,high=max(opening,closing),low=min(opening,closing),volume=None)
        result=inner.update(candle)
        period=int(config.get('ema_exit_length',10));old=inner.state.get('brick_exit_ema')
        exit_ema=closing if old is None else 2/(period+1)*closing+(1-2/(period+1))*old
        inner.state['brick_exit_ema']=exit_ema
        side='BULLISH' if closing>opening else 'BEARISH'
        result.update(strategy_basis='RENKO',confirmation_basis='ORDERED_LIVE_PRICE',
                      source_timestamp=stamp,market_event_at=stamp,source_close=price,
                      source_generation=generation,source_observed_at=received,source_event_index=index,source_sequence=sequence,
                      brick_direction=side,box=box,host_close=price,host_atr=(state.get('brick_host_atr') or {}).get('value',result.get('host_atr')),
                      ema_exit=exit_ema,ema_exit_enabled=config.get('ema_exit_enabled',False),
                      has_completed_brick=True,brick_count=1)
        if result.get('lifecycle_event'):result['lifecycle_event_at']=stamp
        if session_reference:result['session_auto']=deepcopy(session_reference)
        result['brick_exit_events']=[dict(close=closing,ema_exit=exit_ema,brick_direction=side,
                                        sma=result.get('sma'),sma_length=result.get('sma_length'),
                                        raw_supertrend_cross_direction=result.get('raw_supertrend_cross_direction'))]
        result['brick_events']=[deepcopy(result)]
        results.append(result)
    state['brick_indicator_state']=deepcopy(inner.state)
    for result in results:
        export['rows']=(export.get('rows',[])+[deepcopy(result)])[-500:]
    export['last']=deepcopy(results[-1]);state['brick_last']=deepcopy(results[-1])
    state['count']=state.get('count',0)+len(results)
    return results


def _price_event_identity(row):
    return tuple(row.get(key) for key in ('source_generation','source_sequence','source_event_index','timestamp'))

def _remember_price_publication(runner, rows, timing):
    from collections import OrderedDict
    cache=getattr(runner,'_price_event_timings',None)
    if cache is None or getattr(runner,'_price_event_timing_run',None)!=runner.state.get('run_id'):
        cache=OrderedDict();runner._price_event_timings=cache
        runner._price_event_timing_run=runner.state.get('run_id')
    for row in rows:
        cache[_price_event_identity(row)]=dict(timing)
    while len(cache)>2000:cache.popitem(last=False)

def _record_price_execution_timing(runner,row,started,elapsed,decision):
    # Diagnostics only: no event/quote timestamp or execution gate is changed.
    cache=getattr(runner,'_price_event_timings',{}) if getattr(runner,'_price_event_timing_run',None)==runner.state.get('run_id') else {}
    cached=cache.get(_price_event_identity(row))
    result=dict(run_id=runner.state.get('run_id'),event_at=row.get('market_event_at'),
                source_observed_at=row.get('source_observed_at'),
                source_sequence=row.get('source_sequence'),source_event_index=row.get('source_event_index'),
                decision=decision,execution_step_seconds=elapsed,recorded_at=runner.clock())
    if cached:
        result['publication']=dict(cached)
        result['queue_wait_seconds']=max(0,started-cached['queued_monotonic'])
        result['publication'].pop('queued_monotonic',None)
    observed=row.get('source_observed_at')
    age=runner.clock()-observed if isinstance(observed,(int,float)) and not isinstance(observed,bool) else None
    result['receive_to_record_seconds']=age if age is not None and age>=0 else None
    records=runner.state.setdefault('price_execution_timings',[])
    records.append(result)
    runner.state['price_execution_timings']=records[-120:]
    return result


def _publish_price_confirmed(publisher, runner, *, engine, config):
    # A long-lived dashboard can retain the older publisher during source promotion.
    # Inspect capability before calling; never catch/replay an internal TypeError.
    from inspect import signature, Parameter
    parameters=signature(publisher).parameters
    supports_immutable=('immutable_rows' in parameters or
                        any(p.kind==Parameter.VAR_KEYWORD for p in parameters.values()))
    options=dict(engine=engine,config=config)
    if supports_immutable:options['immutable_rows']=True
    return publisher(runner,**options)


def produce(runner,tick,received,generation,*,config=None):
    from .confirmed_feed import publish_confirmed
    from sector_heatmap.workspaces import private_write
    import json,time
    publication_started=time.perf_counter()
    config=deepcopy(runner.state['config'] if config is None else config)
    run_id=runner.state['run_id']
    publication=getattr(runner,'_price_export',None)
    original=publication[1] if publication and publication[0]==run_id else runner.state.get('renko_engine')
    if not original:return []
    live=original['state'].get('price_renko') or {}
    stamp=tick.get('exch_feed_time',tick.get('last_traded_time'));sequence=tick.get('observation_sequence')
    if stamp==live.get('last_exchange_at') and (sequence is None or live.get('last_sequence') is None or sequence<=live['last_sequence']):return []
    export={**original,'state':deepcopy(original['state']),'rows':list(original['rows'])}
    rows=observe(export,{**config,'_run_id':runner.state['run_id'],'_stream_session':runner._price_stream_session},
                 original['identity']['tick_size'],tick,received,generation)
    observed_at=time.perf_counter()
    if runner.state.get('run_id')!=run_id or getattr(runner,'stop_requested',None) and runner.stop_requested.is_set():
        return []
    runner._price_export=(run_id,export)
    if rows:
        # Persist before making an event executable. This sidecar remains independent
        # of an execution request blocked in broker reconciliation or quote lookup.
        private_write(runner.path.with_name('price-confirmed-history.json'),
                      json.dumps(dict(run_id=runner.state['run_id'],config=config,engine=export),allow_nan=False))
        queued_at=time.perf_counter()
        _remember_price_publication(runner,rows,dict(
            observe_seconds=observed_at-publication_started,
            durable_history_seconds=queued_at-observed_at,
            queued_monotonic=queued_at,chart_publication_pending=True))
        for row in rows:runner.confirmed_price_events.put(deepcopy(row))
        # The tick callback can wake execution before this producer has queued
        # the completed bricks. Wake again after durable publication.
        if hasattr(runner,'wake'):runner.wake.set()
    if rows or live.get('stream_session')!=runner._price_stream_session:
        runner._published_confirmed_key=None
        _publish_price_confirmed(publish_confirmed,runner,engine=export,config=config)
        finished=time.perf_counter()
        for row in rows:
            timing=runner._price_event_timings.get(_price_event_identity(row))
            if timing:
                timing.update(chart_publication_seconds=finished-queued_at,
                              chart_publication_pending=False)
    return rows

def producer(runner,run_id):
    from .runner import analysis
    import time
    while runner.state.get('running') and runner.state.get('run_id')==run_id and not runner.stop_requested.is_set():
        try:
            config=deepcopy(runner.state['config'])
            from . import session_auto
            if session_auto.selected(config):session_auto.prepare(runner.adapter,config)
            if not runner.state.get('renko_engine') and (not getattr(runner,'_price_export',None) or runner._price_export[0]!=run_id):
                rows=runner.history_rows(runner.adapter.candles(config))
                runner._price_export=(run_id,analysis(rows,config,runner.adapter.host_tick_size(config['underlying'])))
            stream=runner.adapter.stream_status() if hasattr(runner.adapter,'stream_status') else {'connected':True,'generation':0}
            if not stream.get('connected'):
                runner.price_wake.wait(.2);runner.price_wake.clear();continue
            inputs=[]
            while not runner.price_ticks.empty():inputs.append(runner.price_ticks.get_nowait())
            if not inputs and runner._price_received_seq:
                runner.price_wake.wait(.2);runner.price_wake.clear();continue
            if not inputs:
                now=runner.clock()
                if now-getattr(runner,'_price_last_poll',0)<1:
                    runner.price_wake.wait(.2);runner.price_wake.clear();continue
                runner._price_last_poll=now
                if hasattr(runner.adapter,'tick'):tick=runner.adapter.tick(config['underlying'])
                else:
                    price,stamp=runner.adapter.live_price(config,now)
                    tick=dict(symbol=config['underlying'],ltp=price,exch_feed_time=stamp,source_kind=stream.get('source','BROKER_PRICE_OBSERVATION'))
                inputs=[(tick,now,stream.get('generation'))]
            if len(inputs)>10000:
                inputs=inputs[-1:]
                runner._price_stream_session=str(time.monotonic_ns())
            for tick,received,generation in inputs:
                if runner.stop_requested.is_set():break
                produce(runner,tick,received,generation,config=config)
            runner.price_producer_error=None
        except Exception as error:
            runner.price_producer_error=str(error)
        runner.price_wake.wait(.2);runner.price_wake.clear()


def retain_opposite_exit(runner,row):
    """A queued completed reversal remains an exit obligation after entry expiry."""
    from .exit_indicators import reason
    p=runner.state.get('position')
    if not p or p.get('exit_requested') or not runner.exit_is_later(row,p):return False
    if row.get('market_event_at',float('inf'))>runner.clock():return False
    why=reason(runner.state['config'],row,p['direction'])
    if why!='OPPOSITE_RENKO_BRICK_CLOSE':return False
    p.update(exit_requested=True,exit_reason=why,exit_signal_timestamp=row['timestamp'])
    p['exit_indicator_snapshot']=runner.indicator_snapshot(row,why)
    runner.state['last_exit_bar']=row['timestamp']
    runner.save()
    return True

def run_step(runner):
    runner.recovery.beat()
    from . import anti_chop,manual_trend,calibrated,mtf_rsi,market_structure
    from .signals import completed
    from strategies.ema_crossover.runner import TIMEFRAMES
    import threading
    with runner.lock:
        if not runner.state.get('running'):return
        if runner.stop_requested.is_set() or runner.state.get('squareoff_requested'):
            # Stop first disables entries and marks owned exposure for exit. It
            # cannot complete the drain itself: the normal order-management step
            # must cancel/reconcile pending intent and close filled quantity.
            if not runner.state.get('squareoff_requested'):runner.stop()
            if runner.state.get('running'):return runner._candle_step()
            return
        config=runner.state['config'];now=runner.clock()
        if (runner.state.get('accepting_entries') and not runner.state.get('position')
                and not runner.state.get('pending') and hasattr(runner,'warm_price_options')):
            runner.warm_price_options(config)
        if not getattr(runner,'_price_test_producer',False) and (not getattr(runner,'price_thread',None) or not runner.price_thread.is_alive()):
            runner.price_thread=threading.Thread(target=producer,args=(runner,runner.state['run_id']),name='confirmed-price-renko',daemon=True)
            runner.price_thread.start()
        publication=getattr(runner,'_price_export',None)
        if publication and publication[0]==runner.state.get('run_id'):
            runner.state['renko_engine']=publication[1]
        events=[]
        while not runner.confirmed_price_events.empty():events.append(runner.confirmed_price_events.get_nowait())
        if not events:
            if runner.state.get('position') or runner.state.get('pending'):
                previous=runner.state.get('last_signal') or (runner.state.get('renko_engine') or {}).get('last')
                if previous:
                    runner._price_current={**previous,'entry_qualified':False,'entry_direction':None,'cross_direction':None,
                                           'has_completed_brick':False,'brick_events':[],'brick_exit_events':[]}
                    runner._candle_step()
            else:
                error=getattr(runner,'price_producer_error',None)
                runner.state.update(status='WAITING_FOR_STREAM' if error else 'WATCHING_NO_ENTRY',
                                    message=error or 'Watching ordered prices; full Renko bricks confirm immediately.')
                if (runner.state.get('renko_loss_lock') or {}).get('active'):
                    runner.renko_loss_entry_gate({'has_completed_brick':False})
                runner.save()
            return
        host=[]
        if any(config.get(k) for k in ('anti_chop_enabled','manual_trend_enabled','calibrated_enabled','market_structure_enabled')):
            bucket=int(now)//TIMEFRAMES[config['timeframe']]
            if getattr(runner,'_price_filter_bucket',None)!=bucket:
                runner._price_filter_rows=completed(runner.history_rows(runner.adapter.candles(config)))
                runner._price_filter_bucket=bucket
            host=runner._price_filter_rows
        for row in events:
            import time
            execution_started=time.perf_counter()
            if runner.stop_requested.is_set():
                runner.stop()
                if runner.state.get('running'):return runner._candle_step()
                return
            if not 0<=runner.clock()-row['market_event_at']<=15:
                _record_price_execution_timing(runner,row,execution_started,0,'EXPIRED_ENTRY_EVENT')
                runner.record_entry_assessment(row,False,'STALE_PRICE_EVENT','Price event expired during execution preflight; no entry replay.')
                if retain_opposite_exit(runner,row):
                    runner._price_current={**row,'entry_qualified':False,'cross_direction':None}
                    runner._candle_step()
                continue
            from .trend_reentry import apply as apply_trend_reentry
            row=apply_trend_reentry(runner.state,row)
            side=row['direction']
            if config.get('anti_chop_enabled'):
                gates=runner.state.setdefault('price_host_gates',{})
                at=host[-1]['timestamp'] if host else None
                if gates.get('timestamp')!=at:
                    if not host:raise ValueError('Selected-timeframe anti-chop observations unavailable.')
                    saved=runner.state.setdefault('price_host_filter_state',{})
                    previous=(saved.get('anti_chop') or {}).get('previous') or {}
                    for candle in host:
                        if candle['timestamp']<=previous.get('timestamp',0):continue
                        for direction in ('BULLISH','BEARISH'):
                            trial=deepcopy(saved);gates[direction]=anti_chop.observe(trial,candle,config,direction,TIMEFRAMES[config['timeframe']])
                            if direction=='BULLISH':committed=trial
                        saved=committed
                    gates.update(timestamp=at);runner.state['price_host_filter_state']=saved
                if config.get('anti_chop_role')=='Entry':anti_chop.generate_entry(row,gates[side],runner.state)
                else:anti_chop.apply(row,gates[side])
            if config.get('manual_trend_enabled'):
                manual_trend.apply(row,manual_trend.check(host,config,side,TIMEFRAMES[config['timeframe']]))
            if config.get('calibrated_enabled'):
                gate=calibrated.check(host,config,TIMEFRAMES[config['timeframe']]);row['calibrated_filter']=gate
                if not gate['allowed']:row.update(entry_qualified=False,entry_direction=None,entry_diagnostic=gate['reason'])
            row['supertrend_cross_direction']=row.get('raw_supertrend_cross_direction')
            # Every full qualifying price brick is an event, independent of simulated lifecycle/onset state.
            row['cross_direction']=side if row['entry_qualified'] else None
            if runner.state.get('last_exit_price_observation')==row['source_timestamp']:
                row.update(cross_direction=None,entry_qualified=False,entry_diagnostic='ACTUAL_EXIT_CONSUMED_PRICE_OBSERVATION')
            if config.get('higher_timeframe_enabled'):row['mtf_supertrend']=runner.supertrend_agreement(side,row['market_event_at'])
            if mtf_rsi.enabled(config):row['mtf_rsi']=runner.rsi_agreement(side,row['market_event_at'])
            if config.get('market_structure_enabled'):row['market_structure']=market_structure.check(host,side,TIMEFRAMES[config['timeframe']],row['market_event_at'])
            runner._price_current=row;runner.state['last_signal']=row
            runner.observe_renko_loss_range(row)
            held=bool(runner.state.get('position'))
            try:
                runner._candle_step()
            except Exception as error:
                # Keep processing ordered, still-fresh events from this batch.
                # The worker's generic exception path would drop the rest.
                if not hasattr(runner,'handle_step_error'):raise
                runner.handle_step_error(error)
                continue
            finally:
                _record_price_execution_timing(runner,row,execution_started,
                    time.perf_counter()-execution_started,runner.state.get('status','UNKNOWN'))
            if held and not runner.state.get('position'):runner.state['last_exit_price_observation']=row['source_timestamp']
            runner.save()
        runner.state['price_renko_revision']=REVISION;runner.save()
