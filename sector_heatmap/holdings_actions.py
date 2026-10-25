"""Explicit reviewed Dhan holding exits; never an entry or automatic trailing runner."""
from copy import deepcopy
from datetime import datetime,timezone
from decimal import Decimal,ROUND_CEILING,ROUND_FLOOR
from pathlib import Path
import hashlib,json,secrets,threading,time
from .dhan_execution import DhanAPIError,fresh_quote_snapshot
from .config import _atomic_private_write
from .market_calendar import market_session
from .holdings_analysis import IST

TERMINAL={'TRADED','CANCELLED','REJECTED','EXPIRED'}
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()
def decimal(value):
    if isinstance(value,bool):raise ValueError('Invalid numeric action value.')
    try:v=Decimal(str(value))
    except Exception:raise ValueError('A valid numeric action value is required.') from None
    if not v.is_finite():raise ValueError('A finite action value is required.')
    return v
def grid(value,tick,rounding=ROUND_FLOOR):
    return float((decimal(value)/tick).to_integral_value(rounding=rounding)*tick)

class HoldingActions:
    def __init__(self,execution,clock=time.time):
        self.execution=execution;self.clock=clock;self.lock=threading.RLock();self.previews={}
    def _plan(self,report,row,payload,managed=None,monitor_path=None):
        e=self.execution;c=e._client();now=self.clock()
        if report.get('broker')!='DHAN' or report.get('account_id')!=e.account['id']:
            raise PermissionError('Recommendation belongs to another broker account.')
        stamp=datetime.fromisoformat(report['as_of']).timestamp()
        if not 0<=now-stamp<=600:raise ValueError('Recommendation is older than ten minutes. Run a fresh portfolio review.')
        if row.get('kind')!='DELIVERY_EQUITY' or row.get('action') not in ('TRAIL','EXIT','BOOK_PROFIT'):
            raise ValueError('This recommendation has no executable holding action.')
        meta=row.get('native_identity') or {}
        sid=str(meta.get('securityId') or '');segment=meta.get('exchangeSegment')
        if segment not in ('NSE_EQ','BSE_EQ'):raise ValueError('Only verified cash-equity holdings are supported.')
        master=e.master.resolve(dict(security_id=sid,exchange_segment=segment),datetime.fromtimestamp(now,IST))
        expected=segment.split('_')[0]+':'+master['symbol']+'-EQ'
        if row.get('symbol')!=expected:raise ValueError('Current native master differs from the reviewed holding.')
        tick=decimal(master['tick_size'])
        profile=c.request('GET','/profile')
        if str(profile.get('dhanClientId'))!=str(c.client_id):raise PermissionError('Broker token belongs to another account.')
        books={}
        for name,path in (('holdings','/holdings'),('positions','/positions'),('orders','/orders'),('forever','/forever/orders'),('super','/super/orders')):
            values=c.request('GET',path)
            if not isinstance(values,list) or any(not isinstance(r,dict) or str(r.get('dhanClientId',c.client_id))!=str(c.client_id) for r in values):
                raise PermissionError('Complete broker-owned holdings and protection evidence is required.')
            books[name]=values
        holdings=[h for h in books['holdings'] if str(h.get('securityId'))==sid and str(h.get('tradingSymbol','')).upper()==master['symbol'].upper() and h.get('exchange') in ('ALL',segment.split('_')[0])]
        if len(holdings)!=1:raise ValueError('Holding identity changed or is ambiguous; analyse again.')
        h=holdings[0]
        if decimal(h.get('totalQty'))!=decimal(row['quantity']) or decimal(h.get('avgCostPrice'))!=decimal(row['average_price']):
            raise ValueError('Holding quantity or acquisition cost changed; analyse again.')
        funded=decimal(h.get('mtf_qty') or 0)+decimal(h.get('mtf_t1_qty') or 0)
        product='MTF' if row.get('holding_type')=='MTF funded equity' else 'CNC'
        if product=='MTF' and funded!=decimal(h['totalQty']):raise ValueError('Mixed funded/demat quantity needs separate broker review.')
        if product=='CNC' and funded:raise ValueError('Funding product changed; analyse again.')
        ddpi=str(profile.get('ddpi') or '').upper()
        if product=='CNC' and ddpi not in ('TRUE','1','ACTIVE','ENABLED','Y'):
            raise ValueError('Delivery selling needs verified DDPI/eDIS authority. Complete this action in Dhan.')
        qty=decimal(payload.get('quantity',row['quantity']))
        available=min(decimal(h.get('availableQty',0)),decimal(h['totalQty']))
        if qty<=0 or qty!=int(qty) or qty>available:raise ValueError('Quantity exceeds the current available holding.')
        if row['action']=='TRAIL' and qty!=decimal(row['quantity']):raise ValueError('Protect the full reviewed quantity; partial protection is not this recommendation.')
        related=lambda r:str(r.get('securityId'))==sid and r.get('exchangeSegment')==segment
        owned_id=str((managed or {}).get('order_id') or '')
        owned_rows=[r for r in books['forever'] if str(r.get('orderId'))==owned_id] if owned_id else []
        if owned_id:
            if len(owned_rows)!=1:raise ValueError('The exact managed Forever stop is missing or ambiguous.')
            owned=owned_rows[0]
            if not related(owned) or owned.get('transactionType')!='SELL' or owned.get('productType')!=product or decimal(owned.get('quantity'))!=qty:
                raise ValueError('Managed stop instrument, side, product or quantity changed.')
            if owned.get('orderStatus') not in ('PENDING','CONFIRM') or (owned.get('orderFlag') or owned.get('orderType'))!='SINGLE':
                raise ValueError('Managed stop is no longer an active SINGLE Forever order.')
            for field in ('triggerPrice','price'):
                if decimal(owned.get(field))!=decimal(managed['ticket'][field]):raise ValueError('Broker stop was changed externally. Monitoring needs review.')
            if owned.get('correlationId') and owned['correlationId']!=managed.get('correlation_id'):
                raise ValueError('Managed stop correlation identity changed.')
        for name in ('orders','forever','super'):
            for r in books[name]:
                if name=='forever' and owned_id and str(r.get('orderId'))==owned_id:continue
                if related(r) and str(r.get('orderStatus')) not in TERMINAL:
                    raise ValueError('An existing or uncertain order/protective plan already covers this instrument. Reconcile it in Dhan before creating another; existing stops are never loosened or duplicated.')
        if any(related(r) and decimal(r.get('netQty',0))!=0 for r in books['positions']):
            raise ValueError('An open trading position overlaps this holding; reconcile product ownership in Dhan first.')
        # Any active strategy in this account blocks unmanaged holding exits.
        from .service_restart import stopped_runtime
        if monitor_path or (managed and managed.get('state_path')):
            from .service_restart import runtime_states
            own=Path(monitor_path or managed['state_path']).resolve()
            for path in runtime_states(e.folder/'source'):
                if path.resolve()==own:continue
                state=json.loads(path.read_text())
                if path.parent.parent.name=='holding-trails' and state.get('security_id')!=sid:continue
                if any(state.get(k) for k in ('running','accepting_entries','position','positions','pending','active','loop_running')):
                    raise ValueError('Another strategy or monitor is active in this account. Reconcile ownership before trailing.')
        else:stopped_runtime(e.folder/'source')
        for folder in ('dhan-orders','dhan-strategy-intents','holding-actions'):
            for path in (e.folder/folder).glob('*.json'):
                saved=json.loads(path.read_text())
                if owned_id and str(saved.get('order_id'))==owned_id and saved.get('status') not in ('UNKNOWN','SUBMITTING'):continue
                if saved.get('status') in ('UNKNOWN','SUBMITTING','ACKNOWLEDGED','TRANSIT','PENDING','PART_TRADED','CONFIRM'):
                    ticket=saved.get('ticket') or {}
                    if (str(ticket.get('securityId'))==sid and ticket.get('exchangeSegment')==segment) or saved.get('status') in ('UNKNOWN','SUBMITTING'):
                        raise ValueError('A prior submission needs reconciliation; a duplicate action cannot be prepared.')
        quote,received=fresh_quote_snapshot(c,segment,sid,clock=self.clock)
        price=decimal(quote.get('last_price'))
        if price<=0:raise ValueError('A positive current broker quote is required.')
        ticket=dict(dhanClientId=c.client_id,transactionType='SELL',exchangeSegment=segment,productType=product,
                    orderType='LIMIT',validity='DAY',securityId=sid,quantity=int(qty),disclosedQuantity=0)
        if row['action']=='TRAIL':
            trigger=grid(max(decimal(row['candidate_stop']),decimal(managed['ticket']['triggerPrice'])) if managed else row['candidate_stop'],tick,ROUND_CEILING)
            if trigger<=0 or decimal(trigger)>=price:raise ValueError('Candidate stop is at/above the current market. Analyse again; no immediate sell was substituted.')
            default_limit=managed['ticket']['price'] if managed and decimal(trigger)==decimal(managed['ticket']['triggerPrice']) else decimal(trigger)*Decimal('0.995')
            limit=grid(payload.get('limit_price',default_limit),tick)
            if limit<=0 or limit>trigger or decimal(limit)<decimal(trigger)*Decimal('0.98'):raise ValueError('Protective sell limit must be below/equal to the trigger and within 2%.')
            ticket.update(orderFlag='SINGLE',triggerPrice=trigger,price=limit)
            endpoint='/forever/orders'
            description='Create a fixed GTT/Forever protective SELL stop. This does not run an automatic trailing strategy.'
        else:
            if market_session(datetime.fromtimestamp(now,IST))['status']!='OPEN':raise ValueError('Immediate holding exits require the regular exchange session. No after-market order is substituted.')
            try:bid=decimal(quote['depth']['buy'][0]['price'])
            except Exception:raise ValueError('Executable bid depth is unavailable.') from None
            limit=grid(payload.get('limit_price',bid),tick)
            if limit<=0 or abs(decimal(limit)/price-1)>Decimal('0.02'):raise ValueError('Exit limit must be within 2% of the latest broker price.')
            ticket.update(triggerPrice=0,price=limit,afterMarketOrder=False)
            endpoint='/orders';description='Submit a fixed-quantity LIMIT SELL exit; a limit order may remain unfilled.'
        snapshot=dict(managed_order_id=owned_id,managed_stop=(managed or {}).get('ticket'),holding={k:h.get(k) for k in ('totalQty','availableQty','avgCostPrice','mtf_qty','mtf_t1_qty','isin')},product=product)
        return dict(broker='DHAN',account_id=e.account['id'],symbol=row['symbol'],action=row['action'],ticket=ticket,
                    endpoint=endpoint,state_signature=digest(snapshot),reference_price=float(price),quote_received_at=received,
                    description=description,live_submission_enabled=bool(e.account.get('live_enabled')) and bool(e.execution_allowed()),
                    warnings=['A fixed protective stop may fail to fill after a gap.','Broker acknowledgement is not a fill or guaranteed protection.',
                              'Existing orders and strategy ownership are checked again at submission.'])
    def prepare(self,report,row,payload):
        with self.lock:
            plan=self._plan(report,row,payload)
            pid='HOLD-'+secrets.token_hex(8).upper()
            plan.update(preview_id=pid,confirmation_phrase='CONFIRM '+pid,expires_at=self.clock()+120)
            self.previews={k:v for k,v in self.previews.items() if v['plan']['expires_at']>self.clock()}
            self.previews[pid]=dict(plan=deepcopy(plan),report=deepcopy(report),row=deepcopy(row),payload=deepcopy(payload))
            return plan
    def submit(self,preview_id,confirmation):
        e=self.execution
        with self.lock,e._submission_lock():
            stored=self.previews.get(preview_id)
            if not stored or stored['plan']['expires_at']<self.clock():raise ValueError('Preview expired. Prepare again.')
            if confirmation!=stored['plan']['confirmation_phrase']:raise ValueError('Type the exact confirmation phrase from the reviewed ticket.')
            if not e.account.get('live_enabled') or not e.execution_allowed():raise PermissionError('Live execution is disabled for this account.')
            fresh=self._plan(stored['report'],stored['row'],stored['payload'])
            if fresh['ticket']!=stored['plan']['ticket'] or fresh['state_signature']!=stored['plan']['state_signature']:
                del self.previews[preview_id];raise ValueError('Broker state or ticket changed. Review a fresh preview; no order sent.')
            ips=e._client().request('GET','/ip/getIP')
            if e.egress() not in (ips.get('primaryIP'),ips.get('secondaryIP')):raise PermissionError('Server IP is not whitelisted for this Dhan account.')
            folder=e.folder/'holding-actions';folder.mkdir(mode=0o700,exist_ok=True)
            path=folder/(preview_id+'.json')
            if path.exists():raise ValueError('This action was already attempted. Reconcile in Dhan; no automatic retry.')
            ticket={**fresh['ticket'],'correlationId':preview_id}
            saved=dict(status='SUBMITTING',ticket=ticket,endpoint=fresh['endpoint'],preview=stored['plan'])
            _atomic_private_write(path,json.dumps(saved))
            del self.previews[preview_id]
            try:
                response=e._client().request('POST',fresh['endpoint'],ticket)
                if not isinstance(response,dict) or not response.get('orderId'):raise RuntimeError('No unambiguous broker acknowledgement.')
                saved.update(status=response.get('orderStatus') or 'ACKNOWLEDGED',order_id=str(response['orderId']))
            except DhanAPIError as error:
                saved.update(status='REJECTED' if error.definitive_rejection else 'UNKNOWN')
            except Exception:saved.update(status='UNKNOWN')
            _atomic_private_write(path,json.dumps(saved))
            return dict(status=saved['status'],order_id=saved.get('order_id'),broker='DHAN',account_id=e.account['id'],
                        message='Broker response recorded. Verify the order and protection in Dhan. No automatic retry; acknowledgement does not confirm a fill.')
