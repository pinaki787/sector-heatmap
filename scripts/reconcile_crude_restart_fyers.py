"""Authorized offline historical-fill reconciliation and account-only reload.
Never exposes an order submission API. Original state and evidence are retained.
"""
import os,json,time,signal,subprocess,fcntl,runpy,hashlib,sys
from pathlib import Path
ROOT=Path('/home/trading/sector-heatmap')
AID='bf46fc364b610a0dfd338419e133cb41'
BASE=ROOT/'.private/dashboard-login/accounts'/AID
SOURCE=BASE/'source'
PID=205994
STATE=SOURCE/'.private/renko-instances/4a8a4fa8e499c1b20def/state.json'
EVIDENCE=ROOT/'.private/crude-close-evidence-20261022.json'
def main():
 if (Path('/proc')/str(PID)/'cwd').resolve()!=SOURCE.resolve():raise ValueError('FYERS process identity changed')
 env=dict(item.split('=',1) for item in Path(f'/proc/{PID}/environ').read_text().split('\0') if '=' in item)
 for key in ['SECTOR_PULSE_WORKSPACE_REGISTRY','SECTOR_PULSE_WORKSPACE_ID','SECTOR_PULSE_WORKSPACE_BROKER','FYERS_TOKEN_FILE','XDG_CONFIG_HOME']:
  if key in env:os.environ[key]=env[key]
 os.chdir(SOURCE);sys.path.insert(0,str(SOURCE))
 from sector_heatmap.fyers_execution import _current_client
 from sector_heatmap.service_restart import runtime_states,stopped_state_paths
 from sector_heatmap.workspaces import private_write
 from sector_heatmap.runner_job_history import record
 client=_current_client()
 prepare=runpy.run_path(str(ROOT/'scripts/reconcile_confirmed_crude.py'))['prepare']
 original=json.loads(STATE.read_text())
 from strategies.ema_crossover.external_close import confirmed_close
 proof=confirmed_close(original['position'],[],json.loads(EVIDENCE.read_text())['orders'])
 if original.get('pending'):raise ValueError('Pending intent blocks repair')
 for path in runtime_states(SOURCE):
  state=json.loads(path.read_text())
  if path.resolve()==STATE.resolve():continue
  if any(state.get(k) for k in ['running','accepting_entries','position','positions','pending','active','loop_running']):
   raise ValueError('Another active strategy prevents this reload: '+str(path.relative_to(SOURCE)))
 audit=ROOT/'.private'/('fyers-reconciliation-reload-'+time.strftime('%Y%m%dT%H%M%SZ',time.gmtime()))
 audit.mkdir(mode=0o700)
 private_write(audit/'original-state.json',json.dumps(original))
 private_write(audit/'evidence.json',EVIDENCE.read_text())
 ready=audit/'ready'
 # Replacement holds account ownership while offline reconciliation finishes.
 wrapper="""import os,time,runpy
from pathlib import Path
from sector_heatmap import workspace_guard as module
from sector_heatmap.workspace_guard import WorkspaceGuard
original=module.lock_file
module.lock_file=lambda fd,blocking=False:original(fd,blocking=True)
guard=WorkspaceGuard.from_environment()
module.lock_file=original
deadline=time.monotonic()+45
while not Path(os.environ['SECTOR_PULSE_REPAIR_READY']).exists():
 if time.monotonic()>deadline:raise RuntimeError('Offline repair readiness timeout; no runner armed')
 time.sleep(.1)
factory=WorkspaceGuard.from_environment
def existing(cls):
 WorkspaceGuard.from_environment=factory
 return guard
WorkspaceGuard.from_environment=classmethod(existing)
runpy.run_path('heatmap_server.py',run_name='__main__')
"""
 launch_env={**env,'SECTOR_PULSE_REPAIR_READY':str(ready)}
 frozen=False;replacement=None;terminated=False
 try:
  os.kill(PID,signal.SIGSTOP);frozen=True
  # The process cannot overwrite state while the final evidence is checked.
  check=json.loads(STATE.read_text())
  if check.get('run_id')!=original.get('run_id') or check.get('position')!=original.get('position') or check.get('pending'):
   raise ValueError('Ownership changed before reconciliation')
  print('FYERS worker paused; allowing one rate-limit window before final fresh evidence checks.',flush=True)
  time.sleep(35);time.sleep(35)
  original,final,proof=prepare(STATE,EVIDENCE,client)
  private_write(audit/'quiesced-original-state.json',json.dumps(original))
  with open(BASE/'dashboard.log','a') as log:
   replacement=subprocess.Popen([str(ROOT/'.venv/bin/python'),'-B','-c',wrapper],cwd=SOURCE,env=launch_env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  time.sleep(.2)
  if replacement.poll() is not None:raise ValueError('Replacement failed before handoff')
  os.kill(PID,signal.SIGTERM);os.kill(PID,signal.SIGCONT);frozen=False
  deadline=time.monotonic()+10
  while time.monotonic()<deadline:
   try:
    stat=Path(f'/proc/{PID}/stat').read_text()
    if stat.split(') ',1)[1].startswith('Z'):break
   except FileNotFoundError:break
   time.sleep(.1)
  else:raise ValueError('Old process did not exit; no state rewrite')
  terminated=True
  with open(STATE.with_suffix('.lock'),'a') as lock:
   fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
   # Persist only the result of the existing confirmed-close reconciliation.
   private_write(STATE,json.dumps(final,allow_nan=False))
   record(STATE,final)
   stopped_state_paths(SOURCE)
   private_write(audit/'final-state.json',json.dumps(final,allow_nan=False))
   private_write(ready,'confirmed historical fill reconciled; all runners stopped')
  report={'old_pid':PID,'new_pid':replacement.pid,'status':'WAITING','confirmed_exit_order_id':proof['order_id'],'exit_price':proof['price'],'broker_orders_submitted':0,'audit_directory':str(audit)}
  private_write(audit/'result.json',json.dumps(report))
  print(json.dumps(report),flush=True)
 except Exception:
  if frozen:
   os.kill(PID,signal.SIGCONT)
  if replacement and replacement.poll() is None and not terminated:replacement.terminate()
  raise
if __name__=='__main__':main()
