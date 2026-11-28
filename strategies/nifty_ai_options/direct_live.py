from strategies.nifty_ai_options.multi_runner import runtime_root,configure_executor,worker_admission
"""Explicitly user-started FYERS direct stock/future runtime; Paper by default."""
import json,math,os,queue,threading,time
from pathlib import Path
from datetime import datetime,timedelta
try:
    from .run import client,ok,atomic,normalize_closes,IST,ROOT
    from .live import Reads
    from .markets import FyersInstrumentMaster,margin_reader,SourceBars
    from .direct import DirectStrategy,complete_reversal
    from .direct_execution import DirectExecution
    from . import reversal
except ImportError:
    from run import client,ok,atomic,normalize_closes,IST,ROOT
    from live import Reads
    from markets import FyersInstrumentMaster,margin_reader,SourceBars
    from direct import DirectStrategy,complete_reversal
    from direct_execution import DirectExecution
    import reversal

def market_open(api,meta):
    try:from .markets import fyers_market_open
    except ImportError:from markets import fyers_market_open
    return fyers_market_open(api,meta)

try:from .sma_band import band_enabled,retain_broker_ohlc
except ImportError:from sma_band import band_enabled,retain_broker_ohlc

def history(api,config,meta,frame,directory):
    from sector_heatmap.fyers_history import history as fetch
    today=datetime.now(IST).date();start=(today-timedelta(days=21)).isoformat()
    raw=ok(fetch(api,dict(symbol=config['underlying'],resolution=str(frame),date_format=1,range_from=start,range_to=today.isoformat(),cont_flag=0)))
    atomic(Path(directory)/(str(frame)+'m-raw.json'),raw)
    rows,audit=normalize_closes(raw.get('candles',[]));atomic(Path(directory)/(str(frame)+'m-audit.json'),audit)
    if band_enabled(config) or config.get('zone_targets_enabled') or config.get('grid_trailing_enabled') or config.get('calculation_mode') in ('CANDLES','HYBRID'):rows=retain_broker_ohlc(rows,raw.get('candles',[]))
    return [r for r in rows if r[0]+frame*60<=time.time() and meta['opening_minutes']<=datetime.fromtimestamp(r[0],IST).hour*60+datetime.fromtimestamp(r[0],IST).minute<meta['closing_minutes']]

def inspect(config,api,master):
    if config.get('broker')!='FYERS' or config.get('execution_route')!='DIRECT':raise ValueError('Exact FYERS direct route required')
    if config.get('reference_symbol')!=config.get('underlying'):raise ValueError('Native reference must identify this exact selected instrument')
    if not config.get('reference_session') or not config.get('reference_evidence'):raise ValueError('Dated native parent reference required')
    if isinstance(config.get('lots'),bool) or not isinstance(config.get('lots'),int) or config['lots']<1:raise ValueError('Explicit whole lots/shares required')
    DirectStrategy(config)
    meta=master(config['underlying'])
    if meta['product_type']=='STOCK' and config.get('product') not in ('CNC','INTRADAY'):raise ValueError('Cash stock requires CNC or INTRADAY product')
    if meta['product_type']=='FUTURE' and config.get('product') not in ('MARGIN','INTRADAY'):raise ValueError('Future requires MARGIN or INTRADAY product')
    profile=ok(api.get_profile());identity=(profile.get('data') or {}).get('fy_id')
    if not identity:raise ValueError('Missing exact broker identity')
    import hashlib
    return dict(account_sha256=hashlib.sha256(str(identity).encode()).hexdigest(),instrument=meta,market_open=market_open(api,meta),read_only=True,orders_submitted=0)

def preflight(args):
    config=json.loads(Path(args.config).read_text());raw=client(config['account'])
    try:
        summary=inspect(config,Reads(raw),FyersInstrumentMaster(Path(args.output)/'master'))
        summary.update(spot_brick=DirectStrategy(config).spot_size,stream_started=False)
        atomic(Path(args.output)/'preflight.json',summary);print(json.dumps(summary,indent=2))
    finally:raw._sector_pulse_ipv4_session.close()

try:from .automatic_sizing import automatic_strategy,runtime_configuration
except ImportError:from automatic_sizing import automatic_strategy,runtime_configuration

try:
 from .position_control import entry_guard,EntryBlocked
except ImportError:
 from position_control import entry_guard,EntryBlocked
from contextlib import nullcontext

def stream(args):
    config=json.loads(Path(args.config).read_text());worker_admission(config,getattr(args,'output',None));live=args.live
    if config.get('_verification_only'):raise ValueError('Verification-only config cannot start a stream or orders')
    if live and os.getenv('AI_RENKO_LIVE_ORDERS',os.getenv('NIFTY_AI_LIVE_ORDERS'))!='I_ACCEPT_REAL_ORDERS':raise ValueError('Explicit Live environment opt-in required')
    if not config.get('accept_close_source_renko_approximation'):raise ValueError('Review the confirmed-close Renko basis before Start')
    config.setdefault('execution_mode','LIVE' if live else 'PAPER')
    if not config.get('_managed_resume'):config=runtime_configuration(config,Path(args.output))
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True);raw=client(config['account']);api=Reads(raw)
    socket=executor=None
    try:
        master=FyersInstrumentMaster(out/'master');summary=inspect(config,api,master);meta=summary['instrument']
        atomic(out/'preflight.json',summary)
        if config.get('_managed_resume') and config.get('_resume_account_sha256')!=summary['account_sha256']:raise ValueError('Resume broker account identity differs from captured ownership')
        executor=DirectExecution(api,summary['account_sha256'],runtime_root(config),live=live,lots=config['lots'],product=config['product'],master=master,account_folder=ROOT/'.private/dashboard-login/accounts'/config['account'],margin=margin_reader(raw),management_only=config.get('_managed_resume',False))
        configure_executor(executor,config)
        try:from .confirmed_close import ConfirmedClose,fyers_reader
        except ImportError:from confirmed_close import ConfirmedClose,fyers_reader
        confirmed=ConfirmedClose(fyers_reader(api),out/'confirmed-source')
        try:from .chart_source import ChartSource
        except ImportError:from chart_source import ChartSource
        chart_source=ChartSource(out/'chart-source',calculation_mode=config.get('calculation_mode','RENKO'))
        engine=automatic_strategy(DirectStrategy(config),config,exposure=lambda:bool(executor.state['position'] or executor.state['pending'] or executor.state.get('detached_position')),chart_source=chart_source,config_path=out/'config.json');engine.reset_contract(dict(meta,underlying=config['underlying'],execution_route='DIRECT'))
        rows=history(api,config,meta,config['timeframe'],out/'source-history')
        if not rows:raise ValueError('No completed selected-instrument warm-up history')
        chart_source.seed(config['underlying'],config['timeframe'],rows,engine.spot_size)
        for r in rows:engine.update(dict(kind='underlying',timestamp=r[0],open=r[1],high=r[2],low=r[3],close=r[4]));engine.position=None
        chart_source.seed_bands(engine)
        if config.get('sma_exit_enabled'):
            for r in history(api,config,meta,1,out/'source-history'):engine.update(dict(kind='sma',timestamp=r[0],close=r[4]))
        engine.entry_reset_at=time.time();engine.pending_direction=None
        bars=SourceBars(config['timeframe'],opening_minutes=meta['opening_minutes'],closing_minutes=meta['closing_minutes'],confirmed_closes=True)
        sma=SourceBars(1,opening_minutes=meta['opening_minutes'],closing_minutes=meta['closing_minutes'],confirmed_closes=True)
        q=queue.Queue(maxsize=20000);stopped=threading.Event();symbol=config['underlying'];last_tick=time.monotonic();last_write=0;markers=[];observation_sequence=0
        try:from .manual_entry import LatestQuote,ManualDispatcher,automatic_actions,confirm_entry_fill,restore_unsubmitted
        except ImportError:from manual_entry import LatestQuote,ManualDispatcher,automatic_actions,confirm_entry_fill,restore_unsubmitted
        latest_quote=LatestQuote(symbol)
        import certifi
        os.environ.setdefault('SSL_CERT_FILE',certifi.where())
        from fyers_apiv3.FyersWebsocket import data_ws
        def message(tick):
            latest_quote.accept(tick)
            try:q.put_nowait(tick)
            except queue.Full:stopped.set()
        try:from .session_wait import SessionWait,reconcile_bodies,ReopenConnection,SavedAccountSession
        except ImportError:from session_wait import SessionWait,reconcile_bodies,ReopenConnection,SavedAccountSession
        def verify_saved_session(candidate):
            import hashlib
            identity=(ok(candidate.get_profile()).get('data') or {}).get('fy_id')
            if not identity or hashlib.sha256(str(identity).encode()).hexdigest()!=summary['account_sha256']:
                raise ValueError('Saved broker session identity differs from the active run')
        def apply_saved_session(candidate):
            nonlocal raw
            raw=candidate;api.api=candidate
            if socket is not None:socket.access_token=candidate.header
            executor.margin=margin_reader(candidate)
        account_folder=ROOT/'.private/dashboard-login/accounts'/config['account']
        saved_session=SavedAccountSession(raw,[account_folder/'credentials.json',account_folder/'home/.fyers/token.json'],load=lambda:client(config['account']),verify=verify_saved_session,apply=apply_saved_session)
        def current_market_open():
            saved_session.refresh()
            return market_open(api,master(symbol))
        def current_bounds():
            current=master(symbol)
            opening,closing=current['opening_minutes'],current['closing_minutes']
            if any(isinstance(v,bool) or not isinstance(v,int) for v in (opening,closing)) or not 0<=opening<closing<=1440:raise ValueError('Selected broker regular-session bounds unavailable')
            meta.update(opening_minutes=opening,closing_minutes=closing)
            return meta
        session=SessionWait(current_market_open,meta['opening_minutes'],meta['closing_minutes'],clock=lambda:time.time(),bounds=current_bounds)
        source_unavailable=threading.Event();source_unavailable.set();source_failed=threading.Event()
        def failure(*unused):
            if reopen.restarting:return
            source_unavailable.set();source_failed.set()
        def connected():
            socket.subscribe(symbols=[symbol],data_type='SymbolUpdate');source_unavailable.clear();source_failed.clear()
        def make_socket():
            return data_ws.FyersDataSocket(access_token=raw.header,log_path=str(out),litemode=False,write_to_file=False,reconnect=False,on_connect=connected,on_close=failure,on_error=failure,on_message=message)
        def reconnect_source():
            nonlocal socket
            source_unavailable.set();source_failed.clear()
            socket.close_connection()
            saved_session.refresh(force=True)
            socket=make_socket()
            threading.Thread(target=socket.connect,daemon=True).start()
        reopen=ReopenConnection(reconnect_source)
        socket=make_socket()
        threading.Thread(target=socket.connect,daemon=True).start()
        with (out/'events.jsonl').open('a',buffering=1) as journal:
            def submit(action,quote):
                reversal.remember(engine,executor,action)
                if stopped.is_set():raise ValueError('Source unavailable before order')
                if source_unavailable.is_set() or not current_market_open():
                    restore_unsubmitted(engine,executor,action);session.poll(force=True);heartbeat()
                    return dict(deferred=True,reason='WAITING_FOR_SOURCE' if source_unavailable.is_set() else 'WAITING_FOR_MARKET')
                quote=latest_quote.get()
                if stopped.is_set() or source_unavailable.is_set():
                    restore_unsubmitted(engine,executor,action)
                    return dict(deferred=True,reason='WAITING_FOR_SOURCE')
                try:
                    with entry_guard(out,executor) if action['action'].startswith('OPEN_') else nullcontext():
                        result=reversal.execute(engine,executor,action,lambda:executor.submit(action,quote))
                except EntryBlocked:
                    restore_unsubmitted(engine,executor,action)
                    return dict(deferred=True,reason='WAITING_FOR_POSITION_CONTROL')
                if result.get('deferred'):
                    journal.write(json.dumps(dict(action=action,result=result,recorded_at=time.time()))+'\n')
                    return result
                reversal.entered(executor,action)
                confirm_entry_fill(engine,executor,action)
                journal.write(json.dumps(dict(action=action,result=result))+'\n')
                markers.append(dict(timestamp=action['timestamp'],source_timestamp=action['timestamp'],confirmed_at=time.time(),symbol=symbol,action=action['action'],price=result.get('fill_price',result.get('simulated_fill')),mode='LIVE' if live else 'PAPER',confirmed=True,order_id=result.get('order_id')))
                atomic(out/'markers.json',markers[-1000:]);print(json.dumps(result),flush=True)
                return result
            def manual_quote_ready():
                if stopped.is_set() or source_unavailable.is_set() or not current_market_open():raise ValueError('Market or source unavailable before manual entry')
                return latest_quote.get()['timestamp']
            manual=ManualDispatcher(config,out,'LIVE' if live else 'PAPER',engine,executor,prepare=lambda direction:None,quote_ready=manual_quote_ready,submit=lambda action:submit(action,latest_quote.get()))
            try:from .runtime_control import RuntimeControl
            except ImportError:from runtime_control import RuntimeControl
            def change_timeframe(frame):
                nonlocal bars
                chart_source.roll_timeframe([symbol],config['timeframe'],frame)
                bars=SourceBars(frame,opening_minutes=meta['opening_minutes'],closing_minutes=meta['closing_minutes'],confirmed_closes=True)
                engine.config['timeframe']=frame
                engine.last_time.pop('underlying',None);engine.last_time.pop('hybrid_candle',None)
                manual.inbox.expected['timeframe']=frame
            try:
                from .position_control import PositionManager
                from .position_brokers import FyersPositions
            except ImportError:
                from position_control import PositionManager
                from position_brokers import FyersPositions
            position_view=FyersPositions(api,config,master,summary['account_sha256'])
            def attach_holding(request):
                row=position_view.selected(request)
                return dict(engine.contract,side=row['side'],quantity=row['quantity'],product=row['product'],fill_price=row['average_price'],entry_timestamp=time.time(),attached_existing=True)
            manager=PositionManager(config,out,engine,executor,verify=lambda owned,**kw:position_view.verify(owned,**kw) if live else dict(flat=executor.state.get('position') is None if kw.get('flat') is True else False),attach=attach_holding,submit=lambda action:submit(action,latest_quote.get()),manual=manual)
            control=RuntimeControl(config,out,apply=change_timeframe,apply_mode=lambda mode:engine.config.update(display_mode=mode,exit_confirmation_mode='RENKO_BRICKS_ONLY' if mode=='RENKO' else 'HYBRID_COMPLETED_UNITS'))
            recovery_pending=True
            last_heartbeat=0;last_reconcile=0
            def heartbeat():
                nonlocal last_heartbeat
                now=time.monotonic()
                if now-last_heartbeat<1:return
                last_heartbeat=now
                atomic(out/'heartbeat.json',dict(at=datetime.now(IST).isoformat(),mode='LIVE' if live else 'PAPER',symbol=symbol,selected_contract=engine.contract,calculation_mode=config.get('calculation_mode','RENKO'),native_sizing=getattr(engine,'native_sizing_status',None),moving_bands=engine.band.snapshot(engine.config),midline_filter=getattr(engine,'midline_filter_status',None),position_control=manager.status(),manual_entry_capable=session.ready and not source_unavailable.is_set() and not manager.entry_blocked,source_state='WAITING_FOR_SOURCE' if source_unavailable.is_set() else 'READY',reconfigure_capable=True,timeframe=config['timeframe'],runtime_session=config.get('runtime_session'),position=executor.state['position'],pending=executor.state['pending'],**session.snapshot()))
            while not stopped.is_set():
                if manager.poll(busy=bool(manual.pending)):return
                session.poll(force=source_failed.is_set())
                reopen.observe(session.ready)
                if source_failed.is_set() and session.ready:
                    stopped.set();break
                if not session.ready:recovery_pending=True
                if session.changed:
                    last_tick=time.monotonic()
                    bars=SourceBars(config['timeframe'],opening_minutes=meta['opening_minutes'],closing_minutes=meta['closing_minutes'],confirmed_closes=True)
                    sma=SourceBars(1,opening_minutes=meta['opening_minutes'],closing_minutes=meta['closing_minutes'],confirmed_closes=True)
                    engine.pending_direction=None
                    from strategies.nifty_ai_options.manual_entry import clear_entry_signal
                    clear_entry_signal(engine)
                heartbeat()
                try:tick=q.get(timeout=1)
                except queue.Empty:
                    if not manager.entry_blocked:manual.poll()
                    if not manager.entry_blocked:control.poll(busy=bool(manual.pending or executor.state['pending']),position=bool(executor.state['position']))
                    engine.entry_paused=control.entry_blocked or manager.entry_blocked
                    if session.ready and time.monotonic()-last_tick>30:raise ValueError('Stream heartbeat stalled; exposure preserved')
                    continue
                if not session.ready:
                    session.poll()
                    reopen.observe(session.ready)
                    if not session.ready:continue
                    last_tick=time.monotonic()
                if source_unavailable.is_set():continue
                if not isinstance(tick,dict) or tick.get('symbol')!=symbol:continue
                stamp=tick.get('exch_feed_time') or tick.get('last_traded_time');price=tick.get('ltp')
                if not isinstance(stamp,(int,float)) or not isinstance(price,(int,float)):continue
                if stamp>1e12:stamp/=1000
                if not math.isfinite(price) or price<=0 or not 0<=time.time()-stamp<=5:raise ValueError('Stale/invalid provider tick; halted')
                local=datetime.fromtimestamp(stamp,IST)
                if not meta['opening_minutes']<=local.hour*60+local.minute<meta['closing_minutes']:continue
                if recovery_pending:
                    bars=SourceBars(config['timeframe'],opening_minutes=meta['opening_minutes'],closing_minutes=meta['closing_minutes'],confirmed_closes=True)
                    sma=SourceBars(1,opening_minutes=meta['opening_minutes'],closing_minutes=meta['closing_minutes'],confirmed_closes=True)
                    recovered=reconcile_bodies(engine,confirmed,[('underlying',symbol)],config['timeframe'],stamp,meta['opening_minutes'],sma_enabled=config.get('sma_exit_enabled',False))
                    journal.write(json.dumps(dict(session_recovery=recovered,orders_submitted=0,renko_state_retained=True))+'\n')
                    recovery_pending=False
                last_tick=time.monotonic();quote=dict(timestamp=stamp,ltp=price);events=[]
                if executor.state.get('pending') and time.monotonic()-last_reconcile>=1:
                    last_reconcile=time.monotonic()
                    try:
                        receipt=executor.reconcile_pending()
                        engine.position=__import__('copy').deepcopy(executor.state.get('position'));__import__('strategies.nifty_ai_options.zone_targets',fromlist=['reconciled']).reconciled(engine,executor)
                        if receipt:
                            journal.write(json.dumps(dict(reconciliation=receipt,recorded_at=time.time()))+'\n')
                            if receipt.get('filled_quantity') and receipt.get('broker_flat'):
                                result=dict(order_id=receipt['order_id'],filled_quantity=receipt['filled_quantity'],fill_price=receipt['fill_price'])
                                action=receipt['action'];journal.write(json.dumps(dict(action=action,result=result,recorded_at=time.time()))+'\n')
                                markers.append(dict(timestamp=action['timestamp'],source_timestamp=action['timestamp'],confirmed_at=time.time(),symbol=symbol,action=action['action'],price=receipt['fill_price'],mode='LIVE' if live else 'PAPER',confirmed=True,order_id=receipt['order_id']))
                                atomic(out/'markers.json',markers[-1000:])
                    except ValueError as error:
                        executor.state['reconciliation_notice']=str(error);executor.save()
                if manager.blocked:continue
                if getattr(engine,'session_sma_exit_pending',False) and engine.position:
                    action=engine.exit(time.time(),'OPTIONAL_UNDERLYING_1M_SMA30')[0]
                    result=submit(action,quote)
                    if not result.get('deferred'):engine.session_sma_exit_pending=False
                if not manager.entry_blocked:manual.poll()
                if not manager.entry_blocked:control.poll(busy=bool(manual.pending or executor.state['pending']),position=bool(executor.state['position']))
                engine.entry_paused=control.entry_blocked or manager.entry_blocked
                if manual.pending is None and executor.state['position'] is None and engine.pending_direction is not None:
                    if not session.poll(force=True):continue
                    pending_entry=engine.selected_gate_entry()
                    if pending_entry:submit(pending_entry,quote)
                observation_sequence+=1
                live_event=dict(kind='price',timestamp=stamp,available_at=time.time(),close=price,symbol=symbol,source_basis='BROKER_LIVE_PRICE',sequence=observation_sequence)
                chart_source.append_observation(live_event,config['timeframe'])
                journal.write(json.dumps(dict(event=live_event))+'\n')
                for action in automatic_actions(engine,executor,manual,reversal.suppress_pending(engine,executor,chart_source.decide(engine,live_event))):
                    submit(action,quote)
                    complete_reversal(engine,executor,action,lambda entry:submit(entry,quote))
                if config.get('sma_exit_enabled'):
                    row=sma.update(stamp,price)
                    if row and row[0]>engine.last_time.get('sma',0):events.append(dict(kind='sma',timestamp=row[0],close=row[1]))
                row=bars.update(stamp,price)
                if row and row[0]>engine.last_time.get('underlying',0):events.append(dict(kind='underlying',timestamp=row[0],close=row[1]))
                for event in events:
                    event=confirmed.confirm(event,event.get('symbol') or symbol,1 if event['kind']=='sma' else config['timeframe'],previous=engine.last_time.get(event['kind']),continuous=False,opening_minutes=meta['opening_minutes'])
                    if not session.poll(force=True):break
                    if event['kind']!='sma':chart_source.append(event,config['timeframe'])
                    journal.write(json.dumps(dict(event=event))+'\n')
                    actions=reversal.suppress_pending(engine,executor,chart_source.decide(engine,event))
                    chart_source.append_bands(engine,event)
                    for action in automatic_actions(engine,executor,manual,actions):
                        submit(action,quote)
                        complete_reversal(engine,executor,action,lambda entry:submit(entry,quote))
                if executor.state.get('pending_reversal') and not executor.state.get('pending'):
                    reversal.advance(engine,executor,lambda entry:submit(entry,quote))
                if time.monotonic()-last_write>=1:
                    heartbeat()
                    last_write=time.monotonic()
            raise ValueError('Stream disconnected/overflow; halted; broker exposure preserved')
    finally:
        if getattr(locals().get('engine'),'close_native_sizing',None):engine.close_native_sizing()
        if socket:
            try:socket.close_connection()
            except Exception:pass
        if executor:
            try:
                atomic(out/'heartbeat.json',dict(at=datetime.now(IST).isoformat(),mode='LIVE' if live else 'PAPER',symbol=config['underlying'],selected_contract=getattr(locals().get('engine'),'contract',None),position=executor.state['position'],pending=executor.state['pending'],terminal=True))
            finally:executor.close()
        raw._sector_pulse_ipv4_session.close()
