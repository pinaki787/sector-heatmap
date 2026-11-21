"""Explicitly user-started FYERS direct stock/future runtime; Paper by default."""
import json,math,os,queue,threading,time
from pathlib import Path
from datetime import datetime,timedelta
try:
    from .run import client,ok,atomic,normalize_closes,IST,ROOT
    from .live import Reads
    from .markets import FyersInstrumentMaster,margin_reader,SourceBars
    from .direct import DirectStrategy
    from .direct_execution import DirectExecution
except ImportError:
    from run import client,ok,atomic,normalize_closes,IST,ROOT
    from live import Reads
    from markets import FyersInstrumentMaster,margin_reader,SourceBars
    from direct import DirectStrategy
    from direct_execution import DirectExecution

def market_open(api,meta):
    rows=ok(api.market_status()).get('marketStatus')
    if not isinstance(rows,list):raise ValueError('Broker market status unavailable')
    rows=[r for r in rows if str(r.get('exchange'))==str(meta['exchange_code']) and str(r.get('segment'))==str(meta['segment_code']) and r.get('market_type')=='NORMAL']
    if len(rows)!=1:raise ValueError('Selected master exchange/segment status unavailable')
    return rows[0].get('status')=='OPEN'

def history(api,config,meta,frame,directory):
    from sector_heatmap.fyers_history import history as fetch
    today=datetime.now(IST).date();start=(today-timedelta(days=21)).isoformat()
    raw=ok(fetch(api,dict(symbol=config['underlying'],resolution=str(frame),date_format=1,range_from=start,range_to=today.isoformat(),cont_flag=0)))
    atomic(Path(directory)/(str(frame)+'m-raw.json'),raw)
    rows,audit=normalize_closes(raw.get('candles',[]));atomic(Path(directory)/(str(frame)+'m-audit.json'),audit)
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

def stream(args):
    config=json.loads(Path(args.config).read_text());live=args.live
    if config.get('_verification_only'):raise ValueError('Verification-only config cannot start a stream or orders')
    if live and os.getenv('AI_RENKO_LIVE_ORDERS',os.getenv('NIFTY_AI_LIVE_ORDERS'))!='I_ACCEPT_REAL_ORDERS':raise ValueError('Explicit Live environment opt-in required')
    if not config.get('accept_close_source_renko_approximation'):raise ValueError('Review the confirmed-close Renko basis before Start')
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True);raw=client(config['account']);api=Reads(raw)
    socket=executor=None
    try:
        master=FyersInstrumentMaster(out/'master');summary=inspect(config,api,master);meta=summary['instrument']
        atomic(out/'preflight.json',summary)
        if not summary['market_open']:raise ValueError('Selected broker exchange/segment is not open')
        executor=DirectExecution(api,summary['account_sha256'],ROOT/'.private/nifty-ai-options/runtime',live=live,lots=config['lots'],product=config['product'],master=master,account_folder=ROOT/'.private/dashboard-login/accounts'/config['account'],margin=margin_reader(raw))
        try:from .confirmed_close import ConfirmedClose,fyers_reader
        except ImportError:from confirmed_close import ConfirmedClose,fyers_reader
        confirmed=ConfirmedClose(fyers_reader(api),out/'confirmed-source')
        try:from .chart_source import ChartSource
        except ImportError:from chart_source import ChartSource
        chart_source=ChartSource(out/'chart-source')
        engine=DirectStrategy(config);engine.reset_contract(dict(meta,underlying=config['underlying'],execution_route='DIRECT'))
        rows=history(api,config,meta,config['timeframe'],out/'source-history')
        if not rows:raise ValueError('No completed selected-instrument warm-up history')
        chart_source.seed(config['underlying'],config['timeframe'],rows,engine.spot_size)
        for r in rows:engine.update(dict(kind='underlying',timestamp=r[0],close=r[4]));engine.position=None
        if config.get('sma_exit_enabled'):
            for r in history(api,config,meta,1,out/'source-history'):engine.update(dict(kind='sma',timestamp=r[0],close=r[4]))
        engine.pending_direction=None
        bars=SourceBars(config['timeframe'],opening_minutes=meta['opening_minutes'],closing_minutes=meta['closing_minutes'],confirmed_closes=True)
        sma=SourceBars(1,opening_minutes=meta['opening_minutes'],closing_minutes=meta['closing_minutes'],confirmed_closes=True)
        q=queue.Queue(maxsize=20000);stopped=threading.Event();symbol=config['underlying'];last_tick=time.monotonic();last_write=0;markers=[]
        import certifi
        os.environ.setdefault('SSL_CERT_FILE',certifi.where())
        from fyers_apiv3.FyersWebsocket import data_ws
        def message(tick):
            try:q.put_nowait(tick)
            except queue.Full:stopped.set()
        def failure(*unused):stopped.set()
        def connected():socket.subscribe(symbols=[symbol],data_type='SymbolUpdate')
        socket=data_ws.FyersDataSocket(access_token=raw.header,log_path=str(out),litemode=False,write_to_file=False,reconnect=False,on_connect=connected,on_close=failure,on_error=failure,on_message=message)
        threading.Thread(target=socket.connect,daemon=True).start()
        with (out/'events.jsonl').open('a',buffering=1) as journal:
            def submit(action,quote):
                result=executor.submit(action,quote)
                journal.write(json.dumps(dict(action=action,result=result))+'\n')
                markers.append(dict(timestamp=action['timestamp'],source_timestamp=action['timestamp'],confirmed_at=time.time(),symbol=symbol,action=action['action'],price=result.get('fill_price',result.get('simulated_fill')),mode='LIVE' if live else 'PAPER',confirmed=True,order_id=result.get('order_id')))
                atomic(out/'markers.json',markers[-1000:]);print(json.dumps(result),flush=True)
            while not stopped.is_set():
                try:tick=q.get(timeout=1)
                except queue.Empty:
                    if time.monotonic()-last_tick>30:raise ValueError('Stream heartbeat stalled; exposure preserved')
                    continue
                if not isinstance(tick,dict) or tick.get('symbol')!=symbol:continue
                stamp=tick.get('exch_feed_time') or tick.get('last_traded_time');price=tick.get('ltp')
                if not isinstance(stamp,(int,float)) or not isinstance(price,(int,float)):continue
                if stamp>1e12:stamp/=1000
                if not math.isfinite(price) or price<=0 or not 0<=time.time()-stamp<=5:raise ValueError('Stale/invalid provider tick; halted')
                last_tick=time.monotonic();quote=dict(timestamp=stamp,ltp=price);events=[]
                if executor.state['position'] is None and engine.pending_direction is not None:
                    if not market_open(api,master(symbol)):raise ValueError('Broker market closed before reversal entry')
                    pending_entry=engine.selected_gate_entry()
                    if pending_entry:submit(pending_entry,quote)
                if config.get('sma_exit_enabled'):
                    row=sma.update(stamp,price)
                    if row and row[0]>engine.last_time.get('sma',0):events.append(dict(kind='sma',timestamp=row[0],close=row[1]))
                row=bars.update(stamp,price)
                if row and row[0]>engine.last_time.get('underlying',0):events.append(dict(kind='underlying',timestamp=row[0],close=row[1]))
                for event in events:
                    event=confirmed.confirm(event,event.get('symbol') or symbol,1 if event['kind']=='sma' else config['timeframe'],previous=engine.last_time.get(event['kind']),continuous=False,opening_minutes=meta['opening_minutes'])
                    if not market_open(api,master(symbol)):raise ValueError('Broker market closed; no order mutation')
                    if event['kind']!='sma':chart_source.append(event,config['timeframe'])
                    journal.write(json.dumps(dict(event=event))+'\n')
                    for action in engine.update(event):submit(action,quote)
                if time.monotonic()-last_write>=1:
                    atomic(out/'heartbeat.json',dict(at=datetime.now(IST).isoformat(),mode='LIVE' if live else 'PAPER',symbol=symbol,selected_contract=engine.contract,position=executor.state['position'],pending=executor.state['pending']))
                    last_write=time.monotonic()
            raise ValueError('Stream disconnected/overflow; halted; broker exposure preserved')
    finally:
        if socket:
            try:socket.close_connection()
            except Exception:pass
        if executor:
            try:
                atomic(out/'heartbeat.json',dict(at=datetime.now(IST).isoformat(),mode='LIVE' if live else 'PAPER',symbol=config['underlying'],selected_contract=getattr(locals().get('engine'),'contract',None),position=executor.state['position'],pending=executor.state['pending'],terminal=True))
            finally:executor.close()
        raw._sector_pulse_ipv4_session.close()
