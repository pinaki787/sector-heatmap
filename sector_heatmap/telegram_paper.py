"""Explicitly armed, new-post-only PAPER option pipeline; inert after restart."""
import hashlib,json,os,re,threading,time
from pathlib import Path
from copy import deepcopy
from .telegram_options import recommendation_plan,trigger_satisfied

class PaperPipeline:
 def __init__(self,tickets,polling,path,clock=time.time,feed=None):
  self.tickets=tickets;self.polling=polling;self.path=Path(path);self.clock=clock;self.lock=threading.RLock();self.running=False;self.armed_at=None;self.route=None;self.event=threading.Event();self.thread=None;self.feed=feed
  self.records=json.loads(self.path.read_text()).get('recommendations',{}) if self.path.exists() else {}
  for record in self.records.values():
   if record['status']=='WAITING_TRIGGER':record.update(status='STOPPED_AFTER_RESTART',message='Explicit start required; historical watches are never replayed.')
 def save(self):
  self.path.parent.mkdir(parents=True,exist_ok=True);tmp=self.path.with_suffix('.tmp')
  fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
  with os.fdopen(fd,'w') as out:json.dump(dict(recommendations=self.records),out)
  os.replace(tmp,self.path)
 def status(self):
  with self.lock:return dict(stream=self.feed.stream_status() if self.feed and isinstance(self.feed.stream_status(),dict) else {},running=self.running,mode='PAPER',quantity=1000,live_auto=False,trigger_validity_seconds=300,message='New posts only. Immediate PAPER entry on receipt; recommendation entry/stop/targets are references. XAUUSD uses the disclosed XAUT proxy. Renko owns simulated fills/exits. Stop prevents new entries; owned exits continue. Restart requires explicit start.',recommendations=deepcopy(list(self.records.values())[-30:]))
 def start(self,p):
  with self.lock:
   if p.get('mode')!='PAPER' or p.get('quantity')!=1000 or isinstance(p.get('quantity'),bool):raise ValueError('Unattended authorization is PAPER with 1000 whole contracts only.')
   if self.running:return self.status()
   if self.polling.route!='SUBSCRIBER':raise ValueError('Verified subscriber reception is required for unattended Paper.')
   if not self.polling.running():self.polling.start(dict(auto=False))
   if not self.polling.verified:raise ValueError('Verify channel before arming Paper.')
   with self.polling.lock:self.seen={r['id'] for r in self.polling.data['queue']}
   self.seen.update(self.records);self.armed_at=self.clock();self.route=self.polling.route
   if self.feed is None:
    from strategies.renko_supertrend.delta_broker import Broker
    self.feed=Broker(self.tickets.delta,self.path.with_name('telegram-paper-public-history.sqlite3'))
   for symbol in ('BTCUSD','ETHUSD','XAUTUSD'):self.feed.subscribe(symbol,60)
   self.feed.start();self.event=threading.Event();self.running=True
   self.thread=threading.Thread(target=self.run,args=(self.event,),daemon=True,name='telegram-unattended-paper');self.thread.start();return self.status()
 def stop(self):
  with self.lock:
   self.running=False;self.event.set()
   for record in self.records.values():
    if record['status']=='WAITING_TRIGGER':record.update(status='STOPPED',message='Watch stopped; no replay on next start.')
   self.save()
   if self.feed:self.feed.stop()
   return self.status()
 def run(self,event):
  while not event.wait(2):
   try:self.step()
   except Exception as exc:
    with self.lock:self.error=str(exc)
 def step(self):
  with self.lock:
   if not self.running:return
   if self.polling.route!=self.route or not self.polling.running() or not self.polling.verified:self.stop();return
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
     result=self.tickets.submit(dict(ticket_id=ticket['ticket_id'],text=ticket['text'],mode='PAPER',quantity=1000,entry_confirmed=True,**{k:cfg.get(k) for k in ('timeframe','ema_exit_enabled','ema_exit_length','supertrend_exit_enabled')}))
     record.update(status=result['status'],result=result,contract=ticket['contract'],message='Paper simulation only; Renko owns fills and exits.')
    except Exception as exc:record.update(status='BLOCKED_OR_UNCERTAIN',message=str(exc))
    self.save()
