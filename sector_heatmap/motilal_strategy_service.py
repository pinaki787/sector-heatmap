"""Motilal Renko component inside the existing strategy UI; no separate screen."""
from pathlib import Path
import hashlib,json,re,threading,time
from .config import _atomic_private_write
from .motilal_strategy_broker import Broker,BROKER
from .motilal_history_seed import source_settings
from strategies.renko_supertrend.delta_service import Service as SharedChart
from strategies.renko_supertrend.runner import Runner,configuration

def configure(payload):
    if payload.get('broker')!=BROKER:raise PermissionError('Explicit Motilal broker required.')
    if payload.get('commodity_holding')=='CARRY_FORWARD':raise ValueError('Motilal carry-forward position management is not verified; choose Intraday.')
    if payload.get('execution_route')=='CASH_EQUITY' and payload.get('cash_product','INTRADAY')!='INTRADAY':raise ValueError('Motilal cash delivery product is not verified; choose Intraday.')
    return dict(configuration(payload),broker=BROKER,**source_settings(payload))

class MotilalRunner(Runner):
    configure=staticmethod(configure)
    runtime_revision=Runner.runtime_revision
    def event(self,code,message):return super().event(code,message.replace('FYERS','Motilal Oswal').replace('MARKET (Motilal Oswal MPP)','LIMIT IOC'))
    def record_order(self,pending,status,filled=0,price=None):
        super().record_order(pending,status,filled,price)
        for row in self.state['order_history']:
            if row['tag']==pending['tag']:row.update(broker=BROKER,account_id=self.adapter.service.account['id'],requested_type='LIMIT',validity='IOC')
    def save_preferences(self,payload):
        values=payload.get('settings') or {}
        extra=source_settings(dict(fyers_history_enabled=values.get('fyers-history-enabled',False),fyers_history_account_id=values.get('fyers-history-account-id','')))
        with self.lock:
            result=super().save_preferences(payload)
            result['settings'].update({'fyers-history-enabled':extra['fyers_history_enabled'],'fyers-history-account-id':extra['fyers_history_account_id']})
            _atomic_private_write(self.path.with_name('renko-supertrend-settings.json'),json.dumps(result,allow_nan=False))
            return result
    def snapshot(self):
        value=super().snapshot();value.update(broker=BROKER,motilal_route_revision='motilal-native-renko-v1',account_id=self.adapter.service.account['id'],market_data_source='FYERS explicit history + Motilal native ticks' if (self.state.get('config') or {}).get('fyers_history_enabled') else 'Motilal native ticks; captured completed candles only')
        # FYERS retail fee estimates are not Motilal contract-note charges.
        value['cost_pnl'].update(realized_net=None,unrealized_net=None,total_net=None,model='MOTILAL_FEES_UNVERIFIED',basis='Gross fills available; Motilal contract-note charges are not estimated by another broker model.')
        return value

class Service(SharedChart):
    def __init__(self,execution,root,instance='default'):
        self.execution=execution;self.root=Path(root);self.instance_key=instance;self.instrument=None
        self.context={};self.lock=threading.RLock();self.wake=threading.Event()
        self.order_source='Motilal native orderbook reconciliation; acceptance is not a fill'
        self.broker=Broker(execution);self.chart_broker=Broker(execution)
        folder=execution.folder/'motilal-strategies'/'renko'/instance;folder.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.runner=MotilalRunner(self.broker,folder/'state.json');self.runner.valuation_adapter=self.chart_broker
        if (folder/'instrument.json').exists():self.instrument=json.loads((folder/'instrument.json').read_text())['underlying']
        class EmptyAdoptions:
            lock=threading.RLock();runners={}
        self.adoptions=EmptyAdoptions()
    def history_source(self,payload):
        value=dict(payload)
        if value.get('fyers_history_enabled') is True and not value.get('fyers_history_account_id'):
            value['fyers_history_account_id']=self.execution.history_seed.account_id()
        return value
    def chart_config(self,query):
        query=dict(query)
        if (query.get('fyers_history_enabled') or ['false'])[0]=='true' and not (query.get('fyers_history_account_id') or [''])[0]:
            query['fyers_history_account_id']=[self.execution.history_seed.account_id()]
        value=super().chart_config({**query,'carry_policy':['CONTINUOUS'],'execution_route':['OPTIONS']})
        value.update(broker=BROKER,carry_policy=None,**source_settings(dict(fyers_history_enabled=(query.get('fyers_history_enabled') or ['false'])[0]=='true',fyers_history_account_id=(query.get('fyers_history_account_id') or [''])[0])),**self.chart_broker.session_policy(value));return value
    def chart(self,query):
        result=super().chart(query)
        result['history']['source']='FYERS explicit historical seed + Motilal native live candles; execution Motilal only' if (query.get('fyers_history_enabled') or ['false'])[0]=='true' else 'Motilal native captured ticks; no alternate-broker history or synthesized gaps'
        result['history']['intrabar_history']='Captured bars require uninterrupted subscription coverage from their opening; warmup is mandatory.'
        if (query.get('fyers_history_enabled') or ['false'])[0]=='true':
            aid=(query.get('fyers_history_account_id') or [''])[0];meta=self.chart_broker.underlying(result['symbol'])
            evidence=self.execution.history_seed.evidence.get((aid,meta['symbol']),{})
            result['history']['fyers_seed']=evidence
            if evidence.get('rejected_candles'):result['history']['source']+='; inconsistent FYERS candles rejected; analysis restarts after the latest rejected candle'
        result['squareoff_time']=result['session_policy']['session_deadline']+' Asia/Kolkata'
        return result
    def manual_brick(self,query):
        # Shared implementation already requests selected ATR length and broker
        # policy. Native captures cannot invent past complete session candles.
        return super().manual_brick(query)
    def get_action(self,handler,action,query):
        if action=='stream':return self.stream(handler,query)
        if action=='runner':value=dict(self.runner.snapshot(),instrument=self.instrument)
        elif action=='settings':value=self.runner.read_preferences()
        elif action=='search':value=dict(matches=self.chart_broker.search((query.get('q') or [''])[0],(query.get('market') or [None])[0]))
        elif action=='manual-brick':value=self.manual_brick(query)
        elif action=='chart':value=self.chart(query)
        elif action=='broker-positions':value=dict(positions=[],managers=[],message='External Motilal positions cannot be silently adopted.')
        elif action in ('journal','journal.xlsx'):
            snap=self.runner.snapshot();value=dict(schema_version=1,broker=BROKER,account_id=self.execution.account['id'],exported_at=time.time(),trades=snap.get('trade_history',[]))
            if action.endswith('.xlsx'):
                from strategies.renko_supertrend.journal_export import export_xlsx
                body=export_xlsx(value,self.root);handler.send_response(200);handler.send_header('Content-Type','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');handler.send_header('Content-Length',str(len(body)));handler.end_headers();handler.wfile.write(body);return
        else:raise ValueError('Unsupported Motilal Renko action.')
        handler.send_json(200,value)
    def post_action(self,handler,action,payload):
        payload=self.history_source(payload)
        if payload.get('account_id') not in (None,self.execution.account['id']) or payload.get('broker') not in (None,BROKER):raise PermissionError('Motilal account/broker mismatch.')
        if self.instrument and action in ('start','preview','override-entry') and payload.get('underlying')!=self.instrument:raise ValueError('Action differs from selected instrument.')
        actions={'preview':self.runner.preview,'start':self.runner.activate,'stop':self.runner.request_stop,'settings':self.runner.save_preferences,
                 'chart-timeframe':self.runner.chart_timeframe,'chart-mode':self.runner.chart_mode,'chart-stop':self.runner.chart_stop,
                 'override-entry':self.runner.override_entry,'resume-position':self.runner.resume_position}
        if action not in actions:raise ValueError('Unsupported Motilal strategy action.')
        handler.send_json(200,actions[action](payload))

class Registry:
    def __init__(self,execution,root):self.execution=execution;self.root=root;self.services={};self.lock=threading.RLock()
    def service(self,key):
        if not re.fullmatch('[a-zA-Z0-9_-]{1,64}',key):raise ValueError('Invalid native strategy instance.')
        with self.lock:
            if key not in self.services:self.services[key]=Service(self.execution,self.root,key)
            return self.services[key]
    def dispatch(self,handler,action,query,payload=None):
        if action=='instances':
            rows=[]
            for path in (self.execution.folder/'motilal-strategies'/'renko').glob('*/instrument.json'):
                key=path.parent.name;service=self.service(key)
                rows.append(dict(service.runner.snapshot(),broker=BROKER,account_id=self.execution.account['id'],instance_key=key,instrument=service.instrument))
            handler.send_json(200,dict(instances=rows));return
        if action=='create':
            if payload is None or payload.get('broker')!=BROKER:raise PermissionError('Explicit Motilal create required.')
            symbol=str(payload.get('underlying','')).strip().upper();Broker(self.execution).underlying(symbol)
            key=hashlib.sha256(symbol.encode()).hexdigest()[:24];folder=self.execution.folder/'motilal-strategies'/'renko'/key
            folder.mkdir(parents=True,exist_ok=True,mode=0o700)
            _atomic_private_write(folder/'instrument.json',json.dumps(dict(underlying=symbol)))
            handler.send_json(200,dict(instance_key=key,broker=BROKER,running=False));return
        service=self.service((query.get('instance') or ['default'])[0])
        if payload is None:return service.get_action(handler,action,query)
        return service.post_action(handler,action,payload)
