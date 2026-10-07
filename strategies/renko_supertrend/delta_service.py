"""Delta Renko HTTP component: shared chart math, isolated execution ownership."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import hashlib
import json
from pathlib import Path
import threading
import time
from urllib.parse import parse_qs, urlparse

from .delta_broker import Broker
from .delta_runner import DeltaRunner, DeltaAdoptedRunner
from .adoption import Manager
from .runner import analysis, provisional
from .signals import settings
from strategies.ema_crossover.runner import TIMEFRAMES

PREFIX='/api/renko-delta/'


class Service:
    def __init__(self, delta, root, instance_key='default', instrument=None):
        self.delta=delta; self.root=Path(root); self.wake=threading.Event()
        self.context={}; self.lock=threading.RLock();self.instrument=instrument;self.instance_key=instance_key
        state_root=self.root/'.private' if instance_key=='default' else self.root/'.private'/'renko-delta-instances'/instance_key
        def factory(): return Broker(delta,self.root/'.private'/'renko-delta-history',on_tick=lambda raw:self.wake.set())
        self.broker=factory(); self.chart_broker=factory()
        self.runner=DeltaRunner(self.broker,state_root/'renko-delta-state.json')
        def account(): return self.broker.execution.authenticate()
        def owners():
            symbols=set()
            for state in (self.runner.state,delta.runner):
                if (state.get('config') or {}).get('mode')!='LIVE': continue
                for pos in (state.get('position'),(state.get('pending') or {}).get('position')):
                    if pos and pos.get('symbol'): symbols.add(pos['symbol'])
            if delta.live.get('runner_position'): symbols.add(delta.live['runner_position']['symbol'])
            # All external active broker orders, including native protective
            # orders, block adoption/duplicate entries until resolved.
            for row in self.broker.orders():
                if row['status'] not in (1,2,5,7): symbols.add(row['symbol'])
            return symbols
        self.external_owners=lambda:set()
        local_owners=owners
        self.owners=lambda:local_owners()|set(self.external_owners())
        self.adoptions=Manager(state_root/'renko-delta-adoptions',factory,factory(),account,self.owners,runner_type=DeltaAdoptedRunner)
        self.adoptions.guard(self.runner)

    def chart_config(self, query):
        raw={k:query[k][0] for k in settings({}) if k in query}
        for key,default in [('use_adx','false'),('retest_enabled','false'),('retest_engulfing','true'),('retest_harami','true'),('retest_star','true')]: raw[key]=(query.get(key) or [default])[0]=='true'
        carry=(query.get('carry_policy') or ['CONTINUOUS'])[0]
        if carry not in ('CONTINUOUS','DAILY_SQUARE_OFF'):raise ValueError('Unknown crypto carry policy.')
        deadline=(query.get('session_deadline') or [''])[0] if carry == 'DAILY_SQUARE_OFF' else None
        import re
        if carry == 'DAILY_SQUARE_OFF' and (not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',deadline or '') or deadline=='00:00'): raise ValueError('Choose an explicit Delta daily square-off time.')
        config=dict(settings(raw),underlying=(query.get('symbol') or [''])[0],timeframe=(query.get('timeframe') or ['5 minutes'])[0],session_deadline=deadline,carry_policy=carry,broker='DELTA_INDIA')
        if self.instrument and config['underlying']!=self.instrument:raise ValueError('Select this instance instrument or create another instance.')
        self.chart_broker.session_policy(config)
        return config

    def chart(self, query):
        config=self.chart_config(query); now=time.time(); tz=ZoneInfo('Asia/Kolkata')
        today=datetime.fromtimestamp(now,tz).date(); preset=(query.get('history_preset') or ['45'])[0]
        if preset=='custom':
            first=datetime.fromisoformat(query['history_from'][0]).date(); last=datetime.fromisoformat(query['history_to'][0]).date()
        else:
            if preset not in ('7','45','90'): raise ValueError('Unsupported history range.')
            last=today; first=today-timedelta(days=int(preset)-1)
        if first>last or last>today or (last-first).days>90: raise ValueError('History must span at most 91 past calendar days.')
        begin=datetime.combine(first-timedelta(days=7),datetime.min.time(),tz).timestamp()
        end=datetime.combine(last+timedelta(days=1),datetime.min.time(),tz).timestamp()
        config.update(self.chart_broker.session_policy(config))
        candles=self.chart_broker.candles(dict(config,history_start=begin))
        candles=[c for c in candles if begin<=c['timestamp']<end]
        tick=self.chart_broker.host_tick_size(config['underlying']); result=analysis(candles,config,tick,retain=None)
        display_start=datetime.combine(first,datetime.min.time(),tz).timestamp()
        rows=[r for r in result['rows'] if r['timestamp']>=display_start]
        forming=[c for c in candles if c.get('is_forming')]
        revision=hashlib.sha256(json.dumps([config,rows],sort_keys=True).encode()).hexdigest()
        with self.lock: self.context[json.dumps(self.chart_config(query),sort_keys=True)]=(result,config,tick)
        self.chart_broker.start()
        history=dict(requested_from=first.isoformat(),requested_to=last.isoformat(),display_oldest=rows[0]['timestamp'] if rows else None,display_latest=rows[-1]['timestamp'] if rows else None,display_count=len(rows),initialization_bars=sum(c['timestamp']<display_start for c in candles),source='Delta India public REST OHLCV; backend public WebSocket forming candles.',anchor_policy='Replay selected history from explicit warmup anchor.',intrabar_history='Forming candles are provisional; no historical replay into execution.',analysis_revision=revision,history_error=None)
        return dict(symbol=config['underlying'],timeframe=config['timeframe'],settings=config,tick_size=tick,rows=rows,incremental=False,history=history,latest=rows[-1] if rows else None,initialization_anchor=result['anchor'],host_bar_count=result['state']['count'],forming=forming,history_error=None,session_policy=self.chart_broker.session_policy(config),option_route=self.chart_broker.route_availability(config),squareoff_time=(config['session_deadline']+' Asia/Kolkata') if config.get('session_deadline') else 'None · continuous crypto; held contract expiry applies',parity='Shared supplied Renko engine; broker candle sources differ.',intrabar_entries=(query.get('intrabar_entries') or ['false'])[0]=='true',provisional_candidate=None,provisional_error=None)

    def get(self, handler, path):
        if not path.startswith(PREFIX): return False
        action=path[len(PREFIX):]; query=parse_qs(urlparse(handler.path).query)
        try:
            if action=='stream': return self.stream(handler,query)
            if action=='runner': value=self.runner.snapshot()
            elif action=='settings': value=self.runner.read_preferences()
            elif action=='broker-positions': value=self.adoptions.inventory()
            elif action=='search':
                text=(query.get('q') or [''])[0].upper()
                value=dict(matches=[dict(symbol=p['symbol'],underlying=p['underlying']) for p in self.delta.catalog()['instruments'] if p['contract_type']=='perpetual_futures' and text in p['symbol']][:50])
            elif action=='chart': value=self.chart(query)
            elif action in ('journal','journal.xlsx'):
                snapshot=self.runner.snapshot();value=dict(schema_version=1,exported_at=time.time(),broker='DELTA_INDIA',pnl_currency=snapshot.get('pnl_currency'),trades=snapshot.get('trade_history',[]))
                if action.endswith('.xlsx'):
                    # Use the existing presentable workbook while retaining native
                    # currency in every trade; export rendering is validated below.
                    from .journal_export import export_xlsx
                    body=export_xlsx(value,self.root)
                    handler.send_response(200); handler.send_header('Content-Type','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'); handler.send_header('Content-Disposition','attachment; filename="renko-delta-journal.xlsx"'); handler.send_header('Content-Length',str(len(body))); handler.end_headers(); handler.wfile.write(body); return True
            else: raise ValueError('Unknown Delta Renko read action.')
            handler.send_json(200,value)
        except Exception as error: handler.send_json(409,dict(error=str(error)))
        return True

    def post(self, handler, path, payload):
        if not path.startswith(PREFIX): return False
        if (handler.headers.get('Host') or '').split(':')[0] not in ('localhost','127.0.0.1'): raise PermissionError('Local dashboard required.')
        origin=handler.headers.get('Origin')
        if origin and urlparse(origin).netloc!=handler.headers.get('Host'): raise PermissionError('Cross-origin actions forbidden.')
        actions=dict(settings=self.runner.save_preferences,preview=self.runner.preview,start=self.runner.activate,stop=lambda p:self.runner.stop(),adopt=self.adoptions.apply,**{'adoption-control':self.adoptions.control})
        action=path[len(PREFIX):]
        if action not in actions: raise ValueError('Unknown Delta Renko action.')
        if self.instrument and action in ('preview','start','adopt') and payload.get('underlying')!=self.instrument:raise ValueError('Action instrument differs from selected instance.')
        handler.send_json(200,actions[action](payload)); return True

    def stream(self, handler, query):
        config=self.chart_config(query); self.chart_broker.subscribe(config['underlying'],TIMEFRAMES[config['timeframe']]); self.chart_broker.start()
        handler.send_response(200); handler.send_header('Content-Type','text/event-stream'); handler.send_header('Cache-Control','no-store'); handler.end_headers()
        try:
            while True:
                forming=None; error=None
                try: forming=self.chart_broker.forming(config,[],time.time())
                except ValueError as exc: error=str(exc)
                frame=dict(runner=self.runner.snapshot(),forming=forming,market=dict(connected=self.chart_broker.connected,fresh=forming is not None,error=error),orders=dict(connected=False,basis='Delta REST reconciliation; broker order notifications not claimed.'),server_at=time.time(),bar_seconds=TIMEFRAMES[config['timeframe']],adopted_managers=[dict(id=k,**r.snapshot()) for k,r in self.adoptions.runners.items()])
                with self.lock: context=self.context.get(json.dumps(config,sort_keys=True))
                if context and forming:
                    try: frame['display_analysis']=provisional(*context[:1],forming,context[1],context[2],time.time())
                    except ValueError: pass
                handler.wfile.write(('event: state\ndata: '+json.dumps(frame,allow_nan=False)+'\n\n').encode()); handler.wfile.flush()
                self.wake.wait(1); self.wake.clear(); time.sleep(.15)
        except (BrokenPipeError,ConnectionResetError,TimeoutError): pass
        finally: handler.close_connection=True
        return True
