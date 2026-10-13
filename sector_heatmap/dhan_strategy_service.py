"""Account-bound Dhan strategy services; no global credential fallback."""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import threading
import time
from urllib.parse import parse_qs,urlparse
from strategies.renko_supertrend.delta_service import Service as ChartService
from strategies.renko_supertrend.runner import Runner,configuration
from strategies.ema_crossover.runner import Runner as RsiRunner,configuration as rsi_configuration
from .dhan_strategy_broker import Broker


def renko_configuration(payload):
    if payload.get('broker')!='DHAN':raise ValueError('Explicit Dhan broker selection required.')
    if payload.get('execution_route','OPTIONS')!='OPTIONS':raise ValueError('Dhan Renko currently supports bought options only.')
    return dict(configuration(payload),broker='DHAN')


def rsi_config(payload):
    if payload.get('broker')!='DHAN':raise ValueError('Explicit Dhan broker selection required.')
    if payload.get('execution_route','OPTIONS')!='OPTIONS':raise ValueError('Dhan RSI currently supports bought options only.')
    return dict(rsi_configuration(payload),broker='DHAN')


class DhanRenkoRunner(Runner):
    from .dhan_recovery import reconcile_external_close

    def event(self, code, message):
        message=message.replace('MARKET (FYERS MPP)', 'marketable LIMIT IOC').replace('FYERS','Dhan')
        return super().event(code, message)

    configure=staticmethod(renko_configuration)
    runtime_revision='dhan-renko-owned-options-v1'


    def session_bounds(self,c):
        if c.get('underlying','').startswith('MCX:'):
            from .dhan_mcx import trading_bounds
            return trading_bounds(self.clock())
        return super().session_bounds(c)

    def deadline(self):
        c=self.state.get('config') or {}
        if c.get('underlying','').startswith('MCX:'):
            from .dhan_mcx import session,entry_cutoff
            c.update(session(self.clock()))
            pending=self.state.get('pending') or {}
            held=self.state.get('position') or pending.get('position')
            if self.state.get('running') and held:
                try:
                    # Compute from persisted exact contract metadata, even after
                    # that contract disappears from the current instrument master.
                    symbol=held['symbol']
                    meta=self.adapter.contracts.get(symbol) or self.adapter.contract(symbol)
                    row=dict(SM_SYMBOL_NAME=meta['commodity'],SEM_EXPIRY_DATE=meta['expiry'])
                    cutoff=entry_cutoff(row)
                    if self.clock()>=cutoff:
                        held.update(exit_requested=True,exit_reason='MCX_PRE_EXPIRY_EXIT',expiry_protection_at=cutoff)
                        self.state['accepting_entries']=False
                except (ValueError,KeyError) as error:
                    cutoff=held.get('expiry_protection_at')
                    if not cutoff:
                        held.update(exit_requested=True,exit_reason='MCX_EXPIRY_UNVERIFIED',expiry_error=str(error))
                        self.state['accepting_entries']=False
                    if cutoff and self.clock()>=cutoff:
                        held.update(exit_requested=True,exit_reason='MCX_PRE_EXPIRY_EXIT')
                        self.state['accepting_entries']=False
                self.save()
            if c.get('commodity_holding')=='CARRY_FORWARD':return
        return super().deadline()

    def step(self):
        c=self.state.get('config') or {}
        if c.get('underlying','').startswith('MCX:'):
            from .dhan_mcx import session_open
            with self.lock:
                self.deadline()
                if self.state.get('running') and not session_open(self.clock()):
                    if self.state.get('pending'):self.reconcile()
                    self.state.update(status='OUTSIDE_SESSION',message='Dhan MCX session closed; ownership retained and no stale-price execution.')
                    self.save()
                    return
        return super().step()

    def snapshot(self):
        value=super().snapshot()
        from strategies.renko_supertrend.dhan_costs import MODEL
        value['cost_pnl'].update(model=MODEL,brokerage_per_executed_order=20)
        value['dhan_cost_revision']='dhan-options-costs-v1'
        value['external_close_recovery_revision']='dhan-external-close-v1'
        return value

    def record_order(self,pending,status,filled=0,price=None):
        super().record_order(pending,status,filled,price)
        for row in self.state['order_history']:
            if row['tag']==pending['tag']:
                row.update(dhan_exchange_rate=self.adapter.contract(row['symbol']).get('dhan_exchange_rate'),broker='DHAN',account_id=self.adapter.service.account['id'],requested_type='LIMIT',validity='IOC')


class DhanRsiRunner(RsiRunner):
    from .dhan_recovery import reconcile_external_close

    def event(self, code, message):
        message=message.replace('MARKET (FYERS MPP)', 'marketable LIMIT IOC').replace('FYERS','Dhan')
        return super().event(code, message)

    configure=staticmethod(rsi_config)
    runtime_revision='dhan-rsi-owned-options-v1'
    def record_order(self,pending,status,filled=0,price=None):
        super().record_order(pending,status,filled,price)
        for row in self.state['order_history']:
            if row['tag']==pending['tag']:
                row.update(dhan_exchange_rate=self.adapter.contract(row['symbol']).get('dhan_exchange_rate'),broker='DHAN',account_id=self.adapter.service.account['id'],requested_type='LIMIT',validity='IOC')


class Service(ChartService):
    def __init__(self,execution,root,instance='default',strategy='renko'):
        self.order_source='Dhan REST reconciliation; broker order notifications not claimed.'
        self.execution=execution;self.root=Path(root);self.instance_key=instance;self.instrument=None
        self.context={};self.lock=threading.RLock();self.wake=threading.Event();self.strategy=strategy
        self.broker=Broker(execution);self.chart_broker=Broker(execution)
        folder=execution.folder/'dhan-strategies'/strategy/instance
        folder.mkdir(parents=True,exist_ok=True,mode=0o700)
        if strategy in ('band','kama'):
            from .dhan_indicator_runners import BandRunner,KamaRunner
            runner_type=BandRunner if strategy=='band' else KamaRunner
        else:runner_type=DhanRenkoRunner if strategy=='renko' else DhanRsiRunner
        self.runner=runner_type(self.broker,folder/'state.json')
        self.runner.valuation_adapter=self.chart_broker
        instrument=folder/'instrument.json'
        if instrument.exists():self.instrument=json.loads(instrument.read_text())['underlying']
        class EmptyAdoptions:
            lock=threading.RLock()
            runners={}
        self.adoptions=EmptyAdoptions()

    def chart_config(self,query):
        # Reuse chart indicator parsing, but never Delta carry/product policies.
        compatible={**query,'carry_policy':['CONTINUOUS'],'execution_route':['OPTIONS']}
        config=super().chart_config(compatible)
        config.update(broker='DHAN',carry_policy=None)
        config.update(self.chart_broker.session_policy(config))
        return config

    def chart(self,query):
        result=super().chart(query)
        result['history']['source']='Dhan account Data API OHLCV; REST polling; missing candles are never synthesized.'
        result['squareoff_time']=result['session_policy']['session_deadline']+' Asia/Kolkata'
        return result

    def get_action(self,handler,action,query):
        if action.startswith('form-'):
            from .dhan_form_routes import read
            handler.send_json(200,read(self,action[5:],query));return
        if action=='runner':
            value=self.runner.snapshot();value['instrument']=self.instrument
        elif action=='settings' and self.strategy=='renko':value=self.runner.read_preferences()
        elif action=='search':value=dict(matches=self.chart_broker.search((query.get('q') or [''])[0],(query.get('market') or [None])[0]))
        elif action=='manual-brick' and self.strategy=='renko':value=self.manual_brick(query)
        elif action=='chart' and self.strategy=='renko':value=self.chart(query)
        elif action=='stream' and self.strategy=='renko':return self.stream(handler,query)
        elif action=='broker-positions':value=dict(positions=[],managers=[],message='External Dhan positions cannot be adopted by this strategy.')
        elif action in ('journal','journal.xlsx'):
            snap=self.runner.snapshot()
            value=dict(schema_version=1,broker='DHAN',account_id=self.execution.account['id'],
                       exported_at=time.time(),trades=snap.get('trade_history',snap.get('order_history',[])))
            if action.endswith('.xlsx'):
                from strategies.renko_supertrend.journal_export import export_xlsx
                body=export_xlsx(value,self.root)
                handler.send_response(200);handler.send_header('Content-Type','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                handler.send_header('Content-Length',str(len(body)));handler.end_headers();handler.wfile.write(body);return
        else:raise ValueError('Unsupported Dhan strategy read action.')
        handler.send_json(200,value)

    def post_action(self,handler,action,payload):
        if payload.get('account_id') not in (None,self.execution.account['id']):
            raise PermissionError('Dhan strategy account differs from selected account.')
        if payload.get('broker') not in (None,'DHAN'):raise PermissionError('Dhan strategy cannot route another broker.')
        if action=='preview' and self.strategy in ('band','kama') and payload.get('strategy')!=self.runner.strategy_id:
            raise ValueError('Strategy differs from the selected Dhan form.')
        if self.instrument and (action in ('preview','override-entry') or (action=='start' and self.strategy=='renko')) and payload.get('underlying')!=self.instrument:
            raise ValueError('Action instrument differs from selected Dhan instance.')
        origin=handler.headers.get('Origin')
        if origin and urlparse(origin).netloc!=handler.headers.get('Host'):raise PermissionError('Cross-origin action forbidden.')
        if action.startswith('form-'):
            from .dhan_form_routes import write
            handler.send_json(200,write(self,action[5:],payload));return
        actions=dict(preview=self.runner.preview,start=self.runner.activate if self.strategy=='renko' else self.runner.start,
                     stop=lambda p:self.runner.stop(),**{'reconcile-external-close':lambda p:self.runner.reconcile_external_close(p)})
        if self.strategy=='renko':
            actions.update(settings=self.runner.save_preferences,**{'chart-timeframe':self.runner.chart_timeframe,
                'chart-mode':self.runner.chart_mode,'chart-stop':self.runner.chart_stop,
                'override-entry':self.runner.override_entry,'resume-position':self.runner.resume_position})
        if action not in actions:raise ValueError('Unsupported Dhan strategy action.')
        handler.send_json(200,actions[action](payload))
