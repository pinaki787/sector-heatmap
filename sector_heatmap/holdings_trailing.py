"""Explicit-consent, durable Dhan holding-stop ratchet. Never auto-resumes."""
from copy import deepcopy
from datetime import datetime,timezone
from pathlib import Path
import json,os,secrets,threading,time
from .config import _atomic_private_write
from .file_lock import lock_file,unlock_file
from .holdings_actions import decimal,digest
from .holdings_analysis import HoldingsAnalysis,IST
from .native_holdings import DhanHoldings
from .market_calendar import market_session
from .holdings_sessions import window
from .persistent_jobs import JobCancelled,JobInterrupted

POLICY='Recalculate the same completed-daily technical recommendation. Tighten protection only: raise long stops or lower short stops. Never loosen protection or submit discretionary market exits.'
ACTIVE={'ENABLING','MONITORING','CHECKING','STOPPING','SLEEPING'}
def interval(value):
    if type(value) is not int or value not in (30,60):raise ValueError('Choose 30 minutes or one hour.')
    return value

class HoldingTrails:
    def __init__(self,execution,actions,store,clock=time.time):
        self.e=execution;self.actions=actions;self.store=store;self.clock=clock;self.guard=threading.RLock();self.previews={}
        if not hasattr(store,'wake_events'):store.wake_events={}
        self.folder=execution.folder/'source/.private/holding-trails'
    def path(self,mid):
        if not isinstance(mid,str) or not mid.startswith('TRAIL-') or len(mid)!=22 or any(c not in '0123456789ABCDEF' for c in mid[6:]):
            raise ValueError('Invalid trailing monitor identity.')
        return self.folder/mid/'state.json'
    def save(self,state):
        p=self.path(state['monitor_id']);p.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        with self.guard:
            fd=os.open(p.parent/'state-write.lock',os.O_CREAT|os.O_RDWR,0o600)
            try:
                lock_file(fd,blocking=True)
                if p.exists():
                    prior=json.loads(p.read_text())
                    state['stop_requested']=bool(state.get('stop_requested') or prior.get('stop_requested'))
                    if prior.get('interval_revision',0)>state.get('interval_revision',0):
                        for key in ('interval_minutes','interval_revision','interval_changed_at'):
                            state[key]=prior.get(key)
                        if state.get('running'):state['next_check_at']=prior.get('next_check_at')
                state['updated_at']=self.clock()
                _atomic_private_write(p,json.dumps(state,allow_nan=False))
            finally:unlock_file(fd);os.close(fd)
    def event(self,state,event,**fields):
        path=self.path(state['monitor_id']).parent/'events.jsonl'
        with path.open('a') as f:f.write(json.dumps(dict(at=self.clock(),event=event,**fields),allow_nan=False)+'\n')
        os.chmod(path,0o600)
    def lock(self,security,segment):
        # One writer per account/native instrument, including across root and isolated workers.
        name=digest([str(security),segment])[:24]
        p=self.e.folder/('holding-trail-'+name+'.lock')
        fd=os.open(p,os.O_CREAT|os.O_RDWR,0o600)
        try:lock_file(fd,blocking=False)
        except OSError:os.close(fd);raise ValueError('A trailing monitor already owns this holding.') from None
        return fd
    def load(self,owner,mid):
        state=json.loads(self.path(mid).read_text())
        if state.get('owner')!=owner or state.get('account_id')!=self.e.account['id']:raise PermissionError('Monitor belongs to another user/account.')
        return state
    def list(self,owner):
        result=[]
        for p in sorted(self.folder.glob('*/state.json'),key=lambda p:p.stat().st_mtime,reverse=True)[:100]:
            state=json.loads(p.read_text())
            if state.get('owner')!=owner:continue
            if state.get('running'):
                try:fd=self.lock(state['security_id'],state['exchange_segment'])
                except ValueError:pass
                else:
                    try:
                        state.update(running=False,status='INTERRUPTED',message='Monitor process ended. The broker stop is retained; review and explicitly enable again.')
                        self.save(state)
                    finally:unlock_file(fd);os.close(fd)
            result.append(state)
        return result
    def managed(self,row,owner):
        meta=row.get('native_identity') or {};candidates={}
        for state in self.list(owner):
            stop=state.get('managed_stop')
            if stop and state.get('security_id')==str(meta.get('securityId')) and state.get('exchange_segment')==meta.get('exchangeSegment'):
                if state.get('pending'):raise ValueError('An earlier trailing request is uncertain. Reconcile it before enabling again.')
                if state.get('running'):raise ValueError('This holding already has an active trailing monitor.')
                candidates[stop['order_id']]=stop
        for p in (self.e.folder/'holding-actions').glob('*.json'):
            saved=json.loads(p.read_text());ticket=saved.get('ticket') or {}
            if str(ticket.get('securityId'))==str(meta.get('securityId')) and ticket.get('exchangeSegment')==meta.get('exchangeSegment') and saved.get('endpoint')=='/forever/orders' and saved.get('order_id'):
                candidates.setdefault(str(saved['order_id']),dict(order_id=str(saved['order_id']),ticket=ticket,correlation_id=ticket.get('correlationId')))
        if len(candidates)>1:raise ValueError('Multiple previously owned stops need broker reconciliation.')
        return deepcopy(next(iter(candidates.values()))) if candidates else None
    def preview(self,owner,report,row,payload):
        if row.get('action')!='TRAIL':raise ValueError('A fresh TRAIL recommendation is required to enable automatic trailing.')
        minutes=interval(payload.get('interval_minutes',60))
        managed=self.managed(row,owner)
        plan=self.actions._plan(report,row,{},managed)
        pid='TRAILPREVIEW-'+secrets.token_hex(8).upper()
        view={**plan,'preview_id':pid,'confirmation_phrase':'ENABLE TRAILING '+pid,'expires_at':self.clock()+120,
              'interval_minutes':minutes,'policy':POLICY,'existing_stop':bool(managed),
              'stop_behavior':'Stopping monitoring retains the last broker stop; it does not cancel protection or sell the holding.'}
        with self.guard:
            self.previews={k:v for k,v in self.previews.items() if v['view']['expires_at']>self.clock()}
            self.previews[pid]=dict(owner=owner,view=deepcopy(view),report=deepcopy(report),row=deepcopy(row),managed=managed)
        return view
    def enable(self,owner,pid,confirmation,consent):
        with self.guard:
            stored=self.previews.get(pid)
            if not stored or stored['owner']!=owner or stored['view']['expires_at']<self.clock():raise ValueError('Trailing preview expired or belongs to another account.')
            if consent is not True or confirmation!=stored['view']['confirmation_phrase']:raise ValueError('Explicit automatic-order consent and exact typed confirmation are required.')
            if not self.e.account.get('live_enabled') or not self.e.execution_allowed():raise PermissionError('Live execution is disabled.')
            meta=stored['row']['native_identity'];fd=self.lock(meta['securityId'],meta['exchangeSegment'])
            mid='TRAIL-'+secrets.token_hex(8).upper()
            state=dict(monitor_id=mid,owner=owner,account_id=self.e.account['id'],broker=getattr(self.actions,'broker','DHAN'),symbol=stored['row']['symbol'],
                security_id=str(meta['securityId']),exchange_segment=meta['exchangeSegment'],quantity=stored['row']['quantity'],
                currency=stored['row'].get('currency','INR'),average_price=stored['row']['average_price'],holding_type=stored['row']['holding_type'],interval_minutes=stored['view']['interval_minutes'],
                running=True,status='ENABLING',stop_requested=False,pending=None,managed_stop=stored['managed'],
                created_at=self.clock(),heartbeat_at=self.clock(),last_checked_at=None,next_check_at=None,policy=POLICY,
                message='Explicit enable consent recorded; validating initial broker protection.',consent=dict(preview_id=pid,at=self.clock()))
            self.save(state);del self.previews[pid]
            self.store.wake_events[mid]=threading.Event()
            request=dict(path=getattr(self,'action_route','/api/dhan/holdings-analysis/trail-enable'),account_id=self.e.account['id'],
                         payload=dict(broker=state['broker'],account_id=self.e.account['id'],monitor_id=mid,interval_minutes=state['interval_minutes']))
            try:
                job=self.store.submit(owner,'RUNNER','holdings',state['symbol']+' · Automatic trailing',request,
                    lambda ctx:self.run(ctx,state,stored,fd),mid)
            except Exception:
                state.update(running=False,status='FAILED',message='Monitor could not be queued; no order sent.');self.save(state)
                self.store.wake_events.pop(mid,None)
                unlock_file(fd);os.close(fd);raise
            future=self.store.futures.get(job['job_id'])
            if future:
                def cancelled_before_start(completed):
                    if completed.cancelled():
                        state.update(running=False,status='STOPPED',message='Stopped before enablement; no broker order was sent.')
                        self.save(state);self.store.wake_events.pop(mid,None);unlock_file(fd);os.close(fd)
                future.add_done_callback(cancelled_before_start)
            return dict(monitor_id=mid,job_id=job['job_id'],status=job['status'],message='Trailing enablement accepted. The identified monitor continues after leaving this page.')
    def stopped(self,state):
        saved=json.loads(self.path(state['monitor_id']).read_text())
        return bool(saved.get('stop_requested'))
    def assert_live(self):
        if not self.e.account.get('live_enabled') or not self.e.execution_allowed():raise PermissionError('Live execution is disabled or halted.')
    def confirm_stop(self,state,ticket,order_id,correlation):
        rows=self.e._client().request('GET','/forever/orders')
        if not isinstance(rows,list):raise ValueError('Broker stop reconciliation is unavailable.')
        found=[r for r in rows if str(r.get('orderId'))==str(order_id)]
        if len(found)!=1:raise ValueError('Broker stop acknowledgement could not be reconciled. No automatic retry.')
        r=found[0]
        if str(r.get('dhanClientId',self.e._client().client_id))!=str(self.e._client().client_id):raise PermissionError('Broker stop belongs to another account.')
        for key in ('securityId','exchangeSegment','productType','transactionType'):
            if str(r.get(key))!=str(ticket[key]):raise ValueError('Broker stop identity changed.')
        for key in ('quantity','price','triggerPrice'):
            if decimal(r.get(key))!=decimal(ticket[key]):raise ValueError('Broker stop levels or quantity are unconfirmed. No automatic retry.')
        if r.get('orderStatus') not in ('PENDING','CONFIRM') or (r.get('orderFlag') or r.get('orderType'))!='SINGLE':
            raise ValueError('Broker stop is not confirmed active.')
        if r.get('correlationId') and r['correlationId']!=correlation:raise ValueError('Broker stop ownership differs.')
        return dict(order_id=str(order_id),ticket=deepcopy(ticket),correlation_id=correlation)
    def transmit(self,state,plan,create=False):
        if state.get('pending'):raise ValueError('An earlier broker request is uncertain; reconcile it before any new update.')
        if self.stopped(state):return False
        self.assert_live()
        ips=self.e._client().request('GET','/ip/getIP')
        if self.e.egress() not in (ips.get('primaryIP'),ips.get('secondaryIP')):raise PermissionError('Server IP is not whitelisted.')
        old=state.get('managed_stop')
        ticket=deepcopy(plan['ticket'])
        if not create:
            old_trigger=decimal(old['ticket']['triggerPrice'])
            if decimal(ticket['triggerPrice'])<=old_trigger:
                state['managed_stop']=self.confirm_stop(state,old['ticket'],old['order_id'],old['correlation_id'])
                return False
            payload={k:ticket[k] for k in ('orderFlag','orderType','quantity','price','disclosedQuantity','triggerPrice','validity')}
            payload.update(dhanClientId=self.e._client().client_id,orderId=old['order_id'],legName='TARGET_LEG')
            method='PUT';endpoint='/forever/orders/'+old['order_id'];correlation=old['correlation_id']
        else:
            correlation=state['monitor_id'];payload={**ticket,'correlationId':correlation}
            method='POST';endpoint='/forever/orders'
        if self.stopped(state):return False
        state['pending']=dict(method=method,endpoint=endpoint,payload=payload,at=self.clock())
        self.save(state);self.event(state,'BROKER_REQUEST',method=method,endpoint=endpoint,ticket=ticket)
        response=self.e._client().request(method,endpoint,payload)
        order_id=(response or {}).get('orderId') if isinstance(response,dict) else None
        if not order_id or (old and str(order_id)!=old['order_id']):raise ValueError('Broker update outcome is uncertain. No automatic retry.')
        state['managed_stop']=self.confirm_stop(state,ticket,str(order_id),correlation)
        state['pending']=None;self.save(state)
        self.event(state,'STOP_CONFIRMED',order_id=str(order_id),trigger=ticket['triggerPrice'],limit=ticket['price'])
        return True
    def check(self,state):
        self.assert_live()
        state.update(status='CHECKING',heartbeat_at=self.clock());self.save(state)
        session=window(state['exchange_segment'],self.clock(),state.get('commodity_group'))
        if not session['open']:
            state.update(status='SLEEPING',next_check_at=session['next_open'],session=session,
                         message='Exchange closed; sleeping until the next trading session. No broker polling or recalculation.')
            return
        stop=state['managed_stop']
        self.confirm_stop(state,stop['ticket'],stop['order_id'],stop['correlation_id'])
        adapter=self.adapter() if hasattr(self,'adapter') else DhanHoldings(self.e);analysis=HoldingsAnalysis(clock=self.clock)
        report=analysis.batch(adapter,limit=5,inventory_only=True);rows=[]
        offset=report.get('next_offset')
        while offset is not None:
            if self.stopped(state):return
            report=analysis.batch(adapter,report['capture_id'],offset,limit=5);rows.extend(report['rows']);offset=report.get('next_offset')
        rows=[self.normalize(r) for r in rows] if hasattr(self,'normalize') else rows
        report.update(rows=rows,account_id=self.e.account['id'])
        matches=[r for r in rows if (r.get('native_identity') or {}).get('securityId')==state['security_id'] and (r.get('native_identity') or {}).get('exchangeSegment')==state['exchange_segment'] and r.get('kind') in ('DELIVERY_EQUITY','LINEAR_FUTURE')]
        if len(matches)!=1:raise ValueError('The monitored holding is missing or its native identity changed.')
        row=matches[0]
        if row['quantity']!=state['quantity'] or row['average_price']!=state['average_price'] or row.get('holding_type')!=state['holding_type']:
            raise ValueError('Holding quantity, cost or funding product changed; monitor paused for review.')
        _atomic_private_write(self.path(state['monitor_id']).parent/'last-review.json',json.dumps(report,allow_nan=False))
        state['latest_review']={**report,'rows':[{k:v for k,v in r.items() if k!='chart'} for r in rows]}
        state['last_checked_at']=self.clock()
        self.event(state,'REVIEW',action=row['action'],candidate_stop=row.get('candidate_stop'),gross_pnl=row.get('gross_pnl'))
        if row.get('action')!='TRAIL' or not row.get('candidate_stop'):
            state['message']='Latest review: '+row['action']+'. Existing stop retained; no discretionary exit is submitted.'
            return
        with self.e._submission_lock():
            plan=self.actions._plan(report,row,{},stop,self.path(state['monitor_id']))
            changed=self.transmit(state,plan)
        state['message']='Broker stop tightened and reconciled.' if changed else 'Recommendation does not raise the current stop; existing protection retained.'
    def run(self,context,state,stored,fd):
        try:
            with self.e._submission_lock():
                if self.stopped(state) or context.cancelled():raise JobCancelled()
                plan=self.actions._plan(stored['report'],stored['row'],{},state.get('managed_stop'),self.path(state['monitor_id']))
                if plan['ticket']!=stored['view']['ticket'] or plan['state_signature']!=stored['view']['state_signature']:
                    raise ValueError('Broker state changed after preview. Review enablement again; no new order sent.')
                self.transmit(state,plan,create=not bool(state.get('managed_stop')))
            if not state.get('managed_stop'):raise ValueError('Initial broker stop was not established.')
            state['last_checked_at']=self.clock()
            state.update(status='MONITORING',next_check_at=self.clock()+state['interval_minutes']*60,
                         message='Broker protection confirmed. Scheduled checks are active.')
            self.save(state);context.checkpoint(state['message'],deepcopy(state))
            while True:
                if context.cancelled() or self.stopped(state):raise JobCancelled()
                if self.store.shutdown.is_set():raise JobInterrupted()
                state['heartbeat_at']=self.clock()
                self.save(state)  # Merge explicit interval changes before scheduling work.
                session=window(state['exchange_segment'],self.clock(),state.get('commodity_group'))
                state['session']=session
                wake=self.store.wake_events[state['monitor_id']]
                if not session['open']:
                    state.update(status='SLEEPING',next_check_at=session['next_open'],sleep_until=session['next_open'],
                                 message='Exchange closed; sleeping until the next trading session. No broker polling or recalculation.')
                    self.save(state);context.checkpoint(state['message'],deepcopy(state))
                    wake.wait(max(1,session['next_open']-self.clock()));wake.clear()
                    continue
                if state.get('status')=='SLEEPING':
                    state.update(status='MONITORING',next_check_at=self.clock(),sleep_until=None)
                if self.clock()>=state['next_check_at']:
                    self.check(state)
                    state.update(status='MONITORING',next_check_at=self.clock()+state['interval_minutes']*60)
                if state['next_check_at']>=session['close']:
                    after=window(state['exchange_segment'],session['close']+1,state.get('commodity_group'))
                    state['next_check_at']=after['next_open']
                self.save(state);context.checkpoint(state['message'],deepcopy(state))
                wake.wait(min(30,max(1,session['close']-self.clock())));wake.clear()
        except JobCancelled:
            state.update(status='STOPPED',message='Monitoring stopped. Last broker protective stop remains in place.');return deepcopy(state)
        except JobInterrupted:
            state.update(status='INTERRUPTED',message='Monitoring interrupted. Broker stop retained; explicit enablement is required to restart.');raise
        except Exception as error:
            state.update(status='NEEDS_REVIEW',message=str(error) if isinstance(error,(ValueError,PermissionError)) else 'Broker data or update is unavailable. Review the monitor; no automatic order retry.')
            self.event(state,'PAUSED',message=state['message']);raise ValueError(state['message']) from None
        finally:
            state.update(running=False,heartbeat_at=self.clock(),next_check_at=None)
            self.save(state)
            # Persist final state even when the generic job becomes CANCELLED/INTERRUPTED.
            try:self.store._update(context.job_id,output=deepcopy(state),message=state['message'])
            finally:self.store.wake_events.pop(state['monitor_id'],None);unlock_file(fd);os.close(fd)
    def change_interval(self,owner,mid,minutes):
        minutes=interval(minutes)
        with self.guard:
            state=self.load(owner,mid)
            if not state.get('running') or state.get('stop_requested'):raise ValueError('This monitor is not active. Choose the interval in a new enablement preview.')
            old=state['interval_minutes']
            session=window(state['exchange_segment'],self.clock(),state.get('commodity_group'))
            state.update(interval_minutes=minutes,interval_revision=state.get('interval_revision',0)+1,interval_changed_at=self.clock(),
                         next_check_at=self.clock()+minutes*60 if session['open'] else session['next_open'])
            self.save(state)
            self.event(state,'INTERVAL_CHANGED',previous_minutes=old,interval_minutes=minutes)
            wake=self.store.wake_events.get(mid)
            if wake:wake.set()
            return state

    def stop(self,owner,mid):
        with self.guard:
            state=self.load(owner,mid)
            if not state.get('running'):return state
            state.update(stop_requested=True,status='STOPPING',message='Stop requested; finish the bounded in-flight broker check, then retain the existing protective stop.')
            self.save(state)
            wake=self.store.wake_events.get(mid)
            if wake:wake.set()
            # Cancellation is cooperative; never cancel the queued future and leak its instrument lock.
            for job in self.store.list(owner,200):
                if job['request'].get('payload',{}).get('monitor_id')==mid and not job['terminal']:
                    self.store._update(job['job_id'],status='CANCELLING',message=state['message'])
                    break
            return state
