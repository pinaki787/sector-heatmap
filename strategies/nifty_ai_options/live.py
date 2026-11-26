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
    if not symbol or not symbol.startswith(('NSE:','BSE:','MCX:')):raise ValueError('Explicit NSE/BSE/MCX underlying required for this options adapter')
    return symbol

def exposure_prefix(config):
    symbol=underlying(config);exchange,name=symbol.split(':',1)
    name=name.removesuffix('-INDEX').removesuffix('-EQ')
    if exchange=='MCX':
        import re
        name=re.sub(r'\d{2}[A-Z]{3}FUT$','',name)
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
        if exchange not in ('NSE','BSE','MCX'):raise ValueError('Unsupported FYERS options exchange')
        if self.days.get(exchange)!=today:
            response=requests.get('https://public.fyers.in/sym_details/'+('MCX_COM.csv' if exchange=='MCX' else exchange+'_FO.csv'),timeout=(5,30));response.raise_for_status()
            self.rows.update({r[9]:r for r in csv.reader(io.StringIO(response.text)) if len(r)>17})
            self.days[exchange]=today
            self.directory.mkdir(parents=True,exist_ok=True)
            (self.directory/(('MCX_COM.csv' if exchange=='MCX' else exchange+'_FO.csv'))).write_text(response.text)
        r=self.rows.get(symbol)
        if not r or r[16] not in ('CE','PE'):raise ValueError('Option absent from daily FYERS master')
        lot=float(r[3]);tick=float(r[4])
        if not math.isfinite(lot) or not lot.is_integer() or lot<1 or not math.isfinite(tick) or tick<=0:raise ValueError('Invalid daily master metadata')
        opening,closing=regular_session(r[6])
        return dict(opening_minutes=opening,closing_minutes=closing,underlying_token=r[14],strike_price=float(r[15]),symbol=symbol,lot_size=int(lot),tick_size=tick,expiry_epoch=r[8],option_type=r[16],underlying_asset=r[13],exchange_code=r[10],segment_code=r[11])

def regular_session(value):
    bounds=str(value).split('|')[0].split('-')
    if len(bounds)!=2 or any(len(x)!=4 or not x.isdigit() for x in bounds):raise ValueError('Verified regular-session bounds unavailable')
    opening,closing=[int(x[:2])*60+int(x[2:]) for x in bounds]
    if not 0<=opening<closing<=1440:raise ValueError('Invalid regular-session bounds')
    return opening,closing

def session_bounds(symbol):
    if not symbol.startswith('MCX:'):return 555,930
    try:from .markets import FyersInstrumentMaster
    except ImportError:from markets import FyersInstrumentMaster
    meta=(Master(ROOT/'.private/nifty-ai-options/instrument-master')(symbol) if symbol.endswith(('CE','PE')) else FyersInstrumentMaster(ROOT/'.private/nifty-ai-options/instrument-master')(symbol))
    return meta['opening_minutes'],meta['closing_minutes']

def option_market_open(api,master,symbol):
    try:from .markets import fyers_market_open
    except ImportError:from markets import fyers_market_open
    return fyers_market_open(api,master(symbol))

try:from .sma_band import band_enabled,retain_broker_ohlc
except ImportError:from sma_band import band_enabled,retain_broker_ohlc

def history(api,symbol,frame,start,end,audit_dir=None,band=False):
    from sector_heatmap.fyers_history import history as fetch
    result=ok(fetch(api,dict(symbol=symbol,resolution=str(frame),date_format=1,range_from=start,range_to=end,cont_flag=0)))
    rows,audit=normalize_closes(result.get('candles',[]))
    if band:rows=retain_broker_ohlc(rows,result.get('candles',[]))
    if audit_dir is not None:
        key=hashlib.sha256(json.dumps([symbol,frame,start,end]).encode()).hexdigest()[:20]
        atomic(Path(audit_dir)/(key+'-raw.json'),result)
        atomic(Path(audit_dir)/(key+'-audit.json'),dict(audit,symbol=symbol,frame=frame,start=start,end=end))
    now=time.time();opening,closing=session_bounds(symbol)
    return [r for r in rows if r[0]+frame*60<=now and opening<=datetime.fromtimestamp(r[0],IST).hour*60+datetime.fromtimestamp(r[0],IST).minute<closing]

def validate_config(config,api):
    if not config.get('account'):raise ValueError('Explicit account required')
    if isinstance(config.get('lots'),bool) or not isinstance(config.get('lots'),int) or config['lots']<1:raise ValueError('Explicit lots required')
    if config.get('product') not in ('MARGIN','INTRADAY'):raise ValueError('Explicit MARGIN/INTRADAY product required')
    # The supplied reference is the NATIVE chart ATR brick setting, not synthetic-Renko OHLC ATR.
    if config.get('reference_symbol')!=config.get('underlying'):raise ValueError('Native reference belongs to another selected underlying')
    if config.get('reference_source') not in ('external_native_renko_6h_atr5','external_native_parent_atr5','verified_native_cache','manual_parent_override'):raise ValueError('Explicit native Renko 6h ATR5 reference source required')
    if not config.get('reference_evidence'):raise ValueError('Dated reference evidence description required')
    positive=config.get('reference_value')
    if not isinstance(positive,(float,int)) or isinstance(positive,bool) or not math.isfinite(positive) or positive<=0:raise ValueError('Supply verified reference_value; example 400 is not a measured baseline')
    Strategy(config)
    today=datetime.now(IST).date()
    prior=history(api,underlying(config),15,(today-timedelta(days=14)).isoformat(),(today-timedelta(days=1)).isoformat())
    sessions=sorted(set(datetime.fromtimestamp(r[0],IST).date().isoformat() for r in prior))
    if config.get('sizing_mode')!='MANUAL_PARENT' and (not sessions or config.get('reference_session')!=sessions[-1]):raise ValueError('Reference must be dated to actual previous available completed trading session: '+str(sessions[-1] if sessions else None))
    profile=ok(api.get_profile());identity=(profile.get('data') or {}).get('fy_id')
    if not identity:raise ValueError('Missing account identity')
    positions=ok(api.positions()).get('netPositions')
    orders=ok(api.orderbook()).get('orderBook')
    if not isinstance(positions,list) or not isinstance(orders,list):raise ValueError('Unrecognized broker reconciliation response')
    return dict(account_sha256=hashlib.sha256(str(identity).encode()).hexdigest(),reference_session=sessions[-1] if sessions else None,
                existing_nifty_positions=sum(int(p.get('netQty',0))!=0 for p in positions if str(p.get('symbol','')).startswith(exposure_prefix(config))),
                existing_nifty_pending_orders=sum(p.get('status') in (1,4,6) for p in orders if str(p.get('symbol','')).startswith(exposure_prefix(config))))

def listed_expiries(data,now=None):
    """Only provider-listed cutoffs still in the future; no invented weekly dates."""
    now=time.time() if now is None else now
    valid=set()
    for row in data.get('expiryData',[]):
        try:epoch=int(row['expiry'])
        except (KeyError,TypeError,ValueError):continue
        if epoch>now:valid.add(epoch)
    if not valid:raise ValueError('No unexpired FYERS expiry metadata available')
    return [str(epoch) for epoch in sorted(valid)]

def nearest_expiry(data,now=None):
    return listed_expiries(data,now)[0]

def selected_expiry(data,config,now=None):
    listed=listed_expiries(data,now)
    if config.get('expiry_policy','nearest_tradable')=='nearest_tradable':return listed[0]
    if config.get('expiry_policy')!='explicit_listed':raise ValueError('Unknown expiry policy')
    chosen=str(config.get('expiry',''))
    if chosen not in listed:raise ValueError('Selected expiry is expired or not listed for this underlying; choose a current broker expiry')
    return chosen

def choose(api,master,config,side,require_reference=True,exact_symbol=None):
    # Re-resolve on every new selection; a position retains its frozen contract.
    first=ok(api.optionchain(data=dict(symbol=underlying(config),strikecount=50,timestamp='',greeks='1')))
    expiry=selected_expiry(first.get('data') or {},config)
    reply=ok(api.optionchain(data=dict(symbol=underlying(config),strikecount=50,timestamp=expiry,greeks='1')))
    data=reply.get('data') or {}
    if expiry!=selected_expiry(data,config):raise ValueError('FYERS expiry metadata changed during selection')
    headers=[r for r in data.get('optionsChain',[]) if not r.get('option_type') and r.get('symbol')==underlying(config)]
    if len(headers)!=1:raise ValueError('Option chain does not identify the exact selected underlying')
    chain_asset=headers[0].get('ex_symbol');underlying_price=headers[0].get('ltp');moneyness=config.get('option_moneyness','OTM')
    parent=None
    if underlying(config).startswith('MCX:'):
        try:from .markets import FyersInstrumentMaster
        except ImportError:from markets import FyersInstrumentMaster
        parent=FyersInstrumentMaster(ROOT/'.private/nifty-ai-options/instrument-master')(underlying(config))
    rows=[]
    for row in data.get('optionsChain',[]):
        if row.get('option_type')!=side:continue
        meta=master(row.get('symbol'))
        if not str(row.get('symbol','')).startswith(underlying(config).split(':')[0]+':'):raise ValueError('Option exchange differs from selected underlying')
        if meta.get('strike_price') is not None and meta['strike_price']!=row.get('strike_price'):raise ValueError('Chain/master strike mismatch')
        if parent and str(meta.get('underlying_token'))!=str(parent.get('instrument_token')):raise ValueError('Option belongs to another MCX future delivery')
        if chain_asset and meta.get('underlying_asset')!=chain_asset:raise ValueError('Option chain/master underlying mismatch')
        if str(meta['expiry_epoch'])!=expiry or meta['option_type']!=side:raise ValueError('Chain/master expiry mismatch')
        rows.append(dict(row,expiry=expiry))
    if exact_symbol:
        exact=[r for r in rows if r.get('symbol')==exact_symbol]
        if len(exact)!=1:raise ValueError('Attached contract unavailable in the exact underlying/expiry chain')
        contract=exact[0]
        if moneyness=='ATM' and not config.get('_control_attachment'):
            atm=select_contract(rows,side,expiry,option_moneyness='ATM',underlying_price=underlying_price)
            if contract.get('strike_price')!=atm.get('strike_price'):raise ValueError('Attached holding is not the current ATM strike; choose its actual classification')
        elif not config.get('_control_attachment') and isinstance(underlying_price,(int,float)) and underlying_price>0:
            strike=contract.get('strike_price')
            if not isinstance(strike,(int,float)) or not (strike>underlying_price if side=='CE' else strike<underlying_price):raise ValueError('Attached holding is not OTM; choose its actual classification')
    else:contract=select_contract(rows,side,expiry,config.get('target_premium',40),option_moneyness=moneyness,underlying_price=underlying_price)
    meta=master(contract['symbol'])
    if float(meta['expiry_epoch'])<=time.time():raise ValueError('Selected contract has reached provider expiry cutoff')
    delta=(contract.get('greeks') or {}).get('delta')
    if not isinstance(delta,(int,float)) or isinstance(delta,bool):raise ValueError('No provider option delta')
    if (side=='CE' and delta<=0) or (side=='PE' and delta>=0):raise ValueError('Delta sign disagrees with option type')
    if not math.isfinite(delta) or not 0<abs(delta)<=1:raise ValueError('Invalid provider delta')
    if require_reference:sizes(config['reference_value'],delta,config.get('market','NSE'),config.get('asset'),config.get('option_moneyness','OTM'))
    return dict(symbol=contract['symbol'],option_type=side,expiry=expiry,selection_ltp=contract['ltp'],option_moneyness=moneyness,strike_price=contract.get('strike_price'),underlying_ltp=underlying_price,selected_at=time.time(),lot_size=meta['lot_size'],underlying=underlying(config),underlying_asset=meta.get('underlying_asset')),delta

def preflight(args):
    config=json.loads(Path(args.config).read_text());raw=client(config['account']);api=Reads(raw)
    try:
        summary=validate_config(config,api) if not config.get('_managed_resume') else dict(account_sha256=hashlib.sha256(str((ok(api.get_profile()).get('data') or {})['fy_id']).encode()).hexdigest())
        if config.get('_managed_resume') and summary['account_sha256']!=config.get('_resume_account_sha256'):raise ValueError('Resume account identity mismatch')
        if config.get('execution_mode')=='LIVE' and summary.get('existing_nifty_positions',0)>0 and not config.get('attach_position'):raise ValueError('Open broker position is not selected for attachment. Refresh open positions, select the holding, then Start.')
        summary['market_status']=ok(api.market_status())
        master=Master(Path(args.output)/'master')
        attached=None
        if config.get('attach_position'):
            try:from .attachment import verify_position
            except ImportError:from attachment import verify_position
            attached=verify_position(api,config,config['attach_position'],master)
            summary['attachment']=dict(attached,orders_submitted=0)
        chain_config=dict(config,expiry_policy='explicit_listed',expiry=attached['expiry']) if attached else config
        summary['contracts']={}
        for side in ('CE','PE'):
            contract,delta=choose(api,master,chain_config,side,exact_symbol=attached['symbol']) if attached and side==attached['side'] else choose(api,master,chain_config,side)
            spot,option=sizes(config['reference_value'],delta,config.get('market','NSE'),config.get('asset'),config.get('option_moneyness','OTM'))
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
    def __init__(self,frame,*,confirmed_closes=False,opening_minutes=555,closing_minutes=930):
        super().__init__(frame,opening_minutes=opening_minutes,closing_minutes=closing_minutes,confirmed_closes=confirmed_closes)

try:from .automatic_sizing import automatic_strategy,runtime_configuration
except ImportError:from automatic_sizing import automatic_strategy,runtime_configuration

try:
 from .position_control import entry_guard,EntryBlocked
except ImportError:
 from position_control import entry_guard,EntryBlocked
from contextlib import nullcontext

def stream(args):
    config=json.loads(Path(args.config).read_text())
    if config.get('_verification_only'):raise ValueError('Verification-only configuration cannot start a stream or submit orders')
    live=args.live
    if live and os.getenv('AI_RENKO_LIVE_ORDERS',os.getenv('NIFTY_AI_LIVE_ORDERS'))!='I_ACCEPT_REAL_ORDERS':raise ValueError('Live requires user-set NIFTY_AI_LIVE_ORDERS=I_ACCEPT_REAL_ORDERS')
    if not config.get('accept_close_source_renko_approximation',False):raise ValueError('Explicit close-source approximation acceptance required; TV parity not certified')
    config.setdefault('execution_mode','LIVE' if live else 'PAPER')
    if not config.get('_managed_resume'):config=runtime_configuration(config,Path(args.output))
    raw=client(config['account']);api=Reads(raw);out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    socket=None;executor=None
    try:
        summary=validate_config(config,api) if not config.get('_managed_resume') else dict(account_sha256=hashlib.sha256(str((ok(api.get_profile()).get('data') or {})['fy_id']).encode()).hexdigest())
        if config.get('_managed_resume') and summary['account_sha256']!=config.get('_resume_account_sha256'):raise ValueError('Resume account identity mismatch')
        if config.get('execution_mode')=='LIVE' and summary.get('existing_nifty_positions',0)>0 and not config.get('attach_position'):raise ValueError('Open broker position is not selected for attachment. Refresh open positions, select the holding, then Start.')
        master=Master(out/'master')
        executor=Execution(api,summary['account_sha256'],ROOT/'.private/nifty-ai-options/runtime',live=live,lots=config['lots'],product=config['product'],master=master,account_folder=ROOT/'.private/dashboard-login/accounts'/config['account'],attachment_config=config if config.get('attach_position') else None,management_only=config.get('_managed_resume',False))
        try:from .confirmed_close import ConfirmedClose,fyers_reader
        except ImportError:from confirmed_close import ConfirmedClose,fyers_reader
        confirmed=ConfirmedClose(fyers_reader(api),out/'confirmed-source')
        try:from .chart_source import ChartSource
        except ImportError:from chart_source import ChartSource
        chart_source=ChartSource(out/'chart-source',calculation_mode=config.get('calculation_mode','RENKO'))
        signal_symbol=underlying(config)
        opening,closing=session_bounds(signal_symbol)
        engine=automatic_strategy(Strategy(config),config,exposure=lambda:bool(executor.state['position'] or executor.state['pending'] or executor.state.get('positions') or executor.state.get('detached_position')),chart_source=chart_source,config_path=out/'config.json');today=datetime.now(IST).date()
        start=(today-timedelta(days=14)).isoformat();end=today.isoformat()
        under=history(api,underlying(config),config['timeframe'],start,end,out/'source-history',(band_enabled(config) or config.get('calculation_mode') in ('CANDLES','HYBRID')))
        if not under:raise ValueError('No underlying warm-up history')
        chart_source.seed(signal_symbol,config['timeframe'],under,engine.spot_size)
        for r in under:
            engine.update(dict(kind='underlying',timestamp=r[0],open=r[1],high=r[2],low=r[3],close=r[4]))
            engine.position=None
        chart_source.seed_bands(engine)
        def select(preferred_side=None,attached=None):
            side=preferred_side or (engine.signal_side() or 'PE')
            selected_config=dict(config,expiry_policy='explicit_listed',expiry=attached['expiry'],_control_attachment=True) if attached else config
            contract,delta=choose(api,master,selected_config,side,exact_symbol=attached['symbol']) if attached else choose(api,master,config,side)
            engine.reset_contract(contract,delta);engine.last_time.pop('premium',None)
            if config.get('signal_source')=='UNDERLYING':return contract['symbol']
            rows=history(api,contract['symbol'],config['timeframe'],start,end,out/'source-history',True) if (config.get('band_price_basis')=='premium' and band_enabled(config)) or config.get('calculation_mode') in ('CANDLES','HYBRID') else history(api,contract['symbol'],config['timeframe'],start,end,out/'source-history')
            if not rows:raise ValueError('No selected option warm-up history')
            chart_source.seed(contract['symbol'],config['timeframe'],rows,engine.contract['option_brick'])
            for r in rows:
                engine.update(dict(kind='premium',timestamp=r[0],open=r[1],high=r[2],low=r[3],close=r[4],symbol=contract['symbol']))
                engine.position=None
            if config.get('supertrend_enabled',True) and (engine.premium_result is None or engine.premium_result['host_atr'] is None):raise ValueError('Insufficient selected-option Renko indicator warm-up')
            if config.get('band_price_basis')=='premium':chart_source.seed_bands(engine)
            return contract['symbol']
        attachment=None
        if config.get('attach_position'):
            try:from .attachment import verify_position
            except ImportError:from attachment import verify_position
            attachment=verify_position(api,config,config['attach_position'],master)
        symbol=select(attachment['side'],attachment) if attachment else select()
        engine.pending_underlying_flip=None;engine.entry_reset_at=time.time()
        if attachment:
            # Warm the exact held premium before taking ownership. No new BUY.
            attachment=verify_position(api,config,config['attach_position'],master)
            owned=dict(engine.contract,side=attachment['side'],quantity=attachment['quantity'],fill_price=attachment['average_price'],
                       entry_timestamp=time.time(),attached_existing=True,attachment_verified_at=attachment['verified_at'])
            executor.adopt_existing(owned,config)
            engine.position=dict(owned)
            atomic(out/'attachment.json',dict(phase='ATTACHED',position=owned,orders_submitted=0,checked_at=time.time()))

        if config.get('sma_exit_enabled',False):
            for r in history(api,underlying(config),1,start,end,out/'source-history'):
                engine.update(dict(kind='sma',timestamp=r[0],close=r[4]))
        import certifi
        from fyers_apiv3.FyersWebsocket import data_ws
        os.environ.setdefault('SSL_CERT_FILE',certifi.where())
        q=queue.Queue(maxsize=20000);quotes={};bars={signal_symbol:Bars(config['timeframe'],confirmed_closes=True,opening_minutes=opening,closing_minutes=closing),symbol:Bars(config['timeframe'],confirmed_closes=True,opening_minutes=opening,closing_minutes=closing)};sma=Bars(1,confirmed_closes=True,opening_minutes=opening,closing_minutes=closing)
        try:from .manual_entry import LatestQuote,ManualDispatcher,ManualNotReady,automatic_actions,confirm_entry_fill,restore_unsubmitted,confirmed_flat_entry
        except ImportError:from manual_entry import LatestQuote,ManualDispatcher,ManualNotReady,automatic_actions,confirm_entry_fill,restore_unsubmitted,confirmed_flat_entry
        quote_cache={signal_symbol:LatestQuote(signal_symbol),symbol:LatestQuote(symbol)}
        def message(data):
            if isinstance(data,dict) and data.get('symbol') in quote_cache:quote_cache[data['symbol']].accept(data)
            try:q.put_nowait(('tick',data))
            except queue.Full:
                # Single fail-closed marker; no dropped ticks followed by trading.
                stopped.set()
        stopped=threading.Event()
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
        account_folder=ROOT/'.private/dashboard-login/accounts'/config['account']
        saved_session=SavedAccountSession(raw,[account_folder/'credentials.json',account_folder/'home/.fyers/token.json'],load=lambda:client(config['account']),verify=verify_saved_session,apply=apply_saved_session)
        def current_market_open():
            saved_session.refresh()
            return option_market_open(api,master,symbol)
        def current_bounds():
            nonlocal opening,closing
            opening,closing=session_bounds(signal_symbol)
            return dict(opening_minutes=opening,closing_minutes=closing)
        session=SessionWait(current_market_open,opening,closing,clock=lambda:time.time(),bounds=current_bounds)
        source_unavailable=threading.Event();source_unavailable.set();source_failed=threading.Event()
        def failure(*unused):
            if reopen.restarting:return
            source_unavailable.set();source_failed.set()
        def connected():
            socket.subscribe(symbols=list(quote_cache),data_type='SymbolUpdate');source_unavailable.clear();source_failed.clear()
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
        try:from .option_legs import OptionLegBook,entry_valid,retain_pending_actions
        except ImportError:from option_legs import OptionLegBook,entry_valid,retain_pending_actions
        executor=OptionLegBook(executor,out,config,quote=lambda name:quote_cache[name].get(),ready=lambda:not stopped.is_set() and not source_unavailable.is_set() and current_market_open(),clock=lambda:time.time())
        def unsubscribe_unused(name):
            if not executor.has_symbol(name):socket.unsubscribe(symbols=[name],data_type='SymbolUpdate')
        def discard_unused_quote(name):
            if not executor.has_symbol(name):quote_cache.pop(name,None)
        marker_events=[]
        def record_fill(action,result):
            confirm_entry_fill(engine,executor,action)
            if (out/'markers.json').exists():marker_events[:]=json.loads((out/'markers.json').read_text())
            marker_events.append(dict(timestamp=action['timestamp'],source_timestamp=action['timestamp'],confirmed_at=time.time(),symbol=action['position']['symbol'],action=action['action'],price=result.get('fill_price',result.get('simulated_fill')),mode='LIVE' if live else 'PAPER',order_id=result.get('order_id'),confirmed=True))
            atomic(out/'markers.json',marker_events[-1000:])
        journal=(out/'events.jsonl').open('a',buffering=1)
        last_tick=time.monotonic();observation_sequence=0
        def submit(action):
            if action['action']=='BUY':executor.remember_entry(action)
            if action['action']=='SELL' and action.get('reason')!='USER_STOP_SQUARE_OFF':
                engine.quote_exit_pending=None
                return executor.request_exit(action)
            if stopped.is_set():raise ValueError('Source unavailable before order')
            if source_unavailable.is_set() or not current_market_open():
                restore_unsubmitted(engine,executor,action);session.poll(force=True);heartbeat()
                return dict(deferred=True,reason='WAITING_FOR_SOURCE' if source_unavailable.is_set() else 'WAITING_FOR_MARKET')
            try:
                if action['action']=='BUY':
                    for required in (signal_symbol,symbol):quote_cache[required].get()
                executable_quote=quote_cache[action['position']['symbol']].get()
            except ManualNotReady:
                restore_unsubmitted(engine,executor,action)
                if action['action']=='SELL':engine.quote_exit_pending=dict(action)
                return dict(deferred=True,reason='WAITING_FOR_FRESH_QUOTE')
            if stopped.is_set() or source_unavailable.is_set():
                restore_unsubmitted(engine,executor,action)
                return dict(deferred=True,reason='WAITING_FOR_SOURCE')
            try:
                with entry_guard(out,executor) if action['action']=='BUY' else nullcontext():
                    result=executor.submit(action,executable_quote)
            except EntryBlocked:
                restore_unsubmitted(engine,executor,action)
                return dict(deferred=True,reason='WAITING_FOR_POSITION_CONTROL')
            if result.get('deferred'):
                restore_unsubmitted(engine,executor,action)
                journal.write(json.dumps(dict(action=action,result=result,recorded_at=time.time()))+'\n');return result
            record_fill(action,result)
            if action['action']=='SELL':
                engine.quote_exit_pending=None
            journal.write(json.dumps(dict(action=action,result=result))+'\n')
            return result
        def submit_manual(action):return submit(action)
        def manual_prepare(direction):
            nonlocal symbol
            old=symbol;symbol=select(direction)
            if old!=symbol:
                unsubscribe_unused(old)
                bars.pop(old,None);discard_unused_quote(old)
            bars[symbol]=Bars(config['timeframe'],confirmed_closes=True,opening_minutes=opening,closing_minutes=closing)
            quote_cache[symbol]=LatestQuote(symbol)
            socket.subscribe(symbols=[symbol],data_type='SymbolUpdate')
        def manual_quote_ready():
            if stopped.is_set() or source_unavailable.is_set() or not current_market_open():raise ValueError('Market or source unavailable before manual entry')
            quote_cache[signal_symbol].get()
            return quote_cache[symbol].get()['timestamp']
        manual=ManualDispatcher(config,out,'LIVE' if live else 'PAPER',engine,executor,prepare=manual_prepare,quote_ready=manual_quote_ready,submit=submit_manual)
        try:from .runtime_control import RuntimeControl
        except ImportError:from runtime_control import RuntimeControl
        def change_timeframe(frame):
            chart_source.roll_timeframe(list(bars),config['timeframe'],frame)
            for key in list(bars):bars[key]=Bars(frame,confirmed_closes=True,opening_minutes=opening,closing_minutes=closing)
            engine.config['timeframe']=frame
            for key in ('underlying','premium','hybrid_candle_underlying','hybrid_candle_premium'):engine.last_time.pop(key,None)
            manual.inbox.expected['timeframe']=frame
        try:
            from .position_control import PositionManager
            from .position_brokers import FyersPositions
        except ImportError:
            from position_control import PositionManager
            from position_brokers import FyersPositions
        position_view=FyersPositions(api,config,master,summary['account_sha256'])
        def attach_holding(request):
            nonlocal symbol
            row=position_view.selected(request)
            captured=executor.state.get('detached_position') or executor.state.get('position')
            old=symbol;engine.position=None;symbol=select(row['side'],row)
            if old!=symbol:
                unsubscribe_unused(old);bars.pop(old,None);discard_unused_quote(old)
            bars[symbol]=Bars(config['timeframe'],confirmed_closes=True,opening_minutes=opening,closing_minutes=closing)
            quote_cache[symbol]=LatestQuote(symbol);socket.subscribe(symbols=[symbol],data_type='SymbolUpdate')
            owned=dict(engine.contract,side=row['side'],quantity=row['quantity'],product=row['product'],fill_price=row['average_price'],entry_timestamp=time.time(),attached_existing=True)
            if captured and captured['symbol']==symbol:
                for key in ('spot_brick','option_brick','selection_delta','option_multiplier'):
                    if key in captured:owned[key]=captured[key]
            return owned
        def verify_control(owned,**kw):
            if live:return position_view.verify(owned,**kw)
            return dict(flat=executor.state.get('position') is None if kw.get('flat') is True else False)
        manager=PositionManager(config,out,engine,executor,verify=verify_control,attach=attach_holding,submit=submit,manual=manual)
        control=RuntimeControl(config,out,apply=change_timeframe,apply_mode=lambda mode:engine.config.update(display_mode=mode,exit_confirmation_mode='RENKO_BRICKS_ONLY' if mode=='RENKO' else 'HYBRID_COMPLETED_UNITS'))
        recovery_pending=True
        last_heartbeat=0
        def heartbeat():
            nonlocal last_heartbeat
            now=time.monotonic()
            if now-last_heartbeat<1:return
            last_heartbeat=now
            atomic(out/'heartbeat.json',dict(at=datetime.now(IST).isoformat(),mode='LIVE' if live else 'PAPER',symbol=symbol,selected_contract=engine.contract,calculation_mode=config.get('calculation_mode','RENKO'),exit_waiting_for_quote=bool(getattr(engine,'quote_exit_pending',None)),native_sizing=getattr(engine,'native_sizing_status',None),moving_bands=engine.band.snapshot(engine.config),position_control=manager.status(),manual_entry_capable=session.ready and not source_unavailable.is_set() and not manager.entry_blocked,source_state='WAITING_FOR_SOURCE' if source_unavailable.is_set() else 'READY',reconfigure_capable=True,timeframe=config['timeframe'],runtime_session=config.get('runtime_session'),position=executor.state['position'],pending=executor.state['pending'],**session.snapshot()))
        while not stopped.is_set():
            was_pending=bool(executor.state.get('pending'));executor.poll()
            if was_pending and not executor.state.get('pending'):engine.position=__import__('copy').deepcopy(executor.state.get('position'))
            for cached_symbol in list(quote_cache):
                if cached_symbol not in (signal_symbol,symbol) and not executor.has_symbol(cached_symbol):
                    unsubscribe_unused(cached_symbol);discard_unused_quote(cached_symbol)
            if manager.poll(busy=bool(manual.pending)):return
            session.poll(force=source_failed.is_set())
            reopen.observe(session.ready)
            if source_failed.is_set() and session.ready:
                stopped.set();break
            if not session.ready:recovery_pending=True
            if session.changed:
                last_tick=time.monotonic()
                bars={key:Bars(config['timeframe'],confirmed_closes=True,opening_minutes=opening,closing_minutes=closing) for key in bars}
                sma=Bars(1,confirmed_closes=True,opening_minutes=opening,closing_minutes=closing)
                engine.pending_underlying_flip=None
                from strategies.nifty_ai_options.manual_entry import clear_entry_signal
                clear_entry_signal(engine)
            heartbeat()
            try:_,tick=q.get(timeout=1)
            except queue.Empty:
                if not manager.entry_blocked:manual.poll()
                if not manager.entry_blocked:control.poll(busy=bool(manual.pending or executor.state['pending']),position=bool(executor.state['position']))
                engine.entry_paused=control.entry_blocked or manager.entry_blocked
                if session.ready and time.monotonic()-last_tick>30:raise ValueError('Stream heartbeat stalled; halted without order mutation')
                continue
            if not session.ready:
                session.poll()
                reopen.observe(session.ready)
                if not session.ready:continue
                last_tick=time.monotonic()
            if source_unavailable.is_set():continue
            if not isinstance(tick,dict) or tick.get('symbol') not in bars:continue
            at=tick.get('exch_feed_time') or tick.get('last_traded_time');price=tick.get('ltp')
            if not isinstance(at,(int,float)) or not isinstance(price,(int,float)):continue
            if at>1e12:at/=1000
            if not math.isfinite(price) or price<=0 or not math.isfinite(at):raise ValueError('Invalid provider tick; halted')
            # An order fill may block this consumer while fresh ticks queue.
            # Discard aged observations; never trade them or reset the freshness
            # watchdog. The following fresh queued tick retains the same engine.
            if not 0<=time.time()-at<=5:continue
            local=datetime.fromtimestamp(at,IST)
            if not opening<=local.hour*60+local.minute<closing:continue
            if recovery_pending:
                bars={key:Bars(config['timeframe'],confirmed_closes=True,opening_minutes=opening,closing_minutes=closing) for key in bars}
                sma=Bars(1,confirmed_closes=True,opening_minutes=opening,closing_minutes=closing)
                recovered=reconcile_bodies(engine,confirmed,[('underlying',signal_symbol)]+([] if config.get('signal_source')=='UNDERLYING' else [('premium',symbol)]),config['timeframe'],at,opening,sma_enabled=config.get('sma_exit_enabled',False))
                journal.write(json.dumps(dict(session_recovery=recovered,orders_submitted=0,renko_state_retained=True))+'\n')
                recovery_pending=False
            last_tick=time.monotonic();sym=tick['symbol'];quotes[sym]=dict(timestamp=at,ltp=price)
            if manager.blocked:continue
            if sym==symbol and getattr(engine,'session_sma_exit_pending',False) and engine.position:
                action=engine.exit(time.time(),'OPTIONAL_UNDERLYING_1M_SMA30')[0]
                result=submit(action)
                if not result.get('deferred'):engine.session_sma_exit_pending=False
            if sym==symbol and getattr(engine,'quote_exit_pending',None) and engine.position:
                pending_exit=engine.quote_exit_pending
                result=submit(pending_exit)
                if not result.get('deferred'):engine.position=None
            if not manager.entry_blocked:manual.poll()
            if not manager.entry_blocked:control.poll(busy=bool(manual.pending or executor.state['pending']),position=bool(executor.state['position']))
            engine.entry_paused=control.entry_blocked or manager.entry_blocked
            engine.entry_quotes_ready=True
            try:
                for required in (signal_symbol,symbol):quote_cache[required].get()
            except ManualNotReady:engine.entry_quotes_ready=False
            if sym not in bars:continue
            observation_sequence+=1
            live_event=dict(kind='price',series='underlying' if sym==signal_symbol else 'premium',timestamp=at,available_at=time.time(),close=price,symbol=sym,source_basis='BROKER_LIVE_PRICE',sequence=observation_sequence)
            if live_event['series']=='underlying' or config.get('signal_source')!='UNDERLYING':chart_source.append_observation(live_event,config['timeframe'])
            journal.write(json.dumps(dict(event=live_event))+'\n')
            for action in automatic_actions(engine,executor,manual,retain_pending_actions(engine,executor,chart_source.decide(engine,live_event))):
                if action['action']=='SELECT':continue
                submit(action)
            if manual.pending is None and engine.position is None and engine.signal_side():
                side=engine.signal_side()
                if engine.contract['option_type']!=side:
                    old=symbol;symbol=select()
                    unsubscribe_unused(old)
                    bars.pop(old,None);discard_unused_quote(old)
                    bars[symbol]=Bars(config['timeframe'],confirmed_closes=True,opening_minutes=opening,closing_minutes=closing);quote_cache[symbol]=LatestQuote(symbol)
                    socket.subscribe(symbols=[symbol],data_type='SymbolUpdate')
            if sym not in bars:continue
            events=[]
            # A newly selected contract may complete the underlying-flip gate once its fresh quote arrives.
            if manual.pending is None and sym==symbol and signal_symbol in quotes and 0<=time.time()-quotes[signal_symbol]['timestamp']<=5:
                selected_entry=confirmed_flat_entry(engine,executor)
                if selected_entry:
                    print(json.dumps(submit(selected_entry)),flush=True)
            if sym!=signal_symbol and config.get('signal_source')=='UNDERLYING':heartbeat();continue
            if sym==signal_symbol and config.get('sma_exit_enabled',False):
                row=sma.update(at,price)
                if row and row[0]>engine.last_time.get('sma',0):events.append(dict(kind='sma',timestamp=row[0],close=row[1]))
            row=bars[sym].update(at,price)
            kind='underlying' if sym==signal_symbol else 'premium'
            if row and row[0]>engine.last_time.get(kind,0):events.append(dict(kind=kind,timestamp=row[0],close=row[1],symbol=sym))
            for event in events:
                event=confirmed.confirm(event,event.get('symbol') or signal_symbol,1 if event['kind']=='sma' else config['timeframe'],previous=engine.last_time.get(event['kind']),continuous=False,opening_minutes=opening)
                if not session.poll(force=True):break
                if event['kind']!='sma':chart_source.append(event,config['timeframe'])
                journal.write(json.dumps(dict(event=event))+'\n')
                exited=False
                actions=retain_pending_actions(engine,executor,chart_source.decide(engine,event))
                chart_source.append_bands(engine,event)
                for action in automatic_actions(engine,executor,manual,actions):
                    if action['action']=='SELECT':continue
                    result=submit(action)
                    if action['action']=='SELL':exited=True
                    print(json.dumps(result),flush=True)
                if manual.pending is None and engine.position is None and engine.signal_side():
                    side=engine.signal_side()
                    if exited or engine.contract['option_type']!=side:
                        old=symbol
                        if exited and config.get('signal_source')!='UNDERLYING':engine.pending_underlying_flip=None
                        symbol=select()
                        unsubscribe_unused(old)
                        bars.pop(old,None);bars[symbol]=Bars(config['timeframe'],confirmed_closes=True,opening_minutes=opening,closing_minutes=closing)
                        discard_unused_quote(old);quote_cache[symbol]=LatestQuote(symbol)
                        socket.subscribe(symbols=[symbol],data_type='SymbolUpdate')
            executor.dispatch_entries(submit,lambda action:entry_valid(engine,action))
            executor.poll()
            heartbeat()
        raise ValueError('Stream disconnected/overflow; halted; existing broker exposure preserved')
    finally:
        if locals().get('journal'):journal.close()
        if getattr(locals().get('engine'),'close_native_sizing',None):engine.close_native_sizing()
        if socket:
            try:socket.close_connection()
            except Exception:pass
        if executor:
            try:
                atomic(out/'heartbeat.json',dict(at=datetime.now(IST).isoformat(),mode='LIVE' if live else 'PAPER',symbol=config['underlying'],selected_contract=getattr(locals().get('engine'),'contract',None),position=executor.state['position'],pending=executor.state['pending'],terminal=True))
            finally:executor.close()
        raw._sector_pulse_ipv4_session.close()
