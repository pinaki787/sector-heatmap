"""One account-bound Paper/Live execution controller for fresh Telegram recommendations."""
import hashlib,json,os,tempfile,threading,time
from copy import deepcopy
from .telegram_paper import PaperPipeline

FIELDS=('mode','quantity','product','gold_proxy','timeframe','ema_exit_enabled','ema_exit_length','supertrend_exit_enabled')
class ExecutionPipeline(PaperPipeline):
 def __init__(self,tickets,polling,path,clock=time.time,feed=None,guard=None):
  super().__init__(tickets,polling,path,clock,feed)
  saved=json.loads(self.path.read_text()) if self.path.exists() else {}
  self.settings={**dict(mode='PAPER',quantity=1000,product='ATM_OPTIONS'),**self.options,**saved.get('execution',{})}
  self.settings=self.validate(self.settings)
  self.revision=self.signature(self.settings);self.run_settings=None;self.live_authorized=False
  self.manual={};self.seen=set();self.guard=guard or (lambda mode,phase:None)
 @staticmethod
 def signature(settings):return hashlib.sha256(json.dumps(settings,sort_keys=True,separators=(',',':')).encode()).hexdigest()
 @staticmethod
 def validate(settings):
  cfg={k:settings[k] for k in FIELDS}
  if cfg['mode'] not in ('PAPER','LIVE'):raise ValueError('Choose Paper or Live.')
  if type(cfg['quantity']) is not int or not 1<=cfg['quantity']<=100000:raise ValueError('Enter one whole option-contract quantity from 1 to 100000.')
  if cfg['product']!='ATM_OPTIONS':raise ValueError('Only bought ATM options with Renko exit ownership are supported. Legacy native entries are retired.')
  if any(type(cfg[k]) is not bool for k in ('gold_proxy','ema_exit_enabled','supertrend_exit_enabled')):raise ValueError('Proxy and exit choices must be explicit checkboxes.')
  if cfg['timeframe'] not in ('1 minute','3 minutes','5 minutes','15 minutes','30 minutes','1 hour'):raise ValueError('Choose a supported Renko timeframe.')
  if type(cfg['ema_exit_length']) is not int or not 1<=cfg['ema_exit_length']<=200:raise ValueError('EMA length must be a whole number from 1 to 200.')
  if not (cfg['ema_exit_enabled'] or cfg['supertrend_exit_enabled']):raise ValueError('Choose at least one owned Renko exit.')
  return cfg
 def save(self):
  self.path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
  fd,tmp=tempfile.mkstemp(dir=self.path.parent,prefix='.telegram-execution-')
  try:
   with os.fdopen(fd,'w') as f:
    os.fchmod(f.fileno(),0o600);json.dump(dict(recommendations=self.records,options=self.options,execution=self.settings),f);f.flush();os.fsync(f.fileno())
   os.replace(tmp,self.path)
  finally:
   if os.path.exists(tmp):os.unlink(tmp)
 def status(self):
  with self.lock:
   cfg=self.run_settings if self.running else self.settings
   return dict(api_version=1,workspace_broker=self.workspace_broker,settings=deepcopy(self.settings),revision=self.revision,running=self.running,
    mode=cfg['mode'],quantity=cfg['quantity'],product=cfg['product'],entry_policy='IMMEDIATE_ON_RECEIPT',live_auto=bool(self.running and cfg['mode']=='LIVE'),
    lifecycle=self.lifecycle.status(),recommendations=deepcopy(list(self.records.values())[-30:]),
    message='New recommendations only. Bought ATM options enter at a fresh quote; recommendation entry/stop/targets are references, not attached protective orders. Renko owns confirmed fills and exits. Stop prevents new entries; existing owned exits continue. Restart never rearms.')
 def require_owner(self):
  if self.workspace_broker!='DELTA_INDIA':raise ValueError('Bought option execution belongs to your Delta India workspace. This workspace can receive/review only.')
 def check_revision(self,p):
  if p.get('config_revision')!=self.revision:raise ValueError('Execution settings changed or this page is outdated. Refresh and review the single Paper/Live configuration.')
 def proposed(self,p):
  return self.validate({**self.settings,**{k:p[k] for k in FIELDS if k in p}})
 def configure(self,p):
  with self.lock:
   self.require_owner();self.check_revision(p);cfg=self.proposed(p)
   if self.running and cfg!=self.settings:raise ValueError('Stop new entries before changing mode, quantity or exits. Existing position management is unaffected.')
   if cfg!=self.settings:
    self.settings=cfg;self.options={k:cfg[k] for k in self.options if k in cfg};self.revision=self.signature(cfg);self.manual.clear();self.save()
   return self.status()
 def start(self,p):
  with self.lock:
   was_receiving=self.polling.running();was_running=self.running
   try:
    self.require_owner();self.check_revision(p);cfg=self.proposed(p)
    if self.running:
     if cfg!=self.run_settings:raise ValueError('Execution is already running with different settings. Stop new entries before changing the mode.')
     return self.status()
    if cfg['mode']=='LIVE' and p.get('live_confirmed') is not True:raise ValueError('Explicitly authorize Live execution using the displayed option quantity, immediate entry policy and Renko exits.')
    if self.polling.route not in ('BOT','SUBSCRIBER'):raise ValueError('Connect a verified Telegram reader before starting recommendation execution.')
    self.guard(cfg['mode'],'start');self.configure(p)
    if not self.polling.running():self.polling.start(dict(auto=False))
    if not self.polling.verified:raise ValueError('Verify source channel access before executing recommendations.')
    with self.polling.lock:self.seen={r['id'] for r in self.polling.data['queue']}
    self.seen.update(self.records);self.armed_at=self.clock();self.route=self.polling.route
    self.run_settings=deepcopy(cfg);self.live_authorized=cfg['mode']=='LIVE';self.event=threading.Event();self.running=True
    self.thread=threading.Thread(target=self.run,args=(self.event,),daemon=True,name='telegram-recommendation-execution');self.thread.start()
    self.lifecycle.record('RUNNING','EXPLICIT_START',cfg['mode']+' recommendation execution explicitly started; new posts only.');self.lifecycle.heartbeat()
    return self.status()
   except Exception as exc:
    if not was_running:
     self.running=False;self.run_settings=None;self.live_authorized=False;self.event.set()
     if not was_receiving and self.polling.running():self.polling.stop()
    message=str(exc) if isinstance(exc,(ValueError,PermissionError)) else 'Execution could not start; verify source access and account state.'
    self.lifecycle.record('RUNNING' if self.running else 'STOPPED','START_REJECTED',message)
    raise ValueError(message) from None
 def stop(self,reason='USER_STOP',message='New recommendation entries stopped; reception and owned Renko exits continue.'):
  with self.lock:
   self.live_authorized=False
   return super().stop(reason,message)
 def fresh_row(self,row):
  if row.get('edited_at') or row.get('missed_review') or row.get('submission_id') or row.get('state')!='REVIEW':return False
  stamp=row.get('timestamp')
  return isinstance(stamp,(int,float)) and not isinstance(stamp,bool) and 0<=self.clock()-stamp<=300 and (not self.running or stamp>=self.armed_at)
 def reject_override(self,p,cfg):
  for key in ('mode','quantity','product'):
   if key in p and p[key]!=cfg[key]:raise ValueError('Use the single saved execution mode, product and quantity. Per-ticket overrides are not allowed.')
 def preview(self,p):
  with self.lock:
   self.require_owner();self.check_revision(p);cfg=self.run_settings if self.running else self.settings;self.reject_override(p,cfg)
   if p.get('queue_id'):
    with self.polling.lock:row=next((r for r in self.polling.data['queue'] if r['id']==p['queue_id']),None)
    if not row or not self.fresh_row(row):raise ValueError('This queued post is edited, missed, already claimed or outside the current fresh-message window. It cannot be replayed.')
   ticket=self.tickets.preview(dict(text=p.get('text',''),queue_id=p.get('queue_id'),revision=p.get('revision'),gold_proxy=cfg['gold_proxy']))
   self.manual[ticket['ticket_id']]=dict(ticket=deepcopy(ticket),config_revision=self.revision,settings=deepcopy(cfg),queue_id=p.get('queue_id'))
   return dict(ticket,execution_mode=cfg['mode'],quantity=cfg['quantity'],product=cfg['product'],config_revision=self.revision,entry_policy='IMMEDIATE_ON_RECEIPT')
 def claim(self,key,text,revision,cfg,stamp):
  digest=hashlib.sha256(text.strip().encode()).hexdigest()
  if key in self.records or any(r.get('text_hash')==digest for r in self.records.values()):raise ValueError('Recommendation already processed or claimed. No duplicate or uncertain order will be replayed.')
  record=dict(id=key,revision=revision,timestamp=stamp,status='CLAIMED_NO_REPLAY',text_hash=digest,mode=cfg['mode'],quantity=cfg['quantity'],product=cfg['product'],entry_policy='IMMEDIATE_ON_RECEIPT',config_revision=self.signature(cfg))
  self.records[key]=record;self.save();return record
 def submit_ticket(self,ticket,cfg):
  # The only execution gateway. Never forwards a caller's mode or quantity.
  return self.tickets.submit(dict(ticket_id=ticket['ticket_id'],text=ticket['text'],mode=cfg['mode'],quantity=cfg['quantity'],entry_confirmed=True,
    **{k:cfg[k] for k in ('timeframe','ema_exit_enabled','ema_exit_length','supertrend_exit_enabled')}))
 def finish(self,record,ticket,cfg):
  raw=self.submit_ticket(ticket,cfg)
  result=dict(raw,execution_mode=cfg['mode'],quantity=cfg['quantity'],product=cfg['product'])
  record.update(status=result.get('status','RESPONSE_RECEIVED'),result=result,contract=ticket.get('contract'),message=cfg['mode']+' only; Renko owns fill confirmation and exits.')
  self.save();return result
 def submit_manual(self,p):
  with self.lock:
   self.require_owner();self.check_revision(p);review=self.manual.get(p.get('ticket_id'))
   if not review or review['config_revision']!=self.revision:raise ValueError('Preview a fresh recommendation with the current execution settings.')
   cfg=review['settings'];self.reject_override(p,cfg)
   if p.get('entry_confirmed') is not True:raise ValueError('Review and confirm this immediate option entry.')
   if cfg['mode']=='LIVE' and p.get('live_confirmed') is not True:raise ValueError('Explicit Live confirmation is required for this reviewed entry.')
   ticket=review['ticket']
   if p.get('text')!=ticket['text']:raise ValueError('Recommendation text changed; preview it again.')
   if self.clock()>ticket['expires_at']:raise ValueError('Preview expired; no entry sent.')
   if review['queue_id']:
    with self.polling.lock:row=next((r for r in self.polling.data['queue'] if r['id']==review['queue_id']),None)
    if not row or not self.fresh_row(row):raise ValueError('Queued recommendation is no longer fresh and unclaimed.')
   self.guard(cfg['mode'],'submit')
   key=review['queue_id'] or 'manual-'+hashlib.sha256(ticket['text'].strip().encode()).hexdigest()
   record=self.claim(key,ticket['text'],ticket.get('revision'),cfg,self.clock())
   try:return self.finish(record,ticket,cfg)
   except Exception:
    record.update(status='BLOCKED_OR_UNCERTAIN',message='Entry did not complete normally. Inspect its Renko owner; no automatic retry.');self.save();raise
 def step(self):
  with self.lock:
   if not self.running:return
   if self.polling.route!=self.route:self.stop('CONNECTION_ROUTE_CHANGED','Source route changed; execution stopped.');return
   if not self.polling.running():self.stop('RECEPTION_STOPPED','Source reception stopped; execution requires a new explicit start.');return
   if not self.polling.verified:self.stop('VERIFICATION_LOST','Source channel verification lost; execution stopped.');return
   self.lifecycle.heartbeat()
   with self.polling.lock:rows=deepcopy(self.polling.data['queue'])
   cfg=self.run_settings
   for row in rows:
    if row['id'] in self.seen:continue
    self.seen.add(row['id'])
    if not self.fresh_row(row):continue
    record=None
    try:
     if cfg['mode']=='LIVE' and not self.live_authorized:raise ValueError('Live run authorization unavailable.')
     record=self.claim(row['id'],row['text'],row['revision'],cfg,row['timestamp'])
     self.guard(cfg['mode'],'submit')
     ticket=self.tickets.preview(dict(text=row['text'],queue_id=row['id'],revision=row['revision'],gold_proxy=cfg['gold_proxy']))
     self.finish(record,ticket,cfg)
    except Exception as exc:
     if record is None and row['id'] not in self.records:
      self.records[row['id']]=dict(id=row['id'],revision=row['revision'],timestamp=row['timestamp'],status='DUPLICATE_OR_BLOCKED',mode=cfg['mode'],quantity=cfg['quantity'],message='Recommendation duplicate or unavailable; no entry sent.');self.save()
     if record:
      record.update(status='BLOCKED_OR_UNCERTAIN',message=str(exc) if isinstance(exc,ValueError) else 'Processing uncertain; inspect the Renko owner. No retry.');self.save()
 def run(self,event):
  while not event.wait(2):
   try:self.step()
   except Exception:self.lifecycle.record('RUNNING','PROCESSING_ERROR','Execution processing unavailable; no orders replayed.')


def action_routes(execution,parser,polling,connect,disconnect,retired,verify):
 return {
  'execution-settings':execution.configure,'execution-start':execution.start,'execution-stop':lambda p:execution.stop(),
  'execution-preview':execution.preview,'execution-submit':execution.submit_manual,
  'paper-settings':retired,'paper-start':retired,'paper-stop':lambda p:execution.stop(),
  'option-preview':execution.preview,'option-submit':execution.submit_manual,
  'connect':connect,'config':polling.configure,'route':polling.select,'login':polling.subscriber.login,
  'disconnect':disconnect,'verify':verify,'start':connect,'stop':disconnect,
  'parse':execution.preview,'submit':execution.submit_manual,'reconcile':parser.reconcile}
