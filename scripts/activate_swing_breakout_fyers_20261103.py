"""Operator audit/activation for the explicitly approved FYERS Renko swing gate.
Uses the existing account-scoped guarded reload and normal authenticated API.
No direct broker order methods. Other accounts and runner settings are retained.
"""
import os,sys,json,time,hashlib,argparse,subprocess,secrets,urllib.request
from pathlib import Path
ROOT=Path('/home/trading/sector-heatmap')
AID='bf46fc364b610a0dfd338419e133cb41'
INSTANCE='ebd4221ba77d52b60d29'
BASE=ROOT/'.private/dashboard-login/accounts'/AID
SOURCE=BASE/'source'
STATE=SOURCE/'.private/renko-instances'/INSTANCE/'state.json'
OUT=ROOT/'.private/swing-breakout-activation-20261103'
OUT.mkdir(mode=0o700,exist_ok=True)
owner=json.loads((BASE/'dashboard-owner.lock').read_text())['pid']
assert Path(f'/proc/{owner}/cwd').resolve()==SOURCE
current_env=dict(v.split('=',1) for v in Path(f'/proc/{owner}/environ').read_text().split('\0') if '=' in v)
for key in ('SECTOR_PULSE_WORKSPACE_REGISTRY','SECTOR_PULSE_WORKSPACE_ID','SECTOR_PULSE_WORKSPACE_BROKER','SECTOR_PULSE_WORKSPACE_USER_ID','FYERS_TOKEN_FILE','XDG_CONFIG_HOME'):
 if key in current_env:os.environ[key]=current_env[key]
os.chdir(SOURCE);sys.path.insert(0,str(SOURCE))
from sector_heatmap.workspaces import WorkspaceStore,WorkspaceRuntime,private_write
from sector_heatmap.service_restart import runtime_states,stopped_state_paths
from sector_heatmap.fyers_execution import _current_client
from sector_heatmap.fyers_history import account_read
store=WorkspaceStore(ROOT/'.private/dashboard-login/registry.sqlite3')
with store.db() as db:
 account=dict(db.execute('SELECT * FROM accounts WHERE id=?',(AID,)).fetchone())
 actor=dict(db.execute('SELECT id,username,admin FROM users WHERE id=?',(account['user_id'],)).fetchone())
assert account['broker']=='FYERS' and actor['username']=='pinaki87' and actor['admin']

def audit():
 state=json.loads(STATE.read_text());c=state['config']
 assert c['underlying']=='MCX:CRUDEOILM26NOVFUT' and c['timeframe']=='5 minutes' and c['mode']=='LIVE' and c['lots']==1
 client=_current_client();profile=account_read(client,'get_profile');positions=account_read(client,'positions');orders=account_read(client,'orderbook')
 if any(x.get('s')!='ok' for x in (profile,positions,orders)):raise ValueError('Fresh broker authentication/positions/orders unavailable')
 identity=hashlib.sha256(str(profile['data']['fy_id']).encode()).hexdigest()
 if identity!=state.get('account_identity'):raise ValueError('Broker identity differs from captured runner')
 prefix='MCX:CRUDEOILM26NOV'
 held=[{k:r.get(k) for k in ('symbol','netQty','productType')} for r in positions.get('netPositions',[]) if r.get('symbol','').startswith(prefix) and float(r.get('netQty',0))]
 pending=[{k:r.get(k) for k in ('symbol','status','qty','filledQty','id')} for r in orders.get('orderBook',[]) if r.get('symbol','').startswith(prefix) and int(r.get('status',0)) not in (1,2,5,7)]
 # Read-only WebSocket establishes exchange freshness; REST `tt` is a
 # session-level timestamp and is not evidence of the latest observed tick.
 from strategies.renko_supertrend.runner import Broker
 stream=Broker(SOURCE/'.private/ema-band-masters',lambda *a:[],lambda *a:None)
 stream.symbols.add(c['underlying']);stream.start();deadline=time.monotonic()+15
 try:
  while True:
   try:
    price,stamp=stream.live_price(c,time.time());break
   except ValueError:
    if time.monotonic()>deadline:raise ValueError('Fresh FYERS WebSocket observation unavailable')
    time.sleep(.2)
  q={'lp':price}
 finally:stream.stop()
 summary=dict(checked_at=time.time(),owner_pid=owner,account_id=AID,broker='FYERS',identity_matches=True,runner=INSTANCE,running=state.get('running'),accepting_entries=state.get('accepting_entries'),position=bool(state.get('position')),pending=bool(state.get('pending')),broker_positions=held,broker_pending_orders=pending,underlying=c['underlying'],timeframe=c['timeframe'],mode=c['mode'],lots=c['lots'],quote_price=q.get('lp'),quote_age_seconds=round(time.time()-float(stamp),2))
 private_write(OUT/'latest-preflight.json',json.dumps(summary,indent=2))
 if held or pending or state.get('position') or state.get('pending'):raise ValueError('Affected runner has exposure/pending orders; activation stopped')
 print(json.dumps(summary),flush=True)
 return state

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['audit','reload','activate','status']);args=parser.parse_args()
 if args.phase=='audit':audit()
 elif args.phase=='reload':
  before=audit()
  if before.get('running') or before.get('accepting_entries'):raise ValueError('Runner now active; stop through the normal authorized route before reload')
  stopped_state_paths(SOURCE)
  private_write(OUT/'before-state.json',json.dumps(before))
  private_write(OUT/'other-runtime-before.json',json.dumps({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in runtime_states(SOURCE) if p!=STATE}))
  from sector_heatmap import workspace_bounce
  runtime=WorkspaceRuntime(store,ROOT,int(current_env['SECTOR_PULSE_PORTAL_PORT']))
  result=workspace_bounce.begin(store,runtime,actor,AID);deadline=time.monotonic()+80
  print(json.dumps(result),flush=True)
  while result['status'] in {'CHECKING','RESTARTING','WAITING'}:
   if time.monotonic()>deadline:raise RuntimeError('Reload did not settle; no second attempt')
   time.sleep(1);result=workspace_bounce.status(store,actor,AID)
  private_write(OUT/'reload-result.json',json.dumps(result,indent=2));print(json.dumps(result),flush=True)
  if result['status']!='READY':raise ValueError('Guarded reload failed')
 else:
  # Short-lived operator session for this existing owner. Never printed or stored
  # outside the normal session registry; revoked in finally after the API call.
  token=secrets.token_urlsafe(32);digest=hashlib.sha256(token.encode()).hexdigest();csrf=secrets.token_urlsafe(32)
  with store.db() as db:db.execute('INSERT INTO sessions VALUES(?,?,?,?)',(digest,actor['id'],csrf,time.time()+180))
  host='127.0.0.1:'+str(account['port'])
  def request(path,payload=None):
   body=None if payload is None else json.dumps(payload).encode()
   req=urllib.request.Request('http://'+host+path,data=body,headers={'Cookie':'sector_pulse_session='+token,'Origin':'http://'+host,'Content-Type':'application/json','X-CSRF-Token':csrf})
   with urllib.request.urlopen(req,timeout=120) as r:return json.load(r)
  try:
   status=request('/api/renko-supertrend/runner?instance='+INSTANCE)
   if status.get('swing_breakout_revision')!='renko-swing-breakout-v1':raise ValueError('Reloaded capability missing')
   if args.phase=='activate':
    before=audit()
    if before.get('running') or before.get('accepting_entries'):raise ValueError('Already running: no duplicate Start')
    payload={**before['config'],'swing_breakout_bricks':2,'broker':'FYERS','account_id':AID,'symbol':before['config']['underlying'],'configuration_revision':status['runtime_revision']}
    # Require normalization to retain every existing configuration value.
    from strategies.renko_supertrend.runner import configuration
    normalized=configuration(payload)
    changes={k:{'before':v,'after':normalized.get(k)} for k,v in before['config'].items() if normalized.get(k)!=v and k not in {'session_segment','session_exchange','session_open','session_deadline','requested_deadline','session_source','master_regular_session'}}
    if changes:raise ValueError('Unexpected normalized settings changes: '+json.dumps(changes))
    result=request('/api/renko-supertrend/start?instance='+INSTANCE,payload)
    private_write(OUT/'activation-response.json',json.dumps(result))
    # Persist the same choice into the existing per-instrument preference record.
    prefs=request('/api/renko-supertrend/settings?instance='+INSTANCE)
    values=dict(prefs.get('settings',{}));values['swing-breakout-bricks']=2
    request('/api/renko-supertrend/settings?instance='+INSTANCE,{'settings':values,'broker':'FYERS','account_id':AID,'symbol':payload['underlying']})
    status=request('/api/renko-supertrend/runner?instance='+INSTANCE)
   private_write(OUT/'latest-status.json',json.dumps(status))
   print(json.dumps({k:status.get(k) for k in ('running','accepting_entries','run_id','swing_breakout_revision','position','pending','latest_entry_assessment','message')}),flush=True)
  finally:
   with store.db() as db:db.execute('DELETE FROM sessions WHERE digest=?',(digest,))
