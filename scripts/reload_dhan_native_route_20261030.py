from pathlib import Path
import json,time,subprocess,hashlib
root=Path(__file__).resolve().parents[1]
original=(root/'scripts/activate_manual_multi_20261030.py').read_text()
exec(compile(original.split('guard();before=snapshot()')[0],str(root/'scripts/activate_manual_multi_20261030.py'),'exec'))
runtime=WorkspaceRuntime(store,root,8080)
before=json.loads((out/'activation-preserved-before.json').read_text())
guard()
with store.db() as db:accounts=[dict(r) for r in db.execute('SELECT * FROM accounts')]
result=dict(workers=[],main=dict(new_pid=int(subprocess.check_output(['systemctl','show','sector-heatmap.service','-p','MainPID','--value'],text=True)),port=8080,status='active'))
for account in accounts:
 if not runtime.running(account['id']):continue
 # Correct only live dashboard processes whose inherited portal binding differs.
 old=json.loads((store.folder(account)/'dashboard-owner.lock').read_text())['pid']
 environment=(Path('/proc')/str(old)/'environ').read_bytes().split(b'\0')
 portal=next((v.split(b'=',1)[1].decode() for v in environment if v.startswith(b'SECTOR_PULSE_PORTAL_PORT=')),None)
 if account['broker']=='DHAN': # Load precise native amount endpoint permissions.
  guard()
  with store.db() as db:actor=dict(db.execute('SELECT id,username,admin FROM users WHERE id=?',(account['user_id'],)).fetchone())
  state=workspace_bounce.begin(store,runtime,actor,account['id']);deadline=time.monotonic()+85
  while state['status'] in {'CHECKING','RESTARTING','WAITING'}:
   if time.monotonic()>deadline:raise RuntimeError('Worker readiness timed out; no second attempt.')
   time.sleep(1);state=workspace_bounce.status(store,actor,account['id'])
  if state['status']!='READY':raise RuntimeError(state.get('message','Guarded bounce failed'))
 new=json.loads((store.folder(account)/'dashboard-owner.lock').read_text())['pid']
 environment=(Path('/proc')/str(new)/'environ').read_bytes().split(b'\0')
 assert b'SECTOR_PULSE_PORTAL_PORT=8080' in environment
 row=dict(account=account['id'],broker=account['broker'],old_pid=old,new_pid=new,portal_port=8080,status='READY')
 result['workers'].append(row);print(json.dumps(row),flush=True)
guard();after=snapshot()
assert before['grants']==after['grants'],'Account grants changed'
assert before['policies']==after['policies'],'Schedule policy changed'
for path,value in before['runner_configs'].items():assert after['runner_configs'].get(path)==value,'Runner config changed: '+path
retained=root/'.private/dashboard-login/accounts/a6ef4c9bcecd21d54c4a07e2b9b137a7/source/.private/renko-delta-instances/0fa0ae88f933ca46cbe8/renko-delta-state.json'
digest=json.loads((out/'retained-state-before-restart.json').read_text())['sha256']
result['preserved']=dict(grants=True,policies=True,runner_configs=True,all_runners_stopped=True,retained_delta_state_unchanged=hashlib.sha256(retained.read_bytes()).hexdigest()==digest)
(out/'activation-restart-result.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result),flush=True)
