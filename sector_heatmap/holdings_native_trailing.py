"""Native trailing protection ports. Reads never adopt a manual/strategy stop."""
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime
from pathlib import Path
import json,os,time
from .holdings_actions import decimal,grid,digest
from .holdings_analysis import FyersHoldings,DeltaHoldings,HoldingsAnalysis,IST
from .native_holdings import MotilalHoldings
from .file_lock import lock_file,unlock_file

def rows(reply,key):
    if not isinstance(reply,dict) or reply.get('s')!='ok' or not isinstance(reply.get(key),list):raise ValueError('Complete native broker evidence unavailable.')
    return reply[key]

def normalize(row,broker):
    row=deepcopy(row)
    if broker=='FYERS' and row.get('kind')=='DELIVERY_EQUITY':
        row['native_identity']=dict(securityId=row['symbol'],exchangeSegment=row['symbol'].split(':')[0]+'_EQ')
    elif broker=='MOTILAL_OSWAL' and row.get('native_identity'):
        m=row['native_identity'];m.update(securityId=str(m['token']),exchangeSegment=m['exchange']+'_EQ')
    if broker=='DELTA_INDIA':row.setdefault('holding_type','Linear futures position')
    return row

class Port:
    def __init__(self,account,folder,client=None,service=None,delta=None,allowed=lambda:False,clock=time.time):
        self.account,self.folder,self.client,self.service,self.delta,self.clock=account,Path(folder),client,service,delta,clock
        self.execution_allowed=allowed
    @contextmanager
    def _submission_lock(self):
        p=self.folder/'holding-native-submission.lock';p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('a') as f:
            os.chmod(p,0o600);lock_file(f.fileno(),blocking=True)
            try:yield
            finally:unlock_file(f.fileno())
    def adapter(self):
        broker=self.account['broker']
        if broker=='FYERS':return FyersHoldings(self.client())
        if broker=='MOTILAL_OSWAL':self.service.ready();return MotilalHoldings(self.service)
        return DeltaHoldings(self.delta)
    def inventory(self):
        adapter=self.adapter();items=adapter.inventory()
        if self.account['broker']=='DELTA_INDIA':adapter.enrich(items)
        return [normalize(r,self.account['broker']) for r in items]
    def protection(self):
        broker=self.account['broker']
        if broker=='FYERS':
            c=self.client();profile=c.get_profile()
            if profile.get('s')!='ok' or str((profile.get('data') or {}).get('fy_id','')).upper()!=self.account['account_ref'].upper():raise PermissionError('FYERS profile differs from this account.')
            return rows(c.gtt_orderbook(),'orderBook'),rows(c.orderbook(),'orderBook'),rows(c.positions(),'netPositions')
        if broker=='MOTILAL_OSWAL':
            self.service.ready();self.service.client.profile()
            return self.service.book('orders')['data'],[],self.service.book('positions')['data']
        reply=self.delta._private('GET','/v2/orders',params={'state':'open,pending','page_size':100})
        if reply.get('meta',{}).get('after'):raise ValueError('More Delta orders require reconciliation; protection preview withheld.')
        book=reply.get('result')
        if not isinstance(book,list):raise ValueError('Delta open-order evidence unavailable.')
        return book,[],[]
    def identity(self,r,symbol,meta):
        broker=self.account['broker']
        if broker=='FYERS':return r.get('symbol')==symbol
        if broker=='MOTILAL_OSWAL':return str(r.get('symboltoken'))==str(meta['securityId']) and r.get('exchange')==meta['exchangeSegment'].split('_')[0]
        return str(r.get('product_id'))==str(meta['securityId'])
    def active(self,r):
        if self.account['broker']=='FYERS':return r.get('ord_status',r.get('status')) not in (1,2,5,7)
        if self.account['broker']=='MOTILAL_OSWAL':return str(r.get('orderstatus','')).upper() not in ('CANCEL','TRADED','REJECTED','ERROR')
        return r.get('state') in ('open','pending') or r.get('state') is None
    def order_id(self,r):
        return str(r.get('uniqueorderid') if self.account['broker']=='MOTILAL_OSWAL' else r.get('id') or '')
    def confirmed(self,ticket,order_id,tag):
        book,_,_=self.protection();found=[r for r in book if self.order_id(r)==str(order_id)]
        if len(found)!=1:raise ValueError('Exact broker stop is missing or ambiguous; no automatic retry.')
        r=found[0];b=self.account['broker'];n=ticket['native']
        if b=='FYERS':
            valid=(r.get('symbol')==n['symbol'] and r.get('product_type')==n['productType'] and r.get('tran_side')==n['side']
                   and r.get('gtt_oco_ind')==1 and r.get('ord_status')==6 and str(r.get('client_id',r.get('clientId',''))).upper()==self.account['account_ref'].upper())
            levels=(r.get('qty'),r.get('price_trigger'),r.get('price_limit'))
            if r.get('orderTag') and not str(r['orderTag']).endswith(tag):valid=False
        elif b=='MOTILAL_OSWAL':
            valid=(r.get('exchange')==n['exchange'] and str(r.get('symboltoken'))==str(n['symboltoken']) and str(r.get('buyorsell','')).upper()=='SELL'
                   and str(r.get('producttype','')).upper()==n['producttype'] and str(r.get('orderstatus','')).upper()=='CONFIRM'
                   and str(r.get('ordertype','')).upper() in ('STOPLOSS','P') and str(r.get('orderduration','')).upper()=='GTC'
                   and decimal(r.get('qtytradedtoday',0))==0 and decimal(r.get('totalqtyremaining'))==decimal(ticket['quantity']))
            levels=(r.get('orderqty'),r.get('triggerprice'),r.get('price'))
            if r.get('tag') and r['tag']!=tag:valid=False
        else:
            valid=(str(r.get('product_id'))==str(n['product_id']) and r.get('side')==n['side'] and r.get('reduce_only') is True
                   and r.get('order_type')=='limit_order' and r.get('stop_order_type')=='stop_loss_order'
                   and r.get('stop_trigger_method')=='last_traded_price' and r.get('state')=='pending'
                   and r.get('client_order_id')==tag and r.get('time_in_force')=='gtc' and decimal(r.get('unfilled_size'))==decimal(ticket['quantity']))
            levels=(r.get('size'),r.get('stop_price'),r.get('limit_price'))
        if not valid or any(decimal(a)!=decimal(v) for a,v in zip(levels,(ticket['quantity'],ticket['triggerPrice'],ticket['price']))):
            raise ValueError('Broker stop identity, validity, levels, quantity or state differs. Review protection.')
        return dict(order_id=str(order_id),ticket=deepcopy(ticket),correlation_id=tag)
    def mutate(self,ticket,old,tag):
        n=deepcopy(ticket['native']);b=self.account['broker']
        if b=='FYERS':
            if old:reply=self.client().modify_gtt_order(dict(id=old['order_id'],orderInfo=n['orderInfo']))
            else:reply=self.client().place_gtt_order(dict(n,orderTag=tag))
            if reply.get('s')!='ok' or not reply.get('id'):raise ValueError('FYERS protection outcome requires reconciliation; no retry.')
            return str(reply['id'])
        if b=='MOTILAL_OSWAL':
            if old:
                book,_,_=self.protection();matches=[r for r in book if self.order_id(r)==old['order_id']]
                if len(matches)!=1:raise ValueError('Exact Motilal order is unavailable.')
                r=matches[0]
                reply=self.service.client.request('modify',dict(uniqueorderid=old['order_id'],newordertype='STOPLOSS',neworderduration='GTC',
                    newprice=n['price'],newtriggerprice=n['triggerprice'],newquantityinlot=n['quantityinlot'],newdisclosedquantity=0,
                    lastmodifiedtime=r['lastmodifiedtime'],qtytradedtoday=0))
                return old['order_id'] # Modify acknowledgement has no order id; GET book must reconcile.
            reply=self.service.client.request('place',dict(n,tag=tag))
            if not reply.get('uniqueorderid'):raise ValueError('Motilal stop outcome requires reconciliation; no retry.')
            return str(reply['uniqueorderid'])
        if old:
            body={k:n[k] for k in ('product_id','size','limit_price','stop_price')};body['id']=int(old['order_id'])
            reply=self.delta._private('PUT','/v2/orders',body=body)
        else:reply=self.delta._private('POST','/v2/orders',body=dict(n,client_order_id=tag))
        result=reply.get('result') or {}
        if not result.get('id'):raise ValueError('Delta stop outcome requires reconciliation; no retry.')
        return str(result['id'])

class Actions:
    def __init__(self,port,clock=time.time):self.execution=port;self.broker=port.account['broker'];self.clock=clock
    def _plan(self,report,row,payload,managed=None,monitor_path=None):
        e=self.execution;b=self.broker;now=self.clock();row=normalize(row,b)
        if report.get('broker')!=b or report.get('account_id')!=e.account['id']:raise PermissionError('Review differs from selected broker/account.')
        if not 0<=now-datetime.fromisoformat(report['as_of']).timestamp()<=600:raise ValueError('Run a fresh portfolio review; this review expired.')
        if row.get('action')!='TRAIL' or row.get('kind') not in ('DELIVERY_EQUITY','LINEAR_FUTURE'):raise ValueError('A verified TRAIL recommendation is required.')
        current=[r for r in e.inventory() if r['symbol']==row['symbol'] and r['kind']==row['kind']]
        if len(current)!=1 or any(current[0].get(k)!=row.get(k) for k in ('quantity','average_price','holding_type','native_identity')):raise ValueError('Exact holding identity, quantity, cost or product changed.')
        qty=decimal(row['quantity']);side=1 if qty>0 else -1
        if not qty or abs(qty)!=int(abs(qty)):raise ValueError('A nonzero whole position is required.')
        if b!='DELTA_INDIA' and (qty<0 or row['kind']!='DELIVERY_EQUITY'):raise ValueError('Cash protection requires an existing long delivery holding.')
        meta=row['native_identity'];book,regular,positions=e.protection();oid=str((managed or {}).get('order_id') or '')
        for r in book+regular:
            if e.identity(r,row['symbol'],meta) and e.active(r) and e.order_id(r)!=oid:raise ValueError('Another order/protective plan covers this instrument. Existing orders are never adopted or duplicated.')
        if b=='FYERS' and any(r.get('symbol')==row['symbol'] and decimal(r.get('netQty',0)) for r in positions):raise ValueError('An open trading position overlaps the delivery holding.')
        if b=='MOTILAL_OSWAL' and any(e.identity(r,row['symbol'],meta) and decimal(r.get('buyquantity',0))!=decimal(r.get('sellquantity',0)) for r in positions):raise ValueError('Trading exposure overlaps this DP holding.')
        import sqlite3
        dbpath=e.folder/'handoff-exits.sqlite3'
        if dbpath.exists():
            with sqlite3.connect('file:'+str(dbpath)+'?mode=ro',uri=True) as db:
                for saved, in db.execute('SELECT body FROM trades'):
                    owned=json.loads(saved)
                    if owned.get('symbol')==row['symbol'] and owned.get('state') not in ('CLOSED','FLAT','REJECTED','CANCELLED'):
                        raise ValueError('An existing Handoff lifecycle owns this instrument; its protection is retained.')
        from .service_restart import runtime_states
        own=Path(monitor_path).resolve() if monitor_path else None
        for p in runtime_states(e.folder/'source'):
            if own and p.resolve()==own:continue
            state=json.loads(p.read_text())
            if p.parent.parent.name=='holding-trails' and state.get('security_id')!=meta['securityId']:continue
            if any(state.get(k) for k in ('running','accepting_entries','position','positions','pending','active','loop_running','runner_position')):
                raise ValueError('Another strategy owns active or unresolved exposure in this account.')
        if b=='FYERS':
            from .handoff import FyersCmMaster
            contract=FyersCmMaster().lookup([row['symbol']]).get(row['symbol'])
            if not contract:raise ValueError('Current FYERS native master is unavailable.')
            tick=decimal(contract['tick_size'])
            from .parser_protection_broker import ParserProtectionBroker
            price=decimal(ParserProtectionBroker().fresh_price(row['symbol']))
            product='CNC'
            if str(row.get('holding_type') or '').upper() not in ('HLD','CNC','HOLDING','DEMAT','T1'):raise ValueError('FYERS funding product is not verified as CNC; mixed/MTF holdings require separate review.')
        elif b=='MOTILAL_OSWAL':
            e.service.ready();contract=e.service.master.exact(row['symbol'])
            if str(contract['token'])!=meta['securityId'] or contract['lot_size']!=1:raise ValueError('Native Motilal cash contract changed.')
            tick=decimal(contract['tick_size']);snapshot=e.service.quote(row['symbol']);depth=snapshot.get('depth')
            if not depth or not 0<=now-depth['received_at']<=15:raise ValueError('Fresh native Motilal depth required; no other broker is used.')
            price=decimal(depth['bid']);product='SELLFROMDP';profile=e.service.client.profile()
            if product not in {str(v).upper() for v in profile.get('products',[])}:raise PermissionError('SELLFROMDP is not enabled by the native profile.')
            h=[r for r in e.service.book('holdings')['data'] if str(r.get('nsesymboltoken' if meta['exchangeSegment']=='NSE_EQ' else 'bsescripcode'))==meta['securityId']]
            if len(h)!=1:raise ValueError('Unencumbered DP quantity is ambiguous.')
            held=h[0]
            if decimal(held.get('dpquantity'))!=qty or decimal(held.get('poaquantity'))<qty or any(decimal(held.get(k))!=0 for k in ('blockedquantity','collateralquantity','tpinquantity','nonpoaquantity','rmssellingquantity','buybackquantity','slbmquantity','nbfcquantity','debitstockquantity')):
                raise ValueError('Full reviewed DP quantity needs verified POA authority and no pledge, block, EDIS or lending restriction.')
        else:
            product='REDUCE_ONLY';contract=e.delta.product(row['symbol']);tick=decimal(contract['tick_size'])
            if str(contract['id'])!=meta['securityId']:raise ValueError('Native Delta product identity changed.')
            q=e.delta.ticker(row['symbol']);price=decimal(q['bid' if side>0 else 'ask'])
        trigger=decimal(row['candidate_stop'])
        if managed:
            e.confirmed(managed['ticket'],managed['order_id'],managed['correlation_id'])
            trigger=max(trigger,decimal(managed['ticket']['triggerPrice'])) if side>0 else min(trigger,decimal(managed['ticket']['triggerPrice']))
        from decimal import ROUND_CEILING,ROUND_FLOOR
        trigger=grid(trigger,tick,ROUND_CEILING if side>0 else ROUND_FLOOR)
        if trigger<=0 or side*(price-decimal(trigger))<=0:raise ValueError('Stop is already crossed; no immediate exit is substituted.')
        limit=grid(decimal(trigger)*decimal('0.995' if side>0 else '1.005'),tick,ROUND_FLOOR if side>0 else ROUND_CEILING)
        if managed and decimal(trigger)==decimal(managed['ticket']['triggerPrice']):limit=managed['ticket']['price']
        if decimal(limit)<=0 or side*(decimal(trigger)-decimal(limit))<0 or abs(decimal(limit)/decimal(trigger)-1)>decimal('0.02'):raise ValueError('Tick-aligned stop limit exceeds the supported protection buffer.')
        if b=='FYERS':native=dict(symbol=row['symbol'],side=-1,productType=product,orderInfo=dict(leg1=dict(qty=int(qty),price=limit,triggerPrice=trigger)))
        elif b=='MOTILAL_OSWAL':native=dict(exchange=contract['exchange'],symboltoken=contract['token'],buyorsell='SELL',ordertype='STOPLOSS',
            producttype=product,orderduration='GTC',price=limit,triggerprice=trigger,quantityinlot=int(qty),disclosedquantity=0,amoorder='N',algoid='',participantcode='')
        else:native=dict(product_id=contract['id'],size=int(abs(qty)),side='sell' if side>0 else 'buy',order_type='limit_order',time_in_force='gtc',
            reduce_only=True,limit_price=str(limit),stop_price=str(trigger),stop_order_type='stop_loss_order',stop_trigger_method='last_traded_price')
        ticket=dict(quantity=int(abs(qty)),transactionType='SELL' if side>0 else 'BUY',productType=product,triggerPrice=trigger,price=limit,native=native)
        return dict(broker=b,account_id=e.account['id'],symbol=row['symbol'],action='TRAIL',ticket=ticket,
            state_signature=digest([row['native_identity'],row['quantity'],row['average_price'],row.get('holding_type'),managed]),
            live_submission_enabled=bool(e.account.get('live_enabled')) and e.execution_allowed(),
            description={'FYERS':'Single-leg FYERS GTT stop','MOTILAL_OSWAL':'Native Motilal GTC STOPLOSS; no DAY fallback','DELTA_INDIA':'Delta GTC reduce-only stop-limit'}[b])


from .holdings_trailing import HoldingTrails
class NativeTrails(HoldingTrails):
    def __init__(self,port,store,clock=time.time):
        super().__init__(port,Actions(port,clock),store,clock)
        self.action_route='/api/delta-india/holdings-analysis/trail-enable' if port.account['broker']=='DELTA_INDIA' else '/api/motilal/holdings-analysis/trail-enable' if port.account['broker']=='MOTILAL_OSWAL' else '/api/holdings-analysis/trail-enable'
    def normalize(self,row):return normalize(row,self.e.account['broker'])
    def adapter(self):return self.e.adapter()
    def preview(self,owner,report,row,payload):return super().preview(owner,report,self.normalize(row),payload)
    def managed(self,row,owner):
        meta=row.get('native_identity') or {};found={}
        for state in self.list(owner):
            if state.get('security_id')==str(meta.get('securityId')) and state.get('exchange_segment')==meta.get('exchangeSegment'):
                if state.get('pending'):raise ValueError('Prior broker request needs reconciliation.')
                if state.get('running'):raise ValueError('This position already has an active trailing monitor.')
                if state.get('managed_stop'):found[state['managed_stop']['order_id']]=state['managed_stop']
        if len(found)>1:raise ValueError('Multiple previously owned stops need reconciliation.')
        return deepcopy(next(iter(found.values()))) if found else None
    def confirm_stop(self,state,ticket,order_id,correlation):return self.e.confirmed(ticket,order_id,correlation)
    def transmit(self,state,plan,create=False):
        if state.get('pending'):raise ValueError('An earlier request is uncertain; no automatic retry.')
        if self.stopped(state):return False
        self.assert_live();old=state.get('managed_stop');ticket=deepcopy(plan['ticket']);side=1 if state['quantity']>0 else -1
        if old:
            self.e.confirmed(old['ticket'],old['order_id'],old['correlation_id'])
            if side*(decimal(ticket['triggerPrice'])-decimal(old['ticket']['triggerPrice']))<=0:return False
        tag=(old or {}).get('correlation_id') or ('ST'+digest(state['monitor_id'])[:8] if state['broker']=='MOTILAL_OSWAL' else state['monitor_id'])
        if self.stopped(state):return False
        state['pending']=dict(operation='MODIFY' if old else 'CREATE',ticket=ticket,tag=tag,at=self.clock())
        self.save(state);self.event(state,'BROKER_REQUEST',operation=state['pending']['operation'],ticket=ticket)
        ident=self.e.mutate(ticket,old,tag)
        if old and ident!=old['order_id']:raise ValueError('Broker returned a different order identity; no retry.')
        state['managed_stop']=self.e.confirmed(ticket,ident,tag);state['pending']=None;self.save(state)
        self.event(state,'STOP_CONFIRMED',order_id=ident,trigger=ticket['triggerPrice'],limit=ticket['price'])
        return True
