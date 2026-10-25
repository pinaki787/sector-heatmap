"""Explicitly armed, new-post-only PAPER option pipeline; inert after restart."""
import hashlib,json,os,re,threading,time
from pathlib import Path
from copy import deepcopy
from .telegram_options import recommendation_plan,trigger_satisfied
from .telegram_lifecycle import Lifecycle

class PaperPipeline:
 def __init__(self,tickets,polling,path,clock=time.time,feed=None):
  self.tickets=tickets;self.polling=polling;self.path=Path(path);self.clock=clock;self.lock=threading.RLock();self.running=False;self.armed_at=None;self.route=None;self.event=threading.Event();self.thread=None;self.feed=feed
  saved=json.loads(self.path.read_text()) if self.path.exists() else {}
  self.records=saved.get('recommendations',{})
  self.options={**dict(gold_proxy=False,timeframe='5 minutes',ema_exit_enabled=True,ema_exit_length=10,supertrend_exit_enabled=True),**saved.get('options',{})}
  self.lifecycle=Lifecycle(self.path.with_suffix('.lifecycle.json'),clock)
  self.workspace_broker=os.getenv('SECTOR_PULSE_WORKSPACE_BROKER')

  for record in self.records.values():
   if record['status']=='WAITING_TRIGGER':record.update(status='STOPPED_AFTER_RESTART',message='Explicit start required; historical watches are never replayed.')
 def save(self):
  self.path.parent.mkdir(parents=True,exist_ok=True);tmp=self.path.with_suffix('.tmp')
  fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
  with os.fdopen(fd,'w') as out:json.dump(dict(recommendations=self.records,options=self.options),out)
  os.replace(tmp,self.path)
 def status(self):
  with self.lock:return dict(workspace_broker=self.workspace_broker,options=deepcopy(self.options),lifecycle=self.lifecycle.status(),stream=self.feed.stream_status() if self.feed and isinstance(self.feed.stream_status(),dict) else {},running=self.running,mode='PAPER',quantity=1000,live_auto=False,trigger_validity_seconds=300,message='New posts only. Immediate PAPER entry on receipt; recommendation entry/stop/targets are references. XAUUSD proxy is used only when explicitly enabled in saved Paper settings. Renko owns simulated fills/exits. Stop prevents new entries; owned exits continue. Restart requires explicit start.',recommendations=deepcopy(list(self.records.values())[-30:]))
 def configure(self,p):
  with self.lock:
   if self.running:raise ValueError('Stop new Paper entries before changing Paper settings.')
   options=dict(self.options)
   for key in options:
    if key in p:options[key]=p[key]
   if any(type(options[k]) is not bool for k in ('gold_proxy','ema_exit_enabled','supertrend_exit_enabled')):raise ValueError('Proxy and exit choices must be explicit checkboxes.')
   if options['timeframe'] not in ('1 minute','3 minutes','5 minutes','15 minutes','30 minutes','1 hour'):raise ValueError('Choose a supported Paper timeframe.')
   if type(options['ema_exit_length']) is not int or not 1<=options['ema_exit_length']<=200:raise ValueError('EMA exit length must be a whole number from 1 to 200.')
   if not (options['ema_exit_enabled'] or options['supertrend_exit_enabled']):raise ValueError('Select at least one Paper exit.')
   self.options=options;self.save();return self.status()
 def start(self,p):
  was_receiving=self.polling.running();was_running=self.running
  try:return self._start(p)
  except Exception as exc:
   if not was_running:
    self.running=False;self.event.set()
    if self.feed:self.feed.stop()
    if not was_receiving and self.polling.running():self.polling.stop()
   message=str(exc) if isinstance(exc,ValueError) else 'Reader or market feed could not start; verify subscriber access and dependencies.'
   self.lifecycle.record('RUNNING' if was_running else 'STOPPED','START_REJECTED',message)
   raise ValueError(message) from None
 def _start(self,p):
  with self.lock:
   if self.workspace_broker and self.workspace_broker!='DELTA_INDIA':raise ValueError('Open your Delta India account workspace for unattended option Paper; this workspace cannot own Delta entries.')
   if p.get('mode')!='PAPER' or p.get('quantity')!=1000 or isinstance(p.get('quantity'),bool):raise ValueError('Unattended authorization is PAPER with 1000 whole contracts only.')
   if self.running:return self.status()
   if self.polling.route!='SUBSCRIBER':raise ValueError('Select Subscriber account reception in this Delta workspace, save its application credentials and verify channel access before Start unattended Paper. Bot API is review-only for this pipeline.')
   self.configure(p)
   if not self.polling.running():self.polling.start(dict(auto=False))
   if not self.polling.verified:raise ValueError('Verify channel before arming Paper.')
   with self.polling.lock:self.seen={r['id'] for r in self.polling.data['queue']}
   self.seen.update(self.records);self.armed_at=self.clock();self.route=self.polling.route
   if self.feed is None:
    from strategies.renko_supertrend.delta_broker import Broker
    self.feed=Broker(self.tickets.delta,self.path.with_name('telegram-paper-public-history.sqlite3'))
   for symbol in ('BTCUSD','ETHUSD','XAUTUSD'):self.feed.subscribe(symbol,60)
   self.feed.start();self.event=threading.Event();self.running=True
   self.thread=threading.Thread(target=self.run,args=(self.event,),daemon=True,name='telegram-unattended-paper');self.thread.start();self.lifecycle.record('RUNNING','EXPLICIT_START','Unattended Paper explicitly started; new posts only.');self.lifecycle.heartbeat();return self.status()
 def stop(self,reason='USER_STOP',message='New Paper entries stopped explicitly; owned position exits remain managed by their Renko owner.'):
  with self.lock:
   self.running=False;self.event.set()
   for record in self.records.values():
    if record['status']=='WAITING_TRIGGER':record.update(status='STOPPED',message='Watch stopped; no replay on next start.')
   self.save();self.lifecycle.record('STOPPED',reason,message)
   if self.feed:self.feed.stop()
   return self.status()
 def run(self,event):
  while not event.wait(2):
   try:self.step()
   except Exception as exc:
    with self.lock:
     self.lifecycle.record('RUNNING','PROCESSING_ERROR','Paper processing failed; see recommendation outcomes. No automatic replay.');self.lifecycle.heartbeat()
 def step(self):
  with self.lock:
   if not self.running:return
   if self.polling.route!=self.route:self.stop('CONNECTION_ROUTE_CHANGED','Reception route changed; explicit Paper start required.');return
   if not self.polling.running():self.stop('RECEPTION_STOPPED','Subscriber reception stopped; verify the reader and explicitly restart Paper.');return
   if not self.polling.verified:self.stop('VERIFICATION_LOST','Subscriber channel verification was lost; verify access before explicit start.');return
   self.lifecycle.heartbeat()
   with self.polling.lock:rows=deepcopy(self.polling.data['queue'])
   rows_by_id={r['id']:r for r in rows}
   for row in rows:
    if row['id'] in self.seen:continue
    self.seen.add(row['id'])
    if row.get('edited_at') or row.get('missed_review') or row.get('submission_id') or row['state']!='REVIEW' or not self.armed_at<=row['timestamp']<=self.clock() or self.clock()-row['timestamp']>300:continue
    record=dict(id=row['id'],revision=row['revision'],timestamp=row['timestamp'],status='READY_IMMEDIATE_PAPER',text_hash=hashlib.sha256(row['text'].strip().encode()).hexdigest())
    if any(r.get('text_hash')==record['text_hash'] for r in self.records.values()):record.update(status='DUPLICATE_SKIPPED',message='Identical recommendation already seen; no second entry.')
    else:
     try:
      symbols=set(re.findall(r'\b(?:BTCUSD|ETHUSD|XAUUSD|XAUTUSD)\b',row['text'].upper()))
      if not symbols:
       record.update(status='IGNORED_CHATTER',message='No supported trade recommendation; channel conversation ignored.');self.records[row['id']]=record;self.save();continue
      if len(symbols)!=1:raise ValueError('Use one supported underlying per recommendation.')
      symbol=next(iter(symbols))
      record['gold_proxy']=symbol=='XAUUSD'
      if record['gold_proxy'] and not self.options['gold_proxy']:raise ValueError('XAUUSD proxy disabled. No XAUT option entry; enable the proxy explicitly before starting a new Paper session.')
      record['plan']=recommendation_plan(self.tickets.parse(row['text']),'XAUTUSD' if record['gold_proxy'] else symbol)
      record['entry_policy']='IMMEDIATE_PAPER_ON_RECEIPT; recommendation trigger, stop and targets are references'
     except Exception as exc:record.update(status='BLOCKED',message=str(exc))
    self.records[row['id']]=record;self.save()
   for ident,record in list(self.records.items()):
    if record['status']!='READY_IMMEDIATE_PAPER':continue
    row=rows_by_id.get(ident)
    if not row or row['revision']!=record['revision'] or row.get('edited_at') or row['state']!='REVIEW':record.update(status='EDITED_OR_CHANGED_BLOCKED',message='Recommendation changed; never replay edited advice.');self.save();continue
    if self.clock()-record['timestamp']>300:record.update(status='EXPIRED',message='Five-minute fresh recommendation window expired.');self.save();continue
    record.update(status='CLAIMED_NO_REPLAY');self.save()
    try:
     ticket=self.tickets.preview(dict(text=row['text'],queue_id=ident,revision=row['revision'],gold_proxy=record.get('gold_proxy',False)))
     cfg=ticket['renko_settings']
     result=self.tickets.submit(dict(ticket_id=ticket['ticket_id'],text=ticket['text'],mode='PAPER',quantity=1000,entry_confirmed=True,**{k:self.options[k] for k in ('timeframe','ema_exit_enabled','ema_exit_length','supertrend_exit_enabled')}))
     record.update(status=result['status'],result=result,contract=ticket['contract'],message='Paper simulation only; Renko owns fills and exits.')
    except Exception as exc:record.update(status='BLOCKED_OR_UNCERTAIN',message=str(exc))
    self.save()
