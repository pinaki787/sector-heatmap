"""Selected Delta instrument runtime. Paper default; explicit Live opt-in only."""
import json,math,os,queue,time
from pathlib import Path
from datetime import datetime
try:
    from .run import atomic,normalize_closes,IST,ROOT
    from .delta_adapter import bound_delta,select_option
    from .delta_execution import DeltaExecution
    from .core import Strategy,sizes
    from .direct import DirectStrategy,complete_reversal
    from . import reversal
    from .markets import SourceBars
except ImportError:
    from run import atomic,normalize_closes,IST,ROOT
    from delta_adapter import bound_delta,select_option
    from delta_execution import DeltaExecution
    from core import Strategy,sizes
    from direct import DirectStrategy,complete_reversal
    import reversal
    from markets import SourceBars
FRAMES={1:'1m',5:'5m',30:'30m'}
from strategies.nifty_ai_options.delta_entry_policy import ENTRY_POLICY_REVISION

try:from .sma_band import band_enabled,retain_broker_ohlc
except ImportError:from sma_band import band_enabled,retain_broker_ohlc

def history(delta,symbol,frame,out,band=False):
    import hashlib
    seconds=frame*60;now=int(delta.clock());begin=int(now-14*86400)//seconds*seconds;rows=[];page=0
    scope=hashlib.sha256((symbol+'|'+str(frame)).encode()).hexdigest()[:16]
    while begin<now:
        finish=min(int(now),begin+seconds*499)
        reply=delta._get('/v2/history/candles',dict(symbol=symbol,resolution=FRAMES[frame],start=begin,end=finish));raw=reply.get('result')
        if not isinstance(raw,list):raise ValueError('Delta completed history unavailable')
        atomic(Path(out)/(scope+'-'+str(page)+'-raw.json'),reply)
        rows.extend([[r['time'],r.get('open'),r.get('high'),r.get('low'),r.get('close'),r.get('volume')] for r in raw]);page+=1;begin=finish
    normalized,audit=normalize_closes(rows);atomic(Path(out)/(scope+'-audit.json'),dict(audit,symbol=symbol,frame=frame))
    if band:normalized=retain_broker_ohlc(normalized,rows)
    return [r for r in normalized if r[0]+seconds<=now]

def inspect(config,delta):
    from strategies.renko_supertrend.delta_contracts import perpetual_contract
    if config.get('broker')!='DELTA_INDIA' or config.get('market')!='CRYPTO':raise ValueError('Exact Delta crypto market route required')
    if config.get('execution_route') not in ('DIRECT','OPTIONS'):raise ValueError('Direct or bought-option route required')
    if config.get('reference_symbol')!=config.get('underlying'):raise ValueError('Native reference belongs to another instrument')
    if not config.get('reference_evidence') or not config.get('reference_session'):raise ValueError('Dated native parent reference required')
    if isinstance(config.get('lots'),bool) or not isinstance(config.get('lots'),int) or config['lots']<1:raise ValueError('Explicit whole contracts required')
    meta=perpetual_contract(delta.product(config['underlying']))
    engine=DirectStrategy(config) if config['execution_route']=='DIRECT' else Strategy(config)
    return dict(read_only=True,orders_submitted=0,underlying=config['underlying'],instrument=meta,spot_brick=engine.spot_size,execution_route=config['execution_route'],stream_started=False,entry_order_type='market_order',entry_execution_policy=ENTRY_POLICY_REVISION)

def live_readiness(delta,symbols):
    # Account reads only. Live opt-in still occurs solely at explicit user Start.
    from strategies.renko_supertrend.delta_execution import Execution as NativeExecution
    native=NativeExecution(delta);native.authenticate()
    rows=native.active_orders()
    selected={int(delta.product(symbol)['id']):symbol for symbol in symbols}
    positions={symbol:delta._position(pid) for pid,symbol in selected.items()}
    pending=[r for r in rows if int(r.get('product_id',-1)) in selected]
    if any(value!=0 for value in positions.values()) or pending:
        raise ValueError('Selected Delta execution contract has existing broker exposure or an active order; no AI ownership assumed')
    return dict(authentication='VERIFIED_READ_ONLY',selected_contract_positions=positions,selected_pending_orders=0,orders_submitted=0)

def preflight(args):
    config=json.loads(Path(args.config).read_text());delta=bound_delta(config['account'],Path(args.output)/'native-cache')
    try:
        summary=inspect(config,delta)
        if config['execution_route']=='OPTIONS':
            summary['contracts']={}
            for side in ['CE','PE']:
                c,d=select_option(delta,config['underlying'],side,config.get('target_premium',40),expiry=config.get('expiry') if config.get('expiry_policy')=='explicit_listed' else None);base,brick=sizes(config['reference_value'],d,'CRYPTO',config.get('asset'),config.get('option_moneyness','OTM'))
                summary['contracts'][side]=dict(c,delta=d,spot_brick=base,option_brick=brick)
        if config.get('execution_mode')=='LIVE':
            symbols=[c['symbol'] for c in summary.get('contracts',{}).values()] if config['execution_route']=='OPTIONS' else [config['underlying']]
            summary['live_readiness']=live_readiness(delta,symbols)
        atomic(Path(args.output)/'preflight.json',summary);print(json.dumps(summary,indent=2))
    finally:delta.requester.close()

class SourceBroker:
    """Wrap only this process's native public stream; no shared runner actions."""
    def __init__(self,delta,out,on_tick):
        from strategies.renko_supertrend.delta_broker import Broker
        self.native=Broker(delta,Path(out)/'unused-native-history',on_tick=on_tick)
    def __getattr__(self,key):return getattr(self.native,key)
    def unsubscribe(self,symbol):
        broker=self.native
        with broker.lock:
            resolutions=[broker.candle_resolutions[seconds] for s,seconds in broker.frame_seconds if s==symbol]
            broker.symbols.discard(symbol);broker.frame_seconds={key:val for key,val in broker.frame_seconds.items() if key[0]!=symbol}
            broker.ticks.pop(symbol,None);broker.quotes.pop(symbol,None);socket=broker.socket if broker.connected else None
        if socket:socket.send(json.dumps(dict(type='unsubscribe',payload=dict(channels=[dict(name='ob_l1',symbols=[symbol])]+[dict(name='candlestick_'+resolution,symbols=[symbol]) for resolution in resolutions]))))

try:from .manual_entry import ManualDispatcher,ManualNotReady,automatic_actions,confirm_entry_fill,restore_unsubmitted,confirmed_flat_entry
except ImportError:from manual_entry import ManualDispatcher,ManualNotReady,automatic_actions,confirm_entry_fill,restore_unsubmitted,confirmed_flat_entry

try:from .automatic_sizing import automatic_strategy,runtime_configuration
except ImportError:from automatic_sizing import automatic_strategy,runtime_configuration

try:
 from .position_control import entry_guard,EntryBlocked
except ImportError:
 from position_control import entry_guard,EntryBlocked
from contextlib import nullcontext

def stream(args):
    config=json.loads(Path(args.config).read_text());live=args.live
    if config.get('_verification_only'):raise ValueError('Verification-only configuration cannot start a stream or orders')
    if live and os.getenv('AI_RENKO_LIVE_ORDERS',os.getenv('NIFTY_AI_LIVE_ORDERS'))!='I_ACCEPT_REAL_ORDERS':raise ValueError('Explicit Live environment opt-in required')
    if not config.get('accept_close_source_renko_approximation'):raise ValueError('Review the confirmed-close Renko basis before Start')
    config.setdefault('execution_mode','LIVE' if live else 'PAPER')
    if not config.get('_managed_resume'):config=runtime_configuration(config,Path(args.output))
    from strategies.nifty_ai_options.delta_entry_policy import ENTRY_POLICY_REVISION
    config['entry_execution_policy']=ENTRY_POLICY_REVISION
    config['entry_order_type']='market_order'
    atomic(Path(args.config),config)
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    delta=bound_delta(config['account'],ROOT/'.private/nifty-ai-options/native-delta'/config['account']/('LIVE' if live else 'PAPER'))
    broker=executor=engine=None;symbol=None
    try:
        summary=inspect(config,delta);atomic(out/'preflight.json',summary)
        executor=DeltaExecution(delta,config['account'],ROOT/'.private/nifty-ai-options/runtime',live=live,contracts=config['lots'],management_only=config.get('_managed_resume',False))
        executor.fill_evidence_path=out/'confirmed-fills.jsonl'
        try:from .confirmed_close import ConfirmedClose,delta_reader
        except ImportError:from confirmed_close import ConfirmedClose,delta_reader
        confirmed=ConfirmedClose(delta_reader(delta),out/'confirmed-source')
        try:from .chart_source import ChartSource
        except ImportError:from chart_source import ChartSource
        chart_source=ChartSource(out/'chart-source',calculation_mode=config.get('calculation_mode','RENKO'))
        q=queue.Queue(maxsize=20000);overflow=False
        def on_tick(tick):
            nonlocal overflow
            try:q.put_nowait(tick)
            except queue.Full:overflow=True
        broker=SourceBroker(delta,out,on_tick)
        direct=config['execution_route']=='DIRECT';underlying=config['underlying']
        engine=automatic_strategy(DirectStrategy(config) if direct else Strategy(config),config,exposure=lambda:bool(executor.state['position'] or executor.state['pending'] or executor.state.get('positions') or executor.state.get('detached_position')),chart_source=chart_source,config_path=out/'config.json')
        rows=history(delta,underlying,config['timeframe'],out/'source-history',(band_enabled(config) or config.get('calculation_mode') in ('CANDLES','HYBRID')))
        if not rows:raise ValueError('No selected-underlying completed warm-up closes')
        chart_source.seed(underlying,config['timeframe'],rows,engine.spot_size)
        for r in rows:engine.update(dict(kind='underlying',timestamp=r[0],open=r[1],high=r[2],low=r[3],close=r[4]));engine.position=None
        chart_source.seed_bands(engine)
        def select(preferred_side=None):
            if direct:
                meta=dict(summary['instrument'],underlying=underlying,execution_route='DIRECT');engine.reset_contract(meta);return underlying
            side=preferred_side or (engine.signal_side() or 'PE')
            contract,d=select_option(delta,underlying,side,config.get('target_premium',40),expiry=config.get('expiry') if config.get('expiry_policy')=='explicit_listed' else None);engine.reset_contract(contract,d);engine.last_time.pop('premium',None)
            broker.subscribe(contract['symbol'],config['timeframe']*60)
            if config.get('signal_source')=='UNDERLYING':return contract['symbol']
            rows=history(delta,contract['symbol'],config['timeframe'],out/'source-history',True) if (config.get('band_price_basis')=='premium' and band_enabled(config)) or config.get('calculation_mode') in ('CANDLES','HYBRID') else history(delta,contract['symbol'],config['timeframe'],out/'source-history')
            if not rows:raise ValueError('No selected-premium completed warm-up closes')
            chart_source.seed(contract['symbol'],config['timeframe'],rows,engine.contract['option_brick'])
            for r in rows:engine.update(dict(kind='premium',timestamp=r[0],open=r[1],high=r[2],low=r[3],close=r[4],symbol=contract['symbol']));engine.position=None
            if config.get('supertrend_enabled',True) and (engine.premium_result is None or engine.premium_result['host_atr'] is None):raise ValueError('Selected premium lacks sufficient indicator warm-up')
            if config.get('band_price_basis')=='premium':chart_source.seed_bands(engine)
            return contract['symbol']
        symbol=select()
        if live and not config.get('_managed_resume'):live_readiness(delta,[symbol])
        engine.entry_reset_at=delta.clock()
        if direct:engine.pending_direction=None
        else:engine.pending_underlying_flip=None
        if config.get('sma_exit_enabled'):
            for r in history(delta,underlying,1,out/'source-history'):engine.update(dict(kind='sma',timestamp=r[0],close=r[4]))
            broker.subscribe(underlying,60)
        broker.subscribe(underlying,config['timeframe']*60);broker.subscribe(symbol,config['timeframe']*60)
        bars={underlying:SourceBars(config['timeframe'],continuous=True,confirmed_closes=True)}
        if symbol!=underlying:bars[symbol]=SourceBars(config['timeframe'],continuous=True,confirmed_closes=True)
        from strategies.nifty_ai_options.delta_feed_health import FeedHealth
        feed_health=FeedHealth()
        sma=SourceBars(1,continuous=True,confirmed_closes=True);markers=[];last_tick=time.monotonic();last_write=0;generation=None;observation_sequence=0;last_reconcile=0
        broker.start()
        if not direct:
            try:from .option_legs import OptionLegBook,entry_valid,retain_pending_actions
            except ImportError:from option_legs import OptionLegBook,entry_valid,retain_pending_actions
            executor=OptionLegBook(executor,out,config,quote=lambda name:dict(broker.quote(name),symbol=name),ready=lambda:broker.stream_status()['connected'],clock=delta.clock)
        def unsubscribe_unused(name):
            if direct or not executor.has_symbol(name):broker.unsubscribe(name)
        with (out/'events.jsonl').open('a',buffering=1) as journal:
            def submit(action):
                if not direct:
                    if action['action']=='BUY':executor.remember_entry(action)
                    if action['action']=='SELL' and action.get('reason')!='USER_STOP_SQUARE_OFF':
                        engine.quote_exit_pending=None
                        return executor.request_exit(action)
                if direct:reversal.remember(engine,executor,action)
                if action['action'].startswith('OPEN_'):
                    current=broker.stream_status()
                    if not current['connected'] or generation is not None and current['generation']!=generation:raise ValueError('Source changed before reverse entry; history reconciliation required')
                try:quote=dict(broker.quote(action['position']['symbol']),symbol=action['position']['symbol'])
                except ValueError as error:
                    if direct or str(error)!='Fresh executable Delta backend quote required.':raise
                    restore_unsubmitted(engine,executor,action)
                    if action['action']=='SELL':engine.quote_exit_pending=dict(action)
                    return dict(deferred=True,reason='WAITING_FOR_FRESH_QUOTE')
                try:
                    with entry_guard(out,executor) if action['action'] in ('BUY','OPEN_LONG','OPEN_SHORT') else nullcontext():
                        result=reversal.execute(engine,executor,action,lambda:executor.submit(action,quote)) if direct else executor.submit(action,quote)
                except EntryBlocked:
                    restore_unsubmitted(engine,executor,action)
                    return dict(deferred=True,reason='WAITING_FOR_POSITION_CONTROL')
                if result.get('deferred'):
                    restore_unsubmitted(engine,executor,action)
                    journal.write(json.dumps(dict(action=action,result=result,recorded_at=time.time()))+'\n')
                    print(json.dumps(result),flush=True)
                    return result
                if direct:reversal.entered(executor,action)
                confirm_entry_fill(engine,executor,action,clock=delta.clock)
                if action['action']=='SELL':
                    engine.quote_exit_pending=None
                journal.write(json.dumps(dict(action=action,result=result))+'\n')
                if (out/'markers.json').exists():markers[:]=json.loads((out/'markers.json').read_text())
                markers.append(dict(timestamp=action['timestamp'],source_timestamp=action['timestamp'],confirmed_at=time.time(),symbol=action['position']['symbol'],action=action['action'],mode='LIVE' if live else 'PAPER',confirmed=True,price=result.get('fill_price',result.get('simulated_fill')),order_id=result.get('order_id')))
                atomic(out/'markers.json',markers[-1000:]);print(json.dumps(result),flush=True)
                return result
            def manual_prepare(direction):
                nonlocal symbol
                if direct:return
                old=symbol;symbol=select(direction)
                if old!=symbol:unsubscribe_unused(old)
                bars.pop(old,None);bars[symbol]=SourceBars(config['timeframe'],continuous=True,confirmed_closes=True)
            def manual_quote_ready():
                current=broker.stream_status()
                if not current['connected'] or generation is not None and current['generation']!=generation:raise ValueError('Source changed; history reconciliation required before manual entry')
                try:
                    broker.tick(underlying)
                    quote=broker.quote(symbol)
                except ValueError as error:raise ManualNotReady('Waiting for fresh selected-contract quotes') from error
                return quote['exchange_at']
            manual=ManualDispatcher(config,out,'LIVE' if live else 'PAPER',engine,executor,prepare=manual_prepare,quote_ready=manual_quote_ready,submit=submit)
            try:from .runtime_control import RuntimeControl
            except ImportError:from runtime_control import RuntimeControl
            def change_timeframe(frame):
                chart_source.roll_timeframe(list(bars),config['timeframe'],frame)
                for key in list(bars):
                    bars[key]=SourceBars(frame,continuous=True,confirmed_closes=True)
                    broker.subscribe(key,frame*60)
                engine.config['timeframe']=frame
                for key in ('underlying','premium','hybrid_candle','hybrid_candle_underlying','hybrid_candle_premium'):engine.last_time.pop(key,None)
                manual.inbox.expected['timeframe']=frame
            try:
                from .position_control import PositionManager
                from .position_brokers import DeltaPositions
            except ImportError:
                from position_control import PositionManager
                from position_brokers import DeltaPositions
            position_view=DeltaPositions(delta,config,getattr(executor,'native',None))
            def attach_holding(request):
                nonlocal symbol
                row=position_view.selected(request);captured=executor.state.get('detached_position') or executor.state.get('position')
                engine.position=None;old=symbol;symbol=row['symbol']
                meta=dict(row['meta'],underlying=underlying,execution_route=config['execution_route'])
                if direct:engine.reset_contract(meta)
                else:
                    d=captured.get('selection_delta') if captured and captured['symbol']==symbol else float((delta.ticker(symbol).get('greeks') or {})['delta'])
                    meta.update(option_type=row['side'],expiry=row['expiry'])
                    engine.reset_contract(meta,d)
                    if config.get('signal_source')!='UNDERLYING':
                        rows=history(delta,symbol,config['timeframe'],out/'source-history',(band_enabled(config) or config.get('calculation_mode') in ('CANDLES','HYBRID')))
                        if not rows:raise ValueError('Exact held premium warm-up is unavailable')
                        chart_source.seed(symbol,config['timeframe'],rows,engine.contract['option_brick'])
                        engine.last_time.pop('premium',None)
                        for r in rows:engine.update(dict(kind='premium',timestamp=r[0],open=r[1],high=r[2],low=r[3],close=r[4],symbol=symbol));engine.position=None
                if old!=symbol:unsubscribe_unused(old);bars.pop(old,None)
                broker.subscribe(symbol,config['timeframe']*60);bars[symbol]=SourceBars(config['timeframe'],continuous=True,confirmed_closes=True)
                return dict(engine.contract,side=row['side'],quantity=row['quantity'],product='DELTA',fill_price=row['average_price'],entry_timestamp=delta.clock(),attached_existing=True)
            manager=PositionManager(config,out,engine,executor,verify=lambda owned,**kw:position_view.verify(owned,**kw) if live else dict(flat=executor.state.get('position') is None if kw.get('flat') is True else False),attach=attach_holding,submit=submit,clock=delta.clock,manual=manual)
            control=RuntimeControl(config,out,apply=change_timeframe,apply_mode=lambda mode:engine.config.update(display_mode=mode,exit_confirmation_mode='RENKO_BRICKS_ONLY' if mode=='RENKO' else 'HYBRID_COMPLETED_UNITS'))
            while not overflow:
                if not direct:
                    was_pending=bool(executor.state.get('pending'));executor.poll()
                    if was_pending and not executor.state.get('pending'):engine.position=__import__('copy').deepcopy(executor.state.get('position'))
                if manager.poll(busy=bool(manual.pending)):return
                status=broker.stream_status()
                if generation is not None and (not status['connected'] or status['generation']!=generation):raise ValueError('Public stream disconnected/reconnected; halt for history reconciliation')
                try:tick=q.get(timeout=1)
                except queue.Empty:
                    if time.monotonic()-last_tick>30:
                        if feed_health.attempts == 0:
                            engine.entry_confirmation.clear()
                            engine.pending_direction = None
                            if hasattr(engine,'pending_underlying_flip'):engine.pending_underlying_flip=None
                            engine.band.consume_entry()
                        health=feed_health.check(broker,underlying,time.monotonic())
                        atomic(out/'source-health.json',dict(health,at=delta.clock(),symbol=underlying))
                        atomic(out/'heartbeat.json',dict(at=datetime.now(IST).isoformat(),mode='LIVE' if live else 'PAPER',symbol=symbol,selected_contract=engine.contract,calculation_mode=config.get('calculation_mode','RENKO'),source_health=health,native_sizing=getattr(engine,'native_sizing_status',None),moving_bands=engine.band.snapshot(engine.config),position_control=manager.status(),manual_entry_capable=False,reconfigure_capable=True,timeframe=config['timeframe'],runtime_session=config.get('runtime_session'),position=executor.state['position'],pending=executor.state['pending']))
                        # Waiting/recovery never executes a manual or automatic entry.
                        # Only a fresh validated selected-symbol tick resumes decisions.
                        continue
                    if not manager.entry_blocked:manual.poll()
                    if not manager.entry_blocked:control.poll(busy=bool(manual.pending or executor.state['pending']),position=bool(executor.state['position']))
                    engine.entry_paused=control.entry_blocked or manager.entry_blocked
                    continue
                if tick.get('symbol') not in bars:continue
                stamp,price=tick.get('exch_feed_time'),tick.get('ltp')
                if not isinstance(stamp,(int,float)) or not isinstance(price,(int,float)) or not math.isfinite(price) or price<=0 or not 0<=delta.clock()-stamp<=15:raise ValueError('Stale/invalid Delta source tick')
                current_status=broker.stream_status()
                if not current_status['connected']:raise ValueError('Public stream unavailable before processing tick')
                if generation is None:generation=current_status['generation']
                feed_health.reset()
                last_tick=time.monotonic();sym=tick['symbol']
                if direct and executor.state.get('pending') and time.monotonic()-last_reconcile>=1:
                    last_reconcile=time.monotonic()
                    try:
                        receipt=executor.reconcile_pending()
                        if receipt:
                            engine.position=__import__('copy').deepcopy(executor.state.get('position'))
                            journal.write(json.dumps(dict(reconciliation=receipt,recorded_at=delta.clock()))+'\n')
                            if receipt.get('filled_quantity') and receipt.get('broker_flat'):
                                result=dict(order_id=receipt['order_id'],filled_quantity=receipt['filled_quantity'],fill_price=receipt['fill_price'])
                                action=receipt['action'];journal.write(json.dumps(dict(action=action,result=result,recorded_at=delta.clock()))+'\n')
                                markers.append(dict(timestamp=action['timestamp'],source_timestamp=action['timestamp'],confirmed_at=delta.clock(),symbol=action['position']['symbol'],action=action['action'],price=receipt['fill_price'],mode='LIVE' if live else 'PAPER',confirmed=True,order_id=receipt['order_id']))
                                atomic(out/'markers.json',markers[-1000:])
                    except ValueError as error:
                        executor.state['reconciliation_notice']=str(error);executor.save()
                if manager.blocked:continue
                if not direct and sym==symbol and getattr(engine,'quote_exit_pending',None) and engine.position:
                    result=submit(engine.quote_exit_pending)
                    if not result.get('deferred'):engine.position=None
                if not manager.entry_blocked:manual.poll()
                if not manager.entry_blocked:control.poll(busy=bool(manual.pending or executor.state['pending']),position=bool(executor.state['position']))
                engine.entry_paused=control.entry_blocked or manager.entry_blocked
                if sym not in bars:continue
                if manual.pending is None and sym==symbol and executor.state['position'] is None and not executor.state.get('pending_reversal'):
                    broker.tick(underlying)
                    action=confirmed_flat_entry(engine,executor)
                    if action:submit(action)
                observation_sequence+=1
                live_event=dict(kind='price',series='underlying' if sym==underlying else 'premium',timestamp=stamp,available_at=delta.clock(),close=price,symbol=sym,source_basis='BROKER_LIVE_PRICE',sequence=observation_sequence)
                if direct or live_event['series']=='underlying' or config.get('signal_source')!='UNDERLYING':chart_source.append_observation(live_event,config['timeframe'])
                if not direct:
                    engine.entry_quotes_ready=True
                    try:broker.tick(underlying);broker.quote(symbol)
                    except ValueError:engine.entry_quotes_ready=False
                journal.write(json.dumps(dict(event=live_event))+'\n')
                for action in automatic_actions(engine,executor,manual,reversal.suppress_pending(engine,executor,chart_source.decide(engine,live_event)) if direct else retain_pending_actions(engine,executor,chart_source.decide(engine,live_event))):
                    if action['action']=='SELECT':continue
                    submit(action)
                    if direct:complete_reversal(engine,executor,action,submit)
                if manual.pending is None and not direct and engine.position is None and engine.signal_side():
                    side=engine.signal_side()
                    if engine.contract['option_type']!=side:
                        old=symbol;symbol=select()
                        if old!=symbol:unsubscribe_unused(old)
                        bars.pop(old,None);bars[symbol]=SourceBars(config['timeframe'],continuous=True,confirmed_closes=True)
                if sym not in bars:continue
                if not direct and sym!=underlying and config.get('signal_source')=='UNDERLYING':continue
                events=[]
                if sym==underlying and config.get('sma_exit_enabled'):
                    r=sma.update(stamp,price)
                    if r and r[0]>engine.last_time.get('sma',0):events.append(dict(kind='sma',timestamp=r[0],close=r[1]))
                r=bars[sym].update(stamp,price);kind='underlying' if sym==underlying else 'premium'
                if r and r[0]>engine.last_time.get(kind,0):events.append(dict(kind=kind,timestamp=r[0],close=r[1],symbol=sym))
                for event in events:
                    event=confirmed.confirm(event,event.get('symbol') or underlying,1 if event['kind']=='sma' else config['timeframe'],now=delta.clock(),previous=engine.last_time.get(event['kind']))
                    if event['kind']!='sma':chart_source.append(event,config['timeframe'])
                    journal.write(json.dumps(dict(event=event))+'\n');exited=False
                    actions=chart_source.decide(engine,event)
                    if direct:actions=reversal.suppress_pending(engine,executor,actions)
                    else:actions=retain_pending_actions(engine,executor,actions)
                    chart_source.append_bands(engine,event)
                    for action in automatic_actions(engine,executor,manual,actions):
                        if action['action']=='SELECT':continue
                        submit(action)
                        if direct:complete_reversal(engine,executor,action,submit)
                        exited=action['action']=='SELL' or action['action'].startswith('CLOSE_')
                    if manual.pending is None and not direct and engine.position is None and engine.signal_side():
                        side=engine.signal_side()
                        if exited or engine.contract['option_type']!=side:
                            old=symbol
                            if exited and config.get('signal_source')!='UNDERLYING':engine.pending_underlying_flip=None
                            symbol=select()
                            if old!=symbol:unsubscribe_unused(old)
                            bars.pop(old,None);bars[symbol]=SourceBars(config['timeframe'],continuous=True,confirmed_closes=True)
                if not direct:executor.dispatch_entries(submit,lambda action:entry_valid(engine,action))
                if not direct:executor.poll()
                if direct and executor.state.get('pending_reversal') and not executor.state.get('pending'):
                    reversal.advance(engine,executor,submit)
                if time.monotonic()-last_write>=1:
                    atomic(out/'heartbeat.json',dict(at=datetime.now(IST).isoformat(),mode='LIVE' if live else 'PAPER',symbol=symbol,selected_contract=engine.contract,calculation_mode=config.get('calculation_mode','RENKO'),native_sizing=getattr(engine,'native_sizing_status',None),moving_bands=engine.band.snapshot(engine.config),entry_execution_policy=config['entry_execution_policy'],position_control=manager.status(),manual_entry_capable=not manager.entry_blocked,reconfigure_capable=True,timeframe=config['timeframe'],runtime_session=config.get('runtime_session'),position=executor.state['position'],pending=executor.state['pending']))
                    last_write=time.monotonic()
            raise ValueError('Delta source queue overflow; halted')
    finally:
        if getattr(engine,'close_native_sizing',None):engine.close_native_sizing()
        if executor:
            atomic(out/'heartbeat.json',dict(at=datetime.now(IST).isoformat(),mode='LIVE' if live else 'PAPER',symbol=symbol,selected_contract=getattr(engine,'contract',None),exit_waiting_for_quote=bool(getattr(engine,'quote_exit_pending',None)),position=executor.state['position'],pending=executor.state['pending']))
            executor.close()
        if broker:broker.stop()
        delta.requester.close()
