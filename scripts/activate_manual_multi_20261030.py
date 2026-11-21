"""Explicitly approved dashboard activation; existing guards remain authoritative."""
from pathlib import Path
import json,sqlite3,subprocess,time,socket
from sector_heatmap.workspaces import WorkspaceStore,WorkspaceRuntime
from sector_heatmap.service_restart import stopped_state_paths
from sector_heatmap import workspace_bounce
root=Path(__file__).resolve().parents[1];out=root/'output/manual-multi-20261030'
store=WorkspaceStore(root/'.private/dashboard-login/registry.sqlite3')
runtime=WorkspaceRuntime(store,root,8079)
sources=[root,*root.glob('.private/dashboard-login/accounts/*/source')]
def guard():
 for source in sources:stopped_state_paths(source)
 for p in (root/'.private/dashboard-login').rglob('*.sqlite3'):
  if '/source/' in str(p) or any(x in str(p) for x in ('backup','snapshot')):continue
  with sqlite3.connect(p.resolve().as_uri()+'?mode=ro',uri=True) as db:
   tables=[r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
   for table in tables:
    if not table.replace('_','').isalnum():continue
    cols=[r[1] for r in db.execute('PRAGMA table_info("'+table+'")')]
    if 'state' in cols:
     count=db.execute('SELECT count(*) FROM "'+table+'" WHERE upper(state) IN (?,?,?,?,?)',('SUBMITTING','UNCERTAIN','PROTECTION_PENDING','EXECUTION_STATUS_UNCERTAIN','SUBMISSION_UNCERTAIN')).fetchone()[0]
     if count:raise RuntimeError('Unresolved order state blocks activation: '+p.name+'/'+table)
    if table=='batches' and 'data' in cols:
     for (data,) in db.execute('SELECT data FROM batches'):
      if any(r.get('state') in ('SUBMITTING','UNCERTAIN') for r in json.loads(data).get('rows',[])):raise RuntimeError('Manual broker submission requires reconciliation.')
def snapshot():
 with store.db() as db:grants=[dict(r) for r in db.execute('SELECT id,broker,live_enabled FROM accounts ORDER BY id')]
 policies={}
 for p in (root/'.private/dashboard-login/accounts').glob('*/handoff-schedule.sqlite3'):
  with sqlite3.connect(p.resolve().as_uri()+'?mode=ro',uri=True) as db:
   row=db.execute('SELECT body FROM policy WHERE id=1').fetchone()
   if row:policies[p.parent.name]=json.loads(row[0])
 configs={}
 for source in sources:
  for p in stopped_state_paths(source):
   value=json.loads(p.read_text());configs[str(p.relative_to(root))]=value.get('config')
 return dict(grants=grants,policies=policies,runner_configs=configs)
guard();before=snapshot()
p=out/'activation-preserved-before.json';p.write_text(json.dumps(before,indent=2));p.chmod(0o600)
with store.db() as db:accounts=[dict(r) for r in db.execute('SELECT * FROM accounts')]
running=[a for a in accounts if runtime.running(a['id'])]
for account in running:
 if account['broker'] not in {'DHAN','FYERS','DELTA_INDIA'}:raise RuntimeError('Unexpected running broker; activation scope needs review.')
 workspace_bounce.reload_states(store.folder(account)/'source',account['broker'])
result=dict(workers=[],main={})
for account in running:
 guard()
 with store.db() as db:actor=dict(db.execute('SELECT id,username,admin FROM users WHERE id=?',(account['user_id'],)).fetchone())
 if not actor['admin']:raise RuntimeError('Owned administrator identity required by existing bounce guard.')
 old=json.loads((store.folder(account)/'dashboard-owner.lock').read_text())['pid']
 state=workspace_bounce.begin(store,runtime,actor,account['id'])
 deadline=time.monotonic()+85
 while state['status'] in {'CHECKING','RESTARTING','WAITING'}:
  if time.monotonic()>deadline:raise RuntimeError('Worker bounce timed out; no second attempt sent.')
  time.sleep(1);state=workspace_bounce.status(store,actor,account['id'])
 if state['status']!='READY':raise RuntimeError('Existing broker guard failed: '+state.get('message',''))
 new=json.loads((store.folder(account)/'dashboard-owner.lock').read_text())['pid']
 row=dict(account=account['id'],broker=account['broker'],old_pid=old,new_pid=new,status=state['status'])
 result['workers'].append(row);print(json.dumps(row),flush=True)
 (out/'activation-restart-progress.json').write_text(json.dumps(result,indent=2))
guard()
old=int(subprocess.check_output(['systemctl','show','sector-heatmap.service','-p','MainPID','--value'],text=True))
subprocess.run(['sudo','-n','systemctl','restart','sector-heatmap.service'],check=True,timeout=60)
new=int(subprocess.check_output(['systemctl','show','sector-heatmap.service','-p','MainPID','--value'],text=True))
for _ in range(100):
 try:
  with socket.create_connection(('127.0.0.1',8079),timeout=.25):break
 except OSError:time.sleep(.3)
else:raise RuntimeError('Main dashboard listener did not recover.')
guard();after=snapshot()
assert before['grants']==after['grants'],'Account grants changed'
assert before['policies']==after['policies'],'Schedule policy changed'
for path,value in before['runner_configs'].items():assert after['runner_configs'].get(path)==value,'Runner config changed: '+path
assert old!=new and new>0
result['main']=dict(old_pid=old,new_pid=new,status='active')
result['preserved']=dict(grants=True,policies=True,runner_configs=True,all_runners_stopped=True)
(out/'activation-restart-result.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result),flush=True)
