"""Approved one-time recovery of this exact stopped orphan; no broker mutations."""
from pathlib import Path
import json,os,signal,subprocess,sys,time,sqlite3
from urllib.request import urlopen
from urllib.error import HTTPError
ROOT=Path('/home/trading/sector-heatmap');sys.path.insert(0,str(ROOT))
from sector_heatmap.workspaces import WorkspaceStore,WorkspaceRuntime,isolated_environment,private_write
from sector_heatmap.service_restart import runtime_states,stopped_state_paths
from strategies.renko_supertrend.delta_no_send import fingerprint
AID='a6ef4c9bcecd21d54c4a07e2b9b137a7';INSTANCE='b659338b2d1c8d4848e5';TAG='EC3931119f089ce4a649e4'
store=WorkspaceStore(ROOT/'.private/dashboard-login/registry.sqlite3');runtime=WorkspaceRuntime(store,ROOT,8080)
with store.db() as db:account=dict(db.execute('SELECT * FROM accounts WHERE id=?',(AID,)).fetchone())
folder=store.folder(account);source=folder/'source';state=source/'.private/renko-delta-instances'/INSTANCE/'renko-delta-state.json'
d=json.loads(state.read_text());assert d['pending']['tag']==TAG and not d.get('position') and not d['accepting_entries'] and d['squareoff_requested']
for p in runtime_states(source):
 value=json.loads(p.read_text())
 if p!=state:assert not any(value.get(k) for k in ('running','accepting_entries','position','positions','pending','active','loop_running')),str(p)
receipt=json.loads((source/'.private/delta-pre-submit-rejections'/(TAG+'.json')).read_text())
assert receipt['basis']=='OPERATOR_RECONCILED_ORPHAN' and receipt['account_identity']==d['account_identity'] and receipt['order']==fingerprint(d['pending']['order'])
assert 0<=time.time()-receipt['evidence']['checked_at']<300
pid=json.loads((folder/'dashboard-owner.lock').read_text())['pid'];assert (Path('/proc')/str(pid)/'cwd').resolve()==source.resolve()
audit=ROOT/'.private'/('delta-stop-recovery-approved-'+str(int(time.time())));audit.mkdir();private_write(audit/'before.json',state.read_text())
control=folder/'external-supervisor-config.json';prior=control.read_text();private_write(audit/'supervisor-before.json',prior)
private_write(control,json.dumps(dict(enabled=False,reason='Approved orphan reconciliation maintenance')))
phase=folder/'bounce-status.json';private_write(phase,json.dumps(dict(status='CHECKING',updated_at=time.time(),message='Reconciling proven unsubmitted local entry; no financial request.')))
# Identity and pending intent rechecked immediately before the approved scoped reload.
latest=json.loads(state.read_text());assert latest['run_id']==d['run_id'] and latest.get('pending')==d['pending'] and latest.get('position') is None
os.kill(pid,signal.SIGTERM)
deadline=time.monotonic()+15
while runtime.running(AID):
 if time.monotonic()>deadline:raise RuntimeError('Original dashboard did not release ownership; no force kill or replacement sent')
 time.sleep(.1)
command=[sys.executable,str(ROOT/'scripts/reconcile_delta_no_send.py'),'--account',AID,'--instance',INSTANCE,'--tag',TAG,'--offline']
subprocess.run(command,cwd=ROOT,check=True,timeout=90)
stopped_state_paths(source)
env=isolated_environment(account,folder,store.path,8080)
with (folder/'dashboard.log').open('a') as log:child=subprocess.Popen([sys.executable,'heatmap_server.py'],cwd=source,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
deadline=time.monotonic()+45
while time.monotonic()<deadline:
 if child.poll() is not None:raise RuntimeError('Replacement exited; retained audit requires review')
 try:
  owner=json.loads((folder/'dashboard-owner.lock').read_text())['pid']
  assert owner==child.pid
  try:
   with urlopen('http://127.0.0.1:'+str(account['port'])+'/',timeout=1) as r:ready=r.status==200
  except HTTPError as r:ready=r.code in (401,403)
  if ready:break
 except (OSError,ValueError,AssertionError):pass
 time.sleep(.2)
else:raise RuntimeError('Replacement readiness not confirmed; no second launch sent')
stopped_state_paths(source)
private_write(control,prior)
result=dict(status='READY',updated_at=time.time(),message='Orphan no-send intent reconciled. Flat, no pending order, all runners stopped. Automatic proven-no-send recovery active.',pid=child.pid,audit=str(audit))
private_write(phase,json.dumps(result));private_write(audit/'result.json',json.dumps(result,indent=2));print(json.dumps(result))
