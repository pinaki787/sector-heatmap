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
    def __init__(self,api,account,state_dir,*,live=False,lots=None,product=None,master=None,account_folder=None,margin=None):
        if isinstance(lots,bool) or not isinstance(lots,int) or lots<1:raise ValueError('Explicit whole lots/shares required')
        if product not in ('MARGIN','INTRADAY','CNC'):raise ValueError('Explicit FYERS product required')
        self.api,self.live,self.lots,self.product,self.master,self.account_folder,self.margin=api,live,lots,product,master,account_folder,margin
        directory=Path(state_dir)/account;directory.mkdir(parents=True,exist_ok=True)
        self.lock=(directory/'execution.lock').open('a');fcntl.flock(self.lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        self.path=directory/('direct-live.json' if live else 'direct-paper.json')
        self.state=json.loads(self.path.read_text()) if self.path.exists() else dict(position=None,pending=None,seen=[])
        other=directory/('live.json' if live else 'paper.json')
        if other.exists():
            retained=json.loads(other.read_text())
            if retained.get('position') or retained.get('pending'):
                self.close();raise ValueError('Another AI route retains owned exposure or pending intent; reconcile before switching routes')

        if self.state.get('position') or self.state.get('pending'):self.close();raise ValueError('Owned position or uncertain intent requires reconciliation; no automatic restart')
    def close(self):self.lock.close()
    def save(self):atomic(self.path,self.state)
    def submit(self,action,quote,now=None):
        if action.get('action') not in ACTIONS:raise ValueError('Unknown direct action')
        entry,side=ACTIONS[action['action']]
        from sector_heatmap.chart_trade_admission import entry_lock
        with entry_lock('FYERS',folder=self.account_folder) if self.live and entry else nullcontext():
            if self.live and entry:
                if self.account_folder is None:raise ValueError('Exact private account folder required for Live entry')
                from sector_heatmap.chart_trade_ownership import assert_no_chart_entry_conflict
                folder=Path(self.account_folder)
                assert_no_chart_entry_conflict(folder/'chart-trading.sqlite3',folder.name,'FYERS')
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
        payload=dict(symbol=symbol,qty=quantity,type=1,side=side,productType=self.product,limitPrice=price,stopPrice=0,validity='DAY',disclosedQty=0,offlineOrder=False,stopLoss=0,takeProfit=0)
        key=hashlib.sha256(json.dumps([action['timestamp'],symbol,action['action'],p['entry_timestamp']],sort_keys=True).encode()).hexdigest();payload['orderTag']='nai'+key[:12]
        if key in self.state['seen']:raise ValueError('Duplicate intent blocked')
        if self.live:
            positions=ok(self.api.positions()).get('netPositions');orders=ok(self.api.orderbook()).get('orderBook')
            if not isinstance(positions,list) or not isinstance(orders,list):raise ValueError('Broker books unavailable')
            if any(r.get('symbol')==symbol and r.get('status') in (1,4,6) for r in orders):raise ValueError('Pending broker order blocks submission')
            matching=[r for r in positions if r.get('symbol')==symbol and int(r.get('netQty',0))]
            signed=sum(int(r['netQty']) for r in matching)
            expected=0 if entry else quantity*(1 if p['side']=='LONG' else -1)
            if signed!=expected or any(r.get('productType')!=self.product for r in matching):raise ValueError('Signed broker exposure differs from exact ownership')
            if entry:
                available=next((r.get('equityAmount') for r in ok(self.api.funds()).get('fund_limit',[]) if r.get('id')==10),None)
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
                mark_entry_attempt('FYERS',folder=self.account_folder)
            reply=self.api.place_order(data=payload)
        except Exception:
            self.state['pending']['stage']='UNCERTAIN';self.save();raise RuntimeError('Submission uncertain; retained intent, no retry')
        if not isinstance(reply,dict) or reply.get('s')!='ok' or not reply.get('id'):raise RuntimeError('Acknowledgement unconfirmed; intent retained')
        order_id=str(reply['id']);self.state['pending'].update(order_id=order_id,stage='SUBMITTED');self.save()
        deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            time.sleep(1);rows=ok(self.api.orderbook()).get('orderBook',[])
            row=next((r for r in rows if str(r.get('id'))==order_id),None)
            if row and row.get('status')==2 and int(row.get('filledQty',0))==quantity:
                self.state['position']=dict(p,quantity=quantity,order_id=order_id,fill_price=row.get('tradedPrice')) if entry else None
                self.state['pending']=None;self.save();return dict(dry_run=False,order_id=order_id,filled_quantity=quantity,fill_price=row.get('tradedPrice'))
            if row and (int(row.get('filledQty',0))>0 or row.get('status') in (1,5)):break
        self.state['pending']['stage']='UNRESOLVED_FILL';self.save();raise RuntimeError('Unfilled/partial/unknown outcome retained; no retry or new entry')
