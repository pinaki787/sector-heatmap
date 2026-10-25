"""Reviewed native tickets from the existing Handoff/Screener controls."""
from contextlib import contextmanager
from decimal import Decimal
import json,math,secrets,sqlite3,time
from .motilal_strategy_broker import Broker,BROKER,account_lock,whole
from .motilal_api import positive

class Batches:
    def __init__(self,execution,clock=time.time):
        self.execution=execution;self.clock=clock;self.adapter=Broker(execution)
        self.path=execution.folder/'motilal-shared-previews.sqlite3'
        with self.db() as db:db.execute('CREATE TABLE IF NOT EXISTS previews(id TEXT PRIMARY KEY,user_id TEXT,created REAL,state TEXT,body TEXT,result TEXT)')
        self.path.chmod(0o600)
    @contextmanager
    def db(self):
        db=sqlite3.connect(self.path,timeout=2)
        try:
            with db:yield db
        finally:db.close()
    def capabilities(self):
        return dict(selected_broker=BROKER,motilal_configured=True,live_submission_enabled=self.adapter.live_enabled(),fyers_configured=False,dhan_configured=False,
                    routes=['EQUITY','LONG_OPTION'],spread_submission_enabled=False,message='Native LIMIT IOC. Motilal bought ATM Calls/Puts only; option spreads are excluded.')
    def position_slots(self):
        """Count current positions plus distinct pending native entry contracts."""
        positions=self.adapter.positions()
        existing={row['symbol'] for row in positions};pending=set()
        for row in self.execution.book('orders')['data']:
            status=str(row.get('orderstatus') or '').strip().upper()
            if status in {'CANCEL','TRADED','REJECTED','ERROR'}:continue
            side=str(row.get('buyorsell') or '').strip().upper()
            if side not in {'BUY','SELL'}:raise ValueError('Native pending order side unavailable; position allowance cannot be verified.')
            if side=='SELL':continue
            exchange=str(row.get('exchange') or '').strip().upper()
            from .motilal_api import EXCHANGES
            if exchange not in EXCHANGES:raise ValueError('Native pending order exchange unavailable.')
            symbol=f"MO:{exchange}:{whole(row.get('symboltoken'),'Pending token',False)}"
            if symbol not in existing:pending.add(symbol)
        return len(positions)+len(pending)
    def exclude_duplicate(self,symbol):
        from .exposure_guard import broker_exposures,matches_exposure
        meta=self.adapter.contract(symbol)
        underlying=meta['exchange'].removesuffix('FO')+':'+meta['underlying']
        if matches_exposure(underlying,broker_exposures(self.adapter),[symbol]):
            raise ValueError('An open position or pending order already exists for this underlying; duplicate entry blocked.')
    def booked_loss(self):
        rows=[r for r in self.execution.book('margin')['data'] if whole(r['srno'],'Margin row')==700]
        if len(rows)!=1 or not math.isfinite(float(rows[0]['amount'])):raise ValueError('Native current-session booked P/L unavailable; daily loss gate cannot be verified.')
        return max(0,-float(rows[0]['amount']))
    def prepare(self,user,payload):
        items=payload.get('items') if isinstance(payload.get('items'),list) else [payload]
        if not 1<=len(items)<=12:raise ValueError('Review one to twelve selected candidates.')
        reviews=[];reserved=0;risks=0;symbols=set()
        with account_lock(self.execution.folder):
            for item in items:
                if item.get('mode',payload.get('mode','LIVE'))!='LIVE':raise ValueError('This shared reviewed-order flow is Live; a requested Paper order cannot be upgraded to Live.')
                if item.get('broker','').upper()!=BROKER or item.get('account_id')!=self.execution.account['id']:raise PermissionError('Every item must use this exact Motilal account.')
                proposal=item.get('proposal') or {};kind=proposal.get('kind') or 'OPTION_SPREAD'
                if kind=='EQUITY':
                    if item.get('cash_product',payload.get('cash_product','INTRADAY'))!='INTRADAY':raise ValueError('Native cash delivery management is not verified; no silent conversion to Intraday.')
                    if proposal.get('direction')!='BULLISH':raise ValueError('Native reviewed equity route permits bought equity only; no inferred short exposure.')
                    meta=self.adapter.underlying(item['underlying']);symbol=meta['symbol'];units=whole(item.get('quantity',proposal.get('quantity')),'Shares',False)
                    if meta['instrument']=='INDEX' or meta['exchange'] not in {'NSE','BSE'}:raise ValueError('Exact native cash stock required.')
                elif kind=='LONG_OPTION':
                    legs=proposal.get('legs') or []
                    if len(legs)!=1 or legs[0].get('action')!='BUY':raise ValueError('Review one native bought Call/Put.')
                    symbol=legs[0]['symbol'];meta=self.adapter.contract(symbol)
                    if meta['option_type'] not in {'CE','PE'}:raise ValueError('Native Call/Put required.')
                    candidates=self.adapter.option_rows(item['underlying'])
                    if symbol not in {r['symbol'] for r in candidates}:raise ValueError('Option does not belong to selected underlying.')
                    expected=self.adapter.resolve(dict(underlying=item['underlying'],execution_route='OPTIONS'),proposal.get('direction'))
                    if symbol!=expected['symbol']:raise ValueError('Review the current native ATM Call/Put in the nearest eligible expiry; no substitute contract.')
                    lots=whole(item.get('lots',(proposal.get('sizing') or {}).get('lots')),'Lots',False);units=lots*meta['lot_size']
                else:raise ValueError('Native spread submission is unavailable: complete Greeks/liquidity and protected multi-leg ownership are required. No substitute order will be sent.')
                underlying_key=meta['exchange'].removesuffix('FO')+':'+meta['underlying']
                if underlying_key in symbols:raise ValueError('Duplicate native underlying in batch.')
                symbols.add(underlying_key)
                if symbol in symbols:raise ValueError('Duplicate native contract in batch.')
                symbols.add(symbol);quote=self.adapter.quote(symbol);order=self.adapter.order(symbol,units,1,quote)
                self.adapter.preflight(order,{})
                value=order['limitPrice']*units;reserved+=value
                if kind=='EQUITY':
                    stop=float(positive(item.get('invalidation'),'Structural stop'))
                    if stop>=quote['ask']:raise ValueError('Bought equity invalidation must be below entry.')
                    risk=(quote['ask']-stop)*units
                else:risk=value
                risks+=risk
                if item.get('enforce_risk_controls') is True:
                    if risk>float(positive(item.get('idea_risk_limit'),'Idea loss limit')):raise ValueError('Native idea risk cap exceeded.')
                    if risks>float(positive(item.get('daily_loss_limit'),'Daily loss limit'))-float(item.get('risk_reserve') or 0):raise ValueError('Native batch exceeds daily loss allowance after reserve.')
                    if item.get('external_open_risk') is None:raise ValueError('Confirm external open risk before this risk-controlled batch.')
                    if not math.isfinite(float(item['external_open_risk'])) or float(item['external_open_risk'])<0:raise ValueError('External risk must be finite and nonnegative.')
                    if risks+float(item['external_open_risk'])>float(item['daily_loss_limit'])-float(item.get('risk_reserve') or 0):raise ValueError('External exposure plus batch exceeds daily allowance.')
                    if risks+self.booked_loss()+float(item['external_open_risk'])>float(item['daily_loss_limit'])-float(item.get('risk_reserve') or 0):raise ValueError('Native booked loss plus exposure exceeds daily allowance.')
                    maximum=whole(item.get('max_simultaneous_positions'),'Maximum positions',False)
                    if self.position_slots()+len(items)>maximum:raise ValueError('Native maximum-position cap exceeded.')
                self.exclude_duplicate(symbol)
                reviewed=self.execution.tickets.preview(user['id'],dict(account_id=self.execution.account['id'],broker=BROKER,mode='LIVE',symbol=symbol,side='BUY',product='NORMAL',lots=units//meta['lot_size'],limit_price=order['limitPrice'],duration='IOC',max_notional=value))
                reviews.append(dict(reviewed,proposal=proposal,risk=risk,risk_context=item))
            cap=payload.get('allocation_budget')
            if cap is not None and reserved>float(positive(cap,'Allocated amount')):raise ValueError('Native batch exceeds selected allocation.')
            # Never add common cross-segment margin rows together: they can be the same balance.
            available=min(self.adapter.funds(r['body']['exchange']) for r in reviews)
            if reserved*1.01>available:raise ValueError('Native batch exceeds fresh funds plus reserve.')
            preview='MO-'+secrets.token_hex(16);phrase='SUBMIT '+preview
            body=dict(preview_id=preview,broker=BROKER,account_id=self.execution.account['id'],items=reviews,confirmation_phrase=phrase,expires_at=self.clock()+30,
                      aggregate=dict(order_count=len(reviews),total_worst_case_risk=risks,cash_reserved=reserved),exclusions=[],live_submission_enabled=self.adapter.live_enabled(),submission_eligible=True)
            with self.db() as db:db.execute('INSERT INTO previews VALUES (?,?,?,?,?,NULL)',(preview,user['id'],self.clock(),'REVIEW',json.dumps(body)))
            return body
    def submit(self,user,payload):
        pid=payload.get('preview_id')
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE');row=db.execute('SELECT user_id,created,state,body FROM previews WHERE id=?',(pid,)).fetchone()
            if not row or row[0]!=user['id']:raise PermissionError('Native review belongs to another user.')
            body=json.loads(row[3])
            if payload.get('confirmation')!=body['confirmation_phrase']:raise PermissionError('Confirm the exact native review.')
            if row[2]!='REVIEW' or not 0<=self.clock()-row[1]<=30:raise ValueError('Native review expired or already consumed; inspect orderbook before any retry.')
            db.execute("UPDATE previews SET state='SUBMITTING' WHERE id=?",(pid,))
        results=[]
        try:
            if not self.adapter.live_enabled():raise PermissionError('Motilal Live capability disabled.')
            for item in body['items']:
                policy=item['risk_context']
                if policy.get('enforce_risk_controls') and sum(r['risk'] for r in body['items'])+self.booked_loss()+float(policy['external_open_risk'])>float(policy['daily_loss_limit'])-float(policy.get('risk_reserve') or 0):raise ValueError('Native daily loss allowance changed after review; no order sent.')
            for index,item in enumerate(body['items']):
                order=self.adapter.order(item['symbol'],item['units'],1,dict(ask=item['body']['price'],bid=item['body']['price']))
                with account_lock(self.execution.folder):
                    policy=item['risk_context']
                    if item['proposal'].get('kind')=='LONG_OPTION':
                        expected=self.adapter.resolve(dict(underlying=policy['underlying'],execution_route='OPTIONS'),item['proposal'].get('direction'))
                        if expected['symbol']!=item['symbol']:raise ValueError('Native ATM contract changed after review; review again. No replacement order was sent.')
                    if policy.get('enforce_risk_controls'):
                        maximum=whole(policy.get('max_simultaneous_positions'),'Maximum positions',False)
                        remaining=len(body['items'])-index
                        if self.position_slots()+remaining>maximum:
                            raise ValueError('Native maximum-position allowance changed after review; remaining orders were not sent.')
                        if sum(r['risk'] for r in body['items'])+self.booked_loss()+float(policy['external_open_risk'])>float(policy['daily_loss_limit'])-float(policy.get('risk_reserve') or 0):
                            raise ValueError('Native daily loss allowance changed during submission; remaining orders were not sent.')
                    self.exclude_duplicate(item['symbol'])
                    self.adapter.preflight(order,{})
                    if not self.adapter.live_enabled():raise PermissionError('Motilal Live capability changed during preflight; no order sent.')
                    results.append(self.execution.tickets.submit(user['id'],item['ticket_id'],item['confirmation']))
            result=dict(preview_id=pid,broker=BROKER,status='ACCEPTED',message='Requests accepted; native orderbook determines fills. No automatic retry.',items=results)
        except Exception as error:
            result=dict(preview_id=pid,broker=BROKER,status='RECONCILIATION_REQUIRED',message=str(error),items=results)
        with self.db() as db:db.execute('UPDATE previews SET state=?,result=? WHERE id=?',(result['status'],json.dumps(result),pid))
        return result
