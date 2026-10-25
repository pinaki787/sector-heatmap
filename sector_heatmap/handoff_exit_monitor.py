"""Durable, exit-only coordinator for explicitly authorized FYERS Handoff receipts.

Broker linked exits remain active until a latched trigger hands over after verified
cancellation. Every mutation is persisted BEFORE the call and never blindly replayed.
No entry, free-standing SELL, blanket position exit or guessed ownership exists here.
"""
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime
import fcntl,json,math,os,sqlite3,time
from pathlib import Path
from threading import Event,Thread

REVISION='handoff-owned-exit-monitor-v1'
TERMINAL={1,2,5,7}
PENDING={3,4,6}
def numeric(v):
    if isinstance(v,bool):raise ValueError('Boolean broker quantity/price.')
    x=float(v)
    if not math.isfinite(x):raise ValueError('Nonfinite broker quantity/price.')
    return x
def integer(v):
    n=numeric(v)
    if n<0 or int(n)!=n:raise ValueError('Invalid whole broker quantity.')
    return int(n)
def stamp():return datetime.now().astimezone().isoformat()
def parent_id(row):return str(row.get('parentId') or row.get('id_parent') or '')
def cleared(row):return not any(numeric(row.get(k) or 0)!=0 for k in ('stopLoss','takeProfit'))

class Store:
    def __init__(self,folder):
        self.folder=Path(folder);self.path=self.folder/'handoff-exits.sqlite3'
        with self.db() as d:
            d.execute('CREATE TABLE IF NOT EXISTS control(id INTEGER PRIMARY KEY CHECK(id=1),body TEXT NOT NULL)')
            d.execute('CREATE TABLE IF NOT EXISTS trades(id TEXT PRIMARY KEY,body TEXT NOT NULL)')
            d.execute('CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,at REAL,trade_id TEXT,kind TEXT,body TEXT)')
            d.execute('CREATE TABLE IF NOT EXISTS quotes(symbol TEXT PRIMARY KEY,body TEXT NOT NULL)')
            d.execute('CREATE TABLE IF NOT EXISTS heartbeat(id INTEGER PRIMARY KEY CHECK(id=1),body TEXT NOT NULL)')
        self.path.chmod(0o600)
    def db(self):return sqlite3.connect(self.path,timeout=10)
    def policy(self):
        with self.db() as d:r=d.execute('SELECT body FROM control WHERE id=1').fetchone()
        return json.loads(r[0]) if r else dict(enabled=False,authorized=False)
    def authorize(self,account_id,user_id,at=None):
        # Explicit deployment action only; constructors and page loads never enable.
        p=dict(enabled=True,authorized=True,account_id=account_id,user_id=user_id,scope_start=at or time.time(),revision=REVISION,scope='Owned FYERS Auto Analysis Handoff receipts only',native_fallback=True)
        with self.db() as d:d.execute('INSERT OR REPLACE INTO control VALUES(1,?)',(json.dumps(p),))
        self.event(None,'AUTHORIZED',p);return p
    def pause(self,enabled):
        if type(enabled) is not bool:raise ValueError('Explicit monitoring enabled flag required.')
        p=self.policy()
        if not p.get('authorized'):raise PermissionError('Exit monitoring has not been explicitly authorized.')
        p['enabled']=enabled
        with self.db() as d:d.execute('UPDATE control SET body=? WHERE id=1',(json.dumps(p),))
        self.event(None,'RESUMED' if enabled else 'PAUSED',{});return p
    def rows(self):
        with self.db() as d:return [json.loads(r[0]) for r in d.execute('SELECT body FROM trades ORDER BY rowid DESC')]
    def save(self,r):
        r['updated_at']=time.time()
        with self.db() as d:d.execute('INSERT OR REPLACE INTO trades VALUES(?,?)',(r['id'],json.dumps(r,allow_nan=False)))
    def event(self,key,kind,body):
        with self.db() as d:d.execute('INSERT INTO events(at,trade_id,kind,body) VALUES(?,?,?,?)',(time.time(),key,kind,json.dumps(body,allow_nan=False)))
    def beat(self,**kw):
        with self.db() as d:d.execute('INSERT OR REPLACE INTO heartbeat VALUES(1,?)',(json.dumps(dict(at=time.time(),pid=os.getpid(),revision=REVISION,**kw)),))
    def status(self):
        p=self.policy()
        with self.db() as d:
            b=d.execute('SELECT body FROM heartbeat WHERE id=1').fetchone()
            events=[dict(at=r[0],trade_id=r[1],kind=r[2],detail=json.loads(r[3])) for r in d.execute('SELECT at,trade_id,kind,body FROM events ORDER BY id DESC LIMIT 12')]
        b=json.loads(b[0]) if b else {};fresh=time.time()-b.get('at',0)<=12
        waits=[]
        qp=self.folder/'handoff-entry-waits.sqlite3'
        if qp.exists():
            with sqlite3.connect('file:'+str(qp)+'?mode=ro',uri=True) as d:
                waits=[dict(id=r[0],state=r[1],**json.loads(r[2])) for r in d.execute('SELECT id,state,body FROM waits ORDER BY rowid DESC LIMIT 20')]
        return dict(entry_waits=waits,revision=REVISION,policy=p,heartbeat=b,heartbeat_fresh=fresh,state='PAUSED' if not p.get('enabled') else b.get('state','STARTING') if fresh else 'HEARTBEAT_STALE',trades=self.rows()[:100],events=events,limits='Fresh streamed exact-instrument price required. Broker native exits remain fallback until confirmed handover. No guaranteed price/fill; broker credentials and server must work. No EOD or expiry exit policy is added.')
    def guard_new_entry(self):
        if not self.policy().get('authorized'):return
        s=self.status()
        if not s['policy'].get('enabled') or not s['heartbeat_fresh'] or not s['heartbeat'].get('healthy'):
            raise PermissionError('Handoff exit monitor is paused, stale or unhealthy; new entries withheld.')
        if any(r.get('state') in ('REVIEW','DETACHING','CANCELLING_ENTRY','EXIT_REQUESTED','EXIT_PENDING','UNCERTAIN') for r in s['trades']):
            raise PermissionError('An owned exit requires reconciliation before another Handoff entry.')

class Monitor:
    def __init__(self,store,broker,clock=time.time):self.store,self.broker,self.clock=store,broker,clock
    def state(self,r,state,reason,**kw):
        changed=r.get('state')!=state or r.get('reason')!=reason
        r.update(state=state,reason=reason,**kw);self.store.save(r)
        if changed:self.store.event(r['id'],state,dict(reason=reason))
    def sync(self):
        p=self.store.policy();path=self.store.folder/'handoff-schedule.sqlite3'
        if not path.exists():return
        known={r['id']:r for r in self.store.rows()}
        with sqlite3.connect('file:'+str(path)+'?mode=ro',uri=True) as d:rows=d.execute('SELECT fingerprint,state,body FROM receipts').fetchall()
        for key,state,body in rows:
            if (key in known and known[key].get('entry_id')) or state in ('NOT_SUBMITTED','CLOSED'):continue
            try:
                receipt=json.loads(body);plan=receipt['plan'];result=receipt.get('result') or {}
                intent=json.loads((self.store.folder/'handoff-intents'/(key+'.json')).read_text())
                if intent.get('account_id')!=p.get('account_id') or intent.get('created',0)<p.get('scope_start',float('inf')):continue
                if plan.get('kind') not in ('EQUITY','LONG_OPTION') or (plan.get('ticket_payload',{}).get('analysis_evidence') or {}).get('source')!='ANALYSIS_HANDOFF':continue
                if plan.get('ticket_payload',{}).get('handoff_auto') is not True:continue
                ids=list(map(str,result.get('order_ids') or []))
                if len(ids)!=1:
                    # No guessed symbol matching after a timeout. Refreshing the
                    # exact persisted entry result may supply the original id later.
                    ident=intent.get('preview_id','');base=Path(os.getenv('XDG_CONFIG_HOME',str(Path.home()/'.config')))
                    archive=self.broker.entry_result(ident)
                    ids=list(map(str,(archive or {}).get('order_ids') or []))
                    if len(ids)!=1 and key in known:continue
                qty=integer(plan['quantity']);stop=numeric(plan['stop']);target=numeric(plan['target']);entry=numeric(plan['entry'])
                side=1 if plan['kind']=='LONG_OPTION' or plan['direction']=='BULLISH' else -1
                if not qty or not (0<stop<entry<target if side==1 else 0<target<entry<stop):raise ValueError('Invalid accepted execution levels.')
                product=result.get('actual_product') or ('MARGIN' if plan['kind']=='LONG_OPTION' else plan.get('ticket_payload',{}).get('cash_product','INTRADAY'))
                r=dict(id=key,symbol=plan['symbol'],underlying=plan['underlying'],product=product,quantity=qty,side=side,stop=stop,target=target,entry_id=ids[0] if len(ids)==1 else None,preview_id=intent.get('preview_id'),created_at=self.clock(),state='ENTRY_PENDING',reason='Await exact broker entry fill.',execution_levels_source='Accepted reserved execution plan; report horizon scenarios are excluded',entry_condition=plan.get('entry_condition'),entry_order=plan.get('ticket_payload',{}).get('execution_entry_order',{'type':'LIMIT'}),entry_expires_at=plan.get('ticket_payload',{}).get('entry_valid_until'),actions={},rejected_attempt_ids=[str(i) for a in result.get('product_attempts',[]) if a.get('status')=='REJECTED' for i in a.get('order_ids',[])])
                self.store.save(r);self.store.event(key,'REGISTERED',dict(entry_id=r['entry_id'],symbol=r['symbol'],quantity=qty,stop=stop,target=target))
            except (ValueError,KeyError,TypeError,OSError):continue
    def action(self,r,key,call):
        if not self.store.policy().get('enabled') or not self.broker.allowed(self.store.policy()):
            self.state(r,'PAUSED','Application exit action blocked by current monitor authorization/live gate.');return False
        if key in r['actions']:return False
        r['actions'][key]=dict(at=self.clock(),outcome='REQUESTED');self.store.save(r);self.store.event(r['id'],'ACTION_REQUESTED',dict(action=key))
        try:
            response=call()
            # Do not save arbitrary broker responses or secrets.
            ok=isinstance(response,dict) and response.get('s')=='ok' and response.get('code')!=201
            r['actions'][key].update(outcome='ACKNOWLEDGED' if ok else 'UNCERTAIN',code=response.get('code') if isinstance(response,dict) else None)
        except Exception:r['actions'][key]['outcome']='UNCERTAIN'
        self.store.save(r);return True
    def inspect(self,r,s):
        if not r.get('entry_id'):raise ValueError('Entry identity uncertain; broker reconciliation is required before an owned price exit can be attributed.')
        orders=s['orders'];positions=s['positions']
        parent=[v for v in orders if str(v.get('id'))==r['entry_id']]
        if len(parent)>1:raise ValueError('Ambiguous exact entry id.')
        parent=parent[0] if parent else None
        if parent:
            if parent.get('symbol')!=r['symbol'] or parent.get('productType')!=r['product'] or integer(parent.get('qty'))!=r['quantity'] or numeric(parent.get('side'))!=r['side']:raise ValueError('Entry contract, side, product or quantity mismatch.')
            filled=integer(parent.get('filledQty'));remaining=integer(parent.get('remainingQuantity'))
            if filled+remaining>r['quantity']:raise ValueError('Inconsistent entry fill quantities.')
            status=integer(parent.get('status'))
            if status not in TERMINAL|PENDING:raise ValueError('Unknown entry status.')
            live_entry=status in PENDING and remaining>0
            if filled:
                r.update(entry_filled=filled,entry_average=numeric(parent.get('tradedPrice')),entry_terminal=not live_entry)
                if r['entry_average']<=0:raise ValueError('Positive entry fill average required.')
            else:r.update(entry_filled=0,entry_terminal=not live_entry)
        elif not r.get('entry_terminal'):raise ValueError('Entry absent from broker book before terminal fill confirmation.')
        else:live_entry=False
        children=[v for v in orders if parent_id(v)==r['entry_id'] and v.get('symbol')==r['symbol'] and v.get('productType')==r['product']]
        for v in children:
            if numeric(v.get('side'))!=-r['side']:raise ValueError('Linked exit side mismatch.')
        # Any unowned same-position order is a competing mutation, even one the
        # broker already filled. Never assume that all net quantity belongs to us.
        foreign=[v for v in orders if v.get('symbol')==r['symbol'] and v.get('productType')==r['product'] and str(v.get('id'))!=r['entry_id'] and parent_id(v)!=r['entry_id'] and str(v.get('id')) not in r.get('exit_order_ids',[])]
        prior={v.get('entry_id') for v in self.store.rows() if v.get('state')=='CLOSED' and v.get('id')!=r['id'] and v.get('closed_at',float('inf'))<r.get('created_at',0)}
        foreign=[v for v in foreign if not (integer(v.get('status')) in TERMINAL and (str(v.get('id')) in prior or parent_id(v) in prior))]
        if foreign and not ('exit' in r['actions'] and all(integer(v.get('status')) in TERMINAL for v in foreign)):raise ValueError('Unattributed same-contract/product orders require ownership review.')
        exited=sum(integer(v.get('filledQty',0)) for v in children)
        exited+=sum(integer(v.get('filledQty',0)) for v in orders if str(v.get('id')) in r.get('exit_order_ids',[]) and v not in children)
        owned=r.get('entry_filled',0)-exited
        if owned<0:raise ValueError('Exit fills exceed owned entry quantity; no further exit.')
        pos=[v for v in positions if v.get('symbol')==r['symbol'] and v.get('productType')==r['product'] and numeric(v.get('netQty',0))!=0]
        if len(pos)>1:raise ValueError('Multiple same-product positions are ambiguous.')
        pos=pos[0] if pos else None
        net=numeric(pos.get('netQty')) if pos else 0
        if net!=owned*r['side']:
            # An id-scoped broker exit can be reflected in positions before its
            # order appears. Flat is safe, but P&L remains unverified.
            if not (net==0 and 'exit' in r['actions'] and not live_entry):raise ValueError('Broker net position differs from attributed owned fills.')
        if pos and (not pos.get('id') or pos['id']!=r['symbol']+'-'+r['product']):raise ValueError('Exact broker position id is unavailable.')
        return parent,live_entry,children,pos,owned
    def step_trade(self,r,s,enabled):
        if r.get('state')=='CLOSED':return
        parent,live_entry,children,pos,owned=self.inspect(r,s)
        active_children=[v for v in children if integer(v.get('status')) in PENDING]
        if pos is None and not live_entry:
            if active_children:raise ValueError('Flat position still has linked pending exits; cleanup needs review.')
            r['closed_at']=self.clock();r['owned_remaining']=0
            fills=[v for v in children if integer(v.get('filledQty',0))]
            fills += [v for v in s['orders'] if str(v.get('id')) in r.get('exit_order_ids',[]) and integer(v.get('filledQty',0))]
            if fills and sum(integer(v.get('filledQty',0)) for v in fills)==r.get('entry_filled',0):
                r['gross_realized_pnl']=round(sum((numeric(v['tradedPrice'])-r['entry_average'])*integer(v['filledQty'])*r['side'] for v in fills),2)
                r['pnl_basis']='Exact broker linked/exit fill averages; fees unavailable, net withheld'
            else:r.update(gross_realized_pnl=None,pnl_basis='Broker flat confirmed; exact exit-fill attribution/P&L unavailable')
            self.broker.release(r);self.state(r,'CLOSED','Broker confirmed flat with no outstanding entry or linked exits.');return
        r['owned_remaining']=owned
        if live_entry and not owned and enabled and r.get('entry_condition'):
            from .handoff_entry_conditions import reached
            c=r['entry_condition'];q=self.broker.quote(c['symbol'])
            q=dict(q or {},symbol=c['symbol'])
            met,reason=reached(c,q,self.clock())
            fresh=q.get('connected') and 0<=self.clock()-numeric(q.get('provider_at',0))<=5 and 0<=self.clock()-numeric(q.get('received_at',0))<=5
            if r.get('entry_order',{}).get('type')=='STOP_LIMIT':
                price=numeric(q.get('price',0));level=numeric(c['level'])
                invalid=not fresh or (price>level*1.005 if c['operator']=='AT_OR_ABOVE' else price<level*.995)
            else:invalid=not met
            if invalid and (fresh or self.clock()-r.get('created_at',self.clock())>8):
                self.state(r,'CANCELLING_ENTRY','Unfilled entry condition no longer valid/fresh; cancel only the exact pending order and reconcile a fill race.')
                self.action(r,'cancel_entry',lambda:self.broker.cancel_entry(r));return
        if not owned:
            if live_entry and enabled and r.get('entry_expires_at') and self.clock()>=r['entry_expires_at']:
                self.state(r,'CANCELLING_ENTRY','Unfilled recommendation entry expired; cancel only its exact pending order and reconcile any fill race.')
                self.action(r,'cancel_entry',lambda:self.broker.cancel_entry(r));return
            self.state(r,'ENTRY_PENDING','Entry is pending; no unfilled quantity is exited.');return
        if not enabled:self.state(r,'PAUSED','Application monitoring paused. Broker orders remain independent.');return
        if not self.broker.session_open():self.state(r,'WAITING_SESSION','Market closed; no application exit submitted.');return
        if 'exit' in r['actions']:
            self.state(r,'EXIT_PENDING' if r['actions']['exit']['outcome']=='ACKNOWLEDGED' else 'UNCERTAIN','Exit requested once; waiting for broker-confirmed flat. No replay.');return
        if not r.get('trigger'):
            q=self.broker.quote(r['symbol'])
            if not q or not q.get('connected') or not 0<=self.clock()-numeric(q.get('received_at',0))<=5 or not 0<=self.clock()-numeric(q.get('provider_at',0))<=5:
                self.state(r,'PRICE_STALE','Fresh streamed exact-instrument price unavailable; native exits remain fallback.');return
            price=numeric(q.get('price'));r.update(last_price=price,last_price_at=q['provider_at'])
            if price<=0:raise ValueError('Invalid streamed instrument price.')
            hit_stop=price<=r['stop'] if r['side']==1 else price>=r['stop']
            hit_target=price>=r['target'] if r['side']==1 else price<=r['target']
            if not hit_stop and not hit_target:self.state(r,'PARTIAL_FILL' if live_entry else 'MONITORING','Watching accepted execution target and stop.');return
            r.update(trigger='STOP_LOSS' if hit_stop else 'TARGET',trigger_price=price,trigger_at=self.clock());self.store.save(r);self.store.event(r['id'],'TRIGGERED',dict(reason=r['trigger'],price=price))
        if hasattr(self.broker,'preflight_takeover'):self.broker.preflight_takeover(r,pos)
        # Freeze the unfilled entry before taking over exits. A fill/cancel race is
        # reconciled on a subsequent independent snapshot, never guessed.
        if live_entry:
            self.state(r,'CANCELLING_ENTRY','Trigger latched; cancel only the exact remaining entry before exit.')
            self.action(r,'cancel_entry',lambda:self.broker.cancel_entry(r));return
        if 'detach' not in r['actions']:
            self.state(r,'DETACHING','Trigger latched; removing only this owned position linked exits before takeover.')
            self.action(r,'detach',lambda:self.broker.detach(r,pos,parent));return
        if r['actions']['detach']['outcome']!='ACKNOWLEDGED':raise ValueError('Linked-exit cancellation outcome uncertain; no application exit replay or takeover.')
        if active_children or (parent and integer(parent.get('status')) in (2,4,6) and not cleared(parent)) or (pos and not cleared(pos)):
            self.state(r,'DETACHING','Waiting for broker evidence that linked exits are removed; no competing exit submitted.');return
        # Read again after cancellation and immediately before the id-scoped exit.
        fresh=self.broker.snapshot();parent,live_entry,children,pos,owned=self.inspect(r,fresh)
        if not pos:self.state(r,'RECONCILING','Broker may have closed during handover; await flat reconciliation.');return
        if live_entry or any(integer(v.get('status')) in PENDING for v in children) or (parent and integer(parent.get('status')) in (2,4,6) and not cleared(parent)) or not cleared(pos):raise ValueError('Competing entry/exit remained active after handover.')
        if numeric(pos['netQty'])!=owned*r['side'] or owned<=0:raise ValueError('Owned quantity changed before exit.')
        # Exit-position-by-id can close only that remaining broker position. It
        # cannot create a reverse SELL position if a broker exit won the race.
        self.state(r,'EXIT_REQUESTED','Requesting exact owned broker position exit; no free-standing SELL.')
        self.action(r,'exit',lambda:self.broker.exit_position(r,pos))
    def cycle(self):
        p=self.store.policy()
        if not p.get('authorized'):self.store.beat(state='NOT_AUTHORIZED',healthy=False);return
        self.sync();rows=[r for r in self.store.rows() if r.get('state')!='CLOSED']
        wait_symbols=[]
        qp=self.store.folder/'handoff-entry-waits.sqlite3'
        if qp.exists():
            with sqlite3.connect('file:'+str(qp)+'?mode=ro',uri=True) as d:
                for raw, in d.execute("SELECT body FROM waits WHERE state='WAITING'"):
                    b=json.loads(raw)
                    if b.get('expires_at',0)>self.clock():wait_symbols.append(b['condition']['symbol'])
        self.broker.subscribe(sorted({r['symbol'] for r in rows}|{r['entry_condition']['symbol'] for r in rows if r.get('entry_condition') and not r.get('entry_terminal')}|set(wait_symbols)))
        for symbol in wait_symbols:
            q=self.broker.quote(symbol)
            if q:
                with self.store.db() as d:d.execute('INSERT OR REPLACE INTO quotes VALUES(?,?)',(symbol,json.dumps(dict(q,symbol=symbol))))

        if not rows:self.store.beat(state=('WAITING_ENTRY_TRIGGER' if wait_symbols else 'IDLE') if p.get('enabled') else 'PAUSED',healthy=bool(p.get('enabled')),active=0,waiting_entries=len(wait_symbols));return
        if not self.broker.allowed(p):self.store.beat(state='AUTH_OR_LIVE_GATE_REQUIRED',healthy=False,active=len(rows));return
        try:s=self.broker.snapshot()
        except Exception:self.store.beat(state='BROKER_UNAVAILABLE',healthy=False,active=len(rows));return
        healthy=True
        for r in rows:
            try:self.step_trade(r,s,p.get('enabled',False))
            except (ValueError,KeyError,TypeError) as e:self.state(r,'REVIEW',str(e));healthy=False
            except Exception:self.state(r,'REVIEW','Owned exit integration failed; reconcile broker before another mutation.');healthy=False
            if r.get('state') in ('REVIEW','PRICE_STALE','UNCERTAIN'):healthy=False
        self.store.beat(state='MONITORING' if healthy else 'ATTENTION_REQUIRED',healthy=healthy,active=sum(r.get('state')!='CLOSED' for r in rows))

class Service:
    def __init__(self,folder,broker):self.store=Store(folder);self.engine=Monitor(self.store,broker);self.stopping=Event();self.thread=None
    def start(self):
        if self.thread and self.thread.is_alive():return
        def run():
            with open(self.store.folder/'handoff-exits.lock','a') as lock:
                try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                except BlockingIOError:return
                while not self.stopping.is_set():
                    try:self.engine.cycle()
                    except Exception:self.store.beat(state='INTEGRATION_ERROR',healthy=False)
                    self.stopping.wait(2)
                self.engine.broker.close()
        self.thread=Thread(target=run,daemon=True,name='owned-handoff-exits');self.thread.start()
    def close(self):self.stopping.set();self.engine.broker.close()
