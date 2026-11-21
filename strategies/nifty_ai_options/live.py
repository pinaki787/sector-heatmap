"""Explicitly opted-in live or default paper WebSocket runtime; no dashboard calls."""
import csv,hashlib,io,json,math,os,queue,threading,time
from datetime import datetime,timedelta
from pathlib import Path
import requests
try:
    from .core import Strategy,select_contract,sizes
    from .execution import Execution
    from .run import client,ok,atomic,normalize,normalize_closes,IST,ROOT
except ImportError:
    from core import Strategy,select_contract,sizes
    from execution import Execution
    from run import client,ok,atomic,normalize,normalize_closes,IST,ROOT
def underlying(config):
    symbol=config.get('underlying')
    if not symbol or not symbol.startswith(('NSE:','BSE:')):raise ValueError('Explicit NSE/BSE underlying required for this options adapter')
    return symbol

def exposure_prefix(config):
    symbol=underlying(config);exchange,name=symbol.split(':',1)
    name=name.removesuffix('-INDEX').removesuffix('-EQ')
    name={'NIFTY50':'NIFTY','NIFTYBANK':'BANKNIFTY'}.get(name,name)
    return exchange+':'+name

class Reads:
    def __init__(self,api):self.api=api;self.last=0
    def __getattr__(self,name):
        method=getattr(self.api,name)
        if not callable(method):return method
        def call(*a,**kw):
            wait=.35-(time.monotonic()-self.last)
            if wait>0:time.sleep(wait)
            self.last=time.monotonic()
            return method(*a,**kw)
        return call

class Master:
    def __init__(self,directory):self.directory=Path(directory);self.rows={};self.days={}
    def __call__(self,symbol):
        today=datetime.now(IST).date().isoformat()
        exchange=str(symbol).split(':')[0]
        if exchange not in ('NSE','BSE'):raise ValueError('Unsupported FYERS options exchange')
        if self.days.get(exchange)!=today:
            response=requests.get('https://public.fyers.in/sym_details/'+exchange+'_FO.csv',timeout=(5,30));response.raise_for_status()
            self.rows.update({r[9]:r for r in csv.reader(io.StringIO(response.text)) if len(r)>17})
            self.days[exchange]=today
            self.directory.mkdir(parents=True,exist_ok=True)
            (self.directory/(exchange+'_FO.csv')).write_text(response.text)
        r=self.rows.get(symbol)
        if not r or r[16] not in ('CE','PE'):raise ValueError('Option absent from daily FYERS master')
        lot=float(r[3]);tick=float(r[4])
        if not math.isfinite(lot) or not lot.is_integer() or lot<1 or not math.isfinite(tick) or tick<=0:raise ValueError('Invalid daily master metadata')
        return dict(symbol=symbol,lot_size=int(lot),tick_size=tick,expiry_epoch=r[8],option_type=r[16],underlying_asset=r[13])

def history(api,symbol,frame,start,end,audit_dir=None):
    from sector_heatmap.fyers_history import history as fetch
    result=ok(fetch(api,dict(symbol=symbol,resolution=str(frame),date_format=1,range_from=start,range_to=end,cont_flag=0)))
    rows,audit=normalize_closes(result.get('candles',[]))
    if audit_dir is not None:
        key=hashlib.sha256(json.dumps([symbol,frame,start,end]).encode()).hexdigest()[:20]
        atomic(Path(audit_dir)/(key+'-raw.json'),result)
        atomic(Path(audit_dir)/(key+'-audit.json'),dict(audit,symbol=symbol,frame=frame,start=start,end=end))
    now=time.time()
    return [r for r in rows if r[0]+frame*60<=now and 555<=datetime.fromtimestamp(r[0],IST).hour*60+datetime.fromtimestamp(r[0],IST).minute<930]

def validate_config(config,api):
    if not config.get('account'):raise ValueError('Explicit account required')
    if isinstance(config.get('lots'),bool) or not isinstance(config.get('lots'),int) or config['lots']<1:raise ValueError('Explicit lots required')
    if config.get('product') not in ('MARGIN','INTRADAY'):raise ValueError('Explicit MARGIN/INTRADAY product required')
    # The supplied reference is the NATIVE chart ATR brick setting, not synthetic-Renko OHLC ATR.
    if config.get('reference_symbol')!=config.get('underlying'):raise ValueError('Native reference belongs to another selected underlying')
    if config.get('reference_source') not in ('external_native_renko_6h_atr5','external_native_parent_atr5','verified_native_cache'):raise ValueError('Explicit native Renko 6h ATR5 reference source required')
    if not config.get('reference_evidence'):raise ValueError('Dated reference evidence description required')
    positive=config.get('reference_value')
    if not isinstance(positive,(float,int)) or isinstance(positive,bool) or not math.isfinite(positive) or positive<=0:raise ValueError('Supply verified reference_value; example 400 is not a measured baseline')
    Strategy(config)
    today=datetime.now(IST).date()
    if today.year!=2026:raise ValueError('Calendar is validated for 2026 only; update calendar acceptance')
    prior=history(api,underlying(config),15,(today-timedelta(days=14)).isoformat(),(today-timedelta(days=1)).isoformat())
    sessions=sorted(set(datetime.fromtimestamp(r[0],IST).date().isoformat() for r in prior))
    if not sessions or config.get('reference_session')!=sessions[-1]:raise ValueError('Reference must be dated to actual previous available completed trading session: '+str(sessions[-1] if sessions else None))
    profile=ok(api.get_profile());identity=(profile.get('data') or {}).get('fy_id')
    if not identity:raise ValueError('Missing account identity')
    positions=ok(api.positions()).get('netPositions')
    orders=ok(api.orderbook()).get('orderBook')
    if not isinstance(positions,list) or not isinstance(orders,list):raise ValueError('Unrecognized broker reconciliation response')
    return dict(account_sha256=hashlib.sha256(str(identity).encode()).hexdigest(),reference_session=sessions[-1],
                existing_nifty_positions=sum(int(p.get('netQty',0))!=0 for p in positions if str(p.get('symbol','')).startswith(exposure_prefix(config))),
                existing_nifty_pending_orders=sum(p.get('status') in (1,4,6) for p in orders if str(p.get('symbol','')).startswith(exposure_prefix(config))))

def nearest_expiry(data,now=None):
    """Provider expiry epoch is the cutoff; never invent an exchange calendar."""
    now=time.time() if now is None else now
    valid=[]
    for row in data.get('expiryData',[]):
        try:epoch=int(row['expiry'])
        except (KeyError,TypeError,ValueError):continue
        if epoch>now:valid.append(epoch)
    if not valid:raise ValueError('No unexpired FYERS expiry metadata available')
    return str(min(valid))

def choose(api,master,config,side,require_reference=True):
    # Re-resolve on every new selection; a position retains its frozen contract.
    first=ok(api.optionchain(data=dict(symbol=underlying(config),strikecount=50,timestamp='',greeks='1')))
    expiry=nearest_expiry(first.get('data') or {})
    reply=ok(api.optionchain(data=dict(symbol=underlying(config),strikecount=50,timestamp=expiry,greeks='1')))
    data=reply.get('data') or {}
    if expiry!=nearest_expiry(data):raise ValueError('FYERS expiry metadata changed during selection')
    headers=[r for r in data.get('optionsChain',[]) if not r.get('option_type') and r.get('symbol')==underlying(config)]
    if len(headers)!=1:raise ValueError('Option chain does not identify the exact selected underlying')
    chain_asset=headers[0].get('ex_symbol')
    rows=[]
    for row in data.get('optionsChain',[]):
        if row.get('option_type')!=side:continue
        meta=master(row.get('symbol'))
        if chain_asset and meta.get('underlying_asset')!=chain_asset:raise ValueError('Option chain/master underlying mismatch')
        if str(meta['expiry_epoch'])!=expiry or meta['option_type']!=side:raise ValueError('Chain/master expiry mismatch')
        rows.append(dict(row,expiry=expiry))
    contract=select_contract(rows,side,expiry,config.get('target_premium',40))
    meta=master(contract['symbol'])
    if float(meta['expiry_epoch'])<=time.time():raise ValueError('Selected contract has reached provider expiry cutoff')
    delta=(contract.get('greeks') or {}).get('delta')
    if not isinstance(delta,(int,float)) or isinstance(delta,bool):raise ValueError('No provider option delta')
    if (side=='CE' and delta<=0) or (side=='PE' and delta>=0):raise ValueError('Delta sign disagrees with option type')
    if not math.isfinite(delta) or not 0<abs(delta)<=1:raise ValueError('Invalid provider delta')
    if require_reference:sizes(config['reference_value'],delta,config.get('market','NSE'),config.get('asset'))
    return dict(symbol=contract['symbol'],option_type=side,expiry=expiry,selection_ltp=contract['ltp'],selected_at=time.time(),lot_size=meta['lot_size'],underlying=underlying(config),underlying_asset=meta.get('underlying_asset')),delta

def preflight(args):
    config=json.loads(Path(args.config).read_text());raw=client(config['account']);api=Reads(raw)
    try:
        summary=validate_config(config,api)
        summary['market_status']=ok(api.market_status())
        master=Master(Path(args.output)/'master')
        summary['contracts']={}
        for side in ('CE','PE'):
            contract,delta=choose(api,master,config,side)
            spot,option=sizes(config['reference_value'],delta)
            summary['contracts'][side]=dict(contract,delta=delta,spot_brick=spot,option_brick=option)
        summary['resolved_expiry']=summary['contracts']['CE']['expiry']
        if summary['contracts']['PE']['expiry']!=summary['resolved_expiry']:raise ValueError('Expiry changed during preflight; repeat read-only preparation')
        summary.update(read_only=True,orders_submitted=0,live_orders_enabled=False,stream_started=False,checked_at=datetime.now(IST).isoformat())
        atomic(Path(args.output)/'preflight.json',summary);print(json.dumps(summary,indent=2))
    finally:raw._sector_pulse_ipv4_session.close()

try:from .markets import SourceBars
except ImportError:from markets import SourceBars

class Bars(SourceBars):
    """NSE/BSE source candles start at09:15, including thirty-minute frames."""
    def __init__(self,frame,*,confirmed_closes=False):
        super().__init__(frame,opening_minutes=555,closing_minutes=930,confirmed_closes=confirmed_closes)

def stream(args):
    config=json.loads(Path(args.config).read_text())
    if config.get('_verification_only'):raise ValueError('Verification-only configuration cannot start a stream or submit orders')
    live=args.live
    if live and os.getenv('AI_RENKO_LIVE_ORDERS',os.getenv('NIFTY_AI_LIVE_ORDERS'))!='I_ACCEPT_REAL_ORDERS':raise ValueError('Live requires user-set NIFTY_AI_LIVE_ORDERS=I_ACCEPT_REAL_ORDERS')
    if not config.get('accept_close_source_renko_approximation',False):raise ValueError('Explicit close-source approximation acceptance required; TV parity not certified')
    from sector_heatmap.market_calendar import market_session
    if market_session()['status']!='OPEN':raise ValueError('NSE regular session is not open; use preflight instead')
    raw=client(config['account']);api=Reads(raw);out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    socket=None;executor=None
    try:
        summary=validate_config(config,api)
        master=Master(out/'master')
        executor=Execution(api,summary['account_sha256'],ROOT/'.private/nifty-ai-options/runtime',live=live,lots=config['lots'],product=config['product'],master=master,account_folder=ROOT/'.private/dashboard-login/accounts'/config['account'])
        try:from .confirmed_close import ConfirmedClose,fyers_reader
        except ImportError:from confirmed_close import ConfirmedClose,fyers_reader
        confirmed=ConfirmedClose(fyers_reader(api),out/'confirmed-source')
        try:from .chart_source import ChartSource
        except ImportError:from chart_source import ChartSource
        chart_source=ChartSource(out/'chart-source')
        signal_symbol=underlying(config)
        engine=Strategy(config);today=datetime.now(IST).date()
        start=(today-timedelta(days=14)).isoformat();end=today.isoformat()
        under=history(api,underlying(config),config['timeframe'],start,end,out/'source-history')
        if not under:raise ValueError('No underlying warm-up history')
        chart_source.seed(signal_symbol,config['timeframe'],under,engine.spot_size)
        for r in under:
            engine.update(dict(kind='underlying',timestamp=r[0],close=r[4]))
            engine.position=None
        def select():
            side='CE' if engine.under_result and engine.under_result['direction']<0 else 'PE'
            contract,delta=choose(api,master,config,side)
            engine.reset_contract(contract,delta);engine.last_time.pop('premium',None)
            rows=history(api,contract['symbol'],config['timeframe'],start,end,out/'source-history')
            if not rows:raise ValueError('No selected option warm-up history')
            chart_source.seed(contract['symbol'],config['timeframe'],rows,engine.contract['option_brick'])
            for r in rows:
                engine.update(dict(kind='premium',timestamp=r[0],close=r[4],symbol=contract['symbol']))
                engine.position=None
            if engine.premium_result is None or engine.premium_result['host_atr'] is None:raise ValueError('Insufficient selected-option Renko indicator warm-up')
            return contract['symbol']
        symbol=select();engine.pending_underlying_flip=None
        if config.get('sma_exit_enabled',False):
            for r in history(api,underlying(config),1,start,end,out/'source-history'):
                engine.update(dict(kind='sma',timestamp=r[0],close=r[4]))
        import certifi
        from fyers_apiv3.FyersWebsocket import data_ws
        os.environ.setdefault('SSL_CERT_FILE',certifi.where())
        q=queue.Queue(maxsize=20000);quotes={};bars={signal_symbol:Bars(config['timeframe'],confirmed_closes=True),symbol:Bars(config['timeframe'],confirmed_closes=True)};sma=Bars(1,confirmed_closes=True)
        def message(data):
            try:q.put_nowait(('tick',data))
            except queue.Full:
                # Single fail-closed marker; no dropped ticks followed by trading.
                stopped.set()
        stopped=threading.Event()
        def failure(*unused):stopped.set()
        def connected():
            socket.subscribe(symbols=[signal_symbol,symbol],data_type='SymbolUpdate')
        socket=data_ws.FyersDataSocket(access_token=raw.header,log_path=str(out),litemode=False,write_to_file=False,reconnect=False,on_connect=connected,on_close=failure,on_error=failure,on_message=message)
        threading.Thread(target=socket.connect,daemon=True).start()
        marker_events=[]
        def record_fill(action,result):
            marker_events.append(dict(timestamp=action['timestamp'],source_timestamp=action['timestamp'],confirmed_at=time.time(),symbol=action['position']['symbol'],action=action['action'],price=result.get('fill_price',result.get('simulated_fill')),mode='LIVE' if live else 'PAPER',order_id=result.get('order_id'),confirmed=True))
            atomic(out/'markers.json',marker_events[-1000:])
        journal=(out/'events.jsonl').open('a',buffering=1)
        last_tick=time.monotonic()
        while not stopped.is_set():
            try:_,tick=q.get(timeout=1)
            except queue.Empty:
                if time.monotonic()-last_tick>30:raise ValueError('Stream heartbeat stalled; halted without order mutation')
                continue
            if not isinstance(tick,dict) or tick.get('symbol') not in bars:continue
            at=tick.get('exch_feed_time') or tick.get('last_traded_time');price=tick.get('ltp')
            if not isinstance(at,(int,float)) or not isinstance(price,(int,float)):continue
            if at>1e12:at/=1000
            if not math.isfinite(price) or price<=0 or not 0<=time.time()-at<=5:raise ValueError('Stale/invalid provider tick; halted')
            last_tick=time.monotonic();sym=tick['symbol'];quotes[sym]=dict(timestamp=at,ltp=price)
            events=[]
            # A newly selected contract may complete the underlying-flip gate once its fresh quote arrives.
            if sym==symbol and signal_symbol in quotes and 0<=time.time()-quotes[signal_symbol]['timestamp']<=5:
                selected_entry=engine.selected_gate_entry()
                if selected_entry:
                    result=executor.submit(selected_entry,quotes[symbol]);record_fill(selected_entry,result)
                    journal.write(json.dumps(dict(action=selected_entry,result=result))+'\n')
                    print(json.dumps(result),flush=True)
            if sym==signal_symbol and config.get('sma_exit_enabled',False):
                row=sma.update(at,price)
                if row and row[0]>engine.last_time.get('sma',0):events.append(dict(kind='sma',timestamp=row[0],close=row[1]))
            row=bars[sym].update(at,price)
            kind='underlying' if sym==signal_symbol else 'premium'
            if row and row[0]>engine.last_time.get(kind,0):events.append(dict(kind=kind,timestamp=row[0],close=row[1],symbol=sym))
            for event in events:
                event=confirmed.confirm(event,event.get('symbol') or signal_symbol,1 if event['kind']=='sma' else config['timeframe'],previous=engine.last_time.get(event['kind']),continuous=False,opening_minutes=555)
                if market_session()['status']!='OPEN':raise ValueError('Session closed; halted without forced exit')
                if event['kind']!='sma':chart_source.append(event,config['timeframe'])
                journal.write(json.dumps(dict(event=event))+'\n')
                exited=False
                for action in engine.update(event):
                    if action['action']=='SELECT':continue
                    if action['action']=='BUY':
                        for required in (signal_symbol,symbol):
                            if required not in quotes or not 0<=time.time()-quotes[required]['timestamp']<=5:raise ValueError('Both underlying and premium fresh quotes required')
                    result=executor.submit(action,quotes.get(action['position']['symbol']));record_fill(action,result)
                    if action['action']=='SELL':exited=True
                    journal.write(json.dumps(dict(action=action,result=result))+'\n');print(json.dumps(result),flush=True)
                if engine.position is None and engine.under_result:
                    side='CE' if engine.under_result['direction']<0 else 'PE'
                    if exited or engine.contract['option_type']!=side:
                        old=symbol
                        if exited:engine.pending_underlying_flip=None
                        symbol=select()
                        socket.unsubscribe(symbols=[old],data_type='SymbolUpdate')
                        bars.pop(old,None);bars[symbol]=Bars(config['timeframe'],confirmed_closes=True)
                        socket.subscribe(symbols=[symbol],data_type='SymbolUpdate')
            atomic(out/'heartbeat.json',dict(at=datetime.now(IST).isoformat(),mode='LIVE' if live else 'PAPER',symbol=symbol,selected_contract=engine.contract,position=executor.state['position'],pending=executor.state['pending']))
        raise ValueError('Stream disconnected/overflow; halted; existing broker exposure preserved')
    finally:
        if socket:
            try:socket.close_connection()
            except Exception:pass
        if executor:
            try:
                atomic(out/'heartbeat.json',dict(at=datetime.now(IST).isoformat(),mode='LIVE' if live else 'PAPER',symbol=config['underlying'],selected_contract=getattr(locals().get('engine'),'contract',None),position=executor.state['position'],pending=executor.state['pending'],terminal=True))
            finally:executor.close()
        raw._sector_pulse_ipv4_session.close()
