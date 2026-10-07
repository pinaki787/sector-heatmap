"""Explicit adoption of broker-confirmed long MARGIN options; never an entry fill.

Each selection gets the existing Renko runner with its own durable state. Restart
leaves monitoring stopped. Orders and strategy transitions use the shared runner.
"""
import fcntl
from contextlib import contextmanager
import hashlib
import json
import math
import threading
import time
from copy import deepcopy
from pathlib import Path
from .runner import Runner, BaseRunner, analysis, after_cutoff


def identity(row):
    qty=float(row.get('netQty',0))
    price=float(row.get('netAvg',row.get('avgPrice',row.get('buyAvg',0))) or 0)
    if not math.isfinite(qty) or not qty.is_integer() or qty<=0 or not math.isfinite(price) or price<=0:
        raise ValueError('Only a confirmed positive whole-unit position with a valid broker average can be adopted.')
    if row.get('side') not in (None,1):raise ValueError('Broker side conflicts with positive net quantity.')
    product=row.get('productType')
    if product=='DELTA_LONG_OPTION' and (row.get('broker')!='DELTA_INDIA' or not row.get('product_id') or not row.get('quote_currency')):
        raise ValueError('Verified Delta option identity and currency required.')
    if product not in ('MARGIN','DELTA_LONG_OPTION'):
        raise ValueError('Existing Renko execution supports MARGIN options only.')
    return dict(symbol=str(row['symbol']),quantity=int(qty),entry_price=price,product=product)


def fingerprint(account,position):
    return hashlib.sha256(json.dumps([account,position],sort_keys=True).encode()).hexdigest()


class AdoptedRunner(Runner):
    def step(self):
        # Check before custom Renko exits too. A discrepancy must never send SELL.
        with self.lock:
            if self.state.get('running') and not self.state.get('pending'):
                p=self.state.get('position')
                if p:
                    try:
                        if self.clock()-getattr(self,'account_checked_at',0)>=30:
                            self.adapter.authenticated_client()
                            if getattr(self,'owner_conflict',lambda s:False)(p['symbol']):raise ValueError('Another manager or protective order claims this exposure.')
                            self.account_checked_at=self.clock()
                        rows=[v for v in self.adapter.positions() if v.get('symbol')==p['symbol'] and float(v.get('netQty',0) or 0)!=0]
                        if len(rows)!=1 or identity(rows[0])!={k:p[k] for k in ('symbol','quantity','entry_price','product')}:
                            raise ValueError('Adopted broker exposure changed.')
                    except Exception:
                        self.state.update(running=False,accepting_entries=False)
                        self.event('ADOPTION_RECONCILIATION_REQUIRED','Broker exposure or account could not be reconciled. Monitoring paused; no replacement or closing order sent.')
                        return
                elif not self.state.get('adoption_reentry'):
                    self.state.update(running=False,accepting_entries=False)
                    self.event('ADOPTION_COMPLETE','Adopted exposure closed; re-entry was disabled.')
                    return
            return super().step()


class Manager:
    def __init__(self,path,broker_factory,read_broker,account_reader,owners=lambda:[],runner_type=AdoptedRunner):
        self.path=Path(path);self.reader=read_broker;self.runner_type=runner_type
        self.position_cache=None;self.order_cache=None;self.cache_lock=threading.Lock()
        def factory():
            broker=broker_factory()
            def positions():
                with self.cache_lock:
                    now=time.monotonic()
                    if self.position_cache is None or now-self.position_cache[0]>.75:
                        self.position_cache=(now,self.reader.positions())
                    return deepcopy(self.position_cache[1])
            def fresh_orders():
                with self.cache_lock:
                    now=time.monotonic()
                    if self.order_cache is None or now-self.order_cache[0]>.75:
                        self.order_cache=(now,self.reader.orders());self.position_cache=None
                    return deepcopy(self.order_cache[1])
            broker.positions=positions;broker.orders=fresh_orders
            for action in ('place','cancel'):
                original=getattr(broker,action,None)
                if original:
                    def mutation(*args,_original=original,**kwargs):
                        try:return _original(*args,**kwargs)
                        finally:
                            with self.cache_lock:self.position_cache=None;self.order_cache=None
                    setattr(broker,action,mutation)
            return broker
        self.factory=factory
        self.account_reader=account_reader;self.owners=owners;self.lock=threading.RLock();self.runners={};self.intent_lock=threading.RLock()
        self.path.mkdir(parents=True,exist_ok=True)
        for file in self.path.glob('*.json'):
            if file.name.endswith('-settings.json'):continue
            runner=self.runner_type(self.factory(),file)
            self.guard(runner)
            self.runners[file.stem]=runner

    def guard(self,runner):
        runner.owner_conflict=lambda symbol:symbol in set(self.owners())
        original=runner.submit
        def submit(order,position,reason):
            with self.intent_lock:
                with self.cache_lock:self.position_cache=None;self.order_cache=None
                if order['side']==1 and (runner.state.get('config') or {}).get('mode')=='LIVE':
                    claimed=set(self.owners())
                    for other in list(self.runners.values()):
                        if other is runner:continue
                        p=other.state.get('position') or (other.state.get('pending') or {}).get('position')
                        if p:claimed.add(p['symbol'])
                    if order['symbol'] in claimed:raise ValueError('Another strategy owns or is entering this option; duplicate entry blocked.')
                return original(order,position,reason)
        runner.submit=submit

    def owned_symbols(self):
        return {p['symbol'] for r in self.runners.values() for p in [r.state.get('position') or (r.state.get('pending') or {}).get('position')] if p}

    def inventory(self):
        account=self.account_reader();positions=self.reader.positions();orders=self.reader.orders()
        ownership_error=None;owned=self.owned_symbols()
        if any(float(row.get('netQty',0) or 0)!=0 for row in positions):
            try:owned|=set(self.owners())
            except Exception:ownership_error='Strategy / protective-order ownership unavailable. Adoption disabled until a fresh verification succeeds.'
        result=[]
        for row in positions:
            if float(row.get('netQty',0) or 0)==0:continue
            item={k:row.get(k) for k in ('symbol','netQty','netAvg','avgPrice','buyAvg','productType','side')}
            try:
                p=identity(row)
                item.update(selection=fingerprint(account,p),eligible=not ownership_error and p['symbol'] not in owned,
                            reason=ownership_error or ('Already managed by a dashboard strategy.' if p['symbol'] in owned else 'Select to review and apply Renko settings.'))
            except (ValueError,TypeError,KeyError) as error:item.update(eligible=False,reason=str(error))
            result.append(item)
        return dict(account_identity=account,observed_at=time.time(),positions=result,ownership_error=ownership_error,
                    orders=[{k:r.get(k) for k in ('id','symbol','side','qty','filledQty','remainingQuantity','tradedPrice','productType','status')} for r in orders],
                    managers=[dict(id=k,**r.snapshot()) for k,r in self.runners.items()])

    @contextmanager
    def exclusive(self):
        with self.lock, (self.path/'adoption.lock').open('a') as handle:
            try:fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except OSError:raise ValueError('Another process is changing adoption ownership; refresh and retry.')
            try:yield
            finally:fcntl.flock(handle,fcntl.LOCK_UN)

    def control(self,payload,background=True):
        with self.exclusive():
            r=self.runners.get(str(payload.get('id','')))
            if not r:raise ValueError('Unknown adopted-position manager.')
            with r.lock:
                action=payload.get('action')
                if action=='pause':
                    r.state.update(running=False,accepting_entries=False)
                    r.event('ADOPTION_PAUSED','Monitoring paused by user; broker position and claim preserved. No square-off order requested.')
                elif action=='resume':
                    if r.state.get('running') or (r.thread and r.thread.is_alive()):raise ValueError('Manager is running or finishing shutdown.')
                    c=r.state['config'];context=r.adapter.validate_config(c)
                    if context['account_identity']!=r.state['account_identity']:raise ValueError('Broker account changed.')
                    pending=r.state.get('pending')
                    if pending:
                        matches=[v for v in r.adapter.orders() if (pending.get('id') and str(v.get('id'))==pending['id']) or str(v.get('orderTag','')).split(':')[-1]==pending['tag']]
                        expected=pending['order']
                        if len(matches)!=1 or any(matches[0].get(k)!=expected.get(k) for k in ('symbol','side','qty','productType')):
                            raise ValueError('Saved pending intent does not uniquely match the broker; no replacement order sent.')
                        preview=r.preview(c)
                        BaseRunner.start(r,dict(preview_id=preview['id'],confirmation=preview['confirmation']),False)
                        r.state['accepting_entries']=r.state.get('adoption_reentry',False) and not r.state.get('squareoff_requested');r.save()
                        if background:
                            r.thread=threading.Thread(target=r.loop,name='renko-adoption-pending-recovery',daemon=True);r.thread.start()
                        return r.snapshot()
                    pos=r.state.get('position')
                    matches=[v for v in r.adapter.positions() if v.get('symbol')==pos['symbol'] and float(v.get('netQty',0) or 0)!=0] if pos else []
                    if pos and not matches:
                        r.state.update(position=None,running=False,accepting_entries=False)
                        r.event('EXTERNAL_POSITION_CLOSED','Fresh broker evidence confirms position closed externally. Claim released; external fill/P&L remains unavailable, and no re-entry was started.')
                    else:
                        if not pos or len(matches)!=1 or identity(matches[0])!={k:pos[k] for k in ('symbol','quantity','entry_price','product')}:
                            raise ValueError('Broker quantity, average, product or side changed; manual reconciliation required.')
                        if any(v.get('symbol')==pos['symbol'] and int(v.get('status',0)) not in {1,2,5,7} for v in r.adapter.orders()):raise ValueError('External pending order blocks resume.')
                        preview=r.preview(c)
                        BaseRunner.start(r,dict(preview_id=preview['id'],confirmation=preview['confirmation']),False)
                        r.state['accepting_entries']=r.state.get('adoption_reentry',False);r.save()
                        if background:
                            r.thread=threading.Thread(target=r.loop,name='renko-adoption-recovery',daemon=True);r.thread.start()
                else:raise ValueError('Choose pause or resume.')
                return r.snapshot()

    def apply(self,payload,background=True):
        with self.intent_lock,self.exclusive():
            selected=payload.get('selections')
            if not isinstance(selected,list) or not selected or len(selected)!=len(set(selected)):
                raise ValueError('Select one or more distinct filled positions.')
            if payload.get('configuration_revision')!=self.runner_type.runtime_revision:
                raise ValueError('Reload the current strategy revision before adoption.')
            if not isinstance(payload.get('reentry_enabled'),bool):raise ValueError('Explicitly choose whether re-entry is enabled.')
            account=self.account_reader();rows=self.reader.positions();orders=self.reader.orders()
            available={}
            for row in rows:
                try:
                    p=identity(row);key=fingerprint(account,p)
                    if key in available:raise RuntimeError('Duplicate broker position identity.')
                    available[key]=p
                except (TypeError,KeyError):continue
                except ValueError:continue
            if any(k not in available for k in selected):raise ValueError('Selected exposure changed or closed. Refresh broker positions and select again.')
            candidates=[available[k] for k in selected]
            if len({p['symbol'] for p in candidates})!=len(candidates):raise ValueError('Ambiguous product/symbol selection.')
            busy=self.owned_symbols()|set(self.owners())
            prepared=[]
            for pos in candidates:
                if pos['symbol'] in busy:raise ValueError('This symbol is already managed by another strategy.')
                if any(r.get('symbol')==pos['symbol'] and int(r.get('status',0)) not in {1,2,5,7} for r in orders):
                    raise ValueError('Pending or partially filled order exists for the selected symbol; resolve its remainder first.')
                key=hashlib.sha256((account+pos['symbol']+pos['product']).encode()).hexdigest()[:24]
                file=self.path/(key+'.json')
                if file.exists():
                    saved=json.loads(file.read_text())
                    if saved.get('position') or saved.get('pending') or saved.get('running'):raise ValueError('A durable management claim already exists; use its recovery control.')
                prior=self.runners.get(key)
                if prior and (prior.state.get('running') or prior.state.get('position') or prior.state.get('pending')):raise ValueError('Position already has a management claim.')
                r=self.runner_type(self.factory(),self.path/(key+'.json'))
                settings={**payload,'mode':'LIVE'}
                preview=r.preview(settings);c=preview['config']
                if after_cutoff(r.clock(),c):raise ValueError('Selected instrument square-off cutoff has passed.')
                if preview['context']['account_identity']!=account:raise ValueError('FYERS account changed during review.')
                meta=r.adapter.contract(pos['symbol']);underlying=r.adapter.underlying(c['underlying'])
                segment='MCX_COM' if pos['symbol'].startswith('MCX:') else pos['symbol'].split(':')[0]+'_FO'
                master=next((v for v in r.adapter.rows(segment) if len(v)>16 and v[9]==pos['symbol']),None)
                if not master or master[13]!=underlying[13]:raise ValueError('Selected position is not an option on the selected underlying.')
                if pos['quantity']%meta['lot_size']:raise ValueError('Partial-lot exposure requires manual reconciliation.')
                analyzed=analysis(r.adapter.candles(c),c,r.adapter.host_tick_size(c['underlying']))
                latest=analyzed['rows'][-1]
                prepared.append((key,r,pos,meta,master,preview,latest))
            # Re-read all selected identities immediately before writing ownership.
            refreshed=self.reader.positions()
            keys={fingerprint(account,identity(v)) for v in refreshed if float(v.get('netQty',0) or 0)>0 and v.get('productType') in ('MARGIN','DELTA_LONG_OPTION')}
            latest_orders=self.reader.orders()
            if any(v.get('symbol') in {p['symbol'] for p in candidates} and int(v.get('status',0)) not in {1,2,5,7} for v in latest_orders):raise ValueError('New pending order appeared before adoption.')
            if self.account_reader()!=account or any(k not in keys for k in selected):raise ValueError('Broker account or exposure changed before adoption.')
            if any(p['symbol'] in self.owned_symbols()|set(self.owners()) for p in candidates):raise ValueError('Ownership changed during adoption review.')
            with self.cache_lock:self.position_cache=None
            results=[]
            for key,r,pos,meta,master,preview,latest in prepared:
                now=r.clock();c=preview['config']
                r.state.update(config=c,account_identity=account,run_id='RENKO-ADOPTION-'+key+'-'+str(int(now)),trades_used=1,realized_pnl=0,
                    adoption_reentry=payload['reentry_enabled'],position=dict(**meta,**{k:v for k,v in pos.items() if k not in meta},direction='BULLISH' if master[16]=='CE' else 'BEARISH',
                    opened_at=now,adopted_at=now,entry_signal_timestamp=latest['timestamp'],entry_mode='ADOPTED',strategy=r.strategy_id,
                    lifecycle_id='ADOPTED-'+key+'-'+str(int(now)),entry_origin='BROKER_POSITION_ADOPTION',trailing_config={'trailing_enabled':False}),
                    adoption_evidence=dict(position=deepcopy(pos),observed_at=now,account_identity=account),pending=None)
                r.save();self.guard(r);self.runners[key]=r
                try:
                    BaseRunner.start(r,dict(preview_id=preview['id'],confirmation=preview['confirmation']),False)
                    r.state['accepting_entries']=payload['reentry_enabled']
                    r.event('POSITION_ADOPTED','Existing broker-filled position adopted. No initial entry order submitted; selected Renko exits active.')
                except Exception:
                    for claimed in [self.runners[v['id']] for v in results]+[r]:
                        claimed.state.update(running=False,accepting_entries=False)
                        claimed.event('ADOPTION_RECONCILIATION_REQUIRED','Batch initialization failed. Ownership preserved; no monitoring loop started. Review exposure before recovery.')
                        claimed.adapter.stop();claimed.release()
                    raise
                results.append(dict(id=key,**r.snapshot()))
            if background:
                for result in results:
                    r=self.runners[result['id']]
                    r.thread=threading.Thread(target=r.loop,name='renko-adopted-'+result['id'],daemon=True);r.thread.start()
            return dict(managers=results)
