"""Isolated account-scoped write-ahead order journal; never retries a submission."""
import fcntl,hashlib,json,math,os,time
from contextlib import nullcontext
from pathlib import Path
from decimal import Decimal,ROUND_CEILING,ROUND_FLOOR
try:from .run import atomic,ok
except ImportError:from run import atomic,ok
OPEN_STATUSES={1,4,6}
class Execution:
    def __init__(self,api,account,state_dir,live=False,lots=None,product=None,master=None,account_folder=None):
        self.account_folder=account_folder
        self.api,self.live,self.lots,self.product,self.master=api,live,lots,product,master
        if isinstance(lots,bool) or not isinstance(lots,int) or lots<1:raise ValueError('Explicit positive whole lots required')
        if product not in ('MARGIN','INTRADAY'):raise ValueError('Explicit FYERS product required')
        directory=Path(state_dir)/account
        directory.mkdir(parents=True,exist_ok=True)
        self.lock=(directory/'execution.lock').open('a')
        fcntl.flock(self.lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        self.path=directory/('live.json' if live else 'paper.json')
        self.state=json.loads(self.path.read_text()) if self.path.exists() else dict(position=None,pending=None,seen=[])
        if self.state.get('pending'):self.lock.close();raise ValueError('Uncertain/pending submission retained; reconcile manually before restart; no resend')
        if self.state.get('position'):self.lock.close();raise ValueError('Existing strategy position retained; read-only reconciliation required before restart')
    def close(self):
        self.lock.close()
    def save(self):atomic(self.path,self.state)
    def exposure(self):
        positions=ok(self.api.positions()).get('netPositions')
        orders=ok(self.api.orderbook()).get('orderBook')
        if not isinstance(positions,list) or not isinstance(orders,list):raise ValueError('Unknown broker positions/orders response')
        return positions,orders
    def submit(self,action,quote,now=None):
        from sector_heatmap.chart_trade_admission import entry_lock
        lock=entry_lock('FYERS',folder=self.account_folder) if self.live and action['action']=='BUY' else nullcontext()
        with lock:return self._submit(action,quote,now)
    def _submit(self,action,quote,now=None):
        now=time.time() if now is None else now
        p=action['position'];symbol=p['symbol'];buy=action['action']=='BUY'
        if action['action'] not in ('BUY','SELL'):raise ValueError('Unknown order action')
        if not quote or not 0<=now-quote['timestamp']<=5:raise ValueError('Fresh provider-time quote required')
        if not math.isfinite(quote['ltp']) or quote['ltp']<=0:raise ValueError('Invalid LTP')
        meta=self.master(symbol) # current daily master before EVERY entry or exit
        lot=meta['lot_size'];quantity=lot*self.lots
        if meta['option_type']!=p['option_type'] or not symbol.startswith('NSE:NIFTY') or str(meta['expiry_epoch'])!=str(p['expiry']):
            raise ValueError('Master/contract mismatch')
        if float(meta['expiry_epoch'])<=now:raise ValueError('Expired contract')
        if buy and self.state['position']:raise ValueError('Strategy already owns exposure')
        if not buy:
            own=self.state['position']
            if not own or own['symbol']!=symbol:raise ValueError('No exact strategy-owned position to exit')
            quantity=own['quantity']
        if not isinstance(lot,int) or lot<1 or quantity%lot:raise ValueError('Invalid lot quantity')
        tick=float(meta['tick_size'])
        if not math.isfinite(tick) or tick<=0:raise ValueError('Invalid master tick')
        # Explicit limit slippage avoids unlimited market-entry price. No automatic repricing.
        raw=quote['ltp']*(1.02 if buy else .98)
        price=float((Decimal(str(raw))/Decimal(str(tick))).to_integral_value(rounding=ROUND_CEILING if buy else ROUND_FLOOR)*Decimal(str(tick)))
        if price<=0:raise ValueError('Nonpositive limit')
        key=hashlib.sha256(json.dumps([action['timestamp'],symbol,action['action'],p['entry_timestamp']],sort_keys=True).encode()).hexdigest()
        if key in self.state['seen']:raise ValueError('Duplicate strategy intent blocked')
        payload=dict(symbol=symbol,qty=quantity,type=1,side=1 if buy else -1,productType=self.product,limitPrice=price,stopPrice=0,validity='DAY',disclosedQty=0,offlineOrder=False,stopLoss=0,takeProfit=0,orderTag='nai'+key[:12])
        if self.live:
            positions,orders=self.exposure()
            pending=[o for o in orders if o.get('symbol')==symbol and o.get('status') in OPEN_STATUSES]
            current=sum(int(r.get('netQty',0)) for r in positions if r.get('symbol')==symbol and r.get('productType')==self.product)
            if pending or (current!=0 if buy else current!=quantity):raise ValueError('Broker exposure/open-order reconciliation failed')
            # Prevent other Nifty-option exposure from being mistaken for strategy ownership.
            if buy and (any(int(r.get('netQty',0)) for r in positions if str(r.get('symbol','')).startswith('NSE:NIFTY')) or any(o.get('status') in OPEN_STATUSES for o in orders if str(o.get('symbol','')).startswith('NSE:NIFTY'))):raise ValueError('Existing account Nifty exposure or pending order')
            funds=ok(self.api.funds()).get('fund_limit',[])
            available=next((r.get('equityAmount') for r in funds if r.get('id')==10),None)
            if buy and (available is None or float(available)<price*quantity):raise ValueError('Insufficient/unavailable funds')
        self.state['pending']=dict(key=key,payload=payload,intent=action,stage='PREPARED')
        self.state['seen'].append(key);self.save() # durable BEFORE request; crash => no resend
        if not self.live:
            self.state['position']=dict(p,quantity=quantity,fill_price=quote['ltp'],simulated=True) if buy else None
            self.state['pending']=None;self.save()
            return dict(dry_run=True,payload=payload,simulated_fill=quote['ltp'])
        try:
            if buy:
                from sector_heatmap.chart_trade_admission import mark_entry_attempt
                mark_entry_attempt('FYERS',folder=self.account_folder)
            reply=self.api.place_order(data=payload)
        except Exception:
            self.state['pending']['stage']='UNCERTAIN';self.save()
            raise RuntimeError('Submission uncertain. Retained journal; never retry')
        if not isinstance(reply,dict) or reply.get('s')!='ok' or not reply.get('id'):
            self.state['pending']['stage']='REJECTED_OR_UNCERTAIN';self.save()
            raise RuntimeError('Submission not confirmed. Retained intent; no retry')
        order_id=str(reply['id']);self.state['pending'].update(order_id=order_id,stage='SUBMITTED');self.save()
        deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            time.sleep(1)
            rows=ok(self.api.orderbook()).get('orderBook',[])
            row=next((r for r in rows if str(r.get('id'))==order_id),None)
            if row and row.get('status')==2 and int(row.get('filledQty',0))==quantity:
                self.state['position']=dict(p,quantity=quantity,order_id=order_id,fill_price=row.get('tradedPrice')) if buy else None
                self.state['pending']=None;self.save()
                return dict(dry_run=False,order_id=order_id,filled_quantity=quantity)
            if row and (int(row.get('filledQty',0))>0 or row.get('status') in (1,5)):
                break
        self.state['pending']['stage']='UNRESOLVED_FILL';self.save()
        raise RuntimeError('Unfilled/partial/unknown order retained; no cancellation, replacement, retry or new entry')
