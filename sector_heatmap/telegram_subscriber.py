"""Receive-only selected-channel MTProto transport. No sending or broker callbacks."""
import asyncio, hashlib, importlib.metadata, os, re, threading
from pathlib import Path
from .telegram_polling import TelegramPolling

TELETHON_VERSION = '1.45.0'

class TelegramSubscriber(TelegramPolling):
 def __init__(self,path,clock=None,client_factory=None):
  kw={} if clock is None else dict(clock=clock)
  super().__init__(path,**kw)
  self.data['channel']=self.data.get('channel') or '-1003660684605';self.data.setdefault('api_id',None);self.data.setdefault('api_hash','')
  self.client_factory=client_factory;self.client=None;self.loop=None;self.worker=None;self.receiving=False;self.auth='DISCONNECTED';self.phone=None;self.code_hash=None;self.entity=None;self.watermark=0;self.baseline=0;self.reconciled_id=0;self.reconcile_task=None
 def running(self):return self.receiving
 def status(self):
  s=super().status();s.update(route='SUBSCRIBER',configured=bool(self.data.get('api_id') and self.data.get('api_hash') and self.data['channel']),auto_available=False,mode='CONFIRMATION',authentication=self.auth,dependency=self.dependency(),message='Receive-only subscriber connection. New posts enter review; orders require separate manual confirmation.')
  return s
 def dependency(self):
  if self.client_factory:return 'TEST'
  try:return 'READY' if importlib.metadata.version('Telethon')==TELETHON_VERSION else 'VERSION_MISMATCH'
  except importlib.metadata.PackageNotFoundError:return 'NOT_INSTALLED'
 def configure(self,p):
  with self.lock:
   if self.running() or self.client:raise ValueError('Disconnect the subscriber session before changing configuration.')
   channel=str(p.get('channel') or '').strip();api_id=str(p.get('api_id') or self.data.get('api_id') or '');api_hash=str(p.get('api_hash') or self.data.get('api_hash') or '').strip()
   if not re.fullmatch(r'-100[0-9]{5,20}',channel):raise ValueError('Enter the exact numeric -100 channel ID.')
   if not api_id.isdigit() or int(api_id)<=0 or not re.fullmatch(r'[a-fA-F0-9]{32}',api_hash):raise ValueError('Enter your Telegram application API ID and 32-character API hash in the local fields.')
   if self.data.get('api_id') and (int(api_id)!=self.data['api_id'] or api_hash!=self.data['api_hash']):raise ValueError('Existing application credentials cannot be replaced; use the same application.')
   if channel!=self.data['channel']:self.data.update(queue=[],watermark=0)
   self.data.update(api_id=int(api_id),api_hash=api_hash,channel=channel,channel_label=str(p.get('channel_label') or 'Dr Devendra\'s Crypto Advisory')[:200]);self.save();return self.status()
 def _worker(self,ready):
  self.loop=asyncio.new_event_loop();asyncio.set_event_loop(self.loop);ready.set();self.loop.run_forever()
 def call(self,coro):
  if not self.loop:
   ready=threading.Event();self.worker=threading.Thread(target=self._worker,args=(ready,),daemon=True,name='telegram-subscriber');self.worker.start();ready.wait(5)
  future=asyncio.run_coroutine_threadsafe(coro,self.loop)
  try:return future.result(25)
  except Exception as e:
   future.cancel()
   if isinstance(e,ValueError):raise
   raise ValueError('Subscriber operation failed or timed out; check connection and retry locally.') from None
 async def connect(self):
  if not self.client:
   if self.dependency() not in ('READY','TEST'):raise ValueError('Install the pinned optional Telegram subscriber dependency first.')
   if not self.data.get('api_id') or not self.data.get('api_hash'):raise ValueError('Save subscriber application credentials first.')
   self.path.parent.mkdir(parents=True,exist_ok=True);session_dir=self.path.parent/'telegram-session';session_dir.mkdir(mode=0o700,exist_ok=True);os.chmod(session_dir,0o700)
   if self.client_factory:factory=self.client_factory
   else:
    from telethon import TelegramClient
    factory=TelegramClient
   old=os.umask(0o077)
   try:self.client=factory(str(session_dir/'subscriber'),self.data['api_id'],self.data['api_hash'],auto_reconnect=True,catch_up=False)
   finally:os.umask(old)
   if getattr(self.client,'session',None) is not None:self.client.session.save_entities=False
   await self.client.connect()
   if not self.client_factory:
    from telethon import events
    self.client.add_event_handler(self.on_message,events.NewMessage(chats=int(self.data['channel'])))
    self.client.add_event_handler(self.on_edit,events.MessageEdited(chats=int(self.data['channel'])))
   for f in session_dir.iterdir():
    if f.is_file():os.chmod(f,0o600)
  return await self.client.is_user_authorized()
 async def authenticate(self,p):
  if await self.connect():self.auth='AUTHORIZED';return self.status()
  try:
   if p.get('password'):
    await self.client.sign_in(password=str(p['password']))
   elif p.get('code'):
    if not self.phone or not self.code_hash:raise ValueError('Request a login code first.')
    await self.client.sign_in(phone=self.phone,code=str(p['code']),phone_code_hash=self.code_hash)
   else:
    phone=str(p.get('phone') or '').strip()
    if not re.fullmatch(r'\+[0-9]{7,15}',phone):raise ValueError('Enter your account phone number with country code locally.')
    result=await self.client.send_code_request(phone);self.phone=phone;self.code_hash=result.phone_code_hash;self.auth='CODE_REQUIRED';return self.status()
  except Exception as e:
   if type(e).__name__=='SessionPasswordNeededError':self.auth='PASSWORD_REQUIRED';return self.status()
   raise ValueError('Telegram authentication failed. Check the local code/password or retry after Telegram rate limits.') from None
  self.phone=None;self.code_hash=None;self.auth='AUTHORIZED';return self.status()
 def login(self,p):return self.call(self.authenticate(p))
 async def verify_async(self):
  self.verified=None
  if not await self.connect():self.auth='LOGIN_REQUIRED';raise ValueError('Authenticate your subscriber account locally first.')
  self.auth='AUTHORIZED'
  try:
   # Resolve only this channel from legitimately accessible dialogs; no history import.
   self.entity=None
   async for dialog in self.client.iter_dialogs():
    if dialog.id==int(self.data['channel']):self.entity=dialog.entity;break
   if self.entity is None:raise ValueError('Selected channel or supergroup is not accessible in this account.')
   if not (getattr(self.entity,'broadcast',False) or getattr(self.entity,'megagroup',False)) or getattr(self.entity,'left',False):raise ValueError('Selected peer must be a joined channel or supergroup.')
   self.verified=dict(channel_id=int(self.data['channel']),title=self.entity.title,peer_type='SUPERGROUP' if getattr(self.entity,'megagroup',False) else 'BROADCAST_CHANNEL',at=self.clock());self.error=None
  except ValueError:raise
  except Exception:raise ValueError('Subscriber channel verification failed; check account access and connectivity.') from None
  return self.status()
 def verify(self):return self.call(self.verify_async())
 def ingest_message(self,message,edited=False,missed=False):
  with self.lock:self._ingest_message(message,edited,missed)
 def _ingest_message(self,message,edited=False,missed=False):
  if not self.receiving:return
  mid=int(message.id);text=message.message;stamp=message.date.timestamp()
  if not text:
   self.watermark=max(self.watermark,mid);self.data['watermark']=self.watermark;self.save();return
  ident=self.data['channel']+':'+str(mid)
  old=next((r for r in self.data['queue'] if r['id']==ident),None)
  if mid<=self.baseline and old is None:return
  self.auto=False
  post=dict(chat=dict(id=int(self.data['channel'])),message_id=mid,date=stamp,text=text)
  if edited:post['edit_date']=message.edit_date.timestamp() if message.edit_date else self.clock()
  super().ingest([dict(update_id=mid,**{'edited_channel_post' if edited else 'channel_post':post})],baseline=True)
  self.watermark=max(self.watermark,mid);self.data['watermark']=self.watermark
  row=next(r for r in self.data['queue'] if r['id']==ident);row.update(source='SUBSCRIBER',missed_review=bool(missed));self.save()
 async def on_message(self,event):
  if event.chat_id==int(self.data['channel']):self.ingest_message(event.message,missed=event.message.date.timestamp()<self.clock()-30)
 async def on_edit(self,event):
  if event.chat_id==int(self.data['channel']):self.ingest_message(event.message,edited=True)
 async def reconcile_loop(self):
  while self.receiving:
   await asyncio.sleep(30)
   if not self.receiving:break
   try:
    messages=[m async for m in self.client.iter_messages(self.entity,min_id=self.reconciled_id,limit=201)]
    if len(messages)>200:self.error='More than 200 missed posts; reception stopped for explicit review.';self.receiving=False;break
    for m in reversed(messages):self.ingest_message(m,missed=True)
    self.reconciled_id=max([self.reconciled_id]+[m.id for m in messages])
    self.error=None
   except Exception:self.error='Subscriber reception interrupted; missed posts require review after reconnection.'
 async def start_async(self,p):
  if self.receiving:return self.status()
  if p.get('auto'):raise ValueError('Subscriber reception never supports Auto submission.')
  await self.verify_async()
  latest=await self.client.get_messages(self.entity,limit=1)
  self.watermark=latest[0].id if latest else 0;self.baseline=self.watermark;self.reconciled_id=self.watermark;self.data['watermark']=self.watermark;self.save()
  self.receiving=True;self.auto=False;self.armed_at=self.clock();self.reconcile_task=self.loop.create_task(self.reconcile_loop());return self.status()
 def start(self,p=None):return self.call(self.start_async(p or {}))
 def stop(self):
  self.receiving=False;self.auto=False
  if self.reconcile_task and self.loop:self.loop.call_soon_threadsafe(self.reconcile_task.cancel)
  self.reconcile_task=None;return self.status()
 async def disconnect_async(self):
  self.stop()
  if self.client:await self.client.disconnect()
  self.client=None;self.auth='DISCONNECTED';self.verified=None;self.phone=None;self.code_hash=None;return self.status()
 def disconnect(self,p=None):return self.call(self.disconnect_async())

class TelegramConnections:
 def __init__(self,path):
  self.selection_path=Path(path).with_name('telegram-connection-route.json')
  self.bot=TelegramPolling(path);self.subscriber=TelegramSubscriber(Path(path).with_name('telegram-subscriber.json'));self.route='BOT';self.auto_submit=None
  if self.selection_path.exists():
   import json
   saved=json.loads(self.selection_path.read_text()).get('route');self.route=saved if saved in ('BOT','SUBSCRIBER') else 'BOT'
 def save_route(self):
  import json
  self.selection_path.parent.mkdir(parents=True,exist_ok=True)
  fd=os.open(self.selection_path,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
  with os.fdopen(fd,'w') as f:json.dump(dict(route=self.route),f)
 def active(self):return self.subscriber if self.route=='SUBSCRIBER' else self.bot
 def status(self):return dict(self.active().status(),route=self.route)
 def configure(self,p):
  route=p.get('route','BOT')
  if route not in ('BOT','SUBSCRIBER'):raise ValueError('Choose Bot API or Subscriber.')
  if self.active().running():raise ValueError('Stop reception before changing route.')
  target=self.subscriber if route=='SUBSCRIBER' else self.bot;result=target.configure(p);self.route=route;self.save_route();return self.status()
 def select(self,p):
  if self.active().running():raise ValueError('Stop reception before changing route.')
  if p.get('route') not in ('BOT','SUBSCRIBER'):raise ValueError('Choose connection route.')
  self.route=p['route'];self.save_route();return self.status()
 def start(self,p=None):self.bot.auto_submit=self.auto_submit;return self.active().start(p)
 def stop(self):self.bot.stop();self.subscriber.stop();return self.status()
 def __getattr__(self,name):return getattr(self.active(),name)
