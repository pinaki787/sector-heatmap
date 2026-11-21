"""Owner-bound, amount-sized manual orders across explicitly selected accounts."""
from contextlib import contextmanager
from copy import deepcopy
from decimal import Decimal, ROUND_FLOOR
import json, secrets, sqlite3, time
from pathlib import Path

def positive(value):
    try:
        result=Decimal(str(value))
        if not result.is_finite() or result<=0:raise ValueError()
        return result
    except Exception:raise ValueError('Enter a positive finite amount.') from None

def reserve(preview):
    aggregate=preview.get('aggregate') or {}
    value=aggregate.get('cash_reserved',preview.get('margin_required',preview.get('order_value',(preview.get('instrument') or {}).get('minimum_cash_required'))))
    return positive(value)

def identity(contract):
    import re
    from datetime import datetime
    expiry=contract.get('expiry') or ''
    if contract.get('expiry_epoch'):
        from zoneinfo import ZoneInfo
        expiry=datetime.fromtimestamp(float(contract['expiry_epoch']),ZoneInfo('Asia/Kolkata')).date().isoformat()
    elif expiry:
        for pattern in ('%d %b %Y','%Y-%m-%d'):
            try:expiry=datetime.strptime(expiry[:11] if pattern.startswith('%d') else expiry[:10],pattern).date().isoformat();break
            except ValueError:pass
    option=contract.get('option_type')
    if option not in ('CE','PE'):option=None
    exchange=contract.get('exchange_segment') or contract.get('exchange') or contract.get('segment') or ''
    exchange=exchange.split('_')[0].removesuffix('FO').removesuffix('CM')
    host=re.sub('[^A-Z0-9]','',str(contract.get('underlying') or '').upper())
    return dict(underlying=host,exchange=exchange,expiry=expiry if option else '',option_type=option,strike=str(positive(contract.get('strike')).normalize()) if option else '')
def sized_parser_review(account,payload,amount,call):
    if payload.get('mode','LIVE')!='LIVE':raise ValueError('Choose Live explicitly before preparing amount-based account orders.')
    budget=positive(amount);args=deepcopy(payload)
    args.pop('_manual_parser',None);args.pop('source_account_id',None);args.pop('symbol',None)
    args.update(mode='LIVE',amount_review=True,manual_amount_budget=float(budget),max_notional=float(budget))
    prefix='native-parser-' if payload.get('_source_native') and account['broker']=='DHAN' else 'parser-'
    mapped=call(account,prefix+'parse',args)
    contract=(mapped.get('mapping') or {}).get('contract')
    if not contract or identity(contract)!=payload.get('_identity'):raise ValueError('The exact source instrument does not map to the same exchange, underlying, expiry, strike and type in this account.')
    args['symbol']=contract['symbol'];args['lots']=1
    probe=call(account,prefix+'prepare',args);unit=reserve(probe)
    units=int((budget/(unit*Decimal('1.01'))).to_integral_value(rounding=ROUND_FLOOR))
    if units<1:raise ValueError('Amount cannot fund one native share or lot.')
    args['lots']=units
    final=call(account,prefix+'prepare',args);actual=reserve(final)
    if actual>budget:raise ValueError('Fresh native parser order exceeds the account amount.')
    order=final.get('order') or final.get('body') or {}
    price=order.get('limitPrice',order.get('price'))
    if price is not None and Decimal(str(price)).quantize(Decimal('.01'))!=Decimal(str(price)):
        raise ValueError('This exact executable price needs more than two decimals. Use the native ticket; no rounded order will be sent.')
    final['_submit_action']=prefix+'submit'
    return final,dict(amount=float(budget),reserved=float(actual),unspent=float(budget-actual))

def sized_review(account,payload,amount,call):
    """Size whole share/lot units using fresh native preflights, then enforce cap."""
    if payload.get('_manual_parser'):return sized_parser_review(account,payload,amount,call)
    if payload.get('mode','LIVE')!='LIVE':raise ValueError('Choose Live explicitly; Paper requests cannot be upgraded by account selection.')
    budget=positive(amount);items=deepcopy(payload.get('items') or [payload])
    if not items or len(items)>20:raise ValueError('Select between one and twenty instruments.')
    previews=[];sized=[]
    from .screener_routes import budget_slices
    slices=budget_slices(items,float(budget)) if payload.get('allocation_mode')=='CONVICTION_WEIGHTED' else [float(budget)/len(items)]*len(items)
    for item,portion in zip(items,slices):
        if item.get('mode','LIVE')!='LIVE':raise ValueError('Paper items cannot be upgraded to Live.')
        slice_budget=Decimal(str(portion))
        item.pop('allocation_budget',None)
        item.update(broker=account['broker'],account_id=account['id'],lots=1,portable_manual_ticket=True)
        kind=(item.get('proposal') or {}).get('kind')
        if kind not in ('EQUITY','LONG_OPTION'):raise ValueError('Amount sizing supports cash shares and one bought option only. This instrument needs its dedicated ticket.')
        if kind=='EQUITY':item['quantity']=1
        probe=call(account,'prepare',item)
        unit=reserve(probe)
        if probe.get('submission_eligible') is False:raise ValueError('Native account preview is not eligible for submission.')
        # Full premium and account-specific margin apply. Allow a 1% provision.
        units=int((slice_budget/(unit*Decimal('1.01'))).to_integral_value(rounding=ROUND_FLOOR))
        if units<1:raise ValueError('Amount cannot fund one valid share or lot in this account.')
        item['lots']=units
        if kind=='EQUITY':item['quantity']=units
        sized.append(item)
    final_payload=dict(items=sized,allocation_budget=float(budget),broker=account['broker'],account_id=account['id'],allocation_mode=payload.get('allocation_mode','EQUAL_ALLOCATED_FUNDS'))
    final=call(account,'prepare-batch',final_payload)
    actual=reserve(final)
    for review in final.get('items') or []:
        contracts=(review.get('instrument') or {}).get('contracts') or [review.get('body') or {}]
        for contract in contracts:
            price=contract.get('limit_price',contract.get('limitPrice'))
            if price is not None and Decimal(str(price)).quantize(Decimal('.01'))!=Decimal(str(price)):
                raise ValueError('This exact order price needs more than two decimals. Use the dedicated native ticket; no rounded order will be sent.')
    if actual>budget:raise ValueError('Fresh native order exceeds the account amount. Review a new ticket.')
    if len(final.get('items') or [])!=len(items):raise ValueError('Native review omitted an instrument; partial selection is not accepted.')
    return final,dict(amount=float(budget),reserved=float(actual),unspent=float(budget-actual))

class Tickets:
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        with self.db() as db:db.execute('CREATE TABLE IF NOT EXISTS batches(id TEXT PRIMARY KEY,owner TEXT,created REAL,data TEXT)')
        self.path.chmod(0o600)
    @contextmanager
    def db(self):
        db=sqlite3.connect(self.path,timeout=15)
        try:
            with db:yield db
        finally:db.close()
    def get(self,owner,key):
        with self.db() as db:row=db.execute('SELECT data FROM batches WHERE id=? AND owner=?',(key,str(owner))).fetchone()
        if not row:raise PermissionError('Manual batch is unavailable for this owner.')
        return json.loads(row[0])
    def history(self,owner):
        with self.db() as db:rows=db.execute('SELECT data FROM batches WHERE owner=? ORDER BY created DESC LIMIT 20',(str(owner),)).fetchall()
        return [json.loads(row[0]) for row in rows]
    def prepare(self,owner,items,resolve,call,feature='handoff'):
        if not isinstance(items,list) or not 1<=len(items)<=12:raise ValueError('Explicitly select one to twelve accounts.')
        ids=[item.get('account_id') for item in items]
        if len(set(ids))!=len(ids):raise ValueError('Select each account once.')
        accounts=[resolve(aid) for aid in ids] # all ownership checks before broker reads
        if len({a['broker'] for a in accounts})!=len(accounts):raise ValueError('Choose one explicit execution account per broker; the pool is broker-wise.')
        with self.db() as db: prior=[json.loads(r[0]) for r in db.execute('SELECT data FROM batches WHERE owner=?',(str(owner),)).fetchall()]
        for old in prior:
            if any(r['account_id'] in ids and r['state'] in ('SUBMITTING','UNCERTAIN') for r in old['rows']):
                raise ValueError('An earlier account submission needs broker reconciliation. Further batches are blocked for that account.')
        value=dict(batch_id='MULTI-'+secrets.token_hex(12),created_at=time.time(),rows=[],feature=feature)
        value['confirmation_phrase']='SUBMIT '+value['batch_id']
        for account,item in zip(accounts,items):
            row=dict(account_id=account['id'],broker=account['broker'],label=account['label'],state='BLOCKED',requested_amount=item.get('amount'))
            try:
                preview,allocation=sized_review(account,item['ticket'],item['amount'],call)
                row.update(preview=preview,submit_action=preview.get('_submit_action','submit-batch'),allocation=allocation,state='READY' if preview.get('submission_eligible') and preview.get('live_submission_enabled') else 'BLOCKED')
                if row['state']=='BLOCKED':row['error']='Live capability or native submission eligibility is disabled for this broker. Existing settings were not changed.'
            except Exception as error:row['error']=str(error)[:600]
            value['rows'].append(row)
        with self.db() as db:db.execute('INSERT INTO batches VALUES(?,?,?,?)',(value['batch_id'],str(owner),value['created_at'],json.dumps(value)))
        return value
    def submit(self,owner,key,confirmation,resolve,call):
        value=self.get(owner,key)
        if confirmation!=value['confirmation_phrase']:raise PermissionError('Confirm the exact multi-account review.')
        if time.time()-value['created_at']>120:raise ValueError('Review expired. Reconcile attempted rows before preparing another ticket.')
        for row in value['rows']:resolve(row['account_id'])
        for index,row in enumerate(value['rows']):
            with self.db() as db:
                db.execute('BEGIN IMMEDIATE')
                latest=json.loads(db.execute('SELECT data FROM batches WHERE id=? AND owner=?',(key,str(owner))).fetchone()[0])
                target=latest['rows'][index]
                if target['state']!='READY':continue
                target['state']='SUBMITTING'
                db.execute('UPDATE batches SET data=? WHERE id=?',(json.dumps(latest),key))
            try:
                account=resolve(row['account_id']);p=target['preview']
                result=call(account,target.get('submit_action','submit-batch'),dict(account_id=account['id'],broker=account['broker'],preview_id=p['preview_id'],confirmation=p['confirmation_phrase'],_source_native=target.get('submit_action','').startswith('native-parser-')))
                update=dict(state='RESULT',result=result)
            except Exception as error:update=dict(state='UNCERTAIN',error=str(error)[:600],message='Reconcile this account’s broker orders. This row cannot be resubmitted.')
            with self.db() as db:
                db.execute('BEGIN IMMEDIATE')
                latest=json.loads(db.execute('SELECT data FROM batches WHERE id=? AND owner=?',(key,str(owner))).fetchone()[0])
                latest['rows'][index].update(update)
                db.execute('UPDATE batches SET data=? WHERE id=?',(json.dumps(latest),key))
        return self.get(owner,key)

def native_route(account,action,portal_port):
    broker=account['broker'];port=account['port'];aid=account['id']
    if action=='native-description':
        if broker!='DHAN':raise ValueError('Raw security-ID review requires its owned Dhan account.')
        return port,'/api/dhan/manual-multi/describe'
    if action.startswith(('parser-','native-parser-')):
        name=action.removeprefix('native-parser-').removeprefix('parser-')
        if name not in {'parse','prepare','submit'}:raise ValueError('Unknown native parser action.')
        if broker=='DHAN':return port,'/api/dhan/manual-multi/'+name
        suffix={'parse':'parse','prepare':'prepare-order','submit':'submit-order'}[name]
        if broker=='FYERS':return port,'/api/trade-recommendation/'+suffix
        if broker=='MOTILAL_OSWAL' or broker=='DELTA_INDIA' and name=='parse':
            return portal_port,'/api/broker-parser/'+aid+'/'+suffix
        raise ValueError('This broker has no reviewed native parser entry adapter.')
    if action not in {'prepare','prepare-batch','submit','submit-batch'}:raise ValueError('Unsupported native ticket action.')
    if broker not in {'FYERS','DHAN','MOTILAL_OSWAL'}:raise ValueError('This broker has no compatible manual ticket adapter.')
    return port,('/api/motilal/trade-ticket/' if broker=='MOTILAL_OSWAL' else '/api/trade-ticket/')+action

def handle(auth,handler,mutation=False):
    path=handler.path.split('?',1)[0];prefix='/api/manual-multi/'
    if not path.startswith(prefix):return False
    try:
        from .section_permissions import allowed
        user=auth.authorize(handler.headers,mutation)
        permitted=any(allowed(user,p) for p in ('/api/trade-ticket/prepare','/api/trade-recommendation/prepare-order','/api/dhan/prepare'))
        if not permitted:raise PermissionError('Order-entry section permission required.')
        store=auth.store
        def resolve(aid):
            account=store.account(user,aid);folder=store.folder(account)
            if (folder/'disconnected.json').exists():raise PermissionError('Reconnect the selected account.')
            return account
        def call(account,action,payload):
            import http.client
            from .workspaces import WorkspaceRuntime
            if not WorkspaceRuntime(store,auth.root,auth.port).running(account['id']):raise ValueError('Account dashboard is offline. Open it before preparing orders.')
            payload=dict(payload,account_id=account['id'],broker=account['broker'])
            target_port,route=native_route(account,action,auth.port)
            host='127.0.0.1:'+str(target_port);conn=http.client.HTTPConnection('127.0.0.1',target_port,timeout=90)
            if action in {'parser-submit','native-parser-submit'}:payload=dict(payload,live_confirmation=True)
            try:
                conn.request('POST',route,json.dumps(payload),{'Host':host,'Origin':'http://'+host,'Cookie':handler.headers.get('Cookie',''),'Content-Type':'application/json'})
                response=conn.getresponse();data=json.loads(response.read(2_000_000))
                if response.status>=400:raise ValueError(data.get('error','Native account validation failed.'))
                return data
            finally:conn.close()
        tickets=Tickets(store.path.parent/'manual-multi.sqlite3')
        action=path[len(prefix):]
        def feature_allowed(feature):
            route={'handoff':'/api/trade-ticket/prepare','screener':'/api/chartink/analyze','trade-parser':'/api/trade-recommendation/prepare-order','dhan-entry':'/api/dhan/prepare'}.get(feature)
            return bool(route and allowed(user,route))
        if not mutation and action=='history':result=dict(batches=[b for b in tickets.history(user['id']) if feature_allowed(b.get('feature','handoff'))],revision='manual-multi-v1')
        elif mutation:
            payload=handler.read_json()
            if action=='prepare':
                items=payload.get('items')
                if not isinstance(items,list) or not 1<=len(items)<=12:raise ValueError('Explicit account selections required.')
                selected=[resolve(item.get('account_id')) for item in items]
                if len({a['broker'] for a in selected})!=len(selected):raise ValueError('Choose one execution account per broker before reviewing broker-wise pools.')
                feature='dhan-entry' if all((i.get('ticket') or {}).get('_native_dhan') for i in items) else 'trade-parser' if all((i.get('ticket') or {}).get('_manual_parser') for i in items) else 'screener' if payload.get('flow')=='screener' else 'handoff'
                if not feature_allowed(feature):raise PermissionError('This order-entry section is not assigned.')
                # Re-resolve the source identity from its owned native master;
                # client-supplied canonical identities never acquire authority.
                for item in items:
                    ticket=item.get('ticket') or {}
                    if ticket.get('_native_dhan'):
                        source=resolve(ticket.get('source_account_id'))
                        native=call(source,'native-description',dict(ticket.get('native_payload') or {},account_id=source['id'],broker='DHAN'))
                        ticket=dict(native,source_account_id=source['id'],_manual_parser=True)
                        item['ticket']=ticket
                    if ticket.get('_manual_parser'):
                        source=resolve(ticket.get('source_account_id'))
                        mapped=call(source,'native-parser-parse' if ticket.get('_source_native') and source['broker']=='DHAN' else 'parser-parse',dict(ticket,amount_review=True))
                        contract=(mapped.get('mapping') or {}).get('contract')
                        if not contract:raise ValueError('Resolve one exact source contract before reviewing other accounts.')
                        ticket['_identity']=identity(contract)
                result=tickets.prepare(user['id'],items,resolve,call,feature=feature)
            elif action=='submit':
                saved=tickets.get(user['id'],payload.get('batch_id'))
                if not feature_allowed(saved.get('feature','handoff')):raise PermissionError('This order-entry section is no longer assigned.')
                result=tickets.submit(user['id'],payload.get('batch_id'),payload.get('confirmation'),resolve,call)
            else:raise ValueError('Unknown manual batch action.')
        else:raise ValueError('Unknown manual batch action.')
        auth.json(handler,200,result)
    except PermissionError as error:auth.json(handler,403,dict(error=str(error)))
    except Exception as error:auth.json(handler,409,dict(error=str(error)))
    return True


def native_description(service,payload):
    from datetime import datetime
    from .dhan_execution import IST,contract_underlying
    if payload.get('order_type','LIMIT')!='LIMIT':raise ValueError('This amount review supports LIMIT entries only.')
    contract=service.master.resolve(dict(payload,proposal={'kind':'NATIVE'}),datetime.now(IST))
    rows=[r for r in service.master.load(datetime.now(IST)) if str(r['SEM_SMST_SECURITY_ID'])==str(contract['security_id']) and r['SEM_EXM_EXCH_ID']==contract['exchange_segment'].split('_')[0]]
    if len(rows)!=1:raise ValueError('Resolve one exact current source security ID.')
    row=rows[0];option=contract.get('option_type')
    if row['SEM_SEGMENT']!='E' and option not in ('CE','PE'):raise ValueError('This amount review has no portable futures/currency mapping. Use the native single-account ticket.')
    side=payload.get('transaction_type')
    if side not in ('BUY','SELL'):raise ValueError('Explicit order side required.')
    host=contract_underlying(row) if option in ('CE','PE') else row['SEM_TRADING_SYMBOL']
    if option in ('CE','PE'):
        expiry=datetime.fromisoformat(contract['expiry']).strftime('%d-%b-%Y').upper()
        instrument=f"{host} {expiry} {option} {contract['strike']:g}"
    else:instrument=host
    text=f"{side} {instrument} AT {positive(payload.get('limit_price'))} SL {positive(payload.get('invalidation'))} TARGET {positive(payload.get('target_price'))} {row['SEM_EXM_EXCH_ID']}"
    return dict(_manual_parser=True,_source_native=True,text=text,entry_mode='LIMIT',limit_price=payload['limit_price'],protect_after_fill=False,amount_product=payload.get('product_type'),daily_loss_limit=payload.get('daily_loss_limit',5000),idea_risk_limit=payload.get('idea_risk_limit',2000),risk_reserve=payload.get('risk_reserve',1000),external_open_risk=payload.get('external_open_risk'))
