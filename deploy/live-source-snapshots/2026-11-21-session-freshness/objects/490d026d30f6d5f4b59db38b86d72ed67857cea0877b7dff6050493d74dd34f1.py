"""Durable parser attribution and broker OCO protection; mutation is opt-in.

No existing/manual positions are adopted. An uncertain submission is never retried.
Only a future entry carrying explicit protection consent can be managed.
"""
from .file_lock import lock_file, unlock_file
from contextlib import contextmanager
import hashlib
import json
import math
import os
import sqlite3
import threading
from decimal import Decimal


def protection_plan(parsed, contract, order, selected_target=None):
    targets = parsed.get('targets') or []
    if not targets or not parsed.get('stop_loss'):
        raise ValueError('Protection requires a stop loss and target.')
    if len(targets) > 1 and selected_target in (None, ''):
        raise ValueError('Choose the target for the full filled quantity; multiple-target allocation is not inferred.')
    target = float(targets[0] if selected_target in (None, '') else selected_target)
    stop, tick = float(parsed['stop_loss']), float(contract['tick_size'])
    entry = float(order['stopPrice'] or order['limitPrice'])
    if target not in targets or not all(math.isfinite(x) and x > 0 for x in [target,stop,tick,entry]):
        raise ValueError('Choose a positive target from the parsed recommendation.')
    side = order['side']
    if not (stop < entry < target if side == 1 else target < entry < stop):
        raise ValueError('Stop and target must be on opposite sides of entry for the chosen direction.')
    for price in [stop,target]:
        if Decimal(str(price)) % Decimal(str(tick)):
            raise ValueError('Stop and target must match the exact broker tick; no silent rounding.')
    stop_limit = round(stop - tick if side == 1 else stop + tick, 8)
    if stop_limit <= 0: raise ValueError('Stop limit must be positive.')
    return {'kind':'FYERS_GTT_OCO','stop':stop,'stop_limit':stop_limit,'target':target,
            'targets':list(targets),'allocation':'FULL_FILLED_QUANTITY_AT_SELECTED_TARGET',
            'tick_size':tick,'lot_size':int(contract['lot_size']),
            'consent':'After confirmed fills, create broker OCO target/stop-limit protection for matched quantity only. '
                      'Other listed targets remain reference levels. No automatic trailing. GTT triggers and limit orders do not guarantee fills. '
                      'Uncertain submissions or external position changes require manual reconciliation.'}


class ParserLifecycle:
    def __init__(self, path, broker, enabled=lambda:False):
        path.parent.mkdir(parents=True,exist_ok=True)
        self.lock_path = path.with_suffix(".lock")
        self.db=sqlite3.connect(path,check_same_thread=False)
        os.chmod(path,0o600)
        self.db.execute('CREATE TABLE IF NOT EXISTS entries (id TEXT PRIMARY KEY, data TEXT NOT NULL)')
        self.db.commit();self.lock=threading.RLock();self.broker=broker;self.enabled=enabled

    @contextmanager
    def mutation_lock(self):
        with self.lock:
            fd = os.open(self.lock_path, os.O_CREAT | os.O_RDWR, 0o600)
            try:
                lock_file(fd)
                yield
            finally:
                unlock_file(fd)
                os.close(fd)

    def _save(self, key, data):
        self.db.execute('INSERT OR REPLACE INTO entries VALUES (?,?)',(key,json.dumps(data,allow_nan=False)))
        self.db.commit()

    def rows(self):
        with self.lock:return [json.loads(r[0]) for r in self.db.execute('SELECT data FROM entries ORDER BY rowid DESC')]

    def submit_entry(self, ticket):
        with self.mutation_lock():
            key=ticket['preview_id']
            row=self.db.execute('SELECT data FROM entries WHERE id=?',(key,)).fetchone()
            if row:return json.loads(row[0])
            if not self.enabled():raise ValueError('Parser protection worker is disabled. No entry submitted.')
            account=self.broker.snapshot()
            order=dict(ticket['order'])
            if any(x['symbol']==order['symbol'] and (x.get('netQty',0)!=0) for x in account['positions']):
                raise ValueError('Existing position prevents unambiguous parser attribution.')
            if any(x['symbol']==order['symbol'] and x.get('status') not in {1,2,5,7} for x in account['orders']):
                raise ValueError('Existing pending order prevents unambiguous parser attribution.')
            if any(x.get('symbol')==order['symbol'] for x in account['gtt']):
                raise ValueError('Existing GTT protection prevents unambiguous parser attribution.')
            if any(x['order']['symbol']==order['symbol'] and x['status'] not in {'CLOSED','REJECTED'} for x in self.rows()):
                raise ValueError('An earlier parser lifecycle for this contract still needs reconciliation.')
            order['orderTag']='PR'+hashlib.sha256(key.encode()).hexdigest()[:20]
            row={'id':key,'account':account['account'],'order':order,'plan':ticket['protection'],
                 'entry_id':None,'status':'ENTRY_SUBMISSION_UNKNOWN','filled':0,'protections':[],
                 'message':'Entry intent saved; broker acceptance and fill not yet confirmed.'}
            self._save(key,row)  # durable intent before network side effect
            try:reply=self.broker.place_entry(order)
            except Exception:return row
            if reply.get('s')=='ok' and reply.get('id'):
                row.update(entry_id=str(reply['id']),status='WAITING_FOR_FILL',message='Broker accepted entry. Trigger/acceptance is not a fill; no protection yet.')
            elif reply.get('s')=='error':
                row.update(status='REJECTED',message='FYERS rejected entry; no protection created.')
            self._save(key,row);return row

    def reconcile(self, key):
        with self.mutation_lock():
            raw=self.db.execute('SELECT data FROM entries WHERE id=?',(key,)).fetchone()
            if not raw:raise ValueError('Unknown parser lifecycle.')
            row=json.loads(raw[0])
            if row['status'] in {'REJECTED','CLOSED'}:return row
            row['protected_quantity'] = 0
            try:self._reconcile(row)
            except Exception as error:
                row.update(status='RECONCILIATION_REQUIRED',message=str(error) if isinstance(error,ValueError) else 'Broker reconciliation unavailable; no new exit submitted.')
            self._save(key,row);return row

    def _reconcile(self,row):
        account=self.broker.snapshot();order=row['order'];plan=row['plan']
        if account['account']!=row['account']:raise ValueError('Broker account changed; lifecycle paused.')
        matches=[x for x in account['orders'] if (row['entry_id'] and str(x.get('id'))==row['entry_id']) or str(x.get('orderTag','')).split(':')[-1]==order['orderTag']]
        if len(matches)!=1:raise ValueError('Entry not uniquely reconciled by broker ID/tag; no retry.')
        entry=matches[0]
        for field in ['symbol','side','qty','productType']:
            if entry.get(field)!=order[field]:raise ValueError('Broker entry identity mismatch.')
        row['entry_id']=str(entry['id'])
        filled=int(entry['filledQty'])
        if not row['filled']<=filled<=order['qty']:raise ValueError('Inconsistent cumulative entry fill.')
        row['filled']=filled
        if not filled:
            row.update(status='CLOSED' if entry['status'] in {1,5,7} else 'WAITING_FOR_FILL',message='No confirmed fill; no protective order submitted.')
            return
        positions=[x for x in account['positions'] if x['symbol']==order['symbol'] and x['productType']==order['productType']]
        net=sum(int(x['netQty']) for x in positions)
        if net!=order['side']*filled:
            raise ValueError('Open position differs from attributed fills. Check exits/external trades and outstanding GTTs; no new protection submitted.')
        protected=0
        for intent in row['protections']:
            if not intent.get('broker_id'):raise ValueError('Protection submission outcome unknown; inspect broker GTT book. Never resend automatically.')
            matches=[x for x in account['gtt'] if str(x.get('id'))==intent['broker_id']]
            if len(matches)!=1:raise ValueError('Protective OCO missing from broker reconciliation; no replacement sent.')
            gtt=matches[0]
            if gtt.get('symbol')!=order['symbol'] or gtt.get('side')!=-order['side'] or gtt.get('productType')!=order['productType'] or gtt.get('orderInfo')!=intent['payload']['orderInfo']:
                raise ValueError('Protective OCO identity/terms changed or unsupported response schema.')
            if gtt.get('ord_status')!=6:raise ValueError('OCO is no longer pending. Reconcile triggered child order/fills before further protection; not certified protected.')
            protected+=intent['quantity']
        delta=filled-protected
        row['protected_quantity']=protected
        if delta==0:
            row.update(status='PROTECTED',message='Broker OCO verified pending for attributed open quantity; fills are not guaranteed.');return
        if delta<0 or delta%plan['lot_size']:raise ValueError('Unprotected partial fill is not a whole broker lot; manual protection review required.')
        if not self.enabled():
            row.update(status='FILLED_UNPROTECTED',message='Confirmed fill, but protection worker is disabled.');return
        ltp=self.broker.fresh_price(order['symbol'])
        if not min(plan['stop'],plan['target'])<ltp<max(plan['stop'],plan['target']):
            raise ValueError('Price already crossed a protection level. No late OCO or market exit inferred.')
        high,low=sorted([(plan['target'],plan['target']),(plan['stop'],plan['stop_limit'])],reverse=True)
        payload={'symbol':order['symbol'],'side':-order['side'],'productType':order['productType'],
                 'orderInfo':{'leg1':{'triggerPrice':high[0],'price':high[1],'qty':delta},'leg2':{'triggerPrice':low[0],'price':low[1],'qty':delta}}}
        intent={'quantity':delta,'payload':payload,'broker_id':None}
        row['protections'].append(intent);row.update(status='PROTECTION_SUBMISSION_UNKNOWN',message='Protection intent persisted; awaiting broker reconciliation.')
        self._save(row['id'],row)
        try:reply=self.broker.place_oco(payload)
        except Exception:return
        if reply.get('s')=='ok' and reply.get('id'):
            intent['broker_id']=str(reply['id']);row.update(status='PROTECTION_PENDING',message='OCO acknowledged; broker verification still required.')
        elif reply.get('s')=='error':
            row.update(status='PROTECTION_FAILED',message='FYERS rejected protective OCO. Filled position is not certified protected; no automatic retry.')
