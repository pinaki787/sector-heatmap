from strategies.nifty_ai_options.multi_runner import coordinated_submit
"""Direct stock/futures execution with durable ownership and explicit Live opt-in.

Only an explicit runtime may call submit. Module import/constructor send no order.
"""
import fcntl,hashlib,json,math,time
from pathlib import Path
from decimal import Decimal,ROUND_CEILING,ROUND_FLOOR
from contextlib import nullcontext
try:from .run import atomic,ok
except ImportError:from run import atomic,ok
ACTIONS={'OPEN_LONG':(True,1),'OPEN_SHORT':(True,-1),'CLOSE_LONG':(False,-1),'CLOSE_SHORT':(False,1)}
class DirectExecution:
    def __init__(self,api,account,state_dir,*,live=False,lots=None,product=None,master=None,account_folder=None,margin=None,management_only=False,broker='FYERS'):
        if isinstance(lots,bool) or not isinstance(lots,int) or lots<1:raise ValueError('Explicit whole lots/shares required')
        if product not in ('MARGIN','INTRADAY','CNC'):raise ValueError('Explicit FYERS product required')
        if broker not in ('FYERS','DHAN','MOTILAL_OSWAL'):raise ValueError('Unsupported direct broker boundary')
        self.broker=broker
        self.management_only=management_only
        self.api,self.live,self.lots,self.product,self.master,self.account_folder,self.margin=api,live,lots,product,master,account_folder,margin
        directory=Path(state_dir)/account;directory.mkdir(parents=True,exist_ok=True)
        self.lock=(directory/'execution.lock').open('a')
        try:fcntl.flock(self.lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BaseException:self.lock.close();raise
        self.path=directory/('direct-live.json' if live else 'direct-paper.json')
        self.state=json.loads(self.path.read_text()) if self.path.exists() else dict(position=None,pending=None,seen=[])
        for name in (('live.json' if live else 'paper.json'),('native-indian-live.json' if live else 'native-indian-paper.json')):
            other=directory/name
            if other.exists():
                retained=json.loads(other.read_text())
                if any(retained.get(k) for k in ('position','pending','positions','closing_legs','detached_position','stop_verification_position')):
                    self.close();raise ValueError('Another AI route retains owned exposure or pending intent; reconcile before switching routes')

        if management_only:return
        if self.state.get('detached_position') or self.state.get('stop_verification_position'):self.close();raise ValueError('Retained position control requires Attach or Stop')
        if self.state.get('position') or self.state.get('pending'):self.close();raise ValueError('Owned position or uncertain intent requires reconciliation; no automatic restart')
    def close(self):self.lock.close()
    def save(self):atomic(self.path,self.state)
    def reconcile_pending(self):
        """Read broker truth only; never resubmit a partial or unknown intent."""
        pending=self.state.get('pending')
        if not pending:return None
        if not self.live:raise ValueError('Paper pending state requires explicit recovery')
        identifier=pending.get('order_id');payload=pending.get('payload') or {}
        if not identifier:raise ValueError('Unknown acknowledgement remains retained; no resend')
        positions=ok(self.api.positions()).get('netPositions');orders=ok(self.api.orderbook()).get('orderBook')
        if not isinstance(positions,list) or not isinstance(orders,list):raise ValueError('Complete broker books required for reconciliation')
        rows=[r for r in orders if str(r.get('id'))==str(identifier)]
        if len(rows)!=1:raise ValueError('Direct retained order is not uniquely verified')
        row=rows[0]
        for key in ('symbol','qty','side','productType','orderTag'):
            if row.get(key)!=payload.get(key):raise ValueError('Direct retained order identity mismatch')
        quantity=payload['qty'];filled=row.get('filledQty',0);status=row.get('status')
        if isinstance(filled,bool) or not isinstance(filled,int) or not 0<=filled<=quantity:raise ValueError('Direct fill quantity is unknown')
        if status not in (1,2,5):raise ValueError('Direct order is not terminal; no duplicate order')
        symbol=payload['symbol']
        if any(r.get('symbol')==symbol and r.get('status') in (4,6) for r in orders):raise ValueError('Selected contract still has an open order')
        matching=[r for r in positions if r.get('symbol')==symbol and int(r.get('netQty',0))]
        if any(r.get('productType')!=self.product for r in matching):raise ValueError('Direct broker product differs from retained ownership')
        signed=sum(int(r['netQty']) for r in matching)
        intent=pending['intent'];p=intent['position'];entry=bool(ACTIONS[intent['action']][0])
        remaining=filled if entry else quantity-filled
        expected=remaining*(1 if p['side']=='LONG' else -1)
        if signed!=expected:raise ValueError('Direct signed quantity differs from reconciled fill')
        if status==2 and filled!=quantity:raise ValueError('Direct completed status has an incomplete fill')
        lot=self.master(symbol)['lot_size']
        if remaining%lot:raise ValueError('Residual quantity is not a whole broker lot; retained for recovery')
        self.state['position']=(dict(p,quantity=remaining,order_id=str(identifier),fill_price=row.get('tradedPrice')) if entry else dict(self.state.get('position') or p,quantity=remaining)) if remaining else None
        if not entry and remaining:
            self.state['retained_exit_failure']=dict(pending,stage='CANCELLED_WITHOUT_FILL' if filled==0 else 'PARTIAL_EXIT_REMAINS',filled_quantity=filled)
        elif not entry:self.state.pop('retained_exit_failure',None)
        receipt=dict(kind='DIRECT_ORDER_VERIFIED',action=intent,order_id=str(identifier),filled_quantity=filled,fill_price=row.get('tradedPrice') if filled else None,broker_quantity=signed,broker_flat=signed==0,checked_at=time.time(),orders_submitted=0)
        self.state.setdefault('reconciliations',[]).append(receipt)
        self.state['pending']=None;self.save();return receipt
    @coordinated_submit
    def submit(self,action,quote,now=None):
        if self.management_only and action.get('action','').startswith('OPEN_'):raise ValueError('Position-management worker cannot place new entries')
        if action.get('action') not in ACTIONS:raise ValueError('Unknown direct action')
        entry,side=ACTIONS[action['action']]
        from sector_heatmap.chart_trade_admission import entry_lock
        with entry_lock(self.broker,folder=self.account_folder) if self.live and entry else nullcontext():
            if self.live and entry:
                if self.account_folder is None:raise ValueError('Exact private account folder required for Live entry')
                from sector_heatmap.chart_trade_ownership import assert_no_chart_entry_conflict
                folder=Path(self.account_folder)
                assert_no_chart_entry_conflict(folder/'chart-trading.sqlite3',folder.name,self.broker)
            return self._submit(action,quote,entry,side,time.time() if now is None else now)
    def _submit(self,action,quote,entry,side,now):
        if self.state.get('pending'):raise ValueError('Pending or uncertain intent must be reconciled before another submission')
        p=action['position'];symbol=p['symbol'];meta=self.master(symbol)
        if p.get('execution_route')!='DIRECT' or p.get('underlying')!=symbol:raise ValueError('Direct execution must match selected underlying')
        if not quote or not 0<=now-quote.get('timestamp',0)<=5 or not isinstance(quote.get('ltp'),(int,float)) or not math.isfinite(quote['ltp']) or quote['ltp']<=0:raise ValueError('Fresh provider-time quote required')
        if meta.get('product_type') not in ('STOCK','FUTURE'):raise ValueError('Exact daily-master stock/future required')
        if meta['product_type']=='FUTURE' and float(meta.get('expiry_epoch',0))<=now:raise ValueError('Expired/missing future expiry')
        if meta['product_type']=='STOCK' and self.product not in ('CNC','INTRADAY'):raise ValueError('Cash stock requires CNC or INTRADAY product')
        if meta['product_type']=='FUTURE' and self.product=='CNC':raise ValueError('Future requires MARGIN or INTRADAY product')
        if meta['product_type']=='STOCK' and p['side']=='SHORT' and self.product!='INTRADAY':raise ValueError('Cash short requires INTRADAY product')
        lot=meta.get('lot_size');tick=meta.get('tick_size')
        if isinstance(lot,bool) or not isinstance(lot,int) or lot<1 or not isinstance(tick,(int,float)) or not math.isfinite(tick) or tick<=0:raise ValueError('Invalid daily lot/tick')
        own=self.state['position'];quantity=self.lots*lot
        if entry and own:raise ValueError('Already owns exposure')
        if not entry:
            if not own or own['symbol']!=symbol or own['side']!=p['side']:raise ValueError('No exact owned position to close')
            quantity=own['quantity']
        raw=quote['ltp']*(1.02 if side>0 else .98)
        price=float((Decimal(str(raw))/Decimal(str(tick))).to_integral_value(rounding=ROUND_CEILING if side>0 else ROUND_FLOOR)*Decimal(str(tick)))
        payload=dict(symbol=symbol,qty=quantity,type=2,side=side,productType=self.product,limitPrice=0,stopPrice=0,validity='DAY',disclosedQty=0,offlineOrder=False,stopLoss=0,takeProfit=0)
        key=hashlib.sha256(json.dumps([action['timestamp'],symbol,action['action'],p['entry_timestamp']],sort_keys=True).encode()).hexdigest();payload['orderTag']='nai'+key[:12]
        if key in self.state['seen']:raise ValueError('Duplicate intent blocked')
        if self.broker=='MOTILAL_OSWAL':payload=self.api.prepare_order(payload)
        if self.live:
            positions=ok(self.api.positions()).get('netPositions');orders=ok(self.api.orderbook()).get('orderBook')
            if not isinstance(positions,list) or not isinstance(orders,list):raise ValueError('Broker books unavailable')
            if any(r.get('symbol')==symbol and r.get('status') in (4,6) for r in orders):raise ValueError('Pending broker order blocks submission')
            matching=[r for r in positions if r.get('symbol')==symbol and int(r.get('netQty',0))]
            signed=sum(int(r['netQty']) for r in matching)
            expected=0 if entry else quantity*(1 if p['side']=='LONG' else -1)
            if signed!=expected or any(r.get('productType')!=self.product for r in matching):raise ValueError('Signed broker exposure differs from exact ownership')
            if entry:
                try:from .execution import available_funds
                except ImportError:from execution import available_funds
                available=available_funds(ok(self.api.funds()).get('fund_limit',[]),commodity=symbol.startswith('MCX:'))
                if available is None or not math.isfinite(float(available)):raise ValueError('Available funds unknown')
                if self.margin is None:raise ValueError('Broker margin validation unavailable')
                required=self.margin(payload)
                if not isinstance(required,(int,float)) or not math.isfinite(required) or required<0 or required>float(available):raise ValueError('Required margin unavailable or exceeds available funds')
        self.state['pending']=dict(key=key,payload=payload,intent=action,stage='PREPARED');self.state['seen'].append(key);self.save()
        if not self.live:
            self.state['position']=dict(p,quantity=quantity,fill_price=quote['ltp'],simulated=True) if entry else None
            self.state['pending']=None;self.save();return dict(dry_run=True,payload=payload,simulated_fill=quote['ltp'])
        try:
            if entry:
                from sector_heatmap.chart_trade_admission import mark_entry_attempt
                mark_entry_attempt(self.broker,folder=self.account_folder)
            reply=self.api.place_order(data=payload)
        except Exception as error:
            if self.broker=='MOTILAL_OSWAL' and self.state.get('pending',{}).get('stage')=='PREPARED':
                self.state.setdefault('failed_intents',[]).append(dict(self.state['pending'],stage='NOT_SUBMITTED',notice=str(error)))
                self.state['failed_intents']=self.state['failed_intents'][-200:]
                self.state['pending']=None;self.save();raise
            self.state['pending']['stage']='UNCERTAIN';self.save();raise RuntimeError('Submission uncertain; retained intent, no retry')
        if not isinstance(reply,dict) or reply.get('s')!='ok' or not reply.get('id'):raise RuntimeError('Acknowledgement unconfirmed; intent retained')
        order_id=str(reply['id']);self.state['pending'].update(order_id=order_id,stage='SUBMITTED');self.save()
        deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            time.sleep(1);rows=ok(self.api.orderbook()).get('orderBook',[])
            row=next((r for r in rows if str(r.get('id'))==order_id),None)
            if row and row.get('status')==2 and int(row.get('filledQty',0))==quantity:
                if not entry:
                    self.state['pending']['stage']='FILLED_AWAITING_FLAT';self.save()
                    positions=ok(self.api.positions()).get('netPositions');orders=ok(self.api.orderbook()).get('orderBook')
                    if not isinstance(positions,list) or not isinstance(orders,list) or any(r.get('symbol')==symbol and int(r.get('netQty',0)) for r in positions) or any(r.get('symbol')==symbol and r.get('status') in (4,6) for r in orders):
                        raise RuntimeError('Direct exit fill acknowledged but broker flat state unconfirmed; no reversal or duplicate exit')
                self.state['position']=dict(p,quantity=quantity,order_id=order_id,fill_price=row.get('tradedPrice')) if entry else None
                self.state['pending']=None;self.save();return dict(dry_run=False,order_id=order_id,filled_quantity=quantity,fill_price=row.get('tradedPrice'))
            if row and (int(row.get('filledQty',0))>0 or row.get('status') in (1,5)):break
        self.state['pending']['stage']='UNRESOLVED_FILL';self.save();raise RuntimeError('Unfilled/partial/unknown outcome retained; no retry or new entry')
