"""Isolated account-scoped write-ahead order journal; never retries a submission."""
import fcntl,hashlib,json,math,os,time
from contextlib import nullcontext
from pathlib import Path
from decimal import Decimal,ROUND_CEILING,ROUND_FLOOR
try:from .run import atomic,ok
except ImportError:from run import atomic,ok
OPEN_STATUSES={4,6}
def available_funds(rows,*,commodity=False):
    # FYERS supports a shared NSE/MCX cash pool. Do not add the two columns
    # or count pledged equity collateral as commodity cash.
    def amount(row,key):
        v=row.get(key)
        return float(v) if not isinstance(v,bool) and isinstance(v,(int,float)) and math.isfinite(v) and v>=0 else None
    available=next((r for r in rows if r.get('id')==10 or str(r.get('title','')).lower()=='available balance'),{})
    equity=amount(available,'equityAmount')
    if not commodity:return equity
    dedicated=amount(available,'commodityAmount')
    clear=next((r for r in rows if r.get('id')==3 or str(r.get('title','')).lower()=='clear balance'),{})
    cash=amount(clear,'equityAmount')
    shared=min(equity,cash) if equity is not None and cash is not None else None
    values=[v for v in (dedicated,shared) if v is not None]
    return max(values) if values else None

class Execution:
    def __init__(self,api,account,state_dir,live=False,lots=None,product=None,master=None,account_folder=None,attachment_config=None,management_only=False):
        self.management_only=management_only
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
        other=directory/('direct-live.json' if live else 'direct-paper.json')
        if other.exists():
            retained=json.loads(other.read_text())
            if any(retained.get(k) for k in ('position','pending','detached_position','stop_verification_position')):
                self.close();raise ValueError('Another AI route retains owned exposure or pending intent; reconcile before switching routes')

        if management_only:return
        if any(slot.get('position') or slot.get('pending') for slot in self.state.get('closing_legs',{}).values()):
            self.close();raise ValueError('Previous option legs retain exposure or orders; use the captured Stop recovery before a new run')
        if self.state.get('detached_position') or self.state.get('stop_verification_position'):self.lock.close();raise ValueError('Retained position control requires Attach or Stop; new entries blocked')
        if self.state.get('pending'):self.lock.close();raise ValueError('Uncertain/pending submission retained; reconcile manually before restart; no resend')
        if self.state.get('position') and attachment_config:
            try:
                try:from .attachment import verify_position
                except ImportError:from attachment import verify_position
                checked=verify_position(self.api,attachment_config,attachment_config['attach_position'],self.master)
                own=self.state['position']
                if own.get('symbol')!=checked['symbol'] or own.get('quantity')!=checked['quantity']:raise ValueError('Retained owned position differs from explicit attachment')
                profile=ok(self.api.get_profile());identity=(profile.get('data') or {}).get('fy_id')
                if not identity or hashlib.sha256(str(identity).encode()).hexdigest()!=account:raise ValueError('Attachment account identity mismatch')
            except Exception:
                self.lock.close();raise
        elif self.state.get('position'):
            if not self.live:
                self.lock.close();raise ValueError('Existing Paper position retained; reconcile before restart')
            try:
                profile=ok(self.api.get_profile());identity=(profile.get('data') or {}).get('fy_id')
                if not identity or hashlib.sha256(str(identity).encode()).hexdigest()!=account:
                    raise ValueError('Account identity mismatch during stopped-position reconciliation')
                positions,orders=self.exposure()
                own=self.state['position'];symbol=own['symbol']
                matching=[r for r in positions if r.get('symbol')==symbol and r.get('productType')==self.product]
                if not matching or any(int(r.get('netQty',0))!=0 for r in matching):
                    raise ValueError('Broker still has exposure or has not confirmed the owned contract flat')
                if any(r.get('symbol')==symbol and r.get('status') in OPEN_STATUSES for r in orders):
                    raise ValueError('Broker retains an open order for the owned contract')
                audit=dict(kind='EXTERNAL_FLAT_CONFIRMED',checked_at=time.time(),position=own,product=self.product,
                           broker_positions=matching,orders_submitted=0)
                self.state.setdefault('reconciliations',[]).append(audit)
                self.state['position']=None;self.save()
            except Exception:
                self.lock.close();raise
    def adopt_existing(self,position,config):
        if not self.live or self.state.get('pending'):raise ValueError('Attachment requires Live ownership without a pending intent')
        try:from .attachment import verify_position
        except ImportError:from attachment import verify_position
        checked=verify_position(self.api,config,config['attach_position'],self.master)
        if position.get('symbol')!=checked['symbol'] or position.get('quantity')!=checked['quantity']:raise ValueError('Attachment changed before journal commit')
        previous=self.state.get('position')
        if previous and (previous.get('symbol')!=position.get('symbol') or previous.get('quantity')!=position.get('quantity')):raise ValueError('A different position is already owned')
        self.state.setdefault('attachments',[]).append(dict(position=position,previous_position=previous,checked_at=time.time(),orders_submitted=0))
        self.state['position']=dict(position);self.save()
    def close(self):
        self.lock.close()
    def save(self):atomic(self.path,self.state)
    def exposure(self):
        positions=ok(self.api.positions()).get('netPositions')
        orders=ok(self.api.orderbook()).get('orderBook')
        if not isinstance(positions,list) or not isinstance(orders,list):raise ValueError('Unknown broker positions/orders response')
        return positions,orders
    def reconcile_pending(self):
        pending=self.state.get('pending')
        if not pending:return
        payload=pending.get('payload') or {};identifier=pending.get('order_id')
        if not identifier:raise ValueError('Unknown acknowledgement retained; broker order identity requires recovery')
        positions,orders=self.exposure()
        rows=[r for r in orders if str(r.get('id'))==str(identifier)]
        if len(rows)!=1:raise ValueError('Retained order is not uniquely verified')
        row=rows[0]
        for key in ('symbol','qty','side','productType','orderTag'):
            if row.get(key)!=payload.get(key):raise ValueError('Retained order identity differs from broker')
        quantity=payload['qty'];filled=int(row.get('filledQty',0));status=row.get('status')
        if not 0<=filled<=quantity:raise ValueError('Invalid broker fill quantity')
        if status in OPEN_STATUSES:raise ValueError('Broker order remains open; no duplicate order')
        current=sum(int(r.get('netQty',0)) for r in positions if r.get('symbol')==payload['symbol'] and r.get('productType')==self.product)
        if any(r.get('symbol')==payload['symbol'] and r.get('status') in OPEN_STATUSES for r in orders):raise ValueError('Selected contract has an open order')
        intent=pending['intent'];entry=payload['side']==1
        if filled==quantity and status==2 and current==(quantity if entry else 0):
            if entry:self.state['position']=dict(intent['position'],quantity=quantity,order_id=str(identifier),fill_price=row.get('tradedPrice'))
            else:self.state['position']=None
        elif filled==0 and status in (1,5) and current==(0 if entry else (self.state.get('position') or {}).get('quantity')):
            pass
        else:raise ValueError('Partial or mismatched fill/exposure retained for recovery; no automatic resend')
        self.state.setdefault('reconciliations',[]).append(dict(kind='PENDING_ORDER_VERIFIED',order_id=str(identifier),filled_quantity=filled,broker_quantity=current,checked_at=time.time(),orders_submitted=0))
        receipt=dict(action=intent,order_id=str(identifier),filled_quantity=filled,fill_price=row.get('tradedPrice') if filled else None,broker_flat=current==0,checked_at=time.time(),orders_submitted=0)
        if filled:
            try:from .option_legs import capture_fill
            except ImportError:from option_legs import capture_fill
            capture_fill(self.state,intent,dict(order_id=str(identifier),filled_quantity=filled,fill_price=row.get('tradedPrice')),receipt['checked_at'],pending.get('key'))
        elif not entry and self.state.get('position'):self.state['retained_exit_failure']=dict(pending,stage='CANCELLED_WITHOUT_FILL')
        self.state['pending']=None;self.save();return receipt
    def submit(self,action,quote,now=None):
        if self.management_only and action.get('action')=='BUY':raise ValueError('Position-management worker cannot place new entries')
        from sector_heatmap.chart_trade_admission import entry_lock
        lock=entry_lock('FYERS',folder=self.account_folder) if self.live and action['action']=='BUY' else nullcontext()
        with lock:
            if self.live and action['action']=='BUY':
                if self.account_folder is None:raise ValueError('Exact private account folder required for Live entry')
                from sector_heatmap.chart_trade_ownership import assert_no_chart_entry_conflict
                folder=Path(self.account_folder)
                assert_no_chart_entry_conflict(folder/'chart-trading.sqlite3',folder.name,'FYERS')
            return self._submit(action,quote,now)
    def _submit(self,action,quote,now=None):
        now=time.time() if now is None else now
        if self.state.get('pending'):raise ValueError('Pending or uncertain intent must be reconciled before another submission')
        p=action['position'];symbol=p['symbol'];buy=action['action']=='BUY'
        if action['action'] not in ('BUY','SELL'):raise ValueError('Unknown order action')
        if not quote or not 0<=now-quote['timestamp']<=5:raise ValueError('Fresh provider-time quote required')
        if not math.isfinite(quote['ltp']) or quote['ltp']<=0:raise ValueError('Invalid LTP')
        meta=self.master(symbol) # current daily master before EVERY entry or exit
        lot=meta['lot_size'];quantity=lot*self.lots
        if meta['option_type']!=p['option_type'] or not symbol.startswith(('NSE:','BSE:','MCX:')) or str(meta['expiry_epoch'])!=str(p['expiry']):
            raise ValueError('Master/contract mismatch')
        if p.get('underlying_asset') and meta.get('underlying_asset')!=p['underlying_asset']:raise ValueError('Selected underlying/master mismatch')
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
            funds=ok(self.api.funds()).get('fund_limit',[])
            available=available_funds(funds,commodity=symbol.startswith('MCX:'))
            if buy:
                required=price*quantity
                if symbol.startswith('MCX:'):
                    try:from .markets import margin_reader
                    except ImportError:from markets import margin_reader
                    required=margin_reader(self.api)(payload)
                if available is None or not math.isfinite(float(available)) or float(available)<required:raise ValueError('Insufficient/unavailable funds')
        self.state['pending']=dict(key=key,payload=payload,intent=action,stage='PREPARED')
        self.state['seen'].append(key);self.save() # durable BEFORE request; crash => no resend
        if not self.live:
            self.state['position']=dict(p,quantity=quantity,fill_price=quote['ltp'],simulated=True) if buy else None
            result=dict(dry_run=True,payload=payload,simulated_fill=quote['ltp'],filled_quantity=quantity)
            try:from .option_legs import capture_fill
            except ImportError:from option_legs import capture_fill
            capture_fill(self.state,action,result,now,key)
            self.state['pending']=None;self.save()
            return result
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
        deadline=time.monotonic()+getattr(self,'confirmation_timeout',30)
        while time.monotonic()<deadline:
            time.sleep(1)
            rows=ok(self.api.orderbook()).get('orderBook',[])
            row=next((r for r in rows if str(r.get('id'))==order_id),None)
            if row and row.get('status')==2 and int(row.get('filledQty',0))==quantity:
                if not buy:
                    # Filled order acknowledgement is not proof of account exposure.
                    self.state['pending'].update(stage='FILLED_AWAITING_FLAT',filled_quantity=quantity)
                    self.save()
                    positions,orders=self.exposure()
                    current=sum(int(r.get('netQty',0)) for r in positions if r.get('symbol')==symbol and r.get('productType')==self.product)
                    if current or any(r.get('symbol')==symbol and r.get('status') in OPEN_STATUSES for r in orders):
                        raise RuntimeError('Exit fill acknowledged but broker flat state is not confirmed; no new entry or duplicate exit')
                self.state['position']=dict(p,quantity=quantity,order_id=order_id,fill_price=row.get('tradedPrice')) if buy else None
                result=dict(dry_run=False,order_id=order_id,filled_quantity=quantity,fill_price=row.get('tradedPrice'))
                try:from .option_legs import capture_fill
                except ImportError:from option_legs import capture_fill
                capture_fill(self.state,action,result,time.time(),key)
                self.state['pending']=None;self.save()
                return result
            if row and (int(row.get('filledQty',0))>0 or row.get('status') in (1,5)):
                break
        self.state['pending']['stage']='UNRESOLVED_FILL';self.save()
        raise RuntimeError('Unfilled/partial/unknown order retained; no cancellation, replacement, retry or new entry')
