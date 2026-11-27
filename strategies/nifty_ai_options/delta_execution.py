from strategies.nifty_ai_options.multi_runner import coordinated_submit
"""Own AI ledger around the existing native Delta order/reconciliation boundary."""
import fcntl,hashlib,json,math,time
from pathlib import Path
from contextlib import nullcontext
try:from .run import atomic
except ImportError:from run import atomic
ACTIONS={'BUY':(True,1),'SELL':(False,-1),'OPEN_LONG':(True,1),'OPEN_SHORT':(True,-1),'CLOSE_LONG':(False,-1),'CLOSE_SHORT':(False,1)}
from strategies.nifty_ai_options.delta_entry_policy import ENTRY_POLICY_REVISION
class DeltaExecution:
    entry_policy_revision=ENTRY_POLICY_REVISION
    def __init__(self,delta,owner,state_dir,*,live=False,contracts=None,native=None,management_only=False):
        from strategies.renko_supertrend.delta_execution import Execution as NativeExecution
        if isinstance(contracts,bool) or not isinstance(contracts,int) or contracts<1:raise ValueError('Explicit positive whole Delta contracts required')
        self.management_only=management_only
        self.delta,self.owner,self.live,self.contracts=delta,owner,live,contracts
        self.native=native or NativeExecution(delta)
        directory=Path(state_dir)/owner;directory.mkdir(parents=True,exist_ok=True)
        self.lock=(directory/'execution.lock').open('a')
        try:fcntl.flock(self.lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BaseException:self.lock.close();raise
        self.path=directory/('delta-live.json' if live else 'delta-paper.json')
        self.state=json.loads(self.path.read_text()) if self.path.exists() else dict(position=None,pending=None,seen=[])
        if management_only:return
        if any(slot.get('position') or slot.get('pending') for slot in self.state.get('closing_legs',{}).values()):
            self.close();raise ValueError('Previous option legs retain exposure or orders; use the captured Stop recovery before a new run')
        if self.state.get('detached_position') or self.state.get('stop_verification_position'):self.close();raise ValueError('Retained position control requires Attach or Stop')
        if self.state.get('position') or self.state.get('pending'):self.close();raise ValueError('Owned Delta position/pending intent requires reconciliation before restart')
    def save(self):atomic(self.path,self.state)
    def close(self):self.lock.close()
    def reconcile_pending(self):
        pending=self.state.get('pending')
        if not self.live or not pending:return
        key=pending.get('native_request_id') or pending.get('key')
        row=self.native.reconcile(key)
        intent=pending.get('intent') or {};action=intent.get('action')
        if action in ACTIONS and row.get('status')==2:
            position=intent['position'];product_id=int(position['product_id'])
            entry=ACTIONS[action][0];quantity=self.contracts if entry else (self.state.get('position') or {}).get('quantity')
            filled=row.get('filledQty')
            active=self.native.active_orders()
            if row.get('orderTag')!=key or int(row.get('product_id',-1))!=product_id or not isinstance(quantity,int) or isinstance(filled,bool) or filled!=quantity:return
            if not isinstance(active,list) or any(int(r.get('product_id',-1))==product_id for r in active):return
            expected=(quantity*(-1 if position.get('side')=='SHORT' else 1)) if entry else 0
            current=self.delta._position(product_id)
            if current!=expected:return
            self.state['position']=dict(position,quantity=quantity,fill_price=row.get('tradedPrice'),order_id=str(row.get('id'))) if entry else None
            if not entry:self.state.pop('retained_exit_failure',None)
            receipt=dict(kind='DELTA_ORDER_VERIFIED',action=intent,order_id=str(row.get('id')),filled_quantity=filled,fill_price=row.get('tradedPrice'),broker_quantity=current,broker_flat=current==0,checked_at=self.delta.clock(),orders_submitted=0)
            try:from .option_legs import capture_fill
            except ImportError:from option_legs import capture_fill
            capture_fill(self.state,intent,dict(order_id=receipt['order_id'],filled_quantity=filled,fill_price=receipt['fill_price']),receipt['checked_at'],key)
            self.state.setdefault('reconciled_intents',[]).append(receipt);self.state['pending']=None;self.save();return receipt
        # Only a terminal, zero-fill intent with independently verified flat
        # broker position and no active selected-product orders may be released.
        if row.get('native_status') not in ('cancelled','rejected') or int(row.get('filledQty',0))!=0:return
        product_id=int(pending['intent']['position']['product_id'])
        active=self.native.active_orders()
        if row.get('orderTag')!=key or int(row.get('product_id',-1))!=product_id:return
        if self.delta._position(product_id)!=0 or not isinstance(active,list) or any(int(r.get('product_id',-1))==product_id for r in active):return
        self.state.setdefault('reconciled_intents',[]).append(dict(key=key,order=row,broker_flat=True,at=self.delta.clock()))
        self.state['pending']=None;self.save()
    @coordinated_submit
    def submit(self,action,quote):
        from sector_heatmap.chart_trade_admission import entry_lock
        try:from .run import ROOT
        except ImportError:from run import ROOT
        if self.management_only and action.get('action') in ('BUY','OPEN_LONG','OPEN_SHORT'):raise ValueError('Position-management worker cannot place new entries')
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
        entry_book=None
        if self.live and entry:
            from strategies.nifty_ai_options.delta_entry_policy import read_depth,EntryNotReady
            try:quote,entry_book=read_depth(self.delta,symbol)
            except (EntryNotReady,ValueError) as error:return dict(deferred=True,reason='ENTRY_DEPTH_UNAVAILABLE',detail=str(error),orders_submitted=0)
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
        original_limit=None
        if self.live and entry:
            from strategies.nifty_ai_options.delta_entry_policy import sufficient_market_depth,EntryNotReady
            try:sufficient_market_depth(entry_book,side,quantity)
            except EntryNotReady as error:return dict(deferred=True,reason='ENTRY_DEPTH_UNAVAILABLE',detail=str(error),orders_submitted=0)
        self.state['pending']=dict(key=key,intent=action,stage='PREPARED',order_type='market_order' if entry or p.get('execution_route')=='DIRECT' else 'limit_order',original_limit=original_limit,attempts=[])
        self.state['seen'].append(key);self.save()
        if not self.live:
            price=ask if side>0 else bid
            self.state['position']=dict(p,quantity=quantity,fill_price=price,simulated=True) if entry else None
            result=dict(dry_run=True,simulated_fill=price,filled_quantity=quantity)
            try:from .option_legs import capture_fill
            except ImportError:from option_legs import capture_fill
            capture_fill(self.state,action,result,self.delta.clock(),key)
            self.state['pending']=None;self.save();return result
        if entry:
            from sector_heatmap.chart_trade_admission import mark_entry_attempt
            mark_entry_attempt('DELTA_INDIA',folder=Path('/home/trading/sector-heatmap/.private/dashboard-login/accounts')/self.owner)
        return self._live_attempts(action,quote,entry,side,quantity,key,meta,original_limit)

    def _no_fill(self,reason,detail=None):
        completed=dict(self.state['pending']);completed.update(outcome=reason,completed_at=self.delta.clock())
        self.state.setdefault('entry_attempts',[]).append(completed)
        self.state['pending']=None;self.save()
        return dict(deferred=True,terminal_no_fill=True,reason=reason,detail=detail,attempts=completed.get('attempts',[]))

    def _verify_zero_entry(self,row,key,meta):
        if row.get('orderTag')!=key or row.get('symbol')!=meta['symbol'] or int(row.get('product_id',-1))!=meta['product_id']:return False
        if row.get('native_status')!='cancelled' or int(row.get('filledQty',-1))!=0:return False
        active=self.native.active_orders()
        return isinstance(active,list) and not any(int(r.get('product_id',-1))==meta['product_id'] for r in active) and self.delta._position(meta['product_id'])==0

    def _record_verified_fill(self,action,row,quantity,key):
        # Commit fill evidence before downstream flat/reversal/worker callbacks.
        result=dict(dry_run=False,order_id=row['id'],filled_quantity=quantity,fill_price=row.get('tradedPrice'),filled_at=self.delta.clock())
        try:from .option_legs import capture_fill
        except ImportError:from option_legs import capture_fill
        capture_fill(self.state,action,result,result['filled_at'],key)
        self.save()
        path=getattr(self,'fill_evidence_path',None)
        if path:
            import os
            record=dict(action=action,result=result,recorded_at=result['filled_at'],source='VALIDATED_NATIVE_BROKER_FILL')
            with Path(path).open('a') as stream:
                stream.write(json.dumps(record,sort_keys=True)+'\n');stream.flush();os.fsync(stream.fileno())
        return result

    def _live_attempts(self,action,quote,entry,side,quantity,key,meta,original_limit):
        p=action['position'];symbol=p['symbol']
        for attempt in range(2 if entry else 1):
            native_key=key if attempt==0 else key+'_r1'
            if attempt:
                from strategies.nifty_ai_options.delta_entry_policy import read_depth,sufficient_market_depth,EntryNotReady
                try:
                    quote,book=read_depth(self.delta,symbol)
                    sufficient_market_depth(book,side,quantity)
                except (EntryNotReady,ValueError) as error:return self._no_fill('ENTRY_RETRY_SKIPPED',str(error))
            self.state['pending'].update(stage='SUBMITTING_ATTEMPT',native_request_id=native_key,retry_used=bool(attempt))
            self.state['pending']['attempts'].append(dict(request_id=native_key,limit_price=original_limit,prepared_at=self.delta.clock(),attempt=attempt+1))
            self.save()  # Durable retry identity and budget precede native POST.
            kwargs=dict(reduce_only=not entry)
            if entry or p.get('execution_route')=='DIRECT':kwargs['order_type']='market_order'
            if entry and p.get('execution_route')=='DIRECT':kwargs['collateral_policy']='BROKER_CONFIGURED_MARGIN'
            from strategies.renko_supertrend.delta_execution import EntryFundsRejected,EntryMarginUnavailable
            try:
                self.native.submit(symbol,quantity,side,quote,native_key,p['underlying'],action.get('reason','AI_RENKO_CONFIRMED_FLIP'),**kwargs)
            except (EntryFundsRejected,EntryMarginUnavailable) as error:
                if not entry:raise
                self.state['pending']['attempts'][-1].update(outcome='LOCAL_FUNDS_REJECTED',orders_submitted=0,required=getattr(error,'required',None),available=getattr(error,'available',None),currency=getattr(error,'currency',None))
                result=self._no_fill('ENTRY_FUNDS_UNAVAILABLE' if isinstance(error,EntryFundsRejected) else 'ENTRY_MARGIN_UNAVAILABLE',str(error));result['orders_submitted']=0
                return result
            self.state['pending']['stage']='SUBMITTED_OR_UNCERTAIN';self.save()
            deadline=time.monotonic()+getattr(self,'confirmation_timeout',20);last=None
            while time.monotonic()<deadline:
                row=self.native.reconcile(native_key);last=row
                filled=int(row.get('filledQty',0))
                if row.get('status')==2 and filled==quantity:
                    if entry:
                        self.state['position']=dict(p,quantity=quantity,order_id=row['id'],fill_price=row.get('tradedPrice'))
                        self.state['pending']['stage']='FILLED_VERIFIED'
                    result=self._record_verified_fill(action,row,quantity,key)
                    if not entry:
                        self.state['pending']['stage']='FILLED_AWAITING_FLAT';self.save()
                        active=self.native.active_orders()
                        if self.delta._position(meta['product_id'])!=0 or not isinstance(active,list) or any(int(r.get('product_id',-1))==meta['product_id'] for r in active):
                            raise RuntimeError('Delta exit fill acknowledged but signed flat state unconfirmed; no reversal or duplicate exit')
                    self.state['position']=dict(p,quantity=quantity,order_id=row['id'],fill_price=row.get('tradedPrice')) if entry else None
                    self.state.setdefault('entry_attempts',[]).append(dict(self.state['pending'],outcome='FILLED',completed_at=self.delta.clock()))
                    self.state['pending']=None;self.save()
                    return result
                if entry and row.get('native_status')=='cancelled' and filled==0:
                    if not self._verify_zero_entry(row,native_key,meta):break
                    self.state['pending']['attempts'][-1].update(outcome='CANCELLED_ZERO_FILL',order_id=row.get('id'),verified_flat=True)
                    self.save()
                    if attempt==1:return self._no_fill('ENTRY_IOC_ZERO_FILL')
                    break
                if row.get('status') in (1,5) or filled>0:break
                time.sleep(.5)
            if entry and last and self.state['pending']['attempts'][-1].get('outcome')=='CANCELLED_ZERO_FILL':
                continue
            self.state['pending']['stage']='UNRESOLVED_FILL';self.save()
            raise RuntimeError('Partial/unfilled/unknown Delta intent retained; no new entry or resubmission')
