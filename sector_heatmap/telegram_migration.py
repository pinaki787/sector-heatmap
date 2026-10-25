"""Owner-verified legacy subscriber restoration; never starts a reader or runner."""
import json,os,sqlite3,tempfile,shutil,time
from pathlib import Path

def private_write(path,value):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
 fd,tmp=tempfile.mkstemp(dir=path.parent,prefix=".migration-")
 try:
  with os.fdopen(fd,"w") as f:os.fchmod(f.fileno(),0o600);json.dump(value,f);f.flush();os.fsync(f.fileno())
  os.replace(tmp,path)
 finally:
  if Path(tmp).exists():os.unlink(tmp)

def migration_plan(root,username,account_id):
 root=Path(root).resolve()
 with sqlite3.connect((root/".private/dashboard-login/registry.sqlite3").as_uri()+"?mode=ro",uri=True) as db:
  row=db.execute("SELECT a.id,a.broker,u.id,u.username,u.admin FROM accounts a JOIN users u ON a.user_id=u.id WHERE a.id=?",(account_id,)).fetchone()
 if not row or row[3]!=username or not row[4] or row[1]!="DELTA_INDIA":raise ValueError("Legacy reader restoration requires the owning administrator's Delta India account.")
 evidence=json.loads((root/".private/notifications/config.json").read_text())
 if evidence.get("owner_username")!=username:raise ValueError("Independent Telegram owner binding unavailable.")
 expected=evidence.get("telegram",{}).get("chat_id")
 if type(expected) is not int or expected<=0:raise ValueError("Verified private Telegram owner identity required.")
 legacy=root/".private";target=root/".private/dashboard-login/accounts"/account_id/"source/.private"
 claim=legacy/"telegram-reader-ownership.json"
 if claim.exists():
  previous=json.loads(claim.read_text())
  if previous.get("account_id")!=account_id or previous.get("owner_user_id")!=row[2]:raise ValueError("Legacy session already belongs to a different account; credentials cannot be shared.")
 source=legacy/"telegram-subscriber.json";session=legacy/"telegram-session/subscriber.session"
 if source.is_symlink() or session.is_symlink() or not source.is_file() or not session.is_file():raise ValueError("Protected legacy configuration/session unavailable.")
 config=json.loads(source.read_text())
 if not config.get("api_id") or not config.get("api_hash"):raise ValueError("Legacy application credentials unavailable.")
 for name in ("telegram-subscriber.json","telegram-connection-route.json"):
  if (target/name).exists():raise ValueError("Destination already has reader settings; no overwrite or merge.")
 if (target/"telegram-session/subscriber.session").exists():raise ValueError("Destination session exists; no replacement.")
 return dict(root=root,legacy=legacy,target=target,source=source,session=session,owner_user_id=row[2],owner_username=username,account_id=account_id,expected_telegram_user_id=expected,config=config)

async def restore(plan,legacy_stopped=False,client_factory=None):
 if not legacy_stopped:raise ValueError("Verify legacy reception and Paper are stopped before restoration.")
 if client_factory is None:
  from telethon import TelegramClient
  client_factory=TelegramClient
 stage=Path(tempfile.mkdtemp(dir=plan["legacy"],prefix="telegram-restore-"));os.chmod(stage,0o700)
 session=stage/"subscriber.session"
 client=None;written=[]
 try:
  with sqlite3.connect(plan["session"].as_uri()+"?mode=ro",uri=True) as source,sqlite3.connect(session) as dest:source.backup(dest)
  os.chmod(session,0o600)
  client=client_factory(str(session.with_suffix("")),plan["config"]["api_id"],plan["config"]["api_hash"],auto_reconnect=False,catch_up=False)
  if getattr(client,"session",None) is not None:client.session.save_entities=False
  await client.connect()
  if not await client.is_user_authorized():raise ValueError("Legacy session is not authorized. User-managed login is required; no OTP requested.")
  me=await client.get_me()
  if not me or me.id!=plan["expected_telegram_user_id"]:raise ValueError("Legacy Telegram identity does not match the independently verified owner. Nothing restored.")
  channel=int(plan["config"]["channel"]);entity=None
  async for dialog in client.iter_dialogs():
   if dialog.id==channel:entity=dialog.entity;break
  if not entity or not (getattr(entity,"broadcast",False) or getattr(entity,"megagroup",False)) or getattr(entity,"left",False):raise ValueError("Owner is not a member of the selected source channel. Nothing restored.")
  await client.disconnect();client=None
  binding={k:plan[k] for k in ("owner_user_id","owner_username","account_id","expected_telegram_user_id")}
  binding.update(verified_at=time.time(),channel_id=channel)
  target=plan["target"];(target/"telegram-session").mkdir(parents=True,exist_ok=True,mode=0o700)
  # Copy only this verified session and app configuration to one owned workspace.
  # Queue and armed/running state are intentionally excluded.
  destination=target/"telegram-session/subscriber.session"
  shutil.copyfile(session,destination);os.chmod(destination,0o600);written.append(destination)
  config=dict(plan["config"],queue=[],watermark=0,owner_binding=binding)
  for path,data in ((target/"telegram-subscriber.json",config),(target/"telegram-connection-route.json",{"route":"SUBSCRIBER"}),(target/"telegram-reader-ownership.json",binding)):
   private_write(path,data);written.append(path)
  private_write(plan["legacy"]/"telegram-reader-ownership.json",binding)
  private_write(stage/"verification.json",dict(binding,restored=True,reader_started=False,paper_started=False,queue_imported=False))
  return dict(restored=True,owner_verified=True,channel_access_verified=True,reader_started=False,paper_started=False,queue_imported=False)
 except Exception:
  for path in written:path.unlink(missing_ok=True)
  raise
 finally:
  if client:await client.disconnect()
  # Keep the protected staging session as a recovery backup; never print its contents.
