"""Telegram Bot API channel updates, durable review queue, explicit stopped startup."""
import hashlib,json,os,re,threading,time,uuid
from pathlib import Path
import requests

DEFAULT_CHANNEL_LABEL = "Doctor Devendra’s Crypto Advisory"

class TelegramPolling:
 def __init__(self,path,requester=requests,clock=time.time):
  self.path=Path(path);self.requester=requester;self.clock=clock;self.lock=threading.RLock();self.stop_event=threading.Event();self.thread=None;self.verified=None;self.error=None;self.auto=False;self.auto_submit=None;self.execution={};self.armed_at=None
  self.data=json.loads(self.path.read_text()) if self.path.exists() else dict(token='',channel='',channel_label=DEFAULT_CHANNEL_LABEL,interval=30,offset=0,queue=[])
  self.data.setdefault('channel_label',DEFAULT_CHANNEL_LABEL)
 def save(self):
  self.path.parent.mkdir(parents=True,exist_ok=True);temp=self.path.with_suffix('.tmp');fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
  with os.fdopen(fd,'w') as f:json.dump(self.data,f)
  os.replace(temp,self.path);os.chmod(self.path,0o600)
 def running(self):return bool(self.thread and self.thread.is_alive() and not self.stop_event.is_set())
 def status(self):
  with self.lock:return dict(running=self.running(),configured=bool(self.data['token'] and self.data['channel']),channel=self.data['channel'],channel_label=self.data.get('channel_label',DEFAULT_CHANNEL_LABEL),interval=self.data['interval'],connection='VERIFIED' if self.verified else 'NOT_VERIFIED',verified=self.verified,error=self.error,queue=[dict(r,expired=self.clock()-r['timestamp']>300) for r in reversed(self.data['queue'][-100:])],mode='AUTO' if self.auto else 'CONFIRMATION',auto_available=True,execution=self.execution,message='Auto submits fresh new posts only while explicitly started.' if self.auto else 'Polling starts stopped. Each recommendation requires a fresh Submit order. Bot API receives new channel posts, not arbitrary past channel history.')
 def configure(self,p):
  with self.lock:
   if self.running():raise ValueError('Stop polling before changing Telegram configuration.')
   channel=str(p.get('channel','')).strip();token=str(p.get('token') or self.data['token']).strip();interval=int(p.get('interval',30))
   if not re.fullmatch(r'(@[A-Za-z0-9_]{5,64}|-100[0-9]{5,20})',channel):raise ValueError('Use the exact @channel username or numeric -100 channel ID.')
   if not re.fullmatch(r'[0-9]+:[A-Za-z0-9_-]{20,}',token):raise ValueError('Enter a Telegram bot token in the local masked field.')
   if not 10<=interval<=3600:raise ValueError('Polling interval must be 10–3600 seconds.')
   label=str(p.get('channel_label') or self.data.get('channel_label') or DEFAULT_CHANNEL_LABEL).strip()[:200]
   changed=token!=self.data['token'] or channel!=self.data['channel'];self.data.update(token=token,channel=channel,channel_label=label,interval=interval)
   if changed:self.data.update(offset=0,queue=[])
   self.verified=None;self.save();return self.status()
 def api(self,method,body=None):
  if method not in ('getMe','getChat','getChatMember','getWebhookInfo','getUpdates'):raise ValueError('Telegram read-only method required.')
  try:
   r=self.requester.post('https://api.telegram.org/bot'+self.data['token']+'/'+method,json=body or {},timeout=15);d=r.json()
  except Exception:raise ValueError('Telegram read failed; check connectivity and configured bot access.') from None
  if not d.get('ok'):raise ValueError('Telegram rejected the read; check bot token, channel membership and webhook ownership.')
  return d['result']
 def verify(self):
  with self.lock:
   if not self.data['token'] or not self.data['channel']:raise ValueError('Configure bot token and channel first.')
   self.verified=None;me=self.api('getMe');chat=self.api('getChat',dict(chat_id=self.data['channel']));member=self.api('getChatMember',dict(chat_id=chat['id'],user_id=me['id']))
   if not me.get('is_bot') or chat.get('type')!='channel' or member.get('status') not in ('member','administrator','creator'):raise ValueError('Verified bot membership in the selected channel is required.')
   if self.api('getWebhookInfo').get('url'):raise ValueError('This bot has an existing webhook. Use a dedicated polling bot; no webhook was changed.')
   self.verified=dict(bot=me.get('username'),channel_id=chat['id'],title=chat.get('title'),at=self.clock());self.error=None;return self.status()
 def ingest(self,updates,baseline=False):
  with self.lock:
   fresh=[]
   for update in updates:
    post=update.get('channel_post') or update.get('edited_channel_post');self.data['offset']=max(self.data['offset'],int(update['update_id'])+1)
    if not post or str(post['chat']['id'])!=str(self.verified['channel_id']):continue
    text=post.get('text') or post.get('caption');stamp=post.get('date')
    if not text or not isinstance(stamp,(int,float)):continue
    ident=str(post['chat']['id'])+':'+str(post['message_id']);revision=hashlib.sha256(text.encode()).hexdigest();old=next((r for r in self.data['queue'] if r['id']==ident),None)
    if old and old['revision']==revision:continue
    record=dict(id=ident,revision=revision,text=text[:12000],timestamp=stamp,edited_at=post.get('edit_date'),state='REVIEW',submission_id=None)
    if old:
     record['state']='EDITED_REVIEW' if old['state']!='REVIEW' else 'REVIEW';record['submission_id']=old.get('submission_id');old.update(record)
    else:
     self.data['queue'].append(record)
     if not baseline and self.auto and stamp>=self.armed_at and 0<=self.clock()-stamp<=300:fresh.append(dict(record))
   self.data['queue']=self.data['queue'][-500:];self.save()
   for row in fresh:
    try:
     result=self.auto_submit(row,self.execution)
     stored=next(r for r in self.data['queue'] if r['id']==row['id']);stored.update(result=result,state='BROKER_RESPONSE' if not result.get('error') else 'REJECTED')
    except Exception as e:
     stored=next(r for r in self.data['queue'] if r['id']==row['id']);stored.update(state='BLOCKED_OR_UNCERTAIN',error=str(e))
    self.save()
 def snapshot(self,ident,revision):
  with self.lock:
   row=next((r for r in self.data['queue'] if r['id']==ident),None)
   if not row or row['revision']!=revision or self.clock()-row['timestamp']>300 or row['timestamp']>self.clock()+5:raise ValueError('Queued recommendation changed or expired; load a fresh message.')
   if row['state']!='REVIEW':raise ValueError('Recommendation already submitted or uncertain; reconcile before any retry.')
   return dict(row)
 def reserve(self,ident,revision,submission_id):
  with self.lock:
   self.snapshot(ident,revision);row=next(r for r in self.data['queue'] if r['id']==ident);row.update(state='SUBMISSION_ATTEMPTED',submission_id=submission_id);self.save()
 def poll(self):
  with self.lock:
   if not self.verified:raise ValueError('Verify Telegram channel access first.')
   self.ingest(self.api('getUpdates',dict(offset=self.data['offset'],timeout=0,limit=100,allowed_updates=['channel_post','edited_channel_post'])))
 def start(self,p=None):
  with self.lock:
   if self.running():return self.status()
   self.verify();p=p or {};auto=p.get('auto',False)
   if not isinstance(auto,bool):raise ValueError('Auto submission must be an explicit checkbox choice.')
   if auto and (p.get('broker') not in ('FYERS','DELTA_INDIA') or not self.auto_submit):raise ValueError('Select an execution broker before starting Auto.')
   try:quantity=int(p.get('quantity',1))
   except (TypeError,ValueError):raise ValueError('Enter whole lots/contracts.') from None
   if not 1<=quantity<=100000 or str(quantity)!=str(p.get('quantity',1)):raise ValueError('Enter whole lots/contracts.')
   self.auto=False
   # Drain pending updates as review history before arming; never replay a backlog.
   while True:
    updates=self.api('getUpdates',dict(offset=self.data['offset'],timeout=0,limit=100,allowed_updates=['channel_post','edited_channel_post']))
    self.ingest(updates,baseline=True)
    if len(updates)<100:break
   self.execution=dict(broker=p.get('broker','DELTA_INDIA'),quantity=quantity);self.armed_at=self.clock();self.auto=auto
   self.stop_event=threading.Event();self.thread=threading.Thread(target=self.loop,daemon=True,name='telegram-review-polling');self.thread.start();return self.status()
 def loop(self):
  while not self.stop_event.is_set():
   try:self.poll();self.error=None
   except Exception as e:self.error=str(e)
   self.stop_event.wait(self.data['interval'])
 def stop(self):self.stop_event.set();self.auto=False;return self.status()
