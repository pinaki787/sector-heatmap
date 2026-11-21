"""Selected Delta instrument runtime. Paper default; explicit Live opt-in only."""
import json,math,os,queue,time
from pathlib import Path
from datetime import datetime
try:
    from .run import atomic,normalize_closes,IST,ROOT
    from .delta_adapter import bound_delta,select_option
    from .delta_execution import DeltaExecution
    from .core import Strategy,sizes
    from .direct import DirectStrategy
    from .markets import SourceBars
except ImportError:
    from run import atomic,normalize_closes,IST,ROOT
    from delta_adapter import bound_delta,select_option
    from delta_execution import DeltaExecution
    from core import Strategy,sizes
    from direct import DirectStrategy
    from markets import SourceBars
FRAMES={1:'1m',5:'5m',30:'30m'}

def history(delta,symbol,frame,out):
    import hashlib
    seconds=frame*60;now=delta.clock();begin=int(now-14*86400)//seconds*seconds;rows=[];page=0
    scope=hashlib.sha256((symbol+'|'+str(frame)).encode()).hexdigest()[:16]
    while begin<now:
        finish=min(int(now),begin+seconds*499)
        reply=delta._get('/v2/history/candles',dict(symbol=symbol,resolution=FRAMES[frame],start=begin,end=finish));raw=reply.get('result')
        if not isinstance(raw,list):raise ValueError('Delta completed history unavailable')
        atomic(Path(out)/(scope+'-'+str(page)+'-raw.json'),reply)
        rows.extend([[r['time'],r.get('open'),r.get('high'),r.get('low'),r.get('close'),r.get('volume')] for r in raw]);page+=1;begin=finish
    normalized,audit=normalize_closes(rows);atomic(Path(out)/(scope+'-audit.json'),dict(audit,symbol=symbol,frame=frame))
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
    return dict(read_only=True,orders_submitted=0,underlying=config['underlying'],instrument=meta,spot_brick=engine.spot_size,execution_route=config['execution_route'],stream_started=False)

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
                c,d=select_option(delta,config['underlying'],side,config.get('target_premium',40));base,brick=sizes(config['reference_value'],d,'CRYPTO',config.get('asset'))
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

def stream(args):
    config=json.loads(Path(args.config).read_text());live=args.live
    if config.get('_verification_only'):raise ValueError('Verification-only configuration cannot start a stream or orders')
    if live and os.getenv('AI_RENKO_LIVE_ORDERS',os.getenv('NIFTY_AI_LIVE_ORDERS'))!='I_ACCEPT_REAL_ORDERS':raise ValueError('Explicit Live environment opt-in required')
    if not config.get('accept_close_source_renko_approximation'):raise ValueError('Review the confirmed-close Renko basis before Start')
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    delta=bound_delta(config['account'],ROOT/'.private/nifty-ai-options/native-delta'/config['account']/('LIVE' if live else 'PAPER'))
    broker=executor=engine=None;symbol=None
    try:
        summary=inspect(config,delta);atomic(out/'preflight.json',summary)
        executor=DeltaExecution(delta,config['account'],ROOT/'.private/nifty-ai-options/runtime',live=live,contracts=config['lots'])
        try:from .confirmed_close import ConfirmedClose,delta_reader
        except ImportError:from confirmed_close import ConfirmedClose,delta_reader
        confirmed=ConfirmedClose(delta_reader(delta),out/'confirmed-source')
        try:from .chart_source import ChartSource
        except ImportError:from chart_source import ChartSource
        chart_source=ChartSource(out/'chart-source')
        q=queue.Queue(maxsize=20000);overflow=False
        def on_tick(tick):
            nonlocal overflow
            try:q.put_nowait(tick)
            except queue.Full:overflow=True
        broker=SourceBroker(delta,out,on_tick)
        direct=config['execution_route']=='DIRECT';underlying=config['underlying']
        engine=DirectStrategy(config) if direct else Strategy(config)
        rows=history(delta,underlying,config['timeframe'],out/'source-history')
        if not rows:raise ValueError('No selected-underlying completed warm-up closes')
        chart_source.seed(underlying,config['timeframe'],rows,engine.spot_size)
        for r in rows:engine.update(dict(kind='underlying',timestamp=r[0],close=r[4]));engine.position=None
        def select():
            if direct:
                meta=dict(summary['instrument'],underlying=underlying,execution_route='DIRECT');engine.reset_contract(meta);return underlying
            side='CE' if engine.under_result and engine.under_result['direction']<0 else 'PE'
            contract,d=select_option(delta,underlying,side,config.get('target_premium',40));engine.reset_contract(contract,d);engine.last_time.pop('premium',None)
            broker.subscribe(contract['symbol'],config['timeframe']*60)
            rows=history(delta,contract['symbol'],config['timeframe'],out/'source-history')
            if not rows:raise ValueError('No selected-premium completed warm-up closes')
            chart_source.seed(contract['symbol'],config['timeframe'],rows,engine.contract['option_brick'])
            for r in rows:engine.update(dict(kind='premium',timestamp=r[0],close=r[4],symbol=contract['symbol']));engine.position=None
            if engine.premium_result is None or engine.premium_result['host_atr'] is None:raise ValueError('Selected premium lacks sufficient indicator warm-up')
            return contract['symbol']
        symbol=select()
        if live:live_readiness(delta,[symbol])
        if direct:engine.pending_direction=None
        else:engine.pending_underlying_flip=None
        if config.get('sma_exit_enabled'):
            for r in history(delta,underlying,1,out/'source-history'):engine.update(dict(kind='sma',timestamp=r[0],close=r[4]))
            broker.subscribe(underlying,60)
        broker.subscribe(underlying,config['timeframe']*60);broker.subscribe(symbol,config['timeframe']*60)
        bars={underlying:SourceBars(config['timeframe'],continuous=True,confirmed_closes=True)}
        if symbol!=underlying:bars[symbol]=SourceBars(config['timeframe'],continuous=True,confirmed_closes=True)
        sma=SourceBars(1,continuous=True,confirmed_closes=True);markers=[];last_tick=time.monotonic();last_write=0;generation=None
        broker.start()
        with (out/'events.jsonl').open('a',buffering=1) as journal:
            def submit(action):
                quote=dict(broker.quote(action['position']['symbol']),symbol=action['position']['symbol'])
                result=executor.submit(action,quote);journal.write(json.dumps(dict(action=action,result=result))+'\n')
                markers.append(dict(timestamp=action['timestamp'],source_timestamp=action['timestamp'],confirmed_at=time.time(),symbol=action['position']['symbol'],action=action['action'],mode='LIVE' if live else 'PAPER',confirmed=True,price=result.get('fill_price',result.get('simulated_fill')),order_id=result.get('order_id')))
                atomic(out/'markers.json',markers[-1000:]);print(json.dumps(result),flush=True)
            while not overflow:
                status=broker.stream_status()
                if generation is not None and (not status['connected'] or status['generation']!=generation):raise ValueError('Public stream disconnected/reconnected; halt for history reconciliation')
                try:tick=q.get(timeout=1)
                except queue.Empty:
                    if time.monotonic()-last_tick>30:raise ValueError('Delta source heartbeat stalled; exposure preserved')
                    continue
                if tick.get('symbol') not in bars:continue
                stamp,price=tick.get('exch_feed_time'),tick.get('ltp')
                if not isinstance(stamp,(int,float)) or not isinstance(price,(int,float)) or not math.isfinite(price) or price<=0 or not 0<=delta.clock()-stamp<=15:raise ValueError('Stale/invalid Delta source tick')
                current_status=broker.stream_status()
                if not current_status['connected']:raise ValueError('Public stream unavailable before processing tick')
                if generation is None:generation=current_status['generation']
                last_tick=time.monotonic();sym=tick['symbol']
                if sym==symbol and executor.state['position'] is None:
                    broker.tick(underlying)
                    action=engine.selected_gate_entry()
                    if action:submit(action)
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
                    for action in engine.update(event):
                        if action['action']=='SELECT':continue
                        submit(action);exited=action['action']=='SELL' or action['action'].startswith('CLOSE_')
                    if not direct and engine.position is None and engine.under_result:
                        side='CE' if engine.under_result['direction']<0 else 'PE'
                        if exited or engine.contract['option_type']!=side:
                            old=symbol
                            if exited:engine.pending_underlying_flip=None
                            symbol=select()
                            if old!=symbol:broker.unsubscribe(old)
                            bars.pop(old,None);bars[symbol]=SourceBars(config['timeframe'],continuous=True,confirmed_closes=True)
                if time.monotonic()-last_write>=1:
                    atomic(out/'heartbeat.json',dict(at=datetime.now(IST).isoformat(),mode='LIVE' if live else 'PAPER',symbol=symbol,selected_contract=engine.contract,position=executor.state['position'],pending=executor.state['pending']))
                    last_write=time.monotonic()
            raise ValueError('Delta source queue overflow; halted')
    finally:
        if executor:
            atomic(out/'heartbeat.json',dict(at=datetime.now(IST).isoformat(),mode='LIVE' if live else 'PAPER',symbol=symbol,selected_contract=getattr(engine,'contract',None),position=executor.state['position'],pending=executor.state['pending']))
            executor.close()
        if broker:broker.stop()
        delta.requester.close()
