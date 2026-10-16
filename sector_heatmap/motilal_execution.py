"""Account-native reviewed LIMIT tickets. Acceptance is never reported as a fill."""
from contextlib import contextmanager
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
import secrets
import sqlite3
import threading
import time
from .motilal_api import MotilalError, positive


class Tickets:
    def __init__(self, folder, client, master, feed, account_id, *, clock=time.time):
        self.path=Path(folder)/'motilal-tickets.sqlite3'
        self.path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.client,self.master,self.feed,self.account_id,self.clock=client,master,feed,account_id,clock
        self.lock=threading.Lock()
        with self.db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS tickets(id TEXT PRIMARY KEY, user_id TEXT NOT NULL, mode TEXT NOT NULL, state TEXT NOT NULL, created REAL NOT NULL, body TEXT NOT NULL, result TEXT, tag TEXT UNIQUE NOT NULL)')
        self.path.chmod(0o600)

    @contextmanager
    def db(self):
        db=sqlite3.connect(self.path,timeout=2)
        try:
            with db:yield db
        finally:db.close()

    def validate(self,payload):
        if payload.get('account_id')!=self.account_id or payload.get('broker')!='MOTILAL_OSWAL':
            raise PermissionError('Select this exact Motilal account.')
        mode=payload.get('mode')
        if mode not in {'PAPER','LIVE'}:raise ValueError('Select Paper or Live explicitly.')
        if mode=='LIVE' and not self.client.live_enabled:raise PermissionError('Enable Live capability in this account’s connection settings first.')
        contract=self.master.exact(payload.get('symbol'))
        if contract.get('instrument')=='INDEX':raise ValueError('An index is not an orderable contract.')
        side=payload.get('side')
        product=payload.get('product')
        if side not in {'BUY','SELL'} or product not in {'NORMAL','DELIVERY','VALUEPLUS','SELLFROMDP'}:
            raise ValueError('Select a supported side and product.')
        if product in {'DELIVERY','SELLFROMDP'} and contract['exchange'] not in {'NSE','BSE'}:
            raise ValueError('Delivery products require cash equity.')
        lots=positive(payload.get('lots'),'Lots')
        if lots!=int(lots) or lots>=2**31:raise ValueError('Lots must be a supported positive whole number.')
        price=positive(payload.get('limit_price'),'Limit price')
        tick=Decimal(str(contract['tick_size']))
        if price>=Decimal('100000000000') or price%tick or price.as_tuple().exponent < -4:raise ValueError('Limit price must match the native tick size, with at most four decimal places.')
        units=int(lots)*contract['lot_size']
        if units>=2**31:raise ValueError('Order quantity exceeds the supported native range.')
        cap=contract.get('max_quantity')
        # maxqtyperorder uses the same native lot unit as quantityinlot.
        if cap and lots>cap:raise ValueError('Quantity exceeds the broker’s maximum order quantity.')
        profile=self.client.profile()
        if str(profile.get('usertype','')).strip().casefold() not in {'investorclient','investor client'}:raise PermissionError('This route requires an authenticated investor client; dealer routing is not inferred.')
        if contract['exchange'] not in profile.get('exchanges',[]):raise PermissionError('This segment is not enabled in the authenticated Motilal profile.')
        products={str(p).upper() for p in profile.get('products',[])}
        if product not in products:raise PermissionError('This product is not enabled in the authenticated Motilal profile.')
        quote=self.feed.quote(contract['exchange'],contract['token'])
        budget=positive(payload.get('max_notional'),'Maximum order value')
        value=price*units
        if value>budget:raise ValueError('Order value exceeds the reviewed maximum order value.')
        duration=payload.get('duration','DAY')
        if duration not in {'DAY','IOC'}:raise ValueError('Choose DAY or IOC.')
        # No market/AMO fallback and no inferred strategy intent.
        body=dict(exchange=contract['exchange'],symboltoken=contract['token'],buyorsell=side,ordertype='LIMIT',
                  producttype=product,orderduration=duration,price=float(price),triggerprice=0,
                  quantityinlot=int(lots),disclosedquantity=0,amoorder='N',algoid='',participantcode='')
        return dict(account_id=self.account_id,broker='MOTILAL_OSWAL',mode=mode,symbol=contract['symbol'],name=contract['name'],
                    contract_identity={key:contract.get(key) for key in ('symbol','exchange','token','underlying_token','instrument','expiry','strike','option_type','lot_size','tick_size')},
                    lots=int(lots),lot_size=contract['lot_size'],units=units,max_notional=float(budget),order_value=float(value),
                    bid=quote['bid'],ask=quote['ask'],quote_exchange_at=quote['exchange_at'],body=body)

    def preview(self,user_id,payload):
        with self.db() as db:
            if db.execute("SELECT 1 FROM tickets WHERE state IN ('SUBMITTING','UNCERTAIN') LIMIT 1").fetchone():
                raise ValueError('An earlier order result is uncertain. Reconcile that ticket before reviewing another order.')
        reviewed=self.validate(payload)
        ticket_id=secrets.token_hex(16);tag='SP'+secrets.token_hex(4)
        with self.db() as db:
            db.execute('INSERT INTO tickets VALUES (?,?,?,?,?,?,?,?)',(ticket_id,user_id,reviewed['mode'],'REVIEW',self.clock(),json.dumps(reviewed),None,tag))
        return {**reviewed,'ticket_id':ticket_id,'expires_at':self.clock()+30,'confirmation':f"{reviewed['mode']} {ticket_id}",
                'message':'Review exact account, contract, side, lots and limit price. Broker acceptance does not confirm a fill.'}

    def submit(self,user_id,ticket_id,confirmation):
        # SQLite claim spans processes; never retry a claimed ticket, even after a crash.
        with self.lock:
            with self.db() as db:
                db.execute('BEGIN IMMEDIATE')
                row=db.execute('SELECT user_id,mode,state,created,body,result,tag FROM tickets WHERE id=?',(ticket_id,)).fetchone()
                if not row or row[0]!=user_id:raise PermissionError('Ticket does not belong to this user.')
                if confirmation!=f'{row[1]} {ticket_id}':raise PermissionError('Confirm this exact reviewed ticket.')
                if row[2]!='REVIEW':raise ValueError('This ticket was already consumed; reconcile its broker orderbook before any new ticket.')
                if not 0<=self.clock()-row[3]<=30:raise ValueError('Review expired; request a new preview.')
                if db.execute("SELECT 1 FROM tickets WHERE state IN ('SUBMITTING','UNCERTAIN') AND id<>? LIMIT 1",(ticket_id,)).fetchone():
                    raise ValueError('An earlier submission is uncertain. Reconcile it before another order.')
                saved=json.loads(row[4]);body=saved['body']
                # Refresh profile, native contract and depth. Never change reviewed price or size.
                fresh=self.validate(dict(account_id=self.account_id,broker='MOTILAL_OSWAL',mode=saved['mode'],symbol=saved['symbol'],
                    side=body['buyorsell'],product=body['producttype'],lots=body['quantityinlot'],limit_price=body['price'],
                    duration=body['orderduration'],max_notional=saved['max_notional']))
                if fresh['contract_identity']!=saved.get('contract_identity') or fresh['units']!=saved['units']:
                    raise ValueError('Native contract metadata changed after review. Request a new preview; no order sent.')
                if fresh['body']!=body:
                    raise ValueError('Native order differs from the reviewed ticket. Request a new preview; no order sent.')
                db.execute("UPDATE tickets SET state='SUBMITTING' WHERE id=?",(ticket_id,))
            body={**body,'tag':row[6]}
            try:
                if row[1]=='PAPER':
                    result=dict(state='PAPER_RECORDED',broker_order_id=None,message='Paper limit ticket recorded; no broker order and no simulated fill.')
                else:
                    reply=self.client.request('place',body)
                    order_id=str(reply.get('uniqueorderid') or '')
                    if not re.fullmatch(r'[A-Za-z0-9_-]{1,50}',order_id):raise MotilalError('Broker acceptance lacks a usable order ID. Reconcile the orderbook.',uncertain=True)
                    result=dict(state='ACCEPTED',broker_order_id=order_id,message='Broker accepted the request. Check the orderbook for rejection, partial execution or confirmed fill.')
            except Exception as error:
                # Conservative for every post-claim failure, including an interrupted process.
                with self.db() as db:db.execute('UPDATE tickets SET state=? WHERE id=?',('REJECTED' if isinstance(error,MotilalError) and not error.uncertain else 'UNCERTAIN',ticket_id))
                if isinstance(error,MotilalError):raise
                raise MotilalError('Submission result unavailable; inspect the Motilal orderbook before creating another ticket.',uncertain=True) from None
            with self.db() as db:db.execute('UPDATE tickets SET state=?,result=? WHERE id=?',(result['state'],json.dumps(result),ticket_id))
            return dict(ticket_id=ticket_id,tag=row[6],**result)

    def reconcile(self,user_id,ticket_id):
        with self.lock:
            with self.db() as db:row=db.execute('SELECT user_id,body,tag,mode FROM tickets WHERE id=?',(ticket_id,)).fetchone()
            if not row or row[0]!=user_id:raise PermissionError('Ticket does not belong to this user.')
            if row[3]!='LIVE':raise ValueError('Paper tickets have no broker order to reconcile.')
            reviewed=json.loads(row[1]);body=reviewed['body']
            profile=self.client.profile()
            reply=self.client.request('orders');orders=reply.get('data')
            if not isinstance(orders,list):raise ValueError('Motilal orderbook could not be verified.')
            matches=[r for r in orders if str(r.get('tag') or '').strip()==row[2]]
            if len(matches)!=1:raise ValueError('No unique matching native order was found. Ticket remains blocked; do not retry it.')
            native=matches[0]
            if str(native.get('clientid','')).upper()!=str(profile.get('clientcode','')).upper() or not profile.get('clientcode'):
                raise PermissionError('Matched broker order belongs to a different or unidentified account.')
            native_qty=positive(native.get('orderqty'),'Native order quantity')
            native_lot=positive(native.get('lotsize'),'Native order lot size')
            if native_qty!=reviewed['units'] or native_lot!=reviewed['lot_size']:
                raise ValueError('Broker order quantity differs from the reviewed units or lot size. Reconciliation blocked.')
            if str(native.get('exchange') or '').upper()!=body['exchange'] or str(native.get('symboltoken'))!=str(body['symboltoken']) or str(native.get('buyorsell') or '').upper()!=body['buyorsell'] or str(native.get('producttype') or '').upper()!=body['producttype']:
                raise ValueError('Broker order identity differs from this ticket. Reconciliation blocked.')
            order_id=str(native.get('uniqueorderid') or '')
            status=str(native.get('orderstatus') or '').upper()
            if not re.fullmatch(r'[A-Za-z0-9_-]{1,50}',order_id) or status not in {'CONFIRM','CANCEL','PARTIAL','TRADED','REJECTED','ERROR','SENT'}:
                raise ValueError('Broker order is still ambiguous; keep the ticket blocked.')
            result=dict(state='BROKER_'+status,broker_order_id=order_id,native_order=native,message='Matched the existing broker order. No order was submitted or retried; quantities and prices remain native report fields.')
            with self.db() as db:db.execute('UPDATE tickets SET state=?,result=? WHERE id=?',(result['state'],json.dumps(result),ticket_id))
            return dict(ticket_id=ticket_id,**result)

    def list(self,user_id):
        with self.db() as db:rows=db.execute('SELECT id,mode,state,created,body,result,tag FROM tickets WHERE user_id=? ORDER BY created DESC LIMIT 100',(user_id,)).fetchall()
        return [dict(ticket_id=r[0],mode=r[1],state=r[2],created_at=r[3],review=json.loads(r[4]),result=json.loads(r[5]) if r[5] else None,tag=r[6]) for r in rows]
