"""Own AI ledger around the existing native Delta order/reconciliation boundary."""
import fcntl,hashlib,json,math,time
from pathlib import Path
from contextlib import nullcontext
try:from .run import atomic
except ImportError:from run import atomic
ACTIONS={'BUY':(True,1),'SELL':(False,-1),'OPEN_LONG':(True,1),'OPEN_SHORT':(True,-1),'CLOSE_LONG':(False,-1),'CLOSE_SHORT':(False,1)}
class DeltaExecution:
    def __init__(self,delta,owner,state_dir,*,live=False,contracts=None,native=None):
        from strategies.renko_supertrend.delta_execution import Execution as NativeExecution
        if isinstance(contracts,bool) or not isinstance(contracts,int) or contracts<1:raise ValueError('Explicit positive whole Delta contracts required')
        self.delta,self.owner,self.live,self.contracts=delta,owner,live,contracts
        self.native=native or NativeExecution(delta)
        directory=Path(state_dir)/owner;directory.mkdir(parents=True,exist_ok=True)
        self.lock=(directory/'execution.lock').open('a');fcntl.flock(self.lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        self.path=directory/('delta-live.json' if live else 'delta-paper.json')
        self.state=json.loads(self.path.read_text()) if self.path.exists() else dict(position=None,pending=None,seen=[])
        if self.state.get('position') or self.state.get('pending'):self.close();raise ValueError('Owned Delta position/pending intent requires reconciliation before restart')
    def save(self):atomic(self.path,self.state)
    def close(self):self.lock.close()
    def submit(self,action,quote):
        from sector_heatmap.chart_trade_admission import entry_lock
        try:from .run import ROOT
        except ImportError:from run import ROOT
        if action.get('action') not in ACTIONS:raise ValueError('Unknown Delta AI action')
        entry,side=ACTIONS[action['action']];folder=ROOT/'.private/dashboard-login/accounts'/self.owner
        with entry_lock('DELTA_INDIA',folder=folder) if self.live and entry else nullcontext():
            if self.live and entry:
                from sector_heatmap.chart_trade_ownership import assert_no_chart_entry_conflict
                assert_no_chart_entry_conflict(folder/'chart-trading.sqlite3',self.owner,'DELTA_INDIA')
            return self._submit(action,quote,entry,side)
    def _submit(self,action,quote,entry,side):
        from strategies.renko_supertrend.delta_contracts import contract_metadata
        if self.state.get('pending'):raise ValueError('Pending or uncertain Delta intent must be reconciled before another submission')
        now=self.delta.clock();p=action['position'];symbol=p['symbol'];meta=contract_metadata(self.delta.product(symbol),now)
        if not quote or quote.get('symbol')!=symbol or not -2<=now-quote.get('exchange_at',0)<=15:raise ValueError('Fresh exact Delta quote required')
        bid,ask=quote.get('bid'),quote.get('ask')
        if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<=0 for v in (bid,ask)) or bid>ask:raise ValueError('Valid executable Delta bid/ask required')
        option=meta.get('option_type') in ('CE','PE')
        if option and action['action'] not in ('BUY','SELL'):raise ValueError('Options are bought-only; no direct/naked short action')
        if not option and action['action'] in ('BUY','SELL'):raise ValueError('Direct product requires explicit signed open/close action')
        if p.get('execution_route')=='DIRECT' and p.get('underlying')!=symbol:raise ValueError('Direct Delta product differs from selected underlying')
        if p.get('option_type') and (meta.get('option_type')!=p['option_type'] or float(meta.get('expiry_epoch',0))!=float(p.get('expiry',0))):raise ValueError('Frozen option/master identity differs')
        own=self.state['position'];quantity=self.contracts
        if entry and own:raise ValueError('AI runtime already owns exposure')
        if not entry:
            if not own or own['symbol']!=symbol or own.get('side')!=p.get('side'):raise ValueError('No exact owned Delta position to reduce')
            quantity=own['quantity']
        key='nai_'+hashlib.sha256(json.dumps([action['timestamp'],symbol,action['action'],p['entry_timestamp']],sort_keys=True).encode()).hexdigest()[:40]
        if key in self.state['seen']:raise ValueError('Duplicate Delta intent blocked')
        if self.live and not entry:
            signed=quantity*(-1 if p.get('side')=='SHORT' else 1)
            if self.delta._position(meta['product_id'])!=signed:raise ValueError('Broker signed quantity differs from exact AI ownership')
        self.state['pending']=dict(key=key,intent=action,stage='PREPARED');self.state['seen'].append(key);self.save()
        if not self.live:
            price=ask if side>0 else bid
            self.state['position']=dict(p,quantity=quantity,fill_price=price,simulated=True) if entry else None
            self.state['pending']=None;self.save();return dict(dry_run=True,simulated_fill=price,filled_quantity=quantity)
        if entry:
            from sector_heatmap.chart_trade_admission import mark_entry_attempt
            mark_entry_attempt('DELTA_INDIA',folder=Path('/home/trading/sector-heatmap/.private/dashboard-login/accounts')/self.owner)
        # Native boundary persists its own intent before POST and never resends unknowns.
        owned=self.native.submit(symbol,quantity,side,quote,key,p['underlying'],action.get('reason','AI_RENKO_CONFIRMED_FLIP'),reduce_only=not entry)
        self.state['pending'].update(stage='SUBMITTED_OR_UNCERTAIN',native_request_id=key);self.save()
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            row=self.native.reconcile(key)
            if row.get('status')==2 and int(row.get('filledQty',0))==quantity:
                self.state['position']=dict(p,quantity=quantity,order_id=row['id'],fill_price=row.get('tradedPrice')) if entry else None
                self.state['pending']=None;self.save();return dict(dry_run=False,order_id=row['id'],filled_quantity=quantity,fill_price=row.get('tradedPrice'))
            if row.get('status') in (1,5) or int(row.get('filledQty',0))>0:break
            time.sleep(.5)
        self.state['pending']['stage']='UNRESOLVED_FILL';self.save();raise RuntimeError('Partial/unfilled/unknown Delta intent retained; no new entry or resubmission')
